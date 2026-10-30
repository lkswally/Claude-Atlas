#!/usr/bin/env python3
"""
Reviewer independence (roadmap P7): reduce self-confirmation, and never PRETEND to have reduced it.

Independence is a verified property of a review, not a label someone attaches to it. Four levels, weakest first:

    ROLE_ONLY             a different role (or the same model) -- also used when anything is unknown
    CONTEXT_INDEPENDENT   same model/provider, but a FRESH context (it did not see the implementer's reasoning)
    MODEL_INDEPENDENT     a different model, fresh context
    PROVIDER_INDEPENDENT  a different provider, fresh context

Rules that make the levels mean something:
  * reused context caps the level at ROLE_ONLY, whatever the model: a different model that was handed the
    implementer's chain of thought is not an independent check
  * unknown model/provider/context fails closed to ROLE_ONLY
  * the level is computed from FACTS (models, registry-derived providers, context flag); a claimed
    `independence_level` is only compared against it, never trusted; the provider is taken from the registry,
    not from what the record says
  * if the required level cannot be reached the plan says DEGRADED and why; at HIGH/CRITICAL risk a review that
    ends up ROLE_ONLY (a silent self-review) additionally requires a human gate

Required level by risk (extends config/model-router.yaml `review_policy`):
    LOW       ROLE_ONLY             normal QA role
    MEDIUM    CONTEXT_INDEPENDENT   fresh context and a different role
    HIGH      MODEL_INDEPENDENT     a different model preferred
    CRITICAL  PROVIDER_INDEPENDENT  different provider/model where available, security review, human gate

Record kept per review (concise, no reasoning):
    implementation_model, implementation_provider, review_model, review_provider, context_reused, independence_level
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.providers import provider_id_of  # noqa: E402
from tools.model_router import TaskRequirements, load_registry, route  # noqa: E402
from tools.provider_fallback import collect_health  # noqa: E402

__all__ = ["LEVELS", "POLICY", "classify_independence", "plan_review", "verify_review_record"]

LEVELS = ("ROLE_ONLY", "CONTEXT_INDEPENDENT", "MODEL_INDEPENDENT", "PROVIDER_INDEPENDENT")

POLICY: Dict[str, Dict[str, Any]] = {
    "LOW":      {"required": "ROLE_ONLY",            "fresh_context": False, "security_review": False, "human_gate": False},
    "MEDIUM":   {"required": "CONTEXT_INDEPENDENT",  "fresh_context": True,  "security_review": False, "human_gate": False},
    "HIGH":     {"required": "MODEL_INDEPENDENT",    "fresh_context": True,  "security_review": False, "human_gate": False},
    "CRITICAL": {"required": "PROVIDER_INDEPENDENT", "fresh_context": True,  "security_review": True,  "human_gate": True},
}

_RECORD_FIELDS = ("implementation_model", "implementation_provider", "review_model", "review_provider", "context_reused", "independence_level")


def _rank(level: Optional[str]) -> int:
    return LEVELS.index(level) if level in LEVELS else -1


def _text(v: Any) -> Optional[str]:
    return v if isinstance(v, str) and v.strip() else None


def classify_independence(rec: Mapping[str, Any]) -> str:
    """Level from facts only. Anything unknown or reused-context fails closed to ROLE_ONLY."""
    impl_m, rev_m = _text(rec.get("implementation_model")), _text(rec.get("review_model"))
    if not impl_m or not rev_m:
        return "ROLE_ONLY"
    if rec.get("context_reused") is not False:           # reused OR unknown
        return "ROLE_ONLY"
    impl_p, rev_p = _text(rec.get("implementation_provider")), _text(rec.get("review_provider"))
    if impl_p and rev_p and impl_p != rev_p:
        return "PROVIDER_INDEPENDENT"
    if impl_m != rev_m:
        return "MODEL_INDEPENDENT"
    return "CONTEXT_INDEPENDENT"


def plan_review(req: TaskRequirements, implementation_model: str, registry: Optional[dict] = None, *,
                providers: Optional[Mapping[str, Any]] = None, health_overrides: Optional[Mapping[str, str]] = None,
                probe_unknown: bool = False) -> Dict[str, Any]:
    """Pick the reviewer that reaches the highest independence among models that are ELIGIBLE and HEALTHY for a
    REVIEW task at this risk, and say plainly whether the policy was met."""
    registry = registry or load_registry()
    risk = req.risk if req.risk in POLICY else "CRITICAL"          # unknown risk is treated as the strictest
    pol = POLICY[risk]
    impl_provider = provider_id_of(registry, implementation_model)
    health: Dict[str, str] = {}
    if providers:
        health, _ = collect_health(providers, registry, probe_unknown=probe_unknown)
    health.update(health_overrides or {})                           # explicit signals win

    review_req = TaskRequirements(task_class="REVIEW", complexity=req.complexity, risk=risk,      # normalized: never raises on a bad risk
                                  execution_environment=req.execution_environment, cost_policy=req.cost_policy)
    decision = route(review_req, registry, health_overrides=health, log_decision=False)
    candidates: List[str] = ([decision["selected"]] if decision.get("selected") else []) + list(decision.get("alternatives", []))

    best, best_key = None, None
    for rank, model_id in enumerate(candidates):
        level = classify_independence({
            "implementation_model": implementation_model, "implementation_provider": impl_provider,
            "review_model": model_id, "review_provider": provider_id_of(registry, model_id),
            "context_reused": not pol["fresh_context"],
        })
        key = (_rank(level), -rank)                                 # higher independence first, then router rank
        if best_key is None or key > best_key:
            best, best_key = (model_id, level), key

    reviewer, achieved = best if best else (None, None)
    required = pol["required"]
    degraded = achieved is None or _rank(achieved) < _rank(required)
    if achieved is None:
        reason = f"no model is eligible and healthy to review at risk {risk}"
    elif degraded:
        gap = {"PROVIDER_INDEPENDENT": "no eligible, healthy reviewer from a different provider",
               "MODEL_INDEPENDENT": "no eligible, healthy reviewer other than the implementation model"}.get(required, "no eligible reviewer")
        reason = f"required {required} but the best reachable level is {achieved}: {gap}"
    else:
        reason = f"{achieved} reached by {reviewer}"
    self_review = achieved in (None, "ROLE_ONLY")
    human_gate = bool(pol["human_gate"] or (risk in ("HIGH", "CRITICAL") and self_review))
    return {
        "risk": risk, "required_level": required, "achieved_level": achieved, "degraded": degraded, "reason": reason,
        "reviewer_model": reviewer, "reviewer_provider": provider_id_of(registry, reviewer) if reviewer else None,
        "fresh_context_required": pol["fresh_context"], "security_review_required": pol["security_review"],
        "human_gate_required": human_gate, "silent_self_review_blocked": bool(risk in ("HIGH", "CRITICAL") and self_review),
        "candidates": candidates, "excluded": decision.get("excluded", {}),
        "record_template": {"implementation_model": implementation_model, "implementation_provider": impl_provider,
                            "review_model": reviewer, "review_provider": provider_id_of(registry, reviewer) if reviewer else None,
                            "context_reused": not pol["fresh_context"], "independence_level": achieved},
    }


def verify_review_record(record: Mapping[str, Any], risk: str, registry: Optional[dict] = None) -> Dict[str, Any]:
    """Check a finished review's record. The providers come from the REGISTRY, so a record cannot claim a more
    independent provider than the models actually belong to."""
    registry = registry or load_registry()
    problems: List[str] = []
    for f in _RECORD_FIELDS:
        if f not in record:
            problems.append(f"missing field: {f}")
    facts = dict(record)
    for side in ("implementation", "review"):
        model_id = _text(record.get(f"{side}_model"))
        known = provider_id_of(registry, model_id) if model_id else None
        said = _text(record.get(f"{side}_provider"))
        if model_id and known is None:
            problems.append(f"{side}_model {model_id!r} is not in the registry")
        if known and said and said != known:
            problems.append(f"{side}_provider {said!r} contradicts the registry ({model_id!r} belongs to {known!r})")
        facts[f"{side}_provider"] = known                            # registry wins over the record
    verified = classify_independence(facts)
    claimed = record.get("independence_level")
    if claimed not in LEVELS:
        problems.append(f"independence_level {claimed!r} is not one of {LEVELS}")
    overclaimed = claimed in LEVELS and _rank(claimed) > _rank(verified)
    if overclaimed:
        problems.append(f"over-claimed: record says {claimed} but the facts support only {verified}")
    required = POLICY.get(risk, POLICY["CRITICAL"])["required"]
    meets = _rank(verified) >= _rank(required)
    return {"verified_level": verified, "claimed_level": claimed, "overclaimed": overclaimed, "required_level": required,
            "meets_policy": meets and not problems, "problems": problems}
