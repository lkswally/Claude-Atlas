#!/usr/bin/env python3
"""
Bloque F43 -- Routed execution with provider fallback (roadmap P6)
=============================================================================

Gap: two real providers exist, but nothing recovered from a provider failing. This suite injects every failure
the spec names (timeout, quota, rate limit, auth failure, missing model, both providers unavailable, malformed
response, policy block) through fake providers and a synthetic registry, and checks three things:
  1. the right transition (retry the same model / fall back / stop / report WAITING or NO_ELIGIBLE),
  2. that HARD CONSTRAINTS are re-applied to every fallback candidate (a tempting fallback is never taken when
     risk, tools, context or cost forbid it),
  3. that the loop is bounded (no auth retry loop, no unbounded attempts, nothing sleeps).
`--live` runs the real scenario: the HOST reports Claude failed -> ATLAS executes the task through Codex.
"""
import ast
import copy
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.providers import (  # noqa: E402
    ModelProvider, ProviderCapability, ProviderExecutionResult, ProviderHealth, build_providers,
)
from tools import model_router as mr  # noqa: E402
from tools import provider_fallback as pf  # noqa: E402
from tools.model_router import TaskRequirements  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
A, B, H = "alpha/m", "beta/m", "host/m"


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def ok(text="done"):
    return lambda req: ProviderExecutionResult(req.request_id, req.model_id.split("/")[0], req.model_id, True, "NONE", text)


def fail(klass, hint=None, detail="injected"):
    return lambda req: ProviderExecutionResult(req.request_id, req.model_id.split("/")[0], req.model_id, False, klass, "", detail, 0.0, hint)


class Fake(ModelProvider):
    def __init__(self, pid, model, *results, health="UNKNOWN", executable=True, probe_state=None):
        self.id, self._model, self._exec = pid, model, executable
        self.results = list(results) or [ok()]
        self.exec_calls, self.probes, self._health, self._probe_state = 0, 0, health, probe_state

    def models(self):
        return [self._model]

    def capabilities(self, mid):
        if mid != self._model:
            return None
        return ProviderCapability(self.id, mid, True, None, "large", "UNKNOWN", ("coding",), "configured_free", self._exec)

    def health(self, model_id=None):
        return ProviderHealth(self._health, "fake", "fake")

    def execute(self, req):
        self.exec_calls += 1
        item = self.results[min(self.exec_calls - 1, len(self.results) - 1)]
        return item(req)

    def probe(self, model_id=None, timeout_s=60.0):
        self.probes += 1
        self._health = self._probe_state or "UNKNOWN"
        return self.health(model_id)


def model(pid, strengths, tools, ctx, risks, cost="configured_free", assume=True):
    return {"provider": pid, "enabled": True, "strengths": strengths, "supports_tools": tools, "supports_multimodal": "UNKNOWN",
            "context_tier": ctx, "latency_tier": "UNKNOWN", "cost_tier": cost, "eligible_risks": risks, "assume_available_if_unknown": assume}


def registry(**over):
    reg = copy.deepcopy(mr.load_registry())
    reg["providers"] = {"alpha": {"enabled": True}, "beta": {"enabled": True}, "host": {"enabled": True}}
    reg["models"] = {
        A: model("alpha", ["coding", "analysis", "reasoning"], True, "large", ["low", "medium", "high", "critical"]),
        B: model("beta", ["coding", "analysis"], False, "medium", ["low", "medium"]),
    }
    for k, v in over.items():
        reg["models"][k] = v
    return reg


def req(**kw):
    kw.setdefault("task_class", "CODE")
    kw.setdefault("complexity", "HIGH")
    kw.setdefault("risk", "LOW")
    return TaskRequirements(**kw)


def run(a, b, reg=None, r=None, **kw):
    provs = {"alpha": a, "beta": b}
    provs.update(kw.pop("extra", {}))
    return pf.execute_routed(r or req(), "do the thing", provs, registry=reg or registry(), **kw)


def sig(res):
    return [(x["model"], x["error_class"], x["action"]) for x in res["attempts"]]


