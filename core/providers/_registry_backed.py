"""
Shared base for providers whose model list and declared capabilities come from the Model Router registry
(config/model-router.yaml is the single source). Adapters add health + execution; everything about
"which models, what do they declare" lives here once.

Fail closed: a provider that is missing, not a dict, or not `enabled: true` serves nothing.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from .base import TIERS, ModelProvider, ProviderCapability


def tri(value: Any) -> Optional[bool]:
    """Config spells an unverified boolean as the string UNKNOWN. UNKNOWN is None, never False."""
    return value if isinstance(value, bool) else None


class RegistryBackedProvider(ModelProvider):
    EXECUTABLE_FROM_ATLAS = False        # adapters that can really run a request override this

    def __init__(self, registry: Mapping[str, Any], provider_id: str):
        self.id = provider_id
        self._providers = dict(registry.get("providers") or {})
        self._models = dict(registry.get("models") or {})

    def _enabled(self) -> bool:
        cfg = self._providers.get(self.id)
        return isinstance(cfg, dict) and cfg.get("enabled") is True

    def _model_cfg(self, model_id: str) -> Optional[dict]:
        return self._models[model_id] if model_id in self.models() else None

    def models(self) -> List[str]:
        if not self._enabled():
            return []
        return [mid for mid, m in self._models.items()
                if isinstance(m, dict) and m.get("provider") == self.id and m.get("enabled") is True]

    def capabilities(self, model_id: str) -> Optional[ProviderCapability]:
        m = self._model_cfg(model_id)
        if m is None:
            return None
        ctx = m.get("context_tier")
        strengths = m.get("strengths")
        return ProviderCapability(
            provider_id=self.id,
            model_id=model_id,
            supports_tools=tri(m.get("supports_tools")),
            supports_multimodal=tri(m.get("supports_multimodal")),
            context_tier=ctx if ctx in TIERS else "UNKNOWN",
            latency_tier=str(m.get("latency_tier") or "UNKNOWN"),
            strengths=tuple(str(s) for s in strengths) if isinstance(strengths, (list, tuple)) else (),
            cost_tier=str(m.get("cost_tier") or "UNKNOWN"),
            executable_from_atlas=self.EXECUTABLE_FROM_ATLAS,
        )
