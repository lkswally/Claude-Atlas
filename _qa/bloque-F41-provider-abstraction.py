#!/usr/bin/env python3
"""
Bloque F41 -- Model provider abstraction (core/providers)
=============================================================================

Gap (roadmap P4): model choice was welded to one vendor path. Before any second provider can exist, ATLAS needs
a provider boundary that (a) normalizes health / capability / execution, (b) cannot be fooled by a misbehaving
provider (hang, exception, malformed answer), and (c) represents the CURRENT Anthropic/Claude Code path honestly:
host-managed, health UNKNOWN, execute() not invocable from ATLAS.

Fake providers exercise every guard; the real config exercises the compatibility adapter. No process is spawned
and no network is touched.
"""
import sys
import time
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.providers import (  # noqa: E402
    AnthropicHostProvider, ModelProvider, ProviderCapability, ProviderExecutionRequest, ProviderExecutionResult,
    ProviderHealth, build_providers, classify_failure, invoke, provider_id_of, safe_health,
)
from core.providers import base as pbase  # noqa: E402
from tools import model_router as mr  # noqa: E402
from tools.model_router import TaskRequirements, route  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
SONNET, OPUS = "anthropic/sonnet", "anthropic/opus"


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


class StatusError(Exception):
    def __init__(self, msg, status_code):
        super().__init__(msg)
        self.status_code = status_code


class Fake(ModelProvider):
    id = "fake"

    def __init__(self, behavior="ok", delay=0.0):
        self.behavior, self.delay = behavior, delay
        self.executed = 0
        self.cancelled = []

    def models(self):
        if self.behavior == "models_raises":
            raise RuntimeError("models() blew up")
        return ["fake/m"]

    def capabilities(self, model_id):
        return None

    def health(self, model_id=None):
        return ProviderHealth("AVAILABLE", "probe ok", "probe")

    def cancel(self, request_id):
        self.cancelled.append(request_id)
        return True

    def execute(self, req):
        self.executed += 1
        b = self.behavior
        ok = ProviderExecutionResult(req.request_id, "fake", req.model_id, True, "NONE", "hello")
        if b == "ok":
            return ok
        if b == "sleep":
            time.sleep(self.delay)
            return ok
        if b == "raise_timeout":
            raise TimeoutError("socket timed out")
        if b == "raise_429":
            raise StatusError("slow down", 429)
        if b == "raise_generic":
            raise RuntimeError("boom")
        if b == "none":
            return None
        if b == "dict":
            return {"ok": True}
        if b == "wrong_request":
            return ProviderExecutionResult("someone-else", "fake", req.model_id, True, "NONE", "x")
        if b == "wrong_provider":
            return ProviderExecutionResult(req.request_id, "other", req.model_id, True, "NONE", "x")
        if b == "ok_with_error":
            return ProviderExecutionResult(req.request_id, "fake", req.model_id, True, "TIMEOUT", "x")
        if b == "fail_without_class":
            return ProviderExecutionResult(req.request_id, "fake", req.model_id, False, "NONE", "")
        if b == "bad_hint":
            return ProviderExecutionResult(req.request_id, "fake", req.model_id, True, "NONE", "x", "", 0.0, "BOGUS_STATE")
        if b == "bad_error_class":
            return ProviderExecutionResult(req.request_id, "fake", req.model_id, False, "WEIRD", "")
        return ok


def req(model="fake/m", timeout=5.0, rid="r1"):
    return ProviderExecutionRequest(rid, model, "ping", timeout_s=timeout)


# --------------------------------------------------------------------------- A. vocabulary and router
def test_vocabulary():
    check("01 provider and router health vocabularies are identical (drift guard)", tuple(pbase.HEALTH_STATES) == tuple(mr.HEALTH_STATES))
    check("02 the full required state set is present", set(pbase.HEALTH_STATES) == {
        "AVAILABLE", "DEGRADED", "RATE_LIMITED", "QUOTA_EXHAUSTED", "AUTH_FAILED", "MODEL_UNAVAILABLE", "TIMEOUT", "UNKNOWN"})
    cfg = {"assume_available_if_unknown": True}
    check("03 the router accepts every provider health state as valid (none degrades to INVALID_HEALTH_STATE)",
          all(mr.resolve_health(SONNET, cfg, {SONNET: s}) == s for s in pbase.HEALTH_STATES))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW"), health_overrides={SONNET: "TIMEOUT"}, log_decision=False)
    check("04 a TIMEOUT model is excluded from routing (unservable), the other model still routes",
          SONNET in r["excluded"] and r["selected"] == OPUS, f"selected={r['selected']}")


