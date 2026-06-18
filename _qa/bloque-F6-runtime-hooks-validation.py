#!/usr/bin/env python3
"""
Bloque F6 — Runtime Hook Validation
=====================================

Invoca cada hook registrado en .claude/settings.json como subprocess real,
con payloads realistas de stdin, y verifica:
  - Exit code correcto (0 = allow/warn, 2 = block)
  - Stderr esperado (BLOCK msg, WARN msg, o silencio)
  - Side effects en disco donde aplica (cost-log, session-log, counter, snapshot)

Hooks cubiertos (13 totales en settings.json):
  PreToolUse/Bash      : block-no-verify.js, pipeline-rules.js
  PreToolUse/Write|Edit: config-protection.js
  PostToolUse/Write|Edit: quality-gate.js, console-log-warning.js
  PostToolUse/""       : delegation-tracker.js, qa-auto-audit.js,
                         cost-tracker.js, suggest-compact.js
  PreCompact           : pre-compact-engram.js
  Stop                 : session-summary.js, engram-sync.js
  Notification         : session-start-context.js

Total: 24 tests
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"


# ---------------------------------------------------------------------------
#  Helper
# ---------------------------------------------------------------------------

def run_hook(hook_name: str, stdin_payload, timeout: int = 15) -> tuple[int, str, str]:
    """
    Invoca hook via `node .claude/hooks/<hook_name>` con stdin_payload como JSON.
    Retorna (exit_code, stdout, stderr).
    stdin_payload puede ser dict (se serializa) o str (se pasa literal) o None.
    """
    hook_path = HOOKS_DIR / hook_name
    if not hook_path.exists():
        raise FileNotFoundError(f"Hook no encontrado: {hook_path}")

    if stdin_payload is None:
        stdin_bytes = b""
    elif isinstance(stdin_payload, dict):
        stdin_bytes = json.dumps(stdin_payload).encode()
    else:
        stdin_bytes = str(stdin_payload).encode()

    result = subprocess.run(
        ["node", str(hook_path)],
        input=stdin_bytes,
        capture_output=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, result.stdout.decode(errors="replace"), result.stderr.decode(errors="replace")


def bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def write_payload(file_path: str, content: str = "") -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


def edit_payload(file_path: str, new_string: str = "") -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": file_path, "new_string": new_string}}


# ---------------------------------------------------------------------------
#  block-no-verify.js (5 tests)
# ---------------------------------------------------------------------------

def test_01_block_no_verify_blocks_git_commit_no_verify():
    print("\n=== TEST 01: block-no-verify — BLOQUEA git commit --no-verify ===")
    code, _, err = run_hook("block-no-verify.js", bash_payload("git commit -m 'test' --no-verify"))
    print(f"  exit={code}, stderr={err[:80]!r}")
    assert code == 2, f"Esperado exit 2, got {code}"
    assert "BLOCKED" in err, f"Esperado 'BLOCKED' en stderr"
    print("[OK]")


def test_02_block_no_verify_allows_safe_command():
    print("\n=== TEST 02: block-no-verify — PERMITE git status ===")
    code, _, err = run_hook("block-no-verify.js", bash_payload("git status"))
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0, f"Esperado exit 0, got {code}"
    print("[OK]")


def test_03_block_no_verify_blocks_force_push():
    print("\n=== TEST 03: block-no-verify — BLOQUEA git push --force ===")
    code, _, err = run_hook("block-no-verify.js", bash_payload("git push origin main --force"))
    print(f"  exit={code}, stderr={err[:80]!r}")
    assert code == 2
    assert "BLOCKED" in err
    print("[OK]")


def test_04_block_no_verify_blocks_reset_hard():
    print("\n=== TEST 04: block-no-verify — BLOQUEA git reset --hard ===")
    code, _, err = run_hook("block-no-verify.js", bash_payload("git reset --hard HEAD~1"))
    print(f"  exit={code}, stderr={err[:80]!r}")
    assert code == 2
    assert "BLOCKED" in err
    print("[OK]")


def test_05_block_no_verify_failopen_empty_stdin():
    print("\n=== TEST 05: block-no-verify — fail-open con stdin vacío ===")
    code, _, err = run_hook("block-no-verify.js", "")
    print(f"  exit={code}")
    assert code == 0, f"Esperado exit 0 (fail-open), got {code}"
    print("[OK]")


# ---------------------------------------------------------------------------
#  config-protection.js (3 tests)
# ---------------------------------------------------------------------------

def test_06_config_protection_blocks_env_file():
    print("\n=== TEST 06: config-protection — BLOQUEA escritura de .env ===")
    code, _, err = run_hook("config-protection.js", write_payload("src/.env", "SECRET=abc"))
    print(f"  exit={code}, stderr={err[:80]!r}")
    assert code == 2
    assert "BLOCKED" in err
    print("[OK]")


def test_07_config_protection_warns_eslintrc():
    print("\n=== TEST 07: config-protection — WARN en .eslintrc ===")
    code, _, err = run_hook("config-protection.js", write_payload("src/.eslintrc", '{"rules":{}}'))
    print(f"  exit={code}, stderr={err[:80]!r}")
    assert code == 0
    assert "WARNING" in err or "warning" in err.lower()
    print("[OK]")


def test_08_config_protection_allows_normal_file():
    print("\n=== TEST 08: config-protection — PERMITE archivo normal ===")
    code, _, err = run_hook("config-protection.js", write_payload("src/utils.ts", "export const x = 1"))
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0
    assert err.strip() == ""
    print("[OK]")


# ---------------------------------------------------------------------------
#  quality-gate.js (3 tests)
# ---------------------------------------------------------------------------

def test_09_quality_gate_warns_debugger():
    print("\n=== TEST 09: quality-gate — WARN en debugger; en archivo .ts ===")
    content = "function foo() {\n  debugger;\n  return 42;\n}\n"
    code, _, err = run_hook("quality-gate.js", write_payload("src/app.ts", content))
    print(f"  exit={code}, stderr={err[:100]!r}")
    assert code == 0
    assert "debugger" in err.lower() or "Quality Gate" in err
    print("[OK]")


def test_10_quality_gate_warns_test_only():
    print("\n=== TEST 10: quality-gate — WARN en .only() en archivo .ts ===")
    content = "describe.only('suite', () => { it('test', () => {}); });\n"
    code, _, err = run_hook("quality-gate.js", write_payload("src/suite.ts", content))
    print(f"  exit={code}, stderr={err[:100]!r}")
    assert code == 0
    assert ".only" in err or "Quality Gate" in err
    print("[OK]")


def test_11_quality_gate_silent_clean_code():
    print("\n=== TEST 11: quality-gate — silencioso con código limpio .ts ===")
    content = "export function add(a: number, b: number): number { return a + b; }\n"
    code, _, err = run_hook("quality-gate.js", write_payload("src/math.ts", content))
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0
    assert err.strip() == ""
    print("[OK]")


# ---------------------------------------------------------------------------
#  console-log-warning.js (3 tests)
# ---------------------------------------------------------------------------

def test_12_console_log_warning_warns_in_ts():
    print("\n=== TEST 12: console-log-warning — WARN en console.log en .ts ===")
    content = "export function fetchUser() { console.log('fetching'); return null; }\n"
    code, _, err = run_hook("console-log-warning.js", write_payload("src/userService.ts", content))
    print(f"  exit={code}, stderr={err[:100]!r}")
    assert code == 0
    assert "console" in err.lower() or "Console" in err
    print("[OK]")


def test_13_console_log_warning_silent_in_test_file():
    print("\n=== TEST 13: console-log-warning — silencioso en archivo .test.ts ===")
    content = "it('test', () => { console.log('debug'); });\n"
    code, _, err = run_hook("console-log-warning.js", write_payload("src/app.test.ts", content))
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0
    assert err.strip() == "", f"Esperado sin stderr (test file ignorado), got: {err!r}"
    print("[OK]")


def test_14_console_log_warning_ignores_non_js():
    print("\n=== TEST 14: console-log-warning — ignora archivos no-JS/TS ===")
    content = "console.log('hello')"
    code, _, err = run_hook("console-log-warning.js", write_payload("README.md", content))
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0
    assert err.strip() == ""
    print("[OK]")


# ---------------------------------------------------------------------------
#  pipeline-rules.js (2 tests)
# ---------------------------------------------------------------------------

def test_15_pipeline_rules_allows_non_bash():
    print("\n=== TEST 15: pipeline-rules — PERMITE tool no-Bash (Read) ===")
    payload = {"tool_name": "Read", "tool_input": {"file_path": "src/app.ts"}}
    code, _, err = run_hook("pipeline-rules.js", payload)
    print(f"  exit={code}, stderr={err[:60]!r}")
    assert code == 0
    print("[OK]")


def test_16_pipeline_rules_allows_safe_bash():
    print("\n=== TEST 16: pipeline-rules — PERMITE Bash sin match de reglas ===")
    code, _, err = run_hook("pipeline-rules.js", bash_payload("npm run build"))
    print(f"  exit={code}, stderr={err[:60]!r}")
    assert code == 0
    print("[OK]")


# ---------------------------------------------------------------------------
#  cost-tracker.js — side effect: escribe cost-log.jsonl (1 test)
# ---------------------------------------------------------------------------

def test_17_cost_tracker_writes_cost_log():
    print("\n=== TEST 17: cost-tracker — escribe entrada en cost-log.jsonl ===")
    import os as _os
    home = Path(_os.path.expanduser("~"))
    cost_log = home / ".claude" / "snapshots" / "cost-log.jsonl"

    # Contar líneas antes
    lines_before = 0
    if cost_log.exists():
        lines_before = len([l for l in cost_log.read_text(encoding="utf-8").splitlines() if l.strip()])

    payload = {"tool_name": "Write", "tool_input": {"file_path": "src/test.ts"}}
    code, _, err = run_hook("cost-tracker.js", payload)
    print(f"  exit={code}")
    assert code == 0

    assert cost_log.exists(), f"cost-log.jsonl no fue creado en {cost_log}"
    lines_after = len([l for l in cost_log.read_text(encoding="utf-8").splitlines() if l.strip()])
    print(f"  líneas antes={lines_before}, después={lines_after}")
    assert lines_after > lines_before, "cost-log.jsonl no creció después del hook"

    # Verificar formato de la última entrada
    last_line = [l for l in cost_log.read_text(encoding="utf-8").splitlines() if l.strip()][-1]
    entry = json.loads(last_line)
    assert "ts" in entry
    assert "tool" in entry
    assert entry["tool"] == "Write"
    print(f"  Última entrada: tool={entry['tool']}, category={entry.get('category')}, ts={entry['ts'][:19]}")
    print("[OK]")


# ---------------------------------------------------------------------------
#  suggest-compact.js — side effect: escribe counter en tmpdir (1 test)
# ---------------------------------------------------------------------------

def test_18_suggest_compact_writes_counter():
    print("\n=== TEST 18: suggest-compact — escribe/actualiza counter file ===")
    import tempfile
    counter_path = Path(tempfile.gettempdir()) / ".claude-tool-call-counter.json"

    count_before = 0
    if counter_path.exists():
        try:
            count_before = json.loads(counter_path.read_text())["count"]
        except Exception:
            pass

    code, _, err = run_hook("suggest-compact.js", {"tool_name": "Read", "tool_input": {}})
    print(f"  exit={code}")
    assert code == 0

    assert counter_path.exists(), f"Counter file no creado en {counter_path}"
    data = json.loads(counter_path.read_text())
    count_after = data["count"]
    print(f"  count antes={count_before}, después={count_after}")
    assert count_after > count_before or count_after == 1, "Counter no incrementó"
    print("[OK]")


# ---------------------------------------------------------------------------
#  session-summary.js — side effect: append a session-log.jsonl (1 test)
# ---------------------------------------------------------------------------

def test_19_session_summary_appends_to_log():
    print("\n=== TEST 19: session-summary — append entrada en session-log.jsonl ===")
    import os as _os
    home = Path(_os.path.expanduser("~"))
    session_log = home / ".claude" / "snapshots" / "session-log.jsonl"

    lines_before = 0
    if session_log.exists():
        lines_before = len([l for l in session_log.read_text(encoding="utf-8").splitlines() if l.strip()])

    # Stop hook con stdin vacío (evento de stop de sesión)
    code, _, err = run_hook("session-summary.js", None)
    print(f"  exit={code}")
    assert code == 0

    assert session_log.exists(), f"session-log.jsonl no fue creado en {session_log}"
    lines_after = len([l for l in session_log.read_text(encoding="utf-8").splitlines() if l.strip()])
    print(f"  líneas antes={lines_before}, después={lines_after}")
    assert lines_after > lines_before

    last_line = [l for l in session_log.read_text(encoding="utf-8").splitlines() if l.strip()][-1]
    entry = json.loads(last_line)
    assert entry.get("event") == "stop"
    assert "timestamp" in entry
    print(f"  Última entrada: event={entry['event']}, ts={entry['timestamp'][:19]}")
    print("[OK]")


# ---------------------------------------------------------------------------
#  pre-compact-engram.js — side effect: escribe snapshot + trigger (1 test)
# ---------------------------------------------------------------------------

def test_20_pre_compact_engram_writes_snapshot():
    print("\n=== TEST 20: pre-compact-engram — escribe pre-compact-latest.json ===")
    import os as _os
    home = Path(_os.path.expanduser("~"))
    snapshot_file = home / ".claude" / "snapshots" / "pre-compact-latest.json"
    trigger_file = home / ".claude" / "snapshots" / "compaction-pending.json"

    # Borrar trigger previo para verificar que se re-crea
    if trigger_file.exists():
        trigger_file.unlink()

    code, _, err = run_hook("pre-compact-engram.js", None, timeout=15)
    print(f"  exit={code}, stderr={err[:100]!r}")
    assert code == 0
    assert snapshot_file.exists(), f"pre-compact-latest.json no creado en {snapshot_file}"
    assert trigger_file.exists(), f"compaction-pending.json no creado en {trigger_file}"

    snapshot = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert snapshot.get("event") == "pre-compact"
    assert "timestamp" in snapshot
    print(f"  snapshot.event={snapshot['event']}, cwd={snapshot.get('cwd','?')[:40]}")
    print(f"  trigger file: {trigger_file.name} creado OK")
    print("[OK]")


# ---------------------------------------------------------------------------
#  session-start-context.js — exit 0 siempre, lee snapshots si existen (1 test)
# ---------------------------------------------------------------------------

def test_21_session_start_context_exits_zero():
    print("\n=== TEST 21: session-start-context — exit 0, lee snapshots si existen ===")
    code, _, err = run_hook("session-start-context.js", None, timeout=10)
    print(f"  exit={code}, stderr preview={err[:120]!r}")
    assert code == 0, f"Esperado exit 0, got {code}"
    # Si hay snapshot reciente, debe emitir contexto por stderr — no es obligatorio pero es OK
    print("[OK]")


# ---------------------------------------------------------------------------
#  engram-sync.js --hook — fail-open aunque no haya repo Engram (1 test)
# ---------------------------------------------------------------------------

def test_22_engram_sync_hook_failopen():
    print("\n=== TEST 22: engram-sync --hook — fail-open aunque falle el sync ===")
    # El hook --hook lee stdin y sincroniza. Sin repo Engram configurado,
    # debe fallar de forma silenciosa y salir 0 (fail-open).
    hook_path = HOOKS_DIR / "engram-sync.js"
    result = subprocess.run(
        ["node", str(hook_path), "--hook"],
        input=b"",
        capture_output=True,
        timeout=15,
        cwd=str(PROJECT_ROOT),
    )
    code = result.returncode
    print(f"  exit={code}")
    # Fail-open: puede ser 0 (success o silencioso) o 1 (error interno no-fatal)
    # El hook NUNCA debe crashear (exit 2+ inesperado) — solo exit 0 o 1
    assert code in (0, 1), f"engram-sync --hook con exit inesperado: {code}"
    print("[OK] fail-open confirmado (no crash)")


# ---------------------------------------------------------------------------
#  delegation-tracker.js — sanity check (ya cubierto en F4) (1 test)
# ---------------------------------------------------------------------------

def test_23_delegation_tracker_sanity():
    print("\n=== TEST 23: delegation-tracker — sanity (estado actualizado) ===")
    import tempfile, os as _os
    tmpdir = Path(tempfile.mkdtemp())
    # Copiar tools/ para que el hook los encuentre
    import shutil
    tools_src = PROJECT_ROOT / "tools"
    tools_dst = tmpdir / "tools"
    shutil.copytree(str(tools_src), str(tools_dst))

    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "src/foo.ts"},
        "cwd": str(tmpdir),
    }
    code, _, err = run_hook("delegation-tracker.js", payload, timeout=20)
    print(f"  exit={code}")
    assert code == 0

    state_file = tmpdir / ".pipeline" / "delegation-state.json"
    assert state_file.exists(), f"delegation-state.json no creado en {state_file}"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["consecutive_reads"] == 1
    print(f"  consecutive_reads={state['consecutive_reads']}, last_tool={state.get('last_tool')}")
    print("[OK]")


# ---------------------------------------------------------------------------
#  qa-auto-audit.js — sanity check (ya cubierto en F4) (1 test)
# ---------------------------------------------------------------------------

def test_24_qa_auto_audit_sanity():
    print("\n=== TEST 24: qa-auto-audit — exit 0 silencioso para tool no-Agent ===")
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": "src/app.ts"},
        "cwd": str(PROJECT_ROOT),
    }
    code, _, err = run_hook("qa-auto-audit.js", payload)
    print(f"  exit={code}, stderr={err[:40]!r}")
    assert code == 0
    assert err.strip() == "", f"No debería emitir stderr para tool no-Agent, got: {err!r}"
    print("[OK]")


# ---------------------------------------------------------------------------
#  Runner
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 70)
    print("BLOQUE F6 — Runtime Hook Validation (invocación real como subprocess)")
    print("=" * 70)

    tests = [
        test_01_block_no_verify_blocks_git_commit_no_verify,
        test_02_block_no_verify_allows_safe_command,
        test_03_block_no_verify_blocks_force_push,
        test_04_block_no_verify_blocks_reset_hard,
        test_05_block_no_verify_failopen_empty_stdin,
        test_06_config_protection_blocks_env_file,
        test_07_config_protection_warns_eslintrc,
        test_08_config_protection_allows_normal_file,
        test_09_quality_gate_warns_debugger,
        test_10_quality_gate_warns_test_only,
        test_11_quality_gate_silent_clean_code,
        test_12_console_log_warning_warns_in_ts,
        test_13_console_log_warning_silent_in_test_file,
        test_14_console_log_warning_ignores_non_js,
        test_15_pipeline_rules_allows_non_bash,
        test_16_pipeline_rules_allows_safe_bash,
        test_17_cost_tracker_writes_cost_log,
        test_18_suggest_compact_writes_counter,
        test_19_session_summary_appends_to_log,
        test_20_pre_compact_engram_writes_snapshot,
        test_21_session_start_context_exits_zero,
        test_22_engram_sync_hook_failopen,
        test_23_delegation_tracker_sanity,
        test_24_qa_auto_audit_sanity,
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
            import traceback
            traceback.print_exc()
            failed += 1
            failures.append((t.__name__, f"{type(e).__name__}: {e}"))

    print("\n" + "=" * 70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("=" * 70)

    if failures:
        print("\nFALLOS:")
        for name, msg in failures:
            print(f"  {name}: {msg}")

    if failed == 0:
        print("\nEVIDENCIA DE EJECUCION LIVE:")
        print("[OK] block-no-verify.js — exit 2 en git --no-verify / --force / reset --hard")
        print("[OK] config-protection.js — exit 2 en .env, WARN en .eslintrc, silencio en .ts")
        print("[OK] quality-gate.js — WARN en debugger/.only, silencio en código limpio")
        print("[OK] console-log-warning.js — WARN en .ts, silencio en .test.ts y non-JS")
        print("[OK] pipeline-rules.js — exit 0 en non-Bash y Bash sin match")
        print("[OK] cost-tracker.js — nueva entrada JSON en ~/.claude/snapshots/cost-log.jsonl")
        print("[OK] suggest-compact.js — counter incrementado en tmpdir")
        print("[OK] session-summary.js — entrada 'stop' en ~/.claude/snapshots/session-log.jsonl")
        print("[OK] pre-compact-engram.js — snapshot + trigger escritos en ~/.claude/snapshots/")
        print("[OK] session-start-context.js — exit 0 (lee snapshots existentes)")
        print("[OK] engram-sync.js --hook — fail-open (exit 0 o 1, no crash)")
        print("[OK] delegation-tracker.js — state actualizado en .pipeline/delegation-state.json")
        print("[OK] qa-auto-audit.js — silencioso para tool no-Agent")
        print("\nRIESGOS RESIDUALES:")
        print("- engram-sync.js: sync real con GitHub no testeable sin repo Engram configurado")
        print("- session-start-context.js: contenido de stderr depende de snapshots en disco")
        print("- suggest-compact.js: WARN solo aparece tras 50 tool calls acumulados (no testeable unitariamente)")
        print("- Claude runtime puede usar paths del proyecto o CWD distintos al invocar hooks")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
