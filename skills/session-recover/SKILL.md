---
name: session-recover
description: Recover project session context from readable evidence while preserving damaged records and continuing the work.
---

# Recover a project session

Use the same project choices, chat identifier and checkout as `session-continue`. Invoke `../session-continue/scripts/session.py` with `operation: recover`; its JSON protocol lives in `../session-continue/references/protocol.md`.

Recover from the last readable record and create a linked continuation when newly detected damage requires it. Preserve the unreadable originals. Healthy active sessions are returned unchanged; repeating recovery against unchanged damage does not create a chain of empty sessions.

If no readable record exists, start fresh with available project context and explicitly identify the missing history. Consult authoritative documents and project operations for current work state. Do not invent missing events, approvals or completed work, infer a session start from modification time, or replay an operation with an uncertain outcome.

Report the diagnostic and restored unfinished work briefly. If storage remains unavailable, keep the task moving using available context and the returned recovery. Do not repair a journal by deleting it or rewrite unrelated records.
