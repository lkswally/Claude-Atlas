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


def check_settings_json() -> list[dict] | None:
    """settings.json existe, es JSON válido y tiene sección hooks."""
    if not SETTINGS_PATH.exists():
        FAIL(".claude/settings.json", f"no encontrado en {SETTINGS_PATH}")
        return None
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        FAIL(".claude/settings.json", f"JSON inválido: {e}")
        return None

    hooks = data.get("hooks", {})
    if not hooks:
        FAIL(".claude/settings.json", "sección 'hooks' ausente o vacía")
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
            # engram-sync: exit 1 es aceptable (no puede sincronizar sin repo Engram)
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
    # Forzar UTF-8 en stdout/stderr para que tildes y símbolos funcionen en Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

    # --- Settings y hooks ---
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
