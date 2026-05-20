#!/usr/bin/env python3
"""
Validacion real de Bloque 1A.12: Anti-loop Tracking Enforcement
Test 4 escenarios: primer intento, segundo intento, tercero (escalacion), recovery
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple, List

class AntiLoopValidator:
    """Simula enforce_phase_gate con anti-loop tracking (Bloque 1A.12)"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.phase_gate_retries: Dict[str, int] = {}

    def _check_engram_cajon(self, proyecto: str, cajon: str) -> Dict[str, str]:
        """Mock Engram search"""
        cajon_name = cajon.split("/")[-1]
        disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"

        if disk_path.exists():
            return {"status": "found", "cajon": cajon}
        else:
            return {"status": "not_found", "cajon": cajon}

    def _check_disk_cajon(self, proyecto: str, cajon: str) -> bool:
        """Check disk fallback"""
        cajon_name = cajon.split("/")[-1]
        disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"
        return disk_path.exists()

    def enforce_phase_gate(self, proyecto: str, phase: str, required_cajones: List[str]) -> Tuple[bool, str, List[str]]:
        """Enforce phase gate con anti-loop tracking"""
        missing_cajones = []
        escalation_cajones = []

        for cajon in required_cajones:
            engram_response = self._check_engram_cajon(proyecto, cajon)

            if engram_response["status"] == "found":
                # Reset counter si estaba siendo reintentado
                if cajon in self.phase_gate_retries:
                    del self.phase_gate_retries[cajon]
                continue

            elif engram_response["status"] == "not_found":
                disk_exists = self._check_disk_cajon(proyecto, cajon)
                if not disk_exists:
                    # Cajon falta — implementar anti-loop
                    retry_count = self.phase_gate_retries.get(cajon, 0)

                    if retry_count >= 2:
                        # Max reintentos alcanzado
                        escalation_cajones.append(f"{cajon} (intento {retry_count + 1}/max 2)")
                    else:
                        # Primer o segundo intento
                        missing_cajones.append(cajon)
                        self.phase_gate_retries[cajon] = retry_count + 1

        # Decisión
        if escalation_cajones:
            message = (
                f"FASE {phase.upper()} ESCALACION (Max reintentos alcanzado):\n"
                f"  Cajones bloqueados tras 2+ intentos: {', '.join(escalation_cajones)}\n"
                f"  Accion requerida: Usuario debe resolver manualmente"
            )
            return False, message, escalation_cajones

        if missing_cajones:
            message = f"FASE {phase.upper()} BLOQUEADA:\n  Cajones requeridos faltantes: {', '.join(missing_cajones)}"
            return False, message, missing_cajones

        message = f"FASE {phase.upper()}: Phase Gate OK."
        return True, message, []


def test_primer_intento():
    """Test 1: Primer intento — cajon falta, contador = 1"""
    print("\n" + "="*70)
    print("TEST 1: PRIMER INTENTO -- cajon falta, counter=1")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pipeline_dir = project_root / ".pipeline"
        pipeline_dir.mkdir()

        validator = AntiLoopValidator(project_root)
        can_proceed, message, missing = validator.enforce_phase_gate(
            "atlas", "fase_2", ["atlas/tareas"]
        )

        print(f"Setup: .pipeline/tareas.md NO EXISTE")
        print(f"Result: can_proceed={can_proceed}, missing={missing}")
        print(f"Retry counter: {validator.phase_gate_retries}")

        assert can_proceed is False, "FAIL: Debe bloquear"
        assert "atlas/tareas" in missing, "FAIL: tareas debe estar en missing"
        assert validator.phase_gate_retries.get("atlas/tareas") == 1, "FAIL: Counter debe ser 1"
        assert "BLOQUEADA" in message, "FAIL: Debe ser BLOQUEADA"
        print("[OK] PASS: TEST 1 OK -- Primer intento, counter=1")


