# Changelog

## 0.13.0

- Add session continuation, checkpoint and recovery skills backed by one standard-library Python runtime.
- Restore progress across chats, link eight-hour continuations, deduplicate retries and first-file edits, and preserve unreadable records while recovering context.
- Isolate chat chains, detect context changes, use nonblocking process locks and atomic file replacement, and report recoverable persistence failures without gating work.
- Add lifecycle, recovery and filesystem tests to CI. Automatic host event capture and archival are not included.

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
