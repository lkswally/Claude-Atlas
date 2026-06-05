#!/usr/bin/env python3
"""
Bloque F2.1.1 — Skills Registry (loader + API + validacion)
=============================================================

Verifica:
- Loader parsea YAML valido / vacio / malformado / missing
- Schema validation: campos requeridos, cost_tier valido, id formato
- API find_skills: por domain / agent / applies_when / sin filtros
- API get_skill: existente / inexistente
- API list_domains: lista unica ordenada
- Edge cases: duplicados, malformados (skip silencioso)
- Env var ATLAS_SKILLS_REGISTRY_DISABLED=1 -> retorna []
- Override path via ATLAS_SKILLS_REGISTRY_PATH
- validate_registry retorna diagnostico explicito
- Fail-open: registry missing / PyYAML missing -> no raise
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import skills_registry  # noqa: E402
from skills_registry import (  # noqa: E402
    find_skills,
    get_skill,
    list_domains,
    validate_registry,
    _reset_cache,
)


def _write_registry(tmp_dir: Path, content: str) -> Path:
    """Helper: escribe registry temporal en tmp_dir/.claude/."""
    claude_dir = tmp_dir / ".claude"
    claude_dir.mkdir(exist_ok=True)
    path = claude_dir / "skills.registry.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _valid_registry_yaml(n=2) -> str:
    """Genera YAML valido con n skills."""
    entries = "\n".join([
        f"  - skill_id: \"test.skill-{i}\"\n"
        f"    domain: \"design\"\n"
        f"    agent: \"agent-{i}\"\n"
        f"    description: \"test skill {i}\"\n"
        f"    inputs: [\"input1\"]\n"
        f"    outputs: [\"output1\"]\n"
        f"    cost_tier: \"low\"\n"
        f"    applies_when:\n"
        f"      - \"phase == fase_2\"\n"
        for i in range(n)
    ])
    return f"version: 1\nskills:\n{entries}"


class _IsolatedRegistryMixin:
    """Mixin: setea path override + resetea cache."""

    def _set_registry(self, path: Path):
        os.environ["ATLAS_SKILLS_REGISTRY_PATH"] = str(path)
        os.environ.pop("ATLAS_SKILLS_REGISTRY_DISABLED", None)
        _reset_cache()

    def _clear_registry(self):
        os.environ.pop("ATLAS_SKILLS_REGISTRY_PATH", None)
        os.environ.pop("ATLAS_SKILLS_REGISTRY_DISABLED", None)
        _reset_cache()


# =====================================================================
#  Loader: YAML valido / vacio / malformado / missing
# =====================================================================

class TestLoaderBasics(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_loads_valid_yaml(self):
        path = _write_registry(self.tmp_path, _valid_registry_yaml(n=3))
        self._set_registry(path)
        skills = find_skills()
        self.assertEqual(len(skills), 3)

    def test_empty_skills_list(self):
        path = _write_registry(self.tmp_path, "version: 1\nskills: []\n")
        self._set_registry(path)
        self.assertEqual(find_skills(), [])

    def test_malformed_yaml_returns_empty(self):
        path = _write_registry(self.tmp_path, "this is :: not :: yaml\n  - bad")
        self._set_registry(path)
        self.assertEqual(find_skills(), [])

    def test_missing_file_returns_empty(self):
        # Path no existe
        self._set_registry(self.tmp_path / "does-not-exist.yaml")
        self.assertEqual(find_skills(), [])

    def test_skills_not_a_list_returns_empty(self):
        path = _write_registry(self.tmp_path, "version: 1\nskills: \"string\"\n")
        self._set_registry(path)
        self.assertEqual(find_skills(), [])

    def test_root_not_dict_returns_empty(self):
        path = _write_registry(self.tmp_path, "- just a list\n")
        self._set_registry(path)
        self.assertEqual(find_skills(), [])


# =====================================================================
#  Schema validation
# =====================================================================

class TestSchemaValidation(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_missing_required_field_skipped(self):
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "test.incomplete"
                domain: "design"
                # missing: agent, description, inputs, outputs, cost_tier
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)
        # entry malformada -> filtrada silenciosamente
        self.assertEqual(find_skills(), [])

    def test_invalid_cost_tier_skipped(self):
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "test.bad-tier"
                domain: "design"
                agent: "x"
                description: "y"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "extreme"
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)
        self.assertEqual(find_skills(), [])

    def test_skill_id_without_dot_skipped(self):
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "no-domain-prefix"
                domain: "design"
                agent: "x"
                description: "y"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)
        self.assertEqual(find_skills(), [])

    def test_duplicate_skill_id_keeps_first(self):
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "test.dup"
                domain: "design"
                agent: "first"
                description: "first one"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
              - skill_id: "test.dup"
                domain: "design"
                agent: "second"
                description: "duplicate"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)
        skills = find_skills()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["agent"], "first")


# =====================================================================
#  API find_skills (filtros)
# =====================================================================

class TestFindSkills(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "design.a"
                domain: "design"
                agent: "ux-architect"
                description: "design a"
                inputs: ["x"]
                outputs: ["y"]
                cost_tier: "low"
                applies_when:
                  - "phase == fase_2"
              - skill_id: "design.b"
                domain: "design"
                agent: "ui-designer"
                description: "design b"
                inputs: ["x"]
                outputs: ["y"]
                cost_tier: "medium"
                applies_when:
                  - "phase == fase_2"
                  - "agent == ui-designer"
              - skill_id: "qa.c"
                domain: "qa"
                agent: "evidence-collector"
                description: "qa c"
                inputs: ["x"]
                outputs: ["y"]
                cost_tier: "low"
                applies_when:
                  - "phase == fase_3"
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_find_all_no_filter(self):
        self.assertEqual(len(find_skills()), 3)

    def test_filter_by_domain(self):
        results = find_skills(domain="design")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(s["domain"] == "design" for s in results))

    def test_filter_by_agent(self):
        results = find_skills(agent="evidence-collector")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["skill_id"], "qa.c")

    def test_filter_by_applies_when(self):
        results = find_skills(applies_when={"phase": "fase_2"})
        ids = {s["skill_id"] for s in results}
        self.assertEqual(ids, {"design.a", "design.b"})

    def test_filter_by_applies_when_no_match(self):
        results = find_skills(applies_when={"phase": "fase_9"})
        self.assertEqual(results, [])

    def test_filter_combined_domain_and_agent(self):
        results = find_skills(domain="design", agent="ui-designer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["skill_id"], "design.b")


# =====================================================================
#  API get_skill / list_domains
# =====================================================================

class TestGetSkillAndListDomains(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        path = _write_registry(self.tmp_path, _valid_registry_yaml(n=3))
        # Modificar el primer skill para que tenga domain distinto
        # _valid_registry_yaml todos quedan "design". Reescribo:
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "design.a"
                domain: "design"
                agent: "x"
                description: "x"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
              - skill_id: "qa.b"
                domain: "qa"
                agent: "y"
                description: "y"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
              - skill_id: "branding.c"
                domain: "branding"
                agent: "z"
                description: "z"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "high"
        """)
        path.write_text(yaml_content, encoding="utf-8")
        self._set_registry(path)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_get_skill_existing(self):
        skill = get_skill("design.a")
        self.assertIsNotNone(skill)
        self.assertEqual(skill["domain"], "design")

    def test_get_skill_nonexistent_returns_none(self):
        self.assertIsNone(get_skill("does.not-exist"))

    def test_get_skill_empty_id_returns_none(self):
        self.assertIsNone(get_skill(""))

    def test_get_skill_non_string_returns_none(self):
        self.assertIsNone(get_skill(None))  # type: ignore[arg-type]

    def test_list_domains_unique_sorted(self):
        domains = list_domains()
        self.assertEqual(domains, ["branding", "design", "qa"])


