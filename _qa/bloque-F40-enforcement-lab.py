#!/usr/bin/env python3
"""
Bloque F40 -- Model-routing enforcement lab: verdict logic (offline)
=============================================================================

Gap (roadmap P3): ATLAS cannot claim the Model Router selects the model a subagent runs on unless that is proven
against the real runtime. The live proof needs an authenticated Claude Code binary (currently EXTERNALLY_BLOCKED:
the standalone binary answers "Not logged in"). What can be proven offline, and is, is that the lab's VERDICT LOGIC
cannot be fooled: it is derived only from the runtime's stream-json (the subagent's own assistant `model`), never
from what the hook says it did, and a result is PROVEN only if it differs from its own no-rewrite control.

No process is spawned and no network is touched here; fixtures are synthetic stream-json.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "lab_model_enforcement"))

import enforcement_lab as lab  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
SONNET, OPUS, HAIKU = "claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def stream(parent, sub, spawn=True, requested=None, extra_sub_models=(), auth_fail=False):
    ev = [{"type": "system", "subtype": "init", "model": parent}]
    if auth_fail:
        ev.append({"type": "assistant", "message": {"model": "<synthetic>", "content": []}, "parent_tool_use_id": None})
        ev.append({"type": "result", "is_error": True, "result": "Not logged in · Please run /login"})
        return "\n".join(json.dumps(e) for e in ev)
    call = {"type": "tool_use", "id": "toolu_1", "name": "Agent", "input": {"subagent_type": "general-purpose", "prompt": "x"}}
    if requested:
        call["input"]["model"] = requested
    ev.append({"type": "assistant", "message": {"model": parent, "content": [call]}, "parent_tool_use_id": None})
    if spawn:
        for m in (sub, *extra_sub_models):
            ev.append({"type": "assistant", "message": {"model": m, "content": [{"type": "text", "text": "PONG"}]}, "parent_tool_use_id": "toolu_1"})
    ev.append({"type": "result", "is_error": False, "result": "DONE", "modelUsage": {parent: {}, sub: {}}})
    return "\n".join(json.dumps(e) for e in ev)


def view(parent, sub, hook=True, **kw):
    return lab.case_view(lab.extract_evidence(stream(parent, sub, **kw)), hook)


def matrix(cs_sub, co_sub, up_sub, down_sub, up_hook=True, down_hook=True):
    return lab.classify(view(SONNET, cs_sub, hook=False), view(OPUS, co_sub, hook=False),
                        view(SONNET, up_sub, hook=up_hook, requested=OPUS), view(OPUS, down_sub, hook=down_hook, requested=SONNET))


def test_evidence():
    ev = lab.extract_evidence(stream(SONNET, OPUS))
    check("01 subagent and parent models are separated by parent_tool_use_id",
          ev["subagent_models"] == [OPUS] and ev["parent_models"] == [SONNET] and ev["agent_calls"] == 1)
    ev = lab.extract_evidence(stream(SONNET, SONNET, extra_sub_models=("<synthetic>",)))
    check("02 synthetic placeholder messages are not evidence", ev["subagent_models"] == [SONNET])
    ev = lab.extract_evidence(stream(SONNET, SONNET, requested=OPUS))
    check("03 the model requested in the call is recorded but is not the effective model",
          ev["requested_model_in_call"] == [OPUS] and ev["subagent_models"] == [SONNET])
    ev = lab.extract_evidence(stream(None, None, auth_fail=True))
    check("04 the real R0 output ('Not logged in') is recognized as blocked, not as a model result",
          ev["blocked_auth"] is True and ev["subagent_models"] == [] and ev["agent_calls"] == 0)
    for junk in ("", "not json", '{"type": "assistant"}', "[1,2,3]\n{}\n"):
        try:
            e = lab.extract_evidence(junk)
            ok = e["subagent_models"] == [] and e["blocked_auth"] is False
        except Exception:  # noqa: BLE001
            ok = False
        if not ok:
            break
    check("05 empty / garbage / malformed streams never raise and yield no evidence", ok)
    check("06 model families resolve unambiguously and ambiguous ids resolve to None",
          lab.family(OPUS) == "opus" and lab.family(SONNET) == "sonnet" and lab.family("opus-and-sonnet") is None and lab.family(None) is None)


def test_verdicts():
    # defaults: sonnet parent -> sonnet subagent; opus parent -> opus subagent (inherit)
    r = matrix(SONNET, OPUS, OPUS, SONNET)
    check("07 rewrite honored in both directions and different from each control -> PROVEN", r["verdict"] == "ENFORCEMENT_PROVEN", r["reason"])
    r = matrix(SONNET, OPUS, SONNET, OPUS)
    check("08 hook emitted but the subagent model equals its control in both directions -> UNSUPPORTED", r["verdict"] == "ENFORCEMENT_UNSUPPORTED", r["reason"])
    r = matrix(SONNET, OPUS, SONNET, OPUS, up_hook=False, down_hook=False)
    check("09 models unchanged and the hook never ran -> UNKNOWN, not UNSUPPORTED", r["verdict"] == "ENFORCEMENT_UNKNOWN", r["reason"])
    r = matrix(SONNET, OPUS, OPUS, OPUS)
    check("10 only one direction honored -> UNKNOWN (never PROVEN on half the evidence)", r["verdict"] == "ENFORCEMENT_UNKNOWN", r["reason"])
    r = matrix(OPUS, SONNET, OPUS, SONNET)
    check("11 control already equals the target (default is opus under sonnet, sonnet under opus) -> not attributable, not PROVEN",
          r["verdict"] != "ENFORCEMENT_PROVEN", r["reason"])

    # the central rule: the hook's own claim cannot create a PROVEN
    lying = lab.classify(view(SONNET, SONNET, hook=False), view(OPUS, OPUS, hook=False),
                         view(SONNET, SONNET, hook=True, requested=OPUS), view(OPUS, OPUS, hook=True, requested=SONNET))
    check("12 NEGATIVE CONTROL -- the hook claims rewrites but the runtime shows no change: never PROVEN", lying["verdict"] == "ENFORCEMENT_UNSUPPORTED", lying["reason"])
    asked = lab.classify(view(SONNET, SONNET, hook=False), view(OPUS, OPUS, hook=False),
                         view(SONNET, SONNET, hook=True, requested=OPUS), view(OPUS, OPUS, hook=True, requested=SONNET))
    check("13 NEGATIVE CONTROL -- the Agent call REQUESTED the target model but the runtime ran another: not PROVEN", asked["verdict"] != "ENFORCEMENT_PROVEN")

    blocked = lab.classify(*(lab.case_view(lab.extract_evidence(stream(None, None, auth_fail=True)), False) for _ in range(4)))
    check("14 not authenticated -> UNKNOWN with an explicit EXTERNALLY_BLOCKED reason (what R0 returned)",
          blocked["verdict"] == "ENFORCEMENT_UNKNOWN" and "BLOCKED" in blocked["reason"], blocked["reason"])
    r = lab.classify(view(SONNET, SONNET, hook=False, spawn=False), view(OPUS, OPUS, hook=False),
                     view(SONNET, OPUS, requested=OPUS), view(OPUS, SONNET, requested=SONNET))
    check("15 a case where no subagent was spawned is missing evidence -> UNKNOWN", r["verdict"] == "ENFORCEMENT_UNKNOWN" and "control_sonnet" in r["reason"], r["reason"])
    r = lab.classify(view(SONNET, SONNET, hook=False), view(OPUS, OPUS, hook=False),
                     view(SONNET, OPUS, extra_sub_models=(SONNET,), requested=OPUS), view(OPUS, SONNET, requested=SONNET))
    check("16 a subagent that reports two different models is ambiguous -> UNKNOWN", r["verdict"] == "ENFORCEMENT_UNKNOWN", r["reason"])


def test_source_guards():
    src = (PROJECT_ROOT / "tools" / "lab_model_enforcement" / "enforcement_lab.py").read_text(encoding="utf-8")
    body = src.split("# ------------------------------------------------------------------ running the real binary")[0]
    check("17 the verdict code never opens a hook log or file", "open(" not in body and "read_text" not in body and "hook_log" not in body)
    check("18 the lab is not wired into any ATLAS settings or hooks",
          all("lab_model_enforcement" not in p.read_text(encoding="utf-8", errors="replace")
              for p in [PROJECT_ROOT / "templates" / "settings.json"] if p.exists()))


def main():
    print("=" * 60)
    print("Bloque F40 -- Model-routing enforcement lab (verdict logic)")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_evidence, test_verdicts, test_source_guards):
        print(f"\n-- {fn.__name__} --")
        fn()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
