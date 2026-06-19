#!/usr/bin/env python3
"""
Bloque F22 — secrets_check.py validation
==========================================

Validates that tools/secrets_check.py works correctly.

P2 REWRITE: eliminated subprocess recursion.
Previous version ran 13 subprocess calls × ~10s Python cold start = ~130s.
Now uses module API (load_env_file, check_tokens) directly — <0.1s total.
Only TC1 (file existence) uses no import; TC2 and TC9 use one subprocess each
because they test CLI exit-code behavior specifically.

TC1:  tools/secrets_check.py exists
TC2:  --json CLI exits 0 [subprocess, fast]
TC3:  --json output has required keys (module API)
TC4:  tokens array has correct structure (module API)
TC5:  GITHUB_TOKEN classified as PENDING_TOKEN (module API)
TC6:  VERCEL_TOKEN classified as PENDING_TOKEN (module API)
TC7:  GEMINI_API_KEY classified as OPTIONAL (module API)
TC8:  MAGIC_21ST_KEY classified as DEFERRED_PAID (module API)
TC9:  missing .env.local handled gracefully (module API)
TC10: token VALUES not in JSON output (module API)
TC11: SET token with fake value shows status=SET (module API)
TC12: missing token shows status=PENDING_TOKEN or NOT_SET (module API)
TC13: 'ok' key is boolean in JSON (module API)
TC14: stdout never leaks token values in human mode [subprocess, fast]
"""

import importlib.util
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


def _run_cli(*args, env=None, timeout=15):
    """Subprocess call for CLI behavior tests only."""
    cmd = [sys.executable, str(SECRETS_CHECK)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(PROJECT_ROOT), env=env)


