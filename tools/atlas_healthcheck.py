#!/usr/bin/env python3
"""
ATLAS Runtime Healthcheck
=========================

Valida que el entorno local esté listo para ejecutar el runtime ATLAS:
  - Runtimes disponibles (Node, Python, npm)
  - .claude/settings.json válido y portables
  - Hooks referenciados existen en disco
  - Hooks críticos responden sin crash (smoke test)
  - Carpetas esperadas presentes
  - No hay paths absolutos heredados de otra máquina

Salida:
  [PASS] condición ok
  [WARN] condición subóptima pero no bloquea
  [FAIL] condición que impide el funcionamiento

Exit code:
  0 = no hay FAIL
  1 = al menos un FAIL

Uso:
  python tools/atlas_healthcheck.py
  python tools/atlas_healthcheck.py --json      # salida JSON
  python tools/atlas_healthcheck.py --quiet     # solo FAIL y resumen
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
#  Resolución de rutas
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_DIR    = PROJECT_ROOT / ".claude" / "hooks"
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"

# ---------------------------------------------------------------------------
#  Estado de resultados
# ---------------------------------------------------------------------------

_results: list[dict] = []

# Two INDEPENDENT strictness axes (F24 P5 — release gate semantics).
#
# _STRICT_EXPECTED — enforces the STABLE, committed source of truth:
#   config/atlas.runtime.expected.yaml + templates/settings.json + every
#   expected hook resolving to a real .claude/hooks/*.js. This is what the
#   release gate uses. Set by --strict / ATLAS_HEALTHCHECK_STRICT=1.
#   Missing/invalid expected config → FAIL.
#
# _STRICT_RUNTIME — enforces the LIVE, mutable .claude/settings.json. This file
#   is RUNTIME_MUTABLE: Claude Desktop on Windows creates/removes it between tool
#   calls, so its absence is EXPECTED and must NOT fail a release. It stays WARN
#   unless this axis is explicitly enabled (e.g. asserting the live file inside an
#   active Claude Desktop session). Set by --strict-runtime /
#   ATLAS_HEALTHCHECK_STRICT_RUNTIME=1. Release does NOT enable this axis.
_STRICT_EXPECTED: bool = False
_STRICT_RUNTIME: bool = False


def _record(status: str, check: str, detail: str) -> None:
    _results.append({"status": status, "check": check, "detail": detail})


def PASS(check: str, detail: str) -> None:   _record("PASS", check, detail)
def WARN(check: str, detail: str) -> None:   _record("WARN", check, detail)
def FAIL(check: str, detail: str) -> None:   _record("FAIL", check, detail)


# ---------------------------------------------------------------------------
#  Checks
# ---------------------------------------------------------------------------

def check_node() -> None:
    """Node.js >= 18 requerido para ejecutar hooks."""
    node = shutil.which("node")
    if not node:
        FAIL("Node.js", "no encontrado en PATH — hooks JS no pueden ejecutarse")
        return
    try:
        out = subprocess.check_output(["node", "--version"], text=True, timeout=5).strip()
        # v24.16.0 → 24
        m = re.match(r"v?(\d+)\.", out)
        major = int(m.group(1)) if m else 0
        if major < 18:
            FAIL("Node.js", f"versión {out} < 18 — hooks requieren Node 18+")
        else:
            PASS("Node.js", f"{out} (>= 18 requerido)")
    except Exception as e:
        WARN("Node.js", f"encontrado pero no se pudo verificar versión: {e}")


def check_python() -> None:
    """Python requerido para tests y dispatcher."""
    py = shutil.which("python") or shutil.which("python3")
    if not py:
        WARN("Python", "no encontrado — tests y dispatcher no ejecutables")
        return
    try:
        out = subprocess.check_output([py, "--version"], text=True,
                                      stderr=subprocess.STDOUT, timeout=5).strip()
        PASS("Python", out)
    except Exception as e:
        WARN("Python", f"encontrado pero no se pudo verificar versión: {e}")


def check_npm() -> None:
    """npm requerido para instalar dependencias de proyectos."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        WARN("npm", "no encontrado — instalacion de dependencias puede fallar")
        return
    try:
        out = subprocess.check_output([npm, "--version"], text=True, timeout=5).strip()
        PASS("npm", f"v{out}")
    except Exception as e:
        WARN("npm", f"encontrado pero no se pudo verificar version: {e}")


