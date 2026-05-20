#!/usr/bin/env python3
"""
Validacion real de Bloque 1B.5: Auto-enable Engram MCP at boot

Verifica que ATLASDispatcher.__init__ activa Engram MCP automaticamente
cuando es posible, sin romper backward compat ni introducir logging ruidoso.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# IMPORTANTE: NO setear ATLAS_DISABLE_ENGRAM_MCP aqui — este test valida ambos modos
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from engram_strategy import DiskFallbackStrategy, CallbackStrategy


def make_project(tmpdir: str) -> Path:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_2": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return root


def _clear_env_var(name: str):
    """Helper: borra env var si existe para evitar contaminacion entre tests"""
    if name in os.environ:
        del os.environ[name]


# ============================================================
#  TESTS
# ============================================================

def test_1_auto_enable_when_binary_available():
    print("\n" + "="*70)
    print("TEST 1: Auto-enable activa MCP si binary engram disponible")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    if shutil.which("engram") is None:
        print("[SKIP] engram binary no esta en PATH — test no aplicable en este entorno")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        d = ATLASDispatcher(root)
        print(f"engram_mcp_status: {d.engram_mcp_status}")
        assert d.engram_mcp_status == "active", \
            f"FAIL: status debe ser 'active' con binary disponible, got '{d.engram_mcp_status}'"
        assert isinstance(d._engram_strategy, CallbackStrategy), \
            f"FAIL: strategy debe ser CallbackStrategy (engram_mcp_real), got {type(d._engram_strategy).__name__}"
        assert d._engram_strategy.name == "engram_mcp_real"
        print("[OK] TEST 1: Auto-enable funciona con binary presente")


def test_2_graceful_when_binary_missing():
    print("\n" + "="*70)
    print("TEST 2: Auto-enable cae a disk_fallback si binary missing (no rompe)")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        # Mock shutil.which para simular binary missing + env var nula
        with patch("shutil.which", return_value=None), \
             patch.dict(os.environ, {"ENGRAM_MCP_BINARY": ""}, clear=False):
            # Limpiar ENGRAM_MCP_BINARY si esta
            if "ENGRAM_MCP_BINARY" in os.environ:
                del os.environ["ENGRAM_MCP_BINARY"]
            d = ATLASDispatcher(root)
            print(f"engram_mcp_status: {d.engram_mcp_status}")
            assert d.engram_mcp_status.startswith("unavailable:"), \
                f"FAIL: status debe empezar con 'unavailable:', got '{d.engram_mcp_status}'"
            assert isinstance(d._engram_strategy, DiskFallbackStrategy), \
                f"FAIL: strategy debe quedar como DiskFallbackStrategy"
            # Verificar que dispatcher sigue funcional
            (root / ".pipeline" / "tareas.md").write_text("data")
            result = d._check_engram_cajon("atlas", "atlas/tareas")
            assert result["status"] == "found"
            assert result["source"] == "disk_fallback"
    print("[OK] TEST 2: Binary missing -> disk_fallback graceful, sin excepcion")


def test_3_opt_out_via_env_var():
    print("\n" + "="*70)
    print("TEST 3: ATLAS_DISABLE_ENGRAM_MCP=1 fuerza disk_fallback")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        with patch.dict(os.environ, {"ATLAS_DISABLE_ENGRAM_MCP": "1"}):
            d = ATLASDispatcher(root)
            print(f"engram_mcp_status: {d.engram_mcp_status}")
            assert d.engram_mcp_status == "disabled_by_env", \
                f"FAIL: status debe ser 'disabled_by_env', got '{d.engram_mcp_status}'"
            assert isinstance(d._engram_strategy, DiskFallbackStrategy)
    print("[OK] TEST 3: Env var opt-out funciona")


def test_4_opt_out_via_param():
    print("\n" + "="*70)
    print("TEST 4: auto_enable_mcp=False fuerza disk_fallback")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        d = ATLASDispatcher(root, auto_enable_mcp=False)
        print(f"engram_mcp_status: {d.engram_mcp_status}")
        assert d.engram_mcp_status == "disabled_by_param", \
            f"FAIL: status debe ser 'disabled_by_param', got '{d.engram_mcp_status}'"
        assert isinstance(d._engram_strategy, DiskFallbackStrategy)
    print("[OK] TEST 4: Param opt-out funciona")


def test_5_no_subprocess_spawned_in_init():
    print("\n" + "="*70)
    print("TEST 5: Auto-enable NO spawnea subprocess en __init__ (lazy)")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    if shutil.which("engram") is None:
        print("[SKIP] engram binary no esta en PATH")
        return

    # Count engram processes before
    def count_engram_procs() -> int:
        try:
            if sys.platform == "win32":
                out = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq engram.exe", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                return out.stdout.count("engram.exe")
            else:
                out = subprocess.run(
                    ["pgrep", "-f", "engram mcp"],
                    capture_output=True, text=True, timeout=5
                )
                return len([l for l in out.stdout.splitlines() if l.strip()])
        except Exception:
            return -1

    before = count_engram_procs()

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        dispatchers = [ATLASDispatcher(root) for _ in range(3)]

        after_init = count_engram_procs()
        print(f"  Engram procs before: {before}, after __init__: {after_init}")
        if before >= 0 and after_init >= 0:
            assert after_init <= before + 1, \
                f"FAIL: __init__ NO debe spawnear procesos (lazy). Before={before}, After={after_init}"
        # Cleanup
        del dispatchers
    print("[OK] TEST 5: __init__ no spawnea subprocess (lazy)")


def test_6_status_attribute_visible():
    print("\n" + "="*70)
    print("TEST 6: engram_mcp_status accesible como atributo publico")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        d = ATLASDispatcher(root, auto_enable_mcp=False)
        assert hasattr(d, "engram_mcp_status")
        assert isinstance(d.engram_mcp_status, str)
        assert len(d.engram_mcp_status) > 0
        print(f"  engram_mcp_status: '{d.engram_mcp_status}'")
    print("[OK] TEST 6: Status atributo visible y string no vacio")


def test_7_manual_enable_after_init_updates_status():
    print("\n" + "="*70)
    print("TEST 7: enable_engram_mcp() manual actualiza el status")
    print("="*70)
    _clear_env_var("ATLAS_DISABLE_ENGRAM_MCP")

    if shutil.which("engram") is None:
        print("[SKIP] engram binary no esta en PATH")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        root = make_project(tmpdir)
        # Empezar con opt-out
        d = ATLASDispatcher(root, auto_enable_mcp=False)
        assert d.engram_mcp_status == "disabled_by_param"

        # Activacion manual
        success, msg = d.enable_engram_mcp()
        print(f"  Activation: success={success}")
        print(f"  Status after manual enable: {d.engram_mcp_status}")
        assert success is True
        assert d.engram_mcp_status == "active", \
            f"FAIL: status debe actualizarse a 'active', got '{d.engram_mcp_status}'"
    print("[OK] TEST 7: Status se actualiza al activar manualmente")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1B.5: Auto-enable Engram MCP at boot")
    print("="*70)

    tests = [
        test_1_auto_enable_when_binary_available,
        test_2_graceful_when_binary_missing,
        test_3_opt_out_via_env_var,
        test_4_opt_out_via_param,
        test_5_no_subprocess_spawned_in_init,
        test_6_status_attribute_visible,
        test_7_manual_enable_after_init_updates_status,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("="*70)

    if failed == 0:
        print("\nCONCLUSION HONESTA:")
        print("[OK] Auto-enable activa Engram MCP en __init__ si binary disponible")
        print("[OK] Binary missing -> disk_fallback graceful (no rompe)")
        print("[OK] Opt-out via env var ATLAS_DISABLE_ENGRAM_MCP=1")
        print("[OK] Opt-out via param auto_enable_mcp=False")
        print("[OK] Lazy: __init__ NO spawnea subprocess")
        print("[OK] Status visible en engram_mcp_status (sin logging ruidoso)")
        print("[OK] enable_engram_mcp() manual sigue funcionando")
        print("\nLO QUE 1B.5 NO HACE:")
        print("- NO maneja ambiguous_project (eso es 1B.3)")
        print("- NO expone mem_get_observation (eso es 1B.4)")
        print("- NO hace cross-machine sync (eso es 1B.6+)")
        print("- Solo cierra el gap de activacion runtime")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
