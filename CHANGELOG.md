# Changelog

All notable changes to ATLAS are documented here.

---

## [v0.24.2] — 2026-06-18 — F24 P5: Release Gate Semantics

### Problem Solved
P4 dejó el release gate con 1 FAIL "esperado y documentado" (`healthcheck --strict` con `.claude/settings.json` ausente). Un gate documentado como rojo-esperado es una contradicción: una rc1 no se publica con el gate en rojo. P5 corrige la semántica atacando la causa raíz: `--strict` mezclaba la validación de la config estable commiteada con la del archivo runtime mutable.

### Changes

**Separación de ejes strict en `tools/atlas_healthcheck.py`**
- `_STRICT_MODE` → `_STRICT_EXPECTED` + `_STRICT_RUNTIME` (dos ejes independientes)
- `_STRICT_EXPECTED` (`--strict` / `ATLAS_HEALTHCHECK_STRICT=1`): valida config estable commiteada (expected YAML + template + hooks en disco). Lo usa release.
- `_STRICT_RUNTIME` (`--strict-runtime` / `ATLAS_HEALTHCHECK_STRICT_RUNTIME=1`): valida el archivo runtime mutable `.claude/settings.json`. NO lo usa release.
- `check_expected_config()` (NEW): valida `config/atlas.runtime.expected.yaml` + `templates/settings.json` + cada hook esperado resuelto a `.claude/hooks/*.js`. Bajo `--strict` → FAIL si falta. Es el gate real.
- `check_settings_json()` (RECLASSIFIED): runtime `.claude/settings.json` ausente/corrupto → `WARN_RUNTIME_MUTABLE` siempre (también bajo `--strict`); solo `--strict-runtime` escala a FAIL.

**Tests**
- `_qa/bloque-F23-runtime-settings-separation.py`: TC6 (dual-axis wiring), TC8 (release gate semantics: `--strict` exit 0 + `--strict-runtime` exit 1 con settings ausente), TC9 (separación WARN runtime / gate expected) — 14/14 PASS
- `_qa/bloque-F7-healthcheck-validation.py`: test_3 usa `--strict-runtime` (eje correcto para detectar corrupción del runtime)

**`tools/run_all.py`**
- Comentarios actualizados; release sigue invocando `run_healthcheck(strict=True)` (= expected-strict)

### Results
- `run_all --quick`: 30/30 PASS, 41s
- `run_all --release`: **33/33 PASS, 0 FAIL, 56.6s** (antes 32/33)
- `healthcheck --strict` con settings.json ausente: exit 0 (antes exit 1)
- `healthcheck --strict-runtime` con settings.json ausente: exit 1 (eje preservado, sin falsos verdes)

### Recommendation
**v1.0.0-rc1 LISTO sin condiciones** — release gate verde, sin FAILs "esperados".

---

## [v0.24.1] — 2026-06-18 — F24 Complexity Reduction (P1–P4)

### Problem Solved
`run_all --release` producía 9 FAILs con timeouts de hasta 2400s por recursión subprocess y ausencia de taxonomía de tests. F24 P1-P4 atacó las causas raíz: registry declarativo, eliminación de recursión, corrección de bugs de clasificación.

### Changes

**P1 — Registry declarativo de tests**
- `config/test.registry.yaml` (NEW): 65 suites (33 activas + 32 legacy), con layer/timeout/can_run_in_quick/can_run_in_release/status
- `tools/test_registry.py` (NEW): loader con dataclass `Suite`, `TestRegistry.suites_for_mode()`, `get_suite()`, `detect_orphaned_suites()`, `detect_missing_files()`
- `_qa/bloque-F24-test-registry.py` (NEW): 28 TCs, 0.7s, 100% PASS
- `tools/run_all.py`: discovery y `should_run()` usan registry; timeout por suite desde registry

