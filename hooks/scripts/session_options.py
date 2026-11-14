#!/usr/bin/env python3
"""Build the SessionStart menu from the newest records in Agent_Sessions/.

Usage: session_options.py <sessions-folder> [recent-count]

Prints a short menu (resume the newest unfinished session, pick one of the
last few, or start fresh) for the agent to show the user. Prints nothing when
the folder holds no session records, so the hook stays silent.

Each record carries `status: ongoing | closed | archived` in its frontmatter.
Archived records are left out of the menu. A record without a valid status
falls back to the older rule: it is ongoing when it has no wikilink forward to
a newer record. Records are named YYYY-MM-DD-HHMMSS-slug, so name order is
time order.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterator

RECORD_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}-[a-z0-9-]+$")
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER = re.compile(r"^\ufeff?---\s*\n(.*?)\n---\s*(\n|$)", re.S)
STATUS_LINE = re.compile(r"^status\s*:\s*['\"]?([A-Za-z]+)['\"]?\s*$", re.MULTILINE)
STATUSES = ("ongoing", "closed", "archived")
DEFAULT_RECENT = 3


@dataclass(frozen=True)
class SessionRecord:
    name: str
    title: str
    status: str

    @property
    def unfinished(self) -> bool:
        return self.status == "ongoing"


def slug_title(name: str) -> str:
    return name[len("YYYY-MM-DD-HHMMSS-"):].replace("-", " ")


def linked_names(text: str) -> tuple[str, ...]:
    return tuple(Path(target.strip()).stem for target in WIKILINK.findall(text))


def is_unfinished(name: str, text: str) -> bool:
    return not any(RECORD_NAME.match(link) and link > name for link in linked_names(text))


def read_status(text: str) -> str:
    block = FRONTMATTER.match(text)
    found = STATUS_LINE.search(block.group(1)) if block else None
    value = found.group(1).lower() if found else ""
    return value if value in STATUSES else ""


def read_record(path: Path) -> SessionRecord:
    text = path.read_text(encoding="utf-8", errors="replace")
    heading = HEADING.search(text)
    fallback = "ongoing" if is_unfinished(path.stem, text) else "closed"
    return SessionRecord(
        name=path.stem,
        title=heading.group(1) if heading else slug_title(path.stem),
        status=read_status(text) or fallback,
    )


def all_records(folder: Path) -> Iterator[SessionRecord]:
    """Every record, newest first, read lazily so callers can stop early."""
    paths = sorted(
        (p for p in folder.glob("*.md") if RECORD_NAME.match(p.stem)),
        key=lambda p: p.stem,
        reverse=True,
    ) if folder.is_dir() else []
    return (read_record(p) for p in paths)


def recent_records(folder: Path, limit: int) -> tuple[SessionRecord, ...]:
    live = (r for r in all_records(folder) if r.status != "archived")
    return tuple(islice(live, max(limit, 0)))


def describe(record: SessionRecord) -> str:
    return f"{record.name} ({record.title}) [{record.status}]"


def build_menu(records: tuple[SessionRecord, ...]) -> str:
    unfinished = next((r for r in records if r.unfinished), None)
    resume = (
        (f"Resume the most recent ongoing session: {describe(unfinished)}",)
        if unfinished else ()
    )
    pick = (
        f"Pick a recent session (last {len(records)}, newest first):\n"
        + "\n".join(f"   - {describe(r)}" for r in records),
    )
    fresh = ("Start fresh: open a new session record.",)
    options = resume + pick + fresh
    return "" if not records else "\n".join(
        (
            "=== Session start options (from Agent_Sessions/) ===",
            "Before any other work, show the user these options and wait for their choice.",
            "Read only the record they pick; do not load older records unless asked.",
            *(f"{i}. {text}" for i, text in enumerate(options, start=1)),
        )
    )


def parse_limit(args: list[str]) -> int:
    raw = args[0] if args else ""
    return int(raw) if raw.isdigit() else DEFAULT_RECENT


def main(argv: list[str]) -> int:
    menu = build_menu(recent_records(Path(argv[0]), parse_limit(argv[1:]))) if argv else ""
    sys.stdout.write(menu + ("\n" if menu else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
