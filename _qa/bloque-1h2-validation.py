#!/usr/bin/env python3
"""
Validacion real de Bloque 1H.2: Multi-layer QA Console Log Analysis (capa 2)
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
from console_log_analyzer import (
    ConsoleLogAnalyzer,
    VERDICT_OK, VERDICT_WARN, VERDICT_FAIL,
    SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW,
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

def test_1_no_messages_ok():
    print("\n=== TEST 1: Sin mensajes -> OK con warn de no-data ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([])
    assert r["verdict"] == VERDICT_OK
    assert r["summary"]["total_messages"] == 0
    print("[OK]")


def test_2_uncaught_critical():
    print("\n=== TEST 2: Uncaught exception -> CRITICAL FAIL ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error", "text": "Uncaught TypeError: foo is undefined",
         "location": {"url": "https://app.com/main.js", "lineNumber": 42}},
    ])
    assert r["verdict"] == VERDICT_FAIL
    assert r["issues"][0]["severity"] == SEVERITY_CRITICAL
    assert r["issues"][0]["type"] == "uncaught_exception"
    print("[OK]")


def test_3_cors_critical():
    print("\n=== TEST 3: CORS error -> CRITICAL ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error",
         "text": "Access-Control-Allow-Origin header missing on https://api.com",
         "location": {"url": "https://app.com/main.js"}},
    ])
    assert r["verdict"] == VERDICT_FAIL
    assert r["issues"][0]["type"] == "cors_error"
    print("[OK]")


def test_4_csp_violation():
    print("\n=== TEST 4: CSP violation -> CRITICAL ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error",
         "text": "Refused to execute inline script: Content Security Policy directive",
         "location": {"url": "https://app.com/"}},
    ])
    assert r["verdict"] == VERDICT_FAIL
    assert r["issues"][0]["type"] == "csp_violation"
    print("[OK]")


def test_5_hydration_mismatch():
    print("\n=== TEST 5: React hydration mismatch -> CRITICAL ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error",
         "text": "Hydration failed because the initial UI does not match what was rendered on the server",
         "location": {"url": "https://app.com/_next/static/chunks/main.js"}},
    ])
    assert r["verdict"] == VERDICT_FAIL
    assert r["issues"][0]["type"] == "hydration_mismatch"
    print("[OK]")


def test_6_null_access():
    print("\n=== TEST 6: Cannot read properties of null/undefined -> CRITICAL ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error",
         "text": "TypeError: Cannot read properties of undefined (reading 'name')",
         "location": {"url": "https://app.com/app.js", "lineNumber": 17}},
    ])
    assert r["verdict"] == VERDICT_FAIL
    assert r["issues"][0]["type"] == "null_undefined_access"
    print("[OK]")


def test_7_react_key_warning_high():
    print("\n=== TEST 7: React 'missing key' warning -> HIGH WARN ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "warning",
         "text": "Warning: Each child in a list should have a unique \"key\" prop.",
         "location": {"url": "https://app.com/UserList.js", "lineNumber": 12}},
    ])
    assert r["verdict"] == VERDICT_WARN
    assert r["issues"][0]["severity"] == SEVERITY_HIGH
    assert r["issues"][0]["type"] == "react_missing_key"
    print("[OK]")


def test_8_generic_console_error_high():
    print("\n=== TEST 8: console.error generico -> HIGH ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "error",
         "text": "Failed to load user preferences",
         "location": {"url": "https://app.com/prefs.js"}},
    ])
    assert r["verdict"] == VERDICT_WARN
    assert r["issues"][0]["severity"] == SEVERITY_HIGH
    assert r["issues"][0]["type"] == "console_error_generic"
    print("[OK]")


def test_9_third_party_degraded_to_low():
    print("\n=== TEST 9: Error en third-party origin -> degradado a LOW ===")
    a = ConsoleLogAnalyzer(third_party_origin_patterns=[r"analytics-thirdparty\.com"])
    r = a.analyze([
        {"type": "error",
         "text": "Uncaught TypeError: tracker is undefined",
         "location": {"url": "https://analytics-thirdparty.com/track.js"}},
    ])
    # CRITICAL pattern matchea, pero al ser third-party se degrada a LOW
    assert r["verdict"] == VERDICT_OK
    issue = r["issues"][0]
    assert issue["severity"] == SEVERITY_LOW
    assert issue["third_party_degraded"] is True
    print("[OK]")


def test_10_low_noise_ignored():
    print("\n=== TEST 10: Noise comun (DevTools, source maps) -> ignorado ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "info", "text": "Download the React DevTools for a better experience",
         "location": {"url": ""}},
        {"type": "warning", "text": "Source map not found for chunk.js",
         "location": {"url": "https://app.com/chunk.js"}},
        {"type": "log", "text": "DevTools listening on ws://...",
         "location": {"url": ""}},
    ])
    # Ninguno debe contar como issue
    assert r["summary"]["issues_count"] == 0
    assert r["verdict"] == VERDICT_OK
    print("[OK]")


def test_11_console_warn_medium():
    print("\n=== TEST 11: console.warn generico -> MEDIUM informativo ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "warning", "text": "Performance: render took 250ms",
         "location": {"url": "https://app.com/perf.js"}},
    ])
    assert r["verdict"] == VERDICT_OK  # MEDIUM no bloquea
    assert r["summary"]["by_severity"].get(SEVERITY_MEDIUM, 0) == 1
    print("[OK]")


def test_12_console_log_low():
    print("\n=== TEST 12: console.log -> LOW informativo ===")
    a = ConsoleLogAnalyzer()
    r = a.analyze([
        {"type": "log", "text": "User logged in: user123",
         "location": {"url": "https://app.com/auth.js"}},
    ])
    assert r["verdict"] == VERDICT_OK
    assert r["summary"]["by_severity"].get(SEVERITY_LOW, 0) == 1
    print("[OK]")


def test_13_dispatcher_helper():
    print("\n=== TEST 13: dispatcher.analyze_console_messages() helper ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        r = d.analyze_console_messages(
            messages=[
                {"type": "log", "text": "init complete", "location": {"url": "https://app.com/"}},
                {"type": "error", "text": "Uncaught ReferenceError: foo", "location": {"url": "https://app.com/main.js"}},
            ],
        )
        assert r["verdict"] == VERDICT_FAIL
        assert r["summary"]["by_severity"].get(SEVERITY_CRITICAL, 0) >= 1
    print("[OK]")


def test_14_realistic_mix():
    print("\n=== TEST 14 [INTEGRATION]: Mix realista de console messages ===")
    a = ConsoleLogAnalyzer(third_party_origin_patterns=[r"analytics", r"hotjar", r"sentry\.io"])
    messages = [
        # Normal app logs (LOW)
        {"type": "info", "text": "App initialized v1.2.3", "location": {"url": "https://miapp.com/init.js"}},
        {"type": "log", "text": "User opened settings", "location": {"url": "https://miapp.com/app.js"}},
        # Noise (ignorado)
        {"type": "info", "text": "Download the React DevTools for a better experience", "location": {"url": ""}},
        # React warning HIGH
        {"type": "warning", "text": "Warning: Each child in a list should have a unique \"key\" prop", "location": {"url": "https://miapp.com/UserList.js"}},
        # Third-party error (degradado a LOW)
        {"type": "error", "text": "Uncaught TypeError in tracking", "location": {"url": "https://analytics.com/script.js"}},
        # Performance warning MEDIUM
        {"type": "warning", "text": "Slow component render", "location": {"url": "https://miapp.com/Chart.js"}},
    ]
    r = a.analyze(messages)
    print(f"verdict={r['verdict']}, by_severity={r['summary']['by_severity']}")
    # Sin CRITICAL real (el de third-party fue degradado), 1 HIGH -> WARN
    assert r["verdict"] == VERDICT_WARN
    assert r["summary"]["by_severity"].get(SEVERITY_HIGH, 0) == 1
    # Verificar que el third-party esta degradado
    third_issues = [i for i in r["issues"] if i.get("third_party_degraded")]
    assert len(third_issues) == 1
    assert third_issues[0]["severity"] == SEVERITY_LOW
    print("[OK]")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1H.2: Console Log Analysis")
    print("="*70)

    tests = [
        test_1_no_messages_ok,
        test_2_uncaught_critical,
        test_3_cors_critical,
        test_4_csp_violation,
        test_5_hydration_mismatch,
        test_6_null_access,
        test_7_react_key_warning_high,
        test_8_generic_console_error_high,
        test_9_third_party_degraded_to_low,
        test_10_low_noise_ignored,
        test_11_console_warn_medium,
        test_12_console_log_low,
        test_13_dispatcher_helper,
        test_14_realistic_mix,
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
        print("\nLO QUE 1H.2 NO HACE:")
        print("- Solo cubre console messages (1 capa de multi-layer QA)")
        print("- NO ejecuta codigo de los mensajes — solo analiza texto")
        print("- NO valida call stacks completos")
        print("- NO cubre visual fidelity LLM-as-judge (sera 1H.3)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
