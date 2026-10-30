#!/usr/bin/env python3
"""
Bloque F45 -- Failure-injection campaign (roadmap P16)
=============================================================================

Expectations were pre-registered in docs/FAILURE-INJECTION-CAMPAIGN.md section 2 BEFORE any scenario ran. This suite
injects the failures at real boundaries -- a fake `codex` and a fake `engram` that run as real subprocesses through the
real runners (timeouts, process-tree kill, stdin, env scrubbing), unwritable and torn files, killed writers -- and judges
every scenario against the same eight rules:

  R1 detected   R2 no false success   R3 bounded   R4 unsafe fallback rejected
  R5 evidence   R6 retries per policy (no loop, none dropped)   R7 security active   R8 cost active

A scenario passes only if EVERY applicable rule holds. A rule that cannot apply to a scenario is reported as NA, never
silently counted as passed. `--report FILE` writes the per-scenario rule table as JSON.
"""
import contextlib
import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from core.providers import (  # noqa: E402
    AnthropicHostProvider, CodexCliProvider, ModelProvider, ProviderCapability, ProviderExecutionRequest, ProviderExecutionResult,
    ProviderHealth, invoke,
)
from tools import model_router as mr  # noqa: E402
from tools import provider_fallback as pf  # noqa: E402
from tools import review_independence as ri  # noqa: E402
from tools.bounded_jsonl import BoundedJsonl  # noqa: E402
from tools.model_router import TaskRequirements  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
RECORDS = []
RULES = ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")
SONNET, OPUS, CODEX = "anthropic/sonnet", "anthropic/opus", "openai/codex-cli"
REG = mr.load_registry()
WORK = Path(tempfile.mkdtemp(prefix="atlas_f45_"))

T_LOW = TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW", coding_required=True)
T_HIGH = TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="HIGH", coding_required=True)
T_CRIT = TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="CRITICAL", coding_required=True)


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def judge(cid, label, rules, facts=None):
    """One scenario = one check: it passes only if no rule is False. None = the rule does not apply (reported)."""
    failed = [r for r in RULES if rules.get(r) is False]
    na = [r for r in RULES if rules.get(r) is None]
    RECORDS.append({"id": cid, "label": label, "rules": {r: rules.get(r) for r in RULES}, "facts": facts or {}})
    note = ("failed " + ",".join(failed)) if failed else ("all applicable rules hold" + (f" (NA: {','.join(na)})" if na else ""))
    check(f"{cid} {label}", not failed, note)


# --------------------------------------------------------------------------- fakes (real executables)
FAKE_CODEX = r'''
import json, os, subprocess, sys, time
def mode():
    try:
        return open(os.environ["FAKE_CODEX_MODE_FILE"]).read().strip() or "ok"
    except (KeyError, OSError):
        return "ok"
m = mode()
args = sys.argv[1:]
if args[:2] == ["login", "status"]:
    if m == "logged_out":
        print("Not logged in"); sys.exit(1)
    print("Logged in using ChatGPT"); sys.exit(0)
if os.environ.get("FAKE_CODEX_COUNT_FILE"):
    with open(os.environ["FAKE_CODEX_COUNT_FILE"], "a") as f:
        f.write("x\n")
sys.stdin.read()
def ev(**kw):
    print(json.dumps(kw), flush=True)
if m == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(40)"])
    with open(os.environ["FAKE_CODEX_PID_FILE"], "a") as f:
        f.write("%d\n%d\n" % (os.getpid(), child.pid))
    time.sleep(40); sys.exit(0)
if m == "rate_limit":
    ev(type="turn.failed", error={"message": json.dumps({"status": 429, "error": {"code": "rate_limit_exceeded"}})}); sys.exit(1)
if m == "quota":
    ev(type="turn.failed", error={"message": "You have hit your usage limit. Try again later."}); sys.exit(1)
if m == "auth":
    ev(type="turn.failed", error={"message": json.dumps({"status": 401, "error": {"code": "invalid_api_key"}})}); sys.exit(1)
if m == "model":
    ev(type="turn.failed", error={"message": json.dumps({"status": 400, "error": {"code": "model_not_found"}})}); sys.exit(1)
if m == "garbage":
    print("<<<not an event stream>>>"); sys.exit(0)
if m == "no_turn":
    ev(type="item.completed", item={"type": "agent_message", "text": "PONG"}); sys.exit(0)
if m == "empty":
    ev(type="turn.completed", usage={}); sys.exit(0)
if m == "crash":
    sys.exit(3)
ev(type="thread.started", thread_id="t")
ev(type="item.completed", item={"type": "agent_message", "text": "PONG"})
ev(type="turn.completed", usage={})
'''

FAKE_ENGRAM = r'''
import json, os, sys, time
def mode():
    try:
        return open(os.environ["FAKE_ENGRAM_MODE_FILE"]).read().strip() or "found"
    except (KeyError, OSError):
        return "found"
m = mode()
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
def text(t):
    return {"content": [{"type": "text", "text": json.dumps({"project": "p", "result": t})}], "isError": False}
if m == "exit":
    sys.exit(3)
if m == "hang":
    time.sleep(25); sys.exit(0)
for line in sys.stdin:
    try:
        req = json.loads(line)
    except ValueError:
        continue
    rid, meth = req.get("id"), req.get("method")
    if rid is None:
        continue
    if meth == "initialize":
        if m == "garbage":
            sys.stdout.write("this is not json\n"); sys.stdout.flush(); continue
        send({"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "fake"}}}); continue
    if meth == "tools/call":
        if m == "hang_after_init":
            time.sleep(25); sys.exit(0)
        if m == "dies_on_call":
            sys.exit(4)
        if m == "rpcerror":
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": "boom"}}); continue
        if m == "ambiguous":
            send({"jsonrpc": "2.0", "id": rid, "result": {"isError": True, "content": [{"type": "text", "text": json.dumps({"error_code": "ambiguous_project", "available_projects": ["a", "b"], "message": "ambiguous"})}]}}); continue
        if m == "wrongid":
            # a STALE answer to some other request, with a perfectly plausible payload: accepting it would be a false finding
            send({"jsonrpc": "2.0", "id": rid + 100, "result": text("Found 1 memories:\n[1] #33 (decision) - Title")}); continue
        if m == "notfound":
            send({"jsonrpc": "2.0", "id": rid, "result": text("No memories found for: x")}); continue
        if m == "weird_found":
            send({"jsonrpc": "2.0", "id": rid, "result": text("Memory not found for that topic")}); continue
        if req["params"]["name"] == "mem_get_observation":
            send({"jsonrpc": "2.0", "id": rid, "result": text("Full body of the observation")}); continue
        send({"jsonrpc": "2.0", "id": rid, "result": text("Found 1 memories:\n[1] #33 (decision) - Title")}); continue
'''

CODEX_SCRIPT = WORK / "fake_codex.py"
ENGRAM_DIR = WORK / "engram_cwd"
MODE_FILE, COUNT_FILE, PID_FILE = WORK / "codex.mode", WORK / "codex.count", WORK / "codex.pids"
ENGRAM_MODE = WORK / "engram.mode"


def write_fakes():
    for name, code in (("FAKE_CODEX", FAKE_CODEX), ("FAKE_ENGRAM", FAKE_ENGRAM)):
        compile(code, name, "exec")          # a broken fake would silently turn every "healthy" control into a timeout
    CODEX_SCRIPT.write_text(FAKE_CODEX, encoding="utf-8")
    ENGRAM_DIR.mkdir(exist_ok=True)
    # The bridge runs `<binary> mcp --tools=agent`. With the binary = this Python and the cwd = a directory that holds a
    # script named `mcp`, that is "python mcp --tools=agent": a real child process speaking JSON-RPC on stdio, with no
    # shell wrapper (so killing the bridge's process kills the whole fake).
    (ENGRAM_DIR / "mcp").write_text(FAKE_ENGRAM, encoding="utf-8")
    MODE_FILE.write_text("ok")
    COUNT_FILE.write_text("")
    PID_FILE.write_text("")


def set_mode(m):
    MODE_FILE.write_text(m)


def spawns():
    try:
        return len([l for l in COUNT_FILE.read_text().splitlines() if l.strip()])
    except OSError:
        return 0


def pids():
    try:
        return [int(x) for x in PID_FILE.read_text().split() if x.strip().isdigit()]
    except OSError:
        return []


def alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True).stdout or b""
        return f'"{pid}"'.encode() in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_dead(ps, seconds=6.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        left = [p for p in ps if alive(p)]
        if not left:
            return []
        time.sleep(0.25)
    return [p for p in ps if alive(p)]


def make_providers():
    env = dict(os.environ)
    env.update({"FAKE_CODEX_MODE_FILE": str(MODE_FILE), "FAKE_CODEX_COUNT_FILE": str(COUNT_FILE), "FAKE_CODEX_PID_FILE": str(PID_FILE)})
    codex = CodexCliProvider(REG, "openai", resolver=lambda: [sys.executable, str(CODEX_SCRIPT)], environ=env)
    host = AnthropicHostProvider(REG, "anthropic")
    set_mode("ok")
    codex.probe(CODEX, timeout_s=30)                     # healthy first: failures below happen to a provider that was fine
    return {"anthropic": host, "openai": codex}, codex


def model_cfg(model):
    return (REG.get("models") or {}).get(model) or {}


def eligible_for(model, risk):                          # independent of the router: read straight from the registry
    return risk.lower() in (model_cfg(model).get("eligible_risks") or [])


# --------------------------------------------------------------------------- shared probes (R7 / R8)
def security_probe(codex):
    """After a failure: the secret pre-filter still refuses before anything is spawned, and hard eligibility still
    excludes a model that is not eligible for HIGH risk even when every provider reports healthy."""
    base = spawns()
    secret = "gh" + "p_" + "a" * 36
    r = invoke(codex, ProviderExecutionRequest("sec", CODEX, f"deploy with {secret}", timeout_s=5))
    blocked = (not r.ok) and r.error_class == "POLICY_BLOCKED" and spawns() == base
    healthy = {m: "AVAILABLE" for m in REG["models"]}
    d = mr.route(T_HIGH, REG, health_overrides=healthy, log_decision=False)
    return bool(blocked and CODEX in d["excluded"] and d["selected"] != CODEX)


_HOOK = {}


def hook_still_blocks():
    """The block-no-verify hook still refuses a destructive command (real node process). None if node is absent."""
    if "v" not in _HOOK:
        if not shutil.which("node"):
            _HOOK["v"] = None
        else:
            payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}})
            p = subprocess.run(["node", str(PROJECT_ROOT / ".claude" / "hooks" / "block-no-verify.js")], input=payload,
                               capture_output=True, text=True, timeout=30)
            _HOOK["v"] = (p.returncode == 2)
    return _HOOK["v"]


# --------------------------------------------------------------------------- provider scenarios (FI-01 .. FI-08)
HOST_MSG = {"TIMEOUT": "request timed out", "RATE_LIMITED": 429, "QUOTA_EXHAUSTED": "You have reached your usage limit",
            "AUTH_FAILED": "Not logged in - please run /login", "MODEL_UNAVAILABLE": "model not found"}
HEALTH_FOR = {"TIMEOUT": "TIMEOUT", "RATE_LIMITED": "RATE_LIMITED", "QUOTA_EXHAUSTED": "QUOTA_EXHAUSTED",
              "AUTH_FAILED": "AUTH_FAILED", "MODEL_UNAVAILABLE": "MODEL_UNAVAILABLE"}


def provider_rules(req, res, *, n, elapsed, survivors, security_ok, expect_state, expect_class=None, host_down=None,
                   exact_spawns=None, max_spawns=2, expect_exec=None, expect_handoff=None, max_elapsed=40.0, codex_mode="ok"):
    """Pure judge for one provider scenario: result + physical facts in, the eight rules out."""
    attempts = res.get("attempts") or []
    used = {a["model"] for a in attempts} | ({res["executed_model"]} if res.get("executed_model") else set())         | ({res["handoff"]["model"]} if res.get("handoff") else set())
    rules = {}
    if host_down:                                                    # R1: the failure is visible, as the class it really is
        seen = res.get("provider_health") or {}
        rules["R1"] = all(seen.get(m) == HEALTH_FOR[host_down] for m in (SONNET, OPUS))
    elif expect_class:
        rules["R1"] = any(a.get("error_class") == expect_class for a in attempts)
    else:
        rules["R1"] = True
    if expect_state == "SUCCEEDED":                                  # R2: success only when the work really happened
        rules["R2"] = res["state"] == "SUCCEEDED" and "PONG" in (res.get("text") or "") and n >= 1
    else:
        rules["R2"] = res["state"] != "SUCCEEDED" and not res.get("text") and res.get("executed_model") is None
    rules["R3"] = n <= max_spawns and len(attempts) <= pf.DEFAULT_POLICY["max_attempts"] and elapsed < max_elapsed and not survivors
    rules["R4"] = all(eligible_for(m, req.risk) for m in used) and (expect_exec is None or res.get("executed_model") == expect_exec)         and (expect_handoff is None or (res.get("handoff") or {}).get("model") in expect_handoff)
    consistent = True                                                # R5: the evidence agrees with what physically happened
    for i, a in enumerate(attempts):
        if a.get("action") == "RETRY":
            nxt = attempts[i + 1] if i + 1 < len(attempts) else None
            consistent = consistent and bool(nxt and nxt["model"] == a["model"])      # a logged RETRY must have happened
    if codex_mode != "crash":
        consistent = consistent and len(attempts) == n                                # one attempt per physical spawn
    rules["R5"] = res["state"] == expect_state and consistent and bool(attempts or res.get("provider_health") or res.get("blockers"))
    rules["R6"] = (n == exact_spawns) if exact_spawns is not None else n <= max_spawns   # policy followed: no loop, no dropped retry
    rules["R7"] = bool(security_ok)
    rules["R8"] = all(model_cfg(m).get("cost_tier") == "configured_free" for m in used)
    return rules


def provider_case(cid, label, req, *, expect_state, expect_class=None, host_down=None, codex_mode="ok", require_executable=False,
                  exact_spawns=None, max_spawns=2, expect_exec=None, expect_handoff=None, timeout_s=3.0, max_elapsed=40.0, known=None):
    provs, codex = make_providers()
    set_mode(codex_mode)
    base, pbase = spawns(), len(pids())
    known_failures = dict(known or {})
    if host_down:
        for m in (SONNET, OPUS):
            known_failures[m] = HOST_MSG[host_down]
    t0 = time.perf_counter()
    res = pf.execute_routed(req, "Say PONG.", provs, registry=REG, require_executable=require_executable,
                            known_failures=known_failures or None, timeout_s=timeout_s, request_id=cid)
    elapsed = time.perf_counter() - t0
    n = spawns() - base
    survivors = wait_dead(pids()[pbase:]) if len(pids()) > pbase else []
    rules = provider_rules(req, res, n=n, elapsed=elapsed, survivors=survivors, security_ok=security_probe(codex), expect_state=expect_state,
                           expect_class=expect_class, host_down=host_down, exact_spawns=exact_spawns, max_spawns=max_spawns,
                           expect_exec=expect_exec, expect_handoff=expect_handoff, max_elapsed=max_elapsed, codex_mode=codex_mode)
    attempts = res.get("attempts") or []
    judge(cid, label, rules, {"state": res["state"], "spawns": n, "attempts": [(a["model"], a.get("error_class"), a.get("action")) for a in attempts],
                              "executed": res.get("executed_model"), "elapsed_s": round(elapsed, 2), "survivors": survivors})
    return res


