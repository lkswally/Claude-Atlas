#!/usr/bin/env python3
"""
Validacion real de Bloque 1G.1: Orquestador Runtime Wiring

Tests de presencia documental: verifica que los prompts de agentes y el
agent-protocol.md contengan las invocaciones obligatorias de helpers del
dispatcher. Anti-regresion documental.

NO valida que el LLM en runtime realmente invoque los helpers — eso
depende del comportamiento del modelo. Lo que SI valida: si en un
futuro edit alguien borra las instrucciones, el test detecta la perdida.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))


def read_agent(name: str) -> str:
    """Lee el contenido del .md de un agente."""
    return (REPO_ROOT / ".claude" / "agents" / name).read_text(encoding="utf-8")


def assert_contains(text: str, patterns: List[str], file_label: str) -> None:
    """Falla si alguno de los patterns NO esta en el texto."""
    missing = [p for p in patterns if p not in text]
    if missing:
        raise AssertionError(
            f"{file_label} falta patrones: {missing}"
        )


# ============================================================
#  TESTS
# ============================================================

def test_1_orquestador_has_should_skip_qa():
    print("\n" + "="*70)
    print("TEST 1: orquestador.md menciona should_skip_qa (Fase 3 cache)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "should_skip_qa" in text, "FAIL: orquestador.md NO menciona should_skip_qa"
    assert "cache" in text.lower()
    print("[OK] TEST 1: should_skip_qa documentado en orquestador")


def test_2_orquestador_has_cache_qa_result():
    print("\n" + "="*70)
    print("TEST 2: orquestador.md menciona cache_qa_result (post-PASS write)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "cache_qa_result" in text, "FAIL: orquestador.md NO menciona cache_qa_result"
    print("[OK] TEST 2: cache_qa_result documentado")


def test_3_orquestador_has_design_strict():
    print("\n" + "="*70)
    print("TEST 3: orquestador.md menciona mode=design_strict (Fase 2)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "design_strict" in text, "FAIL: orquestador.md NO menciona design_strict"
    print("[OK] TEST 3: design_strict documentado")


def test_4_orquestador_has_resolve_ambiguous_project():
    print("\n" + "="*70)
    print("TEST 4: orquestador.md menciona resolve_ambiguous_project")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "resolve_ambiguous_project" in text, "FAIL: orquestador.md NO menciona resolve_ambiguous_project"
    assert "ambiguous_project" in text
    print("[OK] TEST 4: resolve_ambiguous_project documentado")


def test_5_orquestador_has_run_certification_re_runs():
    print("\n" + "="*70)
    print("TEST 5: orquestador.md menciona run_certification_re_runs (Fase 4)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "run_certification_re_runs" in text, "FAIL: orquestador.md NO menciona run_certification_re_runs"
    print("[OK] TEST 5: run_certification_re_runs documentado")


def test_6_orquestador_has_get_cajon_full():
    print("\n" + "="*70)
    print("TEST 6: orquestador.md menciona get_cajon_full (2-step real)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "get_cajon_full" in text, "FAIL: orquestador.md NO menciona get_cajon_full"
    print("[OK] TEST 6: get_cajon_full documentado")


def test_7_orquestador_has_delegation_state():
    print("\n" + "="*70)
    print("TEST 7: orquestador.md menciona delegation-state.json (Bloque 1D.1)")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "delegation-state" in text, "FAIL: orquestador.md NO menciona delegation-state"
    assert "escalation_needed" in text
    print("[OK] TEST 7: Delegation Stop Rules check documentado")


def test_8_orquestador_has_runtime_wiring_section():
    print("\n" + "="*70)
    print("TEST 8: orquestador.md tiene seccion 'Runtime Helpers Wiring (Bloque 1G.1)'")
    print("="*70)
    text = read_agent("orquestador.md")
    assert "Runtime Helpers Wiring" in text, "FAIL: falta la seccion explicita"
    assert "Bloque 1G.1" in text
    print("[OK] TEST 8: Seccion 1G.1 presente como anchor")


def test_9_evidence_collector_reforzado():
    print("\n" + "="*70)
    print("TEST 9: evidence-collector.md tiene 'OBLIGATORIO SIEMPRE' en Cache Check")
    print("="*70)
    text = read_agent("evidence-collector.md")
    assert "OBLIGATORIO SIEMPRE" in text, "FAIL: refuerzo OBLIGATORIO SIEMPRE no presente"
    assert "1G.1" in text
    assert "should_skip_qa" in text
    print("[OK] TEST 9: Evidence-collector con refuerzo 1G.1")


def test_10_reality_checker_reforzado():
    print("\n" + "="*70)
    print("TEST 10: reality-checker.md tiene 'INVOCAR ANTES DE CERTIFIED'")
    print("="*70)
    text = read_agent("reality-checker.md")
    assert "INVOCAR ANTES DE CERTIFIED" in text or "ANTES DE CERTIFIED" in text, "FAIL: refuerzo de orden no presente"
    assert "1G.1" in text
    print("[OK] TEST 10: Reality-checker con refuerzo de orden 1G.1")


def test_11_ux_architect_y_ui_designer_referencian_design_strict():
    print("\n" + "="*70)
    print("TEST 11: ux-architect.md y ui-designer.md referencian design_strict + 1G.1")
    print("="*70)
    ux = read_agent("ux-architect.md")
    ui = read_agent("ui-designer.md")
    for label, text in [("ux-architect.md", ux), ("ui-designer.md", ui)]:
        assert "design_strict" in text, f"FAIL: {label} NO referencia design_strict"
        assert "1G.1" in text, f"FAIL: {label} NO menciona 1G.1"
        assert "design_intelligence" in text, f"FAIL: {label} NO menciona design_intelligence"
    print("[OK] TEST 11: ux-architect + ui-designer con refuerzos 1G.1")


def test_12_agent_protocol_has_runtime_wiring_contract():
    print("\n" + "="*70)
    print("TEST 12: agent-protocol.md tiene seccion 4.8 'Runtime Wiring Contract'")
    print("="*70)
    text = read_agent("agent-protocol.md")
    assert "4.8" in text, "FAIL: numero de seccion 4.8 no presente"
    assert "Runtime Wiring Contract" in text, "FAIL: titulo no presente"
    # Matrix consolidada debe mencionar todos los helpers clave
    required_helpers = [
        "get_cajon_full",
        "resolve_ambiguous_project",
        "validate_return_envelope",
        "should_skip_qa",
        "cache_qa_result",
        "run_certification_re_runs",
        "consult_design_intelligence",
        "delegation-state.json",
    ]
    assert_contains(text, required_helpers, "agent-protocol.md § 4.8")
    print("[OK] TEST 12: Matriz consolidada presente en agent-protocol § 4.8")


def test_13_smoke_dispatcher_helpers_importable():
    print("\n" + "="*70)
    print("TEST 13: Smoke -- todos los helpers del wiring son importables/llamables")
    print("="*70)
    from atlas_dispatcher import ATLASDispatcher
    import inspect

    methods = {
        "get_cajon_full",
        "resolve_ambiguous_project",
        "validate_return_envelope",
        "should_skip_qa",
        "cache_qa_result",
        "run_certification_re_runs",
        "consult_design_intelligence",
    }
    for m in methods:
        assert hasattr(ATLASDispatcher, m), f"FAIL: ATLASDispatcher.{m} no existe"
        assert callable(getattr(ATLASDispatcher, m)), f"FAIL: ATLASDispatcher.{m} no es callable"
    print(f"[OK] TEST 13: {len(methods)} helpers presentes en ATLASDispatcher")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1G.1: Orquestador Runtime Wiring")
    print("="*70)
    print("Tipo: presencia documental (anti-regresion sobre prompts)")
    print("NO valida comportamiento del LLM en runtime — eso es out of scope.")

    tests = [
        test_1_orquestador_has_should_skip_qa,
        test_2_orquestador_has_cache_qa_result,
        test_3_orquestador_has_design_strict,
        test_4_orquestador_has_resolve_ambiguous_project,
        test_5_orquestador_has_run_certification_re_runs,
        test_6_orquestador_has_get_cajon_full,
        test_7_orquestador_has_delegation_state,
        test_8_orquestador_has_runtime_wiring_section,
        test_9_evidence_collector_reforzado,
        test_10_reality_checker_reforzado,
        test_11_ux_architect_y_ui_designer_referencian_design_strict,
        test_12_agent_protocol_has_runtime_wiring_contract,
        test_13_smoke_dispatcher_helpers_importable,
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
        print("[OK] orquestador.md tiene seccion 'Runtime Helpers Wiring (1G.1)'")
        print("[OK] orquestador.md menciona los 6 helpers clave:")
        print("     - should_skip_qa, cache_qa_result, design_strict,")
        print("       resolve_ambiguous_project, run_certification_re_runs, get_cajon_full")
        print("[OK] orquestador.md documenta lectura de delegation-state.json")
        print("[OK] evidence-collector, reality-checker, ux-architect, ui-designer")
        print("     tienen refuerzos 1G.1")
        print("[OK] agent-protocol § 4.8 tiene matriz consolidada de helpers")
        print("[OK] Todos los helpers del wiring son importables en ATLASDispatcher")
        print("\nLO QUE 1G.1 NO HACE:")
        print("- NO garantiza que el LLM realmente ejecute las invocaciones")
        print("- NO agrega tracing en runtime (out of scope)")
        print("- NO cambia codigo Python — solo refuerza prompts")
        print("- NO usa hooks PostToolUse para forzar invocacion (seria 1G.2+)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
