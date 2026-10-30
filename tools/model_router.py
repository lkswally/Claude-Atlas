"""
ATLAS Model Router V1 — F38
============================

Deterministic, explainable, DRY-RUN model routing. Advisory only.

ENFORCEMENT BOUNDARY (see docs/MODEL-ROUTER-V1.md, "Runtime enforcement
boundary"). What is proven vs documented-but-unproven:
  * PROVEN: tools/atlas_dispatcher.py never spawns agents (it validates
    envelopes after the fact), and this module invokes no model, process or
    network call -- route() only computes a decision.
  * DOCUMENTED, NOT PROVEN HERE: Claude Code's hook protocol lets a
    PreToolUse hook return hookSpecificOutput.updatedInput, which replaces a
    tool's whole input object before it runs; the subagent tool is named
    `Agent` and its tool_input has `prompt, description, subagent_type,
    model`. Whether a rewritten `model` is honored is NOT stated by the docs
    (they note `resolvedModel` can differ from `tool_input.model`), and no
    such hook is registered or tested in this repo. Until that is proven
    on a real spawn, this router is DECISION_READY / ADVISORY: an
    orchestrator may read its recommendation and pass `model` itself, but
    nothing here forces it. Live automatic switching is NOT enabled.

Only anthropic/sonnet and anthropic/opus are real candidates (the only
providers verified inside this repo). Nothing here represents Codex/Gemini/
Groq/OpenHands as usable. Unknown model characteristics stay "UNKNOWN" and
a hard requirement on an UNKNOWN characteristic FAILS (unverified != supported).

CLI:
  python tools/model_router.py --task-class CODE --complexity HIGH --risk MEDIUM
  python tools/model_router.py --task-text "implement a bug fix" --json
Exit codes: 0 routed, 1 usage/validation error, 3 no route (NO_ELIGIBLE_MODEL / UNKNOWN class).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _PROJECT_ROOT / "config" / "model-router.yaml"
_DECISION_LOG = _PROJECT_ROOT / ".pipeline" / "model-router-decisions.jsonl"
_DECISION_LOG_MAX_LINES = 500  # same bounded-retention convention as cost-tracker.js

TASK_CLASSES = ("FAST", "CODE", "ANALYSIS", "CONTEXT", "REVIEW", "HIGH_RISK", "RESEARCH", "MULTIMODAL")
COMPLEXITY_TIERS = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")
RISK_TIERS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
# Same vocabulary as core/providers/base.py (F41 asserts they never drift). TIMEOUT = the last attempt
# timed out: not servable now; whether to retry or fall back is decided later, not by eligibility.
HEALTH_STATES = ("AVAILABLE", "DEGRADED", "RATE_LIMITED", "QUOTA_EXHAUSTED",
                 "AUTH_FAILED", "MODEL_UNAVAILABLE", "TIMEOUT", "UNKNOWN")
_UNSERVABLE_HEALTH = ("RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_UNAVAILABLE", "TIMEOUT")
_CONTEXT_RANK = {"small": 0, "medium": 1, "large": 2}
COST_POLICIES = ("CONFIGURED_ONLY", "FREE_ONLY", "ALLOW_PAID_WITH_APPROVAL", "BUDGET_LIMITED")

# In-code defaults mirror config/model-router.yaml (fail-open convention of
# tools/architecture_decision.py). Cost policy default preserves current
# behavior: no paid service becomes active.
_DEFAULT_REGISTRY: dict = {
    "version": 1,
    "providers": {"anthropic": {"enabled": True, "health_source": "host_session"}},
    "models": {
        "anthropic/sonnet": {
            "provider": "anthropic", "enabled": True,
            "strengths": ["coding", "analysis", "tool_use"],
            "supports_tools": True, "supports_multimodal": "UNKNOWN",
            "context_tier": "UNKNOWN", "latency_tier": "UNKNOWN", "cost_tier": "configured_free",
            "eligible_risks": ["low", "medium", "high"], "assume_available_if_unknown": True,
        },
        "anthropic/opus": {
            "provider": "anthropic", "enabled": True,
            "strengths": ["reasoning", "analysis", "coding"],
            "supports_tools": True, "supports_multimodal": "UNKNOWN",
            "context_tier": "UNKNOWN", "latency_tier": "UNKNOWN", "cost_tier": "configured_free",
            "eligible_risks": ["low", "medium", "high", "critical"], "assume_available_if_unknown": True,
        },
    },
    "task_classes": {
        "FAST": {"prefer_strengths": [], "prefer_latency": "low", "min_strengths": []},
        "CODE": {"prefer_strengths": ["coding"], "min_strengths": ["coding"]},
        "ANALYSIS": {"prefer_strengths": ["reasoning"], "min_strengths": ["analysis"]},
        "CONTEXT": {"prefer_strengths": [], "min_strengths": [], "requires_context_tier": "large"},
        "REVIEW": {"prefer_strengths": ["reasoning"], "min_strengths": [], "independent_review_preferred": True},
        "HIGH_RISK": {"prefer_strengths": ["reasoning", "coding"], "min_strengths": ["analysis"],
                      "independent_review_required": True},
        "RESEARCH": {"prefer_strengths": ["reasoning"], "min_strengths": ["analysis"]},
        "MULTIMODAL": {"prefer_strengths": [], "min_strengths": [], "requires_multimodal": True},
    },
    "routing_weights": {"task_fit": 3, "complexity_fit": 2, "risk_fit": 2, "latency_fit": 1,
                        "quality_fit": 2, "context_fit": 1, "historical": 0, "degraded_penalty": 2},
    "fallback_policy": {"max_chain_length": 3},
    "risk_policy": {"critical_requires_human_approval": True},
    "cost_policy": {"default": "CONFIGURED_ONLY"},
    "review_policy": {
        "LOW": {"independent_required": False},
        "MEDIUM": {"independent_required": False},
        "HIGH": {"independent_required": True, "dimension": "model"},
        "CRITICAL": {"independent_required": True, "dimension": "model_and_provider", "human_approval": True},
    },
}

_REGISTRY_SECTIONS = ("providers", "models", "task_classes", "routing_weights",
                      "fallback_policy", "risk_policy", "cost_policy", "review_policy")


def _copy_defaults() -> dict:
    return json.loads(json.dumps(_DEFAULT_REGISTRY))


def _sanitize(data: object) -> dict:
    """Keep only well-formed content. Routing config is data: it is never
    executed, and unknown keys (e.g. a `command:` entry) are ignored, so a
    config file cannot add executable behavior, credentials or policy."""
    reg = _copy_defaults()
    if not isinstance(data, dict):
        return reg
    for key in _REGISTRY_SECTIONS:
        section = data.get(key)
        if not isinstance(section, dict) or not section:
            continue
        if key in ("models", "providers", "task_classes"):
            clean = {k: v for k, v in section.items() if isinstance(k, str) and isinstance(v, dict)}
            if clean:
                reg[key] = clean
        else:
            reg[key] = section
    return reg


_PARSE_CACHE: dict = {}  # (path, mtime_ns, size) -> sanitized registry


def load_registry(path: Path | None = None) -> dict:
    """Load config/model-router.yaml; fail-open to the in-code defaults on a
    missing/unparseable/malformed file, never crash the router. The parse is
    cached per (path, mtime, size) and a defensive copy is returned, so a
    caller that mutates its registry cannot corrupt later calls."""
    target = path or _REGISTRY_PATH
    try:
        st = target.stat()
    except OSError:
        return _copy_defaults()
    key = (str(target), st.st_mtime_ns, st.st_size)
    cached = _PARSE_CACHE.get(key)
    if cached is None:
        try:
            import yaml
            cached = _sanitize(yaml.safe_load(target.read_text(encoding="utf-8")))
        except Exception:
            cached = _copy_defaults()
        _PARSE_CACHE.clear()  # keep at most one entry
        _PARSE_CACHE[key] = cached
    return json.loads(json.dumps(cached))


@dataclass
class TaskRequirements:
    """Every field changes a routing decision (eligibility, scoring or the
    review/approval plan) -- no decorative metadata."""
    task_class: str                       # TASK_CLASSES or "UNKNOWN"      -> class policy
    complexity: str = "MEDIUM"            # COMPLEXITY_TIERS               -> complexity_fit
    risk: str = "LOW"                     # RISK_TIERS                     -> eligibility + risk_fit + review
    context_tier: str = "UNKNOWN"         # small|medium|large|UNKNOWN     -> eligibility + context_fit
    latency_priority: str = "normal"      # low|normal|high                -> latency_fit
    quality_priority: str = "normal"      # low|normal|high                -> quality_fit
    tool_requirements: list = field(default_factory=list)  # non-empty    -> eligibility (supports_tools)
    coding_required: bool = False         # -> eligibility (needs "coding" strength)
    reasoning_required: bool = False      # -> eligibility (needs "reasoning" strength)
    multimodal_required: bool = False     # -> eligibility
    independent_review_required: bool = False  # -> review plan
    cost_policy: str = "CONFIGURED_ONLY"  # COST_POLICIES                  -> eligibility
    execution_environment: str = "claude_code"  # -> eligibility

    def __post_init__(self):
        if self.task_class not in TASK_CLASSES and self.task_class != "UNKNOWN":
            raise ValueError(f"unknown task_class {self.task_class!r}, must be one of {TASK_CLASSES} or UNKNOWN")
        if self.complexity not in COMPLEXITY_TIERS:
            raise ValueError(f"unknown complexity {self.complexity!r}, must be one of {COMPLEXITY_TIERS}")
        if self.risk not in RISK_TIERS:
            raise ValueError(f"unknown risk {self.risk!r}, must be one of {RISK_TIERS}")
        if self.cost_policy not in COST_POLICIES:
            raise ValueError(f"unknown cost_policy {self.cost_policy!r}, must be one of {COST_POLICIES}")


# --------------------------------------------------------------------------
# Deterministic classification (keyword+weight+confidence, same mechanism as
# tools/intent_classifier.py; different output domain). Ambiguity => UNKNOWN.
# --------------------------------------------------------------------------
_CLASS_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "HIGH_RISK": [
        (r"\bproduction\b|\bproducci[oó]n\b", 3), (r"\bdeploy\w*\b|\bdespleg\w*\b", 2),
        (r"\bcredential\w*\b|\bsecret\w*\b|\bpassword\w*\b|\bapi.?key\w*\b", 3),
        (r"\bmigrat\w*\b|\bmigraci[oó]n\b", 2), (r"\bdrop table\b|\bdelete\b.{0,20}\bdatabase\b", 3),
        (r"\bauth\w*\b|\bsecurity\b|\bseguridad\b", 2),
    ],
    "RESEARCH": [(r"\bresearch\b|\binvestig\w*\b", 3), (r"\bcompar\w*\b", 2), (r"\bbenchmark\w*\b", 2),
                 (r"\bmarket\b|\bmercado\b", 1), (r"\bliterature\b|\bsurvey\b", 2)],
    "ANALYSIS": [(r"\barchitect\w*\b|\barquitect\w*\b", 3), (r"\banaliz\w*\b|\banalyz\w*\b|\banalysis\b", 2),
                 (r"\broot cause\b|\bcausa raiz\b", 3), (r"\baudit\w*\b", 2)],
    "CONTEXT": [(r"\bentire (?:codebase|repo)\b|\btodo el repo\b", 3), (r"\blarge (?:document|file)\b", 2),
                (r"\bsummariz\w* .{0,15}\b(?:repo|document|book)\b", 2)],
    "REVIEW": [(r"\bcode review\b", 3), (r"\breview\b|\brevis\w*\b", 3), (r"\bsecond opinion\b", 2),
               (r"\bindependent (?:check|verification)\b", 3)],
    "MULTIMODAL": [(r"\bimage\b|\bimagen\b|\bscreenshot\b|\bphoto\b", 2), (r"\bvideo\b|\baudio\b", 2)],
    "CODE": [(r"\bimplement\w*\b|\bimplementa\w*\b", 3), (r"\bdebug\w*\b|\bfix\b|\barregl\w*\b", 2),
             (r"\btest\w*\b", 1), (r"\brefactor\w*\b", 2), (r"\bwrite .{0,10}(?:code|function|class)\b", 2)],
    "FAST": [(r"\bclassif\w*\b", 2), (r"\bextract\w*\b", 2), (r"\bshort\b|\bsimple\b|\bbrief\b", 1)],
}


def classify_task_class(text: str) -> dict:
    """{task_class, confidence, signals, rationale}. Low confidence => UNKNOWN
    (ESCALATE_CLASSIFICATION): the caller must supply task_class explicitly."""
    low = (text or "").lower()
    scores: dict[str, int] = {}
    signals: list[dict] = []
    for cls, patterns in _CLASS_KEYWORDS.items():
        total = 0
        for pattern, weight in patterns:
            if re.search(pattern, low, re.I):
                total += weight
                signals.append({"class": cls, "pattern": pattern, "weight": weight})
        if total:
            scores[cls] = total
    if not scores:
        return {"task_class": "UNKNOWN", "confidence": "low", "signals": [],
                "rationale": "no keyword signal matched any task class"}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_cls, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    if top >= 3 and top - second >= 2:
        confidence = "high"
    elif top >= 2 and top > second:
        confidence = "medium"
    else:
        return {"task_class": "UNKNOWN", "confidence": "low", "signals": signals,
                "rationale": f"ambiguous: top candidates {ranked[:2]}"}
    return {"task_class": top_cls, "confidence": confidence, "signals": signals,
            "rationale": f"keyword signals favored {top_cls} (score {top} vs next {second})"}


def estimate_complexity(signals: dict) -> tuple[str, list[str]]:
    """Observable signals only -- never an unexplained LLM score. Returns the
    tier and the concise factors that produced it."""
    factors: list[str] = []
    score = 0
    fc = signals.get("file_count") or 0
    if fc > 5:
        score += 2; factors.append("multi-file (>5)")
    elif fc > 1:
        score += 1; factors.append("multi-file (2-5)")
    for key, pts, label in (("cross_module", 2, "cross-module impact"),
                            ("external_dependency", 1, "external dependency"),
                            ("ambiguous", 2, "ambiguous requirements"),
                            ("test_surface_large", 1, "broad test surface"),
                            ("context_large", 1, "large context"),
                            ("irreversible", 1, "irreversible change")):
        if signals.get(key):
            score += pts; factors.append(label)
    tier = "VERY_HIGH" if score >= 6 else "HIGH" if score >= 4 else "MEDIUM" if score >= 2 else "LOW"
    return tier, (factors or ["no elevating signal observed"])


_RISK_SIGNALS: dict[str, list[str]] = {
    "security_sensitive": ["secret", "credential", "auth", "permission", "password", "token", "api key"],
    "production_or_destructive": ["production", "producción", "deploy to prod", "drop table",
                                  "delete database", "migration", "migración", "rm -rf", "force push"],
    "data_sensitive": ["pii", "personal data", "customer data", "gdpr"],
    "reversible": ["reversible", "revert", "rollback", "behind flag", "disabled by default",
                   "docs only", "comment only"],
}


def estimate_risk(text: str, signals: Optional[dict] = None) -> tuple[str, list[str]]:
    """Independent of complexity (same signal mechanism as architecture_decision.py)."""
    low = (text or "").lower()
    found = [n for n, kws in _RISK_SIGNALS.items() if any(k in low for k in kws)]
    score = 0
    factors: list[str] = []
    if "production_or_destructive" in found:
        score += 3; factors.append("production/destructive keyword")
    if "security_sensitive" in found:
        score += 3; factors.append("security/credential keyword")
    if "data_sensitive" in found:
        score += 2; factors.append("sensitive-data keyword")
    if (signals or {}).get("multi_system"):
        score += 1; factors.append("multiple systems involved")
    if "reversible" in found:
        score = max(0, score - 2); factors.append("explicitly reversible")
    tier = "CRITICAL" if score >= 5 else "HIGH" if score >= 3 else "MEDIUM" if score >= 1 else "LOW"
    return tier, (factors or ["no elevating signal observed"])


# --------------------------------------------------------------------------
# Provider health. No runtime health/quota API exists for Claude Code's
# host-managed models, so UNKNOWN is never silently converted to AVAILABLE
# except via the explicit, config-visible `assume_available_if_unknown` flag.
# --------------------------------------------------------------------------
def resolve_health(model_id: str, model_cfg: dict, health_overrides: Optional[dict] = None) -> str:
    overrides = health_overrides or {}
    if model_id in overrides:
        value = overrides[model_id]
        return value if value in HEALTH_STATES else "INVALID_HEALTH_STATE"  # fail closed
    return "AVAILABLE" if model_cfg.get("assume_available_if_unknown") else "UNKNOWN"


def _effective(req: TaskRequirements, class_policy: dict) -> dict:
    need_ctx = "large" if (req.context_tier == "large" or class_policy.get("requires_context_tier") == "large") \
        else req.context_tier
    min_strengths = set(class_policy.get("min_strengths") or [])
    if req.coding_required:
        min_strengths.add("coding")
    if req.reasoning_required:
        min_strengths.add("reasoning")
    return {
        "multimodal": bool(req.multimodal_required or class_policy.get("requires_multimodal")),
        "context_rank": _CONTEXT_RANK.get(need_ctx, 0) if need_ctx in ("medium", "large") else 0,
        "context_need": need_ctx,
        "min_strengths": min_strengths,
    }


def check_eligibility(model_id: str, model_cfg: dict, req: TaskRequirements, health: str,
                      registry: dict, class_policy: Optional[dict] = None) -> tuple[bool, list[str]]:
    """Hard filters, evaluated BEFORE scoring. A high score never overrides these."""
    class_policy = class_policy if class_policy is not None else registry.get("task_classes", {}).get(req.task_class, {})
    eff = _effective(req, class_policy)
    reasons: list[str] = []

    if not model_cfg.get("enabled", False):
        reasons.append("disabled in registry")
    if not registry.get("providers", {}).get(model_cfg.get("provider"), {}).get("enabled", False):
        reasons.append(f"provider {model_cfg.get('provider')!r} not enabled")

    if health in _UNSERVABLE_HEALTH:
        reasons.append(f"health={health}")
    elif health == "UNKNOWN":
        reasons.append("health=UNKNOWN (no assume_available_if_unknown policy for this model)")
    elif health not in HEALTH_STATES:
        reasons.append(f"health={health}")

    if req.tool_requirements and not model_cfg.get("supports_tools"):
        reasons.append("required tools unsupported")
    if eff["multimodal"] and model_cfg.get("supports_multimodal") is not True:
        reasons.append("multimodal required but not confirmed supported")
    if eff["context_rank"] > 0:
        have = _CONTEXT_RANK.get(model_cfg.get("context_tier"), -1)
        if have < eff["context_rank"]:
            reasons.append(f"{eff['context_need']} context required but model context_tier="
                           f"{model_cfg.get('context_tier')} (unverified != supported)")
    missing = eff["min_strengths"] - set(model_cfg.get("strengths") or [])
    if missing:
        reasons.append(f"required capability unsupported: {sorted(missing)}")

    if req.risk.lower() not in [str(r).lower() for r in (model_cfg.get("eligible_risks") or [])]:
        reasons.append(f"risk tier {req.risk} not in model's eligible_risks {model_cfg.get('eligible_risks')}")

    cost_tier = model_cfg.get("cost_tier", "UNKNOWN")
    if req.cost_policy in ("FREE_ONLY", "CONFIGURED_ONLY") and cost_tier != "configured_free":
        reasons.append(f"cost_policy={req.cost_policy} but model cost_tier={cost_tier}")
    if req.cost_policy in ("ALLOW_PAID_WITH_APPROVAL", "BUDGET_LIMITED") and cost_tier not in ("configured_free",):
        # V1 never enables spending: paid tiers stay ineligible even under these policies.
        reasons.append(f"cost_policy={req.cost_policy} but paid tiers are not enabled in V1 (cost_tier={cost_tier})")

    if req.execution_environment != "claude_code":
        reasons.append(f"execution_environment {req.execution_environment!r} not supported by this router")
    return (not reasons), reasons


def score_model(model_id: str, model_cfg: dict, req: TaskRequirements, class_policy: dict,
                weights: dict, health: str = "AVAILABLE") -> dict:
    """Deterministic, explainable. historical=0 (neutral): no real per-model
    metrics exist yet."""
    strengths = set(model_cfg.get("strengths") or [])
    reasoning = "reasoning" in strengths
    eff = _effective(req, class_policy)
    prefer = set(class_policy.get("prefer_strengths") or [])
    w = lambda k: weights.get(k, 0)  # noqa: E731
    wants_low_latency = req.latency_priority == "high" or class_policy.get("prefer_latency") == "low"
    factors = {
        "task_fit": w("task_fit") if (not prefer or prefer & strengths) else 0,
        "complexity_fit": w("complexity_fit") if (req.complexity in ("LOW", "MEDIUM") or reasoning) else 0,
        "risk_fit": w("risk_fit") if (req.risk in ("LOW", "MEDIUM") or reasoning) else 0,
        # only a KNOWN low-latency tier earns this when speed is wanted; UNKNOWN earns nothing.
        "latency_fit": w("latency_fit") if (not wants_low_latency or model_cfg.get("latency_tier") == "low") else 0,
        "quality_fit": w("quality_fit") if (req.quality_priority != "high" or reasoning) else 0,
        "context_fit": w("context_fit") if (eff["context_rank"] == 0 or
                                             _CONTEXT_RANK.get(model_cfg.get("context_tier"), -1) >= eff["context_rank"]) else 0,
        "historical": 0,
        "health_penalty": -w("degraded_penalty") if health == "DEGRADED" else 0,
    }
    return {"model_id": model_id, "total": sum(factors.values()), "factors": factors, "health": health}


def _review_plan(req: TaskRequirements, class_policy: dict, registry: dict, selected: str,
                 eligible: dict[str, dict]) -> dict:
    """Never claims independence that does not exist: if the only reviewer
    candidates share the implementation model (or provider, when the policy
    demands it), independence is reported as unavailable."""
    pol = registry.get("review_policy", {}).get(req.risk, {})
    required = bool(req.independent_review_required or class_policy.get("independent_review_required")
                    or pol.get("independent_required"))
    recommended = required or bool(class_policy.get("independent_review_preferred"))
    dimension = pol.get("dimension", "model") if required else None
    sel_provider = eligible[selected].get("provider")
    candidates = [m for m in eligible if m != selected]
    if dimension == "model_and_provider":
        candidates = [m for m in candidates if eligible[m].get("provider") != sel_provider]
    plan = {"required": required, "recommended": recommended, "dimension": dimension,
            "reviewer_candidates": candidates}
    if required or recommended:
        plan["independence"] = "available" if candidates else (
            "UNAVAILABLE: no eligible reviewer differs from the implementation "
            + ("model/provider" if dimension == "model_and_provider" else "model"))
    return plan


def route(req: TaskRequirements, registry: Optional[dict] = None,
          health_overrides: Optional[dict] = None, log_decision: bool = True) -> dict:
    """Zero execution side effects: never invokes a model or spawns an agent.
    Only I/O is the optional, bounded decision-log append."""
    registry = registry or load_registry()
    class_policy = registry.get("task_classes", {}).get(req.task_class, {})

    def _finish(result: dict) -> dict:
        if log_decision:
            _log_decision(req, result)
        return result

    if req.task_class == "UNKNOWN":
        return _finish({"selected": None, "provider": None, "score": None,
                        "reason": "ESCALATE_CLASSIFICATION: task_class is UNKNOWN -- classification confidence "
                                  "too low to route; caller must supply an explicit task_class",
                        "alternatives": [], "fallback_chain": [], "excluded": {}, "decision_factors": []})

    excluded: dict[str, list[str]] = {}
    eligible: dict[str, dict] = {}
    healths: dict[str, str] = {}
    for model_id, cfg in registry.get("models", {}).items():
        health = resolve_health(model_id, cfg, health_overrides)
        ok, reasons = check_eligibility(model_id, cfg, req, health, registry, class_policy)
        if ok:
            eligible[model_id] = cfg
            healths[model_id] = health
        else:
            excluded[model_id] = reasons

    if not eligible:
        return _finish({"selected": None, "provider": None, "score": None,
                        "reason": "NO_ELIGIBLE_MODEL -- every candidate failed a hard eligibility filter",
                        "alternatives": [], "fallback_chain": [], "excluded": excluded, "decision_factors": []})

    weights = registry.get("routing_weights", {})
    # Stable sort on total only: ties fall back to registry order -- intentional
    # ("don't invent a preference you can't justify").
    scored = [score_model(m, c, req, class_policy, weights, healths[m]) for m, c in eligible.items()]
    scored.sort(key=lambda s: s["total"], reverse=True)
    primary = scored[0]
    max_chain = registry.get("fallback_policy", {}).get("max_chain_length", 3)
    positive = [k for k, v in primary["factors"].items() if v > 0]
    review = _review_plan(req, class_policy, registry, primary["model_id"], eligible)
    approval = (req.risk == "CRITICAL" and registry.get("risk_policy", {}).get("critical_requires_human_approval", False)) \
        or bool(registry.get("review_policy", {}).get(req.risk, {}).get("human_approval"))
    return _finish({
        "selected": primary["model_id"],
        "provider": eligible[primary["model_id"]].get("provider"),
        "score": primary["total"],
        "reason": f"task_class={req.task_class} complexity={req.complexity} risk={req.risk} -- "
                  f"positive factors: {', '.join(positive) or 'none (baseline eligible candidate)'}",
        "alternatives": [s["model_id"] for s in scored[1:]],
        "fallback_chain": [s["model_id"] for s in scored[1:max_chain]],
        "excluded": excluded,
        "decision_factors": scored,
        "review": review,
        "independent_review_required": review["required"],
        "human_approval_required": approval,
        "enforcement": "ADVISORY (not mechanically enforced; see module docstring)",
    })


def _log_decision(req: TaskRequirements, result: dict) -> None:
    """Bounded append-only JSONL (same atomic-trim pattern as cost-tracker.js).
    Concise decision metadata only; no reasoning dump."""
    try:
        _DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "task_class": req.task_class, "complexity": req.complexity, "risk": req.risk,
                 "selected": result.get("selected"), "fallback": result.get("fallback_chain", []),
                 "excluded": list(result.get("excluded", {}).keys()), "reason": result.get("reason")}
        lines: list[str] = []
        if _DECISION_LOG.exists():
            lines = [l for l in _DECISION_LOG.read_text(encoding="utf-8").split("\n") if l.strip()]
        lines.append(json.dumps(entry, ensure_ascii=False))
        if len(lines) > _DECISION_LOG_MAX_LINES:
            lines = lines[-int(_DECISION_LOG_MAX_LINES * 0.8):]
        tmp = _DECISION_LOG.with_suffix(f".tmp.{os.getpid()}")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(_DECISION_LOG)
    except Exception:
        pass  # fail-open: logging must never break routing


def _cli() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raw = sys.argv[1:]
    as_json = "--json" in raw

    def opt(name: str, default=None):
        if name in raw:
            i = raw.index(name)
            if i + 1 < len(raw):
                return raw[i + 1]
        return default

    task_text = opt("--task-text")
    task_class = opt("--task-class")
    derived: dict = {}
    if not task_class and task_text:
        c = classify_task_class(task_text)
        task_class = c["task_class"]
        derived["task_class"] = {"confidence": c["confidence"], "rationale": c["rationale"]}
    if not task_class:
        print('Usage: model_router.py --task-class <CLASS> | --task-text "..." [--complexity L] [--risk L] '
              '[--signals-json \'{"file_count":6}\'] [--context-tier T] [--latency-priority P] '
              '[--cost-policy P] [--json]', file=sys.stderr)
        sys.exit(1)

    try:
        signals = json.loads(opt("--signals-json", "{}") or "{}")
        complexity = opt("--complexity")
        if complexity is None:
            complexity, factors = estimate_complexity(signals) if signals else ("MEDIUM", ["default (no signals given)"])
            derived["complexity"] = factors
        risk = opt("--risk")
        if risk is None:
            risk, factors = estimate_risk(task_text or "", signals) if task_text else ("LOW", ["default (no text given)"])
            derived["risk"] = factors
        req = TaskRequirements(
            task_class=task_class, complexity=complexity, risk=risk,
            context_tier=opt("--context-tier", "UNKNOWN"), latency_priority=opt("--latency-priority", "normal"),
            quality_priority=opt("--quality-priority", "normal"), cost_policy=opt("--cost-policy", "CONFIGURED_ONLY"),
            coding_required="--coding-required" in raw, reasoning_required="--reasoning-required" in raw,
        )
    except (ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    result = route(req, log_decision="--no-log" not in raw)
    if as_json:
        print(json.dumps({"requirements": asdict(req), "derived": derived, **result},
                         ensure_ascii=False, indent=2, default=str))
    else:
        print("=" * 64)
        print("ATLAS Model Router V1 (dry-run, ADVISORY -- not enforced)")
        print("=" * 64)
        print(f"TASK_CLASS: {req.task_class}   COMPLEXITY: {req.complexity}   RISK: {req.risk}")
        print(f"SELECTED: {result['selected'] or '(none)'}")
        print(f"REASON: {result['reason']}")
        print(f"ALTERNATIVES: {result['alternatives'] or '-'}   FALLBACK_CHAIN: {result['fallback_chain'] or '-'}")
        if result["excluded"]:
            print(f"EXCLUDED: {result['excluded']}")
        if result.get("review", {}).get("required") or result.get("review", {}).get("recommended"):
            print(f"REVIEW: {result['review']}")
        if result.get("human_approval_required"):
            print("HUMAN_APPROVAL_REQUIRED: True")
    sys.exit(0 if result["selected"] else 3)


if __name__ == "__main__":
    _cli()
