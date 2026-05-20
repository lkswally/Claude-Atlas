#!/usr/bin/env python3
"""
Validacion real de Bloque 1D.1: Delegation Stop Rules Enforcement
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Opt-out de Engram auto-enable para aislamiento
os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from delegation_tracker import (
    DelegationTracker,
    THRESHOLD_CONSECUTIVE_READS,
    THRESHOLD_TOOL_CALLS_WITHOUT_SPAWN,
    THRESHOLD_NON_TRIVIAL_FILES_MODIFIED,
)


def make_tracker(tmpdir: str) -> DelegationTracker:
    root = Path(tmpdir)
    return DelegationTracker(root)


# ============================================================
#  TESTS
# ============================================================

def test_1_consecutive_reads_threshold():
    print("\n" + "="*70)
    print("TEST 1: 5 Reads consecutivas -> escalation_needed")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # 4 reads: NO debe disparar
        for i in range(4):
            t.record_tool_call("Read", {"file_path": f"src/file{i}.ts"})
        state = t.get_state()
        print(f"After 4 reads: consecutive_reads={state['consecutive_reads']}, escalation={state['flags']['escalation_needed']}")
        assert state["consecutive_reads"] == 4
        assert state["flags"]["escalation_needed"] is False

        # 5ta read: dispara
        t.record_tool_call("Read", {"file_path": "src/file4.ts"})
        state = t.get_state()
        print(f"After 5 reads: consecutive_reads={state['consecutive_reads']}, escalation={state['flags']['escalation_needed']}")
        assert state["consecutive_reads"] == 5
        assert state["flags"]["escalation_needed"] is True
    print("[OK] TEST 1: Threshold de 5 reads consecutivas detectado")


def test_2_tool_calls_threshold():
    print("\n" + "="*70)
    print("TEST 2: 20 tool calls sin Agent -> pause_recommended")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # 19 calls (alternados para no disparar escalation_needed)
        tools_cycle = ["Read", "Bash", "Grep"]
        for i in range(19):
            t.record_tool_call(tools_cycle[i % 3])
        state = t.get_state()
        print(f"After 19 calls: total={state['total_tool_calls_since_spawn']}, pause={state['flags']['pause_recommended']}")
        assert state["total_tool_calls_since_spawn"] == 19
        assert state["flags"]["pause_recommended"] is False

        # 20mo: dispara
        t.record_tool_call("Bash")
        state = t.get_state()
        print(f"After 20 calls: total={state['total_tool_calls_since_spawn']}, pause={state['flags']['pause_recommended']}")
        assert state["total_tool_calls_since_spawn"] == 20
        assert state["flags"]["pause_recommended"] is True
    print("[OK] TEST 2: Threshold de 20 tool calls detectado")


def test_3_non_trivial_files_threshold():
    print("\n" + "="*70)
    print("TEST 3: 2 archivos no-triviales modificados -> fresh_review_recommended")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # 1 archivo no-trivial
        t.record_tool_call("Edit", {"file_path": "src/components/Header.tsx"})
        state = t.get_state()
        assert state["flags"]["fresh_review_recommended"] is False

        # 2do archivo no-trivial
        t.record_tool_call("Write", {"file_path": "src/lib/api.ts"})
        state = t.get_state()
        print(f"Files modified: {state['files_modified']}, fresh_review={state['flags']['fresh_review_recommended']}")
        assert state["flags"]["fresh_review_recommended"] is True
    print("[OK] TEST 3: Threshold de archivos no-triviales detectado")


def test_4_agent_spawn_resets():
    print("\n" + "="*70)
    print("TEST 4: Agent spawn resetea todos los contadores y flags")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # Acumular flags
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "src/f.ts"})
        t.record_tool_call("Edit", {"file_path": "src/a.ts"})
        t.record_tool_call("Edit", {"file_path": "src/b.ts"})

        state = t.get_state()
        assert state["flags"]["escalation_needed"] is True
        assert state["flags"]["fresh_review_recommended"] is True

        # Spawn Agent → reset
        t.record_tool_call("Agent")
        state = t.get_state()
        print(f"After Agent spawn: consecutive_reads={state['consecutive_reads']}, total={state['total_tool_calls_since_spawn']}, files={state['files_modified']}")
        print(f"  flags: {state['flags']}")
        assert state["consecutive_reads"] == 0
        assert state["total_tool_calls_since_spawn"] == 0
        assert state["files_modified"] == []
        assert state["flags"]["escalation_needed"] is False
        assert state["flags"]["pause_recommended"] is False
        assert state["flags"]["fresh_review_recommended"] is False
    print("[OK] TEST 4: Agent spawn resetea correctamente")


def test_5_state_persistence():
    print("\n" + "="*70)
    print("TEST 5: State persiste entre instancias")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Tracker 1: acumula
        t1 = DelegationTracker(root)
        for _ in range(3):
            t1.record_tool_call("Read", {"file_path": "src/f.ts"})

        # Tracker 2: lee mismo state desde disco
        t2 = DelegationTracker(root)
        state = t2.get_state()
        print(f"Tracker 2 lee: consecutive_reads={state['consecutive_reads']}")
        assert state["consecutive_reads"] == 3

        # Tracker 2 continua incrementando
        for _ in range(2):
            t2.record_tool_call("Read", {"file_path": "src/g.ts"})
        state = t2.get_state()
        assert state["consecutive_reads"] == 5
        assert state["flags"]["escalation_needed"] is True
    print("[OK] TEST 5: State persiste en .pipeline/delegation-state.json")


def test_6_alternating_no_consecutive_false_positive():
    print("\n" + "="*70)
    print("TEST 6: Reads alternados con otros tools NO disparan escalation")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # 4 Reads alternados con Bash — consecutive_reads max sera 1
        for i in range(4):
            t.record_tool_call("Read", {"file_path": f"src/f{i}.ts"})
            t.record_tool_call("Bash")
        state = t.get_state()
        print(f"consecutive_reads={state['consecutive_reads']}, escalation={state['flags']['escalation_needed']}")
        assert state["consecutive_reads"] == 0  # Bash fue el ultimo
        assert state["flags"]["escalation_needed"] is False
    print("[OK] TEST 6: Reads NO consecutivas no disparan falso positivo")


def test_7_trivial_paths_excluded():
    print("\n" + "="*70)
    print("TEST 7: Archivos en paths triviales NO cuentan para fresh_review")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # Editar 3 archivos triviales
        t.record_tool_call("Edit", {"file_path": ".pipeline/tareas.md"})
        t.record_tool_call("Edit", {"file_path": "node_modules/foo.js"})
        t.record_tool_call("Edit", {"file_path": "README.md"})
        state = t.get_state()
        print(f"Files modified: {state['files_modified']}, fresh_review={state['flags']['fresh_review_recommended']}")
        assert state["files_modified"] == []
        assert state["flags"]["fresh_review_recommended"] is False
    print("[OK] TEST 7: Paths triviales correctamente excluidos")


def test_8_cli_record_command():
    print("\n" + "="*70)
    print("TEST 8: CLI 'record' funciona end-to-end")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tool_path = Path(__file__).parent.parent / "tools" / "delegation_tracker.py"

        # Ejecutar via CLI
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, str(tool_path), "record", "--tool=Read", "--file=src/foo.ts"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        print(f"Exit code: {result.returncode}")
        print(f"Stdout (first 200 chars): {result.stdout[:200]}")
        assert result.returncode == 0
        state = json.loads(result.stdout)
        assert state["consecutive_reads"] == 1
        assert state["last_tool"] == "Read"

        # Verificar persistencia en .pipeline/delegation-state.json
        state_file = root / ".pipeline" / "delegation-state.json"
        assert state_file.exists(), "State file no creado"
    print("[OK] TEST 8: CLI 'record' actualiza state correctamente")


def test_9_corrupted_state_recovers_fail_open():
    print("\n" + "="*70)
    print("TEST 9: State corrupto se recupera con defaults (fail-open)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        pipeline = root / ".pipeline"
        pipeline.mkdir()
        # Escribir state corrupto
        (pipeline / "delegation-state.json").write_text("{this is not valid JSON")

        t = DelegationTracker(root)
        state = t.get_state()
        print(f"State after corrupted load: consecutive_reads={state['consecutive_reads']}")
        assert state["consecutive_reads"] == 0
        assert state["flags"]["escalation_needed"] is False

        # Despues de record, state queda valido
        t.record_tool_call("Read", {"file_path": "src/foo.ts"})
        state2 = t.get_state()
        assert state2["consecutive_reads"] == 1
    print("[OK] TEST 9: State corrupto manejado con fail-open")


def test_10_active_warnings_output():
    print("\n" + "="*70)
    print("TEST 10: active_warnings retorna lista legible cuando hay flags")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        # Sin warnings al inicio
        assert t.active_warnings() == []

        # Disparar escalation
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "src/f.ts"})
        warnings = t.active_warnings()
        print(f"Warnings activos: {warnings}")
        assert len(warnings) >= 1
        assert any("escalation_needed" in w for w in warnings)
    print("[OK] TEST 10: active_warnings produce output legible")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1D.1: Delegation Stop Rules Enforcement")
    print("="*70)

    tests = [
        test_1_consecutive_reads_threshold,
        test_2_tool_calls_threshold,
        test_3_non_trivial_files_threshold,
        test_4_agent_spawn_resets,
        test_5_state_persistence,
        test_6_alternating_no_consecutive_false_positive,
        test_7_trivial_paths_excluded,
        test_8_cli_record_command,
        test_9_corrupted_state_recovers_fail_open,
        test_10_active_warnings_output,
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
        print("[OK] Threshold 5+ reads consecutivas -> escalation_needed")
        print("[OK] Threshold 20+ tool calls sin spawn -> pause_recommended")
        print("[OK] Threshold 2+ files no-triviales -> fresh_review_recommended")
        print("[OK] Agent/Task spawn resetea contadores y flags")
        print("[OK] State persiste en .pipeline/delegation-state.json")
        print("[OK] Reads alternadas NO disparan falso positivo")
        print("[OK] Paths triviales (.pipeline/, node_modules/, *.md) excluidos")
        print("[OK] CLI 'record' funciona para hook PostToolUse")
        print("[OK] State corrupto se recupera con fail-open (no rompe)")
        print("[OK] active_warnings produce output legible")
        print("\nLO QUE 1D.1 NO HACE:")
        print("- NO bloquea tool calls (es advisory)")
        print("- NO conecta automaticamente con el orquestador agente (capability disponible)")
        print("- Hook PostToolUse listo pero requiere registrar en .claude/settings.json")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
