# Changelog

## 0.13.0

- SessionStart now offers a start menu built from the newest `Agent_Sessions/` records: resume the most recent ongoing session, pick a recent one, or start fresh.
- Session records carry an explicit `status: ongoing | closed | archived` (now required for new writes in the `software-project` archetype). Archived records are hidden from the menu. Older records without a status fall back to the forward-link rule.
- The naming hook checks enum values through an optional `values` map in archetype frontmatter rules.
- New `Stop` hook asks the agent to checkpoint the ongoing session record when project files changed after it was last written. New `UserPromptSubmit` hook reminds it to log `## Decision` entries. Both live in `hooks/scripts/session_freshness.py`; turn them off with `vault.freshness.enabled: false`.
- New `hooks/scripts/session_options.py`; tests for all new hook behavior in `hooks/tests/`, run in CI.
- New optional config `vault.sessionOptions` (`enabled`, `recent` default 3, `folder` default `Agent_Sessions`) and `vault.freshness` (`enabled`).
- `init-workspace` session bootstrap steps now start from the menu instead of reading the two newest records.
- Session registry index: SessionStart loads `Agent_Sessions/` once into `<vault>/.agent-continuity/session-index.json` (git-ignored), re-reading only changed records. The Stop and UserPromptSubmit hooks read the index instead of scanning the folder. Only the newest record that is not archived can be ongoing, so an old record without a status can no longer be picked up as the current session.
- Checkpoints are asked for only when a rule fires: first change to a file, a new commit, a commit rolled back or amended, or a push (detected from git), unless the record was already updated. Plan tasks, code reviews and session end are agent rules in `init-workspace`.
- Sessions are capped at 8 hours. The start menu asks before resuming a session from a different checkout, and recovers from an unreadable record by continuing from the last readable one without asking.
- New `reconcile-sessions` skill and `hooks/scripts/reconcile_sessions.py`: upgrade old-format records (status, single ongoing, forward links) with backups. Runs automatically at session start when old-format records are found or the plugin version changed; installers take `--project DIR` to run it right away.
- The vault must sit inside the project folder. A setting that points outside (absolute path, `..`, or a link) is ignored, the default `AI_Codex*/` folder is used, and the agent is told to ask the user for the correct folder.

## 0.12.3

- Codex marketplace fix: built adapters emit `.agents/plugins/marketplace.json` (Codex does not accept `.codex-plugin/` alone).
- Repo-root marketplace indexes for hassle-free host installs: `.agents/plugins/marketplace.json`, `.cursor-plugin/marketplace.json` (+ plugin.json), keep `.claude-plugin/`.
- Document all install options per host (curl, Claude `/plugin`, Codex CLI marketplace, Cursor team import / public submit).

## 0.12.2

- Dedicated `adapters/<host>/uninstall.sh`; removed `--uninstall` from `install.sh`.

## 0.12.1

- Install script upgrades in one command (replaces prior managed install).
- Dedicated `adapters/<host>/uninstall.sh` (no `--uninstall` on install.sh).

## 0.12.0

- Flatten plugin to Open Plugins layout at repo root (`.plugin/plugin.json`).
- Marketplace source is `./` (single-plugin repo).
- Add host adapters, curl installers, VERSION lockstep packaging, and CI.
- Hooks resolve via `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`.

## 0.11.1

- Docs: comprehensive README and harness-safe descriptions.

## Earlier

See `docs/plugin-package-readme.md` and `STATUS.md` for pre-0.11.1 history.
