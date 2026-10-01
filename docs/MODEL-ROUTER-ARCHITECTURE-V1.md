# Model Router Architecture Audit V1

Audit + design only. **No runtime code changed.** Every "current state" claim below was verified against real code/config (`grep`, direct file reads), not inferred from docs. Where a value genuinely cannot be verified from this repo, it is marked `UNKNOWN` rather than invented.

## CURRENT MODEL ROUTING — classified

| Mechanism | File | Status |
|---|---|---|
| Per-agent model declaration | `.claude/agents/*.md` frontmatter (`model: opus\|sonnet`) | **CONFIG_ONLY** — 27 files declare it (5 `opus`, 22 `sonnet`); `grep` across `tools/*.py` and `core/**/*.py` found **zero** code that reads or enforces this field. It is consumed only by Claude Code's own native subagent-spawn mechanism, outside ATLAS's control. |
| Dynamic/runtime model selection | — | **MISSING**. No function anywhere computes a model choice from task characteristics. |
| Provider selection (LLM execution) | — | **MISSING**. `grep` for `groq\|codex\|openhands` across `tools/`, `core/`, `config/` returned zero hits. ATLAS has exactly one usable LLM provider today: whatever Claude Code's own host runtime is configured with. |
| Capability/MCP router | `core/capabilities/router.py` (`resolve_capability()`) | **LIVE** — but for MCP *tools* (documentation/browser/memory → context7/playwright/engram), a different axis entirely from LLM model/provider selection. Good architectural template (see Reusable Components); not reusable as-is. |
| Fallback logic (models) | — | **MISSING**. The capability router's `Resolution.fallback` field is LIVE but scoped to MCP tools, not models. |
| Health checks (LLM provider) | — | **MISSING**. ATLAS has no concept of "is Claude available right now" — that's handled transparently by the Claude Code host, invisible to ATLAS's own code. |
| Quota handling (LLM) | — | **MISSING**. `secrets_check.py`'s tracked tokens (`GITHUB_TOKEN`, `VERCEL_TOKEN`, `GEMINI_API_KEY`, `HF_TOKEN`, `REPLICATE_API_TOKEN`) are for git/deploy/image/video integrations, not LLM execution — confirmed zero `ANTHROPIC_*`/`OPENAI_*`/execution-model key anywhere. |
| Model-specific configuration | — | **MISSING**. No file defines a per-model capability profile (context window, strengths, cost tier). |
| Agent-specific model preference | `.claude/agents/*.md` | **CONFIG_ONLY** (same as row 1) — static, 1:1, hardcoded. |
| Reviewer/model independence | `CLAUDE.md` model table + `reality-checker.md`/`evidence-collector.md` | **PARTIAL** — the final certification gate (`reality-checker`) is `opus`, differing from most implementers (`sonnet`), but this is a static role assignment, not a dynamic, risk-based independence decision. The QA gate (`evidence-collector`) is `sonnet` — frequently the *same* tier as the dev-agent it checks. |
| Cost tracking | `.claude/hooks/cost-tracker.js` + `cost-report.js` | **PARTIAL** — logs each `Agent` tool call's `model` field (or `'inherited'`) to an append-only JSONL and aggregates **call counts** by category/tool/subagent-type. Computes **zero actual dollar cost** despite the name — worth flagging precisely rather than assuming it does what it's named. |
| Latency tracking | — | **MISSING**. No duration/timestamp-pair computation found anywhere. |
| Success metrics (per model) | — | **MISSING**. The closest adjacent mechanism (Stability Repair 06's `QARetryState`) counts attempts per *task*, not per *model*. |
| Task-type classification (for routing) | — | **MISSING** for the FAST/CODE/ANALYSIS/… axis this mission needs. A *different*, adjacent classifier exists (see below) but solves a different problem. |
| Risk/security signal detection | `tools/architecture_decision.py` + `config/architecture.decision-policy.yaml` | **LIVE** — but classifies architecture *proposals*, not runtime tasks. Excellent reusable template (see below). |

## CURRENT PROVIDERS — verified inventory

| Provider | Model | Available | Auth status | Tools | Context window | Multimodal | Code strength | Latency | Cost policy | Current role | Health check | Fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Anthropic (via Claude Code host) | Opus | Yes (host-managed) | Host-managed, invisible to ATLAS | All Claude Code tools | UNKNOWN (not exposed to ATLAS) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN (host-billed, not tracked in this repo) | Orchestrator, project-manager-senior, security-engineer, game-designer, reality-checker (static, per-frontmatter) | None at ATLAS layer | None |
| Anthropic (via Claude Code host) | Sonnet | Yes (host-managed) | Host-managed | All Claude Code tools | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | All other 22 agents (static) | None at ATLAS layer | None |

No other provider is configured, referenced, or reachable from ATLAS today. Per the mission's instruction, nothing above is invented — every `UNKNOWN` is a genuine gap in what this repo can verify, not a guess.

## CURRENT AGENT MODEL ASSIGNMENTS

All 27 agents: **hardcoded**, in frontmatter, no override mechanism, no runtime verification possible (nothing reads the field at the ATLAS layer — Claude Code's own spawn mechanism is the only consumer, and that's outside this repo). `CAN OVERRIDE`: only via the `Agent` tool's own ad hoc `model` parameter at call time (confirmed real — `cost-tracker.js` logs exactly this field) — but that's a caller-side override available to *whoever invokes* `Agent`, not a decision ATLAS's own dispatcher makes. No unnecessary hardcoding was found that looks like an oversight — the 5 Opus / 22 Sonnet split matches `CLAUDE.md`'s documented rationale (high-stakes reasoning roles vs. structured-execution roles) exactly. Nothing here needs removing; it needs a *parallel* dynamic layer, not a replacement.

## REUSABLE COMPONENTS (patterns, not code — different domains)

1. **`core/capabilities/router.py`'s `Resolution` dataclass** — `{capability, provider, status, fallback, action, notes}`, an `is_usable` property, a bounded status enum (`LIVE/CONFIG_ONLY/PENDING_TOKEN/DEFERRED_PAID/UNAVAILABLE`). Template for a future `ModelResolution`.
2. **`tools/intent_classifier.py`'s keyword+weight+confidence pattern** — ES/EN keyword tables with weights, `confidence: high/medium/low`, and an explicit escalation question when confidence is low rather than silently guessing. Template for the Task Classifier (§ below) — same mechanism, different output domain (pipeline intent vs. task class).
3. **`tools/architecture_decision.py` + `config/architecture.decision-policy.yaml`** — the single best template in the repo: config-driven signal detection → ordered rule matching (`when_any`/`when_not`) → `{decision, risk, impact, reason, recommendation}`, fail-open with sane in-code defaults if the YAML is missing, pure/read-only/advisory. This is the architecture the mission describes in §11 almost exactly, already built, for a different domain (architecture proposals, not runtime tasks).
4. **`.claude/hard-rules.json` + `block-no-verify` hook** — real-time pattern-based hard constraints (BLOCK/WARN). Template for the "hard eligibility filter, can't be outranked by score" requirement (§12).
5. **`tools/qa_retry_state.py`** (Stability Repair 06) — disk-persisted, cross-process-locked, fail-closed per-key counter. Proof ATLAS already knows how to build a safe historical counter correctly, if/when per-model `success_rate`/`retry_rate` metrics get built.
6. **`tools/invocation_tracker.py`** — generic helper-invocation logging with context/outcome + `audit_invocations()`. Reusable directly for persisting routing-decision evidence (§20) rather than building a new telemetry subsystem.

## MISSING COMPONENTS

Everything that actually *decides* a model/provider: task-class classifier for this purpose, complexity model, risk model (runtime-task-scoped, not proposal-scoped), model capability profiles, eligibility filters, scoring algorithm, provider health for LLMs, quota/rate-limit tracking for LLMs, fallback chains, retry-vs-fallback policy, reviewer-independence logic, cost-policy enforcement, model metrics (latency/success/retry/rejection rates), and the canonical config layer tying it together.

## TASK CLASSIFICATION (proposed)

`FAST | CODE | ANALYSIS | CONTEXT | REVIEW | HIGH_RISK | RESEARCH | MULTIMODAL | AUTOMATION` — adopted as given in the mission, since nothing in current ATLAS conflicts with or already defines these. Built the same way `intent_classifier.py` builds pipeline-intent: keyword/pattern signals + weights, `confidence` field, escalate (don't guess) when ambiguous. A **new, separate** module — do not repurpose `intent_classifier.py` itself, since its 4-bucket output (audit/redesign/implement/validate) answers a different question (which pipeline phase) than this one (what kind of technical work, for model-fit purposes).

## TASK REQUIREMENTS PROFILE (proposed)

```
task_class, complexity, risk, context_size, latency_priority,
quality_priority, cost_policy, tool_requirements, multimodal_required,
coding_required, reasoning_required, long_context_required,
independent_review_required, execution_environment
```
Every field maps to a concrete filter or scoring dimension below — none added speculatively.

## COMPLEXITY MODEL (proposed)

`LOW / MEDIUM / HIGH / VERY_HIGH`, from **observable** signals (never an unexplained LLM 1-10 score): number of files touched, estimated code-surface (lines/functions), cross-module impact (how many of ATLAS's own existing "affected_components" categories a task touches — reusing `architecture_decision.py`'s `_COMPONENT_HINTS` keyword-to-component mapping as a starting point), external dependency count, test surface, ambiguity (can reuse `intent_classifier.py`'s own confidence mechanism — "low confidence" is itself a complexity signal), irreversibility.

## RISK MODEL (proposed — separate from complexity)

`LOW / MEDIUM / HIGH / CRITICAL`. **Do not reinvent signal detection** — reuse `architecture_decision.py`'s exact `security_sensitive`/`touches_runtime`/`external_service` signal categories and its 0-5 risk heuristic as the starting point for a task-scoped variant, since that module already encodes exactly the right judgment (a simple refactor is low risk regardless of file count; a one-line credential change is high risk regardless of complexity) for this repo's own domain. High complexity must never auto-imply high risk, per mission §8 — confirmed consistent with how `architecture_decision.py` already treats them as independent axes.

## MODEL CAPABILITY PROFILE (proposed)

Exactly the shape the mission sketches (`model_id`, `provider`, `strengths`, `supports_tools`, `supports_multimodal`, `context_tier`, `latency_tier`, `cost_tier`, `eligible_for_high_risk`) — editable/configurable, not hardcoded marketing claims. Given today's verified inventory has only two real entries (Opus, Sonnet, both via Claude Code, most of their own characteristics `UNKNOWN` to this repo), the profile file should ship with those two entries only, `UNKNOWN` fields left as `UNKNOWN` (not guessed), and room to add rows later without code changes.

## ROUTING ALGORITHM (proposed)

Exactly the mission's own pipeline, since nothing in current ATLAS suggests a better order: eligibility filter → capability fit → complexity fit → risk fit → latency preference → cost preference → provider health → historical adjustment (only once history exists — see §10/22). Deterministic, explainable, config-driven (reusing the `architecture_decision.py` *mechanism*) — never one opaque LLM prompt. Returns `{selected_model, selected_provider, score, reason, alternatives, fallback_chain}`.

## ELIGIBILITY FILTERS (proposed, hard — never outranked by score)

Auth unavailable, provider unhealthy, quota exhausted, required tools unsupported, required context unsupported, cost policy forbids, risk policy forbids this model for this risk tier, execution environment incompatible. Mirrors `.claude/hard-rules.json`'s BLOCK-before-rank philosophy.

## PROVIDER HEALTH (proposed)

`AVAILABLE / DEGRADED / RATE_LIMITED / QUOTA_EXHAUSTED / AUTH_FAILED / TIMEOUT / MODEL_UNAVAILABLE / UNKNOWN` — directly modeled on `core/capabilities/router.py`'s existing `ResolutionStatus` enum shape, extended for this domain. **Do not build a duplicate health system** — if/when ATLAS gains a second real LLM provider, extend the *existing* capability-router pattern rather than inventing a parallel one.

## FALLBACK

Ordered `fallback_chain`, each entry still passing every hard eligibility filter (never degrade requirements to find a fallback). No valid fallback → `WAITING_PROVIDER` / `BLOCKED`, never silently picking an unsuitable model — same fail-closed philosophy as `QARetryState`.

## RETRY VS FALLBACK

Timeout → retry once, same model. Quota exhausted → fallback or `WAITING_PROVIDER`. Auth failure → do not retry (won't self-heal); escalate. Model unavailable → fallback immediately. This policy is currently **impossible to exercise for real** since ATLAS has only one provider today — it's a forward design, explicitly not implementable as live behavior yet (mission §29 already anticipates this: "no live autonomous model switching yet unless current architecture makes it trivial and safe" — it does not).

## REVIEWER INDEPENDENCE

Dimensions: different model, different provider, clean context, different agent role. Today only "different role" is guaranteed; "different model" holds only at the final `reality-checker` gate (Opus vs. mostly-Sonnet implementers), not at the `evidence-collector` QA step (often same tier as the dev-agent). Not every task needs every dimension — for `HIGH_RISK` specifically, the mission's own policy (different model + different provider where available) should gate `requires_human_approval` the same way `architecture_decision.py` already gates `NEEDS_HUMAN_APPROVAL` for security-sensitive proposals.

## AGENCY ROUTER BOUNDARY

Kept strictly separate from the Model Router, per mission §18/19 and consistent with the two prior audits this session (`DECOUPLED-SYSTEMS-ARCHITECTURE-V1.md`, `ATLAS-MAOS-DIRECTIONAL-BOUNDARY-V1.md`): Capability/Agency selection (native agent vs. MAOS vs. future agency) happens *before* the Model Router is even consulted — if a task routes to MAOS, ATLAS does not then dictate MAOS's internal model choice; MAOS owns that. **Not implemented in this audit** — ATLAS→MAOS capability remains `MISSING` as already established; this document only confirms where the Agency Router sits relative to the Model Router (upstream, mutually exclusive branch) and does not touch MAOS integration at all.

## CONFIGURATION (proposed)

One canonical `config/model-router.yaml`, same convention as `config/architecture.decision-policy.yaml`: `models`, `providers`, `task_classes`, `routing_weights`, `fallback_policy`, `risk_policy`, `review_policy` sections. Not created in this audit, per mission §23 ("do not create config until current architecture has been audited") — this document *is* that audit.

## MODEL METRICS (future, not implemented)

`tasks_attempted, tasks_completed, success_rate, retry_rate, average_latency, review_rejection_rate, fallback_rate, failure_type`, optional `cost` only if reliably available (today it is not — see Cost Tracking row above). No adaptive routing yet.

## FAILURE MODES

| Mode | Owner | Fallback | State | Notification |
|---|---|---|---|---|
| No eligible model | Model Router | none possible | `BLOCKED` | escalate to user |
| All providers unavailable | Model Router | none | `WAITING_PROVIDER` | escalate |
| Router config invalid/missing | Router (fail-open, like `architecture_decision.py`'s in-code defaults) | in-code default profile (Opus/Sonnet only) | degrade, don't crash | warn |
| Unknown model referenced | Router | reject that entry, continue with rest | — | warn |
| Health/quota state stale | Health subsystem | treat as `UNKNOWN`, not `AVAILABLE` | conservative | — |
| Provider fails after selection | Execution layer | one retry per §16 policy, then fallback | — | log |
| Reviewer unavailable | Reviewer selection | fall back to same-provider review with explicit `independence_degraded` flag | documented, not hidden | warn |
| Model response malformed | Execution layer | existing Return Envelope validation already catches this class of problem | — | — |

## SECURITY / COST POLICY

Router must not: enable a paid provider outside policy, read arbitrary credentials, disable approvals, select an unapproved model, alter risk classification to bypass controls, or change its own policy. Routing config stays externally controlled (human-edited YAML, same as `architecture.decision-policy.yaml` today). Cost policy enum: `FREE_ONLY / CONFIGURED_ONLY / ALLOW_PAID_WITH_APPROVAL / BUDGET_LIMITED` — this audit adds **no** paid provider and enables **no** spending; it only designs where the policy check would live (as a hard eligibility filter, same tier as the auth/quota checks).

## MODEL ROUTER VS AGENT ROUTER

Current ATLAS conflates them: picking an agent role (orchestrator judgment, unchanged) *is* picking a model today, because the binding is static 1:1 in frontmatter. Proposed order, justified by that exact evidence: Task Classifier → Agent Router (role selection, as today, orchestrator judgment) → **Model Router** (new: given the chosen role + this specific invocation's complexity/risk/context, pick the model/provider, rather than inheriting a hardcoded value) → Provider Health. This decouples "which role" from "which model" without touching role-selection logic at all.

## TEST STRATEGY (for the eventual implementation, not run now)

Simple FAST task, complex CODE task, large-context task, high-risk task, quota-exhausted provider, provider timeout, provider auth failure, no eligible provider, fallback selection, cost-policy rejection, reviewer independence, malformed config, determinism (same task + same state → same result). Per mission §31: tests must prove both correct selection *and* correct rejection — not just mirror the config back at itself. Mutation sanity (future): disabling eligibility, disabling health filtering, and inverting complexity scoring must each break a distinct test, the same disposable-worktree methodology already used in Stability Repairs 02/05/06 this session.

## MIGRATION PLAN

Purely additive. No existing agent frontmatter, dispatcher logic, or capability router changes. The two real models (Opus, Sonnet) keep working exactly as today for every agent that doesn't opt into dynamic routing; the Model Router is a new, parallel decision layer that — initially — has nothing to route to beyond those same two models, so its first real value is *structure and explainability*, not actual provider diversity (which doesn't exist yet).

## FIRST IMPLEMENTATION BATCH

1. `TaskRequirements` dataclass (normalized profile, no logic yet).
2. `config/model-router.yaml` with exactly the two verified real entries (Opus, Sonnet), `UNKNOWN` fields left `UNKNOWN`.
3. Deterministic eligibility filters (hard constraints only — reuse the `when_any`/`when_not` rule shape from `architecture_decision.py`).
4. Explainable scoring returning `{selected_model, score, reason, alternatives, fallback_chain}` — no live switching behavior yet, since there's nothing to switch *to*.
5. Fallback chain structure (will be trivially short — one entry — until a second provider exists).
6. Provider-health input interface, extending `core/capabilities/router.py`'s `ResolutionStatus` enum rather than duplicating it.
7. Dry-run CLI (`tools/model_router.py --dry-run`, mirroring `architecture_decision.py --text "..."`'s own CLI shape).
8. Tests per the Test Strategy section above, run against the dry-run CLI only.

No live autonomous model switching — current architecture does not make it trivial or safe (there is nothing to switch to yet), consistent with mission §29's own conditional.

## RISKS

1. **Scope mismatch risk**: building a rich multi-provider router when ATLAS has exactly one provider risks over-engineering — `architecture_decision.py`'s own `over_engineering` signal (`"plugin architecture", "generic abstraction", "new layer"`) would flag a naive version of this proposal. Mitigation: ship Batch 1 scoped to the two real models only; treat multi-provider support as design-ready, not design-complete, until JARVIS or another integration actually brings a second provider into scope.
2. **False sense of coverage**: `cost-tracker.js`/`cost-report.js` are named "cost" but track call counts, not dollars — any future metrics work must not silently inherit that naming confusion.
3. **Reviewer-independence gap**: the QA step (`evidence-collector`) currently shares a model tier with most dev-agents; a `HIGH_RISK` task today gets independence only at the very last gate (`reality-checker`), not throughout the loop — worth a dedicated look before this audit's design goes further, but out of scope here per mission's explicit "do not implement yet."

`MODEL_ROUTER_BASELINE_ESTABLISHED`
