"""
ATLAS Boot Profiler — F29
==========================

Lightweight, metadata-only profiler for knowledge-load events during boot and
runtime. The goal (F28 → F29) is to MEASURE before refactoring: which knowledge
files get read, when, why, how big, and whether they were already loaded this
session — so the boot-loader redesign (future F30/F31) is driven by data, not
guesses.

DESIGN PRINCIPLES (mirrors core/capabilities/events.py):
  - Metadata only. NEVER records file content. Only path + size + reason.
  - Append-only JSONL, one event per line.
  - Fail-open: emit() never raises; on any error it returns False.
  - Disable: ATLAS_BOOT_PROFILER_DISABLED=1 → emit() is a no-op.
  - Thread-safe writes.

LOG LOCATION:
  .claude/logs/boot-profile.jsonl  (gitignored — runtime log, not versioned)

EVENT SHAPE (see KnowledgeLoadEvent):
  {
    "event": "knowledge_load",
    "timestamp": "2026-06-19T...Z",
    "path": "CLAUDE.md",
    "source": "boot|agent|capability|manual|test",
    "reason": "startup|orchestrator|qa|docs|memory|unknown",
    "bytes": 12345,
    "lines": 123,
    "estimated_tokens": 3086,
    "load_type": "always_on|lazy|manual",
    "session_id": "abc123",
    "dedup_key": "CLAUDE.md",
    "duration_ms": 1.2,
    "already_loaded": false
  }

CLI:
  python tools/boot_profiler.py summary          # aggregate the current log
  python tools/boot_profiler.py summary --json   # machine-readable
  python tools/boot_profiler.py tail [N]         # last N events
"""

from __future__ import annotations

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
# Paths / constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
_LOG_FILE = _PROJECT_ROOT / ".claude" / "logs" / "boot-profile.jsonl"

# Heuristic: ~4 chars per token (matches F28 audit methodology).
_CHARS_PER_TOKEN = 4

VALID_SOURCES = {"boot", "agent", "capability", "manual", "test"}
VALID_REASONS = {"startup", "orchestrator", "qa", "docs", "memory", "unknown"}
VALID_LOAD_TYPES = {"always_on", "lazy", "manual"}

_write_lock = threading.Lock()

# In-process dedup set: tracks dedup_keys already seen this session so the
# profiler can report already_loaded without re-reading the whole log.
_seen_keys: set[str] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_disabled() -> bool:
    return os.environ.get("ATLAS_BOOT_PROFILER_DISABLED") == "1"


def estimate_tokens(num_chars: int) -> int:
    """Estimate tokens from a character count (chars / 4, floor)."""
    if num_chars <= 0:
        return 0
    return num_chars // _CHARS_PER_TOKEN


def _default_session_id() -> str:
    """Best-effort session id from env, else a per-process fallback."""
    return (
        os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("ATLAS_SESSION_ID")
        or f"pid-{os.getpid()}"
    )


