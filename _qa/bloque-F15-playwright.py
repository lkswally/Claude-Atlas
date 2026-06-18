#!/usr/bin/env python3
"""
Bloque F15 — Playwright MCP Validation
=========================================

Valida Playwright MCP (browser QA):
  1. playwright en registry con status CONFIG_ONLY o LIVE
  2. atlas_capability = browser
  3. cli_available = true, versión presente
  4. npx @playwright/mcp --version responde sin error
  5. Chromium browser instalado en disco
  6. .mcp.json contiene entrada playwright
  7. capabilities incluyen browser_navigate, browser_screenshot, browser_click
  8. required_for incluye evidence-collector y reality-checker
  9. capability layer: "browser" disponible
 10. validate_registry() limpio

Total: 10 tests
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
    m = get_mcp("playwright")
    if not m:
        fail("T1 Playwright in registry", "not found")
        return
    status = m.get("status", "")
    if status in ("LIVE", "CONFIG_ONLY"):
        ok("T1 Playwright in registry", f"status={status}")
    else:
        fail("T1 Playwright in registry", f"status={status} (expected LIVE or CONFIG_ONLY)")


def test_atlas_capability():
    from mcp_registry import get_mcp
    m = get_mcp("playwright")
    cap = m.get("atlas_capability") if m else None
    if cap == "browser":
        ok("T2 atlas_capability=browser")
    else:
        fail("T2 atlas_capability=browser", f"got={cap}")


def test_cli_available():
    from mcp_registry import get_mcp
    m = get_mcp("playwright")
    if not m:
        fail("T3 cli_available", "entry missing"); return
    if m.get("cli_available") is True:
        ok("T3 cli_available", f"version={m.get('cli_version','?')}")
    else:
        fail("T3 cli_available", f"cli_available={m.get('cli_available')}")


def test_npx_mcp_responds():
    import shutil
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        r = subprocess.run(
            [npx, "-y", "@playwright/mcp", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            ok("T4 npx @playwright/mcp --version", out.split("\n")[0][:60])
        else:
            fail("T4 npx @playwright/mcp --version", f"exit {r.returncode}: {out[:80]}")
    except subprocess.TimeoutExpired:
        fail("T4 npx @playwright/mcp --version", "timeout >30s")
    except Exception as e:
        fail("T4 npx @playwright/mcp --version", str(e))


def test_chromium_installed():
    import os
    ms_playwright = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not ms_playwright.exists():
        fail("T5 Chromium installed", f"ms-playwright dir not found: {ms_playwright}")
        return
    chromium_dirs = [d for d in ms_playwright.iterdir() if "chromium" in d.name.lower()]
    if chromium_dirs:
        sizes = [sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) // (1024*1024)
                 for d in chromium_dirs]
        ok("T5 Chromium installed", f"{len(chromium_dirs)} browser(s): {[d.name for d in chromium_dirs]}, ~{sum(sizes)}MB")
    else:
        fail("T5 Chromium installed", f"no chromium in {ms_playwright}")


def test_mcp_json_configured():
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    if not mcp_file.exists():
        fail("T6 .mcp.json configured", "not found"); return
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "playwright" in servers:
            args = servers["playwright"].get("args", [])
            ok("T6 .mcp.json configured", f"args={args}")
        else:
            fail("T6 .mcp.json configured", f"playwright not in mcpServers. Keys: {list(servers.keys())}")
    except Exception as e:
        fail("T6 .mcp.json configured", str(e))


def test_capabilities_coverage():
    from mcp_registry import get_mcp
    m = get_mcp("playwright")
    caps = set(m.get("capabilities", [])) if m else set()
    required = {"browser_navigate", "browser_screenshot", "browser_click", "browser_evaluate"}
    missing = required - caps
    if not missing:
        ok("T7 Capabilities coverage", f"{len(caps)} caps")
    else:
        fail("T7 Capabilities coverage", f"missing: {missing}")


def test_required_for():
    from mcp_registry import get_mcp
    m = get_mcp("playwright")
    req = set(m.get("required_for", [])) if m else set()
    needed = {"evidence-collector", "reality-checker"}
    missing = needed - req
    if not missing:
        ok("T8 required_for QA agents", f"{sorted(req)}")
    else:
        fail("T8 required_for QA agents", f"missing: {missing}")


def test_capability_layer():
    try:
        from core.capabilities import get_capability
        cap = get_capability("browser")
        if not cap:
            fail("T9 Capability layer: browser", "not found"); return
        p = cap.active_provider
        if p:
            ok("T9 Capability layer: browser", f"provider={p.mcp_id} status={p.status}")
        else:
            fail("T9 Capability layer: browser", "no active provider")
    except ImportError as e:
        fail("T9 Capability layer", f"import error: {e}")


def test_validate_registry():
    from mcp_registry import validate_registry
    errors = validate_registry()
    if not errors:
        ok("T10 validate_registry() clean")
    else:
        fail("T10 validate_registry() clean", f"{len(errors)} errors: {errors[:2]}")


def main():
    print("=" * 60)
    print("Bloque F15 -- Playwright MCP Validation")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_registry_status()
    test_atlas_capability()
    test_cli_available()
    test_npx_mcp_responds()
    test_chromium_installed()
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
