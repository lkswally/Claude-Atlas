#!/usr/bin/env python3
"""
Bloque F44 -- Reviewer independence (roadmap P7)
=============================================================================

Gap: role separation exists, but "independent review" was a label. Same model + same context + same assumptions
would pass as independent. This suite checks that the level is computed from FACTS (models, registry-derived
providers, a fresh-context flag), that a claim can never exceed the facts, that an unreachable requirement is
reported as DEGRADED instead of being quietly accepted, and that a silent self-review at HIGH/CRITICAL risk
always needs a human gate.

Offline; no model or process is run (the plan says who should review, it does not run the review).
"""
import ast
import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools import model_router as mr  # noqa: E402
from tools import review_independence as ri  # noqa: E402
from tools.model_router import TaskRequirements  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
SONNET, OPUS, CODEX, GAMMA = "anthropic/sonnet", "anthropic/opus", "openai/codex-cli", "gamma/x"


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def req(risk, **kw):
    return TaskRequirements(task_class="CODE", complexity=kw.pop("complexity", "MEDIUM"), risk=risk, **kw)


def rec(im, rm, ip=None, rp=None, reused=False, claimed=None):
    return {"implementation_model": im, "implementation_provider": ip, "review_model": rm, "review_provider": rp,
            "context_reused": reused, "independence_level": claimed}


def with_gamma(risks=("low", "medium", "high", "critical")):
    reg = copy.deepcopy(mr.load_registry())
    reg["providers"]["gamma"] = {"enabled": True}
    reg["models"][GAMMA] = {"provider": "gamma", "enabled": True, "strengths": ["coding", "analysis", "reasoning"], "supports_tools": True,
                            "supports_multimodal": "UNKNOWN", "context_tier": "large", "latency_tier": "UNKNOWN", "cost_tier": "configured_free",
                            "eligible_risks": list(risks), "assume_available_if_unknown": True}
    return reg


# --------------------------------------------------------------------------- A. levels from facts
def test_levels():
    c = ri.classify_independence
    check("01 same model, fresh context -> CONTEXT_INDEPENDENT", c(rec(SONNET, SONNET, "anthropic", "anthropic")) == "CONTEXT_INDEPENDENT")
    check("02 same model, reused context -> ROLE_ONLY", c(rec(SONNET, SONNET, "anthropic", "anthropic", reused=True)) == "ROLE_ONLY")
    check("03 different model, same provider, fresh context -> MODEL_INDEPENDENT", c(rec(SONNET, OPUS, "anthropic", "anthropic")) == "MODEL_INDEPENDENT")
    check("04 NEGATIVE: a different model that was handed the implementer's context is only ROLE_ONLY", c(rec(SONNET, OPUS, "anthropic", "anthropic", reused=True)) == "ROLE_ONLY")
    check("05 different provider, fresh context -> PROVIDER_INDEPENDENT", c(rec(SONNET, CODEX, "anthropic", "openai")) == "PROVIDER_INDEPENDENT")
    check("06 NEGATIVE: a different provider with a reused context is only ROLE_ONLY", c(rec(SONNET, CODEX, "anthropic", "openai", reused=True)) == "ROLE_ONLY")
    check("07 unknown context (missing / None) fails closed to ROLE_ONLY",
          c({"implementation_model": SONNET, "review_model": OPUS}) == "ROLE_ONLY" and c(rec(SONNET, OPUS, reused=None)) == "ROLE_ONLY")
    check("08 missing or blank models fail closed to ROLE_ONLY", c({}) == "ROLE_ONLY" and c(rec(SONNET, "  ")) == "ROLE_ONLY" and c(rec(None, OPUS)) == "ROLE_ONLY")
    check("09 models differ but providers are unknown -> MODEL_INDEPENDENT (provider independence needs both providers known)",
          c(rec(SONNET, OPUS)) == "MODEL_INDEPENDENT")
    check("10 levels are ordered weakest to strongest", ri.LEVELS == ("ROLE_ONLY", "CONTEXT_INDEPENDENT", "MODEL_INDEPENDENT", "PROVIDER_INDEPENDENT"))
    pol = mr.load_registry().get("review_policy", {})
    check("11 drift guard: this policy agrees with config review_policy (HIGH needs a model, CRITICAL a provider + human approval)",
          pol["HIGH"]["dimension"] == "model" and ri.POLICY["HIGH"]["required"] == "MODEL_INDEPENDENT"
          and pol["CRITICAL"]["dimension"] == "model_and_provider" and ri.POLICY["CRITICAL"]["required"] == "PROVIDER_INDEPENDENT"
          and pol["CRITICAL"]["human_approval"] is True and ri.POLICY["CRITICAL"]["human_gate"] is True
          and pol["LOW"]["independent_required"] is False and ri.POLICY["LOW"]["required"] == "ROLE_ONLY")


