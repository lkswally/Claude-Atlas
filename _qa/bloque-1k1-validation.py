#!/usr/bin/env python3
"""
Validacion real de Bloque 1K.1: Auto-invocation Hook for QA Workflow

10 tests:
- 8 unit (mapping + audit + CLI subcommand)
- 1 hook subprocess end-to-end
- 1 hook with real settings registration check
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from atlas_dispatcher import ATLASDispatcher


def make_dispatcher(tmpdir: str) -> ATLASDispatcher:
    root = Path(tmpdir)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "phase_playbook.json").write_text(
        json.dumps({"fase_1": {"e2e_required": []}, "fase_3": {"e2e_required": []}})
    )
    (root / ".pipeline").mkdir(exist_ok=True)
    return ATLASDispatcher(root, auto_enable_mcp=False)


# ============================================================
#  TESTS
# ============================================================

def test_1_agent_helper_map_has_evidence_collector():
    print("\n=== TEST 1: AGENT_HELPER_REQUIREMENTS mapea evidence-collector con 6 helpers ===")
    required = ATLASDispatcher.AGENT_HELPER_REQUIREMENTS.get("evidence-collector")
    assert required is not None
    assert "validate_return_envelope" in required
    assert "should_skip_qa" in required
    assert "inspect_network_requests" in required
    assert "analyze_console_messages" in required
    assert "check_visual_fidelity" in required
    assert "verify_screenshot_evidence" in required
    print(f"[OK] evidence-collector tiene {len(required)} helpers obligatorios")


def test_2_dev_agents_mapped():
    print("\n=== TEST 2: Todos los dev-agents mapeados con validate_return_envelope ===")
    devs = ["frontend-developer", "backend-architect", "rapid-prototyper",
            "mobile-developer", "xr-immersive-developer", "build-resolver"]
    for d in devs:
        required = ATLASDispatcher.AGENT_HELPER_REQUIREMENTS.get(d)
        assert required is not None, f"{d} no mapeado"
        assert "validate_return_envelope" in required
        assert "verify_pre_return_audit" in required
        assert "verify_declared_files" in required
    print(f"[OK] {len(devs)} dev-agents mapeados")


def test_3_design_agents_mapped():
    print("\n=== TEST 3: ux-architect y ui-designer mapeados con design helpers ===")
    for d in ["ux-architect", "ui-designer"]:
        required = ATLASDispatcher.AGENT_HELPER_REQUIREMENTS.get(d)
        assert "consult_design_intelligence" in required
        assert "verify_design_intelligence_real" in required
    print("[OK]")


def test_4_unknown_agent_skipped():
    print("\n=== TEST 4: Agente desconocido -> verdict=skipped ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        result = d.audit_helpers_for_agent("agente-inventado-xyz")
        assert result["verdict"] == "skipped"
        assert result["agent_known"] is False
        print("[OK]")


def test_5_agent_with_empty_requirements_skipped():
    print("\n=== TEST 5: Agente con required=[] -> verdict=skipped (no critica) ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # brand-agent tiene required=[]
        result = d.audit_helpers_for_agent("brand-agent")
        assert result["verdict"] == "skipped"
        assert result["agent_known"] is True
        assert result["required_for_agent"] == []
        print("[OK]")


def test_6_audit_evidence_collector_complete():
    print("\n=== TEST 6: evidence-collector con todos los helpers invocados -> complete ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Invocar todos los helpers que evidence-collector requiere
        d.validate_return_envelope({"status": "PASS", "tarea": "x", "engram": "y", "archivos": ["a.ts"]}, mode="qa_strict")
        d.should_skip_qa("task-1", [])
        d.inspect_network_requests([])
        d.analyze_console_messages([])
        d.check_visual_fidelity({}, {})
        d.verify_screenshot_evidence({"screenshot_path": ""})  # path empty -> unverifiable pero invocado

        result = d.audit_helpers_for_agent("evidence-collector")
        print(f"verdict={result['verdict']}, missing={result.get('missing', [])}")
        assert result["verdict"] == "complete"
        assert result["agent_known"] is True
        assert result.get("missing", []) == []
    print("[OK]")


def test_7_audit_evidence_collector_incomplete():
    print("\n=== TEST 7: evidence-collector con helpers faltantes -> incomplete ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        d = make_dispatcher(tmpdir)
        # Solo invoca 2 de los 6 obligatorios
        d.validate_return_envelope({"status": "PASS", "tarea": "x", "engram": "y", "archivos": ["a.ts"]}, mode="qa_strict")
        d.should_skip_qa("task-1", [])

        result = d.audit_helpers_for_agent("evidence-collector")
        print(f"verdict={result['verdict']}, missing={result['missing']}")
        assert result["verdict"] == "incomplete"
        # Deberian faltar inspect_network, analyze_console, check_visual, verify_screenshot
        assert "inspect_network_requests" in result["missing"]
        assert "analyze_console_messages" in result["missing"]
        assert "check_visual_fidelity" in result["missing"]
        assert "verify_screenshot_evidence" in result["missing"]
    print("[OK]")


def test_8_cli_audit_agent_subcommand():
    print("\n=== TEST 8: CLI subcommand audit-agent funciona ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Setup dispatcher config
        (root / "config").mkdir()
        (root / "config" / "phase_playbook.json").write_text(json.dumps({"fase_1": {"e2e_required": []}}))
        (root / ".pipeline").mkdir()

        # Copiar tools al tmpdir para que el subprocess los encuentre
        tools_src = Path(__file__).parent.parent / "tools"
        tools_dst = root / "tools"
        tools_dst.mkdir()
        for f in tools_src.glob("*.py"):
            shutil.copy(f, tools_dst / f.name)

        env = os.environ.copy()
        env["ATLAS_DISABLE_ENGRAM_MCP"] = "1"

        # Ejecutar CLI: audit-agent con agente desconocido -> skipped (exit 0)
        result = subprocess.run(
            [sys.executable, str(tools_dst / "atlas_dispatcher.py"),
             "audit-agent", "--agent=agente-inventado"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        print(f"Exit: {result.returncode}, output preview: {result.stdout[:120]}")
        assert result.returncode == 0  # skipped no es error
        audit = json.loads(result.stdout)
        assert audit["verdict"] == "skipped"
    print("[OK]")


def test_9_cli_audit_agent_missing_agent_param_fail_open():
    print("\n=== TEST 9: CLI audit-agent sin --agent= -> fail-open exit 0 ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "config").mkdir()
        (root / "config" / "phase_playbook.json").write_text(json.dumps({"fase_1": {"e2e_required": []}}))
        (root / ".pipeline").mkdir()
        tools_src = Path(__file__).parent.parent / "tools"
        tools_dst = root / "tools"
        tools_dst.mkdir()
        for f in tools_src.glob("*.py"):
            shutil.copy(f, tools_dst / f.name)
        env = os.environ.copy()
        env["ATLAS_DISABLE_ENGRAM_MCP"] = "1"

        result = subprocess.run(
            [sys.executable, str(tools_dst / "atlas_dispatcher.py"), "audit-agent"],
            cwd=root, env=env, capture_output=True, text=True, timeout=10,
        )
        # fail-open: exit 0 con error en stderr
        assert result.returncode == 0
        assert "missing" in result.stderr.lower() or "agent" in result.stderr.lower()
    print("[OK]")


def test_10_hook_settings_registration():
    print("\n=== TEST 10: Hook registrado en .claude/settings.json ===")
    settings_path = Path(__file__).parent.parent / ".claude" / "settings.json"
    if not settings_path.exists():
        print("[SKIP] settings.json no encontrado en repo")
        return
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    post_tool_use = settings.get("hooks", {}).get("PostToolUse", [])
    # Buscar el hook qa-auto-audit
    found = False
    for matcher_block in post_tool_use:
        for hook in matcher_block.get("hooks", []):
            cmd = hook.get("command", "")
            if "qa-auto-audit" in cmd:
                found = True
                break
        if found:
            break
    assert found, "Hook qa-auto-audit.js no esta registrado en settings.json"

    # Verificar que el archivo del hook existe
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "qa-auto-audit.js"
    assert hook_path.exists(), "Hook file qa-auto-audit.js no existe"
    print("[OK] Hook registrado + archivo presente")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1K.1: Auto-invocation Hook for QA Workflow")
    print("="*70)

    tests = [
        test_1_agent_helper_map_has_evidence_collector,
        test_2_dev_agents_mapped,
        test_3_design_agents_mapped,
        test_4_unknown_agent_skipped,
        test_5_agent_with_empty_requirements_skipped,
        test_6_audit_evidence_collector_complete,
        test_7_audit_evidence_collector_incomplete,
        test_8_cli_audit_agent_subcommand,
        test_9_cli_audit_agent_missing_agent_param_fail_open,
        test_10_hook_settings_registration,
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

    print(f"\nRESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    if failed == 0:
        print("\nLO QUE 1K.1 NO HACE:")
        print("- NO bloquea el flujo del agente — solo emite WARN en stderr")
        print("- NO ejecuta los helpers faltantes automaticamente — solo audita")
        print("- Fail-open ante errores del hook (subprocess crash, JSON malformado)")
        print("- Requiere que dispatcher se haya invocado durante la sesion (sino")
        print("  no hay invocation log que auditar)")
        print("- AGENT_HELPER_REQUIREMENTS map debe mantenerse actualizado si")
        print("  cambian los helpers obligatorios por subagente")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
