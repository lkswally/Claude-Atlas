"""
Codex CLI provider (roadmap P5): the first provider ATLAS can actually INVOKE (executable_from_atlas = True).

Why this one: the only other-vendor tool already installed and logged in on this machine (`codex login status` ->
"Logged in using ChatGPT"); no new credential, no per-token spend (the owner's existing ChatGPT plan allowance).
The shapes below were captured from real runs on codex-cli 0.147.0, not assumed:

    success   rc 0   thread.started, turn.started, item.completed(agent_message), turn.completed(usage)
              (stderr may carry unrelated ERROR log lines -- stderr is NOT a failure signal)
    bad model rc 1   turn.failed {"status":400,"error":{"code":"model_not_found", ...}}
    no login  rc 1   ~18 s of "Reconnecting... n/5 (401 Unauthorized ...)" events, then failure

Containment (this runs an agent binary, so it is locked down, not trusted):
  * argv list, never a shell; the prompt goes on STDIN (not argv); no -c overrides
  * --sandbox read-only, --ephemeral, --ignore-user-config, --ignore-rules, --skip-git-repo-check, --json
  * working dir is a private EMPTY temp dir; the last-message file lives there too and is removed
  * environment is scrubbed of anything named like a key/token/secret/password/credential
  * obvious secrets in the prompt are refused before anything is spawned (heuristic, not a guarantee)
  * timeouts kill the whole process tree (node wrapper + native child), not just the wrapper
Data sent in a prompt goes to OpenAI: callers must not put credentials or regulated data in it.

Health is a real signal or UNKNOWN: "logged in" (a fast local check) is NOT "available". AVAILABLE needs a recent
successful round trip (probe() or any successful execute()); failures are remembered for a short TTL.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ._registry_backed import RegistryBackedProvider
from .base import (
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderHealth,
    classify_failure,
    invoke,
)

MAX_PROMPT_CHARS = 200_000
MAX_OUTPUT_CHARS = 262_144
SUCCESS_TTL_SECONDS = 600.0
FAILURE_TTL_SECONDS = 120.0
LOGIN_CACHE_SECONDS = 60.0
PROBE_PROMPT = "Reply with exactly the word PONG and nothing else."

_SECRET_ENV = re.compile(r"(?i)(key|token|secret|password|credential)")
_SECRET_PROMPT = [re.compile(p) for p in (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bghp_[A-Za-z0-9]{30,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bsk-[A-Za-z0-9_-]{20,}\b",
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
    r"\bAIza[0-9A-Za-z_-]{35}\b",
)]
_TRANSIENT = re.compile(r"^\s*Reconnecting\.\.\.\s*\d+/\d+", re.I)


@dataclass
class RunOutcome:
    returncode: Optional[int]          # None when we killed it
    stdout: str
    stderr: str
    timed_out: bool = False


# ------------------------------------------------------------------ process handling
def kill_tree(proc: "subprocess.Popen[str]") -> None:
    """Kill the process AND its children. The npm wrapper (node) spawns the native codex binary; killing only
    the wrapper would leave the real work running."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def default_runner(argv: Sequence[str], stdin_text: str, env: Mapping[str, str], cwd: str, timeout_s: float,
                   on_start: Optional[Callable[["subprocess.Popen[str]"], None]] = None) -> RunOutcome:
    kwargs: Dict[str, Any] = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  encoding="utf-8", errors="replace", env=dict(env), cwd=cwd)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(list(argv), **kwargs)
    if on_start:
        on_start(proc)
    try:
        out, err = proc.communicate(stdin_text, timeout=timeout_s)
        return RunOutcome(proc.returncode, out or "", err or "")
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except Exception:  # noqa: BLE001
            out, err = "", ""
        return RunOutcome(None, out or "", err or "", True)


def resolve_command(which: Callable[[str], Optional[str]] = shutil.which,
                    exists: Callable[[str], bool] = os.path.exists) -> Optional[List[str]]:
    """argv prefix to launch Codex. Prefer `node <pkg>/bin/codex.js` over the .cmd/.ps1 shim so no shell is involved."""
    exe = which("codex")
    if not exe:
        return None
    base = os.path.dirname(exe)
    js = os.path.join(base, "node_modules", "@openai", "codex", "bin", "codex.js")
    node = which("node")
    if node and exists(js):
        return [node, js]
    return [exe]


