#!/usr/bin/env python3
"""
Validacion real de Bloque 1E.1: Reality-Checker Random Re-runs

9 tests:
- 8 unit (sampler + runner + dispatcher helper)
- 1 integration con qa_results sinteticos realistas
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
from reality_check_runner import RealityCheckRunner, DEFAULT_SAMPLE_SIZE


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_4": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


def make_qa_results(n_pass: int, n_fail: int = 0) -> List[Dict[str, Any]]:
    """Genera lista de QA results sinteticos para tests."""
    results = []
    for i in range(n_pass):
        results.append({
            "tarea": f"Task-{i}",
            "status": "PASS",
            "archivos": [f"src/file{i}.tsx"],
            "verificacion": "layout",
        })
    for i in range(n_fail):
        results.append({
            "tarea": f"FailTask-{i}",
            "status": "FAIL",
            "bloqueadores": ["test bloqueador"],
        })
    return results


# ============================================================
#  UNIT TESTS
# ============================================================

def test_1_sampler_deterministic_with_seed():
    print("\n" + "="*70)
    print("TEST 1: Sampler con seed fija es reproducible")
    print("="*70)
    qa = make_qa_results(n_pass=10)

    r1 = RealityCheckRunner(seed=42, sample_size=3)
    r2 = RealityCheckRunner(seed=42, sample_size=3)

    s1 = r1.sample(qa)
    s2 = r2.sample(qa)
    print(f"Sample 1: {[t['tarea'] for t in s1]}")
    print(f"Sample 2: {[t['tarea'] for t in s2]}")
    assert s1 == s2, "FAIL: misma seed debe producir misma muestra"
    assert len(s1) == 3
    print("[OK] TEST 1: Sampler determinista con seed fija")


def test_2_sampler_fewer_qa_than_sample_size():
    print("\n" + "="*70)
    print("TEST 2: Menos QA que sample_size -> retorna todos los disponibles")
    print("="*70)
    qa = make_qa_results(n_pass=2)  # menos que default 3

    r = RealityCheckRunner(seed=1, sample_size=5)
    s = r.sample(qa)
    print(f"Sample size obtenido: {len(s)}, tareas: {[t['tarea'] for t in s]}")
    assert len(s) == 2, f"FAIL: debe retornar los 2 disponibles, got {len(s)}"
    print("[OK] TEST 2: Sampler ajusta a items disponibles sin romper")


def test_3_sampler_zero_qa_results():
    print("\n" + "="*70)
    print("TEST 3: 0 QA results -> sample vacio sin romper")
    print("="*70)
    r = RealityCheckRunner(seed=1, sample_size=3)

    # Lista vacia
    assert r.sample([]) == []

    # Solo FAILs (sin PASS)
    qa_fails = make_qa_results(n_pass=0, n_fail=3)
    assert r.sample(qa_fails) == []
    print("[OK] TEST 3: 0 QA PASS -> sample vacio")


def test_4_run_re_runs_all_confirmed():
    print("\n" + "="*70)
    print("TEST 4: Todos los reruns confirman -> verdict CONFIRMED")
    print("="*70)
    qa = make_qa_results(n_pass=5)

    def confirming_callback(qa_result):
        return {"status": "PASS", "details": "rerun OK"}

    r = RealityCheckRunner(seed=1, sample_size=3)
    verdict = r.run_re_runs(qa, confirming_callback)
    print(f"verdict={verdict['verdict']}, sample={verdict['sample_size']}, total={verdict['total_qa_pass']}")
    print(f"  rerun_results: {[(x['tarea'], x['verdict']) for x in verdict['rerun_results']]}")
    assert verdict["verdict"] == "CONFIRMED"
    assert verdict["sample_size"] == 3
    assert verdict["total_qa_pass"] == 5
    assert all(r["verdict"] == "CONFIRMED" for r in verdict["rerun_results"])
    assert verdict["discrepancies"] == []
    print("[OK] TEST 4: Todos confirmados -> CONFIRMED global")


def test_5_run_re_runs_with_discrepancy():
    print("\n" + "="*70)
    print("TEST 5: Al menos 1 rerun FAIL -> verdict DISCREPANCY")
    print("="*70)
    qa = make_qa_results(n_pass=5)

    call_count = [0]
    def flaky_callback(qa_result):
        call_count[0] += 1
        # Segunda invocacion retorna FAIL
        if call_count[0] == 2:
            return {"status": "FAIL", "details": "screenshot diff detected"}
        return {"status": "PASS", "details": "rerun OK"}

    r = RealityCheckRunner(seed=1, sample_size=3)
    verdict = r.run_re_runs(qa, flaky_callback)
    print(f"verdict={verdict['verdict']}, discrepancies={len(verdict['discrepancies'])}")
    print(f"  rerun_results: {[(x['tarea'], x['rerun'], x['verdict']) for x in verdict['rerun_results']]}")
    assert verdict["verdict"] == "DISCREPANCY"
    assert len(verdict["discrepancies"]) == 1
    assert verdict["discrepancies"][0]["original"] == "PASS"
    assert verdict["discrepancies"][0]["rerun"] == "FAIL"
    assert "screenshot diff" in verdict["discrepancies"][0]["details"]
    print("[OK] TEST 5: Discrepancia detectada con detalle")


def test_6_run_re_runs_callback_raises_inconclusive():
    print("\n" + "="*70)
    print("TEST 6: Callback raisea -> rerun marcado INCONCLUSIVE (no DISCREPANCY)")
    print("="*70)
    qa = make_qa_results(n_pass=3)

    def buggy_callback(qa_result):
        raise RuntimeError("network unavailable")

    r = RealityCheckRunner(seed=1, sample_size=3)
    verdict = r.run_re_runs(qa, buggy_callback)
    print(f"verdict={verdict['verdict']}")
    print(f"  rerun_results: {[(x['tarea'], x['verdict']) for x in verdict['rerun_results']]}")
    assert verdict["verdict"] == "INCONCLUSIVE"
    # NO debe haber discrepancias (excepcion no es FAIL legitimo)
    assert verdict["discrepancies"] == []
    # Todos los rerun_results deben tener detalles de excepcion
    for r_result in verdict["rerun_results"]:
        assert r_result["verdict"] == "INCONCLUSIVE"
        assert "network unavailable" in r_result["details"]
    print("[OK] TEST 6: Excepcion NO se confunde con discrepancia")


def test_7_zero_qa_pass_returns_inconclusive_warning():
    print("\n" + "="*70)
    print("TEST 7: Sin QA PASS -> verdict INCONCLUSIVE con warning")
    print("="*70)
    qa = make_qa_results(n_pass=0, n_fail=2)  # solo FAILs

    def any_callback(qa_result):
        return {"status": "PASS"}

    r = RealityCheckRunner(seed=1, sample_size=3)
    verdict = r.run_re_runs(qa, any_callback)
    print(f"verdict={verdict['verdict']}, note: {verdict['note'][:80]}")
    assert verdict["verdict"] == "INCONCLUSIVE"
    assert verdict["sample_size"] == 0
    assert verdict["total_qa_pass"] == 0
    assert verdict["rerun_results"] == []
    assert "No hay QA results" in verdict["note"]
    print("[OK] TEST 7: 0 QA PASS no rompe, INCONCLUSIVE warning")


def test_8_dispatcher_helper_integration():
    print("\n" + "="*70)
    print("TEST 8: dispatcher.run_certification_re_runs() helper end-to-end")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        qa = make_qa_results(n_pass=4)

        def callback(qa_result):
            return {"status": "PASS", "details": "ok"}

        verdict = d.run_certification_re_runs(
            qa_results=qa,
            rerun_callback=callback,
            sample_size=2,
            seed=42,
        )
        print(f"verdict={verdict['verdict']}, sample={verdict['sample_size']}")
        assert verdict["verdict"] == "CONFIRMED"
        assert verdict["sample_size"] == 2
        assert verdict["total_qa_pass"] == 4
        assert verdict["seed"] == 42
    print("[OK] TEST 8: Helper del dispatcher funciona end-to-end")


def test_9_backward_compat_envelope_validation():
    print("\n" + "="*70)
    print("TEST 9: Backward compat — validate_return_envelope sin re_runs")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Envelope tipico de reality-checker SIN re_runs_performed
        envelope = {
            "status": "CERTIFIED",
            "tarea": "Certificacion proyecto",
            "archivos": ["report.md"],
            "engram": "atlas/certificacion",
            "verificacion": "none",
            "bloqueadores": [],
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="standard")
        print(f"is_valid={is_valid}, errores={errores}")
        # 1E.1 no agrega exigencias en validate_return_envelope todavia
        # (el agente decide si invocar el helper antes de certificar)
        assert is_valid is True, "FAIL: envelope sin re_runs debe seguir pasando en standard"
    print("[OK] TEST 9: Backward compat preservada")


# ============================================================
#  INTEGRATION
# ============================================================

def test_10_realistic_scenario_50_qa_results():
    print("\n" + "="*70)
    print("TEST 10 [INTEGRATION-LIKE]: Escenario realista con 50 QA results")
    print("="*70)
    # Simulamos un proyecto grande: 50 QA PASS + 3 FAIL
    qa = make_qa_results(n_pass=50, n_fail=3)

    # Callback que simula: 1 de cada 25 reruns difiere (4% falso positivo)
    rerun_count = [0]
    def realistic_callback(qa_result):
        rerun_count[0] += 1
        # El task con indice 7 (al azar) "tiene" un falso PASS
        if "Task-7" in qa_result.get("tarea", ""):
            return {"status": "FAIL", "details": "race condition discovered"}
        return {"status": "PASS", "details": "rerun OK"}

    # Seed que probabilisticamente incluye Task-7 en la muestra
    # (con sample_size=10 sobre 50 hay buena chance)
    r = RealityCheckRunner(seed=42, sample_size=10)
    verdict = r.run_re_runs(qa, realistic_callback)
    print(f"verdict={verdict['verdict']}, sample={verdict['sample_size']}/{verdict['total_qa_pass']}")
    print(f"  rerun calls: {rerun_count[0]}")
    print(f"  discrepancies: {len(verdict['discrepancies'])}")

    # Verificaciones mas relajadas: el sampler puede o no incluir Task-7
    # Lo importante: el flujo end-to-end funciona, el verdict es consistente
    assert verdict["total_qa_pass"] == 50
    assert verdict["sample_size"] == 10
    assert verdict["verdict"] in {"CONFIRMED", "DISCREPANCY"}
    # Si incluyo Task-7, debe ser DISCREPANCY; si no, CONFIRMED
    sample_tareas = {r["tarea"] for r in verdict["rerun_results"]}
    if "Task-7" in sample_tareas:
        assert verdict["verdict"] == "DISCREPANCY"
        print("  Task-7 incluido en sample -> DISCREPANCY detectado correctamente")
    else:
        assert verdict["verdict"] == "CONFIRMED"
        print("  Task-7 NO incluido en sample -> CONFIRMED (sin descubrir el falso PASS)")
    print("[OK] TEST 10: Escenario realista funciona end-to-end")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1E.1: Reality-Checker Random Re-runs")
    print("="*70)

    tests = [
        test_1_sampler_deterministic_with_seed,
        test_2_sampler_fewer_qa_than_sample_size,
        test_3_sampler_zero_qa_results,
        test_4_run_re_runs_all_confirmed,
        test_5_run_re_runs_with_discrepancy,
        test_6_run_re_runs_callback_raises_inconclusive,
        test_7_zero_qa_pass_returns_inconclusive_warning,
        test_8_dispatcher_helper_integration,
        test_9_backward_compat_envelope_validation,
        test_10_realistic_scenario_50_qa_results,
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
        print("[OK] Sampler determinista con seed fija")
        print("[OK] Sampler ajusta cuando hay menos QA que sample_size")
        print("[OK] 0 QA PASS no rompe (sample vacio)")
        print("[OK] Reruns confirmados -> CONFIRMED")
        print("[OK] Discrepancia detectada con detalle preservado")
        print("[OK] Callback que raisea -> INCONCLUSIVE (no DISCREPANCY)")
        print("[OK] 0 QA PASS -> INCONCLUSIVE con warning (no romper)")
        print("[OK] dispatcher.run_certification_re_runs() helper funciona")
        print("[OK] Backward compat: validate_return_envelope sin cambios")
        print("[OK] Escenario realista 50 QA results funciona")
        print("\nLO QUE 1E.1 NO HACE:")
        print("- Solo cubre random re-runs en certificacion")
        print("- NO cubre QA visual multi-capa (LLM-as-judge, network inspection)")
        print("- NO fuerza al reality-checker agente a invocar el helper")
        print("- El agente DEBE leer su md actualizado y llamar al runner")
        print("- 3 muestras de N tareas sigue siendo bajo coverage (acepto como")
        print("  mejora incremental honesta sobre confianza ciega)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
