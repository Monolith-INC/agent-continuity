# Host adapters (optional)

Use the **flat Open Plugins root** (`.plugin/plugin.json` + `skills/`) for day-to-day development and hosts that load a plugin directory directly.

Use **adapters** only when you need host-native marketplace trees, vendor-prefixed manifests, or host-specific skill overlays.

| Host | Builder | Manifest directory | User install |
| --- | --- | --- | --- |
| Cursor | `adapters/cursor/build_plugin.py` | `.cursor-plugin/` | `install.sh` / `uninstall.sh` |
| Claude Code | `adapters/claude/build_plugin.py` | `.claude-plugin/` | `install.sh` / `uninstall.sh` |
| Codex | `adapters/codex/build_plugin.py` | `.codex-plugin/` | `install.sh` / `uninstall.sh` |

## End-user install (primary path)

Plain install upgrades in place. Each host has its own copy-paste blocks.

### Claude Code

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/claude/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

Uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/claude/uninstall.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

### Cursor

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/cursor/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

Uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/cursor/uninstall.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

### Codex

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/codex/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

Uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/codex/uninstall.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

From a clone: `./adapters/<host>/install.sh` or `./adapters/<host>/uninstall.sh`. Shared helpers: `_install_lib.sh`, `_uninstall_lib.sh`, `_install_lib.py`.

Forks: replace `Monolith-INC/agent-continuity` with `OWNER/REPO`.


## Build flow

1. Copy portable `skills/*/` into `dist/<host>-marketplace/plugins/agent-continuity/skills/*/`
2. Inject `skill-overlay.md` into a **copy** of `SKILL.md` (canonical source is never mutated)
3. Copy shared components (`agents/`, `commands/`, `rules/`, `hooks/`, `scripts/lint.sh`)
4. Write vendor + vendor-neutral manifests
5. Emit `BUILD-MANIFEST.json` and an optional fixed-timestamp zip

```bash
python3 adapters/cursor/build_plugin.py
python3 adapters/claude/build_plugin.py
python3 adapters/codex/build_plugin.py
# or
./scripts/build_all.sh
```

`dist/` is gitignored. Do not hand-edit generated trees.
