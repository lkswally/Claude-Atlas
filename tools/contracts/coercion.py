"""
Coercion layer between legacy dict envelopes and the formal
`Envelope.v1` Pydantic model.

Bloque F1.1. The dispatcher uses this at the top of
`validate_return_envelope` so that callers passing either form are
treated identically and the rest of the method keeps working with a
plain dict.

GUARANTEES
- `coerce_envelope(dict_input)` returns an `Envelope` instance with the
  same shape, including unknown fields (extra="allow").
- `coerce_envelope(envelope_instance)` returns the instance unchanged.
- `coerce_envelope(None)` / `coerce_envelope(str)` / etc. raises
  `ContractValidationError` loudly (programmer bug).
- `coerce_envelope(dict_with_bad_shape)` raises `LegacyShapeError` with
  `.errors: List[str]` formatted exactly like the legacy validator output.
- `to_legacy_dict(envelope)` produces a dict that is byte-equivalent (modulo
  key ordering) to what the agent originally sent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

from pydantic import ValidationError

from .envelope import Envelope
from .errors import ContractValidationError, LegacyShapeError


def coerce_envelope(obj: Union[Dict[str, Any], Envelope, Any]) -> Envelope:
    """Coerce a dict (or pass-through an Envelope) into an Envelope.

    Raises:
        ContractValidationError: if `obj` is not dict-like and not an Envelope.
        LegacyShapeError: if `obj` is a dict but fails contract validation.
            The exception carries `errors: List[str]` in legacy format so
            callers can return `(False, e.errors)` without translation.
    """
    if isinstance(obj, Envelope):
        return obj
    if not isinstance(obj, dict):
        raise ContractValidationError(
            f"Expected dict or Envelope, got {type(obj).__name__}"
        )
    try:
        return Envelope.model_validate(obj)
    except ValidationError as e:
        raise LegacyShapeError(_format_pydantic_errors(e)) from e


def to_legacy_dict(envelope: Envelope) -> Dict[str, Any]:
    """Serialise an Envelope back to a legacy dict.

    Thin wrapper over `Envelope.to_legacy_dict` for symmetry with
    `coerce_envelope` so callers can `from contracts.coercion import *`
    and have both helpers available.
    """
    if not isinstance(envelope, Envelope):
        raise ContractValidationError(
            f"to_legacy_dict expected Envelope, got {type(envelope).__name__}"
        )
    return envelope.to_legacy_dict()


# ---------------------------------------------------------------------
#  Internal: translate Pydantic errors to the legacy `List[str]` format
# ---------------------------------------------------------------------

def _format_pydantic_errors(err: ValidationError) -> List[str]:
    """
    Render a Pydantic ValidationError as the legacy validator did:
    one short human string per problem.

    Examples produced:
      - "status: input is not a valid string (got int)"
      - "archivos: input is not a valid list"
      - "contract_version: must be 'envelope.v1'"

    We deliberately keep the format short and field-prefixed so existing
    tests that grep for field names ('status', 'archivos', etc.) keep
    matching.
    """
    out: List[str] = []
    for item in err.errors():
        loc = ".".join(str(p) for p in item.get("loc", ())) or "<root>"
        msg = item.get("msg", "invalid")
        out.append(f"{loc}: {msg}")
    return out
