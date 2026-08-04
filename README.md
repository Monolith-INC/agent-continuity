# agent-continuity

A single-plugin Claude Code marketplace shipping [`agent-continuity`](./agent-continuity) — **Agent Continuity**: portable hooks and skills that pair a code monorepo with an Obsidian vault as the agent's durable, canonical knowledge base.

## For users

Add this marketplace and install the plugin in any project:

```text
/plugin marketplace add <github-owner>/agent-continuity
/plugin install agent-continuity@agent-continuity
```

See [`agent-continuity/README.md`](./agent-continuity/README.md) for what the plugin does and how to configure it.

## For maintainers

Layout:

```text
agent-continuity/
├── .claude-plugin/
│   └── marketplace.json      ← marketplace manifest
├── agent-continuity/           ← the plugin itself
│   └── ...                   ← see plugin README
└── README.md                 ← this file
```

The marketplace manifest declares exactly one plugin (`agent-continuity`) sourced from the sibling directory.


## Migration from `codex-workflow`

| Old | New |
| --- | --- |
| Marketplace / plugin id `codex-workflow(-marketplace)` | `agent-continuity` |
| Skills `/codex-workflow:codex-*` | `/agent-continuity:<skill>` (e.g. `init-vault`) |
| Config `.claude/codex-workflow.config.json` | `.claude/agent-continuity.config.json` (legacy file still read) |
| Config keys `codex.folder` / `codex.bootstrap` | `vault.folder` / `vault.bootstrap` (legacy keys still read) |
| Marker `.codex-vault.json` | `.agent-continuity-vault.json` (legacy marker still read) |

Vault folder autodetection (`AI_Codex*/`) is unchanged.

## Versioning

Plugin version is declared in `agent-continuity/.claude-plugin/plugin.json` and mirrored in the marketplace manifest's `plugins[].version`. Bump both when releasing.
