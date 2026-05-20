#!/usr/bin/env python3
"""
Skills Invocation Wrapper (Bloque 1C.1)
========================================

Wrapper Python para invocar el motor BM25 de design intelligence
(`~/.claude/design-data/search.js`) desde el dispatcher.

ALCANCE HONESTO:
- SOLO cubre ui-ux-pro-max-skill (motor BM25 sobre 161 industrias + 19 estilos)
- NO cubre otros skills (creative-coding, scroll-storytelling, etc.)
- NO modifica el motor JS — solo lo invoca y parsea su output
- Fallback controlado si la skill no esta disponible (no rompe pipeline)

Resolucion de la skill:
1. Param `skill_path` explicito
2. Env var `ATLAS_DESIGN_SKILL_PATH`
3. `~/.claude/design-data/search.js` (default benchmark)

API:
    inv = SkillsInvocation()
    available = inv.is_available()  # bool
    result = inv.query("saas b2b", domain="product")
    # result = {"status": "ok", "results": [...], "count": int}
    # o {"status": "unavailable", "reason": "..."}
    # o {"status": "error", "error": "..."}

CLI:
    python tools/skills_invocation.py "saas b2b" --domain=product
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


VALID_DOMAINS = {
    "style",
    "color",
    "chart",
    "landing",
    "product",
    "ux",
    "typography",
}


class SkillsInvocation:
    """Wrapper para ui-ux-pro-max-skill (BM25 design intelligence)."""

    DEFAULT_TIMEOUT_S = 5.0

    def __init__(
        self,
        skill_path: Optional[str] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self._skill_path = self._resolve_skill_path(skill_path)
        self._timeout = timeout_s

    @staticmethod
    def _resolve_skill_path(skill_path: Optional[str]) -> Optional[str]:
        """Resuelve la ruta a search.js. Retorna None si no se encuentra."""
        # 1. Param explicito
        if skill_path:
            return skill_path if Path(skill_path).exists() else None

        # 2. Env var
        env_path = os.environ.get("ATLAS_DESIGN_SKILL_PATH")
        if env_path and Path(env_path).exists():
            return env_path

        # 3. Default ~/.claude/design-data/search.js
        default = Path.home() / ".claude" / "design-data" / "search.js"
        if default.exists():
            return str(default)

        return None

    def is_available(self) -> bool:
        """Returns True si la skill esta accesible."""
        if not self._skill_path:
            return False
        # Node tiene que estar disponible
        return shutil.which("node") is not None

    def query(
        self,
        query: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Invoca la skill con un query + domain opcional.

        Retorna dict con shape:
        - {"status": "ok", "results": [...], "count": N, "domain": ...,
           "query": ..., "file": ...}
        - {"status": "unavailable", "reason": "skill o node missing"}
        - {"status": "error", "error": "..."}

        Domain valido: style | color | chart | landing | product | ux | typography
        Si no se pasa, search.js usa el default ("product").
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "reason": (
                    "ui-ux-pro-max-skill no disponible. "
                    "Verificar ~/.claude/design-data/search.js y `node` en PATH, "
                    "o ATLAS_DESIGN_SKILL_PATH env var."
                ),
                "skill_path": self._skill_path,
            }

        if domain and domain not in VALID_DOMAINS:
            return {
                "status": "error",
                "error": f"Domain invalido: {domain}. Validos: {sorted(VALID_DOMAINS)}",
            }

        if not isinstance(query, str) or not query.strip():
            return {
                "status": "error",
                "error": "Query debe ser string no vacio",
            }

        args = ["node", self._skill_path, query]
        if domain:
            args.extend(["--domain", domain])

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Skill timeout tras {self._timeout}s",
            }
        except (OSError, FileNotFoundError) as e:
            return {
                "status": "error",
                "error": f"No se pudo invocar skill: {type(e).__name__}: {e}",
            }

        if proc.returncode != 0:
            return {
                "status": "error",
                "error": f"Skill exit {proc.returncode}: {proc.stderr.strip()[:200]}",
            }

        # Parsear JSON output
        raw = proc.stdout.strip()
        if not raw:
            return {
                "status": "error",
                "error": "Skill retorno output vacio",
            }

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            return {
                "status": "error",
                "error": f"Output no parseable como JSON: {e}",
                "raw_preview": raw[:200],
            }

        if not isinstance(parsed, dict):
            return {
                "status": "error",
                "error": f"Output JSON no es dict: {type(parsed).__name__}",
            }

        # Output esperado: {"domain":..., "query":..., "file":..., "count":..., "results":[...]}
        results = parsed.get("results")
        if not isinstance(results, list):
            return {
                "status": "error",
                "error": "Output no tiene campo 'results' como lista",
                "raw_preview": raw[:200],
            }

        return {
            "status": "ok",
            "domain": parsed.get("domain"),
            "query": parsed.get("query"),
            "file": parsed.get("file"),
            "count": parsed.get("count", len(results)),
            "results": results,
            "skill_path": self._skill_path,
        }


# ============================================================
#  CLI (para uso desde tests o debugging)
# ============================================================

def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Uso: skills_invocation.py <query> [--domain=DOMAIN]\n"
            "     skills_invocation.py --check\n"
            f"Domains validos: {sorted(VALID_DOMAINS)}",
            file=sys.stderr,
        )
        return 2

    inv = SkillsInvocation()

    if sys.argv[1] == "--check":
        print(json.dumps({
            "available": inv.is_available(),
            "skill_path": inv._skill_path,
            "node_in_path": shutil.which("node") is not None,
        }, indent=2))
        return 0 if inv.is_available() else 1

    query = sys.argv[1]
    domain = None
    for arg in sys.argv[2:]:
        if arg.startswith("--domain="):
            domain = arg[len("--domain="):]

    result = inv.query(query, domain=domain)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
