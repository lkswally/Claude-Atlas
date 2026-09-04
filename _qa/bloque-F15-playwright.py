#!/usr/bin/env python3
"""
Bloque F15 — Playwright MCP Validation
=========================================

Valida el CONTRATO/CONFIGURACION del provider Playwright, no su reachability
en vivo (eso es un diagnostico Browser E2E separado — ver
docs/F15-CI-DETERMINISM-FIX.md). Cada test se etiqueta con el concepto que
prueba (nunca equivalentes entre si):

  REGISTERED       — declarado en config/mcp.registry.yaml
  CONFIGURED       — .mcp.json (runtime) lo referencia
  PACKAGE_AVAILABLE — el paquete npm existe en el cache LOCAL (offline, sin red)
  LIVE_REACHABLE   — el MCP server responde AHORA (requiere red — diagnostico
                      opcional, nunca bloqueante en quick/release/CI)

  1. [REGISTERED]        playwright en registry con status CONFIG_ONLY o LIVE
  2. [REGISTERED]        atlas_capability = browser
  3. [REGISTERED]        cli_available = true, versión presente
  4. [PACKAGE_AVAILABLE] npx --offline @playwright/mcp --version — deterministico,
                         sin red. PASS si esta cacheado localmente, SKIP (no FAIL)
                         si el runner esta limpio — un runner limpio sin el
                         paquete preinstalado es un estado ESPERADO, no una rotura.
  5. [PACKAGE_AVAILABLE] Chromium browser instalado en disco (SKIP si ausente)
  6. [CONFIGURED]        .mcp.json contiene entrada playwright (SKIP si ausente)
  7. [REGISTERED]        capabilities incluyen browser_navigate, browser_screenshot, browser_click
  8. [REGISTERED]        required_for incluye evidence-collector y reality-checker
  9. [REGISTERED/CONFIGURED] capability layer: "browser" disponible via resolve_capability()
 10. [REGISTERED]        validate_registry() limpio

Total: 10 tests (bloqueantes) + 1 diagnostico opcional LIVE_REACHABLE
(--network-diagnostic o ATLAS_RUN_NETWORK_DIAGNOSTIC=1 — nunca cuenta para
PASS/FAIL, es puramente informativo; requiere red y puede tardar hasta 30s).
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


def skip(name: str, detail: str = "") -> None:
    """Non-blocking: env dependency absent (e.g. CI). Does not affect exit code."""
    print(f"  [SKIP] {name}{' -- ' + detail if detail else ''}")


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


def test_package_available_offline():
    """
    PACKAGE_AVAILABLE, not LIVE_REACHABLE: `--offline` forces npx to resolve
    purely from the local npm cache -- zero network I/O. Deterministic and
    fast (no CI cold-fetch latency to time out on). A clean runner without
    this package cached is an EXPECTED state (SKIP), not a broken one (FAIL).
    Root cause of the old always-FAIL-on-clean-CI behavior: `npx -y <pkg>`
    (no --offline) always round-trips to the npm registry to resolve the
    version even when `-y` is set (`-y` only skips the install-confirmation
    prompt, it does not mean "prefer cache") -- on a fresh GitHub Actions
    runner (actions/setup-node has no `cache:` param in this repo's
    .github/workflows/ci.yml, confirmed) the npm cache is genuinely empty
    every run, so this was structurally guaranteed to be slow/flaky, not a
    transient network hiccup. See docs/F15-CI-DETERMINISM-FIX.md.
    """
    import shutil
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        r = subprocess.run(
            [npx, "--offline", "-y", "@playwright/mcp", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            ok("T4 package available (offline)", out.split("\n")[0][:60])
        else:
            skip("T4 package available (offline)",
                 f"no preinstalado localmente (CI/entorno limpio, no bloqueante): {out[:80]}")
    except subprocess.TimeoutExpired:
        skip("T4 package available (offline)", "timeout >10s en modo offline (no bloqueante)")
    except Exception as e:
        skip("T4 package available (offline)", str(e))


def test_live_reachable_diagnostic():
    """
    LIVE_REACHABLE (optional, opt-in, NEVER blocking): a real network fetch
    of the package, informational only. This is the ONLY place in this file
    that touches the network. It never calls ok()/fail() -- it cannot affect
    PASS_COUNT/FAIL_COUNT or the process exit code, by construction. This is
    NOT the Browser E2E diagnostic (real Chromium launch/navigate/screenshot)
    -- that lives in docs/BROWSER-VISUAL-QA-DIAGNOSTIC.md and is a distinct,
    separate concern from this file's contract/config validation.
    """
    import os
    import shutil
    if os.environ.get("ATLAS_RUN_NETWORK_DIAGNOSTIC") != "1" and "--network-diagnostic" not in sys.argv:
        return
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        r = subprocess.run(
            [npx, "-y", "@playwright/mcp", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0:
            print(f"  [INFO] LIVE_REACHABLE (network) -- OK: {out.splitlines()[0][:60]}")
        else:
            print(f"  [INFO] LIVE_REACHABLE (network) -- unreachable: {out[:80]} (informational only)")
    except subprocess.TimeoutExpired:
        print("  [INFO] LIVE_REACHABLE (network) -- timeout >30s (informational only)")
    except Exception as e:
        print(f"  [INFO] LIVE_REACHABLE (network) -- {e} (informational only)")


def test_chromium_installed():
    import os
    ms_playwright = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    if not ms_playwright.exists():
        # Playwright browser cache is an optional local install; absent in clean
        # CI runners → SKIP, not FAIL (the MCP/registry checks above still run).
        skip("T5 Chromium installed", f"ms-playwright ausente (CI/entorno limpio): {ms_playwright}")
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
        # Runtime MCP config (Claude Desktop), not committed → SKIP in CI.
        skip("T6 .mcp.json configured", f"runtime .mcp.json ausente (CI/entorno limpio): {mcp_file}"); return
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
    test_package_available_offline()
    test_chromium_installed()
    test_mcp_json_configured()
    test_capabilities_coverage()
    test_required_for()
    test_capability_layer()
    test_validate_registry()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")

    # Opt-in only (ATLAS_RUN_NETWORK_DIAGNOSTIC=1 or --network-diagnostic).
    # Never affects PASS_COUNT/FAIL_COUNT/exit code -- see docstring above.
    test_live_reachable_diagnostic()

    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
