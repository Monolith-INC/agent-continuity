# Agent Continuity

[![Release](https://img.shields.io/github/v/release/Monolith-INC/agent-continuity?include_prereleases&sort=semver&label=release)](https://github.com/Monolith-INC/agent-continuity/releases)
[![Tag](https://img.shields.io/github/v/tag/Monolith-INC/agent-continuity?label=latest%20tag)](https://github.com/Monolith-INC/agent-continuity/tags)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-plugin-1f6feb?logo=anthropic&logoColor=white)](https://code.claude.com/docs/en/plugins)
[![Obsidian](https://img.shields.io/badge/Obsidian-vault%20native-7c3aed?logo=obsidian&logoColor=white)](https://obsidian.md/)
[![Version](https://img.shields.io/badge/plugin-v0.12.1-0ea5e9)](./.plugin/plugin.json)

**Durable knowledge for coding agents.** Pair your repository with an Obsidian vault so agents keep orientation, tickets, style, and architecture context across sessions—instead of rediscovering the project every time.

```bash
# Claude Code (recommended)
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/claude/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main

# Cursor
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/cursor/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

Claude alternative (marketplace add from this repo):

```text
/plugin marketplace add Monolith-INC/agent-continuity
/plugin install agent-continuity@agent-continuity
```

Then `/reload-plugins` (or restart Claude Code / Reload Window in Cursor).

---

## The problem

Coding agents are powerful **inside a session** and amnesic **across sessions**.

Without a durable store they:

- Re-read random markdown and invent project structure
- Lose open tickets, decisions, and style conventions
- Drift filename/frontmatter patterns until the vault is unqueryable
- Treat notes as disposable chat residue instead of a source of truth

Chat history is not a knowledge base. A pile of `.md` files without conventions is not one either.

## The solution

**Agent Continuity** makes an **Obsidian vault** the agent’s canonical knowledge base, then enforces the loop that keeps it useful:

| Layer | Role |
| --- | --- |
| **Vault** | Durable notes: tickets, knowledge, sessions, architecture |
| **Hooks** | Always-on: bootstrap orientation, allowlist reads, gate naming/frontmatter |
| **Skills** | On-demand: scaffold, mine history into notes, query Bases, ingest research, lint drift |
| **Archetypes** | Research-backed vault shapes (`software-project`, `research`, `personal-pkm`, `technical-docs`) |

```mermaid
flowchart LR
  subgraph Repo["Code repository"]
    Code[Source + CLAUDE.md]
    Rules[".agent/rules"]
  end

  subgraph Plugin["agent-continuity plugin"]
    Hooks[Hooks]
    Skills[Skills]
  end

  subgraph Vault["Obsidian vault"]
    Orient[README + Agent_Orientation]
    Tickets[Tickets / Features]
    Knowledge[Knowledge]
    Bases[".base dashboards"]
  end

  Code --> Hooks
  Hooks -->|SessionStart injects| Orient
  Hooks -->|allowlist + naming| Vault
  Skills -->|scaffold / mine / query / lint| Vault
  Skills --> Rules
  Bases -->|obsidian CLI| Skills
```

---

## How it works

### Always-on hooks

```mermaid
sequenceDiagram
  participant U as User / session
  participant H as Hooks
  participant V as Vault
  participant A as Agent tools

  U->>H: SessionStart
  H->>V: Read bootstrap files
  H-->>U: Inject orientation as additionalContext

  A->>H: Read/Grep *.md
  alt Path allowlisted or inside vault
    H-->>A: Allow
  else Project markdown off-allowlist
    H-->>A: Deny (prefer structured vault channel)
  end

  A->>H: Write *.md inside marked vault
  alt Filename + frontmatter match archetype
    H-->>A: Allow
  else Structural violation
    H-->>A: Deny with fix guidance
  end
```

1. **`SessionStart` — orientation injection**  
   Loads vault `README.md` + `Knowledge/Agent_Orientation.md` (configurable) into session context so every run starts oriented.

2. **`PreToolUse(Read|Grep)` — markdown allowlist**  
   Blocks casual reads of project `.md` outside a small allowlist and the vault. Pushes agents toward the vault / Bases instead of scraping every doc.

3. **`PreToolUse(Write)` — archetype naming enforcement**  
   Inside a marked vault, denies writes whose **filename shape** or **frontmatter keys** violate the archetype spec. Fail-open outside marked vaults.

### Skills (interactive, confirm-before-write)

Most skills are walkthroughs: inspect → propose → confirm → write. They do **not** overwrite without per-file approval. `query-vault` is the exception: read-only and model-invocable.

```mermaid
flowchart TD
  Start([Adopt Agent Continuity]) --> IW[init-workspace]
  IW --> IV[init-vault]
  IV --> IR[init-rules]
  IR --> Ready([Day-to-day ready])

  Ready --> Q[query-vault]
  Ready --> RI[research-ingest]
  Ready --> CM[canvas-map]
  Ready --> MS[mine-style]
  Ready --> AR[add-refactor-entry]
  Ready --> MB[mine-bases]
  Ready --> VL[vault-lint]

  MB --> Bases[(Obsidian Bases)]
  Q --> Bases
```

---

## Skills catalog

Invoke as `/agent-continuity:<skill>`.

### Init — stand up the system

| Skill | Purpose | When to use | What to expect |
| --- | --- | --- | --- |
| **`init-workspace`** | Scaffold root + per-project `CLAUDE.md` from stack detection (`package.json`, `pubspec.yaml`, etc.) | New repo, or existing repo with no agent entrypoints | Proposed file tree; writes only after you approve each file |
| **`init-vault`** | Scaffold an Obsidian vault from an **archetype**; writes `.agent-continuity-vault.json` | First-time vault, or adopting the plugin on a project | Folder skeleton, orientation notes, optional `.base` dashboards (software-project); marker for hooks/lint |
| **`init-rules`** | Drop starter `.agent/rules/*.md` templates | Empty or missing rules set | Templates for implementation lock, architect protocol, git workflow, date/time handling |

**Archetypes** for `init-vault --type`:

| Type | Best for | Method basis |
| --- | --- | --- |
| `software-project` (default) | Agile/XP codebases | Tickets by status folder + Knowledge hybrid |
| `research` | Academic / research | Zettelkasten + PARA + MOCs |
| `personal-pkm` | Life / general PKM | PARA |
| `technical-docs` | Product / library docs | Diátaxis |

### Mining — turn history into canon

| Skill | Purpose | When to use | What to expect |
| --- | --- | --- | --- |
| **`mine-style`** | Mine an author’s git history into a canonical style-examples Knowledge note | You want agents to imitate real project style, not generic advice | Draft note with file/line anchors + Agent Rules block; confirm before write |
| **`add-refactor-entry`** | Append a before/after entry to the Style Refactor Catalog from a commit | After a meaningful refactor commit | Diff-derived catalog entry annotated with the principle applied |
| **`mine-bases`** | Backfill frontmatter + emit Obsidian Bases over Tickets/Features/Agent_Sessions | Vault exists but has no queryable dashboards | Property backfill (safe prepend), `.base` boards; status stays folder-encoded |

### Query & visualize — live vault channel

| Skill | Purpose | When to use | What to expect |
| --- | --- | --- | --- |
| **`query-vault`** | Read-only live queries via Obsidian CLI (`base:query`, `search`, `backlinks`) | Need open tickets, features by area, recent sessions, or search—without raw file dumps | Structured results when Obsidian is open; graceful degrade otherwise. **Model-invocable** |
| **`canvas-map`** | Build a JSON Canvas map for a hub note (links + backlinks) into `Architecture/` | Explaining or documenting a domain hub’s relationship graph | Validated `.canvas` with hub centered, outgoing/backlink sides, arrowed edges |

### Research & maintenance

| Skill | Purpose | When to use | What to expect |
| --- | --- | --- | --- |
| **`research-ingest`** | Fetch a URL with Defuddle → source-stamped `Knowledge/` reference note | Capturing an external spec/article into the vault with provenance | `type: reference` note + frontmatter (`source`/`domain`/`retrieved`) + index-friendly shape |
| **`vault-lint`** | Audit vault vs archetype; propose/fix drift | Legacy vault, rename mess, or pre-archetype notes | Structural report (filenames, frontmatter, strays, duplicate ticket ids) + semantic pass; `git mv` + wikilink repair on confirm |

---

## Typical workflows

### Cold start (new project)

```mermaid
flowchart LR
  A[Install plugin] --> B[init-workspace]
  B --> C[init-vault]
  C --> D[init-rules]
  D --> E[Optional: mine-style / mine-bases]
  E --> F[Code with hooks on]
```

1. Install + reload plugins  
2. `/agent-continuity:init-workspace`  
3. `/agent-continuity:init-vault` (pick archetype)  
4. `/agent-continuity:init-rules`  
5. As notes accumulate: `mine-bases`, `mine-style`

### Daily agent loop

```mermaid
flowchart TD
  S[Session starts] --> B[Orientation injected]
  B --> W{Need vault state?}
  W -->|yes| Q[query-vault]
  W -->|no| Work[Implement against code]
  Q --> Work
  Work --> N{New knowledge?}
  N -->|URL / research| RI[research-ingest]
  N -->|Architecture hub| CM[canvas-map]
  N -->|Refactor landed| AR[add-refactor-entry]
  N -->|Drift suspected| VL[vault-lint]
```

### Retrofit an existing vault

1. Ensure a marker exists (or run `vault-lint --type …` / write `.agent-continuity-vault.json`)  
2. `/agent-continuity:mine-bases` to normalize frontmatter + Bases  
3. `/agent-continuity:vault-lint` to fix naming/frontmatter drift  
4. Point `vault.folder` in config if the folder is not `AI_Codex*`

---

## Installation

### One-command install

One command upgrades in place (replaces any prior managed install).

```bash
# Claude Code
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/claude/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main

# Cursor
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/cursor/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main

# Codex
curl -fsSL https://raw.githubusercontent.com/Monolith-INC/agent-continuity/main/adapters/codex/install.sh \
  | bash -s -- --repo Monolith-INC/agent-continuity --ref main
```

From a clone: `./adapters/<host>/install.sh`.

### Claude marketplace (also supported)

This repo is a flat Open Plugins package. The root `.claude-plugin/marketplace.json` points at `./`, so GitHub marketplace add still works:

```text
/plugin marketplace add Monolith-INC/agent-continuity
/plugin install agent-continuity@agent-continuity
```

Open `/hooks` or restart the host so SessionStart / PreToolUse hooks attach to the current session.

### Dependencies

**Required for hooks:** `bash`, `jq`, `realpath`, `python3` (stdlib only).

**Optional for skills:**

| Skill | Needs |
| --- | --- |
| `query-vault`, `canvas-map` | [`obsidian` CLI](https://github.com/Yakitrak/obsidian-cli) + Obsidian running with the vault open |
| `research-ingest` | [`defuddle`](https://github.com/kepano/defuddle) (`npm install -g defuddle`) |

---

## Configuration

Zero-config default: autodetect vault folder via `AI_Codex*/`, bootstrap `README.md` + `Knowledge/Agent_Orientation.md`, sensible markdown allowlist.

Optional project file: `.claude/agent-continuity.config.json`

```json
{
  "vault": {
    "folder": "AI_Codex_MyProject",
    "bootstrap": [
      "README.md",
      "Knowledge/Agent_Orientation.md"
    ]
  },
  "markdownAllowlist": {
    "patterns": [
      "CLAUDE.md",
      "GEMINI.md",
      ".agent/*",
      "docs/*",
      "projects/*/CLAUDE.md",
      "projects/*/GEMINI.md",
      "projects/*/.agent/*",
      "projects/*/e2e_test/*"
    ]
  },
  "namingEnforcement": {
    "enabled": true
  }
}
```

See [`examples/agent-continuity.config.example.json`](./examples/agent-continuity.config.example.json).

**Legacy (still read):** `.claude/codex-workflow.config.json`, `codex.folder` / `codex.bootstrap`, marker `.codex-vault.json`.

---

## What the plugin package contains

Flat Open Plugins layout (repo root = plugin):

```text
agent-continuity/
├── .plugin/plugin.json           ← Open Plugins manifest
├── .claude-plugin/               ← Claude marketplace + plugin manifests
│   ├── marketplace.json          ← source: ./
│   └── plugin.json
├── hooks/                        ← SessionStart + PreToolUse
├── skills/                       ← ten interactive skills
├── archetypes/                   ← four vault specs + marker contract
├── scripts/vault-lint.py         ← deterministic structural scanner
├── references/                   ← frontmatter convention
├── examples/                     ← config example
├── adapters/                     ← Cursor / Claude / Codex build + curl install
├── docs/
└── README.md
```

Deep dives:

- [Former package README](./docs/plugin-package-readme.md) — hooks internals, layout, roadmap history  
- [Vault archetypes](./archetypes/README.md)  
- [Frontmatter convention](./references/frontmatter-convention.md)  
- [Obsidian leverage map](./docs/obsidian-leverage.md)  
- [Host matrix](./docs/HOST_MATRIX.md)

---

## Design principles

1. **Vault is canon** — orientation and durable decisions live in Obsidian, not only in chat.  
2. **Non-destructive by default** — skills propose; users confirm; prefer deprecate over delete.  
3. **Status by folder** — ticket status is the path (`Tickets/Active/…`), never a duplicated `status:` field.  
4. **Structure is enforceable; semantics are lintable** — hooks gate shape/keys; `vault-lint` handles judgment calls.  
5. **Fail-open outside the contract** — no marker / unknown archetype → hooks do not block ordinary work.  
6. **Structured read channel** — prefer Bases / `query-vault` over scraping every markdown file.

---

## Migration from `codex-workflow`

| Old | New |
| --- | --- |
| Marketplace / plugin id `codex-workflow(-marketplace)` | `agent-continuity` |
| Skills `/codex-workflow:codex-*` | `/agent-continuity:<skill>` (e.g. `init-vault`) |
| Config `.claude/codex-workflow.config.json` | `.claude/agent-continuity.config.json` (legacy still read) |
| Keys `codex.folder` / `codex.bootstrap` | `vault.folder` / `vault.bootstrap` (legacy still read) |
| Marker `.codex-vault.json` | `.agent-continuity-vault.json` (legacy still read) |

`AI_Codex*/` vault autodetection is unchanged.

---

## Versioning & releases

Plugin version is declared in [`VERSION`](./VERSION), [`.plugin/plugin.json`](./.plugin/plugin.json), and the Claude marketplace/plugin manifests (lockstep-checked by `scripts/validate.sh`). Release tags follow `agent-continuity--vX.Y.Z`.

---

## License / contributing

Issues and PRs welcome at [Monolith-INC/agent-continuity](https://github.com/Monolith-INC/agent-continuity). Prefer additive changes; mark deprecated paths instead of silent deletes.
