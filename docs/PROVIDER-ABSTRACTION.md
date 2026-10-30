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

## Not done on purpose

No retry/fallback policy and no provider health wired into `route()` (P6), no runtime/role binding type (P8 defines it when it is used), no use of Codex by any ATLAS flow yet.

## Known limit

`invoke()` enforces its timeout with a daemon worker thread; a hung worker is abandoned, not killed. A real adapter (HTTP, subprocess) must enforce its own timeout at the I/O layer; the guard guarantees the *caller* is never blocked.
