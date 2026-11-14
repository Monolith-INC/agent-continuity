#!/usr/bin/env python3
"""Keep the session registry (Agent_Sessions/) fresh while an agent works.

Usage: session_freshness.py stop|prompt   (hook input JSON on stdin)

stop    Stop hook. When project files changed after the ongoing session record
        was last written, block the stop once and ask the agent to append an
        Implementation Checkpoint (or a Decision entry) first. With no ongoing
        record, ask it to open one. Never blocks twice in a row.
prompt  UserPromptSubmit hook. While a record is ongoing, add a one-line
        reminder to log a Decision entry if the user's message settles one.

Silent (fail-open) when there is no vault, no git repository, or the config
turns it off: .claude/agent-continuity.config.json -> {"vault":{"freshness":{"enabled":false}}}.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_options import SessionRecord, all_records  # noqa: E402

CONFIG_NAMES = ("agent-continuity.config.json", "codex-workflow.config.json")


def load_config(project: Path) -> dict:
    paths = (project / ".claude" / name for name in CONFIG_NAMES)
    found = next((p for p in paths if p.is_file()), None)
    try:
        return json.loads(found.read_text(encoding="utf-8")) if found else {}
    except (OSError, ValueError):
        return {}


def vault_root(project: Path, config: dict) -> Path | None:
    vault = config.get("vault") or {}
    named = vault.get("folder") or (config.get("codex") or {}).get("folder") or ""
    globbed = next((p.name for p in sorted(project.glob("AI_Codex*")) if p.is_dir()), "")
    folder = project / (named or globbed) if (named or globbed) else None
    return folder if folder and folder.is_dir() else None


def changed_files(project: Path, vault: Path) -> tuple[Path, ...]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ()
    paths = (project / line[3:].split(" -> ")[-1].strip('"') for line in out.splitlines() if len(line) > 3)
    return tuple(p for p in paths if p.is_file() and vault not in p.parents)


def newest_mtime(paths: tuple[Path, ...]) -> float:
    return max((p.stat().st_mtime for p in paths), default=0.0)


def ongoing_record(sessions: Path) -> SessionRecord | None:
    return next((r for r in all_records(sessions) if r.status == "ongoing"), None)


def stop_reason(project: Path, vault: Path, sessions: Path) -> str:
    work_time = newest_mtime(changed_files(project, vault))
    current = ongoing_record(sessions)
    record_path = sessions / f"{current.name}.md" if current else None
    newest_any = next(iter(all_records(sessions)), None)
    newest_time = (sessions / f"{newest_any.name}.md").stat().st_mtime if newest_any else 0.0
    rel = sessions.relative_to(project)
    match (current, work_time):
        case (_, 0.0):
            return ""
        case (None, t) if t > newest_time:
            return (
                "Session registry: project files changed but no session record is ongoing. "
                f"Open a new record in {rel}/ with `status: ongoing` in its frontmatter and a "
                "backlink to the previous record, log what you did, then finish."
            )
        case (None, _):
            return ""
        case (_, t) if t > record_path.stat().st_mtime:
            return (
                f"Session registry: files changed since {rel}/{current.name}.md was last updated. "
                "Append an `## Implementation Checkpoint - <timestamp>` (Scope / Changes / Validation), "
                "or a `## Decision - <timestamp>` if you settled a decision, then finish."
            )
        case _:
            return ""


def prompt_context(project: Path, sessions: Path) -> str:
    current = ongoing_record(sessions)
    rel = sessions.relative_to(project)
    return (
        f"Session registry: if this message settles a decision, append a `## Decision - <timestamp>` "
        f"entry (what was decided and why) to {rel}/{current.name}.md before moving on."
    ) if current else ""


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    config = load_config(project)
    vault_cfg = config.get("vault") or {}
    enabled = (vault_cfg.get("freshness") or {}).get("enabled", True) is not False
    vault = vault_root(project, config) if enabled else None
    sessions = vault / ((vault_cfg.get("sessionOptions") or {}).get("folder") or "Agent_Sessions") if vault else None
    mode = argv[0] if argv else ""
    match (mode, sessions):
        case (_, None):
            return 0
        case ("stop", folder) if folder.is_dir() and not payload.get("stop_hook_active"):
            reason = stop_reason(project, vault, folder)
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) if reason else "")
        case ("prompt", folder) if folder.is_dir():
            context = prompt_context(project, folder)
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit", "additionalContext": context,
            }}) if context else "")
        case _:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