def scrubbed_env(environ: Mapping[str, str]) -> Dict[str, str]:
    return {k: v for k, v in environ.items() if not _SECRET_ENV.search(k)}


def parse_events(stdout: str) -> Dict[str, Any]:
    """Facts from `codex exec --json` output. Transient 'Reconnecting...' errors are not final failures."""
    completed, last_text, failed_msg, errors = False, "", "", []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        t = ev.get("type")
        if t == "turn.completed":
            completed = True
        elif t == "turn.failed":
            failed_msg = str((ev.get("error") or {}).get("message") or "")
        elif t == "error":
            msg = str(ev.get("message") or "")
            if msg and not _TRANSIENT.match(msg):
                errors.append(msg)
        elif t == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                last_text = item["text"]
    return {"completed": completed, "text": last_text, "failed_message": failed_msg, "errors": errors}


# ------------------------------------------------------------------ the provider
class CodexCliProvider(RegistryBackedProvider):
    KIND = "cli_subprocess"
    EXECUTABLE_FROM_ATLAS = True

    def __init__(self, registry: Mapping[str, Any], provider_id: str = "openai", *,
                 runner: Callable[..., RunOutcome] = default_runner,
                 resolver: Callable[[], Optional[List[str]]] = resolve_command,
                 environ: Optional[Mapping[str, str]] = None,
                 clock: Callable[[], float] = time.monotonic):
        super().__init__(registry, provider_id)
        self._runner, self._resolver, self._clock = runner, resolver, clock
        self._environ = environ if environ is not None else os.environ
        self._obs: Optional[Tuple[str, str, float]] = None       # (state, reason, at) from a real round trip
        self._login: Optional[Tuple[bool, str, float]] = None    # cached `codex login status`
        self._procs: Dict[str, "subprocess.Popen[str]"] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------- health (real signal or UNKNOWN)
    def _login_status(self, cmd: List[str]) -> Tuple[bool, str]:
        now = self._clock()
        if self._login and now - self._login[2] < LOGIN_CACHE_SECONDS:
            return self._login[0], self._login[1]
        workdir = tempfile.mkdtemp(prefix="atlas_codex_login_")
        try:
            out = self._runner(cmd + ["login", "status"], "", scrubbed_env(self._environ), workdir, 20.0)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        text = (out.stdout or "") + " " + (out.stderr or "")
        ok = (not out.timed_out) and out.returncode == 0 and "logged in" in text.lower() and "not logged in" not in text.lower()
        reason = "codex login status: logged in" if ok else ("codex login status timed out" if out.timed_out else "codex login status: not logged in")
        self._login = (ok, reason, now)
        return ok, reason

    def health(self, model_id: Optional[str] = None) -> ProviderHealth:
        if not self._enabled():
            return ProviderHealth("UNKNOWN", "provider disabled or absent in config", "config")
        if model_id is not None and model_id not in self.models():
            return ProviderHealth("MODEL_UNAVAILABLE", f"{model_id} is not an enabled model of {self.id}", "config")
        cmd = self._resolver()
        if not cmd:
            return ProviderHealth("MODEL_UNAVAILABLE", "codex CLI not found on PATH", "executable")
        logged_in, why = self._login_status(cmd)
        if not logged_in:
            return ProviderHealth("AUTH_FAILED", why, "login_status")
        now = self._clock()
        if self._obs:
            state, reason, at = self._obs
            ttl = SUCCESS_TTL_SECONDS if state == "AVAILABLE" else FAILURE_TTL_SECONDS
            if now - at < ttl:
                return ProviderHealth(state, reason, "recent_round_trip")
        return ProviderHealth("UNKNOWN", "logged in, but no recent round trip: call probe() for a real signal", "login_status")

    def _observe(self, state: str, reason: str) -> None:
        self._obs = (state, reason, self._clock())

    def probe(self, model_id: Optional[str] = None, timeout_s: float = 60.0) -> ProviderHealth:
        """One tiny real request (costs a little of the owner's Codex allowance). The only way to reach AVAILABLE."""
        mid = model_id or (self.models()[0] if self.models() else "")
        res = invoke(self, ProviderExecutionRequest(f"probe-{int(self._clock() * 1000)}", mid, PROBE_PROMPT, timeout_s=timeout_s))
        if res.ok and "PONG" in res.text.upper():
            self._observe("AVAILABLE", "probe round trip succeeded")
        elif res.ok:
            self._observe("DEGRADED", "probe returned an unexpected answer")
        else:
            self._observe(res.health_hint or "UNKNOWN", f"probe failed: {res.error_class}")
        return self.health(mid)

    # -------------------------------------------------------- execution
    def _argv(self, cmd: List[str], workdir: str, outfile: str, model_flag: Optional[str]) -> List[str]:
        argv = cmd + ["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral",
                      "--ignore-user-config", "--ignore-rules", "--json", "--cd", workdir, "-o", outfile]
        if model_flag:
            argv += ["-m", model_flag]
        return argv + ["-"]                       # prompt is read from stdin

    def _fail(self, req: ProviderExecutionRequest, klass: str, detail: str, hint: Optional[str], t0: float) -> ProviderExecutionResult:
        return ProviderExecutionResult(req.request_id, self.id, req.model_id, False, klass, "", detail[:500],
                                       round((self._clock() - t0) * 1000, 3), hint)

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        t0 = self._clock()
        prompt = request.prompt if isinstance(request.prompt, str) else ""
        if not prompt.strip():
            return self._fail(request, "POLICY_BLOCKED", "empty prompt", None, t0)
        if len(prompt) > MAX_PROMPT_CHARS:
            return self._fail(request, "POLICY_BLOCKED", f"prompt larger than {MAX_PROMPT_CHARS} characters", None, t0)
        if any(p.search(prompt) for p in _SECRET_PROMPT):
            return self._fail(request, "POLICY_BLOCKED", "prompt appears to contain a credential or private key; not sent", None, t0)
        cmd = self._resolver()
        if not cmd:
            return self._fail(request, "MODEL_UNAVAILABLE", "codex CLI not found on PATH", "MODEL_UNAVAILABLE", t0)

        cfg = self._model_cfg(request.model_id) or {}
        model_flag = cfg.get("codex_model") if isinstance(cfg.get("codex_model"), str) else None
        workdir = tempfile.mkdtemp(prefix="atlas_codex_")             # private, empty
        outfile = os.path.join(workdir, "last_message.txt")
        argv = self._argv(cmd, workdir, outfile, model_flag)

        def on_start(proc: "subprocess.Popen[str]") -> None:
            with self._lock:
                self._procs[request.request_id] = proc

        try:
            outcome = self._runner(argv, prompt, scrubbed_env(self._environ), workdir, max(1.0, request.timeout_s * 0.9), on_start)
            last_file = ""
            try:
                with open(outfile, encoding="utf-8", errors="replace") as f:
                    last_file = f.read()
            except OSError:
                pass
        finally:
            with self._lock:
                self._procs.pop(request.request_id, None)
            shutil.rmtree(workdir, ignore_errors=True)

        if outcome.timed_out:
            self._observe("TIMEOUT", "request timed out")
            return self._fail(request, "TIMEOUT", f"no answer within {request.timeout_s}s; process tree killed", "TIMEOUT", t0)
        ev = parse_events(outcome.stdout)
        text = (last_file or ev["text"]).strip()
        if outcome.returncode == 0 and ev["completed"] and text:
            self._observe("AVAILABLE", "last request succeeded")
            return ProviderExecutionResult(request.request_id, self.id, request.model_id, True, "NONE", text[:MAX_OUTPUT_CHARS], "",
                                           round((self._clock() - t0) * 1000, 3), "AVAILABLE")
        message = ev["failed_message"] or (ev["errors"][-1] if ev["errors"] else "") or (outcome.stderr or "").strip()[-400:]
        if outcome.returncode == 0:
            return self._fail(request, "INVALID_RESPONSE", "exit 0 without a completed turn or answer text", "DEGRADED", t0)
        status = None
        try:                                       # the error message is usually itself a JSON document
            inner = json.loads(message)
            if isinstance(inner, dict) and isinstance(inner.get("status"), int):
                status = inner["status"]
        except ValueError:
            pass
        state, klass = classify_failure(status_code=status, message=message)
        self._observe(state, f"last request failed: {klass}")
        return self._fail(request, klass, message or f"exit code {outcome.returncode}", state, t0)

    def cancel(self, request_id: str) -> bool:
        with self._lock:
            proc = self._procs.get(request_id)
        if proc is None:
            return False
        kill_tree(proc)
        return True

    def status(self) -> Dict[str, Any]:
        cmd = self._resolver()
        return {"id": self.id, "kind": self.KIND, "enabled": self._enabled(), "models": self.models(),
                "executable_from_atlas": True, "cli_found": bool(cmd)}
