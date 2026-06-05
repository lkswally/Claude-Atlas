"""
Skills Registry (Bloque F2.1 MVP)
==================================

Loader + API de busqueda para .claude/skills.registry.yaml.

ALCANCE HONESTO:
- Carga el catalogo declarativo (no inventa skills).
- Provee 3 funciones publicas: find_skills, get_skill, list_domains.
- Sin DSL custom, sin activation contracts, sin precondiciones evaluables.
- Solo matching de string simple sobre fields (domain, agent, applies_when).
- Fail-open: si el YAML no existe o esta malformado, retorna lista vacia.

DISABLE RUNTIME:
- ATLAS_SKILLS_REGISTRY_DISABLED=1 -> find_skills retorna [] silenciosamente.

NO ES:
- Un motor de activacion (eso es F2.2 si se justifica)
- Un sistema de versionado (asume v1 implicito)
- Un framework — es un indice + helper de busqueda

USO TIPICO:
    from skills_registry import find_skills, get_skill
    skills = find_skills(domain="design")
    skill = get_skill("design.intelligence-search")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


REGISTRY_FILENAME = "skills.registry.yaml"
REGISTRY_DEFAULT_LOCATIONS = [
    Path.cwd() / ".claude" / REGISTRY_FILENAME,
    Path(__file__).parent.parent / ".claude" / REGISTRY_FILENAME,
]

REQUIRED_FIELDS = ("skill_id", "domain", "agent", "description",
                   "inputs", "outputs", "cost_tier")
VALID_COST_TIERS = {"low", "medium", "high"}


# ============================================================
#  Internal cache (lazy load)
# ============================================================

_CACHED_SKILLS: Optional[List[Dict[str, Any]]] = None
_CACHED_PATH: Optional[Path] = None


def _registry_disabled() -> bool:
    """ATLAS_SKILLS_REGISTRY_DISABLED=1 fuerza modo no-op."""
    return os.environ.get(
        "ATLAS_SKILLS_REGISTRY_DISABLED", ""
    ).lower() in ("1", "true", "yes")


def _resolve_registry_path() -> Optional[Path]:
    """Busca el YAML en ubicaciones conocidas. None si no existe."""
    env_override = os.environ.get("ATLAS_SKILLS_REGISTRY_PATH")
    if env_override:
        p = Path(env_override)
        return p if p.exists() else None
    for candidate in REGISTRY_DEFAULT_LOCATIONS:
        if candidate.exists():
            return candidate
    return None


def _validate_skill_entry(entry: Dict[str, Any]) -> Optional[str]:
    """
    Valida shape minimo de una entry. Retorna mensaje de error o None.
    NO raise — el caller decide que hacer (skip o reportar).
    """
    if not isinstance(entry, dict):
        return f"entry no es dict (recibido {type(entry).__name__})"

    for field in REQUIRED_FIELDS:
        if field not in entry:
            return f"falta campo obligatorio '{field}' en skill_id={entry.get('skill_id', '<unknown>')!r}"

    if not isinstance(entry["skill_id"], str) or "." not in entry["skill_id"]:
        return f"skill_id invalido: {entry['skill_id']!r} (esperado 'domain.name')"

    if entry["cost_tier"] not in VALID_COST_TIERS:
        return f"cost_tier invalido: {entry['cost_tier']!r} (esperado low|medium|high)"

    for list_field in ("inputs", "outputs"):
        if not isinstance(entry[list_field], list):
            return f"{list_field} debe ser lista en skill_id={entry['skill_id']!r}"

    return None


def _load_registry(path: Optional[Path] = None,
                   *, force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    Carga y cachea el registry. Fail-open: errores devuelven lista vacia.

    Args:
        path: override de path (None = autodetect)
        force_reload: ignora cache. Para tests.
    """
    global _CACHED_SKILLS, _CACHED_PATH

    if _registry_disabled():
        return []

    resolved = path or _resolve_registry_path()
    if resolved is None:
        return []

    if (not force_reload
            and _CACHED_SKILLS is not None
            and _CACHED_PATH == resolved):
        return _CACHED_SKILLS

    try:
        import yaml
    except ImportError:
        return []

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return []

    if not isinstance(data, dict):
        return []

    raw_skills = data.get("skills")
    if not isinstance(raw_skills, list):
        return []

    # Validar y filtrar — entries invalidas se descartan silenciosamente
    # (fail-open). Para diagnostico via CLI se expone validate_registry().
    valid: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for entry in raw_skills:
        err = _validate_skill_entry(entry)
        if err is not None:
            continue
        sid = entry["skill_id"]
        if sid in seen_ids:
            # Duplicado -> skip silencioso
            continue
        seen_ids.add(sid)
        valid.append(entry)

    _CACHED_SKILLS = valid
    _CACHED_PATH = resolved
    return valid


def _reset_cache() -> None:
    """Solo para tests."""
    global _CACHED_SKILLS, _CACHED_PATH
    _CACHED_SKILLS = None
    _CACHED_PATH = None