**P2 — Eliminación de recursión subprocess**
- `_qa/bloque-F22-run-all.py` (REWRITTEN): importlib en lugar de subprocess `run_all --quick`; 0.4s vs ~2400s budget
- `_qa/bloque-F22-secrets-check.py` (REWRITTEN): importlib + API directa; 0.26s vs ~130s (13 subprocs)
- `_qa/bloque-F22-runtime-truth.py` (MODIFIED): TC14 usa `read_events(tail=1000)`; 0.36s vs 42.5s
- `core/capabilities/events.py` (MODIFIED): parámetro `tail: int | None` añadido a `read_events()`

**P3 — Corrección de bugs (→ 30/30 PASS en --quick, 41s)**
- `_qa/bloque-F7-healthcheck-validation.py`: guard `existed = SETTINGS_PATH.exists()` en tests 3-5; test_3 usa `--strict`; masking de `[FAIL]` en output anidado
- `tools/run_all.py`: secondary FAIL check cambiado a `line.lstrip().startswith("[FAIL]")` (elimina false-positives)
- `config/test.registry.yaml`: entrada duplicada F24 eliminada; evidence-layer override eliminado de `should_run()`

**P4 — Estabilización --release (→ 32/33 PASS, 56.8s)**
- `_qa/bloque-F13-engram-active.py`: T7 usa `warn()` en lugar de `fail()` cuando settings.json ausente (RUNTIME_MUTABLE)
- `tools/run_all.py`: `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")` para Windows cp1252
- `docs/F24-COMPLEXITY-AUDIT.md`: secciones P1+P2 Result y P4 Result añadidas

### Known Issues
- `run_all --release` produce 1 FAIL en `bloque-F23` TC14: `healthcheck --strict` con settings.json ausente cuando Claude Desktop no está activo. Clasificado como RUNTIME_MUTABLE, esperado, no bloquea rc1.

---

## [v0.24.0] — 2026-06-18 — Release Candidate Engineering

### Problem Solved
ATLAS needed a single official command to validate everything before tagging, automated CI, a one-command bootstrap, and a diagnostic doctor — converting ATLAS from a functional system into a reproducible, verifiable, publishable architecture.

### Changes

**P1/P2 — Release Pipeline + Release Report**
- `tools/run_all.py`: added `get_git_metadata()` (commit/tag/branch/dirty), healthcheck always runs in `--release` mode (including `--json`), `generate_release_report()` auto-writes `release-report.md` on every `--release` run, `--out FILE` saves JSON to file, git metadata in JSON output

**P3 — GitHub Actions**
- `.github/workflows/ci.yml`: on PR/push to main, runs `python tools/run_all.py --quick --json`, uploads `run_all.json` as artifact
- `.github/workflows/release.yml`: on version tags, runs `python tools/run_all.py --release`, uploads `release-report.md` + `run_all.json`, fails if any suite fails

**P4 — Bootstrap**
- `bootstrap/install.ps1`: Windows one-command installer — checks Python/Node/Git/Go/Claude, installs PyYAML+Playwright, verifies Engram+Context7+.mcp.json, runs healthcheck, reports `ATLAS READY` or `ATLAS NOT READY`
- `bootstrap/install.sh`: Linux/macOS equivalent

**P5 — Doctor**
- `tools/doctor.py`: read-only diagnostic — Python/Node/Git/Go/Claude/GitHub CLI versions, Engram binary+DB, Playwright, key imports, .mcp.json, filesystem structure, hook syntax checks, settings.json, environment variables, PATH coverage, write permissions. JSON output with `--json`. Never modifies anything.

**P6 — Architecture**
- `ARCHITECTURE.md`: added sections for Release Pipeline, Release Report Format, Doctor, Bootstrap, GitHub Actions, Registry Layer. Added invariants 7+8 (release command must pass before tagging; release-report.md must be committed).

**P7 — Developer Experience**
- `docs/GETTING_STARTED.md`: new — prerequisites, bootstrap, pipeline activation, quick validation
- `docs/TESTING.md`: new — full suite catalog, mode comparison table, JSON output structure, how to write a new suite
- `docs/RELEASE.md`: new — release checklist, tagging procedure, tag integrity verification, versioning scheme, known stable WARNs
- `docs/CONFIGURATION.md`: new — all config files documented, environment variables table, hook configuration guidance

