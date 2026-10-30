#!/usr/bin/env python3
"""
Bloque F42 -- Codex CLI provider (second real provider, roadmap P5)
=============================================================================

Offline cases replay REAL outputs captured from codex-cli 0.147.0 (success, nonexistent model, no login) through a
fake runner, so the suite is deterministic and spends nothing. `--live` additionally drives the real binary:
login status, a PONG round trip, a bad model, an unauthenticated run (empty CODEX_HOME) and a timeout that must
leave no orphan process. Live cases are opt-in because CI has no Codex login.

Not reproducible safely, therefore SYNTHETIC wording (marked below): quota exhaustion and rate limiting.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.providers import CodexCliProvider, ProviderExecutionRequest, build_providers, invoke  # noqa: E402
from core.providers import codex_cli as cx  # noqa: E402
from tools import model_router as mr  # noqa: E402
from tools.model_router import TaskRequirements, route  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
CODEX = "openai/codex-cli"
SONNET, OPUS = "anthropic/sonnet", "anthropic/opus"


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def jl(*events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


# ---- fixtures: REAL captures (ids shortened) --------------------------------------------------------------
OK_STDOUT = jl({"type": "thread.started", "thread_id": "t1"}, {"type": "turn.started"},
               {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "PONG"}},
               {"type": "turn.completed", "usage": {"input_tokens": 17013, "cached_input_tokens": 10496, "output_tokens": 6}})
OK_STDERR_NOISE = "2026-10-30T06:50:27Z ERROR codex_models_manager::manager: failed to load models cache: missing field `supports_parallel_tool_calls`"
BAD_MODEL_MSG = ('{"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The \'x\' model is not supported '
                 'when using Codex with a ChatGPT account.","code":"model_not_found"}}')
BAD_MODEL_STDOUT = jl({"type": "thread.started", "thread_id": "t2"},
                      {"type": "item.completed", "item": {"id": "item_0", "type": "error", "message": "Model metadata for `x` not found."}},
                      {"type": "turn.started"}, {"type": "error", "message": BAD_MODEL_MSG}, {"type": "turn.failed", "error": {"message": BAD_MODEL_MSG}})
RECONNECT = "Reconnecting... {n}/5 (unexpected status 401 Unauthorized: Missing bearer or basic authentication in header, url: wss://api.openai.com/v1/responses)"
FINAL_401 = "unexpected status 401 Unauthorized: Missing bearer or basic authentication in header, url: https://api.openai.com/v1/responses"
NOAUTH_STDOUT = jl({"type": "thread.started", "thread_id": "t3"}, {"type": "turn.started"},
                   *[{"type": "error", "message": RECONNECT.format(n=i)} for i in range(1, 6)],
                   {"type": "item.completed", "item": {"id": "item_0", "type": "error", "message": "Falling back from WebSockets to HTTPS transport."}},
                   {"type": "error", "message": FINAL_401}, {"type": "turn.failed", "error": {"message": FINAL_401}})


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Runner:
    """Fake process runner. Each outcome is a RunOutcome or a callable(argv) -> RunOutcome."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def __call__(self, argv, stdin_text, env, cwd, timeout_s, on_start=None):
        self.calls.append({"argv": list(argv), "stdin": stdin_text, "env": dict(env), "cwd": cwd, "timeout": timeout_s,
                           "cwd_existed": os.path.isdir(cwd), "cwd_files": sorted(os.listdir(cwd)) if os.path.isdir(cwd) else None})
        out = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
        if on_start:
            on_start(type("P", (), {"pid": 0})())
        return out(argv) if callable(out) else out


def ok_outcome(text="PONG", stdout=OK_STDOUT):
    def make(argv):
        if "-o" in argv:
            Path(argv[argv.index("-o") + 1]).write_text(text, encoding="utf-8")
        return cx.RunOutcome(0, stdout, OK_STDERR_NOISE)
    return make


LOGGED_IN = cx.RunOutcome(0, "", "Logged in using ChatGPT")
NOT_LOGGED_IN = cx.RunOutcome(1, "", "Not logged in")


