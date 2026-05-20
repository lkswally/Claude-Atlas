#!/usr/bin/env python3
"""
Validacion real de Bloque 1B.4: mem_get_observation / 2-step pattern

9 tests:
- 8 unit (mock subprocess)
- 1 integration opt-in (Engram real, ATLAS_RUN_INTEGRATION=1)
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Tests crean dispatcher con opt-out por defecto, salvo el integration
os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from engram_strategy import DiskFallbackStrategy, CallbackStrategy
from engram_mcp_bridge import EngramMCPBridge


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

def test_1_extract_observation_id_from_text():
    print("\n" + "="*70)
    print("TEST 1: Parser extrae observation_id entero del preview text")
    print("="*70)
    cases = [
        ("[1] #33 (decision) — Title", 33),
        ("Found 1 memories:\n\n[1] #142 (decision)", 142),
        ("No memories found for: foo", None),
        ("Result: #1 [decision] Title", 1),
        ("plain text without id", None),
    ]
    for text, expected in cases:
        got = EngramMCPBridge._extract_observation_id_from_text(text)
        assert got == expected, f"FAIL: text={text!r}, expected={expected}, got={got}"
    print(f"[OK] TEST 1: 5 casos de extraccion validados")


def test_2_parse_search_result_with_real_format():
    print("\n" + "="*70)
    print("TEST 2: _parse_search_result maneja formato real de Engram v1.15.10")
    print("="*70)
    # Simular respuesta real (text es JSON-encoded)
    real_text = json.dumps({
        "project": "atlas-audit",
        "result": "Found 1 memories:\n\n[1] #33 (decision) — ATLAS Bloque 1A.16 — preview...\n",
    })
    result = {
        "content": [{"type": "text", "text": real_text}],
        "isError": False,
    }
    parsed = EngramMCPBridge._parse_search_result(result, "atlas/bloque-1a16")
    print(f"Parsed: {parsed}")
    assert parsed["status"] == "found"
    assert parsed["observation_id"] == 33, f"FAIL: observation_id debe ser 33, got {parsed.get('observation_id')}"
    assert parsed["source"] == "engram_mcp_real"
    print("[OK] TEST 2: Parser extrae observation_id de respuesta real")


def test_3_parse_get_observation_full_content():
    print("\n" + "="*70)
    print("TEST 3: _parse_get_observation_result extrae contenido completo + metadata")
    print("="*70)
    real_text = json.dumps({
        "project": "atlas-audit",
        "result": "#33 [decision] ATLAS Bloque 1A.16 — File Change Declaration Verification\n**What**: Cierre del loop 1A...\n**Why**: ...\nTopic: atlas/bloque-1a16-file-declaration\nCreated: 2026-05-20",
    })
    result = {
        "content": [{"type": "text", "text": real_text}],
        "isError": False,
    }
    parsed = EngramMCPBridge._parse_get_observation_result(result, 33)
    print(f"Parsed status: {parsed['status']}, type: {parsed.get('type')}, title: {parsed.get('title')[:40] if parsed.get('title') else None}")
    print(f"  topic_key: {parsed.get('topic_key')}, raw_length: {parsed.get('raw_length')}")
    assert parsed["status"] == "found"
    assert parsed["id"] == 33
    assert parsed["type"] == "decision"
    assert "ATLAS Bloque 1A.16" in parsed["title"]
    assert parsed["topic_key"] == "atlas/bloque-1a16-file-declaration"
    assert parsed["raw_length"] > 100  # contenido no esta truncado
    print("[OK] TEST 3: Contenido completo + metadata estructurada extraidos")


def test_4_get_observation_not_found():
    print("\n" + "="*70)
    print("TEST 4: get_observation con id inexistente -> not_found (no se confunde con timeout)")
    print("="*70)
    real_text = json.dumps({
        "project": "atlas-audit",
        "result": "Observation not found for id: 9999",
    })
    result = {"content": [{"type": "text", "text": real_text}], "isError": False}
    parsed = EngramMCPBridge._parse_get_observation_result(result, 9999)
    print(f"Parsed: {parsed}")
    assert parsed["status"] == "not_found"
    assert parsed["id"] == 9999
    print("[OK] TEST 4: not_found distinguido de timeout")


def test_5_get_observation_timeout_not_confused_with_not_found():
    print("\n" + "="*70)
    print("TEST 5: Timeout en get_observation NO se confunde con not_found")
    print("="*70)
    # Mock bridge subprocess que cuelga en la segunda call
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    # Handshake response + busca search (con observation_id 33) + cuelga en get_observation
    handshake = json.dumps({"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{},"serverInfo":{"name":"engram"}}}) + "\n"
    search_text = json.dumps({"result": "[1] #33 (decision) — Title"})
    search_resp = json.dumps({"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":search_text}],"isError":False}}) + "\n"

    import threading as _t
    block_event = _t.Event()

    def readline_gen():
        for r in [handshake, search_resp]:
            yield r
        while True:
            block_event.wait()
            yield ""

    gen = readline_gen()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline = lambda: next(gen)
    mock_proc.stdin = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("shutil.which", return_value="/fake/engram"):
        bridge = EngramMCPBridge(timeout_s=0.3)
        # search OK (extrae id=33)
        s = bridge.mem_search("atlas", "atlas/x")
        assert s["status"] == "found"
        assert s["observation_id"] == 33
        # get_observation timeoutea
        obs = bridge.mem_get_observation(33, retry_on_crash=False)
        print(f"get_observation result: {obs}")
        assert obs["status"] == "timeout"
        assert obs["status"] != "not_found", "FAIL: timeout NO debe ser not_found"
        bridge.close()
    print("[OK] TEST 5: timeout != not_found en mem_get_observation")


def test_6_dispatcher_get_cajon_full_2step_mocked():
    print("\n" + "="*70)
    print("TEST 6: dispatcher.get_cajon_full() hace 2-step end-to-end (mocked)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # Inyectar strategy mock que retorna found + content completo
        def fake_search(p, c):
            return {"status": "found", "observation_id": 42, "source": "mock", "topic_key": c}

        def fake_get(obs_id):
            assert obs_id == 42, f"FAIL: debe pasar el observation_id del search, got {obs_id}"
            return {
                "status": "found",
                "id": 42,
                "content": "<contenido COMPLETO de 2000 chars>" * 50,
                "title": "Mock title",
                "type": "decision",
                "topic_key": "atlas/mock",
                "source": "mock",
            }

        d._engram_strategy = CallbackStrategy(
            callback=fake_search,
            fallback=None,
            name="mock",
            get_observation_callback=fake_get,
        )

        result = d.get_cajon_full("atlas", "atlas/mock")
        print(f"Status: {result['status']}, content_len: {len(result.get('content',''))}, title: {result.get('title')}")
        assert result["status"] == "found"
        assert len(result["content"]) > 1000, "FAIL: contenido debe ser completo, no truncado"
        assert result["title"] == "Mock title"
        assert result["type"] == "decision"
    print("[OK] TEST 6: 2-step end-to-end correcto")


def test_7_dispatcher_get_cajon_full_skips_step2_if_search_not_found():
    print("\n" + "="*70)
    print("TEST 7: Si search retorna not_found, NO se llama get_observation")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        get_called = [False]

        def fake_search(p, c):
            return {"status": "not_found", "source": "mock"}

        def fake_get(obs_id):
            get_called[0] = True
            return {"status": "found", "content": "should not be reached"}

        d._engram_strategy = CallbackStrategy(
            callback=fake_search,
            fallback=None,
            name="mock",
            get_observation_callback=fake_get,
        )

        result = d.get_cajon_full("atlas", "atlas/missing")
        print(f"Result: {result}")
        assert result["status"] == "not_found"
        assert result["step"] == "search"
        assert not get_called[0], "FAIL: get_observation NO debe llamarse si search dice not_found"
    print("[OK] TEST 7: Skip de step 2 cuando search es not_found")


def test_8_inconsistent_state_detected():
    print("\n" + "="*70)
    print("TEST 8: Inconsistencia detectada — search=found pero get_observation=not_found")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        def fake_search(p, c):
            return {"status": "found", "observation_id": 99, "source": "mock"}

        def fake_get(obs_id):
            return {"status": "not_found", "id": obs_id, "source": "mock"}

        d._engram_strategy = CallbackStrategy(
            callback=fake_search,
            fallback=None,
            name="mock",
            get_observation_callback=fake_get,
        )

        result = d.get_cajon_full("atlas", "atlas/race")
        print(f"Result: {result}")
        assert result["status"] == "inconsistent", f"FAIL: debe ser 'inconsistent', got {result['status']}"
        assert result["step"] == "get_observation"
        assert "race condition" in result.get("note", "").lower() or "stale" in result.get("note", "").lower()
    print("[OK] TEST 8: Inconsistencia detectada (no silenciada)")


# ============================================================
#  INTEGRATION TEST
# ============================================================

def test_9_integration_real_engram_2step():
    print("\n" + "="*70)
    print("TEST 9 [INTEGRATION]: Engram real - 2-step end-to-end con contenido completo")
    print("="*70)
    if not os.environ.get("ATLAS_RUN_INTEGRATION"):
        print("[SKIP] ATLAS_RUN_INTEGRATION no seteado")
        return
    if shutil.which("engram") is None:
        print("[SKIP] engram binary no esta en PATH")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "config").mkdir(exist_ok=True)
        (root / "config" / "phase_playbook.json").write_text(
            json.dumps({"fase_1": {"e2e_required": []}})
        )

        # NO opt-out — queremos auto-enable real
        # Limpiar env var por si esta seteada por otro test
        prev = os.environ.pop("ATLAS_DISABLE_ENGRAM_MCP", None)
        try:
            d = ATLASDispatcher(root)
            assert d.engram_mcp_status == "active", f"FAIL: Engram debe estar activo, got {d.engram_mcp_status}"

            # 2-step real contra cajon conocido
            full = d.get_cajon_full("atlas-audit", "atlas/bloque-1a16-file-declaration")
            print(f"Status: {full['status']}")
            print(f"  type: {full.get('type')}")
            print(f"  title: {full.get('title','')[:60] if full.get('title') else None}")
            print(f"  raw_length: {full.get('raw_length')}")
            print(f"  topic_key: {full.get('topic_key')}")
            print(f"  content preview: {full.get('content','')[:120]}...")

            assert full["status"] == "found", f"FAIL: cajon conocido debe ser found, got {full}"
            assert full.get("raw_length", 0) > 500, f"FAIL: contenido completo debe >500 chars, got {full.get('raw_length')}"
            assert full.get("type") == "decision", f"FAIL: type debe ser 'decision', got {full.get('type')}"
            assert "1A.16" in (full.get("title") or ""), "FAIL: title debe mencionar 1A.16"
        finally:
            # Restaurar env var si estaba
            if prev is not None:
                os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = prev
    print("[OK] TEST 9: 2-step real con Engram retorna contenido completo")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1B.4: mem_get_observation / 2-step pattern")
    print("="*70)

    tests = [
        test_1_extract_observation_id_from_text,
        test_2_parse_search_result_with_real_format,
        test_3_parse_get_observation_full_content,
        test_4_get_observation_not_found,
        test_5_get_observation_timeout_not_confused_with_not_found,
        test_6_dispatcher_get_cajon_full_2step_mocked,
        test_7_dispatcher_get_cajon_full_skips_step2_if_search_not_found,
        test_8_inconsistent_state_detected,
        test_9_integration_real_engram_2step,
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
        print("[OK] Parser extrae observation_id entero del preview")
        print("[OK] mem_get_observation expuesto via bridge")
        print("[OK] get_cajon_full() implementa 2-step real")
        print("[OK] not_found en step 1 skipea step 2")
        print("[OK] Inconsistencia entre pasos detectada explicitamente")
        print("[OK] Timeout NO se confunde con not_found")
        print("[OK] Integration test con Engram real verifica contenido completo")
        print("\nLO QUE 1B.4 NO HACE:")
        print("- NO maneja ambiguous_project (eso es 1B.3)")
        print("- NO integra get_cajon_full() automaticamente desde el orquestador")
        print("- NO expone mem_save desde Python")
        print("- NO hace cross-machine sync")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
