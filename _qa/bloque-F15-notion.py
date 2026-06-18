#!/usr/bin/env python3
"""
Bloque F15 — Notion MCP Validation
=====================================

Valida el estado LIVE de Notion MCP:
  1. Notion presente en registry con status LIVE
  2. atlas_capability = project_management
  3. Tools detectadas en deferred list (verificación estática de prefijo)
  4. capabilities cubren create/update/fetch/search
  5. required_for incluye project-manager-senior y orquestador
  6. plugin scope (no requiere .mcp.json)
  7. validate_registry() sin errores
  8. capabilities layer: capability "project_management" disponible

Total: 8 tests
"""

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
    suffix = f" -- {detail}" if detail else ""
    print(f"  [PASS] {name}{suffix}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    suffix = f" -- {detail}" if detail else ""
    print(f"  [FAIL] {name}{suffix}")


def test_notion_in_registry():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    if m and m.get("status") == "LIVE":
        ok("T1 Notion in registry LIVE", f"provider={m.get('provider')}")
    else:
        status = m.get("status") if m else "not found"
        fail("T1 Notion in registry LIVE", f"status={status}")


def test_notion_atlas_capability():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    cap = m.get("atlas_capability") if m else None
    if cap == "project_management":
        ok("T2 atlas_capability=project_management")
    else:
        fail("T2 atlas_capability=project_management", f"got={cap}")


def test_notion_tool_prefix():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    prefix = m.get("live_tool_prefix", "") if m else ""
    if "52722bcc" in prefix or "notion" in prefix.lower():
        ok("T3 Tool prefix valid", prefix[:50])
    else:
        fail("T3 Tool prefix valid", f"prefix={prefix}")


def test_notion_capabilities_coverage():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    caps = set(m.get("capabilities", [])) if m else set()
    required = {"create_page", "update_page", "fetch_page", "search"}
    missing = required - caps
    if not missing:
        ok("T4 Capabilities coverage", f"{len(caps)} caps including CRUD+search")
    else:
        fail("T4 Capabilities coverage", f"missing: {missing}")


def test_notion_required_for():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    req = set(m.get("required_for", [])) if m else set()
    needed = {"orquestador", "project-manager-senior"}
    missing = needed - req
    if not missing:
        ok("T5 required_for includes core agents", f"{sorted(req)}")
    else:
        fail("T5 required_for includes core agents", f"missing: {missing}")


def test_notion_plugin_scope():
    from mcp_registry import get_mcp
    m = get_mcp("notion")
    scope = m.get("config_scope", "") if m else ""
    if scope == "plugin":
        ok("T6 config_scope=plugin", "no .mcp.json required")
    else:
        fail("T6 config_scope=plugin", f"scope={scope}")


def test_validate_registry_clean():
    from mcp_registry import validate_registry
    errors = validate_registry()
    if not errors:
        ok("T7 validate_registry() clean")
    else:
        fail("T7 validate_registry() clean", f"{len(errors)} errors: {errors[:2]}")


def test_capability_layer():
    try:
        from core.capabilities import get_capability
        cap = get_capability("project_management")
        if cap and cap.active_provider and cap.active_provider.status == "LIVE":
            ok("T8 Capability layer: project_management LIVE",
               f"provider={cap.active_provider.mcp_id}")
        elif cap:
            fail("T8 Capability layer: project_management LIVE",
                 f"status={cap.active_provider.status if cap.active_provider else 'no provider'}")
        else:
            fail("T8 Capability layer: project_management LIVE", "capability not found")
    except ImportError as e:
        fail("T8 Capability layer", f"import error: {e}")


def main():
    print("=" * 60)
    print("Bloque F15 -- Notion MCP Validation")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_notion_in_registry()
    test_notion_atlas_capability()
    test_notion_tool_prefix()
    test_notion_capabilities_coverage()
    test_notion_required_for()
    test_notion_plugin_scope()
    test_validate_registry_clean()
    test_capability_layer()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