def test_provider_failures():
    print("\n-- FI-01..FI-08 provider failures (A = Claude host-reported, B = Codex real subprocess) --")
    # FI-01 .. FI-06, direction A: the host reports Claude failed; the task may move to Codex only if it stays eligible
    for cid, klass in (("FI-01A", "TIMEOUT"), ("FI-03A", "RATE_LIMITED"), ("FI-04A", "QUOTA_EXHAUSTED"),
                       ("FI-05A", "AUTH_FAILED"), ("FI-06A", "MODEL_UNAVAILABLE")):
        provider_case(f"{cid}-low", f"Claude {klass} (host-reported), T_LOW -> falls back to Codex, which really runs", T_LOW,
                      expect_state="SUCCEEDED", host_down=klass, exact_spawns=1, expect_exec=CODEX)
        transient = klass in ("TIMEOUT", "RATE_LIMITED", "QUOTA_EXHAUSTED")
        provider_case(f"{cid}-high", f"Claude {klass} (host-reported), T_HIGH -> Codex is not eligible: "
                      f"{'WAITING_PROVIDER' if transient else 'NO_ELIGIBLE_PROVIDER'}, nothing spawned", T_HIGH,
                      expect_state="WAITING_PROVIDER" if transient else "NO_ELIGIBLE_PROVIDER", host_down=klass, exact_spawns=0, max_spawns=0)
    provider_case("FI-01A-crit", "Claude TIMEOUT (host-reported), T_CRIT -> only opus is eligible and it is down: WAITING_PROVIDER", T_CRIT,
                  expect_state="WAITING_PROVIDER", host_down="TIMEOUT", exact_spawns=0, max_spawns=0)

    # direction B: Codex really fails. require_executable=True = "run it here, in ATLAS", so Codex is the only candidate.
    for cid, mode, klass, state, spawn_n, tmo in (
            ("FI-02B", "hang", "TIMEOUT", "WAITING_PROVIDER", 2, 3.0),
            ("FI-03B", "rate_limit", "RATE_LIMITED", "WAITING_PROVIDER", 1, 10.0),
            ("FI-04B", "quota", "QUOTA_EXHAUSTED", "WAITING_PROVIDER", 1, 10.0),
            ("FI-05B", "auth", "AUTH_FAILED", "NO_ELIGIBLE_PROVIDER", 1, 10.0),
            ("FI-06B", "model", "MODEL_UNAVAILABLE", "NO_ELIGIBLE_PROVIDER", 1, 10.0),
            ("FI-07B-garbage", "garbage", "INVALID_RESPONSE", "WAITING_PROVIDER", 2, 10.0),
            ("FI-07B-no-turn", "no_turn", "INVALID_RESPONSE", "WAITING_PROVIDER", 2, 10.0),
            ("FI-07B-empty", "empty", "INVALID_RESPONSE", "WAITING_PROVIDER", 2, 10.0)):
        provider_case(cid, f"Codex {klass} ({mode}), T_LOW, executed in ATLAS -> {state} after exactly {spawn_n} spawn(s), no text",
                      T_LOW, expect_state=state, expect_class=klass, codex_mode=mode, require_executable=True,
                      exact_spawns=spawn_n, max_spawns=spawn_n, timeout_s=tmo)
    provider_case("FI-07B-crash", "Codex dies with no output (crash), T_LOW -> bounded, never a success", T_LOW,
                  expect_state="WAITING_PROVIDER", codex_mode="crash", require_executable=True, max_spawns=4, timeout_s=10.0)

    # after Codex failed, the orchestrator re-routes with what it learned: a Claude hand-off, only if still eligible
    for cid, req, allowed in (("FI-02B-handoff-low", T_LOW, {SONNET, OPUS}), ("FI-02B-handoff-high", T_HIGH, {SONNET, OPUS}),
                              ("FI-02B-handoff-crit", T_CRIT, {OPUS})):
        provider_case(cid, f"Codex failed (host re-routes), {req.risk} -> HANDOFF to a Claude model eligible for the task, ATLAS spawns nothing",
                      req, expect_state="HANDOFF", known={CODEX: "request timed out"}, exact_spawns=0, max_spawns=0, expect_handoff=allowed)

    # FI-08 both unavailable
    provider_case("FI-08-quota", "Claude quota (host) AND Codex quota (real), T_LOW -> WAITING_PROVIDER, no text", T_LOW,
                  expect_state="WAITING_PROVIDER", host_down="QUOTA_EXHAUSTED", codex_mode="quota", exact_spawns=1, expect_class="QUOTA_EXHAUSTED")
    provider_case("FI-08-auth", "Claude auth (host) AND Codex auth (real), T_LOW -> NO_ELIGIBLE_PROVIDER (credentials are the owner's), no retry",
                  T_LOW, expect_state="NO_ELIGIBLE_PROVIDER", host_down="AUTH_FAILED", codex_mode="auth", exact_spawns=1, expect_class="AUTH_FAILED")
    provider_case("FI-08-high", "Claude timeout (host) AND Codex timeout, T_HIGH -> Codex is never tried, WAITING_PROVIDER", T_HIGH,
                  expect_state="WAITING_PROVIDER", host_down="TIMEOUT", codex_mode="hang", exact_spawns=0, max_spawns=0)

    # negative control for the oracle: healthy Codex really succeeds and the judge says so
    provider_case("FI-00-control", "control: no failure injected, executed in ATLAS -> SUCCEEDED on Codex with its answer", T_LOW,
                  expect_state="SUCCEEDED", require_executable=True, exact_spawns=1, expect_exec=CODEX)


def test_provider_object_faults():
    print("\n-- FI-07 malformed results from a provider OBJECT (the invoke() guard) --")
    provs, codex = make_providers()

    class Liar:
        id = "openai"
        def __init__(self, behavior):
            self.behavior = behavior
        def models(self):
            return [CODEX]
        def capabilities(self, mid):
            return codex.capabilities(mid)
        def health(self, model_id=None):
            return codex.health(model_id)
        def cancel(self, rid):
            return False
        def execute(self, req):
            b = self.behavior
            if b == "none":
                return None
            if b == "dict":
                return {"ok": True, "text": "PONG"}
            if b == "other_request":
                return ProviderExecutionResult("someone-else", "openai", CODEX, True, "NONE", "PONG")
            if b == "ok_with_error":
                return ProviderExecutionResult(req.request_id, "openai", CODEX, True, "RATE_LIMITED", "PONG")
            if b == "raises":
                raise RuntimeError("boom")
            if b == "hang":
                time.sleep(3.0)                       # a provider that enforces no timeout of its own
                return ProviderExecutionResult(req.request_id, "openai", CODEX, True, "NONE", "PONG too late")
            return ProviderExecutionResult(req.request_id, "openai", CODEX, False, "NONE", "")
    for b in ("none", "dict", "other_request", "ok_with_error", "raises", "fail_no_class", "hang"):
        r = invoke(Liar(b), ProviderExecutionRequest("q", CODEX, "Say PONG.", timeout_s=0.4 if b == "hang" else 5))
        want = ("TIMEOUT",) if b == "hang" else ("INVALID_RESPONSE", "PROVIDER_ERROR")
        rules = {"R1": r.error_class in want, "R2": (not r.ok) and not r.text,
                 "R3": r.latency_ms < (2000 if b == "hang" else 5000), "R4": True, "R5": bool(r.error_detail), "R6": True,
                 "R7": security_probe(codex), "R8": None}
        judge(f"FI-07O-{b}", f"provider object returns/raises '{b}' -> a failed INVALID_RESPONSE/PROVIDER_ERROR (TIMEOUT for a hang) result, never a success, never an exception", rules)


def test_cost_policy():
    print("\n-- FI-08c the cost policy stays active while every free provider is down --")
    reg = copy.deepcopy(REG)
    reg["providers"]["paidco"] = {"enabled": True, "health_source": "probe"}
    reg["models"]["paidco/big"] = {"provider": "paidco", "enabled": True, "strengths": ["coding", "analysis", "reasoning"], "supports_tools": True,
                                   "supports_multimodal": "UNKNOWN", "context_tier": "large", "latency_tier": "UNKNOWN",
                                   "cost_tier": "per_token_paid", "eligible_risks": ["low", "medium", "high", "critical"],
                                   "assume_available_if_unknown": True}

    class Paid(ModelProvider):
        id = "paidco"
        calls = 0

        def models(self):
            return ["paidco/big"]

        def capabilities(self, mid):
            return ProviderCapability("paidco", mid, True, None, "large", "UNKNOWN", ("coding",), "per_token_paid", True)

        def health(self, model_id=None):
            return ProviderHealth("AVAILABLE", "healthy and tempting", "fake")

        def execute(self, req):
            Paid.calls += 1
            return ProviderExecutionResult(req.request_id, "paidco", req.model_id, True, "NONE", "PONG from a paid model")
    provs, codex = make_providers()
    provs["paidco"] = Paid()
    set_mode("quota")
    res = pf.execute_routed(T_LOW, "Say PONG.", provs, registry=reg, timeout_s=10, request_id="cost-1",
                            known_failures={SONNET: HOST_MSG["QUOTA_EXHAUSTED"], OPUS: HOST_MSG["QUOTA_EXHAUSTED"]})
    rules = {"R1": any(a.get("error_class") == "QUOTA_EXHAUSTED" for a in res["attempts"]),
             "R2": res["state"] != "SUCCEEDED" and not res.get("text"),
             "R3": len(res["attempts"]) <= pf.DEFAULT_POLICY["max_attempts"], "R4": res.get("executed_model") != "paidco/big",
             "R5": res["state"] == "WAITING_PROVIDER", "R6": None, "R7": security_probe(codex), "R8": Paid.calls == 0}
    judge("FI-08c", "Claude and Codex both out of quota, a healthy PAID model exists -> never executed (cost_policy CONFIGURED_ONLY), WAITING_PROVIDER",
          rules, {"state": res["state"], "paid_calls": Paid.calls})
    set_mode("ok")


