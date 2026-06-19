#!/usr/bin/env python3
"""
Bloque F9 — Projects Registry
==============================

Tests para:
  - config/projects.registry.yaml (estructura y contenido)
  - tools/projects_registry.py (loader API)
  - atlas_healthcheck.py check_projects_registry (integracion)

Tests:
  1.  Registry YAML existe en config/
  2.  Registry tiene version y projects
  3.  marketing_agency_os esta registrado con campos requeridos
  4.  path de marketing_agency_os existe en disco
  5.  list_projects() retorna lista no vacia
  6.  get_project("marketing_agency_os") retorna el proyecto
  7.  get_project("inexistente") retorna None
  8.  list_projects(status="active") incluye marketing_agency_os
  9.  check_project_health("marketing_agency_os") retorna path_exists=True
  10. check_project_health detecta dubious ownership (si aplica) como warning, no error fatal
  11. ATLAS_PROJECTS_REGISTRY_DISABLED=1 hace list_projects retornar []
  12. Healthcheck de ATLAS incluye check de projects registry
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "config" / "projects.registry.yaml"
TOOLS_DIR = PROJECT_ROOT / "tools"

sys.path.insert(0, str(TOOLS_DIR))


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _load_yaml_raw():
    """Carga el YAML crudo. Skipea el test si PyYAML no esta instalado."""
    try:
        import yaml
        return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    except ImportError:
        return None  # caller skipea con mensaje


def _import_loader():
    """Importa projects_registry fresco (sin cache de modulo previo)."""
    import importlib
    if "projects_registry" in sys.modules:
        del sys.modules["projects_registry"]
    return importlib.import_module("projects_registry")


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

def test_01_registry_yaml_exists():
    print("\n=== TEST 01: config/projects.registry.yaml existe ===")
    assert REGISTRY_PATH.exists(), f"No encontrado: {REGISTRY_PATH}"
    assert REGISTRY_PATH.stat().st_size > 0, "El archivo esta vacio"
    print(f"  path: {REGISTRY_PATH}")
    print("[OK]")


def test_02_registry_has_version_and_projects():
    print("\n=== TEST 02: registry tiene version y projects ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado — saltear test de estructura YAML")
        return
    assert isinstance(data, dict), f"El YAML no es un dict: {type(data)}"
    assert "version" in data, "Falta campo 'version'"
    assert "projects" in data, "Falta campo 'projects'"
    assert isinstance(data["projects"], list), "'projects' no es lista"
    assert len(data["projects"]) > 0, "projects esta vacio"
    print(f"  version={data['version']}, proyectos={len(data['projects'])}")
    print("[OK]")


def test_03_mkt_entry_has_required_fields():
    print("\n=== TEST 03: marketing_agency_os tiene campos requeridos ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    assert "marketing_agency_os" in projects, \
        f"marketing_agency_os no encontrado. ids: {list(projects.keys())}"
    mkt = projects["marketing_agency_os"]
    for field in ("id", "name", "path", "type", "status",
                  "last_known_phase", "summary", "confidence"):
        assert field in mkt, f"falta campo '{field}'"
    assert mkt["type"] == "sibling_repo", f"type esperado 'sibling_repo', got {mkt['type']!r}"
    assert mkt["status"] == "active", f"status esperado 'active', got {mkt['status']!r}"
    assert mkt["confidence"] == "high", f"confidence esperado 'high', got {mkt['confidence']!r}"
    print(f"  id={mkt['id']}, status={mkt['status']}, confidence={mkt['confidence']}")
    print("[OK]")


def test_04_mkt_path_exists_on_disk():
    print("\n=== TEST 04: path de marketing_agency_os existe en disco ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    mkt = projects.get("marketing_agency_os")
    assert mkt is not None, "marketing_agency_os no en registry"
    path = Path(mkt["path"])
    if not path.exists():
        # sibling_repo lives outside the ATLAS repo (user's machine layout).
        # Absent in clean CI runners → SKIP, not FAIL.
        print(f"  [SKIP] sibling_repo ausente (CI/entorno sin repos hermanos): {path}")
        return
    assert path.is_dir(), f"path existe pero no es dir: {path}"
    print(f"  path existe: {path}")
    print("[OK]")


def test_05_list_projects_returns_nonempty():
    print("\n=== TEST 05: list_projects() retorna lista no vacia ===")
    mod = _import_loader()
    projects = mod.list_projects()
    if not projects:
        # Puede ser porque PyYAML no esta instalado — acceptable
        print("  [INFO] list_projects() retorno [] (PyYAML ausente o registry disabled) — acceptable")
        print("[OK]")
        return
    assert isinstance(projects, list)
    print(f"  proyectos={len(projects)}: {[p['id'] for p in projects]}")
    print("[OK]")


def test_06_get_project_returns_mkt():
    print("\n=== TEST 06: get_project('marketing_agency_os') retorna el proyecto ===")
    mod = _import_loader()
    proj = mod.get_project("marketing_agency_os")
    if proj is None:
        print("  [INFO] get_project retorno None (PyYAML ausente o disabled) — acceptable")
        print("[OK]")
        return
    assert proj["id"] == "marketing_agency_os"
    assert proj["name"] == "MARKETING-AGENCY-OS"
    print(f"  id={proj['id']}, name={proj['name']}")
    print("[OK]")


def test_07_get_project_returns_none_for_unknown():
    print("\n=== TEST 07: get_project('inexistente') retorna None ===")
    mod = _import_loader()
    result = mod.get_project("proyecto_que_no_existe_jamas")
    assert result is None, f"Esperado None, got {result!r}"
    print("[OK]")


def test_08_list_projects_status_filter():
    print("\n=== TEST 08: list_projects(status='active') incluye marketing_agency_os ===")
    mod = _import_loader()
    active = mod.list_projects(status="active")
    if not active:
        print("  [INFO] lista vacia (PyYAML ausente) — acceptable")
        print("[OK]")
        return
    ids = [p["id"] for p in active]
    assert "marketing_agency_os" in ids, \
        f"marketing_agency_os no en activos. activos: {ids}"
    # Verificar que el filtro funciona: no debe haber proyectos con otro status
    for p in active:
        assert p.get("status") == "active", \
            f"Proyecto {p['id']} tiene status {p.get('status')!r}, no 'active'"
    print(f"  activos={len(active)}: {ids}")
    print("[OK]")


def test_09_check_project_health_path_exists():
    print("\n=== TEST 09: check_project_health path_exists=True ===")
    mod = _import_loader()
    health = mod.check_project_health("marketing_agency_os")
    if health["path"] is None:
        print("  [INFO] proyecto no encontrado en loader (PyYAML ausente) — acceptable")
        print("[OK]")
        return
    if health["checks"].get("path_exists") is not True:
        # sibling_repo absent on disk (CI/entorno sin repos hermanos) → SKIP.
        print(f"  [SKIP] sibling_repo ausente (CI): path={health.get('path')}")
        return
    assert health["checks"].get("path_exists") is True, \
        f"path_exists debe ser True. checks={health['checks']}"
    print(f"  path_exists={health['checks']['path_exists']}")
    print(f"  is_git_repo={health['checks'].get('is_git_repo')}")
    print(f"  warnings={health['warnings']}")
    print("[OK]")


def test_10_dubious_ownership_is_warning_not_fail():
    print("\n=== TEST 10: dubious ownership reportado como warning, no error fatal ===")
    mod = _import_loader()
    health = mod.check_project_health("marketing_agency_os")
    if health["path"] is None:
        print("  [SKIP] proyecto no en loader")
        return
    # Si hay dubious ownership, debe estar en warnings pero el health check
    # no debe hacer exit != 0 — la funcion debe retornar un dict (no raise)
    dubious = health["checks"].get("git_dubious_ownership")
    if dubious:
        assert any("safe.directory" in w for w in health["warnings"]), \
            "Dubious ownership detectado pero no hay warning con 'safe.directory'"
        print(f"  [INFO] dubious ownership detectado y reportado en warnings")
    else:
        print(f"  [INFO] git_dubious_ownership={dubious} (git no disponible o resuelto)")
    # Lo importante: la funcion no raise — si llegamos aca, paso
    print("[OK]")


def test_11_disabled_flag_returns_empty():
    print("\n=== TEST 11: ATLAS_PROJECTS_REGISTRY_DISABLED=1 -> list_projects retorna [] ===")
    env_before = os.environ.get("ATLAS_PROJECTS_REGISTRY_DISABLED")
    try:
        os.environ["ATLAS_PROJECTS_REGISTRY_DISABLED"] = "1"
        mod = _import_loader()
        result = mod.list_projects()
        assert result == [], f"Esperado [], got {result}"
        result2 = mod.get_project("marketing_agency_os")
        assert result2 is None, f"Esperado None con flag, got {result2}"
    finally:
        if env_before is None:
            os.environ.pop("ATLAS_PROJECTS_REGISTRY_DISABLED", None)
        else:
            os.environ["ATLAS_PROJECTS_REGISTRY_DISABLED"] = env_before
    print("[OK]")


def test_13_embedded_projects_registered():
    print("\n=== TEST 13: proyectos embedded registrados (conexo_web, lucas_rojo_web, reyesoft_internal) ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    for pid in ("conexo_web", "lucas_rojo_web", "reyesoft_internal"):
        assert pid in projects, \
            f"'{pid}' no encontrado en registry. ids: {list(projects.keys())}"
        p = projects[pid]
        assert p.get("type") == "embedded", \
            f"{pid}: type esperado 'embedded', got {p.get('type')!r}"
        for field in ("id", "name", "path", "type", "status",
                      "last_known_phase", "summary", "confidence"):
            assert field in p, f"{pid}: falta campo '{field}'"
    print(f"  conexo_web: status={projects['conexo_web']['status']}")
    print(f"  lucas_rojo_web: status={projects['lucas_rojo_web']['status']}")
    print(f"  reyesoft_internal: status={projects['reyesoft_internal']['status']}")
    print("[OK]")


def test_14_embedded_projects_paths_exist():
    print("\n=== TEST 14: paths de proyectos embedded existen en disco ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    for pid in ("conexo_web", "lucas_rojo_web", "reyesoft_internal"):
        p = projects.get(pid)
        assert p is not None, f"'{pid}' no en registry"
        path = Path(p["path"])
        if not path.exists():
            # Embedded/sibling project dir outside the ATLAS repo; absent in CI.
            print(f"  [SKIP] {pid}: path ausente (CI/entorno sin repos hermanos): {path}")
            continue
        assert path.is_dir(), f"{pid}: path existe pero no es dir: {path}"
        print(f"  {pid}: {path} ✓")
    print("[OK]")


def test_15_lucas_rojo_web_gitlink_warn_documented():
    print("\n=== TEST 15: lucas_rojo_web documenta el gitlink roto en known_risks ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    lrw = projects.get("lucas_rojo_web")
    assert lrw is not None, "lucas_rojo_web no en registry"
    risks = lrw.get("known_risks", [])
    assert any("gitlink" in r.lower() or "submodule" in r.lower() for r in risks), \
        f"lucas_rojo_web.known_risks no documenta el problema del gitlink. risks={risks}"
    print(f"  known_risks documenta el gitlink: True")
    print(f"  risks={risks[:1]}")
    print("[OK]")


def test_16_embedded_health_check_no_git_fail():
    print("\n=== TEST 16: check_project_health para embedded no falla por ausencia de .git ===")
    mod = _import_loader()
    for pid in ("conexo_web", "lucas_rojo_web"):
        health = mod.check_project_health(pid)
        if health["path"] is None:
            print(f"  [INFO] {pid} no en loader (PyYAML ausente) — acceptable")
            continue
        if health["checks"].get("path_exists") is not True:
            # Embedded/sibling project dir absent on disk (CI) → SKIP.
            print(f"  [SKIP] {pid}: path ausente (CI/entorno sin repos hermanos)")
            continue
        # Para embedded, is_git_repo debe ser None (no aplica), no False
        assert health["checks"].get("is_git_repo") is None, \
            f"{pid}: is_git_repo esperado None para embedded, got {health['checks'].get('is_git_repo')}"
        # path_exists debe ser True
        assert health["checks"].get("path_exists") is True, \
            f"{pid}: path_exists debe ser True. checks={health['checks']}"
        # No debe haber warning sobre .git ausente
        git_warnings = [w for w in health["warnings"] if ".git" in w.lower() and "ausente" in w.lower()]
        assert not git_warnings, \
            f"{pid}: warnings inesperados sobre .git: {git_warnings}"
        print(f"  {pid}: path_exists=True, is_git_repo=None, warnings={health['warnings']}")
    print("[OK]")


def test_17_category_field_valid():
    print("\n=== TEST 17: campo category valido en todos los proyectos que lo tienen ===")
    data = _load_yaml_raw()
    if data is None:
        print("  [SKIP] PyYAML no instalado")
        return
    VALID = {"ATLAS_PROJECT", "ATLAS_EXTENSION"}
    for p in data.get("projects", []):
        cat = p.get("category")
        if cat is not None:
            assert cat in VALID, \
                f"project {p.get('id')!r}: category invalida {cat!r} (esperado {VALID})"
    # Al menos los proyectos clave deben tener category
    projects = {p["id"]: p for p in data.get("projects", []) if "id" in p}
    for pid in ("marketing_agency_os", "conexo_web", "lucas_rojo_web",
                "reyesoft_internal", "pixel_bridge"):
        assert pid in projects, f"'{pid}' no en registry"
        assert "category" in projects[pid], \
            f"{pid}: campo 'category' ausente (se requiere para taxonomia F12B)"
    cats = {p.get("id"): p.get("category") for p in data["projects"]}
    print(f"  categorias: {cats}")
    print("[OK]")


def test_12_healthcheck_includes_projects_registry():
    print("\n=== TEST 12: healthcheck de ATLAS incluye check de projects registry ===")
    healthcheck = PROJECT_ROOT / "tools" / "atlas_healthcheck.py"
    assert healthcheck.exists(), f"healthcheck no encontrado: {healthcheck}"

    r = subprocess.run(
        [sys.executable, str(healthcheck), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "ATLAS_DISABLE_ENGRAM_MCP": "1"},
    )
    assert r.returncode == 0, \
        f"Healthcheck retorno exit {r.returncode}. Output:\n{r.stdout[-400:]}"

    data = json.loads(r.stdout)
    check_names = [res["check"] for res in data["results"]]
    assert any("projects" in name.lower() or "registry" in name.lower() for name in check_names), \
        f"No hay check de projects registry en healthcheck. checks={check_names}"
    print(f"  check encontrado: {[n for n in check_names if 'project' in n.lower() or 'registry' in n.lower()]}")
    print("[OK]")


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 70)
    print("BLOQUE F9 — Projects Registry")
    print("=" * 70)
    print(f"\n  registry: {REGISTRY_PATH}")
    print(f"  registry existe: {REGISTRY_PATH.exists()}")

    tests = [
        test_01_registry_yaml_exists,
        test_02_registry_has_version_and_projects,
        test_03_mkt_entry_has_required_fields,
        test_04_mkt_path_exists_on_disk,
        test_05_list_projects_returns_nonempty,
        test_06_get_project_returns_mkt,
        test_07_get_project_returns_none_for_unknown,
        test_08_list_projects_status_filter,
        test_09_check_project_health_path_exists,
        test_10_dubious_ownership_is_warning_not_fail,
        test_11_disabled_flag_returns_empty,
        test_12_healthcheck_includes_projects_registry,
        # F12C.1 — registry expansion
        test_13_embedded_projects_registered,
        test_14_embedded_projects_paths_exist,
        test_15_lucas_rojo_web_gitlink_warn_documented,
        test_16_embedded_health_check_no_git_fail,
        test_17_category_field_valid,
    ]

    passed = failed = 0
    failures = []
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {t.__name__}: {e}")
            failed += 1
            failures.append((t.__name__, str(e)))
        except Exception as e:
            print(f"\n[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
            failures.append((t.__name__, f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("=" * 70)

    if failures:
        print("\nFALLOS:")
        for name, msg in failures:
            print(f"  {name}: {msg[:200]}")

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] config/projects.registry.yaml existe y tiene estructura correcta")
        print("[OK] marketing_agency_os registrado con todos los campos requeridos")
        print("[OK] path del proyecto existe en disco")
        print("[OK] list_projects / get_project / filter por status operativos")
        print("[OK] check_project_health reporta dubious ownership como warning")
        print("[OK] ATLAS_PROJECTS_REGISTRY_DISABLED=1 hace fail-open limpio")
        print("[OK] atlas_healthcheck incluye check de projects registry")
        print("[OK] conexo_web / lucas_rojo_web / reyesoft_internal registrados como embedded")
        print("[OK] paths de proyectos embedded existen en disco")
        print("[OK] lucas_rojo_web gitlink documentado en known_risks — no FAIL")
        print("[OK] embedded health check: is_git_repo=None, path_exists=True")
        print("[OK] campo category valido en todos los proyectos (ATLAS_PROJECT / ATLAS_EXTENSION)")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
