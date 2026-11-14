#!/usr/bin/env bash
# SessionStart hook: inject Agent Continuity orientation as additionalContext.
#
# Config (preferred): $CLAUDE_PROJECT_DIR/.claude/agent-continuity.config.json
# Legacy fallback:    $CLAUDE_PROJECT_DIR/.claude/codex-workflow.config.json
#   .vault.folder / .codex.folder       — vault folder name (defaults to glob AI_Codex*/)
#   .vault.bootstrap / .codex.bootstrap — relative paths to inject (defaults to
#                                        README.md + Knowledge/Agent_Orientation.md)
#   .vault.sessionOptions.enabled       — false turns off the start menu (default true)
#   .vault.sessionOptions.recent        — how many recent sessions to list (default 3)
#   .vault.sessionOptions.folder        — session records folder (default Agent_Sessions)
#
# Behavior:
#   - If config exists, its values win.
#   - If no config and no AI_Codex*/ folder found, the hook is a silent no-op.
#   - Missing individual files are silently skipped.
#   - A "Session start options" menu built from the newest session records is
#     appended (see session_options.py), so the agent can offer resume / pick /
#     start fresh before any other work.

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

menu=""
options_enabled="true"
recent="3"
sessions_folder="Agent_Sessions"
if [[ -n "$config" ]]; then
  options_enabled="$(jq -r 'if .vault.sessionOptions.enabled == false then "false" else "true" end' "$config")"
  recent="$(jq -r '.vault.sessionOptions.recent // 3' "$config")"
  sessions_folder="$(jq -r '.vault.sessionOptions.folder // "Agent_Sessions"' "$config")"
fi
if [[ "$options_enabled" == "true" ]] && command -v python3 >/dev/null 2>&1; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  menu="$(python3 "$script_dir/session_options.py" "$vault_root/$sessions_folder" "$recent" 2>/dev/null || true)"
fi

if [[ ${#present_files[@]} -eq 0 ]] && [[ -z "$menu" ]]; then
  exit 0
fi

context="$(
  printf '=== Agent Continuity bootstrap (auto-loaded via SessionStart hook) ===\n'
  printf 'Source: %s\n' "$vault_folder"
  for f in "${present_files[@]}"; do
    printf '\n--- %s/%s ---\n' "$vault_folder" "$f"
    cat -- "$vault_root/$f"
  done
  if [[ -n "$menu" ]]; then
    printf '\n%s\n' "$menu"
  fi
)"

jq -n --arg ctx "$context" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
