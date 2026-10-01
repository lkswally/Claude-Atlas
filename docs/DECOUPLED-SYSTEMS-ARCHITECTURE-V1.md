# Decoupled Systems Architecture Audit V1 — JARVIS × ATLAS × MAOS

Audit-only. No code changed. Evidence gathered via three independent read-only sweeps (one per system) plus direct verification of the cross-references each turned up. Bottom line, stated up front: **the three systems are already almost exactly as decoupled as the target architecture asks for.** There is no tight coupling, no circular dependency, and no shared database to repair. The real work is formalizing two already-planned, not-yet-built bridges correctly before they get implemented — not undoing anything that exists today.

## CURRENT JARVIS

Private repo `lkswally/Jarvis` (not on this machine permanently — audited via a refreshed read-only clone at commit `e95b4d3`). A 24/7 meta-orchestrator on an Oracle/Ubuntu VPS: receives requests via Telegram (Hermes agent), resolves device intents deterministically (no LLM), routes everything else through a provider-selection strategy, enforces human approval for sensitive actions, and controls physical devices (PC Casa/Trabajo, a TV) through a pull-based Host Agent polling model. State lives in PostgreSQL (tasks, approvals, notifications, device lifecycle) plus its own Engram instance (`jarvis-engram`, a separate deployed service, not the local `~/.engram` this dev machine uses for ATLAS/MAOS).

**Key disambiguation:** `app/atlas_routing.py`'s "ATLAS" is a pure, deterministic, no-I/O provider-ranking *strategy name* internal to JARVIS — it selects among Groq/Claude/Codex/Gemini/OpenHands for `FAST`/`CODE`/`ANALYSIS`/`CONTEXT`/`DUAL`/`HIGH_RISK` strategies. It is **not** a call into the real Claude-Atlas system. JARVIS's own `README.md:53,261` and `docs/ATLAS_STATE.md:100` say so explicitly: *"Atlas OS (repo `Claude-Atlas`) is separate and is not yet invoked from JARVIS"* — `DUAL`/`HIGH_RISK` are planned but the worker doesn't execute their steps yet.

## CURRENT ATLAS

`D:\ProyectosIA\ProyectosClaude`, GitHub `lkswally/Claude-Atlas`. A Claude Code orchestration layer: 1 orchestrator + 24 subagents, `tools/atlas_dispatcher.py` enforcing Return Envelope/phase-gate/QA-retry contracts (just hardened in Stability Repairs 01–06 this session), a capability router resolving to third-party MCPs only (engram/context7/playwright/github/vercel/notion — nothing JARVIS/MAOS-shaped), and a `config/projects.registry.yaml` that passively catalogs sibling repos (including MAOS) as metadata — status notes, not code dependencies.

## CURRENT MAOS

