# Model provider abstraction (roadmap P4)

`core/providers/` separates **who serves a model** from everything around it. No second provider exists yet (that is P5); this phase makes one possible without touching routing logic, and represents today's path honestly.

## Four dimensions that stay separate

| Dimension | Meaning | Owner |
|---|---|---|
| Agent role | what job is done (reviewer, developer …) | agent definitions / Agent Router |
| Model | which intelligence, e.g. `anthropic/sonnet` | Model Router (`tools/model_router.py`) |
| **Provider** | who serves that model | **`ModelProvider` (this package)** |
| Runtime | how the work is executed (Claude Code host, native, Herdr …) | AgentRuntime (P8) |

Provider types carry no `role` / `runtime` field (F41 asserts it), and `core/providers` never imports `tools/` or the router: the router may consume providers, never the reverse.

## Contract (`core/providers/base.py`)

`ModelProvider`: `health(model_id)`, `models()`, `capabilities(model_id)`, `execute(request)`, `cancel(request_id)`, `status()`. Normalized types: `ProviderHealth`, `ProviderCapability`, `ProviderExecutionRequest`, `ProviderExecutionResult`.

Health states (shared with the router, drift-tested): `AVAILABLE, DEGRADED, RATE_LIMITED, QUOTA_EXHAUSTED, AUTH_FAILED, MODEL_UNAVAILABLE, TIMEOUT, UNKNOWN`. The router treats `RATE_LIMITED, QUOTA_EXHAUSTED, AUTH_FAILED, MODEL_UNAVAILABLE, TIMEOUT` as unservable.

Honesty rules, each covered by a negative control:
- **UNKNOWN is a value.** Unverified capabilities are `None` / `"UNKNOWN"`, never guessed `True`/`False`.
- **Configured ≠ available.** `health()` reports only what a real signal supports; with none it returns `UNKNOWN`.
- **`execute()` may be unsupported.** Reported as `NOT_EXECUTABLE`, never faked.
- **Nothing a provider does can leak.** All calls go through `invoke()`: an unserved model never reaches `execute()`, a hang is cut off at `timeout_s` (→ `TIMEOUT`, then a best-effort `cancel`), exceptions are classified not propagated, and any malformed answer (wrong type, wrong request/provider id, `ok` contradicting `error_class`, bad health hint) becomes `INVALID_RESPONSE`. `safe_health()` degrades a raising or garbage `health()` to `UNKNOWN`.

`classify_failure(status_code, message, exc)` maps raw failures to `(health, error_class)`: 429 → RATE_LIMITED; 402 / "usage limit" / "quota" → QUOTA_EXHAUSTED; 401 / 403 / "Not logged in" → AUTH_FAILED; 404 / "model not found" → MODEL_UNAVAILABLE; 408 / 504 / timeouts → TIMEOUT; 5xx / "overloaded" → DEGRADED; anything unrecognized → `(UNKNOWN, PROVIDER_ERROR)`. A structured status wins over message text. Retry-vs-fallback is **not** decided here (P6).

## Current path: `AnthropicHostProvider` (compatibility adapter)

The models are run by the Claude Code host through the `Agent` tool; ATLAS's dispatcher never spawns agents. So the adapter: lists the enabled models from `config/model-router.yaml` (single source), reports their declared capabilities (`executable_from_atlas = False`), returns `health() = UNKNOWN` (host-managed: no health/quota API), and `execute()` = `NOT_EXECUTABLE`. Whether to *assume* availability inside an active session stays a router policy (`assume_available_if_unknown`); a provider may not claim it. `build_providers(registry)` instantiates only providers with a verified adapter; anything else named in config is returned in `skipped` and never built.

Observable routing behavior is unchanged: the only router edit is adding `TIMEOUT` to the shared vocabulary (previously such a value failed closed as an invalid state; it still excludes the model).

## Second provider: Codex CLI (`core/providers/codex_cli.py`, roadmap P5)

