---
name: init-vault
description: Scaffold an Agent Continuity Obsidian vault from a research-backed archetype (software-project, research, personal-pkm, technical-docs). Reads the archetype spec for folder structure and conventions, scaffolds the skeleton, writes a .agent-continuity-vault.json marker, and seeds archetype-appropriate files. Use when a project adopting Agent Continuity needs a new vault, or the user asks to "create the agent vault" / "scaffold the agent knowledge vault".
disable-model-invocation: true
argument-hint: [--type <software-project|research|personal-pkm|technical-docs>]
allowed-tools: Read Write Glob Bash(ls *) Bash(mkdir *) Bash(basename *) Bash(jq *) Bash(date *) Bash(cat *)
---

# Scaffold an Agent Continuity vault from an archetype

Interactive walkthrough. Choose archetype, inspect, propose, confirm, write. The archetype
spec is the single source of truth for folder structure, naming, and frontmatter — the same
spec the `PreToolUse(Write)` enforcement hook and `vault-lint` read, so scaffold,
enforcement, and audit never disagree.

## Step 1 — Choose the archetype

Take `--type <archetype>` from `$ARGUMENTS`, or ask. See
`${CLAUDE_PLUGIN_ROOT}/archetypes/README.md` for the full rationale.

| `--type` | For | Basis |
|---|---|---|
| `software-project` | Agile/XP codebases (default) | Project + knowledge hybrid; status-by-folder |
| `research` | Academic / research projects | Zettelkasten + PARA + MOCs |
| `personal-pkm` | General knowledge management | PARA |
| `technical-docs` | Product/library documentation | Diataxis |

Load and sanity-check the spec:

```bash
TYPE=software-project                                   # from --type or the user's choice
SPEC="${CLAUDE_PLUGIN_ROOT}/archetypes/${TYPE}.json"
jq -e . "$SPEC" >/dev/null && jq -r '.title + " — " + .description' "$SPEC"
```

## Step 2 — Decide the vault folder name

Default `AI_Codex_<ProjectName>` (ProjectName = repo basename in CamelCase). The `SessionStart`
hook autodetects via glob `AI_Codex*/`, so any `AI_Codex*` name is zero-config; other names need
`vault.folder` in `.claude/agent-continuity.config.json`. Show the proposed name; let the user override.

**The vault must live inside the project folder.** Refuse any name that is an absolute path,
climbs out with `..`, or resolves (through a link) outside the project, and ask for a folder
inside the project instead. The hooks ignore such a setting anyway: they fall back to the
default `AI_Codex*/` folder and tell the agent to ask the user for the correct one.

## Step 3 — Refuse if a vault already exists at that name

Check with `ls`/Glob. If it exists, do not overwrite — offer to pick another name, add only the
missing skeleton pieces (Step 5, skipping anything present), or abort.

## Step 4 — Show the plan and confirm

List exactly what will be created, from the spec, and confirm before writing:

```bash
echo "Folders:";  jq -r '.folders[] | "  \(.path)/  — \(.purpose)"' "$SPEC"
echo "Marker:   .agent-continuity-vault.json  (records type=$TYPE)"
echo "Naming:";  jq -r '.naming.rules[] | "  \(.match) → \(.style)"' "$SPEC"
```

## Step 5 — Scaffold (spec-driven)

Create every folder with a `.gitkeep`, then write the marker. The marker is how the enforcement
hook and `vault-lint` know which archetype governs this vault — do not skip it.

```bash
while IFS= read -r p; do mkdir -p "$VAULT/$p"; : > "$VAULT/$p/.gitkeep"; done < <(jq -r '.folders[].path' "$SPEC")
jq -n --arg t "$TYPE" '{type:$t, specVersion:1}' > "$VAULT/.agent-continuity-vault.json"
```

## Step 6 — Seed files

Keep seed content light — structure accretes from real work; never seed topical notes beyond an
entry note. Replace `<today>` with `date +%Y-%m-%d`.

**Always:** a `README.md` vault map generated from the spec, and a single entry/orientation note.
Generate the README's taxonomy section straight from the spec so it can't drift:

```bash
jq -r '.folders[] | "- **\(.path)/** — \(.purpose)"' "$SPEC"
```

**Per archetype, additionally:**

- `software-project` — `Knowledge/Agent_Orientation.md` (with the slash-command table below),
  `Agent_Sessions/README.md`, and the three Base dashboards `Tickets.base` / `Features.base` /
  `Agent_Sessions.base` (see `mine-bases` and `../references/frontmatter-convention.md`).
  These Bases belong to `software-project` only — it is the archetype with those folders.
- `research` — `MOCs/Home.md` (the root Map of Content) and `Meta/templates/` stubs for
  fleeting / literature / permanent notes.
- `personal-pkm` — `MOCs/Home.md` and a `99 Meta/templates/` stub.
- `technical-docs` — a one-line `index` note in each Diataxis folder and a `Meta/style-guide`
  stub.

Slash-command table for the orientation/entry note:

```markdown
| Command | Purpose |
| --- | --- |
| `/agent-continuity:init-workspace` | Scaffold the CLAUDE.md tree. |
| `/agent-continuity:init-vault` | Scaffold this vault skeleton. |
| `/agent-continuity:init-rules` | Drop starter `.agent/rules/*.md` templates. |
| `/agent-continuity:mine-bases` | Backfill frontmatter + Base dashboards (software-project). |
| `/agent-continuity:query-vault` | Read-only live query of the vault via the Obsidian CLI. |
| `/agent-continuity:canvas-map` | Generate an Architecture Canvas relationship map. |
| `/agent-continuity:research-ingest` | Ingest a URL into a source-stamped reference note. |
| `/agent-continuity:vault-lint` | Audit the vault against its archetype spec. |
```

## Step 7 — Conventions and enforcement

Tell the user where the rules live and how they are enforced:

- **Naming + frontmatter rules are in the spec** (`$SPEC`) — per-folder filename patterns and
  required/optional/forbidden frontmatter keys.
- The **`PreToolUse(Write)` hook reads the same spec** (via the marker) and structurally gates
  new files: wrong filename shape or missing/forbidden frontmatter is rejected. It is fail-open
  outside a marked vault.
- **`vault-lint`** audits an existing vault against the spec for the semantic issues a
  regex cannot catch (mixed languages, near-duplicate notes, stray files).

## Step 8 — Follow-ups

- `/agent-continuity:init-workspace` if there's no CLAUDE.md tree yet (it should reference this vault).
- `/agent-continuity:init-rules` for the `.agent/rules/*` starter set.
- `software-project`: once real notes exist, `/agent-continuity:mine-bases`.
- Open the vault in Obsidian to use wikilinks, Bases, and Canvas.

## Notes

- **One vault = one archetype.** The marker records it; mixing archetypes in a single vault
  defeats the spec, the hook, and the linter.
- The vault is edited by humans and agents alike. Skeleton content is intentionally light.
- If the vault name does not start with `AI_Codex`, set `vault.folder` in
  `.claude/agent-continuity.config.json` so autodetect finds it.

