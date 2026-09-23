"""
ATLAS Capability Events — F18
==============================

Event model and JSONL logger for capability resolution observability.

Each call to resolve_capability() optionally emits a CapabilityEvent to
.pipeline/capability-events.jsonl (append-only, one JSON object per line).

Disable: ATLAS_CAPABILITY_EVENTS_DISABLED=1
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_EVENTS_FILE = _PROJECT_ROOT / ".pipeline" / "capability-events.jsonl"

# Thread-safe write lock — protects concurrent writers *within one process*.
# Does NOT protect across separate OS processes (each process gets its own
# instance of this lock). See _locked_append() below for the cross-process
# guard, which is the actual gap Architecture Repair 02 fixes.
_write_lock = threading.Lock()

# Architecture Repair 02: cross-process append lock.
#
# Root cause (CONFIRMED by reproduction, not assumed): emit() already built
# each record as a single string (json + "\n") and issued a single
# f.write() call — correct in isolation, but that alone does not guarantee
# the OS treats it as one atomic append when multiple separate *processes*
# (not threads — ATLAS spawns a fresh short-lived Python/Node process per
# tool/hook invocation) append to the same file at nearly the same instant.
# POSIX O_APPEND gives that atomicity guarantee under certain conditions;
# Windows — the platform this ships on — does not. Reproduced directly:
# spawning >=5 real concurrent OS processes against the real production
# emit() writer, targeting a disposable file, produced the exact same
# corruption signature already present in .pipeline/capability-events.jsonl
# (a line starting mid-object, missing its opening "{", because another
# process's write landed in between two writes of the same record).
#
# Fix: wrap the single write in a short-lived, stdlib-only, cross-platform
# advisory file lock (msvcrt on Windows, fcntl on POSIX/Linux — covers both
# this dev machine and the Linux CI runner, zero new dependencies). Bounded
# by a timeout so a stalled/crashed holder can't hang other writers
# forever; on timeout the write is skipped and emit() returns False,
# preserving the existing fail-open, non-blocking telemetry contract.
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_INTERVAL = 0.02

if sys.platform == "win32":
    import msvcrt

    @contextlib.contextmanager
    def _cross_process_lock(fh, timeout: float = _LOCK_TIMEOUT_SECONDS):
        """Advisory, whole-file lock via msvcrt (Windows). Blocks other
        processes/threads that also go through this same context manager
        on the same file; released automatically on close (including on
        crash — the OS releases file locks when the handle is closed)."""
        deadline = time.monotonic() + timeout
        locked = False
        try:
            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "capability-events.jsonl: could not acquire "
                            "cross-process write lock in time"
                        )
                    time.sleep(_LOCK_POLL_INTERVAL)
            yield
        finally:
            if locked:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
else:
    import fcntl

    @contextlib.contextmanager
    def _cross_process_lock(fh, timeout: float = _LOCK_TIMEOUT_SECONDS):
        """Advisory, whole-file lock via fcntl.flock (POSIX/Linux)."""
        deadline = time.monotonic() + timeout
        locked = False
        try:
            while True:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "capability-events.jsonl: could not acquire "
                            "cross-process write lock in time"
                        )
                    time.sleep(_LOCK_POLL_INTERVAL)
            yield
        finally:
            if locked:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


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
    Append event to JSONL log. Returns True on success, False on any error
    (including a lock-acquisition timeout under heavy concurrent write
    load). Never raises — fail-open by design; a skipped telemetry write
    never blocks or breaks the caller's actual capability resolution.
    """
    if _is_disabled():
        return False

    target = events_file or _EVENTS_FILE

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = event.to_jsonl() + "\n"
        with _write_lock:  # in-process: cheap, avoids the OS lock when possible
            with target.open("a", encoding="utf-8") as f:
                # Nominal byte-0 lock region: every writer (this process and
                # every other) locks/unlocks the same 1-byte region as a
                # pure mutex over the file, independent of where the actual
                # append lands. Position is managed explicitly rather than
                # relying on "a" mode's default seek behavior.
                f.seek(0)
                with _cross_process_lock(f):
                    f.seek(0, os.SEEK_END)
                    f.write(line)
                    f.flush()
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

def read_events(events_file: Path | None = None, tail: int | None = None) -> list[CapabilityEvent]:
    """
    Read events from JSONL file. Returns [] if file doesn't exist or is empty.
    Skips malformed lines silently.

    tail: if set, read only the last N lines (avoids loading the full file for tests).
    """
    target = events_file or _EVENTS_FILE
    if not target.exists():
        return []

    events: list[CapabilityEvent] = []
    try:
        if tail is not None:
            # Read last N lines without loading the entire file into memory
            from collections import deque
            with open(target, encoding="utf-8", errors="replace") as fh:
                lines_to_parse = list(deque(fh, maxlen=tail))
        else:
            with open(target, encoding="utf-8", errors="replace") as fh:
                lines_to_parse = fh.readlines()
        for line in lines_to_parse:
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
