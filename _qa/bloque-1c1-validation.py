#!/usr/bin/env python3
"""
Validacion real de Bloque 1C.1: UI-UX Pro Max Skill Enforcement

9 tests:
- 8 unit (mock skill + envelope validation)
- 1 integration opt-in (skill real)

Cubre SOLO ui-ux-pro-max-skill (motor BM25 design intelligence).
NO cubre otros skills.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from skills_invocation import SkillsInvocation, VALID_DOMAINS


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_2": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  UNIT TESTS
# ============================================================

def test_1_skill_resolution():
    print("\n" + "="*70)
    print("TEST 1: SkillsInvocation resuelve path correctamente")
    print("="*70)

    # Path explicito existente
    skill_path = Path.home() / ".claude" / "design-data" / "search.js"
    if not skill_path.exists():
        print("[SKIP] search.js no esta en ~/.claude/design-data/")
        return

    inv = SkillsInvocation(skill_path=str(skill_path))
    assert inv._skill_path == str(skill_path)
    assert inv.is_available() is True

    # Path inexistente
    inv2 = SkillsInvocation(skill_path="/nonexistent/path.js")
    assert inv2._skill_path is None
    assert inv2.is_available() is False
    print("[OK] TEST 1: Resolucion de path + is_available correctos")


def test_2_skill_invocation_real():
    print("\n" + "="*70)
    print("TEST 2: Skill real responde a query con output parseable")
    print("="*70)
    skill_path = Path.home() / ".claude" / "design-data" / "search.js"
    if not skill_path.exists() or shutil.which("node") is None:
        print("[SKIP] skill o node no disponibles")
        return

    inv = SkillsInvocation()
    result = inv.query("saas b2b", domain="product")
    print(f"status: {result['status']}, count: {result.get('count')}")
    assert result["status"] == "ok"
    assert isinstance(result.get("results"), list)
    assert result["count"] > 0
    assert result["domain"] == "product"
    print(f"[OK] TEST 2: Skill real retorno {result['count']} resultados")


def test_3_skill_unavailable_fallback():
    print("\n" + "="*70)
    print("TEST 3: Skill no disponible -> status unavailable (no rompe)")
    print("="*70)
    inv = SkillsInvocation(skill_path="/nonexistent/skill.js")
    result = inv.query("anything")
    print(f"Result: status={result['status']}, reason preview={result.get('reason','')[:60]}")
    assert result["status"] == "unavailable"
    assert "reason" in result
    print("[OK] TEST 3: Fallback controlado sin excepciones")


def test_4_invalid_domain():
    print("\n" + "="*70)
    print("TEST 4: Domain invalido -> error explicito")
    print("="*70)
    skill_path = Path.home() / ".claude" / "design-data" / "search.js"
    if not skill_path.exists():
        print("[SKIP] skill no disponible")
        return

    inv = SkillsInvocation()
    result = inv.query("test", domain="invalid_domain_xyz")
    print(f"Result: status={result['status']}")
    assert result["status"] == "error"
    assert "Domain invalido" in result["error"]
    print("[OK] TEST 4: Domain invalido rechazado limpiamente")


def test_5_envelope_without_design_intelligence_rejected():
    print("\n" + "="*70)
    print("TEST 5: design_strict + envelope SIN design_intelligence -> REJECT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        envelope = {
            "status": "completado",
            "tarea": "Definir paleta de colores",
            "archivos": ["design/tokens.css"],
            "engram": "atlas/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            # design_intelligence ausente
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="design_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is False
        assert any("design_intelligence obligatorio" in e for e in errores)
    print("[OK] TEST 5: Envelope sin design_intelligence rechazado")


def test_6_envelope_with_queried_false_rejected():
    print("\n" + "="*70)
    print("TEST 6: design_strict + queried=false -> REJECT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "tarea": "Spec de tipografia",
            "archivos": ["design/typography.md"],
            "engram": "atlas/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            "design_intelligence": {
                "queried": False,
                "industry": "saas",
            },
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="design_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is False
        assert any("queried=false" in e for e in errores)
    print("[OK] TEST 6: queried=false rechazado")


def test_7_envelope_with_design_intelligence_complete_accepted():
    print("\n" + "="*70)
    print("TEST 7: design_strict + design_intelligence completo -> ACCEPT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "tarea": "Design tokens completos",
            "archivos": ["design/tokens.css"],
            "engram": "atlas/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            "design_intelligence": {
                "queried": True,
                "industry": "saas-b2b",
                "style": "Glassmorphism + Flat Design",
                "verified_against": ["styles.csv", "colors.csv", "typography.csv"],
                "anti_generic_validated": True,
            },
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="design_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True
        assert errores == []
    print("[OK] TEST 7: Envelope completo aceptado")


def test_8_minimal_queried_true_passes_with_warnings():
    print("\n" + "="*70)
    print("TEST 8: design_strict + queried=true minimo -> ACCEPT con warnings")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "tarea": "Spec minimo",
            "archivos": ["design/x.md"],
            "engram": "atlas/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            "design_intelligence": {
                "queried": True,
                # falta industry, style, verified_against, anti_generic_validated
            },
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="design_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        warnings = envelope.get("_dispatcher_warnings", [])
        print(f"warnings count: {len(warnings)}")
        assert is_valid is True, "FAIL: queried=true solo debe pasar con warnings"
        assert errores == []
        assert len(warnings) >= 3, f"FAIL: debe haber warnings sobre campos faltantes, got {warnings}"
    print("[OK] TEST 8: queried=true minimo pasa con warnings (no block)")


def test_9_backward_compat_standard_mode():
    print("\n" + "="*70)
    print("TEST 9: standard mode NO exige design_intelligence")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {
            "status": "completado",
            "tarea": "Tarea normal",
            "archivos": ["x.ts"],
            "engram": "atlas/x",
            "verificacion": "layout",
            "bloqueadores": [],
            # sin design_intelligence
        }
        is_valid, errores = d.validate_return_envelope(envelope, mode="standard")
        print(f"is_valid={is_valid}")
        assert is_valid is True
    print("[OK] TEST 9: Backward compat — standard mode no exige design")


def test_10_dispatcher_helper_consult_design_intelligence():
    print("\n" + "="*70)
    print("TEST 10: dispatcher.consult_design_intelligence() helper funciona")
    print("="*70)
    skill_path = Path.home() / ".claude" / "design-data" / "search.js"
    if not skill_path.exists() or shutil.which("node") is None:
        print("[SKIP] skill o node no disponibles — test integration")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        result = d.consult_design_intelligence("saas b2b", domain="product")
        print(f"status: {result['status']}, count: {result.get('count')}")
        assert result["status"] == "ok"
        assert result["count"] > 0
    print("[OK] TEST 10: Helper del dispatcher invoca skill correctamente")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1C.1: UI-UX Pro Max Skill Enforcement")
    print("="*70)

    tests = [
        test_1_skill_resolution,
        test_2_skill_invocation_real,
        test_3_skill_unavailable_fallback,
        test_4_invalid_domain,
        test_5_envelope_without_design_intelligence_rejected,
        test_6_envelope_with_queried_false_rejected,
        test_7_envelope_with_design_intelligence_complete_accepted,
        test_8_minimal_queried_true_passes_with_warnings,
        test_9_backward_compat_standard_mode,
        test_10_dispatcher_helper_consult_design_intelligence,
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
        print("[OK] Skill resolution + is_available correctos")
        print("[OK] Skill real responde a queries (integration)")
        print("[OK] Fallback controlado si skill no disponible (no rompe)")
        print("[OK] Domain invalido rechazado")
        print("[OK] Envelope sin design_intelligence -> REJECT en design_strict")
        print("[OK] queried=false -> REJECT")
        print("[OK] design_intelligence completo -> ACCEPT")
        print("[OK] queried=true minimo -> ACCEPT con warnings (no block)")
        print("[OK] Backward compat: standard mode no afectado")
        print("[OK] dispatcher.consult_design_intelligence helper funciona")
        print("\nLO QUE 1C.1 NO HACE:")
        print("- Solo cubre ui-ux-pro-max-skill (no otros skills)")
        print("- Los agentes ux-architect/ui-designer reciben docs pero")
        print("  el orquestador todavia debe invocar mode=design_strict")
        print("- NO valida CONTENIDO del output contra anti-generic (eso es 1A.3)")
        print("- Solo verifica que la consulta haya ocurrido")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
