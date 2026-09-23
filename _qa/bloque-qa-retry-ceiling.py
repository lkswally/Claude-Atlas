#!/usr/bin/env python3
"""
Bloque QA Retry Ceiling — Architecture Repair 03
=============================================================================

Gap demostrado: Architecture Reality Audit V1 (P1-3) encontro que el limite
de "max 3 reintentos" del loop dev<->QA (Fase 3, evidence-collector) no
tenia NINGUN contador ni chequeo a nivel de codigo -- cero referencias a
`qa_intento_actual` en todo tools/*.py. El unico mecanismo relacionado
(should_skip_qa/cache_qa_result, Bloque 1F.1) es un cache de resultados
PASS, no un contador de intentos, y no bloquea ni marca nada al 4to intento
fallido consecutivo -- reproducido con la implementacion real, no solo
grep: 4 llamadas identicas a should_skip_qa/cache_qa_result para el mismo
task_id se comportan identico en el intento 4 que en el intento 1.

CANONICAL_RETRY_SEMANTICS (resuelto por evidencia, ver
.claude/agents/refs/orchestrator-pipeline-phase-3.md lineas 73/102/113/
129-134 y .claude/agents/evidence-collector.md self-guard): MAX_ATTEMPTS=3
TOTALES por task_id (no 3 reintentos tras un intento inicial = 4 totales).
El contador incrementa SOLO en fallos funcionales de QA ("fail"), nunca en
fallos de infraestructura/Engram ("infra_error"). Un PASS limpia el
contador. Persistencia por-task_id, sobrevive reinicio de proceso/sesion
(NO es session-local).

Este suite usa las funciones reales del dispatcher
(record_qa_attempt/check_qa_retry_limit/reset_qa_retry_state), respaldadas
por tools/qa_retry_state.py, contra un project_root descartable -- nunca
el .pipeline/qa-retry-state.json real.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from qa_retry_state import QARetryState  # noqa: E402

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


def _fresh_state(tmpdir: str) -> QARetryState:
    return QARetryState(tmpdir)


def test_01_02_03_first_second_third_attempt_allowed():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        r1 = s.record_qa_attempt("t1", "fail", reason="issue 1")
        r2 = s.record_qa_attempt("t1", "fail", reason="issue 2")
        r3 = s.record_qa_attempt("t1", "fail", reason="issue 3")
        if r1["attempt_count"] == 1 and not r1["retry_limit_reached"]:
            ok("01 first attempt allowed", f"attempt_count=1, not at limit")
        else:
            fail("01 first attempt allowed", str(r1))
        if r2["attempt_count"] == 2 and not r2["retry_limit_reached"]:
            ok("02 second attempt allowed", f"attempt_count=2, not at limit")
        else:
            fail("02 second attempt allowed", str(r2))
        # Canonical semantics: 3 attempts is the ceiling itself (not the
        # 4th) -- the 3rd attempt is allowed/counted but flips the flag so
        # the caller knows not to permit a 4th.
        if r3["attempt_count"] == 3 and r3["retry_limit_reached"]:
            ok("03 third attempt allowed, flags ceiling reached", f"attempt_count=3, retry_limit_reached=True")
        else:
            fail("03 third attempt allowed, flags ceiling reached", str(r3))


def test_04_next_attempt_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        for _ in range(3):
            s.record_qa_attempt("t1", "fail")
        # A caller consulting BEFORE attempting a 4th sees the ceiling.
        pre_check = s.check_qa_retry_limit("t1")
        r4 = s.record_qa_attempt("t1", "fail")  # still recorded for evidence, but flagged
        if pre_check["retry_limit_reached"] and r4["retry_limit_reached"] and r4["attempt_count"] == 4:
            ok("04 next attempt blocked/escalated", f"pre-check already True; 4th call still flags True (attempt_count={r4['attempt_count']})")
        else:
            fail("04 next attempt blocked/escalated", f"pre_check={pre_check} r4={r4}")


def test_05_counter_persisted_across_new_instance():
    with tempfile.TemporaryDirectory() as tmp:
        s1 = _fresh_state(tmp)
        s1.record_qa_attempt("t1", "fail")
        s1.record_qa_attempt("t1", "fail")
        s2 = _fresh_state(tmp)  # simulates a fresh dispatcher instance / process restart
        r = s2.check_qa_retry_limit("t1")
        if r["attempt_count"] == 2:
            ok("05 counter persisted across new instance", f"attempt_count=2 survives fresh QARetryState()")
        else:
            fail("05 counter persisted across new instance", str(r))


def test_06_successful_qa_resets_state():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        s.record_qa_attempt("t1", "fail")
        s.record_qa_attempt("t1", "fail")
        r = s.record_qa_attempt("t1", "pass")
        after = s.check_qa_retry_limit("t1")
        if r["cleared"] and after["attempt_count"] == 0:
            ok("06 successful QA resets state", "cleared=True, attempt_count back to 0")
        else:
            fail("06 successful QA resets state", f"pass_result={r} after={after}")


def test_07_new_task_gets_fresh_counter():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        s.record_qa_attempt("t1", "fail")
        s.record_qa_attempt("t1", "fail")
        s.record_qa_attempt("t1", "fail")
        fresh = s.check_qa_retry_limit("t2-different-task")
        if fresh["attempt_count"] == 0 and not fresh["retry_limit_reached"]:
            ok("07 new task gets fresh counter", "t2 unaffected by t1's 3 fails")
        else:
            fail("07 new task gets fresh counter", str(fresh))


def test_08_same_task_not_reset_by_process_restart():
    with tempfile.TemporaryDirectory() as tmp:
        s1 = _fresh_state(tmp)
        s1.record_qa_attempt("t1", "fail")
        s1.record_qa_attempt("t1", "fail")
        s1.record_qa_attempt("t1", "fail")
        s2 = _fresh_state(tmp)  # new process/instance
        r = s2.check_qa_retry_limit("t1")
        if r["attempt_count"] == 3 and r["retry_limit_reached"]:
            ok("08 same task NOT reset by process restart", "ceiling survives a fresh instance for the same task_id")
        else:
            fail("08 same task NOT reset by process restart", str(r))


def test_09_malformed_state_handled_safely():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        s.record_qa_attempt("t1", "fail")  # create the file first
        state_file = Path(tmp) / ".pipeline" / "qa-retry-state.json"
        state_file.write_text("{this is not valid json", encoding="utf-8")
        r = s.check_qa_retry_limit("t1")
        r2 = s.record_qa_attempt("t1", "fail")
        # FAIL CLOSED is the required behavior: a broken state file must
        # NOT silently permit unlimited retries.
        if r["retry_limit_reached"] and r.get("state_error") and r2["retry_limit_reached"]:
            ok("09 malformed state handled safely (fail-closed)", f"state_error surfaced, retry_limit_reached=True (not silently permissive)")
        else:
            fail("09 malformed state handled safely (fail-closed)", f"check={r} record={r2}")


def test_10_limit_event_contains_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        for i in range(3):
            r = s.record_qa_attempt("t1", "fail", reason=f"issue {i}", agent="frontend-developer")
        required = {"task_id", "attempt_count", "max_attempts", "retry_limit_reached", "last_failure_reason", "last_agent"}
        has_all = required.issubset(r.keys())
        has_identity = r["task_id"] == "t1" and r["last_failure_reason"] == "issue 2" and r["last_agent"] == "frontend-developer"
        if has_all and has_identity:
            ok("10 limit event contains evidence", f"task identity + last_failure_reason + last_agent all present")
        else:
            fail("10 limit event contains evidence", f"has_all={has_all} has_identity={has_identity} r={r}")


def test_11_no_interference_with_phase_gate_retries():
    """qa_retry_state.py is a fully separate module/file/class from
    ATLASDispatcher.phase_gate_retries (Fase-gate cajon waits). Confirm
    they don't share state or collide on the same task_id."""
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        s.record_qa_attempt("shared-name", "fail")
        s.record_qa_attempt("shared-name", "fail")
        s.record_qa_attempt("shared-name", "fail")
        state_path = Path(tmp) / ".pipeline" / "qa-retry-state.json"
        content = state_path.read_text(encoding="utf-8")
        # phase_gate_retries lives entirely in dispatcher instance memory
        # (self.phase_gate_retries dict), never touches this file at all.
        no_phase_gate_leakage = "phase_gate" not in content
        if no_phase_gate_leakage and state_path.exists():
            ok("11 no interference with phase-gate retries", "separate file (qa-retry-state.json), separate class, phase_gate_retries is in-memory only")
        else:
            fail("11 no interference with phase-gate retries", f"content={content[:200]}")


