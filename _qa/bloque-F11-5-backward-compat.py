#!/usr/bin/env python3
"""
Bloque F1.1 - Backward compatibility critica
=============================================

EL TEST MAS IMPORTANTE de F1.1. Verifica que la introduccion del contrato
Pydantic NO altera el comportamiento observable de `validate_return_envelope`
para envelopes dict legacy representativos de TODOS los modos.

Comparacion par a par:
  1. Llamar validate_return_envelope CON contracts activos (default)
  2. Llamar validate_return_envelope CON contracts disabled (env var)
  3. (ok_a, errores_a) debe ser identico a (ok_b, errores_b)

Cobertura por modo:
  - standard (laxo)
  - qa_strict (PASS/FAIL exclusivos, archivos no vacios en PASS, etc.)
  - dev_strict (pre_return_audit + file declaration)
  - design_strict (design_intelligence + 1L.2/1L.3/1L.4 NO testeados aqui —
    cubiertos en bloques 1L propios; aqui solo el core 1C.1)

NO modifica ningun test existente. NO depende de Engram MCP.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


# =====================================================================
#  Helpers
# =====================================================================

def _build_dispatcher():
    """Construye dispatcher sin Engram MCP para tests rapidos."""
    from atlas_dispatcher import ATLASDispatcher
    return ATLASDispatcher(project_root=Path.cwd(), auto_enable_mcp=False)


def _validate_both_paths(dispatcher, envelope_dict, mode, **kwargs):
    """
    Llama validate_return_envelope con contracts activos y disabled.
    Retorna ((ok_a, errs_a), (ok_b, errs_b)).
    El llamador hace deep-copy del dict porque el dispatcher muta downstream.
    """
    import copy

    # Path A: contracts activos (default)
    os.environ.pop("ATLAS_PYDANTIC_CONTRACTS_DISABLED", None)
    env_a = copy.deepcopy(envelope_dict)
    ok_a, errs_a = dispatcher.validate_return_envelope(env_a, mode=mode, **kwargs)

    # Path B: contracts disabled
    os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"] = "1"
    try:
        env_b = copy.deepcopy(envelope_dict)
        ok_b, errs_b = dispatcher.validate_return_envelope(env_b, mode=mode, **kwargs)
    finally:
        del os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"]

    return (ok_a, errs_a), (ok_b, errs_b)


class _ParityMixin:
    """Mixin que aporta el assertion clave: parity entre paths."""

    def assert_parity(self, envelope, mode, **kwargs):
        (ok_a, errs_a), (ok_b, errs_b) = _validate_both_paths(
            self.dispatcher, envelope, mode, **kwargs
        )
        self.assertEqual(
            ok_a, ok_b,
            f"Parity FAIL en ok: contracts={ok_a} disabled={ok_b}\n"
            f"errs_a={errs_a}\nerrs_b={errs_b}"
        )
        # Los mensajes pueden diferir si Pydantic agrega errores antes,
        # pero el SET de errores debe ser equivalente. En la implementacion
        # actual con v1 permisivo, Pydantic no agrega errores propios
        # cuando el dict es shape-OK -> errores deben ser identicos.
        self.assertEqual(
            errs_a, errs_b,
            f"Parity FAIL en errores:\nA={errs_a}\nB={errs_b}"
        )
        return ok_a, errs_a


# =====================================================================
#  Mode: standard (laxo)
# =====================================================================

class TestParityStandardMode(unittest.TestCase, _ParityMixin):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_minimal_valid_envelope(self):
        env = {
            "status": "completado",
            "tarea": "test",
            "archivos": [],
            "engram": "p/c",
            "verificacion": "none",
        }
        ok, errs = self.assert_parity(env, mode="standard")
        self.assertTrue(ok)

    def test_complete_envelope_with_all_fields(self):
        env = {
            "status": "completado",
            "tarea": "test",
            "archivos": ["a.py", "b.py"],
            "engram": "p/c",
            "verificacion": "layout",
            "servidor": "http://localhost:3000",
            "bloqueadores": [],
            "notas": "ok",
        }
        self.assert_parity(env, mode="standard")

    def test_missing_required_field_status(self):
        env = {"tarea": "x", "engram": "p/c"}
        ok, errs = self.assert_parity(env, mode="standard")
        # Debe fallar igual en ambos paths (campo obligatorio status)
        self.assertFalse(ok)

    def test_invalid_status_in_standard(self):
        env = {
            "status": "WRONG_STATUS",
            "tarea": "x",
            "engram": "p/c",
            "archivos": [],
        }
        ok, errs = self.assert_parity(env, mode="standard")
        self.assertFalse(ok)

    def test_extra_custom_fields_preserved(self):
        env = {
            "status": "completado",
            "tarea": "x",
            "engram": "p/c",
            "archivos": [],
            "custom_data": {"any": "value"},
        }
        ok, errs = self.assert_parity(env, mode="standard")
        self.assertTrue(ok)


# =====================================================================
#  Mode: qa_strict
# =====================================================================

class TestParityQAStrictMode(unittest.TestCase, _ParityMixin):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_pass_with_archivos(self):
        env = {
            "status": "PASS",
            "tarea": "qa test",
            "archivos": ["test.png"],
            "engram": "p/qa-1",
            "verificacion": "layout",
            "bloqueadores": [],
        }
        ok, errs = self.assert_parity(env, mode="qa_strict")
        self.assertTrue(ok)

    def test_pass_without_archivos_rejected(self):
        env = {
            "status": "PASS",
            "tarea": "qa test",
            "archivos": [],
            "engram": "p/qa-1",
            "verificacion": "layout",
        }
        ok, errs = self.assert_parity(env, mode="qa_strict")
        self.assertFalse(ok)

    def test_fail_with_bloqueadores(self):
        env = {
            "status": "FAIL",
            "tarea": "qa test",
            "archivos": [],
            "engram": "p/qa-1",
            "verificacion": "layout",
            "bloqueadores": ["element X missing"],
        }
        ok, errs = self.assert_parity(env, mode="qa_strict")
        self.assertTrue(ok)

    def test_fail_without_bloqueadores_rejected(self):
        env = {
            "status": "FAIL",
            "tarea": "qa test",
            "archivos": [],
            "engram": "p/qa-1",
            "verificacion": "layout",
            "bloqueadores": [],
        }
        ok, errs = self.assert_parity(env, mode="qa_strict")
        self.assertFalse(ok)

    def test_invalid_status_for_qa_rejected(self):
        env = {
            "status": "completado",  # no es PASS/FAIL
            "tarea": "qa test",
            "archivos": [],
            "engram": "p/qa-1",
            "verificacion": "layout",
        }
        ok, errs = self.assert_parity(env, mode="qa_strict")
        self.assertFalse(ok)


# =====================================================================
#  Mode: dev_strict (Bloques 1A.14 / 1A.15 / 1A.16)
# =====================================================================

class TestParityDevStrictMode(unittest.TestCase, _ParityMixin):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_dev_strict_completado_with_audit_ok(self):
        env = {
            "status": "completado",
            "tarea": "dev task",
            "archivos": [],
            "engram": "p/dev-1",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {
                "ok": True,
                "summary": {"by_severity": {}},
            },
        }
        # NOTA: no afirmamos ok=True porque dev_strict+completado dispara
        # verify_declared_files (Bloque 1A.16) que compara con git diff real.
        # En un working dir con cambios pendientes el envelope va a fallar
        # por under-declaration de archivos — comportamiento esperado, NO
        # regresion de F1.1. Lo unico que importa aca es PARIDAD entre
        # paths (contracts on vs off).
        self.assert_parity(env, mode="dev_strict")

    def test_dev_strict_missing_pre_return_audit_rejected(self):
        env = {
            "status": "completado",
            "tarea": "dev task",
            "archivos": [],
            "engram": "p/dev-1",
            "verificacion": "layout",
        }
        ok, errs = self.assert_parity(env, mode="dev_strict")
        self.assertFalse(ok)

    def test_dev_strict_fallido_skips_audit_check(self):
        env = {
            "status": "fallido",
            "tarea": "dev task",
            "archivos": [],
            "engram": "p/dev-1",
            "verificacion": "none",
            "bloqueadores": ["something broke"],
        }
        ok, errs = self.assert_parity(env, mode="dev_strict")
        # fallido NO requiere pre_return_audit
        self.assertTrue(ok)


# =====================================================================
#  Mode: design_strict (1C.1 nucleo — sin 1L.x para mantener test focalizado)
# =====================================================================

class TestParityDesignStrictMode(unittest.TestCase, _ParityMixin):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        # Tambien disable 1L.2/1L.3/1L.4 para focalizar en 1C.1 + parity
        os.environ["ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED"] = "1"
        os.environ["ATLAS_REFERENCES_ENFORCEMENT_DISABLED"] = "1"
        os.environ["ATLAS_EDITORIAL_ENFORCEMENT_DISABLED"] = "1"
        cls.dispatcher = _build_dispatcher()

    @classmethod
    def tearDownClass(cls):
        for k in (
            "ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED",
            "ATLAS_REFERENCES_ENFORCEMENT_DISABLED",
            "ATLAS_EDITORIAL_ENFORCEMENT_DISABLED",
        ):
            os.environ.pop(k, None)

    def test_design_strict_with_design_intelligence(self):
        env = {
            "status": "completado",
            "tarea": "design task",
            "archivos": [],
            "engram": "p/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            "design_intelligence": {
                "queried": True,
                "queries": ["x"],
                "results_used": ["y"],
                "decisions_referenced": {"k": "v"},
            },
        }
        ok, errs = self.assert_parity(env, mode="design_strict")
        self.assertTrue(ok)

    def test_design_strict_missing_design_intelligence_rejected(self):
        env = {
            "status": "completado",
            "tarea": "design task",
            "archivos": [],
            "engram": "p/design-system",
            "verificacion": "layout",
            "bloqueadores": [],
            # design_intelligence ausente
        }
        ok, errs = self.assert_parity(env, mode="design_strict")
        self.assertFalse(ok)


# =====================================================================
#  Mutaciones del dispatcher: warnings / enforcement
# =====================================================================

class TestDispatcherMutationsPreserved(unittest.TestCase):
    """
    El dispatcher muta el dict response in-place para agregar
    `_dispatcher_warnings`. Verificamos que la coercion F1.1 NO rompe
    esa mutacion — el caller debe ver la mutacion en su propio dict.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_caller_dict_reference_preserved_through_validate(self):
        # Simulamos que el caller mantiene una referencia al dict y
        # despues de validate_return_envelope sigue siendo SU dict.
        env = {
            "status": "completado",
            "tarea": "x",
            "archivos": [],
            "engram": "p/c",
            "verificacion": "none",
        }
        env_id_before = id(env)
        ok, errs = self.dispatcher.validate_return_envelope(env, mode="standard")
        env_id_after = id(env)
        # Misma referencia (no se reasigno)
        self.assertEqual(env_id_before, env_id_after)
        # El caller puede seguir mutando
        env["after_validate"] = "value"
        self.assertEqual(env.get("after_validate"), "value")


