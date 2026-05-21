#!/usr/bin/env python3
"""
Validacion real de Bloque 1K.4: Auto-Invocation of Missing Helpers

12 tests:
- 11 unit (auto-invoke por helper, contexto insuficiente, loop guard, etc.)
- 1 integration realistic con envelope completo
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


def write_screenshot(root: Path, rel: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 5000)
    return p


# ============================================================
#  TESTS
# ============================================================

def test_1_auto_invoke_should_skip_qa():
    print("\n=== TEST 1: Auto-invoke should_skip_qa con tarea+archivos ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "PASS",
            "tarea": "atlas/tarea-1",
            "archivos": ["src/Login.tsx"],
        }
        result = d._try_auto_invoke_helpers(envelope, ["should_skip_qa"])
        print(f"auto_invoked: {[a['helper'] for a in result['auto_invoked']]}")
        assert any(a["helper"] == "should_skip_qa" for a in result["auto_invoked"])
        assert result["still_missing"] == []
    print("[OK]")


def test_2_auto_invoke_should_skip_qa_no_context():
    print("\n=== TEST 2: should_skip_qa sin tarea -> contexto insuficiente ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "PASS"}  # sin tarea ni archivos
        result = d._try_auto_invoke_helpers(envelope, ["should_skip_qa"])
        assert result["auto_invoked"] == []
        assert any(f["helper"] == "should_skip_qa" for f in result["auto_invoke_failed"])
        assert "should_skip_qa" in result["still_missing"]
    print("[OK]")


def test_3_auto_invoke_verify_screenshot_evidence():
    print("\n=== TEST 3: Auto-invoke verify_screenshot_evidence con screenshot_path ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_screenshot(d.project_root, "qa-evidence/login.png")
        envelope = {
            "status": "PASS",
            "tarea": "task-1",
            "archivos": ["x.tsx"],
            "screenshot_path": "qa-evidence/login.png",
        }
        result = d._try_auto_invoke_helpers(envelope, ["verify_screenshot_evidence"])
        assert any(a["helper"] == "verify_screenshot_evidence" for a in result["auto_invoked"])
        # verdict del helper debe ser "ok" (archivo existe)
        screenshot_check = [a for a in result["auto_invoked"] if a["helper"] == "verify_screenshot_evidence"][0]
        assert screenshot_check.get("verdict") == "ok"
    print("[OK]")


def test_4_auto_invoke_verify_screenshot_no_path():
    print("\n=== TEST 4: verify_screenshot sin screenshot_path -> contexto insuficiente ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "PASS"}
        result = d._try_auto_invoke_helpers(envelope, ["verify_screenshot_evidence"])
        assert result["auto_invoked"] == []
        assert any(f["helper"] == "verify_screenshot_evidence" for f in result["auto_invoke_failed"])
    print("[OK]")


def test_5_auto_invoke_design_intelligence_real_mocked():
    print("\n=== TEST 5: Auto-invoke verify_design_intelligence_real con di en envelope ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "design_intelligence": {
                "queried": True,
                "industry": "saas-b2b",
                "style": "Glassmorphism + Flat Design",
            },
        }

        # Mock skill para no depender de skill real
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [{"Product Type": "SaaS", "Primary Style Recommendation": "Glassmorphism + Flat Design"}],
                "count": 1, "domain": "product", "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            result = d._try_auto_invoke_helpers(envelope, ["verify_design_intelligence_real"])

        assert any(a["helper"] == "verify_design_intelligence_real" for a in result["auto_invoked"])
        match_check = [a for a in result["auto_invoked"] if a["helper"] == "verify_design_intelligence_real"][0]
        assert match_check.get("verdict") == "match"
    print("[OK]")


def test_6_non_auto_invocable_helpers():
    print("\n=== TEST 6: Helpers NO auto-invocables quedan en still_missing ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "PASS"}
        non_auto = ["inspect_network_requests", "analyze_console_messages",
                    "check_visual_fidelity", "run_certification_re_runs"]
        result = d._try_auto_invoke_helpers(envelope, non_auto)
        assert result["auto_invoked"] == []
        assert sorted(result["not_auto_invocable"]) == sorted(non_auto)
        assert sorted(result["still_missing"]) == sorted(non_auto)
    print("[OK]")


def test_7_loop_guard_validate_return_envelope():
    print("\n=== TEST 7: Loop guard — validate_return_envelope NO se auto-invoca ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "PASS"}
        result = d._try_auto_invoke_helpers(envelope, ["validate_return_envelope"])
        # Esta en NON_AUTO_INVOCABLE_HELPERS -> queda en still_missing
        assert "validate_return_envelope" in result["not_auto_invocable"]
        assert "validate_return_envelope" in result["still_missing"]
    print("[OK]")


def test_8_validate_return_envelope_try_auto_invoke_resolves():
    print("\n=== TEST 8: validate_return_envelope con try_auto_invoke=True resuelve ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_screenshot(d.project_root, "screenshots/task-1.png")

        envelope = {
            "status": "PASS",
            "tarea": "atlas/tarea-1",
            "engram": "atlas/qa-1",
            "archivos": ["src/Login.tsx"],
            "bloqueadores": [],
            "screenshot_path": "screenshots/task-1.png",
        }
        # Solo auto-invocables van a faltar: should_skip_qa, cache_qa_result, verify_screenshot_evidence
        # NO auto-invocables: inspect_network, analyze_console, check_visual

        # PRIMERO: sin try_auto_invoke (default False) -> rechazar
        is_valid_default, errores_default = d.validate_return_envelope(
            envelope, mode="qa_strict", enforce_helpers=True, agent_name="evidence-collector"
        )
        assert is_valid_default is False  # missing helpers

        # AHORA: con try_auto_invoke=True
        # Crear nuevo envelope porque el anterior tiene _dispatcher_enforcement de la prev call
        envelope2 = {
            "status": "PASS",
            "tarea": "atlas/tarea-1",
            "engram": "atlas/qa-1",
            "archivos": ["src/Login.tsx"],
            "bloqueadores": [],
            "screenshot_path": "screenshots/task-1.png",
        }
        is_valid_auto, errores_auto = d.validate_return_envelope(
            envelope2, mode="qa_strict", enforce_helpers=True,
            agent_name="evidence-collector", try_auto_invoke=True,
        )
        print(f"  enforcement verdict: {envelope2.get('_dispatcher_enforcement', {}).get('verdict')}")
        print(f"  auto_invoked: {[a['helper'] for a in envelope2.get('_dispatcher_enforcement', {}).get('auto_invoked', [])]}")
        # Algunos helpers son no auto-invocables (inspect_network, analyze_console, check_visual)
        # → seguiran missing, pero al menos should_skip_qa, cache_qa_result, verify_screenshot_evidence
        # deberian estar auto_invoked
        enforcement = envelope2.get("_dispatcher_enforcement", {})
        auto_inv_helpers = [a["helper"] for a in enforcement.get("auto_invoked", [])]
        # evidence-collector requirements: validate_return_envelope, should_skip_qa,
        # inspect_network_requests, analyze_console_messages, check_visual_fidelity,
        # verify_screenshot_evidence
        # De esos, auto-invocables son: should_skip_qa y verify_screenshot_evidence
        # NO auto-invocables: inspect_network, analyze_console, check_visual
        # cache_qa_result NO esta en requirements, no se audita como missing
        assert "should_skip_qa" in auto_inv_helpers
        assert "verify_screenshot_evidence" in auto_inv_helpers
    print("[OK]")


def test_9_backward_compat_try_auto_invoke_false():
    print("\n=== TEST 9: try_auto_invoke=False (default) -> 1K.3 puro ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "PASS", "tarea": "x", "engram": "y",
            "archivos": ["a.ts"], "bloqueadores": [],
            "screenshot_path": "no-existe.png",
        }
        # Sin try_auto_invoke
        is_valid, errores = d.validate_return_envelope(
            envelope, mode="qa_strict",
            enforce_helpers=True, agent_name="evidence-collector",
        )
        enforcement = envelope.get("_dispatcher_enforcement", {})
        # No debe haber auto_invoked
        assert "auto_invoked" not in enforcement
        assert enforcement.get("verdict") == "incomplete"
    print("[OK]")


def test_10_non_critical_agent_no_auto_invoke():
    print("\n=== TEST 10: Agente no critico + try_auto_invoke=True -> skipped (no aplica) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "completado", "tarea": "logo", "engram": "x",
                    "archivos": ["logo.svg"], "bloqueadores": []}
        is_valid, errores = d.validate_return_envelope(
            envelope, mode="standard",
            enforce_helpers=True, agent_name="brand-agent",
            try_auto_invoke=True,
        )
        # brand-agent no es critico -> enforcement skipped, no auto-invoke
        assert is_valid is True
        assert "_dispatcher_enforcement" not in envelope
    print("[OK]")


def test_11_cache_qa_result_only_pass():
    print("\n=== TEST 11: cache_qa_result auto-invoke solo si status=PASS ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # status=FAIL -> NO debe auto-invocar cache_qa_result
        envelope_fail = {
            "status": "FAIL", "tarea": "task-1", "archivos": ["x.ts"],
        }
        result = d._try_auto_invoke_helpers(envelope_fail, ["cache_qa_result"])
        assert result["auto_invoked"] == []
        assert any(f["helper"] == "cache_qa_result" and "PASS" in f["reason"]
                   for f in result["auto_invoke_failed"])

        # status=PASS -> SI auto-invoca
        envelope_pass = {
            "status": "PASS", "tarea": "task-1", "archivos": ["x.ts"],
        }
        result = d._try_auto_invoke_helpers(envelope_pass, ["cache_qa_result"])
        assert any(a["helper"] == "cache_qa_result" for a in result["auto_invoked"])
    print("[OK]")


def test_12_integration_realistic_envelope():
    print("\n=== TEST 12 [INTEGRATION]: Envelope realistico con todos los datos ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_screenshot(d.project_root, "qa-evidence/login-flow.png")

        # Envelope con TODOS los datos posibles para auto-invocacion
        envelope = {
            "status": "PASS",
            "tarea": "atlas/tarea-5",
            "engram": "atlas/qa-5",
            "archivos": ["src/Login.tsx", "src/auth.ts"],
            "bloqueadores": [],
            "screenshot_path": "qa-evidence/login-flow.png",
            "design_intelligence": {
                "queried": True,
                "industry": "saas-b2b",
                "style": "Glassmorphism",
                "verified_against": ["styles.csv"],
                "anti_generic_validated": True,
            },
        }

        # Mock skill para no depender de runtime real
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [{"Product Type": "SaaS", "Primary Style Recommendation": "Glassmorphism + Flat Design"}],
                "count": 1, "domain": "product", "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            is_valid, errores = d.validate_return_envelope(
                envelope, mode="qa_strict",
                enforce_helpers=True, agent_name="evidence-collector",
                try_auto_invoke=True,
            )

        enforcement = envelope.get("_dispatcher_enforcement", {})
        print(f"  verdict={enforcement.get('verdict')}")
        print(f"  auto_invoked={[a['helper'] for a in enforcement.get('auto_invoked', [])]}")
        print(f"  not_auto_invocable={enforcement.get('not_auto_invocable', [])}")

        # Deberian auto-invocarse: should_skip_qa, cache_qa_result, verify_screenshot_evidence
        # NO auto-invocables: inspect_network_requests, analyze_console_messages, check_visual_fidelity
        # → still_missing tiene los 3 no auto-invocables
        auto_inv_helpers = [a["helper"] for a in enforcement.get("auto_invoked", [])]
        assert "should_skip_qa" in auto_inv_helpers
        assert "verify_screenshot_evidence" in auto_inv_helpers
        # Pero quedan no auto-invocables → verdict=incomplete
        assert enforcement.get("verdict") == "incomplete"
        not_auto = enforcement.get("not_auto_invocable", [])
        assert "inspect_network_requests" in not_auto
        assert "analyze_console_messages" in not_auto
        assert "check_visual_fidelity" in not_auto
    print("[OK] Envelope realistico: auto-invoke parcial + still_missing detalle")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1K.4: Auto-Invocation of Missing Helpers")
    print("="*70)

    tests = [
        test_1_auto_invoke_should_skip_qa,
        test_2_auto_invoke_should_skip_qa_no_context,
        test_3_auto_invoke_verify_screenshot_evidence,
        test_4_auto_invoke_verify_screenshot_no_path,
        test_5_auto_invoke_design_intelligence_real_mocked,
        test_6_non_auto_invocable_helpers,
        test_7_loop_guard_validate_return_envelope,
        test_8_validate_return_envelope_try_auto_invoke_resolves,
        test_9_backward_compat_try_auto_invoke_false,
        test_10_non_critical_agent_no_auto_invoke,
        test_11_cache_qa_result_only_pass,
        test_12_integration_realistic_envelope,
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
        print("\nLO QUE 1K.4 NO HACE:")
        print("- NO inventa datos. Si el contexto no esta, no ejecuta")
        print("- NO obliga al orquestador a usar try_auto_invoke=True (opt-in)")
        print("- NO cubre helpers no auto-invocables (network, console, visual_fidelity, re_runs)")
        print("- NO modifica el envelope salvo agregar _dispatcher_enforcement con detalle")
        print("- NO genera retry automatico del subagent — solo intenta resolver via dispatcher")
        print("- Backward compat estricto: sin try_auto_invoke=True, comportamiento 1K.3 puro")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
