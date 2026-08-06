## Codex adapter execution

This installed Codex edition adds host-specific guidance on top of the portable Agent Continuity skills.

1. Prefer namespaced skills such as `/agent-continuity:query-vault`.
2. Hooks resolve via `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`.
3. Keep archetypes and vault-lint in the shipped plugin payload.
