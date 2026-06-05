#!/usr/bin/env python3
"""
Bloque F2.1.b — Registry Consumption Hints / Usage Logging
============================================================

Verifica:
- find_skills / get_skill / list_domains agregan entries al JSONL
- Entries tienen shape valido: ts (ISO+tz), event, kwargs relevantes
- usage_stats agrega total, by_event, top_skills, top_domains, top_agents
- since_days filter funciona
- Env var ATLAS_SKILLS_USAGE_LOG_DISABLED=1 desactiva escritura
- Env var ATLAS_SKILLS_USAGE_LOG_PATH override funciona
- Fail-open: path no escribible -> API sigue retornando datos correctos
- usage_stats con log inexistente -> shape con total=0
- usage_stats con JSONL malformado -> entries skipped, no crash
- CLI stats produce JSON valido
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

_HERE = Path(__file__).parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import skills_registry  # noqa: E402
from skills_registry import (  # noqa: E402
    find_skills, get_skill, list_domains,
    usage_stats,
    _reset_cache,
)


class _IsolatedLogTestCase(unittest.TestCase):
    """Base class: cada test usa un usage log temporal aislado."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.log_path = self.tmp_path / "usage.jsonl"
        os.environ["ATLAS_SKILLS_USAGE_LOG_PATH"] = str(self.log_path)
        os.environ.pop("ATLAS_SKILLS_USAGE_LOG_DISABLED", None)
        os.environ.pop("ATLAS_SKILLS_REGISTRY_PATH", None)
        os.environ.pop("ATLAS_SKILLS_REGISTRY_DISABLED", None)
        _reset_cache()

    def tearDown(self):
        os.environ.pop("ATLAS_SKILLS_USAGE_LOG_PATH", None)
        os.environ.pop("ATLAS_SKILLS_USAGE_LOG_DISABLED", None)
        self.tmpdir.cleanup()

    def _read_log(self):
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries


# =====================================================================
#  Logging basico
# =====================================================================

class TestLoggingBasic(_IsolatedLogTestCase):

    def test_find_skills_logs_invocation(self):
        find_skills(domain="design")
        entries = self._read_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event"], "find_skills")
        self.assertEqual(entries[0]["domain"], "design")
        self.assertIn("result_count", entries[0])
        self.assertIn("ts", entries[0])

    def test_get_skill_logs_invocation(self):
        get_skill("design.intelligence-search")
        entries = self._read_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event"], "get_skill")
        self.assertEqual(entries[0]["skill_id"], "design.intelligence-search")
        self.assertTrue(entries[0]["found"])

    def test_get_skill_not_found_still_logs(self):
        get_skill("does.not-exist")
        entries = self._read_log()
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["found"])

    def test_list_domains_logs_invocation(self):
        list_domains()
        entries = self._read_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event"], "list_domains")
        self.assertIn("result_count", entries[0])

    def test_multiple_invocations_append(self):
        find_skills(domain="design")
        find_skills(agent="evidence-collector")
        get_skill("design.intelligence-search")
        list_domains()
        entries = self._read_log()
        self.assertEqual(len(entries), 4)


# =====================================================================
#  Entry shape
# =====================================================================

class TestEntryShape(_IsolatedLogTestCase):

    def test_ts_is_iso_with_tz(self):
        find_skills()
        entry = self._read_log()[0]
        ts = entry["ts"]
        # Debe parsearse como ISO con tz
        parsed = datetime.fromisoformat(ts)
        self.assertIsNotNone(parsed.tzinfo)

    def test_find_skills_with_none_filters_logged(self):
        find_skills()
        entry = self._read_log()[0]
        self.assertIsNone(entry["domain"])
        self.assertIsNone(entry["agent"])
        self.assertIsNone(entry["applies_when"])

    def test_get_skill_invalid_id_logs_reason(self):
        get_skill("")
        entry = self._read_log()[0]
        self.assertEqual(entry["reason"], "invalid_id")


# =====================================================================
#  Disable + override
# =====================================================================

class TestDisableAndOverride(_IsolatedLogTestCase):

    def test_disable_env_skips_writing(self):
        os.environ["ATLAS_SKILLS_USAGE_LOG_DISABLED"] = "1"
        try:
            find_skills(domain="design")
            self.assertFalse(self.log_path.exists())
        finally:
            del os.environ["ATLAS_SKILLS_USAGE_LOG_DISABLED"]

    def test_path_override_respected(self):
        # Ya configurado en setUp via env var
        find_skills()
        self.assertTrue(self.log_path.exists())


# =====================================================================
#  usage_stats
# =====================================================================

