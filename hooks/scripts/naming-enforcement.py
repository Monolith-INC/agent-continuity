#!/usr/bin/env python3
"""PreToolUse(Write) hook: structural naming + frontmatter enforcement for agent vaults.

Activates only when the target .md file lives inside a vault that declares its archetype
via a vault marker (written by init-vault). Outside such a vault it is a silent no-op
(fail-open), so it never blocks ordinary code/file writes.

Marker (preferred): .agent-continuity-vault.json
Legacy fallback:    .codex-vault.json

It enforces only what regex/sets can decide — filename SHAPE, required/forbidden
frontmatter keys, and allowed values for enum keys (a rule's optional "values" map) — per the active archetype spec in ../archetypes/<type>.json. Semantic
issues (language, near-duplicates, stray files) are the linter's job, not this hook's.

Disable per project via .claude/agent-continuity.config.json
(or legacy .claude/codex-workflow.config.json) -> {"namingEnforcement":{"enabled":false}}.
"""
import sys, os, json, re

MARKER_NAMES = (".agent-continuity-vault.json", ".codex-vault.json")
CONFIG_NAMES = ("agent-continuity.config.json", "codex-workflow.config.json")


def allow():
    sys.exit(0)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def match_dir(glob, reldir):
    pref = glob[:-3] if glob.endswith("/**") else glob
    return reldir == pref or reldir.startswith(pref + "/")


def find_marker(directory):
    for name in MARKER_NAMES:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path
    return None


def resolve_config(project_dir):
    if not project_dir:
        return ""
    for name in CONFIG_NAMES:
        path = os.path.join(project_dir, ".claude", name)
        if os.path.isfile(path):
            return path
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        allow()

    if data.get("tool_name") != "Write":
        allow()
    fp = (data.get("tool_input") or {}).get("file_path", "")
    if not fp:
        allow()
    fp_abs = os.path.abspath(fp)
    if not fp_abs.lower().endswith(".md"):
        allow()

    # Find the vault root: walk up for the marker.
    d = os.path.dirname(fp_abs)
    vault = None
    marker_path = None
    while True:
        found = find_marker(d)
        if found:
            vault = d
            marker_path = found
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    if not vault:
        allow()  # not inside a marked vault -> fail-open

    # Optional per-project disable.
    cfg = resolve_config(os.environ.get("CLAUDE_PROJECT_DIR", ""))
    if cfg:
        try:
            c = json.load(open(cfg))
            if c.get("namingEnforcement", {}).get("enabled", True) is False:
                allow()
        except Exception:
            pass

    try:
        vtype = json.load(open(marker_path)).get("type", "")
    except Exception:
        allow()
    plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    spec_path = os.path.join(plugin_root, "archetypes", f"{vtype}.json")
    if not os.path.isfile(spec_path):
        allow()  # unknown archetype -> fail-open
    spec = json.load(open(spec_path))

    rel = os.path.relpath(fp_abs, vault).replace(os.sep, "/")
    reldir = os.path.dirname(rel)
    base = os.path.basename(rel)[:-3]  # strip .md
    top = rel.split("/", 1)[0] if "/" in rel else ""

    naming = spec.get("naming", {})
    exempt = naming.get("exempt", {})
    if os.path.basename(rel) in exempt.get("basenames", []):
        allow()
    if top in exempt.get("folders", []):
        allow()

    # Filename shape: first rule whose match-glob covers reldir, else default.
    rule = None
    for r in naming.get("rules", []):
        if match_dir(r["match"], reldir):
            rule = r
            break
    if rule is None:
        rule = naming.get("default")
    if rule and not re.match(rule["filename"], base):
        deny(
            f"agent-continuity naming ({vtype}): '{base}.md' does not match the convention for "
            f"{(reldir + '/') if reldir else 'the vault root'} — expected {rule.get('style','')} "
            f"(e.g. {rule.get('example','')}). Rename to match, or see archetypes/{vtype}.json."
        )

    # Frontmatter keys: parse the leading --- block of the content being written.
    fm_keys = set()
    fm_values = {}
    content = (data.get("tool_input") or {}).get("content", "")
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*(\n|$)", content, re.S)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$", line)
            if mm:
                fm_keys.add(mm.group(1))
                fm_values[mm.group(1)] = mm.group(2).strip("'\"")

    fmrule = None
    for fr in spec.get("frontmatter", []):
        if match_dir(fr["match"], reldir):
            fmrule = fr
            break
    if fmrule:
        missing = [k for k in fmrule.get("required", []) if k not in fm_keys]
        forbidden = [k for k in fmrule.get("forbidden", []) if k in fm_keys]
        invalid = [
            f"{k}={fm_values[k]!r} (allowed: {', '.join(allowed)})"
            for k, allowed in fmrule.get("values", {}).items()
            if k in fm_values and fm_values[k] not in allowed
        ]
        if missing or forbidden or invalid:
            parts = []
            if missing:
                parts.append("missing required key(s): " + ", ".join(missing))
            if forbidden:
                parts.append("forbidden key(s) present: " + ", ".join(forbidden))
            if invalid:
                parts.append("invalid value(s): " + "; ".join(invalid))
            deny(
                f"agent-continuity frontmatter ({vtype}, {(reldir + '/') if reldir else 'root'}): "
                + "; ".join(parts)
                + f". required={fmrule.get('required', [])}, forbidden={fmrule.get('forbidden', [])}."
            )

    allow()


if __name__ == "__main__":
    main()
