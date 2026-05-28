#!/usr/bin/env python3
"""
Bloque 1L.2 -- Design Quality Blocking en design_strict
=========================================================

Verifica:
- design_strict rechaza envelope con HIGH findings (sin brand.style)
- Otros modos (standard / qa_strict / dev_strict) NO se ven afectados
- Whitelist por brand.style degrada HIGH font -> warning SOLO para fonts canonicos
- Whitelist NO degrada HIGH color / layout / opacity / radius (anti-disguise)
- enforce_design_quality=False explicito desactiva enforcement aun en design_strict
- ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED=1 desactiva runtime
- Errores son accionables (file:line + suggestion)
- Sin archivos UI escaneables -> warning, no bloqueo
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _make_envelope_completado(archivos, **extra):
    """Envelope base con todo lo que design_strict + 1C.1 piden para que
    SOLO 1L.2 sea la barrera (o no)."""
    base = {
        "status": "completado",
        "tarea": "test 1L.2",
        "archivos": archivos,
        "engram": "test/cajon",
        "verificacion": "layout",
        "bloqueadores": [],
        # Bloque 1C.1: design_intelligence consultado
        "design_intelligence": {
            "queried": True,
            "queries": ["test"],
            "results_used": ["style.editorial-raw"],
            "decisions_referenced": {"fonts": "Fraunces"},
        },
    }
    base.update(extra)
    return base


class TestDesignQualityBlocking(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Desactivar Engram MCP para no abrir subprocess
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        # Asegurar enforcement runtime ON
        os.environ.pop("ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED", None)
        from atlas_dispatcher import ATLASDispatcher
        # Usar Path.cwd() para que dispatcher encuentre phase_playbook.json
        cls.project_root = Path.cwd()
        cls.dispatcher = ATLASDispatcher(
            project_root=cls.project_root,
            auto_enable_mcp=False,
        )
        # Subdir temporal para artefactos del test, dentro del repo
        cls._tmpdir = tempfile.TemporaryDirectory(
            prefix="bloque-1L2-", dir=str(cls.project_root / "_qa")
        )
        cls.test_dir = Path(cls._tmpdir.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def _write(self, name: str, content: str) -> str:
        p = self.test_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    # ---------- Core blocking ----------

    def test_design_strict_blocks_on_high_font(self):
        # Inter es HIGH font sin whitelist (no brand.style)
        css = self._write("a.css", "body { font-family: 'Inter', sans-serif; }")
        env = _make_envelope_completado([css])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        # Mensaje accionable: pattern_type + pattern + file + line + suggestion
        joined = "\n".join(errores)
        self.assertIn("design_quality", joined)
        self.assertIn("font", joined)
        self.assertIn("inter", joined.lower())
        self.assertIn("a.css", joined)

    def test_design_strict_blocks_on_high_color(self):
        # Tailwind blue #3b82f6 es HIGH color, NO whitelistable bajo ningun style
        css = self._write("c.css", ".btn { background: #3b82f6; }")
        env = _make_envelope_completado([css], brand={"style": "brutalism"})
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        # Aunque brand.style=brutalism, color NO se whitelista (anti-disguise)
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("color", joined.lower())
        self.assertIn("3b82f6", joined.lower())

    # ---------- Backward compat ----------

    def test_standard_mode_unaffected(self):
        css = self._write("std.css", "body { font-family: 'Inter'; }")
        env = _make_envelope_completado([css])
        # Quitar design_intelligence (no aplica en standard)
        env.pop("design_intelligence", None)
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="standard")
        # standard NO ejecuta 1L.2
        self.assertTrue(ok, f"standard mode should pass; errores={errores}")

    def test_qa_strict_unaffected(self):
        # qa_strict tiene reglas propias (PASS/FAIL); no debe disparar 1L.2
        env = {
            "status": "PASS",
            "tarea": "test",
            "archivos": ["dummy.css"],  # archivo no existe, qa_strict no scanea
            "engram": "test/cajon",
            "verificacion": "layout",
            "bloqueadores": [],
        }
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="qa_strict")
        self.assertTrue(ok, f"qa_strict should pass; errores={errores}")

    # ---------- Whitelist ----------

    def test_whitelist_degrades_helvetica_in_brutalism(self):
        css = self._write("brut.css", "body { font-family: 'Helvetica', sans-serif; }")
        env = _make_envelope_completado([css], brand={"style": "brutalism"})
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        # Helvetica HIGH degradada a warning bajo style=brutalism
        self.assertTrue(ok, f"brutalism+helvetica should pass; errores={errores}")
        warnings = env.get("_dispatcher_warnings", [])
        joined_w = "\n".join(warnings)
        self.assertIn("whitelist", joined_w.lower())
        self.assertIn("brutalism", joined_w.lower())

    def test_whitelist_does_not_cover_inter(self):
        # Inter NUNCA se whitelista, ni siquiera bajo brutalism
        css = self._write("brut2.css", "body { font-family: 'Inter', sans-serif; }")
        env = _make_envelope_completado([css], brand={"style": "brutalism"})
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("inter", joined.lower())

    def test_whitelist_loads_from_brand_json_on_disk(self):
        # brand.json en disco con style=neo-grotesque debe whitelistar Arial.
        # Apuntamos project_root temporalmente al test_dir para no contaminar repo.
        original_root = self.dispatcher.project_root
        brand_path = self.test_dir / "brand.json"
        brand_path.write_text(json.dumps({"style": "neo-grotesque"}), encoding="utf-8")
        self.dispatcher.project_root = self.test_dir
        try:
            css = self._write("ng.css", "body { font-family: 'Arial', sans-serif; }")
            env = _make_envelope_completado([css])
            ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
            self.assertTrue(ok, f"neo-grotesque+arial should pass; errores={errores}")
        finally:
            self.dispatcher.project_root = original_root
            brand_path.unlink(missing_ok=True)

    # ---------- Rollback flags ----------

    def test_enforce_false_disables_even_in_design_strict(self):
        css = self._write("off.css", "body { font-family: 'Inter'; }")
        env = _make_envelope_completado([css])
        ok, errores = self.dispatcher.validate_return_envelope(
            env, mode="design_strict", enforce_design_quality=False,
        )
        # Sin 1L.2: solo 1C.1 design_intelligence (que ya esta poblado) -> PASS
        self.assertTrue(ok, f"enforce_design_quality=False should pass; errores={errores}")

    def test_env_var_disables_runtime(self):
        os.environ["ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED"] = "1"
        try:
            css = self._write("env.css", "body { font-family: 'Inter'; }")
            env = _make_envelope_completado([css])
            ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
            self.assertTrue(ok, f"env var disabled should pass; errores={errores}")
        finally:
            del os.environ["ATLAS_DESIGN_QUALITY_BLOCKING_DISABLED"]

    # ---------- Edge cases ----------

    def test_no_ui_files_warning_no_block(self):
        # Archivos sin extension UI relevante (ej: .py, .md) -> warning + PASS
        py = self._write("script.py", "x = 1")
        env = _make_envelope_completado([py])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertTrue(ok, f"non-UI files should pass with warning; errores={errores}")
        warnings = env.get("_dispatcher_warnings", [])
        joined_w = "\n".join(warnings)
        self.assertIn("0 archivos UI escaneados", joined_w)

    def test_missing_file_does_not_crash(self):
        env = _make_envelope_completado(["does-not-exist.css"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        # No crashea. Sin archivos escaneados -> PASS con warning.
        self.assertIsInstance(ok, bool)

    def test_actionable_error_includes_suggestion(self):
        css = self._write("act.css", "body { font-family: 'Inter'; }")
        env = _make_envelope_completado([css])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        # Suggestion debe estar presente
        self.assertIn("->", joined)
        self.assertTrue(
            any(kw in joined.lower() for kw in ("syne", "clash", "fraunces", "personalidad")),
            f"Error message lacks actionable suggestion: {joined}",
        )

    def test_failido_status_does_not_trigger_dq(self):
        # status=fallido NO debe ejecutar 1L.2 (el agente ya fallo)
        env = {
            "status": "fallido",
            "tarea": "fallido test",
            "archivos": [],
            "engram": "test/cajon",
            "verificacion": "none",
            "bloqueadores": ["algo fallo"],
        }
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        # No deberia rechazar por 1L.2 (no se ejecuta en fallido)
        # Puede fallar por 1C.1 si lo pide, pero no por design_quality
        joined = "\n".join(errores)
        self.assertNotIn("Bloque 1L.2", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
