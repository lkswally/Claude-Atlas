#!/usr/bin/env python3
"""
Bloque Envelope Casing — Architecture Repair 01
=============================================================================

Gap demostrado: Architecture Reality Audit V1 encontro que
ATLASDispatcher.validate_return_envelope() exige claves lowercase
("status", "tarea", "engram") mientras que TODOS los contratos de agente
(.claude/agents/*.md, agent-protocol.md — 27 archivos) documentan el
Return Envelope con claves UPPERCASE (STATUS, TAREA, ARCHIVOS, ENGRAM,
VERIFICACION, BLOQUEADORES, NOTAS). Ningun archivo de agente documenta el
envelope en lowercase. Un envelope construido exactamente como lo muestra
cualquier contrato de agente era rechazado como "campos requeridos
faltantes", pese a estar bien formado.

Fix: normalizacion de claves in-place al entrar a validate_return_envelope
(alias lowercase agregado al mismo dict, sin eliminar la clave original,
preservando la referencia del caller). Duplicados con valores en conflicto
(ej. STATUS="PASS" + status="FAIL" en el mismo envelope) se rechazan
explicitamente como AMBIGUOUS_ENVELOPE_KEY, no se resuelven en silencio.

Este suite llama al metodo REAL del dispatcher (no una reimplementacion),
usando dicts construidos igual que los ejemplos reales de los contratos de
agente — es la frontera de integracion real tal como existe hoy en el
codebase (no existe, ni existia antes de este fix, un parser que convierta
markdown "STATUS: ..." crudo en dict; el caller siempre construye el dict
el mismo — validar ese dict via el metodo real ES la integracion real).

Total: 10 tests requeridos por el mandato del fix + 1 check de referencia
preservada (no se rompe el patron F1.1 de mutacion in-place).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from atlas_dispatcher import ATLASDispatcher  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def get_dispatcher() -> ATLASDispatcher:
    return ATLASDispatcher(project_root=str(PROJECT_ROOT))


def test_01_uppercase_documented_envelope():
    """Exact documented shape from every agent contract -> must validate."""
    d = get_dispatcher()
    env = {
        "STATUS": "completado",
        "TAREA": "fixture",
        "ARCHIVOS": ["src/example.ts"],
        "ENGRAM": "fixture/task",
        "VERIFICACION": "none",
        "BLOQUEADORES": [],
        "NOTAS": "",
    }
    is_valid, errors = d.validate_return_envelope(env)
    if is_valid:
        ok("01 uppercase documented envelope validates", f"errors={errors}")
    else:
        fail("01 uppercase documented envelope validates", f"errors={errors}")


def test_02_existing_lowercase_backward_compat():
    """Pre-fix lowercase dicts (used by existing _qa suites) must keep working."""
    d = get_dispatcher()
    env = {"status": "completado", "tarea": "x", "archivos": [], "engram": "proj/cajon"}
    is_valid, errors = d.validate_return_envelope(env)
    if is_valid:
        ok("02 lowercase envelope backward-compat", f"errors={errors}")
    else:
        fail("02 lowercase envelope backward-compat", f"errors={errors}")


def test_03_mixed_non_conflicting():
    """Mixed casing, no key collision -> must validate (documented behavior)."""
    d = get_dispatcher()
    env = {"STATUS": "completado", "tarea": "x", "archivos": [], "ENGRAM": "p/c"}
    is_valid, errors = d.validate_return_envelope(env)
    if is_valid:
        ok("03 mixed non-conflicting envelope validates", f"errors={errors}")
    else:
        fail("03 mixed non-conflicting envelope validates", f"errors={errors}")


def test_04_conflicting_duplicate_rejected():
    """STATUS='PASS' and status='FAIL' in the same envelope -> explicit FAIL, never silently resolved."""
    d = get_dispatcher()
    env = {"STATUS": "PASS", "status": "FAIL", "tarea": "x", "archivos": [], "engram": "p/c"}
    is_valid, errors = d.validate_return_envelope(env)
    has_ambiguous = any("AMBIGUOUS_ENVELOPE_KEY" in e for e in errors)
    if (not is_valid) and has_ambiguous:
        ok("04 conflicting STATUS/status rejected explicitly", f"errors={errors}")
    else:
        fail("04 conflicting STATUS/status rejected explicitly", f"valid={is_valid} errors={errors}")


def test_05_missing_required_field():
    """Missing ENGRAM -> must still FAIL after normalization (validation not weakened)."""
    d = get_dispatcher()
    env = {"STATUS": "completado", "TAREA": "x"}
    is_valid, errors = d.validate_return_envelope(env)
    if (not is_valid) and any("engram" in e for e in errors):
        ok("05 missing required field (ENGRAM) still FAILs", f"errors={errors}")
    else:
        fail("05 missing required field (ENGRAM) still FAILs", f"valid={is_valid} errors={errors}")


def test_06_invalid_status_value():
    """STATUS with a value outside the valid set -> must still FAIL."""
    d = get_dispatcher()
    env = {"STATUS": "maybe", "TAREA": "x", "ENGRAM": "p/c"}
    is_valid, errors = d.validate_return_envelope(env)
    if not is_valid:
        ok("06 invalid STATUS value still FAILs", f"errors={errors}")
    else:
        fail("06 invalid STATUS value still FAILs", f"valid={is_valid} errors={errors}")


def test_07_archivos_wrong_type():
    """ARCHIVOS as a string instead of a list -> must still FAIL."""
    d = get_dispatcher()
    env = {"STATUS": "completado", "TAREA": "x", "ARCHIVOS": "not-a-list", "ENGRAM": "p/c"}
    is_valid, errors = d.validate_return_envelope(env)
    if not is_valid:
        ok("07 ARCHIVOS wrong type still FAILs", f"errors={errors}")
    else:
        fail("07 ARCHIVOS wrong type still FAILs", f"valid={is_valid} errors={errors}")


def test_08_optional_fields_handled():
    """NOTAS/VERIFICACION/BLOQUEADORES omitted (optional per contract) -> must still validate."""
    d = get_dispatcher()
    env = {"STATUS": "completado", "TAREA": "x", "ARCHIVOS": [], "ENGRAM": "p/c"}
    is_valid, errors = d.validate_return_envelope(env)
    if is_valid:
        ok("08 optional fields omitted still validates", f"errors={errors}")
    else:
        fail("08 optional fields omitted still validates", f"errors={errors}")


def test_09_real_sample_from_agent_contract():
    """Envelope shaped exactly like security-engineer.md's own documented example."""
    d = get_dispatcher()
    # Copied in spirit from .claude/agents/security-engineer.md's own
    # "Ejemplo de NOTAS" + Return Envelope block.
    env = {
        "STATUS": "completado",
        "TAREA": "Security Spec para mi-proyecto, 3 amenazas criticas, 7 headers, OWASP: A01 A03 A05",
        "ARCHIVOS": [],
        "ENGRAM": "mi-proyecto/security-spec",
        "NOTAS": "",
    }
    is_valid, errors = d.validate_return_envelope(env)
    if is_valid:
        ok("09 real sample from security-engineer.md validates", f"errors={errors}")
    else:
        fail("09 real sample from security-engineer.md validates", f"errors={errors}")


