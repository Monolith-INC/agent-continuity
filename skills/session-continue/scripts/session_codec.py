"""Parse external JSON once; planners receive frozen values only."""

from __future__ import annotations

import json
import re
from dataclasses import asdict

from session_model import Active, Closed, EVENT_KINDS, Event, Failure, Progress, Receipt, Recorded, Request, Session


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def texts(value: object) -> bool:
    return isinstance(value, list) and all(text(v) for v in value)


def progress(value: object) -> Progress | Failure:
    match value:
        case {"orientation": o, "decisions": d, "evidence": e, "unfinished": u} if all(texts(v) for v in (o, d, e, u)):
            return Progress(tuple(o), tuple(d), tuple(e), tuple(u))
        case _:
            return Failure("invalid-progress", "Supply orientation, decisions, evidence and unfinished as lists of text, using only observed facts and source references.")


def event(value: object) -> Event | Failure:
    match value:
        case {"id": key, "kind": kind, "outcome": outcome, "progress": raw} if text(key) and text(kind) and kind in EVENT_KINDS and outcome in ("succeeded", "failed"):
            return event_progress(value, key, kind, outcome, progress(raw))
        case _:
            return Failure("invalid-event", "Supply a stable id, supported event kind, succeeded/failed outcome and current progress; retry uncertain operations only after resolving their outcome.")


def event_progress(raw: dict, key: str, kind: str, outcome: str, parsed: Progress | Failure) -> Event | Failure:
    match (parsed, raw.get("path", "")):
        case (Failure() as failure, _):
            return failure
        case (Progress() as saved, str() as path) if kind != "first-edit" or valid_path(path):
            return Event(key, kind, outcome, path, saved)
        case _:
            return Failure("invalid-path", "A first-edit event needs a project-relative file path without traversal or empty components.")


def valid_path(path: str) -> bool:
    return bool(path) and not re.match(r"[/\\]|[A-Za-z]:", path) and "\\" not in path and all(p not in ("", ".", "..") for p in path.split("/"))


def request(value: object) -> Request | Failure:
    match value:
        case {"operation": op, "chat": chat, "checkout": checkout} if op in ("continue", "checkpoint", "recover") and text(chat) and text(checkout):
            return request_options(value, op, chat, checkout)
        case _:
            return Failure("invalid-request", "Supply operation continue/checkpoint/recover and stable chat and checkout identities.")


def request_options(raw: dict, op: str, chat: str, checkout: str) -> Request | Failure:
    match (raw.get("intention", ""), raw.get("confirmChange", False), event(raw.get("event")) if op == "checkpoint" else None):
        case (_, _, Failure() as failure):
            return failure
        case (str() as intent, bool() as confirmed, supplied):
            return Request(op, chat, checkout, intent, confirmed, supplied)
        case _:
            return Failure("invalid-options", "Supply intention as text and confirmChange as a boolean; confirmation must come from the user.")


def timestamp(value: object) -> bool:
    return type(value) is int and value >= 0


def session(value: object) -> Session | Failure:
    match value:
        case {"schema": 1, "id": key, "chat": chat, "checkout": checkout, "intention": intent, "started_at": start,
              "observed_at": observed, "state": state, "previous": previous, "progress": raw, "events": events,
              "receipts": receipts, "issues": issues, "notes": notes} if all(text(v) for v in (key, chat, checkout)) and isinstance(intent, str) and isinstance(previous, str) and timestamp(start) and timestamp(observed) and observed >= start and isinstance(events, list) and isinstance(receipts, list) and texts(issues) and texts(notes):
            return session_parts(value, progress(raw), tuple(recorded(r) for r in events), tuple(receipt(r) for r in receipts), parse_state(state))
        case _:
            return Failure("unreadable-record", "Preserve this record and recover from the last readable session.")


def parse_state(value: object) -> Active | Closed | Failure:
    match value:
        case {"kind": "active"}:
            return Active()
        case {"kind": "closed", "at": at, "reason": reason} if timestamp(at) and text(reason):
            return Closed(at, reason)
        case _:
            return Failure("unreadable-state", "Recover without overwriting the unreadable record.")


def recorded(value: object) -> Recorded | Failure:
    match value:
        case {"event": raw, "at": at} if timestamp(at):
            match event(raw):
                case Event() as parsed:
                    return Recorded(parsed, at)
                case Failure() as failure:
                    return failure
        case _:
            return Failure("unreadable-event", "Recover from readable evidence; do not invent the missing event.")


def receipt(value: object) -> Receipt | Failure:
    match value:
        case {"id": key, "digest": digest} if text(key) and isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest):
            return Receipt(key, digest)
        case _:
            return Failure("unreadable-receipt", "Preserve this record and recover from readable evidence.")


def session_parts(raw: dict, saved: Progress | Failure, events: tuple, receipts: tuple, state: Active | Closed | Failure) -> Session | Failure:
    match (saved, state, any(isinstance(e, Failure) for e in events + receipts)):
        case (Progress(), Active() | Closed(), False) if valid_record_times(raw, events, state) and len({e.event.id for e in events} | {r.id for r in receipts}) == len(events) + len(receipts):
            return Session(raw["id"], raw["chat"], raw["checkout"], raw["intention"], raw["started_at"], raw["observed_at"],
                           state, raw["previous"], saved, events, receipts, tuple(raw["issues"]), tuple(raw["notes"]))
        case _:
            return Failure("unreadable-record", "Preserve this record and recover from readable evidence.")


def valid_record_times(raw: dict, events: tuple[Recorded, ...], state: Active | Closed) -> bool:
    return all(raw["started_at"] <= e.at <= raw["observed_at"] for e in events) and len({e.event.id for e in events}) == len(events) and (
        isinstance(state, Active) or raw["started_at"] <= state.at <= raw["observed_at"])


def document(saved: Session) -> dict:
    return {"schema": 1, **asdict(saved), "state": {"kind": "active"} if isinstance(saved.state, Active) else {"kind": "closed", **asdict(saved.state)}}


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def decode(raw: str) -> object | Failure:
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        return Failure("invalid-json", "Preserve the invalid JSON and retry with a readable document.")
