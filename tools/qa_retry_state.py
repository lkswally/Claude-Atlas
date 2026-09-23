#!/usr/bin/env python3
"""
QA Retry State (Architecture Repair 03)
=========================================

Mechanical enforcement for the documented dev<->QA retry ceiling.

Canonical semantics (resolved from evidence, not assumed — see
docs/ARCHITECTURE-REALITY-AUDIT-V1.md P1-3 remediation note for the full
citation trail):

- Source of truth for the contract: .claude/agents/refs/orchestrator-pipeline-phase-3.md
  ("El orquestador mantiene el contador de intentos en DAG State en
  tareas[N].qa_intento_actual, incrementandolo SOLO en fallos funcionales
  de QA, NO en fallos de Engram" / "evidence-collector ha fallado 3 veces").
- MAX_ATTEMPTS = 3 TOTAL attempts per task_id (not 3 retries after an
  initial attempt = 4 total). evidence-collector.md's own self-guard says
  "Si el intento es > 3, RECHAZAR" -- attempts 1, 2, 3 proceed; a 4th does not.
- The counter increments ONLY on a genuine functional QA failure
  ("fail") for that task_id. A "pass" ends the loop (state cleared). A
  non-functional issue (e.g. Engram unreachable) must NOT increment --
  callers pass status="infra_error" for that case, which is a no-op here.
- Scope is per-task_id, persisted to disk (NOT session/process-local):
  process restart, a resumed session, or the same task being rephrased in
  a new message must NOT reset the counter. Only a genuine PASS, a
  genuinely different task_id, or an explicit call to reset() may reset it.

ALCANCE HONESTO (matching the pattern already established by
file_hash_cache.py's own docstring):
- This module provides correct, deterministic COUNTING and LIMIT-CHECK
  logic once invoked. It does not, and cannot from this layer, force the
  orchestrator LLM to invoke it at the right moment in a live Claude Code
  session -- there is no PreToolUse-style interception point for Task/
  Agent delegation calls in this architecture. Invocation is contractual
  (the agent contracts are updated to call this instead of self-counting
  from free text); the counting and the 3-attempt ceiling itself, once
  called, are mechanically correct and cannot be miscounted by an LLM
  losing track of a number in a long conversation.
- This is a DIFFERENT mechanism from FileHashCache (.pipeline/qa-cache.json,
  Bloque 1F.1) -- that one caches PASS results to skip redundant QA runs.
  This one counts FAIL attempts toward an escalation ceiling. They share
  the same task_id key and the same persistence pattern (atomic write to
  .pipeline/) by design, but are intentionally separate files/classes --
  conflating them was avoided per Architecture Repair 03's own mandate not
  to mix retry mechanisms.
- Distinct from tools/atlas_dispatcher.py's phase_gate_retries (Fase-gate
  cajon waits, cap 2) and from the boot-sequence "intento_actual" counter
  in orchestrator-routing.md/boot_sequence_helper.py (session boot-mode
  light-vs-full selection). Same word "intento"/"attempt" is used for all
  three in the docs; they are three separate mechanisms with separate
  state, separate owners, and separate limits. This module implements
  only the dev<->QA one.

Persistencia:
- {project_root}/.pipeline/qa-retry-state.json
- Atomic write (tmpfile + os.replace), same technique as file_hash_cache.py
- Cross-process advisory lock around the read-modify-write increment
  (msvcrt on Windows, fcntl on POSIX/Linux -- stdlib only, no new
  dependency) -- the dev<->QA loop is sequential by architecture (one
  task at a time through Fase 3), so concurrent increments for the same
  task_id are not an expected normal case, but the lock removes the
  possibility of a lost-update race rather than assuming it away.

Failure semantics (correctness-sensitive -- deliberately NOT fail-open):
- If the state file cannot be reliably read or written, record_qa_attempt
  and check_qa_retry_limit return retry_limit_reached=True with
  state_error set, rather than silently permitting unlimited retries.
  A telemetry write failing open is acceptable (Architecture Repair 02);
  a retry-ceiling check failing open is not -- it would defeat the whole
  point of this repair. See ARCHITECTURE-REALITY-AUDIT-V1.md P1-3.
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

STATE_VERSION = 1
DEFAULT_MAX_ATTEMPTS = 3
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_INTERVAL = 0.02

DEFAULT_STATE: Dict[str, Any] = {
    "version": STATE_VERSION,
    "tasks": {},  # {task_id: {attempt_count, last_failure_reason, last_agent, updated_at}}
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Cross-process lock (self-contained -- deliberately not shared with
# core/capabilities/events.py to keep this repair's diff isolated to only
# what P1-3 needs; same proven technique, independent implementation).
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    @contextlib.contextmanager
    def _cross_process_lock(fh, timeout: float = _LOCK_TIMEOUT_SECONDS):
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
                        raise TimeoutError("qa-retry-state.json: lock acquisition timed out")
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
                        raise TimeoutError("qa-retry-state.json: lock acquisition timed out")
                    time.sleep(_LOCK_POLL_INTERVAL)
            yield
        finally:
            if locked:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


class QARetryState:
    """Per-task_id dev<->QA attempt counter, disk-persisted, fail-closed."""

    def __init__(self, project_root: Path, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self.project_root = Path(project_root)
        self.state_dir = self.project_root / ".pipeline"
        self.state_path = self.state_dir / "qa-retry-state.json"
        self.max_attempts = max_attempts

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_locked(self, fh) -> Dict[str, Any]:
        fh.seek(0)
        content = fh.read()
        if not content.strip():
            return copy.deepcopy(DEFAULT_STATE)
        state = json.loads(content)
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
            return copy.deepcopy(DEFAULT_STATE)
        merged = copy.deepcopy(DEFAULT_STATE)
        merged.update(state)
        if "tasks" not in state or not isinstance(state["tasks"], dict):
            merged["tasks"] = {}
        return merged

    @contextlib.contextmanager
    def _locked_state(self):
        """Open+lock the state file for a read-modify-write critical
        section, ensuring the file exists first so there's always a valid
        fd to lock. Yields the loaded state; caller mutates it in place
        and this context manager writes it back to the SAME open,
        locked handle on clean exit.

        Deliberately does NOT use the tempfile+os.replace atomic-write
        technique here (unlike file_hash_cache.py / core/capabilities/
        events.py's own writes): this method already holds an exclusive
        lock on state_path for the whole critical section, and on Windows
        os.replace() onto a path that is itself still open in the same
        process raises PermissionError (WinError 5) -- found by direct
        testing, not assumed. Writing to the already-locked handle avoids
        that conflict entirely while keeping the same correctness
        guarantee: every other reader/writer goes through the same lock,
        so no one can observe a state file mid-write."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self.state_path.write_text(json.dumps(DEFAULT_STATE, indent=2), encoding="utf-8")
        with self.state_path.open("r+", encoding="utf-8") as fh:
            with _cross_process_lock(fh):
                state = self._load_locked(fh)
                yield state
                fh.seek(0)
                json.dump(state, fh, indent=2)
                fh.flush()
                fh.truncate()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def record_qa_attempt(
        self,
        task_id: str,
        status: str,
        reason: str = "",
        agent: str = "",
    ) -> Dict[str, Any]:
        """
        Record the outcome of one dev<->QA cycle for task_id.

        status:
          "fail"        -> genuine functional QA failure. Increments the
                            counter (this is the ONLY status that does).
          "pass"        -> QA passed. Clears the entry for task_id (loop done).
          "infra_error" -> non-functional issue (Engram unreachable, etc.).
                            Does NOT increment, per canonical semantics.

        Returns:
          {task_id, attempt_count, max_attempts, retry_limit_reached,
           last_failure_reason, last_agent, updated_at}
          On unrecoverable state I/O failure: the same shape with
          state_error=True and retry_limit_reached=True (fail CLOSED --
          see module docstring; a broken counter must not silently permit
          unlimited retries).
        """
        try:
            with self._locked_state() as state:
                tasks = state.setdefault("tasks", {})
                entry = tasks.setdefault(task_id, {
                    "attempt_count": 0,
                    "last_failure_reason": None,
                    "last_agent": None,
                    "updated_at": None,
                })
                if status == "pass":
                    tasks.pop(task_id, None)
                    return {
                        "task_id": task_id,
                        "attempt_count": 0,
                        "max_attempts": self.max_attempts,
                        "retry_limit_reached": False,
                        "last_failure_reason": None,
                        "last_agent": None,
                        "updated_at": _now_iso(),
                        "cleared": True,
                    }
                if status == "fail":
                    entry["attempt_count"] = int(entry.get("attempt_count", 0)) + 1
                    entry["last_failure_reason"] = reason or None
                    entry["last_agent"] = agent or None
                    entry["updated_at"] = _now_iso()
                # status == "infra_error" (or anything else unrecognized):
                # no increment, just touch updated_at for observability.
                elif status != "pass":
                    entry["updated_at"] = _now_iso()

                attempt_count = int(entry.get("attempt_count", 0))
                return {
                    "task_id": task_id,
                    "attempt_count": attempt_count,
                    "max_attempts": self.max_attempts,
                    "retry_limit_reached": attempt_count >= self.max_attempts,
                    "last_failure_reason": entry.get("last_failure_reason"),
                    "last_agent": entry.get("last_agent"),
                    "updated_at": entry.get("updated_at"),
                    "cleared": False,
                }
        except Exception as e:
            # Fail CLOSED: a broken counter must block, not permit.
            return {
                "task_id": task_id,
                "attempt_count": self.max_attempts,
                "max_attempts": self.max_attempts,
                "retry_limit_reached": True,
                "last_failure_reason": reason or None,
                "last_agent": agent or None,
                "updated_at": _now_iso(),
                "cleared": False,
                "state_error": f"{type(e).__name__}: {e}",
            }

    def check_qa_retry_limit(self, task_id: str) -> Dict[str, Any]:
        """
        Read-only check: has task_id already reached/exceeded max_attempts?
        Does not mutate state. Same fail-closed contract as record_qa_attempt.
        """
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            if not self.state_path.exists():
                return {
                    "task_id": task_id, "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "retry_limit_reached": False,
                    "last_failure_reason": None, "last_agent": None,
                    "updated_at": None,
                }
            with self.state_path.open("r", encoding="utf-8") as fh:
                with _cross_process_lock(fh):
                    state = self._load_locked(fh)
            entry = state.get("tasks", {}).get(task_id)
            if not entry:
                return {
                    "task_id": task_id, "attempt_count": 0,
                    "max_attempts": self.max_attempts,
                    "retry_limit_reached": False,
                    "last_failure_reason": None, "last_agent": None,
                    "updated_at": None,
                }
            attempt_count = int(entry.get("attempt_count", 0))
            return {
                "task_id": task_id,
                "attempt_count": attempt_count,
                "max_attempts": self.max_attempts,
                "retry_limit_reached": attempt_count >= self.max_attempts,
                "last_failure_reason": entry.get("last_failure_reason"),
                "last_agent": entry.get("last_agent"),
                "updated_at": entry.get("updated_at"),
            }
        except Exception as e:
            return {
                "task_id": task_id,
                "attempt_count": self.max_attempts,
                "max_attempts": self.max_attempts,
                "retry_limit_reached": True,
                "last_failure_reason": None,
                "last_agent": None,
                "updated_at": _now_iso(),
                "state_error": f"{type(e).__name__}: {e}",
            }

    def reset(self, task_id: str) -> bool:
        """
        Explicit reset for task_id. NOT called automatically anywhere
        except record_qa_attempt(status="pass"). This is the closest thing
        to a human-override lever this module provides: it exists to be
        invoked deliberately (e.g. by the orchestrator after explicit user
        direction to retry a task past the ceiling), never automatically
        upon reaching the limit. Returns True if an entry was removed.
        """
        try:
            with self._locked_state() as state:
                tasks = state.setdefault("tasks", {})
                existed = task_id in tasks
                tasks.pop(task_id, None)
                return existed
        except Exception:
            return False

    def stats(self) -> Dict[str, Any]:
        """Debugging/observability helper."""
        try:
            if not self.state_path.exists():
                return {"total_tasks": 0, "state_path": str(self.state_path)}
            with self.state_path.open("r", encoding="utf-8") as fh:
                with _cross_process_lock(fh):
                    state = self._load_locked(fh)
            tasks = state.get("tasks", {})
            return {
                "total_tasks": len(tasks),
                "state_path": str(self.state_path),
                "task_ids": sorted(tasks.keys()),
            }
        except Exception as e:
            return {"error": str(e)}
