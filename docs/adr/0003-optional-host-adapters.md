# ADR 0003 — Host adapters are optional

## Status

Accepted, 2026-08-05.

## Context

Some products need reproducible marketplace trees, vendor manifests, and install docs. Many starters do not.

## Decision

Adapters under `adapters/{cursor,claude,codex}/` are an advanced track. They share `adapters/_build_lib.py`, inject `skill-overlay.md` into skill copies, and write `BUILD-MANIFEST.json` plus optional fixed-timestamp zips. The flat Open Plugins root remains sufficient for local development.

## Consequences

- CI validates lockstep versions and runs packaging tests.
- `dist/` stays gitignored.
- Authors must not `copytree` `adapters/` into shipped skill payloads.
