#!/usr/bin/env python3
"""
Bloque F1.1 - Envelope contract (Pydantic model)
==================================================

Verifica el contrato `Envelope.v1` de forma aislada del dispatcher:
- Shape: campos obligatorios, opcionales, defaults
- Version literal
- Status enum (todos los strings historicos aceptados)
- Coercion dict -> Envelope, Envelope -> Envelope, tipos invalidos
- to_legacy_dict preserva extras y excluye None
- Roundtrip dict -> Envelope -> dict
- Fields 1L (design_intelligence, references, editorial_compliance, etc.)
- pre_return_audit (1A.14)
- agent field (PENDING-1L3-2 preparado)

NO testea el dispatcher (eso lo cubre bloque-F11-5).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from contracts import (  # noqa: E402
    Envelope,
    EnvelopeMode,
    EnvelopeStatus,
    ENVELOPE_VERSION,
    coerce_envelope,
    to_legacy_dict,
    ContractValidationError,
    LegacyShapeError,
)


# =====================================================================
#  Shape basico
# =====================================================================

class TestEnvelopeShape(unittest.TestCase):

    def test_construct_empty_envelope(self):
        # Contrato v1 es permisivo: ningun campo es required.
        env = Envelope()
        self.assertEqual(env.contract_version, "envelope.v1")
        self.assertIsNone(env.status)
        self.assertIsNone(env.tarea)
        self.assertIsNone(env.archivos)
        self.assertIsNone(env.engram)

    def test_construct_minimal_envelope(self):
        env = Envelope(
            status="completado",
            tarea="x",
            archivos=[],
            engram="proyecto/cajon",
            verificacion="none",
        )
        self.assertEqual(env.status, "completado")
        self.assertEqual(env.tarea, "x")
        self.assertEqual(env.archivos, [])
        self.assertEqual(env.engram, "proyecto/cajon")

    def test_optional_fields_default_none(self):
        env = Envelope(status="completado")
        self.assertIsNone(env.servidor)
        self.assertIsNone(env.bloqueadores)
        self.assertIsNone(env.pre_return_audit)
        self.assertIsNone(env.design_intelligence)
        self.assertIsNone(env.references)
        self.assertIsNone(env.references_used)
        self.assertIsNone(env.editorial_compliance)
        self.assertIsNone(env.agent)


# =====================================================================
#  Versionado
# =====================================================================

class TestEnvelopeVersion(unittest.TestCase):

    def test_default_version(self):
        self.assertEqual(Envelope().contract_version, ENVELOPE_VERSION)
        self.assertEqual(ENVELOPE_VERSION, "envelope.v1")

    def test_correct_version_explicit_passes(self):
        env = Envelope(contract_version="envelope.v1")
        self.assertEqual(env.contract_version, "envelope.v1")

    def test_other_version_rejected(self):
        # Pydantic Literal validation
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Envelope(contract_version="envelope.v2")


# =====================================================================
#  Status enum
# =====================================================================

class TestEnvelopeStatus(unittest.TestCase):

    def test_all_historical_statuses_accepted(self):
        for status_str in ("completado", "fallido", "PASS", "FAIL",
                           "CERTIFIED", "NEEDS WORK"):
            env = Envelope(status=status_str)
            self.assertEqual(env.status, status_str)

    def test_status_enum_values_match(self):
        # El enum cubre exactamente los strings historicos.
        expected = {"completado", "fallido", "PASS", "FAIL",
                    "CERTIFIED", "NEEDS WORK"}
        actual = {member.value for member in EnvelopeStatus}
        self.assertEqual(actual, expected)

    def test_status_is_optional(self):
        # Por contrato v1, status es Optional (el dispatcher decide
        # requeridos por modo).
        env = Envelope()
        self.assertIsNone(env.status)

    def test_arbitrary_status_string_accepted_per_v1_permissive(self):
        # v1 acepta status como Optional[str], NO restringe al enum a
        # nivel contrato. La restriccion es del dispatcher por modo.
        env = Envelope(status="custom-status-xyz")
        self.assertEqual(env.status, "custom-status-xyz")


# =====================================================================
#  Mode enum (uso opcional para callers type-safe)
# =====================================================================

class TestEnvelopeMode(unittest.TestCase):

    def test_mode_enum_values(self):
        expected = {"standard", "qa_strict", "dev_strict", "design_strict"}
        actual = {m.value for m in EnvelopeMode}
        self.assertEqual(actual, expected)


# =====================================================================
#  extra="allow"
# =====================================================================

class TestEnvelopeExtras(unittest.TestCase):

    def test_unknown_field_preserved(self):
        env = Envelope(status="completado", custom_extra_field="value123")
        d = env.to_legacy_dict()
        self.assertEqual(d.get("custom_extra_field"), "value123")

    def test_dispatcher_warnings_can_be_set_post_validate(self):
        # validate_assignment=True; un dict legacy puede tener
        # _dispatcher_warnings pre-existentes
        env = coerce_envelope({"status": "completado", "_dispatcher_warnings": ["w1"]})
        d = env.to_legacy_dict()
        self.assertIn("_dispatcher_warnings", d)


# =====================================================================
#  Roundtrip dict <-> model
# =====================================================================

class TestEnvelopeRoundtrip(unittest.TestCase):

    def test_dict_to_model_to_dict_preserves_known_fields(self):
        original = {
            "status": "completado",
            "tarea": "test task",
            "archivos": ["a.py", "b.py"],
            "engram": "p/c",
            "verificacion": "layout",
            "bloqueadores": [],
            "notas": "all good",
        }
        env = coerce_envelope(original)
        d = to_legacy_dict(env)
        for k, v in original.items():
            self.assertEqual(d.get(k), v, f"key {k!r} mismatch")

    def test_roundtrip_preserves_extras(self):
        original = {
            "status": "completado",
            "custom_a": 1,
            "custom_b": [1, 2, 3],
            "custom_c": {"nested": True},
        }
        env = coerce_envelope(original)
        d = to_legacy_dict(env)
        self.assertEqual(d.get("custom_a"), 1)
        self.assertEqual(d.get("custom_b"), [1, 2, 3])
        self.assertEqual(d.get("custom_c"), {"nested": True})

    def test_roundtrip_none_fields_excluded(self):
        env = coerce_envelope({"status": "completado"})
        d = to_legacy_dict(env)
        # status estaba -> aparece
        self.assertIn("status", d)
        # tarea NO estaba -> excluido (exclude_none=True)
        self.assertNotIn("tarea", d)
        self.assertNotIn("archivos", d)


# =====================================================================
#  Coercion: dict / Envelope / tipos invalidos
# =====================================================================

class TestCoercion(unittest.TestCase):

    def test_coerce_dict_returns_envelope(self):
        env = coerce_envelope({"status": "completado"})
        self.assertIsInstance(env, Envelope)
        self.assertEqual(env.status, "completado")

    def test_coerce_envelope_instance_passthrough(self):
        orig = Envelope(status="completado")
        result = coerce_envelope(orig)
        self.assertIs(result, orig)

    def test_coerce_none_raises_contract_validation_error(self):
        with self.assertRaises(ContractValidationError):
            coerce_envelope(None)

    def test_coerce_string_raises_contract_validation_error(self):
        with self.assertRaises(ContractValidationError):
            coerce_envelope("not-a-dict")

    def test_coerce_int_raises_contract_validation_error(self):
        with self.assertRaises(ContractValidationError):
            coerce_envelope(42)

    def test_coerce_list_raises_contract_validation_error(self):
        with self.assertRaises(ContractValidationError):
            coerce_envelope([1, 2, 3])

    def test_to_legacy_dict_non_envelope_raises(self):
        with self.assertRaises(ContractValidationError):
            to_legacy_dict({"not": "an envelope"})  # type: ignore[arg-type]

    def test_bad_shape_raises_legacy_shape_error(self):
        # Pasamos un valor que SI dispara ValidationError (wrong type
        # estricto: lista esperada como list, pasamos str).
        with self.assertRaises(LegacyShapeError) as ctx:
            coerce_envelope({"status": "completado", "archivos": "not-a-list"})
        # Errores en formato legacy List[str]
        self.assertIsInstance(ctx.exception.errors, list)
        self.assertTrue(len(ctx.exception.errors) > 0)
        joined = "\n".join(ctx.exception.errors)
        self.assertIn("archivos", joined)


# =====================================================================
#  Campos especificos de bloques posteriores
# =====================================================================

class TestEnvelope1LFields(unittest.TestCase):

    def test_design_intelligence_field(self):
        env = Envelope(design_intelligence={
            "queried": True,
            "queries": ["x"],
            "results_used": ["y"],
            "decisions_referenced": {"k": "v"},
        })
        self.assertEqual(env.design_intelligence["queried"], True)

    def test_references_field(self):
        env = Envelope(references=[
            {"url": "https://a.com", "rationale": "ten char min", "take": ["x"]}
        ])
        self.assertEqual(len(env.references), 1)
        self.assertEqual(env.references[0]["url"], "https://a.com")

    def test_references_used_field(self):
        env = Envelope(references_used=["https://a.com"])
        self.assertEqual(env.references_used, ["https://a.com"])

    def test_editorial_compliance_field(self):
        ec = {
            "asymmetric_section": {"present": True, "where": "hero",
                                   "rationale": "x" * 30},
            "typography_mix": {"display": "Serif", "body": "Sans",
                               "justified": True},
            "references_cited": ["https://a.com"],
            "boilerplate_avoided": {"explained": "y" * 30},
            "whitespace_intentional": {"documented": True},
        }
        env = Envelope(editorial_compliance=ec)
        self.assertEqual(env.editorial_compliance["asymmetric_section"]["where"], "hero")

    def test_brand_and_brand_style_fields(self):
        env = Envelope(brand={"style": "editorial-raw"}, brand_style="editorial-raw")
        self.assertEqual(env.brand["style"], "editorial-raw")
        self.assertEqual(env.brand_style, "editorial-raw")

    def test_pre_return_audit_field(self):
        env = Envelope(pre_return_audit={"ok": True, "summary": {}})
        self.assertEqual(env.pre_return_audit["ok"], True)

    def test_agent_field_present_in_contract(self):
        # PENDING-1L3-2: agent field reservado en contrato v1 (no enforced).
        env = Envelope(agent="ui-designer")
        self.assertEqual(env.agent, "ui-designer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
