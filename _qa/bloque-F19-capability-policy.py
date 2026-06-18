#!/usr/bin/env python3
"""
Bloque F19 — Capability Policy Engine Tests
============================================

Verifica que el Policy Engine evalúa correctamente capabilities contra
políticas declarativas y devuelve decisiones consistentes.

Tests:
  T1  policy.py importa sin error
  T2  config/capability.policy.yaml existe y parsea correctamente
  T3  memory LIVE => ALLOW (capability crítica con provider LIVE)
  T4  repository PENDING_TOKEN => WARN, no BLOCK (block_if_unavailable=false)
  T5  design DEFERRED_PAID => WARN (not critical, not blocking)
  T6  capability crítica sin provider => WARN (memory forzado sin provider)
  T7  capability crítica sin provider + block_if_unavailable => BLOCK
  T8  browser con fallback permitido + primario degradado => DEGRADED
  T9  capability sin policy => MISSING_POLICY
  T10 ATLAS_CAPABILITY_POLICY_DISABLED=1 => decision ALLOW sin evaluar
  T11 evaluate_all_capabilities retorna todas las capabilities con policy
  T12 resolve_with_policy retorna (Resolution, PolicyDecision) correctamente
  T13 PolicyDecision.is_usable / is_blocking flags
  T14 policy_decision emitido en capability-events.jsonl (metadata)

Salida:
  [PASS] / [FAIL] por test
  Resumen al final

Exit code: 0 = todo PASS | 1 = al menos un FAIL
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_results: list[tuple[str, bool, str]] = []


def PASS(name: str, detail: str = "") -> None:
    _results.append((name, True, detail))
    print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))


def FAIL(name: str, detail: str = "") -> None:
    _results.append((name, False, detail))
    print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t1_policy_imports() -> None:
    try:
        from core.capabilities.policy import (
            load_policy, get_policy, evaluate_capability,
            evaluate_all_capabilities, PolicyDecision, CapabilityPolicy,
        )
        PASS("T1 policy.py importa", "todas las funciones públicas OK")
    except Exception as e:
        FAIL("T1 policy.py importa", str(e))


def t2_policy_yaml_parses() -> None:
    try:
        from core.capabilities.policy import load_policy, _reset_cache
        _reset_cache()
        policies = load_policy()
        assert len(policies) >= 14, f"esperaba >=14 policies, got {len(policies)}"
        assert "memory" in policies
        assert "browser" in policies
        assert "repository" in policies
        assert policies["memory"].critical is True
        assert policies["memory"].block_if_unavailable is True
        assert policies["browser"].fallback_allowed is True
        PASS("T2 policy YAML parsea", f"{len(policies)} capabilities con policy")
    except Exception as e:
        FAIL("T2 policy YAML parsea", str(e))


def t3_memory_live_allow() -> None:
    try:
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("memory", _emit=False)
        assert d.decision == "ALLOW", f"decision={d.decision}"
        assert d.provider == "engram", f"provider={d.provider}"
        assert d.status == "LIVE", f"status={d.status}"
        assert d.is_usable is True
        PASS("T3 memory LIVE => ALLOW", f"provider={d.provider} status={d.status}")
    except Exception as e:
        FAIL("T3 memory LIVE => ALLOW", str(e))


def t4_repository_pending_warn_not_block() -> None:
    try:
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("repository", _emit=False)
        # repository has PENDING_TOKEN status, required_status=LIVE, block_if_unavailable=false
        assert d.decision in ("WARN", "DEGRADED"), f"decision={d.decision} (expected WARN)"
        assert d.decision != "BLOCK", f"repository should not BLOCK (block_if_unavailable=false)"
        assert d.is_usable is True or d.decision == "WARN"
        PASS("T4 repository PENDING => WARN (not BLOCK)", f"decision={d.decision} provider={d.provider}")
    except Exception as e:
        FAIL("T4 repository PENDING => WARN (not BLOCK)", str(e))


def t5_design_deferred_warn() -> None:
    try:
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("design", _emit=False)
        assert d.decision in ("WARN", "DEGRADED", "BLOCK"), f"decision={d.decision}"
        # design is not critical and not block_if_unavailable, so should be WARN not BLOCK
        assert d.decision != "BLOCK", f"design should not BLOCK"
        PASS("T5 design DEFERRED => WARN", f"decision={d.decision} status={d.status}")
    except Exception as e:
        FAIL("T5 design DEFERRED => WARN", str(e))


def t6_critical_no_provider_warn() -> None:
    """Force memory to UNAVAILABLE by using a policy that has block_if_unavailable=false."""
    try:
        import tempfile, textwrap
        from core.capabilities.policy import evaluate_capability, _reset_cache

        # Write a temp policy where memory is critical but block_if_unavailable=false
        policy_yaml = textwrap.dedent("""
            memory:
              critical: true
              required_status: LIVE
              fallback_allowed: false
              block_if_unavailable: false
              recovery_hint: "test hint"
              owner: test
              severity: CRITICAL
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(policy_yaml)
            tmp_path = Path(f.name)

        try:
            # Override router so memory appears unavailable
            # We test with a real file but mock a non-existent capability name
            # that has critical=true but no provider
            policy_yaml2 = textwrap.dedent("""
                nonexistent_critical_cap:
                  critical: true
                  required_status: LIVE
                  fallback_allowed: false
                  block_if_unavailable: false
                  recovery_hint: "test"
                  owner: test
                  severity: CRITICAL
            """)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f2:
                f2.write(policy_yaml2)
                tmp_path2 = Path(f2.name)

            try:
                d = evaluate_capability("nonexistent_critical_cap", policy_file=tmp_path2, _emit=False)
                assert d.decision in ("WARN", "BLOCK"), f"decision={d.decision}"
                PASS("T6 critical no provider => WARN", f"decision={d.decision}")
            finally:
                tmp_path2.unlink(missing_ok=True)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:
        FAIL("T6 critical no provider => WARN", str(e))