# --------------------------------------------------------------------------- B. failure classification
def test_classification():
    table = [
        (dict(status_code=429), ("RATE_LIMITED", "RATE_LIMITED")),
        (dict(status_code=402), ("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")),
        (dict(status_code=401), ("AUTH_FAILED", "AUTH_FAILED")),
        (dict(status_code=403), ("AUTH_FAILED", "AUTH_FAILED")),
        (dict(status_code=404), ("MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE")),
        (dict(status_code=408), ("TIMEOUT", "TIMEOUT")),
        (dict(status_code=529), ("DEGRADED", "PROVIDER_ERROR")),
        (dict(message="Not logged in · Please run /login"), ("AUTH_FAILED", "AUTH_FAILED")),        # the real R0 output
        (dict(message="You have reached your usage limit"), ("QUOTA_EXHAUSTED", "QUOTA_EXHAUSTED")),
        (dict(message="Rate limit exceeded, retry later"), ("RATE_LIMITED", "RATE_LIMITED")),
        (dict(message="model not found: claude-x"), ("MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE")),
        (dict(message="request timed out after 30s"), ("TIMEOUT", "TIMEOUT")),
        (dict(message="overloaded_error: Overloaded"), ("DEGRADED", "PROVIDER_ERROR")),
        (dict(message="something nobody has ever seen"), ("UNKNOWN", "PROVIDER_ERROR")),
        (dict(), ("UNKNOWN", "PROVIDER_ERROR")),
    ]
    bad = [(k, classify_failure(**k), v) for k, v in table if classify_failure(**k) != v]
    check("05 failure table: statuses and real-world messages map to the right health/error class", not bad, str(bad[:2]))
    check("06 NEGATIVE: nothing unrecognized ever maps to AVAILABLE",
          all(classify_failure(message=m)[0] != "AVAILABLE" for m in ("", "ok", "fine", "unknown thing", "\x00")))
    check("07 a structured status wins over misleading text (401 + 'rate limit' stays AUTH_FAILED)",
          classify_failure(status_code=401, message="rate limit")[0] == "AUTH_FAILED")
    check("08 exceptions classify: TimeoutError -> TIMEOUT; status_code attribute is honored",
          classify_failure(exc=TimeoutError("x")) == ("TIMEOUT", "TIMEOUT") and classify_failure(exc=StatusError("m", 429))[0] == "RATE_LIMITED")
    try:
        ok = classify_failure(message=None, status_code="429") == ("UNKNOWN", "PROVIDER_ERROR")        # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        ok = False
    check("09 non-string message / non-int status never raise", ok)


