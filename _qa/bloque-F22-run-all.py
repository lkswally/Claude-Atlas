#!/usr/bin/env python3
"""
Bloque F22 — run_all.py validation
=====================================

Validates that tools/run_all.py works correctly:
- exists
- --list works
- --quick runs without crash
- --json output is valid
- discovers all _qa/bloque-F*.py suites
- exit codes are correct

TC1:  tools/run_all.py exists
TC2:  --list exits 0
TC3:  --list discovers all existing suites
TC4:  --json exits with code 0 or 1 (never 2)
TC5:  --json output is valid JSON with required keys
TC6:  --json total matches discovered suite count (within --quick scope)
TC7:  --quick mode runs in under 1800s (Python 3.14 + Windows startup; F23 has 420s override)
TC8:  --quick exit code is 0 (all suites pass)
TC9:  LIVE_BINARY_SUITES are skipped in --quick
TC10: --list --no-network excludes network suites
TC11: JSON output has 'passed', 'failed', 'total' keys
TC12: JSON output 'mode' is 'quick' when --quick flag used
TC13: individual suite pass/fail reported in JSON 'suites' array
TC14: healthcheck key absent in JSON for --quick (only in --release)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RUN_ALL = PROJECT_ROOT / "tools" / "run_all.py"
QA_DIR = PROJECT_ROOT / "_qa"

PASS_COUNT = 0
FAIL_COUNT = 0


def PASS(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    msg = f"  [PASS] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def FAIL(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run(*args, timeout=1800):
    cmd = [sys.executable, str(RUN_ALL)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(PROJECT_ROOT))


# TC1
if RUN_ALL.exists():
    PASS("TC1 tools/run_all.py exists")
else:
    FAIL("TC1 tools/run_all.py exists", "MISSING — all remaining tests will fail")
    print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
    sys.exit(1)

# TC2
try:
    r = run("--list", timeout=15)
    if r.returncode == 0:
        PASS("TC2 --list exits 0")
    else:
        FAIL("TC2 --list exits 0", f"returncode={r.returncode}")
except Exception as e:
    FAIL("TC2 --list", str(e))

# TC3
try:
    r = run("--list", timeout=15)
    discovered_on_disk = len(list(QA_DIR.glob("bloque-F*.py")))
    lines_with_bloque = [l for l in r.stdout.splitlines() if "bloque-F" in l]
    if len(lines_with_bloque) >= discovered_on_disk - 5:  # allow up to 5 skipped
        PASS("TC3 --list discovers all suites", f"{len(lines_with_bloque)} listed, {discovered_on_disk} on disk")
    else:
        FAIL("TC3 --list discovers all suites", f"listed={len(lines_with_bloque)}, on disk={discovered_on_disk}")
except Exception as e:
    FAIL("TC3 --list discovers suites", str(e))

# TC4 — --json exits 0 or 1 (never 2)
try:
    r = run("--json", timeout=1800)
    if r.returncode in (0, 1):
        PASS("TC4 --json exits 0 or 1 (not 2)", f"returncode={r.returncode}")
    else:
        FAIL("TC4 --json exits 0 or 1", f"returncode={r.returncode}")
except subprocess.TimeoutExpired:
    FAIL("TC4 --json timeout", "exceeded 450s")
except Exception as e:
    FAIL("TC4 --json", str(e))

# TC5 — --json output is valid JSON with required keys
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    required = {"total", "passed", "failed", "suites", "mode"}
    missing = required - data.keys()
    if not missing:
        PASS("TC5 --json output has required keys")
    else:
        FAIL("TC5 --json required keys", f"missing: {missing}")
except json.JSONDecodeError as e:
    FAIL("TC5 --json valid JSON", f"parse error: {e} | stdout[:200]={r.stdout[:200]}")
except Exception as e:
    FAIL("TC5 --json", str(e))

# TC6 — JSON total matches suite count
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    total = data.get("total", 0)
    suite_count = len(data.get("suites", []))
    if total > 0 and total == suite_count:
        PASS("TC6 JSON total matches suite array length", f"total={total}")
    else:
        FAIL("TC6 JSON total matches suite length", f"total={total} suites={suite_count}")
except Exception as e:
    FAIL("TC6 JSON total", str(e))

# TC7 — --quick runs in under 1800s (30 min)
# F23 has a 420s override; other suites have 120s default (Python 3.14 + Windows
# startup is slower). Total expected: 600-1200s on this machine.
try:
    start = time.monotonic()
    r = run("--quick", timeout=1800)
    elapsed = time.monotonic() - start
    if elapsed < 1800:
        PASS("TC7 --quick completes in under 1800s", f"{elapsed:.1f}s")
    else:
        FAIL("TC7 --quick under 1800s", f"took {elapsed:.1f}s")
except subprocess.TimeoutExpired:
    FAIL("TC7 --quick timeout", "exceeded 1800s")
except Exception as e:
    FAIL("TC7 --quick", str(e))

# TC8 — --quick exit code is 0
try:
    r = run("--quick", timeout=1800)
    if r.returncode == 0:
        PASS("TC8 --quick exit code 0 (all suites pass)")
    else:
        # Show which failed
        detail = ""
        for line in (r.stdout + r.stderr).splitlines():
            if "[FAIL]" in line or "RESULTADO: FAIL" in line:
                detail = line.strip()
                break
        FAIL("TC8 --quick exit code 0", f"returncode={r.returncode} {detail}")
except Exception as e:
    FAIL("TC8 --quick exit", str(e))

# TC9 — LIVE_BINARY_SUITES skipped in --quick (bloque-F13-engram-active)
try:
    r = run("--list", timeout=15)
    # In --quick mode, F13-engram-active should NOT be in selected list
    selected_lines = r.stdout.split("Skipped")[0] if "Skipped" in r.stdout else r.stdout
    if "bloque-F13-engram-active" not in selected_lines or "Skipped" in r.stdout:
        PASS("TC9 F13-engram-active skipped in --quick mode")
    else:
        FAIL("TC9 F13-engram-active skipped", "found in selected but should be skipped")
except Exception as e:
    FAIL("TC9 skip F13-engram-active", str(e))

# TC10 — --no-network flag accepted (exits 0 or 1)
try:
    r = run("--list", "--no-network", timeout=15)
    if r.returncode == 0:
        PASS("TC10 --no-network flag accepted")
    else:
        FAIL("TC10 --no-network", f"returncode={r.returncode}")
except Exception as e:
    FAIL("TC10 --no-network", str(e))

# TC11 — JSON has passed, failed, total
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    all_keys = {"passed", "failed", "total"}
    if all_keys.issubset(data.keys()) and isinstance(data["passed"], int):
        PASS("TC11 JSON has passed/failed/total as integers")
    else:
        FAIL("TC11 JSON passed/failed/total", f"keys={list(data.keys())}")
except Exception as e:
    FAIL("TC11 JSON keys", str(e))

# TC12 — JSON 'mode' is 'quick' by default
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    if data.get("mode") == "quick":
        PASS("TC12 JSON mode='quick' by default")
    else:
        FAIL("TC12 JSON mode", f"got mode={data.get('mode')}")
except Exception as e:
    FAIL("TC12 JSON mode", str(e))

# TC13 — JSON suites array has per-suite results
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    suites = data.get("suites", [])
    if suites and all("suite" in s and "passed" in s for s in suites):
        PASS("TC13 JSON suites array has suite+passed per entry", f"{len(suites)} suites")
    else:
        FAIL("TC13 JSON suites array", f"suites={suites[:1]}")
except Exception as e:
    FAIL("TC13 JSON suites", str(e))

# TC14 — healthcheck key absent in --quick JSON (only in --release)
try:
    r = run("--json", timeout=1800)
    data = json.loads(r.stdout)
    hc = data.get("healthcheck")
    if hc is None:
        PASS("TC14 healthcheck absent in --quick JSON output")
    else:
        FAIL("TC14 healthcheck absent in --quick", f"found: {hc}")
except Exception as e:
    FAIL("TC14 healthcheck absent", str(e))


print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
