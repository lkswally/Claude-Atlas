"""
Envelope.v1 — Formal Pydantic contract for subagent return envelopes.

Bloque F1.1 reducido. Scope: ONLY the envelope contract. PhaseGate,
AuditTrail and ClaimAudit are NOT in this bloque.

BACKWARD COMPAT (regla dura):
- Every field that does not exist in legacy envelopes is Optional with
  default=None.
- `extra="allow"` so any unknown field a subagent emits is preserved.
- `EnvelopeStatus` enum includes EVERY status string that has ever been
  used in ATLAS (completado, fallido, PASS, FAIL, CERTIFIED, NEEDS WORK).
- `contract_version` defaults to "envelope.v1" so legacy dicts that do
  not declare it still validate.

The dispatcher's `validate_return_envelope` semantics do NOT change. This
file only formalises the shape; the per-mode validation logic stays
exactly where it was (in atlas_dispatcher.py).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ENVELOPE_VERSION = "envelope.v1"


class EnvelopeStatus(StrEnum):
    """
    Every status string the dispatcher recognises today.

    Adding a new value here is a backward-compatible change. Removing one
    is a breaking change and must wait for v2.
    """

    COMPLETADO = "completado"
    FALLIDO = "fallido"
    PASS = "PASS"
    FAIL = "FAIL"
    CERTIFIED = "CERTIFIED"
    NEEDS_WORK = "NEEDS WORK"


class EnvelopeMode(StrEnum):
    """
    The four validation modes the dispatcher exposes.

    Surfaced as an enum here for type-safety in code that wants to call
    `validate_return_envelope` with an explicit mode. The dispatcher itself
    still accepts plain strings.
    """

    STANDARD = "standard"
    QA_STRICT = "qa_strict"
    DEV_STRICT = "dev_strict"
    DESIGN_STRICT = "design_strict"


class Envelope(BaseModel):
    """
    Formal envelope contract — v1.

    Mirrors the ad-hoc dict shape that subagents have been emitting since
    the dispatcher's inception. Every field is permissive by default.
    Per-mode validations (qa_strict / dev_strict / design_strict) remain
    in the dispatcher and are NOT re-implemented here.

    Coercion from a legacy dict is done via `tools.contracts.coercion.coerce_envelope`.
    Serialisation back to a legacy dict is done via `to_legacy_dict`.
    """

    model_config = ConfigDict(
        # Subagents may emit custom fields (typo, project-specific
        # extensions). We preserve them silently to keep backward compat.
        extra="allow",
        # We accept enums by value (string), not just by enum instance.
        use_enum_values=True,
        # We do NOT freeze the model — the dispatcher mutates the dict
        # form by appending _dispatcher_warnings etc.
        frozen=False,
        # Validate on assignment so callers building incrementally still
        # get protection.
        validate_assignment=True,
    )

    # ---- versioning --------------------------------------------------

    contract_version: Literal["envelope.v1"] = ENVELOPE_VERSION

    # ---- always-required-in-some-mode core fields --------------------
    # NOTE: the dispatcher decides per-mode whether these are required.
    # The contract itself keeps them Optional so legacy dicts that omit
    # one because they failed earlier (e.g. partial responses) can still
    # be coerced and inspected.

    status: Optional[str] = None
    tarea: Optional[str] = None
    archivos: Optional[List[str]] = None
    engram: Optional[str] = None
    verificacion: Optional[str] = None

    # ---- core optional ----------------------------------------------

    servidor: Optional[str] = None
    bloqueadores: Optional[List[str]] = Field(default=None)
    notas: Optional[str] = ""

    # ---- agent identification (1L.3 PENDING-1L3-2 prepares ground) ---
    # NOT enforced as required anywhere yet; F1.1 only formalises the
    # field name so future blocks can rely on it without a schema bump.

    agent: Optional[str] = None

    # ---- audit fields used by dev_strict (1A.14 / 1A.15 / 1A.16) -----

    pre_return_audit: Optional[Dict[str, Any]] = None

    # ---- design_strict fields (1C.1 / 1L.2 / 1L.3 / 1L.4) ------------

    design_intelligence: Optional[Dict[str, Any]] = None
    brand: Optional[Dict[str, Any]] = None
    brand_style: Optional[str] = None
    references: Optional[List[Dict[str, Any]]] = None
    references_used: Optional[List[str]] = None
    editorial_compliance: Optional[Dict[str, Any]] = None

    # ---- dispatcher annotations (set BY the dispatcher, not the agent) ----

    _dispatcher_warnings: Optional[List[str]] = None
    _dispatcher_enforcement: Optional[Dict[str, Any]] = None

    # ===== helpers ====================================================

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Serialise to a dict shaped exactly like the legacy envelope.

        - mode="json" so enum values become strings (use_enum_values=True
          already does this on validation, but model_dump's mode flag
          covers any datetime / UUID future fields without surprises)
        - exclude_none=True so optional fields that were never set don't
          leak as null into a legacy consumer that doesn't expect them

        Extra fields preserved via `extra="allow"` ARE included in the
        output (Pydantic 2 puts them in `model_extra`).
        """
        base = self.model_dump(mode="json", exclude_none=True)
        # Pydantic 2: extra fields land in `__pydantic_extra__` and are
        # included in model_dump by default. Belt-and-suspenders check:
        extras = getattr(self, "__pydantic_extra__", None) or {}
        for k, v in extras.items():
            if k not in base and v is not None:
                base[k] = v
        return base