def measure_file(path: str | Path) -> tuple[int, int]:
    """
    Return (bytes, lines) for a file WITHOUT retaining its content.
    Returns (0, 0) if the file can't be read. Never raises.
    """
    p = Path(path)
    try:
        data = p.read_bytes()
    except Exception:
        return (0, 0)
    n_bytes = len(data)
    # Count newlines without keeping decoded text around.
    n_lines = data.count(b"\n") + (1 if n_bytes and not data.endswith(b"\n") else 0)
    return (n_bytes, n_lines)


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeLoadEvent:
    """Metadata-only record of a single knowledge-file load. No content."""
    path: str
    source: str
    reason: str
    bytes: int
    lines: int
    estimated_tokens: int
    load_type: str
    session_id: str
    dedup_key: str
    duration_ms: float = 0.0
    already_loaded: bool = False
    event: str = "knowledge_load"
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        # Coerce unknown enums to safe defaults rather than failing.
        if self.source not in VALID_SOURCES:
            self.source = "manual"
        if self.reason not in VALID_REASONS:
            self.reason = "unknown"
        if self.load_type not in VALID_LOAD_TYPES:
            self.load_type = "manual"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def make_event(
    path: str | Path,
    source: str = "manual",
    reason: str = "unknown",
    load_type: str = "manual",
    *,
    bytes_: int | None = None,
    lines: int | None = None,
    duration_ms: float = 0.0,
    session_id: str | None = None,
    dedup_key: str | None = None,
) -> KnowledgeLoadEvent:
    """
    Build a KnowledgeLoadEvent. If bytes_/lines are not given, the file is
    measured on disk (metadata only). `already_loaded` is derived from the
    in-process dedup set for this session.
    """
    path_str = str(path)
    if bytes_ is None or lines is None:
        measured_bytes, measured_lines = measure_file(path_str)
        bytes_ = measured_bytes if bytes_ is None else bytes_
        lines = measured_lines if lines is None else lines

    key = dedup_key or path_str
    already = key in _seen_keys

    return KnowledgeLoadEvent(
        path=path_str,
        source=source,
        reason=reason,
        bytes=bytes_,
        lines=lines,
        estimated_tokens=estimate_tokens(bytes_),
        load_type=load_type,
        session_id=session_id or _default_session_id(),
        dedup_key=key,
        duration_ms=round(duration_ms, 3),
        already_loaded=already,
    )


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

def emit(event: KnowledgeLoadEvent, log_file: Path | None = None) -> bool:
    """
    Append event to the JSONL log. Returns True on success, False on any error
    or when disabled. Never raises — fail-open by design. Updates the in-process
    dedup set so subsequent loads of the same key report already_loaded=True.
    """
    if _is_disabled():
        return False

    target = log_file or _LOG_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        line = event.to_jsonl() + "\n"
        with _write_lock:
            with target.open("a", encoding="utf-8") as f:
                f.write(line)
            _seen_keys.add(event.dedup_key)
        return True
    except Exception:
        return False


def record_load(
    path: str | Path,
    source: str = "manual",
    reason: str = "unknown",
    load_type: str = "manual",
    *,
    session_id: str | None = None,
    dedup_key: str | None = None,
    log_file: Path | None = None,
) -> bool:
    """
    Convenience: measure the file, build the event, and emit in one call.
    Returns True on success. Fail-open.
    """
    evt = make_event(
        path,
        source=source,
        reason=reason,
        load_type=load_type,
        session_id=session_id,
        dedup_key=dedup_key,
    )
    return emit(evt, log_file=log_file)


class profile_load:
    """
    Context manager that times a read and records it on exit.

        with profile_load("CLAUDE.md", source="boot", reason="startup",
                          load_type="always_on"):
            text = Path("CLAUDE.md").read_text()

    The timing wraps whatever happens in the block. Fail-open.
    """

    def __init__(
        self,
        path: str | Path,
        source: str = "manual",
        reason: str = "unknown",
        load_type: str = "manual",
        *,
        session_id: str | None = None,
        dedup_key: str | None = None,
        log_file: Path | None = None,
    ) -> None:
        self.path = path
        self.source = source
        self.reason = reason
        self.load_type = load_type
        self.session_id = session_id
        self.dedup_key = dedup_key
        self.log_file = log_file
        self._start = 0.0

    def __enter__(self) -> "profile_load":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> bool:
        duration_ms = (time.perf_counter() - self._start) * 1000.0
        try:
            evt = make_event(
                self.path,
                source=self.source,
                reason=self.reason,
                load_type=self.load_type,
                duration_ms=duration_ms,
                session_id=self.session_id,
                dedup_key=self.dedup_key,
            )
            emit(evt, log_file=self.log_file)
        except Exception:
            pass
        return False  # never suppress exceptions


# ---------------------------------------------------------------------------
# Reader / aggregation
# ---------------------------------------------------------------------------

