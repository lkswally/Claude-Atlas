"""
ATLAS Capability Policy Engine — F19
======================================

Evaluates capabilities against declarative policies in
config/capability.policy.yaml and returns structured decisions.

Decision outcomes:
  ALLOW          — capability is LIVE or meets required_status, proceed
  WARN           — usable but below ideal; log and continue
  DEGRADED       — fallback active or partial functionality; proceed with caution
  BLOCK          — no usable provider AND block_if_unavailable=true; halt task
  MISSING_POLICY — no policy entry found; treat as WARN

Disable: ATLAS_CAPABILITY_POLICY_DISABLED=1

Public API:
    from core.capabilities.policy import evaluate_capability, evaluate_all_capabilities

    decision = evaluate_capability("memory")
    # PolicyDecision(capability="memory", decision="ALLOW", provider="engram",
    #                status="LIVE", severity="CRITICAL", recovery_hint=None)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PolicyOutcome = Literal["ALLOW", "WARN", "DEGRADED", "BLOCK", "MISSING_POLICY"]

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_POLICY_FILE = _PROJECT_ROOT / "config" / "capability.policy.yaml"

# Status rank: higher = better
_STATUS_RANK: dict[str, int] = {
    "LIVE": 5,
    "CONFIG_ONLY": 4,
    "CLI_ONLY": 3,
    "PENDING_TOKEN": 2,
    "DEFERRED_PAID": 1,
    "NOT_RECOMMENDED": 1,
    "UNAVAILABLE": 0,
}

_REQUIRED_STATUS_RANK: dict[str, int] = {
    "LIVE": 5,
    "CONFIG_ONLY": 4,
    "PENDING_TOKEN": 2,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CapabilityPolicy:
    """Parsed policy entry for one capability."""
    capability: str
    critical: bool = False
    required_status: str = "LIVE"
    fallback_allowed: bool = False
    allowed_fallbacks: list[str] = field(default_factory=list)
    block_if_unavailable: bool = False
    recovery_hint: str = ""
    owner: str = ""
    severity: str = "MEDIUM"


@dataclass
class PolicyDecision:
    """Result of evaluating a capability against its policy."""
    capability: str
    decision: PolicyOutcome
    provider: str | None
    status: str
    severity: str
    recovery_hint: str
    fallback_used: bool = False
    notes: str = ""

    @property
    def is_blocking(self) -> bool:
        return self.decision == "BLOCK"

    @property
    def is_usable(self) -> bool:
        return self.decision in ("ALLOW", "WARN", "DEGRADED")

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "decision": self.decision,
            "provider": self.provider,
            "status": self.status,
            "severity": self.severity,
            "recovery_hint": self.recovery_hint,
            "fallback_used": self.fallback_used,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------

_policy_cache: dict[str, CapabilityPolicy] | None = None


def _load_yaml(path: Path) -> dict:
    """Load YAML without requiring PyYAML — uses stdlib fallback parser."""
    try:
        import yaml  # type: ignore[import]
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        pass
    # Minimal YAML-ish parser for our specific format (no complex types)
    return _parse_simple_yaml(path.read_text(encoding="utf-8"))


def _parse_simple_yaml(text: str) -> dict:
    """
    Parse the subset of YAML used in capability.policy.yaml:
    top-level keys, string/bool/list values, indented blocks.
    Falls back to {} on any ambiguity.
    """
    result: dict[str, Any] = {}
    current_cap: str | None = None
    current_list_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()

        # Skip comments and blank lines
        if not stripped or stripped.startswith("#"):
            current_list_key = None
            continue

        indent = len(line) - len(stripped)

        if indent == 0 and not stripped.startswith("-"):
            # Top-level key (capability name)
            key = stripped.rstrip(":")
            current_cap = key
            result[current_cap] = {}
            current_list_key = None

        elif indent == 2 and current_cap is not None and not stripped.startswith("-"):
            # Field under capability
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "":
                    # Expecting a list next
                    current_list_key = k
                    result[current_cap][k] = []
                elif v.lower() == "true":
                    result[current_cap][k] = True
                    current_list_key = None
                elif v.lower() == "false":
                    result[current_cap][k] = False
                    current_list_key = None
                else:
                    result[current_cap][k] = v.strip('"').strip("'")
                    current_list_key = None

        elif indent == 4 and stripped.startswith("- ") and current_cap and current_list_key:
            # List item
            item = stripped[2:].strip().strip('"').strip("'")
            result[current_cap][current_list_key].append(item)

    return result


def load_policy(policy_file: Path | None = None) -> dict[str, CapabilityPolicy]:
    """
    Load and parse capability.policy.yaml. Returns dict keyed by capability name.
    Caches after first load. Returns {} on any error (fail-open).
    """
    global _policy_cache
    if _policy_cache is not None and policy_file is None:
        return _policy_cache

    target = policy_file or _POLICY_FILE
    if not target.exists():
        return {}

    try:
        raw = _load_yaml(target)
    except Exception:
        return {}

    policies: dict[str, CapabilityPolicy] = {}
    for cap_name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        policies[cap_name] = CapabilityPolicy(
            capability=cap_name,
            critical=bool(entry.get("critical", False)),
            required_status=str(entry.get("required_status", "LIVE")),
            fallback_allowed=bool(entry.get("fallback_allowed", False)),
            allowed_fallbacks=list(entry.get("allowed_fallbacks") or []),
            block_if_unavailable=bool(entry.get("block_if_unavailable", False)),
            recovery_hint=str(entry.get("recovery_hint", "")),
            owner=str(entry.get("owner", "")),
            severity=str(entry.get("severity", "MEDIUM")),
        )

    if policy_file is None:
        _policy_cache = policies
    return policies


def get_policy(capability: str, policy_file: Path | None = None) -> CapabilityPolicy | None:
    """Return the policy for a capability, or None if not defined."""
    return load_policy(policy_file).get(capability)


def _reset_cache() -> None:
    """Clear the policy cache (used in tests)."""
    global _policy_cache
    _policy_cache = None


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_capability(
    name: str,
    policy_file: Path | None = None,
    _emit: bool = True,
    _events_file: Path | None = None,
) -> PolicyDecision:
    """
    Evaluate a capability against its policy.

    Combines router resolution + policy rules into a PolicyDecision.
    Never raises — returns MISSING_POLICY on unknown capability or any error.

    Args:
        name:         Capability name
        policy_file:  Override policy YAML path (for testing)
        _emit:        Whether to emit event to capability-events.jsonl
        _events_file: Override events file path (for testing)
    """
    if os.environ.get("ATLAS_CAPABILITY_POLICY_DISABLED") == "1":
        return PolicyDecision(
            capability=name,
            decision="ALLOW",
            provider=None,
            status="LIVE",
            severity="LOW",
            recovery_hint="",
            notes="policy disabled via ATLAS_CAPABILITY_POLICY_DISABLED=1",
        )

    # Get policy
    policy = get_policy(name, policy_file)
    if policy is None:
        decision = PolicyDecision(
            capability=name,
            decision="MISSING_POLICY",
            provider=None,
            status="UNKNOWN",
            severity="LOW",
            recovery_hint="",
            notes=f"No policy defined for '{name}'",
        )
        if _emit:
            _emit_policy_event(decision, "", _events_file)
        return decision

    # Get router resolution
    try:
        from .router import resolve_capability
        resolution = resolve_capability(name, requested_by="policy-engine", emit=False)
    except Exception as e:
        return PolicyDecision(
            capability=name,
            decision="BLOCK" if policy.block_if_unavailable else "WARN",
            provider=None,
            status="UNAVAILABLE",
            severity=policy.severity,
            recovery_hint=policy.recovery_hint,
            notes=f"Router error: {e}",
        )

    provider = resolution.provider
    status = resolution.status

    # Evaluate
    decision_outcome, fallback_used, notes = _apply_policy(policy, resolution)

    decision = PolicyDecision(
        capability=name,
        decision=decision_outcome,
        provider=provider,
        status=status,
        severity=policy.severity,
        recovery_hint=policy.recovery_hint if decision_outcome not in ("ALLOW",) else "",
        fallback_used=fallback_used,
        notes=notes,
    )

    if _emit:
        _emit_policy_event(decision, policy.owner, _events_file)

    return decision


def _apply_policy(
    policy: CapabilityPolicy,
    resolution: Any,
) -> tuple[PolicyOutcome, bool, str]:
    """
    Apply policy rules to a resolution. Returns (decision, fallback_used, notes).
    """
    status = resolution.status
    provider = resolution.provider
    fallback_used = False
    notes = ""

    # UNAVAILABLE
    if status == "UNAVAILABLE" or provider is None:
        if policy.block_if_unavailable:
            return "BLOCK", False, f"No provider available and block_if_unavailable=true"
        if policy.critical:
            return "WARN", False, f"Critical capability '{policy.capability}' has no provider"
        return "WARN", False, f"No provider available for '{policy.capability}'"

    # Check if status meets required_status
    actual_rank = _STATUS_RANK.get(status, 0)
    required_rank = _REQUIRED_STATUS_RANK.get(policy.required_status, 5)

    if actual_rank >= required_rank:
        # Provider meets policy requirements
        return "ALLOW", False, ""

    # Provider does NOT meet required_status
    # Check if fallback is allowed
    if policy.fallback_allowed:
        fallback = resolution.fallback
        if fallback and fallback.provider:
            fb_rank = _STATUS_RANK.get(fallback.status, 0)
            if fb_rank >= required_rank:
                # Fallback meets requirements
                return "DEGRADED", True, (
                    f"Primary provider '{provider}' is {status}; "
                    f"fallback '{fallback.provider}' is {fallback.status}"
                )
        # No fallback meets requirements
        notes = f"Provider '{provider}' is {status} (required: {policy.required_status}); no qualifying fallback"
        return "WARN", False, notes

    # Fallback not allowed
    if policy.block_if_unavailable and actual_rank == 0:
        return "BLOCK", False, f"Provider '{provider}' is {status}, fallback not allowed"

    # Sub-optimal but continue
    notes = f"Provider '{provider}' is {status} (required: {policy.required_status})"
    if policy.critical:
        return "WARN", False, notes
    return "WARN", False, notes


def evaluate_all_capabilities(
    policy_file: Path | None = None,
    _emit: bool = False,
    _events_file: Path | None = None,
) -> dict[str, PolicyDecision]:
    """
    Evaluate all capabilities that have a policy entry.
    Returns dict keyed by capability name.
    """
    policies = load_policy(policy_file)
    return {
        name: evaluate_capability(name, policy_file=policy_file, _emit=_emit, _events_file=_events_file)
        for name in policies
    }


# ---------------------------------------------------------------------------
# Events integration
# ---------------------------------------------------------------------------

def _emit_policy_event(
    decision: PolicyDecision,
    owner: str,
    events_file: Path | None = None,
) -> None:
    """Append policy decision to capability-events.jsonl. Fail-open."""
    try:
        from .events import emit_resolution
        emit_resolution(
            capability=decision.capability,
            provider_selected=decision.provider,
            provider_status=decision.status,
            fallback_used=decision.fallback_used,
            action=f"policy:{decision.decision}",
            requested_by=f"policy-engine:{owner}" if owner else "policy-engine",
            reason=decision.notes or f"policy decision: {decision.decision}",
            metadata={
                "policy_decision": decision.decision,
                "severity": decision.severity,
                "recovery_hint": decision.recovery_hint,
            },
            events_file=events_file,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    if args:
        for cap in args:
            d = evaluate_capability(cap, _emit=False)
            print(json.dumps(d.as_dict(), indent=2, ensure_ascii=False))
    else:
        results = evaluate_all_capabilities(_emit=False)
        n_block = sum(1 for d in results.values() if d.decision == "BLOCK")
        n_warn  = sum(1 for d in results.values() if d.decision == "WARN")
        n_allow = sum(1 for d in results.values() if d.decision == "ALLOW")
        print(f"Policy evaluation: {len(results)} capabilities")
        print(f"  ALLOW={n_allow}  WARN={n_warn}  BLOCK={n_block}")
        print()
        for name, d in sorted(results.items()):
            mark = {"ALLOW": "✓", "WARN": "~", "BLOCK": "✗", "DEGRADED": "≈", "MISSING_POLICY": "?"}.get(d.decision, "?")
            note = f" | {d.notes}" if d.notes else ""
            print(f"  [{mark}] {name:<22} {d.decision:<16} {d.status:<18} provider={d.provider or '—'}{note}")
