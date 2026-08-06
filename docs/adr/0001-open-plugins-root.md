# ADR 0001 — Open Plugins root as the primary layout

## Status

Accepted, 2026-08-05.

## Context

Hosts differ on vendor-prefixed metadata directories (`.cursor-plugin/`, `.claude-plugin/`, `.codex-plugin/`). The Open Plugins specification recommends vendor-neutral `.plugin/plugin.json` with components at the plugin root.

## Decision

The repository root is a single Open Plugins package. Day-to-day development and direct `--plugin-dir` loads use this layout. Host adapters are optional and emit vendor-prefixed manifests under `dist/`.

## Consequences

- New contributors start from `.plugin/plugin.json` + `skills/`.
- Marketplace zips are generated, not hand-maintained.