# --------------------------------------------------------------------------- A. setup sanity + happy path
def test_basics():
    base = mr.route(req(), registry(), log_decision=False)
    check("01 setup: alpha outranks beta (the scenarios below rely on this order)", base["selected"] == A and base["alternatives"][:1] == [B])
    a, b = Fake("alpha", A, ok("alpha says hi")), Fake("beta", B)
    res = run(a, b)
    check("02 happy path: primary executes, no fallback, one attempt",
          res["state"] == "SUCCEEDED" and res["executed_model"] == A and res["fallback_used"] is False and res["text"] == "alpha says hi"
          and len(res["attempts"]) == 1 and b.exec_calls == 0)
    need = {"state", "reason", "selected", "executed_model", "provider", "fallback_used", "provider_health", "alternatives", "text", "handoff", "attempts", "blockers"}
    check("03 the result carries selected / fallback_used / reason / provider_health / alternatives (+ attempts)", need <= set(res), str(sorted(need - set(res))))
    r1, r2 = run(Fake("alpha", A, fail("TIMEOUT", "TIMEOUT"), fail("TIMEOUT", "TIMEOUT")), Fake("beta", B)), run(Fake("alpha", A, fail("TIMEOUT", "TIMEOUT"), fail("TIMEOUT", "TIMEOUT")), Fake("beta", B))
    check("04 deterministic: the same inputs produce the same attempt sequence", sig(r1) == sig(r2) and r1["state"] == r2["state"])