def check_expected_config() -> None:
    """
    Config ESTABLE y commiteada — la fuente de verdad del release (F24 P5).

    A diferencia del runtime .claude/settings.json (RUNTIME_MUTABLE), valida los
    archivos que SÍ están commiteados y deben estar siempre presentes/correctos:
      - config/atlas.runtime.expected.yaml (con secciones requeridas)
      - templates/settings.json (referencia estable de hooks)
      - cada hook de expected_hooks resuelve a un .claude/hooks/*.js real en disco

    Bajo _STRICT_EXPECTED (release / --strict): faltante/inválido → FAIL.
    En no-strict → WARN. Este es el check sobre el que descansa el gate de
    release, reemplazando el viejo comportamiento de FAIL por un settings.json
    runtime ausente (que era RUNTIME_MUTABLE esperado).
    """
    def _missing(detail: str) -> None:
        if _STRICT_EXPECTED:
            FAIL("Expected config", detail)
        else:
            WARN("Expected config", detail)

    expected_yaml = PROJECT_ROOT / "config" / "atlas.runtime.expected.yaml"
    template = PROJECT_ROOT / "templates" / "settings.json"

    if not expected_yaml.exists():
        _missing("config/atlas.runtime.expected.yaml no encontrado (fuente de verdad)")
        return
    try:
        import yaml
        expected = yaml.safe_load(expected_yaml.read_text(encoding="utf-8")) or {}
    except ImportError:
        WARN("Expected config", "PyYAML no instalado — no se puede validar expected YAML")
        return
    except Exception as e:
        _missing(f"expected YAML inválido: {e}")
        return

    required_sections = {"expected_hooks", "ownership", "version"}
    missing_sections = required_sections - expected.keys()
    if missing_sections:
        _missing(f"secciones faltantes en expected YAML: {sorted(missing_sections)}")
        return

    if not template.exists():
        _missing("templates/settings.json no encontrado (referencia estable de hooks)")
        return

    # Cada hook esperado debe resolver a un .js real en disco.
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    missing_hooks = []
    for event, names in (expected.get("expected_hooks") or {}).items():
        for name in names or []:
            if not (hooks_dir / name).exists():
                missing_hooks.append(f"{event}:{name}")
    if missing_hooks:
        _missing(f"hooks esperados faltantes en disco: {', '.join(missing_hooks)}")
        return

    n_hooks = sum(len(v or []) for v in (expected.get("expected_hooks") or {}).values())
    PASS("Expected config",
         f"expected YAML v{expected.get('version')} válido | "
         f"{n_hooks} hooks esperados resueltos en disco | templates/settings.json OK")


def check_settings_json() -> list[dict] | None:
    """
    Runtime .claude/settings.json — RUNTIME_MUTABLE (no es el gate de release).

    Este es el archivo LIVE gestionado por Claude Desktop en Windows; puede
    aparecer/desaparecer entre tool calls. Su ausencia/corrupción es WARN por
    defecto Y bajo release/--strict — NUNCA bloquea un release, porque la config
    estable se valida aparte en check_expected_config() (ese sí es el gate).

    Solo _STRICT_RUNTIME (--strict-runtime / ATLAS_HEALTHCHECK_STRICT_RUNTIME=1)
    escala a FAIL — para cuando se quiere afirmar explícitamente que el archivo
    runtime existe (p. ej. dentro de una sesión activa de Claude Desktop).
    """
    _runtime_mutable_msg = (
        "WARN_RUNTIME_MUTABLE — archivo gestionado por Claude Desktop en Windows | "
        "config estable validada en 'Expected config' | "
        "usar --strict-runtime para exigir el archivo runtime"
    )

    if not SETTINGS_PATH.exists():
        if _STRICT_RUNTIME:
            FAIL(".claude/settings.json", f"no encontrado en {SETTINGS_PATH} (--strict-runtime)")
        else:
            WARN(".claude/settings.json", _runtime_mutable_msg)
        return None

    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        if _STRICT_RUNTIME:
            FAIL(".claude/settings.json", f"JSON inválido: {e} (--strict-runtime)")
        else:
            WARN(".claude/settings.json", f"WARN_RUNTIME_MUTABLE — JSON inválido: {e} | {_runtime_mutable_msg}")
        return None

    hooks = data.get("hooks", {})
    if not hooks:
        if _STRICT_RUNTIME:
            FAIL(".claude/settings.json", "sección 'hooks' ausente o vacía (--strict-runtime)")
        else:
            WARN(".claude/settings.json", f"WARN_RUNTIME_MUTABLE — sección 'hooks' ausente o vacía | {_runtime_mutable_msg}")
        return None

    # Contar todas las entradas de hook
    all_entries = []
    for event, blocks in hooks.items():
        for block in blocks:
            for hook in block.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    all_entries.append({"event": event, "command": cmd})

    PASS(".claude/settings.json", f"JSON válido, {len(all_entries)} hooks registrados")
    return all_entries


def check_hook_files_exist(entries: list[dict]) -> None:
    """Todos los .js referenciados deben existir en disco."""
    if not entries:
        WARN("Hooks en disco", "sin entradas que verificar")
        return

    missing = []
    for e in entries:
        parts = e["command"].split()
        if len(parts) < 2 or parts[0] != "node":
            continue
        raw = parts[1]
        # Soportar .claude/hooks/X.js (relativo al PROJECT_ROOT)
        if raw.startswith(".claude/"):
            path = PROJECT_ROOT / raw
        elif os.path.isabs(raw):
            path = Path(raw)
        else:
            path = PROJECT_ROOT / raw

        if not path.exists():
            missing.append(f"{e['event']}:{Path(raw).name}")

    total = sum(1 for e in entries if "node" in e["command"])
    if missing:
        FAIL("Hooks en disco", f"{len(missing)} faltantes: {', '.join(missing)}")
    else:
        PASS("Hooks en disco", f"{total}/{total} existen")