`D:\ProyectosIA\MARKETING-AGENCY-OS`. A marketing-agency automation tool with its own CLI (`mkt`, `cli/main.py`), 24 core modules, 16 agent specs (`docs/AGENTS.md` — all `status: spec_only`, none implemented yet, runtime doesn't exist), and its own independently-implemented Return Envelope / Phase Gates / Audit Trail, explicitly inspired by ATLAS's *philosophy* but with zero shared code (`docs/relation-to-atlas.md`, already states the rule: *"MKT does not import ATLAS code. Ever."*). Already has a real, working, one-way, zero-import handoff contract to ATLAS (see below) and a disjoint Engram namespace (`marketing-agency-os/*` vs ATLAS's `atlas/*`).

## CURRENT DEPENDENCY GRAPH

```
JARVIS  (standalone — zero code edges to ATLAS or MAOS)
   │  (documented gap: "invoke Atlas OS" from worker — not built)
   ╎
ATLAS  (standalone — zero code edges to JARVIS; passive registry
   │    awareness of MAOS's filesystem path only)
   │  (one real, built, one-way data artifact: MAOS → ATLAS)
   ╎  (documented gap: ATLAS → MAOS bridge — not built)
MAOS   (standalone — zero code edges to JARVIS or ATLAS)
```
No cycles. No shared database. No shared imports. The two `╎` edges are prose/design-doc intent, not executable code.

## DIRECT COUPLINGS FOUND

| Location | What | Classification |
|---|---|---|
| `core/atlas_bridge/` (MAOS) | Built, versioned (`atlas-handoff-brief.v1`), zero-import, zero-HTTP Markdown+JSON artifact a human copies into ATLAS's workflow. Direction: MAOS→ATLAS. | **GOOD_CONTRACT** |
| `config/projects.registry.yaml:32-55` (ATLAS) | Passive catalog entry for MAOS (path, status, notes). Already states the correct rule in prose: *"MKT standalone; ATLAS puede invocar MKT via bridge one-way (nunca al revés)."* `check_project_health()` only runs `git rev-parse --git-dir` on the sibling path — no MAOS code imported/executed. | **ACCEPTABLE_TEMPORARY** (descriptive only) |
| `BACKLOG.md`, `.claude/hard-rules.json:50` (ATLAS) | Human-readable notes/warnings naming MARKETING-AGENCY-OS as a separate repo, one of them literally a guardrail against *accidental* cross-repo git mistakes. | **NOT_ACTUAL_COUPLING** |
| `registry/projects.yaml:18-28` + `docs/adr/ADR-001-multiproject-worker.md` (JARVIS) | A planned, currently-gated multi-project worker concept naming MAOS's real GitHub repo as a future sandboxed client project. `autonomous_execution=false`, no network, no secrets, approval-required deploy. Nothing live. | **ACCEPTABLE_TEMPORARY** (dormant, explicitly gated) |
| `docs/relation-to-atlas.md` + `.env.example:MKT_BRIDGE_ATLAS` (MAOS) | Fully specified future ATLAS→MKT bridge (`bridge/atlas_adapter.py`, contract `bridge.v1`: `run_workflow`/`validate_claims`/`get_brand_voice`), gated by an env var that is reserved in docs but read by **zero** `.py` files today — inert by construction. | **ACCEPTABLE_TEMPORARY** (vaporware by design) |
| `tools/atlas_dispatcher.py:main()` (ATLAS) | An argv/stdin/stdout JSON CLI, today only invoked by Claude Code hooks within the same interactive session. No external caller exists, but the shape is already a clean boundary. | **GOOD_CONTRACT** (latent) |
| "jarvis" anywhere in ATLAS or MAOS | Zero matches, confirmed independently in both repos. | **NOT_ACTUAL_COUPLING** (clean) |

No `TIGHT_COUPLING` and no `CIRCULAR_DEPENDENCY` findings anywhere.

## RESPONSIBILITIES (confirmed against real code, not just the target diagram)

- **JARVIS:** project/task lifecycle, scheduler, human approvals, notifications, device lifecycle (PostgreSQL), provider-health-aware routing strategy selection.
- **ATLAS:** technical planning, agent/model/provider routing for *Claude Code* work specifically, Return Envelope + phase-gate + QA-retry enforcement, security backstop, evidence/QA.
- **MAOS:** marketing-agency domain execution (campaigns, creatives, analytics), its own independently-built contract layer, per-client state.

## JARVIS → EXECUTION BACKEND PORT (proposed, not built)

Ground it in JARVIS's own existing `select_strategy()` output shape (`{strategy, steps:[{role, provider, fallbacks}], requires_human_approval, notes}`) rather than inventing a new one — `submit_task()`/`get_status()`/`resume_task()`/`cancel_task()`/`get_result()`/`health()` wrapping that same decision structure, versioned (`contract_version`), so JARVIS core keeps selecting *when* ATLAS is warranted (as it already does) while an `AtlasExecutionAdapter` translates the result into an actual ATLAS invocation.

## ATLAS ADAPTER (proposed)

Seed it from the existing `atlas_dispatcher.py main()` argv/stdin/stdout JSON CLI — already a clean, import-free boundary (confirmed: nothing calls it externally today, so there's no backward-compat burden). Do not let `core/capabilities/*` grow a reverse import toward this adapter.

## ATLAS → CAPABILITY PROVIDER PORT (proposed)

Target MAOS's own already-sketched `bridge.v1` almost verbatim (`run_workflow(workflow_name, client_slug, brief) -> Envelope`, `validate_claims`, `get_brand_voice`) rather than re-deriving a generic `CapabilityProvider` from scratch — MAOS has already done this design work, correctly, in the right direction.

## MAOS ADAPTER (proposed)

This is the **reverse direction** of the already-built `core/atlas_bridge/` (which is MAOS→ATLAS). The forward adapter ATLAS needs is MAOS's planned `bridge/atlas_adapter.py` (MKT-6C) — not yet implemented, already versioned and env-gated (`MKT_BRIDGE_ATLAS`, off by default, instant kill-switch). Build it per MAOS's own existing design doc rather than ATLAS dictating a different shape.

**Naming risk to flag explicitly:** `core/atlas_bridge/` (built, MAOS→ATLAS) and `bridge/atlas_adapter.py` (unbuilt, ATLAS→MAOS) sound similar but run opposite directions. Any implementer must not conflate them.

## STATE OWNERSHIP / DATABASE BOUNDARIES

JARVIS owns PostgreSQL + its own `jarvis-engram` service (separate deployment). ATLAS owns `.pipeline/*.json*` + `~/.engram` under the `atlas/*` namespace. MAOS owns `data/clients/*.json` + optionally the same local Engram under the disjoint `marketing-agency-os/*` namespace. No file found crosses these boundaries. The two Engram "instances" (JARVIS's deployed `jarvis-engram:18100` vs. the local `~/.engram` ATLAS/MAOS share on this dev machine) are different deployments entirely — not a shared database, but worth stating precisely rather than glossing over.

## CONTRACT VERSIONING

MAOS already models the right pattern (`bridge.v1`/`atlas-handoff-brief.v1`, explicit "both versions may coexist," instant env-var kill-switch). Recommend the same convention for the JARVIS↔ATLAS `ExecutionBackend` contract once it's built, rather than inventing a different versioning scheme per boundary.

## FAILURE ISOLATION

Each system already fails in its own documented style: JARVIS is fail-closed by design (pull-based device queue, evidence-based completion, approval gates — `README.md §1,§3`). ATLAS is fail-open by design (`CLAUDE.md`: every feature has an `ATLAS_*_DISABLED=1` escape hatch). MAOS's adapters are fail-open (`relation-to-atlas.md`: "all adapters in `integrations/` swallow failures, log, degrade"). None of §25's listed failure tests (JARVIS-offline, ATLAS-offline, malformed response, timeout, version mismatch) are currently exercisable end-to-end, because neither bridge exists yet — they become required **acceptance tests for whichever bridge gets built first**, not a gap in today's running systems.

## SECURITY BOUNDARIES

Already least-privilege by design on both existing/planned contracts: MAOS's `atlas_bridge` models explicitly carry no credential/token/api_key field and never embed binary assets. JARVIS's registry entry for MAOS sets `network: false, secrets: none, deploy_policy: approval_required`. Nothing found anywhere exposes a whole repo, whole memory store, or credentials across a boundary.

## OBSERVABILITY / CORRELATION

Already well-aligned: JARVIS uses `task_id`, MAOS's `OperationContext` already carries a generic `correlation_id` (auto-generated, not ATLAS-specific) plus `actor_id`/`role`/`source` — exactly the "generic ID, not a coupling" shape the target architecture asks for. ATLAS would need to adopt an equivalent `run_id` when it gains an external-facing boundary; nothing today prevents that.

## INDEPENDENT DEPLOYMENT

All three already version, deploy, test, and restart independently today — three separate repos, three separate CI pipelines, no synchronized-release requirement found anywhere. This criterion is already met, not aspirational.

## REPLACE ATLAS / REPLACE MAOS SCENARIOS

Trivial today in both directions, precisely because no executable coupling exists yet to unwind: replacing ATLAS would mean pointing JARVIS's (not-yet-built) `ExecutionBackend` at a different adapter — JARVIS core doesn't reference ATLAS anywhere today. Replacing MAOS means swapping the (not-yet-built) `CapabilityProvider` target — ATLAS core doesn't reference MAOS anywhere today either. The scenarios are easy to satisfy *because* the systems were kept apart; the risk is entirely in how the two pending bridges get built, not in anything that exists now.

## RISKS

1. **Naming collision** between `core/atlas_bridge/` (built, MAOS→ATLAS) and the planned `bridge/atlas_adapter.py` (ATLAS→MAOS) — flagged above, worth a one-line note in both repos' docs when the second is built.
2. **JARVIS's generic `execute_claude()` path** (in `worker-v2.py`, shells out to the plain `claude` CLI as one of several generic coding-agent backends) must **not** become the accidental implementation of "invoke Atlas OS" — that gap needs a dedicated `AtlasExecutionAdapter` calling ATLAS's actual orchestrator pipeline, not a reuse of the generic single-shot CLI shell-out meant for ad hoc coding tasks.
3. **JARVIS's ADR-001 multi-project worker**, if implemented as "clone MAOS's repo and run arbitrary coding tasks against it" rather than through the `ExecutionBackend`/`CapabilityProvider` chain, would recreate exactly the tight coupling this audit is meant to prevent. The ADR's own current gating (`autonomous_execution=false`, no network/secrets) buys time to get this right before activating it.

## MIGRATION PLAN

No migration of existing code is required — nothing today needs to be un-coupled. The plan is purely additive: formalize the two pending bridges as versioned contracts before either is implemented, using the already-existing design sketches (MAOS's `bridge.v1`, ATLAS's dispatcher CLI shape, JARVIS's `select_strategy()` output shape) as the starting point rather than designing from scratch.

## FIRST SAFE IMPLEMENTATION BATCH

1. Write down `ExecutionBackend` (JARVIS→ATLAS) and `CapabilityProvider` (ATLAS→MAOS) as versioned schemas — reusing the three shapes already found in this audit, not new ones.
2. Build `AtlasExecutionAdapter` as a thin skeleton wrapping `atlas_dispatcher.py`'s existing CLI — health/discovery only, no real task execution yet.
3. Build `MAOSAdapter` as a thin skeleton implementing MAOS's own already-sketched `bridge.v1` signatures — health/discovery only.
4. Contract tests for both skeletons (schema validation, health states) — no live cross-system call yet.
5. Leave `MKT_BRIDGE_ATLAS` off, leave JARVIS's `autonomous_execution` off for the MAOS registry entry, leave "invoke Atlas OS" un-implemented. Flip these only after Batch 1 proves the contracts hold.

## FINAL VERDICT

**DECOUPLED_ARCHITECTURE_VALID**
