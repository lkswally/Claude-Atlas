"""
Anthropic compatibility adapter (roadmap P4): the CURRENT model path, expressed through ModelProvider without
changing how anything runs.

What is true today, and what this adapter therefore says:
  * The models (anthropic/sonnet, anthropic/opus) are run by the Claude Code HOST via its Agent tool. ATLAS's
    dispatcher never spawns agents, so ATLAS can describe and route to these models but cannot invoke them:
    execute() returns NOT_EXECUTABLE, it does not pretend.
  * Claude Code exposes no health or quota API to ATLAS, so health() is UNKNOWN. Whether to *assume* availability
    inside an active session is a router policy (`assume_available_if_unknown` in config/model-router.yaml), not
    something a provider may claim on its own.
  * Capabilities come from config/model-router.yaml (single source). A characteristic the config does not verify
    stays UNKNOWN (None / "UNKNOWN"); it is never guessed.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from .base import (
    TIERS,
    ModelProvider,
    ProviderCapability,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderHealth,
)


def _tri(value: Any) -> Optional[bool]:
    """Config spells an unverified boolean as the string UNKNOWN. UNKNOWN is None, never False."""
    return value if isinstance(value, bool) else None


class AnthropicHostProvider(ModelProvider):
    KIND = "host_managed"

    def __init__(self, registry: Mapping[str, Any], provider_id: str = "anthropic"):
        self.id = provider_id
        self._providers = dict(registry.get("providers") or {})
        self._models = dict(registry.get("models") or {})

    def _enabled(self) -> bool:
        cfg = self._providers.get(self.id)
        return isinstance(cfg, dict) and cfg.get("enabled") is True     # missing / non-bool => disabled (fail closed)

    def models(self) -> List[str]:
        if not self._enabled():
            return []
        return [mid for mid, m in self._models.items()
                if isinstance(m, dict) and m.get("provider") == self.id and m.get("enabled") is True]

    def capabilities(self, model_id: str) -> Optional[ProviderCapability]:
        if model_id not in self.models():
            return None
        m = self._models[model_id]
        ctx = m.get("context_tier")
        strengths = m.get("strengths")
        return ProviderCapability(
            provider_id=self.id,
            model_id=model_id,
            supports_tools=_tri(m.get("supports_tools")),
            supports_multimodal=_tri(m.get("supports_multimodal")),
            context_tier=ctx if ctx in TIERS else "UNKNOWN",
            latency_tier=str(m.get("latency_tier") or "UNKNOWN"),
            strengths=tuple(str(s) for s in strengths) if isinstance(strengths, (list, tuple)) else (),
            cost_tier=str(m.get("cost_tier") or "UNKNOWN"),
            executable_from_atlas=False,
        )

    def health(self, model_id: Optional[str] = None) -> ProviderHealth:
        if not self._enabled():
            return ProviderHealth("UNKNOWN", "provider disabled or absent in config", "config")
        if model_id is not None and model_id not in self.models():
            return ProviderHealth("MODEL_UNAVAILABLE", f"{model_id} is not an enabled model of {self.id}", "config")
        return ProviderHealth("UNKNOWN", "host-managed: Claude Code exposes no health/quota API to ATLAS", "host_session")

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        return ProviderExecutionResult(
            request.request_id, self.id, request.model_id, False, "NOT_EXECUTABLE", "",
            "host-managed: these models run inside the Claude Code host via the Agent tool; ATLAS does not spawn agents",
        )

    def status(self) -> dict:
        return {"id": self.id, "kind": self.KIND, "enabled": self._enabled(), "models": self.models(),
                "executable_from_atlas": False, "health": self.health().state}