def test_10_no_regression_strict_modes():
    """qa_strict/dev_strict/design_strict: identical verdict for the same
    envelope regardless of casing -- proves normalization doesn't change
    what these modes actually enforce, only which spelling of the keys
    they accept."""
    d = get_dispatcher()
    all_match = True
    details = []

    qa_upper = {"STATUS": "PASS", "TAREA": "1", "ENGRAM": "p/qa-1"}
    qa_lower = {"status": "PASS", "tarea": "1", "engram": "p/qa-1"}
    r_u = d.validate_return_envelope(dict(qa_upper), mode="qa_strict")
    r_l = d.validate_return_envelope(dict(qa_lower), mode="qa_strict")
    if r_u != r_l:
        all_match = False
        details.append(f"qa_strict mismatch: upper={r_u} lower={r_l}")

    dev_upper = {"STATUS": "completado", "TAREA": "x", "ARCHIVOS": ["a.ts"], "ENGRAM": "p/c"}
    dev_lower = {"status": "completado", "tarea": "x", "archivos": ["a.ts"], "engram": "p/c"}
    r_du = d.validate_return_envelope(dict(dev_upper), mode="dev_strict")
    r_dl = d.validate_return_envelope(dict(dev_lower), mode="dev_strict")
    if r_du != r_dl:
        all_match = False
        details.append(f"dev_strict mismatch: upper={r_du} lower={r_dl}")

    ds_upper = {"STATUS": "completado", "TAREA": "x", "ARCHIVOS": [], "ENGRAM": "p/c"}
    ds_lower = {"status": "completado", "tarea": "x", "archivos": [], "engram": "p/c"}
    r_su = d.validate_return_envelope(dict(ds_upper), mode="design_strict")
    r_sl = d.validate_return_envelope(dict(ds_lower), mode="design_strict")
    if r_su != r_sl:
        all_match = False
        details.append(f"design_strict mismatch: upper={r_su} lower={r_sl}")

    if all_match:
        ok("10 qa_strict/dev_strict/design_strict casing-independent", "; ".join(details) or "all identical")
    else:
        fail("10 qa_strict/dev_strict/design_strict casing-independent", "; ".join(details))


def test_11_reference_preserved_in_place():
    """Normalization must mutate the caller's dict in place (same object
    identity), matching the existing Bloque F1.1 contract — not replace it
    with a new dict, or downstream mutations (_dispatcher_warnings, etc.)
    would stop reaching the caller."""
    d = get_dispatcher()
    caller_dict = {"STATUS": "completado", "TAREA": "x", "ARCHIVOS": [], "ENGRAM": "p/c"}
    before_id = id(caller_dict)
    d.validate_return_envelope(caller_dict)
    same_object = id(caller_dict) == before_id
    alias_landed = "status" in caller_dict and caller_dict["status"] == "completado"
    if same_object and alias_landed:
        ok("11 normalization mutates caller dict in place", f"lowercase alias present: {alias_landed}")
    else:
        fail("11 normalization mutates caller dict in place", f"same_object={same_object} alias_landed={alias_landed}")


def main():
    print("=" * 60)
    print("Bloque Envelope Casing -- Architecture Repair 01")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_01_uppercase_documented_envelope()
    test_02_existing_lowercase_backward_compat()
    test_03_mixed_non_conflicting()
    test_04_conflicting_duplicate_rejected()
    test_05_missing_required_field()
    test_06_invalid_status_value()
    test_07_archivos_wrong_type()
    test_08_optional_fields_handled()
    test_09_real_sample_from_agent_contract()
    test_10_no_regression_strict_modes()
    test_11_reference_preserved_in_place()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()

    if FAIL_COUNT > 0:
        print("RESULTADO: FAIL")
        sys.exit(1)
    else:
        print("RESULTADO: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
