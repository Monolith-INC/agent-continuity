# Session protocol v1

The public entry point is `skills/session-continue/scripts/session.py`. Python 3.10+ and its standard library are sufficient. All operations use the same planner and file interpreter. The project supplies settings; this runtime makes no tracker calls and installs no hooks.

Example request:

```json
{
  "operation": "checkpoint",
  "chat": "stable-host-chat-id",
  "checkout": "/absolute/path/to/checkout",
  "intention": "Deliver the approved story",
  "event": {
    "id": "commit:full-observed-commit-hash",
    "kind": "commit",
    "outcome": "succeeded",
    "progress": {
      "orientation": ["docs/design.md"],
      "decisions": ["docs/adr/001.md"],
      "evidence": ["Observed commit hash and verification report"],
      "unfinished": ["Finish installed-host verification"]
    }
  }
}
```

`continue` and `recover` omit `event`. Optional `confirmChange` defaults to false; true represents explicit consent to a changed checkout or intention. Empty `intention` preserves the existing value. The supplied checkpoint progress is a complete snapshot, not a patch. Text uses the project's selected language; identifiers and schema keys remain stable.

Supported event kinds: `first-edit`, `commit`, `history-change`, `task`, `push`, `review`, `session-end`. Outcomes: `succeeded`, `failed`. A `first-edit` additionally requires a project-relative `path` without traversal. Use separate event identities for a failed attempt and a later successful attempt. Retrying the same event reuses both identity and payload.

The command returns JSON and exit code 0 on confirmed success, 1 on a recoverable failure. Success includes the current or replayed `session`, its `disposition`, and the session identifiers written by this invocation. `already-recorded` returns the original event's session; use `continue` to restore the latest session rather than treating a checkpoint receipt as current orientation. Failure includes `code`, `recovery`, and `workMayContinue: true`. A missing executable or Python runtime must be reported separately; a host exit code is not automatically a runtime result.

Journals live at `<root>/<sha256(chat)>/<session-id>.json`. Each session holds its checkpoint events, latest progress, predecessor, observed issue fingerprints and lifecycle state. A new chat may seed from the latest readable session in the same checkout without modifying that other chat's chain; thereafter it follows its own chain. Millisecond timestamps are UTC epoch values. A closed record carries its end time and reason; elapsed closure uses the original eight-hour expiry even after idle days. Recovery note codes are `restored-readable-history` and `history-unavailable`; explain them in the project's language. Application-provided progress remains verbatim.

Atomic replacement preserves the previous readable file on an interrupted write. One nonblocking process-scoped lock protects each chat chain; process termination releases it. A rollover writes the closed predecessor before the successor. If interrupted between those writes, replay starts from that closed predecessor and completes continuation without losing its progress. A suppressed repeated file edit keeps an identity/digest receipt without duplicating its progress, including across rollover. Unreadable records are left in place and their fingerprints are carried into the recovery record, so unchanged damage is reported once. A new session cannot overwrite an occupied unreadable destination. No retention or deletion occurs.

Existing Markdown journals are not automatically migrated. They can be linked as evidence in progress. Do not claim archived sessions, freshness of source documents, knowledge incorporation, or automatic host event capture on the strength of this protocol.
