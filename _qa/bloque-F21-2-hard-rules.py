#!/usr/bin/env python3
"""
Bloque F2.1.2 — Hard Rules (hook pipeline-rules.js)
=====================================================

Verifica el hook PreToolUse via subprocess + stdin JSON.

Cobertura:
- block rule: gh pr merge 25 cuando pilotos NO PASS -> exit 2 + stderr
- block rule: git push --force a main -> exit 2
- warn rule: cd <ruta> && git commit -> exit 0 + stderr
- pass-through: comandos benignos (ls, etc.) -> exit 0 sin stderr
- pass-through: tool_name distinto de Bash -> exit 0
- bypass per-rule: ATLAS_FORCE_MERGE_PR25=1 saltea regla
- disable global: ATLAS_HARD_RULES_DISABLED=1 -> hook no-op
- fail-open: hard-rules.json missing -> exit 0 silencioso
- fail-open: hard-rules.json malformado -> exit 0 silencioso
- file_contains condition: pilotos con C3 PASS -> NO bloquea
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).parent
_REPO = _HERE.parent
_HOOK_PATH = _REPO / ".claude" / "hooks" / "pipeline-rules.js"
_REAL_RULES_PATH = _REPO / ".claude" / "hard-rules.json"


def _run_hook(payload: dict, env_overrides: dict | None = None,
              project_dir: Path | None = None) -> tuple[int, str, str]:
    """Ejecuta el hook con payload JSON via stdin. Retorna (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    # Limpiar bypass envs comunes para tests deterministicos
    for k in ("ATLAS_HARD_RULES_DISABLED", "ATLAS_FORCE_MERGE_PR25",
              "ATLAS_ALLOW_FORCE_PUSH_MAIN", "ATLAS_SUPPRESS_REGISTRY_HINT"):
        env.pop(k, None)
    if env_overrides:
        env.update(env_overrides)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    result = subprocess.run(
        ["node", str(_HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return result.returncode, result.stdout, result.stderr


class _ProjectDirMixin:
    """Mixin que crea un project dir temporal con copia de hard-rules.json."""

    def _setup_project(self, custom_rules: str | None = None,
                       with_pilots: bool = False) -> Path:
        """
        Crea un tmpdir, copia hard-rules.json (o usa custom),
        y opcionalmente crea _qa/pilotos-1L/P1.md con C3 PASS.
        """
        tmpdir = tempfile.mkdtemp(prefix="f21-rules-")
        self._tmpdirs.append(tmpdir)
        tmp = Path(tmpdir)
        (tmp / ".claude").mkdir()
        if custom_rules is not None:
            (tmp / ".claude" / "hard-rules.json").write_text(
                custom_rules, encoding="utf-8"
            )
        else:
            shutil.copy(_REAL_RULES_PATH, tmp / ".claude" / "hard-rules.json")
        if with_pilots:
            pilots_dir = tmp / "_qa" / "pilotos-1L"
            pilots_dir.mkdir(parents=True)
            (pilots_dir / "P1.md").write_text(
                "Piloto P1\n\n## Criterios\n- C3: PASS\n- C4: PASS\n",
                encoding="utf-8",
            )
        return tmp


# =====================================================================
#  Block rules
# =====================================================================

class TestBlockRules(unittest.TestCase, _ProjectDirMixin):

    def setUp(self):
        self._tmpdirs: list[str] = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_pr25_merge_blocked_when_no_pilots(self):
        proj = self._setup_project(with_pilots=False)
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "gh pr merge 25 --rebase"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 2)
        self.assertIn("no-merge-pr25-without-pilots", err)
        self.assertIn("BLOQUEADO", err)

    def test_pr25_merge_allowed_when_pilots_pass(self):
        proj = self._setup_project(with_pilots=True)
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "gh pr merge 25 --rebase"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0, f"stderr={err}")

    def test_force_push_main_blocked(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin main"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 2)
        self.assertIn("no-force-push-main", err)

    def test_force_push_main_short_flag_blocked(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push -f origin main"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 2)

    def test_force_push_other_branch_not_blocked(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin feature/x"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)


# =====================================================================
#  Warn rules
# =====================================================================

class TestWarnRules(unittest.TestCase, _ProjectDirMixin):

    def setUp(self):
        self._tmpdirs: list[str] = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_cross_repo_commit_warns_no_block(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "cd /tmp/other && git commit -m wip"}},
            project_dir=proj,
        )
        # warn -> exit 0 + stderr
        self.assertEqual(rc, 0)
        self.assertIn("warn-cross-repo-commit", err)
        self.assertIn("WARNING", err)


# =====================================================================
#  Pass-through
# =====================================================================

class TestPassThrough(unittest.TestCase, _ProjectDirMixin):

    def setUp(self):
        self._tmpdirs: list[str] = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_benign_command_passes(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)
        # Sin warn ni block triggered
        self.assertNotIn("BLOCK", err)
        self.assertNotIn("WARN", err)

    def test_non_bash_tool_passes(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Read", "tool_input": {"file_path": "x"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)

    def test_empty_command_passes(self):
        proj = self._setup_project()
        rc, _, _ = _run_hook(
            {"tool_name": "Bash", "tool_input": {"command": ""}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)


# =====================================================================
#  Bypass per-rule + disable global
# =====================================================================

class TestBypassAndDisable(unittest.TestCase, _ProjectDirMixin):

    def setUp(self):
        self._tmpdirs: list[str] = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_bypass_pr25_via_env(self):
        proj = self._setup_project(with_pilots=False)
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "gh pr merge 25"}},
            env_overrides={"ATLAS_FORCE_MERGE_PR25": "1"},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)
        self.assertIn("SKIP rule=no-merge-pr25-without-pilots", err)

    def test_bypass_force_push_via_env(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin main"}},
            env_overrides={"ATLAS_ALLOW_FORCE_PUSH_MAIN": "1"},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)
        self.assertIn("SKIP rule=no-force-push-main", err)

    def test_global_disable(self):
        proj = self._setup_project()
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin main"}},
            env_overrides={"ATLAS_HARD_RULES_DISABLED": "1"},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)
        # Disabled global: ningun mensaje
        self.assertNotIn("BLOCK", err)
        self.assertNotIn("WARN", err)


# =====================================================================
#  Fail-open
# =====================================================================

class TestFailOpen(unittest.TestCase, _ProjectDirMixin):

    def setUp(self):
        self._tmpdirs: list[str] = []

    def tearDown(self):
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_rules_file_missing(self):
        tmpdir = tempfile.mkdtemp(prefix="f21-noruleshfile-")
        self._tmpdirs.append(tmpdir)
        # No copiamos hard-rules.json
        rc, _, err = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin main"}},
            project_dir=Path(tmpdir),
        )
        # Sin rules file -> fail-open -> exit 0
        self.assertEqual(rc, 0)
        self.assertNotIn("BLOCK", err)

    def test_rules_file_malformed_json(self):
        proj = self._setup_project(custom_rules="{not valid json")
        rc, _, _ = _run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push --force origin main"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)

    def test_rules_file_with_invalid_rules_skipped(self):
        # Rule sin severity valida -> filtrada, otras siguen
        custom = json.dumps({
            "version": 1,
            "rules": [
                {"rule_id": "broken", "predicate": {"type": "command_match",
                                                    "pattern": "ls"}}  # falta severity
            ]
        })
        proj = self._setup_project(custom_rules=custom)
        rc, _, err = _run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}},
            project_dir=proj,
        )
        self.assertEqual(rc, 0)


# =====================================================================
#  Shipped rules sanity
# =====================================================================

class TestShippedRulesSanity(unittest.TestCase):
    """Verifica que hard-rules.json real del repo es JSON valido."""

    def test_real_rules_parses(self):
        with open(_REAL_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("rules", data)
        self.assertIsInstance(data["rules"], list)
        # MVP: max 4 reglas (regla de no-sobre-ingenieria)
        self.assertLessEqual(len(data["rules"]), 4)
        # Cada regla tiene campos basicos
        for r in data["rules"]:
            self.assertIn("rule_id", r)
            self.assertIn("severity", r)
            self.assertIn(r["severity"], ("block", "warn"))
            self.assertIn("predicate", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
