#!/usr/bin/env python3
"""
Validacion real de Bloque 1J.1: Visual Evidence Independent Verification

10 tests:
- 9 unit (con mock + skill real cuando disponible)
- 1 integration con skill real (auto-skip si no disponible)
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_2": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  TESTS
# ============================================================

def test_1_no_design_intelligence_unverifiable():
    print("\n=== TEST 1: Envelope sin design_intelligence -> unverifiable ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"status": "completado", "tarea": "x", "engram": "y"}
        r = d.verify_design_intelligence_real(envelope)
        assert r["verdict"] == "unverifiable"
        assert "responsabilidad de validate_return_envelope" in r["note"].lower() or "design_intelligence ausente" in r["note"].lower()
        print("[OK]")


def test_2_queried_false_unverifiable():
    print("\n=== TEST 2: queried=false -> unverifiable (nada que reverificar) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {"queried": False, "industry": "saas"}}
        r = d.verify_design_intelligence_real(envelope)
        assert r["verdict"] == "unverifiable"
        assert "queried=false" in r["note"].lower()
        print("[OK]")


def test_3_no_industry_declared_unverifiable():
    print("\n=== TEST 3: queried=true pero sin industry -> unverifiable ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {"queried": True}}
        r = d.verify_design_intelligence_real(envelope)
        assert r["verdict"] == "unverifiable"
        print("[OK]")


def test_4_skill_unavailable_unverifiable():
    print("\n=== TEST 4: Skill no disponible -> unverifiable (no rompe) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {"queried": True, "industry": "saas-b2b", "style": "Glassmorphism"}}

        # Mock SkillsInvocation.is_available para retornar False
        from skills_invocation import SkillsInvocation
        with patch.object(SkillsInvocation, "is_available", return_value=False):
            r = d.verify_design_intelligence_real(envelope)
        assert r["verdict"] == "unverifiable"
        assert "no disponible" in r["note"].lower()
        print("[OK]")


def test_5_industry_inventada_mismatch_critical():
    print("\n=== TEST 5: Industria inexistente en catalogo -> mismatch CRITICAL ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {
            "queried": True,
            "industry": "inexistente-xyz-no-real",
            "style": "Glassmorphism",
        }}

        # Mock skill: retorna count=0 para industria inexistente
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {"status": "ok", "results": [], "count": 0, "domain": domain, "query": q}
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            r = d.verify_design_intelligence_real(envelope)
        print(f"verdict={r['verdict']}, discrepancies={len(r['discrepancies'])}")
        assert r["verdict"] == "mismatch"
        assert any(d.get("severity") == "CRITICAL" for d in r["discrepancies"])
        print("[OK]")


def test_6_style_inventado_mismatch_high():
    print("\n=== TEST 6: Style declarado NO en results del skill -> mismatch HIGH ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {
            "queried": True,
            "industry": "saas-b2b",
            "style": "Estilo-Inventado-Que-No-Existe",
        }}

        # Mock skill: retorna resultados con OTROS styles
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [
                    {"Product Type": "SaaS (General)", "Primary Style Recommendation": "Glassmorphism + Flat Design"},
                    {"Product Type": "Micro SaaS", "Primary Style Recommendation": "Flat Design + Vibrant"},
                ],
                "count": 2,
                "domain": "product",
                "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            r = d.verify_design_intelligence_real(envelope)
        print(f"verdict={r['verdict']}")
        assert r["verdict"] == "mismatch"
        style_disc = [d for d in r["discrepancies"] if d.get("field") == "design_intelligence.style"]
        assert len(style_disc) == 1
        assert style_disc[0]["severity"] == "HIGH"
        assert "available_styles" in style_disc[0]
        print("[OK]")


def test_7_style_correcto_match():
    print("\n=== TEST 7: Style declarado SI esta en results -> match ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {
            "queried": True,
            "industry": "saas-b2b",
            "style": "Glassmorphism + Flat Design",
        }}

        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [
                    {"Product Type": "SaaS (General)", "Primary Style Recommendation": "Glassmorphism + Flat Design"},
                ],
                "count": 1,
                "domain": "product",
                "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            r = d.verify_design_intelligence_real(envelope)
        print(f"verdict={r['verdict']}, checks={len(r['checks'])}")
        assert r["verdict"] == "match"
        assert r["discrepancies"] == []
        print("[OK]")


def test_8_style_partial_match():
    print("\n=== TEST 8: Style declarado parcial (token) matchea aunque skill diga otro nombre ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Agente dice solo "Glassmorphism", skill dice "Glassmorphism + Flat Design"
        envelope = {"design_intelligence": {
            "queried": True,
            "industry": "saas",
            "style": "Glassmorphism",
        }}
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [
                    {"Product Type": "SaaS", "Primary Style Recommendation": "Glassmorphism + Flat Design"},
                ],
                "count": 1,
                "domain": "product",
                "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            r = d.verify_design_intelligence_real(envelope)
        assert r["verdict"] == "match"  # match parcial OK
        print("[OK]")


def test_9_verified_against_invalid_csv_low():
    print("\n=== TEST 9: verified_against con CSV invalido -> LOW warning ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        envelope = {"design_intelligence": {
            "queried": True,
            "industry": "saas",
            "style": "Glassmorphism + Flat Design",
            "verified_against": ["styles.csv", "fake.csv", "colors.csv"],
        }}
        from skills_invocation import SkillsInvocation
        def mock_query(self, q, domain=None):
            return {
                "status": "ok",
                "results": [{"Product Type": "SaaS", "Primary Style Recommendation": "Glassmorphism + Flat Design"}],
                "count": 1, "domain": "product", "query": q,
            }
        with patch.object(SkillsInvocation, "is_available", return_value=True), \
             patch.object(SkillsInvocation, "query", new=mock_query):
            r = d.verify_design_intelligence_real(envelope)
        # No es mismatch porque LOW no es CRITICAL/HIGH, pero hay warning en checks
        assert r["verdict"] == "match"
        csv_check = [c for c in r["checks"] if c.get("field") == "design_intelligence.verified_against"]
        assert len(csv_check) == 1
        assert csv_check[0]["severity"] == "LOW"
        assert "fake.csv" in csv_check[0]["details"]
        print("[OK]")


def test_10_integration_skill_real():
    print("\n=== TEST 10 [INTEGRATION]: Skill real verifica industria 'saas b2b' ===")
    skill_path = Path.home() / ".claude" / "design-data" / "search.js"
    if not skill_path.exists() or shutil.which("node") is None:
        print("[SKIP] skill o node no disponibles")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Caso 1: agente honesto declara industria/style real
        envelope_honest = {"design_intelligence": {
            "queried": True,
            "industry": "saas b2b",
            "style": "Glassmorphism + Flat Design",  # styles que vimos en exploracion previa
        }}
        r1 = d.verify_design_intelligence_real(envelope_honest)
        print(f"Honest verdict: {r1['verdict']}, count: {r1['skill_query_result']['count'] if r1.get('skill_query_result') else None}")
        # Esperamos match o al menos no mismatch CRITICAL (industry encontrada)
        assert r1["verdict"] in ("match", "mismatch")  # match si style coincide, sino HIGH mismatch

        # Caso 2: agente miente declarando industria inexistente
        envelope_lying = {"design_intelligence": {
            "queried": True,
            "industry": "industria-completamente-falsa-zzzzz",
            "style": "Glassmorphism",
        }}
        r2 = d.verify_design_intelligence_real(envelope_lying)
        print(f"Lying verdict: {r2['verdict']}, count: {r2['skill_query_result']['count'] if r2.get('skill_query_result') else None}")
        # Skill puede o no encontrar resultados — pero si count=0 -> mismatch CRITICAL
        if r2.get("skill_query_result", {}).get("count", 0) == 0:
            assert r2["verdict"] == "mismatch"
            assert any(d.get("severity") == "CRITICAL" for d in r2["discrepancies"])
        print("[OK] Skill real verifica industria honesta vs inventada")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1J.1: Visual Evidence Independent Verification")
    print("="*70)

    tests = [
        test_1_no_design_intelligence_unverifiable,
        test_2_queried_false_unverifiable,
        test_3_no_industry_declared_unverifiable,
        test_4_skill_unavailable_unverifiable,
        test_5_industry_inventada_mismatch_critical,
        test_6_style_inventado_mismatch_high,
        test_7_style_correcto_match,
        test_8_style_partial_match,
        test_9_verified_against_invalid_csv_low,
        test_10_integration_skill_real,
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
        print("\nLO QUE 1J.1 NO HACE:")
        print("- NO valida que el agente realmente vio el screenshot — solo")
        print("  re-invoca skill con la industria/style declarados")
        print("- NO compara visual evidence (eso es 1H.3) — compara la declaracion")
        print("  de design_intelligence contra el output real del skill")
        print("- Skill unavailable -> unverifiable (no rompe pero no garantiza)")
        print("- Match parcial por tokens permite que estilos compuestos coincidan")
        print("- Honestidad sobre 'verified_against' es LOW (informativo, no block)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
