#!/usr/bin/env python3
"""Session registry core shared by the session hooks and the reconcile tool.

Records live in <vault>/Agent_Sessions/ as YYYY-MM-DD-HHMMSS-slug.md, so name order
is time order. Reading every record on every hook would grow with the registry, so
the session start hook builds a small index once:

    <vault>/.agent-continuity/session-index.json   (git-ignored, rebuilt on demand)

It holds every record's summary newest first (a lookup by name is a dict built from
that list), the ongoing record, the checkout the ongoing session runs in, and a git
snapshot the Stop hook compares against to decide whether a checkpoint is due.
Later hooks read the index and re-read only records whose file changed.

Rules kept here:
- Only the newest record that is not archived can be ongoing.
- A session may run at most MAX_SESSION_HOURS.
- The vault must sit inside the project folder; anything else is refused.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

RECORD_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}-[a-z0-9-]+$")
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER = re.compile(r"^﻿?---\s*\n(.*?)\n---\s*(\n|$)", re.S)
FRONTMATTER_OPEN = re.compile(r"^﻿?---\s*\n")
STATUS_LINE = re.compile(r"^status\s*:\s*['\"]?([A-Za-z]+)['\"]?\s*$", re.MULTILINE)
STATUSES = ("ongoing", "closed", "archived")
UNREADABLE = "unreadable"

CONFIG_NAMES = ("agent-continuity.config.json", "codex-workflow.config.json")
DEFAULT_SESSIONS = "Agent_Sessions"
STATE_DIR = ".agent-continuity"
INDEX_NAME = "session-index.json"
INDEX_VERSION = 1
MAX_SESSION_HOURS = 8
CONFIG_HINT = "Ask the user for the correct vault folder inside the project and set `vault.folder` in .claude/agent-continuity.config.json."


# ---------------------------------------------------------------- records

@dataclass(frozen=True)
class SessionRecord:
    name: str
    title: str
    status: str      # ongoing | closed | archived | unreadable
    explicit: bool   # status came from a valid frontmatter line
    forward: bool    # links to a newer record
    mtime: float
    problem: str = ""

    @property
    def readable(self) -> bool:
        return self.status != UNREADABLE


def slug_title(name: str) -> str:
    return name[len("YYYY-MM-DD-HHMMSS-"):].replace("-", " ")


def linked_names(text: str) -> tuple[str, ...]:
    return tuple(Path(target.strip()).stem for target in WIKILINK.findall(text))


def links_forward(name: str, text: str) -> bool:
    return any(RECORD_NAME.match(link) and link > name for link in linked_names(text))


def read_status(text: str) -> str:
    block = FRONTMATTER.match(text)
    found = STATUS_LINE.search(block.group(1)) if block else None
    value = found.group(1).lower() if found else ""
    return value if value in STATUSES else ""


def unreadable(name: str, mtime: float, problem: str) -> SessionRecord:
    return SessionRecord(name, slug_title(name), UNREADABLE, False, False, mtime, problem)


def parse_record(name: str, text: str, mtime: float) -> SessionRecord:
    match (bool(text.strip()), bool(FRONTMATTER_OPEN.match(text)), bool(FRONTMATTER.match(text))):
        case (False, _, _):
            return unreadable(name, mtime, "the file is empty")
        case (True, True, False):
            return unreadable(name, mtime, "its frontmatter block is never closed")
        case _:
            heading = HEADING.search(text)
            forward = links_forward(name, text)
            explicit = read_status(text)
            return SessionRecord(
                name=name,
                title=heading.group(1) if heading else slug_title(name),
                status=explicit or ("closed" if forward else "ongoing"),
                explicit=bool(explicit),
                forward=forward,
                mtime=mtime,
            )


def read_record(path: Path) -> SessionRecord:
    try:
        return parse_record(path.stem, path.read_text(encoding="utf-8"), path.stat().st_mtime)
    except UnicodeDecodeError:
        return unreadable(path.stem, path.stat().st_mtime, "it is not valid UTF-8 text")
    except OSError as error:
        return unreadable(path.stem, 0.0, f"it can't be opened ({error.strerror or error})")


def started_at(name: str) -> datetime:
    return datetime.strptime(name[:17], "%Y-%m-%d-%H%M%S")


def over_cap(name: str, now: datetime | None = None) -> bool:
    return (now or datetime.now()) - started_at(name) > timedelta(hours=MAX_SESSION_HOURS)


def live(records: Iterable[SessionRecord]) -> tuple[SessionRecord, ...]:
    return tuple(r for r in records if r.status != "archived")


def chain_head(records: Iterable[SessionRecord]) -> SessionRecord | None:
    return next(iter(live(records)), None)


def ongoing_of(records: Iterable[SessionRecord]) -> SessionRecord | None:
    head = chain_head(records)
    return head if head and head.status == "ongoing" else None


def broken_head(records: Iterable[SessionRecord]) -> SessionRecord | None:
    head = chain_head(records)
    return head if head and not head.readable else None


def last_readable(records: Iterable[SessionRecord]) -> SessionRecord | None:
    return next((r for r in live(records) if r.readable), None)


def needs_reconcile(records: tuple[SessionRecord, ...]) -> bool:
    """True when a readable record is not in the current format: no valid status,
    an ongoing status that is not the newest record, or no forward link to its successor."""
    head = chain_head(records)
    return any(
        r.readable and (
            not r.explicit
            or (r.status == "ongoing" and r is not head)
            or (i > 0 and not r.forward)
        )
        for i, r in enumerate(records)
    )


# ---------------------------------------------------------------- index

def index_path(vault: Path) -> Path:
    return vault / STATE_DIR / INDEX_NAME


def load_index(vault: Path) -> dict:
    try:
        data = json.loads(index_path(vault).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == INDEX_VERSION else {}


def records_of(index: dict) -> tuple[SessionRecord, ...]:
    raw = index.get("records") or ()
    try:
        return tuple(r if isinstance(r, SessionRecord) else SessionRecord(**r) for r in raw)
    except TypeError:
        return ()


def state_dir(vault: Path) -> Path:
    """The plugin's private, git-ignored folder inside the vault."""
    folder = vault / STATE_DIR
    folder.mkdir(exist_ok=True)
    ignore = folder / ".gitignore"
    _ = ignore.exists() or ignore.write_text("*\n", encoding="utf-8")
    return folder


