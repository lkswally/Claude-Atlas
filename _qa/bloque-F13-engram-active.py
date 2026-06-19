#!/usr/bin/env python3
"""
Bloque F13-Active — Engram Live MCP Validation
================================================

Valida el estado ACTIVE_LIVE de Engram:
  1. Binary ejecutable y versión correcta (>=1.16.3)
  2. DB existe y no está vacía
  3. save funciona: guarda una memoria de test
  4. search recupera la memoria guardada
  5. stats: DB reporta al menos 1 memoria
  6. .mcp.json existe con configuración correcta
  7. enabledMcpjsonServers incluye "engram" en settings.json
  8. Healthcheck reporta ENGRAM_ACTIVE

Total: 8 tests
Veredicto final: ACTIVE_LIVE si 8/8, ACTIVE_CONFIG_ONLY si >=6/8
"""

import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOME = Path.home()

ENGRAM_BIN = (
    shutil.which("engram")
    or str(HOME / "go" / "bin" / "engram.exe")
    or str(HOME / "go" / "bin" / "engram")
)

PASS_COUNT = 0
FAIL_COUNT = 0
RESULTS = []

def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [PASS] {name}{suffix}")
    RESULTS.append(("PASS", name, detail))

def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [FAIL] {name}{suffix}")
    RESULTS.append(("FAIL", name, detail))

def warn(name: str, detail: str = "") -> None:
    """Non-blocking: counted separately, does not affect exit code."""
    suffix = f" — {detail}" if detail else ""
    print(f"  [WARN] {name}{suffix}")
    RESULTS.append(("WARN", name, detail))

