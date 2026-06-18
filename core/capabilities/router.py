"""
ATLAS Capability Router — F16
==============================

Resolves capabilities to providers without coupling agents to specific MCPs.

Usage:
    from core.capabilities.router import resolve_capability, CapabilityRouter

    resolution = resolve_capability("documentation")
    # Resolution(capability="documentation", provider="context7",
    #            status="LIVE", tool_prefix="mcp__context7__", fallback=None, action="use")

Agents must request capabilities by name, not MCP IDs:
    WRONG: "usar Context7"
    RIGHT: "solicitar capability documentation"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ResolutionStatus = Literal[
    "LIVE",           # provider active, tools visible in session
    "CONFIG_ONLY",    # configured in .mcp.json, available after restart
    "PENDING_TOKEN",  # configured but needs secret/token
    "DEFERRED_PAID",  # requires paid subscription — not available
    "UNAVAILABLE",    # no provider registered
]

# Human-readable action hints returned with each resolution
_ACTION: dict[str, str] = {
    "LIVE":          "use",
    "CONFIG_ONLY":   "restart_session",
    "PENDING_TOKEN": "set_token",
    "DEFERRED_PAID": "acquire_license",
    "UNAVAILABLE":   "register_provider",
}

# Critical capabilities: the router WARNs if these have no LIVE provider
CRITICAL_CAPABILITIES = {"memory", "browser", "documentation"}


@dataclass
class Resolution:
    """Result of resolving a capability name to a concrete provider."""
    capability: str
    provider: str | None         # primary provider mcp_id, or None
    status: ResolutionStatus
    tool_prefix: str | None      # e.g. "mcp__context7__"
    fallback: "Resolution | None"  # next-best provider, or None
    action: str                  # hint: what to do to activate this resolution
    notes: str = ""              # extra info from provider entry

    @property
    def is_usable(self) -> bool:
        """True when the provider is immediately usable (LIVE or CONFIG_ONLY)."""
        return self.status in ("LIVE", "CONFIG_ONLY")

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "provider": self.provider,
            "status": self.status,
            "tool_prefix": self.tool_prefix,
            "fallback": self.fallback.as_dict() if self.fallback else None,
            "action": self.action,
            "notes": self.notes,
        }


def _make_unavailable(capability: str) -> Resolution:
    return Resolution(
        capability=capability,
        provider=None,
        status="UNAVAILABLE",
        tool_prefix=None,
        fallback=None,
        action=_ACTION["UNAVAILABLE"],
    )


def resolve_capability(name: str) -> Resolution:
    """
    Resolve a capability name to its best available provider.

    Returns a Resolution with:
    - primary provider (best status)
    - fallback provider (next best, if primary is not LIVE)
    - action hint

    Never raises — returns UNAVAILABLE resolution on unknown capability.
    """
    if os.environ.get("ATLAS_CAPABILITIES_DISABLED") == "1":
        return _make_unavailable(name)

    try:
        from .registry import get_capability
    except Exception:
        return _make_unavailable(name)

    cap = get_capability(name)
    if cap is None:
        return _make_unavailable(name)

    providers = cap.providers
    if not providers:
        return _make_unavailable(name)

    # Priority order matches base.py active_provider
    _PRIORITY = ("LIVE", "CONFIG_ONLY", "CLI_ONLY", "PENDING_TOKEN", "DEFERRED_PAID", "NOT_RECOMMENDED")

    def _resolution_for(p) -> Resolution:
        status: ResolutionStatus
        raw = p.status
        if raw in ("LIVE", "CONFIG_ONLY", "PENDING_TOKEN", "DEFERRED_PAID"):
            status = raw  # type: ignore[assignment]
        elif raw in ("CLI_ONLY", "NOT_RECOMMENDED", "MISSING", "OPTIONAL"):
            status = "CONFIG_ONLY"  # surface as needing setup
        else:
            status = "UNAVAILABLE"
        return Resolution(
            capability=name,
            provider=p.mcp_id,
            status=status,
            tool_prefix=p.tool_prefix,
            fallback=None,
            action=_ACTION.get(status, "check"),
            notes=p.notes,
        )

    # Build ordered list of resolutions
    ordered: list[Resolution] = []
    for priority_status in _PRIORITY:
        for p in providers:
            if p.status == priority_status:
                ordered.append(_resolution_for(p))

    if not ordered:
        return _make_unavailable(name)

    primary = ordered[0]
    # Fallback: next provider with different mcp_id
    fallback = next(
        (r for r in ordered[1:] if r.provider != primary.provider),
        None,
    )
    primary.fallback = fallback
    return primary


class CapabilityRouter:
    """
    Stateful router for batch capability resolution.
    Caches resolutions within the same instance.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Resolution] = {}

    def resolve(self, capability: str) -> Resolution:
        if capability not in self._cache:
            self._cache[capability] = resolve_capability(capability)
        return self._cache[capability]

    def resolve_many(self, capabilities: list[str]) -> dict[str, Resolution]:
        return {name: self.resolve(name) for name in capabilities}

    def critical_status(self) -> dict[str, str]:
        """Returns status of all CRITICAL_CAPABILITIES."""
        return {name: self.resolve(name).status for name in CRITICAL_CAPABILITIES}

    def all_live(self) -> list[str]:
        """List all capabilities that have a LIVE provider."""
        try:
            from .registry import list_capabilities
            caps = list_capabilities()
        except Exception:
            return []
        return [
            c.name for c in caps
            if c.active_provider and c.active_provider.status == "LIVE"
        ]


# Module-level singleton — use for one-off lookups
_router = CapabilityRouter()


def router() -> CapabilityRouter:
    """Return the module-level router singleton."""
    return _router


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if args:
        for cap_name in args:
            r = resolve_capability(cap_name)
            import json
            print(json.dumps(r.as_dict(), indent=2))
    else:
        import json
        rt = CapabilityRouter()
        try:
            from .registry import list_capabilities
            names = [c.name for c in list_capabilities()]
        except Exception:
            names = list(CRITICAL_CAPABILITIES)
        results = rt.resolve_many(names)
        for name, res in results.items():
            fb = f" (fallback: {res.fallback.provider})" if res.fallback else ""
            print(f"  {name:<22} {res.status:<18} provider={res.provider or '—'}{fb}")
