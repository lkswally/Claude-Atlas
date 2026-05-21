#!/usr/bin/env python3
"""
Validacion real de Bloque 1F.1: File Hash Caching para QA

11 tests:
- 10 unit (cache logic + dispatcher helpers + edge cases)
- 1 integration realistic con dev->QA loop simulado
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher
from file_hash_cache import FileHashCache, CACHE_VERSION


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


def make_cache(tmpdir: str, **kwargs) -> FileHashCache:
    root = Path(tmpdir)
    (root / ".pipeline").mkdir(exist_ok=True)
    return FileHashCache(root, **kwargs)


def write_file(root: Path, rel_path: str, content: str) -> Path:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ============================================================
#  UNIT TESTS
# ============================================================

def test_1_sha256_deterministic():
    print("\n" + "="*70)
    print("TEST 1: SHA256 determinista para mismo contenido")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "export const x = 1;\n")
        write_file(root, "src/foo2.ts", "export const x = 1;\n")  # mismo contenido

        cache = make_cache(tmpdir)
        h1 = cache.compute_hashes(["src/foo.ts"])
        h2 = cache.compute_hashes(["src/foo2.ts"])
        print(f"Hash foo.ts: {h1['src/foo.ts']['sha256'][:16]}...")
        print(f"Hash foo2.ts: {h2['src/foo2.ts']['sha256'][:16]}...")
        assert h1["src/foo.ts"]["sha256"] == h2["src/foo2.ts"]["sha256"]
    print("[OK] TEST 1: SHA256 determinista")


def test_2_hash_changes_with_content():
    print("\n" + "="*70)
    print("TEST 2: Hash cambia si archivo cambia (1 byte diff)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = write_file(root, "src/foo.ts", "export const x = 1;\n")

        cache = make_cache(tmpdir)
        h1 = cache.compute_hashes(["src/foo.ts"])

        # Cambiar 1 byte
        f.write_text("export const x = 2;\n")
        h2 = cache.compute_hashes(["src/foo.ts"])

        print(f"Hash original: {h1['src/foo.ts']['sha256'][:16]}...")
        print(f"Hash modificado: {h2['src/foo.ts']['sha256'][:16]}...")
        assert h1["src/foo.ts"]["sha256"] != h2["src/foo.ts"]["sha256"]
    print("[OK] TEST 2: 1 byte cambia -> hash diferente")


def test_3_cache_miss_when_no_entry():
    print("\n" + "="*70)
    print("TEST 3: Cache miss cuando no hay entry")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "data")
        cache = make_cache(tmpdir)

        result = cache.get_cached_result("task-1", ["src/foo.ts"])
        print(f"Result: {result}")
        assert result is None
    print("[OK] TEST 3: Sin entry -> None (no romper)")


def test_4_cache_hit_when_hashes_match():
    print("\n" + "="*70)
    print("TEST 4: Cache hit cuando hashes coinciden")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "data1")
        write_file(root, "src/bar.ts", "data2")

        cache = make_cache(tmpdir)
        qa_pass = {"status": "PASS", "tarea": "T1", "verificacion": "layout"}

        # Cachear
        write_meta = cache.cache_result("task-1", ["src/foo.ts", "src/bar.ts"], qa_pass)
        print(f"Cache write: {write_meta}")
        assert write_meta["cached"] is True
        assert write_meta["files_cached"] == 2

        # Consultar
        hit = cache.get_cached_result("task-1", ["src/foo.ts", "src/bar.ts"])
        print(f"Hit: status={hit['qa_result']['status']}, from_cache={hit['from_cache']}")
        assert hit is not None
        assert hit["qa_result"]["status"] == "PASS"
        assert hit["from_cache"] is True
        assert hit["task_id"] == "task-1"
    print("[OK] TEST 4: Hashes coinciden -> hit con resultado correcto")


def test_5_hash_mismatch_returns_miss():
    print("\n" + "="*70)
    print("TEST 5: Hash mismatch -> miss (no falso hit)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = write_file(root, "src/foo.ts", "version1")

        cache = make_cache(tmpdir)
        cache.cache_result("task-1", ["src/foo.ts"], {"status": "PASS", "tarea": "T1"})

        # Verificar hit inicial
        assert cache.get_cached_result("task-1", ["src/foo.ts"]) is not None

        # Modificar archivo
        time.sleep(0.05)  # asegurar mtime diferente
        f.write_text("version2")

        # Ahora debe ser miss
        result = cache.get_cached_result("task-1", ["src/foo.ts"])
        print(f"After modify: result={result}")
        assert result is None
    print("[OK] TEST 5: Archivo cambia -> miss (no falso PASS)")


def test_6_mtime_newer_invalidates():
    print("\n" + "="*70)
    print("TEST 6: mtime mas nuevo invalida (paranoid mode)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        f = write_file(root, "src/foo.ts", "content")

        cache = make_cache(tmpdir)
        cache.cache_result("task-1", ["src/foo.ts"], {"status": "PASS"})

        # Touch sin cambiar contenido (mtime cambia, hash NO)
        time.sleep(0.05)
        # Re-escribir mismo contenido (no cambia hash pero si mtime)
        f.write_text("content")

        # Hash deberia coincidir pero mtime es mas nuevo -> invalidar
        result = cache.get_cached_result("task-1", ["src/foo.ts"])
        print(f"After touch (same content, newer mtime): result={result}")
        assert result is None, "FAIL: mtime mas nuevo debe invalidar aunque hash coincida"
    print("[OK] TEST 6: mtime newer -> invalidacion (paranoid)")


def test_7_fail_only_not_cached():
    print("\n" + "="*70)
    print("TEST 7: FAIL no se cachea (solo PASS)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "data")

        cache = make_cache(tmpdir)
        result = cache.cache_result("task-1", ["src/foo.ts"], {"status": "FAIL", "bloqueadores": ["bug"]})
        print(f"Cache FAIL attempt: {result}")
        assert result["cached"] is False
        assert "PASS" in result["reason"]

        # Verificar que NO esta en cache
        hit = cache.get_cached_result("task-1", ["src/foo.ts"])
        assert hit is None
    print("[OK] TEST 7: FAIL nunca cacheado")


def test_8_corrupted_cache_fail_open():
    print("\n" + "="*70)
    print("TEST 8: Cache corrupto -> fail-open (no romper)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "data")
        cache_dir = root / ".pipeline"
        cache_dir.mkdir(exist_ok=True)
        # Escribir cache corrupto
        (cache_dir / "qa-cache.json").write_text("not valid {{{ json")

        cache = make_cache(tmpdir)

        # get debe retornar None sin excepcion
        result = cache.get_cached_result("task-1", ["src/foo.ts"])
        print(f"After corrupted: result={result}")
        assert result is None

        # cache_result debe funcionar (sobrescribe el corrupto)
        write = cache.cache_result("task-1", ["src/foo.ts"], {"status": "PASS"})
        assert write["cached"] is True

        # Ahora hit debe funcionar
        hit = cache.get_cached_result("task-1", ["src/foo.ts"])
        assert hit is not None
    print("[OK] TEST 8: Cache corrupto -> reset graceful, no rompe")


def test_9_prune_old_entries():
    print("\n" + "="*70)
    print("TEST 9: prune_old elimina entries > max_age")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        write_file(root, "src/foo.ts", "data")

        cache = make_cache(tmpdir, max_age_days=14)
        cache.cache_result("task-recent", ["src/foo.ts"], {"status": "PASS"})

        # Inyectar entry vieja manualmente
        state = cache._load_state()
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        state["entries"]["task-old"] = {
            "hashes": {"src/old.ts": {"sha256": "abc", "mtime": 0}},
            "qa_result": {"status": "PASS"},
            "cached_at": old_date,
            "hash_version": 1,
        }
        cache._save_state(state)

        removed = cache.prune_old()
        print(f"Removed: {removed} entries")
        assert removed == 1

        # task-recent debe seguir
        stats = cache.stats()
        assert "task-recent" in stats["task_ids"]
        assert "task-old" not in stats["task_ids"]
    print("[OK] TEST 9: Prune elimina entries viejas")


def test_10_dispatcher_helpers_end_to_end():
    print("\n" + "="*70)
    print("TEST 10: dispatcher.should_skip_qa + cache_qa_result end-to-end")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        write_file(d.project_root, "src/Header.tsx", "<header>v1</header>")

        # Initial miss
        miss = d.should_skip_qa("task-header", ["src/Header.tsx"])
        print(f"Initial: {miss}")
        assert miss is None

        # Cachear PASS
        write = d.cache_qa_result(
            "task-header",
            ["src/Header.tsx"],
            {"status": "PASS", "tarea": "Header", "verificacion": "layout"},
        )
        print(f"Cache write: {write}")
        assert write["cached"] is True

        # Re-consultar: HIT
        hit = d.should_skip_qa("task-header", ["src/Header.tsx"])
        print(f"After cache: from_cache={hit['from_cache'] if hit else None}")
        assert hit is not None
        assert hit["from_cache"] is True
        assert hit["qa_result"]["status"] == "PASS"
    print("[OK] TEST 10: Helpers del dispatcher end-to-end")


def test_11_realistic_dev_qa_loop():
    print("\n" + "="*70)
    print("TEST 11 [INTEGRATION-LIKE]: Loop dev->QA con cache real")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Setup: 3 archivos de una tarea
        write_file(d.project_root, "src/Login.tsx", "// login v1")
        write_file(d.project_root, "src/auth.ts", "// auth v1")
        write_file(d.project_root, "src/styles.css", "/* styles v1 */")
        archivos = ["src/Login.tsx", "src/auth.ts", "src/styles.css"]

        # Ciclo 1: QA fresh (miss + cache write)
        miss1 = d.should_skip_qa("task-login", archivos)
        assert miss1 is None
        d.cache_qa_result("task-login", archivos, {"status": "PASS", "tarea": "Login"})

        # Ciclo 2: re-invocar sin cambios -> HIT
        hit2 = d.should_skip_qa("task-login", archivos)
        assert hit2 is not None
        assert hit2["from_cache"] is True
        print(f"Ciclo 2 (sin cambios): HIT")

        # Ciclo 3: modificar 1 archivo -> miss
        time.sleep(0.05)
        write_file(d.project_root, "src/Login.tsx", "// login v2 (fix)")
        miss3 = d.should_skip_qa("task-login", archivos)
        assert miss3 is None
        print(f"Ciclo 3 (Login.tsx modificado): MISS correcto")

        # Re-cachear despues del fix
        d.cache_qa_result("task-login", archivos, {"status": "PASS", "tarea": "Login fixed"})

        # Ciclo 4: HIT con la nueva version
        hit4 = d.should_skip_qa("task-login", archivos)
        assert hit4 is not None
        assert hit4["qa_result"]["tarea"] == "Login fixed"
        print(f"Ciclo 4 (cacheado de nuevo): HIT con tarea actualizada")
    print("[OK] TEST 11: Dev->QA loop con cache funciona correctamente")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1F.1: File Hash Caching para QA")
    print("="*70)

    tests = [
        test_1_sha256_deterministic,
        test_2_hash_changes_with_content,
        test_3_cache_miss_when_no_entry,
        test_4_cache_hit_when_hashes_match,
        test_5_hash_mismatch_returns_miss,
        test_6_mtime_newer_invalidates,
        test_7_fail_only_not_cached,
        test_8_corrupted_cache_fail_open,
        test_9_prune_old_entries,
        test_10_dispatcher_helpers_end_to_end,
        test_11_realistic_dev_qa_loop,
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
        print("[OK] SHA256 determinista")
        print("[OK] Hash cambia con cualquier diff (1 byte)")
        print("[OK] Cache miss limpio sin excepcion")
        print("[OK] Cache hit con resultado correcto")
        print("[OK] Hash mismatch invalida (no falso PASS)")
        print("[OK] mtime newer invalida (paranoid mode)")
        print("[OK] FAIL nunca cacheado (solo PASS)")
        print("[OK] Cache corrupto -> fail-open (reset graceful)")
        print("[OK] Prune elimina entries > max_age_days")
        print("[OK] dispatcher.should_skip_qa + cache_qa_result helpers")
        print("[OK] Loop dev->QA realista con cache funciona")
        print("\nLO QUE 1F.1 NO HACE:")
        print("- El agente evidence-collector debe leer su md y consultar cache")
        print("- NO trackea cambios externos (deps, env, build config)")
        print("- NO valida que el PASS cacheado sigue valido contra cambios fuera")
        print("- Cache NO se prunea automaticamente — invocar prune_old() manual")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
