#!/usr/bin/env python3
"""
Routed execution with provider fallback (roadmap P6).

    TaskRequirements -> eligibility -> ranking -> provider health -> primary -> execution
                     -> failure classification -> RETRY same model | FALLBACK | STOP

Two facts about this architecture shape the design:
  * Only some providers are INVOCABLE by ATLAS (Codex CLI). The Claude models are host-managed: ATLAS can route
    to them but the Claude Code host must run them. So the primary may end as a HANDOFF, not an execution.
  * When the HOST reports that a Claude model failed (usage limit ...), ATLAS can re-route with that knowledge
    (`known_failures`) and, if an invocable provider satisfies the task, execute it there.

Hard rule: after EVERY failure that is not a same-model retry the router is run again from scratch with what was
learned (a retry re-runs the model the router just selected for the same task, so its constraints are unchanged
and the provider's memory of the failure that caused the retry cannot veto it). Risk, tool,
context, cost and environment constraints are therefore re-applied to every fallback candidate; a fallback can
never bypass them, and if nothing satisfies them the answer is NO_ELIGIBLE_PROVIDER / WAITING_PROVIDER -- never
"the next best incompatible model".

Retry policy (bounded; total executions <= max_attempts; nothing sleeps or polls here):
    TIMEOUT / INVALID_RESPONSE / PROVIDER_ERROR  one same-model retry, then fallback (TIMEOUT only if idempotent)
    RATE_LIMITED / QUOTA_EXHAUSTED / MODEL_UNAVAILABLE / AUTH_FAILED / NOT_EXECUTABLE   fallback, never retried
    POLICY_BLOCKED / CANCELLED   STOP: falling back would push a blocked prompt to another vendor

Terminal states: SUCCEEDED | HANDOFF | NO_ELIGIBLE_PROVIDER (constraints cannot be met by anyone, or only by
persistently unavailable providers) | WAITING_PROVIDER (someone can satisfy them but is transiently limited)
| POLICY_BLOCKED | CANCELLED | FAILED (attempt budget exhausted).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.providers import (  # noqa: E402
    ProviderExecutionRequest,
    classify_failure,
    invoke,
    provider_id_of,
    safe_health,
)
from tools.model_router import TaskRequirements, load_registry, route  # noqa: E402

__all__ = ["DEFAULT_POLICY", "execute_routed", "collect_health"]

DEFAULT_POLICY: Dict[str, Any] = {
    "max_attempts": 4,
    "retries": {"TIMEOUT": 1, "INVALID_RESPONSE": 1, "PROVIDER_ERROR": 1},
    "stop_classes": ("POLICY_BLOCKED", "CANCELLED"),
}

UNSERVABLE = ("RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_UNAVAILABLE", "TIMEOUT")
TRANSIENT_STATES = ("RATE_LIMITED", "QUOTA_EXHAUSTED", "TIMEOUT")
TRANSIENT_CLASSES = ("TIMEOUT", "RATE_LIMITED", "QUOTA_EXHAUSTED", "INVALID_RESPONSE", "PROVIDER_ERROR")
_STATE_FOR_CLASS = {
    "TIMEOUT": "TIMEOUT", "RATE_LIMITED": "RATE_LIMITED", "QUOTA_EXHAUSTED": "QUOTA_EXHAUSTED",
    "AUTH_FAILED": "AUTH_FAILED", "MODEL_UNAVAILABLE": "MODEL_UNAVAILABLE",
}


def _cap(provider: Any, model_id: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return provider.capabilities(model_id), None
    except Exception as e:  # noqa: BLE001
        return None, f"capabilities() raised {type(e).__name__}: {e}"


def collect_health(providers: Mapping[str, Any], registry: Mapping[str, Any], *, probe_unknown: bool = True,
                   require_executable: bool = False, learned: Optional[Mapping[str, str]] = None) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Routing health per model from REAL signals. UNKNOWN is not passed on, so the router's own explicit
    assume_available_if_unknown policy decides. Returns (health_overrides, notes)."""
    over: Dict[str, str] = {}
    notes: Dict[str, str] = {}
    learned = learned or {}
    for model_id, cfg in (registry.get("models") or {}).items():
        if not isinstance(cfg, dict):
            continue
        prov = providers.get(provider_id_of(registry, model_id) or "")
        if prov is None:
            over[model_id], notes[model_id] = "MODEL_UNAVAILABLE", "no verified adapter for this provider"
            continue
        if model_id in learned:
            over[model_id], notes[model_id] = learned[model_id], "learned during this run"
            continue
        cap, err = _cap(prov, model_id)
        if err:
            over[model_id], notes[model_id] = "MODEL_UNAVAILABLE", err
            continue
        if cap is None:
            continue                                    # not served (e.g. disabled): the router excludes it itself
        if require_executable and not cap.executable_from_atlas:
            over[model_id], notes[model_id] = "MODEL_UNAVAILABLE", "not executable from ATLAS (host-managed)"
            continue
        h = safe_health(prov, model_id)
        if h.state == "UNKNOWN" and probe_unknown and cap.executable_from_atlas and hasattr(prov, "probe"):
            try:
                h = prov.probe(model_id)
                notes[model_id] = "health probed"
            except Exception:  # noqa: BLE001
                pass
        if h.state != "UNKNOWN":
            over[model_id] = h.state
            notes.setdefault(model_id, h.reason)
    return over, notes