# --------------------------------------------------------------------------- FI-09 reviewer unavailable
def test_reviewer():
    print("\n-- FI-09 reviewer unavailable --")

    def case(cid, label, req, impl, health, *, reviewer_none=False, gate=None, degraded=True, meets=False):
        plan = ri.plan_review(req, impl, REG, health_overrides=health)
        rec = dict(plan["record_template"])
        v = ri.verify_review_record(rec, plan["risk"], REG)
        rules = {
            "R1": plan["degraded"] is degraded,
            "R2": (plan["reviewer_model"] is None) == reviewer_none and v["meets_policy"] is meets,
            "R3": True,
            "R4": (plan["reviewer_model"] is None or eligible_for(plan["reviewer_model"], plan["risk"]))
            and ((gate is None) or (plan["human_gate_required"] is gate)),
            "R5": bool(plan["reason"]),
            "R6": None,
            "R7": hook_still_blocks(),
            "R8": plan["reviewer_model"] is None or model_cfg(plan["reviewer_model"]).get("cost_tier") == "configured_free",
        }
        judge(cid, label, rules, {"level": plan["achieved_level"], "reviewer": plan["reviewer_model"], "gate": plan["human_gate_required"]})

    down = lambda *ms, s="RATE_LIMITED": {m: s for m in ms}
    case("FI-09a", "HIGH: the only other model is rate-limited -> degraded to same-model review, NOT meeting policy, human gate REQUIRED",
         T_HIGH, SONNET, down(OPUS), reviewer_none=False, gate=True)
    case("FI-09b", "HIGH: every eligible reviewer unavailable -> no reviewer, degraded, human gate required",
         T_HIGH, SONNET, down(SONNET, OPUS, s="AUTH_FAILED"), reviewer_none=True, gate=True)
    case("FI-09c", "CRITICAL: opus (the only eligible reviewer) unavailable -> no reviewer, human gate required",
         T_CRIT, OPUS, down(OPUS), reviewer_none=True, gate=True)
    case("FI-09d", "MEDIUM: nothing can review -> no reviewer and never a pass", TaskRequirements(task_class="CODE", risk="MEDIUM"),
         SONNET, down(SONNET, OPUS, CODEX, s="QUOTA_EXHAUSTED"), reviewer_none=True, gate=None)
    case("FI-09e", "control: HIGH with everything healthy -> a different model reviews, policy met, not degraded",
         T_HIGH, SONNET, {}, reviewer_none=False, gate=False, degraded=False, meets=True)


