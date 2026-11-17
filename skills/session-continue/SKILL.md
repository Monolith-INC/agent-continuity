---
name: session-continue
description: Start or resume a chat's project session, restore saved progress and evidence, and link an eight-hour continuation without blocking the work.
---

# Continue a project session

Reuse the project's selected language, document location and shared knowledge settings. The project owns setup; ask only for missing choices through its existing bootstrap. Do not run vault scaffolding or a second setup interview when those settings are already available.

Use the host's stable chat identifier and the actual checkout path, not a branch name. Each chat owns its session chain. Keep that identifier across restarts of the same chat; use a new one for a new chat. A new chat seeds its context from the most recently observed readable session in the same checkout and links to it without closing or modifying another chat's session. Subsequent operations use this chat's own chain. The project supplies its existing journal directory, or accepts `<artifactsPath>/sessions` when no location exists. Existing Markdown journals remain readable evidence; reference their useful contents without rewriting or silently importing them.

Run the bundled public command, using Python 3.10 or newer and the script beside this skill:

```text
python3 <this-skill-directory>/scripts/session.py --project <project> --root <journal-directory> --input <request.json>
```

For the JSON request and record format, read [session protocol](references/protocol.md). Start with `operation: continue`, the stable `chat` and `checkout`, and an `intention` only when the user explicitly stated it. Host time is supplied by the command, not guessed from file modification dates.

Restore the returned orientation, decisions, evidence and unfinished work. Consult authoritative documents and live tracker/SCM state through project operations before treating historical progress as current. Saved approvals are historical evidence, never fresh permission. Read shared knowledge through its existing catalog/find/fetch path; do not mirror a second knowledge store into the journal.

At eight elapsed hours, including idle time, the operation closes the expired session and creates one linked continuation. An inactive host cannot run a timer: continuation happens when it next executes, with the actual start time and the old expiry preserved. It never manufactures sessions for each idle interval.

Missing or unreadable records recover from the last readable session with a diagnostic. The damaged files are preserved. With no readable history, start fresh and disclose that earlier context could not be recovered; use known project context rather than inventing it.

On `needs-decision`, ask once whether to close the session for the changed checkout or intention. Preserve the request and retry with `confirmChange: true` only after the user agrees. Other failures carry their recovery; say progress was not confirmed saved, continue the task, and retry at the next checkpoint.

Use this operation at session entry through a verified host entry point, or explicitly when automatic entry is unavailable. Its existence does not prove a host hook is active. Do not poll it before every skill.
