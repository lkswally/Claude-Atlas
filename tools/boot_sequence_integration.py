#!/usr/bin/env python3
"""
Boot Sequence Integration — Real Operational Wrapper
Coordinates boot decision: read prev state → decide mode → return new state for persistence.
Called by orquestador.md § Boot Sequence Paso 4.
"""

import json
import sys
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from boot_sequence_helper import BootSequenceCalculator, BootState


class BootSequenceIntegrator:
    """Coordinates boot decision workflow for orquestador"""

    def __init__(self):
        self.calculator = BootSequenceCalculator()

    def run_boot_decision(
        self,
        proyecto: str,
        session_id: str,
        phase_actual: str,
        prev_boot_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute complete boot decision workflow.

        Args:
            proyecto: Project name (for topic_key)
            session_id: Current session UUID
            phase_actual: Current phase (fase_1_planificacion, etc.)
            prev_boot_state: Previous boot-state from Engram (dict or None if not found)

        Returns:
            {
              "mode": "light" | "full",
              "boot_state": {new state to persist},
              "context_savings": {...},
              "decision_reason": "...",
              "topic_key": "{proyecto}/boot-state"
            }

        Workflow:
          1. Parse prev_boot_state (or create new)
          2. Call decide_mode() with real values
          3. Increment intento_actual or reset per session
          4. Return new boot_state ready for mem_save
        """

        # Step 1: Parse previous boot state (or init new)
        is_bootstrap = False
        if prev_boot_state:
            try:
                prev_state = BootState.from_dict(prev_boot_state)
            except:
                prev_state = self._init_boot_state(session_id)
                is_bootstrap = True
        else:
            prev_state = self._init_boot_state(session_id)
            is_bootstrap = True

        # Step 2: Decide mode
        # For retake detection: pass prev session_id to know if this is same session continuing
        # If session_id == prev_state.session_id: RETAKE (same session)
        # If session_id != prev_state.session_id: NEW SESSION
        mode = self.calculator.decide_mode(
            session_id=session_id,
            last_session_id=prev_state.session_id,  # Use previous session ID, not last_session_id
            intento_actual=prev_state.intento_actual,
            phase_actual=phase_actual,
        )

        # Step 3: Prepare new boot state
        if is_bootstrap:
            # First boot: don't update, just set mode
            new_boot_state = BootState(
                session_id=session_id,
                last_session_id=None,
                intento_actual=1,
                boot_mode_used=mode,
                timestamp_boot=datetime.utcnow().isoformat() + "Z",
            )
        else:
            # Retake or new session: update from previous
            new_boot_state = self._update_boot_state(prev_state, session_id, mode)

        # Step 4: Calculate savings
        savings = self.calculator.calculate_context_savings(mode)

        # Step 5: Reason (for debugging)
        reason = self._explain_decision(
            session_id, prev_state.last_session_id, prev_state.intento_actual, mode
        )

        return {
            "ok": True,
            "mode": mode,
            "boot_state": new_boot_state.to_dict(),
            "context_savings": savings,
            "decision_reason": reason,
            "topic_key": f"{proyecto}/boot-state",
        }

    @staticmethod
    def _init_boot_state(session_id: str) -> BootState:
        """Initialize new boot state for first session"""
        return BootState(
            session_id=session_id,
            last_session_id=None,
            intento_actual=1,
            boot_mode_used="unknown",
            timestamp_boot=datetime.utcnow().isoformat() + "Z",
        )

    @staticmethod
    def _update_boot_state(
        prev_state: BootState, current_session_id: str, mode: Literal["light", "full"]
    ) -> BootState:
        """
        Update boot state for next boot:
        - If new session (current != prev): reset intento to 1, move prev to last
        - If same session: increment intento
        """

        if current_session_id != prev_state.session_id:
            # New session: reset counter, save prev as last
            return BootState(
                session_id=current_session_id,
                last_session_id=prev_state.session_id,
                intento_actual=1,
                boot_mode_used=mode,
                timestamp_boot=datetime.utcnow().isoformat() + "Z",
            )
        else:
            # Same session: increment intento
            return BootState(
                session_id=current_session_id,
                last_session_id=prev_state.last_session_id,
                intento_actual=prev_state.intento_actual + 1,
                boot_mode_used=mode,
                timestamp_boot=datetime.utcnow().isoformat() + "Z",
            )

    @staticmethod
    def _explain_decision(
        session_id: str,
        last_session_id: Optional[str],
        intento_actual: int,
        mode: str,
    ) -> str:
        """Generate human-readable explanation of decision"""
        if session_id != last_session_id:
            prev_str = f"{last_session_id[:8]}..." if last_session_id else "none"
            return f"New session (prev: {prev_str}) = full"
        elif intento_actual >= 3:
            return f"Escalation (intento={intento_actual}) = full"
        else:
            return f"Retake (intento={intento_actual}) = {mode}"


def main():
    """CLI entry point for testing"""
    if len(sys.argv) < 2:
        print(
            "Usage: python tools/boot_sequence_integration.py <command> [args...]"
        )
        print("Commands:")
        print("  run-boot-decision PROYECTO SESSION_ID PHASE [prev_boot_state.json]")
        print("  test-all")
        sys.exit(1)

    command = sys.argv[1]
    integrator = BootSequenceIntegrator()

    try:
        if command == "run-boot-decision":
            proyecto = sys.argv[2] if len(sys.argv) > 2 else "test-proj"
            session_id = sys.argv[3] if len(sys.argv) > 3 else "sess-new"
            phase = sys.argv[4] if len(sys.argv) > 4 else "fase_3_desarrollo"
            prev_json = sys.argv[5] if len(sys.argv) > 5 else None

            prev_state = None
            if prev_json:
                try:
                    with open(prev_json) as f:
                        prev_state = json.load(f)
                except:
                    pass

            result = integrator.run_boot_decision(
                proyecto, session_id, phase, prev_state
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif command == "test-all":
            print("Running 3 functional tests...")
            print()

            # TEST 1: Bootstrap (new project, Fase 1)
            print("[TEST 1] Bootstrap — new project, Fase 1")
            result_1 = integrator.run_boot_decision(
                proyecto="test-proj",
                session_id="sess-1",
                phase_actual="fase_1_planificacion",
                prev_boot_state=None,
            )
            assert result_1["mode"] == "full", "TEST 1: expected full mode for Fase 1"
            assert (
                result_1["boot_state"]["intento_actual"] == 1
            ), "TEST 1: expected intento=1"
            assert (
                result_1["boot_state"]["last_session_id"] is None
            ), "TEST 1: expected last_session=None"
            print(f"[PASS] {result_1['decision_reason']}")
            print(f"       Mode: {result_1['mode']}, Boot state saved: {result_1['topic_key']}")
            print()

            # TEST 2: Retake same session, Fase 3
            print("[TEST 2] Retake - same session, Fase 3, intento 2->3")
            result_2 = integrator.run_boot_decision(
                proyecto="test-proj",
                session_id="sess-1",
                phase_actual="fase_3_desarrollo",
                prev_boot_state=result_1["boot_state"],
            )
            assert result_2["mode"] == "light", "TEST 2: expected light mode for Fase 3 retake"
            assert (
                result_2["boot_state"]["intento_actual"] == 2
            ), "TEST 2: expected intento=2 (incremented from 1)"
            assert (
                result_2["boot_state"]["session_id"] == "sess-1"
            ), "TEST 2: session_id should not change"
            print(f"[PASS] {result_2['decision_reason']}")
            print(f"       Mode: {result_2['mode']}, Context savings: {result_2['context_savings']['savings_percent']}%")
            print()

            # TEST 3: New session, Fase 3
            print("[TEST 3] New session - different session_id, Fase 3, intento reset")
            result_3 = integrator.run_boot_decision(
                proyecto="test-proj",
                session_id="sess-new",
                phase_actual="fase_3_desarrollo",
                prev_boot_state=result_2["boot_state"],
            )
            assert result_3["mode"] == "full", "TEST 3: expected full mode for new session"
            assert (
                result_3["boot_state"]["intento_actual"] == 1
            ), "TEST 3: expected intento=1 (reset for new session)"
            assert (
                result_3["boot_state"]["last_session_id"] == "sess-1"
            ), "TEST 3: expected last_session_id = prev session"
            print(f"[PASS] {result_3['decision_reason']}")
            print(f"       Mode: {result_3['mode']}, Boot state reset for new session")
            print()

            print("=" * 60)
            print("ALL 3 TESTS PASSED")
            print("=" * 60)
            result = {
                "ok": True,
                "status": "PASS",
                "tests_run": 3,
                "details": [
                    "TEST 1: Bootstrap (new project) = full mode PASS",
                    "TEST 2: Retake (same session, intento++) = light mode PASS",
                    "TEST 3: New session (reset intento) = full mode PASS",
                ],
            }
            print(json.dumps(result, indent=2, ensure_ascii=True))

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        import traceback
        error_result = {
            "ok": False,
            "error": str(e),
            "command": command,
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_result, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