# --------------------------------------------------------------------------- FI-10 Engram
def engram_env(proj):
    from atlas_dispatcher import ATLASDispatcher
    cfg = proj / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "config" / "phase_playbook.json", cfg / "phase_playbook.json")
    (proj / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(project_root=proj, auto_enable_mcp=False)


@contextlib.contextmanager
def engram_cwd():
    old = os.getcwd()
    os.chdir(ENGRAM_DIR)
    try:
        yield
    finally:
        os.chdir(old)


def test_engram():
    print("\n-- FI-10 Engram unavailable (real fake-engram subprocess behind the real bridge) --")
    import engram_mcp_bridge as bridge_mod
    from engram_strategy import make_mcp_bridge_strategy
    saved = bridge_mod.EngramMCPBridge.HANDSHAKE_TIMEOUT_S
    bridge_mod.EngramMCPBridge.HANDSHAKE_TIMEOUT_S = 0.8
    modes = ("exit", "hang", "garbage", "hang_after_init", "dies_on_call", "rpcerror", "wrongid", "ambiguous", "weird_found")
    try:
        for mode in modes + ("found", "notfound"):
            for disk in (True, False):
                proj = Path(tempfile.mkdtemp(prefix="eg_", dir=WORK))
                d = engram_env(proj)
                phase = next(iter(d.phase_playbook))
                cajon = "proj/planning"
                if disk:
                    (proj / ".pipeline" / "planning.md").write_text("# planning", encoding="utf-8")
                ENGRAM_MODE.write_text(mode)
                os.environ["FAKE_ENGRAM_MODE_FILE"] = str(ENGRAM_MODE)
                # A HEALTHY control gets generous timeouts so a loaded machine cannot turn it into a false failure; the failure
                # modes keep short ones, because waiting out the timeout IS their signal.
                bridge_mod.EngramMCPBridge.HANDSHAKE_TIMEOUT_S = 5.0 if mode in ("found", "notfound") else 0.8
                strat = make_mcp_bridge_strategy(binary_path=sys.executable, timeout_s=5.0 if mode in ("found", "notfound") else 1.0,
                                                 use_disk_fallback=True, project_root=proj)
                d._engram_strategy = strat
                healthy = mode in ("found", "notfound")
                t0 = time.perf_counter()
                with engram_cwd():
                    raw = strat.check_cajon("proj", cajon)
                    ok, msg, missing = d.enforce_phase_gate("proj", phase, [cajon])
                    full = d.get_cajon_full("proj", cajon) if (not healthy and not disk) else {"status": "n/a"}
                elapsed = time.perf_counter() - t0
                with contextlib.suppress(Exception):
                    strat._bridge.close()
                if mode == "found":
                    expect_pass = True
                else:
                    expect_pass = disk                 # closed unless the dual-write disk copy exists
                used_disk = bool(raw.get("fallback_used")) or raw.get("source") == "disk_fallback"
                rules = {
                    "R1": healthy or raw.get("status") in ("timeout", "ambiguous_project") or used_disk,
                    "R2": ok is expect_pass,
                    "R3": elapsed < 25.0,
                    "R4": (not used_disk) or disk,
                    "R5": ("source" in raw) and (healthy or used_disk or raw.get("status") in ("timeout", "ambiguous_project")),
                    "R6": elapsed < 25.0,
                    "R7": hook_still_blocks(),
                    "R8": None,
                }
                # a semantic-memory claim is only allowed from a healthy Engram
                if not healthy and raw.get("status") == "found":
                    rules["R5"] = rules["R5"] and raw.get("source") != "engram_mcp_real"
                # get_cajon_full never turns an Engram failure into "does not exist" while the disk copy exists
                if not healthy and not disk:
                    rules["R2"] = rules["R2"] and full.get("status") in ("timeout", "ambiguous_project", "not_found")
                judge(f"FI-10-{mode}-{'disk' if disk else 'nodisk'}",
                      f"Engram '{mode}', disk copy {'present' if disk else 'absent'} -> gate "
                      f"{'proceeds (DEGRADED_CONTINUE, source disk)' if expect_pass and not healthy else ('proceeds' if expect_pass else 'FAIL_CLOSED')}",
                      rules, {"gate_ok": ok, "raw_status": raw.get("status"), "raw_source": raw.get("source"), "full_status": full.get("status"),
                              "elapsed_s": round(elapsed, 2)})
    finally:
        bridge_mod.EngramMCPBridge.HANDSHAKE_TIMEOUT_S = saved
        os.environ.pop("FAKE_ENGRAM_MODE_FILE", None)

    print("\n-- FI-10 unknown status from any Engram strategy --")
    from engram_strategy import CallbackStrategy
    for status in ("ambiguous_project", "bogus_status", None):
        proj = Path(tempfile.mkdtemp(prefix="eg2_", dir=WORK))
        d = engram_env(proj)
        phase = next(iter(d.phase_playbook))
        d._engram_strategy = CallbackStrategy(callback=lambda p, c, s=status: ({"status": s} if s else {}), name="stub")
        ok, msg, missing = d.enforce_phase_gate("proj", phase, ["proj/planning"])
        rules = {"R1": True, "R2": ok is False, "R3": True, "R4": True, "R5": bool(msg), "R6": None, "R7": hook_still_blocks(), "R8": None}
        judge(f"FI-10-status-{status}", f"Engram strategy answers status={status!r}, no disk copy -> the gate is NOT passed", rules, {"gate_ok": ok})

    print("\n-- FI-10 operational truth never depends on Engram --")
    from delegation_tracker import DelegationTracker
    from qa_retry_state import QARetryState

    class Boom:
        name = "boom"
        called = 0
        def check_cajon(self, *a, **k):
            Boom.called += 1
            raise AssertionError("Engram consulted")
        def get_observation(self, *a, **k):
            Boom.called += 1
            raise AssertionError("Engram consulted")
    proj = Path(tempfile.mkdtemp(prefix="eg3_", dir=WORK))
    d = engram_env(proj)
    d._engram_strategy = Boom()
    qa = QARetryState(proj).record_qa_attempt("t1", "fail", "x")
    dt = DelegationTracker(proj).record_tool_call("Read", {})
    rt = mr.route(T_LOW, REG, log_decision=False)
    check("FI-10-ops operational state (QA retry, delegation, router) works with Engram unreachable and never consults it",
          Boom.called == 0 and qa["attempt_count"] == 1 and isinstance(dt, dict) and rt["selected"] is not None)




# --------------------------------------------------------------------------- FI-11 / FI-12 capabilities
def test_capabilities():
    print("\n-- FI-11 MCP unavailable (host-reported) / FI-12 capability unavailable, UNKNOWN, malformed --")
    import importlib
    # `core.capabilities` re-exports a router() FUNCTION, which shadows the module of the same name in a from-import
    cev = importlib.import_module("core.capabilities.events")
    cp = importlib.import_module("core.capabilities.policy")
    creg = importlib.import_module("core.capabilities.registry")
    cr = importlib.import_module("core.capabilities.router")
    from core.capabilities.base import Capability, Provider

    def attempt(fn, *a, **kw):
        try:
            return fn(*a, **kw), None
        except TypeError as e:                     # the layer has no way to be told about a failure
            return None, f"TypeError: {e}"

    def cap_case(cid, label, name, observed, *, usable, provider, down, decisions, evidence, policy_file=None):
        t0 = time.perf_counter()
        if observed is not None:
            r, e1 = attempt(cr.resolve_capability, name, emit=False, observed=observed)
        else:
            r, e1 = attempt(cr.resolve_capability, name, emit=False)
        kw = {"policy_file": policy_file} if policy_file else {}
        if observed is not None:
            kw["observed"] = observed
        d, e2 = attempt(cp.evaluate_capability, name, _emit=False, **kw)
        if r is None or d is None:
            rules = {k: False for k in ("R1", "R2", "R4", "R5")}
            rules.update({"R3": True, "R6": None, "R7": hook_still_blocks(), "R8": None})
            judge(cid, label + "  [the capability layer cannot accept a host-reported failure]", rules, {"error": e1 or e2})
            return
        rules = {
            "R1": sorted(getattr(r, "observed_down", None) or []) == sorted(down),
            "R2": r.is_usable is usable and d.decision in decisions,
            "R3": time.perf_counter() - t0 < 5.0,
            "R4": r.provider == provider and r.provider not in down,
            "R5": getattr(r, "evidence", None) == evidence and bool(d.notes or d.decision == "ALLOW" or d.recovery_hint),
            "R6": None, "R7": hook_still_blocks(), "R8": None,
        }
        judge(cid, label, rules, {"status": r.status, "provider": r.provider, "decision": d.decision, "evidence": getattr(r, "evidence", None)})

    cap_case("FI-11a", "documentation: context7 reported CONNECT_TIMEOUT by the host -> not LIVE/use, unavailable, policy WARN/BLOCK",
             "documentation", {"context7": "CONNECT_TIMEOUT"}, usable=False, provider=None, down=["context7"], decisions=("WARN", "BLOCK"), evidence="host_reported")
    cap_case("FI-11b", "browser: playwright reported down -> a different DECLARED provider serves, labelled declared, policy DEGRADED",
             "browser", {"playwright": "FAILED"}, usable=True, provider="claude_in_chrome", down=["playwright"], decisions=("DEGRADED",), evidence="declared")
    cap_case("FI-11c", "browser: every provider reported down -> unavailable, no provider invented",
             "browser", {"playwright": "FAILED", "claude_in_chrome": "UNREACHABLE", "claude_preview": "FAILED"}, usable=False, provider=None,
             down=["claude_in_chrome", "claude_preview", "playwright"], decisions=("WARN",), evidence="host_reported")
    cap_case("FI-11d", "memory: engram reported down -> unavailable and the policy BLOCKS (memory is block_if_unavailable)",
             "memory", {"engram": "CONNECTION_CLOSED"}, usable=False, provider=None, down=["engram"], decisions=("BLOCK",), evidence="host_reported")
    cap_case("FI-11e", "documentation: health reported UNKNOWN -> still the declared provider, NOT claimed verified",
             "documentation", {"context7": "UNKNOWN"}, usable=True, provider="context7", down=[], decisions=("ALLOW",), evidence="declared")
    cap_case("FI-11f", "documentation: host reports context7 OK -> the only case that is labelled host_reported",
             "documentation", {"context7": "OK"}, usable=True, provider="context7", down=[], decisions=("ALLOW",), evidence="host_reported")
    cap_case("FI-12h", "documentation: a malformed (non-string) health report fails CLOSED, never LIVE",
             "documentation", {"context7": {"weird": 1}}, usable=False, provider=None, down=["context7"], decisions=("WARN", "BLOCK"), evidence="host_reported")

    cap_case("FI-12a", "unknown capability -> unavailable, no provider, no exception, MISSING_POLICY (never ALLOW)",
             "__no_such_capability__", None, usable=False, provider=None, down=[], decisions=("MISSING_POLICY",), evidence="declared")

    old = os.environ.get("ATLAS_CAPABILITIES_DISABLED")
    os.environ["ATLAS_CAPABILITIES_DISABLED"] = "1"
    try:
        cap_case("FI-12b", "ATLAS_CAPABILITIES_DISABLED=1 -> every capability unavailable (memory therefore BLOCKS), nothing invented",
                 "memory", None, usable=False, provider=None, down=[], decisions=("BLOCK",), evidence="declared")
    finally:
        if old is None:
            os.environ.pop("ATLAS_CAPABILITIES_DISABLED", None)
        else:
            os.environ["ATLAS_CAPABILITIES_DISABLED"] = old

    creg._index["__empty__"] = Capability("__empty__", "no providers", [])
    creg._index["__weird__"] = Capability("__weird__", "malformed status", [Provider("x", "X", "WEIRD", "mcp__x__")])
    try:
        cap_case("FI-12c", "a capability with no providers -> unavailable", "__empty__", None, usable=False, provider=None, down=[],
                 decisions=("MISSING_POLICY",), evidence="declared")
        cap_case("FI-12d", "a provider with a malformed status is never selected", "__weird__", None, usable=False, provider=None, down=[],
                 decisions=("MISSING_POLICY",), evidence="declared")
    finally:
        creg._index.pop("__empty__", None)
        creg._index.pop("__weird__", None)

    bad = WORK / "bad_policy.yaml"
    bad.write_text("::: not yaml [[[ {{{\n\t- ???\n", encoding="utf-8")
    cap_case("FI-12e", "malformed policy file -> never ALLOW and never an exception", "memory", None, usable=True, provider="engram", down=[],
             decisions=("MISSING_POLICY", "BLOCK", "WARN"), evidence="declared", policy_file=bad)
    cap_case("FI-12f", "missing policy file -> never ALLOW", "memory", None, usable=True, provider="engram", down=[],
             decisions=("MISSING_POLICY", "BLOCK", "WARN"), evidence="declared", policy_file=WORK / "does_not_exist.yaml")

    ev = WORK / "events.jsonl"
    cev.emit_resolution(capability="x", provider_selected="p", provider_status="LIVE", fallback_used=False, action="use",
                        requested_by="f45", events_file=ev)
    with open(ev, "ab") as f:
        f.write(b"\x00\xff not json at all\n{\"torn\": \n")
    cev.emit_resolution(capability="y", provider_selected="p", provider_status="LIVE", fallback_used=False, action="use",
                        requested_by="f45", events_file=ev)
    try:
        got = cev.read_events(ev)
        ok = [e.capability for e in got] == ["x", "y"]
    except Exception:                                # noqa: BLE001
        ok = False
    judge("FI-12g", "malformed lines in the capability events file are skipped; valid events survive; no exception",
          {"R1": ok, "R2": ok, "R3": True, "R4": True, "R5": ok, "R6": None, "R7": hook_still_blocks(), "R8": None})


# --------------------------------------------------------------------------- FI-13 / FI-14 telemetry
def test_telemetry():
    print("\n-- FI-13 telemetry append fails / FI-14 rotation fails --")
    import invocation_tracker as it
    bj = sys.modules[BoundedJsonl.__module__]       # the module the class really reads its constants from (tools.bounded_jsonl)
    d = Path(tempfile.mkdtemp(prefix="tm_", dir=WORK))
    hook = hook_still_blocks()

    def tele_rules(detected, no_false, t0, evidence, extra=True):
        return {"R1": detected, "R2": no_false, "R3": time.perf_counter() - t0 < 5.0, "R4": None, "R5": evidence, "R6": extra,
                "R7": hook, "R8": None}

    # 13a: the log path is a directory
    p = d / "a.jsonl"
    p.mkdir()
    t0 = time.perf_counter()
    r = BoundedJsonl(p).append({"x": 1})
    judge("FI-13a", "append to a path that is a directory -> AppendResult(ok=False, reason), no exception, nothing stored",
          tele_rules(r.ok is False and bool(r.error), p.is_dir() and not any(p.iterdir()), t0, bool(r.error)))

    # 13b: read-only file (skipped as root on POSIX, where permissions do not bind)
    p = d / "b.jsonl"
    p.write_text('{"keep": 1}\n', encoding="utf-8")
    before = p.read_bytes()
    os.chmod(p, stat.S_IREAD)
    root = hasattr(os, "geteuid") and os.geteuid() == 0
    try:
        t0 = time.perf_counter()
        r = BoundedJsonl(p).append({"x": 2})
    finally:
        os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    if root:
        print("  [SKIP] FI-13b read-only file: running as root, permissions do not bind")
    else:
        judge("FI-13b", "append to a read-only file -> ok=False with a reason; the existing content is byte-identical",
              tele_rules(r.ok is False and bool(r.error), p.read_bytes() == before, t0, bool(r.error)))

    # 13c: the parent directory does not exist and this writer must not create it
    t0 = time.perf_counter()
    r = BoundedJsonl(d / "no" / "such" / "c.jsonl", create_parent=False).append({"x": 3})
    judge("FI-13c", "create_parent=False with a missing parent -> ok=False, the directory is NOT created",
          tele_rules(r.ok is False, not (d / "no").exists(), t0, bool(r.error)))

    # 13d: an entry that cannot be serialised
    t0 = time.perf_counter()
    r = BoundedJsonl(d / "d.jsonl").append({"x": object()})
    judge("FI-13d", "an unserialisable entry -> ok=False, nothing written, no exception",
          tele_rules(r.ok is False and "TypeError" in (r.error or ""), not (d / "d.jsonl").exists() or (d / "d.jsonl").stat().st_size == 0, t0, bool(r.error)))

    # 13e: tracker + audit with an unwritable log -> missing evidence is INCOMPLETE, never complete
    proj = Path(tempfile.mkdtemp(prefix="trk_", dir=WORK))
    (proj / ".pipeline" / "invocation-log.jsonl").mkdir(parents=True)
    tr = it.InvocationTracker(proj)
    t0 = time.perf_counter()
    rec = tr.record("helper_x")
    aud = tr.audit_invocations(["helper_x"])
    judge("FI-13e", "tracker cannot append -> record() says ok=False, and the audit of that helper is INCOMPLETE (a lost log is not evidence of invocation)",
          tele_rules(rec.get("ok") is False, aud["verdict"] == "incomplete" and "helper_x" in aud["missing"], t0, bool(rec.get("error"))))

    # 13f / 13g / 13h: the tracker itself broken -> the dispatcher's audit must not say "complete"
    from atlas_dispatcher import ATLASDispatcher
    cfg = proj / "config"
    cfg.mkdir(exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "config" / "phase_playbook.json", cfg / "phase_playbook.json")
    disp = ATLASDispatcher(project_root=proj, auto_enable_mcp=False)
    real_cls = it.InvocationTracker

    class Broken:
        def __init__(self, *a, **k):
            pass

        def audit_invocations(self, *a, **k):
            raise RuntimeError("tracker exploded")

        def record(self, *a, **k):
            return {"ok": False}
    it.InvocationTracker = Broken
    try:
        t0 = time.perf_counter()
        a1 = disp.audit_invocations(["helper_x"])
    finally:
        it.InvocationTracker = real_cls
    judge("FI-13f", "the tracker raises during an audit -> the audit verdict is NOT 'complete'",
          tele_rules(a1.get("verdict") != "complete", a1.get("verdict") in ("incomplete", "unverifiable"), t0, bool(a1.get("note"))),
          {"verdict": a1.get("verdict")})
    saved_mod = sys.modules.get("invocation_tracker")
    sys.modules["invocation_tracker"] = None            # makes `from invocation_tracker import ...` raise ImportError
    try:
        t0 = time.perf_counter()
        a2 = disp.audit_invocations(["helper_x"])
    finally:
        sys.modules["invocation_tracker"] = saved_mod
    judge("FI-13g", "the tracker cannot even be imported -> the audit verdict is NOT 'complete'",
          tele_rules(a2.get("verdict") != "complete", a2.get("verdict") in ("incomplete", "unverifiable"), t0, bool(a2.get("note"))),
          {"verdict": a2.get("verdict")})
    crit = None
    for name in sorted(getattr(disp, "CRITICAL_AGENTS", ())):
        if getattr(disp, "AGENT_HELPER_REQUIREMENTS", {}).get(name):
            crit = name
            break
    it.InvocationTracker = Broken
    try:
        enf = disp.enforce_helpers_for_agent({}, crit) if crit else {"verdict": "n/a"}
    finally:
        it.InvocationTracker = real_cls
    judge("FI-13h", "hard enforcement of a CRITICAL agent while the tracker is broken -> never 'passed'",
          tele_rules(enf.get("verdict") != "passed", enf.get("verdict") in ("incomplete",), time.perf_counter(),
                     bool(enf.get("note") or enf.get("missing_helpers"))),
          {"agent": crit, "verdict": enf.get("verdict")})

    # 13i: the router's decision log is unwritable -> the decision is still returned
    blocker = d / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    saved_log = mr._DECISION_LOG
    mr._DECISION_LOG = blocker / "x.jsonl"
    try:
        t0 = time.perf_counter()
        dec = mr.route(T_LOW, REG, log_decision=True)
    finally:
        mr._DECISION_LOG = saved_log
    judge("FI-13i", "the router's decision log cannot be written -> the decision is still returned (documented fail-open) and names a model",
          tele_rules(True, dec.get("selected") is not None and not (blocker / "x.jsonl").exists(), t0, True))

    # 14a: the archive path is a directory -> rotation cannot happen
    p = d / "r.jsonl"
    (d / "r.1.jsonl").mkdir()
    store = BoundedJsonl(p, max_bytes=300)
    calls = []
    real_replace = os.replace

    def counting(src, dst):
        if str(src) == str(p):
            calls.append(1)
        return real_replace(src, dst)
    os.replace = counting
    try:
        t0 = time.perf_counter()
        results = [store.append({"n": i, "pad": "x" * 20}) for i in range(30)]
    finally:
        os.replace = real_replace
    lines = p.read_text(encoding="utf-8").splitlines()
    parse_ok = True
    for ln in lines:
        try:
            json.loads(ln)
        except ValueError:
            parse_ok = False
    st = store.status()
    judge("FI-14a", "rotation impossible (archive path is a directory) -> every append still stored whole, rotation_error surfaced, over_bound visible, "
                    "and rotation is retried at most once inside the backoff window",
          tele_rules(any(x.rotation_error for x in results) and st["last_rotation_error"] is not None,
                     all(x.ok for x in results) and len(lines) == 30 and parse_ok, t0, st["over_bound"] is True, extra=len(calls) == 1),
          {"rotation_attempts": len(calls), "over_bound": st["over_bound"]})

    # 14b: another holder has the lock -> bounded wait, then ok=False, nothing stored
    import threading
    p = d / "l.jsonl"
    store = BoundedJsonl(p)
    held, release = threading.Event(), threading.Event()

    def holder():
        with bj._file_lock(store.lock_path, 5.0):
            held.set()
            release.wait(6.0)
    th = threading.Thread(target=holder, daemon=True)
    th.start()
    held.wait(3.0)
    saved_to = bj.LOCK_TIMEOUT_SECONDS
    bj.LOCK_TIMEOUT_SECONDS = 0.3
    try:
        t0 = time.perf_counter()
        r = store.append({"x": 1})
        waited = time.perf_counter() - t0
    finally:
        bj.LOCK_TIMEOUT_SECONDS = saved_to
        release.set()
        th.join(3.0)
    judge("FI-14b", "the rotation/append lock is held elsewhere -> a bounded wait (not a hang), ok=False with the reason, nothing stored",
          tele_rules(r.ok is False and "Timeout" in (r.error or ""), not p.exists() or p.stat().st_size == 0, t0, bool(r.error), extra=waited < 3.0))

    # 14c: malformed archive
    p = d / "m.jsonl"
    seg = d / "m.1.jsonl"
    seg.write_bytes(b"\x00\xff garbage without newline\n{\"torn\": \n" + json.dumps({"ts": "x", "ok": 1}).encode() + b"\n")
    store = BoundedJsonl(p, max_bytes=200)
    try:
        got = store.tail_entries(100)
        read_ok = [e for e in got if e.get("ok") == 1] != [] and all(isinstance(e, dict) for e in got)
    except Exception:                                # noqa: BLE001
        read_ok = False
    rs = [store.append({"n": i, "pad": "y" * 30}) for i in range(10)]
    judge("FI-14c", "a malformed archive never breaks reads, and rotation over it still works",
          tele_rules(read_ok, all(x.ok for x in rs) and any(x.rotated for x in rs), time.perf_counter(), True))


# --------------------------------------------------------------------------- FI-15 malformed execution state
def test_state():
    print("\n-- FI-15 malformed execution state --")
    from delegation_tracker import DelegationTracker
    from qa_retry_state import QARetryState
    variants = {
        "truncated-json": b'{"version": 1, "tasks": {"t1": {"attempt_co',
        "top-level-array": b"[]",
        "top-level-null": b"null",
        "top-level-string": b'"hello"',
        "wrong-version": b'{"version": 2, "tasks": {}}',
        "tasks-is-list": b'{"version": 1, "tasks": []}',
        "entry-is-int": b'{"version": 1, "tasks": {"t1": 5}}',
        "negative-count": b'{"version": 1, "tasks": {"t1": {"attempt_count": -9}}}',
        "non-numeric-count": b'{"version": 1, "tasks": {"t1": {"attempt_count": "two"}}}',
        "binary": bytes(range(256)),
        "bom-garbage": b"\xef\xbb\xbf{{{",
    }
    hook = hook_still_blocks()
    for name, raw in variants.items():
        proj = Path(tempfile.mkdtemp(prefix="qa_", dir=WORK))
        sp = proj / ".pipeline" / "qa-retry-state.json"
        sp.parent.mkdir()
        sp.write_bytes(raw)
        q = QARetryState(proj)
        t0 = time.perf_counter()
        c = q.check_qa_retry_limit("t1")
        kept_after_check = sp.read_bytes() == raw
        r = q.record_qa_attempt("t1", "fail", "x")
        kept = kept_after_check and sp.read_bytes() == raw
        judge(f"FI-15-qa-{name}", f"QA retry state '{name}' -> FAIL_CLOSED (limit reached + state_error) and the unreadable file is preserved, not overwritten",
              {"R1": bool(c.get("state_error")), "R2": c["retry_limit_reached"] is True and r["retry_limit_reached"] is True and kept,
               "R3": time.perf_counter() - t0 < 5.0, "R4": None, "R5": bool(c.get("state_error")) and bool(r.get("state_error")),
               "R6": None, "R7": hook, "R8": None},
              {"check": {k: c.get(k) for k in ("attempt_count", "retry_limit_reached", "state_error")}, "file_preserved": kept})

    ok_all = True
    for name, raw in (("truncated", b'{"version": 1, "consec'), ("array", b"[]"), ("wrong-version", b'{"version": 9}'), ("binary", bytes(range(256)))):
        proj = Path(tempfile.mkdtemp(prefix="dl_", dir=WORK))
        sp = proj / ".pipeline" / "delegation-state.json"
        sp.parent.mkdir()
        sp.write_bytes(raw)
        t = DelegationTracker(proj)
        try:
            st = t.get_state()
            out = t.record_tool_call("Read", {})
            ok_all = ok_all and isinstance(st, dict) and st.get("version") == 1 and isinstance(out, dict)
        except Exception:                            # noqa: BLE001
            ok_all = False
    check("FI-15-delegation malformed delegation state (advisory, documented DEGRADED_CONTINUE) -> continues with a valid default state, never raises", ok_all)


# --------------------------------------------------------------------------- FI-16 duplicates
def test_duplicates():
    print("\n-- FI-16 duplicate execution / request --")
    from qa_retry_state import QARetryState
    proj = Path(tempfile.mkdtemp(prefix="dup_", dir=WORK))
    procs = []
    code = ("import sys; sys.path.insert(0, sys.argv[2]); from pathlib import Path; from qa_retry_state import QARetryState; "
            "q = QARetryState(Path(sys.argv[1]), max_attempts=1000); "
            "[q.record_qa_attempt('tc', 'fail', 'x') for _ in range(5)]")
    for _ in range(4):
        procs.append(subprocess.Popen([sys.executable, "-c", code, str(proj), str(PROJECT_ROOT / "tools")]))
    for p in procs:
        p.wait(timeout=120)
    n = QARetryState(proj, max_attempts=1000).check_qa_retry_limit("tc")["attempt_count"]
    check("FI-16a four concurrent processes recording 5 failures each -> exactly 20 counted (no lost update, no double count)", n == 20, f"count={n}")

    q = QARetryState(Path(tempfile.mkdtemp(prefix="dup2_", dir=WORK)))
    seq = [q.record_qa_attempt("tb", "fail", "same event")["retry_limit_reached"] for _ in range(3)]
    check("FI-16b the same failure recorded without an id counts each time (documented): the ceiling is reached at exactly 3 records, earlier never later",
          seq == [False, False, True], str(seq))

    q = QARetryState(Path(tempfile.mkdtemp(prefix="dup3_", dir=WORK)))
    try:
        a = q.record_qa_attempt("tc", "fail", "x", attempt_id="a1")
        b = q.record_qa_attempt("tc", "fail", "x", attempt_id="a1")
        c = q.record_qa_attempt("tc", "fail", "x", attempt_id="a2")
        ok = a["attempt_count"] == 1 and b["attempt_count"] == 1 and b.get("duplicate") is True and c["attempt_count"] == 2
        detail = f"counts={a['attempt_count']},{b['attempt_count']},{c['attempt_count']}"
    except TypeError as e:
        ok, detail = False, f"TypeError: {e}"
    check("FI-16c a repeated attempt_id does NOT count twice; a new id does", ok, detail)

    provs, codex = make_providers()
    set_mode("ok")
    base = spawns()
    r1 = pf.execute_routed(T_LOW, "Say PONG.", provs, registry=REG, require_executable=True, request_id="dup-1", timeout_s=20)
    r2 = pf.execute_routed(T_LOW, "Say PONG.", provs, registry=REG, require_executable=True, request_id="dup-1", timeout_s=20)
    n = spawns() - base
    check("FI-16e [accepted gap AG-1] the same request_id sent twice is NOT detected (stateless executor): at most 2 bounded spawns, both reported truthfully",
          n <= 2 and r1["state"] == "SUCCEEDED" and r2["state"] == "SUCCEEDED", f"spawns={n}")


# --------------------------------------------------------------------------- FI-17 checkpoint interruption
def run_child(code, *args, timeout=60):
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, timeout=timeout)


