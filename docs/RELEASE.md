# Release Process

This document describes how to tag and publish a new ATLAS version.

## Release checklist

Before tagging, run the complete release validation:

```bash
python tools/run_all.py --release
```

This single command:
1. Collects git metadata (commit, tag, branch, dirty state)
2. Runs `atlas_healthcheck.py --strict` (25 checks, settings.json FAIL in strict mode)
3. Runs all QA suites
4. Writes `run_all.json` (machine-readable structured output)
5. Writes `release-report.md` (human-readable release artifact)

The command must exit with code 0. If it exits 1, fix all failures before tagging.

## Tagging

```bash
# Commit the release report
git add release-report.md
git commit -m "chore(release): v0.X.0 release report"

# Create annotated tag
git tag -a v0.X.0-atlas-description HEAD -m "ATLAS v0.X.0 — description"

# Push
git push origin main
git push origin v0.X.0-atlas-description
```

## Verify tag integrity

After tagging:

```bash
git show --no-patch --oneline v0.X.0-atlas-description
git rev-parse HEAD
git rev-parse v0.X.0-atlas-description
```

Both should show the same commit hash. If they differ, the tag was created at the wrong commit:

```bash
git tag -d v0.X.0-atlas-description
git push origin :refs/tags/v0.X.0-atlas-description
git tag -a v0.X.0-atlas-description <correct-commit> -m "ATLAS v0.X.0 — description (final)"
git push origin v0.X.0-atlas-description
```

## Versioning scheme

```
v{MAJOR}.{MINOR}.{PATCH}-atlas-{description}
```

- `MAJOR`: breaking changes to the pipeline protocol or dispatcher API
- `MINOR`: new F-block features (F23, F24…)
- `PATCH`: fixes within a feature block

Examples: `v0.23.0-atlas-runtime-settings-separated`, `v0.24.0-atlas-rc1`

## GitHub Actions

On tag push, `.github/workflows/release.yml` runs automatically:
- Executes `run_all.py --release`
- Uploads `release-report.md` and `run_all.json` as artifacts
- Fails the job if any suite fails

## Known stable WARNs (not failures)

These WARNs appear consistently and are documented, not bugs:

| WARN | Reason | F-block |
|------|--------|---------|
| `.claude/settings.json absent` | Windows Claude Desktop manages this file (race condition) | F23 |
| `Dispatcher timeout` | Cold-start penalty on first invocation | F22 |
| `bloque-F13-engram-active skipped` | Needs live Engram binary, excluded from --quick | F13 |