class SmartRunner:
    """Dispatches by WHAT was called: `login status` gets the login outcome, everything else is an exec."""

    def __init__(self, login=None, *execs):
        self.login = login or LOGGED_IN
        self.execs = list(execs) or [ok_outcome()]
        self.login_calls, self.exec_calls = 0, []

    def __call__(self, argv, stdin_text, env, cwd, timeout_s, on_start=None):
        if list(argv[-2:]) == ["login", "status"]:
            self.login_calls += 1
            return self.login
        self.exec_calls.append(list(argv))
        out = self.execs[min(len(self.exec_calls) - 1, len(self.execs) - 1)]
        return out(argv) if callable(out) else out


def provider(runner, registry=None, clock=None, resolver=lambda: ["fake-codex"], environ=None):
    return CodexCliProvider(registry or mr.load_registry(), runner=runner, resolver=resolver,
                            environ=environ if environ is not None else {"PATH": "/bin"}, clock=clock or Clock())


def request(prompt="Review this function.", model=CODEX, timeout=30.0, rid="q1"):
    return ProviderExecutionRequest(rid, model, prompt, timeout_s=timeout)


# --------------------------------------------------------------------------- A. registry integration
def test_registry():
    reg = mr.load_registry()
    provs, skipped = build_providers(reg)
    check("01 both verified providers are built from the registry and nothing is skipped",
          set(provs) == {"anthropic", "openai"} and isinstance(provs["openai"], CodexCliProvider) and skipped == [])
    p = provs["openai"]
    cap = p.capabilities(CODEX)
    check("02 declared capabilities: invocable, tool-less for ATLAS, nothing unverified guessed",
          p.models() == [CODEX] and cap.executable_from_atlas is True and cap.supports_tools is False
          and cap.supports_multimodal is None and cap.context_tier == "UNKNOWN" and cap.cost_tier == "configured_free"
          and cap.strengths == ("coding", "analysis"))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW"), log_decision=False)
    check("03 registered but NOT silently routable: with no health signal the router excludes it and routing is unchanged",
          CODEX in r["excluded"] and "health=UNKNOWN" in " ".join(r["excluded"][CODEX]) and r["selected"] in (SONNET, OPUS))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW"), health_overrides={CODEX: "AVAILABLE"}, log_decision=False)
    check("04 given a real AVAILABLE signal it becomes eligible (registry integration works end to end)",
          CODEX not in r["excluded"] and (r["selected"] == CODEX or CODEX in [a if isinstance(a, str) else a.get("model") for a in r["alternatives"]]))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW", tool_requirements=["bash"]), health_overrides={CODEX: "AVAILABLE"}, log_decision=False)
    check("05 NEGATIVE: a task that needs ATLAS tools excludes it (it has none)", CODEX in r["excluded"] and "required tools unsupported" in " ".join(r["excluded"][CODEX]))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="HIGH"), health_overrides={CODEX: "AVAILABLE"}, log_decision=False)
    check("06 NEGATIVE: HIGH risk is outside its eligible_risks", CODEX in r["excluded"] and "eligible_risks" in " ".join(r["excluded"][CODEX]))
    r = route(TaskRequirements(task_class="CODE", complexity="MEDIUM", risk="LOW"), health_overrides={CODEX: "TIMEOUT"}, log_decision=False)
    check("07 NEGATIVE: a TIMEOUT / failure health state excludes it", CODEX in r["excluded"])


