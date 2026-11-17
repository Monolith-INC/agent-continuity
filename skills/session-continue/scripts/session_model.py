"""Pure session transitions. Time, records and events are explicit inputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json

EIGHT_HOURS = 8 * 60 * 60 * 1000
EVENT_KINDS = frozenset({"first-edit", "commit", "history-change", "task", "push", "review", "session-end"})


@dataclass(frozen=True)
class Failure:
    code: str
    recovery: str


@dataclass(frozen=True)
class Progress:
    orientation: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    unfinished: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    outcome: str
    path: str
    progress: Progress


@dataclass(frozen=True)
class Recorded:
    event: Event
    at: int


@dataclass(frozen=True)
class Receipt:
    id: str
    digest: str


@dataclass(frozen=True)
class Active:
    pass


@dataclass(frozen=True)
class Closed:
    at: int
    reason: str


@dataclass(frozen=True)
class Session:
    id: str
    chat: str
    checkout: str
    intention: str
    started_at: int
    observed_at: int
    state: Active | Closed = Active()
    previous: str = ""
    progress: Progress = Progress()
    events: tuple[Recorded, ...] = ()
    receipts: tuple[Receipt, ...] = ()
    issues: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Request:
    operation: str
    chat: str
    checkout: str
    intention: str = ""
    confirm_change: bool = False
    event: Event | None = None


@dataclass(frozen=True)
class Ready:
    session: Session
    writes: tuple[Session, ...]
    disposition: str


def identity(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def latest(sessions: tuple[Session, ...]) -> Session | None:
    ancestors = frozenset(s.previous for s in sessions)
    return max((s for s in sessions if s.id not in ancestors), key=lambda s: (s.started_at, s.id), default=None)


def new_session(request: Request, now: int, previous: Session | None, issues: tuple[str, ...]) -> Session:
    return Session(identity(json.dumps((request.chat, previous.id if previous else "", now, issues))), request.chat,
                   request.checkout, request.intention or (previous.intention if previous else ""), now, now,
                   previous=previous.id if previous else "", progress=previous.progress if previous else Progress(),
                   issues=issues, notes=recovery_notes(previous, tuple(i for i in issues if not previous or i not in previous.issues)))


def recovery_notes(previous: Session | None, issues: tuple[str, ...]) -> tuple[str, ...]:
    return () if not issues else (("restored-readable-history" if previous else "history-unavailable"),)


def changed(request: Request, session: Session) -> bool:
    return request.checkout != session.checkout or bool(request.intention and session.intention and request.intention != session.intention)


def close(session: Session, now: int, reason: str) -> Session:
    match session.state:
        case Closed():
            return session
        case Active():
            return replace(session, observed_at=now, state=Closed(min(now, session.started_at + EIGHT_HOURS), reason))


def advance(request: Request, sessions: tuple[Session, ...], issues: tuple[str, ...], now: int, seed: Session | None) -> Ready | Failure:
    match latest(sessions):
        case None if seed is not None and now < seed.observed_at:
            return Failure("clock-regressed", "Check the system clock before linking to this session; no progress was changed.")
        case None:
            fresh = new_session(request, now, seed, issues)
            recovered = replace(fresh, notes=("history-unavailable",)) if request.operation == "recover" and not issues and seed is None else fresh
            return Ready(recovered, (recovered,), "started")
        case Session() as current if now < current.observed_at:
            return Failure("clock-regressed", "Check the system clock and retry; saved progress is unchanged.")
        case Session() as current if changed(request, current) and not request.confirm_change:
            return Failure("needs-decision", "Ask whether to close this session for the changed checkout or intention; retry with confirmChange only after consent.")
        case Session() as current:
            return advance_current(request, current, issues, now)


def advance_current(request: Request, current: Session, issues: tuple[str, ...], now: int) -> Ready:
    needs_recovery = bool(set(issues).difference(current.issues))
    match (current.state, needs_recovery, changed(request, current), now >= current.started_at + EIGHT_HOURS):
        case (Active(), False, False, False):
            adopted = replace(current, intention=request.intention, observed_at=now) if not current.intention and request.intention else current
            return Ready(adopted, () if adopted == current else (adopted,), "continued")
        case _:
            reason = "recovered" if needs_recovery else "changed-context" if changed(request, current) else "elapsed"
            successor = new_session(request, now, current, issues)
            closed = close(current, now, reason)
            return Ready(successor, (() if closed == current else (closed,)) + (successor,), reason)


def existing_event(request: Request, sessions: tuple[Session, ...]) -> Ready | Failure | None:
    found = tuple((s, r.digest) for s in sessions for r in event_receipts(s) if request.event and r.id == request.event.id)
    match found:
        case ((session, digest),) if request.event and digest == event_digest(request.event):
            return Ready(session, (), "already-recorded")
        case ():
            return None
        case _:
            return Failure("event-conflict", "The event identity has different evidence. Reuse the original payload or supply a new identity for a different event.")


def event_digest(event: Event) -> str:
    return identity(json.dumps(asdict(event), ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def event_receipts(session: Session) -> tuple[Receipt, ...]:
    return tuple(Receipt(r.event.id, event_digest(r.event)) for r in session.events) + session.receipts


def first_edit_recorded(session: Session, event: Event) -> bool:
    return event.kind == "first-edit" and event.outcome == "succeeded" and any(
        r.event.kind == "first-edit" and r.event.outcome == "succeeded" and r.event.path == event.path for r in session.events)


def checkpoint(ready: Ready, event: Event, now: int) -> Ready:
    match first_edit_recorded(ready.session, event):
        case True:
            updated = replace(ready.session, observed_at=now, receipts=ready.session.receipts + (Receipt(event.id, event_digest(event)),))
            return Ready(updated, tuple(s for s in ready.writes if s.id != updated.id) + (updated,), "first-edit-already-recorded")
        case False:
            updated = replace(ready.session, observed_at=now, progress=event.progress,
                              events=ready.session.events + (Recorded(event, now),))
            ended = close(updated, now, "session-end") if event.kind == "session-end" and event.outcome == "succeeded" else updated
            return Ready(ended, tuple(s for s in ready.writes if s.id != ended.id) + (ended,), "recorded")


def plan(request: Request, sessions: tuple[Session, ...], issues: tuple[str, ...], now: int, seed: Session | None = None) -> Ready | Failure:
    match existing_event(request, sessions):
        case Ready() | Failure() as result:
            return result
        case None:
            return apply_event(advance(request, sessions, issues, now, seed), request.event, now)


def apply_event(result: Ready | Failure, event: Event | None, now: int) -> Ready | Failure:
    match (result, event):
        case (Ready() as ready, Event() as supplied):
            return checkpoint(ready, supplied, now)
        case _:
            return result