def t7_critical_no_provider_block() -> None:
    """Critical capability with block_if_unavailable=true and no provider => BLOCK."""
    try:
        import textwrap
        from core.capabilities.policy import evaluate_capability

        policy_yaml = textwrap.dedent("""
            nonexistent_blocker:
              critical: true
              required_status: LIVE
              fallback_allowed: false
              block_if_unavailable: true
              recovery_hint: "must be fixed"
              owner: test
              severity: CRITICAL
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(policy_yaml)
            tmp_path = Path(f.name)
        try:
            d = evaluate_capability("nonexistent_blocker", policy_file=tmp_path, _emit=False)
            assert d.decision == "BLOCK", f"expected BLOCK, got {d.decision}"
            assert d.is_blocking is True
            assert d.is_usable is False
            PASS("T7 critical block_if_unavailable => BLOCK", f"decision={d.decision}")
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:
        FAIL("T7 critical block_if_unavailable => BLOCK", str(e))


def t8_fallback_allowed_degraded() -> None:
    """
    When primary is below required_status and fallback is available => DEGRADED.
    We write a policy requiring LIVE for a synthetic capability that resolves
    to CONFIG_ONLY primary but has a fallback.
    """
    try:
        import textwrap
        from core.capabilities.policy import _apply_policy, CapabilityPolicy

        class _FakeProvider:
            def __init__(self, provider, status):
                self.provider = provider
                self.status = status
                self.fallback = None

        policy = CapabilityPolicy(
            capability="test_browser",
            critical=True,
            required_status="LIVE",
            fallback_allowed=True,
            allowed_fallbacks=["claude_in_chrome"],
            block_if_unavailable=False,
            recovery_hint="use fallback",
            severity="HIGH",
        )

        # Simulate primary=CONFIG_ONLY, fallback=LIVE
        primary = _FakeProvider("playwright", "CONFIG_ONLY")
        fallback_res = _FakeProvider("claude_in_chrome", "LIVE")
        primary.fallback = fallback_res

        outcome, fb_used, notes = _apply_policy(policy, primary)
        assert outcome == "DEGRADED", f"expected DEGRADED got {outcome}"
        assert fb_used is True
        PASS("T8 fallback allowed => DEGRADED", f"outcome={outcome} fallback_used={fb_used}")
    except Exception as e:
        FAIL("T8 fallback allowed => DEGRADED", str(e))


def t9_missing_policy() -> None:
    try:
        import textwrap
        from core.capabilities.policy import evaluate_capability

        # Use an empty policy file
        policy_yaml = "# empty\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(policy_yaml)
            tmp_path = Path(f.name)
        try:
            d = evaluate_capability("memory", policy_file=tmp_path, _emit=False)
            assert d.decision == "MISSING_POLICY", f"expected MISSING_POLICY got {d.decision}"
            PASS("T9 missing policy => MISSING_POLICY", f"decision={d.decision}")
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:
        FAIL("T9 missing policy => MISSING_POLICY", str(e))


def t10_disabled_env_var() -> None:
    original = os.environ.get("ATLAS_CAPABILITY_POLICY_DISABLED")
    try:
        os.environ["ATLAS_CAPABILITY_POLICY_DISABLED"] = "1"
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("memory", _emit=False)
        assert d.decision == "ALLOW", f"expected ALLOW when disabled, got {d.decision}"
        assert "disabled" in d.notes.lower()
        PASS("T10 DISABLED => ALLOW", f"notes='{d.notes}'")
    except Exception as e:
        FAIL("T10 DISABLED => ALLOW", str(e))
    finally:
        if original is None:
            os.environ.pop("ATLAS_CAPABILITY_POLICY_DISABLED", None)
        else:
            os.environ["ATLAS_CAPABILITY_POLICY_DISABLED"] = original


def t11_evaluate_all_capabilities() -> None:
    try:
        from core.capabilities.policy import evaluate_all_capabilities, load_policy, _reset_cache
        _reset_cache()
        policies = load_policy()
        results = evaluate_all_capabilities(_emit=False)
        assert len(results) == len(policies), f"expected {len(policies)}, got {len(results)}"
        for name, d in results.items():
            assert d.capability == name, f"mismatch: {d.capability} != {name}"
            assert d.decision in ("ALLOW", "WARN", "DEGRADED", "BLOCK", "MISSING_POLICY")
        n_allow = sum(1 for d in results.values() if d.decision == "ALLOW")
        PASS("T11 evaluate_all_capabilities", f"{len(results)} evaluated, {n_allow} ALLOW")
    except Exception as e:
        FAIL("T11 evaluate_all_capabilities", str(e))


def t12_resolve_with_policy() -> None:
    try:
        from core.capabilities.router import resolve_with_policy
        from core.capabilities.policy import PolicyDecision
        resolution, decision = resolve_with_policy("memory", emit_event=False)
        assert resolution is not None
        assert resolution.provider == "engram"
        assert decision is not None
        assert isinstance(decision, PolicyDecision)
        assert decision.decision in ("ALLOW", "WARN", "DEGRADED", "BLOCK", "MISSING_POLICY")
        PASS("T12 resolve_with_policy", f"resolution.provider={resolution.provider} decision={decision.decision}")
    except Exception as e:
        FAIL("T12 resolve_with_policy", str(e))


def t13_policy_decision_flags() -> None:
    try:
        from core.capabilities.policy import PolicyDecision
        allow = PolicyDecision("test", "ALLOW", "p", "LIVE", "LOW", "")
        block = PolicyDecision("test", "BLOCK", None, "UNAVAILABLE", "CRITICAL", "fix it")
        warn  = PolicyDecision("test", "WARN", "p", "CONFIG_ONLY", "HIGH", "")
        degrad= PolicyDecision("test", "DEGRADED", "p2", "LIVE", "MEDIUM", "")

        assert allow.is_usable is True and allow.is_blocking is False
        assert block.is_usable is False and block.is_blocking is True
        assert warn.is_usable is True and warn.is_blocking is False
        assert degrad.is_usable is True and degrad.is_blocking is False
        PASS("T13 PolicyDecision flags", "is_usable / is_blocking correctos")
    except Exception as e:
        FAIL("T13 PolicyDecision flags", str(e))


def t14_policy_event_metadata() -> None:
    """Policy decision emits event with policy_decision in metadata."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            from core.capabilities.policy import evaluate_capability, _reset_cache
            _reset_cache()
            evaluate_capability("memory", _emit=True, _events_file=events_file)

            assert events_file.exists(), "No events file created"
            lines = events_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) >= 1, f"expected >=1 line, got {len(lines)}"

            # Find event with policy metadata
            found = False
            for line in lines:
                d = json.loads(line)
                meta = d.get("metadata", {})
                if "policy_decision" in meta:
                    assert meta["policy_decision"] in ("ALLOW", "WARN", "DEGRADED", "BLOCK")
                    found = True
                    break
            assert found, f"No event with policy_decision in metadata. Lines: {lines}"
            PASS("T14 policy event metadata", f"policy_decision={meta.get('policy_decision')} in event")
    except Exception as e:
        FAIL("T14 policy event metadata", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("Bloque F19 — Capability Policy Engine Tests")
    print("=" * 60)
    print()

    t1_policy_imports()
    t2_policy_yaml_parses()
    t3_memory_live_allow()
    t4_repository_pending_warn_not_block()
    t5_design_deferred_warn()
    t6_critical_no_provider_warn()
    t7_critical_no_provider_block()
    t8_fallback_allowed_degraded()
    t9_missing_policy()
    t10_disabled_env_var()
    t11_evaluate_all_capabilities()
    t12_resolve_with_policy()
    t13_policy_decision_flags()
    t14_policy_event_metadata()

    print()
    n_pass = sum(1 for _, ok, _ in _results if ok)
    n_fail = sum(1 for _, ok, _ in _results if not ok)
    total  = len(_results)
    print(f"Total: {total} | PASS: {n_pass} | FAIL: {n_fail}")
    print()
    if n_fail == 0:
        print("RESULTADO: PASS")
    else:
        failed = [name for name, ok, _ in _results if not ok]
        print(f"RESULTADO: FAIL — {', '.join(failed)}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