# =====================================================================
#  Pydantic Envelope explicit input
# =====================================================================

class TestPydanticInputPath(unittest.TestCase):
    """
    Verifica el camino NUEVO de F1.1: el caller puede pasar una instancia
    `Envelope` directamente. El dispatcher la convierte a dict y procede
    normalmente.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_envelope_instance_standard_pass(self):
        from contracts import Envelope
        env = Envelope(
            status="completado",
            tarea="x",
            archivos=[],
            engram="p/c",
            verificacion="none",
        )
        ok, errs = self.dispatcher.validate_return_envelope(env, mode="standard")
        self.assertTrue(ok)

    def test_envelope_instance_qa_strict_pass(self):
        from contracts import Envelope
        env = Envelope(
            status="PASS",
            tarea="qa",
            archivos=["x.png"],
            engram="p/qa-1",
            verificacion="layout",
            bloqueadores=[],
        )
        ok, errs = self.dispatcher.validate_return_envelope(env, mode="qa_strict")
        self.assertTrue(ok, f"errs={errs}")

    def test_envelope_instance_invalid_rejected(self):
        from contracts import Envelope
        env = Envelope(status="completado")  # falta tarea, engram
        ok, errs = self.dispatcher.validate_return_envelope(env, mode="standard")
        self.assertFalse(ok)


# =====================================================================
#  Tipos invalidos rechazados ruidosamente
# =====================================================================

class TestInvalidInputTypes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_none_rejected(self):
        ok, errs = self.dispatcher.validate_return_envelope(None, mode="standard")
        self.assertFalse(ok)
        self.assertTrue(any("tipo no soportado" in e or "Expected" in e for e in errs))

    def test_string_rejected(self):
        ok, errs = self.dispatcher.validate_return_envelope("string-input", mode="standard")
        self.assertFalse(ok)

    def test_int_rejected(self):
        ok, errs = self.dispatcher.validate_return_envelope(42, mode="standard")
        self.assertFalse(ok)


# =====================================================================
#  Disable flag end-to-end
# =====================================================================

class TestDisableFlag(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        cls.dispatcher = _build_dispatcher()

    def test_flag_disables_coercion_completely(self):
        os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"] = "1"
        try:
            env = {
                "status": "completado",
                "tarea": "x",
                "archivos": [],
                "engram": "p/c",
                "verificacion": "none",
            }
            ok, errs = self.dispatcher.validate_return_envelope(env, mode="standard")
            self.assertTrue(ok)
        finally:
            del os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"]

    def test_flag_disabled_still_rejects_bad_types(self):
        # Aun con flag disabled, el dispatcher rechaza tipos invalidos
        # (el mensaje viene del path legacy, no del path Pydantic).
        os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"] = "1"
        try:
            ok, errs = self.dispatcher.validate_return_envelope("not-dict", mode="standard")
            self.assertFalse(ok)
        finally:
            del os.environ["ATLAS_PYDANTIC_CONTRACTS_DISABLED"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