# --------------------------------------------------------------------------- B. the failure matrix
def test_failures():
    a, b = Fake("alpha", A, fail("TIMEOUT", "TIMEOUT"), ok("recovered")), Fake("beta", B)
    res = run(a, b)
    check("05 TIMEOUT: one same-model retry, success on the retry, NOT counted as a fallback",
          res["state"] == "SUCCEEDED" and res["executed_model"] == A and res["fallback_used"] is False and sig(res) == [(A, "TIMEOUT", "RETRY"), (A, "NONE", "SUCCESS")] and b.exec_calls == 0)
    a, b = Fake("alpha", A, fail("TIMEOUT", "TIMEOUT")), Fake("beta", B, ok("from beta"))
    res = run(a, b)
    check("06 TIMEOUT twice: retry once, then fall back to the next provider", res["executed_model"] == B and res["fallback_used"] is True
          and sig(res) == [(A, "TIMEOUT", "RETRY"), (A, "TIMEOUT", "FALLBACK"), (B, "NONE", "SUCCESS")] and a.exec_calls == 2)
    a, b = Fake("alpha", A, fail("TIMEOUT", "TIMEOUT")), Fake("beta", B)
    res = run(a, b, idempotent=False)
    check("07 TIMEOUT on a NON-idempotent request is never retried (could duplicate side effects): straight to fallback",
          a.exec_calls == 1 and res["executed_model"] == B)
    for klass, hint, label in (("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED", "08 QUOTA_EXHAUSTED"), ("RATE_LIMITED", "RATE_LIMITED", "09 RATE_LIMITED"),
                               ("MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE", "10 model missing (MODEL_UNAVAILABLE)")):
        a, b = Fake("alpha", A, fail(klass, hint)), Fake("beta", B, ok("from beta"))
        res = run(a, b)
        check(f"{label}: immediate fallback, the failed provider is not retried",
              a.exec_calls == 1 and res["executed_model"] == B and res["fallback_used"] and sig(res)[0] == (A, klass, "FALLBACK"))
    a, b = Fake("alpha", A, fail("AUTH_FAILED", "AUTH_FAILED")), Fake("beta", B, ok("from beta"))
    res = run(a, b)
    check("11 AUTH_FAILED: exactly one attempt on the failing provider (no retry loop), then fallback", a.exec_calls == 1 and res["executed_model"] == B)
    a = Fake("alpha", A, fail("AUTH_FAILED", "AUTH_FAILED"))
    reg = registry()
    del reg["models"][B]
    res = run(a, Fake("beta", B), reg=reg)
    check("12 AUTH_FAILED with nobody else eligible: NO_ELIGIBLE_PROVIDER (persistent), still one attempt, no loop",
          res["state"] == "NO_ELIGIBLE_PROVIDER" and a.exec_calls == 1, res["reason"][:90])
    a, b = Fake("alpha", A, fail("INVALID_RESPONSE", "DEGRADED")), Fake("beta", B, ok("from beta"))
    res = run(a, b)
    check("13 malformed response: one bounded retry, then fallback", sig(res)[:2] == [(A, "INVALID_RESPONSE", "RETRY"), (A, "INVALID_RESPONSE", "FALLBACK")] and res["executed_model"] == B)
    a, b = Fake("alpha", A, fail("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")), Fake("beta", B, fail("RATE_LIMITED", "RATE_LIMITED"))
    t0 = time.perf_counter()
    res = run(a, b)
    check("14 both providers unavailable but only transiently -> WAITING_PROVIDER, returned immediately (nothing sleeps)",
          res["state"] == "WAITING_PROVIDER" and a.exec_calls == 1 and b.exec_calls == 1 and time.perf_counter() - t0 < 1.0 and set(res["blockers"]) == {A, B})
    a, b = Fake("alpha", A, fail("AUTH_FAILED", "AUTH_FAILED")), Fake("beta", B, fail("MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE"))
    res = run(a, b)
    check("15 both persistently unavailable (auth / model missing) -> NO_ELIGIBLE_PROVIDER, not WAITING", res["state"] == "NO_ELIGIBLE_PROVIDER")
    a, b = Fake("alpha", A, fail("POLICY_BLOCKED")), Fake("beta", B, ok("must not run"))
    res = run(a, b)
    check("16 POLICY_BLOCKED stops: no fallback (it would send the blocked prompt to another vendor)",
          res["state"] == "POLICY_BLOCKED" and b.exec_calls == 0 and a.exec_calls == 1)
    a, b = Fake("alpha", A, fail("INVALID_RESPONSE", "DEGRADED")), Fake("beta", B, fail("INVALID_RESPONSE", "DEGRADED"))
    res = run(a, b, policy={"max_attempts": 3})
    check("17 the loop is bounded: with always-failing providers total executions never exceed max_attempts", a.exec_calls + b.exec_calls <= 3 and res["state"] != "SUCCEEDED")
    ghost = lambda *a, **k: {"selected": "ghost/m", "provider": "ghost", "alternatives": [], "fallback_chain": [], "excluded": {}}
    t0 = time.perf_counter()
    res = pf.execute_routed(req(), "x", {"alpha": Fake("alpha", A)}, registry=registry(), router=ghost)
    check("17b the loop terminates even if the router keeps returning a model nobody can run (no adapter): FAILED, not a hang",
          res["state"] == "FAILED" and time.perf_counter() - t0 < 2.0, f"state={res['state']}")


# --------------------------------------------------------------------------- C. hard constraints survive fallback
def test_hard_constraints():
    def case(label, reg, r, **kw):
        a, b = Fake("alpha", A, fail("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")), Fake("beta", B, ok("MUST NOT RUN"))
        res = run(a, b, reg=reg, r=r, **kw)
        check(label, b.exec_calls == 0 and res["executed_model"] is None and res["state"] in ("WAITING_PROVIDER", "NO_ELIGIBLE_PROVIDER"),
              f"state={res['state']} beta calls={b.exec_calls}")
    case("18 NEGATIVE: HIGH risk -- beta is a tempting fallback but outside its eligible_risks, so it is never run", registry(), req(risk="HIGH"))
    case("19 NEGATIVE: the task needs tools -- beta has none, so it is never run", registry(), req(tool_requirements=["bash"]))
    case("20 NEGATIVE: large context required -- beta's context tier is insufficient, so it is never run", registry(), req(context_tier="large"))
    reg = registry()
    reg["models"][B]["cost_tier"] = "paid_per_token"
    case("21 NEGATIVE: cost policy CONFIGURED_ONLY -- a paid fallback is never run", reg, req())
    res = run(Fake("alpha", A), Fake("beta", B), r=req(risk="CRITICAL"), reg=(lambda g: (g["models"][A].__setitem__("eligible_risks", ["low"]), g)[1])(registry()))
    check("22 nothing satisfies the constraints from the start -> NO_ELIGIBLE_PROVIDER with the reasons, zero executions",
          res["state"] == "NO_ELIGIBLE_PROVIDER" and not res["attempts"] and "eligible_risks" in res["reason"], res["reason"][:100])
    a, b = Fake("alpha", A, fail("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")), Fake("beta", B, ok("ok"))
    res = run(a, b, r=req(risk="HIGH"))
    check("23 the same HIGH-risk request reports WAITING (alpha satisfies it but is out of quota), not a downgrade to beta", res["state"] == "WAITING_PROVIDER" and res["blockers"].get(A) == "QUOTA_EXHAUSTED")


