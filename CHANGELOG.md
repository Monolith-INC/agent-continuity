# Changelog

## 0.13.0

- SessionStart now offers a start menu built from the newest `Agent_Sessions/` records: resume the most recent ongoing session, pick a recent one, or start fresh.
- Session records carry an explicit `status: ongoing | closed | archived` (now required for new writes in the `software-project` archetype). Archived records are hidden from the menu. Older records without a status fall back to the forward-link rule.
- The naming hook checks enum values through an optional `values` map in archetype frontmatter rules.
- New `Stop` hook asks the agent to checkpoint the ongoing session record when project files changed after it was last written. New `UserPromptSubmit` hook reminds it to log `## Decision` entries. Both live in `hooks/scripts/session_freshness.py`; turn them off with `vault.freshness.enabled: false`.
- New `hooks/scripts/session_options.py`; tests for all new hook behavior in `hooks/tests/`, run in CI.
- New optional config `vault.sessionOptions` (`enabled`, `recent` default 3, `folder` default `Agent_Sessions`) and `vault.freshness` (`enabled`).
- `init-workspace` session bootstrap steps now start from the menu instead of reading the two newest records.

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
