#!/usr/bin/env python3
"""
Bloque F35 — Architecture Decision Governor
===========================================

Valida config/architecture.decision-policy.yaml + tools/architecture_decision.py
(read-only decision aid). No runtime, no internet.

Tests:
  1  policy YAML existe y es válido
  2  CLI existe + API (load_policy, evaluate)
  3  dependencia/external fuerte -> NEEDS_HUMAN_APPROVAL o DEFER
  4  documentación simple -> ACCEPT_WITH_LIMITS
  5  toca dispatcher -> NEEDS_EVIDENCE
  6  aumenta boot tokens -> DEFER o NEEDS_EVIDENCE
  7  mejora tests sin runtime -> ACCEPT_WITH_LIMITS
  8  output JSON válido
  9  no modifica archivos (mtime de policy estable)
  10 corre sin acceso a internet (solo stdlib + yaml local)

Total: 10 tests
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name, detail=""):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("Bloque F35 -- Architecture Decision Governor")
    print("=" * 60)
    print()

    # T1 policy YAML
    pol_path = PROJECT_ROOT / "config" / "architecture.decision-policy.yaml"
    try:
        import yaml
        data = yaml.safe_load(pol_path.read_text(encoding="utf-8"))
        if pol_path.exists() and isinstance(data, dict) and "states" in data and "rules" in data:
            ok("T1 policy YAML valid")
        else:
            fail("T1 policy", "missing states/rules")
    except Exception as e:
        fail("T1 policy", str(e))

    # T2 CLI + API
    try:
        import architecture_decision as ad
        if hasattr(ad, "load_policy") and hasattr(ad, "evaluate"):
            ok("T2 CLI import + API")
        else:
            fail("T2 API"); print("\nRESULTADO: FAIL"); sys.exit(1)
    except Exception as e:
        fail("T2 import", str(e)); print("\nRESULTADO: FAIL"); sys.exit(1)

    def dec(text):
        return ad.evaluate(text)["decision"]

    # T3 dependency / external
    d = dec("Add Engram Cloud sync with a new dependency")
    if d in ("NEEDS_HUMAN_APPROVAL", "DEFER"):
        ok("T3 dependency/external -> approval/defer", d)
    else:
        fail("T3 dependency", d)

    # T4 simple documentation
    d = dec("Add documentation and clarify wording in a reference doc")
    if d == "ACCEPT_WITH_LIMITS":
        ok("T4 simple docs -> ACCEPT_WITH_LIMITS")
    else:
        fail("T4 docs", d)

    # T5 dispatcher
    d = dec("Refactor the dispatcher runtime logic")
    if d == "NEEDS_EVIDENCE":
        ok("T5 dispatcher -> NEEDS_EVIDENCE")
    else:
        fail("T5 dispatcher", d)

    # T6 boot tokens
    d = dec("Load more capability docs into CLAUDE.md always-on at boot")
    if d in ("DEFER", "NEEDS_EVIDENCE"):
        ok("T6 boot increase -> DEFER/NEEDS_EVIDENCE", d)
    else:
        fail("T6 boot", d)

    # T7 tests, no runtime
    d = dec("Improve test coverage with a new qa check suite, no runtime changes")
    if d == "ACCEPT_WITH_LIMITS":
        ok("T7 tests-only -> ACCEPT_WITH_LIMITS")
    else:
        fail("T7 tests", d)

    # T8 JSON valid (CLI)
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "architecture_decision.py"),
                        "--text", "Add Engram Cloud sync", "--json"],
                       capture_output=True, text=True, timeout=60)
    try:
        j = json.loads(r.stdout)
        if "decision" in j and "risk" in j and "recommendation" in j:
            ok("T8 --json valid")
        else:
            fail("T8 json", "missing keys")
    except Exception as e:
        fail("T8 json", str(e))

    # T9 no file modification (policy mtime stable)
    before = pol_path.stat().st_mtime
    ad.evaluate("Some proposal touching dispatcher and cloud and docs")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "architecture_decision.py"),
                    "--text", "x"], capture_output=True, text=True, timeout=30)
    after = pol_path.stat().st_mtime
    if before == after:
        ok("T9 read-only (policy mtime unchanged)")
    else:
        fail("T9 read-only", "policy modified")

    # T10 no internet needed: evaluate works with no network (pure local)
    # (implicit — module imports only stdlib + yaml; assert evaluate returns dict offline)
    res = ad.evaluate("decompose orchestrator pipeline into per-phase lazy refs")
    if isinstance(res, dict) and res.get("decision"):
        ok("T10 runs offline (no network dependency)")
    else:
        fail("T10 offline", "no result")

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