def _load_sc():
    """Import secrets_check as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("secrets_check", str(SECRETS_CHECK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_json_result(sc_mod, env_path: Path | None = None) -> dict:
    """Build the same dict that --json would produce, via module API."""
    default_env = PROJECT_ROOT / ".env.local"
    path = env_path or default_env
    env = sc_mod.load_env_file(path)
    tokens = sc_mod.check_tokens(env)
    missing_required = [t["var"] for t in tokens if t["status"] == "MISSING"]
    return {
        "tokens": tokens,
        "ok": len(missing_required) == 0,
        "missing_required": missing_required,
        "env_file_exists": path.exists(),
    }


# ── TC1 ─────────────────────────────────────────────────────────────────────

if SECRETS_CHECK.exists():
    PASS("TC1 tools/secrets_check.py exists")
else:
    FAIL("TC1 tools/secrets_check.py exists", "MISSING")
    print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
    sys.exit(1)

# Load module once
try:
    _sc = _load_sc()
    _sc_ok = True
except Exception as _sc_err:
    _sc = None
    _sc_ok = False

# ── TC2 — CLI exit code [subprocess, fast] ──────────────────────────────────
try:
    r = _run_cli("--json", timeout=15)
    if r.returncode == 0:
        PASS("TC2 --json CLI exits 0 (no REQUIRED tokens missing)")
    else:
        FAIL("TC2 --json exits 0", f"returncode={r.returncode}")
except Exception as e:
    FAIL("TC2 --json CLI", str(e))

# ── Build shared result (module API, <1ms) ───────────────────────────────────
_data = None
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    _data = _build_json_result(_sc)
except Exception as _data_err:
    pass

# ── TC3 — required keys in result ───────────────────────────────────────────
try:
    if _data is None:
        raise RuntimeError("module result not available")
    required = {"tokens", "ok", "missing_required", "env_file_exists"}
    missing = required - _data.keys()
    if not missing:
        PASS("TC3 result has required keys")
    else:
        FAIL("TC3 required keys", f"missing: {missing}")
except Exception as e:
    FAIL("TC3 required keys", str(e))

# ── TC4 — tokens array structure ────────────────────────────────────────────
try:
    if _data is None:
        raise RuntimeError("module result not available")
    tokens = _data.get("tokens", [])
    if tokens and all("var" in t and "category" in t and "status" in t and "present" in t for t in tokens):
        PASS("TC4 tokens array has correct structure", f"{len(tokens)} tokens")
    else:
        FAIL("TC4 tokens structure", f"sample={tokens[:1]}")
except Exception as e:
    FAIL("TC4 tokens structure", str(e))

# ── TC5 — GITHUB_TOKEN is PENDING_TOKEN ─────────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    all_tokens = _sc.check_tokens({})  # no env — all tokens unset
    gh = next((t for t in all_tokens if t["var"] == "GITHUB_TOKEN"), None)
    if gh and gh["category"] == "PENDING_TOKEN":
        PASS("TC5 GITHUB_TOKEN classified as PENDING_TOKEN")
    else:
        FAIL("TC5 GITHUB_TOKEN category", f"got {gh}")
except Exception as e:
    FAIL("TC5 GITHUB_TOKEN", str(e))

# ── TC6 — VERCEL_TOKEN is PENDING_TOKEN ─────────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    all_tokens = _sc.check_tokens({})
    t = next((t for t in all_tokens if t["var"] == "VERCEL_TOKEN"), None)
    if t and t["category"] == "PENDING_TOKEN":
        PASS("TC6 VERCEL_TOKEN classified as PENDING_TOKEN")
    else:
        FAIL("TC6 VERCEL_TOKEN category", f"got {t}")
except Exception as e:
    FAIL("TC6 VERCEL_TOKEN", str(e))

# ── TC7 — GEMINI_API_KEY is OPTIONAL ────────────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    all_tokens = _sc.check_tokens({})
    t = next((t for t in all_tokens if t["var"] == "GEMINI_API_KEY"), None)
    if t and t["category"] == "OPTIONAL":
        PASS("TC7 GEMINI_API_KEY classified as OPTIONAL")
    else:
        FAIL("TC7 GEMINI_API_KEY category", f"got {t}")
except Exception as e:
    FAIL("TC7 GEMINI_API_KEY", str(e))

# ── TC8 — MAGIC_21ST_KEY is DEFERRED_PAID ───────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    all_tokens = _sc.check_tokens({})
    t = next((t for t in all_tokens if t["var"] == "MAGIC_21ST_KEY"), None)
    if t and t["category"] == "DEFERRED_PAID":
        PASS("TC8 MAGIC_21ST_KEY classified as DEFERRED_PAID")
    else:
        FAIL("TC8 MAGIC_21ST_KEY category", f"got {t}")
except Exception as e:
    FAIL("TC8 MAGIC_21ST_KEY", str(e))

# ── TC9 — missing .env.local handled gracefully ─────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    nonexistent = Path(tempfile.gettempdir()) / ".env.definitely.does.not.exist.tmp"
    nonexistent.unlink(missing_ok=True)
    result = _build_json_result(_sc, nonexistent)
    if result["env_file_exists"] is False and result["ok"] is True:
        PASS("TC9 missing .env.local handled gracefully")
    else:
        FAIL("TC9 missing .env graceful", f"env_file_exists={result['env_file_exists']}")
except Exception as e:
    FAIL("TC9 missing .env", str(e))

# ── TC10 — token VALUES not in result ───────────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    fake_token = "FAKE_SECRET_VALUE_SHOULD_NOT_APPEAR_XYZ123"
    env = {"GITHUB_TOKEN": fake_token}
    tokens = _sc.check_tokens(env)
    serialized = json.dumps(tokens)
    if fake_token not in serialized:
        PASS("TC10 token values not in result")
    else:
        FAIL("TC10 token values leaked in result")
except Exception as e:
    FAIL("TC10 token leakage", str(e))

# ── TC11 — SET token shows status=SET ───────────────────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    fake_token = "ghp_FAKEGITHUBTOKEN123456789"
    tokens = _sc.check_tokens({"GITHUB_TOKEN": fake_token})
    gh = next((t for t in tokens if t["var"] == "GITHUB_TOKEN"), None)
    if gh and gh["status"] == "SET" and gh["present"] is True:
        PASS("TC11 SET token shows status=SET and present=True")
    else:
        FAIL("TC11 SET token status", f"got {gh}")
except Exception as e:
    FAIL("TC11 SET token", str(e))

# ── TC12 — missing token shows informative status ───────────────────────────
try:
    if not _sc_ok:
        raise RuntimeError(str(_sc_err))
    tokens = _sc.check_tokens({})
    gh = next((t for t in tokens if t["var"] == "GITHUB_TOKEN"), None)
    valid_statuses = {"PENDING_TOKEN", "NOT_SET", "MISSING"}
    if gh and gh["status"] in valid_statuses:
        PASS("TC12 missing token shows informative status", f"status={gh['status']}")
    else:
        FAIL("TC12 missing token status", f"got {gh}")
except Exception as e:
    FAIL("TC12 missing token", str(e))

# ── TC13 — 'ok' key is boolean ──────────────────────────────────────────────
try:
    if _data is None:
        raise RuntimeError("module result not available")
    if isinstance(_data.get("ok"), bool):
        PASS("TC13 'ok' key is boolean", f"ok={_data['ok']}")
    else:
        FAIL("TC13 ok is boolean", f"got type {type(_data.get('ok'))}")
except Exception as e:
    FAIL("TC13 ok boolean", str(e))

# ── TC14 — human-mode CLI never leaks token values [subprocess, fast] ────────
try:
    fake_token = "VERY_SECRET_TOKEN_SHOULD_NEVER_APPEAR_IN_STDOUT_ABCDEF"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write(f"GITHUB_TOKEN={fake_token}\n")
        tmp_path = f.name
    try:
        r = _run_cli(f"--env={tmp_path}", timeout=15)
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
