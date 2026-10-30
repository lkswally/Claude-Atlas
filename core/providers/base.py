"""
Model provider boundary (roadmap P4).

Four things that must never be conflated, and where each one lives:

    Agent role  -- what job is done (reviewer, developer ...)      -> agent definitions / Agent Router
    Model       -- which intelligence (a model_id such as anthropic/sonnet)  -> Model Router
    Provider    -- who serves that model (this module)             -> ModelProvider
    Runtime     -- how the work is executed (Claude Code host, native, Herdr ...) -> AgentRuntime (roadmap P8)

A provider therefore knows about models, health and execution of a request for a model. Its types carry no
`role` and no `runtime` field (asserted by F41), and nothing here imports the Model Router: the router (a
higher layer) may consume providers, never the reverse.

Honesty rules baked into the contract:
  * UNKNOWN is a value, not a default. Unverified capabilities are None / "UNKNOWN", never guessed True/False.
  * A provider is not AVAILABLE because it is configured. health() reports only what a real signal supports.
  * execute() may be unsupported (host-managed providers). That is reported as NOT_EXECUTABLE, never faked.
  * No provider call can leak an exception, hang past its timeout, or return a malformed result to a caller:
    everything goes through invoke().
"""

from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

# Health of a provider/model as a ROUTING input. Shared vocabulary with tools/model_router.py (drift-tested).
HEALTH_STATES: Tuple[str, ...] = (
    "AVAILABLE", "DEGRADED", "RATE_LIMITED", "QUOTA_EXHAUSTED",
    "AUTH_FAILED", "MODEL_UNAVAILABLE", "TIMEOUT", "UNKNOWN",
)

# Outcome class of one execution. NONE only when ok=True.
ERROR_CLASSES: Tuple[str, ...] = (
    "NONE", "TIMEOUT", "RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_UNAVAILABLE",
    "INVALID_RESPONSE", "NOT_EXECUTABLE", "PROVIDER_ERROR", "CANCELLED",
)

TIERS = ("small", "medium", "large")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ normalized types
@dataclass(frozen=True)
class ProviderHealth:
    state: str
    reason: str
    source: str                    # where the signal came from, e.g. "host_session", "http_probe"
    checked_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class ProviderCapability:
    provider_id: str
    model_id: str                  # full id, "<provider>/<model>"
    supports_tools: Optional[bool]       # None = UNKNOWN (never guessed)
    supports_multimodal: Optional[bool]  # None = UNKNOWN
    context_tier: str              # "small" | "medium" | "large" | "UNKNOWN"
    latency_tier: str              # free-form tier or "UNKNOWN"
    strengths: Tuple[str, ...]
    cost_tier: str
    executable_from_atlas: bool    # False for host-managed providers: ATLAS can route to them, not invoke them


@dataclass(frozen=True)
class ProviderExecutionRequest:
    request_id: str
    model_id: str
    prompt: str
    timeout_s: float = 60.0
    max_tokens: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderExecutionResult:
    request_id: str
    provider_id: str
    model_id: str
    ok: bool
    error_class: str = "NONE"
    text: str = ""
    error_detail: str = ""
    latency_ms: float = 0.0
    health_hint: Optional[str] = None    # a HEALTH_STATES value this outcome implies, if any


# ------------------------------------------------------------------ failure classification
def classify_failure(status_code: Optional[int] = None, message: str = "",
                     exc: Optional[BaseException] = None) -> Tuple[str, str]:
    """Map a raw provider failure to (health_state, error_class). Structured signals win over text; anything
    unrecognized is (UNKNOWN, PROVIDER_ERROR) -- never silently AVAILABLE."""
    if exc is not None:
        if isinstance(exc, TimeoutError):
            return "TIMEOUT", "TIMEOUT"
        code = getattr(exc, "status_code", None)
        if isinstance(code, int) and status_code is None:
            status_code = code
        message = message or str(exc)
    if isinstance(status_code, int):
        if status_code == 429:
            return "RATE_LIMITED", "RATE_LIMITED"
        if status_code == 402:
            return "QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED"
        if status_code in (401, 403):
            return "AUTH_FAILED", "AUTH_FAILED"
        if status_code == 404:
            return "MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE"
        if status_code in (408, 504):
            return "TIMEOUT", "TIMEOUT"
        if status_code in (500, 502, 503, 529):
            return "DEGRADED", "PROVIDER_ERROR"
    text = message.lower() if isinstance(message, str) else ""
    rules = (
        (("not logged in", "/login", "invalid api key", "invalid x-api-key", "authentication", "unauthorized", "permission denied for key"),
         ("AUTH_FAILED", "AUTH_FAILED")),
        (("rate limit", "rate_limit", "too many requests"), ("RATE_LIMITED", "RATE_LIMITED")),
        (("usage limit", "quota", "credit balance", "insufficient credit", "billing"), ("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")),
        (("model not found", "model_not_found", "no such model", "does not exist", "model is not available", "not_found_error"),
         ("MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE")),
        (("timed out", "timeout", "deadline exceeded"), ("TIMEOUT", "TIMEOUT")),
        (("overloaded", "service unavailable", "internal server error", "bad gateway"), ("DEGRADED", "PROVIDER_ERROR")),
    )
    for needles, outcome in rules:
        if any(n in text for n in needles):
            return outcome
    return "UNKNOWN", "PROVIDER_ERROR"


