# Model Router V1 (F38)

Deterministic, explainable, **dry-run / advisory** model routing. Builds on `docs/MODEL-ROUTER-ARCHITECTURE-V1.md` (left unchanged). Code: `tools/model_router.py`; config: `config/model-router.yaml`; tests: `_qa/bloque-F38-model-router.py` (54 checks, registered in `config/test.registry.yaml`, runs in Quick and Release).

**Status: `DECISION_READY / ADVISORY`.** The router computes a recommendation. Nothing forces an agent to use it, and live automatic model switching is **not enabled**.

## Scope and verified providers

Two real candidates only: `anthropic/sonnet` and `anthropic/opus` (the only models verified inside this repo; both run via the Claude Code host). Codex, Gemini, Groq and OpenHands are **not** represented and cannot be selected. Every model characteristic that this repo cannot verify (`context_tier`, `latency_tier`, `supports_multimodal`) is `UNKNOWN`, and **a hard requirement on an `UNKNOWN` characteristic fails eligibility** (unverified ≠ supported). Consequences, by design: a `CONTEXT` (large-context) or `MULTIMODAL` task returns `NO_ELIGIBLE_MODEL` until an operator records vendor-verified values in `config/model-router.yaml`; `FAST` has no verified latency data, so Sonnet vs Opus is a tie resolved by registry order.

## Pipeline

`TaskRequirements` → **hard eligibility** → deterministic scoring of the survivors → selection + fallback chain → review/approval plan → (optional) decision log.

- **TaskRequirements** (every field changes a decision): `task_class` (FAST, CODE, ANALYSIS, CONTEXT, REVIEW, HIGH_RISK, RESEARCH, MULTIMODAL, or UNKNOWN), `complexity` (LOW…VERY_HIGH), `risk` (LOW…CRITICAL), `context_tier`, `latency_priority`, `quality_priority`, `tool_requirements`, `coding_required`, `reasoning_required`, `multimodal_required`, `independent_review_required`, `cost_policy`, `execution_environment`.
- **Classification** is keyword+weight+confidence (same mechanism as `tools/intent_classifier.py`). Ambiguous or empty input yields `UNKNOWN` → `ESCALATE_CLASSIFICATION`; the router does not guess. **Complexity** is derived from observable signals (file count, cross-module, external dependency, ambiguity, test surface, context, irreversibility) and returns its factors. **Risk** is derived independently (production/destructive, credential/security, sensitive data, reversibility); a large but safe refactor stays `LOW`.
- **Hard eligibility** (never overridden by score): model/provider disabled; health `RATE_LIMITED`/`QUOTA_EXHAUSTED`/`AUTH_FAILED`/`MODEL_UNAVAILABLE`, an invalid health string, or `UNKNOWN` health without the explicit `assume_available_if_unknown` flag; tools, multimodal or context requirement unsupported; task-class `min_strengths` / `coding_required` / `reasoning_required` not met; risk tier outside the model's `eligible_risks`; cost policy (V1 never enables paid tiers, even under `ALLOW_PAID_WITH_APPROVAL`/`BUDGET_LIMITED`); unsupported `execution_environment`.
- **Scoring** (weights in config): `task_fit`, `complexity_fit`, `risk_fit`, `latency_fit`, `quality_fit`, `context_fit`, `historical` (**0 / neutral** — no real per-model metrics exist), and a `DEGRADED` health penalty (still eligible, ranked lower). Output: `selected`, `provider`, `score`, `reason`, `alternatives`, `fallback_chain`, `excluded` (with reasons), `decision_factors`.
- **Fallback:** ordered, capped by `fallback_policy.max_chain_length`; every entry independently passed eligibility. Re-routing after a failure re-runs eligibility — a weaker model is never accepted blindly (e.g. CRITICAL risk with Opus unavailable → `NO_ELIGIBLE_MODEL`, not Sonnet).
- **Review plan:** `independent_review_required`/`recommended` come from the request, the task class, and `review_policy[risk]`. The plan lists reviewer candidates that differ from the implementation model (and provider, when the policy dimension is `model_and_provider`). If none exists it reports `independence: UNAVAILABLE…` — it never claims independence that only a role change would provide. `CRITICAL` also sets `human_approval_required`.
- **Cost policy** enum: `CONFIGURED_ONLY` (default, preserves current behavior), `FREE_ONLY`, `ALLOW_PAID_WITH_APPROVAL`, `BUDGET_LIMITED`. No spending is enabled and no paid provider added.

## Provider health

States: `AVAILABLE, DEGRADED, RATE_LIMITED, QUOTA_EXHAUSTED, AUTH_FAILED, MODEL_UNAVAILABLE, UNKNOWN`. Claude Code exposes no health/quota API to ATLAS, so no probe was built. Callers (or a future real signal) pass `health_overrides`. Without one, a model is `AVAILABLE` only through its explicit, config-visible `assume_available_if_unknown: true`, justified because the router only runs inside an already-active Claude Code session. This is a documented policy, not a silent conversion.

## Dry-run CLI

