# Host matrix

| Concern | Open Plugins (repo root) | Cursor adapter | Claude adapter | Codex adapter |
| --- | --- | --- | --- | --- |
| Manifest | `.plugin/plugin.json` | `.cursor-plugin/plugin.json` | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Marketplace index | n/a (single plugin) | `.cursor-plugin/marketplace.json` | `.claude-plugin/marketplace.json` | `.codex-plugin/marketplace.json` |
| Plugin root placeholder | `${PLUGIN_ROOT}` | `${PLUGIN_ROOT}` / host equivalents | `${CLAUDE_PLUGIN_ROOT}` / `${PLUGIN_ROOT}` | host-specific |
| Overlay source | none | `adapters/cursor/skill-overlay.md` | `adapters/claude/skill-overlay.md` | `adapters/codex/skill-overlay.md` |
| Build output | n/a | `dist/cursor-marketplace/` | `dist/claude-marketplace/` | `dist/codex-marketplace/` |

Standards:

- [Open Plugins Specification](https://open-plugins.com/plugin-builders/specification)
- [Agent Skills Specification](https://agentskills.io/specification)
- [OpenSkills catalog](https://openskills.cc/) (discovery/install, not the format standard)
