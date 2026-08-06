#!/usr/bin/env bash
# SessionStart hook: inject Agent Continuity orientation as additionalContext.
#
# Config (preferred): $CLAUDE_PROJECT_DIR/.claude/agent-continuity.config.json
# Legacy fallback:    $CLAUDE_PROJECT_DIR/.claude/codex-workflow.config.json
#   .vault.folder / .codex.folder       — vault folder name (defaults to glob AI_Codex*/)
#   .vault.bootstrap / .codex.bootstrap — relative paths to inject (defaults to
#                                        README.md + Knowledge/Agent_Orientation.md)
#
# Behavior:
#   - If config exists, its values win.
#   - If no config and no AI_Codex*/ folder found, the hook is a silent no-op.
#   - Missing individual files are noted inline rather than aborting.

set -euo pipefail

project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"
config=""
if [[ -f "$project_dir/.claude/agent-continuity.config.json" ]]; then
  config="$project_dir/.claude/agent-continuity.config.json"
elif [[ -f "$project_dir/.claude/codex-workflow.config.json" ]]; then
  config="$project_dir/.claude/codex-workflow.config.json"
fi

vault_folder=""
if [[ -n "$config" ]]; then
  vault_folder="$(jq -r '.vault.folder // .codex.folder // ""' "$config")"
fi

if [[ -z "$vault_folder" ]]; then
  for d in "$project_dir"/AI_Codex*/; do
    [[ -d "$d" ]] || continue
    vault_folder="$(basename "$d")"
    break
  done
fi

if [[ -z "$vault_folder" ]] || [[ ! -d "$project_dir/$vault_folder" ]]; then
  exit 0
fi

files=()
if [[ -n "$config" ]]; then
  while IFS= read -r f; do
    [[ -n "$f" ]] && files+=("$f")
  done < <(jq -r '(.vault.bootstrap // .codex.bootstrap // [])[]? // empty' "$config")
fi
if [[ ${#files[@]} -eq 0 ]]; then
  files=("README.md" "Knowledge/Agent_Orientation.md")
fi

vault_root="$project_dir/$vault_folder"

# Only include files that actually exist; silently skip missing ones.
present_files=()
for f in "${files[@]}"; do
  [[ -f "$vault_root/$f" ]] && present_files+=("$f")
done

if [[ ${#present_files[@]} -eq 0 ]]; then
  exit 0
fi

context="$(
  printf '=== Agent Continuity bootstrap (auto-loaded via SessionStart hook) ===\n'
  printf 'Source: %s\n' "$vault_folder"
  for f in "${present_files[@]}"; do
    printf '\n--- %s/%s ---\n' "$vault_folder" "$f"
    cat -- "$vault_root/$f"
  done
)"

jq -n --arg ctx "$context" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
