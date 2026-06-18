# Changelog

All notable changes to ATLAS are documented here.

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