# --------------------------------------------------------------------------- B. containment
def test_containment():
    rn = Runner(ok_outcome())
    p = provider(rn, environ={"PATH": "/bin", "CODEX_HOME": "/h", "OPENAI_API_KEY": "sk-x", "GITHUB_TOKEN": "t", "MY_SECRET": "s", "DB_PASSWORD": "p", "AWS_CREDENTIAL_X": "c"})
    prompt = "Explain quicksort in two lines."
    res = invoke(p, request(prompt))
    c = rn.calls[0]
    argv = c["argv"]
    need = ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--json"]
    check("08 argv carries every containment flag and ends with '-' (stdin prompt)",
          all(x in argv for x in need) and argv[argv.index("--sandbox") + 1] == "read-only" and argv[-1] == "-" and argv[0] == "fake-codex")
    bad = [a for a in argv if a.startswith("--dangerously") or a in ("--full-auto", "--add-dir", "-c", "--config", "--oss", "--yolo")]
    check("09 NEGATIVE: no sandbox bypass, no config override, no extra writable dirs in argv", not bad, str(bad))
    check("10 the prompt travels on stdin and never appears in argv", c["stdin"] == prompt and not any(prompt in a for a in argv))
    check("11 it runs in a private EMPTY directory that is removed afterwards",
          c["cwd_existed"] and c["cwd_files"] == [] and not os.path.exists(c["cwd"]) and argv[argv.index("--cd") + 1] == c["cwd"])
    env = c["env"]
    check("12 the child environment is scrubbed of key/token/secret/password/credential names but keeps what Codex needs",
          set(env) == {"PATH", "CODEX_HOME"}, str(sorted(env)))
    check("13 the result was a clean success through invoke()", res.ok and res.text == "PONG")
    reg = mr.load_registry()
    reg["models"][CODEX]["codex_model"] = "gpt-test"
    rn2 = Runner(ok_outcome())
    invoke(provider(rn2, registry=reg), request())
    a2 = rn2.calls[0]["argv"]
    check("14 a model flag is passed only when the registry sets codex_model", "-m" in a2 and a2[a2.index("-m") + 1] == "gpt-test" and "-m" not in argv)
    exists = lambda path: path.endswith("codex.js")
    which = lambda name: {"codex": "/npm/codex.CMD", "node": "/usr/bin/node"}.get(name)
    check("15 command resolution prefers 'node codex.js' over the .cmd shim (no shell)", cx.resolve_command(which, exists) == ["/usr/bin/node", os.path.join("/npm", "node_modules", "@openai", "codex", "bin", "codex.js")])
    check("16 ... falls back to the shim, and to None when codex is absent",
          cx.resolve_command(which, lambda _: False) == ["/npm/codex.CMD"] and cx.resolve_command(lambda n: None, exists) is None)


# --------------------------------------------------------------------------- C. parsing real outputs
def test_parsing():
    r = invoke(provider(Runner(ok_outcome())), request())
    check("17 success (rc 0 + turn.completed): ok, text, AVAILABLE hint -- stderr noise is not a failure",
          r.ok and r.text == "PONG" and r.error_class == "NONE" and r.health_hint == "AVAILABLE")
    truncated = jl({"type": "turn.started"}, {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "PONG"}})
    r = invoke(provider(Runner(cx.RunOutcome(0, truncated, ""))), request())
    check("18 rc 0 with answer text but NO completed turn (truncated stream) is INVALID_RESPONSE, not success",
          r.error_class == "INVALID_RESPONSE" and not r.ok)
    r = invoke(provider(Runner(cx.RunOutcome(1, OK_STDOUT, ""))), request())
    check("18b a completed turn with a non-zero exit code is a failure, not a success", not r.ok and r.error_class != "NONE")
    r = invoke(provider(Runner(cx.RunOutcome(0, jl({"type": "turn.completed", "usage": {}}), ""))), request())
    check("19 a completed turn with no answer text is not success", not r.ok and r.error_class == "INVALID_RESPONSE")
    r = invoke(provider(Runner(cx.RunOutcome(1, BAD_MODEL_STDOUT, ""))), request())
    check("20 REAL capture: nonexistent model -> MODEL_UNAVAILABLE", r.error_class == "MODEL_UNAVAILABLE" and r.health_hint == "MODEL_UNAVAILABLE")
    r = invoke(provider(Runner(cx.RunOutcome(1, NOAUTH_STDOUT, ""))), request())
    check("21 REAL capture: no login (10 transient reconnects, then 401) -> AUTH_FAILED", r.error_class == "AUTH_FAILED" and r.health_hint == "AUTH_FAILED")
    ev = cx.parse_events(NOAUTH_STDOUT)
    check("22 transient 'Reconnecting...' errors are not taken as the final failure", ev["failed_message"] == FINAL_401 and all(not e.startswith("Reconnecting") for e in ev["errors"]))
    r = invoke(provider(Runner(cx.RunOutcome(1, jl({"type": "error", "message": RECONNECT.format(n=1)}), "boom"))), request())
    check("23 only transient errors and rc 1: classified from stderr as unknown, never AVAILABLE", not r.ok and r.health_hint != "AVAILABLE")
    quota = jl({"type": "turn.failed", "error": {"message": "You've hit your usage limit. Try again later."}})      # SYNTHETIC wording
    rate = jl({"type": "turn.failed", "error": {"message": json.dumps({"type": "error", "status": 429, "error": {"message": "slow down"}})}})   # SYNTHETIC wording
    check("24 SYNTHETIC (not observed live): usage-limit text -> QUOTA_EXHAUSTED",
          invoke(provider(Runner(cx.RunOutcome(1, quota, ""))), request()).error_class == "QUOTA_EXHAUSTED")
    check("25 SYNTHETIC (not observed live): HTTP 429 inside the error JSON -> RATE_LIMITED",
          invoke(provider(Runner(cx.RunOutcome(1, rate, ""))), request()).error_class == "RATE_LIMITED")
    r = invoke(provider(Runner(cx.RunOutcome(None, "", "", True))), request())
    check("26 a killed (timed-out) run is TIMEOUT", r.error_class == "TIMEOUT" and r.health_hint == "TIMEOUT")
    r = invoke(provider(Runner(cx.RunOutcome(1, "garbage", "Not logged in"))), request())
    check("27 no JSON at all: stderr text still classifies (Not logged in -> AUTH_FAILED)", r.error_class == "AUTH_FAILED")