def read_events(log_file: Path | None = None, tail: int | None = None) -> list[KnowledgeLoadEvent]:
    """
    Read events from the JSONL log. Returns [] if missing/empty. Skips malformed
    lines silently. `tail` reads only the last N lines.
    """
    target = log_file or _LOG_FILE
    if not target.exists():
        return []

    events: list[KnowledgeLoadEvent] = []
    try:
        if tail is not None:
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
                # Drop unknown keys defensively; keep only dataclass fields.
                allowed = KnowledgeLoadEvent.__dataclass_fields__.keys()
                d = {k: v for k, v in d.items() if k in allowed}
                events.append(KnowledgeLoadEvent(**d))
            except Exception:
                pass
    except Exception:
        pass
    return events


def summarize(events: list[KnowledgeLoadEvent]) -> dict:
    """Aggregate metrics: totals, by load_type, by source, by reason, top files, dedup waste."""
    total_events = len(events)
    total_tokens = sum(e.estimated_tokens for e in events)
    total_bytes = sum(e.bytes for e in events)

    by_load_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    per_path_tokens: dict[str, int] = {}
    redundant_tokens = 0  # tokens spent re-loading already-seen keys

    for e in events:
        by_load_type[e.load_type] = by_load_type.get(e.load_type, 0) + 1
        by_source[e.source] = by_source.get(e.source, 0) + 1
        by_reason[e.reason] = by_reason.get(e.reason, 0) + 1
        per_path_tokens[e.path] = per_path_tokens.get(e.path, 0) + e.estimated_tokens
        if e.already_loaded:
            redundant_tokens += e.estimated_tokens

    always_on_tokens = sum(e.estimated_tokens for e in events if e.load_type == "always_on")
    top_files = sorted(per_path_tokens.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total_events": total_events,
        "total_estimated_tokens": total_tokens,
        "total_bytes": total_bytes,
        "always_on_tokens": always_on_tokens,
        "redundant_tokens": redundant_tokens,
        "by_load_type": by_load_type,
        "by_source": by_source,
        "by_reason": by_reason,
        "top_files_by_tokens": top_files,
    }


# ---------------------------------------------------------------------------
# Knowledge Registry + static scan (F29.2 / F29.3 / F29.4)
# ---------------------------------------------------------------------------

_KNOWLEDGE_REGISTRY_FILE = _PROJECT_ROOT / "config" / "knowledge.registry.yaml"

VALID_LOAD_POLICIES = {"always_on", "lazy", "manual", "runtime", "deprecated", "unknown"}

# File globs scanned by --scan (relative to project root).
_SCAN_GLOBS = [
    "CLAUDE.md",
    ".claude/agents/orquestador.md",
    ".claude/agents/agent-protocol.md",
    ".claude/agents/*.md",
    "agents/*.md",
    "docs/*.md",
    "config/*.yaml",
    ".claude/skills.registry.yaml",
]

# Doctrinal keywords for the duplication scan (F29.4) — detect only, never edit.
_DUPLICATION_KEYWORDS = [
    "Engram", "regla de oro", "pipeline", "cinco fases", "MCP",
    "capability", "QA", "release", "registry", "hard rules",
]


def load_knowledge_registry(path: Path | None = None) -> list[dict]:
    """Load config/knowledge.registry.yaml. Fail-open → [] if missing/invalid/no PyYAML."""
    target = path or _KNOWLEDGE_REGISTRY_FILE
    if not target.exists():
        return []
    try:
        import yaml
    except Exception:
        return []
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        entries = data.get("knowledge", data if isinstance(data, list) else [])
        return entries if isinstance(entries, list) else []
    except Exception:
        return []


def _registry_policy_map(path: Path | None = None) -> dict[str, str]:
    """Map of registered path → load_policy (for annotating scan results)."""
    out: dict[str, str] = {}
    for e in load_knowledge_registry(path):
        p = str(e.get("path", "")).replace("\\", "/")
        if p:
            out[p] = str(e.get("load_policy", "unknown"))
    return out


