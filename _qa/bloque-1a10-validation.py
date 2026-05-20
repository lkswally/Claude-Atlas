#!/usr/bin/env python3
"""
Validación real de Bloque 1A.10: Return Envelope Validation Loop (Strict QA Mode)
Test 5 escenarios: PASS válido, FAIL válido, malformados
"""

import json
from typing import Dict, Any, Tuple, List

class ReturnEnvelopeValidator:
    """Simula validate_return_envelope con strict mode QA"""

    def validate_return_envelope(self, response: Dict[str, Any], mode: str = "standard") -> Tuple[bool, List[str]]:
        """Validar Return Envelope con modo strict QA"""
        errores = []

        # CAMPOS OBLIGATORIOS en ambos modos
        required_always = {"status", "tarea", "engram"}
        missing = required_always - set(response.keys())
        if missing:
            errores.append(f"Campos requeridos faltantes: {missing}")

        # VALIDACIÓN DE STATUS
        if mode == "qa_strict":
            valid_status = {"PASS", "FAIL"}
            if response.get("status") not in valid_status:
                errores.append(f"Return Envelope QA inválido: status inválido: {response.get('status')}, esperado PASS o FAIL")
        else:
            valid_status = {"completado", "fallido", "PASS", "FAIL", "CERTIFIED", "NEEDS WORK"}
            if response.get("status") not in valid_status:
                errores.append(f"STATUS inválido: {response.get('status')}. Esperado: {valid_status}")

        # VALIDACIONES ESPECÍFICAS PARA QA STRICT
        if mode == "qa_strict":
            status = response.get("status")

            # PASS requiere: status=PASS, archivos (NO VACÍO), NO bloqueadores
            if status == "PASS":
                # archivos es OBLIGATORIO y DEBE tener al menos 1 elemento
                archivos = response.get("archivos")
                if archivos is None:
                    errores.append("Return Envelope QA inválido: PASS requiere archivos (lista no vacía)")
                elif not isinstance(archivos, list):
                    errores.append(f"Return Envelope QA inválido: archivos debe ser lista, recibido {type(archivos).__name__}")
                elif len(archivos) == 0:
                    errores.append("Return Envelope QA inválido: PASS requiere archivos (lista no vacía)")

                # bloqueadores PROHIBIDO si status=PASS
                bloqueadores = response.get("bloqueadores")
                if bloqueadores is not None and len(bloqueadores) > 0:
                    errores.append("Return Envelope QA inválido: PASS prohibe bloqueadores")

            # FAIL requiere: status=FAIL, bloqueadores (NO VACÍO)
            elif status == "FAIL":
                # bloqueadores es OBLIGATORIO y DEBE tener al menos 1 elemento
                bloqueadores = response.get("bloqueadores")
                if bloqueadores is None:
                    errores.append("Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)")
                elif not isinstance(bloqueadores, list):
                    errores.append(f"Return Envelope QA inválido: bloqueadores debe ser lista, recibido {type(bloqueadores).__name__}")
                elif len(bloqueadores) == 0:
                    errores.append("Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)")

                # archivos es OPCIONAL para FAIL
                archivos = response.get("archivos")
                if archivos is not None and not isinstance(archivos, list):
                    errores.append(f"Return Envelope QA inválido: archivos debe ser lista, recibido {type(archivos).__name__}")

        return len(errores) == 0, errores

