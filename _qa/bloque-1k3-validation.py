#!/usr/bin/env python3
"""
Validacion real de Bloque 1K.3: Hard Enforcement Escalation

11 tests:
- 10 unit (enforcement per critical/non-critical agent, backward compat)
- 1 integration con audit real
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from invocation_tracker import InvocationTracker


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


def make_valid_envelope_qa() -> Dict[str, Any]:
    """Envelope valido para qa_strict mode (PASS con archivos)."""
    return {
        "status": "PASS",
        "tarea": "Login flow QA",
        "engram": "atlas/qa-1",
        "archivos": ["src/Login.tsx"],
        "bloqueadores": [],
    }


# ============================================================
#  TESTS
# ============================================================

def test_1_critical_agents_set_correct():
    print("\n=== TEST 1: CRITICAL_AGENTS contiene los 4 esperados ===")
    expected = {"evidence-collector", "reality-checker", "ux-architect", "ui-designer"}
    assert ATLASDispatcher.CRITICAL_AGENTS == expected
    print(f"[OK] {len(expected)} agentes criticos definidos")


def test_2_non_critical_agent_enforcement_skipped():
    print("\n=== TEST 2: Agente no critico + enforce_helpers=True -> skipped ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "completado", "tarea": "logo", "engram": "x", "archivos": ["logo.svg"], "bloqueadores": []}
        is_valid, errores = d.validate_return_envelope(
            envelope,
            mode="standard",
            enforce_helpers=True,
            agent_name="brand-agent",
        )
        # brand-agent no esta en CRITICAL_AGENTS -> enforcement skipped
        # Validacion normal pasa
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True
        # Y no debe haber _dispatcher_enforcement
        assert "_dispatcher_enforcement" not in envelope
    print("[OK] Agente no critico no afectado por enforce_helpers")


def test_3_critical_agent_all_helpers_passes():
    print("\n=== TEST 3: Agente critico + todos helpers invocados -> ACCEPT ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Invocar todos los helpers de evidence-collector
        d.validate_return_envelope({"status": "PASS", "tarea": "x", "engram": "y", "archivos": ["a"]}, mode="qa_strict")
        d.should_skip_qa("task-1", [])
        d.inspect_network_requests([])
        d.analyze_console_messages([])
        d.check_visual_fidelity({}, {})
        d.verify_screenshot_evidence({"screenshot_path": ""})

        envelope = make_valid_envelope_qa()
        is_valid, errores = d.validate_return_envelope(
            envelope,
            mode="qa_strict",
            enforce_helpers=True,
            agent_name="evidence-collector",
        )
        print(f"is_valid={is_valid}, errores={errores[:1] if errores else []}")
        assert is_valid is True
        # No debe haber enforcement record (passed)
        # Pero si lo hay, debe ser passed
        if "_dispatcher_enforcement" in envelope:
            assert envelope["_dispatcher_enforcement"].get("verdict") != "incomplete"
    print("[OK] Critico con helpers completos: ACCEPT")


def test_4_critical_agent_missing_helpers_blocked():
    print("\n=== TEST 4: Agente critico + helpers faltantes -> REJECT ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Solo invocar validate_return_envelope (no los otros 5 helpers)
        # nota: la propia llamada de abajo cuenta como una invocacion mas

        envelope = make_valid_envelope_qa()
        is_valid, errores = d.validate_return_envelope(
            envelope,
            mode="qa_strict",
            enforce_helpers=True,
            agent_name="evidence-collector",
        )
        print(f"is_valid={is_valid}, num errores={len(errores)}")
        print(f"  enforcement: {envelope.get('_dispatcher_enforcement', {}).get('verdict')}")
        # Faltan should_skip_qa, inspect_network, analyze_console, check_visual, verify_screenshot
        assert is_valid is False
        assert any("Hard enforcement" in e for e in errores)
        assert any("evidence-collector" in e for e in errores)
        # Verificar el record en el envelope
        enforcement = envelope.get("_dispatcher_enforcement")
        assert enforcement is not None
        assert enforcement["verdict"] == "incomplete"
        assert enforcement["severity"] == "HARD_BLOCK"
        assert len(enforcement["missing_helpers"]) >= 4
    print("[OK] Critico con missing helpers: REJECT con detalle")


def test_5_backward_compat_no_enforce_default():
    print("\n=== TEST 5: enforce_helpers=False (default) -> idéntico a pre-1K.3 ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = make_valid_envelope_qa()

        # SIN enforce_helpers (default False)
        is_valid1, errores1 = d.validate_return_envelope(envelope, mode="qa_strict")

        # CON enforce_helpers=False explicito
        envelope2 = make_valid_envelope_qa()
        is_valid2, errores2 = d.validate_return_envelope(
            envelope2, mode="qa_strict", enforce_helpers=False, agent_name="evidence-collector"
        )

        assert is_valid1 == is_valid2
        assert "_dispatcher_enforcement" not in envelope
        assert "_dispatcher_enforcement" not in envelope2
    print("[OK] enforce_helpers=False preserva backward compat")


def test_6_enforce_without_agent_name_skipped():
    print("\n=== TEST 6: enforce_helpers=True sin agent_name -> sin enforcement ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = make_valid_envelope_qa()
        is_valid, errores = d.validate_return_envelope(
            envelope, mode="qa_strict", enforce_helpers=True, agent_name=None
        )
        # Sin agent_name, no se aplica enforcement
        assert is_valid is True
        assert "_dispatcher_enforcement" not in envelope
    print("[OK] Sin agent_name: fallback graceful")


def test_7_unknown_agent_enforcement_skipped():
    print("\n=== TEST 7: Agente desconocido + enforce=True -> sin enforcement ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = make_valid_envelope_qa()
        is_valid, errores = d.validate_return_envelope(
            envelope, mode="qa_strict", enforce_helpers=True, agent_name="agente-inventado-xyz"
        )
        # Agente desconocido no esta en CRITICAL_AGENTS -> skip
        assert is_valid is True
        assert "_dispatcher_enforcement" not in envelope
    print("[OK] Agente desconocido: skipped sin romper")


def test_8_ux_architect_critical_enforcement():
    print("\n=== TEST 8: ux-architect critico sin helpers -> REJECT ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "tarea": "Tokens CSS",
            "engram": "atlas/css-foundation",
            "archivos": ["tokens.css"],
            "bloqueadores": [],
            "design_intelligence": {"queried": True, "industry": "saas", "style": "Glassmorphism"},
        }
        is_valid, errores = d.validate_return_envelope(
            envelope, mode="design_strict", enforce_helpers=True, agent_name="ux-architect"
        )
        print(f"is_valid={is_valid}")
        # ux-architect requiere validate_return_envelope, consult_design_intelligence, verify_design_intelligence_real
        # Solo se invoco validate_return_envelope (la llamada actual) -> 2 helpers faltantes
        assert is_valid is False
        enforcement = envelope.get("_dispatcher_enforcement")
        assert enforcement is not None
        assert enforcement["is_critical"] is True
        assert "consult_design_intelligence" in enforcement["missing_helpers"] or \
               "verify_design_intelligence_real" in enforcement["missing_helpers"]
    print("[OK] ux-architect bloqueado correctamente")


def test_9_enforce_helpers_for_agent_direct():
    print("\n=== TEST 9: enforce_helpers_for_agent() directo ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Agente NO critico
        env1 = {"status": "completado"}
        r1 = d.enforce_helpers_for_agent(env1, "brand-agent")
        assert r1["verdict"] == "skipped"
        assert r1["is_critical"] is False
        assert "_dispatcher_enforcement" not in env1

        # Agente critico sin helpers invocados
        env2 = {"status": "PASS"}
        r2 = d.enforce_helpers_for_agent(env2, "reality-checker")
        # reality-checker requiere validate_return_envelope + run_certification_re_runs
        # Ninguno invocado -> incomplete
        assert r2["verdict"] == "incomplete"
        assert r2["is_critical"] is True
        assert "_dispatcher_enforcement" in env2
        assert env2["_dispatcher_enforcement"]["severity"] == "HARD_BLOCK"
    print("[OK] enforce_helpers_for_agent funciona standalone")


def test_10_envelope_enforcement_persists_after_block():
    print("\n=== TEST 10: Envelope marcado con _dispatcher_enforcement queda observable ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = make_valid_envelope_qa()
        d.validate_return_envelope(
            envelope, mode="qa_strict", enforce_helpers=True, agent_name="evidence-collector"
        )
        # El envelope debe quedar marcado para que el orquestador lo vea
        enforcement = envelope.get("_dispatcher_enforcement")
        assert enforcement is not None
        assert "verdict" in enforcement
        assert "missing_helpers" in enforcement
        assert "severity" in enforcement
        assert "audit" in enforcement
        # audit debe tener detalle
        assert "required_for_agent" in enforcement["audit"]
        assert "invoked" in enforcement["audit"]
        print(f"  enforcement: verdict={enforcement['verdict']}, missing_count={len(enforcement['missing_helpers'])}")
    print("[OK] Envelope marcado con detalle completo")


def test_11_integration_realistic_flow():
    print("\n=== TEST 11 [INTEGRATION]: Flujo realistico Fase 3 con enforcement ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Simular flujo Fase 3 completo de evidence-collector (todos los helpers)
        d.should_skip_qa("atlas/tarea-1", ["src/Login.tsx"])
        d.inspect_network_requests([{"url": "https://app.com", "status": 200}])
        d.analyze_console_messages([])
        d.check_visual_fidelity({}, {})
        # Crear screenshot fake para verify_screenshot_evidence
        (d.project_root / "screenshots").mkdir(exist_ok=True)
        (d.project_root / "screenshots" / "task-1.png").write_bytes(b"\x89PNG" + b"\x00" * 2000)
        d.verify_screenshot_evidence({"screenshot_path": "screenshots/task-1.png"})

        envelope = {
            "status": "PASS",
            "tarea": "Login flow QA",
            "engram": "atlas/qa-1",
            "archivos": ["src/Login.tsx"],
            "bloqueadores": [],
        }

        # Validar con enforcement
        is_valid, errores = d.validate_return_envelope(
            envelope,
            mode="qa_strict",
            enforce_helpers=True,
            agent_name="evidence-collector",
        )
        print(f"verdict={is_valid}, errores={[e[:80] for e in errores]}")
        # Todos los helpers invocados -> accept
        assert is_valid is True
        # Si hay enforcement record, debe ser passed o ausente
        if "_dispatcher_enforcement" in envelope:
            assert envelope["_dispatcher_enforcement"].get("verdict") != "incomplete"
    print("[OK] Flujo realistico con todos los helpers: ACCEPT")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1K.3: Hard Enforcement Escalation")
    print("="*70)

    tests = [
        test_1_critical_agents_set_correct,
        test_2_non_critical_agent_enforcement_skipped,
        test_3_critical_agent_all_helpers_passes,
        test_4_critical_agent_missing_helpers_blocked,
        test_5_backward_compat_no_enforce_default,
        test_6_enforce_without_agent_name_skipped,
        test_7_unknown_agent_enforcement_skipped,
        test_8_ux_architect_critical_enforcement,
        test_9_enforce_helpers_for_agent_direct,
        test_10_envelope_enforcement_persists_after_block,
        test_11_integration_realistic_flow,
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
        print("\nLO QUE 1K.3 NO HACE:")
        print("- NO ejecuta helpers faltantes automaticamente — solo bloquea envelope")
        print("- NO fuerza al orquestador a usar enforce_helpers=True (opt-in)")
        print("- NO cubre agentes fuera de CRITICAL_AGENTS (enforcement progresivo)")
        print("- NO genera retry automatico — solo señala 'envelope no aceptable'")
        print("- NO modifica qa-auto-audit.js hook (sigue advisory, complementa)")
        print("- Backward compat estricto: sin enforce_helpers=True, comportamiento identico")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