def _decide(error_class: str, model: str, retries_used: Mapping[str, int], policy: Mapping[str, Any], idempotent: bool) -> str:
    if error_class in policy["stop_classes"]:
        return "STOP"
    allowed = int(policy["retries"].get(error_class, 0))
    if error_class == "TIMEOUT" and not idempotent:
        allowed = 0
    return "RETRY" if retries_used.get(model, 0) < allowed else "FALLBACK"


def _result(state: str, reason: str, **kw: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {"state": state, "reason": reason, "selected": None, "executed_model": None, "provider": None,
                            "fallback_used": False, "provider_health": {}, "alternatives": [], "text": None,
                            "handoff": None, "attempts": [], "blockers": {}}
    base.update(kw)
    return base


def execute_routed(req: TaskRequirements, prompt: str, providers: Mapping[str, Any], *,
                   registry: Optional[dict] = None, policy: Optional[Mapping[str, Any]] = None,
                   probe_unknown: bool = True, require_executable: bool = False,
                   known_failures: Optional[Mapping[str, Any]] = None, request_id: str = "req",
                   timeout_s: float = 60.0, idempotent: bool = True,
                   router: Callable[..., dict] = route) -> Dict[str, Any]:
    registry = registry or load_registry()
    pol = dict(DEFAULT_POLICY)
    pol.update(policy or {})
    learned: Dict[str, str] = {}
    cause: Dict[str, str] = {}
    for model_id, failure in (known_failures or {}).items():          # failures the HOST observed
        state, klass = classify_failure(message=failure if isinstance(failure, str) else "",
                                        status_code=failure if isinstance(failure, int) else None)
        learned[model_id] = state if state in UNSERVABLE else "MODEL_UNAVAILABLE"
        cause[model_id] = klass if klass != "NONE" else "PROVIDER_ERROR"

    attempts: List[Dict[str, Any]] = []
    retries_used: Dict[str, int] = {}
    first_selected: Optional[str] = None
    executions = 0
    health: Dict[str, str] = {}
    decision: dict = {}

    # Hard bound on router passes, independent of any other function: every pass either executes (bounded by
    # max_attempts) or learns about one more model (bounded by the registry), plus slack.
    passes = int(pol["max_attempts"]) + len(registry.get("models") or {}) + 2
    pending_retry: Optional[str] = None
    for _ in range(passes):
        if executions >= int(pol["max_attempts"]):
            break
        if pending_retry is not None:
            # A same-model retry is the policy's own probe of whether the failure was transient. Its constraints are
            # unchanged (the same model was just selected for the same task), so it does not go back through the health
            # filter: the provider's memory of the failure that CAUSED the retry would otherwise cancel the retry.
            model, pending_retry = pending_retry, None
        else:
            health, notes = collect_health(providers, registry, probe_unknown=probe_unknown,
                                           require_executable=require_executable, learned=learned)
            decision = router(req, registry, health_overrides=health, log_decision=False)
            model = decision.get("selected")
            if model is None:
                break
        if first_selected is None:
            first_selected = model
        prov = providers.get(provider_id_of(registry, model) or "")
        if prov is None:                                     # router picked a model with no adapter: learn it, re-route
            learned[model], cause[model] = "MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE"
            continue
        cap, _ = _cap(prov, model)
        is_fallback = bool(known_failures) or model != first_selected
        if not (cap and cap.executable_from_atlas):
            return _result("HANDOFF", f"{model} is host-managed: the Claude Code host must run it; ATLAS cannot invoke it",
                           selected=first_selected, provider=decision.get("provider"), provider_health=health,
                           alternatives=list(decision.get("alternatives", [])), attempts=attempts,
                           handoff={"model": model, "provider": decision.get("provider"),
                                    "fallback_chain": list(decision.get("fallback_chain", []))},
                           fallback_used=is_fallback)
        executions += 1
        r = invoke(prov, ProviderExecutionRequest(f"{request_id}-{executions}", model, prompt, timeout_s=timeout_s))
        entry = {"model": model, "provider": decision.get("provider"), "ok": r.ok, "error_class": r.error_class,
                 "latency_ms": r.latency_ms}
        if r.ok:
            entry["action"] = "SUCCESS"
            attempts.append(entry)
            return _result("SUCCEEDED", "executed", selected=first_selected, executed_model=model, provider=decision.get("provider"),
                           fallback_used=is_fallback, provider_health=health,
                           alternatives=list(decision.get("alternatives", [])), text=r.text, attempts=attempts)
        action = _decide(r.error_class, model, retries_used, pol, idempotent)
        entry["action"] = action
        attempts.append(entry)
        if action == "STOP":
            state = "POLICY_BLOCKED" if r.error_class == "POLICY_BLOCKED" else "CANCELLED"
            return _result(state, f"{r.error_class}: {r.error_detail} -- no fallback (it would route the same prompt elsewhere)",
                           selected=first_selected, provider=decision.get("provider"), provider_health=health, attempts=attempts)
        if action == "RETRY":
            retries_used[model] = retries_used.get(model, 0) + 1
            pending_retry = model
            continue
        learned[model] = _STATE_FOR_CLASS.get(r.error_class, "MODEL_UNAVAILABLE")
        cause[model] = r.error_class

    if decision.get("selected") is not None:
        return _result("FAILED", f"attempt budget exhausted ({pol['max_attempts']} executions)", selected=first_selected,
                       provider_health=health, attempts=attempts, alternatives=list(decision.get("alternatives", [])))

    # nothing eligible right now: is that "never" or "not at the moment"?
    healthy = {m: "AVAILABLE" for m, c in (registry.get("models") or {}).items() if isinstance(c, dict)}
    structural, _ = collect_health(providers, registry, probe_unknown=False, require_executable=require_executable)
    healthy.update({m: s for m, s in structural.items() if s == "MODEL_UNAVAILABLE" and m not in learned})
    when_healthy = router(req, registry, health_overrides=healthy, log_decision=False)
    capable = ([when_healthy["selected"]] + list(when_healthy.get("alternatives", []))) if when_healthy.get("selected") else []
    blockers = {m: health.get(m, "UNKNOWN") for m in capable}
    transient = [m for m, s in blockers.items() if cause.get(m) in TRANSIENT_CLASSES or s in TRANSIENT_STATES]
    common = dict(selected=first_selected, provider_health=health, attempts=attempts, blockers=blockers,
                  alternatives=list(decision.get("alternatives", [])))
    if not capable:
        detail = "; ".join(f"{m}: {' / '.join(r)}" for m, r in (when_healthy.get("excluded") or {}).items())
        return _result("NO_ELIGIBLE_PROVIDER", "no model satisfies the task's hard constraints, even if every provider were healthy: "
                       + (detail or str(when_healthy.get("reason"))), **common)
    if transient:
        return _result("WAITING_PROVIDER", f"constraint-satisfying providers are transiently limited: {sorted(transient)}", **common)
    return _result("NO_ELIGIBLE_PROVIDER", f"constraint-satisfying providers are persistently unavailable: {blockers}", **common)