# --------------------------------------------------------------------------- C. capability mapping
def test_capabilities():
    reg = mr.load_registry()
    providers, skipped = build_providers(reg)
    p = providers.get("anthropic")
    check("10 the real config builds exactly the anthropic host adapter and skips nothing", isinstance(p, AnthropicHostProvider) and skipped == [])
    enabled = [m for m, c in reg["models"].items() if c.get("enabled") and c.get("provider") == "anthropic"]
    check("11 models() equals the router's enabled anthropic models, in config order", p.models() == enabled and p.models() == [SONNET, OPUS])
    cs, co = p.capabilities(SONNET), p.capabilities(OPUS)
    check("12 capabilities carry provider/model ids and the verified fields",
          cs.provider_id == "anthropic" and cs.model_id == SONNET and cs.supports_tools is True
          and cs.strengths == tuple(reg["models"][SONNET]["strengths"]) and co.strengths == tuple(reg["models"][OPUS]["strengths"]))
    check("13 UNKNOWN stays UNKNOWN: unverified multimodal is None (not False), context/latency are 'UNKNOWN'",
          cs.supports_multimodal is None and cs.context_tier == "UNKNOWN" and cs.latency_tier == "UNKNOWN")
    check("14 the host-managed adapter says it cannot be invoked from ATLAS", cs.executable_from_atlas is False and co.executable_from_atlas is False)
    check("15 every router registry field maps 1:1 for every model (compatibility)",
          all(p.capabilities(m).cost_tier == reg["models"][m]["cost_tier"] and p.capabilities(m).supports_tools == reg["models"][m]["supports_tools"]
              for m in p.models()))
    check("16 provider_id_of() asks the registry, not the id string", provider_id_of(reg, SONNET) == "anthropic" and provider_id_of(reg, "nope/x") is None)

    syn = {"providers": {"anthropic": {"enabled": True}, "off": {"enabled": False}, "noflag": {}},
           "models": {"anthropic/a": {"provider": "anthropic", "enabled": True, "context_tier": "large", "supports_multimodal": True, "supports_tools": False},
                      "anthropic/disabled": {"provider": "anthropic", "enabled": False},
                      "off/x": {"provider": "off", "enabled": True},
                      "other/y": {"provider": "other", "enabled": True},
                      "anthropic/b": "not a dict"}}
    a = AnthropicHostProvider(syn, "anthropic")
    check("17 only enabled models of an enabled provider are listed (disabled, foreign, malformed excluded)", a.models() == ["anthropic/a"])
    ca = a.capabilities("anthropic/a")
    check("18 explicit config values are preserved (large context, multimodal True, tools False)",
          ca.context_tier == "large" and ca.supports_multimodal is True and ca.supports_tools is False)
    check("19 a disabled or flagless provider is fail-closed: no models, no capabilities",
          AnthropicHostProvider(syn, "off").models() == [] and AnthropicHostProvider(syn, "noflag").models() == []
          and AnthropicHostProvider(syn, "off").capabilities("off/x") is None)
    try:
        junk = [AnthropicHostProvider(x, "anthropic").models() for x in ({}, {"providers": None, "models": None}, {"providers": {"anthropic": 5}, "models": []})]
        ok = junk == [[], [], []]
    except Exception:  # noqa: BLE001
        ok = False
    check("20 garbage registry shapes never raise and yield no models", ok)
    extra = dict(reg, providers=dict(reg["providers"], codex={"enabled": True}))
    pp, sk = build_providers(extra)
    check("21 a provider named in config without a verified adapter is skipped, never instantiated", sk == ["codex"] and "codex" not in pp)


# --------------------------------------------------------------------------- D. honest health and execution
def test_host_honesty():
    reg = mr.load_registry()
    p = build_providers(reg)[0]["anthropic"]
    check("22 config says assume_available_if_unknown, yet the provider reports UNKNOWN (configured != available)",
          reg["models"][SONNET]["assume_available_if_unknown"] is True and p.health(SONNET).state == "UNKNOWN" and p.health().state == "UNKNOWN")
    check("23 the health source is named honestly", p.health().source == "host_session" and "no health" in p.health().reason)
    check("24 health for a model it does not serve is MODEL_UNAVAILABLE", p.health("codex/x").state == "MODEL_UNAVAILABLE")
    check("25 NEGATIVE: no health value of the host adapter is AVAILABLE", all(p.health(m).state != "AVAILABLE" for m in (None, SONNET, OPUS, "x/y")))
    r = p.execute(req(SONNET))
    check("26 execute() reports NOT_EXECUTABLE (ok=False) instead of pretending to run a model", r.ok is False and r.error_class == "NOT_EXECUTABLE")
    g = invoke(p, req(SONNET))
    check("27 through invoke(): same honest answer, no exception", g.ok is False and g.error_class == "NOT_EXECUTABLE" and g.provider_id == "anthropic")
    check("28 an unknown model fails with MODEL_UNAVAILABLE and unknown capabilities are None",
          invoke(p, req("codex/x")).error_class == "MODEL_UNAVAILABLE" and p.capabilities("codex/x") is None)
    check("29 status() describes a non-invocable host-managed provider", p.status()["executable_from_atlas"] is False and p.status()["kind"] == "host_managed")
    check("30 the router's decision is unchanged by the abstraction (selection for CODE/HIGH/MEDIUM)",
          route(TaskRequirements(task_class="CODE", complexity="HIGH", risk="MEDIUM"), log_decision=False)["selected"] in (SONNET, OPUS))


