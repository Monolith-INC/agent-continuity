"""Filesystem interpreter. Effects are deferred until the CLI runs its task."""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from session_codec import decode, document, encode, session
from session_model import Failure, Ready, Request, Session, identity, plan


@dataclass(frozen=True)
class Observed:
    sessions: tuple[Session, ...]
    issues: tuple[str, ...]
    versions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class File:
    name: str
    digest: str
    parsed: Session | Failure


def safe_directory(project: Path, root: Path) -> bool:
    return root.is_relative_to(project) and ".." not in root.relative_to(project).parts and all(
        not p.is_symlink() for p in (root, *root.parents) if p.is_relative_to(project))


def read_record(path: Path, chat: str | None) -> File:
    try:
        match path.is_symlink():
            case True:
                return File(path.name, "symlink", Failure("unsafe-record", "Preserve the symbolic link; use a regular session record."))
            case False:
                raw = path.read_bytes()
                parsed = session(decode(raw.decode("utf-8")))
                valid = isinstance(parsed, Session) and (chat is None or parsed.chat == chat) and identity(parsed.chat) == path.parent.name and f"{parsed.id}.json" == path.name
                return File(path.name, identity(raw.hex()), parsed if valid else Failure("unreadable-record", "Preserve this record and recover from readable evidence."))
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return File(path.name, "unreadable", Failure("unreadable-record", "Check access to this record; continue from readable evidence."))


def observe(directory: Path, chat: str) -> Observed:
    records = tuple(read_record(p, chat) for p in sorted(directory.glob("*.json")))
    return Observed(tuple(r.parsed for r in records if isinstance(r.parsed, Session)),
                    tuple(f"{r.name}:{r.digest}" for r in records if isinstance(r.parsed, Failure)),
                    tuple((r.name, r.digest) for r in records))


@contextmanager
def exclusive(path: Path):
    """Process-scoped locks release on crash. Never follow a lock-file symlink."""
    match path.is_symlink():
        case True:
            raise OSError("unsafe lock file")  # Converted to a recoverable failure at the filesystem boundary.
        case False:
            pass
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "r+b") as handle:
        acquire(handle)
        try:
            yield handle
        finally:
            release(handle)


def acquire(handle) -> int:
    match sys.platform:
        case "win32":
            import msvcrt
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        case _:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle.fileno()


def release(handle) -> int:
    match sys.platform:
        case "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        case _:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_UN)
    return handle.fileno()


def atomic_write(path: Path, raw: str) -> Path:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".session-", delete=False) as pending:
        staged = Path(pending.name)
        pending.write(raw.encode("utf-8"))
        pending.flush()
        os.fsync(pending.fileno())
    try:
        os.replace(staged, path)
        return path
    finally:
        staged.unlink(missing_ok=True)  # Only the temporary file created by this invocation.


def save(directory: Path, snapshots: tuple[Session, ...]) -> tuple[str, ...]:
    return tuple(str(atomic_write(directory / f"{s.id}.json", encode(document(s)))) for s in snapshots)


def execute(project: Path, root: Path, request: Request, now: int) -> Ready | Failure:
    try:
        return run_safe(project, root, request, now) if safe_directory(project, root) else Failure(
            "unsafe-root", "Choose a journal directory within the project, without symbolic links.")
    except (OSError, ValueError):
        return Failure("storage-unavailable", "Progress was not confirmed saved. Preserve records, check directory access or another writer, and retry the same event identity; work may continue.")


def run_safe(project: Path, root: Path, request: Request, now: int) -> Ready | Failure:
    directory = root / identity(request.chat)
    match safe_directory(project, directory):
        case False:
            return Failure("unsafe-chain", "Preserve the existing path and choose a regular journal directory.")
        case True:
            directory.mkdir(parents=True, exist_ok=True)
            return run_locked(directory, request, now)


def run_locked(directory: Path, request: Request, now: int) -> Ready | Failure:
    with exclusive(directory / ".writer.lock"):
        observed = observe(directory, request.chat)
        seed = project_seed(directory.parent, request) if not observed.sessions else None
        return persist(directory, request, observed, plan(request, observed.sessions, observed.issues, now, seed))


def project_seed(root: Path, request: Request) -> Session | None:
    records = tuple(read_record(path, None).parsed for folder in root.iterdir() if folder.is_dir() and not folder.is_symlink()
                    and folder.name != identity(request.chat) for path in folder.glob("*.json"))
    candidates = tuple(s for s in records if isinstance(s, Session) and s.checkout == request.checkout)
    ancestors = frozenset(s.previous for s in candidates)
    return max((s for s in candidates if s.id not in ancestors), key=lambda s: (s.observed_at, s.started_at, s.id), default=None)


def persist(directory: Path, request: Request, observed: Observed, result: Ready | Failure) -> Ready | Failure:
    match result:
        case Failure():
            return result
        case Ready() if observe(directory, request.chat).versions != observed.versions:
            return Failure("concurrent-change", "Another writer changed session evidence. Reload and retry the same event; do not overwrite it.")
        case Ready() if any(f"{s.id}.json" in dict(observed.versions) and s.id not in {r.id for r in observed.sessions} for s in result.writes):
            return Failure("occupied-record", "A new session path is already occupied by unreadable evidence. Preserve it and retry continuation with the current clock.")
        case Ready():
            save(directory, result.writes)
            return result


def session_task(project: Path, root: Path, request: Request, now: int) -> Callable[[], Ready | Failure]:
    return lambda: execute(project, root, request, now)