class TestUsageStats(_IsolatedLogTestCase):

    def test_stats_empty_when_log_missing(self):
        # No invoque nada -> log no existe
        report = usage_stats()
        self.assertEqual(report["total_invocations"], 0)
        self.assertEqual(report["by_event"], {})
        self.assertEqual(report["top_skills"], [])

    def test_stats_aggregates_correctly(self):
        find_skills(domain="design")
        find_skills(domain="design")
        find_skills(domain="qa")
        get_skill("design.intelligence-search")
        get_skill("design.intelligence-search")
        list_domains()
        report = usage_stats()
        self.assertEqual(report["total_invocations"], 6)
        self.assertEqual(report["by_event"]["find_skills"], 3)
        self.assertEqual(report["by_event"]["get_skill"], 2)
        self.assertEqual(report["by_event"]["list_domains"], 1)

    def test_stats_top_skills(self):
        get_skill("design.intelligence-search")
        get_skill("design.intelligence-search")
        get_skill("qa.evidence-collection")
        report = usage_stats()
        top = report["top_skills"]
        self.assertEqual(top[0]["skill_id"], "design.intelligence-search")
        self.assertEqual(top[0]["count"], 2)

    def test_stats_top_domains(self):
        find_skills(domain="design")
        find_skills(domain="design")
        find_skills(domain="qa")
        report = usage_stats()
        top = report["top_domains"]
        self.assertEqual(top[0]["domain"], "design")
        self.assertEqual(top[0]["count"], 2)

    def test_stats_top_agents(self):
        find_skills(agent="ui-designer")
        find_skills(agent="evidence-collector")
        find_skills(agent="ui-designer")
        report = usage_stats()
        top = report["top_agents"]
        self.assertEqual(top[0]["agent"], "ui-designer")
        self.assertEqual(top[0]["count"], 2)

    def test_stats_first_last_ts(self):
        find_skills()
        find_skills()
        report = usage_stats()
        self.assertIsNotNone(report["first_ts"])
        self.assertIsNotNone(report["last_ts"])

    def test_stats_since_days_filter(self):
        # Escribir una entry "vieja" manualmente con ts > since_days
        find_skills()  # genera entry actual
        # Inyectar entry vieja
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": old_ts, "event": "find_skills", "domain": "OLD",
            }) + "\n")
        # since_days=5 debe excluir la entry vieja
        report = usage_stats(since_days=5)
        # find_skills inicial es de ahora -> incluido. OLD excluido.
        self.assertEqual(report["total_invocations"], 1)
        domains = {d["domain"] for d in report["top_domains"]}
        self.assertNotIn("OLD", domains)


# =====================================================================
#  Fail-open
# =====================================================================

class TestFailOpen(_IsolatedLogTestCase):

    def test_malformed_log_lines_skipped_no_crash(self):
        # Escribir JSONL con basura mezclada
        find_skills()  # entry valida
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write("not valid json\n")
            f.write('{"missing_event": true}\n')
            f.write('   \n')
            f.write(json.dumps({"event": "find_skills", "ts": "now"}) + "\n")
        report = usage_stats()
        # 1 valida del setUp + 1 inyectada valida = 2 procesadas
        # 1 not-json + 1 missing-event = 2 skipped
        self.assertEqual(report["total_invocations"], 2)
        self.assertGreaterEqual(report["entries_skipped_malformed"], 2)

    def test_api_still_returns_when_log_path_unwritable(self):
        # Apuntar log a path inexistente cuyo parent NO se puede crear
        # En Windows una ruta tipo "X:\imposible\..." si X: no existe.
        # Approach robusto: borrar el log_path actual y apuntar a una ruta
        # con char invalido (en NTFS '?' no es valido en nombre).
        os.environ["ATLAS_SKILLS_USAGE_LOG_PATH"] = str(
            self.tmp_path / "non?existent" / "log.jsonl"
        )
        # find_skills NO debe crashear, debe retornar resultado real
        result = find_skills(domain="design")
        self.assertIsInstance(result, list)
        # Log NO se escribio
        self.assertFalse((self.tmp_path / "non?existent").exists())


# =====================================================================
#  CLI stats
# =====================================================================

class TestStatsCLI(_IsolatedLogTestCase):

    def test_cli_stats_returns_json(self):
        find_skills(domain="design")
        get_skill("design.intelligence-search")
        env = os.environ.copy()
        env["ATLAS_SKILLS_USAGE_LOG_PATH"] = str(self.log_path)
        result = subprocess.run(
            [sys.executable, str(_TOOLS / "skills_registry.py"), "stats"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertEqual(result.returncode, 0,
                         f"stderr={result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["total_invocations"], 2)

    def test_cli_stats_since_flag(self):
        find_skills()
        env = os.environ.copy()
        env["ATLAS_SKILLS_USAGE_LOG_PATH"] = str(self.log_path)
        result = subprocess.run(
            [sys.executable, str(_TOOLS / "skills_registry.py"),
             "stats", "--since=7"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["since_days"], 7)


# =====================================================================
#  Backward compat: F21-1 sigue verde
# =====================================================================
# Se verifica al correr el sweep — este suite NO modifica F21-1.


if __name__ == "__main__":
    unittest.main(verbosity=2)
