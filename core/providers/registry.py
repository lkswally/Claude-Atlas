"""
Provider factory (roadmap P4). Builds ModelProvider instances from the Model Router's registry dict.

Only providers with a VERIFIED adapter are instantiated. A provider named in the config without one is
reported in `skipped` and never built, so listing "codex" in YAML can never make it look usable.
The registry dict is passed in by the caller: core/ does not import tools/ (no reverse dependency).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from .anthropic_host import AnthropicHostProvider
from .base import ModelProvider

# provider id -> adapter class. Adding a provider means adding a verified adapter here (roadmap P5).
_ADAPTERS = {
    "anthropic": AnthropicHostProvider,
}


def build_providers(registry: Mapping[str, Any]) -> Tuple[Dict[str, ModelProvider], List[str]]:
    providers: Dict[str, ModelProvider] = {}
    skipped: List[str] = []
    for pid in (registry.get("providers") or {}):
        adapter = _ADAPTERS.get(pid)
        if adapter is None:
            skipped.append(pid)
        else:
            providers[pid] = adapter(registry, pid)
    return providers, skipped


def provider_id_of(registry: Mapping[str, Any], model_id: str) -> Optional[str]:
    """The registry is the authority on which provider serves a model (not string-splitting the id)."""
    m = (registry.get("models") or {}).get(model_id)
    return m.get("provider") if isinstance(m, dict) else None