def test_12_human_override_explicit_not_automatic():
    with tempfile.TemporaryDirectory() as tmp:
        s = _fresh_state(tmp)
        s.record_qa_attempt("t1", "fail")
        s.record_qa_attempt("t1", "fail")
        s.record_qa_attempt("t1", "fail")
        at_limit = s.check_qa_retry_limit("t1")
        # Merely checking (many times) must never auto-reset.
        s.check_qa_retry_limit("t1")
        s.check_qa_retry_limit("t1")
        still_at_limit = s.check_qa_retry_limit("t1")
        reset_result = s.reset("t1")  # the ONLY way past the ceiling: explicit call
        after_reset = s.check_qa_retry_limit("t1")
        if (at_limit["retry_limit_reached"] and still_at_limit["retry_limit_reached"]
                and reset_result and not after_reset["retry_limit_reached"]):
            ok("12 human override is explicit, never automatic", "repeated checks don't reset; only an explicit reset() call does")
        else:
            fail("12 human override is explicit, never automatic",
                 f"at_limit={at_limit} still_at_limit={still_at_limit} reset_result={reset_result} after_reset={after_reset}")


def test_13_concurrent_increment_no_lost_updates():
    """Real OS subprocesses (not threads), same task_id, one increment
    each -- proves the cross-process lock prevents a read-modify-write
    race from losing increments."""
    worker = Path(__file__).parent / "_qa_retry_worker.py"
    with tempfile.TemporaryDirectory() as tmp:
        n_writers = 10
        procs = [
            subprocess.Popen([sys.executable, str(worker), str(PROJECT_ROOT / "tools"), tmp, "concurrent-task", "1"])
            for _ in range(n_writers)
        ]
        for p in procs:
            p.communicate(timeout=30)
        s = _fresh_state(tmp)
        r = s.check_qa_retry_limit("concurrent-task")
        if r["attempt_count"] == n_writers:
            ok("13 concurrent increments — no lost updates", f"{n_writers} processes, {n_writers} concurrent increments, exact count {r['attempt_count']}")
        else:
            fail("13 concurrent increments — no lost updates", f"expected={n_writers} actual={r['attempt_count']}")


def main():
    print("=" * 60)
    print("Bloque QA Retry Ceiling -- Architecture Repair 03")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_01_02_03_first_second_third_attempt_allowed()
    test_04_next_attempt_blocked()
    test_05_counter_persisted_across_new_instance()
    test_06_successful_qa_resets_state()
    test_07_new_task_gets_fresh_counter()
    test_08_same_task_not_reset_by_process_restart()
    test_09_malformed_state_handled_safely()
    test_10_limit_event_contains_evidence()
    test_11_no_interference_with_phase_gate_retries()
    test_12_human_override_explicit_not_automatic()
    test_13_concurrent_increment_no_lost_updates()

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