def categorize(rel_path: str) -> str:
    """Best-effort category from a project-relative path."""
    p = rel_path.replace("\\", "/")
    if p == "CLAUDE.md":
        return "system"
    if p.endswith("orquestador.md"):
        return "orchestrator"
    if p.endswith("agent-protocol.md"):
        return "agent-protocol"
    in_agents = "/agents/" in p or p.startswith("agents/")
    if p.endswith("-reference.md") and in_agents:
        return "agent-ref"
    if in_agents:
        return "agent"
    if p.endswith(".registry.yaml"):
        return "registry"
    if p.startswith("config/"):
        return "config"
    if p.startswith("docs/"):
        return "doc"
    if p.endswith(".md"):
        return "doc"
    return "other"


def estimate_load_policy(rel_path: str) -> str:
    """Heuristic load policy when the file isn't in the knowledge registry."""
    cat = categorize(rel_path)
    return {
        "system": "always_on",
        "orchestrator": "lazy",
        "agent-protocol": "lazy",
        "agent": "lazy",
        "agent-ref": "lazy",
        "registry": "manual",
        "config": "manual",
        "doc": "manual",
    }.get(cat, "unknown")


def scan_files(project_root: Path | None = None) -> list[dict]:
    """
    Static scan of relevant knowledge files. Metadata only (no content persisted).
    Returns one dict per file: path, bytes, lines, estimated_tokens, load_policy,
    category, existence, notes.
    """
    root = project_root or _PROJECT_ROOT
    reg_map = _registry_policy_map()
    seen: set[str] = set()
    rows: list[dict] = []

    for pattern in _SCAN_GLOBS:
        for match in sorted(root.glob(pattern)):
            if not match.is_file():
                continue
            rel = str(match.relative_to(root)).replace("\\", "/")
            if rel in seen:
                continue
            seen.add(rel)
            n_bytes, n_lines = measure_file(match)
            registered = rel in reg_map
            policy = reg_map.get(rel) or estimate_load_policy(rel)
            notes = "registered" if registered else "heuristic policy (not in knowledge registry)"
            rows.append({
                "path": rel,
                "bytes": n_bytes,
                "lines": n_lines,
                "estimated_tokens": estimate_tokens(n_bytes),
                "load_policy": policy,
                "category": categorize(rel),
                "existence": match.exists(),
                "notes": notes,
            })

    rows.sort(key=lambda r: r["estimated_tokens"], reverse=True)
    return rows


def scan_duplications(project_root: Path | None = None) -> list[dict]:
    """
    Detect doctrinal keyword spread across scanned files (F29.4). Reports only:
    keyword → number of files + count, flagged as candidate if it appears in >1 file.
    Never edits, never emits file content.
    """
    root = project_root or _PROJECT_ROOT
    rows = scan_files(root)
    results: list[dict] = []
    for kw in _DUPLICATION_KEYWORDS:
        kw_lower = kw.lower()
        files_hit: list[str] = []
        total = 0
        for r in rows:
            try:
                text = (root / r["path"]).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            c = text.lower().count(kw_lower)
            if c > 0:
                files_hit.append(r["path"])
                total += c
        results.append({
            "keyword": kw,
            "file_count": len(files_hit),
            "total_occurrences": total,
            "duplication_candidate": len(files_hit) > 1,
            "files": files_hit[:12],
        })
    results.sort(key=lambda d: d["file_count"], reverse=True)
    return results