# --------------------------------------------------------------------------- B. policy by risk (real registry)
def test_plans():
    p = ri.plan_review(req("LOW"), SONNET)
    check("12 LOW: normal QA role is enough; nothing degraded, no gate, no fresh context demanded",
          p["required_level"] == "ROLE_ONLY" and not p["degraded"] and not p["human_gate_required"] and p["fresh_context_required"] is False)
    p = ri.plan_review(req("MEDIUM"), SONNET)
    check("13 MEDIUM: a fresh context is required and reached", p["required_level"] == "CONTEXT_INDEPENDENT" and p["fresh_context_required"]
          and not p["degraded"] and ri.LEVELS.index(p["achieved_level"]) >= 1 and p["record_template"]["context_reused"] is False)
    for impl, other in ((SONNET, OPUS), (OPUS, SONNET)):
        p = ri.plan_review(req("HIGH"), impl)
        check(f"14 HIGH: {impl.split('/')[1]} implements -> {other.split('/')[1]} reviews: MODEL_INDEPENDENT, not degraded",
              p["achieved_level"] == "MODEL_INDEPENDENT" and p["reviewer_model"] == other and not p["degraded"])
    p = ri.plan_review(req("HIGH"), SONNET, health_overrides={OPUS: "RATE_LIMITED"})
    check("15 HIGH, preferred reviewer unavailable: degrades EXPLICITLY to a fresh-context self-review, says why, never silent",
          p["achieved_level"] == "CONTEXT_INDEPENDENT" and p["degraded"] and "MODEL_INDEPENDENT" in p["reason"] and p["reviewer_model"] == SONNET
          and p["excluded"].get(OPUS), p["reason"][:90])
    p = ri.plan_review(req("HIGH"), SONNET, health_overrides={OPUS: "AUTH_FAILED", SONNET: "QUOTA_EXHAUSTED"})
    check("16 HIGH, nobody can review: no reviewer, degraded, and a HUMAN GATE (a silent self-review never passes)",
          p["reviewer_model"] is None and p["achieved_level"] is None and p["degraded"] and p["human_gate_required"] and p["silent_self_review_blocked"])
    p = ri.plan_review(req("CRITICAL"), OPUS)
    check("17 CRITICAL with today's fleet (only opus is eligible): degraded to CONTEXT_INDEPENDENT, explicit, with security review + human gate",
          p["achieved_level"] == "CONTEXT_INDEPENDENT" and p["degraded"] and p["security_review_required"] and p["human_gate_required"]
          and "different provider" in p["reason"], p["reason"][:100])


# --------------------------------------------------------------------------- C. a second provider changes the outcome
def test_second_provider():
    reg = with_gamma()
    p = ri.plan_review(req("CRITICAL"), OPUS, reg)
    check("18 CRITICAL with an eligible second provider: PROVIDER_INDEPENDENT reached, not degraded (human gate + security review still required)",
          p["achieved_level"] == "PROVIDER_INDEPENDENT" and p["reviewer_model"] == GAMMA and not p["degraded"] and p["human_gate_required"] and p["security_review_required"])
    p = ri.plan_review(req("CRITICAL"), OPUS, reg, health_overrides={GAMMA: "AUTH_FAILED"})
    check("19 CRITICAL, second provider unavailable: degrades (not silently) and does not pick the unhealthy provider",
          p["degraded"] and p["reviewer_model"] != GAMMA and p["achieved_level"] != "PROVIDER_INDEPENDENT" and GAMMA in p["excluded"])
    p = ri.plan_review(req("CRITICAL"), OPUS, with_gamma(risks=("low", "medium")))
    check("20 NEGATIVE: a provider that is not eligible at CRITICAL risk is never chosen as reviewer, however independent it would be",
          p["reviewer_model"] != GAMMA and p["degraded"])
    p = ri.plan_review(req("MEDIUM"), SONNET, health_overrides={CODEX: "AVAILABLE"})
    check("21 real registry: with Codex reported AVAILABLE, a MEDIUM review of Claude's work is PROVIDER_INDEPENDENT (exceeds the requirement)",
          p["reviewer_model"] == CODEX and p["achieved_level"] == "PROVIDER_INDEPENDENT" and not p["degraded"])
    p = ri.plan_review(req("HIGH"), SONNET, health_overrides={CODEX: "AVAILABLE"})
    check("22 ... but at HIGH risk Codex is outside its eligible_risks, so the reviewer is a Claude model (MODEL_INDEPENDENT)",
          p["reviewer_model"] == OPUS and CODEX in p["excluded"] and p["achieved_level"] == "MODEL_INDEPENDENT")
    p = ri.plan_review(req("MEDIUM"), SONNET)
    check("23 without a health signal Codex is not assumed available: the reviewer stays within the Claude models", p["reviewer_model"] in (SONNET, OPUS))
    a, b = ri.plan_review(req("HIGH"), SONNET), ri.plan_review(req("HIGH"), SONNET)
    check("24 deterministic: identical inputs give an identical plan", a == b)
    from types import SimpleNamespace
    stub = SimpleNamespace(risk="EXTREME", complexity="MEDIUM", execution_environment="claude_code", cost_policy="CONFIGURED_ONLY")   # bypasses TaskRequirements' own validation
    try:
        p = ri.plan_review(stub, OPUS)
        ok = p["required_level"] == "PROVIDER_INDEPENDENT" and p["risk"] == "CRITICAL" and p["human_gate_required"] and p["degraded"]
    except Exception as e:  # noqa: BLE001
        ok, p = False, {"reason": f"raised {type(e).__name__}"}
    check("25 an unrecognized risk is treated as CRITICAL (policy AND routing), never raises, and still needs the human gate", ok, str(p.get("reason"))[:80])


