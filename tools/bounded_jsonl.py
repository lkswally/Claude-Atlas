#!/usr/bin/env python3
"""
Bounded JSONL log (ATLAS telemetry retention, roadmap P2)
=========================================================

Append-only JSONL with a hard size bound, cross-process-safe appends, and
newest-first reads that never deserialize the whole history.

WHY (measured, not assumed)
---------------------------
* .pipeline/invocation-log.jsonl had grown to 34.65 MB / 186,111 lines and was
  fully re-read by every audit; on the HDD volume a cold read took 1.5 s idle
  and ~23 s while a Defender full scan was running.
* The same unlocked append left 165 torn lines in invocation-log.jsonl and 472
  in skills-registry-usage.jsonl, while the locked capability-events.jsonl has
  0 (core/capabilities/events.py documents the Windows multi-process cause).
  So appends are locked here too, not only rotation.
* Timestamps in those logs are not strictly ordered (max backward skew
  observed: 77 s), so time-window reads tolerate skew instead of stopping at
  the first old entry.

DESIGN
------
    <name>.jsonl         current segment (readers/writers' canonical path)
    <name>.1.jsonl       previous segment (the only archive kept)
    <name>.lock          advisory lock file (msvcrt on Windows, fcntl on POSIX)
    <name>.legacy-*.jsonl  one-time migration copy of an oversized legacy log

* Retention is bounded: current + one archive, each <= max_bytes (+ one line).
  Events older than the archive are discarded BY DESIGN; nothing here claims
  otherwise. Oversized legacy logs are never deleted: the newest max_bytes are
  kept as the archive and the full original is renamed to *.legacy-*.jsonl
  (never read by code; the operator decides when to delete it).
* Append and rotation happen under one lock; rotation is a single atomic
  os.replace, so a crash leaves either the old or the new state, never a
  partial one (an oversized current file simply rotates again next append).
* Readers take the lock only to open both segments (a consistent pair), then
  read lazily newest-first from the open handles.
* Failure policy is fail-open for the caller (telemetry must not break the
  work) but visible: append() returns an AppendResult, rotation failures are
  reported in the result, on stderr (once per path per process) and in
  status(), and rotation retries are throttled.

NOT A DATABASE. If queries beyond "last N" / "recent window" are needed, that
is a different tool.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

__all__ = ["BoundedJsonl", "AppendResult", "DEFAULT_MAX_BYTES"]

DEFAULT_MAX_BYTES = 2_000_000          # per segment; ~10k invocation-log entries
LEGACY_FACTOR = 4                      # current > 4 x max_bytes => legacy migration path
LOCK_TIMEOUT_SECONDS = 5.0             # same bound as core/capabilities/events.py
READ_LOCK_TIMEOUT_SECONDS = 2.0
LOCK_POLL_INTERVAL = 0.02
ROTATION_RETRY_BACKOFF_SECONDS = 30.0
READ_SLACK_SECONDS = 120.0             # > 77 s max backward skew observed
READ_CONSECUTIVE_OLD_STOP = 100        # stop only after this many consecutive too-old entries
_BLOCK = 64 * 1024

_WARNED: set = set()


def _warn_once(key: str, message: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


# ------------------------------------------------------------------ locking
if sys.platform == "win32":
    import msvcrt

    def _try_lock(fh) -> None:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(fh) -> None:
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _file_lock(lock_path: Path, timeout: float):
    """Advisory whole-file lock on a dedicated lock file (nominal byte 0).
    Released by the OS on handle close, including on crash."""
    deadline = time.monotonic() + timeout
    fh = None
    locked = False
    try:
        fh = open(lock_path, "a+b")
        while True:
            try:
                fh.seek(0)
                _try_lock(fh)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"could not acquire lock {lock_path.name} in {timeout}s")
                time.sleep(LOCK_POLL_INTERVAL)
        yield
    finally:
        if locked:
            try:
                fh.seek(0)
                _unlock(fh)
            except OSError:
                pass
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass


_THREAD_LOCKS: Dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(lock_path: Path) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(str(lock_path)))
    with _THREAD_LOCKS_GUARD:
        lk = _THREAD_LOCKS.get(key)
        if lk is None:
            lk = _THREAD_LOCKS[key] = threading.Lock()
        return lk


# ------------------------------------------------------------------ helpers
def _parse_ts(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _reverse_lines(fh) -> Iterator[bytes]:
    """Yield non-empty lines of an open binary file, last line first, reading
    64 KiB blocks from the end (never the whole file unless asked to)."""
    fh.seek(0, os.SEEK_END)
    pos = fh.tell()
    carry = b""
    while pos > 0:
        n = min(_BLOCK, pos)
        pos -= n
        fh.seek(pos)
        buf = fh.read(n) + carry
        parts = buf.split(b"\n")
        carry = parts[0]                       # may be a partial line; completed next block
        for line in reversed(parts[1:]):
            line = line.strip()
            if line:
                yield line
    carry = carry.strip()
    if carry:
        yield carry


@dataclass
class AppendResult:
    ok: bool
    rotated: bool = False
    error: Optional[str] = None            # append failed (entry NOT stored)
    rotation_error: Optional[str] = None   # entry stored, rotation did not happen


class BoundedJsonl:
    def __init__(self, path, max_bytes: int = DEFAULT_MAX_BYTES, create_parent: bool = True):
        """create_parent=False keeps a writer that never created directories (e.g. an
        env-override log path) from creating them now: append() then fails open instead."""
        self.path = Path(path)
        self.create_parent = create_parent
        self.max_bytes = max(1, int(max_bytes))
        self.segment_path = self.path.with_name(f"{self.path.stem}.1{self.path.suffix}")
        self.lock_path = self.path.with_name(f"{self.path.stem}.lock")
        self.last_rotation_error: Optional[str] = None
        self._rotation_blocked_until = 0.0

    # ------------------------------------------------------------ locking
    @contextlib.contextmanager
    def _exclusive(self, timeout: float):
        tl = _thread_lock_for(self.lock_path)
        if not tl.acquire(timeout=timeout):
            raise TimeoutError("in-process lock timeout")
        try:
            with _file_lock(self.lock_path, timeout):
                yield
        finally:
            tl.release()

    # ------------------------------------------------------------ write
    def append(self, entry: Any) -> AppendResult:
        try:
            if isinstance(entry, (bytes, bytearray)):
                payload = bytes(entry)
            elif isinstance(entry, str):
                payload = entry.encode("utf-8")
            else:
                payload = json.dumps(entry, ensure_ascii=False).encode("utf-8")
            if not payload.endswith(b"\n"):
                payload += b"\n"
        except (TypeError, ValueError) as e:
            return AppendResult(False, error=f"{type(e).__name__}: {e}")
        try:
            if self.create_parent:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._exclusive(LOCK_TIMEOUT_SECONDS):
                with open(self.path, "ab") as f:
                    f.write(payload)
                    f.flush()
                    size = os.fstat(f.fileno()).st_size
                if size >= self.max_bytes:
                    rotated, rot_err = self._rotate_locked()
                    return AppendResult(True, rotated, None, rot_err)
                return AppendResult(True)
        except (OSError, TimeoutError) as e:
            return AppendResult(False, error=f"{type(e).__name__}: {e}")

    def _rotate_locked(self):
        now = time.monotonic()
        if now < self._rotation_blocked_until:
            return False, self.last_rotation_error
        try:
            size = self.path.stat().st_size
            self._cleanup_stale_tmp()
            if size > LEGACY_FACTOR * self.max_bytes:
                self._rotate_legacy_locked()
            else:
                os.replace(self.path, self.segment_path)
            self.last_rotation_error = None
            return True, None
        except OSError as e:
            msg = f"{type(e).__name__}: {e}"
            self.last_rotation_error = msg
            self._rotation_blocked_until = now + ROTATION_RETRY_BACKOFF_SECONDS
            _warn_once(f"rot:{self.path}", f"[bounded_jsonl] rotation failed for {self.path.name}: {msg}")
            return False, msg

    def _rotate_legacy_locked(self) -> None:
        """Current file is far over the bound (pre-retention log): keep its newest
        max_bytes as the archive, rename the full original to *.legacy-*.jsonl."""
        tail = self._read_tail_bytes(self.path, self.max_bytes)
        tmp = self.segment_path.with_name(f"{self.segment_path.name}.tmp{os.getpid()}")
        try:
            with open(tmp, "wb") as f:
                f.write(tail)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.segment_path)
        finally:
            with contextlib.suppress(OSError):
                tmp.unlink()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        legacy = self.path.with_name(f"{self.path.stem}.legacy-{stamp}{self.path.suffix}")
        n = 0
        while legacy.exists():
            n += 1
            legacy = self.path.with_name(f"{self.path.stem}.legacy-{stamp}-{n}{self.path.suffix}")
        os.replace(self.path, legacy)

    @staticmethod
    def _read_tail_bytes(path: Path, n: int) -> bytes:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            start = max(0, size - n)
            f.seek(start)
            data = f.read()
        if start > 0:                                   # drop the (likely partial) first line
            nl = data.find(b"\n")
            data = data[nl + 1:] if nl != -1 else b""
        return data

    def _cleanup_stale_tmp(self) -> None:
        # Safe: only the lock holder rotates, so no live rotator owns a tmp file.
        for p in self.segment_path.parent.glob(f"{self.segment_path.name}.tmp*"):
            with contextlib.suppress(OSError):
                p.unlink()

    # ------------------------------------------------------------ read
    def _open_pair(self) -> List[Optional[Any]]:
        handles: List[Optional[Any]] = []
        for p in (self.path, self.segment_path):        # newest first
            try:
                handles.append(open(p, "rb"))
            except OSError:
                handles.append(None)
        return handles

    def _snapshot_handles(self) -> List[Optional[Any]]:
        try:
            with self._exclusive(READ_LOCK_TIMEOUT_SECONDS):
                return self._open_pair()
        except (TimeoutError, OSError):
            return self._open_pair()                    # best effort without the lock

    def exists(self) -> bool:
        return self.path.exists() or self.segment_path.exists()

    def iter_lines_reverse(self) -> Iterator[bytes]:
        handles = self._snapshot_handles()
        try:
            for fh in handles:
                if fh is not None:
                    yield from _reverse_lines(fh)
        finally:
            for fh in handles:
                if fh is not None:
                    with contextlib.suppress(OSError):
                        fh.close()

    def iter_lines_forward(self) -> Iterator[str]:
        handles = self._snapshot_handles()
        try:
            for fh in reversed(handles):                # archive (older) first, then current
                if fh is None:
                    continue
                fh.seek(0)
                for raw in fh:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        yield line
        finally:
            for fh in handles:
                if fh is not None:
                    with contextlib.suppress(OSError):
                        fh.close()

    def iter_entries_reverse(self) -> Iterator[Dict[str, Any]]:
        for raw in self.iter_lines_reverse():
            try:
                obj = json.loads(raw)
            except ValueError:
                continue                                # torn / malformed line: skipped
            if isinstance(obj, dict):
                yield obj

    def tail_entries(self, max_lines: int = 10000) -> List[Dict[str, Any]]:
        """Newest `max_lines` raw lines parsed, returned oldest -> newest."""
        out: List[Dict[str, Any]] = []
        seen = 0
        for raw in self.iter_lines_reverse():
            seen += 1
            try:
                obj = json.loads(raw)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                out.append(obj)
            if seen >= max_lines:
                break
        out.reverse()
        return out

    def recent_entries(self, cutoff: datetime, ts_key: str = "timestamp",
                       slack_seconds: float = READ_SLACK_SECONDS) -> List[Dict[str, Any]]:
        """Entries with ts >= cutoff, oldest -> newest. Newest-first scan; stops after
        READ_CONSECUTIVE_OLD_STOP consecutive entries older than cutoff - slack, so a
        few out-of-order entries cannot truncate the window."""
        cutoff_ts = cutoff.timestamp()
        out: List[Dict[str, Any]] = []
        old_run = 0
        for obj in self.iter_entries_reverse():
            ts = _parse_ts(obj.get(ts_key))
            if ts is None:
                continue
            if ts >= cutoff_ts:
                out.append(obj)
                old_run = 0
            elif ts < cutoff_ts - slack_seconds:
                old_run += 1
                if old_run >= READ_CONSECUTIVE_OLD_STOP:
                    break
            else:
                old_run = 0
        out.reverse()
        return out

    # ------------------------------------------------------------ admin
    def status(self) -> Dict[str, Any]:
        def size(p: Path) -> Optional[int]:
            try:
                return p.stat().st_size
            except OSError:
                return None
        cur, seg = size(self.path), size(self.segment_path)
        legacy = sorted(p.name for p in self.path.parent.glob(f"{self.path.stem}.legacy-*{self.path.suffix}")) \
            if self.path.parent.exists() else []
        return {
            "path": str(self.path),
            "max_bytes": self.max_bytes,
            "current_bytes": cur,
            "segment_bytes": seg,
            "legacy_files": legacy,
            "over_bound": bool(cur is not None and cur > 2 * self.max_bytes),   # rotation is failing
            "last_rotation_error": self.last_rotation_error,
        }

    def clear(self) -> None:
        """Remove current + archive (tests / explicit reset). Legacy files are never touched."""
        for p in (self.path, self.segment_path):
            with contextlib.suppress(OSError):
                p.unlink()
