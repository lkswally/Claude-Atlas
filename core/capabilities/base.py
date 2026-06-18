"""Base class for all ATLAS capabilities."""

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["LIVE", "CONFIG_ONLY", "CLI_ONLY", "PENDING_TOKEN", "DEFERRED_PAID", "NOT_RECOMMENDED", "MISSING"]


@dataclass
class Provider:
    """One MCP provider implementing a capability."""
    mcp_id: str
    name: str
    status: Status
    tool_prefix: str
    notes: str = ""


@dataclass
class Capability:
    """
    A named capability that ATLAS can request.
    Multiple providers may implement the same capability;
    the first LIVE provider is the active one.
    """
    name: str
    description: str
    providers: list[Provider] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)

    @property
    def active_provider(self) -> Provider | None:
        """Return best available provider by priority order."""
        for status in ("LIVE", "CONFIG_ONLY", "CLI_ONLY", "PENDING_TOKEN", "DEFERRED_PAID", "NOT_RECOMMENDED"):
            for p in self.providers:
                if p.status == status:
                    return p
        return None

    @property
    def is_available(self) -> bool:
        """True if any provider is LIVE, CONFIG_ONLY, or CLI_ONLY."""
        p = self.active_provider
        return p is not None and p.status in ("LIVE", "CONFIG_ONLY", "CLI_ONLY")

    def summary(self) -> dict:
        p = self.active_provider
        return {
            "capability": self.name,
            "available": self.is_available,
            "provider": p.mcp_id if p else None,
            "status": p.status if p else "UNAVAILABLE",
            "tool_prefix": p.tool_prefix if p else None,
        }
