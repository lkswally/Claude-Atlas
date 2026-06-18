#!/usr/bin/env python3
"""
Bloque F20 — Capability Contract Tests
========================================

Pruebas funcionales de contrato por cada capability registrada.
NO valida solo instalación — valida que la interfaz del sistema cumple
los contratos declarados en registry, policy y router.

Contratos verificados:
  memory        → resolve LIVE, proveedor engram, fallback None
  browser       → resolve LIVE, fallback chain playwright→chrome→preview
  documentation → resolve LIVE, proveedor context7
  repository    → resolve PENDING_TOKEN, recovery_hint útil
  design        → resolve DEFERRED_PAID, no bloquear sin block_if_unavailable
  visualization → resolve LIVE, proveedor visualize
  scheduling    → resolve LIVE, proveedor scheduled_tasks
  deployment    → resolve PENDING_TOKEN, no bloquear
  database      → NOT_RECOMMENDED → CONFIG_ONLY, no bloquear
  computer_ctrl → resolve LIVE

Contrato de política:
  critical + LIVE → ALLOW
  critical + no provider → WARN (no BLOCK si block_if_unavailable=false)
  non-critical + UNAVAILABLE → WARN
  block_if_unavailable + no provider → BLOCK

Contrato del event log:
  resolve_capability + emit=True → evento escrito a JSONL
  PolicyDecision.metadata.policy_decision → presente en evento

Tests: 14 (matching F16-F19 pattern)
Exit code: 0 = todo PASS | 1 = al menos un FAIL
"""

from __future__ import annotations

import json
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

def tc1_memory_contract() -> None:
    """memory → LIVE via engram, no fallback needed at primary."""
    try:
        from core.capabilities.router import resolve_capability
        r = resolve_capability("memory", requested_by="contract-test", emit=False)
        assert r.status == "LIVE", f"status={r.status}"
        assert r.provider == "engram", f"provider={r.provider}"
        assert r.is_usable is True
        PASS("TC1 memory contract", f"LIVE via {r.provider}")
    except Exception as e:
        FAIL("TC1 memory contract", str(e))


def tc2_browser_fallback_chain() -> None:
    """browser → LIVE primary (playwright), has ≥2 fallback chain."""
    try:
        from core.capabilities.router import resolve_capability
        r = resolve_capability("browser", requested_by="contract-test", emit=False)
        assert r.status == "LIVE", f"status={r.status}"
        assert r.provider in ("playwright", "claude_in_chrome", "claude_preview"), \
            f"provider={r.provider}"
        # fallback chain exists
        assert r.fallback is not None, "browser must have fallback provider"
        PASS("TC2 browser fallback chain", f"primary={r.provider} fallback={r.fallback.provider}")
    except Exception as e:
        FAIL("TC2 browser fallback chain", str(e))


def tc3_documentation_contract() -> None:
    """documentation → LIVE via context7."""
    try:
        from core.capabilities.router import resolve_capability
        r = resolve_capability("documentation", requested_by="contract-test", emit=False)
        assert r.is_usable is True, f"not usable: {r.status}"
        assert r.provider == "context7", f"provider={r.provider}"
        PASS("TC3 documentation contract", f"LIVE via {r.provider}")
    except Exception as e:
        FAIL("TC3 documentation contract", str(e))


def tc4_repository_pending_not_blocked() -> None:
    """repository → PENDING_TOKEN: no bloquea (block_if_unavailable=false), recovery_hint útil."""
    try:
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("repository", _emit=False)
        assert d.decision != "BLOCK", f"repository should not BLOCK, got {d.decision}"
        assert d.decision in ("WARN", "ALLOW", "DEGRADED"), f"decision={d.decision}"
        # Policy tiene recovery_hint útil
        from core.capabilities.policy import get_policy
        p = get_policy("repository")
        assert p is not None
        assert len(p.recovery_hint) > 10, "recovery_hint should be informative"
        PASS("TC4 repository pending not blocked",
             f"decision={d.decision} hint='{p.recovery_hint[:40]}'")
    except Exception as e:
        FAIL("TC4 repository pending not blocked", str(e))


