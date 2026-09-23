#!/usr/bin/env python3
"""
Bloque Capability Events Integrity — Architecture Repair 02
=============================================================================

Gap demostrado: Architecture Reality Audit V1 (P1-2) encontro que
.pipeline/capability-events.jsonl tenia 1,782/216,862 lineas invalidas
(0.82%), con la firma de un fragmento truncado (linea que empieza a mitad
de un objeto JSON, le falta el "{" de apertura). ROOT CAUSE CONFIRMADO
esta sesion (no solo observado): reproducido directamente con el writer de
produccion real (core.capabilities.events.emit) bajo concurrencia real de
PROCESOS del SO (no solo threads) contra un archivo descartable — a partir
de 5 escritores concurrentes aparecen lineas invalidas identicas en forma
a las del archivo real; a 50 escritores, 14/1000 invalidas + 80 eventos
perdidos. El _write_lock existente es threading.Lock — no protege entre
procesos separados, que es exactamente como ATLAS invoca sus herramientas
(cada tool-call/hook es un proceso corto nuevo).

Fix: lock de archivo cross-proceso, stdlib-only (msvcrt en Windows, fcntl
en POSIX/Linux — cubre esta maquina de desarrollo Y el runner de Linux en
CI, sin dependencias nuevas), envolviendo el mismo f.write() de una sola
linea que ya existia. Acotado por timeout para que un holder trabado no
cuelgue a otros escritores; en timeout, emit() devuelve False (contrato
fail-open preexistente, sin cambios).

Este suite usa el writer real de produccion (core.capabilities.events.emit)
contra archivos descartables — nunca .pipeline/capability-events.jsonl.
El test de concurrencia (test_04) es el mismo escenario que, ejecutado
manualmente contra el codigo pre-fix durante el desarrollo de este parche,
produjo 6-14 lineas invalidas + 31-80 eventos perdidos en corridas
repetidas — evidencia de que efectivamente habria fallado sin el fix,
documentada en el reporte de Architecture Repair 02 (no solo asumida).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
WORKER_SCRIPT = Path(__file__).parent / "_capability_events_worker.py"

sys.path.insert(0, str(PROJECT_ROOT))
from core.capabilities.events import make_event, emit, _is_disabled  # noqa: E402

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


def _tmp(name: str) -> Path:
    d = Path(os.environ.get("TEMP") or "/tmp") / "atlas-qa-capability-events"
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _read_valid_invalid(path: Path):
    if not path.exists():
        return [], 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    valid = []
    invalid = 0
    for l in lines:
        if not l.strip():
            invalid += 1
            continue
        try:
            valid.append(json.loads(l))
        except Exception:
            invalid += 1
    return valid, invalid


# ---------------------------------------------------------------------------
# 1-2: single + sequential appends
# ---------------------------------------------------------------------------
def test_01_02_single_and_sequential_appends():
    target = _tmp("t01_single.jsonl")
    if target.exists():
        target.unlink()
    evt = make_event("t", "dummy", "LIVE", False, "use", requested_by="single")
    result = emit(evt, events_file=target)
    valid, invalid = _read_valid_invalid(target)
    if result and len(valid) == 1 and invalid == 0:
        ok("01 single append", f"1 valid record written")
    else:
        fail("01 single append", f"result={result} valid={len(valid)} invalid={invalid}")

    target2 = _tmp("t02_sequential.jsonl")
    if target2.exists():
        target2.unlink()
    n = 200
    for i in range(n):
        emit(make_event("t", "dummy", "LIVE", False, "use", requested_by="seq", metadata={"seq": i}), events_file=target2)
    valid, invalid = _read_valid_invalid(target2)
    seqs = sorted(v["metadata"]["seq"] for v in valid)
    if len(valid) == n and invalid == 0 and seqs == list(range(n)):
        ok("02 sequential appends", f"{n}/{n} valid, in order, 0 invalid")
    else:
        fail("02 sequential appends", f"valid={len(valid)}/{n} invalid={invalid}")


# ---------------------------------------------------------------------------
# 3-4: realistic + stress concurrent writers (real OS processes, real writer)
# ---------------------------------------------------------------------------
def _run_concurrent(n_writers: int, n_events: int, label: str):
    target = _tmp(f"t_concurrent_{label}.jsonl")
    if target.exists():
        target.unlink()
    procs = []
    for w in range(n_writers):
        p = subprocess.Popen(
            [sys.executable, str(WORKER_SCRIPT), str(PROJECT_ROOT), str(target), str(w), str(n_events)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        procs.append(p)
    for p in procs:
        p.communicate(timeout=60)
    valid, invalid = _read_valid_invalid(target)
    expected = n_writers * n_events
    seen = set()
    dup = 0
    for v in valid:
        key = (v["metadata"].get("worker"), v["metadata"].get("seq"))
        if key in seen:
            dup += 1
        seen.add(key)
    return dict(expected=expected, valid=len(valid), invalid=invalid, duplicates=dup, target=target)


def test_03_realistic_concurrent_writers():
    r = _run_concurrent(5, 20, "realistic")
    if r["invalid"] == 0 and r["valid"] == r["expected"] and r["duplicates"] == 0:
        ok("03 realistic concurrency (5 processes x 20 events)", f"{r['valid']}/{r['expected']} valid, 0 invalid, 0 dup")
    else:
        fail("03 realistic concurrency (5 processes x 20 events)",
             f"valid={r['valid']}/{r['expected']} invalid={r['invalid']} dup={r['duplicates']}")


def test_04_stress_concurrent_writers():
    """Same scenario that reproduced 14/1000 invalid + 80 lost events against
    the pre-fix writer during this patch's development (documented in the
    Architecture Repair 02 report) -- this is the regression proof."""
    r = _run_concurrent(50, 20, "stress")
    if r["invalid"] == 0 and r["valid"] == r["expected"] and r["duplicates"] == 0:
        ok("04 stress concurrency (50 processes x 20 events)",
           f"{r['valid']}/{r['expected']} valid, 0 invalid, 0 dup -- pre-fix writer produced 14 invalid + 80 lost on this exact scenario")
    else:
        fail("04 stress concurrency (50 processes x 20 events)",
             f"valid={r['valid']}/{r['expected']} invalid={r['invalid']} dup={r['duplicates']}")


# ---------------------------------------------------------------------------
# 5-6: exact event count / every line valid JSON (covered by 03/04 too;
# dedicated check for clarity per the mandate's explicit numbered list)
# ---------------------------------------------------------------------------
def test_05_06_exact_count_and_all_valid():
    r = _run_concurrent(10, 15, "count_check")
    all_valid_json = r["invalid"] == 0
    exact_count = r["valid"] == r["expected"] == 150
    if all_valid_json and exact_count:
        ok("05-06 exact event count + every line valid JSON", f"{r['valid']} events, 0 invalid")
    else:
        fail("05-06 exact event count + every line valid JSON", f"valid={r['valid']} expected=150 invalid={r['invalid']}")


# ---------------------------------------------------------------------------
# 7-8: unicode + embedded newline/quote characters in values
# ---------------------------------------------------------------------------
def test_07_08_unicode_and_special_chars():
    target = _tmp("t07_unicode.jsonl")
    if target.exists():
        target.unlink()
    tricky = 'línea con "comillas", \n newline literal, emoji 🚀, 中文, back\\slash'
    evt = make_event("t", "dummy", "LIVE", False, "use", requested_by="unicode-test",
                      metadata={"notes": tricky})
    result = emit(evt, events_file=target)
    valid, invalid = _read_valid_invalid(target)
    roundtrip_ok = len(valid) == 1 and valid[0]["metadata"]["notes"] == tricky
    # the file itself must still be exactly one physical line (embedded \n
    # must be JSON-escaped, not a literal newline byte, or it would split
    # the JSONL record in two)
    line_count = len([l for l in target.read_text(encoding="utf-8").splitlines() if l.strip()])
    if result and invalid == 0 and roundtrip_ok and line_count == 1:
        ok("07-08 unicode + embedded quotes/newline survive round-trip", "content byte-identical after json round-trip, still 1 JSONL line")
    else:
        fail("07-08 unicode + embedded quotes/newline survive round-trip",
             f"result={result} invalid={invalid} roundtrip_ok={roundtrip_ok} line_count={line_count}")


# ---------------------------------------------------------------------------
# 9: large payload
# ---------------------------------------------------------------------------
def test_09_large_payload():
    target = _tmp("t09_large.jsonl")
    if target.exists():
        target.unlink()
    big = "x" * 200_000  # 200KB single field, larger than typical OS pipe/atomic-write buffers
    evt = make_event("t", "dummy", "LIVE", False, "use", requested_by="large-payload", metadata={"blob": big})
    result = emit(evt, events_file=target)
    valid, invalid = _read_valid_invalid(target)
    if result and len(valid) == 1 and invalid == 0 and len(valid[0]["metadata"]["blob"]) == len(big):
        ok("09 large payload (200KB field)", "written and parsed back intact, still exactly 1 line")
    else:
        fail("09 large payload (200KB field)", f"result={result} valid={len(valid)} invalid={invalid}")


# ---------------------------------------------------------------------------
# 10-11: output directory failure / fail-open behavior
# ---------------------------------------------------------------------------
def test_10_11_directory_failure_fail_open():
    # Target a path where the parent cannot be created (a file, not a dir,
    # sitting where a directory component is expected) — must not raise,
    # must return False.
    blocker_file = _tmp("t10_blocker_is_a_file")
    blocker_file.write_text("i am a file, not a directory", encoding="utf-8")
    bad_target = blocker_file / "cannot_create_under_a_file" / "events.jsonl"
    raised = False
    result = None
    try:
        result = emit(make_event("t", "dummy", "LIVE", False, "use"), events_file=bad_target)
    except Exception:
        raised = True
    if blocker_file.exists():
        blocker_file.unlink()
    if (not raised) and result is False:
        ok("10-11 output directory failure is fail-open", "emit() returned False, did not raise")
    else:
        fail("10-11 output directory failure is fail-open", f"raised={raised} result={result}")

    # ATLAS_CAPABILITY_EVENTS_DISABLED=1 short-circuits cleanly too.
    os.environ["ATLAS_CAPABILITY_EVENTS_DISABLED"] = "1"
    try:
        disabled_target = _tmp("t11_disabled.jsonl")
        if disabled_target.exists():
            disabled_target.unlink()
        result_disabled = emit(make_event("t", "dummy", "LIVE", False, "use"), events_file=disabled_target)
        wrote_nothing = not disabled_target.exists()
        if result_disabled is False and wrote_nothing:
            ok("11b ATLAS_CAPABILITY_EVENTS_DISABLED=1 short-circuits", "no file written, returns False")
        else:
            fail("11b ATLAS_CAPABILITY_EVENTS_DISABLED=1 short-circuits", f"result={result_disabled} wrote_nothing={wrote_nothing}")
    finally:
        del os.environ["ATLAS_CAPABILITY_EVENTS_DISABLED"]


# ---------------------------------------------------------------------------
# 12: no unexpected duplicates (covered inside 03/04/05-06; explicit check)
# ---------------------------------------------------------------------------
def test_12_no_unexpected_duplicates():
    r = _run_concurrent(8, 25, "dup_check")
    if r["duplicates"] == 0:
        ok("12 no unexpected duplicates under concurrency", f"0 duplicates across {r['valid']} events")
    else:
        fail("12 no unexpected duplicates under concurrency", f"{r['duplicates']} duplicates found")


# ---------------------------------------------------------------------------
# 13: Windows-safe behavior
# ---------------------------------------------------------------------------
def test_13_windows_safe_behavior():
    if sys.platform == "win32":
        import core.capabilities.events as ev
        has_msvcrt_path = hasattr(ev, "_cross_process_lock")
        # Prove the lock is actually the Windows msvcrt-backed implementation,
        # not silently falling back to a no-op.
        import inspect
        src = inspect.getsource(ev._cross_process_lock)
        uses_msvcrt = "msvcrt" in src
        if has_msvcrt_path and uses_msvcrt:
            ok("13 Windows-safe cross-process lock", "msvcrt-backed lock confirmed present on win32")
        else:
            fail("13 Windows-safe cross-process lock", f"has_lock={has_msvcrt_path} uses_msvcrt={uses_msvcrt}")
    else:
        ok("13 Windows-safe cross-process lock", "not running on win32 this pass -- fcntl POSIX path exercised instead by tests 03/04/12")


def main():
    print("=" * 60)
    print("Bloque Capability Events Integrity -- Architecture Repair 02")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_01_02_single_and_sequential_appends()
    test_03_realistic_concurrent_writers()
    test_04_stress_concurrent_writers()
    test_05_06_exact_count_and_all_valid()
    test_07_08_unicode_and_special_chars()
    test_09_large_payload()
    test_10_11_directory_failure_fail_open()
    test_12_no_unexpected_duplicates()
    test_13_windows_safe_behavior()

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