```bash
python tools/model_router.py --task-class CODE --complexity HIGH --risk MEDIUM
python tools/model_router.py --task-text "deploy to production and rotate the credential" --json
python tools/model_router.py --task-class FAST --no-log
```
Flags: `--complexity`, `--risk`, `--signals-json '{"file_count":6,"cross_module":true}'`, `--context-tier`, `--latency-priority`, `--quality-priority`, `--cost-policy`, `--coding-required`, `--reasoning-required`, `--json`, `--no-log`. When `--risk`/`--complexity` are omitted they are derived from `--task-text`/`--signals-json` and the factors are echoed under `derived`. Exit codes: `0` routed, `1` usage/validation error, `3` no route (`NO_ELIGIBLE_MODEL` or `ESCALATE_CLASSIFICATION`). No model is invoked, no process is spawned, no network is touched (a regression test asserts the source contains none of `subprocess`, `os.system`, `Popen`, `socket`, `urllib`, `requests`, `eval(`, `exec(`).

## Decision log and retention

One concise JSON line per decision in `.pipeline/model-router-decisions.jsonl` (`ts, task_class, complexity, risk, selected, fallback, excluded, reason`), no reasoning dump. Retention is built in from day one: capped at 500 lines, trimming to the newest 400 with an atomic temp-file replace (same convention as `cost-tracker.js`). Logging is fail-open and can be skipped with `--no-log` / `log_decision=False`.

## Metrics contract (design only; nothing implemented or aggregated)

Future event, one per executed task: `task_class, complexity, risk, model, provider, result, latency_ms, retry_count, review_result, fallback_used, failure_type`. No `success_rate` should be computed until enough real events exist; `historical` stays 0 until then. Adaptive routing, if ever added, must stay bounded and may not change security, cost or approval policy.

## Security

Routing config is **data**: the router never executes anything from it. Unknown keys are ignored (a test injects `command:`, `env:` and `autonomy_policy:` and proves they are inert), malformed or missing files fail open to the two verified models, and the router can only *select among* models already listed. It cannot enable commands, inject credentials, change approval or autonomy policy, or disable security controls. Risk and approval rules only get stricter than the model's own `eligible_risks`, never looser.

## Runtime enforcement boundary

What is **proven** in this repo: `tools/atlas_dispatcher.py` never spawns agents (it validates envelopes after they return); the router itself has no execution capability; no hook is registered on the `Agent` tool (`templates/settings.json` registers `PreToolUse` only for `Bash` and `Write|Edit`; the `PostToolUse` hooks `delegation-tracker`, `qa-auto-audit` and `cost-tracker` merely observe spawns after the fact).

What Claude Code **documents** (hooks reference, fetched 2026-10-29): the subagent tool is named `Agent`; its `tool_input` has `prompt, description, subagent_type, model` (`model` = "Optional model alias to override the default"); a `PreToolUse` hook may deny the call or return `hookSpecificOutput.updatedInput`, which replaces the **entire** input object before the tool runs (precedence among hooks: `deny > defer > ask > allow`; how several `updatedInput` values combine is not stated).

What is **not proven**: whether a `model` rewritten through `updatedInput` is actually honored for a subagent — the docs do not say, and note that `resolvedModel` can differ from `tool_input.model` when `availableModels` or another override applies. No such hook exists here, and the local `cost-log.jsonl` contains no `Agent` entries to inspect real payloads.

**Therefore Router V1 is `DECISION_READY / ADVISORY`.** The minimal future integration point is a `PreToolUse` hook with `matcher: "Agent"` that calls the router and returns `updatedInput` (full object, `model` set) with `permissionDecision: "allow"`. **Proof protocol before enabling** (needs owner approval, since it changes live agent behavior): register the hook only in a scratch project's local settings; spawn one harmless no-tool subagent; verify via a `PostToolUse` payload that `resolvedModel` equals the router's choice; confirm the hook fails open (exit 0, no rewrite) when the router errors; only then consider rollout. **Status 2026-10-30:** that protocol was built as an isolated lab (`tools/lab_model_enforcement/`, see `docs/MODEL-ROUTER-ENFORCEMENT-EXPERIMENT.md`); the first run stopped at `Not logged in` (no authenticated binary available to a script), so the verdict is `ENFORCEMENT_UNKNOWN` and the router remains advisory. Agent frontmatter `model:` declarations stay as compatibility defaults; none of the 27 were modified. Correction: earlier ATLAS documents said no interception point exists for `Agent` calls; see `docs/STABILITY-PHASE2-REMEDIATIONS.md`, "Correction (2026-10-29)".

## Agent / model decoupling

Today an agent role *is* its model (static, 1:1, frontmatter). V1 makes the intended flow expressible — agent role + `TaskRequirements` → Model Router → model — without changing anything: existing behavior is preserved until enforcement is proven.

## Known limitations

- Only two models, both Anthropic, both via the host; most of their characteristics are `UNKNOWN`, so `CONTEXT` and `MULTIMODAL` fail closed and FAST cannot differentiate.
- `eligible_risks` (Sonnet excluded from `CRITICAL`) is an ATLAS policy choice documented in config, not a vendor claim.
- No health probe, no quota data, no historical metrics, no latency/cost telemetry (the existing `cost-tracker.js` counts calls, not dollars).
- Task classification is heuristic and is meant to be overridden by an explicit `task_class`.
- Advisory only (above).

## Verification summary

54/54 checks pass, including 9 negative controls in which a synthetic candidate engineered to be the highest-scoring option is rejected by a single hard constraint. Mutation sanity in a disposable worktree: disabling eligibility (23 failures), inverting a scoring preference (4), ignoring provider health (6), and treating `UNKNOWN` as supported (2) were all caught; the clean copy returned to 54/54. Performance: pure decision ≈ 0.02–0.05 ms/route; default call path (registry parse cached by mtime) ≈ 0.25 ms/route over 1,000 routes; CLI end-to-end ≈ 0.5–0.7 s, dominated by interpreter and YAML import.