# --------------------------------------------------------------------------- D. policy
def test_policy():
    rn = Runner(ok_outcome())
    p = provider(rn)
    secrets = {"private key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE", "aws": "key AKIAABCDEFGHIJKLMNOP here", "github": "ghp_" + "a" * 36,
               "sk": "use sk-" + "A1b2C3d4" * 4, "slack": "xoxb-1234567890-abcdef", "google": "AIza" + "B" * 35}
    res = {k: invoke(p, request(v)) for k, v in secrets.items()}
    check("28 prompts containing credentials are refused and nothing is spawned",
          all(r.error_class == "POLICY_BLOCKED" for r in res.values()) and rn.calls == [], str({k: r.error_class for k, r in res.items()}))
    check("29 empty and oversized prompts are refused", invoke(p, request("   ")).error_class == "POLICY_BLOCKED"
          and invoke(p, request("x" * (cx.MAX_PROMPT_CHARS + 1))).error_class == "POLICY_BLOCKED" and rn.calls == [])
    r = invoke(provider(Runner(ok_outcome())), request("Explain what a bearer token and a secret handshake are in networking."))
    check("30 NEGATIVE CONTROL: ordinary prose that mentions 'token'/'secret' is not blocked (no false positive)", r.ok)
    rn = Runner(ok_outcome())
    r = invoke(provider(rn, resolver=lambda: None), request())
    check("31 codex missing from PATH: MODEL_UNAVAILABLE and nothing is spawned", r.error_class == "MODEL_UNAVAILABLE" and rn.calls == [])


