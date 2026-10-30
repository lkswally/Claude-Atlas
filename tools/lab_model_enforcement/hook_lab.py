#!/usr/bin/env python3
"""
LAB-ONLY PreToolUse/PostToolUse hook for the Model Router enforcement experiment (roadmap P3). Not registered anywhere.
Never referenced from any real Claude settings: enforcement_lab.py generates a hook-only settings file at run
time and passes it with --settings. It does exactly what LAB_MODE says and logs every payload it receives, but
the experiment never infers its verdict from this hook's output (see enforcement_lab.classify).

LAB_MODE (env var set per run):
  log_only            allow, change nothing                         (baseline: payload shape + default model)
  rewrite:<model>     allow, return updatedInput = tool_input + {"model": <model>}
  deny                permissionDecision = deny
  malformed           print non-JSON and exit 0
  crash               exit 1 with no output
"""
import json
import os
import sys
import time

LOG = os.environ.get("LAB_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook-log.jsonl"))
MODE = os.environ.get("LAB_MODE", "log_only")


def log(rec):
    rec["t"] = time.time()
    rec["mode"] = MODE
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        log({"event": "unparseable_stdin", "raw": raw[:300]})
        return 0
    event = payload.get("hook_event_name")
    log({"event": event, "tool_name": payload.get("tool_name"), "tool_input": payload.get("tool_input"),
         "tool_response_keys": sorted((payload.get("tool_response") or {}).keys()) if isinstance(payload.get("tool_response"), dict) else None,
         "payload_keys": sorted(payload.keys())})
    if event != "PreToolUse":
        return 0
    ti = payload.get("tool_input") or {}
    if MODE == "log_only":
        return 0
    if MODE.startswith("rewrite:"):
        new_input = dict(ti)
        new_input["model"] = MODE.split(":", 1)[1]
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                      "permissionDecisionReason": "lab: model rewrite", "updatedInput": new_input}}
        log({"event": "emitted", "updatedInput": new_input})
        print(json.dumps(out))
        return 0
    if MODE == "deny":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": "lab: denied"}}))
        return 0
    if MODE == "malformed":
        print("this is {not json")
        return 0
    if MODE == "crash":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
