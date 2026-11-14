---
name: reconcile-sessions
description: Upgrade Agent_Sessions records that are not in the current format (missing or invalid status, more than one ongoing record, missing forward links) and refresh the session index. Use when the start menu reports old-format or unreadable records, after importing older session notes, or when the user asks to "fix / reconcile / upgrade the session records".
argument-hint: "[--apply]"
allowed-tools: Read Bash(python3 *)
---

# Reconcile session records

The session start hook already runs this automatically (apply, then report) when it
finds old-format records or when the plugin version changed. Use this skill to run it
on demand.

## Step 1 — Preview

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/reconcile_sessions.py" --project "${CLAUDE_PROJECT_DIR:-$PWD}"
```

It lists each record it would change and why. Nothing is written yet.

## Step 2 — Apply

If the user passed `--apply`, or agrees after seeing the preview:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/reconcile_sessions.py" --project "${CLAUDE_PROJECT_DIR:-$PWD}" --apply
```

What it changes, and nothing else:

- Adds `date`, `type` and a valid `status` to the frontmatter when missing.
- Keeps only the newest record that is not archived as `ongoing`; older ongoing records become `closed`.
- Appends `Next session: [[<successor>]]` to any record that has no forward link.

Each original is kept as `<vault>/.agent-continuity/backups/<stamp>/<name>.md.bak`, and
the session index is refreshed.

## Step 3 — Report

Tell the user in one or two lines how many records changed and where the backups are.
Records the tool reports as unreadable are left as they are; do not stop work over them.
The next session record notes the problem in one line and links back to the last
readable record.
