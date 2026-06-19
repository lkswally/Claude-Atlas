# ATLAS Roadmap

## Current State — v0.24.0-rc1

**Architecture maturity: ~91%**  
**Open Source DX readiness: ~95%**  
**System reliability: ~88%**  
**v1.0 readiness: ~82%**

### What's Solid (production-ready)
- 5-phase pipeline with phase gates and retry logic
- 25-agent catalog with defined tools and responsibilities
- Capability abstraction layer (F16–F19): router, registry, events, policy
- Security enforcement: 13 reactive hooks, 22/22 security contract tests
- 218+ QA tests across all feature blocs — 100% green
- ADR system with self-auditor drift detection
- Python tools layer: healthcheck (25 checks), dispatcher, metrics, dependency graph
- Engram MCP: persistent memory, dual-write, cross-session continuity
- **Runtime settings separation (F23)**: healthcheck tolerates Windows/Claude Desktop race condition; WARN not FAIL when settings.json absent; `--strict` mode for release validation
- **Release pipeline (F24)**: `python tools/run_all.py --release` validates everything, auto-generates `release-report.md`, structured JSON output, GitHub Actions CI, bootstrap installer, doctor diagnostic

### What's Incomplete
- Context7 and GitHub MCP require manual token configuration
- Python tools are invoked manually (no auto-trigger on agent completion)
- F25 (Agent Output Contracts) and F26 (Token Budget) deferred to post-v1.0

---

## What Would Block v1.0.0 Stable

### P0 — Must Have
1. **Install automation** — `install/linux.sh` and `install/windows.md` are outdated (reference wrong clone URL). A working one-command install script for both platforms.
2. **Secrets management** — currently tokens go in `.env.local` with no validation. Should have a `setup-tokens` command that validates each token before accepting it.
3. **Full QA suite runner** — `python tools/run_all.py` runs all bloque-F* suites and reports overall pass/fail with timing. ✅ Created in F22.
4. **First-run experience** — after installation, `python tools/atlas_healthcheck.py` should guide the user through fixing any WARN/FAIL items.

### P1 — Should Have
5. **Capability auto-discovery** — instead of hardcoding 14 capabilities in `registry.py`, detect which MCPs are registered in `.mcp.json` and build the registry dynamically.
6. **Policy hot-reload** — currently policy changes require restarting Claude. Should watch `config/capability.policy.yaml` for changes.
7. **Agent output contracts** — formal schema per agent for what they're allowed to write/save. Currently only the envelope format is enforced.
8. **Token budget per agent** — set hard limits on how many tokens each sub-agent can use per task, with automatic escalation if exceeded.

### P2 — Nice to Have
9. **Web dashboard** — render the dependency graph and capability status in a browser UI (could use `tools/dependency_graph.py --json` as the backend).
10. **Replay mode** — given a `.pipeline/capability-events.jsonl`, replay the session and show what decisions were made and why.
11. **MCP auto-install** — if a capability is PENDING_TOKEN or CONFIG_ONLY, generate the exact setup command for the user.

---

---

## Atlas CLI Design (F22 target)

A single `atlas` command that replaces the current manual incantations.  
**Design only — not yet implemented.**

| Command | What it does | Current equivalent |
|---------|-------------|-------------------|
| `atlas doctor` | Run all 25 healthcheck tests, report PASS/FAIL with fix hints | `python tools/atlas_healthcheck.py` |
| `atlas install` | Copy agents/hooks to `~/.claude/`, configure `settings.json`, verify MCPs | Manual copy + `install/linux.sh` |
| `atlas update` | Pull latest, re-copy agents/hooks, run drift check, healthcheck | `git pull` + manual copy + QA |
| `atlas qa` | Run all `_qa/bloque-F*.py` suites, report totals | `for f in _qa/bloque-F*.py; do python "$f"; done` |
| `atlas health` | Live capability status — which MCPs are LIVE/WARN/BLOCK right now | `python tools/capability_metrics.py --report` |
| `atlas bootstrap` | Interactive first-run: verify prerequisites, configure tokens, set up MCPs, run doctor | FIRST_RUN.md walkthrough |

**Implementation notes for F22:**
- `atlas` should be a shell wrapper (`atlas.sh` / `atlas.ps1`) — no new runtime dependency
- Commands must work without ATLAS being "installed" (pre-install scenario)
- `atlas doctor` exit code must be: 0 = all PASS, 1 = any FAIL
- `atlas qa` must discover suites dynamically via glob, not a hardcoded list
- `atlas bootstrap` should call `atlas doctor` at the end and show the result

---

## Planned Feature Blocs

### F22 — System Integrity Audit ✅ Completed v0.22.0
- `tools/run_all.py` unified QA runner with --quick/--full/--release/--json/--list modes
- `tools/secrets_check.py` token classifier with no-leakage guarantee
- 4 new QA suites (56 tests): command-audit, runtime-truth, run-all, secrets-check
- Fixed: context7 MCP registry CONFIG_ONLY → LIVE; JSONL corrupted lines cleaned

