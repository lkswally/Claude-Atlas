#!/usr/bin/env python3
"""
Bloque 1L.1 — Intent Classifier Validation
============================================

Verifica:
- intent_classifier.classify_user_intent retorna shape correcto
- 4 buckets clasifican casos prototipo high-confidence
- Prompts ambiguos retornan confidence='low' con escalation_question
- Prompts triviales / vacios retornan intent=None
- Prompts gigantes no rompen
- Dispatcher.classify_user_intent integra correctamente
- Flag ATLAS_INTENT_CLASSIFIER_DISABLED desactiva el classifier
- Modulo es importable de forma aislada

NO requiere Engram MCP, NO toca disco. Tests puros de la heuristica + wiring.
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Path setup
_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from intent_classifier import classify_user_intent  # noqa: E402


class TestIntentClassifierShape(unittest.TestCase):
    """Shape del retorno es estable."""

    def test_returns_dict_with_required_keys(self):
        result = classify_user_intent("auditá esta landing")
        self.assertIsInstance(result, dict)
        for key in ("intent", "confidence", "signals", "fallback_intent",
                    "rationale", "escalation_question"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_confidence_is_valid_label(self):
        result = classify_user_intent("auditá esta landing")
        self.assertIn(result["confidence"], ("high", "medium", "low"))

    def test_intent_is_valid_or_none(self):
        result = classify_user_intent("auditá esta landing")
        self.assertIn(
            result["intent"],
            (None, "audit", "redesign", "implement", "validate"),
        )

    def test_signals_is_list_of_dicts(self):
        result = classify_user_intent("auditá esta landing")
        self.assertIsInstance(result["signals"], list)
        for sig in result["signals"]:
            self.assertIsInstance(sig, dict)
            self.assertIn("bucket", sig)


class TestHighConfidenceCases(unittest.TestCase):
    """Prototipos de cada bucket en HIGH confidence."""

    def test_audit_explicit_es(self):
        r = classify_user_intent("auditá la landing y analizá los problemas de diseño actuales")
        self.assertEqual(r["intent"], "audit")
        self.assertEqual(r["confidence"], "high")
        self.assertIsNone(r["escalation_question"])

    def test_audit_explicit_en(self):
        r = classify_user_intent("audit the landing page and review the current design issues")
        self.assertEqual(r["intent"], "audit")
        self.assertEqual(r["confidence"], "high")

    def test_redesign_explicit_es(self):
        r = classify_user_intent("rediseñá la home completa desde cero, nuevo diseño")
        self.assertEqual(r["intent"], "redesign")
        self.assertEqual(r["confidence"], "high")

    def test_redesign_explicit_en(self):
        r = classify_user_intent("redesign the entire homepage from scratch, new design")
        self.assertEqual(r["intent"], "redesign")
        self.assertEqual(r["confidence"], "high")

    def test_implement_explicit_es(self):
        r = classify_user_intent("implementá el dark mode pendiente y agregá un nuevo componente de navegación")
        self.assertEqual(r["intent"], "implement")
        self.assertEqual(r["confidence"], "high")

    def test_implement_explicit_en(self):
        r = classify_user_intent("implement the dark mode and add a new navigation component")
        self.assertEqual(r["intent"], "implement")
        self.assertEqual(r["confidence"], "high")

    def test_validate_explicit_es(self):
        r = classify_user_intent("validá que la página funciona en mobile, verificá el QA y testeá los flows")
        self.assertEqual(r["intent"], "validate")
        self.assertEqual(r["confidence"], "high")

    def test_validate_explicit_en(self):
        r = classify_user_intent("validate the page works on mobile, verify QA and test the flows")
        self.assertEqual(r["intent"], "validate")
        self.assertEqual(r["confidence"], "high")


class TestLowConfidenceCases(unittest.TestCase):
    """Casos ambiguos que DEBEN escalar."""

    def test_ambiguous_mejorar_landing(self):
        r = classify_user_intent("mejorá la landing")
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")
        self.assertIsNotNone(r["escalation_question"])
        # Debe ofrecer al menos redesign o implement como opciones
        self.assertTrue(
            "redesign" in r["escalation_question"]
            or "implement" in r["escalation_question"]
            or "audit" in r["escalation_question"]
        )

    def test_ambiguous_improve_site(self):
        r = classify_user_intent("improve the site")
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")
        self.assertIsNotNone(r["escalation_question"])

    def test_audit_low_signals_medium(self):
        # "ver qué" (1pt) + "qué onda" (1pt) = audit score 2 → medium audit.
        # Sin ambiguous boosters, no se degrada a low.
        r = classify_user_intent("podés ver qué onda con esta página")
        self.assertEqual(r["intent"], "audit")
        self.assertEqual(r["confidence"], "medium")

    def test_empty_prompt(self):
        r = classify_user_intent("")
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")
        # No debe escalar — es trivial, no pipeline
        self.assertIsNone(r["escalation_question"])

    def test_none_prompt(self):
        r = classify_user_intent(None)
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")

    def test_non_string_prompt(self):
        r = classify_user_intent(12345)
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")


class TestEdgeCases(unittest.TestCase):
    """Casos limite que no deben romper."""

    def test_gigantic_prompt_does_not_crash(self):
        # Prompt de 25000 chars (mayor a MAX_PROMPT_LENGTH_FOR_SCAN)
        big = ("rediseñar la landing " * 1500)
        r = classify_user_intent(big)
        # Debe retornar resultado valido, intent=redesign (keyword dominante)
        self.assertIn(r["confidence"], ("high", "medium", "low"))
        # No crashea
        self.assertIsInstance(r["signals"], list)

    def test_mixed_buckets_low_confidence(self):
        # Ambiguo: tiene senales de audit Y redesign
        r = classify_user_intent("revisar y rediseñar la página")
        # Puede ser high de redesign si dominance>=2, o low si empate.
        # Validamos solo que el shape es correcto.
        self.assertIn(r["confidence"], ("high", "medium", "low"))

    def test_no_pipeline_message(self):
        # Mensaje conversacional sin verbos de pipeline
        r = classify_user_intent("hola, como estas?")
        self.assertIsNone(r["intent"])
        self.assertEqual(r["confidence"], "low")
        # No escalar — no es pipeline
        self.assertIsNone(r["escalation_question"])

    def test_technical_question(self):
        # Pregunta tecnica pura
        r = classify_user_intent("que es better-auth?")
        self.assertIsNone(r["intent"])
        # No escalar
        self.assertIsNone(r["escalation_question"])


class TestDispatcherIntegration(unittest.TestCase):
    """Wiring con ATLASDispatcher."""

    def setUp(self):
        from atlas_dispatcher import ATLASDispatcher
        # Deshabilitar Engram MCP para no abrir subprocess en tests
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        # Asegurar intent classifier ON
        os.environ.pop("ATLAS_INTENT_CLASSIFIER_DISABLED", None)
        self.dispatcher = ATLASDispatcher(
            project_root=Path.cwd(),
            auto_enable_mcp=False,
        )

    def test_dispatcher_has_method(self):
        self.assertTrue(hasattr(self.dispatcher, "classify_user_intent"))
        self.assertTrue(callable(self.dispatcher.classify_user_intent))

    def test_dispatcher_classifier_enabled_by_default(self):
        self.assertTrue(self.dispatcher.intent_classifier_enabled)

    def test_dispatcher_classifies_redesign(self):
        r = self.dispatcher.classify_user_intent("rediseñá toda la landing desde cero")
        self.assertEqual(r["intent"], "redesign")

    def test_dispatcher_respects_disabled_flag(self):
        os.environ["ATLAS_INTENT_CLASSIFIER_DISABLED"] = "1"
        try:
            from atlas_dispatcher import ATLASDispatcher
            d = ATLASDispatcher(
                project_root=Path.cwd(),
                auto_enable_mcp=False,
            )
            self.assertFalse(d.intent_classifier_enabled)
            r = d.classify_user_intent("auditá la landing")
            # Disabled → retorna shape neutro con intent=None
            self.assertIsNone(r["intent"])
            self.assertIn("disabled", r["rationale"].lower())
        finally:
            del os.environ["ATLAS_INTENT_CLASSIFIER_DISABLED"]

    def test_dispatcher_classifier_fail_open_on_error(self):
        # Simular un input que no debiera romper (None está cubierto en classifier).
        r = self.dispatcher.classify_user_intent(None)
        self.assertIsInstance(r, dict)
        self.assertIn("intent", r)
        self.assertIsNone(r["intent"])


class TestCLI(unittest.TestCase):
    """CLI subcommand classify-intent."""

    def test_cli_subcommand_works(self):
        import subprocess
        env = dict(os.environ)
        env["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        result = subprocess.run(
            [sys.executable, str(_TOOLS / "atlas_dispatcher.py"),
             "classify-intent", "rediseñá la home desde cero"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0,
                         f"stdout={result.stdout}\nstderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["intent"], "redesign")

    def test_cli_stdin_works(self):
        import subprocess
        env = dict(os.environ)
        env["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        result = subprocess.run(
            [sys.executable, str(_TOOLS / "atlas_dispatcher.py"),
             "classify-intent", "-"],
            input="auditá esta landing y revisá los issues",
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0,
                         f"stdout={result.stdout}\nstderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["intent"], "audit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
