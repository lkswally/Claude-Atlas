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


# =============================================================================
# Stability Repair 06 -- invocation-enforcement integration tests.
#
# P1 Closure Audit V1 (docs/P1-CLOSURE-AUDIT-V1.md) demonstrated that
# nothing forced record_qa_attempt() to be called at all: 10 consecutive
# qa_strict FAIL envelopes for the same task_id passed validate_return_
# envelope() with zero interaction with the retry-state file. Fixed by
# giving validate_return_envelope() an opt-in task_id parameter that,
# for mode="qa_strict" only, automatically performs the SAME accounting
# record_qa_attempt() always did -- as a side effect of the ONE call the
# orchestrator can no longer skip without also skipping envelope
# validation entirely.
#
# These tests exercise that integrated path (ATLASDispatcher.
# validate_return_envelope, not QARetryState directly), against the REAL
# project_root (ATLASDispatcher needs real config/phase_playbook.json
# etc. to construct) but with clearly-marked, disposable task_ids that
# are explicitly reset via reset_qa_retry_state() in a try/finally, so
# no residue is left in the real .pipeline/qa-retry-state.json.
# =============================================================================

sys.path.insert(0, str(PROJECT_ROOT))
from tools.atlas_dispatcher import ATLASDispatcher  # noqa: E402


def _qa_envelope(status: str, blockers=None):
    env = {
        "STATUS": status, "TAREA": "repair06 integration test",
        "ENGRAM": "repair06/integration-test",
    }
    if status == "PASS":
        env["ARCHIVOS"] = ["src/x.ts"]
        env["BLOQUEADORES"] = []
    else:
        env["BLOQUEADORES"] = blockers if blockers is not None else ["still broken"]
    return env


