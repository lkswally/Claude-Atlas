#!/usr/bin/env python3
"""
Validacion real de Bloque 1I.1: Anti-Loop INTER-Sesion Persistente

11 tests:
- 10 unit (record session, cross-session detection, edge cases)
- 1 realistic con loop persistente cross-session
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from delegation_tracker import DelegationTracker


def make_tracker(tmpdir: str) -> DelegationTracker:
    root = Path(tmpdir)
    return DelegationTracker(root)


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  TESTS
# ============================================================

def test_1_record_session_summary_writes_log():
    print("\n=== TEST 1: record_session_summary escribe entry valida en jsonl ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        # Disparar estado
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "src/foo.ts"})

        result = t.record_session_summary(session_id="sess-001", task_id="atlas/tarea-1")
        assert result["ok"] is True
        # Leer jsonl manualmente
        history = t._read_history()
        assert len(history) == 1
        assert history[0]["session_id"] == "sess-001"
        assert history[0]["task_id"] == "atlas/tarea-1"
        assert history[0]["flags"]["escalation_needed"] is True
        print("[OK] Entry escrita con metadata completa")


def test_2_record_session_appends():
    print("\n=== TEST 2: Multiples records hacen append (no sobrescriben) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record_session_summary("sess-a", "task-x")
        t.record_tool_call("Read", {"file_path": "x"})
        t.record_session_summary("sess-b", "task-x")
        t.record_session_summary("sess-c", "task-y")

        history = t._read_history()
        assert len(history) == 3
        ids = [e["session_id"] for e in history]
        assert ids == ["sess-a", "sess-b", "sess-c"]
        print("[OK] Append-only preserva orden")


def test_3_cross_session_no_history_ok():
    print("\n=== TEST 3: Sin history para task -> verdict=ok ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        r = t.cross_session_flags("atlas/tarea-nueva")
        assert r["verdict"] == "ok"
        assert r["sessions_analyzed"] == 0
        assert "primera vez" in r["note"].lower()
        print("[OK] Task nueva -> ok sin flags sticky")


def test_4_cross_session_no_loop_ok():
    print("\n=== TEST 4: History sin flags activas -> ok ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        # 3 sesiones sin flags (state limpio)
        for sid in ["s1", "s2", "s3"]:
            t.reset()
            t.record_session_summary(sid, "task-1")

        r = t.cross_session_flags("task-1")
        print(f"verdict={r['verdict']}, loop_count={r['loop_count']}")
        assert r["verdict"] == "ok"
        assert r["sessions_analyzed"] == 3
        assert not any(r["flags_sticky"].values())
        print("[OK] Sin flags -> ok")


def test_5_cross_session_sticky_escalation():
    print("\n=== TEST 5: escalation_needed en 2/3 sesiones -> sticky LOOP_DETECTED ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # Sesion 1: dispara escalation (5 reads)
        t.reset()
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "x"})
        t.record_session_summary("s1", "task-loop")

        # Sesion 2: dispara escalation nuevamente
        t.reset()
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "x"})
        t.record_session_summary("s2", "task-loop")

        # Sesion 3: limpia
        t.reset()
        t.record_session_summary("s3", "task-loop")

        r = t.cross_session_flags("task-loop", recent_sessions=3)
        print(f"verdict={r['verdict']}, sticky={r['flags_sticky']}, count={r['loop_count']}")
        assert r["verdict"] == "loop_detected"
        assert r["flags_sticky"]["escalation_needed_sticky"] is True
        assert r["loop_count"]["escalation_needed"] == 2
        assert "loop cross-session" in r["note"].lower()
        print("[OK] Sticky escalation detectada en 2/3 sesiones")


def test_6_cross_session_only_one_session_not_sticky():
    print("\n=== TEST 6: Flag en SOLO 1 sesion -> NO sticky ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        # 1 sesion con escalation, 2 limpias
        t.reset()
        for _ in range(5):
            t.record_tool_call("Read", {"file_path": "x"})
        t.record_session_summary("s1", "task-once")

        t.reset()
        t.record_session_summary("s2", "task-once")
        t.reset()
        t.record_session_summary("s3", "task-once")

        r = t.cross_session_flags("task-once", recent_sessions=3)
        print(f"verdict={r['verdict']}, sticky={r['flags_sticky']}, count={r['loop_count']}")
        assert r["verdict"] == "ok"
        assert not r["flags_sticky"]["escalation_needed_sticky"]
        assert r["loop_count"]["escalation_needed"] == 1
        print("[OK] 1/3 NO es sticky (no genera false positive)")


def test_7_cross_session_filter_by_task_id():
    print("\n=== TEST 7: cross_session_flags filtra correctamente por task_id ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        # Sesiones para task-A con loop
        for sid in ["sA1", "sA2"]:
            t.reset()
            for _ in range(5):
                t.record_tool_call("Read", {"file_path": "a"})
            t.record_session_summary(sid, "task-A")
        # Sesiones para task-B sin loop
        for sid in ["sB1", "sB2"]:
            t.reset()
            t.record_session_summary(sid, "task-B")

        rA = t.cross_session_flags("task-A")
        rB = t.cross_session_flags("task-B")
        print(f"task-A: {rA['verdict']}, task-B: {rB['verdict']}")
        assert rA["verdict"] == "loop_detected"
        assert rB["verdict"] == "ok"
        # Verificar que no se mezclan
        assert all(e["task_id"] == "task-A" for e in rA["history_entries"])
        assert all(e["task_id"] == "task-B" for e in rB["history_entries"])
        print("[OK] Filtrado por task_id correcto")


def test_8_history_stats():
    print("\n=== TEST 8: history_stats reporta metricas ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record_session_summary("s1", "task-1")
        t.record_session_summary("s2", "task-1")
        t.record_session_summary("s3", "task-2")

        stats = t.history_stats()
        print(f"stats: {stats}")
        assert stats["total_entries"] == 3
        assert stats["unique_task_ids"] == 2
        assert stats["unique_sessions"] == 3
        assert stats["exists"] is True
        print("[OK] history_stats correcto")


def test_9_corrupted_history_fail_open():
    print("\n=== TEST 9: history corrupto se ignora (fail-open) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / ".pipeline").mkdir()
        # Escribir history con lineas malformadas
        history_path = root / ".pipeline" / "delegation-history.jsonl"
        history_path.write_text(
            '{"session_id": "ok", "task_id": "t", "flags": {}}\n'
            'not valid json {{{\n'
            '{"session_id": "ok2", "task_id": "t", "flags": {"escalation_needed": true}}\n'
        )

        t = make_tracker(tmpdir)
        entries = t._read_history()
        # Lineas malformadas se saltean
        assert len(entries) == 2
        assert entries[0]["session_id"] == "ok"
        assert entries[1]["session_id"] == "ok2"

        # cross_session sigue funcionando
        r = t.cross_session_flags("t")
        assert r["sessions_analyzed"] == 2
        print("[OK] Lineas malformadas salteadas, no rompe")


def test_10_dispatcher_helpers():
    print("\n=== TEST 10: dispatcher.record_session_summary + check_cross_session_loops ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Simular 2 sesiones con loop en task-X
        from delegation_tracker import DelegationTracker
        t = DelegationTracker(d.project_root)
        for sid in ["s1", "s2"]:
            t.reset()
            for _ in range(5):
                t.record_tool_call("Read", {"file_path": "x"})
            d.record_session_summary(session_id=sid, task_id="task-X")

        # Consultar via dispatcher
        result = d.check_cross_session_loops("task-X", recent_sessions=3)
        print(f"verdict={result['verdict']}")
        assert result["verdict"] == "loop_detected"
        assert result["flags_sticky"]["escalation_needed_sticky"] is True
    print("[OK] Helpers del dispatcher end-to-end")


def test_11_realistic_3_session_loop():
    print("\n=== TEST 11 [INTEGRATION]: Loop persistente cross 3 sesiones consecutivas ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)

        # 3 sesiones, todas terminan con loop activo en task-stuck
        for sid in ["session-2026-05-19", "session-2026-05-20", "session-2026-05-21"]:
            t.reset()
            # Read loop
            for _ in range(6):
                t.record_tool_call("Read", {"file_path": "src/complex.ts"})
            # Multiple file modifications
            t.record_tool_call("Edit", {"file_path": "src/a.ts"})
            t.record_tool_call("Edit", {"file_path": "src/b.ts"})
            t.record_session_summary(sid, "atlas/tarea-stuck")

        r = t.cross_session_flags("atlas/tarea-stuck", recent_sessions=3)
        print(f"verdict={r['verdict']}")
        print(f"  sticky flags: {r['flags_sticky']}")
        print(f"  loop counts: {r['loop_count']}")
        print(f"  note: {r['note'][:120]}")
        assert r["verdict"] == "loop_detected"
        assert r["flags_sticky"]["escalation_needed_sticky"] is True
        assert r["flags_sticky"]["fresh_review_recommended_sticky"] is True
        assert r["loop_count"]["escalation_needed"] == 3
        assert r["loop_count"]["fresh_review_recommended"] == 3
        print("[OK] Loop persistente 3/3 sesiones detectado correctamente")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1I.1: Anti-Loop INTER-Sesion")
    print("="*70)

    tests = [
        test_1_record_session_summary_writes_log,
        test_2_record_session_appends,
        test_3_cross_session_no_history_ok,
        test_4_cross_session_no_loop_ok,
        test_5_cross_session_sticky_escalation,
        test_6_cross_session_only_one_session_not_sticky,
        test_7_cross_session_filter_by_task_id,
        test_8_history_stats,
        test_9_corrupted_history_fail_open,
        test_10_dispatcher_helpers,
        test_11_realistic_3_session_loop,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\nRESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    if failed == 0:
        print("\nLO QUE 1I.1 NO HACE:")
        print("- NO bloquea automaticamente: produce verdict 'loop_detected' que")
        print("  el agente/orquestador debe consumir para decidir escalar")
        print("- NO purga history vieja — crece append-only (mitigable con prune futuro)")
        print("- Honestidad del task_id supuesta — caller debe usar IDs consistentes")
        print("- Dispatcher debe leer su md y consultar (capability disponible)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
