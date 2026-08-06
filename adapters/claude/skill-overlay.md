## Claude Code adapter execution

This installed Claude Code edition adds host-specific guidance on top of the portable Agent Continuity skills.

1. Prefer namespaced skills such as `/agent-continuity:query-vault`.
2. Hooks resolve via `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`; Claude continues to expand `CLAUDE_PLUGIN_ROOT`.
3. Claude-only skill frontmatter (`allowed-tools`, `disable-model-invocation`) remains in the portable skills for now — do not strip it during packaging.
