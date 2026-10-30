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
  * Capabilities come from config/model-router.yaml (single source, see _registry_backed). A characteristic the
    config does not verify stays UNKNOWN (None / "UNKNOWN"); it is never guessed.
"""

from __future__ import annotations

from typing import Optional

from ._registry_backed import RegistryBackedProvider
from .base import ProviderExecutionRequest, ProviderExecutionResult, ProviderHealth


class AnthropicHostProvider(RegistryBackedProvider):
    KIND = "host_managed"
    EXECUTABLE_FROM_ATLAS = False

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
