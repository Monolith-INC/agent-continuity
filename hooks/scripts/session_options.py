#!/usr/bin/env python3
"""SessionStart: load the session registry once and build the start menu.

Usage: session_options.py [project-dir]   (defaults to $CLAUDE_PROJECT_DIR or cwd)

Steps, all fail-open:
1. Find the vault (it must sit inside the project; a bad setting falls back to the
   default folder and the agent is told to ask the user for the right one).
2. Refresh the session index (re-reads only records whose file changed).
3. Upgrade old-format records (apply, then report) when any are found or when the
   plugin version changed since the last session. See reconcile_sessions.py.
4. Save a git snapshot so the Stop hook only counts work done in this session, and
   remember the checkout the ongoing session runs in.
5. Print the menu: resume / pick a recent session / start fresh, adjusted for a
   session past the 8-hour cap, a different checkout, or an unreadable record.

Prints nothing when there is no vault and nothing to report.
Config: vault.sessionOptions.{enabled, recent (default 3), folder (default Agent_Sessions)}.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconcile_sessions import reconcile  # noqa: E402
from registry import (  # noqa: E402
    MAX_SESSION_HOURS,
    SessionRecord,
    broken_head,
    checkout_of,
    git_state,
    last_readable,
    live,
    load_config,
    load_index,
    needs_reconcile,
    ongoing_of,
    over_cap,
    plugin_version,
    records_of,
    refresh,
    resolve_vault,
    save_index,
    sessions_folder,
    track_checkout,
)

DEFAULT_RECENT = 3


@dataclass(frozen=True)
class StartView:
    recent: tuple[SessionRecord, ...]
    ongoing: SessionRecord | None
    capped: bool
    moved: str
    broken: SessionRecord | None
    fallback: SessionRecord | None
    notes: tuple[str, ...]


def describe(record: SessionRecord) -> str:
    return f"{record.name} ({record.title})"


def moved_note(checkout: dict, state: dict | None) -> str:
    now = checkout_of(state)
    then = {k: checkout.get(k, "") for k in now}
    return "" if not state or not any(then.values()) or then == now else (
        f"It ran on branch {then['branch'] or '?'} in {then['worktree'] or '?'}, and this checkout is on "
        f"branch {now['branch'] or '?'} in {now['worktree'] or '?'}. "
        "Ask the user whether to close it and start a new session before resuming."
    )


def first_option(view: StartView) -> tuple[str, ...]:
    match view:
        case StartView(broken=SessionRecord() as bad, fallback=SessionRecord() as good):
            return (
                f"Continue from {describe(good)} in a new session: {bad.name} can't be read ({bad.problem}). "
                f"Do this without asking the user about it: open a new record with `status: ongoing` and a "
                f"backlink to {good.name}, add one line noting the problem with {bad.name}, and carry on.",
            )
        case StartView(ongoing=SessionRecord() as current, capped=True):
            return (
                f"Continue in a new session linked to {describe(current)}: it has run more than "
                f"{MAX_SESSION_HOURS} hours, so close it first (`status: closed` plus a forward link), "
                "then open a new record with `status: ongoing` and a backlink to it.",
            )
        case StartView(ongoing=SessionRecord() as current, moved=note):
            return (f"Resume the ongoing session: {describe(current)}" + (f". {note}" if note else ""),)
        case _:
            return ()


def build_menu(view: StartView) -> str:
    pick = (
        (f"Pick a recent session (last {len(view.recent)}, newest first):\n"
         + "\n".join(f"   - {describe(r)} [{r.status}]" for r in view.recent)),
    ) if view.recent else ()
    fresh = ("Start fresh: close any ongoing record, then open a new one with `status: ongoing` "
             "and a backlink to the newest record.",)
    options = first_option(view) + pick + fresh
    return "\n".join((
        "=== Session start options (from Agent_Sessions/) ===",
        "Before any other work, show the user these options and wait for their choice.",
        "Read only the record they pick; do not load older records unless asked.",
        *(f"Note: {n}" for n in view.notes),
        *(f"{i}. {text}" for i, text in enumerate(options, start=1)),
    ))


def parse_limit(raw: object) -> int:
    return raw if isinstance(raw, int) and raw >= 0 else int(raw) if str(raw).isdigit() else DEFAULT_RECENT


def start(project: Path) -> str:
    config = load_config(project)
    options = (config.get("vault") or {}).get("sessionOptions") or {}
    enabled = options.get("enabled", True) is not False
    vault, vault_notice = resolve_vault(project, config)
    sessions, folder_notice = sessions_folder(vault, config) if vault else (None, "")
    notices = tuple(n for n in (vault_notice, folder_notice) if n)
    match sessions:
        case None:
            return "\n".join(f"Note: {n}" for n in notices)
        case folder if not folder.is_dir():
            return "\n".join(f"Note: {n}" for n in notices)
        case _:
            pass

    index = load_index(vault)
    records = refresh(sessions, index, full=True)
    version = plugin_version()
    upgrade = index.get("plugin") != version or needs_reconcile(records)
    report = reconcile(vault, sessions, project) if upgrade else ""
    index = load_index(vault) if report else index
    records = records_of(index) if report else records

    state = git_state(project, vault)
    ongoing = ongoing_of(records)
    checkout = track_checkout(index, ongoing, state)
    capped = bool(ongoing) and over_cap(ongoing.name)
    save_index(vault, {
        **index,
        "records": records,
        "plugin": version,
        "ongoing": ongoing.name if ongoing else None,
        "checkout": checkout,
        "snapshot": {**state, "at": time.time()} if state else None,
        "cap_notified": ongoing.name if capped else index.get("cap_notified"),
    })

    limit = parse_limit(options.get("recent", DEFAULT_RECENT))
    view = StartView(
        recent=live(records)[:limit],
        ongoing=ongoing,
        capped=capped,
        moved=moved_note(checkout, state) if ongoing else "",
        broken=broken_head(records),
        fallback=last_readable(records),
        notes=notices + ((f"{report}\nMention this upgrade to the user in one line.",) if report else ()),
    )
    return build_menu(view) if enabled and records else "\n".join(f"Note: {n}" for n in view.notes if enabled)


def main(argv: list[str]) -> int:
    project = Path(argv[0] if argv else os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    try:
        menu = start(project)
    except Exception as error:  # fail-open: a hook must never stop the session
        menu = f"Note: the session start menu could not be built ({type(error).__name__}: {error})."
    sys.stdout.write(menu + ("\n" if menu else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
