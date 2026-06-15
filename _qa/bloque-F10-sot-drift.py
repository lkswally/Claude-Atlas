#!/usr/bin/env python3
"""
Bloque F10 — Single Source of Truth Drift Detection
=====================================================

Verifica que hooks/ y agents/ (carpetas de distribucion) esten en sync
con .claude/hooks/ y .claude/agents/ (source of truth en runtime).

FALLA si hay drift — eso es el objetivo.

Principio:
  .claude/hooks/  → source of truth  → hooks/  debe ser copia exacta
  .claude/agents/ → source of truth  → agents/ debe ser copia exacta

Archivos extra en hooks/ o agents/ que no esten en .claude/* son permitidos
(el distribuidor puede tener scripts extra) pero se reportan como WARN.

Tests:
  1. Todos los .js de .claude/hooks/ existen en hooks/ con hash identico
  2. Todos los .md de .claude/agents/ existen en agents/ con hash identico
  3. templates/settings.json tiene todos los hooks de .claude/settings.json
     (con placeholder __CLAUDE_HOME__ en lugar de .claude/hooks/)
  4. No hay archivos en hooks/ que no esten en .claude/hooks/ (WARN, no FAIL)
  5. No hay archivos en agents/ que no esten en .claude/agents/ (WARN, no FAIL)
"""

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_RUNTIME = PROJECT_ROOT / ".claude" / "hooks"
HOOKS_DIST    = PROJECT_ROOT / "hooks"
AGENTS_RUNTIME = PROJECT_ROOT / ".claude" / "agents"
AGENTS_DIST    = PROJECT_ROOT / "agents"
SETTINGS_REAL  = PROJECT_ROOT / ".claude" / "settings.json"
SETTINGS_TMPL  = PROJECT_ROOT / "templates" / "settings.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect_hooks(directory: Path, ext: str) -> dict:
    """Retorna {filename: sha256} para todos los archivos con extension ext."""
    if not directory.exists():
        return {}
    return {f.name: sha256(f) for f in directory.iterdir() if f.suffix == ext}


# ---------------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------------

def test_01_hooks_dist_matches_runtime():
    print("\n=== TEST 01: hooks/ es copia exacta de .claude/hooks/ ===")
    runtime = _collect_hooks(HOOKS_RUNTIME, ".js")
    dist    = _collect_hooks(HOOKS_DIST, ".js")

    missing  = []  # en runtime, no en dist
    mismatch = []  # en ambos, hash diferente

    for name, rhash in sorted(runtime.items()):
        if name not in dist:
            missing.append(name)
        elif dist[name] != rhash:
            mismatch.append(name)

    if missing:
        print(f"  [FAIL] Hooks faltantes en hooks/ (existen en .claude/hooks/): {missing}")
    if mismatch:
        print(f"  [FAIL] Hooks con contenido diferente: {mismatch}")

    assert not missing, f"Hooks faltantes en distribucion: {missing}"
    assert not mismatch, f"Hooks con drift de contenido: {mismatch}"
    print(f"  {len(runtime)} hooks en runtime, todos presentes y con hash identico en dist")
    print("[OK]")


def test_02_agents_dist_matches_runtime():
    print("\n=== TEST 02: agents/ es copia exacta de .claude/agents/ ===")
    runtime = _collect_hooks(AGENTS_RUNTIME, ".md")
    dist    = _collect_hooks(AGENTS_DIST, ".md")

    missing  = []
    mismatch = []

    for name, rhash in sorted(runtime.items()):
        if name not in dist:
            missing.append(name)
        elif dist[name] != rhash:
            mismatch.append(name)

    if missing:
        print(f"  [FAIL] Agents faltantes en agents/ (existen en .claude/agents/): {missing}")
    if mismatch:
        print(f"  [FAIL] Agents con contenido diferente: {mismatch}")

    assert not missing, f"Agents faltantes en distribucion: {missing}"
    assert not mismatch, f"Agents con drift de contenido: {mismatch}"
    print(f"  {len(runtime)} agents en runtime, todos presentes y con hash identico en dist")
    print("[OK]")


