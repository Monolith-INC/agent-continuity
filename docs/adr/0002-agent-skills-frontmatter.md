# ADR 0002 — Anchor skills on the Agent Skills specification

## Status

Accepted, 2026-08-05.

## Context

OpenSkills catalogs and installs skills, but the portable format is the Agent Skills open standard (`agentskills.io`). Host-specific frontmatter supersets create lock-in.

## Decision

Portable `SKILL.md` frontmatter carries only `name`, `description`, and optional `license`. Host concerns (model, tool grants, marketplace UI, overlays) live under `adapters/`.

OpenSkills is treated as a catalog/installer, not as the specification itself.

## Consequences

- Skills remain loadable by any Agent Skills-conformant host.
- Adapter overlays may append host execution sections at build time without mutating the canonical skill.