def save_index(vault: Path, index: dict) -> None:
    folder = state_dir(vault)
    payload = {**index, "version": INDEX_VERSION, "records": [asdict(r) for r in records_of(index)]}
    temp = folder / f".{INDEX_NAME}.{os.getpid()}.tmp"
    temp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    temp.replace(index_path(vault))


def record_paths(sessions: Path) -> dict[str, Path]:
    try:
        entries = tuple(os.scandir(sessions))
    except OSError:
        return {}
    return {
        e.name[:-3]: Path(e.path)
        for e in entries
        if e.name.endswith(".md") and RECORD_NAME.match(e.name[:-3])
    }


def refresh(sessions: Path, index: dict, full: bool) -> tuple[SessionRecord, ...]:
    """Bring the index's records up to date with the folder, newest first.

    full=True stats every record and re-reads only the ones whose file changed.
    full=False (cheap, for per-turn hooks) lists the folder and re-reads only new
    records and the newest few, trusting the index for the rest."""
    known = {r.name: r for r in records_of(index)}
    paths = record_paths(sessions)
    names = sorted(paths, reverse=True)
    recheck = set(names[:3]) | {n for n in names if n not in known}

    def current(name: str) -> SessionRecord:
        cached = known.get(name)
        check = full or name in recheck
        fresh = check and (cached is None or _mtime(paths[name]) != cached.mtime)
        return read_record(paths[name]) if fresh or cached is None else cached

    return tuple(current(n) for n in names)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


# ---------------------------------------------------------------- config & vault

