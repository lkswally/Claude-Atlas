#!/usr/bin/env python3
"""
Model-routing enforcement lab (roadmap P3) -- LAB ONLY, not wired into ATLAS.

Question: can a Claude Code PreToolUse hook on the `Agent` tool mechanically force the model a subagent runs on?
Documented: a PreToolUse hook may return hookSpecificOutput.updatedInput (replaces the tool input). NOT documented:
whether a rewritten `model` is honored. This lab answers it by running the real binary in an isolated, hook-only
settings scope and reading the RUNTIME's own evidence.

Rule that makes the verdict honest (and is enforced by classify(), unit-tested in F39/F40):
  The verdict is derived ONLY from the stream-json the runtime emits -- the `model` field of the subagent's own
  assistant messages. What the hook says it did (its log, its JSON) can never produce ENFORCEMENT_PROVEN; it is only
  used to tell "rewrite ignored" (UNSUPPORTED) from "hook never ran" (UNKNOWN).

Verdicts: ENFORCEMENT_PROVEN | ENFORCEMENT_UNSUPPORTED | ENFORCEMENT_UNKNOWN (incl. BLOCKED: authentication required).

CLI:  python enforcement_lab.py run <label> <parent_model> <LAB_MODE> [--out DIR]
      python enforcement_lab.py matrix [--out DIR]          # R0 control, R1 sonnet->opus, R2 opus->sonnet
Env:  ATLAS_LAB_CLAUDE_BIN (path to claude binary), ATLAS_LAB_CLAUDE_CONFIG_DIR (isolated, logged-in config dir)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
AGENT_TOOL_NAMES = ("Agent", "Task")
FAMILIES = ("opus", "sonnet", "haiku")
PROMPT = ('Call the Agent tool exactly once with subagent_type "general-purpose", description "lab ping" and prompt '
          '"Reply with exactly the word PONG and nothing else.". After it returns, reply with the single word DONE. '
          'Do not use any other tool.')


# ------------------------------------------------------------------ evidence (pure, offline-testable)
def family(model: Optional[str]) -> Optional[str]:
    m = (model or "").lower()
    hits = [f for f in FAMILIES if f in m]
    return hits[0] if len(hits) == 1 else None


def _events(stream_text: str) -> List[Dict[str, Any]]:
    out = []
    for line in (stream_text or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict):
                out.append(ev)
    return out


def extract_evidence(stream_text: str) -> Dict[str, Any]:
    """Facts the RUNTIME reported. Never reads hook output."""
    evs = _events(stream_text)
    sub, par, agent_inputs = [], [], []
    for ev in evs:
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message") or {}
        model = msg.get("model")
        if model and model != "<synthetic>":
            (sub if ev.get("parent_tool_use_id") else par).append(model)
        for blk in msg.get("content") or []:
            if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") in AGENT_TOOL_NAMES:
                agent_inputs.append(blk.get("input") or {})
    result = next((e for e in reversed(evs) if e.get("type") == "result"), {})
    text = str(result.get("result") or "")
    blocked = bool(result.get("is_error")) and ("Not logged in" in text or "/login" in text)
    return {
        "blocked_auth": blocked,
        "parent_models": sorted(set(par)),
        "subagent_models": sorted(set(sub)),
        "agent_calls": len(agent_inputs),
        "requested_model_in_call": [i.get("model") for i in agent_inputs],
        "model_usage": sorted((result.get("modelUsage") or {}).keys()),
        "result_error": bool(result.get("is_error")),
    }


def case_view(evidence: Dict[str, Any], hook_emitted: bool) -> Dict[str, Any]:
    pf = {family(m) for m in evidence.get("parent_models", [])} - {None}
    sf = {family(m) for m in evidence.get("subagent_models", [])} - {None}
    return {
        "parent_family": next(iter(pf)) if len(pf) == 1 else None,
        "subagent_family": next(iter(sf)) if len(sf) == 1 else None,
        "spawned": evidence.get("agent_calls", 0) >= 1 and bool(evidence.get("subagent_models")),
        "blocked_auth": evidence.get("blocked_auth", False),
        "hook_emitted": hook_emitted,
    }


def classify(control_sonnet: Dict[str, Any], control_opus: Dict[str, Any],
             to_opus: Dict[str, Any], to_sonnet: Dict[str, Any]) -> Dict[str, str]:
    """Four case_view() dicts, all from the same prompt:
      control_sonnet = log_only hook, sonnet parent      (what a subagent gets by default under a sonnet parent)
      control_opus   = log_only hook, opus parent        (default under an opus parent)
      to_opus        = rewrite->opus, sonnet parent
      to_sonnet      = rewrite->sonnet, opus parent
    A direction is PROVEN only if the rewritten subagent model differs from ITS OWN no-rewrite control, so a model that
    is simply the default (or inherited) can never be mistaken for enforcement."""
    cases = {"control_sonnet": control_sonnet, "control_opus": control_opus, "to_opus": to_opus, "to_sonnet": to_sonnet}
    if any(c["blocked_auth"] for c in cases.values()):
        return {"verdict": "ENFORCEMENT_UNKNOWN", "reason": "BLOCKED: the binary is not authenticated (EXTERNALLY_BLOCKED)"}
    missing = [k for k, c in cases.items() if not c["spawned"] or c["subagent_family"] is None or c["parent_family"] is None]
    if missing:
        return {"verdict": "ENFORCEMENT_UNKNOWN", "reason": f"no usable runtime evidence for: {', '.join(missing)}"}
    honored_up = to_opus["subagent_family"] == "opus" and control_sonnet["subagent_family"] != "opus"
    honored_down = to_sonnet["subagent_family"] == "sonnet" and control_opus["subagent_family"] != "sonnet"
    if honored_up and honored_down:
        return {"verdict": "ENFORCEMENT_PROVEN",
                "reason": "subagent assistant `model` followed the rewrite in both directions and differs from each no-rewrite control"}
    ignored_up = to_opus["subagent_family"] == control_sonnet["subagent_family"]
    ignored_down = to_sonnet["subagent_family"] == control_opus["subagent_family"]
    if to_opus["hook_emitted"] and to_sonnet["hook_emitted"] and ignored_up and ignored_down:
        return {"verdict": "ENFORCEMENT_UNSUPPORTED",
                "reason": "the hook emitted rewrites but the subagent model equals its no-rewrite control in both directions"}
    return {"verdict": "ENFORCEMENT_UNKNOWN",
            "reason": "mixed or partial evidence (one direction honored, the hook did not run, or the result is not attributable to it)"}


# ------------------------------------------------------------------ running the real binary
def find_claude_bin() -> Optional[str]:
    env = os.environ.get("ATLAS_LAB_CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Claude-Data"
    cands = sorted(base.glob("*/claude-code/*/*/claude.exe"), key=lambda p: p.stat().st_mtime, reverse=True) if base.exists() else []
    return str(cands[0]) if cands else None


def run_case(label: str, parent: str, mode: str, out: Path, hooks: bool = True, timeout: int = 300) -> Dict[str, Any]:
    exe = find_claude_bin()
    if not exe:
        raise SystemExit("claude binary not found; set ATLAS_LAB_CLAUDE_BIN")
    out.mkdir(parents=True, exist_ok=True)
    hook_log = out / f"{label}.hook.jsonl"
    hook_log.unlink(missing_ok=True)
    settings = out / "settings.generated.json"
    cmd_line = f'"{sys.executable}" "{HERE / "hook_lab.py"}"'
    entry = [{"matcher": "Agent|Task", "hooks": [{"type": "command", "command": cmd_line, "timeout": 20}]}]
    settings.write_text(json.dumps({"hooks": {"PreToolUse": entry, "PostToolUse": entry}}), encoding="utf-8")
    cmd = [exe, "-p", PROMPT, "--model", parent, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
           "--allowedTools", "Agent", "--disable-slash-commands"]
    if hooks:
        cmd += ["--settings", str(settings)]
    env = dict(os.environ, LAB_MODE=mode, LAB_LOG=str(hook_log))
    if os.environ.get("ATLAS_LAB_CLAUDE_CONFIG_DIR"):
        env["CLAUDE_CONFIG_DIR"] = os.environ["ATLAS_LAB_CLAUDE_CONFIG_DIR"]
    try:
        p = subprocess.run(cmd, cwd=str(out), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        stdout = p.stdout
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else ""
    (out / f"{label}.stream.jsonl").write_text(stdout, encoding="utf-8")
    emitted = hook_log.exists() and any('"event": "emitted"' in l for l in hook_log.read_text(encoding="utf-8").splitlines())
    return {"evidence": extract_evidence(stdout), "hook_emitted": emitted}


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("run", "matrix"):
        print(__doc__)
        return 2
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path(tempfile.gettempdir()) / "atlas-enforcement-lab"
    if argv[1] == "run":
        r = run_case(argv[2], argv[3], argv[4], out)
        print(json.dumps({"label": argv[2], **r, "view": case_view(r["evidence"], r["hook_emitted"])}, indent=2))
        return 0
    results = {
        "control_sonnet": run_case("R0a-control-sonnet", "sonnet", "log_only", out),
        "control_opus": run_case("R0b-control-opus", "opus", "log_only", out),
        "to_opus": run_case("R1-sonnet-to-opus", "sonnet", "rewrite:opus", out),
        "to_sonnet": run_case("R2-opus-to-sonnet", "opus", "rewrite:sonnet", out),
    }
    views = {k: case_view(v["evidence"], v["hook_emitted"]) for k, v in results.items()}
    verdict = classify(views["control_sonnet"], views["control_opus"], views["to_opus"], views["to_sonnet"])
    print(json.dumps({"views": views, **verdict}, indent=2))
    return 0 if verdict["verdict"] == "ENFORCEMENT_PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
