#!/usr/bin/env python3
"""
Bloque F22 — Command Audit
===========================

Validates that scripts and tools documented in README/docs actually exist
and can be imported or invoked without crashing.

TC1:  install.sh root wrapper exists
TC2:  install/linux.sh exists
TC3:  install/windows.md exists
TC4:  tools/atlas_healthcheck.py exists
TC5:  tools/run_all.py exists
TC6:  tools/capability_metrics.py exists
TC7:  tools/dependency_graph.py exists
TC8:  tools/skills_registry.py exists
TC9:  tools/secrets_check.py exists
TC10: tools/atlas_dispatcher.py exists
TC11: capability_metrics --json produces valid JSON
TC12: skills_registry.py list produces valid JSON
TC13: secrets_check.py --json produces valid JSON
TC14: run_all.py --list exits 0 and lists suites
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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


def file_exists(rel_path: str) -> bool:
    return (PROJECT_ROOT / rel_path).exists()


def run(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable] + cmd if cmd[0].endswith(".py") else cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# TC1
if file_exists("install.sh"):
    PASS("TC1 install.sh root wrapper exists")
else:
    FAIL("TC1 install.sh root wrapper exists", "MISSING: install.sh")

# TC2
if file_exists("install/linux.sh"):
    PASS("TC2 install/linux.sh exists")
else:
    FAIL("TC2 install/linux.sh exists", "MISSING: install/linux.sh")

# TC3
if file_exists("install/windows.md"):
    PASS("TC3 install/windows.md exists")
else:
    FAIL("TC3 install/windows.md exists", "MISSING: install/windows.md")

# TC4
if file_exists("tools/atlas_healthcheck.py"):
    PASS("TC4 tools/atlas_healthcheck.py exists")
else:
    FAIL("TC4 tools/atlas_healthcheck.py exists", "MISSING")

# TC5
if file_exists("tools/run_all.py"):
    PASS("TC5 tools/run_all.py exists")
else:
    FAIL("TC5 tools/run_all.py exists", "MISSING — F22 P0")

# TC6
if file_exists("tools/capability_metrics.py"):
    PASS("TC6 tools/capability_metrics.py exists")
else:
    FAIL("TC6 tools/capability_metrics.py exists", "MISSING")

# TC7
if file_exists("tools/dependency_graph.py"):
    PASS("TC7 tools/dependency_graph.py exists")
else:
    FAIL("TC7 tools/dependency_graph.py exists", "MISSING")

# TC8
if file_exists("tools/skills_registry.py"):
    PASS("TC8 tools/skills_registry.py exists")
else:
    FAIL("TC8 tools/skills_registry.py exists", "MISSING")

# TC9
if file_exists("tools/secrets_check.py"):
    PASS("TC9 tools/secrets_check.py exists")
else:
    FAIL("TC9 tools/secrets_check.py exists", "MISSING — F22 P0")

# TC10
if file_exists("tools/atlas_dispatcher.py"):
    PASS("TC10 tools/atlas_dispatcher.py exists")
else:
    FAIL("TC10 tools/atlas_dispatcher.py exists", "MISSING")

# TC11 — capability_metrics --json produces valid JSON
try:
    r = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools/capability_metrics.py"), "--json"],
        capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT)
    )
    data = json.loads(r.stdout)
    if "total_resolutions" in data or "by_capability" in data:
        PASS("TC11 capability_metrics --json produces valid JSON")
    else:
        FAIL("TC11 capability_metrics --json produces valid JSON", f"unexpected keys: {list(data.keys())[:3]}")
except Exception as e:
    FAIL("TC11 capability_metrics --json produces valid JSON", str(e))

# TC12 — skills_registry list produces valid JSON
try:
    r = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools/skills_registry.py"), "list"],
        capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT)
    )
    data = json.loads(r.stdout)
    if isinstance(data, list):
        PASS("TC12 skills_registry list produces JSON array", f"{len(data)} skills")
    else:
        FAIL("TC12 skills_registry list produces JSON array", f"got type {type(data)}")
except Exception as e:
    FAIL("TC12 skills_registry list produces JSON array", str(e))

# TC13 — secrets_check --json produces valid JSON
try:
    r = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools/secrets_check.py"), "--json"],
        capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT)
    )
    data = json.loads(r.stdout)
    required_keys = {"tokens", "ok", "missing_required"}
    if required_keys.issubset(data.keys()):
        PASS("TC13 secrets_check --json produces valid JSON")
    else:
        FAIL("TC13 secrets_check --json produces valid JSON", f"missing keys: {required_keys - data.keys()}")
except Exception as e:
    FAIL("TC13 secrets_check --json produces valid JSON", str(e))

# TC14 — run_all.py --list exits 0 and lists suites
try:
    r = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools/run_all.py"), "--list"],
        capture_output=True, text=True, timeout=15, cwd=str(PROJECT_ROOT)
    )
    if r.returncode == 0 and "bloque-F" in r.stdout:
        count = r.stdout.count("bloque-F")
        PASS("TC14 run_all.py --list exits 0 and lists suites", f"{count} suites listed")
    else:
        FAIL("TC14 run_all.py --list exits 0", f"returncode={r.returncode} stdout={r.stdout[:100]}")
except Exception as e:
    FAIL("TC14 run_all.py --list", str(e))


print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
