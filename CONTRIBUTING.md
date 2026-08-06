# Contributing

## Versioning

Keep these in lockstep when you cut a release:

1. Root `VERSION`
2. `.plugin/plugin.json` `version`
3. `adapters/*/plugin.template.json` `version`
4. `CHANGELOG.md` entry

`scripts/validate.sh` fails if they drift.

## Do not hand-edit `dist/`

Marketplace trees and zips under `dist/` are generated. Run:

```bash
python3 adapters/cursor/build_plugin.py
# or
./scripts/build_all.sh
```

Commit source and adapter templates only. Leave `dist/` gitignored.

## Validation

```bash
./scripts/validate.sh
```

Optional: `skills-ref validate ./skills/<skill-name>` when installed.