# ------------------------------------------------------------------ the interface
class ModelProvider(abc.ABC):
    """One provider of models. Implementations must not leak vendor details outside their own module."""

    id: str = ""

    @abc.abstractmethod
    def health(self, model_id: Optional[str] = None) -> ProviderHealth:
        """Current health from a REAL signal. If there is none, return UNKNOWN -- not AVAILABLE."""

    @abc.abstractmethod
    def models(self) -> List[str]:
        """Full ids of the enabled models this provider serves."""

    @abc.abstractmethod
    def capabilities(self, model_id: str) -> Optional[ProviderCapability]:
        """Declared capabilities, or None if the model is not served by this provider."""

    @abc.abstractmethod
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        """Run one request. Callers go through invoke(), which adds timeout, validation and exception safety."""

    def cancel(self, request_id: str) -> bool:
        """Best-effort cancel. Default: unsupported."""
        return False

    def status(self) -> Dict[str, Any]:
        return {"id": self.id, "models": self.models()}


# ------------------------------------------------------------------ guarded access
def _result(request: ProviderExecutionRequest, provider_id: str, ok: bool, error_class: str, detail: str,
            latency_ms: float, hint: Optional[str] = None) -> ProviderExecutionResult:
    return ProviderExecutionResult(request.request_id, provider_id, request.model_id, ok, error_class,
                                   "", detail, round(latency_ms, 3), hint)


def _valid(result: Any, request: ProviderExecutionRequest, provider_id: str) -> Optional[str]:
    """Return None if the provider's answer is well-formed, else why not."""
    if not isinstance(result, ProviderExecutionResult):
        return f"provider returned {type(result).__name__}, not ProviderExecutionResult"
    if result.request_id != request.request_id or result.model_id != request.model_id:
        return "result does not answer this request (request_id/model_id mismatch)"
    if result.provider_id != provider_id:
        return "result claims a different provider_id"
    if not isinstance(result.ok, bool) or result.error_class not in ERROR_CLASSES:
        return "ok/error_class malformed"
    if result.ok and result.error_class != "NONE":
        return "ok=True with an error_class"
    if not result.ok and result.error_class == "NONE":
        return "ok=False without an error_class"
    if result.health_hint is not None and result.health_hint not in HEALTH_STATES:
        return "health_hint is not a known health state"
    return None


def invoke(provider: ModelProvider, request: ProviderExecutionRequest) -> ProviderExecutionResult:
    """The single way to call a provider. Never raises, never hangs past request.timeout_s, never returns a
    malformed result. An unknown model never reaches the provider's execute()."""
    t0 = time.perf_counter()
    pid = getattr(provider, "id", "") or "unknown"
    try:
        served = provider.models()
    except Exception as e:  # noqa: BLE001
        return _result(request, pid, False, "PROVIDER_ERROR", f"models() raised {type(e).__name__}: {e}", 0.0, "UNKNOWN")
    if request.model_id not in served:
        return _result(request, pid, False, "MODEL_UNAVAILABLE", f"{request.model_id} is not served by {pid}", 0.0, "MODEL_UNAVAILABLE")

    box: Dict[str, Any] = {}

    def run() -> None:
        try:
            box["result"] = provider.execute(request)
        except BaseException as e:  # noqa: BLE001  (a worker must never die silently)
            box["error"] = e

    worker = threading.Thread(target=run, name=f"provider-{pid}", daemon=True)
    worker.start()
    worker.join(max(0.0, float(request.timeout_s)))
    elapsed = (time.perf_counter() - t0) * 1000
    if worker.is_alive():
        try:
            provider.cancel(request.request_id)
        except Exception:  # noqa: BLE001
            pass
        return _result(request, pid, False, "TIMEOUT", f"no answer within {request.timeout_s}s (worker abandoned)", elapsed, "TIMEOUT")
    if "error" in box:
        state, klass = classify_failure(exc=box["error"])
        return _result(request, pid, False, klass, f"{type(box['error']).__name__}: {box['error']}", elapsed, state)
    res = box.get("result")
    problem = _valid(res, request, pid)
    if problem:
        return _result(request, pid, False, "INVALID_RESPONSE", problem, elapsed, "DEGRADED")
    return ProviderExecutionResult(res.request_id, res.provider_id, res.model_id, res.ok, res.error_class, res.text,
                                   res.error_detail, round(elapsed, 3), res.health_hint)


def safe_health(provider: ModelProvider, model_id: Optional[str] = None) -> ProviderHealth:
    """health() that cannot raise and cannot return an unknown state: failures degrade to UNKNOWN."""
    pid = getattr(provider, "id", "") or "unknown"
    try:
        h = provider.health(model_id)
    except Exception as e:  # noqa: BLE001
        return ProviderHealth("UNKNOWN", f"health() raised {type(e).__name__}: {e}", pid)
    if not isinstance(h, ProviderHealth) or h.state not in HEALTH_STATES:
        return ProviderHealth("UNKNOWN", "provider returned a malformed health value", pid)
    return h