def test_14_integrated_fail_auto_counts():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-fail-autocounts"
    try:
        env = _qa_envelope("FAIL")
        valid, errors = d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        r = env.get("_dispatcher_qa_retry")
        if valid and r and r["attempt_count"] == 1 and not r["retry_limit_reached"]:
            ok("14 integrated: functional FAIL auto-counts via validate_return_envelope", f"attempt_count=1 with zero manual record_qa_attempt call")
        else:
            fail("14 integrated: functional FAIL auto-counts via validate_return_envelope", f"valid={valid} r={r}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_15_integrated_second_fail_auto_counts():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-second-fail"
    try:
        env1 = _qa_envelope("FAIL")
        d.validate_return_envelope(env1, mode="qa_strict", task_id=task_id)
        env2 = _qa_envelope("FAIL")
        d.validate_return_envelope(env2, mode="qa_strict", task_id=task_id)
        r = env2.get("_dispatcher_qa_retry")
        if r and r["attempt_count"] == 2 and not r["retry_limit_reached"]:
            ok("15 integrated: second FAIL auto-counts", f"attempt_count=2")
        else:
            fail("15 integrated: second FAIL auto-counts", str(r))
    finally:
        d.reset_qa_retry_state(task_id)


def test_16_integrated_third_reaches_ceiling():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-third-ceiling"
    try:
        env = None
        for _ in range(3):
            env = _qa_envelope("FAIL")
            d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        r = env.get("_dispatcher_qa_retry")
        if r and r["attempt_count"] == 3 and r["retry_limit_reached"]:
            ok("16 integrated: third FAIL reaches ceiling", f"attempt_count=3, retry_limit_reached=True")
        else:
            fail("16 integrated: third FAIL reaches ceiling", str(r))
    finally:
        d.reset_qa_retry_state(task_id)


def test_17_integrated_fourth_normal_retry_blocked():
    """The bypass regression: this exact call sequence, against the
    pre-fix validate_return_envelope (no task_id parameter at all),
    would raise TypeError -- a loud, immediate signal that accounting
    integration was reverted. Against the pre-fix BEHAVIOR (task_id
    accepted but ignored), it would silently show attempt_count staying
    unset / bypass reproducing. Either way this test fails pre-fix."""
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-fourth-blocked"
    try:
        env = None
        for i in range(4):
            env = _qa_envelope("FAIL")
            valid, errors = d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        r = env.get("_dispatcher_qa_retry")
        # Normal runtime path exposes retry_limit_reached=True well before
        # a 4th attempt would be allowed to re-delegate -- the orchestrator
        # contract reads this flag after attempt 3 and escalates instead
        # of calling evidence-collector again.
        if r and r["retry_limit_reached"] and r["attempt_count"] >= 3:
            ok("17 integrated: 4th normal retry blocked (ceiling already flagged)", f"r={r}")
        else:
            fail("17 integrated: 4th normal retry blocked (ceiling already flagged)", str(r))
    finally:
        d.reset_qa_retry_state(task_id)


def test_18_integrated_pass_resets():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-pass-resets"
    try:
        for _ in range(2):
            env = _qa_envelope("FAIL")
            d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        env_pass = _qa_envelope("PASS")
        d.validate_return_envelope(env_pass, mode="qa_strict", task_id=task_id)
        r = env_pass.get("_dispatcher_qa_retry")
        after = d.check_qa_retry_limit(task_id)
        if r and r["cleared"] and after["attempt_count"] == 0:
            ok("18 integrated: PASS resets the counter", f"cleared=True, attempt_count back to 0")
        else:
            fail("18 integrated: PASS resets the counter", f"r={r} after={after}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_19_integrated_new_task_starts_fresh():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_a = "_test_repair06/integrated-new-task-A"
    task_b = "_test_repair06/integrated-new-task-B"
    try:
        for _ in range(3):
            env = _qa_envelope("FAIL")
            d.validate_return_envelope(env, mode="qa_strict", task_id=task_a)
        env_b = _qa_envelope("FAIL")
        d.validate_return_envelope(env_b, mode="qa_strict", task_id=task_b)
        r_b = env_b.get("_dispatcher_qa_retry")
        if r_b and r_b["attempt_count"] == 1 and not r_b["retry_limit_reached"]:
            ok("19 integrated: new task_id starts fresh", "task B unaffected by task A's 3 fails")
        else:
            fail("19 integrated: new task_id starts fresh", str(r_b))
    finally:
        d.reset_qa_retry_state(task_a)
        d.reset_qa_retry_state(task_b)


def test_20_integrated_infra_failure_does_not_increment():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-infra-noincrement"
    try:
        # Malformed envelope (missing required ENGRAM field) -> invalid ->
        # auto-classified infra_error internally, must NOT increment.
        bad_env = {"STATUS": "FAIL", "TAREA": "x", "BLOQUEADORES": ["b"]}
        valid, errors = d.validate_return_envelope(bad_env, mode="qa_strict", task_id=task_id)
        r = bad_env.get("_dispatcher_qa_retry")
        if (not valid) and r and r["attempt_count"] == 0:
            ok("20 integrated: invalid envelope (infra_error) does not increment", f"valid=False, attempt_count stays 0, errors={errors}")
        else:
            fail("20 integrated: invalid envelope (infra_error) does not increment", f"valid={valid} r={r}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_21_integrated_invalid_envelope_behaves_safely():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-invalid-safe"
    try:
        # status not in {PASS, FAIL} at all
        bad_env = {"STATUS": "WEIRD", "TAREA": "x", "ENGRAM": "y"}
        valid, errors = d.validate_return_envelope(bad_env, mode="qa_strict", task_id=task_id)
        r = bad_env.get("_dispatcher_qa_retry")
        if (not valid) and len(errors) > 0 and r and r["attempt_count"] == 0:
            ok("21 integrated: malformed status handled safely, no crash, no increment", f"errors={errors}")
        else:
            fail("21 integrated: malformed status handled safely, no crash, no increment", f"valid={valid} r={r}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_22_integrated_persists_across_dispatcher_instance():
    task_id = "_test_repair06/integrated-persist-instance"
    d1 = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    try:
        for _ in range(2):
            env = _qa_envelope("FAIL")
            d1.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        d2 = ATLASDispatcher(project_root=str(PROJECT_ROOT))  # fresh instance
        r = d2.check_qa_retry_limit(task_id)
        if r["attempt_count"] == 2:
            ok("22 integrated: persists across fresh ATLASDispatcher instance", f"attempt_count=2 survives new dispatcher object")
        else:
            fail("22 integrated: persists across fresh ATLASDispatcher instance", str(r))
    finally:
        d1.reset_qa_retry_state(task_id)


def test_23_integrated_persists_across_process():
    task_id = "_test_repair06/integrated-persist-process"
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    try:
        for _ in range(2):
            env = _qa_envelope("FAIL")
            d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        proc = subprocess.run(
            [sys.executable, "-c", f"""
import sys
sys.path.insert(0, r"{PROJECT_ROOT}")
from tools.atlas_dispatcher import ATLASDispatcher
d = ATLASDispatcher(project_root=r"{PROJECT_ROOT}")
r = d.check_qa_retry_limit("{task_id}")
print(r.get("attempt_count"), r.get("retry_limit_reached"))
"""],
            capture_output=True, text=True, timeout=20,
        )
        out = proc.stdout.strip()
        if out == "2 False":
            ok("23 integrated: persists across fresh OS process", f"stdout={out!r}")
        else:
            fail("23 integrated: persists across fresh OS process", f"stdout={out!r} stderr={proc.stderr[:200]!r}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_24_no_double_counting_single_call_single_increment():
    """Critical: one validate_return_envelope(qa_strict, task_id=...) call
    must increment the counter by exactly 1, never 2 -- proves the
    integration doesn't internally invoke record_qa_attempt more than
    once per validation call."""
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-no-double-count"
    try:
        env = _qa_envelope("FAIL")
        d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        r = d.check_qa_retry_limit(task_id)
        if r["attempt_count"] == 1:
            ok("24 no double-counting: single call increments exactly once", f"attempt_count=1 after exactly 1 validate call")
        else:
            fail("24 no double-counting: single call increments exactly once", f"expected 1, got {r['attempt_count']}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_25_phase_gate_retries_unaffected_by_integration():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-phase-gate-check"
    try:
        before = dict(getattr(d, "phase_gate_retries", {}))
        for _ in range(3):
            env = _qa_envelope("FAIL")
            d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        after = dict(getattr(d, "phase_gate_retries", {}))
        if before == after:
            ok("25 phase_gate_retries unaffected by the new integration", "in-memory dict untouched by qa_strict+task_id calls")
        else:
            fail("25 phase_gate_retries unaffected by the new integration", f"before={before} after={after}")
    finally:
        d.reset_qa_retry_state(task_id)


def test_26_invocation_logging_correct_through_integration():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-invocation-log"
    try:
        env = _qa_envelope("FAIL")
        d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        audit = d.audit_invocations(["record_qa_attempt", "validate_return_envelope"], since_seconds=30)
        if audit.get("verdict") == "complete" and not audit.get("missing"):
            ok("26 invocation logging correct through the integrated path", f"both helpers logged: {audit.get('invoked')}")
        else:
            fail("26 invocation logging correct through the integrated path", str(audit))
    finally:
        d.reset_qa_retry_state(task_id)


def test_27_integrated_malformed_state_fails_closed():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_id = "_test_repair06/integrated-malformed-failclosed"
    state_path = PROJECT_ROOT / ".pipeline" / "qa-retry-state.json"
    backup = state_path.read_text(encoding="utf-8") if state_path.exists() else None
    try:
        env0 = _qa_envelope("FAIL")
        d.validate_return_envelope(env0, mode="qa_strict", task_id=task_id)  # ensure file exists
        state_path.write_text("{ not valid json at all !!", encoding="utf-8")
        env = _qa_envelope("FAIL")
        valid, errors = d.validate_return_envelope(env, mode="qa_strict", task_id=task_id)
        r = env.get("_dispatcher_qa_retry")
        # Envelope shape itself is still valid (FAIL well-formed); the
        # retry-accounting side effect fails CLOSED on the broken state.
        if valid and r and r.get("retry_limit_reached") is True and r.get("state_error"):
            ok("27 integrated: malformed retry-state file fails CLOSED", f"r={r}")
        else:
            fail("27 integrated: malformed retry-state file fails CLOSED", f"valid={valid} r={r}")
    finally:
        if backup is not None:
            state_path.write_text(backup, encoding="utf-8")
        elif state_path.exists():
            state_path.unlink()
        d.reset_qa_retry_state(task_id)


def test_28_integrated_casing_compatibility_preserved():
    d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
    task_a = "_test_repair06/integrated-casing-upper"
    task_b = "_test_repair06/integrated-casing-lower"
    try:
        env_upper = {"STATUS": "FAIL", "TAREA": "x", "ENGRAM": "y", "BLOQUEADORES": ["b"]}
        env_lower = {"status": "FAIL", "tarea": "x", "engram": "y", "bloqueadores": ["b"]}
        v1, e1 = d.validate_return_envelope(env_upper, mode="qa_strict", task_id=task_a)
        v2, e2 = d.validate_return_envelope(env_lower, mode="qa_strict", task_id=task_b)
        r1 = env_upper.get("_dispatcher_qa_retry")
        r2 = env_lower.get("_dispatcher_qa_retry")
        if (v1 == v2 and r1 and r2 and r1["attempt_count"] == r2["attempt_count"] == 1
                and r1["retry_limit_reached"] == r2["retry_limit_reached"] == False):
            ok("28 integrated: casing compatibility preserved (upper vs lower, same accounting)", f"both attempt_count=1")
        else:
            fail("28 integrated: casing compatibility preserved (upper vs lower, same accounting)", f"v1={v1} r1={r1} v2={v2} r2={r2}")
    finally:
        d.reset_qa_retry_state(task_a)
        d.reset_qa_retry_state(task_b)


def main():
    print("=" * 60)
    print("Bloque QA Retry Ceiling -- Architecture Repair 03 + Stability Repair 06")
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
    test_14_integrated_fail_auto_counts()
    test_15_integrated_second_fail_auto_counts()
    test_16_integrated_third_reaches_ceiling()
    test_17_integrated_fourth_normal_retry_blocked()
    test_18_integrated_pass_resets()
    test_19_integrated_new_task_starts_fresh()
    test_20_integrated_infra_failure_does_not_increment()
    test_21_integrated_invalid_envelope_behaves_safely()
    test_22_integrated_persists_across_dispatcher_instance()
    test_23_integrated_persists_across_process()
    test_24_no_double_counting_single_call_single_increment()
    test_25_phase_gate_retries_unaffected_by_integration()
    test_26_invocation_logging_correct_through_integration()
    test_27_integrated_malformed_state_fails_closed()
    test_28_integrated_casing_compatibility_preserved()

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