def test_checkpoints():
    print("\n-- FI-17 interrupted writes (a real process is killed in the middle) --")
    from delegation_tracker import DelegationTracker
    from qa_retry_state import QARetryState
    hook = hook_still_blocks()
    tools = str(PROJECT_ROOT / "tools")

    proj = Path(tempfile.mkdtemp(prefix="cp1_", dir=WORK))
    t = DelegationTracker(proj)
    st = t.get_state()
    st["consecutive_reads"] = 3
    t._save_state(st)
    child = ("import os, sys; sys.path.insert(0, sys.argv[2]); from pathlib import Path; import delegation_tracker as dt\n"
             "def die(a, b): os._exit(7)\n"
             "dt.os.replace = die\n"
             "t = dt.DelegationTracker(Path(sys.argv[1])); s = t.get_state(); s['consecutive_reads'] = 99; t._save_state(s)\n")
    r = run_child(child, str(proj), tools)
    after = DelegationTracker(proj).get_state()
    strays = list((proj / ".pipeline").glob(".delegation-state-*.tmp"))
    judge("FI-17a", "delegation state: the writer dies between the temp write and the rename -> the previous valid state is intact",
          {"R1": r.returncode == 7, "R2": after.get("consecutive_reads") == 3, "R3": True, "R4": None,
           "R5": isinstance(after, dict) and after.get("version") == 1, "R6": None, "R7": hook, "R8": None},
          {"stray_tmp_files": len(strays)})

    proj = Path(tempfile.mkdtemp(prefix="cp2_", dir=WORK))
    QARetryState(proj).record_qa_attempt("t1", "fail", "first")
    child = ("import json, os, sys; sys.path.insert(0, sys.argv[2]); from pathlib import Path; import qa_retry_state as qs\n"
             "def torn(obj, fh, **kw):\n"
             "    s = json.dumps(obj, **kw); fh.write(s[: len(s) // 2]); fh.flush(); os._exit(9)\n"
             "json.dump = torn\n"
             "qs.QARetryState(Path(sys.argv[1])).record_qa_attempt('t1', 'fail', 'second ' * 60)\n")
    r = run_child(child, str(proj), tools)
    c = QARetryState(proj).check_qa_retry_limit("t1")
    silently_reset = c["attempt_count"] == 0 and not c.get("state_error")
    judge("FI-17b", "QA retry state: the writer dies in the MIDDLE of the write -> never read back as 'no attempts' (the previous count survives or the read fails closed)",
          {"R1": r.returncode == 9, "R2": not silently_reset and (bool(c.get("state_error")) or c["attempt_count"] >= 1),
           "R3": True, "R4": None, "R5": bool(c.get("state_error")) or c["attempt_count"] >= 1, "R6": None, "R7": hook, "R8": None},
          {"after": {k: c.get(k) for k in ("attempt_count", "retry_limit_reached", "state_error")}})
    check("FI-17b' the interruption really produced a torn file (the fail-closed branch was exercised, not a lucky valid write)",
          bool(c.get("state_error")), str(c.get("state_error"))[:80])

    for when in ("before", "after"):
        d = Path(tempfile.mkdtemp(prefix=f"cp3{when}_", dir=WORK))
        p = d / "j.jsonl"
        pre = BoundedJsonl(p, max_bytes=10_000_000)
        for i in range(12):
            pre.append({"n": i, "pad": "z" * 20})
        child = ("import os, sys; sys.path.insert(0, sys.argv[2]); from pathlib import Path; import bounded_jsonl as bj\n"
                 "p = Path(sys.argv[1]); real = os.replace; when = sys.argv[3]\n"
                 "def hook(a, b):\n"
                 "    if str(a) == str(p):\n"
                 "        if when == 'before': os._exit(5)\n"
                 "        real(a, b); os._exit(5)\n"
                 "    return real(a, b)\n"
                 "os.replace = hook\n"
                 "bj.BoundedJsonl(p, max_bytes=300).append({'n': 99, 'pad': 'z' * 20})\n")
        r = run_child(child, str(p), tools, when)
        store = BoundedJsonl(p, max_bytes=300)
        got = store.tail_entries(1000)
        both_parse = True
        for f in (p, store.segment_path):
            if f.exists():
                for ln in f.read_text(encoding="utf-8").splitlines():
                    try:
                        json.loads(ln)
                    except ValueError:
                        both_parse = False
        nxt = store.append({"n": 100})
        judge(f"FI-17c-{when}", f"telemetry rotation: the writer dies {when} the rename -> current + archive both parse, no entry lost, the next append works",
              {"R1": r.returncode == 5, "R2": len(got) == 13 and both_parse, "R3": True, "R4": None, "R5": both_parse, "R6": nxt.ok,
               "R7": hook, "R8": None}, {"entries": len(got)})

    src = (PROJECT_ROOT / "tools" / "provider_fallback.py").read_text(encoding="utf-8")
    persists = [tok for tok in ("open(", "write_text", "write_bytes", "os.replace", "json.dump(", "sqlite", "shelve", "pickle") if tok in src]
    check("FI-17d the provider executor persists no checkpoint (stateless: nothing to interrupt) -> NOT_APPLICABLE, asserted statically", not persists, str(persists))

    print("  [INFO] FI-17e orphan check is documented, not asserted: a hard-killed ATLAS process leaves a running Codex child (no job object); "
          "see docs/FAILURE-INJECTION-CAMPAIGN.md section 5.")


