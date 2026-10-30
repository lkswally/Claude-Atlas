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

## Not done on purpose

No second provider (P5), no retry/fallback policy (P6), no provider health wired into `route()` (there is no real signal to wire yet), no runtime/role binding type (P8 will define it when it is used).

## Known limit

`invoke()` enforces its timeout with a daemon worker thread; a hung worker is abandoned, not killed. A real adapter (HTTP, subprocess) must enforce its own timeout at the I/O layer; the guard guarantees the *caller* is never blocked.