# ============================================================
#  API publica
# ============================================================

def find_skills(
    domain: Optional[str] = None,
    agent: Optional[str] = None,
    applies_when: Optional[Dict[str, str]] = None,
    *,
    registry_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Busca skills por filtros. Filtros se combinan con AND.

    Args:
        domain: filtra por dominio exacto (ej: "design")
        agent: filtra por agente exacto (ej: "ui-designer")
        applies_when: dict {key: value} — matching simple sobre strings
                      "key == value" en el campo applies_when de cada entry.
                      Solo se requiere que UNA de las condiciones del entry
                      matchee, no todas (OR sobre applies_when).
        registry_path: override (tests)

    Returns:
        Lista de skills (dicts). Lista vacia si nada matchea o registry
        no disponible. NO raise.

    Sin filtros: retorna TODAS las skills cargadas.
    """
    skills = _load_registry(registry_path)
    if not skills:
        return []

    result = skills

    if domain is not None:
        result = [s for s in result if s.get("domain") == domain]

    if agent is not None:
        result = [s for s in result if s.get("agent") == agent]

    if applies_when:
        result = [
            s for s in result
            if _matches_applies_when(s.get("applies_when") or [], applies_when)
        ]

    return result


def get_skill(
    skill_id: str,
    *,
    registry_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Obtiene una skill por id exacto. None si no existe (NO raise).
    """
    if not isinstance(skill_id, str) or not skill_id:
        return None
    skills = _load_registry(registry_path)
    for s in skills:
        if s.get("skill_id") == skill_id:
            return s
    return None


def list_domains(*, registry_path: Optional[Path] = None) -> List[str]:
    """
    Lista unica de dominios presentes en el registry. Ordenada alfabeticamente.
    """
    skills = _load_registry(registry_path)
    return sorted({s.get("domain") for s in skills if s.get("domain")})


def validate_registry(
    *,
    registry_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Diagnostico explicito del registry. Retorna report.
    Util para CLI / debugging. NO afecta cache.
    """
    resolved = registry_path or _resolve_registry_path()
    if resolved is None:
        return {
            "ok": False,
            "path": None,
            "reason": "registry file not found in known locations",
        }

    try:
        import yaml
    except ImportError:
        return {"ok": False, "path": str(resolved), "reason": "PyYAML missing"}

    try:
        with open(resolved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        return {"ok": False, "path": str(resolved), "reason": f"{type(e).__name__}: {e}"}

    if not isinstance(data, dict):
        return {"ok": False, "path": str(resolved), "reason": "root is not a mapping"}

    raw_skills = data.get("skills")
    if not isinstance(raw_skills, list):
        return {"ok": False, "path": str(resolved), "reason": "'skills' is not a list"}

    errors: List[str] = []
    seen_ids: set = set()
    valid_count = 0
    for i, entry in enumerate(raw_skills):
        err = _validate_skill_entry(entry)
        if err:
            errors.append(f"entry[{i}]: {err}")
            continue
        sid = entry["skill_id"]
        if sid in seen_ids:
            errors.append(f"entry[{i}]: duplicate skill_id {sid!r}")
            continue
        seen_ids.add(sid)
        valid_count += 1

    return {
        "ok": len(errors) == 0,
        "path": str(resolved),
        "total_entries": len(raw_skills),
        "valid": valid_count,
        "errors": errors,
    }


# ============================================================
#  Helpers internos
# ============================================================

def _matches_applies_when(
    entry_conditions: List[str],
    filter_dict: Dict[str, str],
) -> bool:
    """
    Matcher simple: para cada (k, v) en filter_dict, busca un string
    "k == v" (con varios espacios tolerados) en entry_conditions.

    Retorna True si AL MENOS UNA condicion del filtro matchea.
    Esto es deliberadamente OR (no AND) para que find_skills sea util:
    una skill que "applies_when phase == fase_2" debe aparecer cuando el
    caller filtra por phase=fase_2, aunque la skill tambien tenga otras
    condiciones que no se pasaron.
    """
    if not entry_conditions or not filter_dict:
        return False

    # Normalizar conditions a tuplas (left, right) si tienen "=="
    normalized: List[tuple[str, str]] = []
    for cond in entry_conditions:
        if not isinstance(cond, str):
            continue
        if "==" not in cond:
            continue
        left, _, right = cond.partition("==")
        normalized.append((left.strip(), right.strip()))

    for key, value in filter_dict.items():
        for left, right in normalized:
            if left == key and right == str(value):
                return True
    return False


# ============================================================
#  CLI (debug / validacion)
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        report = validate_registry()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report.get("ok") else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "list":
        skills = find_skills()
        print(json.dumps(
            [{"skill_id": s["skill_id"], "domain": s["domain"],
              "agent": s["agent"]} for s in skills],
            indent=2, ensure_ascii=False,
        ))
        sys.exit(0)

    print(
        "usage:\n"
        "  python tools/skills_registry.py validate\n"
        "  python tools/skills_registry.py list\n",
        file=sys.stderr,
    )
    sys.exit(1)
