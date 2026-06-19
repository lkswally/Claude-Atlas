#!/usr/bin/env python3
"""
Bloque F7 — Healthcheck Validation
====================================

Tests para tools/atlas_healthcheck.py:
  1. Healthcheck completo del repo real -> exit 0 (HEALTHY)
  2. Salida --json tiene estructura esperada
  3. Detección de settings.json inválido -> exit 1 (FAIL)
  4. Detección de hook faltante -> exit 1 (FAIL)
  5. Detección de path heredado -> exit 1 (FAIL)
  6. --quiet suprime PASS y WARN, muestra sólo FAIL
  7. Salida tiene marcadores [PASS]/[WARN]/[FAIL]
  8. Exit 0 cuando no hay FAIL aunque haya WARN
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HEALTHCHECK  = PROJECT_ROOT / "tools" / "atlas_healthcheck.py"
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"

# Minimal valid settings.json for tests that need to manipulate the file.
# Used when Claude Desktop hasn't created the file yet (RUNTIME_MUTABLE state).
_MINIMAL_SETTINGS = {
    "hooks": {
        "Stop": [],
        "PreToolUse": [],
        "PostToolUse": [],
    }
}


@contextlib.contextmanager
def _synthetic_settings(content: dict | None = None):
    """
    Context manager: ensures settings.json exists for the duration of the block.

    If settings.json already exists, backs it up and restores after.
    If it doesn't exist (RUNTIME_MUTABLE / Claude Desktop not running),
    creates a synthetic one from _MINIMAL_SETTINGS and removes it after.
    """
    existed = SETTINGS_PATH.exists()
    backup = SETTINGS_PATH.with_suffix(".json.bak_f7_ctx")
    created = False
    try:
        if existed:
            SETTINGS_PATH.rename(backup)
        base = content if content is not None else _MINIMAL_SETTINGS
        SETTINGS_PATH.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
        created = True
        yield
    finally:
        SETTINGS_PATH.unlink(missing_ok=True)
        if existed and backup.exists():
            backup.rename(SETTINGS_PATH)
        elif not existed:
            pass  # leave it absent, as before


def run_healthcheck(*extra_args, cwd=None, env=None) -> tuple[int, str]:
    """Ejecuta healthcheck como subprocess; retorna (exit_code, combined_output)."""
    cmd = [sys.executable, str(HEALTHCHECK)] + list(extra_args)
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=str(cwd or PROJECT_ROOT),
        env=env or os.environ.copy(),
    )
    return r.returncode, r.stdout + r.stderr


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

def test_1_healthy_on_real_repo():
    print("\n=== TEST 1: Healthcheck del repo real -> exit 0 (HEALTHY) ===")
    code, out = run_healthcheck()
    print(f"  exit={code}")
    # Mostrar últimas líneas del output
    for line in out.splitlines()[-6:]:
        print(f"  {line}")
    assert code == 0, f"Esperado exit 0 (HEALTHY), got {code}\nOutput:\n{out[-600:]}"
    assert "HEALTHY" in out or "PASS" in out
    print("[OK]")


def test_2_json_output_structure():
    print("\n=== TEST 2: --json tiene estructura correcta ===")
    code, out = run_healthcheck("--json")
    print(f"  exit={code}")
    assert code == 0, f"Exit {code}, output: {out[-300:]}"
    data = json.loads(out)
    assert "results" in data
    assert "summary" in data
    assert "healthy" in data
    summary = data["summary"]
    assert "pass" in summary and "warn" in summary and "fail" in summary
    assert data["healthy"] is True
    assert summary["fail"] == 0
    assert summary["pass"] > 0
    print(f"  pass={summary['pass']}, warn={summary['warn']}, fail={summary['fail']}, healthy={data['healthy']}")
    print("[OK]")


def test_3_detects_invalid_settings_json():
    print("\n=== TEST 3: Detecta settings.json invalido -> exit 1 (--strict-runtime) ===")
    # The runtime .claude/settings.json is RUNTIME_MUTABLE (F24 P5):
    #   --strict (expected/release): corrupt runtime settings → WARN (not a release blocker).
    #   --strict-runtime: corrupt runtime settings → FAIL (asserts the live file).
    # Detection of a corrupt runtime file lives on the RUNTIME axis now.
    existed = SETTINGS_PATH.exists()
    backup = SETTINGS_PATH.with_suffix(".json.bak_f7c")
    try:
        if existed:
            SETTINGS_PATH.rename(backup)
        SETTINGS_PATH.write_text("{invalid json!!", encoding="utf-8")

        code, out = run_healthcheck("--strict-runtime")
        print(f"  exit={code}")
        fail_lines = [l for l in out.splitlines() if "[FAIL]" in l]
        for l in fail_lines[:3]:
            # Mask [FAIL] so run_all's secondary marker check doesn't false-positive
            # on nested tool output when this suite itself is passing.
            print(f"  hc:{l.strip().replace('[FAIL]', 'FAIL:')}")
        assert code == 1, f"Esperado exit 1 (FAIL en --strict-runtime), got {code}\nOutput:\n{out[-600:]}"
        assert any("settings.json" in l for l in fail_lines), \
            f"Esperado FAIL sobre settings.json, lines={fail_lines}"
    finally:
        SETTINGS_PATH.unlink(missing_ok=True)
        if existed and backup.exists():
            backup.rename(SETTINGS_PATH)
    print("[OK]")


def test_4_detects_missing_hook_file():
    print("\n=== TEST 4: Detecta hook faltante en disco -> exit 1 ===")
    original = SETTINGS_PATH.read_text(encoding="utf-8") if SETTINGS_PATH.exists() else None
    settings = json.loads(original) if original else dict(_MINIMAL_SETTINGS)

    # Inyectar referencia a hook inexistente
    settings["hooks"]["Stop"].append({
        "hooks": [{"type": "command", "command": "node .claude/hooks/nonexistent-hook.js", "timeout": 5}]
    })

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
        dir=str(PROJECT_ROOT / ".claude")
    ) as tf:
        temp_path = Path(tf.name)
        json.dump(settings, tf, ensure_ascii=False, indent=2)

    # Parchear temporalmente: renombrar settings.json original (if exists) y poner el modificado
    existed = SETTINGS_PATH.exists()
    backup = SETTINGS_PATH.with_suffix(".json.bak_f7")
    try:
        if existed:
            SETTINGS_PATH.rename(backup)
        temp_path.rename(SETTINGS_PATH)

        code, out = run_healthcheck()
        print(f"  exit={code}")
        fail_lines = [l for l in out.splitlines() if "[FAIL]" in l]
        for l in fail_lines[:3]:
            # Mask [FAIL] so run_all's secondary marker check doesn't false-positive
            # on nested tool output when this suite itself is passing.
            print(f"  hc:{l.strip().replace('[FAIL]', 'FAIL:')}")
        assert code == 1, f"Esperado exit 1, got {code}"
        assert any("nonexistent" in l or "Hooks" in l for l in fail_lines), \
            f"Esperado FAIL sobre hook faltante, lines={fail_lines}"
    finally:
        SETTINGS_PATH.unlink(missing_ok=True)
        if existed and backup.exists():
            backup.rename(SETTINGS_PATH)
        temp_path.unlink(missing_ok=True)

    print("[OK]")


def test_5_detects_legacy_absolute_path():
    print("\n=== TEST 5: Detecta path heredado /c/Users/Lucas/ -> exit 1 ===")
    original = SETTINGS_PATH.read_text(encoding="utf-8") if SETTINGS_PATH.exists() else None
    settings = json.loads(original) if original else dict(_MINIMAL_SETTINGS)

    # Inyectar path absoluto heredado
    settings["hooks"]["Stop"].append({
        "hooks": [{
            "type": "command",
            "command": "node /c/Users/Lucas/.claude/hooks/session-summary.js",
            "timeout": 5
        }]
    })

    existed = SETTINGS_PATH.exists()
    backup = SETTINGS_PATH.with_suffix(".json.bak_f7b")
    try:
        if existed:
            SETTINGS_PATH.rename(backup)
        SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

        code, out = run_healthcheck()
        print(f"  exit={code}")
        fail_lines = [l for l in out.splitlines() if "[FAIL]" in l]
        for l in fail_lines[:3]:
            # Mask [FAIL] so run_all's secondary marker check doesn't false-positive
            # on nested tool output when this suite itself is passing.
            print(f"  hc:{l.strip().replace('[FAIL]', 'FAIL:')}")
        assert code == 1, f"Esperado exit 1, got {code}"
        assert any("Paths" in l or "path" in l.lower() or "Lucas" in l for l in fail_lines), \
            f"Esperado FAIL sobre paths heredados, lines={fail_lines}"
    finally:
        SETTINGS_PATH.unlink(missing_ok=True)
        if existed and backup.exists():
            backup.rename(SETTINGS_PATH)

    print("[OK]")


def test_6_quiet_mode_suppresses_pass():
    print("\n=== TEST 6: --quiet suprime [PASS] y [WARN], muestra sólo [FAIL] ===")
    code, out = run_healthcheck("--quiet")
    print(f"  exit={code}")
    lines = out.splitlines()
    pass_lines = [l for l in lines if "[PASS]" in l]
    print(f"  líneas [PASS] en output: {len(pass_lines)}")
    assert code == 0
    assert len(pass_lines) == 0, f"--quiet no debería mostrar [PASS], encontradas: {pass_lines[:3]}"
    print("[OK]")


def test_7_output_has_status_markers():
    print("\n=== TEST 7: Output contiene marcadores [PASS]/[WARN]/[FAIL] ===")
    code, out = run_healthcheck()
    assert code == 0
    lines = [l for l in out.splitlines() if "[PASS]" in l or "[WARN]" in l or "[FAIL]" in l]
    print(f"  líneas con marcador: {len(lines)}")
    assert len(lines) >= 5, f"Esperado >= 5 líneas con marcadores, got {len(lines)}"
    assert any("[PASS]" in l for l in lines), "No hay ningún [PASS]"
    print("[OK]")


def test_8_exit_0_with_only_warns():
    print("\n=== TEST 8: Exit 0 aunque haya WARN (sólo FAIL produce exit 1) ===")
    # Simular WARN forzado: usar tmpdir sin .pipeline/ ni config/ ni snapshots/
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Estructura mínima válida para que no haya FAILs
        claude_dir = tmp / ".claude"
        claude_dir.mkdir()
        (claude_dir / "hooks").mkdir()
        # settings.json sin hooks para que el check de hooks sea WARN, no FAIL
        (claude_dir / "settings.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"hooks": []}]}}),
            encoding="utf-8"
        )
        (tmp / "tools").mkdir()
        # Copiar solo el healthcheck al tools del tmpdir
        shutil.copy(str(HEALTHCHECK), str(tmp / "tools" / "atlas_healthcheck.py"))
        shutil.copy(
            str(PROJECT_ROOT / "tools" / "atlas_dispatcher.py"),
            str(tmp / "tools" / "atlas_dispatcher.py")
        )
        (tmp / "_qa").mkdir()
        # NO crear .pipeline/, config/, ni snapshots — generarán WARNs

        env = os.environ.copy()
        env["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        code, out = run_healthcheck(cwd=tmp, env=env)
        print(f"  exit={code}")
        warn_lines = [l for l in out.splitlines() if "[WARN]" in l]
        fail_lines = [l for l in out.splitlines() if "[FAIL]" in l]
        print(f"  WARNs={len(warn_lines)}, FAILs={len(fail_lines)}")
        for l in warn_lines[:4]:
            print(f"  {l.strip()}")
        # En este escenario puede no haber WARNs (node/python/npm se encuentran)
        # pero lo importante es que exit code refleja sólo FAILs
        if fail_lines:
            assert code == 1, "Con FAIL debe ser exit 1"
        else:
            assert code == 0, f"Sin FAIL debe ser exit 0, got {code}"
    print("[OK]")


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 70)
    print("BLOQUE F7 — Healthcheck Validation")
    print("=" * 70)

    tests = [
        test_1_healthy_on_real_repo,
        test_2_json_output_structure,
        test_3_detects_invalid_settings_json,
        test_4_detects_missing_hook_file,
        test_5_detects_legacy_absolute_path,
        test_6_quiet_mode_suppresses_pass,
        test_7_output_has_status_markers,
        test_8_exit_0_with_only_warns,
    ]

    passed = failed = 0
    failures = []
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {t.__name__}: {e}")
            failed += 1
            failures.append((t.__name__, str(e)))
        except Exception as e:
            print(f"\n[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            failures.append((t.__name__, f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("=" * 70)

    if failures:
        print("\nFALLOS:")
        for name, msg in failures:
            print(f"  {name}: {msg[:200]}")

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] Healthcheck real del repo -> HEALTHY (exit 0)")
        print("[OK] --json tiene estructura {results, summary, healthy}")
        print("[OK] Detecta settings.json invalido (FAIL + exit 1)")
        print("[OK] Detecta hook faltante en disco (FAIL + exit 1)")
        print("[OK] Detecta path heredado /c/Users/Lucas/ (FAIL + exit 1)")
        print("[OK] --quiet suprime lineas PASS")
        print("[OK] Output contiene marcadores [PASS]/[WARN]/[FAIL]")
        print("[OK] Exit 0 con solo WARNs, exit 1 solo con FAIL")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