# --------------------------------------------------------------------------- E. the guard
def test_invoke_guard():
    f = Fake("ok")
    r = invoke(f, req())
    check("31 well-formed result passes through with measured latency", r.ok and r.text == "hello" and r.latency_ms >= 0 and f.executed == 1)
    f = Fake("ok")
    r = invoke(f, req("fake/other"))
    check("32 an unserved model never reaches execute()", r.error_class == "MODEL_UNAVAILABLE" and f.executed == 0)
    f = Fake("sleep", delay=2.5)
    t0 = time.perf_counter()
    r = invoke(f, req(timeout=0.2))
    dt = time.perf_counter() - t0
    check("33 a hanging provider is cut off at its timeout and reported as TIMEOUT", r.error_class == "TIMEOUT" and r.health_hint == "TIMEOUT" and dt < 1.5, f"{dt:.2f}s")
    check("34 the timed-out request is cancelled best-effort", f.cancelled == ["r1"])
    for beh, klass in (("raise_timeout", "TIMEOUT"), ("raise_429", "RATE_LIMITED"), ("raise_generic", "PROVIDER_ERROR")):
        try:
            r = invoke(Fake(beh), req())
            ok = (r.ok is False and r.error_class == klass)
        except Exception:  # noqa: BLE001
            ok = False
        check(f"35 provider exception '{beh}' is contained and classified as {klass}", ok)
    bad = {}
    for beh in ("none", "dict", "wrong_request", "wrong_provider", "ok_with_error", "fail_without_class", "bad_hint", "bad_error_class"):
        r = invoke(Fake(beh), req())
        bad[beh] = r.error_class
    check("36 every malformed answer (None, dict, wrong id, wrong provider, contradictory flags, bad hint/class) is INVALID_RESPONSE",
          set(bad.values()) == {"INVALID_RESPONSE"}, str(bad))
    r = invoke(Fake("models_raises"), req())
    check("37 an adapter whose models() raises is reported as PROVIDER_ERROR, not propagated", r.ok is False and r.error_class == "PROVIDER_ERROR")

    class Raises(Fake):
        def health(self, model_id=None):
            raise RuntimeError("probe died")

    class Garbage(Fake):
        def health(self, model_id=None):
            return "AVAILABLE"

    class BadState(Fake):
        def health(self, model_id=None):
            return ProviderHealth("TOTALLY_FINE", "x", "probe")

    check("38 safe_health: a raising health() degrades to UNKNOWN", safe_health(Raises()).state == "UNKNOWN")
    check("39 safe_health: a non-ProviderHealth answer degrades to UNKNOWN", safe_health(Garbage()).state == "UNKNOWN")
    check("40 safe_health: an unknown state degrades to UNKNOWN (never trusted)", safe_health(BadState()).state == "UNKNOWN")
    check("41 safe_health: a valid answer passes through", safe_health(Fake()).state == "AVAILABLE")


# --------------------------------------------------------------------------- F. separation of concerns
def test_boundaries():
    def names(cls):
        return {f.name for f in fields(cls)}
    leak = [(c.__name__, n) for c in (ProviderExecutionRequest, ProviderExecutionResult, ProviderCapability, ProviderHealth)
            for n in names(c) if n in ("role", "agent", "runtime", "agent_role")]
    check("42 provider types carry no agent role / runtime field (the four dimensions stay separate)", not leak, str(leak))
    try:
        ModelProvider()  # type: ignore[abstract]
        abstract = False
    except TypeError:
        abstract = True
    check("43 ModelProvider is abstract: an adapter must implement health/models/capabilities/execute", abstract)
    import ast
    import re
    imported, calls = set(), []
    # Every provider file is held to the strict no-process/no-network rule EXCEPT codex_cli.py, the one adapter
    # that must spawn a process; F42 (#47-49) holds it to its own, narrower allow-list.
    strict = sorted(p.name for p in (PROJECT_ROOT / "core" / "providers").glob("*.py") if p.name != "codex_cli.py")
    for n in strict:
        text = (PROJECT_ROOT / "core" / "providers" / n).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):                       # real imports and calls only -- never prose in docstrings
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (f"{fn.value.id}.{fn.attr}" if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) else "")
                if name in ("eval", "exec", "os.system", "os.popen", "compile", "__import__"):
                    calls.append(name)
        if re.search(r"shell\s*=\s*True", text.replace('"""', "")) and "shell=True" in "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("#", '"'))):
            calls.append("shell=True")
    banned_imports = {"subprocess", "socket", "urllib", "requests", "http", "ssl", "pickle", "ctypes"}
    check("44 the provider package imports nothing process / network / pickle related and calls no eval/exec/system",
          not (imported & banned_imports) and not calls, f"imports={sorted(imported & banned_imports)} calls={calls}")
    check("45 no reverse dependency: core/providers never imports tools/ or the Model Router",
          "tools" not in imported and "model_router" not in imported)


def main():
    print("=" * 60)
    print("Bloque F41 -- Model provider abstraction")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_vocabulary, test_classification, test_capabilities, test_host_honesty, test_invoke_guard, test_boundaries):
        print(f"\n-- {fn.__name__} --")
        fn()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