# --------------------------------------------------------------------------- the oracle itself
def test_oracle():
    print("\n-- the judge is checked against fabricated bad results (it must say FALSE) --")
    base = dict(n=1, elapsed=1.0, survivors=[], security_ok=True, expect_state="SUCCEEDED", exact_spawns=1, max_spawns=1)

    def res(**kw):
        r = {"state": "SUCCEEDED", "text": "PONG", "executed_model": CODEX,
             "attempts": [{"model": CODEX, "action": "SUCCESS", "error_class": "NONE"}],
             "provider_health": {}, "blockers": {}, "handoff": None}
        r.update(kw)
        return r
    good = provider_rules(T_LOW, res(), **base)
    check("O0 a genuine success passes every rule", all(good.values()), str(good))
    check("O1 SUCCEEDED with no text is a false success (R2)", provider_rules(T_LOW, res(text=""), **base)["R2"] is False)
    check("O2 execution on a model not eligible for HIGH risk is an unsafe fallback (R4)", provider_rules(T_HIGH, res(), **base)["R4"] is False)
    retry_only = res(state="WAITING_PROVIDER", text=None, executed_model=None,
                     attempts=[{"model": CODEX, "action": "RETRY", "error_class": "TIMEOUT"}])
    two = dict(n=1, elapsed=1.0, survivors=[], security_ok=True, expect_state="WAITING_PROVIDER", exact_spawns=2, max_spawns=2)
    check("O3 a logged RETRY that never happened is inconsistent evidence (R5)", provider_rules(T_LOW, retry_only, **two)["R5"] is False)
    check("O4 a dropped retry (1 spawn where policy says 2) fails R6", provider_rules(T_LOW, retry_only, **two)["R6"] is False)
    over = provider_rules(T_LOW, res(), **dict(base, n=5))
    check("O5 more spawns than the bound fails R3 and R6", over["R3"] is False and over["R6"] is False)
    check("O6 a surviving process fails R3", provider_rules(T_LOW, res(), **dict(base, survivors=[123]))["R3"] is False)
    check("O7 a model outside configured_free fails R8",
          provider_rules(T_LOW, res(executed_model="x/unknown", attempts=[]), **dict(base, exact_spawns=None))["R8"] is False)
    check("O8 a security probe failure fails R7", provider_rules(T_LOW, res(), **dict(base, security_ok=False))["R7"] is False)
    check("O9 a failure case that reports SUCCEEDED fails R2",
          provider_rules(T_LOW, res(), **dict(base, expect_state="WAITING_PROVIDER"))["R2"] is False)


