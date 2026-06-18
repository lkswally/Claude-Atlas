#!/usr/bin/env python3
"""
Bloque F14 — MCP Registry Tests
==================================

Valida config/mcp.registry.yaml y tools/mcp_registry.py:
  1. Registry file existe y es YAML válido
  2. load_registry() retorna >= 8 entradas
  3. Todos los status son válidos
  4. Engram existe en el registry
  5. Engram tiene cli_available = true
  6. MCPs LIVE: al menos 5 detectados
  7. get_mcp("notion") retorna status LIVE
  8. find_mcps(status="MISSING") no incluye LIVE entries
  9. validate_registry() retorna []
 10. summary() tiene campos requeridos
 11. find_mcps(required_for="evidence-collector") incluye playwright o chrome
 12. list_missing_required() no incluye MCPs LIVE

Total: 12 tests
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

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


# ---------------------------------------------------------------------------
# T1: Registry file existe
# ---------------------------------------------------------------------------
def test_registry_file_exists():
    f = PROJECT_ROOT / "config" / "mcp.registry.yaml"
    if f.exists():
        ok("T1 Registry file exists", f"{f.stat().st_size} bytes")
    else:
        fail("T1 Registry file exists", f"not found: {f}")


# ---------------------------------------------------------------------------
# T2: load_registry() retorna >= 8 entradas
# ---------------------------------------------------------------------------
def test_load_registry():
    try:
        from mcp_registry import load_registry
        reg = load_registry()
        if len(reg) >= 8:
            ok("T2 load_registry()", f"{len(reg)} entries")
        else:
            fail("T2 load_registry()", f"only {len(reg)} entries, expected >= 8")
    except Exception as e:
        fail("T2 load_registry()", str(e))


# ---------------------------------------------------------------------------
# T3: Todos los status son válidos
# ---------------------------------------------------------------------------
def test_valid_statuses():
    try:
        from mcp_registry import load_registry
        valid = {"LIVE", "CONFIG_ONLY", "CLI_ONLY", "MISSING", "OPTIONAL"}
        bad = []
        for m in load_registry():
            s = m.get("status", "")
            if s not in valid:
                bad.append(f"{m.get('id','?')}={s}")
        if not bad:
            ok("T3 All statuses valid")
        else:
            fail("T3 All statuses valid", f"invalid: {bad}")
    except Exception as e:
        fail("T3 All statuses valid", str(e))


# ---------------------------------------------------------------------------
# T4: Engram existe en el registry
# ---------------------------------------------------------------------------
def test_engram_exists():
    try:
        from mcp_registry import get_mcp
        m = get_mcp("engram")
        if m:
            ok("T4 Engram in registry", f"status={m.get('status')}")
        else:
            fail("T4 Engram in registry", "not found")
    except Exception as e:
        fail("T4 Engram in registry", str(e))


# ---------------------------------------------------------------------------
# T5: Engram tiene cli_available = true
# ---------------------------------------------------------------------------
def test_engram_cli_available():
    try:
        from mcp_registry import get_mcp
        m = get_mcp("engram")
        if m and m.get("cli_available") is True:
            ok("T5 Engram cli_available", f"version={m.get('cli_version','?')}")
        else:
            val = m.get("cli_available") if m else "entry missing"
            fail("T5 Engram cli_available", f"cli_available={val}")
    except Exception as e:
        fail("T5 Engram cli_available", str(e))


# ---------------------------------------------------------------------------
# T6: MCPs LIVE al menos 5
# ---------------------------------------------------------------------------
def test_live_count():
    try:
        from mcp_registry import list_live
        live = list_live()
        ids = [m["id"] for m in live]
        if len(live) >= 5:
            ok("T6 LIVE MCPs >= 5", f"{len(live)}: {', '.join(ids)}")
        else:
            fail("T6 LIVE MCPs >= 5", f"only {len(live)}: {ids}")
    except Exception as e:
        fail("T6 LIVE MCPs >= 5", str(e))


# ---------------------------------------------------------------------------
# T7: get_mcp("notion") retorna status LIVE
# ---------------------------------------------------------------------------
def test_notion_live():
    try:
        from mcp_registry import get_mcp
        m = get_mcp("notion")
        if m and m.get("status") == "LIVE":
            ok("T7 Notion LIVE")
        else:
            status = m.get("status") if m else "not found"
            fail("T7 Notion LIVE", f"status={status}")
    except Exception as e:
        fail("T7 Notion LIVE", str(e))


# ---------------------------------------------------------------------------
# T8: find_mcps(status="MISSING") no incluye LIVE entries
# ---------------------------------------------------------------------------
def test_missing_not_live():
    try:
        from mcp_registry import find_mcps
        missing = find_mcps(status="MISSING")
        bad = [m["id"] for m in missing if m.get("status") != "MISSING"]
        if not bad:
            ok("T8 MISSING filter clean", f"{len(missing)} entries")
        else:
            fail("T8 MISSING filter clean", f"contaminated: {bad}")
    except Exception as e:
        fail("T8 MISSING filter clean", str(e))


# ---------------------------------------------------------------------------
# T9: validate_registry() retorna []
# ---------------------------------------------------------------------------
def test_validate():
    try:
        from mcp_registry import validate_registry
        errors = validate_registry()
        if not errors:
            ok("T9 validate_registry() clean")
        else:
            fail("T9 validate_registry() clean", f"{len(errors)} errors: {errors[:2]}")
    except Exception as e:
        fail("T9 validate_registry()", str(e))


# ---------------------------------------------------------------------------
# T10: summary() tiene campos requeridos
# ---------------------------------------------------------------------------
def test_summary_fields():
    try:
        from mcp_registry import summary
        s = summary()
        required = {"total", "by_status", "live", "missing_required", "registry_file"}
        missing = required - set(s.keys())
        if not missing:
            ok("T10 summary() fields", f"total={s['total']}, live={len(s['live'])}")
        else:
            fail("T10 summary() fields", f"missing keys: {missing}")
    except Exception as e:
        fail("T10 summary() fields", str(e))


# ---------------------------------------------------------------------------
# T11: find_mcps(required_for="evidence-collector") incluye browser tools
# ---------------------------------------------------------------------------
def test_evidence_collector_mcps():
    try:
        from mcp_registry import find_mcps
        mcps = find_mcps(required_for="evidence-collector")
        ids = {m["id"] for m in mcps}
        browser_tools = {"playwright", "claude_in_chrome", "claude_preview"}
        found = ids & browser_tools
        if found:
            ok("T11 evidence-collector MCPs", f"found: {', '.join(found)}")
        else:
            fail("T11 evidence-collector MCPs", f"no browser tools found. Got: {ids}")
    except Exception as e:
        fail("T11 evidence-collector MCPs", str(e))


# ---------------------------------------------------------------------------
# T12: list_missing_required() no incluye MCPs LIVE
# ---------------------------------------------------------------------------
def test_missing_required_no_live():
    try:
        from mcp_registry import list_missing_required
        mr = list_missing_required()
        bad = [m["id"] for m in mr if m.get("status") == "LIVE"]
        if not bad:
            ok("T12 list_missing_required() excludes LIVE",
               f"{len(mr)} missing: {[m['id'] for m in mr]}")
        else:
            fail("T12 list_missing_required() excludes LIVE", f"LIVE in list: {bad}")
    except Exception as e:
        fail("T12 list_missing_required()", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Bloque F14 -- MCP Registry Tests")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_registry_file_exists()
    test_load_registry()
    test_valid_statuses()
    test_engram_exists()
    test_engram_cli_available()
    test_live_count()
    test_notion_live()
    test_missing_not_live()
    test_validate()
    test_summary_fields()
    test_evidence_collector_mcps()
    test_missing_required_no_live()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()

    if FAIL_COUNT > 0:
        print("RESULTADO: FAIL")
        sys.exit(1)
    else:
        print("RESULTADO: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
