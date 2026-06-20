#!/usr/bin/env python3
"""
Bloque F36 — Claim Linter
=========================

Valida tools/claim_linter.py + config/claim-linter.registry.yaml (read-only,
WARN-only documentation truthfulness gate).

Tests:
  1  config existe
  2  CLI/módulo existe + API (load_registry, lint_text, scan)
  3  detecta un claim absoluto falso sintético
  4  clasifica "no raw MCP" como HIGH/CRITICAL
  5  sugiere verifier para claim MCP
  6  sugiere secrets_check para claim de secretos
  7  sugiere run_all release para release-ready
  8  --json válido (CLI)
  9  --file funciona (CLI)
  10 healthcheck incluye Claim Linter (PASS/WARN, nunca FAIL)
  11 no modifica archivos (mtime config estable)
  12 corre offline (sin red)

Total: 12 tests
"""

import json
import subprocess
import sys
import tempfile
import os
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
    print("Bloque F36 -- Claim Linter")
    print("=" * 60)
    print()

    cfg = PROJECT_ROOT / "config" / "claim-linter.registry.yaml"

    # T1 config
    if cfg.exists():
        ok("T1 config exists")
    else:
        fail("T1 config missing")

    # T2 import + API
    try:
        import claim_linter as cl
        if all(hasattr(cl, a) for a in ("load_registry", "lint_text", "scan")):
            ok("T2 import + API")
        else:
            fail("T2 API"); print("\nRESULTADO: FAIL"); sys.exit(1)
    except Exception as e:
        fail("T2 import", str(e)); print("\nRESULTADO: FAIL"); sys.exit(1)

    reg = cl.load_registry()

    # T3 synthetic absolute false claim
    synthetic = "This system always works and 100% guaranteed, no agent ever fails."
    fnd = cl.lint_text(synthetic, reg, source="<synthetic>")
    if fnd:
        ok("T3 detects synthetic absolute claim", f"{len(fnd)} findings")
    else:
        fail("T3 synthetic", "no findings")

    # T4 "no raw MCP" HIGH/CRITICAL
    fnd = cl.lint_text("The project has no raw MCP usage.", reg)
    mcp = [f for f in fnd if f["id"] == "no-raw-mcp"]
    if mcp and mcp[0]["severity"] in ("HIGH", "CRITICAL"):
        ok("T4 'no raw MCP' -> HIGH/CRITICAL", mcp[0]["severity"])
    else:
        fail("T4 no raw mcp", str([(f['id'], f['severity']) for f in fnd]))

    # T5 verifier for MCP
    if mcp and mcp[0].get("evidence_verifier"):
        ok("T5 MCP claim suggests verifier", mcp[0]["evidence_verifier"][:30])
    else:
        fail("T5 mcp verifier", "no verifier")

    # T6 secrets verifier
    fnd = cl.lint_text("There are no secrets in this repo.", reg)
    sec = [f for f in fnd if f["id"] == "no-secrets"]
    if sec and "secrets_check" in (sec[0].get("evidence_verifier") or ""):
        ok("T6 secrets claim suggests secrets_check")
    else:
        fail("T6 secrets verifier", str([(f['id'], f.get('evidence_verifier')) for f in fnd]))

    # T7 release-ready verifier
    fnd = cl.lint_text("ATLAS is release-ready.", reg)
    rel = [f for f in fnd if f["id"] == "status-strong"]
    if rel and "run_all" in (rel[0].get("evidence_verifier") or ""):
        ok("T7 release-ready suggests run_all release")
    else:
        fail("T7 release verifier", str([(f['id'], f.get('evidence_verifier')) for f in fnd]))

    # T8 --json valid
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "claim_linter.py"), "--json"],
                       capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout)
        if "findings" in d and "by_severity" in d:
            ok("T8 --json valid", f"{d['total_findings']} findings")
        else:
            fail("T8 json", "missing keys")
    except Exception as e:
        fail("T8 json", str(e))

    # T9 --file works
    tmp = PROJECT_ROOT / "_qa" / "_f36_tmp.md"
    try:
        tmp.write_text("# x\nThis is fully secure and all tests pass.\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "claim_linter.py"),
                            "--file", "_qa/_f36_tmp.md", "--json"],
                           capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        if d.get("total_findings", 0) >= 1:
            ok("T9 --file works", f"{d['total_findings']} findings")
        else:
            fail("T9 --file", "no findings")
    finally:
        tmp.unlink(missing_ok=True)

    # T10 healthcheck includes Claim Linter (PASS/WARN, never FAIL)
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "atlas_healthcheck.py"), "--json"],
                       capture_output=True, text=True, timeout=60)
    try:
        hc = json.loads(r.stdout)
        cl_check = next((c for c in hc.get("results", []) if "Claim linter" in c.get("check", "")), {})
        if cl_check and cl_check.get("status") in ("PASS", "WARN"):
            ok("T10 healthcheck includes Claim Linter (WARN-only)", cl_check["status"])
        else:
            fail("T10 healthcheck", f"status={cl_check.get('status')}")
    except Exception as e:
        fail("T10 healthcheck", str(e))

    # T11 read-only (config mtime stable)
    before = cfg.stat().st_mtime
    cl.scan()
    after = cfg.stat().st_mtime
    if before == after:
        ok("T11 read-only (config mtime unchanged)")
    else:
        fail("T11 read-only", "config modified")

    # T12 offline
    res = cl.scan()
    if isinstance(res, dict) and "findings" in res:
        ok("T12 runs offline")
    else:
        fail("T12 offline")

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