def test_segundo_intento():
    """Test 2: Segundo intento — cajon sigue faltando, contador = 2"""
    print("\n" + "="*70)
    print("TEST 2: SEGUNDO INTENTO -- cajon sigue faltando, counter=2")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pipeline_dir = project_root / ".pipeline"
        pipeline_dir.mkdir()

        validator = AntiLoopValidator(project_root)

        # Simular primer intento
        validator.enforce_phase_gate("atlas", "fase_2", ["atlas/tareas"])
        assert validator.phase_gate_retries.get("atlas/tareas") == 1

        # Segundo intento
        can_proceed, message, missing = validator.enforce_phase_gate(
            "atlas", "fase_2", ["atlas/tareas"]
        )

        print(f"Setup: Primer intento ya hizo counter=1")
        print(f"Result: can_proceed={can_proceed}, missing={missing}")
        print(f"Retry counter: {validator.phase_gate_retries}")

        assert can_proceed is False, "FAIL: Debe bloquear"
        assert "atlas/tareas" in missing, "FAIL: tareas debe estar en missing"
        assert validator.phase_gate_retries.get("atlas/tareas") == 2, "FAIL: Counter debe ser 2"
        assert "BLOQUEADA" in message, "FAIL: Debe ser BLOQUEADA"
        print("[OK] PASS: TEST 2 OK -- Segundo intento, counter=2")


def test_tercero_escalacion():
    """Test 3: Tercer intento — ESCALACIÓN (no re-delega)"""
    print("\n" + "="*70)
    print("TEST 3: TERCER INTENTO -- ESCALACION (max reintentos alcanzado)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pipeline_dir = project_root / ".pipeline"
        pipeline_dir.mkdir()

        validator = AntiLoopValidator(project_root)

        # Simular primer intento
        validator.enforce_phase_gate("atlas", "fase_2", ["atlas/tareas"])

        # Simular segundo intento
        validator.enforce_phase_gate("atlas", "fase_2", ["atlas/tareas"])
        assert validator.phase_gate_retries.get("atlas/tareas") == 2

        # Tercer intento
        can_proceed, message, missing = validator.enforce_phase_gate(
            "atlas", "fase_2", ["atlas/tareas"]
        )

        print(f"Setup: Ya pasaron 2 intentos, counter=2")
        print(f"Result: can_proceed={can_proceed}")
        print(f"Message: {message}")
        print(f"Retry counter: {validator.phase_gate_retries}")

        assert can_proceed is False, "FAIL: Debe bloquear"
        assert "ESCALACION" in message, f"FAIL: Debe tener ESCALACION, recibio: {message}"
        assert "atlas/tareas" not in missing, "FAIL: NO debe estar en missing (es escalacion)"
        assert "intento 3" in message, "FAIL: Debe mencionar intento 3"
        print("[OK] PASS: TEST 3 OK -- Tercer intento = ESCALACION")


def test_recovery():
    """Test 4: Recovery — cajon aparece, counter se resetea"""
    print("\n" + "="*70)
    print("TEST 4: RECOVERY -- cajon aparece, counter=0 (reset)")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        pipeline_dir = project_root / ".pipeline"
        pipeline_dir.mkdir()

        validator = AntiLoopValidator(project_root)

        # Simular intento 1
        validator.enforce_phase_gate("atlas", "fase_2", ["atlas/tareas"])
        assert validator.phase_gate_retries.get("atlas/tareas") == 1

        # Crear archivo (recovery)
        (pipeline_dir / "tareas.md").write_text("tareas content")

        # Intento 2 — ahora cajon existe
        can_proceed, message, missing = validator.enforce_phase_gate(
            "atlas", "fase_2", ["atlas/tareas"]
        )

        print(f"Setup: Counter=1 tras intento 1")
        print(f"Action: Crear .pipeline/tareas.md")
        print(f"Result: can_proceed={can_proceed}")
        print(f"Retry counter after: {validator.phase_gate_retries}")

        assert can_proceed is True, "FAIL: Debe permitir (cajon existe)"
        assert "Phase Gate OK" in message, "FAIL: Debe ser OK"
        assert "atlas/tareas" not in validator.phase_gate_retries, "FAIL: Counter debe ser removido"
        print("[OK] PASS: TEST 4 OK -- Recovery, counter reset")


def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1A.12: Anti-loop Tracking Enforcement")
    print("="*70)

    try:
        test_primer_intento()
        test_segundo_intento()
        test_tercero_escalacion()
        test_recovery()

        print("\n" + "="*70)
        print("ALL TESTS PASSED [OK]")
        print("="*70)
        print("\nCONCLUSION:")
        print("[OK] Anti-loop tracking funciona correctamente")
        print("[OK] Intento 1-2: missing cajones, incrementa counter")
        print("[OK] Intento 3+: ESCALACION (no re-delega)")
        print("[OK] Recovery: si cajon aparece, counter reset a 0")
        print("\nNo mas reintentos infinitos -- fase bloquea y escala a usuario.")

    except AssertionError as e:
        print(f"\n[FAIL] ASSERTION FAILED: {e}")
        raise


if __name__ == "__main__":
    main()
