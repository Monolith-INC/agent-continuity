#!/usr/bin/env python3
"""Upgrade session records that are not in the current format.

Usage: reconcile_sessions.py [--project DIR] [--apply]

Current format, per record in Agent_Sessions/:
- frontmatter with `date`, `type` and a valid `status` (ongoing | closed | archived);
- only the newest record that is not archived may be `ongoing`; older ones are `closed`;
- every record except the newest links forward to its successor ([[next-record]]).

Without --apply it only lists what it would change. With --apply it writes the
changes, keeps each original as <vault>/.agent-continuity/backups/<stamp>/<name>.md.bak,
and refreshes the session index. Only the frontmatter block and a trailing
"Next session" link are touched. Unreadable records are left alone.

The SessionStart hook runs this automatically (apply, then report) when it finds
old-format records or when the plugin version changed since the last session.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import (  # noqa: E402
    FRONTMATTER,
    SessionRecord,
    chain_head,
    load_config,
    load_index,
    read_record,
    record_paths,
    refresh,
    resolve_vault,
    save_index,
    sessions_folder,
    state_dir,
)


@dataclass(frozen=True)
class Change:
    name: str
    text: str
    reasons: tuple[str, ...]


def has_key(lines: list[str], key: str) -> bool:
    return any(re.match(rf"^{key}\s*:", line) for line in lines)


def set_frontmatter(text: str, name: str, status: str) -> str:
    """Set `status` and add a missing `date` / `type`, leaving every other line as it was."""
    block = FRONTMATTER.match(text)
    lines = block.group(1).splitlines() if block else []
    kept = [line for line in lines if not re.match(r"^status\s*:", line)]
    added = (
        ([] if has_key(kept, "date") else [f"date: {name[:10]}"])
        + ([] if has_key(kept, "type") else ["type: session"])
        + [f"status: {status}"]
    )
    body = "\n".join(kept + added)
    return (
        text[: block.start(1)] + body + text[block.end(1):]
        if block else f"---\n{body}\n---\n" + text
    )


def target_status(record: SessionRecord, head: SessionRecord | None) -> str:
    match (record.status, record is head):
        case ("ongoing", True):
            return "ongoing"
        case ("ongoing", False):
            return "closed"
        case (status, _):
            return status


def change_for(record: SessionRecord, text: str, head: SessionRecord | None, successor: str) -> Change | None:
    status = target_status(record, head)
    needs_link = bool(successor) and not record.forward
    reasons = tuple(
        reason for fired, reason in (
            (not record.explicit, f"added status: {status}"),
            (record.explicit and status != record.status, f"status {record.status} -> {status} (only the newest record can be ongoing)"),
            (needs_link, f"added forward link to {successor}"),
        ) if fired
    )
    updated = set_frontmatter(text, record.name, status) if (not record.explicit or status != record.status) else text
    linked = updated.rstrip("\n") + f"\n\nNext session: [[{successor}]]\n" if needs_link else updated
    return Change(record.name, linked, reasons) if reasons else None


def plan(sessions: Path) -> tuple[Change, ...]:
    paths = record_paths(sessions)
    names = sorted(paths, reverse=True)
    records = tuple(read_record(paths[n]) for n in names)
    head = chain_head(records)
    successors = dict(zip(names[1:], names))
    changes = (
        change_for(r, paths[r.name].read_text(encoding="utf-8"), head, successors.get(r.name, ""))
        for r in records if r.readable
    )
    return tuple(c for c in changes if c)


def apply(vault: Path, sessions: Path, changes: tuple[Change, ...], stamp: str) -> Path:
    backup = state_dir(vault) / "backups" / stamp
    backup.mkdir(parents=True, exist_ok=True)
    for change in changes:
        path = sessions / f"{change.name}.md"
        (backup / f"{change.name}.md.bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(change.text, encoding="utf-8")
    return backup


def plural(count: int) -> str:
    return f"{count} old-format session record" + ("" if count == 1 else "s")


def describe(changes: tuple[Change, ...]) -> str:
    return "\n".join(f"   - {c.name}: {'; '.join(c.reasons)}" for c in changes)


def report(changes: tuple[Change, ...], backup: Path, root: Path) -> str:
    where = backup.relative_to(root) if root in backup.parents else backup
    return f"Upgraded {plural(len(changes))} to the current format (originals kept in {where}/):\n" + describe(changes)


def reconcile(vault: Path, sessions: Path, root: Path) -> str:
    """Apply every pending change, refresh the index, and return a report ('' if nothing to do)."""
    changes = plan(sessions)
    match changes:
        case ():
            return ""
        case _:
            backup = apply(vault, sessions, changes, datetime.now().strftime("%Y%m%d-%H%M%S"))
            index = load_index(vault)
            save_index(vault, {**index, "records": refresh(sessions, index, full=True)})
            return report(changes, backup, root)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Upgrade old-format session records.")
    parser.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    parser.add_argument("--apply", action="store_true", help="write the changes (default: only list them)")
    args = parser.parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    config = load_config(project)
    vault, notice = resolve_vault(project, config)
    sessions, folder_notice = sessions_folder(vault, config) if vault else (None, "")
    notes = "\n".join(n for n in (notice, folder_notice) if n)
    match (sessions, args.apply):
        case (None, _):
            print(notes or f"No vault found in {project}.")
            return 0
        case (folder, _) if not folder.is_dir():
            print(f"No session folder at {folder}.")
            return 0
        case (folder, True):
            print((notes + "\n" if notes else "") + (reconcile(vault, folder, project) or "Session records are already in the current format."))
        case (folder, False):
            changes = plan(folder)
            print(
                (notes + "\n" if notes else "")
                + (f"Would upgrade {plural(len(changes))} (run again with --apply):\n" + describe(changes)
                   if changes else "Session records are already in the current format.")
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