# --------------------------------------------------------------------------- D. verifying records
def test_records():
    v = ri.verify_review_record(rec(SONNET, SONNET, "anthropic", "anthropic", claimed="MODEL_INDEPENDENT"), "HIGH")
    check("26 NEGATIVE (same model selected by accident): claims MODEL_INDEPENDENT, the facts say CONTEXT_INDEPENDENT -> over-claim, fails HIGH",
          v["overclaimed"] and v["verified_level"] == "CONTEXT_INDEPENDENT" and not v["meets_policy"])
    v = ri.verify_review_record(rec(SONNET, CODEX, "anthropic", "openai", reused=True, claimed="PROVIDER_INDEPENDENT"), "MEDIUM")
    check("27 NEGATIVE (clean-context requirement): a different provider that reused the context cannot claim independence",
          v["overclaimed"] and v["verified_level"] == "ROLE_ONLY" and not v["meets_policy"])
    v = ri.verify_review_record(rec(SONNET, OPUS, "anthropic", "openai", claimed="PROVIDER_INDEPENDENT"), "CRITICAL")
    check("28 NEGATIVE: a record cannot invent a provider -- the registry says opus is anthropic, so it is only MODEL_INDEPENDENT",
          v["verified_level"] == "MODEL_INDEPENDENT" and v["overclaimed"] and any("contradicts the registry" in x for x in v["problems"]) and not v["meets_policy"])
    v = ri.verify_review_record(rec(SONNET, CODEX, "anthropic", "openai", claimed="PROVIDER_INDEPENDENT"), "HIGH")
    check("29 an honest PROVIDER_INDEPENDENT record verifies and meets HIGH", v["verified_level"] == "PROVIDER_INDEPENDENT" and not v["overclaimed"] and v["meets_policy"] and not v["problems"])
    v = ri.verify_review_record(rec(SONNET, SONNET, "anthropic", "anthropic", claimed="CONTEXT_INDEPENDENT"), "HIGH")
    check("30 an honest but insufficient record is not over-claimed yet does NOT meet the policy", not v["overclaimed"] and not v["meets_policy"])
    v = ri.verify_review_record({"review_model": OPUS}, "LOW")
    check("31 missing fields are reported", sum("missing field" in x for x in v["problems"]) >= 4 and not v["meets_policy"])
    v = ri.verify_review_record(rec("ghost/m", OPUS, claimed="MODEL_INDEPENDENT"), "HIGH")
    check("32 a model that is not in the registry is flagged", any("not in the registry" in x for x in v["problems"]) and not v["meets_policy"])
    v = ri.verify_review_record(rec(SONNET, OPUS, "anthropic", "anthropic", claimed="SUPERB"), "HIGH")
    check("33 an invalid independence_level value is flagged", any("not one of" in x for x in v["problems"]) and not v["meets_policy"])
    ok = True
    for risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        for impl in (SONNET, OPUS):
            plan = ri.plan_review(req(risk), impl, health_overrides={CODEX: "AVAILABLE"})
            if plan["reviewer_model"] is None:
                continue
            verified = ri.verify_review_record(plan["record_template"], risk)
            ok = ok and (not verified["overclaimed"]) and verified["verified_level"] == plan["achieved_level"] and not verified["problems"]
    check("34 round trip: the record the planner hands out always verifies with the same level (planner and verifier cannot disagree)", ok)


# --------------------------------------------------------------------------- E. source guard
def test_source():
    tree = ast.parse((PROJECT_ROOT / "tools" / "review_independence.py").read_text(encoding="utf-8"))
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {x.name.split(".")[0] for x in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            imported.add(n.module.split(".")[0])
    check("35 no process, network, sleep or file capability: it only reasons over the registry",
          not (imported & {"subprocess", "socket", "urllib", "requests", "time", "threading", "os", "shutil", "tempfile"}), str(sorted(imported)))


def main():
    print("=" * 60)
    print("Bloque F44 -- Reviewer independence")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_levels, test_plans, test_second_provider, test_records, test_source):
        print(f"\n-- {fn.__name__} --")
        fn()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