# --------------------------------------------------------------------------- E. health
def test_health():
    p = provider(SmartRunner(), resolver=lambda: None)
    check("32 health: CLI missing -> MODEL_UNAVAILABLE", p.health().state == "MODEL_UNAVAILABLE")
    h = provider(SmartRunner(NOT_LOGGED_IN)).health()
    check("33 health: not logged in -> AUTH_FAILED", h.state == "AUTH_FAILED" and h.source == "login_status")
    rn = SmartRunner(LOGGED_IN)
    clock = Clock()
    p = provider(rn, clock=clock)
    h = p.health()
    check("34 HONESTY: logged in is NOT available -> UNKNOWN until a real round trip", h.state == "UNKNOWN" and "probe()" in h.reason and rn.exec_calls == [])
    p.health()
    check("35 the login check is cached (one `login status` call for two health() calls)", rn.login_calls == 1)
    clock.t += cx.LOGIN_CACHE_SECONDS + 1
    p.health()
    check("35b ... and refreshed once its cache window passes", rn.login_calls == 2)

    rn = SmartRunner(LOGGED_IN, ok_outcome())
    clock = Clock()
    p = provider(rn, clock=clock)
    res = invoke(p, request())
    h = p.health()
    check("36 after a successful request health is AVAILABLE (source: recent round trip)", res.ok and h.state == "AVAILABLE" and h.source == "recent_round_trip")
    clock.t += cx.SUCCESS_TTL_SECONDS + 1
    check("37 AVAILABLE expires: after the TTL health is UNKNOWN again (logged in, no recent round trip)", p.health().state == "UNKNOWN")

    fail = cx.RunOutcome(1, jl({"type": "turn.failed", "error": {"message": "429 Too Many Requests"}}), "")      # SYNTHETIC wording
    clock = Clock()
    p = provider(SmartRunner(LOGGED_IN, fail), clock=clock)
    invoke(p, request())
    first = p.health().state
    clock.t += cx.FAILURE_TTL_SECONDS + 1
    check("38 SYNTHETIC wording: after a rate-limit failure health is RATE_LIMITED, then UNKNOWN once the failure TTL passes",
          first == "RATE_LIMITED" and p.health().state == "UNKNOWN", f"{first} -> {p.health().state}")

    rn = SmartRunner(LOGGED_IN, ok_outcome())
    check("39 probe(): one real round trip is the way to AVAILABLE", provider(rn).probe().state == "AVAILABLE" and len(rn.exec_calls) == 1)
    other = ok_outcome("something else", stdout=OK_STDOUT.replace("PONG", "something else"))
    check("40 probe() with an unexpected answer is DEGRADED, not AVAILABLE", provider(SmartRunner(LOGGED_IN, other)).probe().state == "DEGRADED")
    h = provider(SmartRunner(LOGGED_IN, cx.RunOutcome(1, NOAUTH_STDOUT, ""))).probe()
    check("41 a failed probe wins over 'logged in': the observed failure is reported (login says yes, the round trip says 401)",
          h.state == "AUTH_FAILED" and h.source == "recent_round_trip")
    check("42 health for a model it does not serve is MODEL_UNAVAILABLE", provider(SmartRunner()).health("x/y").state == "MODEL_UNAVAILABLE")
    reg = mr.load_registry()
    reg["providers"]["openai"]["enabled"] = False
    pd = provider(SmartRunner(), registry=reg)
    check("43 disabled provider: no models and health UNKNOWN", pd.models() == [] and pd.health().state == "UNKNOWN")


# --------------------------------------------------------------------------- F. process handling
def alive(pid):
    if os.name == "nt":
        # Bytes + CSV: tasklist's text is localized (and PYTHONUTF8=1 in the runner cannot decode it); a quoted
        # CSV field also avoids the substring trap (PID 12 matching 123).
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True).stdout or b""
        return f'"{pid}"'.encode() in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_processes():
    def hang(argv, stdin_text, env, cwd, timeout_s, on_start=None):
        time.sleep(2.0)
        return cx.RunOutcome(0, OK_STDOUT, "")
    t0 = time.perf_counter()
    r = invoke(provider(hang), request(timeout=0.3))
    check("44 backstop: a runner that hangs is cut off by invoke() at the request timeout", r.error_class == "TIMEOUT" and time.perf_counter() - t0 < 1.5)

    killed = []
    real_kill = cx.kill_tree
    cx.kill_tree = lambda proc: killed.append(proc.pid)
    try:
        p = provider(None)
        holder = {}

        def slow(argv, stdin_text, env, cwd, timeout_s, on_start=None):
            fake = type("P", (), {"pid": 4242})()
            on_start(fake)
            holder["registered"] = p.cancel("q-cancel")
            return cx.RunOutcome(0, OK_STDOUT, "")
        p._runner = slow
        invoke(p, request(rid="q-cancel"))
        gone = p.cancel("q-cancel")
    finally:
        cx.kill_tree = real_kill
    check("45 cancel() kills the registered process tree while running, and is a no-op afterwards", holder.get("registered") is True and killed == [4242] and gone is False)

    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    check("45b the liveness helper itself is sound: this process is alive, a reaped child is not",
          alive(os.getpid()) is True and alive(dead.pid) is False)

    code = ("import subprocess, sys, time\n"
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(c.pid, flush=True)\n"
            "time.sleep(60)\n")
    t0 = time.perf_counter()
    out = cx.default_runner([sys.executable, "-c", code], "", dict(os.environ), tempfile.gettempdir(), 1.5)
    dt = time.perf_counter() - t0
    child = int((out.stdout.split() or ["0"])[0])
    time.sleep(0.5)
    check("46 real timeout: the process AND its child are killed (no orphan)", out.timed_out and child > 0 and not alive(child) and dt < 15, f"child pid {child}, {dt:.1f}s")


