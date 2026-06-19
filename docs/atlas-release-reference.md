# ATLAS — Release Reference

> Release gates, RC status, CI policy, and allowed warnings. Load when tagging,
> publishing, or reasoning about what blocks a release.

## Current state

- **Valid release candidate:** `v1.0.0-rc2` (commit `51e5842`), published as a
  GitHub pre-release. Supersedes `v1.0.0-rc1` (kept as historical; its Release
  Validation failed due to a workflow bug, since fixed — not a product defect).
- CI Quick: success. Release Validation (rc2): success.

## Gate policy — when to run which

| Layer | When | Runs | Cost |
|-------|------|------|------|
| `python tools/run_all.py --quick` | **daily development** | ~30 suites | ~40s |
| `python tools/run_all.py --release` | **before publishing / tagging** | active suites + healthcheck gate | ~60s |
| `python tools/run_all.py --full` | research / maintenance | everything incl. legacy | variable |
| `python tools/atlas_healthcheck.py --strict` | release gate (stable expected config) | ~25 checks | fast |

You do **not** need `--release` for everyday work — `--quick` is the default loop.
CI runs Quick on every push to `main`; Release Validation runs only on tag push.

## What blocks a release

- Any suite **FAIL** in `--release`.
- Healthcheck **FAIL** (FAIL only — WARN never blocks).
- Leaked secrets (`tools/secrets_check.py` non-zero on a real leak).

## Allowed warnings (documented, non-blocking)

- `.claude/settings.json` → **WARN_RUNTIME_MUTABLE**: managed by Claude Desktop on
  Windows; the stable source of truth is `templates/settings.json` +
  `config/atlas.runtime.expected.yaml`. Absence is expected.
- `capability-events.jsonl` invalid-line count (F18): tolerated by the reader;
  candidate for rotation, not a blocker.
- Knowledge registry (F29): WARN-only by design.

## States glossary

| State | Meaning |
|-------|---------|
| PASS | check/suite succeeded |
| WARN | non-blocking notice; never fails a gate |
| FAIL | blocking failure; non-zero exit |
| SKIP | optional dependency absent (Engram binary, Chromium, `.mcp.json` in clean CI) |
| RUNTIME_MUTABLE | file owned by the runtime; absence expected → WARN |
| PENDING_TOKEN | configured, waiting for a token (GitHub/Vercel) → not blocking |
| CONFIG_ONLY | declared but not verified live this run |
| LIVE | verified active and responding |

## CI / Release Validation

- **CI** (`.github/workflows/ci.yml`): runs `run_all.py --quick` on push to main.
- **Release Validation** (`.github/workflows/release.yml`): runs `run_all.py
  --release` on tag push (`v*`). Both install from `requirements.txt`.

## References

- Full integral validation: `docs/F25-INTEGRAL-VALIDATION.md`
- Architecture criticism + capability-router honesty: `docs/F27-CAPABILITY-ROUTER-CLAIM-AUDIT.md`
- Complexity/release-gate engineering: `docs/F24-COMPLEXITY-AUDIT.md`
