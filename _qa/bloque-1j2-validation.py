#!/usr/bin/env python3
"""
Validacion real de Bloque 1J.2: Screenshot Hash Verification

11 tests:
- 10 unit (path missing, file missing, hash mismatch, etc.)
- 1 integration con screenshot real
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

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


def write_fake_screenshot(root: Path, rel_path: str, content_bytes: bytes = None) -> Path:
    """Crea un archivo fake que pretende ser un screenshot (PNG-like)."""
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    if content_bytes is None:
        # Generar ~5KB de bytes "PNG-like" (signature + padding)
        content_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 5000
    p.write_bytes(content_bytes)
    return p


def compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
#  TESTS
# ============================================================

def test_1_evidence_not_dict_unverifiable():
    print("\n=== TEST 1: Evidence no es dict -> unverifiable ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        r = d.verify_screenshot_evidence("not a dict")  # type: ignore
        assert r["verdict"] == "unverifiable"
        assert "no es dict" in r["note"].lower()
        print("[OK]")


def test_2_no_path_declared_unverifiable():
    print("\n=== TEST 2: Sin screenshot_path -> unverifiable ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        r = d.verify_screenshot_evidence({"detected_colors": ["#000"]})
        assert r["verdict"] == "unverifiable"
        assert "no declara" in r["note"].lower()
        print("[OK]")


def test_3_file_missing_critical_mismatch():
    print("\n=== TEST 3: Archivo declarado no existe -> mismatch CRITICAL ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        r = d.verify_screenshot_evidence({"screenshot_path": "screenshots/phantom.png"})
        print(f"verdict={r['verdict']}, discrepancies={[d['severity'] for d in r['discrepancies']]}")
        assert r["verdict"] == "mismatch"
        assert r["file_exists"] is False
        assert any(d.get("severity") == "CRITICAL" for d in r["discrepancies"])
        print("[OK]")


def test_4_file_exists_no_hash_declared_ok():
    print("\n=== TEST 4: File existe, sin hash declarado -> ok + computed_hash ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_fake_screenshot(d.project_root, "screenshots/real.png")
        r = d.verify_screenshot_evidence({"screenshot_path": "screenshots/real.png"})
        print(f"verdict={r['verdict']}, hash={r['computed_hash'][:16]}...")
        assert r["verdict"] == "ok"
        assert r["file_exists"] is True
        assert r["computed_hash"] is not None
        assert len(r["computed_hash"]) == 64  # SHA256 hex
        assert r["discrepancies"] == []
        print("[OK]")


def test_5_hash_match_ok():
    print("\n=== TEST 5: File existe + hash declarado coincide -> ok ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        p = write_fake_screenshot(d.project_root, "screenshots/test.png")
        correct_hash = compute_hash(p)

        r = d.verify_screenshot_evidence({
            "screenshot_path": "screenshots/test.png",
            "screenshot_hash": correct_hash,
        })
        assert r["verdict"] == "ok"
        assert r["discrepancies"] == []
        # Verificar que el check de hash esta presente con match
        hash_checks = [c for c in r["checks"] if c.get("field") == "screenshot_hash"]
        assert len(hash_checks) == 1
        assert hash_checks[0].get("match") is True
        print("[OK]")


def test_6_hash_mismatch_critical():
    print("\n=== TEST 6: Hash declarado INCORRECTO -> mismatch CRITICAL ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_fake_screenshot(d.project_root, "screenshots/test.png")

        r = d.verify_screenshot_evidence({
            "screenshot_path": "screenshots/test.png",
            "screenshot_hash": "fakehash" + "0" * 56,  # 64 chars pero no es el real
        })
        print(f"verdict={r['verdict']}")
        assert r["verdict"] == "mismatch"
        hash_disc = [d for d in r["discrepancies"] if d.get("field") == "screenshot_hash"]
        assert len(hash_disc) == 1
        assert hash_disc[0]["severity"] == "CRITICAL"
        assert hash_disc[0]["match"] is False
        print("[OK]")


def test_7_hash_with_sha256_prefix_accepted():
    print("\n=== TEST 7: Hash con prefijo 'sha256:' aceptado ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        p = write_fake_screenshot(d.project_root, "screenshots/test.png")
        correct_hash = compute_hash(p)

        r = d.verify_screenshot_evidence({
            "screenshot_path": "screenshots/test.png",
            "screenshot_hash": f"sha256:{correct_hash}",
        })
        assert r["verdict"] == "ok"
        print("[OK]")


def test_8_expected_path_match_ok():
    print("\n=== TEST 8: expected_path coincide con declarado -> ok ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_fake_screenshot(d.project_root, "screenshots/login.png")
        r = d.verify_screenshot_evidence(
            {"screenshot_path": "screenshots/login.png"},
            expected_path="screenshots/login.png",
        )
        assert r["verdict"] == "ok"
        print("[OK]")


def test_9_expected_path_mismatch_high():
    print("\n=== TEST 9: expected_path difiere del declarado -> mismatch HIGH ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_fake_screenshot(d.project_root, "screenshots/wrong.png")
        r = d.verify_screenshot_evidence(
            {"screenshot_path": "screenshots/wrong.png"},
            expected_path="screenshots/login.png",
        )
        print(f"verdict={r['verdict']}")
        assert r["verdict"] == "mismatch"
        path_disc = [d for d in r["discrepancies"] if "expected_match" in d.get("field", "")]
        assert len(path_disc) == 1
        assert path_disc[0]["severity"] == "HIGH"
        print("[OK]")


def test_10_empty_file_high_mismatch():
    print("\n=== TEST 10: Archivo de 0 bytes -> mismatch HIGH ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_fake_screenshot(d.project_root, "screenshots/empty.png", content_bytes=b"")
        r = d.verify_screenshot_evidence({"screenshot_path": "screenshots/empty.png"})
        print(f"verdict={r['verdict']}, file_size={r['file_size']}")
        assert r["verdict"] == "mismatch"
        assert r["file_size"] == 0
        size_disc = [d for d in r["discrepancies"] if d.get("field") == "file_size"]
        assert len(size_disc) == 1
        assert size_disc[0]["severity"] == "HIGH"
        print("[OK]")


def test_11_realistic_qa_scenario():
    print("\n=== TEST 11 [INTEGRATION]: Scenario realista de QA con cache de hash ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        # 1. Primer QA: agente reporta evidencia, computamos hash
        write_fake_screenshot(d.project_root, "qa-evidence/task-1-screenshot.png")
        r1 = d.verify_screenshot_evidence({
            "screenshot_path": "qa-evidence/task-1-screenshot.png",
        })
        assert r1["verdict"] == "ok"
        cached_hash = r1["computed_hash"]
        print(f"  Primer QA: hash cacheado = {cached_hash[:16]}...")

        # 2. Re-run QA: agente reporta el mismo screenshot — debe coincidir
        r2 = d.verify_screenshot_evidence({
            "screenshot_path": "qa-evidence/task-1-screenshot.png",
            "screenshot_hash": cached_hash,
        })
        assert r2["verdict"] == "ok"
        print(f"  Re-run QA: hash match -> OK")

        # 3. Tamper: archivo modificado pero agente sigue declarando hash viejo
        write_fake_screenshot(d.project_root, "qa-evidence/task-1-screenshot.png",
                             content_bytes=b"\x89PNG\r\n\x1a\nMODIFIED" + b"\x00" * 5000)
        r3 = d.verify_screenshot_evidence({
            "screenshot_path": "qa-evidence/task-1-screenshot.png",
            "screenshot_hash": cached_hash,  # hash de version anterior
        })
        print(f"  Tamper detectado: verdict={r3['verdict']}")
        assert r3["verdict"] == "mismatch"
        assert any(d.get("severity") == "CRITICAL" for d in r3["discrepancies"])
        print("[OK] Scenario realista: detecta tampering entre runs")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1J.2: Screenshot Hash Verification")
    print("="*70)

    tests = [
        test_1_evidence_not_dict_unverifiable,
        test_2_no_path_declared_unverifiable,
        test_3_file_missing_critical_mismatch,
        test_4_file_exists_no_hash_declared_ok,
        test_5_hash_match_ok,
        test_6_hash_mismatch_critical,
        test_7_hash_with_sha256_prefix_accepted,
        test_8_expected_path_match_ok,
        test_9_expected_path_mismatch_high,
        test_10_empty_file_high_mismatch,
        test_11_realistic_qa_scenario,
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
        print("\nLO QUE 1J.2 NO HACE:")
        print("- NO valida que el screenshot sea de la pagina correcta — solo")
        print("  que exista y tenga hash verificable")
        print("- NO compara contra screenshot 'esperado' a nivel de contenido")
        print("  (eso requiere image diff o LLM-as-judge — 1H.3)")
        print("- Archivos < 1KB se marcan LOW (sospechoso pero no bloquea)")
        print("- expected_path es opcional — si no se pasa, no se compara")
        print("- Sin path declarado -> unverifiable (no detecta nada)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
