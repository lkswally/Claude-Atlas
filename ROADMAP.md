# ATLAS Roadmap

## Current State — v1.0.0-rc2

ATLAS reached **v1.0.0-rc2**: CI green, release gate green (39/39), healthcheck 0 FAIL,
Architecture Score 86/100. The RC2 line (F25–F37) added no new pipeline features — it
hardened boot cost, governance, and documentation honesty. Detail in `CHANGELOG.md`.

### Completed
- **Core** — 5-phase pipeline, 24-subagent catalog, phase gates + retry, Engram MCP
  (persistent memory, dual-write, cross-session continuity).
- **Governance** — Architecture Decision Governor (F35, `tools/architecture_decision.py`)
  + policy YAML; Architecture Intelligence audit (F31, score 62→86).
- **Evidence / QA** — declarative test registry (F24); `run_all.py --quick` 36/36,
  `--release` 39/39; 12-layer evidence QA.
- **Healthcheck** — 26 checks, dual-axis strict (expected vs runtime), 0 FAIL.
- **Knowledge resolver** — F33/F34, `resolve_knowledge()` metadata-only + wiring.
- **Boot optimization** — F30 slimming (CLAUDE.md −81%) + F32 decomposition (god-files
  −96%/−97%); always-on ~1841 tok within budget.
- **Claim linter** — F36, documentation truthfulness gate (0 HIGH / 0 CRITICAL).
- **Release readiness** — F37 audit + this closure (CHANGELOG, ROADMAP, hygiene).

### Current
- **Documentation closure** — CHANGELOG/ROADMAP synced to real state (this pass).
- **Clean-install validation** — verify a new user can install + healthcheck from the README.
- **Pilot in real projects** — exercise ATLAS on registered projects; let friction drive next work.

### Deferred (no adoption without evidence of real friction)
- **Codegraph / structured code retrieval** — optional provider; external dependency,
  needs measured tool-call reduction first (governor: NEEDS_HUMAN_APPROVAL).
- **No-JS Render Audit** — QA gate idea from the external review (ADAPT); touches
  evidence-collector — measure first.
- **Anti-repetition visual memory** — only if projects show repeated structure.
- **Dispatcher decomposition (v1.1)** — `atlas_dispatcher.py` (~3,366 LOC) split behind
  the same public API, one extraction at a time; maintainability debt, not a defect.
- Any feature not backed by a real, observed need.

### Maintenance policy (post-v1.0)
After v1.0, work is limited to: **bugs · security · compatibility · improvements that
originate from real project usage**. No more automatic self-improvement phases — the next
change must come from an observed error or friction, not from an audit for its own sake.

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

### F25–F37 — Shipped in v1.0.0-rc2
The phases originally sketched here as "F25 Agent Output Contracts" and "F26 Token
Budget" were **not** implemented under those labels. The actual F25–F37 work went into
system validation, boot/context optimization, architecture governance, documentation
truthfulness, and the external review — all consolidated in `CHANGELOG.md` under
`v1.0.0-rc2`. The two original ideas remain **deferred concepts** (no evidence of need):
- *Agent Output Contracts* — per-agent write/save schema beyond the envelope. Deferred.
- *Token Budget Enforcement* — per-agent token limits with auto-escalation. Deferred.

### v1.1 — Dispatcher Decomposition
- **Known debt:** `tools/atlas_dispatcher.py` is monolithic (~3,366 LOC, the largest tool in the repo). It mixes envelope validation, phase gates, E2E flow checks, design-quality enforcement, and ~24 public helpers.
- **Not a v1.0.0-rc2 blocker** — the dispatcher is stable, covered by the F24 test net (envelope/phase/contract suites green), and behaves correctly. This is maintainability debt, not a defect.
- **Plan (v1.1):** split into focused modules (e.g. `dispatcher/envelope.py`, `dispatcher/phases.py`, `dispatcher/audit.py`) behind the same public API, one extraction at a time, each validated against the existing F24 suites so behavior is preserved.
- **Precondition met:** the stable regression net required for a safe refactor was built in F24.

---

## Version History

| Version | Tag | Focus |
|---------|-----|-------|
| v1.0.0-rc2 | _(untagged — pending release policy)_ | RC2 — F25–F37: validation, boot/context optimization, architecture governance, claim linter, external review (NO_CHANGE), release readiness |
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