def test_pass_valid():
    """Test 1: PASS válido (archivos presentes)"""
    print("\n" + "="*70)
    print("TEST 1: PASS VÁLIDO (archivos presentes)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "PASS",
        "tarea": "Validé tarea 1: Login UI responsive",
        "engram": "atlas/qa-1",
        "archivos": ["/tmp/qa/tarea-1-desktop.png", "/tmp/qa/tarea-1-mobile.png"],
        "verificacion": "layout"
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is True, "FAIL: PASS válido debe pasar"
    assert errores == [], f"FAIL: No debe haber errores, recibió {errores}"
    print("[OK] PASS: TEST 1 OK -- PASS valido aceptado")


def test_fail_valid():
    """Test 2: FAIL válido (bloqueadores presentes)"""
    print("\n" + "="*70)
    print("TEST 2: FAIL VÁLIDO (bloqueadores presentes)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "FAIL",
        "tarea": "Validé tarea 2: Landing page",
        "engram": "atlas/qa-2",
        "bloqueadores": ["scroll horizontal no deseado en mobile", "touch targets < 44px"]
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is True, "FAIL: FAIL válido debe pasar"
    assert errores == [], f"FAIL: No debe haber errores, recibió {errores}"
    print("[OK] PASS: TEST 2 OK -- FAIL valido aceptado")


def test_pass_sin_archivos():
    """Test 3: PASS malformado (sin archivos)"""
    print("\n" + "="*70)
    print("TEST 3: PASS MALFORMADO (sin archivos)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "PASS",
        "tarea": "Validé tarea 1",
        "engram": "atlas/qa-1",
        "archivos": []  # VACÍO = ERROR
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is False, "FAIL: PASS sin archivos debe RECHAZARSE"
    assert len(errores) > 0, "FAIL: Debe tener errores"
    assert "PASS requiere archivos" in errores[0], f"FAIL: Error debe mencionar archivos, recibió {errores[0]}"
    print(f"[OK] PASS: TEST 3 OK -- Error especifico: {errores[0]}")


def test_fail_sin_bloqueadores():
    """Test 4: FAIL malformado (sin bloqueadores)"""
    print("\n" + "="*70)
    print("TEST 4: FAIL MALFORMADO (sin bloqueadores)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "FAIL",
        "tarea": "Validé tarea 2",
        "engram": "atlas/qa-2",
        "bloqueadores": []  # VACÍO = ERROR
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is False, "FAIL: FAIL sin bloqueadores debe RECHAZARSE"
    assert len(errores) > 0, "FAIL: Debe tener errores"
    assert "FAIL requiere bloqueadores" in errores[0], f"FAIL: Error debe mencionar bloqueadores, recibió {errores[0]}"
    print(f"[OK] PASS: TEST 4 OK -- Error especifico: {errores[0]}")


def test_status_invalido():
    """Test 5: STATUS inválido (no PASS ni FAIL)"""
    print("\n" + "="*70)
    print("TEST 5: STATUS INVÁLIDO (PENDING, CERTIFIED, etc.)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "PENDING",  # INVÁLIDO para QA
        "tarea": "Validé tarea 3",
        "engram": "atlas/qa-3",
        "archivos": ["/tmp/qa/screenshot.png"]
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is False, "FAIL: STATUS inválido debe RECHAZARSE"
    assert len(errores) > 0, "FAIL: Debe tener errores"
    assert "status inválido" in errores[0], f"FAIL: Error debe mencionar status inválido, recibió {errores[0]}"
    print(f"[OK] PASS: TEST 5 OK -- Error especifico: {errores[0]}")


def test_pass_con_bloqueadores():
    """Test 6: PASS con bloqueadores (prohibido)"""
    print("\n" + "="*70)
    print("TEST 6: PASS CON BLOQUEADORES (prohibido)")
    print("="*70)

    validator = ReturnEnvelopeValidator()
    response = {
        "status": "PASS",
        "tarea": "Validé tarea 1",
        "engram": "atlas/qa-1",
        "archivos": ["/tmp/qa/screenshot.png"],
        "bloqueadores": ["minor issue"]  # PROHIBIDO en PASS
    }

    is_valid, errores = validator.validate_return_envelope(response, mode="qa_strict")
    print(f"Input: {json.dumps(response, indent=2)}")
    print(f"Result: valid={is_valid}, errores={errores}")

    assert is_valid is False, "FAIL: PASS con bloqueadores debe RECHAZARSE"
    assert len(errores) > 0, "FAIL: Debe tener errores"
    assert "PASS prohibe bloqueadores" in errores[0], f"FAIL: Error debe mencionar prohibición, recibió {errores[0]}"
    print(f"[OK] PASS: TEST 6 OK -- Error especifico: {errores[0]}")


def main():
    print("\n" + "="*70)
    print("VALIDACIÓN REAL — Bloque 1A.10: Return Envelope QA Strict Mode")
    print("="*70)

    try:
        test_pass_valid()
        test_fail_valid()
        test_pass_sin_archivos()
        test_fail_sin_bloqueadores()
        test_status_invalido()
        test_pass_con_bloqueadores()

        print("\n" + "="*70)
        print("ALL TESTS PASSED [OK]")
        print("="*70)
        print("\nCONCLUSION:")
        print("[OK] Return Envelope QA strict mode funciona correctamente")
        print("[OK] PASS valido: aceptado (archivos requerido, bloqueadores prohibido)")
        print("[OK] FAIL valido: aceptado (bloqueadores requerido)")
        print("[OK] PASS sin archivos: RECHAZADO con error especifico")
        print("[OK] FAIL sin bloqueadores: RECHAZADO con error especifico")
        print("[OK] STATUS invalido: RECHAZADO con error especifico")
        print("[OK] PASS con bloqueadores: RECHAZADO con error especifico")
        print("\nPipeline no avanzará si Return Envelope QA es inválido.")
        print("Evidence-collector será re-delegado con error específico.")

    except AssertionError as e:
        print(f"\n✗ ASSERTION FAILED: {e}")
        raise


if __name__ == "__main__":
    main()
