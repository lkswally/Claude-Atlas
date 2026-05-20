#!/usr/bin/env python3
"""
Validacion real de Bloque 1B.1: Engram Strategy Pattern
(preparacion para MCP real en 1B.2)

NO valida Engram MCP real — valida que el plugin point funcione.
8 tests cubren default disk_fallback + callback inyectado + manejo de errores.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from engram_strategy import DiskFallbackStrategy, CallbackStrategy


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_2": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    # Bloque 1B.5: opt-out explicito para preservar semantica disk_fallback de estos tests
    return ATLASDispatcher(root, auto_enable_mcp=False)


def write_cajon(root: Path, cajon_name: str, content: str = "data") -> None:
    (root / ".pipeline" / f"{cajon_name}.md").write_text(content)


# ============================================================
#  TESTS
# ============================================================

def test_1_default_is_disk_fallback():
    print("\n" + "="*70)
    print("TEST 1: Default strategy es DiskFallbackStrategy (NO Engram real)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_cajon(d.project_root, "tareas", "tareas data")

        result = d._check_engram_cajon("atlas", "atlas/tareas")
        print(f"Result: {result}")

        assert result["status"] == "found", f"FAIL: cajon debe existir, got {result}"
        assert result["source"] == "disk_fallback", f"FAIL: source debe ser disk_fallback (NO 'engram_proxy'), got {result['source']}"
        assert "Engram proxy" not in str(result), "FAIL: el termino 'Engram proxy' enganoso NO debe aparecer"
        print("[OK] TEST 1: Default es disk_fallback, naming honesto")


def test_2_regression_phase_gate_with_default():
    print("\n" + "="*70)
    print("TEST 2: Regression 1A.7 — phase gate funciona con default disk_fallback")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_cajon(d.project_root, "tareas")
        write_cajon(d.project_root, "intent")

        can_proceed, message, missing = d.enforce_phase_gate(
            "atlas", "fase_2", ["atlas/tareas", "atlas/intent"]
        )
        print(f"can_proceed={can_proceed}, missing={missing}")
        assert can_proceed is True
        assert missing == []
        print("[OK] TEST 2: Regression OK — comportamiento default preservado")


def test_3_callback_returns_found():
    print("\n" + "="*70)
    print("TEST 3: Callback retorna found -> dispatcher usa callback (no disco)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # NO crear archivo en disco — callback es autoritativo

        def fake_mcp(proyecto, cajon):
            return {"status": "found", "observation_id": "obs-123", "topic_key": cajon}

        d.set_engram_callback(fake_mcp, name="fake_mcp")

        result = d._check_engram_cajon("atlas", "atlas/tareas")
        print(f"Result: {result}")
        assert result["status"] == "found"
        assert result.get("observation_id") == "obs-123"
        assert result["source"] == "fake_mcp"
        print("[OK] TEST 3: Callback autoritativo cuando retorna found")


def test_4_callback_returns_not_found():
    print("\n" + "="*70)
    print("TEST 4: Callback not_found + sin disco -> not_found")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        def fake_mcp(proyecto, cajon):
            return {"status": "not_found", "cajon": cajon}

        d.set_engram_callback(fake_mcp, name="fake_mcp")
        result = d._check_engram_cajon("atlas", "atlas/missing")
        print(f"Result: {result}")
        assert result["status"] == "not_found"
        print("[OK] TEST 4: not_found respetado")


def test_5_callback_timeout_falls_back_to_disk():
    print("\n" + "="*70)
    print("TEST 5: Callback timeout + disco TIENE el cajon -> fallback found")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_cajon(d.project_root, "tareas", "disco tiene el cajon")

        def fake_mcp(proyecto, cajon):
            return {"status": "timeout", "error": "MCP no responde"}

        d.set_engram_callback(fake_mcp, name="fake_mcp")
        result = d._check_engram_cajon("atlas", "atlas/tareas")
        print(f"Result: {result}")
        assert result["status"] == "found", f"FAIL: fallback a disco debe encontrar, got {result}"
        assert result.get("fallback_used") is True
        assert result.get("callback_status") == "timeout"
        print("[OK] TEST 5: timeout activa fallback a disco")


def test_6_callback_raises_exception():
    print("\n" + "="*70)
    print("TEST 6: Callback raisea Exception -> capturada, fallback a disco")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_cajon(d.project_root, "tareas")

        def buggy_mcp(proyecto, cajon):
            raise ConnectionError("MCP server unreachable")

        d.set_engram_callback(buggy_mcp, name="buggy_mcp")

        # NO debe propagar excepcion
        try:
            result = d._check_engram_cajon("atlas", "atlas/tareas")
            print(f"Result: {result}")
        except ConnectionError:
            assert False, "FAIL: excepcion del callback NO debe propagarse"

        # Debe haber hecho fallback a disco
        assert result["status"] == "found", f"FAIL: disk fallback debe encontrar, got {result}"
        assert result.get("fallback_used") is True
        assert "ConnectionError" in result.get("callback_error", ""), "FAIL: callback_error debe describir la excepcion"
        print("[OK] TEST 6: Exception capturada + fallback exitoso")


def test_7_callback_invalid_format():
    print("\n" + "="*70)
    print("TEST 7: Callback retorna formato invalido -> tratado como timeout")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        def bad_format_mcp(proyecto, cajon):
            return "not a dict"  # formato invalido

        d.set_engram_callback(bad_format_mcp, name="bad_format_mcp", use_disk_fallback=False)
        result = d._check_engram_cajon("atlas", "atlas/tareas")
        print(f"Result: {result}")
        assert result["status"] == "timeout"
        assert "invalid format" in result.get("error", "")
        print("[OK] TEST 7: Formato invalido manejado como timeout")


def test_8_unset_callback_restores_disk_fallback():
    print("\n" + "="*70)
    print("TEST 8: set_engram_callback(None) restaura DiskFallbackStrategy")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_cajon(d.project_root, "tareas")

        # Set custom callback
        d.set_engram_callback(lambda p, c: {"status": "not_found"}, name="custom")
        result1 = d._check_engram_cajon("atlas", "atlas/tareas")
        assert result1["status"] == "not_found", f"FAIL: callback debe estar activo, got {result1}"

        # Reset
        d.set_engram_callback(None)
        result2 = d._check_engram_cajon("atlas", "atlas/tareas")
        print(f"After reset: {result2}")
        assert result2["status"] == "found", "FAIL: tras reset debe usar disk_fallback"
        assert result2["source"] == "disk_fallback"
        print("[OK] TEST 8: Reset a default funciona")


def test_9_naming_honesty():
    print("\n" + "="*70)
    print("TEST 9: Naming honesto — strategies se llaman por lo que son")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Default
        assert d._engram_strategy.name == "disk_fallback", f"FAIL: default name debe ser disk_fallback, got {d._engram_strategy.name}"

        # Con callback
        d.set_engram_callback(lambda p, c: {"status": "found"}, name="mock_mcp")
        assert d._engram_strategy.name == "mock_mcp"

        print("[OK] TEST 9: Naming honesto preservado")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1B.1: Engram Strategy Pattern")
    print("                   (preparacion para MCP real en 1B.2)")
    print("="*70)

    tests = [
        test_1_default_is_disk_fallback,
        test_2_regression_phase_gate_with_default,
        test_3_callback_returns_found,
        test_4_callback_returns_not_found,
        test_5_callback_timeout_falls_back_to_disk,
        test_6_callback_raises_exception,
        test_7_callback_invalid_format,
        test_8_unset_callback_restores_disk_fallback,
        test_9_naming_honesty,
    ]

    passed = 0
    failed = 0
    try:
        for t in tests:
            t()
            passed += 1
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        failed += 1

    print("\n" + "="*70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("="*70)

    if failed == 0:
        print("\nCONCLUSION HONESTA:")
        print("[OK] Strategy pattern operativo — plugin point listo para 1B.2")
        print("[OK] Default sigue siendo disk_fallback (NO Engram real)")
        print("[OK] Callback inyectable manejando found/not_found/timeout/exception")
        print("[OK] Fallback a disco cuando callback falla")
        print("[OK] Naming honesto en codigo y output")
        print("\nLO QUE FALTA PARA 1B.2:")
        print("- MCPBridgeStrategy real (Python MCP SDK o subprocess o agent-delegation)")
        print("- Integracion con orquestador para inyectar el callback en boot")
        print("- Validacion end-to-end con mem_search() real")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
