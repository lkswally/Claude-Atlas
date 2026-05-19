#!/usr/bin/env python3
"""
Boot Sequence Helper — Light vs Full Mode Decision Engine
Implements context-aware boot mode selection to reduce token usage in retomas.
Hypothesis: 70% token savings in light mode vs full mode for retomas in non-critical phases.
"""

import json
from typing import Literal, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BootState:
    """Current boot state read from Engram"""
    session_id: str
    last_session_id: Optional[str]
    intento_actual: int
    boot_mode_used: str
    timestamp_boot: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BootState":
        return BootState(
            session_id=data.get("session_id"),
            last_session_id=data.get("last_session_id"),
            intento_actual=data.get("intento_actual", 1),
            boot_mode_used=data.get("boot_mode_used", "unknown"),
            timestamp_boot=data.get("timestamp_boot", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "last_session_id": self.last_session_id,
            "intento_actual": self.intento_actual,
            "boot_mode_used": self.boot_mode_used,
            "timestamp_boot": self.timestamp_boot,
        }


class BootSequenceCalculator:
    """Decision engine for light vs full boot mode selection"""

    # Phase-specific boot configurations (overridable)
    PHASE_CONFIG = {
        "fase_1_planificacion": {"force_full_mode": True, "allow_light_mode": False},
        "fase_2_arquitectura": {"force_full_mode": False, "allow_light_mode": True},
        "fase_2b_assets_creativos": {"force_full_mode": False, "allow_light_mode": True},
        "fase_3_desarrollo": {"force_full_mode": False, "allow_light_mode": True},
        "fase_4_certificacion": {"force_full_mode": True, "allow_light_mode": False},
        "fase_5_publicacion": {"force_full_mode": True, "allow_light_mode": False},
        "modificacion": {"force_full_mode": False, "allow_light_mode": True},
    }

    # Token estimates (hypothesis values — measure in practice)
    TOKEN_ESTIMATES = {
        "light": {"min": 50, "max": 100, "typical": 75},
        "full": {"min": 500, "max": 2000, "typical": 1200},
    }

    def __init__(self):
        pass

    def decide_mode(
        self,
        session_id: str,
        last_session_id: Optional[str],
        intento_actual: int,
        phase_actual: str,
    ) -> Literal["light", "full"]:
        """
        Decide boot mode based on session continuity, attempt count, and phase.

        Args:
            session_id: Current session UUID
            last_session_id: Previous session UUID (None if unknown)
            intento_actual: Attempt counter (1-3+)
            phase_actual: Current phase (fase_1, fase_2, etc.)

        Returns:
            "light" or "full" — mode to use
        """

        # Phase override: some phases always require full mode
        phase_config = self.PHASE_CONFIG.get(phase_actual, {})
        if phase_config.get("force_full_mode", False):
            return "full"

        if not phase_config.get("allow_light_mode", True):
            return "full"

        # Escalation: attempt 3+ always requires full mode (decisions/state needed)
        if intento_actual >= 3:
            return "full"

        # Session change: new session requires full mode to load DAG State
        if session_id != last_session_id:
            return "full"

        # Retake same session, attempt < 3, non-critical phase → light mode
        return "light"

    def estimate_tokens(self, mode: Literal["light", "full"]) -> Dict[str, int]:
        """
        Estimate token usage for a given boot mode.

        Returns dict with min, max, typical token counts.
        """
        return self.TOKEN_ESTIMATES.get(mode, {})

    def extract_light_summary(self, dag_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract minimal summary from DAG State for light boot.

        Light summary contains only immediate context needed to continue a task:
        - Current phase
        - Current task number and total
        - Stack (single line)
        - Last save timestamp
        """
        development = dag_state.get("desarrollo", {})
        stack = dag_state.get("stack", {})

        # Condense stack to single line
        stack_line = (
            f"{stack.get('frontend', 'none')}/"
            f"{stack.get('backend', 'none')}/"
            f"{stack.get('db', 'none')}"
        )

        return {
            "fase": dag_state.get("fase_actual"),
            "tarea_actual": development.get("tarea_actual", 0),
            "tarea_total": development.get("total_tareas", 0),
            "stack": stack_line,
            "ultimo_save": development.get("ultimo_save", ""),
            "type": "light_summary",
        }

    def validate_boot_state(self, boot_state: BootState) -> bool:
        """
        Validate that boot state is complete and coherent.

        Returns True if valid, False if missing critical fields.
        """
        if not boot_state.session_id:
            return False
        if boot_state.intento_actual < 1 or boot_state.intento_actual > 5:
            return False
        if boot_state.boot_mode_used not in ("light", "full"):
            return False
        return True

    def calculate_context_savings(
        self, boot_mode: Literal["light", "full"]
    ) -> Dict[str, Any]:
        """
        Calculate estimated context savings if using light mode vs full mode.

        Returns: {"mode": "light", "tokens_saved": 1125, "savings_percent": 70.0}
        """
        light = self.TOKEN_ESTIMATES["light"]["typical"]
        full = self.TOKEN_ESTIMATES["full"]["typical"]

        if boot_mode == "light":
            saved = full - light
            percent = (saved / full) * 100
            return {
                "boot_mode": "light",
                "tokens_saved": saved,
                "savings_percent": round(percent, 1),
            }
        else:
            return {
                "boot_mode": "full",
                "tokens_saved": 0,
                "savings_percent": 0.0,
            }


def main():
    """CLI entry point for testing and diagnostics"""
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python tools/boot_sequence_helper.py <command> [args...]"
        )
        print("Commands:")
        print("  decide-mode SESSION_ID LAST_SESSION_ID INTENTO PHASE")
        print("  estimate-tokens MODE")
        print("  extract-summary <dag-state.json>")
        print("  validate-state <boot-state.json>")
        print("  test-all")
        sys.exit(1)

    command = sys.argv[1]
    calc = BootSequenceCalculator()

    try:
        if command == "decide-mode":
            session_id = sys.argv[2] if len(sys.argv) > 2 else "sess-new"
            last_session_id = (
                sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "null" else None
            )
            intento = int(sys.argv[4]) if len(sys.argv) > 4 else 1
            phase = sys.argv[5] if len(sys.argv) > 5 else "fase_3_desarrollo"

            mode = calc.decide_mode(session_id, last_session_id, intento, phase)
            savings = calc.calculate_context_savings(mode)

            result = {
                "ok": True,
                "mode": mode,
                "reason": f"session_id={'match' if session_id == last_session_id else 'changed'}, intento={intento}, phase={phase}",
                "context_savings": savings,
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))

        elif command == "estimate-tokens":
            mode = sys.argv[2] if len(sys.argv) > 2 else "light"
            estimates = calc.estimate_tokens(mode)
            print(
                json.dumps(
                    {"ok": True, "mode": mode, "estimates": estimates},
                    indent=2,
                    ensure_ascii=False,
                )
            )

        elif command == "test-all":
            # TEST 1: Light mode when session_id == last + intento < 3 + non-critical
            test_1 = calc.decide_mode(
                "sess-123", "sess-123", 2, "fase_3_desarrollo"
            )
            assert test_1 == "light", f"TEST 1 FAIL: expected 'light', got '{test_1}'"

            # TEST 2: Full mode when session_id differs
            test_2 = calc.decide_mode(
                "sess-new", "sess-old", 1, "fase_3_desarrollo"
            )
            assert test_2 == "full", f"TEST 2 FAIL: expected 'full', got '{test_2}'"

            # TEST 3: Full mode forced for critical phases
            test_3 = calc.decide_mode(
                "sess-123", "sess-123", 1, "fase_1_planificacion"
            )
            assert (
                test_3 == "full"
            ), f"TEST 3 FAIL: expected 'full' for Fase 1, got '{test_3}'"

            # TEST 4: Full mode for escalation (intento >= 3)
            test_4 = calc.decide_mode(
                "sess-123", "sess-123", 3, "fase_3_desarrollo"
            )
            assert (
                test_4 == "full"
            ), f"TEST 4 FAIL: expected 'full' for intento=3, got '{test_4}'"

            # TEST 5: Validate boot state
            valid_state = BootState(
                session_id="sess-123",
                last_session_id="sess-123",
                intento_actual=2,
                boot_mode_used="light",
                timestamp_boot="2026-05-19T14:30:00Z",
            )
            assert calc.validate_boot_state(
                valid_state
            ), "TEST 5 FAIL: valid state rejected"

            # TEST 6: Extract light summary
            dag = {
                "fase_actual": "fase_3_desarrollo",
                "desarrollo": {
                    "tarea_actual": 5,
                    "total_tareas": 10,
                    "ultimo_save": "2026-05-19T14:25:00Z",
                },
                "stack": {
                    "frontend": "Next.js",
                    "backend": "Hono",
                    "db": "PostgreSQL",
                },
            }
            summary = calc.extract_light_summary(dag)
            assert summary["tarea_actual"] == 5, "TEST 6 FAIL: tarea extraction"
            assert (
                "Next.js" in summary["stack"]
            ), "TEST 6 FAIL: stack extraction"

            result = {
                "ok": True,
                "status": "PASS",
                "tests_run": 6,
                "details": [
                    "TEST 1: Light mode (same session, retake) — PASS",
                    "TEST 2: Full mode (new session) — PASS",
                    "TEST 3: Full mode (critical phase) — PASS",
                    "TEST 4: Full mode (escalation) — PASS",
                    "TEST 5: Validate boot state — PASS",
                    "TEST 6: Extract light summary — PASS",
                ],
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        error_result = {"ok": False, "error": str(e), "command": command}
        print(json.dumps(error_result, indent=2, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
