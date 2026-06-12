"""
Projects Registry (Bloque F9)
==============================

Loader para config/projects.registry.yaml.

Registra proyectos externos conocidos por ATLAS para evitar perdida
de contexto operativo entre sesiones.

ALCANCE:
- Carga el catalogo declarativo (no modifica proyectos externos).
- Provee: list_projects, get_project, check_project_health.
- Fail-open: si el YAML no existe o falta PyYAML, retorna [] sin error.

DISABLE RUNTIME:
- ATLAS_PROJECTS_REGISTRY_DISABLED=1 -> list_projects retorna [] silenciosamente.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


REGISTRY_FILENAME = "projects.registry.yaml"
REGISTRY_DEFAULT_LOCATIONS = [
    Path.cwd() / "config" / REGISTRY_FILENAME,
    Path(__file__).parent.parent / "config" / REGISTRY_FILENAME,
]

REQUIRED_FIELDS = ("id", "name", "path", "type", "status",
                   "last_known_phase", "summary", "confidence")

VALID_TYPES = {"sibling_repo", "embedded", "submodule"}
VALID_STATUSES = {"active", "paused", "archived", "broken"}
VALID_CONFIDENCE = {"high", "medium", "low"}

_CACHED_PROJECTS: Optional[List[Dict[str, Any]]] = None
_CACHED_PATH: Optional[Path] = None


def _registry_disabled() -> bool:
    return os.environ.get(
        "ATLAS_PROJECTS_REGISTRY_DISABLED", ""
    ).lower() in ("1", "true", "yes")


def _resolve_registry_path() -> Optional[Path]:
    env_override = os.environ.get("ATLAS_PROJECTS_REGISTRY_PATH")
    if env_override:
        p = Path(env_override)
        return p if p.exists() else None
    for candidate in REGISTRY_DEFAULT_LOCATIONS:
        if candidate.exists():
            return candidate
    return None


def _load_yaml(path: Path) -> Optional[List[Dict[str, Any]]]:
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data.get("projects", []) if isinstance(data, dict) else None
    except Exception:
        return None


def _validate_entry(entry: Dict[str, Any]) -> Optional[str]:
    if not isinstance(entry, dict):
        return f"entry no es dict (tipo {type(entry).__name__})"
    for field in REQUIRED_FIELDS:
        if field not in entry:
            return f"falta campo '{field}' en id={entry.get('id', '<unknown>')!r}"
    if entry.get("type") not in VALID_TYPES:
        return f"type invalido: {entry.get('type')!r} (esperado {VALID_TYPES})"
    if entry.get("status") not in VALID_STATUSES:
        return f"status invalido: {entry.get('status')!r} (esperado {VALID_STATUSES})"
    if entry.get("confidence") not in VALID_CONFIDENCE:
        return f"confidence invalido: {entry.get('confidence')!r} (esperado {VALID_CONFIDENCE})"
    return None


def _load_registry() -> List[Dict[str, Any]]:
    global _CACHED_PROJECTS, _CACHED_PATH
    path = _resolve_registry_path()
    if path is None:
        return []
    if _CACHED_PATH == path and _CACHED_PROJECTS is not None:
        return _CACHED_PROJECTS
    raw = _load_yaml(path)
    if raw is None:
        return []
    projects = []
    for entry in raw:
        err = _validate_entry(entry)
        if err is None:
            projects.append(entry)
    _CACHED_PROJECTS = projects
    _CACHED_PATH = path
    return projects


# ============================================================
#  Public API
# ============================================================

def list_projects(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna todos los proyectos registrados, opcionalmente filtrados por status.

    Args:
        status: "active" | "paused" | "archived" | "broken" | None (todos)

    Returns:
        Lista de dicts. Lista vacia si el registry no existe o esta deshabilitado.
    """
    if _registry_disabled():
        return []
    projects = _load_registry()
    if status is None:
        return projects
    return [p for p in projects if p.get("status") == status]


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna el proyecto con el id dado, o None si no existe.
    """
    if _registry_disabled():
        return None
    for p in _load_registry():
        if p.get("id") == project_id:
            return p
    return None


def check_project_health(project_id: str) -> Dict[str, Any]:
    """
    Verifica el estado de salud de un proyecto registrado.

    Checks:
      - path existe en disco
      - si el tipo es sibling_repo: es un git repo valido
      - tiene PENDING.md
      - tiene BACKLOG.md (o README.md como fallback)
      - si requiere safe.directory (git dubious ownership)

    Retorna dict:
      {
        "id": str,
        "path": str,
        "checks": {
          "path_exists": bool,
          "is_git_repo": bool | None,        # None si type != sibling_repo
          "has_pending_md": bool,
          "has_backlog_md": bool,
          "git_dubious_ownership": bool | None,  # None si no es git repo
        },
        "warnings": list[str],
        "healthy": bool,
      }
    """
    project = get_project(project_id)
    if project is None:
        return {
            "id": project_id,
            "path": None,
            "checks": {},
            "warnings": [f"proyecto '{project_id}' no encontrado en el registry"],
            "healthy": False,
        }

    path = Path(project["path"])
    proj_type = project.get("type", "")
    checks: Dict[str, Any] = {}
    warnings: List[str] = []

    # check 1: path existe
    checks["path_exists"] = path.exists() and path.is_dir()
    if not checks["path_exists"]:
        warnings.append(f"path no encontrado: {path}")

    # check 2: es git repo (solo para sibling_repo)
    if proj_type == "sibling_repo" and checks["path_exists"]:
        checks["is_git_repo"] = (path / ".git").exists()
        if not checks["is_git_repo"]:
            warnings.append("no es un repositorio git (.git ausente)")
    else:
        checks["is_git_repo"] = None

    # check 3: git dubious ownership (solo si es git repo)
    if checks.get("is_git_repo"):
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--git-dir"],
                capture_output=True, text=True, timeout=5,
            )
            dubious = "dubious ownership" in result.stderr
            checks["git_dubious_ownership"] = dubious
            if dubious:
                warnings.append(
                    f"git dubious ownership — ejecutar: "
                    f"git config --global --add safe.directory {path}"
                )
        except Exception:
            checks["git_dubious_ownership"] = None
    else:
        checks["git_dubious_ownership"] = None

    # check 4: PENDING.md
    checks["has_pending_md"] = (path / "PENDING.md").exists()
    if not checks["has_pending_md"]:
        warnings.append("PENDING.md no encontrado")

    # check 5: BACKLOG.md o README.md
    checks["has_backlog_md"] = (path / "BACKLOG.md").exists()
    if not checks["has_backlog_md"]:
        # README es aceptable como fallback
        if (path / "README.md").exists():
            warnings.append("BACKLOG.md ausente (README.md presente como fallback)")
        else:
            warnings.append("BACKLOG.md y README.md ausentes")

    healthy = (
        checks["path_exists"]
        and checks.get("is_git_repo") is not False
        and not checks.get("git_dubious_ownership", False)
    )

    return {
        "id": project_id,
        "path": str(path),
        "checks": checks,
        "warnings": warnings,
        "healthy": healthy,
    }


# ============================================================
#  CLI (uso directo: python tools/projects_registry.py)
# ============================================================

def _cli() -> None:
    import json
    import sys

    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if not a.startswith("--")]

    cmd = args[0] if args else "list"

    if cmd == "list":
        projects = list_projects()
        if as_json:
            print(json.dumps(projects, ensure_ascii=False, indent=2))
        else:
            if not projects:
                print("No hay proyectos registrados (o registry no disponible).")
                return
            for p in projects:
                status_icon = {"active": "✓", "paused": "~", "archived": "x", "broken": "!"}.get(
                    p.get("status", ""), "?"
                )
                print(f"  [{status_icon}] {p['id']}  ({p['status']})  — {p['name']}")
                print(f"      path: {p['path']}")
                print(f"      fase: {p.get('last_known_phase', 'desconocida')}")
                print()

    elif cmd == "health" and len(args) >= 2:
        project_id = args[1]
        result = check_project_health(project_id)
        if as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            icon = "OK" if result["healthy"] else "DEGRADED"
            print(f"[{icon}] {result['id']} — {result['path']}")
            for k, v in result["checks"].items():
                print(f"  {k}: {v}")
            if result["warnings"]:
                print("  warnings:")
                for w in result["warnings"]:
                    print(f"    - {w}")

    elif cmd == "health":
        print("Uso: projects_registry.py health <project_id>", file=sys.stderr)
        sys.exit(1)

    else:
        print(f"Comando desconocido: {cmd!r}. Opciones: list, health <id>", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