def build_scan(project_root: Path | None = None) -> dict:
    """Full static scan payload: files + duplications + totals + policy breakdown."""
    files = scan_files(project_root)
    by_policy: dict[str, dict] = {}
    for r in files:
        b = by_policy.setdefault(r["load_policy"], {"files": 0, "estimated_tokens": 0})
        b["files"] += 1
        b["estimated_tokens"] += r["estimated_tokens"]
    return {
        "total_files": len(files),
        "total_estimated_tokens": sum(r["estimated_tokens"] for r in files),
        "always_on_tokens": sum(r["estimated_tokens"] for r in files if r["load_policy"] == "always_on"),
        "by_load_policy": by_policy,
        "files": files,
        "duplications": scan_duplications(project_root),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_scan_human(scan: dict, top_n: int | None = None) -> None:
    print("=" * 72)
    print("ATLAS Boot Profiler — static knowledge scan")
    print("=" * 72)
    print(f"files: {scan['total_files']}  "
          f"est_tokens: {scan['total_estimated_tokens']}  "
          f"always_on: {scan['always_on_tokens']}")
    print(f"by_load_policy: " + ", ".join(
        f"{k}={v['files']}f/{v['estimated_tokens']}t" for k, v in sorted(scan["by_load_policy"].items())))
    print()
    rows = scan["files"][:top_n] if top_n else scan["files"]
    print(f"{'tokens':>8}  {'lines':>6}  {'policy':<11} {'category':<14} path")
    print("-" * 72)
    for r in rows:
        print(f"{r['estimated_tokens']:>8}  {r['lines']:>6}  {r['load_policy']:<11} "
              f"{r['category']:<14} {r['path']}")
    if top_n is None:
        print()
        print("duplication candidates (doctrinal keywords across files):")
        for d in scan["duplications"]:
            if d["duplication_candidate"]:
                print(f"  {d['keyword']:<14} {d['file_count']:>3} files  "
                      f"{d['total_occurrences']:>5} hits")


def _cli() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    raw = sys.argv[1:]
    as_json = "--json" in raw
    want_scan = "--scan" in raw
    want_report = "--report" in raw
    want_top = "--top" in raw

    # --top N (optional numeric after --top); default 20
    top_n = 20
    if want_top:
        try:
            i = raw.index("--top")
            if i + 1 < len(raw) and raw[i + 1].isdigit():
                top_n = int(raw[i + 1])
        except Exception:
            pass

    positional = [a for a in raw if not a.startswith("--") and not a.isdigit()]
    cmd = positional[0] if positional else None

    # --- F29.2 static-scan family -------------------------------------------
    # --scan / --report / --top all operate on the static knowledge scan.
    # --json alone (no positional command) also returns the scan as JSON.
    if want_scan or want_report or want_top or (as_json and cmd is None):
        scan = build_scan()
        if as_json:
            payload = scan
            if want_top:
                payload = {**scan, "files": scan["files"][:top_n]}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        _print_scan_human(scan, top_n=top_n if want_top else None)
        return

    if cmd is None:
        cmd = "summary"

    if cmd == "summary":
        evts = read_events()
        s = summarize(evts)
        if as_json:
            print(json.dumps(s, ensure_ascii=False, indent=2))
            return
        print("=" * 60)
        print(f"ATLAS Boot Profiler — {_LOG_FILE}")
        print("=" * 60)
        print(f"events: {s['total_events']}  "
              f"est_tokens: {s['total_estimated_tokens']}  "
              f"always_on: {s['always_on_tokens']}  "
              f"redundant: {s['redundant_tokens']}")
        print(f"by_load_type: {s['by_load_type']}")
        print(f"by_source:    {s['by_source']}")
        print(f"by_reason:    {s['by_reason']}")
        print("top files by tokens:")
        for path, tok in s["top_files_by_tokens"]:
            print(f"  {tok:>8}  {path}")

    elif cmd == "tail":
        n = 10
        nums = [a for a in raw if a.isdigit()]
        if nums:
            n = int(nums[0])
        for e in read_events(tail=n):
            flag = " (dup)" if e.already_loaded else ""
            print(f"  {e.timestamp[:19]}  {e.load_type:<10} {e.source:<10} "
                  f"{e.estimated_tokens:>7}t  {e.path}{flag}")

    else:
        print(f"Unknown command: {cmd!r}. "
              f"Use: summary [--json] | tail [N] | --scan | --report | --top [N] | --json",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