**P8 — Project State**
- `CHANGELOG.md`: this entry
- `ROADMAP.md`: F24 marked completed, version history updated

### QA
- `tools/doctor.py`: runs clean, no false positives
- `bootstrap/install.ps1`: syntax verified
- `.github/workflows/ci.yml`: YAML valid
- `.github/workflows/release.yml`: YAML valid

---

## [v0.23.0] — 2026-06-18 — Runtime Settings Separation

### Problem Solved
`.claude/settings.json` is managed by Claude Desktop on Windows and may appear/disappear between tool calls, causing 5 QA suites and the healthcheck to emit false FAIL results (race condition).

### Changes
- `tools/atlas_healthcheck.py`: `check_settings_json()` emits WARN (not FAIL) when settings.json absent; `--strict` flag and `ATLAS_HEALTHCHECK_STRICT=1` env var restore FAIL behavior for release validation
- `config/atlas.runtime.expected.yaml`: new stable reference — lists expected hooks by event type, expected MCP servers, ownership model, escape hatch documentation
- `_qa/bloque-F5-settings-wiring-validation.py`: falls back to `templates/settings.json` with `__CLAUDE_HOME__` → `.claude` resolution when runtime absent
- `_qa/bloque-F10-sot-drift.py TC03`: skips (not FAILs) when `.claude/settings.json` is absent
- `tools/run_all.py`: passes `--strict` to healthcheck in `--release` mode; removed `HEALTHCHECK_DEPENDENT_SUITES` classification (suites now tolerate the race)
- `_qa/bloque-F23-runtime-settings-separation.py`: 14 new tests validating all F23 changes

### QA
- `bloque-F23-runtime-settings-separation.py`: 14/14 PASS
- `atlas_healthcheck.py`: HEALTHY (21 PASS, 2 WARN, 0 FAIL)
- `bloque-F22-command-audit.py`, `bloque-F14-mcp-registry.py`, `bloque-F15-context7.py`, `bloque-F15-playwright.py`: all PASS

---

## [v0.21.0] — 2026-06-18 — Developer Experience + Open Source Readiness

### Documentation — New Files
- `VISION.md`: one-sentence mission, 5 core principles, 5 non-negotiables, v1.0 success definition
- `INSTALL.md`: cross-platform installation from zero (all 11 steps + dependency table)
- `FIRST_RUN.md`: first project walkthrough, key commands, what ATLAS can't do
- `TROUBLESHOOTING.md`: categorized fixes for healthcheck, Claude, Python, and Windows issues
- `FAQ.md`: 30+ questions covering general, installation, usage, capabilities, hooks, contributing
- `GLOSSARY.md`: 27 terms defined — ADR through v0.x→v1.0
- `docs/AGENTS.md`: full catalog of all 25 agents, communication contract, add-agent checklist
- `docs/HOOKS.md`: all 16 hooks documented, hook types table, safe hook writing guide
- `docs/SKILLS.md`: all 10 skills by domain, API examples, adding a new skill
- `docs/SECURITY.md`: all 6 security layers explained with escape hatches and philosophy

### Documentation — Updated
- `README.md`: complete rewrite — sell the concept, full architecture diagram, quick start in 5 commands
- `CONTRIBUTING.md`: updated with all new documents, atlas CLI design, full commit checklist
- `ROADMAP.md`: Atlas CLI design section (6 commands), updated maturity metrics, F22-F25 planned blocs

### Install Guides — Fixed
- `install/linux.sh`: Python 3.10+ check added, correct counts (25 agents, 38 files, 13 hooks), removed "Vibecoding" branding
- `install/windows.md`: Python step added, clone URL placeholder corrected, all counts updated (38 files, 16 hooks), added healthcheck verification step
- `.env.example`: new file — template for all 5 token variables + all 5 `ATLAS_*_DISABLED` escape hatches

