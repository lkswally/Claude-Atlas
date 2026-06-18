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

__all__ = ["get_capability", "list_capabilities", "capability_status"]