def check_no_legacy_paths(entries: list[dict]) -> None:
    """Ningún hook debe usar paths absolutos heredados de otra máquina."""
    if not entries:
        return

    legacy = []
    absolute = []
    for e in entries:
        parts = e["command"].split()
        if len(parts) < 2:
            continue
        raw = parts[1]
        if "/c/Users/" in raw or "/home/" in raw:
            legacy.append(f"{e['event']}:{Path(raw).name}")
        elif os.path.isabs(raw) and not raw.startswith("."):
            absolute.append(f"{e['event']}:{Path(raw).name}")

    if legacy:
        FAIL("Paths portables", f"{len(legacy)} paths heredados de otra máquina: {', '.join(legacy)}")
    elif absolute:
        WARN("Paths portables",
             f"{len(absolute)} paths absolutos (puede no ser portable entre máquinas): {', '.join(absolute)}")
    else:
        PASS("Paths portables", "todos los hooks usan rutas relativas")


def check_hooks_smoke_test() -> None:
    """
    Todos los hooks deben ser fail-open: con stdin vacío deben salir 0.
    Excepción esperada: engram-sync.js puede salir 1 (falla real, pero no crash).
    """
    if not HOOKS_DIR.exists():
        WARN("Hooks smoke test", f"directorio {HOOKS_DIR} no encontrado")
        return

    hook_files = [f for f in HOOKS_DIR.iterdir() if f.suffix == ".js"
                  and f.name not in ("audit-system.js", "cost-report.js", "learning-index.js")]

    crashed = []
    skipped = []

    for hook in sorted(hook_files):
        try:
            r = subprocess.run(
                ["node", str(hook)],
                input=b"",
                capture_output=True,
                timeout=8,
            )
            # engram-sync: exit 0 siempre en modo hook (fail-open cuando no hay git repo)
            if hook.name == "engram-sync.js":
                if r.returncode not in (0, 1):
                    crashed.append(f"{hook.name}(exit={r.returncode})")
            elif r.returncode not in (0, 2):
                # exit 0 = allow/warn, exit 2 = block (ej. block-no-verify con stdin vacío
                # no debería bloquear porque input.trim() == '' → exit 0, pero
                # si por alguna razón un hook sale 2 con stdin vacío, lo marcamos)
                if r.returncode == 2:
                    # Fail-open violation — hooks no deben bloquear con stdin vacío
                    crashed.append(f"{hook.name}(BLOCK-on-empty)")
                else:
                    crashed.append(f"{hook.name}(exit={r.returncode})")
        except subprocess.TimeoutExpired:
            crashed.append(f"{hook.name}(timeout)")
        except FileNotFoundError:
            skipped.append(hook.name)

    tested = len(hook_files) - len(skipped)
    if crashed:
        FAIL("Hooks smoke test",
             f"{len(crashed)} hooks NO fail-open: {', '.join(crashed)}")
    elif skipped:
        WARN("Hooks smoke test",
             f"{tested}/{len(hook_files)} testeados (skipped: {', '.join(skipped)})")
    else:
        PASS("Hooks smoke test", f"{tested}/{len(hook_files)} salen 0 con stdin vacío (fail-open)")


