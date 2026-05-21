#!/usr/bin/env python3
"""
Validacion real de Bloque 1G.2: Runtime Invocation Tracking + Enforcement

11 tests:
- 10 unit (tracker + dispatcher instrumentation + audit)
- 1 integration realistic
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from invocation_tracker import InvocationTracker, TRACKED_HELPERS


def make_tracker(tmpdir: str) -> InvocationTracker:
    return InvocationTracker(Path(tmpdir))


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

def test_1_record_creates_log_entry():
    print("\n=== TEST 1: record() escribe entry valida ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        result = t.record("validate_return_envelope", context={"mode": "dev_strict"}, outcome="ok")
        assert result["ok"] is True
        entries = t._read_log()
        assert len(entries) == 1
        assert entries[0]["helper"] == "validate_return_envelope"
        assert entries[0]["context"]["mode"] == "dev_strict"
        print("[OK]")


def test_2_append_only():
    print("\n=== TEST 2: Multiples records hacen append ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        for i in range(5):
            t.record(f"helper_{i}")
        entries = t._read_log()
        assert len(entries) == 5
        assert [e["helper"] for e in entries] == [f"helper_{i}" for i in range(5)]
        print("[OK]")


def test_3_get_recent_filters_by_time():
    print("\n=== TEST 3: get_recent filtra por ventana de tiempo ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.log_dir.mkdir(parents=True, exist_ok=True)
        # Inyectar entry vieja manualmente
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        with open(t.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"helper": "old_one", "timestamp": old_ts, "context": {}}) + "\n")
        # Record reciente
        t.record("recent_one")

        recent = t.get_recent(since_seconds=300)  # 5 min
        helpers = [e["helper"] for e in recent]
        assert "recent_one" in helpers
        assert "old_one" not in helpers
        print("[OK]")


def test_4_audit_all_required_invoked():
    print("\n=== TEST 4: Audit cuando todos los requeridos fueron invocados -> complete ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record("validate_return_envelope")
        t.record("get_cajon_full")
        t.record("should_skip_qa")
        audit = t.audit_invocations(
            required_helpers=["validate_return_envelope", "get_cajon_full"]
        )
        assert audit["verdict"] == "complete"
        assert audit["missing"] == []
        print("[OK]")


def test_5_audit_missing_helpers_incomplete():
    print("\n=== TEST 5: Audit con missing -> incomplete + lista exacta ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record("validate_return_envelope")
        # NO invocar get_cajon_full
        audit = t.audit_invocations(
            required_helpers=["validate_return_envelope", "get_cajon_full", "should_skip_qa"]
        )
        assert audit["verdict"] == "incomplete"
        assert "get_cajon_full" in audit["missing"]
        assert "should_skip_qa" in audit["missing"]
        assert "validate_return_envelope" not in audit["missing"]
        print("[OK]")


def test_6_audit_extra_invocations_tracked():
    print("\n=== TEST 6: Audit reporta extra (invocaciones no requeridas) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record("validate_return_envelope")
        t.record("cache_qa_result")  # no esta en required
        audit = t.audit_invocations(required_helpers=["validate_return_envelope"])
        assert "cache_qa_result" in audit["extra"]
        print("[OK]")


def test_7_audit_with_context_filter():
    print("\n=== TEST 7: Audit con context_filter solo cuenta matchs ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.record("validate_return_envelope", context={"mode": "dev_strict"})
        t.record("validate_return_envelope", context={"mode": "qa_strict"})
        # Filtrar solo dev_strict
        audit = t.audit_invocations(
            required_helpers=["validate_return_envelope"],
            context_filter={"mode": "dev_strict"},
        )
        assert audit["verdict"] == "complete"
        # Total invocations en ventana (con filtro): 1
        assert audit["total_invocations"] == 1
        print("[OK]")


def test_8_corrupted_log_fail_open():
    print("\n=== TEST 8: Log corrupto -> read fail-open (saltea malformadas) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        t = make_tracker(tmpdir)
        t.log_dir.mkdir(parents=True, exist_ok=True)
        t.log_path.write_text(
            '{"helper": "ok", "timestamp": "2026-05-21T00:00:00+00:00"}\n'
            'not valid json {\n'
            '{"helper": "ok2", "timestamp": "2026-05-21T00:00:00+00:00"}\n'
        )
        entries = t._read_log()
        assert len(entries) == 2
        assert [e["helper"] for e in entries] == ["ok", "ok2"]
        print("[OK]")


def test_9_dispatcher_helpers_auto_record():
    print("\n=== TEST 9: Dispatcher helpers se auto-registran ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Invocar varios helpers
        d.validate_return_envelope({"status": "completado", "tarea": "x", "engram": "y"}, mode="standard")
        d.inspect_network_requests([], page_origin=None)
        d.analyze_console_messages([])

        t = InvocationTracker(d.project_root)
        entries = t._read_log()
        helpers_invoked = {e["helper"] for e in entries}
        assert "validate_return_envelope" in helpers_invoked
        assert "inspect_network_requests" in helpers_invoked
        assert "analyze_console_messages" in helpers_invoked
        print(f"[OK] {len(helpers_invoked)} helpers auto-registrados")


def test_10_dispatcher_audit_invocations_helper():
    print("\n=== TEST 10: dispatcher.audit_invocations() helper end-to-end ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        d.validate_return_envelope({"status": "completado", "tarea": "x", "engram": "y"})
        d.inspect_network_requests([])

        audit = d.audit_invocations(
            required_helpers=["validate_return_envelope", "inspect_network_requests", "missing_helper"]
        )
        assert audit["verdict"] == "incomplete"
        assert "missing_helper" in audit["missing"]
        assert "validate_return_envelope" in audit["invoked"]
        assert "inspect_network_requests" in audit["invoked"]
        print("[OK]")


def test_11_realistic_fase_3_audit():
    print("\n=== TEST 11 [INTEGRATION]: Audit realistico de Fase 3 ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Simular flujo Fase 3 con TODOS los helpers obligatorios
        # 1. Dev-agent envelope validation
        d.validate_return_envelope(
            {"status": "completado", "tarea": "Header", "engram": "atlas/tareas", "archivos": []},
            mode="standard",  # standard porque no tenemos dev_strict completo
        )

        # 2. Cache check antes de QA
        d.should_skip_qa("atlas/tarea-1", [])

        # 3. Network inspection
        d.inspect_network_requests([
            {"url": "https://app.com", "status": 200},
        ], page_origin="https://app.com")

        # 4. Console log analysis
        d.analyze_console_messages([])

        # Audit: lista de helpers obligatorios en Fase 3
        required_fase_3 = [
            "validate_return_envelope",
            "should_skip_qa",
            "inspect_network_requests",
            "analyze_console_messages",
        ]
        audit = d.audit_invocations(required_helpers=required_fase_3)
        print(f"verdict={audit['verdict']}, invoked={len(audit['invoked'])}, missing={audit['missing']}")
        assert audit["verdict"] == "complete"
        assert audit["missing"] == []

        # Audit con helper requerido NO invocado
        audit2 = d.audit_invocations(
            required_helpers=required_fase_3 + ["check_visual_fidelity"]
        )
        assert audit2["verdict"] == "incomplete"
        assert "check_visual_fidelity" in audit2["missing"]
        print("[OK] Fase 3 audit funciona end-to-end")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1G.2: Runtime Invocation Tracking")
    print("="*70)

    tests = [
        test_1_record_creates_log_entry,
        test_2_append_only,
        test_3_get_recent_filters_by_time,
        test_4_audit_all_required_invoked,
        test_5_audit_missing_helpers_incomplete,
        test_6_audit_extra_invocations_tracked,
        test_7_audit_with_context_filter,
        test_8_corrupted_log_fail_open,
        test_9_dispatcher_helpers_auto_record,
        test_10_dispatcher_audit_invocations_helper,
        test_11_realistic_fase_3_audit,
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
        print("\nLO QUE 1G.2 NO HACE:")
        print("- NO bloquea automaticamente — produce verdict que orquestador consume")
        print("- NO trackea tool calls (Read/Edit/Write) — eso es delegation_tracker (1D.1)")
        print("- Requiere que el dispatcher se invoque desde Python")
        print("- Si el agente salta el dispatcher, no hay log")
        print("- Audit es opt-in: el orquestador debe consultar audit_invocations()")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
