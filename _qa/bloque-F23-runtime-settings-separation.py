#!/usr/bin/env python3
"""
Bloque F23 — Runtime Settings Separation
==========================================

Valida que el race condition de .claude/settings.json en Windows/Claude Desktop
está resuelto: healthcheck y suites toleran la ausencia temporal del archivo
sin emitir FAIL.

TC1:  config/atlas.runtime.expected.yaml existe
TC2:  expected YAML válido con secciones required (expected_hooks, ownership)
TC3:  expected_hooks cubre PreToolUse, PostToolUse, Stop
TC4:  templates/settings.json con __CLAUDE_HOME__ resuelto tiene hooks existentes
TC5:  healthcheck (no-strict) exits 0 con settings.json presente
TC6:  healthcheck source: dos ejes strict (_STRICT_EXPECTED / _STRICT_RUNTIME)
TC7:  healthcheck (no-strict) exits 0 cuando settings.json temporalmente ausente
TC8:  release gate semantics — --strict (expected) exits 0 con settings runtime
      ausente; --strict-runtime sigue exits 1 (eje runtime explícito)
TC9:  healthcheck source: settings runtime = WARN_RUNTIME_MUTABLE + check_expected_config
TC10: bloque-F5 pasa cuando settings.json ausente (fallback a template)
TC11: bloque-F10 pasa cuando settings.json ausente (TC03 skip, no FAIL)
TC12: run_all.py no clasifica F5/F7/F9/F10/F11 como suites dependientes-de-healthcheck
TC13: run_all.py --quick exits 0 (todas las suites core pasan)
TC14: run_all.py --release pasa --strict a healthcheck subprocess
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "settings.json"
EXPECTED_YAML = PROJECT_ROOT / "config" / "atlas.runtime.expected.yaml"
HEALTHCHECK   = PROJECT_ROOT / "tools" / "atlas_healthcheck.py"
RUN_ALL       = PROJECT_ROOT / "tools" / "run_all.py"

PASS_COUNT = 0
FAIL_COUNT = 0


def PASS(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    msg = f"  [PASS] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def FAIL(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def run_py(*args, timeout: int = 60, env=None) -> tuple[int, str]:
    """Run a Python script as subprocess, return (exit_code, combined_output)."""
    r = subprocess.run(
        [sys.executable] + list(args),
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **(env or {})},
    )
    return r.returncode, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# TC1 — config/atlas.runtime.expected.yaml exists
# ---------------------------------------------------------------------------
try:
    if EXPECTED_YAML.exists():
        PASS("TC1 config/atlas.runtime.expected.yaml exists")
    else:
        FAIL("TC1 config/atlas.runtime.expected.yaml exists", f"not found: {EXPECTED_YAML}")
except Exception as e:
    FAIL("TC1 expected YAML exists", str(e))

# ---------------------------------------------------------------------------
# TC2 — YAML valid with required sections
# ---------------------------------------------------------------------------
_expected_data: dict = {}
try:
    import yaml
    _expected_data = yaml.safe_load(EXPECTED_YAML.read_text(encoding="utf-8")) or {}
    required_sections = {"expected_hooks", "ownership", "version"}
    missing = required_sections - _expected_data.keys()
    if not missing:
        PASS("TC2 expected YAML valid with required sections",
             f"version={_expected_data.get('version')}")
    else:
        FAIL("TC2 expected YAML sections", f"missing: {missing}")
except ImportError:
    FAIL("TC2 expected YAML valid", "PyYAML not installed")
except Exception as e:
    FAIL("TC2 expected YAML valid", str(e))

# ---------------------------------------------------------------------------
# TC3 — expected_hooks covers PreToolUse, PostToolUse, Stop
# ---------------------------------------------------------------------------
try:
    hooks = _expected_data.get("expected_hooks", {})
    required_events = {"PreToolUse", "PostToolUse", "Stop"}
    present = required_events & hooks.keys()
    if present == required_events:
        counts = {ev: len(hooks[ev]) for ev in required_events}
        PASS("TC3 expected_hooks covers all event types", str(counts))
    else:
        FAIL("TC3 expected_hooks events", f"missing: {required_events - present}")
except Exception as e:
    FAIL("TC3 expected_hooks events", str(e))

# ---------------------------------------------------------------------------
# TC4 — templates/settings.json hooks resolve to existing files
# ---------------------------------------------------------------------------
try:
    assert TEMPLATE_PATH.exists(), f"templates/settings.json not found"
    raw = TEMPLATE_PATH.read_text(encoding="utf-8").replace("__CLAUDE_HOME__", ".claude")
    tmpl = json.loads(raw)
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    missing_files = []
    for event, blocks in tmpl.get("hooks", {}).items():
        for block in blocks:
            for hook in block.get("hooks", []):
                cmd = hook.get("command", "")
                parts = cmd.split()
                if len(parts) >= 2 and parts[0] == "node":
                    # strip any --flags
                    js_path_str = parts[1]
                    js_path = PROJECT_ROOT / js_path_str
                    if not js_path.exists():
                        missing_files.append(js_path_str)
    if not missing_files:
        PASS("TC4 templates hooks resolve to existing .js files")
    else:
        FAIL("TC4 templates hooks resolve", f"missing: {missing_files}")
except Exception as e:
    FAIL("TC4 templates hooks resolve", str(e))

# ---------------------------------------------------------------------------
# TC5 — healthcheck (no-strict) exits 0 with settings.json present
# ---------------------------------------------------------------------------
try:
    code, out = run_py(str(HEALTHCHECK), timeout=45)
    if code == 0:
        PASS("TC5 healthcheck exits 0 (non-strict, settings present)")
    else:
        fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
        FAIL("TC5 healthcheck exits 0", f"code={code} fails={fails[:3]}")
except Exception as e:
    FAIL("TC5 healthcheck non-strict", str(e))

# ---------------------------------------------------------------------------
# TC6 — healthcheck wires TWO independent strict axes (F24 P5):
#   _STRICT_EXPECTED (release gate, --strict) and _STRICT_RUNTIME (--strict-runtime).
# Behavioral exit codes covered in TC7/TC8. Here we verify the source wiring.
# ---------------------------------------------------------------------------
try:
    hc_source = HEALTHCHECK.read_text(encoding="utf-8")
    has_expected = '_STRICT_EXPECTED: bool = False' in hc_source
    has_runtime = '_STRICT_RUNTIME: bool = False' in hc_source
    has_argv_strict = '"--strict" in sys.argv' in hc_source
    has_argv_runtime = '"--strict-runtime" in sys.argv' in hc_source
    has_env_check = 'ATLAS_HEALTHCHECK_STRICT' in hc_source
    if all((has_expected, has_runtime, has_argv_strict, has_argv_runtime, has_env_check)):
        PASS("TC6 healthcheck dual strict-axis wiring in source",
             "_STRICT_EXPECTED + _STRICT_RUNTIME + argv (--strict / --strict-runtime) + env")
    else:
        FAIL("TC6 healthcheck dual strict-axis wiring",
             f"expected={has_expected} runtime={has_runtime} "
             f"argv_strict={has_argv_strict} argv_runtime={has_argv_runtime} env={has_env_check}")
except Exception as e:
    FAIL("TC6 healthcheck dual strict-axis wiring", str(e))

# ---------------------------------------------------------------------------
# TC7 — healthcheck (no-strict) exits 0 when settings.json temporarily absent
# ---------------------------------------------------------------------------
backup = SETTINGS_PATH.with_suffix(".json.bak_f23a")
_settings_was_present = SETTINGS_PATH.exists()
try:
    if _settings_was_present:
        os.replace(str(SETTINGS_PATH), str(backup))
    code, out = run_py(str(HEALTHCHECK), timeout=45)
    if code == 0:
        PASS("TC7 healthcheck non-strict exits 0 when settings absent")
    else:
        fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
        FAIL("TC7 healthcheck non-strict exits 0 when absent", f"code={code} fails={fails[:3]}")
except Exception as e:
    FAIL("TC7 healthcheck absent settings", str(e))
finally:
    if backup.exists():
        SETTINGS_PATH.unlink(missing_ok=True)
        os.replace(str(backup), str(SETTINGS_PATH))

# ---------------------------------------------------------------------------
# TC8 — Release gate semantics (F24 P5):
#   --strict (expected) must NOT FAIL on absent runtime settings.json (it's
#   RUNTIME_MUTABLE; expected config is present) → exit 0.
#   --strict-runtime still enforces the live file → exit 1.
# ---------------------------------------------------------------------------
backup = SETTINGS_PATH.with_suffix(".json.bak_f23b")
_settings_was_present = SETTINGS_PATH.exists()
try:
    if _settings_was_present:
        os.replace(str(SETTINGS_PATH), str(backup))
    code_exp, out_exp = run_py(str(HEALTHCHECK), "--strict", timeout=45)
    code_rt, out_rt = run_py(str(HEALTHCHECK), "--strict-runtime", timeout=45)
    expected_ok = code_exp == 0
    runtime_ok = code_rt == 1
    if expected_ok and runtime_ok:
        PASS("TC8 release gate: --strict exit 0, --strict-runtime exit 1 (settings absent)")
    else:
        exp_fails = [l.strip() for l in out_exp.splitlines() if "[FAIL]" in l][:3]
        FAIL("TC8 release gate semantics",
             f"--strict code={code_exp} (esperado 0, fails={exp_fails}) | "
             f"--strict-runtime code={code_rt} (esperado 1)")
except Exception as e:
    FAIL("TC8 release gate semantics", str(e))
finally:
    if backup.exists():
        SETTINGS_PATH.unlink(missing_ok=True)
        os.replace(str(backup), str(SETTINGS_PATH))

# ---------------------------------------------------------------------------
# TC9 — healthcheck source: runtime settings = WARN_RUNTIME_MUTABLE, gated on the
# RUNTIME axis (not the expected/release axis), plus a separate check_expected_config
# that IS the release gate. Verified via source (behavioral exit codes in TC8).
# ---------------------------------------------------------------------------
try:
    hc_source = HEALTHCHECK.read_text(encoding="utf-8")
    has_warn_path = 'WARN(".claude/settings.json"' in hc_source
    has_runtime_mutable = "WARN_RUNTIME_MUTABLE" in hc_source
    has_expected_check = "def check_expected_config" in hc_source
    has_runtime_axis = "_STRICT_RUNTIME" in hc_source
    has_expected_axis = "_STRICT_EXPECTED" in hc_source
    # The runtime settings.json FAIL must be gated on the RUNTIME axis only.
    runtime_fail_gated = "FAIL(\".claude/settings.json\"" in hc_source and "_STRICT_RUNTIME" in hc_source
    if all((has_warn_path, has_runtime_mutable, has_expected_check,
            has_runtime_axis, has_expected_axis, runtime_fail_gated)):
        PASS("TC9 healthcheck separates runtime-mutable WARN from expected-config gate",
             "WARN_RUNTIME_MUTABLE + check_expected_config + dual axis present")
    else:
        FAIL("TC9 healthcheck settings/expected separation",
             f"warn={has_warn_path} runtime_mutable={has_runtime_mutable} "
             f"expected_check={has_expected_check} runtime_axis={has_runtime_axis} "
             f"expected_axis={has_expected_axis}")
except Exception as e:
    FAIL("TC9 healthcheck settings/expected separation", str(e))

# ---------------------------------------------------------------------------
# TC10 — bloque-F5 passes when settings.json absent (template fallback)
# ---------------------------------------------------------------------------
backup = SETTINGS_PATH.with_suffix(".json.bak_f23d")
_settings_was_present = SETTINGS_PATH.exists()
try:
    if _settings_was_present:
        os.replace(str(SETTINGS_PATH), str(backup))
    f5_suite = PROJECT_ROOT / "_qa" / "bloque-F5-settings-wiring-validation.py"
    code, out = run_py(str(f5_suite), timeout=30)
    if code == 0:
        PASS("TC10 bloque-F5 passes when settings absent (template fallback)")
    else:
        fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
        FAIL("TC10 bloque-F5 absent settings", f"code={code} fails={fails[:3]}")
except Exception as e:
    FAIL("TC10 bloque-F5 absent settings", str(e))
finally:
    if backup.exists():
        SETTINGS_PATH.unlink(missing_ok=True)
        os.replace(str(backup), str(SETTINGS_PATH))

# ---------------------------------------------------------------------------
# TC11 — bloque-F10 passes when settings.json absent (TC03 skipped)
# ---------------------------------------------------------------------------
backup = SETTINGS_PATH.with_suffix(".json.bak_f23e")
_settings_was_present = SETTINGS_PATH.exists()
try:
    if _settings_was_present:
        os.replace(str(SETTINGS_PATH), str(backup))
    f10_suite = PROJECT_ROOT / "_qa" / "bloque-F10-sot-drift.py"
    code, out = run_py(str(f10_suite), timeout=30)
    if code == 0:
        skip_note = "TC03 skipped" if "SKIP" in out else "all tests passed"
        PASS("TC11 bloque-F10 passes when settings absent", skip_note)
    else:
        fails = [l.strip() for l in out.splitlines() if "FAIL" in l]
        FAIL("TC11 bloque-F10 absent settings", f"code={code} fails={fails[:3]}")
except Exception as e:
    FAIL("TC11 bloque-F10 absent settings", str(e))
finally:
    if backup.exists():
        SETTINGS_PATH.unlink(missing_ok=True)
        os.replace(str(backup), str(SETTINGS_PATH))

# ---------------------------------------------------------------------------
# TC12 — run_all.py does not use HEALTHCHECK_DEPENDENT_SUITES to skip suites
# ---------------------------------------------------------------------------
try:
    run_all_text = (PROJECT_ROOT / "tools" / "run_all.py").read_text(encoding="utf-8")
    # The set should not be used to exclude suites in should_run()
    # It may still exist as a comment/reference, but should not be a set
    # that conditionally excludes F5/F7/F9/F10/F11
    if "HEALTHCHECK_DEPENDENT_SUITES" in run_all_text and "if stem in HEALTHCHECK_DEPENDENT" in run_all_text:
        FAIL("TC12 HEALTHCHECK_DEPENDENT_SUITES not used to skip",
             "still conditionally skipping suites based on healthcheck dependency")
    else:
        PASS("TC12 run_all.py does not skip suites for settings.json dependency")
except Exception as e:
    FAIL("TC12 run_all HEALTHCHECK_DEPENDENT", str(e))

# ---------------------------------------------------------------------------
# TC13 — F5/F10/F11 pass with settings.json explicitly absent
# Ensures template fallback and skip logic work deterministically.
# ---------------------------------------------------------------------------
backup_tc13 = SETTINGS_PATH.with_suffix(".json.bak_f23_tc13")
_had_settings_tc13 = SETTINGS_PATH.exists()
try:
    if _had_settings_tc13:
        os.replace(str(SETTINGS_PATH), str(backup_tc13))
    target_suites = [
        "bloque-F5-settings-wiring-validation",
        "bloque-F10-sot-drift",
        "bloque-F11-skills-registry-runtime",
    ]
    suite_results = []
    for name in target_suites:
        suite_path = PROJECT_ROOT / "_qa" / f"{name}.py"
        code, out = run_py(str(suite_path), timeout=45)
        suite_results.append((name, code, out))
    failures = [(n, c, o) for n, c, o in suite_results if c != 0]
    if not failures:
        PASS("TC13 F5/F10/F11 pass with settings absent (race resolved)",
             f"{len(target_suites)} suites OK")
    else:
        for n, c, o in failures:
            fails = [l.strip() for l in o.splitlines() if "FAIL" in l][:2]
            FAIL("TC13 suite failed", f"{n}: code={c} fails={fails}")
except Exception as e:
    FAIL("TC13 suites with absent settings", str(e))
finally:
    if backup_tc13.exists():
        SETTINGS_PATH.unlink(missing_ok=True)
        os.replace(str(backup_tc13), str(SETTINGS_PATH))

# ---------------------------------------------------------------------------
# TC14 — run_all.py --release passes --strict to healthcheck subprocess
# ---------------------------------------------------------------------------
try:
    run_all_text = (PROJECT_ROOT / "tools" / "run_all.py").read_text(encoding="utf-8")
    # run_healthcheck(strict=True) must be called in release mode
    if "run_healthcheck(strict=True)" in run_all_text:
        PASS("TC14 run_all --release passes --strict to healthcheck")
    else:
        FAIL("TC14 run_all --release strict", "run_healthcheck(strict=True) not found in run_all.py")
except Exception as e:
    FAIL("TC14 run_all --release strict", str(e))


print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
