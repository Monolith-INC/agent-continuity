#!/usr/bin/env python3
"""Keep the session registry (Agent_Sessions/) fresh while an agent works.

Usage: session_freshness.py stop|prompt   (hook input JSON on stdin)

stop    Stop hook. Compares the code now with the git snapshot saved at the last
        check (see registry.py) and blocks the stop once when a checkpoint rule fired:
          - first change to a file          - a new commit
          - a commit rolled back or amended - a push
        It stays quiet when the ongoing record was already updated since the last
        check. It also asks once to roll over a session older than 8 hours, to open
        a record when none is ongoing, and to recover (without asking the user) when
        the newest record can't be read. Never blocks twice in a row.
        Plan tasks, code reviews and the end of a session are not visible to git;
        the session rules in init-workspace cover those.
prompt  UserPromptSubmit hook. While a record is ongoing, adds a one-line reminder
        to log a Decision entry if the user's message settles one. Reads only the
        index, never the records.

Silent (fail-open) when there is no vault, no git repository, or the config
turns it off: .claude/agent-continuity.config.json -> {"vault":{"freshness":{"enabled":false}}}.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry import (  # noqa: E402
    MAX_SESSION_HOURS,
    SessionRecord,
    broken_head,
    git_state,
    is_ancestor,
    last_readable,
    load_config,
    load_index,
    ongoing_of,
    over_cap,
    refresh,
    resolve_vault,
    save_index,
    sessions_folder,
    track_checkout,
    triggers,
)


def heads_related(project: Path, before: dict, now: dict) -> bool:
    old, new = before.get("head") or "", now.get("head") or ""
    return True if not old or not new or old == new else is_ancestor(project, old, new)


def stop_reasons(
    rel: str,
    fired: tuple[str, ...],
    ongoing: SessionRecord | None,
    touched: bool,
    capped: bool,
    broken: SessionRecord | None,
    fallback: SessionRecord | None,
) -> tuple[str, ...]:
    due = "; ".join(fired)
    cap = (
        f"Session registry: {rel}/{ongoing.name}.md has run more than {MAX_SESSION_HOURS} hours. "
        "Close it (`status: closed` plus a forward link), open a new record with `status: ongoing` "
        "and a backlink to it, and continue there.",
    ) if capped and ongoing else ()
    match (bool(fired), ongoing, broken):
        case (False, _, _):
            work = ()
        case (True, SessionRecord() as current, _):
            work = () if touched else (
                f"Session registry: checkpoint due ({due}). Append an `## Implementation Checkpoint - <timestamp>` "
                f"(Scope / Changes / Validation) to {rel}/{current.name}.md, then finish.",
            )
        case (True, None, SessionRecord() as bad):
            link = f"a backlink to {fallback.name}" if fallback else "a note that no readable record was left"
            work = (
                f"Session registry: {bad.name} can't be read ({bad.problem}). Without asking the user, open a new "
                f"record in {rel}/ with `status: ongoing` and {link}, "
                f"add one line noting the problem with {bad.name}, log this work ({due}), then finish.",
            )
        case _:
            work = (
                f"Session registry: work happened ({due}) but no session record is ongoing. Open a new record in "
                f"{rel}/ with `status: ongoing` in its frontmatter and a backlink to the previous record, "
                "log what you did, then finish.",
            )
    return cap + work


def run_stop(project: Path, vault: Path, sessions: Path) -> str:
    index = load_index(vault)
    records = refresh(sessions, index, full=not index)
    state = git_state(project, vault)
    before = index.get("snapshot") or None
    ongoing = ongoing_of(records)
    fired = triggers(before, state, heads_related(project, before, state)) if before and state else ()
    touched = bool(ongoing and before) and ongoing.mtime > float(before.get("at") or 0)
    capped = bool(ongoing) and over_cap(ongoing.name) and index.get("cap_notified") != ongoing.name
    rel = os.path.relpath(sessions, project)
    reasons = stop_reasons(rel, fired, ongoing, touched, capped, broken_head(records), last_readable(records))
    save_index(vault, {
        **index,
        "records": records,
        "ongoing": ongoing.name if ongoing else None,
        "checkout": track_checkout(index, ongoing, state),
        "snapshot": {**state, "at": time.time()} if state else before,
        "cap_notified": ongoing.name if capped else index.get("cap_notified"),
    })
    return json.dumps({"decision": "block", "reason": " ".join(reasons)}) if reasons else ""


def run_prompt(project: Path, vault: Path, sessions: Path) -> str:
    current = load_index(vault).get("ongoing")
    rel = os.path.relpath(sessions, project)
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            "Session registry: if this message settles a decision, append a `## Decision - <timestamp>` "
            f"entry (what was decided and why) to {rel}/{current}.md before moving on."
        ),
    }}) if isinstance(current, str) and current else ""


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    config = load_config(project)
    enabled = ((config.get("vault") or {}).get("freshness") or {}).get("enabled", True) is not False
    vault = resolve_vault(project, config)[0] if enabled else None
    sessions = sessions_folder(vault, config)[0] if vault else None
    mode = argv[0] if argv else ""
    try:
        match (mode, sessions):
            case (_, None):
                out = ""
            case (_, folder) if not folder.is_dir():
                out = ""
            case ("stop", folder) if not payload.get("stop_hook_active"):
                out = run_stop(project, vault, folder)
            case ("prompt", folder):
                out = run_prompt(project, vault, folder)
            case _:
                out = ""
    except Exception:  # fail-open: never break the agent's turn
        out = ""
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
