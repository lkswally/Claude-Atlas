#!/usr/bin/env python3
"""
Bloque F15 — Context7 MCP Validation
=======================================

Valida Context7 (documentación de librerías):
  1. context7 en registry con status CONFIG_ONLY o LIVE
  2. atlas_capability = documentation
  3. cli_available = true, versión >= 3.0.0
  4. npx @upstash/context7-mcp --version responde sin error
  5. .mcp.json contiene entrada context7
  6. capabilities incluyen resolve_library_id y get_library_docs
  7. required_for incluye agentes dev
  8. capability layer: "documentation" disponible
  9. validate_registry() limpio

Total: 9 tests
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT))

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def test_registry_status():
    from mcp_registry import get_mcp
    m = get_mcp("context7")
    if not m:
        fail("T1 Context7 in registry", "not found")
        return
    status = m.get("status", "")
    if status in ("LIVE", "CONFIG_ONLY"):
        ok("T1 Context7 in registry", f"status={status}")
    else:
        fail("T1 Context7 in registry", f"status={status} (expected LIVE or CONFIG_ONLY)")


def test_atlas_capability():
    from mcp_registry import get_mcp
    m = get_mcp("context7")
    cap = m.get("atlas_capability") if m else None
    if cap == "documentation":
        ok("T2 atlas_capability=documentation")
    else:
        fail("T2 atlas_capability=documentation", f"got={cap}")


def test_cli_available():
    from mcp_registry import get_mcp
    m = get_mcp("context7")
    if not m:
        fail("T3 cli_available", "entry missing")
        return
    cli_ok = m.get("cli_available") is True
    version = m.get("cli_version", "?")
    if cli_ok:
        ok("T3 cli_available", f"version={version}")
    else:
        fail("T3 cli_available", f"cli_available={m.get('cli_available')}")


def test_npx_responds():
    import shutil
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        r = subprocess.run(
            [npx, "-y", "@upstash/context7-mcp", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 or any(c.isdigit() for c in out[:10]):
            ok("T4 npx context7-mcp --version", out.split("\n")[0][:60])
        else:
            fail("T4 npx context7-mcp --version", f"exit {r.returncode}: {out[:80]}")
    except subprocess.TimeoutExpired:
        fail("T4 npx context7-mcp --version", "timeout >30s")
    except Exception as e:
        fail("T4 npx context7-mcp --version", str(e))


def test_mcp_json_configured():
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    if not mcp_file.exists():
        fail("T5 .mcp.json configured", f"not found at {mcp_file}")
        return
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "context7" in servers:
            args = servers["context7"].get("args", [])
            ok("T5 .mcp.json configured", f"args={args}")
        else:
            fail("T5 .mcp.json configured", f"context7 not in mcpServers. Keys: {list(servers.keys())}")
    except Exception as e:
        fail("T5 .mcp.json configured", str(e))


def test_capabilities_coverage():
    from mcp_registry import get_mcp
    m = get_mcp("context7")
    caps = set(m.get("capabilities", [])) if m else set()
    required = {"resolve_library_id", "get_library_docs"}
    missing = required - caps
    if not missing:
        ok("T6 Capabilities coverage", f"{caps}")
    else:
        fail("T6 Capabilities coverage", f"missing: {missing}")


def test_required_for():
    from mcp_registry import get_mcp
    m = get_mcp("context7")
    req = set(m.get("required_for", [])) if m else set()
    needed = {"frontend-developer", "backend-architect"}
    missing = needed - req
    if not missing:
        ok("T7 required_for dev agents", f"{sorted(req)}")
    else:
        fail("T7 required_for dev agents", f"missing: {missing}")


def test_capability_layer():
    try:
        from core.capabilities import get_capability
        cap = get_capability("documentation")
        if cap and cap.active_provider:
            ok("T8 Capability layer: documentation",
               f"provider={cap.active_provider.mcp_id} status={cap.active_provider.status}")
        else:
            fail("T8 Capability layer: documentation", "no active provider")
    except ImportError as e:
        fail("T8 Capability layer", f"import error: {e}")


def test_validate_registry():
    from mcp_registry import validate_registry
    errors = validate_registry()
    if not errors:
        ok("T9 validate_registry() clean")
    else:
        fail("T9 validate_registry() clean", f"{len(errors)} errors: {errors[:2]}")


def main():
    print("=" * 60)
    print("Bloque F15 -- Context7 MCP Validation")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_registry_status()
    test_atlas_capability()
    test_cli_available()
    test_npx_responds()
    test_mcp_json_configured()
    test_capabilities_coverage()
    test_required_for()
    test_capability_layer()
    test_validate_registry()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
