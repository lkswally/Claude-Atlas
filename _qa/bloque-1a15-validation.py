#!/usr/bin/env python3
"""
Validacion real de Bloque 1A.15: Pre-Return Audit Enforcement
8 escenarios cubriendo dev_strict mode + re-verificacion independiente.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    """Crear dispatcher con phase_playbook minimo"""
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    playbook = {"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}}
    (root / "config" / "phase_playbook.json").write_text(json.dumps(playbook))
    (root / "src").mkdir(exist_ok=True)
    return ATLASDispatcher(root)


def write_file(root: Path, rel: str, content: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return rel


# ============================================================
#  TESTS
# ============================================================

def test_1_dev_strict_valid_envelope_clean_files():
    print("\n" + "="*70)
    print("TEST 1: dev_strict + envelope con audit valido + archivos limpios -> ACCEPT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        f = write_file(d.project_root, "src/clean.ts", "export const x = 1;\n")

        envelope = {
            "status": "completado",
            "tarea": "Implementar componente",
            "archivos": [f],
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": True,
                "summary": "PASS (0 blocks, 0 warns)",
                "block_findings": [],
                "warn_findings": [],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True, f"FAIL: envelope limpio debe pasar, errores={errores}"
        assert errores == []
        print("[OK] TEST 1: envelope valido aceptado")


def test_2_dev_strict_missing_audit_field():
    print("\n" + "="*70)
    print("TEST 2: dev_strict + envelope SIN campo pre_return_audit -> REJECT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        f = write_file(d.project_root, "src/foo.ts", "export const x = 1;\n")

        envelope = {
            "status": "completado",
            "tarea": "Implementar",
            "archivos": [f],
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            # pre_return_audit ausente
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is False
        assert any("pre_return_audit obligatorio" in e for e in errores), f"FAIL: error debe mencionar obligatoriedad, got {errores}"
        print("[OK] TEST 2: envelope sin audit rechazado con error claro")


def test_3_dev_strict_mismatch_agent_claims_pass_but_blocks_exist():
    print("\n" + "="*70)
    print("TEST 3: dev_strict + agente declara PASS pero archivo tiene debugger -> REJECT (mismatch)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        f = write_file(d.project_root, "src/buggy.ts", "export function x() {\n  debugger;\n}\n")

        envelope = {
            "status": "completado",
            "tarea": "Implementar",
            "archivos": [f],
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": True,  # MIENTE — el archivo tiene debugger
                "summary": "PASS (0 blocks, 0 warns)",
                "block_findings": [],
                "warn_findings": [],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}")
        print(f"errores={errores}")
        assert is_valid is False
        assert any("MISMATCH" in e for e in errores), f"FAIL: debe detectar mismatch, got {errores}"
        assert any("debugger" in e for e in errores), f"FAIL: debe mencionar la regla violada, got {errores}"
        print("[OK] TEST 3: mismatch detectado correctamente")


def test_4_dev_strict_agent_declares_ok_false_should_not_emit():
    print("\n" + "="*70)
    print("TEST 4: dev_strict + agente declara ok=false (no debio emitir envelope) -> REJECT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        f = write_file(d.project_root, "src/foo.ts", "export const x = 1;\n")

        envelope = {
            "status": "completado",
            "tarea": "Implementar",
            "archivos": [f],
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": False,  # Agente declaro fallo pero igual emitio
                "summary": "FAIL (2 blocks, 0 warns)",
                "block_findings": [{"rule": "debugger", "file": f, "line": 5}],
                "warn_findings": [],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is False
        assert any("ok=false" in e or "corregir blocks" in e for e in errores), f"FAIL: debe rechazar ok=false, got {errores}"
        print("[OK] TEST 4: envelope con ok=false rechazado")


def test_5_dev_strict_empty_archivos_trivial_pass():
    print("\n" + "="*70)
    print("TEST 5: dev_strict + archivos=[] -> ACCEPT (nada que auditar)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        envelope = {
            "status": "completado",
            "tarea": "Tarea sin archivos modificados",
            "archivos": [],
            "engram": "atlas/tareas",
            "verificacion": "none",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": True,
                "summary": "PASS (0 blocks, 0 warns) — no files",
                "block_findings": [],
                "warn_findings": [],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True, f"FAIL: archivos=[] debe pasar trivialmente, errores={errores}"
        print("[OK] TEST 5: envelope sin archivos acepta (trivial)")


def test_6_dev_strict_warns_only_passes():
    print("\n" + "="*70)
    print("TEST 6: dev_strict + audit con WARNs (no blocks) -> ACCEPT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # console.log es WARN, no BLOCK
        f = write_file(d.project_root, "src/logger.ts", "console.log('hello');\nexport const x = 1;\n")

        envelope = {
            "status": "completado",
            "tarea": "Implementar logger",
            "archivos": [f],
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            "notas": "1 warn: console.log",
            "pre_return_audit": {
                "ok": True,
                "summary": "PASS (0 blocks, 1 warns)",
                "block_findings": [],
                "warn_findings": [{"rule": "console_log", "file": f, "line": 1}],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True, f"FAIL: warns no deben bloquear, errores={errores}"
        print("[OK] TEST 6: envelope con solo warns aceptado")


def test_7_dev_strict_missing_declared_file():
    print("\n" + "="*70)
    print("TEST 7: dev_strict + archivos declara archivo inexistente -> REJECT")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)

        envelope = {
            "status": "completado",
            "tarea": "Implementar",
            "archivos": ["src/ghost.ts"],  # No existe
            "engram": "atlas/tareas",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": True,
                "summary": "PASS",
                "block_findings": [],
                "warn_findings": [],
            },
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="dev_strict")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is False
        assert any("MISMATCH" in e or "missing_file" in e for e in errores), f"FAIL: archivo inexistente debe detectarse, got {errores}"
        print("[OK] TEST 7: archivo inexistente rechazado")


def test_8_standard_mode_does_not_require_audit():
    print("\n" + "="*70)
    print("TEST 8: mode=standard NO exige pre_return_audit (backward compat)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        f = write_file(d.project_root, "src/foo.ts", "export const x = 1;\n")

        envelope = {
            "status": "completado",
            "tarea": "Tarea de creativo",
            "archivos": [f],
            "engram": "brand/logo",
            "verificacion": "none",
            "bloqueadores": [],
            # pre_return_audit ausente — OK para creativos en standard mode
        }

        is_valid, errores = d.validate_return_envelope(envelope, mode="standard")
        print(f"is_valid={is_valid}, errores={errores}")
        assert is_valid is True, f"FAIL: standard mode debe ser permisivo, errores={errores}"
        print("[OK] TEST 8: standard mode no exige audit (backward compat preservado)")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1A.15: Pre-Return Audit Enforcement")
    print("="*70)

    tests = [
        test_1_dev_strict_valid_envelope_clean_files,
        test_2_dev_strict_missing_audit_field,
        test_3_dev_strict_mismatch_agent_claims_pass_but_blocks_exist,
        test_4_dev_strict_agent_declares_ok_false_should_not_emit,
        test_5_dev_strict_empty_archivos_trivial_pass,
        test_6_dev_strict_warns_only_passes,
        test_7_dev_strict_missing_declared_file,
        test_8_standard_mode_does_not_require_audit,
    ]

    passed = 0
    failed = 0
    try:
        for t in tests:
            t()
            passed += 1
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        failed += 1

    print("\n" + "="*70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("="*70)

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] dev_strict mode exige pre_return_audit en envelope")
        print("[OK] Dispatcher re-verifica independientemente (no confia en claim)")
        print("[OK] Mismatch detectado (agente miente -> rechazo)")
        print("[OK] ok=false rechazado (agente no debio emitir)")
        print("[OK] archivos=[] pasa trivialmente")
        print("[OK] Solo warns no bloquea")
        print("[OK] standard mode preserva backward compat")
        print("\nPre-Return Audit Enforcement operativo. Loop cerrado.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
