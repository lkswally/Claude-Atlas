# ATLAS × MAOS — Directional Boundary Verification V1

Addendum to `docs/DECOUPLED-SYSTEMS-ARCHITECTURE-V1.md`. Audit-only. No code changed in either repo.

## CURRENT MAOS→ATLAS BEHAVIOR

Traced completely: entry point `build_and_persist_atlas_handoff()` (`core/atlas_bridge/factory.py`), reached from the CLI command `_cmd_atlas_handoff` (`cli/main.py:1791`, verb `atlas-brief`). Imports: only MAOS's own `core.*` modules (`core.approval`, `core.contracts`, `core.creative`, `core.domain`, `core.image_jobs`, `core.memory`, `core.strategy`, `core.visual`) plus stdlib — zero reference to anything outside the MAOS repo. Outputs: an in-memory `AtlasHandoffBrief` Pydantic object, persisted to MAOS's **own** `JsonFileMemory`, then rendered to two local files (`atlas-{kind}-brief.md`/`.json`) under the caller-specified `--outputs-dir`. Side effects: one MAOS-domain audit-trail event (`actor="atlas_handoff_factory"`). No `subprocess`, no `os.system`, no HTTP client, no socket, anywhere in the call path — confirmed both by reading every line of `factory.py`/`models.py` and by live execution with tripwires (below). The brief's own fields (`client_slug`, `kind`, `landing_brief`, `strategy_report_id`, `creative_pack_id`, …) are 100% MAOS-domain marketing/design concepts — zero `atlas_task_id`/`atlas_agent`/`atlas_phase`/`atlas_retry`/`atlas_model`/`atlas_dispatcher` anywhere in the schema (`grep` confirmed zero hits).

Direct answers: Does MAOS invoke ATLAS? **No.** Start an ATLAS process? **No.** Wait for ATLAS? **No.** Inspect ATLAS state? **No.** Require ATLAS to complete MAOS's own workflow? **No** — `_cmd_atlas_handoff` returns exit 0 the instant the local files are written, with no dependency on anything downstream reading them. It produces a handoff artifact, full stop.

## RUNTIME DEPENDENCY

**None.** Zero process spawning, zero HTTP, zero filesystem reach outside MAOS's own `--root`/`--outputs-dir`.

## STANDALONE PROOF

Real (non-mocked) end-to-end execution, not a static-read inference: ran `mkt run-campaign --intake examples/intake/demo-business.json` followed by `mkt atlas-brief --kind landing` in a disposable temp directory, with `subprocess.Popen`, `os.system`, and `socket.socket` monkey-patched to raise immediately if called (a tripwire covering the *entire* pipeline — campaign-strategy generation through brief rendering, not just the bridge module alone).

```
run-campaign exit code: 0
client_slug: acme-bootstrapped
atlas-handoff exit code: 0
md exists: True  size: 3496
json exists: True  size: 4722
TRIPWIRE_HITS: 0
STANDALONE_PROOF: PASS
```

Zero tripwire hits across the whole run. This is stronger than "ATLAS directory absent" (which this test deliberately avoided — renaming/moving a separate, live, actively-worked-on repo as a side effect of a MAOS test would be reckless): it proves directly that the code path never *attempts* to reach outside the process at all, regardless of what exists on disk nearby. Target architecture's §3 condition is satisfied: MAOS does not fail, degrade, or require anything because ATLAS is absent — because it never checks.

## CURRENT ATLAS→MAOS CAPABILITY

**MISSING.** Re-confirmed from the prior audit (unchanged since): no `capability_router.py`/`core/capabilities/router.py` entry, MCP registry entry, or any file in ATLAS points at MAOS functionally. The only MAOS-aware content in the ATLAS repo is the passive `config/projects.registry.yaml` catalog entry (filesystem path + status notes, no import, no invocation). There is no spec-only placeholder *inside ATLAS's own repo* for consuming MAOS — the only design sketch for this direction lives in MAOS's own `docs/relation-to-atlas.md` (`bridge/atlas_adapter.py`, MKT-6C, not yet implemented) and in this session's own `DECOUPLED-SYSTEMS-ARCHITECTURE-V1.md`. Classified `MISSING` rather than `SPEC_ONLY` because the spec exists only on the MAOS side, not reciprocated in ATLAS's own docs/config.