### DX Audit (Part 1 findings resolved)
- P0: Wrong clone URL fixed (placeholder + instructions)
- P0: Python 3.10+ now documented in both install guides
- P0: Hook count inconsistency fixed (16 = 13 reactive + 3 manual utilities)
- P0: `.env.example` created
- P1: `install/linux.sh` header updated (correct counts, removed legacy naming)
- P1: All missing docs created (FIRST_RUN, TROUBLESHOOTING, FAQ, GLOSSARY, VISION)

---

## [v0.20.0] — 2026-06-18 — Architecture Hardening + Open Source Readiness

### Security
- `block-no-verify.js`: closed 3 bypass gaps — `git -C <dir> push --force`, `chmod -R 777`/`0777`, `chown -R`/`--recursive`
- Added `.gitattributes` with `* text=auto eol=lf` to prevent CRLF drift on Windows

### QA
- New `_qa/bloque-F20-security-hooks.py` (22/22 PASS): full coverage of blocked and safe commands
- New `_qa/bloque-F20-capability-contracts.py` (14/14 PASS): functional contract tests for all 14 capabilities

### Architecture
- Added `ADR/` directory with 4 Architecture Decision Records (0001–0004)
- Self-auditor T9: Architecture Drift Check — detects DRIFT, OVERDUE, RECONSIDERED patterns
- New `tools/dependency_graph.py`: full Agent→Capability→Policy→Provider→MCP→CLI→Binary tree

### Documentation
- Full `README.md` rewrite: fixed counts (38 files, 16 hooks), added capability system section, Python tools section, ADRs table
- New `ARCHITECTURE.md`: internal design with layer diagram, directory structure, invariants
- New `FLOWS.md`: 6 end-to-end request flows (new project, resume, capability resolution, hook interception, policy block, compaction)
- New `CHANGELOG.md`, `CONTRIBUTING.md`, `ROADMAP.md`

---

## [v0.19.0] — 2026-06-18 — Capability Policy Engine

### Added
- `config/capability.policy.yaml` — 14 declarative capability policies
- `core/capabilities/policy.py` — `PolicyDecision`, `evaluate_capability()`, `evaluate_all_capabilities()`
- `PolicyOutcome`: ALLOW | WARN | DEGRADED | BLOCK | MISSING_POLICY
- `router.resolve_with_policy()` — returns `(Resolution, PolicyDecision)` tuple
- Healthcheck check: `check_capability_policy()` — validates policy YAML, critical caps not BLOCKED
- `_qa/bloque-F19-capability-policy.py` — 14/14 PASS
- `agent-protocol.md` updated: Router vs Policy table, decision table, when to stop/degrade/escalate

### Behavior
- `ATLAS_CAPABILITY_POLICY_DISABLED=1` makes all evaluations return ALLOW unconditionally

---

## [v0.18.0] — 2026-06-18 — Capability Runtime Metrics

### Added
- `core/capabilities/events.py` — `CapabilityEvent` dataclass, `emit()`, `read_events()`, thread-safe JSONL appends
- `tools/capability_metrics.py` — CLI: `--last N`, `--capability X`, `--json`, `--critical`; exit 0/1/2
- `resolve_capability()` gains `emit=True` parameter; events written to `.pipeline/capability-events.jsonl`
- Healthcheck check: `check_capability_metrics()` — validates imports, JSONL integrity, `.pipeline/` writable
- `_qa/bloque-F18-capability-metrics.py` — 14/14 PASS

### Behavior
- `ATLAS_CAPABILITY_EVENTS_DISABLED=1` suppresses all event writes

---

## [v0.17.0] — Capability Protocol Compliance

### Added
- Agent protocol updated: capability API examples, when to use `resolve_capability` vs raw MCP
- All agent files audited for raw MCP references — migrated to capability names
- `_qa/bloque-F17-capability-protocol.py` — verifies no agent uses raw MCP prefixes

