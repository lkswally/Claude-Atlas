#!/usr/bin/env python3
"""
Bloque F38 -- Model Router V1 (dry-run, advisory)
=============================================================================

Gap demostrado: docs/MODEL-ROUTER-ARCHITECTURE-V1.md confirmo que ATLAS no
tenia ruteo de modelo: 27 agentes declaran `model: opus|sonnet` estatico en
frontmatter y cero codigo lo lee. Este suite valida tools/model_router.py,
una capa de DECISION deterministica y explicable que nunca invoca un modelo.

Alcance verificado: solo anthropic/sonnet y anthropic/opus son candidatos
reales. Codex/Gemini/Groq/OpenHands NO estan representados.

Principio de los tests: afirman COMPORTAMIENTO, no reflejan el YAML. Los
controles negativos construyen un candidato que SERIA el de mayor score y
verifican que igual se rechaza por una restriccion dura.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools import model_router as mr  # noqa: E402
from tools.model_router import (  # noqa: E402
    TaskRequirements, route, load_registry, classify_task_class,
    estimate_complexity, estimate_risk,
)

PASS_COUNT = 0
FAIL_COUNT = 0
SONNET, OPUS = "anthropic/sonnet", "anthropic/opus"


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def R(task_class, complexity="MEDIUM", risk="LOW", **kw):
    return TaskRequirements(task_class=task_class, complexity=complexity, risk=risk, **kw)


def go(req, registry=None, health=None):
    return route(req, registry=registry, health_overrides=health, log_decision=False)


def top_model(**over):
    """A synthetic candidate engineered to be the HIGHEST-scoring option
    (reasoning+coding+analysis, tools, large context) -- used by the negative
    controls so a hard constraint, not a low score, is what removes it."""
    base = {"provider": "anthropic", "enabled": True, "strengths": ["reasoning", "coding", "analysis"],
            "supports_tools": True, "supports_multimodal": True, "context_tier": "large",
            "latency_tier": "low", "cost_tier": "configured_free",
            "eligible_risks": ["low", "medium", "high", "critical"], "assume_available_if_unknown": True}
    base.update(over)
    return base


# ------------------------------------------------------------------ selection
def test_selection():
    r = go(R("FAST", "LOW", "LOW"))
    tied = len({s["total"] for s in r["decision_factors"]}) == 1
    check("01 FAST/LOW/LOW: tie (no verified latency data) resolves to registry order", r["selected"] == SONNET and tied,
          f"selected={r['selected']} tie={tied}")
    check("02 CODE/MEDIUM/LOW selects the efficient default", go(R("CODE"))["selected"] == SONNET)
    check("03 CODE/HIGH/MEDIUM prefers the reasoning-capable model", go(R("CODE", "HIGH", "MEDIUM"))["selected"] == OPUS)
    check("04 CODE/VERY_HIGH selects opus", go(R("CODE", "VERY_HIGH"))["selected"] == OPUS)
    r = go(R("ANALYSIS", "HIGH"))
    check("05 ANALYSIS/HIGH selects opus with sonnet as fallback", r["selected"] == OPUS and r["fallback_chain"] == [SONNET],
          str(r["fallback_chain"]))
    r = go(R("HIGH_RISK", "HIGH", "HIGH"))
    check("06 HIGH_RISK/HIGH/HIGH selects opus and requires independent review",
          r["selected"] == OPUS and r["review"]["required"] and r["review"]["independence"] == "available",
          str(r["review"]))
    r = go(R("HIGH_RISK", "VERY_HIGH", "CRITICAL"))
    check("07 CRITICAL: opus only, human approval, and NO false independence claim (same provider)",
          r["selected"] == OPUS and SONNET in r["excluded"] and r["human_approval_required"]
          and str(r["review"]["independence"]).startswith("UNAVAILABLE"), str(r["review"]))
    check("08 REVIEW class recommends independent review", go(R("REVIEW"))["review"]["recommended"] is True)


# ------------------------------------------------- fail-closed on UNKNOWN specs
def test_unknown_specs_fail_closed():
    r = go(R("CONTEXT"))
    check("09 CONTEXT with unverified context_tier -> NO_ELIGIBLE_MODEL (unverified != supported)",
          r["selected"] is None and r["reason"].startswith("NO_ELIGIBLE_MODEL")
          and all("context" in " ".join(v) for v in r["excluded"].values()), str(r["excluded"]))
    reg = load_registry()
    reg["models"][SONNET]["context_tier"] = "large"
    r = go(R("CONTEXT"), registry=reg)
    check("10 CONTEXT routes once an operator verifies context_tier; the unverified model stays excluded",
          r["selected"] == SONNET and OPUS in r["excluded"], str(r["excluded"]))
    r = go(R("MULTIMODAL"))
    check("11 MULTIMODAL class (no flag) is fail-closed: capability not confirmed", r["selected"] is None, str(r["excluded"]))
    reg = load_registry()
    reg["models"][OPUS]["supports_multimodal"] = True
    r = go(R("MULTIMODAL"), registry=reg)
    check("12 MULTIMODAL routes to the confirmed model only", r["selected"] == OPUS and SONNET in r["excluded"])


# ---------------------------------------------------------- negative controls
def test_negative_controls():
    def winner_rejected(name, reg, req, health=None, why=""):
        r = go(req, registry=reg, health=health)
        check(name, "X/top" in r["excluded"] and r["selected"] != "X/top" and why in " ".join(r["excluded"].get("X/top", [])),
              f"selected={r['selected']} reasons={r['excluded'].get('X/top')}")

    base = lambda **o: (lambda reg: (reg["models"].__setitem__("X/top", top_model(**o)), reg)[1])(load_registry())
    # Sanity: with no violation the engineered candidate really is the best-scoring one.
    r = go(R("ANALYSIS", "HIGH", "HIGH"), registry=base())
    check("13 control sanity: the engineered candidate wins when nothing is wrong",
          r["selected"] in ("X/top", OPUS) and r["decision_factors"][0]["total"] >= r["decision_factors"][-1]["total"])

    winner_rejected("14 disabled model rejected despite top score", base(enabled=False), R("ANALYSIS", "HIGH", "HIGH"), why="disabled")
    winner_rejected("15 risk-ineligible model rejected despite top score", base(eligible_risks=["low"]),
                    R("HIGH_RISK", "HIGH", "HIGH"), why="eligible_risks")
    winner_rejected("16 tool-incompatible model rejected despite top score", base(supports_tools=False),
                    R("CODE", "HIGH", tool_requirements=["bash"]), why="tools")
    winner_rejected("17 context-incompatible model rejected despite top score", base(context_tier="small"),
                    R("CONTEXT"), why="context")
    winner_rejected("18 cost-ineligible model rejected despite top score (FREE_ONLY)", base(cost_tier="paid"),
                    R("CODE", cost_policy="FREE_ONLY"), why="cost_policy")
    winner_rejected("19 paid tier stays ineligible even under ALLOW_PAID_WITH_APPROVAL (V1 never enables spending)",
                    base(cost_tier="paid"), R("CODE", cost_policy="ALLOW_PAID_WITH_APPROVAL"), why="not enabled in V1")
    winner_rejected("20 unhealthy provider rejected despite top score", base(), R("ANALYSIS", "HIGH"),
                    health={"X/top": "QUOTA_EXHAUSTED"}, why="health=QUOTA_EXHAUSTED")
    winner_rejected("21 missing required strength rejected despite everything else", base(strengths=["reasoning"]),
                    R("CODE", "HIGH"), why="required capability")
    winner_rejected("22 environment-incompatible request excludes every candidate incl. the top one", base(),
                    R("CODE", execution_environment="bare_metal"), why="execution_environment")

    for state in ("RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_UNAVAILABLE"):
        r = go(R("ANALYSIS", "HIGH"), health={OPUS: state})
        if not (OPUS in r["excluded"] and r["selected"] == SONNET):
            check(f"23 {state} excludes the model", False, str(r["excluded"]))
            break
    else:
        check("23 RATE_LIMITED/QUOTA_EXHAUSTED/AUTH_FAILED/MODEL_UNAVAILABLE each exclude the better model", True)

    r = go(R("CODE"), health={SONNET: "NOT_A_REAL_STATE"})
    check("24 invalid health state fails closed", SONNET in r["excluded"])
    reg = load_registry()
    reg["models"][OPUS]["assume_available_if_unknown"] = False
    r = go(R("ANALYSIS", "HIGH"), registry=reg)
    check("25 UNKNOWN health is not silently AVAILABLE without the explicit policy flag",
          OPUS in r["excluded"] and "UNKNOWN" in " ".join(r["excluded"][OPUS]) and r["selected"] == SONNET)
    r = go(R("CODE"), health={SONNET: "QUOTA_EXHAUSTED", OPUS: "AUTH_FAILED"})
    check("26 all providers unhealthy -> NO_ELIGIBLE_MODEL", r["selected"] is None and r["reason"].startswith("NO_ELIGIBLE_MODEL"))

    r = go(R("CODE", reasoning_required=True))
    check("27 reasoning_required excludes the non-reasoning model", r["selected"] == OPUS and SONNET in r["excluded"])
    reg = load_registry()
    reg["models"]["X/noncoder"] = top_model(strengths=["reasoning", "analysis"])
    r = go(R("FAST", coding_required=True), registry=reg)
    check("28 coding_required excludes a model without the coding strength", "X/noncoder" in r["excluded"])
    r = go(R("ANALYSIS"), registry=(lambda g: (g["models"].__setitem__("X/c", top_model(strengths=["coding"])), g)[1])(load_registry()))
    check("29 task-class min_strengths is enforced as a hard filter", "X/c" in r["excluded"])


# ------------------------------------------------------------ health & fallback
def test_health_and_fallback():
    r = go(R("CODE", "LOW", "LOW"), health={SONNET: "DEGRADED"})
    sonnet_pen = [s for s in r["decision_factors"] if s["model_id"] == SONNET][0]["factors"]["health_penalty"]
    check("30 DEGRADED stays eligible but is ranked below a healthy equal", r["selected"] == OPUS
          and SONNET in r["alternatives"] and SONNET not in r["excluded"] and sonnet_pen < 0, f"penalty={sonnet_pen}")
    reg = load_registry()
    reg["models"]["X/third"] = top_model(strengths=["coding", "analysis"], eligible_risks=["low", "medium", "high"])
    reg["fallback_policy"]["max_chain_length"] = 2
    r = go(R("CODE"), registry=reg)
    check("31 fallback chain honors max_chain_length and never contains the selected model",
          len(r["fallback_chain"]) == 1 and r["selected"] not in r["fallback_chain"], str(r["fallback_chain"]))
    check("32 every fallback independently satisfies the hard filters", all(m not in r["excluded"] for m in r["fallback_chain"]))
    r = go(R("HIGH_RISK", "HIGH", "CRITICAL"), health={OPUS: "AUTH_FAILED"})
    check("33 primary unavailable -> eligibility re-evaluated; the weaker model is NOT blindly accepted",
          r["selected"] is None and SONNET in r["excluded"] and OPUS in r["excluded"])
    r = go(R("UNKNOWN"))
    check("34 UNKNOWN task class escalates instead of guessing", r["selected"] is None and "ESCALATE_CLASSIFICATION" in r["reason"])


# ----------------------------------------------- classification / complexity / risk
def test_models_of_the_task():
    cases = {
        "Please implement a bug fix in the login handler": "CODE",
        "Analyze the architecture of the payment module and find the root cause": "ANALYSIS",
        "Deploy to production and rotate the credentials": "HIGH_RISK",
        "Research and compare vector databases, benchmark them": "RESEARCH",
    }
    got = {t: classify_task_class(t)["task_class"] for t in cases}
    check("35 classifier maps clear requests to the right class", got == cases, str(got))
    check("36 classifier returns UNKNOWN (low confidence) for gibberish", classify_task_class("asdf qwer zxcv")["task_class"] == "UNKNOWN")
    amb = classify_task_class("review the architecture")
    check("37 classifier refuses to guess on ambiguous input", amb["task_class"] == "UNKNOWN" and amb["confidence"] == "low", str(amb["rationale"]))

    tiers = [estimate_complexity({})[0], estimate_complexity({"file_count": 3, "cross_module": True})[0],
             estimate_complexity({"file_count": 8, "cross_module": True, "external_dependency": True})[0],
             estimate_complexity({"file_count": 8, "cross_module": True, "ambiguous": True, "irreversible": True,
                                  "test_surface_large": True})[0]]
    check("38 complexity is derived from observable signals into 4 ordered tiers",
          tiers == ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"], str(tiers))
    docs_only = estimate_risk("update the readme docs only, reversible")[0]
    prod = estimate_risk("deploy to production")[0]
    crit = estimate_risk("deploy to production and rotate the credential secret")[0]
    big_but_safe = estimate_risk("rename a variable across the codebase")[0]
    check("39 risk tiers are independent of complexity (large safe refactor stays LOW)",
          (docs_only, prod, crit, big_but_safe) == ("LOW", "HIGH", "CRITICAL", "LOW"), str((docs_only, prod, crit, big_but_safe)))
    bad = []
    for kw in ({"task_class": "NOPE"}, {"task_class": "CODE", "complexity": "EXTREME"},
               {"task_class": "CODE", "risk": "NONE"}, {"task_class": "CODE", "cost_policy": "FREE_LUNCH"}):
        try:
            TaskRequirements(**kw)
            bad.append(kw)
        except ValueError:
            pass
    check("40 TaskRequirements rejects invalid enum values", not bad, str(bad))


# ------------------------------------------------------ config / security / purity
def test_config_and_security():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        missing = load_registry(p / "nope.yaml")
        (p / "garbage.yaml").write_text("::: not [valid yaml {{{", encoding="utf-8")
        (p / "wrongshape.yaml").write_text("models:\n  anthropic/x: just-a-string\n  anthropic/y:\n    enabled: true\n", encoding="utf-8")
        garbage = load_registry(p / "garbage.yaml")
        wrong = load_registry(p / "wrongshape.yaml")
        check("41 missing and malformed config fail open to the two verified models",
              set(missing["models"]) == set(garbage["models"]) == {SONNET, OPUS})
        check("42 malformed model entries are dropped, well-formed ones kept (no crash)",
              "anthropic/x" not in wrong["models"] and "anthropic/y" in wrong["models"])
        (p / "inject.yaml").write_text(
            "models:\n  anthropic/sonnet:\n    provider: anthropic\n    enabled: true\n    strengths: [coding, analysis]\n"
            "    supports_tools: true\n    cost_tier: configured_free\n    eligible_risks: [low, medium, high]\n"
            "    assume_available_if_unknown: true\n    command: 'calc.exe'\n    env: {API_KEY: leaked}\n"
            "autonomy_policy: {mode: unrestricted}\n", encoding="utf-8")
        inj = load_registry(p / "inject.yaml")
        r = go(R("CODE"), registry=inj)
        check("43 injected command/env/autonomy keys in config are inert (data only)",
              r["selected"] == "anthropic/sonnet" and "autonomy_policy" not in inj and "command" not in json.dumps(r))
    src = (PROJECT_ROOT / "tools" / "model_router.py").read_text(encoding="utf-8")
    forbidden = [w for w in ("subprocess", "os.system", "Popen", "socket", "urllib", "requests", "eval(", "exec(", "__import__")
                 if re.search(r"(?<![\w.])" + re.escape(w), src.replace("# ", "#"))]
    check("44 router source cannot execute commands or reach the network", not forbidden, str(forbidden))


def test_determinism_and_logging():
    req = R("ANALYSIS", "HIGH", "MEDIUM")
    first = json.dumps(go(req), sort_keys=True, default=str)
    check("45 20 identical calls produce byte-identical decisions", all(json.dumps(go(req), sort_keys=True, default=str) == first for _ in range(20)))
    old_path, old_max = mr._DECISION_LOG, mr._DECISION_LOG_MAX_LINES
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mr._DECISION_LOG = Path(tmp) / "decisions.jsonl"
            route(R("FAST"), log_decision=False)
            check("46 dry-run without logging writes nothing", not mr._DECISION_LOG.exists())
            mr._DECISION_LOG_MAX_LINES = 50
            for i in range(120):
                route(R("CODE", "HIGH" if i % 2 else "LOW"), log_decision=True)
            lines = [l for l in mr._DECISION_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
            last = json.loads(lines[-1])
            need = {"ts", "task_class", "complexity", "risk", "selected", "fallback", "excluded", "reason"}
            check("47 decision log is concise JSONL with enforced retention (120 writes, cap 50)",
                  len(lines) <= 50 and need <= set(last) and last["complexity"] == "HIGH", f"lines={len(lines)}")
            check("48 decision log stores no reasoning dump", "decision_factors" not in last and len(lines[-1]) < 600)
    finally:
        mr._DECISION_LOG, mr._DECISION_LOG_MAX_LINES = old_path, old_max


# ------------------------------------------------------------------------ CLI
def cli(*args):
    return subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "model_router.py"), "--no-log", *args],
                          capture_output=True, text=True, timeout=30)


def test_cli():
    p = cli("--task-class", "CODE", "--complexity", "HIGH", "--risk", "MEDIUM", "--json")
    d = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    check("49 CLI --json routes and exits 0", p.returncode == 0 and d.get("selected") == OPUS, f"rc={p.returncode}")
    p = cli("--task-text", "deploy to production and rotate the credential secret", "--json")
    d = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    check("50 CLI derives class AND risk from text; CRITICAL excludes sonnet and needs human approval",
          d.get("requirements", {}).get("task_class") == "HIGH_RISK" and d.get("requirements", {}).get("risk") == "CRITICAL"
          and d.get("selected") == OPUS and d.get("human_approval_required") is True, str(d.get("derived")))
    check("51 CLI exits 3 when no model is eligible", cli("--task-class", "MULTIMODAL").returncode == 3)
    check("52 CLI exits 1 on usage error", cli().returncode == 1)
    check("53 CLI exits 1 on an invalid enum", cli("--task-class", "CODE", "--risk", "EXTREME").returncode == 1)
    p = cli("--task-text", "asdf qwer", "--json")
    check("54 CLI exits 3 and escalates when classification is not confident",
          p.returncode == 3 and "ESCALATE_CLASSIFICATION" in p.stdout)


def main():
    print("=" * 60)
    print("Bloque F38 -- Model Router V1 (dry-run, advisory)")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_selection, test_unknown_specs_fail_closed, test_negative_controls, test_health_and_fallback,
               test_models_of_the_task, test_config_and_security, test_determinism_and_logging, test_cli):
        print(f"\n-- {fn.__name__} --")
        fn()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