# =====================================================================
#  Env var disable
# =====================================================================

class TestDisableEnv(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        path = _write_registry(self.tmp_path, _valid_registry_yaml(n=2))
        self._set_registry(path)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_disabled_returns_empty(self):
        os.environ["ATLAS_SKILLS_REGISTRY_DISABLED"] = "1"
        try:
            self.assertEqual(find_skills(), [])
            self.assertIsNone(get_skill("test.skill-0"))
            self.assertEqual(list_domains(), [])
        finally:
            del os.environ["ATLAS_SKILLS_REGISTRY_DISABLED"]


# =====================================================================
#  validate_registry (diagnostico)
# =====================================================================

class TestValidateRegistry(unittest.TestCase, _IsolatedRegistryMixin):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self._clear_registry()
        self.tmpdir.cleanup()

    def test_validate_clean_registry(self):
        path = _write_registry(self.tmp_path, _valid_registry_yaml(n=3))
        self._set_registry(path)
        report = validate_registry()
        self.assertTrue(report["ok"])
        self.assertEqual(report["total_entries"], 3)
        self.assertEqual(report["valid"], 3)
        self.assertEqual(report["errors"], [])

    def test_validate_with_errors(self):
        yaml_content = dedent("""\
            version: 1
            skills:
              - skill_id: "good.one"
                domain: "design"
                agent: "x"
                description: "y"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
              - skill_id: "bad.cost"
                domain: "design"
                agent: "x"
                description: "y"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "invalid"
              - skill_id: "good.one"
                domain: "qa"
                agent: "x"
                description: "duplicate"
                inputs: ["a"]
                outputs: ["b"]
                cost_tier: "low"
        """)
        path = _write_registry(self.tmp_path, yaml_content)
        self._set_registry(path)
        report = validate_registry()
        self.assertFalse(report["ok"])
        self.assertEqual(report["total_entries"], 3)
        self.assertEqual(report["valid"], 1)
        self.assertEqual(len(report["errors"]), 2)

    def test_validate_missing_file(self):
        self._set_registry(self.tmp_path / "missing.yaml")
        report = validate_registry()
        self.assertFalse(report["ok"])
        self.assertIn("not found", report["reason"])


# =====================================================================
#  Real registry shipped (sanity)
# =====================================================================

class TestShippedRegistrySanity(unittest.TestCase):
    """Verifica que el .claude/skills.registry.yaml real del repo valida."""

    def setUp(self):
        # Limpiar overrides para usar el real
        os.environ.pop("ATLAS_SKILLS_REGISTRY_PATH", None)
        os.environ.pop("ATLAS_SKILLS_REGISTRY_DISABLED", None)
        _reset_cache()

    def test_shipped_registry_valid(self):
        report = validate_registry()
        self.assertTrue(
            report["ok"],
            f"Shipped registry has errors: {report.get('errors', [])}",
        )
        # Esperamos al menos 5 skills en el catalogo inicial
        self.assertGreaterEqual(report["valid"], 5)

    def test_shipped_registry_has_design_domain(self):
        domains = list_domains()
        self.assertIn("design", domains)


if __name__ == "__main__":
    unittest.main(verbosity=2)
