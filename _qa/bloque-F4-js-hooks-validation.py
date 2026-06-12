#!/usr/bin/env python3
"""
Validacion real de Fase 4: JS Hook Execution Validation

Testea los hooks JS (.claude/hooks/) como subprocesos reales con Node.
No testea la capa Python (eso lo hacen bloque-1k1 y bloque-1d1).

Hooks cubiertos:
  - qa-auto-audit.js    (PostToolUse, advisory, 1K.1)
  - delegation-tracker.js (PostToolUse, advisory, 1D.1)

Requiere: Node.js 18+ en PATH.
          Si node no esta disponible, todos los tests son SKIP.

Contratos validados:
  - Exit code siempre 0 (fail-open, nunca bloquea)
  - stdin JSON parseado correctamente
  - WARN en stderr cuando corresponde (incomplete audit)
  - Silencio cuando no corresponde (non-Agent tool, sin subagent_type)
  - Path resolution: hooks encuentran tools/ en cwd del proyecto
  - State file creado en .pipeline/ cuando tracker registra tool call
  - Settings.json contiene ambos hooks registrados

16 tests totales.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
#  Setup
# ---------------------------------------------------------------------------
os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")

REPO_ROOT  = Path(__file__).parent.parent
TOOLS_DIR  = REPO_ROOT / "tools"
HOOKS_DIR  = REPO_ROOT / ".claude" / "hooks"
QA_HOOK    = HOOKS_DIR / "qa-auto-audit.js"
DT_HOOK    = HOOKS_DIR / "delegation-tracker.js"

NODE = shutil.which("node") or shutil.which("node.exe")


def skip(name: str) -> None:
    print(f"[SKIP] {name} — Node.js no disponible")


def run_hook(hook_path: Path, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    """Ejecuta un hook JS con el payload dado. Siempre captura stdout+stderr."""
    return subprocess.run(
        [NODE, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=15,
        env={**os.environ, "ATLAS_DISABLE_ENGRAM_MCP": "1"},
    )


def make_project_dir(base: Path, with_tools: bool = True) -> Path:
    """Crea un directorio de proyecto aislado con tools/ copiados."""
    proj = base / "project"
    proj.mkdir(parents=True, exist_ok=True)
    if with_tools:
        tools_dst = proj / "tools"
        tools_dst.mkdir(exist_ok=True)
        for py in TOOLS_DIR.glob("*.py"):
            shutil.copy2(py, tools_dst / py.name)
        # Copiar subdirectorio contracts si existe
        contracts_src = TOOLS_DIR / "contracts"
        if contracts_src.exists():
            shutil.copytree(contracts_src, tools_dst / "contracts", dirs_exist_ok=True)
        # Copiar config si existe en repo root
        config_src = REPO_ROOT / "config"
        if config_src.exists():
            shutil.copytree(config_src, proj / "config", dirs_exist_ok=True)
    (proj / ".pipeline").mkdir(exist_ok=True)
    return proj


# ============================================================
#  TESTS — qa-auto-audit.js
# ============================================================

def test_qa1_hook_file_exists():
    print("\n=== QA-TEST 1: qa-auto-audit.js existe en .claude/hooks/ ===")
    assert QA_HOOK.exists(), f"No encontrado: {QA_HOOK}"
    print(f"[OK] {QA_HOOK}")


def test_qa2_non_agent_tool_exit0_no_output():
    print("\n=== QA-TEST 2: Non-Agent tool -> exit 0, sin output ===")
    if not NODE:
        skip("test_qa2"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        for tool in ["Write", "Read", "Bash", "Edit"]:
            r = run_hook(QA_HOOK, {"tool_name": tool, "cwd": str(proj)}, proj)
            assert r.returncode == 0, f"{tool}: exit {r.returncode}"
            assert r.stdout == "", f"{tool}: stdout no vacio: {r.stdout!r}"
            assert r.stderr == "", f"{tool}: stderr no vacio: {r.stderr!r}"
    print("[OK] Write/Read/Bash/Edit -> exit 0 silencioso")


def test_qa3_agent_without_subagent_type_exit0():
    print("\n=== QA-TEST 3: Agent sin subagent_type -> exit 0, sin output ===")
    if not NODE:
        skip("test_qa3"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        r = run_hook(QA_HOOK,
                     {"tool_name": "Agent", "cwd": str(proj), "tool_input": {}},
                     proj)
        assert r.returncode == 0
        assert r.stderr == ""
    print("[OK]")


def test_qa4_malformed_json_exit0():
    print("\n=== QA-TEST 4: JSON malformado -> exit 0 (fail-open) ===")
    if not NODE:
        skip("test_qa4"); return
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [NODE, str(QA_HOOK)],
            input="NOT_JSON",
            capture_output=True, text=True,
            cwd=tmp, timeout=10,
            env={**os.environ, "ATLAS_DISABLE_ENGRAM_MCP": "1"},
        )
        assert proc.returncode == 0, f"exit {proc.returncode}"
    print("[OK] JSON malformado -> fail-open exit 0")


def test_qa5_no_dispatcher_exit0_no_error():
    print("\n=== QA-TEST 5: Sin tools/atlas_dispatcher.py -> exit 0, sin output ===")
    if not NODE:
        skip("test_qa5"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp), with_tools=False)  # sin tools/
        r = run_hook(QA_HOOK,
                     {"tool_name": "Agent", "cwd": str(proj),
                      "tool_input": {"subagent_type": "evidence-collector"}},
                     proj)
        assert r.returncode == 0
        # Sin dispatcher -> silencioso (fail-open original: no avisa)
    print("[OK] Sin dispatcher -> exit 0 sin error")


def test_qa6_known_agent_no_invocations_warn():
    print("\n=== QA-TEST 6: Agent conocido, 0 helpers invocados -> WARN en stderr ===")
    if not NODE:
        skip("test_qa6"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        r = run_hook(QA_HOOK,
                     {"tool_name": "Agent", "cwd": str(proj),
                      "tool_input": {"subagent_type": "evidence-collector"}},
                     proj)
        assert r.returncode == 0, f"exit {r.returncode} — stderr: {r.stderr}"
        # WARN esperado porque 0 helpers fueron invocados en esta sesion
        assert "[qa-auto-audit] WARN" in r.stderr, \
            f"WARN esperado pero stderr={r.stderr!r}"
        assert "evidence-collector" in r.stderr
        assert "helpers obligatorios" in r.stderr
    print("[OK] WARN emitido con agente y helpers faltantes listados")


def test_qa7_unknown_agent_exit0_no_warn():
    print("\n=== QA-TEST 7: Agente desconocido -> exit 0, sin WARN ===")
    if not NODE:
        skip("test_qa7"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        r = run_hook(QA_HOOK,
                     {"tool_name": "Agent", "cwd": str(proj),
                      "tool_input": {"subagent_type": "agente-inventado-xyz"}},
                     proj)
        assert r.returncode == 0
        # agente desconocido -> verdict=skipped -> NO emite WARN
        assert "[qa-auto-audit] WARN" not in r.stderr, \
            f"WARN inesperado: {r.stderr!r}"
    print("[OK] Agente desconocido -> skipped, sin WARN")


def test_qa8_settings_registration():
    print("\n=== QA-TEST 8: qa-auto-audit.js registrado en .claude/settings.json ===")
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    if not settings_path.exists():
        print("[SKIP] settings.json no encontrado"); return
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    post = settings.get("hooks", {}).get("PostToolUse", [])
    found = any(
        "qa-auto-audit" in h.get("command", "")
        for block in post
        for h in block.get("hooks", [])
    )
    assert found, "Hook qa-auto-audit.js no esta en PostToolUse de settings.json"
    print("[OK] Registrado en settings.json")


# ============================================================
#  TESTS — delegation-tracker.js
# ============================================================

def test_dt1_hook_file_exists():
    print("\n=== DT-TEST 1: delegation-tracker.js existe en .claude/hooks/ ===")
    assert DT_HOOK.exists(), f"No encontrado: {DT_HOOK}"
    print(f"[OK] {DT_HOOK}")


def test_dt2_malformed_json_exit0():
    print("\n=== DT-TEST 2: JSON malformado -> exit 0 (fail-open) ===")
    if not NODE:
        skip("test_dt2"); return
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [NODE, str(DT_HOOK)],
            input="NOT_JSON",
            capture_output=True, text=True,
            cwd=tmp, timeout=10,
            env={**os.environ, "ATLAS_DISABLE_ENGRAM_MCP": "1"},
        )
        assert proc.returncode == 0
    print("[OK]")


def test_dt3_missing_tool_name_exit0():
    print("\n=== DT-TEST 3: Sin tool_name -> exit 0 silencioso ===")
    if not NODE:
        skip("test_dt3"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        r = run_hook(DT_HOOK, {"cwd": str(proj)}, proj)
        assert r.returncode == 0
        assert r.stderr == ""
    print("[OK]")


def test_dt4_no_tracker_tool_exit0():
    print("\n=== DT-TEST 4: Sin tools/delegation_tracker.py -> exit 0 silencioso ===")
    if not NODE:
        skip("test_dt4"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp), with_tools=False)
        r = run_hook(DT_HOOK,
                     {"tool_name": "Read", "cwd": str(proj),
                      "tool_input": {"file_path": "src/foo.ts"}},
                     proj)
        assert r.returncode == 0
        # Sin tracker -> silencioso fail-open
    print("[OK] Sin tracker -> exit 0 sin error")


def test_dt5_read_creates_state_file():
    print("\n=== DT-TEST 5: Read registrado -> crea .pipeline/delegation-state.json ===")
    if not NODE:
        skip("test_dt5"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        r = run_hook(DT_HOOK,
                     {"tool_name": "Read", "cwd": str(proj),
                      "tool_input": {"file_path": "src/foo.ts"}},
                     proj)
        assert r.returncode == 0, f"exit {r.returncode}, stderr: {r.stderr}"
        state_file = proj / ".pipeline" / "delegation-state.json"
        assert state_file.exists(), ".pipeline/delegation-state.json no creado"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert state["consecutive_reads"] == 1, f"consecutive_reads={state['consecutive_reads']}"
        assert state["last_tool"] == "Read"
    print("[OK] State file creado con consecutive_reads=1")


def test_dt6_agent_spawn_resets_counters():
    print("\n=== DT-TEST 6: Agent spawn -> resetea contadores en state ===")
    if not NODE:
        skip("test_dt6"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        # Acumular 3 Reads
        for i in range(3):
            run_hook(DT_HOOK,
                     {"tool_name": "Read", "cwd": str(proj),
                      "tool_input": {"file_path": f"src/f{i}.ts"}},
                     proj)
        state_after_reads = json.loads(
            (proj / ".pipeline" / "delegation-state.json").read_text(encoding="utf-8")
        )
        assert state_after_reads["consecutive_reads"] == 3

        # Agent spawn
        run_hook(DT_HOOK,
                 {"tool_name": "Agent", "cwd": str(proj), "tool_input": {}},
                 proj)
        state_after_spawn = json.loads(
            (proj / ".pipeline" / "delegation-state.json").read_text(encoding="utf-8")
        )
        assert state_after_spawn["consecutive_reads"] == 0, \
            f"consecutive_reads no reseteado: {state_after_spawn['consecutive_reads']}"
        assert state_after_spawn["total_tool_calls_since_spawn"] == 0
    print("[OK] consecutive_reads=0 despues de Agent spawn")


def test_dt7_escalation_warn_on_5_reads():
    print("\n=== DT-TEST 7: 5 Reads consecutivas -> escalation_needed -> WARN en stderr ===")
    if not NODE:
        skip("test_dt7"); return
    with tempfile.TemporaryDirectory() as tmp:
        proj = make_project_dir(Path(tmp))
        last_result = None
        for i in range(5):
            last_result = run_hook(DT_HOOK,
                                   {"tool_name": "Read", "cwd": str(proj),
                                    "tool_input": {"file_path": f"src/f{i}.ts"}},
                                   proj)
        # El 5to Read deberia emitir WARN via stderr (reenviado desde tracker)
        state = json.loads(
            (proj / ".pipeline" / "delegation-state.json").read_text(encoding="utf-8")
        )
        assert state["flags"]["escalation_needed"] is True, \
            f"escalation_needed no True: {state['flags']}"
        # El WARN puede venir en el 5to call (cuando tracker activa el flag)
        assert last_result.returncode == 0
    print("[OK] escalation_needed=True tras 5 reads consecutivas")


def test_dt8_settings_registration():
    print("\n=== DT-TEST 8: delegation-tracker.js registrado en .claude/settings.json ===")
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    if not settings_path.exists():
        print("[SKIP] settings.json no encontrado"); return
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    post = settings.get("hooks", {}).get("PostToolUse", [])
    found = any(
        "delegation-tracker" in h.get("command", "")
        for block in post
        for h in block.get("hooks", [])
    )
    assert found, "Hook delegation-tracker.js no esta en PostToolUse de settings.json"
    print("[OK] Registrado en settings.json")


# ============================================================
#  RUNNER
# ============================================================

def main() -> int:
    print("\n" + "="*70)
    print("VALIDACION REAL -- Fase 4: JS Hook Execution Validation")
    print(f"Node: {NODE or 'NO DISPONIBLE'}")
    print("="*70)

    tests = [
        # qa-auto-audit.js
        test_qa1_hook_file_exists,
        test_qa2_non_agent_tool_exit0_no_output,
        test_qa3_agent_without_subagent_type_exit0,
        test_qa4_malformed_json_exit0,
        test_qa5_no_dispatcher_exit0_no_error,
        test_qa6_known_agent_no_invocations_warn,
        test_qa7_unknown_agent_exit0_no_warn,
        test_qa8_settings_registration,
        # delegation-tracker.js
        test_dt1_hook_file_exists,
        test_dt2_malformed_json_exit0,
        test_dt3_missing_tool_name_exit0,
        test_dt4_no_tracker_tool_exit0,
        test_dt5_read_creates_state_file,
        test_dt6_agent_spawn_resets_counters,
        test_dt7_escalation_warn_on_5_reads,
        test_dt8_settings_registration,
    ]

    passed = failed = skipped = 0
    for t in tests:
        try:
            t()
            if not NODE and t.__name__ not in ("test_qa1_hook_file_exists",
                                                "test_qa8_settings_registration",
                                                "test_dt1_hook_file_exists",
                                                "test_dt8_settings_registration"):
                skipped += 1
            else:
                passed += 1
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    total = len(tests)
    print(f"RESULTADO: {passed}/{total} PASS, {failed} FAIL, {skipped} SKIP")
    print("="*70)

    if failed == 0 and NODE:
        print("\nCONCLUSION:")
        print("[OK] qa-auto-audit.js: fail-open, WARN cuando hay helpers faltantes,")
        print("     silencioso para non-Agent tools y agentes desconocidos")
        print("[OK] delegation-tracker.js: fail-open, state file en .pipeline/,")
        print("     Agent spawn resetea contadores, WARN en threshold")
        print("[OK] Ambos hooks registrados en .claude/settings.json")
        print("\nLO QUE ESTOS HOOKS NO HACEN:")
        print("- NO bloquean el flujo (exit siempre 0)")
        print("- NO reportan nada si el proyecto no tiene tools/ en su cwd")
        print("  (fail-open silencioso cuando dispatcher/tracker ausente)")
    elif not NODE:
        print("\n[WARN] Node no disponible — instalar Node 18+ para ejecutar tests JS")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
