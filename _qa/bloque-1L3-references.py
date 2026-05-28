#!/usr/bin/env python3
"""
Bloque 1L.3 -- reference-driven-design obligatorio
====================================================

Verifica:
- design_strict rechaza envelope SIN brand.references
- design_strict rechaza < 2 o > 5 references
- design_strict rechaza entries con url / rationale / take invalidos
- ui-designer (heuristica) DEBE citar references_used
- references_used debe ser subset estricto de brand.references URLs
- Otros modos (standard / qa_strict / dev_strict) NO se ven afectados
- enforce_references=False explicito desactiva enforcement
- ATLAS_REFERENCES_ENFORCEMENT_DISABLED=1 desactiva runtime
- brand.json en disco se resuelve correctamente
- NO valida HTTP (heuristica "." o "://" solamente)
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


def _valid_refs(n=2):
    return [
        {
            "url": f"https://site-{i}.com",
            "rationale": f"razon valida y suficientemente larga {i}",
            "take": ["palette", "typography"],
            "skip": ["copy"],
        }
        for i in range(n)
    ]


def _ui_envelope(refs=None, references_used=None, agent="ui-designer", archivos=None):
    """Envelope ui-designer base que pasa 1C.1 + 1L.2 (sin archivos UI escaneables)."""
    env = {
        "status": "completado",
        "tarea": "test 1L.3",
        "archivos": archivos if archivos is not None else [],
        "engram": "test/design-system",
        "verificacion": "layout",
        "bloqueadores": [],
        "agent": agent,
        "design_intelligence": {
            "queried": True,
            "queries": ["test"],
            "results_used": ["style.editorial-raw"],
            "decisions_referenced": {"fonts": "Fraunces"},
        },
    }
    if refs is not None:
        env["brand"] = {"style": "editorial-raw", "references": refs}
    if references_used is not None:
        env["references_used"] = references_used
    return env


class TestReferencesEnforcement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
        os.environ.pop("ATLAS_REFERENCES_ENFORCEMENT_DISABLED", None)
        from atlas_dispatcher import ATLASDispatcher
        cls.project_root = Path.cwd()
        cls.dispatcher = ATLASDispatcher(
            project_root=cls.project_root,
            auto_enable_mcp=False,
        )
        cls._tmpdir = tempfile.TemporaryDirectory(
            prefix="bloque-1L3-", dir=str(cls.project_root / "_qa")
        )
        cls.test_dir = Path(cls._tmpdir.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    # ---------- Missing / wrong cardinality ----------

    def test_missing_references_blocks(self):
        env = _ui_envelope(refs=None, references_used=["x"])
        # Quitar brand entero para forzar missing
        env.pop("brand", None)
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("brand.references ausente", joined)

    def test_too_few_references_blocks(self):
        env = _ui_envelope(refs=_valid_refs(1), references_used=["https://site-0.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("minimo 2", joined)

    def test_too_many_references_blocks(self):
        env = _ui_envelope(refs=_valid_refs(6), references_used=["https://site-0.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("maximo 5", joined)

    # ---------- Entry shape ----------

    def test_entry_missing_url_blocks(self):
        refs = _valid_refs(2)
        del refs[0]["url"]
        env = _ui_envelope(refs=refs, references_used=["https://site-1.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("url ausente o invalido", joined)

    def test_entry_short_rationale_blocks(self):
        refs = _valid_refs(2)
        refs[0]["rationale"] = "corta"  # < 10 chars
        env = _ui_envelope(refs=refs, references_used=["https://site-0.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("rationale", joined)

    def test_entry_empty_take_blocks(self):
        refs = _valid_refs(2)
        refs[0]["take"] = []
        env = _ui_envelope(refs=refs, references_used=["https://site-0.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("take debe ser lista no-vacia", joined)

    def test_entry_url_without_dot_or_scheme_blocks(self):
        refs = _valid_refs(2)
        refs[0]["url"] = "noturl"  # sin "." y sin "://"
        env = _ui_envelope(refs=refs, references_used=["https://site-1.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("no parece URL", joined)

    def test_skip_present_must_be_list(self):
        refs = _valid_refs(2)
        refs[0]["skip"] = "not a list"
        env = _ui_envelope(refs=refs, references_used=["https://site-0.com"])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("skip", joined)

    # ---------- references_used (ui-designer obligatorio) ----------

    def test_ui_designer_missing_references_used_blocks(self):
        env = _ui_envelope(refs=_valid_refs(2), references_used=None)
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("references_used", joined)

    def test_ui_designer_empty_references_used_blocks(self):
        env = _ui_envelope(refs=_valid_refs(2), references_used=[])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("references_used vacio", joined)

    def test_references_used_not_subset_blocks(self):
        env = _ui_envelope(
            refs=_valid_refs(2),
            references_used=["https://invented.com"],
        )
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("NO estan en brand.references", joined)

    def test_references_used_valid_subset_passes(self):
        env = _ui_envelope(
            refs=_valid_refs(3),
            references_used=["https://site-0.com", "https://site-2.com"],
        )
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertTrue(ok, f"valid subset should pass; errores={errores}")

    # ---------- Non-ui agent ----------

    def test_brand_agent_without_references_used_passes(self):
        # brand-agent NO necesita citar references_used (es quien las produce)
        env = _ui_envelope(refs=_valid_refs(2), references_used=None, agent="brand-agent")
        # Quitar design_intelligence (brand-agent no consulta UI BM25)
        env.pop("design_intelligence", None)
        # Pero design_strict pide design_intelligence -> agregar minimo
        env["design_intelligence"] = {"queried": True, "queries": ["x"],
                                      "results_used": ["y"],
                                      "decisions_referenced": {"k": "v"}}
        # _looks_like_ui_designer dispara True por design_intelligence.queried.
        # En la realidad brand-agent NO setea ese campo. Lo limpiamos:
        env.pop("design_intelligence", None)
        # Eliminar el cajon engram con 'design-system' para no triggear heuristica
        env["engram"] = "test/brand"
        # En este caso, _looks_like_ui_designer = False -> references_used opcional.
        # Pero el envelope ya NO pasa 1C.1 sin design_intelligence.
        # Soluciono: este test solo verifica que verify_references no exige
        # references_used cuando heuristica dice no-ui. Llamamos al helper
        # directamente.
        errores, warnings = self.dispatcher.verify_references(env)
        # Sin references_used pero refs validos -> PASS
        self.assertEqual(errores, [], f"errores: {errores}")

    # ---------- Backward compat ----------

    def test_standard_mode_unaffected(self):
        env = {
            "status": "completado",
            "tarea": "test",
            "archivos": [],
            "engram": "x/y",
            "verificacion": "none",
            "bloqueadores": [],
        }
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="standard")
        self.assertTrue(ok, f"standard should pass; errores={errores}")

    def test_dev_strict_unaffected(self):
        # dev_strict no debe disparar 1L.3
        env = {
            "status": "completado",
            "tarea": "test",
            "archivos": [],
            "engram": "x/y",
            "verificacion": "layout",
            "bloqueadores": [],
            "pre_return_audit": {"ok": True, "summary": {"by_severity": {}}},
        }
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="dev_strict")
        joined = "\n".join(errores)
        self.assertNotIn("Bloque 1L.3", joined)

    # ---------- Rollback ----------

    def test_enforce_false_disables_in_design_strict(self):
        env = _ui_envelope(refs=None, references_used=None)
        env.pop("brand", None)
        ok, errores = self.dispatcher.validate_return_envelope(
            env, mode="design_strict", enforce_references=False,
        )
        # Sin 1L.3: el envelope pasa (1C.1 + 1L.2 OK)
        self.assertTrue(ok, f"enforce_references=False should pass; errores={errores}")

    def test_env_var_disables_runtime(self):
        os.environ["ATLAS_REFERENCES_ENFORCEMENT_DISABLED"] = "1"
        try:
            env = _ui_envelope(refs=None, references_used=None)
            env.pop("brand", None)
            ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
            self.assertTrue(ok, f"env var disabled should pass; errores={errores}")
        finally:
            del os.environ["ATLAS_REFERENCES_ENFORCEMENT_DISABLED"]

    # ---------- Disk resolution ----------

    def test_brand_json_on_disk_resolves(self):
        # brand.json en disco con references validos debe ser leido
        original_root = self.dispatcher.project_root
        brand_path = self.test_dir / "brand.json"
        brand_path.write_text(json.dumps({
            "style": "editorial-raw",
            "references": _valid_refs(2),
        }), encoding="utf-8")
        self.dispatcher.project_root = self.test_dir
        try:
            env = _ui_envelope(
                refs=None,
                references_used=["https://site-0.com"],
            )
            env.pop("brand", None)  # forzar lectura de disco
            ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
            self.assertTrue(ok, f"disk brand.json should pass; errores={errores}")
        finally:
            self.dispatcher.project_root = original_root

    # ---------- Edge cases ----------

    def test_duplicate_urls_warn_no_block(self):
        refs = _valid_refs(2)
        refs[1]["url"] = refs[0]["url"]
        env = _ui_envelope(refs=refs, references_used=[refs[0]["url"]])
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertTrue(ok, f"duplicate URL should warn not block; errores={errores}")
        warnings = env.get("_dispatcher_warnings", [])
        joined_w = "\n".join(warnings)
        self.assertIn("duplicadas", joined_w.lower())

    def test_references_not_a_list_blocks(self):
        env = _ui_envelope(refs="not a list", references_used=["x"])
        env["brand"] = {"style": "editorial-raw", "references": "not a list"}
        ok, errores = self.dispatcher.validate_return_envelope(env, mode="design_strict")
        self.assertFalse(ok)
        joined = "\n".join(errores)
        self.assertIn("debe ser lista", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
