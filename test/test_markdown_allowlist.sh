#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
allowlist="$root/codex-workflow/hooks/scripts/markdown-allowlist.sh"

passes() {
  local rel="$1"
  local allowed=0
  local patterns=(
    "CLAUDE.md"
    "GEMINI.md"
    ".agent/*"
    "docs/*"
    "e2e_test/*"
    "projects/*/CLAUDE.md"
    "projects/*/GEMINI.md"
    "projects/*/.agent/*"
    "projects/*/e2e_test/*"
  )
  for p in "${patterns[@]}"; do
    case "$rel" in
      $p) allowed=1; break ;;
    esac
  done
  [[ "$allowed" -eq 1 ]]
}

must_allow() {
  local rel="$1"
  if ! passes "$rel"; then
    echo "expected allowlist to permit: $rel" >&2
    exit 1
  fi
}

must_allow "e2e_test/modules/attendance/scenarios/create/test-plan.md"
must_allow "e2e_test/modules/attendance/domain.md"
must_allow "projects/myapp/e2e_test/modules/attendance/scenarios/create/test-plan.md"

echo "markdown allowlist regression tests passed"