**Why this one.** Audited by presence only (no secret read): the `codex` CLI is installed (0.147.0) and `codex login status` reports *Logged in using ChatGPT*. Gemini has a config directory but no CLI; Groq, Mistral, OpenRouter, Ollama and LM Studio have no CLI, no credential variable and no listening runtime. So: no new credential, no per-token spend (the owner's existing ChatGPT plan allowance, whose quota is finite), minimal work.

**It is the first provider ATLAS can actually invoke** (`executable_from_atlas = True`). Observed formats (real runs, not assumed): success is exit 0 + `turn.completed` (stderr may carry unrelated ERROR lines, so stderr is not a failure signal); an unknown model gives `turn.failed` with `code: model_not_found`; no login gives about 18 s of internal "Reconnecting… 401" before failing.

**Containment (it runs an agent binary):** argv list, never a shell; prompt on **stdin**; `--sandbox read-only --ephemeral --ignore-user-config --ignore-rules --skip-git-repo-check --json`; a private empty working directory that is removed afterwards; environment scrubbed of anything named key/token/secret/password/credential; prompts that contain obvious credentials (private-key headers, AWS/GitHub/Slack/Google/`sk-` keys) are refused before anything is spawned (a heuristic, not a guarantee); timeouts kill the **whole process tree** (the npm wrapper spawns the native binary). Prompts go to OpenAI: callers must not put credentials or regulated data in them.

**Health is a real signal or UNKNOWN.** `codex login status` (fast, local, cached 60 s) can say AUTH_FAILED or MODEL_UNAVAILABLE (CLI missing). *Logged in* alone is **UNKNOWN**, never AVAILABLE. AVAILABLE needs a recent successful round trip (`probe()` or any successful `execute()`, valid 10 min); a recent failure is reported as its mapped state for 2 min.

**Registered, not routable by accident.** `openai/codex-cli` is in `config/model-router.yaml` with `assume_available_if_unknown: false`, `supports_tools: false` (ATLAS tools are not available to it), `eligible_risks: [low, medium]`. With no health signal the router excludes it, so routing for every existing request is unchanged; given an AVAILABLE signal it becomes eligible. The router still rejects any non-`claude_code` execution environment globally, so making Codex actually selectable is a P6 decision.

**Proof.** F42: 51 offline checks replaying the real captures (mutation sanity 16/16), plus `--live` (5 checks against the real binary, all passing 2026-10-30): health, a PONG round trip → AVAILABLE, a nonexistent model → MODEL_UNAVAILABLE, an unauthenticated run (empty `CODEX_HOME`) → AUTH_FAILED, and a 1.5 s timeout → TIMEOUT with the process tree gone. **Not reproducible safely, so the wording is synthetic and labelled as such in the tests:** quota exhaustion and rate limiting.

## Fallback across providers (`tools/provider_fallback.py`, roadmap P6)

`execute_routed(req, prompt, providers, ...)` is the loop: **route → provider health → execute → classify the failure → retry the same model | fall back | stop**. Two facts about this architecture shape it. Only some providers are invocable by ATLAS (Codex); the Claude models are host-managed, so the primary may end as a `HANDOFF` for the host to run. And when the *host* reports that a Claude model failed, passing it as `known_failures` makes ATLAS re-route and execute the task on an invocable provider.

**Hard constraints are re-applied to every fallback candidate.** After each failure that leads to a fallback the router is run again from scratch with what was learned, so risk, tool, context, cost and environment rules govern every candidate. (A same-model retry re-runs the model the router just selected for the same task and skips the health filter: the provider's memory of the very failure that caused the retry would otherwise cancel it. Found by the failure-injection campaign, `docs/FAILURE-INJECTION-CAMPAIGN.md` D1.) A tempting fallback is never taken when they forbid it: with Claude out of quota, a HIGH-risk task does *not* fall back to Codex (outside its `eligible_risks`) and a task that needs tools does not either.

| Failure | Action |
|---|---|
| TIMEOUT, malformed answer (INVALID_RESPONSE), PROVIDER_ERROR | one same-model retry, then fall back (a TIMEOUT is never retried when the request is not idempotent) |
| RATE_LIMITED, QUOTA_EXHAUSTED, MODEL_UNAVAILABLE, AUTH_FAILED | fall back immediately; **AUTH_FAILED is never retried** |
| POLICY_BLOCKED, CANCELLED | **stop**: falling back would send a blocked prompt to another vendor |

Terminal states: `SUCCEEDED`, `HANDOFF`, `NO_ELIGIBLE_PROVIDER` (the constraints cannot be met by anyone, or only by persistently unavailable providers), `WAITING_PROVIDER` (someone can meet them but is transiently limited), `POLICY_BLOCKED`, `CANCELLED`, `FAILED` (attempt budget exhausted). Nothing sleeps or polls; executions are bounded by `max_attempts` and router passes by a separate hard bound (a mutation test found the first version could spin if the router kept returning a model with no adapter). The result reports `selected`, `executed_model`, `fallback_used`, `reason`, `provider_health`, `alternatives` and every attempt.

Proof: F43, 36 offline checks over fake providers (mutation sanity 16/16) plus `--live` (2 checks, passing 2026-10-30): Claude reported out of quota → the task ran on the real Codex and returned PONG with `fallback_used`; the same outage on a HIGH-risk task correctly returned `WAITING_PROVIDER` without touching Codex. Quota and rate-limit failures are injected, not reproduced against a real provider.

## Not done on purpose

No provider health plumbing inside `route()` itself (the executor passes it in), no persistent fallback metrics (the metrics event contract is still design only), no runtime/role binding type (P8 defines it when it is used), and no ATLAS flow calls the executor yet.

## Known limit

`invoke()` enforces its timeout with a daemon worker thread; a hung worker is abandoned, not killed. A real adapter (HTTP, subprocess) must enforce its own timeout at the I/O layer; the guard guarantees the *caller* is never blocked.