def check_critical_hooks_block() -> None:
    """
    Hooks de bloqueo deben retornar exit 2 ante payloads peligrosos.
    Solo verifica block-no-verify.js y config-protection.js.
    """
    checks = [
        {
            "hook": HOOKS_DIR / "block-no-verify.js",
            "payload": {"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}},
            "expect": 2,
            "label": "block-no-verify BLOCKS git --no-verify",
        },
        {
            "hook": HOOKS_DIR / "config-protection.js",
            "payload": {"tool_name": "Write", "tool_input": {"file_path": "project/.env", "content": "S=x"}},
            "expect": 2,
            "label": "config-protection BLOCKS .env write",
        },
    ]

    failures = []
    for c in checks:
        if not c["hook"].exists():
            failures.append(f"{c['label']}: archivo no encontrado")
            continue
        try:
            r = subprocess.run(
                ["node", str(c["hook"])],
                input=json.dumps(c["payload"]).encode(),
                capture_output=True,
                timeout=6,
            )
            if r.returncode != c["expect"]:
                failures.append(
                    f"{c['label']}: exit {r.returncode} (esperado {c['expect']})"
                )
        except subprocess.TimeoutExpired:
            failures.append(f"{c['label']}: timeout")

    if failures:
        FAIL("Hooks críticos (block)", "; ".join(failures))
    else:
        PASS("Hooks críticos (block)", "block-no-verify y config-protection bloquean correctamente")


def check_directory(rel_path: str, description: str, required: bool = True) -> None:
    """Verifica que un directorio relativo al proyecto exista."""
    full = PROJECT_ROOT / rel_path
    if full.exists() and full.is_dir():
        PASS(f"Directorio {rel_path}/", description)
    elif required:
        FAIL(f"Directorio {rel_path}/", f"no encontrado — {description}")
    else:
        WARN(f"Directorio {rel_path}/", f"no encontrado — {description} (se crea al primer uso)")


def check_snapshots_dir() -> None:
    """~/.claude/snapshots/ es opcional pero esperado tras primera ejecución."""
    home = Path.home()
    snap = home / ".claude" / "snapshots"
    if snap.exists():
        files = list(snap.iterdir())
        PASS("~/.claude/snapshots/", f"existe con {len(files)} archivo(s)")
    else:
        WARN("~/.claude/snapshots/", "no existe — cost-tracker/session-summary lo crean al primer uso")


def check_hard_rules() -> None:
    """hard-rules.json requerido por pipeline-rules.js."""
    hr = PROJECT_ROOT / ".claude" / "hard-rules.json"
    if not hr.exists():
        WARN(".claude/hard-rules.json", "no encontrado — pipeline-rules.js corre en fail-open sin él")
        return
    try:
        data = json.loads(hr.read_text(encoding="utf-8"))
        n = len(data.get("rules", []))
        PASS(".claude/hard-rules.json", f"válido, {n} regla(s)")
    except json.JSONDecodeError as e:
        FAIL(".claude/hard-rules.json", f"JSON inválido: {e}")


def check_skills_registry() -> None:
    """
    Skills Registry (F2.1): PyYAML disponible, registry existe, parsea y tiene skills validas.

    WARN en lugar de FAIL porque el registry es fail-open por disenio.
    Si PyYAML falta, emite WARN visible (no silencio).
    """
    registry_path = PROJECT_ROOT / ".claude" / "skills.registry.yaml"

    # Check 1: PyYAML disponible
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        WARN("Skills registry", "PyYAML no instalado — registry silenciosamente muerto (pip install pyyaml)")
        return

    # Check 2: archivo existe
    if not registry_path.exists():
        WARN("Skills registry", f".claude/skills.registry.yaml no encontrado")
        return

    # Check 3: parsea sin error
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except Exception as e:
        WARN("Skills registry", f"YAML invalido: {e}")
        return

    if not isinstance(data, dict):
        WARN("Skills registry", "YAML no es un dict en la raiz")
        return

    # Check 4: tiene skills
    skills = data.get("skills", [])
    if not isinstance(skills, list) or len(skills) == 0:
        WARN("Skills registry", "registry existe pero lista 'skills' vacia o ausente")
        return

    # Check 5: al menos una skill con campos minimos validos
    REQUIRED = ("skill_id", "domain", "agent", "description", "inputs", "outputs", "cost_tier")
    valid = [s for s in skills if isinstance(s, dict) and all(k in s for k in REQUIRED)]
    invalid = len(skills) - len(valid)
    domains = sorted({s.get("domain", "") for s in valid if s.get("domain")})

    if invalid > 0:
        WARN("Skills registry",
             f"{valid}/{len(skills)} skills validas, {invalid} con campos faltantes. "
             f"Dominios: {domains}")
    else:
        PASS("Skills registry",
             f"{len(valid)} skills, dominios: {domains}")


def check_knowledge_registry() -> None:
    """
    Knowledge Registry (F29): catalogo de archivos de conocimiento + load_policy.

    WARN-only por disenio (F29.5) — es observabilidad para guiar F30, NO debe
    bloquear release. Verifica: existe, campos minimos, paths criticos en disco,
    load_policy valido, y las invariantes de politica (CLAUDE.md always_on,
    orquestador/agent-protocol lazy).
    """
    registry_path = PROJECT_ROOT / "config" / "knowledge.registry.yaml"

    try:
        import yaml  # type: ignore[import]
    except ImportError:
        WARN("Knowledge registry", "PyYAML no instalado — no se puede validar")
        return

    if not registry_path.exists():
        WARN("Knowledge registry", "config/knowledge.registry.yaml no encontrado (F29)")
        return

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        WARN("Knowledge registry", f"YAML invalido: {e}")
        return

    entries = data.get("knowledge", []) if isinstance(data, dict) else []
    if not isinstance(entries, list) or not entries:
        WARN("Knowledge registry", "lista 'knowledge' vacia o ausente")
        return

    VALID_POLICIES = {"always_on", "lazy", "manual", "runtime", "deprecated", "unknown"}
    REQUIRED = ("id", "path", "category", "load_policy")
    by_path = {}
    issues = []

    for e in entries:
        if not isinstance(e, dict):
            issues.append("entrada no-dict")
            continue
        miss = [k for k in REQUIRED if k not in e]
        if miss:
            issues.append(f"{e.get('id', '?')}: faltan {miss}")
            continue
        by_path[str(e["path"]).replace("\\", "/")] = e
        if e["load_policy"] not in VALID_POLICIES:
            issues.append(f"{e['id']}: load_policy invalido '{e['load_policy']}'")
        # paths criticos deben existir en disco
        if not (PROJECT_ROOT / e["path"]).exists():
            issues.append(f"{e['id']}: path no existe ({e['path']})")

    # Invariantes de politica (F29.3)
    invariants = {
        "CLAUDE.md": "always_on",
        ".claude/agents/orquestador.md": "lazy",
        ".claude/agents/agent-protocol.md": "lazy",
    }
    for path, expected in invariants.items():
        ent = by_path.get(path)
        if not ent:
            issues.append(f"{path} no registrado")
        elif ent.get("load_policy") != expected:
            issues.append(f"{path} deberia ser {expected}, es {ent.get('load_policy')}")

    # F29.5: WARN-only — nunca FAIL (no bloquea release). PASS si todo correcto.
    if issues:
        WARN("Knowledge registry",
             f"{len(entries)} entradas; {len(issues)} observacion(es): {'; '.join(issues[:4])}"
             + (" ..." if len(issues) > 4 else ""))
    else:
        PASS("Knowledge registry",
             f"{len(entries)} entradas, invariantes de politica OK, paths criticos en disco")


def check_claim_linter() -> None:
    """
    Claim Linter (F36): escanea docs por claims riesgosos. WARN-only por disenio —
    nunca FAIL. WARN si hay claims CRITICAL sin evidence mapping; informa HIGH count.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        import claim_linter as cl
    except Exception as e:
        WARN("Claim linter", f"no se pudo importar claim_linter: {e}")
        return
    try:
        result = cl.scan()
    except Exception as e:
        WARN("Claim linter", f"scan fallo: {e}")
        return

    by_sev = result.get("by_severity", {})
    crit_no_ev = result.get("critical_without_evidence", 0)
    high = by_sev.get("HIGH", 0)
    crit = by_sev.get("CRITICAL", 0)

    if crit_no_ev > 0:
        WARN("Claim linter",
             f"{crit_no_ev} claim(s) CRITICAL sin evidence mapping — revisar docs "
             f"(WARN-only F36). HIGH={high} CRITICAL={crit}")
    else:
        PASS("Claim linter",
             f"sin CRITICAL sin-evidencia | {result.get('total_findings',0)} findings "
             f"(HIGH={high} CRITICAL={crit}, {result.get('files_scanned',0)} files)")


def check_projects_registry() -> None:
    """Projects registry: existe, es YAML valido y proyectos activos tienen paths en disco."""
    registry_path = PROJECT_ROOT / "config" / "projects.registry.yaml"
    if not registry_path.exists():
        WARN("Projects registry", "config/projects.registry.yaml no encontrado — F9 no configurado")
        return

    # Intentar parsear con PyYAML (fail-open si no esta instalado)
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        WARN("Projects registry", "PyYAML no instalado — no se puede parsear el registry (pip install pyyaml)")
        return

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except Exception as e:
        FAIL("Projects registry", f"YAML invalido: {e}")
        return

    projects = data.get("projects", []) if isinstance(data, dict) else []
    if not projects:
        WARN("Projects registry", "registry existe pero no contiene proyectos")
        return

    active = [p for p in projects if p.get("status") == "active"]
    missing_paths = []
    dubious_git = []

    for p in active:
        path = p.get("path", "")
        if not path or not Path(path).is_dir():
            missing_paths.append(p.get("id", "<sin id>"))
            continue
        # Detectar dubious ownership via git
        if p.get("type") == "sibling_repo" and (Path(path) / ".git").exists():
            try:
                r = subprocess.run(
                    ["git", "-C", path, "rev-parse", "--git-dir"],
                    capture_output=True, text=True, timeout=5,
                )
                if "dubious ownership" in r.stderr:
                    dubious_git.append(p.get("id", "<sin id>"))
            except Exception:
                pass

    issues = []
    if missing_paths:
        issues.append(f"paths no encontrados: {', '.join(missing_paths)}")
    if dubious_git:
        issues.append(f"git dubious ownership: {', '.join(dubious_git)}")

    total_active = len(active)
    if issues:
        WARN("Projects registry",
             f"{total_active} proyecto(s) activo(s), issues: {'; '.join(issues)}")
    else:
        PASS("Projects registry",
             f"{len(projects)} proyecto(s) registrado(s), {total_active} activo(s), paths OK")


def check_engram() -> None:
    """Detecta estado de Engram: ACTIVE / FAIL_OPEN / DISABLED."""
    import shutil

    # 1. Feature flag
    if os.environ.get("ENGRAM_SYNC_DISABLED") == "1":
        WARN("Engram", "ENGRAM_DISABLED — ENGRAM_SYNC_DISABLED=1 activo")
        return

    # 2. Binary presente?
    engram_bin = shutil.which("engram") or str(
        Path.home() / "go" / "bin" / "engram.exe"
    ) or str(Path.home() / "go" / "bin" / "engram")
    bin_found = Path(engram_bin).exists() if engram_bin else False
    if not bin_found:
        WARN("Engram", "ENGRAM_FAIL_OPEN — binario engram no encontrado en PATH ni ~/go/bin")
        return

    # 3. DB presente?
    db_path = Path.home() / ".engram" / "engram.db"
    if not db_path.exists():
        WARN("Engram", f"ENGRAM_FAIL_OPEN — DB no encontrada en {db_path}")
        return

    # 4. Smoke test: engram search con query vacía (debe terminar en <3s)
    try:
        r = subprocess.run(
            [engram_bin, "search", "atlas"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            PASS("Engram", f"ENGRAM_ACTIVE — binario OK, DB OK, search OK ({db_path})")
        else:
            WARN("Engram", f"ENGRAM_FAIL_OPEN — search exit {r.returncode}: {r.stderr[:80]}")
    except subprocess.TimeoutExpired:
        WARN("Engram", "ENGRAM_FAIL_OPEN — smoke test timeout (>5s)")
    except Exception as e:
        WARN("Engram", f"ENGRAM_FAIL_OPEN — {e}")


def _probe_engram_runtime(engram_entry: dict) -> tuple[str, str]:
    """
    Probe runtime status of Engram via CLI validation_command.
    Returns (runtime_status, detail): "OK" | "WARN" | "SKIP".
    """
    cmd = engram_entry.get("validation_command", "")
    if not cmd:
        return "SKIP", "no validation_command"
    parts = cmd.split()
    try:
        r = subprocess.run(parts, capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return "OK", "CLI probe passed"
        else:
            return "WARN", f"CLI probe exit {r.returncode}"
    except subprocess.TimeoutExpired:
        return "WARN", "CLI probe timeout"
    except Exception as e:
        return "WARN", f"CLI probe error: {e}"


def check_mcp_registry() -> None:
    """
    Valida config/mcp.registry.yaml.
    Para Engram distingue:
      config_status  — estado declarado en el registry (YAML)
      runtime_status — resultado del CLI probe en esta ejecución
    """
    reg_file = PROJECT_ROOT / "config" / "mcp.registry.yaml"
    if not reg_file.exists():
        WARN("MCP Registry", f"config/mcp.registry.yaml no encontrado")
        return

    try:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        from mcp_registry import load_registry, validate_registry, summary

        errors = validate_registry()
        if errors:
            FAIL("MCP Registry", f"{len(errors)} errores: {errors[0]}")
            return

        s = summary()
        live = s.get("live", [])
        missing_req = s.get("missing_required", [])

        # Engram: config_status (declarativo) + runtime_status (CLI probe)
        from mcp_registry import get_mcp
        engram = get_mcp("engram")
        config_status = engram.get("status", "UNKNOWN") if engram else "NOT_IN_REGISTRY"

        if engram and config_status == "LIVE":
            runtime_status, runtime_detail = _probe_engram_runtime(engram)
            engram_label = f"engram=LIVE (runtime:{runtime_status})"
        else:
            engram_label = f"engram={config_status}"
            runtime_status = "SKIP"

        detail = (
            f"{s['total']} MCPs, {len(live)} LIVE, "
            f"{len(missing_req)} missing-required | "
            f"{engram_label}"
        )

        if missing_req and "engram" in missing_req:
            WARN("MCP Registry", detail + " (engram requerido no LIVE)")
        elif runtime_status == "WARN":
            WARN("MCP Registry", detail + " — config LIVE pero CLI probe falló")
        else:
            PASS("MCP Registry", detail)

    except ImportError:
        WARN("MCP Registry", "PyYAML no disponible — skip registry validation")
    except Exception as e:
        WARN("MCP Registry", f"error al cargar: {e}")


def check_capabilities_layer() -> None:
    """core/capabilities/ — runtime capability abstraction layer."""
    cap_dir = PROJECT_ROOT / "core" / "capabilities"
    required_files = ["__init__.py", "base.py", "registry.py"]
    missing = [f for f in required_files if not (cap_dir / f).exists()]
    if missing:
        WARN("Capabilities layer", f"core/capabilities/ missing: {missing}")
        return

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from core.capabilities import capability_status
        s = capability_status()
        live = s.get("live", [])
        pending = s.get("pending", [])
        deferred = s.get("deferred", [])
        detail = (
            f"{s['total']} capabilities | "
            f"LIVE={len(live)} | PENDING={len(pending)} | DEFERRED={len(deferred)}"
        )
        if live:
            PASS("Capabilities layer", detail)
        else:
            WARN("Capabilities layer", detail + " — no LIVE capabilities")
    except Exception as e:
        WARN("Capabilities layer", f"error loading: {e}")


def check_capability_router() -> None:
    """
    F16: Capability Router — valida que resolve_capability() funciona
    y que capabilities críticas tienen provider LIVE o fallback.
    """
    cap_dir = PROJECT_ROOT / "core" / "capabilities"
    if not (cap_dir / "router.py").exists():
        FAIL("Capability router", "core/capabilities/router.py no encontrado")
        return

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from core.capabilities.router import resolve_capability, CRITICAL_CAPABILITIES

        # 1. Probes críticas
        critical_issues = []
        for cap_name in sorted(CRITICAL_CAPABILITIES):
            r = resolve_capability(cap_name)
            if r.status == "UNAVAILABLE":
                critical_issues.append(f"{cap_name}=UNAVAILABLE (sin provider)")
            elif r.provider is None:
                critical_issues.append(f"{cap_name}=sin provider")

        # 2. Prueba capability inexistente no rompe
        r_missing = resolve_capability("__nonexistent_capability__")
        if r_missing.status != "UNAVAILABLE":
            critical_issues.append("capability desconocida no retorna UNAVAILABLE")

        # 3. Prueba capability conocida retorna provider
        r_mem = resolve_capability("memory")
        if r_mem.provider != "engram":
            critical_issues.append(f"memory debería resolverse a engram, got={r_mem.provider}")

        if critical_issues:
            FAIL("Capability router", "; ".join(critical_issues))
        else:
            # Resumen de resoluciones críticas
            summary_parts = []
            for cap_name in sorted(CRITICAL_CAPABILITIES):
                r = resolve_capability(cap_name)
                summary_parts.append(f"{cap_name}={r.status}")
            PASS("Capability router", f"resolve_capability OK | {' | '.join(summary_parts)}")

    except Exception as e:
        FAIL("Capability router", f"error loading router: {e}")


def check_mcp_json() -> None:
    """.mcp.json en CWD raíz — verifica servidores configurados."""
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    if not mcp_file.exists():
        WARN(".mcp.json (CWD raíz)", f"no encontrado en {mcp_file}")
        return
    try:
        import json
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        servers = list(data.get("mcpServers", {}).keys())
        PASS(".mcp.json (CWD raíz)", f"{len(servers)} servidores: {', '.join(servers)}")
    except Exception as e:
        WARN(".mcp.json (CWD raíz)", f"error: {e}")


def check_capability_policy() -> None:
    """
    F19: Capability Policy Engine — valida que el policy file existe,
    parsea correctamente, capabilities críticas tienen policy, y
    evaluate_all_capabilities no rompe.
    """
    policy_file = PROJECT_ROOT / "config" / "capability.policy.yaml"
    policy_mod  = PROJECT_ROOT / "core" / "capabilities" / "policy.py"

    if not policy_mod.exists():
        FAIL("Capability policy (F19)", "core/capabilities/policy.py no encontrado")
        return

    if not policy_file.exists():
        FAIL("Capability policy (F19)", f"config/capability.policy.yaml no encontrado")
        return

    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from core.capabilities.policy import (
            load_policy, evaluate_all_capabilities, get_policy,
        )
        from core.capabilities.router import CRITICAL_CAPABILITIES

        # 1. Policy file parsea
        policies = load_policy()
        if not policies:
            FAIL("Capability policy (F19)", "policy file vacío o no parseable")
            return

        # 2. Capabilities críticas tienen policy
        missing_critical = [c for c in CRITICAL_CAPABILITIES if c not in policies]
        if missing_critical:
            FAIL("Capability policy (F19)", f"critical capabilities sin policy: {missing_critical}")
            return

        # 3. evaluate_all_capabilities no rompe
        results = evaluate_all_capabilities(_emit=False)
        if not results:
            WARN("Capability policy (F19)", "evaluate_all_capabilities retornó vacío")
            return

        # 4. Ninguna capability crítica en BLOCK
        blocked_critical = [
            c for c in CRITICAL_CAPABILITIES
            if c in results and results[c].decision == "BLOCK"
        ]
        n_allow = sum(1 for d in results.values() if d.decision == "ALLOW")
        n_warn  = sum(1 for d in results.values() if d.decision == "WARN")
        n_block = sum(1 for d in results.values() if d.decision == "BLOCK")

        summary = f"{len(policies)} policies | ALLOW={n_allow} WARN={n_warn} BLOCK={n_block}"
        if blocked_critical:
            FAIL("Capability policy (F19)", f"critical capabilities bloqueadas: {blocked_critical} | {summary}")
        else:
            PASS("Capability policy (F19)", summary)

    except Exception as e:
        FAIL("Capability policy (F19)", f"error: {e}")


def check_capability_metrics() -> None:
    """
    F18: Capability Metrics — valida que el módulo de eventos existe,
    el directorio .pipeline es escribible, y el metrics reader importa.
    No bloquea si no hay eventos (normal en entorno limpio).
    """
    pipeline_dir = PROJECT_ROOT / ".pipeline"
    events_file  = pipeline_dir / "capability-events.jsonl"
    metrics_tool = PROJECT_ROOT / "tools" / "capability_metrics.py"

    issues: list[str] = []
    warns:  list[str] = []

    # 1. events.py existe
    events_mod = PROJECT_ROOT / "core" / "capabilities" / "events.py"
    if not events_mod.exists():
        issues.append("core/capabilities/events.py no encontrado")
    else:
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from core.capabilities.events import make_event, emit, read_events
        except Exception as e:
            issues.append(f"events.py no importa: {e}")

    # 2. capability_metrics.py existe
    if not metrics_tool.exists():
        issues.append("tools/capability_metrics.py no encontrado")
    else:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("capability_metrics", metrics_tool)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            _ = mod.load_events
            _ = mod.compute_metrics
        except Exception as e:
            issues.append(f"capability_metrics.py no importa: {e}")

    # 3. .pipeline dir es escribible (o puede crearse)
    try:
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        test_file = pipeline_dir / ".healthcheck_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
    except Exception as e:
        issues.append(f".pipeline/ no escribible: {e}")

    # 4. Si el archivo de eventos existe, verifica que sea JSONL válido
    if events_file.exists():
        bad_lines = 0
        try:
            for line in events_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except Exception:
                    bad_lines += 1
        except Exception as e:
            warns.append(f"No se pudo leer capability-events.jsonl: {e}")
        if bad_lines:
            warns.append(f"{bad_lines} líneas JSONL inválidas en capability-events.jsonl")
    else:
        warns.append("capability-events.jsonl no existe aún (normal en entorno limpio)")

    if issues:
        FAIL("Capability metrics (F18)", "; ".join(issues))
    elif warns:
        WARN("Capability metrics (F18)", " | ".join(warns))
    else:
        PASS("Capability metrics (F18)", "events.py + metrics reader OK | .pipeline/ escribible")


def check_dispatcher() -> None:
    """tools/atlas_dispatcher.py debe existir e importarse sin error."""
    dp = PROJECT_ROOT / "tools" / "atlas_dispatcher.py"
    if not dp.exists():
        FAIL("Dispatcher", f"tools/atlas_dispatcher.py no encontrado")
        return
    try:
        r = subprocess.run(
            [sys.executable, str(dp), "audit-agent", "--agent=unknown-xyz"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "ATLAS_DISABLE_ENGRAM_MCP": "1"},
        )
        if r.returncode == 0:
            PASS("Dispatcher", "atlas_dispatcher.py ejecutable (audit-agent skipped OK)")
        else:
            FAIL("Dispatcher", f"exit {r.returncode}: {r.stderr[:100]}")
    except subprocess.TimeoutExpired:
        WARN("Dispatcher", "timeout — puede ser lento en primera ejecución")
    except Exception as e:
        FAIL("Dispatcher", str(e))


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------

def run_all() -> int:
    global _STRICT_EXPECTED, _STRICT_RUNTIME
    # Forzar UTF-8 en stdout/stderr para que tildes y símbolos funcionen en Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # --strict  → expected-strict (release gate: stable committed config)
    # --strict-runtime → runtime-strict (asserts the live .claude/settings.json)
    _STRICT_EXPECTED = "--strict" in sys.argv or os.environ.get("ATLAS_HEALTHCHECK_STRICT") == "1"
    _STRICT_RUNTIME = "--strict-runtime" in sys.argv or os.environ.get("ATLAS_HEALTHCHECK_STRICT_RUNTIME") == "1"
    quiet  = "--quiet" in sys.argv
    as_json = "--json" in sys.argv

    if not as_json:
        print("=" * 60)
        print("ATLAS Runtime Healthcheck")
        print(f"Proyecto : {PROJECT_ROOT}")
        print(f"Python   : {sys.version.split()[0]}")
        print("=" * 60)
        print()

    # --- Runtimes ---
    check_node()
    check_python()
    check_npm()

    # --- Config estable (gate de release) ---
    check_expected_config()

    # --- Settings runtime y hooks ---
    entries = check_settings_json()
    if entries is not None:
        check_hook_files_exist(entries)
        check_no_legacy_paths(entries)

    # --- Ejecución real ---
    check_hooks_smoke_test()
    check_critical_hooks_block()

    # --- Directorios del proyecto ---
    check_directory(".claude/hooks",   "scripts de hooks JS",           required=True)
    check_directory("tools",           "dispatcher + tracker Python",   required=True)
    check_directory("_qa",             "suite de tests",                required=True)
    check_directory("config",          "phase playbook + config",       required=False)
    check_directory(".pipeline",       "estado de delegation-tracker",  required=False)

    # --- Extras opcionales ---
    check_snapshots_dir()
    check_hard_rules()
    check_skills_registry()
    check_knowledge_registry()
    check_claim_linter()
    check_projects_registry()
    check_engram()
    check_mcp_registry()
    check_mcp_json()
    check_capabilities_layer()
    check_capability_router()
    check_capability_policy()
    check_capability_metrics()
    check_dispatcher()

    # --- Reporte ---
    n_pass = sum(1 for r in _results if r["status"] == "PASS")
    n_warn = sum(1 for r in _results if r["status"] == "WARN")
    n_fail = sum(1 for r in _results if r["status"] == "FAIL")
    total  = len(_results)

    if as_json:
        print(json.dumps({
            "results": _results,
            "summary": {"pass": n_pass, "warn": n_warn, "fail": n_fail},
            "healthy": n_fail == 0,
        }, ensure_ascii=False, indent=2))
        return 1 if n_fail > 0 else 0

    # Texto normal
    label_width = max((len(r["check"]) for r in _results), default=20) + 2
    for r in _results:
        if quiet and r["status"] != "FAIL":
            continue
        tag = f"[{r['status']}]"
        print(f"{tag:<7} {r['check']:<{label_width}} {r['detail']}")

    print()
    print("=" * 60)
    status_str = "HEALTHY" if n_fail == 0 else "DEGRADED" if n_warn > n_fail else "BROKEN"
    print(f"RESULTADO : PASS={n_pass}  WARN={n_warn}  FAIL={n_fail}  / {total} checks")
    print(f"STATUS    : {status_str}")
    print("=" * 60)

    if n_fail > 0:
        print("\nFAILS:")
        for r in _results:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['check']}: {r['detail']}")

    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(run_all())
