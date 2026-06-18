"""
ATLAS Capability Events — F18
==============================

Event model and JSONL logger for capability resolution observability.

Each call to resolve_capability() optionally emits a CapabilityEvent to
.pipeline/capability-events.jsonl (append-only, one JSON object per line).

Disable: ATLAS_CAPABILITY_EVENTS_DISABLED=1
"""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_EVENTS_FILE = _PROJECT_ROOT / ".pipeline" / "capability-events.jsonl"

# Thread-safe write lock
_write_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

@dataclass
class CapabilityEvent:
    """
    Immutable record of a single capability resolution attempt.

    Fields:
      timestamp        ISO-8601 UTC
      capability       Name requested (e.g. "browser")
      requested_by     Free-text caller hint (agent name, module, "unknown")
      provider_selected mcp_id of the chosen provider, or None
      provider_status  LIVE | CONFIG_ONLY | PENDING_TOKEN | DEFERRED_PAID | UNAVAILABLE
      fallback_used    True if primary was not LIVE and fallback was returned
      resolution_ok    True if result is immediately usable (LIVE or CONFIG_ONLY)
      action           Hint from router: "use" | "restart_session" | "set_token" | ...
      reason           Human-readable summary of why this resolution happened
      metadata         Arbitrary extra dict (tool_prefix, notes, etc.)
    """
    timestamp: str
    capability: str
    requested_by: str
    provider_selected: str | None
    provider_status: str
    fallback_used: bool
    resolution_ok: bool
    action: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def make_event(
    capability: str,
    provider_selected: str | None,
    provider_status: str,
    fallback_used: bool,
    action: str,
    requested_by: str = "unknown",
    reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> CapabilityEvent:
    """Build a CapabilityEvent from resolution results."""
    return CapabilityEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        capability=capability,
        requested_by=requested_by,
        provider_selected=provider_selected,
        provider_status=provider_status,
        fallback_used=fallback_used,
        resolution_ok=provider_status in ("LIVE", "CONFIG_ONLY"),
        action=action,
        reason=reason or _default_reason(capability, provider_status, fallback_used),
        metadata=metadata or {},
    )


def _default_reason(capability: str, status: str, fallback_used: bool) -> str:
    reasons = {
        "LIVE":          f"{capability} resolved to LIVE provider",
        "CONFIG_ONLY":   f"{capability} provider configured but needs session restart",
        "PENDING_TOKEN": f"{capability} provider needs token/secret to activate",
        "DEFERRED_PAID": f"{capability} provider requires paid license",
        "UNAVAILABLE":   f"{capability} has no registered provider",
    }
    base = reasons.get(status, f"{capability} → {status}")
    if fallback_used:
        base += " (fallback active)"
    return base


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

def _is_disabled() -> bool:
    return os.environ.get("ATLAS_CAPABILITY_EVENTS_DISABLED") == "1"


def emit(event: CapabilityEvent, events_file: Path | None = None) -> bool:
    """
    Append event to JSONL log. Returns True on success, False on any error.
    Never raises — fail-open by design.
    """
    if _is_disabled():
        return False

    target = events_file or _EVENTS_FILE

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = event.to_jsonl() + "\n"
        with _write_lock:
            with target.open("a", encoding="utf-8") as f:
                f.write(line)
        return True
    except Exception:
        return False


def emit_resolution(
    capability: str,
    provider_selected: str | None,
    provider_status: str,
    fallback_used: bool,
    action: str,
    requested_by: str = "unknown",
    reason: str = "",
    metadata: dict[str, Any] | None = None,
    events_file: Path | None = None,
) -> bool:
    """Convenience: build + emit in one call."""
    evt = make_event(
        capability=capability,
        provider_selected=provider_selected,
        provider_status=provider_status,
        fallback_used=fallback_used,
        action=action,
        requested_by=requested_by,
        reason=reason,
        metadata=metadata,
    )
    return emit(evt, events_file=events_file)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def read_events(events_file: Path | None = None) -> list[CapabilityEvent]:
    """
    Read all events from JSONL file. Returns [] if file doesn't exist or is empty.
    Skips malformed lines silently.
    """
    target = events_file or _EVENTS_FILE
    if not target.exists():
        return []

    events: list[CapabilityEvent] = []
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                events.append(CapabilityEvent(**d))
            except Exception:
                pass
    except Exception:
        pass
    return events


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    evts = read_events()
    print(f"Events in {_EVENTS_FILE}: {len(evts)}")
    for e in evts[-10:]:
        print(f"  {e.timestamp[:19]}  {e.capability:<20} {e.provider_status:<16} provider={e.provider_selected or '—'}")
