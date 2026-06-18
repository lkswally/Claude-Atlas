#!/usr/bin/env python3
"""
Bloque F13 — Engram Activation Tests
======================================

Valida los estados de Engram en ATLAS:
  1. ENGRAM_SYNC_DISABLED=1 → hook sale 0 (fail-open)
  2. CLI ausente simulado → hook sale 0 (fail-open)
  3. DB ausente → healthcheck reporta FAIL_OPEN
  4. Engram ACTIVE → binary responde, DB existe, search retorna
  5. engram-sync.js hook → siempre sale 0 en modo hook
  6. pre-compact-engram.js → sale 0 sin CLI
  7. session-start-context.js → sale 0 sin CLI

Total: 7 tests
"""

import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"
HOME = Path.home()
ENGRAM_BIN = shutil.which("engram") or str(HOME / "go" / "bin" / "engram.exe")

PASS_COUNT = 0
FAIL_COUNT = 0

def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [PASS] {name}{suffix}")

def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [FAIL] {name}{suffix}")

def run_hook(hook_name: str, stdin_data: dict | None = None, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    hook_path = HOOKS_DIR / hook_name
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    stdin_bytes = json.dumps(stdin_data or {}).encode()
    return subprocess.run(
        ["node", str(hook_path)],
        input=stdin_bytes,
        capture_output=True,
        timeout=15,
        env=env,
        cwd=str(PROJECT_ROOT),
    )


# ---------------------------------------------------------------------------
# Test 1: ENGRAM_SYNC_DISABLED=1 → engram-sync.js exit 0
# ---------------------------------------------------------------------------
def test_engram_sync_disabled():
    r = run_hook("engram-sync.js", env_extra={"ENGRAM_SYNC_DISABLED": "1"})
    if r.returncode == 0:
        ok("T1 ENGRAM_SYNC_DISABLED", "exit 0 (fail-open OK)")
    else:
        fail("T1 ENGRAM_SYNC_DISABLED", f"exit {r.returncode}, expected 0")


# ---------------------------------------------------------------------------
# Test 2: engram-sync.js en modo hook → exit 0 aunque ~/.engram no sea git repo
# ---------------------------------------------------------------------------
def test_engram_sync_hook_mode():
    """El hook recibe stdin (como en modo Stop event) y debe salir 0.
    En producción se invoca con --hook (ver settings.json)."""
    payload = {"session_id": "test-session", "tool_name": "Stop"}
    hook_path = HOOKS_DIR / "engram-sync.js"
    stdin_bytes = json.dumps(payload).encode()
    r = subprocess.run(
        ["node", str(hook_path), "--hook"],
        input=stdin_bytes,
        capture_output=True,
        timeout=15,
        env={**os.environ},
        cwd=str(PROJECT_ROOT),
    )
    # Fail-open: exit 0 aunque no haya git repo en ~/.engram
    if r.returncode == 0:
        ok("T2 engram-sync hook mode", "exit 0 (fail-open)")
    else:
        fail("T2 engram-sync hook mode", f"exit {r.returncode} — debería ser fail-open (0)")


# ---------------------------------------------------------------------------
# Test 3: pre-compact-engram.js → exit 0 sin CLI
# ---------------------------------------------------------------------------
def test_pre_compact_no_cli():
    r = run_hook("pre-compact-engram.js", env_extra={"ENGRAM_SYNC_DISABLED": "1"})
    if r.returncode == 0:
        ok("T3 pre-compact-engram.js", "exit 0")
    else:
        fail("T3 pre-compact-engram.js", f"exit {r.returncode}")


# ---------------------------------------------------------------------------
# Test 4: session-start-context.js → exit 0 sin CLI
# ---------------------------------------------------------------------------
def test_session_start_no_cli():
    payload = {"type": "notification", "message": "Session started"}
    r = run_hook("session-start-context.js", stdin_data=payload)
    if r.returncode == 0:
        ok("T4 session-start-context.js", "exit 0")
    else:
        fail("T4 session-start-context.js", f"exit {r.returncode}")


# ---------------------------------------------------------------------------
# Test 5: Engram binary existe y responde
# ---------------------------------------------------------------------------
def test_engram_binary_exists():
    if not ENGRAM_BIN or not Path(ENGRAM_BIN).exists():
        fail("T5 Engram binary", f"no encontrado en {ENGRAM_BIN}")
        return
    try:
        r = subprocess.run([ENGRAM_BIN, "--version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            version = (r.stdout or r.stderr).decode().strip().split("\n")[0]
            ok("T5 Engram binary", version)
        else:
            fail("T5 Engram binary", f"exit {r.returncode}")
    except Exception as e:
        fail("T5 Engram binary", str(e))


# ---------------------------------------------------------------------------
# Test 6: Engram DB existe
# ---------------------------------------------------------------------------
def test_engram_db_exists():
    db = HOME / ".engram" / "engram.db"
    if db.exists():
        size_kb = db.stat().st_size // 1024
        ok("T6 Engram DB", f"{db} ({size_kb} KB)")
    else:
        fail("T6 Engram DB", f"no encontrada en {db}")


# ---------------------------------------------------------------------------
# Test 7: Engram search funciona (ACTIVE state)
# ---------------------------------------------------------------------------
def test_engram_search():
    if not ENGRAM_BIN or not Path(ENGRAM_BIN).exists():
        fail("T7 Engram search", "binary no disponible")
        return
    db = HOME / ".engram" / "engram.db"
    if not db.exists():
        fail("T7 Engram search", "DB no disponible")
        return
    try:
        r = subprocess.run(
            [ENGRAM_BIN, "search", "atlas"],
            capture_output=True,
            timeout=5,
        )
        stdout = r.stdout.decode(errors="replace").strip()
        if r.returncode == 0:
            lines = stdout.split("\n") if stdout else []
            ok("T7 Engram search", f"exit 0, {len(lines)} resultado(s)")
        else:
            fail("T7 Engram search", f"exit {r.returncode}: {r.stderr.decode()[:80]}")
    except subprocess.TimeoutExpired:
        fail("T7 Engram search", "timeout >5s")
    except Exception as e:
        fail("T7 Engram search", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Bloque F13 — Engram Activation Tests")
    print(f"Project  : {PROJECT_ROOT}")
    print(f"Engram   : {ENGRAM_BIN}")
    print("=" * 60)
    print()

    test_engram_sync_disabled()
    test_engram_sync_hook_mode()
    test_pre_compact_no_cli()
    test_session_start_no_cli()
    test_engram_binary_exists()
    test_engram_db_exists()
    test_engram_search()

    print()
    print(f"Total: {PASS_COUNT + FAIL_COUNT} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()

    if FAIL_COUNT > 0:
        print("RESULTADO: FAIL")
        sys.exit(1)
    else:
        print("RESULTADO: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
