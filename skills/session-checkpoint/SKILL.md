---
name: session-checkpoint
description: Save observed project progress at a meaningful event, deduplicate retries and first-file edits, and preserve work when persistence is unavailable.
---

# Save a session checkpoint

Use the project choices and stable chat/checkout identity already established by `session-continue`. Invoke the same bundled command in `../session-continue/scripts/session.py` with `operation: checkpoint`. Read `../session-continue/references/protocol.md` for its request format. There is one session implementation for all three operations.

Supply a stable event identity, its supported kind and observed succeeded/failed outcome, plus the current orientation, decisions, evidence references and unfinished work. Reuse the identical identity and payload on a retry. An identity collision with different evidence requires reconciliation, not overwriting the saved event.

The seven kinds are `first-edit`, `commit`, `history-change`, `task`, `push`, `review`, and `session-end`. Include the project-relative file `path` for `first-edit`; only the first successful edit to that file in a session is recorded. Give task start/end events separate identities and describe their observed phase in the evidence. Include commit hashes, push receipts or review references where available. Resolve an uncertain operation's outcome before claiming success. A proposed command or command text alone is not completion evidence.

The supplied progress is a complete current snapshot; preserve unfinished work until there is evidence it is complete. Link source documents and explicit decisions. Do not infer new approval, publish knowledge, change tracker state or rewrite documentation as a checkpoint side effect.

A successful `session-end` closes the session. The next continuation links to it. A failed attempt is evidence of the failure and does not falsely close the session or count as a successful first edit.

Check the returned result. On failure, keep the original event/payload, report the bounded recovery, continue the task, and retry at the next opportunity. A failed save must not be described as saved. This checkpoint never gates editing, commits, pushes or reviews.

Capture events through verified host boundaries or explicit workflow calls. Do not add universal per-skill checks, tracker policies, read allowlists or branch prohibitions. No background capture is implied by installing these skills.