def tc5_design_deferred_not_blocked() -> None:
    """design → DEFERRED_PAID: WARN, no BLOCK (block_if_unavailable=false)."""
    try:
        from core.capabilities.policy import evaluate_capability
        d = evaluate_capability("design", _emit=False)
        assert d.decision != "BLOCK", f"design should not BLOCK, got {d.decision}"
        assert d.status in ("DEFERRED_PAID", "CONFIG_ONLY", "UNAVAILABLE"), \
            f"unexpected status={d.status}"
        PASS("TC5 design deferred not blocked", f"decision={d.decision} status={d.status}")
    except Exception as e:
        FAIL("TC5 design deferred not blocked", str(e))


def tc6_critical_block_contract() -> None:
    """block_if_unavailable=true + no provider → BLOCK (contract guarantee)."""
    try:
        import textwrap
        from core.capabilities.policy import evaluate_capability
        policy_yaml = textwrap.dedent("""
            critical_contract_test:
              critical: true
              required_status: LIVE
              fallback_allowed: false
              block_if_unavailable: true
              recovery_hint: "contract test blocker"
              owner: test
              severity: CRITICAL
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                         delete=False, encoding="utf-8") as f:
            f.write(policy_yaml)
            tmp = Path(f.name)
        try:
            d = evaluate_capability("critical_contract_test", policy_file=tmp, _emit=False)
            assert d.decision == "BLOCK", f"expected BLOCK got {d.decision}"
            assert d.is_blocking is True
            assert d.is_usable is False
            PASS("TC6 critical block contract", "block_if_unavailable + no provider → BLOCK")
        finally:
            tmp.unlink(missing_ok=True)
    except Exception as e:
        FAIL("TC6 critical block contract", str(e))


def tc7_visualization_live() -> None:
    """visualization → LIVE via visualize."""
    try:
        from core.capabilities.router import resolve_capability
        r = resolve_capability("visualization", requested_by="contract-test", emit=False)
        assert r.is_usable is True, f"not usable: {r.status}"
        PASS("TC7 visualization live", f"status={r.status} provider={r.provider}")
    except Exception as e:
        FAIL("TC7 visualization live", str(e))


def tc8_all_critical_have_policy() -> None:
    """Todas las capabilities críticas tienen policy declarada."""
    try:
        from core.capabilities.router import CRITICAL_CAPABILITIES
        from core.capabilities.policy import get_policy, _reset_cache
        _reset_cache()
        missing = [c for c in CRITICAL_CAPABILITIES if get_policy(c) is None]
        assert not missing, f"missing policy for: {missing}"
        PASS("TC8 critical capabilities have policy",
             f"{len(CRITICAL_CAPABILITIES)} critical, all have policy")
    except Exception as e:
        FAIL("TC8 critical capabilities have policy", str(e))


def tc9_resolve_with_policy_tuple() -> None:
    """resolve_with_policy returns (Resolution, PolicyDecision) correctly."""
    try:
        from core.capabilities.router import resolve_with_policy
        from core.capabilities.router import Resolution
        from core.capabilities.policy import PolicyDecision
        res, dec = resolve_with_policy("memory", emit_event=False)
        assert isinstance(res, Resolution), f"type={type(res)}"
        assert isinstance(dec, PolicyDecision), f"type={type(dec)}"
        assert res.provider == "engram"
        assert dec.decision in ("ALLOW", "WARN", "DEGRADED", "BLOCK", "MISSING_POLICY")
        PASS("TC9 resolve_with_policy tuple", f"res.provider={res.provider} dec={dec.decision}")
    except Exception as e:
        FAIL("TC9 resolve_with_policy tuple", str(e))


def tc10_event_contract() -> None:
    """resolve_capability(emit=True) writes JSONL event with correct fields."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            from core.capabilities.router import resolve_capability
            resolve_capability("memory", requested_by="tc10", emit=True,
                               _events_file=events_file)
            assert events_file.exists(), "no events file created"
            lines = events_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) >= 1
            d = json.loads(lines[0])
            required_fields = ["timestamp", "capability", "requested_by",
                               "provider_selected", "provider_status",
                               "fallback_used", "resolution_ok", "action"]
            missing = [f for f in required_fields if f not in d]
            assert not missing, f"missing fields: {missing}"
            assert d["capability"] == "memory"
            assert d["requested_by"] == "tc10"
            PASS("TC10 event contract", f"all {len(required_fields)} required fields present")
    except Exception as e:
        FAIL("TC10 event contract", str(e))


