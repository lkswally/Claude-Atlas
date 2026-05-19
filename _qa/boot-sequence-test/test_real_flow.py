#!/usr/bin/env python3
"""
Boot Sequence Real Flow Validation
Simulates actual Paso 4a-4d execution in realistic conditions.
NOT a unit test — pragmatic validation of real workflow.
"""

import sys
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add tools to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from boot_sequence_helper import BootSequenceCalculator
from boot_sequence_integration import BootSequenceIntegrator


class BootSequenceRealFlowValidator:
    """Validates Boot Sequence in realistic Paso 4a-4d scenario"""

    def __init__(self, proyecto: str):
        self.proyecto = proyecto
        self.integrator = BootSequenceIntegrator()
        # Simulate Engram storage: {topic_key: observation}
        self.engram_simulation = {}

    def mem_search_simulation(self, topic_key: str) -> Optional[Dict[str, Any]]:
        """Simulates mem_search — returns stored boot-state or None"""
        return self.engram_simulation.get(topic_key)

    def mem_save_simulation(self, topic_key: str, content: Dict[str, Any]) -> bool:
        """Simulates mem_save — stores boot-state, returns success"""
        self.engram_simulation[topic_key] = content
        return True

    def run_scenario(
        self,
        scenario_name: str,
        session_id: str,
        phase: str,
        intento_hint: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute one scenario: Paso 4a → 4b → 4c → 4d

        Real flow:
        1. Paso 4a: mem_search boot-state (might be null)
        2. Paso 4b: run_boot_decision
        3. Paso 4c: mem_save new boot-state
        4. Paso 4d: return mode for DAG load

        Returns: evidence dict with all decisions made
        """

        print(f"\n{'='*70}")
        print(f"SCENARIO: {scenario_name}")
        print(f"{'='*70}")

        topic_key = f"{self.proyecto}/boot-state"

        # PASO 4a: Read previous boot-state from Engram (simulation)
        print(f"[Paso 4a] mem_search('{topic_key}')")
        prev_boot_state_dict = self.mem_search_simulation(topic_key)
        if prev_boot_state_dict:
            print(f"  [FOUND] Previous boot-state")
            print(f"     session_id: {prev_boot_state_dict.get('session_id')}")
            print(f"     last_session_id: {prev_boot_state_dict.get('last_session_id')}")
            print(f"     intento_actual: {prev_boot_state_dict.get('intento_actual')}")
        else:
            print(f"  [NOT FOUND] Boot-state (bootstrap scenario)")
            prev_boot_state_dict = None

        # PASO 4b: Execute run_boot_decision with REAL parameters
        print(f"\n[Paso 4b] run_boot_decision()")
        print(f"  Input:")
        print(f"    proyecto: {self.proyecto}")
        print(f"    session_id: {session_id}")
        print(f"    phase_actual: {phase}")
        print(f"    prev_boot_state: {prev_boot_state_dict is not None}")

        result = self.integrator.run_boot_decision(
            proyecto=self.proyecto,
            session_id=session_id,
            phase_actual=phase,
            prev_boot_state=prev_boot_state_dict,
        )

        boot_mode = result["mode"]
        new_boot_state = result["boot_state"]
        savings = result["context_savings"]

        print(f"  Output:")
        print(f"    mode: {boot_mode}")
        print(f"    context_savings: {savings['savings_percent']}%")
        print(f"    new boot_state.intento_actual: {new_boot_state['intento_actual']}")

        # PASO 4c: Persist new boot-state to Engram (simulation)
        print(f"\n[Paso 4c] mem_save(topic_key='{topic_key}')")
        save_success = self.mem_save_simulation(topic_key, new_boot_state)
        print(f"  [SAVED] Boot-state persisted: {save_success}")
        print(f"     session_id: {new_boot_state['session_id']}")
        print(f"     last_session_id: {new_boot_state['last_session_id']}")
        print(f"     intento_actual: {new_boot_state['intento_actual']}")

        # PASO 4d: Use mode for DAG State loading
        print(f"\n[Paso 4d] Use boot_mode for DAG load")
        print(f"  [LOAD] boot_mode='{boot_mode}' = Load")
        if boot_mode == "light":
            print(f"     DAG light summary (~75 tokens)")
        else:
            print(f"     DAG full state (~1200 tokens)")

        # Evidence: what happened in this scenario
        evidence = {
            "scenario": scenario_name,
            "session_id": session_id,
            "phase": phase,
            "prev_boot_state_found": prev_boot_state_dict is not None,
            "boot_mode_chosen": boot_mode,
            "context_savings_percent": savings["savings_percent"],
            "new_boot_state": new_boot_state,
            "decision_reason": result["decision_reason"],
            "intento_incremented": (
                prev_boot_state_dict.get("intento_actual", 0)
                if prev_boot_state_dict
                else 0
            )
            < new_boot_state["intento_actual"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        return evidence


def main():
    """Run 3 validation scenarios"""

    print("\n" + "=" * 70)
    print("BOOT SEQUENCE REAL FLOW VALIDATION")
    print("=" * 70)

    validator = BootSequenceRealFlowValidator(proyecto="test-projeto-boot-sequence")
    all_evidence = []

    # TEST 1: Bootstrap (new project, Fase 1)
    print("\n\n" + "=" * 70)
    print("TEST 1: BOOTSTRAP - New project, Fase 1")
    print("=" * 70)

    evidence_1 = validator.run_scenario(
        scenario_name="Bootstrap",
        session_id="sess-boot-001",
        phase="fase_1_planificacion",
    )
    all_evidence.append(evidence_1)

    # TEST 2: Retake same session (Fase 3, intento increments)
    print("\n\n" + "=" * 70)
    print("TEST 2: RETAKE - Same session, Fase 3")
    print("=" * 70)

    evidence_2 = validator.run_scenario(
        scenario_name="Retake (same session)",
        session_id="sess-boot-001",  # SAME session as TEST 1
        phase="fase_3_desarrollo",
    )
    all_evidence.append(evidence_2)

    # TEST 3: New session (Fase 3, intento resets)
    print("\n\n" + "=" * 70)
    print("TEST 3: NEW SESSION - Different session_id, Fase 3")
    print("=" * 70)

    evidence_3 = validator.run_scenario(
        scenario_name="New session",
        session_id="sess-boot-002",  # DIFFERENT session
        phase="fase_3_desarrollo",
    )
    all_evidence.append(evidence_3)

    # Validation summary
    print("\n\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    print("\n[TEST 1] Bootstrap:")
    print(f"  Mode: {evidence_1['boot_mode_chosen']} (expected: full)")
    print(
        f"  intento: {evidence_1['new_boot_state']['intento_actual']} (expected: 1)"
    )
    print(f"  Result: {'PASS' if evidence_1['boot_mode_chosen'] == 'full' else 'FAIL'}")

    print("\n[TEST 2] Retake same session:")
    print(f"  Mode: {evidence_2['boot_mode_chosen']} (expected: light)")
    print(
        f"  intento: {evidence_2['new_boot_state']['intento_actual']} (expected: 2)"
    )
    print(
        f"  Savings: {evidence_2['context_savings_percent']}% (expected: ~93.8%)"
    )
    print(
        f"  Result: {'PASS' if evidence_2['boot_mode_chosen'] == 'light' else 'FAIL'}"
    )

    print("\n[TEST 3] New session:")
    print(f"  Mode: {evidence_3['boot_mode_chosen']} (expected: full)")
    print(
        f"  intento: {evidence_3['new_boot_state']['intento_actual']} (expected: 1)"
    )
    print(
        f"  last_session_id: {evidence_3['new_boot_state']['last_session_id']} (expected: sess-boot-001)"
    )
    test_3_pass = (
        evidence_3["boot_mode_chosen"] == "full"
        and evidence_3["new_boot_state"]["intento_actual"] == 1
        and evidence_3["new_boot_state"]["last_session_id"] == "sess-boot-001"
    )
    print(f"  Result: {'PASS' if test_3_pass else 'FAIL'}")

    # Final verdict
    print("\n" + "=" * 70)
    all_pass = (
        evidence_1["boot_mode_chosen"] == "full"
        and evidence_2["boot_mode_chosen"] == "light"
        and test_3_pass
    )
    print(f"OVERALL: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 70)

    # Detailed JSON evidence
    print("\n\nDETAILED EVIDENCE (JSON):")
    print(json.dumps(all_evidence, indent=2, ensure_ascii=True))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