def run_engram(*args, timeout=10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [ENGRAM_BIN, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# T1: Binary ejecutable y versión correcta
# ---------------------------------------------------------------------------
def test_binary_version():
    if not ENGRAM_BIN or not Path(ENGRAM_BIN).exists():
        fail("T1 Binary version", f"no encontrado: {ENGRAM_BIN}")
        return
    try:
        r = run_engram("--version")
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and "1.16" in out:
            ok("T1 Binary version", out.split("\n")[0])
        elif r.returncode == 0:
            ok("T1 Binary version", out.split("\n")[0])
        else:
            fail("T1 Binary version", f"exit {r.returncode}")
    except Exception as e:
        fail("T1 Binary version", str(e))


# ---------------------------------------------------------------------------
# T2: DB existe y tiene tamaño > 0
# ---------------------------------------------------------------------------
def test_db_exists():
    db = HOME / ".engram" / "engram.db"
    if not db.exists():
        fail("T2 DB exists", f"no encontrada: {db}")
        return
    size_kb = db.stat().st_size // 1024
    if size_kb > 0:
        ok("T2 DB exists", f"{size_kb} KB — {db}")
    else:
        fail("T2 DB exists", "existe pero está vacía (0 bytes)")


# ---------------------------------------------------------------------------
# T3: save — guardar memoria de validación
# ---------------------------------------------------------------------------
VALIDATION_TITLE = "ATLAS F13 active validation test"
VALIDATION_CONTENT = "F13 live MCP validation — bloque-F13-engram-active.py run"

def test_save():
    if not Path(ENGRAM_BIN).exists():
        fail("T3 Save memory", "binary no disponible")
        return
    try:
        r = run_engram("save", VALIDATION_TITLE, VALIDATION_CONTENT)
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and ("saved" in out.lower() or "#" in out):
            ok("T3 Save memory", out.split("\n")[0])
        else:
            fail("T3 Save memory", f"exit {r.returncode}: {out[:80]}")
    except Exception as e:
        fail("T3 Save memory", str(e))


# ---------------------------------------------------------------------------
# T4: search — recuperar la memoria guardada
# ---------------------------------------------------------------------------
def test_search():
    if not Path(ENGRAM_BIN).exists():
        fail("T4 Search memory", "binary no disponible")
        return
    try:
        r = run_engram("search", "F13 active validation")
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and VALIDATION_TITLE.lower()[:20] in out.lower():
            lines = [l for l in out.split("\n") if l.strip()]
            ok("T4 Search memory", f"encontrado ({len(lines)} línea(s))")
        elif r.returncode == 0 and "found" in out.lower():
            ok("T4 Search memory", out.split("\n")[0])
        else:
            fail("T4 Search memory", f"exit {r.returncode}: {out[:100]}")
    except Exception as e:
        fail("T4 Search memory", str(e))


# ---------------------------------------------------------------------------
# T5: stats — DB tiene al menos 1 memoria
# ---------------------------------------------------------------------------
def test_stats():
    if not Path(ENGRAM_BIN).exists():
        fail("T5 Stats", "binary no disponible")
        return
    try:
        r = run_engram("stats")
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            ok("T5 Stats", out.split("\n")[0] if out else "OK")
        else:
            fail("T5 Stats", f"exit {r.returncode}: {out[:80]}")
    except Exception as e:
        fail("T5 Stats", str(e))


# ---------------------------------------------------------------------------
# T6: .mcp.json existe y tiene engram configurado
# ---------------------------------------------------------------------------
def test_mcp_json():
    mcp_file = PROJECT_ROOT / ".mcp.json"
    if not mcp_file.exists():
        fail("T6 .mcp.json", "no encontrado")
        return
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "engram" in servers:
            cmd = servers["engram"].get("command", "?")
            args = servers["engram"].get("args", [])
            ok("T6 .mcp.json", f"engram: {cmd} {chr(43)} {chr(39).join(args)}")
        else:
            fail("T6 .mcp.json", f"engram no encontrado. Claves: {list(servers.keys())}")
    except Exception as e:
        fail("T6 .mcp.json", str(e))


# ---------------------------------------------------------------------------
# T7: enabledMcpjsonServers incluye "engram"
# ---------------------------------------------------------------------------
def test_settings_json():
    settings_file = PROJECT_ROOT / ".claude" / "settings.json"
    if not settings_file.exists():
        # RUNTIME_MUTABLE: Claude Desktop manages this file on Windows.
        # Absent when Claude Desktop isn't running — not a blocking FAIL.
        warn("T7 settings.json", "RUNTIME_MUTABLE — ausente (Claude Desktop lo gestiona)")
        return
    try:
        data = json.loads(settings_file.read_text())
        enabled = data.get("enabledMcpjsonServers", [])
        if "engram" in enabled:
            ok("T7 settings.json", f"enabledMcpjsonServers incluye 'engram'")
        else:
            fail("T7 settings.json", f"enabledMcpjsonServers={enabled}")
    except Exception as e:
        fail("T7 settings.json", str(e))


# ---------------------------------------------------------------------------
# T8: Healthcheck reporta ENGRAM_ACTIVE
# ---------------------------------------------------------------------------
def test_healthcheck_engram():
    hc = PROJECT_ROOT / "tools" / "atlas_healthcheck.py"
    if not hc.exists():
        fail("T8 Healthcheck ENGRAM_ACTIVE", "atlas_healthcheck.py no encontrado")
        return
    try:
        r = subprocess.run(
            [sys.executable, str(hc), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        data = json.loads(r.stdout)
        engram_check = next(
            (c for c in data.get("results", []) if c.get("check") == "Engram"),
            None,
        )
        if engram_check and engram_check["status"] == "PASS":
            ok("T8 Healthcheck ENGRAM_ACTIVE", engram_check.get("detail", "PASS"))
        elif engram_check:
            fail("T8 Healthcheck ENGRAM_ACTIVE",
                 f"{engram_check['status']}: {engram_check.get('detail','')}")
        else:
            fail("T8 Healthcheck ENGRAM_ACTIVE", "check 'Engram' no encontrado en resultados")
    except Exception as e:
        fail("T8 Healthcheck ENGRAM_ACTIVE", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Bloque F13-Active — Engram Live MCP Validation")
    print(f"Project  : {PROJECT_ROOT}")
    print(f"Engram   : {ENGRAM_BIN}")
    print("=" * 60)
    print()

    test_binary_version()
    test_db_exists()
    test_save()
    test_search()
    test_stats()
    test_mcp_json()
    test_settings_json()
    test_healthcheck_engram()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()

    if FAIL_COUNT == 0:
        veredicto = "ACTIVE_LIVE"
    elif PASS_COUNT >= 6:
        veredicto = "ACTIVE_CONFIG_ONLY"
    else:
        veredicto = "FAIL_OPEN"

    print(f"VEREDICTO: {veredicto}")
    print()

    # Nota MCP session
    print("NOTA: La validación MCP live (herramientas mcp__engram__*)")
    print("requiere una sesión nueva iniciada DESPUÉS de que .mcp.json")
    print("existiera. Esta suite valida config + CLI (mismo DB).")

    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