# --------------------------------------------------------------------------- D. provider health is a real input
def test_health_input():
    a, b = Fake("alpha", A, health="RATE_LIMITED"), Fake("beta", B, ok("from beta"))
    res = run(a, b)
    check("24 a provider that REPORTS RATE_LIMITED is skipped without being called", a.exec_calls == 0 and res["executed_model"] == B)
    a, b = Fake("alpha", A, fail("TIMEOUT", "TIMEOUT")), Fake("beta", B, health="AUTH_FAILED")
    res = run(a, b)
    check("25 NEGATIVE: a provider that reports AUTH_FAILED is never chosen as the fallback", b.exec_calls == 0 and res["executed_model"] is None)
    reg = registry()
    for m in (A, B):
        reg["models"][m]["assume_available_if_unknown"] = False
    a, b = Fake("alpha", A, ok("probed ok"), probe_state="AVAILABLE"), Fake("beta", B)
    res = run(a, b, reg=reg)
    check("26 UNKNOWN health + a probe-capable invocable provider: probed once, then executed", a.probes == 1 and res["state"] == "SUCCEEDED" and res["executed_model"] == A)
    a, b = Fake("alpha", A, ok()), Fake("beta", B)
    res = run(a, b, reg=reg, probe_unknown=False)
    check("27 NEGATIVE: UNKNOWN health with no assume policy and probing off -> nothing is run", a.exec_calls == 0 and res["state"] == "NO_ELIGIBLE_PROVIDER" and res["executed_model"] is None)


# --------------------------------------------------------------------------- E. host-managed models and host-reported failures
def test_host():
    hm = model("host", ["coding", "analysis", "reasoning", "tool_use"], True, "large", ["low", "medium", "high", "critical"])
    reg = registry(**{H: hm})
    reg["models"][A]["strengths"] = ["coding"]                       # make the host model the clear favourite
    reg["models"][B]["strengths"] = ["coding"]
    a, b, h = Fake("alpha", A), Fake("beta", B), Fake("host", H, executable=False)
    res = run(a, b, reg=reg, extra={"host": h})
    check("28 the best model is host-managed -> HANDOFF (ATLAS does not pretend to run it), nothing executed",
          res["state"] == "HANDOFF" and res["handoff"]["model"] == H and h.exec_calls == 0 and a.exec_calls == 0)
    res = run(Fake("alpha", A, ok("by alpha")), Fake("beta", B), reg=reg, extra={"host": Fake("host", H, executable=False)}, require_executable=True)
    check("29 require_executable skips host-managed models and runs an invocable one", res["state"] == "SUCCEEDED" and res["executed_model"] in (A, B))
    a, b = Fake("alpha", A, ok("rescued by alpha")), Fake("beta", B)
    res = run(a, b, reg=reg, extra={"host": Fake("host", H, executable=False)}, known_failures={H: "You've hit your usage limit"})
    check("30 the HOST reports its model hit a usage limit -> ATLAS re-routes and executes elsewhere; it is a fallback",
          res["state"] == "SUCCEEDED" and res["executed_model"] == A and res["fallback_used"] is True and res["provider_health"].get(H) == "QUOTA_EXHAUSTED")
    res = run(Fake("alpha", A), Fake("beta", B), reg=reg, extra={"host": Fake("host", H, executable=False)},
              known_failures={H: "usage limit", A: "429 Too Many Requests", B: "rate limit"})
    check("31 every candidate already failed -> WAITING_PROVIDER (transient), nothing is executed", res["state"] == "WAITING_PROVIDER" and not res["attempts"])
    reg2 = registry()
    del reg2["models"][B]
    res = run(Fake("alpha", A), Fake("beta", B), reg=reg2, known_failures={A: "Not logged in"})
    check("32 a host-reported AUTH failure on the only eligible model -> NO_ELIGIBLE_PROVIDER (persistent)", res["state"] == "NO_ELIGIBLE_PROVIDER")
    res = pf.execute_routed(req(), "x", {"alpha": Fake("alpha", A, ok("by alpha"))}, registry=registry())      # beta has no adapter at all
    check("33 a model whose provider has no adapter is treated as unavailable: the healthy one still runs",
          res["state"] == "SUCCEEDED" and res["executed_model"] == A and res["provider_health"].get(B) == "MODEL_UNAVAILABLE")
    res = pf.execute_routed(req(), "x", {"alpha": Fake("alpha", A, fail("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED"))}, registry=registry())
    check("33b ... and it is never a fallback target when the only adapter fails: WAITING_PROVIDER, beta never attempted",
          res["state"] == "WAITING_PROVIDER" and [x["model"] for x in res["attempts"]] == [A])


