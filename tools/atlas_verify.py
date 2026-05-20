#!/usr/bin/env python3
"""
Post-merge verification for ATLAS Boot Sequence (Bloque 1A.5)
Validates that Boot Sequence implementation is complete and integrated.
"""

import sys
import os
import json
from pathlib import Path

def check_files_exist():
    """Verify all Boot Sequence files exist"""
    required_files = [
        "tools/boot_sequence_helper.py",
        "tools/boot_sequence_integration.py",
        "config/phase_playbook.json",
        "_qa/boot-sequence-test/VALIDATION-REPORT.md",
        "agents/orquestador.md"
    ]

    results = {}
    for f in required_files:
        path = Path(f)
        exists = path.exists()
        results[f] = "[PASS]" if exists else "[FAIL]"

    return results

def check_boot_sequence_logic():
    """Verify Boot Sequence logic is present"""
    try:
        from boot_sequence_helper import BootSequenceCalculator
        from boot_sequence_integration import BootSequenceIntegrator

        # Test basic instantiation
        calc = BootSequenceCalculator()
        integrator = BootSequenceIntegrator()

        # Test decide_mode exists
        assert hasattr(calc, 'decide_mode'), "decide_mode method missing"
        assert hasattr(integrator, 'run_boot_decision'), "run_boot_decision method missing"

        return {"boot_sequence_logic": "[PASS]"}
    except Exception as e:
        return {"boot_sequence_logic": f"[FAIL] {str(e)}"}

def check_phase_playbook():
    """Verify phase_playbook.json has boot_config"""
    try:
        with open("config/phase_playbook.json") as f:
            config = json.load(f)

        # Check if boot_config exists in phases
        boot_config_present = all(
            "boot_config" in phase
            for phase in config.get("phases", [])
        )

        if boot_config_present:
            return {"phase_playbook_boot_config": "[PASS]"}
        else:
            return {"phase_playbook_boot_config": "[FAIL] boot_config missing in phases"}
    except Exception as e:
        return {"phase_playbook_boot_config": f"[FAIL] {str(e)}"}

def check_orquestador_documentation():
    """Verify orquestador.md has Boot Sequence Paso 4a-4d"""
    try:
        with open("agents/orquestador.md", encoding="utf-8") as f:
            content = f.read()

        required_steps = ["Paso 4a", "Paso 4b", "Paso 4c", "Paso 4d"]
        # Check case-insensitive and allow for markdown formatting
        steps_present = all(
            any(step.lower() in line.lower() for line in content.split('\n'))
            for step in required_steps
        )

        if steps_present:
            return {"orquestador_boot_sequence": "[PASS]"}
        else:
            missing = [s for s in required_steps if s not in content]
            return {"orquestador_boot_sequence": f"[FAIL] Missing {missing}"}
    except Exception as e:
        return {"orquestador_boot_sequence": f"[FAIL] {str(e)}"}

def main():
    print("\n" + "="*70)
    print("ATLAS Boot Sequence Post-Merge Verification")
    print("="*70 + "\n")

    all_results = {}

    # Run checks
    print("[1/4] Checking files exist...")
    all_results.update(check_files_exist())

    print("[2/4] Checking Boot Sequence logic...")
    all_results.update(check_boot_sequence_logic())

    print("[3/4] Checking phase_playbook.json...")
    all_results.update(check_phase_playbook())

    print("[4/4] Checking orquestador.md documentation...")
    all_results.update(check_orquestador_documentation())

    # Print results
    print("\n" + "-"*70)
    print("VERIFICATION RESULTS")
    print("-"*70)

    for check, result in all_results.items():
        print(f"{check:40} {result}")

    # Overall status
    passes = sum(1 for r in all_results.values() if "[PASS]" in r)
    total = len(all_results)

    print("\n" + "="*70)
    if passes == total:
        print(f"[PASS] ALL CHECKS PASSED ({passes}/{total})")
        print("Boot Sequence is complete and integrated.")
        return 0
    else:
        print(f"[FAIL] SOME CHECKS FAILED ({passes}/{total})")
        return 1

if __name__ == "__main__":
    sys.exit(main())