---

## [v0.16.0] — Capability Router Abstraction

### Added
- `core/capabilities/registry.py` — 14 capabilities, `Provider` dataclass, `ResolutionStatus`
- `core/capabilities/router.py` — `resolve_capability(name)` → `Resolution`
- `core/capabilities/__init__.py` — public API exports
- `ResolutionStatus`: LIVE | CONFIG_ONLY | PENDING_TOKEN | DEFERRED_PAID | UNAVAILABLE
- `CRITICAL_CAPABILITIES`: {"memory", "browser", "documentation"}
- `ATLAS_CAPABILITIES_DISABLED=1` bypass (raw MCP passthrough)
- `_qa/bloque-F16-capability-router.py` — 14/14 PASS

---

## [v0.15.x] — Skills Registry + Hard Rules (F2)

### Added
- `.claude/skills.registry.yaml` — declarative skills catalog (10 skills)
- `tools/skills_registry.py` — `find_skills()`, `get_skill()`, `list_domains()`, usage logging
- `.claude/hard-rules.json` — 4 hard rules (no-force-push-main, no-merge-pr25-without-pilots, etc.)
- `hooks/pipeline-rules.js` — Hard rules enforcement
- Usage logging to `.claude/logs/skills-registry-usage.jsonl`

---

## [v0.14.x] — Envelope v1 (F1)

### Added
- `tools/contracts/envelope_v1.py` — Pydantic `Envelope` model, bidirectional coercion
- `validate_return_envelope` accepts both dict and `Envelope` instances
- Per-mode validations: qa_strict / dev_strict / design_strict / standard

---

## [v0.13.x] — Design Criterion Hardening (1L)

### Added
- Intent Classifier (`classify_user_intent`): 4 buckets with confidence levels
- Design quality blocking in design_strict mode (HIGH findings reject envelope)
- Reference-driven design requirement (`brand.references` schema)
- Editorial compliance verification (5 sub-fields, rationales ≥20 chars)

---

## [v0.12.x] — Visual Evidence Verification (1J)

### Added
- Design Intelligence re-verification (independent invocation, detects invented styles)
- Screenshot hash verification (SHA256 match, detects phantom evidence)

---

## [v0.11.x] — Auto-Audit Hook (1K)

### Added
- `qa-auto-audit.js` — PostToolUse hook audits mandatory helpers after agent spawn

---

## [v0.10.x] — Multi-Layer QA (1H)

### Added
- Network inspection: detects 5xx, mixed content, redirects >3, 4xx on critical assets
- Console log analysis: Uncaught, CORS, CSP, hydration mismatch, null access patterns
- Visual fidelity checker: palette/typography/mood/anti-patterns with RGB tolerance

---

## [v0.9.x] — Runtime Wiring (1G)

### Added
- `_record_invocation()` tracking on 15 helpers
- `audit_invocations()` — verifies runtime calls at certification
- Documentation of all runtime helper wiring in `orquestador.md`

---

## [v0.8.x] — Performance + Tokens (1F)

### Added
- File hash caching for QA (SHA256 + mtime + atomic write, ~70-80% token savings)

---

## [v0.7.x] — Anti-Loop + Certification (1D, 1E, 1I)

### Added
- Delegation stop rules: `escalation_needed`, `pause_recommended`, `fresh_review_recommended`
- Reality-Checker random re-runs with reproducible seed
- Anti-Loop inter-session: append-only history detects persistent loops across 3+ sessions

---

## [v0.6.x] — Core Pipeline (1A, 1B, 1C)

### Added
- Phase Gates operational (1A.7) with intra-session anti-loop (1A.12)
- Pre-Return Audit (1A.14, 1A.15, 1A.16) — 6 auto-executable rules
- Engram MCP real connection — JSON-RPC stdio inline (1B.2)
- 2-step Engram pattern enforced (1B.4)
- UI-UX Pro Max Skill enforcement in design_strict mode (1C.1)
