"""
Exception classes for the formal contracts layer (Bloque F1.1).

These are intentionally minimal. They exist so that the dispatcher can
distinguish:

  - "the input is not even coerceable" (programmer bug, raise loudly)
  - "the input is a dict that fails contract validation" (caller bug,
    must be reported in legacy List[str] format so we stay backward
    compatible with validate_return_envelope's return signature)

NOTHING in this module imports Pydantic. Keep it free of heavy deps so
that `from tools.contracts.errors import ...` is cheap.
"""

from __future__ import annotations

from typing import List


class ContractValidationError(Exception):
    """
    Raised when the input to `coerce_envelope` cannot be coerced at all.

    This is for programmer errors: passing `None`, a `str`, an `int`, etc.
    where a dict or Envelope instance was expected.

    Callers that hit this should treat it as a bug, not a user-facing error.
    """


class LegacyShapeError(Exception):
    """
    Raised when a dict is coerceable in principle but fails the contract
    schema (missing required fields, wrong types, etc.).

    Carries `errors: List[str]` formatted exactly like the legacy
    `validate_return_envelope` return value, so callers can re-emit them
    without translation.

    The dispatcher catches this and returns `(False, e.errors)`.
    """

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors) if errors else "envelope shape invalid")
        self.errors: List[str] = list(errors)