# --------------------------------------------------------------------------- G. source guards
def test_source():
    src = (PROJECT_ROOT / "core" / "providers" / "codex_cli.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported, bad_calls, shell_kw = set(), [], False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (f"{fn.value.id}.{fn.attr}" if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) else "")
            if name in ("eval", "exec", "os.system", "os.popen", "__import__", "compile"):
                bad_calls.append(name)
            for kw in node.keywords:
                if kw.arg == "shell" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                    shell_kw = True
    allowed = {"json", "os", "re", "shutil", "signal", "subprocess", "tempfile", "threading", "time", "dataclasses", "typing", "__future__"}
    check("47 codex_cli imports only process-handling stdlib: no network, pickle, ctypes", imported <= allowed, str(sorted(imported - allowed)))
    check("48 no shell=True, no eval/exec/system anywhere in the adapter", not bad_calls and not shell_kw)
    check("49 the dangerous flags appear nowhere in the adapter source", "--dangerously" not in src and "--full-auto" not in src and "--yolo" not in src)


# --------------------------------------------------------------------------- H. live (opt-in)
def test_live():
    print("\n-- LIVE (real codex binary; spends a few tiny requests of the owner's Codex allowance) --")
    p = CodexCliProvider(mr.load_registry())
    cmd = cx.resolve_command()
    if not cmd:
        check("L0 codex is installed", False, "not found")
        return
    h = p.health()
    check("L1 health: logged in -> UNKNOWN (not AVAILABLE before any round trip)", h.state in ("UNKNOWN", "AVAILABLE"), f"{h.state}: {h.reason}")
    if h.state == "AUTH_FAILED":
        check("L2 live round trip skipped: not logged in", False, h.reason)
        return
    h = p.probe(timeout_s=90)
    check("L2 probe(): a real round trip returns PONG and health becomes AVAILABLE", h.state == "AVAILABLE", f"{h.state}: {h.reason}")
    reg = mr.load_registry()
    reg["models"][CODEX]["codex_model"] = "definitely-not-a-real-model-xyz"
    r = invoke(CodexCliProvider(reg), request("Reply with PONG.", timeout=60))
    check("L3 nonexistent model -> MODEL_UNAVAILABLE (real)", r.error_class == "MODEL_UNAVAILABLE", f"{r.error_class}: {r.error_detail[:80]}")
    empty = tempfile.mkdtemp(prefix="cx_empty_home_")
    r = invoke(CodexCliProvider(mr.load_registry(), environ={**os.environ, "CODEX_HOME": empty}), request("Reply with PONG.", timeout=60))
    check("L4 no credentials (empty CODEX_HOME) -> AUTH_FAILED (real, ~18 s of internal retries)", r.error_class == "AUTH_FAILED", f"{r.error_class}: {r.error_detail[:80]}")
    pids = []
    orig = cx.default_runner

    def spy(argv, stdin_text, env, cwd, timeout_s, on_start=None):
        return orig(argv, stdin_text, env, cwd, timeout_s, lambda pr: (pids.append(pr.pid), on_start and on_start(pr)))
    t0 = time.perf_counter()
    r = invoke(CodexCliProvider(mr.load_registry(), runner=spy), request("Write a 400 word essay about the history of computing.", timeout=1.5))
    time.sleep(1.0)
    check("L5 a 1.5 s timeout on a real run -> TIMEOUT and the whole process tree is gone", r.error_class == "TIMEOUT" and pids and not alive(pids[0]),
          f"{time.perf_counter() - t0:.1f}s, pid {pids}")


def main():
    live = "--live" in sys.argv
    print("=" * 60)
    print("Bloque F42 -- Codex CLI provider" + (" [LIVE]" if live else ""))
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_registry, test_containment, test_parsing, test_policy, test_health, test_processes, test_source):
        print(f"\n-- {fn.__name__} --")
        fn()
    if live:
        test_live()
    else:
        print("\n(live cases skipped: pass --live to drive the real codex binary)")
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
