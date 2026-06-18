#!/usr/bin/env python3
"""
Validacion de Fase 5 — Settings Path Normalization

Tests:
1. No quedan paths /c/Users/Lucas/ en settings.json
2. Todos los .js referenciados existen en .claude/hooks/
3. qa-auto-audit.js esta registrado en PostToolUse
4. delegation-tracker.js esta registrado en PostToolUse
5. Todos los hooks usan paths relativos (ninguno con /c/ o C:\\)
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "settings.json"
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"

_USING_TEMPLATE = False  # set when runtime absent


def load_settings():
    global _USING_TEMPLATE
    if SETTINGS_PATH.exists():
        _USING_TEMPLATE = False
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    # Fallback: runtime absent (Windows/Claude Desktop race condition)
    assert TEMPLATE_PATH.exists(), (
        f"Ni .claude/settings.json ni templates/settings.json encontrados."
    )
    _USING_TEMPLATE = True
    raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    # Resolve placeholder so paths match what .claude/hooks/*.js actually is
    raw = raw.replace("__CLAUDE_HOME__", ".claude")
    print("  [WARN] .claude/settings.json ausente — usando templates/settings.json como referencia estable (F23)")
    return json.loads(raw)


def extract_all_commands(settings):
    """Devuelve lista de (event, matcher, command) para todos los hooks."""
    commands = []
    for event, blocks in settings.get("hooks", {}).items():
        for block in blocks:
            matcher = block.get("matcher", "(none)")
            for hook in block.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    commands.append((event, matcher, cmd))
    return commands


def test_1_no_legacy_absolute_paths():
    print("\n=== TEST 1: Sin paths /c/Users/Lucas/ en settings.json ===")
    settings = load_settings()
    commands = extract_all_commands(settings)
    stale = [(ev, m, cmd) for ev, m, cmd in commands if "/c/Users/Lucas/" in cmd]
    for ev, m, cmd in stale:
        print(f"  [STALE] {ev}/{m}: {cmd}")
    assert len(stale) == 0, f"{len(stale)} paths obsoletos encontrados"
    print(f"[OK] 0 paths /c/Users/Lucas/ — {len(commands)} comandos revisados")


def test_2_all_hook_files_exist():
    print("\n=== TEST 2: Todos los .js referenciados existen en .claude/hooks/ ===")
    settings = load_settings()
    commands = extract_all_commands(settings)
    missing = []
    for ev, m, cmd in commands:
        parts = cmd.split()
        if parts[0] != "node":
            continue
        raw_path = parts[1]
        # Normalizar: soporta .claude/hooks/X.js o node_modules/... etc.
        # Solo verificar hooks de .claude/hooks/
        if raw_path.startswith(".claude/hooks/"):
            hook_file = PROJECT_ROOT / raw_path
            if not hook_file.exists():
                missing.append((ev, m, raw_path))
    for ev, m, path in missing:
        print(f"  [MISSING] {ev}/{m}: {path}")
    assert len(missing) == 0, f"{len(missing)} archivos de hook no encontrados"
    print(f"[OK] Todos los hooks .claude/hooks/*.js existen en disco")


def test_3_qa_auto_audit_registered():
    print("\n=== TEST 3: qa-auto-audit.js registrado en PostToolUse ===")
    settings = load_settings()
    post = settings.get("hooks", {}).get("PostToolUse", [])
    found = any(
        "qa-auto-audit" in hook.get("command", "")
        for block in post
        for hook in block.get("hooks", [])
    )
    assert found, "qa-auto-audit.js no esta registrado en PostToolUse"
    print("[OK] qa-auto-audit.js presente en PostToolUse")


def test_4_delegation_tracker_registered():
    print("\n=== TEST 4: delegation-tracker.js registrado en PostToolUse ===")
    settings = load_settings()
    post = settings.get("hooks", {}).get("PostToolUse", [])
    found = any(
        "delegation-tracker" in hook.get("command", "")
        for block in post
        for hook in block.get("hooks", [])
    )
    assert found, "delegation-tracker.js no esta registrado en PostToolUse"
    print("[OK] delegation-tracker.js presente en PostToolUse")


def test_5_no_absolute_paths_anywhere():
    print("\n=== TEST 5: Ningun hook usa path absoluto (/c/ o C:\\) ===")
    settings = load_settings()
    commands = extract_all_commands(settings)
    absolute = []
    for ev, m, cmd in commands:
        parts = cmd.split()
        if parts[0] != "node":
            continue
        raw_path = parts[1]
        if raw_path.startswith("/c/") or raw_path.lower().startswith("c:\\") or raw_path.lower().startswith("c:/"):
            absolute.append((ev, m, raw_path))
    for ev, m, path in absolute:
        print(f"  [ABSOLUTE] {ev}/{m}: {path}")
    assert len(absolute) == 0, f"{len(absolute)} hooks con paths absolutos encontrados"
    print(f"[OK] 0 paths absolutos — hooks portables")


def main():
    print("\n" + "="*70)
    print("VALIDACION Fase 5 — Settings Path Normalization")
    print("="*70)

    tests = [
        test_1_no_legacy_absolute_paths,
        test_2_all_hook_files_exist,
        test_3_qa_auto_audit_registered,
        test_4_delegation_tracker_registered,
        test_5_no_absolute_paths_anywhere,
    ]

    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("="*70)

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] settings.json sin paths /c/Users/Lucas/ obsoletos")
        print("[OK] Todos los archivos .js referenciados existen en .claude/hooks/")
        print("[OK] qa-auto-audit.js y delegation-tracker.js registrados en PostToolUse")
        print("[OK] Hooks portables — sin paths absolutos de maquina externa")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
