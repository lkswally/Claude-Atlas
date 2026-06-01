"""
ATLAS formal contracts — public re-exports.

Bloque F1.1 reducido (scope: envelope only). Future blocks will add
PhaseGate / AuditTrail / ClaimAudit here.

USAGE
    from tools.contracts import (
        Envelope, EnvelopeStatus, EnvelopeMode,
        coerce_envelope, to_legacy_dict,
        ContractValidationError, LegacyShapeError,
    )

The dispatcher imports this module via a try/except so the contracts
layer is OPTIONAL: if for any reason `tools/contracts/` is removed or
Pydantic is missing, the dispatcher falls back to the legacy dict path
without raising.
"""

from .envelope import (
    ENVELOPE_VERSION,
    Envelope,
    EnvelopeMode,
    EnvelopeStatus,
)
from .coercion import coerce_envelope, to_legacy_dict
from .errors import ContractValidationError, LegacyShapeError

__all__ = [
    # Models / enums
    "Envelope",
    "EnvelopeStatus",
    "EnvelopeMode",
    "ENVELOPE_VERSION",
    # Coercion helpers
    "coerce_envelope",
    "to_legacy_dict",
    # Errors
    "ContractValidationError",
    "LegacyShapeError",
]