def load_config(project: Path) -> dict:
    found = next((p for p in (project / ".claude" / n for n in CONFIG_NAMES) if p.is_file()), None)
    try:
        data = json.loads(found.read_text(encoding="utf-8")) if found else {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_inside(root: Path, path: Path) -> bool:
    base, target = root.resolve(), path.resolve()
    return target == base or base in target.parents


def default_vault(project: Path) -> Path | None:
    return next(
        (p for p in sorted(project.glob("AI_Codex*")) if p.is_dir() and is_inside(project, p) and p.resolve() != project.resolve()),
        None,
    )


def resolve_vault(project: Path, config: dict) -> tuple[Path | None, str]:
    """The vault folder and a notice for the agent when the setting had to be ignored."""
    vault_cfg = config.get("vault") or {}
    named = str(vault_cfg.get("folder") or (config.get("codex") or {}).get("folder") or "")
    candidate = project / named
    fallback = default_vault(project)
    inside = bool(named) and is_inside(project, candidate) and candidate.resolve() != project.resolve()
    match (named, inside, candidate.is_dir()):
        case ("", _, _):
            return fallback, ""
        case (_, True, True):
            return candidate, ""
        case (_, inside_flag, _):
            reason = "does not exist" if inside_flag else "points outside the project folder, which is not allowed"
            using = f" Using {fallback.relative_to(project)}/ for now." if fallback else ""
            return fallback, f"Vault folder setting {named!r} {reason}, so it was ignored.{using} {CONFIG_HINT}"


def sessions_folder(vault: Path, config: dict) -> tuple[Path, str]:
    named = str(((config.get("vault") or {}).get("sessionOptions") or {}).get("folder") or DEFAULT_SESSIONS)
    candidate = vault / named
    match is_inside(vault, candidate) and candidate.resolve() != vault.resolve():
        case True:
            return candidate, ""
        case False:
            return vault / DEFAULT_SESSIONS, (
                f"Session folder setting {named!r} points outside the vault, so {DEFAULT_SESSIONS}/ is used. "
                "Ask the user for the correct folder and set `vault.sessionOptions.folder`."
            )


def plugin_version() -> str:
    manifest = Path(__file__).resolve().parents[2] / ".plugin" / "plugin.json"
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


# ---------------------------------------------------------------- git

def git(project: Path, *args: str, raw: bool = False) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(project), *args],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        return out if raw else out.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def porcelain_path(line: str) -> str:
    return line[3:].split(" -> ")[-1].strip('"')


def git_state(project: Path, vault: Path) -> dict | None:
    """Where the code stands now: commit, branch, upstream, push, and changed files."""
    top = git(project, "rev-parse", "--show-toplevel")
    status = git(project, "status", "--porcelain", "--untracked-files=all", raw=True) if top is not None else None
    match (top, status):
        case (None, _) | (_, None):
            return None
        case _:
            pass
    upstream_ref = git(project, "rev-parse", "--symbolic-full-name", "@{u}") or ""
    push_note = git(project, "reflog", "show", "-n", "1", "--format=%gs", upstream_ref) if upstream_ref else ""
    vault_rel = _relative(Path(top), vault)
    dirty = sorted({
        p for p in map(porcelain_path, status.splitlines() if status else ())
        if p and not (vault_rel and (p == vault_rel or p.startswith(vault_rel + "/")))
    })
    return {
        "worktree": top,
        "branch": git(project, "symbolic-ref", "--short", "-q", "HEAD") or "detached",
        "head": git(project, "rev-parse", "HEAD") or "",
        "upstream": (git(project, "rev-parse", "@{u}") or "") if upstream_ref else "",
        "pushed": (push_note or "").startswith("update by push"),
        "dirty": dirty,
    }


def _relative(top: Path, vault: Path) -> str:
    try:
        return vault.resolve().relative_to(top.resolve()).as_posix()
    except ValueError:
        return ""


def is_ancestor(project: Path, old: str, new: str) -> bool:
    try:
        return subprocess.run(
            ["git", "-C", str(project), "merge-base", "--is-ancestor", old, new],
            capture_output=True, timeout=5,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


def describe_files(paths: list[str]) -> str:
    shown = ", ".join(paths[:5])
    return shown + (f" and {len(paths) - 5} more" if len(paths) > 5 else "")


def triggers(before: dict, now: dict, ancestor: bool) -> tuple[str, ...]:
    """Which checkpoint rules fired between two git snapshots."""
    new_files = sorted(set(now.get("dirty") or ()) - set(before.get("dirty") or ()))
    old_head, new_head = before.get("head") or "", now.get("head") or ""
    moved = bool(new_head) and old_head != new_head
    pushed = bool(now.get("pushed")) and bool(now.get("upstream")) and now.get("upstream") != before.get("upstream")
    return tuple(
        text for fired, text in (
            (bool(new_files), f"first change to {describe_files(new_files)}"),
            (moved and (ancestor or not old_head), "new commit"),
            (moved and bool(old_head) and not ancestor, "commit rolled back or amended"),
            (pushed, "push"),
        ) if fired
    )


def checkout_of(state: dict | None) -> dict:
    return {"branch": (state or {}).get("branch", ""), "worktree": (state or {}).get("worktree", "")}


def track_checkout(index: dict, ongoing: SessionRecord | None, state: dict | None) -> dict:
    """Remember the checkout an ongoing session started in, the first time it is seen."""
    stored = index.get("checkout") or {}
    match (ongoing, stored.get("session") == (ongoing.name if ongoing else None)):
        case (None, _):
            return {}
        case (_, True):
            return stored
        case _:
            return {"session": ongoing.name, **checkout_of(state)}
