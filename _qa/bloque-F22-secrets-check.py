#!/usr/bin/env python3
"""
Bloque F22 — secrets_check.py validation
==========================================

Validates that tools/secrets_check.py works correctly:
- exists and runs
- produces valid JSON
- correctly classifies tokens
- handles missing .env.local gracefully
- never prints token values

TC1:  tools/secrets_check.py exists
TC2:  --json exits 0 (no REQUIRED tokens missing)
TC3:  --json output has required keys
TC4:  tokens array has correct structure
TC5:  GITHUB_TOKEN classified as PENDING_TOKEN
TC6:  VERCEL_TOKEN classified as PENDING_TOKEN
TC7:  GEMINI_API_KEY classified as OPTIONAL
TC8:  MAGIC_21ST_KEY classified as DEFERRED_PAID
TC9:  missing .env.local handled gracefully (exit 0)
TC10: token VALUES not in JSON output
TC11: SET token with fake value shows status=SET
TC12: missing token shows status=PENDING_TOKEN or NOT_SET
TC13: --json 'ok' key is boolean
TC14: stdout never contains actual token values (no leakage)
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SECRETS_CHECK = PROJECT_ROOT / "tools" / "secrets_check.py"

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


def run(*args, env=None, timeout=15):
    cmd = [sys.executable, str(SECRETS_CHECK)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(PROJECT_ROOT), env=env)


# TC1
if SECRETS_CHECK.exists():
    PASS("TC1 tools/secrets_check.py exists")
else:
    FAIL("TC1 tools/secrets_check.py exists", "MISSING")
    print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
    sys.exit(1)

# TC2 — --json exits 0 (no REQUIRED tokens — system has no required tokens currently)
try:
    r = run("--json")
    if r.returncode == 0:
        PASS("TC2 --json exits 0 (no REQUIRED tokens missing)")
    else:
        FAIL("TC2 --json exits 0", f"returncode={r.returncode} stderr={r.stderr[:100]}")
except Exception as e:
    FAIL("TC2 --json", str(e))

# TC3 — required keys in JSON
try:
    r = run("--json")
    data = json.loads(r.stdout)
    required = {"tokens", "ok", "missing_required", "env_file_exists"}
    missing = required - data.keys()
    if not missing:
        PASS("TC3 --json output has required keys")
    else:
        FAIL("TC3 --json required keys", f"missing: {missing}")
except Exception as e:
    FAIL("TC3 --json keys", str(e))

# TC4 — tokens array has correct structure
try:
    r = run("--json")
    data = json.loads(r.stdout)
    tokens = data.get("tokens", [])
    if tokens and all("var" in t and "category" in t and "status" in t and "present" in t for t in tokens):
        PASS("TC4 tokens array has correct structure", f"{len(tokens)} tokens")
    else:
        FAIL("TC4 tokens structure", f"sample={tokens[:1]}")
except Exception as e:
    FAIL("TC4 tokens structure", str(e))

# TC5 — GITHUB_TOKEN classified as PENDING_TOKEN
try:
    r = run("--json")
    data = json.loads(r.stdout)
    gh = next((t for t in data["tokens"] if t["var"] == "GITHUB_TOKEN"), None)
    if gh and gh["category"] == "PENDING_TOKEN":
        PASS("TC5 GITHUB_TOKEN classified as PENDING_TOKEN")
    else:
        FAIL("TC5 GITHUB_TOKEN category", f"got {gh}")
except Exception as e:
    FAIL("TC5 GITHUB_TOKEN", str(e))

# TC6 — VERCEL_TOKEN classified as PENDING_TOKEN
try:
    r = run("--json")
    data = json.loads(r.stdout)
    t = next((t for t in data["tokens"] if t["var"] == "VERCEL_TOKEN"), None)
    if t and t["category"] == "PENDING_TOKEN":
        PASS("TC6 VERCEL_TOKEN classified as PENDING_TOKEN")
    else:
        FAIL("TC6 VERCEL_TOKEN category", f"got {t}")
except Exception as e:
    FAIL("TC6 VERCEL_TOKEN", str(e))

# TC7 — GEMINI_API_KEY classified as OPTIONAL
try:
    r = run("--json")
    data = json.loads(r.stdout)
    t = next((t for t in data["tokens"] if t["var"] == "GEMINI_API_KEY"), None)
    if t and t["category"] == "OPTIONAL":
        PASS("TC7 GEMINI_API_KEY classified as OPTIONAL")
    else:
        FAIL("TC7 GEMINI_API_KEY category", f"got {t}")
except Exception as e:
    FAIL("TC7 GEMINI_API_KEY", str(e))

# TC8 — MAGIC_21ST_KEY classified as DEFERRED_PAID
try:
    r = run("--json")
    data = json.loads(r.stdout)
    t = next((t for t in data["tokens"] if t["var"] == "MAGIC_21ST_KEY"), None)
    if t and t["category"] == "DEFERRED_PAID":
        PASS("TC8 MAGIC_21ST_KEY classified as DEFERRED_PAID")
    else:
        FAIL("TC8 MAGIC_21ST_KEY category", f"got {t}")
except Exception as e:
    FAIL("TC8 MAGIC_21ST_KEY", str(e))

# TC9 — missing .env.local handled gracefully
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / ".env.nonexistent"
        r = run("--json", f"--env={nonexistent}")
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if data.get("env_file_exists") is False:
                PASS("TC9 missing .env.local handled gracefully")
            else:
                FAIL("TC9 missing .env graceful", f"env_file_exists={data.get('env_file_exists')}")
        else:
            FAIL("TC9 missing .env graceful", f"returncode={r.returncode}")
except Exception as e:
    FAIL("TC9 missing .env", str(e))

# TC10 — token values NOT in JSON output
try:
    # Write a temp .env with a recognizable fake token
    fake_token = "FAKE_SECRET_VALUE_SHOULD_NOT_APPEAR_IN_OUTPUT_XYZ123"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(f"GITHUB_TOKEN={fake_token}\n")
        tmp_path = f.name
    try:
        r = run("--json", f"--env={tmp_path}")
        if fake_token not in r.stdout and fake_token not in r.stderr:
            PASS("TC10 token values not in JSON output")
        else:
            FAIL("TC10 token values leaked in output")
    finally:
        os.unlink(tmp_path)
except Exception as e:
    FAIL("TC10 token leakage check", str(e))

# TC11 — SET token shows status=SET
try:
    fake_token = "ghp_FAKEGITHUBTOKEN123456789"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(f"GITHUB_TOKEN={fake_token}\n")
        tmp_path = f.name
    try:
        r = run("--json", f"--env={tmp_path}")
        data = json.loads(r.stdout)
        gh = next((t for t in data["tokens"] if t["var"] == "GITHUB_TOKEN"), None)
        if gh and gh["status"] == "SET" and gh["present"] is True:
            PASS("TC11 SET token shows status=SET and present=True")
        else:
            FAIL("TC11 SET token status", f"got {gh}")
    finally:
        os.unlink(tmp_path)
except Exception as e:
    FAIL("TC11 SET token", str(e))

# TC12 — missing token shows PENDING_TOKEN or NOT_SET (not blank)
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("# empty env file\n")
        tmp_path = f.name
    try:
        r = run("--json", f"--env={tmp_path}")
        data = json.loads(r.stdout)
        gh = next((t for t in data["tokens"] if t["var"] == "GITHUB_TOKEN"), None)
        valid_statuses = {"PENDING_TOKEN", "NOT_SET", "MISSING"}
        if gh and gh["status"] in valid_statuses:
            PASS("TC12 missing token shows informative status", f"status={gh['status']}")
        else:
            FAIL("TC12 missing token status", f"got {gh}")
    finally:
        os.unlink(tmp_path)
except Exception as e:
    FAIL("TC12 missing token", str(e))

# TC13 — 'ok' key is boolean
try:
    r = run("--json")
    data = json.loads(r.stdout)
    if isinstance(data.get("ok"), bool):
        PASS("TC13 'ok' key is boolean", f"ok={data['ok']}")
    else:
        FAIL("TC13 'ok' is boolean", f"got type {type(data.get('ok'))}")
except Exception as e:
    FAIL("TC13 ok boolean", str(e))

# TC14 — stdout never leaks env var values in default (human) mode
try:
    fake_token = "VERY_SECRET_TOKEN_SHOULD_NEVER_APPEAR_IN_STDOUT_ABCDEF"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(f"GITHUB_TOKEN={fake_token}\n")
        tmp_path = f.name
    try:
        r = run(f"--env={tmp_path}")  # human mode, not --json
        if fake_token not in r.stdout and fake_token not in r.stderr:
            PASS("TC14 no token leakage in human output mode")
        else:
            FAIL("TC14 no token leakage in human mode")
    finally:
        os.unlink(tmp_path)
except Exception as e:
    FAIL("TC14 token leakage human mode", str(e))


print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