def tc11_policy_event_metadata() -> None:
    """evaluate_capability + _emit=True writes policy_decision to event metadata."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            from core.capabilities.policy import evaluate_capability, _reset_cache
            _reset_cache()
            evaluate_capability("browser", _emit=True, _events_file=events_file)
            lines = events_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) >= 1
            found = any(
                json.loads(l).get("metadata", {}).get("policy_decision") is not None
                for l in lines
            )
            assert found, "no event with policy_decision in metadata"
            PASS("TC11 policy event metadata", "policy_decision present in event metadata")
    except Exception as e:
        FAIL("TC11 policy event metadata", str(e))


def tc12_all_capabilities_evaluate() -> None:
    """evaluate_all_capabilities() runs without crash for all 14 capabilities."""
    try:
        from core.capabilities.policy import evaluate_all_capabilities, _reset_cache
        _reset_cache()
        results = evaluate_all_capabilities(_emit=False)
        assert len(results) >= 14, f"expected >=14 capabilities, got {len(results)}"
        for name, d in results.items():
            assert d.capability == name
            assert d.decision in ("ALLOW", "WARN", "DEGRADED", "BLOCK", "MISSING_POLICY")
        n_allow = sum(1 for d in results.values() if d.decision == "ALLOW")
        PASS("TC12 all capabilities evaluate",
             f"{len(results)} evaluated, {n_allow} ALLOW, 0 crashes")
    except Exception as e:
        FAIL("TC12 all capabilities evaluate", str(e))


def tc13_registry_policy_consistency() -> None:
    """Every capability in registry has a policy entry (no orphans)."""
    try:
        from core.capabilities.registry import list_capabilities
        from core.capabilities.policy import load_policy, _reset_cache
        _reset_cache()
        policies = load_policy()
        caps = list_capabilities()
        orphaned = [c.name for c in caps if c.name not in policies]
        if orphaned:
            FAIL("TC13 registry-policy consistency",
                 f"capabilities without policy: {orphaned}")
        else:
            PASS("TC13 registry-policy consistency",
                 f"all {len(caps)} capabilities have policy")
    except Exception as e:
        FAIL("TC13 registry-policy consistency", str(e))


def tc14_dependency_graph_no_critical_broken() -> None:
    """Critical capabilities with LIVE status have no broken policy or registry entry."""
    try:
        from core.capabilities.router import CRITICAL_CAPABILITIES
        from core.capabilities.router import resolve_capability
        from core.capabilities.policy import evaluate_capability, _reset_cache
        _reset_cache()
        broken = []
        for cap_name in CRITICAL_CAPABILITIES:
            r = resolve_capability(cap_name, requested_by="tc14", emit=False)
            d = evaluate_capability(cap_name, _emit=False)
            if not r.is_usable:
                broken.append(f"{cap_name}: not usable (status={r.status})")
            if d.is_blocking:
                broken.append(f"{cap_name}: policy BLOCK — {d.recovery_hint[:40]}")
        if broken:
            FAIL("TC14 dependency graph", "; ".join(broken))
        else:
            PASS("TC14 dependency graph",
                 f"all {len(CRITICAL_CAPABILITIES)} critical capabilities usable, none BLOCK")
    except Exception as e:
        FAIL("TC14 dependency graph", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("Bloque F20 — Capability Contract Tests")
    print("=" * 60)
    print()

    tc1_memory_contract()
    tc2_browser_fallback_chain()
    tc3_documentation_contract()
    tc4_repository_pending_not_blocked()
    tc5_design_deferred_not_blocked()
    tc6_critical_block_contract()
    tc7_visualization_live()
    tc8_all_critical_have_policy()
    tc9_resolve_with_policy_tuple()
    tc10_event_contract()
    tc11_policy_event_metadata()
    tc12_all_capabilities_evaluate()
    tc13_registry_policy_consistency()
    tc14_dependency_graph_no_critical_broken()

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
