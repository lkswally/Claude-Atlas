#!/usr/bin/env python3
"""
Validacion real de Bloque 1H.3: Multi-layer QA Visual Fidelity Checker (capa 3)
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
from visual_fidelity_checker import (
    VisualFidelityChecker,
    VERDICT_OK, VERDICT_WARN, VERDICT_FAIL,
    SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
    _hex_to_rgb, _color_distance, _find_closest_color,
)


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_4": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  TESTS
# ============================================================

def test_1_color_helpers():
    print("\n=== TEST 1: Helpers de color (hex->rgb, distancia, closest) ===")
    assert _hex_to_rgb("#FF6B35") == (255, 107, 53)
    assert _hex_to_rgb("FF6B35") == (255, 107, 53)
    assert _hex_to_rgb("#F63") == (255, 102, 51)
    assert _hex_to_rgb("invalid") is None
    # Distancia
    assert _color_distance("#000000", "#FFFFFF") is not None
    assert _color_distance("#FF0000", "#FF0001") < 5
    # Closest
    closest, dist = _find_closest_color("#FF6B35", ["#000000", "#FF6B36", "#FFFFFF"])
    assert closest == "#FF6B36"
    print("[OK]")


def test_2_exact_match_ok():
    print("\n=== TEST 2: Spec exacta -> OK clean ===")
    c = VisualFidelityChecker()
    spec = {
        "declared_palette": {"primary": "#1A1A1A", "accent": "#FF6B35"},
        "declared_typography": {"heading_font": "Syne", "body_font": "Inter"},
        "mood_preset": "brutalist",
        "anti_patterns_obligatorios": ["no-gradient-overuse"],
        "layout_pattern": "hero-asymmetric",
    }
    evidence = {
        "detected_colors": ["#1A1A1A", "#FF6B35", "#FAFAFA"],
        "detected_typography": {"heading_font": "Syne", "body_font": "Inter"},
        "detected_mood": "brutalist",
        "anti_pattern_violations": [],
        "detected_layout_pattern": "hero-asymmetric",
    }
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}, fields={r['summary']['total_fields_checked']}")
    assert r["verdict"] == VERDICT_OK
    assert r["summary"]["issues_count"] == 0
    print("[OK]")


def test_3_primary_color_mismatch_critical():
    print("\n=== TEST 3: Primary color muy distinto -> CRITICAL FAIL ===")
    c = VisualFidelityChecker()
    spec = {"declared_palette": {"primary": "#1A1A1A"}}
    evidence = {"detected_colors": ["#FFFFFF", "#FF0000"]}  # nada cerca de #1A1A1A
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}, issues: {[(i['field'], i['severity']) for i in r['issues']]}")
    assert r["verdict"] == VERDICT_FAIL
    assert any(i["type"] == "palette_primary_mismatch" for i in r["issues"])
    print("[OK]")


def test_4_primary_color_close_match_ok():
    print("\n=== TEST 4: Primary color casi exacto (dentro tolerancia) -> OK ===")
    c = VisualFidelityChecker()
    spec = {"declared_palette": {"primary": "#1A1A1A"}}
    # #1A1A1A es (26,26,26); #1B1B1B es (27,27,27) — distancia ~1.7
    evidence = {"detected_colors": ["#1B1B1B", "#FFFFFF"]}
    r = c.check(spec, evidence)
    assert r["verdict"] == VERDICT_OK
    assert r["summary"]["issues_count"] == 0
    print("[OK]")


def test_5_heading_font_mismatch_critical():
    print("\n=== TEST 5: Heading font diferente -> CRITICAL ===")
    c = VisualFidelityChecker()
    spec = {"declared_typography": {"heading_font": "Syne", "body_font": "Inter"}}
    evidence = {
        "detected_typography": {"heading_font": "Roboto", "body_font": "Inter"},
    }
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}, issues: {[(i['field'], i['severity']) for i in r['issues']]}")
    assert r["verdict"] == VERDICT_FAIL
    assert any(i["type"] == "typography_font_mismatch" and i["field"] == "typography.heading_font" for i in r["issues"])
    print("[OK]")


def test_6_body_font_mismatch_high():
    print("\n=== TEST 6: Body font diferente -> HIGH WARN ===")
    c = VisualFidelityChecker()
    spec = {"declared_typography": {"heading_font": "Syne", "body_font": "Inter"}}
    evidence = {
        "detected_typography": {"heading_font": "Syne", "body_font": "Arial"},
    }
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}")
    assert r["verdict"] == VERDICT_WARN
    assert any(i["field"] == "typography.body_font" and i["severity"] == SEVERITY_HIGH for i in r["issues"])
    print("[OK]")


def test_7_anti_pattern_violation_high():
    print("\n=== TEST 7: Anti-pattern violado por evidence -> HIGH ===")
    c = VisualFidelityChecker()
    spec = {"anti_patterns_obligatorios": ["no-gradient-overuse", "no-shadow-gloss"]}
    evidence = {"anti_pattern_violations": ["gradient overuse detectado en hero"]}
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}, issues: {[(i['type']) for i in r['issues']]}")
    assert r["verdict"] == VERDICT_WARN
    assert any(i["type"] == "anti_pattern_violation" for i in r["issues"])
    print("[OK]")


def test_8_mood_mismatch_high():
    print("\n=== TEST 8: Mood declarado != detectado -> HIGH ===")
    c = VisualFidelityChecker()
    spec = {"mood_preset": "brutalist"}
    evidence = {"detected_mood": "minimal"}
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}")
    assert r["verdict"] == VERDICT_WARN
    assert any(i["type"] == "mood_mismatch" for i in r["issues"])
    print("[OK]")


def test_9_layout_pattern_mismatch_medium():
    print("\n=== TEST 9: Layout pattern diferente -> MEDIUM (no bloquea) ===")
    c = VisualFidelityChecker()
    spec = {"layout_pattern": "hero-asymmetric"}
    evidence = {"detected_layout_pattern": "hero-centered"}
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}, by_severity={r['summary']['by_severity']}")
    assert r["verdict"] == VERDICT_OK  # MEDIUM no bloquea
    assert r["summary"]["by_severity"].get(SEVERITY_MEDIUM, 0) == 1
    print("[OK]")


def test_10_primary_missing_detection_critical():
    print("\n=== TEST 10: Evidence sin detected_colors -> CRITICAL ===")
    c = VisualFidelityChecker()
    spec = {"declared_palette": {"primary": "#1A1A1A"}}
    evidence = {"detected_colors": []}
    r = c.check(spec, evidence)
    assert r["verdict"] == VERDICT_FAIL
    assert any(i["type"] == "palette_no_detected" for i in r["issues"])
    print("[OK]")


def test_11_empty_spec_no_issues():
    print("\n=== TEST 11: Spec vacia -> OK (no hay nada que validar) ===")
    c = VisualFidelityChecker()
    r = c.check({}, {})
    assert r["verdict"] == VERDICT_OK
    print("[OK]")


def test_12_invalid_input_ok():
    print("\n=== TEST 12: Input invalido (no dict) -> OK con note (no rompe) ===")
    c = VisualFidelityChecker()
    r = c.check("not a dict", None)
    assert r["verdict"] == VERDICT_OK
    assert "no son dicts" in r["note"]
    print("[OK]")


def test_13_dispatcher_helper():
    print("\n=== TEST 13: dispatcher.check_visual_fidelity() helper ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        spec = {
            "declared_palette": {"primary": "#000000"},
            "declared_typography": {"heading_font": "Inter"},
        }
        evidence = {
            "detected_colors": ["#FFFFFF"],  # opuesto -> CRITICAL
            "detected_typography": {"heading_font": "Inter"},
        }
        r = d.check_visual_fidelity(spec, evidence)
        assert r["verdict"] == VERDICT_FAIL
    print("[OK]")


def test_14_realistic_scenario_brutalist():
    print("\n=== TEST 14 [INTEGRATION]: Scenario realista — proyecto brutalist con desvios ===")
    c = VisualFidelityChecker()
    spec = {
        "declared_palette": {
            "primary": "#0A0A0A",      # casi negro
            "accent": "#FF3366",       # rojo brutalist
            "background": "#F5F5F0",   # off-white
        },
        "declared_typography": {
            "heading_font": "Space Grotesk",
            "body_font": "JetBrains Mono",
        },
        "mood_preset": "brutalist",
        "anti_patterns_obligatorios": [
            "no-gradient-overuse",
            "no-shadow-gloss",
            "no-corporate-blue",
        ],
        "layout_pattern": "hero-asymmetric-large-type",
    }
    # Agente reporta: 90% match, pero body font esta cambiado y hay un gradient
    evidence = {
        "detected_colors": ["#0B0B0B", "#FF3366", "#F4F4EF", "#888888"],
        "detected_typography": {
            "heading_font": "Space Grotesk",
            "body_font": "Inter",  # cambio no autorizado
        },
        "detected_mood": "brutalist",
        "anti_pattern_violations": ["gradient overuse en CTA section"],
        "detected_layout_pattern": "hero-asymmetric-large-type",
    }
    r = c.check(spec, evidence)
    print(f"verdict={r['verdict']}")
    print(f"  by_severity: {r['summary']['by_severity']}")
    print(f"  issues: {[(i['field'], i['type'], i['severity']) for i in r['issues']]}")
    # No CRITICAL (primary OK), pero HIGH x 2 (body font + anti-pattern)
    assert r["verdict"] == VERDICT_WARN
    assert r["summary"]["by_severity"].get(SEVERITY_HIGH, 0) >= 2
    print("[OK]")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1H.3: Visual Fidelity Checker")
    print("="*70)

    tests = [
        test_1_color_helpers,
        test_2_exact_match_ok,
        test_3_primary_color_mismatch_critical,
        test_4_primary_color_close_match_ok,
        test_5_heading_font_mismatch_critical,
        test_6_body_font_mismatch_high,
        test_7_anti_pattern_violation_high,
        test_8_mood_mismatch_high,
        test_9_layout_pattern_mismatch_medium,
        test_10_primary_missing_detection_critical,
        test_11_empty_spec_no_issues,
        test_12_invalid_input_ok,
        test_13_dispatcher_helper,
        test_14_realistic_scenario_brutalist,
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
        print("\nLO QUE 1H.3 NO HACE:")
        print("- NO analiza imagenes propio — el agente Claude provee la evidence")
        print("- NO pixel-perfect — usa tolerancias para color matching")
        print("- NO valida microcopy, spacing exacto, icon style")
        print("- Evidence-collector / reality-checker debe leer su md y consultar")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
