"""Model provider boundary. See core/providers/base.py for the contract and its honesty rules."""

from .anthropic_host import AnthropicHostProvider
from .codex_cli import CodexCliProvider
from .base import (
    ERROR_CLASSES,
    HEALTH_STATES,
    ModelProvider,
    ProviderCapability,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderHealth,
    classify_failure,
    invoke,
    safe_health,
)
from .registry import build_providers, provider_id_of

__all__ = [
    "AnthropicHostProvider", "CodexCliProvider", "ERROR_CLASSES", "HEALTH_STATES", "ModelProvider", "ProviderCapability",
    "ProviderExecutionRequest", "ProviderExecutionResult", "ProviderHealth", "build_providers",
    "classify_failure", "invoke", "provider_id_of", "safe_health",
]
