"""
core/capabilities — ATLAS Capability Runtime
=============================================

Abstraction layer between the dispatcher and MCP providers.
The dispatcher requests capabilities by name; this layer resolves
which MCP implements them and exposes a uniform interface.

Usage:
    from core.capabilities import get_capability, list_capabilities
    cap = get_capability("documentation")   # returns Context7 provider info
    cap = get_capability("repository")      # returns GitHub provider info

Provider resolution order: LIVE > CONFIG_ONLY > CLI_ONLY
"""

from .registry import get_capability, list_capabilities, capability_status
from .router import resolve_capability, resolve_with_policy, CapabilityRouter, router, Resolution, CRITICAL_CAPABILITIES
from .policy import (
    evaluate_capability, evaluate_all_capabilities,
    get_policy, load_policy,
    PolicyDecision, CapabilityPolicy,
)

__all__ = [
    "get_capability", "list_capabilities", "capability_status",
    "resolve_capability", "resolve_with_policy", "CapabilityRouter", "router",
    "Resolution", "CRITICAL_CAPABILITIES",
    "evaluate_capability", "evaluate_all_capabilities",
    "get_policy", "load_policy",
    "PolicyDecision", "CapabilityPolicy",
]
