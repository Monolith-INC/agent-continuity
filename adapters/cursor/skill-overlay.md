## Cursor adapter execution

This installed Cursor edition adds host-specific guidance on top of the portable Agent Continuity skills.

1. Prefer namespaced skills such as `/agent-continuity:query-vault`.
2. Hooks resolve via `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` so Open Plugins and Claude hosts both work.
3. Keep archetypes, vault-lint, and naming/allowlist hooks intact — they are the product, not optional template demos.
