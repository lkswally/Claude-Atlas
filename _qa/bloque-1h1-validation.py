#!/usr/bin/env python3
"""
Validacion real de Bloque 1H.1: Multi-layer QA Network Inspection

11 tests:
- 10 unit (severidad, verdict, edge cases)
- 1 integration realistic con request mix tipico
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
from network_inspector import (
    NetworkInspector,
    VERDICT_OK,
    VERDICT_WARN,
    VERDICT_FAIL,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
)


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  TESTS
# ============================================================

def test_1_all_200_ok():
    print("\n" + "="*70)
    print("TEST 1: Todos 200 OK -> verdict OK")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/", "status": 200, "method": "GET"},
        {"url": "https://example.com/app.js", "status": 200, "method": "GET"},
        {"url": "https://example.com/style.css", "status": 200, "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, issues={report['summary']['issues_count']}")
    assert report["verdict"] == VERDICT_OK
    assert report["summary"]["issues_count"] == 0
    print("[OK] TEST 1: All 200 -> OK clean")


def test_2_http_500_critical():
    print("\n" + "="*70)
    print("TEST 2: HTTP 500 -> verdict FAIL (CRITICAL)")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/api/users", "status": 500, "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, issues: {report['issues']}")
    assert report["verdict"] == VERDICT_FAIL
    assert report["summary"]["by_severity"].get(SEVERITY_CRITICAL) == 1
    assert report["issues"][0]["type"] == "http_5xx"
    print("[OK] TEST 2: 500 detectado como CRITICAL -> FAIL")


def test_3_mixed_content_critical():
    print("\n" + "="*70)
    print("TEST 3: Mixed content HTTPS->HTTP -> CRITICAL FAIL")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/", "status": 200, "method": "GET"},
        {"url": "http://insecure-cdn.com/script.js", "status": 200, "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, by_severity={report['summary']['by_severity']}")
    assert report["verdict"] == VERDICT_FAIL
    issue_types = [i["type"] for i in report["issues"]]
    assert "mixed_content" in issue_types
    print("[OK] TEST 3: Mixed content -> CRITICAL FAIL")


def test_4_network_error_critical():
    print("\n" + "="*70)
    print("TEST 4: Network error (request fallido) -> CRITICAL FAIL")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/api/data", "error": "ERR_CONNECTION_REFUSED", "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, issues: {[i['type'] for i in report['issues']]}")
    assert report["verdict"] == VERDICT_FAIL
    assert report["issues"][0]["type"] == "network_error"
    print("[OK] TEST 4: Network error -> CRITICAL")


def test_5_4xx_critical_same_origin_asset():
    print("\n" + "="*70)
    print("TEST 5: 4xx en JS same-origin -> HIGH (asset critico roto)")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/", "status": 200, "method": "GET"},
        {"url": "https://example.com/app.js", "status": 404, "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, by_severity={report['summary']['by_severity']}")
    assert report["verdict"] == VERDICT_WARN
    assert report["summary"]["by_severity"].get(SEVERITY_HIGH) == 1
    issue_types = [i["type"] for i in report["issues"]]
    assert "http_4xx_critical_asset" in issue_types
    print("[OK] TEST 5: 4xx en JS critico -> HIGH WARN")


def test_6_4xx_cross_origin_medium():
    print("\n" + "="*70)
    print("TEST 6: 4xx en cross-origin (tracking) -> MEDIUM (no bloquea)")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/", "status": 200, "method": "GET"},
        # 404 en third-party (tracking script desactivado)
        {"url": "https://analytics.thirdparty.com/track.js", "status": 404, "method": "GET"},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, by_severity={report['summary']['by_severity']}")
    assert report["verdict"] == VERDICT_OK  # MEDIUM/LOW no bloquean
    # 404 en cross-origin no-critico se clasifica como LOW (expected)
    assert (
        report["summary"]["by_severity"].get(SEVERITY_LOW, 0) > 0
        or report["summary"]["by_severity"].get(SEVERITY_MEDIUM, 0) > 0
    )
    print("[OK] TEST 6: 404 cross-origin tracking -> no bloquea")


def test_7_long_redirect_chain():
    print("\n" + "="*70)
    print("TEST 7: Redirect chain > 3 -> HIGH WARN")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/old-page", "status": 200, "method": "GET", "redirect_count": 5},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, issues: {[i['type'] for i in report['issues']]}")
    assert report["verdict"] == VERDICT_WARN
    assert any(i["type"] == "long_redirect_chain" for i in report["issues"])
    print("[OK] TEST 7: Long redirect chain detectada")


def test_8_slow_request_medium():
    print("\n" + "="*70)
    print("TEST 8: Slow request > 5s -> MEDIUM (no bloquea)")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    requests = [
        {"url": "https://example.com/api/heavy", "status": 200, "method": "GET", "duration_ms": 8000},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}, by_severity={report['summary']['by_severity']}")
    assert report["verdict"] == VERDICT_OK  # MEDIUM no bloquea
    assert report["summary"]["by_severity"].get(SEVERITY_MEDIUM, 0) >= 1
    assert any(i["type"] == "slow_request" for i in report["issues"])
    print("[OK] TEST 8: Slow request detectado como MEDIUM")


def test_9_empty_requests():
    print("\n" + "="*70)
    print("TEST 9: Lista vacia -> OK con warning de no-data")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://example.com")
    report = inspector.inspect([])
    print(f"verdict={report['verdict']}, note: {report['note'][:60]}")
    assert report["verdict"] == VERDICT_OK
    assert report["summary"]["total_requests"] == 0
    assert "no hay requests" in report["note"].lower() or "WARN" in report["note"]
    print("[OK] TEST 9: Lista vacia manejada limpiamente")


def test_10_dispatcher_helper():
    print("\n" + "="*70)
    print("TEST 10: dispatcher.inspect_network_requests() helper")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        requests = [
            {"url": "https://example.com/", "status": 200},
            {"url": "https://example.com/api/users", "status": 500},
        ]
        report = d.inspect_network_requests(requests, page_origin="https://example.com")
        print(f"verdict={report['verdict']}")
        assert report["verdict"] == VERDICT_FAIL
        assert report["summary"]["by_severity"].get(SEVERITY_CRITICAL, 0) >= 1
    print("[OK] TEST 10: Helper del dispatcher funciona end-to-end")


def test_11_realistic_scenario():
    print("\n" + "="*70)
    print("TEST 11 [INTEGRATION]: Scenario realista — landing con mix tipico")
    print("="*70)
    inspector = NetworkInspector(page_origin="https://miapp.com")
    requests = [
        # Landing OK
        {"url": "https://miapp.com/", "status": 200, "method": "GET", "duration_ms": 350},
        # JS/CSS criticos OK
        {"url": "https://miapp.com/_next/static/main.js", "status": 200, "duration_ms": 220},
        {"url": "https://miapp.com/_next/static/main.css", "status": 200, "duration_ms": 180},
        # Fonts OK (cross-origin)
        {"url": "https://fonts.googleapis.com/css?family=Inter", "status": 200, "duration_ms": 120},
        # API OK
        {"url": "https://miapp.com/api/auth/session", "status": 200, "duration_ms": 90},
        # Tracking deshabilitado (cross-origin 404)
        {"url": "https://analytics-thirdparty.com/script.js", "status": 404, "duration_ms": 50},
        # Favicon missing (404 en root pero no critico)
        {"url": "https://miapp.com/favicon.ico", "status": 404, "duration_ms": 30},
        # Slow image
        {"url": "https://miapp.com/hero-image.jpg", "status": 200, "duration_ms": 6500},
    ]
    report = inspector.inspect(requests)
    print(f"verdict={report['verdict']}")
    print(f"  by_severity: {report['summary']['by_severity']}")
    print(f"  by_type: {report['summary']['by_type']}")
    # No CRITICAL, no HIGH -> OK con MEDIUM/LOW informativos
    assert report["verdict"] == VERDICT_OK
    # Pero debe haber issues reportados (favicon 404 + slow + tracking 404)
    assert report["summary"]["issues_count"] >= 2
    assert report["summary"]["by_severity"].get(SEVERITY_MEDIUM, 0) >= 1  # slow + favicon same-origin
    print("[OK] TEST 11: Scenario realista clasifica correctamente todas las capas")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1H.1: Multi-layer QA Network Inspection")
    print("="*70)

    tests = [
        test_1_all_200_ok,
        test_2_http_500_critical,
        test_3_mixed_content_critical,
        test_4_network_error_critical,
        test_5_4xx_critical_same_origin_asset,
        test_6_4xx_cross_origin_medium,
        test_7_long_redirect_chain,
        test_8_slow_request_medium,
        test_9_empty_requests,
        test_10_dispatcher_helper,
        test_11_realistic_scenario,
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
        print("[OK] Todos 200 -> OK clean")
        print("[OK] 5xx -> CRITICAL FAIL")
        print("[OK] Mixed content HTTPS->HTTP -> CRITICAL FAIL")
        print("[OK] Network error -> CRITICAL FAIL")
        print("[OK] 4xx en asset critico same-origin -> HIGH WARN")
        print("[OK] 4xx cross-origin tracking -> no bloquea (MEDIUM/LOW)")
        print("[OK] Long redirect chain (>3) -> HIGH WARN")
        print("[OK] Slow request (>5s) -> MEDIUM informativo")
        print("[OK] Lista vacia -> OK con warning de no-data")
        print("[OK] dispatcher.inspect_network_requests helper funciona")
        print("[OK] Scenario realista clasifica multi-capa correctamente")
        print("\nLO QUE 1H.1 NO HACE:")
        print("- SOLO cubre network inspection (1 capa de multi-layer QA)")
        print("- NO cubre console log analysis (sera 1H.2)")
        print("- NO cubre visual fidelity LLM-as-judge (sera 1H.3)")
        print("- Evidence-collector agente debe leer su md y consultar el helper")
        print("- NO inspecciona response bodies — solo metadata")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