## BRIDGE CLASSIFICATION

**ATLAS_SPECIFIC_EXPORT** — not `GENERIC_HANDOFF`, not `REVERSE_RUNTIME_DEPENDENCY`, not `LIFECYCLE_COUPLING`. Nuance: the underlying **data** is generic (any system that builds landing pages/branding/page designs could consume it — no ATLAS-specific fields exist in the schema). What makes it `ATLAS_SPECIFIC_EXPORT` rather than fully generic is the **naming and framing**: the module path (`core/atlas_bridge/`), class names (`AtlasHandoffBrief`, `AtlasHandoffKind`), and output filenames (`atlas-{kind}-brief.md/json`) all explicitly target "ATLAS" as the intended consumer, even though nothing in the code actually requires that. It is emphatically not a reverse dependency: a reverse dependency would require MAOS to invoke, wait for, or inspect ATLAS — none of which happens, per the proof above.

## TARGET DIRECTION

Confirmed compatible with the required graph (`JARVIS → ExecutionBackend → ATLAS → CapabilityProvider/AgencyBackend → MAOS`). The existing MAOS→ATLAS artifact is a **one-way, passive, pull-style handoff** (a human or a future ATLAS-side adapter picks it up) — this does not violate "ATLAS may invoke MAOS, MAOS must not depend on or control ATLAS," because MAOS never depends on anything happening to the artifact after it's written. A future `MAOSAdapter` living on the ATLAS side (per the prior audit's recommendation) would be the correct way for ATLAS to *pull* MAOS capabilities going forward — distinct from, and not blocked by, this existing *export*.

## BRIDGE DECISION

**KEEP_AS_IS.** This is a healthy, well-tested (`tests/atlas_bridge/*`, 4+ passing test files), zero-coupling component — there is no functional reason to touch it. Per the mission's own instruction not to delete a healthy component for its name alone, and not to rename during an audit unless necessary: nothing here is urgent or broken.

## NAMING RECOMMENDATION

Not executed now (per instruction). For a **future, non-urgent** change: since the data is genuinely generic, a name like `handoff/` or `export/` (e.g. `core/handoff/`, `HandoffBrief`, output files `handoff-{kind}-brief.*`) would more accurately represent the component's actual responsibility than `atlas_bridge`/`AtlasHandoffBrief` — which currently implies a tighter ATLAS-specific relationship than exists. This is a documentation/clarity improvement, not a correctness fix.

## JARVIS NAMING COLLISION (recorded only — JARVIS repo not touched)

JARVIS's `app/atlas_routing.py` uses "ATLAS" as the name of an internal AI-provider-routing strategy (`select_strategy()`, `ROLE_PREFERENCE`, strategies `FAST`/`CODE`/`ANALYSIS`/`CONTEXT`/`DUAL`/`HIGH_RISK`, selecting among Groq/Claude/Codex/Gemini/OpenHands) — unrelated to, and now confusingly identically named as, the real external Claude-Atlas execution system this document also discusses. Recommended neutral replacement, evidence-backed from the code's own actual job: **`PROVIDER_ROUTER`** (equivalently `EXECUTION_STRATEGY_ROUTER`) — it selects an AI *provider* per strategy, nothing more. This recommendation is recorded here only; per instruction, JARVIS's repo was not modified from ATLAS.

## MIGRATION REQUIRED

**None for today's behavior.** The only future work is building the not-yet-implemented ATLAS→MAOS adapter (on either side) correctly from the start — using MAOS's own already-sketched `bridge.v1` contract (`run_workflow`/`validate_claims`/`get_brand_voice`, env-gated via `MKT_BRIDGE_ATLAS`, kill-switched by default) as the starting point, consistent with the prior audit's recommendation.

## FIRST SAFE CHANGE

Purely documentation, no code: (1) note in `core/atlas_bridge/__init__.py`'s docstring that the brief's schema is consumer-agnostic despite the module's name (sets up the future rename without executing it now); (2) record the JARVIS `PROVIDER_ROUTER` naming recommendation in JARVIS's own backlog/ADR process (owner-driven, not from this repo). Nothing in either item changes runtime behavior.

## VERDICT

`ATLAS_MAOS_DIRECTION_VALID`