### F23 — Runtime Settings Separation ✅ Completed v0.23.0
- `config/atlas.runtime.expected.yaml` stable config reference (source of truth)
- Healthcheck: WARN (not FAIL) when `.claude/settings.json` absent; `--strict` for release
- `_qa/bloque-F5`: fallback to `templates/settings.json` when runtime absent
- `_qa/bloque-F10 TC03`: skip (not FAIL) when runtime absent
- `_qa/bloque-F23-runtime-settings-separation.py`: 14 tests, all PASS

### F24 — Release Candidate Engineering ✅ Completed v0.24.0-rc1

**P1 ✅ — Registry declarativo de tests**
- `config/test.registry.yaml`: 65 suites (33 activas + 32 legacy), layers, timeouts, modos
- `tools/test_registry.py`: loader con API `suites_for_mode()`, `get_suite()`, `detect_orphaned_suites()`
- `_qa/bloque-F24-test-registry.py`: 28 TCs, 0.7s, 100% PASS
- `tools/run_all.py`: discovery y should_run() ahora usan registry como única fuente de verdad

**P2 ✅ — Eliminación de recursión subprocess**
- `_qa/bloque-F22-run-all.py`: reescrita via importlib (0.4s vs ~2400s budget)
- `_qa/bloque-F22-secrets-check.py`: reescrita via importlib (0.26s vs ~130s)
- `_qa/bloque-F22-runtime-truth.py` TC14: `read_events(tail=1000)` (0.36s vs 42.5s)
- `core/capabilities/events.py`: parámetro `tail` añadido a `read_events()`

**P3 ✅ — 30/30 PASS en --quick (41s)**
- Bugs corregidos: F7 tests 3-5 (settings.json guard), secondary FAIL check false-positive, duplicate F24 registry entry, evidence-layer override erróneo, import path de test_registry

**P4 ✅ — 32/33 PASS en --release (56.8s)**
- `_qa/bloque-F13-engram-active.py`: T7 usa `warn()` para settings.json ausente (RUNTIME_MUTABLE)
- `tools/run_all.py`: UTF-8 stdout fix (reconfigure encoding)
- 1 FAIL residual: healthcheck `--strict` con settings.json ausente — resuelto en P5

**P5 ✅ — Release gate semantics — 33/33 PASS en --release (56.6s), 0 FAIL**
- `tools/atlas_healthcheck.py`: `_STRICT_MODE` separado en dos ejes: `_STRICT_EXPECTED` (config estable commiteada, gate de release) y `_STRICT_RUNTIME` (archivo runtime mutable)
- Nuevo `check_expected_config()`: valida expected YAML + template + hooks en disco — este es el gate real de release
- `check_settings_json()`: runtime `.claude/settings.json` ahora siempre `WARN_RUNTIME_MUTABLE` (también bajo `--strict`); solo `--strict-runtime` lo escala a FAIL
- F23 TC6/TC8/TC9 + F7 test_3 actualizados al modelo de dos ejes
- **Gate verde sin falsos verdes ni FAILs "esperados"** → habilita v1.0.0-rc1

**Herramientas previas (desde F24-rc0)**
- `tools/run_all.py --release`: comando único de validación, git metadata, release-report.md, JSON output
- `tools/doctor.py`: diagnóstico read-only
- `bootstrap/install.ps1` + `bootstrap/install.sh`: instalador one-command
- `.github/workflows/ci.yml` + `release.yml`: CI/CD via GitHub Actions
- `docs/GETTING_STARTED.md`, `docs/TESTING.md`, `docs/RELEASE.md`, `docs/CONFIGURATION.md`: nuevos

### F25 — Agent Output Contracts
- Per-agent schema: what drawers they write, what files they touch
- Dispatcher validates agent output against contract
- Violations logged to `.pipeline/contract-violations.jsonl`

### F26 — Token Budget Enforcement
- Per-agent token limits in `config/agent-budgets.yaml`
- Dispatcher tracks tokens per delegation
- Auto-escalate to orchestrator when budget exceeded

---

## Version History

| Version | Tag | Focus |
|---------|-----|-------|
| v0.24.0-rc1 | `v0.24.0-atlas-rc1` | Release Candidate Engineering — run_all --release, release report, doctor, bootstrap, CI |
| v0.23.0 | `v0.23.0-atlas-runtime-settings-separated` | Runtime settings separation, F23 — healthcheck WARN/FAIL split, template fallback |
| v0.22.0 | `v0.22.0-atlas-integrity-audit` | System Integrity Audit — tools/run_all.py, secrets_check, 56 new QA tests |
| v0.21.0 | `v0.21.0-atlas-dx` | DX, open source readiness, 12 new docs, install guides fixed |
| v0.20.0 | `v0.20.0-atlas-architecture-hardening` | Architecture hardening, docs, ADRs, security |
| v0.19.0 | `v0.19.0-atlas-capability-policy` | Capability Policy Engine |
| v0.18.0 | `v0.18.0-atlas-capability-metrics` | Capability Runtime Metrics |
| v0.17.0 | `v0.17.0-atlas-capability-protocol` | Agent protocol compliance |
| v0.16.0 | `v0.16.0-atlas-capability-router` | Capability Router Abstraction |
| v0.15.x | Skills Registry + Hard Rules (F2) |
| v0.14.x | Envelope v1 Pydantic (F1) |
| v0.13.x | Design Criterion Hardening (1L) |
| ≤v0.12.x | Core pipeline, Engram, QA loops, hooks (1A–1K) |
