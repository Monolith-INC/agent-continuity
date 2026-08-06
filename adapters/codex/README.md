# Codex adapter

## Install (users)

One command for this repo:

```bash
curl -fsSL https://raw.githubusercontent.com/theocarranza/agent-continuity/main/adapters/codex/install.sh \
  | bash -s -- --repo theocarranza/agent-continuity --ref main
```

Forks: replace `theocarranza/agent-continuity` with `OWNER/REPO`.

From a local clone:

```bash
./adapters/codex/install.sh
```

Copies a durable marketplace under `~/.agents/plugins/agent-continuity-codex-marketplace`, then runs:

```bash
codex plugin marketplace add <durable-path>
codex plugin add agent-continuity@agent-continuity-local
```

Restart Codex or start a new thread, then invoke `/agent-continuity:query-vault`.

Flags: `--dry-run`, `--uninstall`, `--prefix DIR` (copies marketplace only; prints CLI commands and skips registration).

## Authoring / build

```bash
python3 adapters/codex/build_plugin.py
```

## Fallback

Load the repo root as an Open Plugins directory when the host supports `.plugin/plugin.json`.

## Note

Some Codex setups place agents outside the plugin tree. Keep Codex-specific agent files under `adapters/codex/agents/` and document any out-of-plugin install steps here as you add them.