def test_03_templates_settings_has_all_hooks():
    """
    templates/settings.json debe registrar los mismos hooks que .claude/settings.json,
    usando __CLAUDE_HOME__/hooks/ como prefijo de path en lugar de .claude/hooks/.
    """
    print("\n=== TEST 03: templates/settings.json registra todos los hooks del runtime ===")
    assert SETTINGS_REAL.exists(), f"settings.json runtime no encontrado: {SETTINGS_REAL}"
    assert SETTINGS_TMPL.exists(), f"templates/settings.json no encontrado: {SETTINGS_TMPL}"

    real_data = json.loads(SETTINGS_REAL.read_text(encoding="utf-8"))
    tmpl_data = json.loads(SETTINGS_TMPL.read_text(encoding="utf-8"))

    def extract_hook_names(data):
        names = set()
        for ev, blocks in data.get("hooks", {}).items():
            for block in blocks:
                for h in block.get("hooks", []):
                    cmd = h.get("command", "")
                    # Extraer nombre del archivo .js / .js --flag
                    parts = cmd.split()
                    if len(parts) >= 2 and parts[0] == "node":
                        hook_file = Path(parts[1]).name  # e.g. "block-no-verify.js"
                        names.add(hook_file)
        return names

    real_hooks = extract_hook_names(real_data)
    tmpl_hooks = extract_hook_names(tmpl_data)

    missing_from_tmpl = real_hooks - tmpl_hooks
    if missing_from_tmpl:
        print(f"  [FAIL] Hooks registrados en runtime pero ausentes en template: {sorted(missing_from_tmpl)}")

    assert not missing_from_tmpl, \
        f"templates/settings.json le faltan hooks: {sorted(missing_from_tmpl)}"

    # Verificar que el template usa __CLAUDE_HOME__ (no rutas hardcodeadas)
    tmpl_text = SETTINGS_TMPL.read_text(encoding="utf-8")
    assert "__CLAUDE_HOME__" in tmpl_text, \
        "templates/settings.json no contiene placeholder __CLAUDE_HOME__"
    assert ".claude/hooks/" not in tmpl_text, \
        "templates/settings.json contiene rutas .claude/hooks/ hardcodeadas (debe usar __CLAUDE_HOME__)"

    print(f"  runtime={len(real_hooks)} hooks, template={len(tmpl_hooks)} hooks, todos presentes")
    print(f"  placeholder __CLAUDE_HOME__ presente: True")
    print("[OK]")


def test_04_no_extra_hooks_in_dist_warn():
    """Archivos extra en hooks/ que no esten en .claude/hooks/ — WARN, no FAIL."""
    print("\n=== TEST 04: (WARN) hooks/ no tiene archivos extra vs .claude/hooks/ ===")
    runtime = set(_collect_hooks(HOOKS_RUNTIME, ".js").keys())
    dist    = set(_collect_hooks(HOOKS_DIST, ".js").keys())
    extra = dist - runtime
    if extra:
        print(f"  [WARN] Archivos en hooks/ no presentes en .claude/hooks/: {sorted(extra)}")
        print("  (No es error — podria ser contenido legacy para distribucion)")
    else:
        print(f"  Sin archivos extra en hooks/")
    print("[OK]")  # Siempre pasa — es WARN informativo


def test_05_no_extra_agents_in_dist_warn():
    """Archivos extra en agents/ que no esten en .claude/agents/ — WARN, no FAIL."""
    print("\n=== TEST 05: (WARN) agents/ no tiene archivos extra vs .claude/agents/ ===")
    runtime = set(_collect_hooks(AGENTS_RUNTIME, ".md").keys())
    dist    = set(_collect_hooks(AGENTS_DIST, ".md").keys())
    extra = dist - runtime
    if extra:
        print(f"  [WARN] Archivos en agents/ no presentes en .claude/agents/: {sorted(extra)}")
    else:
        print(f"  Sin archivos extra en agents/")
    print("[OK]")


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\n" + "=" * 70)
    print("BLOQUE F10 — Single Source of Truth Drift Detection")
    print("=" * 70)
    print(f"\n  .claude/hooks/ : {HOOKS_RUNTIME} (source of truth)")
    print(f"  hooks/         : {HOOKS_DIST} (copia de distribucion)")
    print(f"  .claude/agents/: {AGENTS_RUNTIME} (source of truth)")
    print(f"  agents/        : {AGENTS_DIST} (copia de distribucion)")

    tests = [
        test_01_hooks_dist_matches_runtime,
        test_02_agents_dist_matches_runtime,
        test_03_templates_settings_has_all_hooks,
        test_04_no_extra_hooks_in_dist_warn,
        test_05_no_extra_agents_in_dist_warn,
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
        print("\nFALLOS (ejecutar tools/sync_dist.py para corregir):")
        for name, msg in failures:
            print(f"  {name}: {msg[:200]}")

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] hooks/ es copia exacta de .claude/hooks/ — sin drift")
        print("[OK] agents/ es copia exacta de .claude/agents/ — sin drift")
        print("[OK] templates/settings.json registra todos los hooks del runtime")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