def test_live():
    print("\n-- LIVE: real Codex failures through the routed executor (a few tiny requests at most) --")
    if not shutil.which("codex"):
        check("L0 the codex CLI is installed (needed for --live)", False, "codex not found on PATH")
        return

    def routed(reg, env, timeout_s):
        codex = CodexCliProvider(reg, "openai", environ=env)
        provs = {"anthropic": AnthropicHostProvider(reg, "anthropic"), "openai": codex}
        if not env.get("CODEX_HOME_EMPTY"):
            codex._observe("AVAILABLE", "live test: skip the paid probe; the failure below is what is being tested")
        return pf.execute_routed(T_LOW, "Reply with exactly the word PONG.", provs, registry=reg, require_executable=True,
                                 timeout_s=timeout_s, request_id="live")

    # L1 a model that does not exist: the real service refuses it
    reg = copy.deepcopy(REG)
    reg["models"][CODEX]["codex_model"] = "atlas-f45-no-such-model"
    t0 = time.perf_counter()
    res = routed(reg, dict(os.environ), 90)
    rules = provider_rules(T_LOW, res, n=len(res["attempts"]), elapsed=time.perf_counter() - t0, survivors=[], security_ok=True,
                           expect_state="NO_ELIGIBLE_PROVIDER", expect_class="MODEL_UNAVAILABLE", exact_spawns=1, max_spawns=1,
                           max_elapsed=120, codex_mode="live")
    judge("L1", "REAL Codex, a model that does not exist -> MODEL_UNAVAILABLE after exactly one request, NO_ELIGIBLE_PROVIDER, no text", rules,
          {"state": res["state"], "attempts": [(a["model"], a.get("error_class")) for a in res["attempts"]]})

    # L2 no credentials: an empty CODEX_HOME is a real "not logged in"
    empty = Path(tempfile.mkdtemp(prefix="atlas_f45_codexhome_", dir=WORK))
    env = dict(os.environ)
    env["CODEX_HOME"] = str(empty)
    env["CODEX_HOME_EMPTY"] = "1"
    t0 = time.perf_counter()
    res = routed(copy.deepcopy(REG), env, 90)
    ok = res["state"] == "NO_ELIGIBLE_PROVIDER" and not res.get("text") and res.get("executed_model") is None \
        and CODEX in (res.get("provider_health") or res.get("blockers") or {}) and len(res["attempts"]) == 0
    check("L2 REAL Codex with no login (empty CODEX_HOME) -> detected from the login status before any request is spent, NO_ELIGIBLE_PROVIDER, never retried",
          ok, f"state={res['state']} health={res.get('provider_health') or res.get('blockers')}")

    # L3 a timeout: the real request is cut off at 1.5 s and its process tree is killed
    t0 = time.perf_counter()
    res = routed(copy.deepcopy(REG), dict(os.environ), 1.5)
    n = len(res["attempts"])
    rules = provider_rules(T_LOW, res, n=n, elapsed=time.perf_counter() - t0, survivors=[], security_ok=True,
                           expect_state="WAITING_PROVIDER", expect_class="TIMEOUT", exact_spawns=2, max_spawns=2, max_elapsed=60, codex_mode="live")
    judge("L3", "REAL Codex cut off at 1.5 s -> TIMEOUT, exactly one retry, then WAITING_PROVIDER, no text", rules,
          {"state": res["state"], "attempts": [(a["model"], a.get("error_class"), a.get("action")) for a in res["attempts"]]})


def finish_cleanup():
    for p in pids():
        with contextlib.suppress(Exception):
            if alive(p):
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
                else:
                    os.kill(p, 9)
    shutil.rmtree(WORK, ignore_errors=True)


def main():
    live = "--live" in sys.argv
    report = sys.argv[sys.argv.index("--report") + 1] if "--report" in sys.argv else None
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    print("=" * 60)
    print("Bloque F45 -- Failure-injection campaign (P16)" + (" [LIVE]" if live else ""))
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    write_fakes()
    t0 = time.perf_counter()
    try:
        for fn in (test_oracle, test_provider_failures, test_provider_object_faults, test_cost_policy, test_reviewer, test_engram, test_capabilities,
                   test_telemetry, test_state, test_duplicates, test_checkpoints):
            if only and not any(o in fn.__name__ for o in only):
                continue
            fn()
        if live:
            test_live()
    finally:
        finish_cleanup()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nElapsed: {time.perf_counter() - t0:.1f}s")
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    if report:
        Path(report).write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