# --------------------------------------------------------------------------- F. source guards
def test_source():
    src = (PROJECT_ROOT / "tools" / "provider_fallback.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported, calls = set(), []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {x.name.split(".")[0] for x in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            imported.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f"{f.value.id}.{f.attr}" if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else "")
            if name in ("eval", "exec", "os.system", "time.sleep", "__import__"):
                calls.append(name)
    check("34 the executor never sleeps or polls and has no process/network capability", not calls and not (imported & {"time", "subprocess", "socket", "urllib", "requests", "threading"}),
          f"imports={sorted(imported)} calls={calls}")


# --------------------------------------------------------------------------- G. live (opt-in)
def test_live():
    print("\n-- LIVE (real Codex; the HOST reports Claude failed -> ATLAS runs the task on Codex) --")
    reg = mr.load_registry()
    provs, _ = build_providers(reg)
    res = pf.execute_routed(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW"), "Reply with exactly the word PONG and nothing else.",
                            provs, registry=reg, require_executable=True, timeout_s=90,
                            known_failures={"anthropic/sonnet": "You've hit your usage limit", "anthropic/opus": "You've hit your usage limit"})
    check("L1 real fallback: Claude models reported out of quota -> executed on openai/codex-cli, fallback_used, answer PONG",
          res["state"] == "SUCCEEDED" and res["executed_model"] == "openai/codex-cli" and res["fallback_used"] and "PONG" in (res["text"] or "").upper(),
          f"state={res['state']} model={res['executed_model']} attempts={[(x['model'], x['action']) for x in res['attempts']]}")
    res = pf.execute_routed(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="HIGH"), "Reply with PONG.", provs, registry=reg, require_executable=True,
                            timeout_s=90, known_failures={"anthropic/sonnet": "usage limit", "anthropic/opus": "usage limit"})
    check("L2 real constraint: the same outage on a HIGH-risk task does NOT fall back to Codex (outside its eligible_risks) -> WAITING_PROVIDER",
          res["state"] == "WAITING_PROVIDER" and not res["attempts"], f"state={res['state']}")


def main():
    live = "--live" in sys.argv
    print("=" * 60)
    print("Bloque F43 -- Routed execution with provider fallback" + (" [LIVE]" if live else ""))
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_basics, test_failures, test_hard_constraints, test_health_input, test_host, test_source):
        print(f"\n-- {fn.__name__} --")
        fn()
    if live:
        test_live()
    else:
        print("\n(live cases skipped: pass --live to run the real Codex fallback)")
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
