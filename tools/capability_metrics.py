#!/usr/bin/env python3
"""
ATLAS Capability Metrics — F18
================================

Reads .pipeline/capability-events.jsonl and produces observability reports.

Usage:
  python tools/capability_metrics.py                  # summary report
  python tools/capability_metrics.py --last 20        # last N events
  python tools/capability_metrics.py --capability browser  # filter by capability
  python tools/capability_metrics.py --json           # machine-readable output
  python tools/capability_metrics.py --critical       # critical capability status only

Exit codes:
  0  healthy (all critical capabilities LIVE or usable)
  1  degraded (at least one critical capability not LIVE)
  2  no events yet (informational — not an error)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
EVENTS_FILE = PROJECT_ROOT / ".pipeline" / "capability-events.jsonl"
CRITICAL_CAPABILITIES = {"memory", "browser", "documentation"}

sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Load events
# ---------------------------------------------------------------------------

def load_events(events_file: Path | None = None) -> list[dict]:
    """Load all events from JSONL. Returns [] on missing file or parse errors."""
    target = events_file or EVENTS_FILE
    if not target.exists():
        return []
    events = []
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return events


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_metrics(events: list[dict]) -> dict:
    """
    Compute aggregate metrics from a list of event dicts.

    Returns:
      total_resolutions     int
      by_capability         {capability: count}
      by_provider           {provider: count}
      by_status             {status: count}
      fallback_count        int
      unresolved            [capability names with UNAVAILABLE status]
      critical_status       {capability: last_status}
      resolution_ok_rate    float (0-1)
      last_events           last 10 events (list of dicts)
    """
    if not events:
        return {
            "total_resolutions": 0,
            "by_capability": {},
            "by_provider": {},
            "by_status": {},
            "fallback_count": 0,
            "unresolved": [],
            "critical_status": {c: "NO_DATA" for c in CRITICAL_CAPABILITIES},
            "resolution_ok_rate": None,
            "last_events": [],
        }

    by_capability: Counter = Counter()
    by_provider: Counter = Counter()
    by_status: Counter = Counter()
    fallback_count = 0
    ok_count = 0
    unresolved_caps: set[str] = set()
    # Track last status per critical capability
    critical_last: dict[str, str] = {}

    for evt in events:
        cap = evt.get("capability", "unknown")
        provider = evt.get("provider_selected") or "—"
        status = evt.get("provider_status", "UNKNOWN")
        fallback = evt.get("fallback_used", False)
        ok = evt.get("resolution_ok", False)

        by_capability[cap] += 1
        by_provider[provider] += 1
        by_status[status] += 1
        if fallback:
            fallback_count += 1
        if ok:
            ok_count += 1
        if status == "UNAVAILABLE":
            unresolved_caps.add(cap)
        if cap in CRITICAL_CAPABILITIES:
            critical_last[cap] = status

    # Fill in any critical caps not seen in events
    for c in CRITICAL_CAPABILITIES:
        if c not in critical_last:
            critical_last[c] = "NO_DATA"

    return {
        "total_resolutions": len(events),
        "by_capability": dict(by_capability.most_common()),
        "by_provider": dict(by_provider.most_common()),
        "by_status": dict(by_status.most_common()),
        "fallback_count": fallback_count,
        "unresolved": sorted(unresolved_caps),
        "critical_status": critical_last,
        "resolution_ok_rate": round(ok_count / len(events), 3) if events else None,
        "last_events": events[-10:],
    }


def last_n_events(events: list[dict], n: int = 20) -> list[dict]:
    return events[-n:]


def filter_by_capability(events: list[dict], capability: str) -> list[dict]:
    return [e for e in events if e.get("capability") == capability]


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _ok_rate_str(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    pct = int(rate * 100)
    mark = "✓" if pct >= 80 else "⚠"
    return f"{pct}% {mark}"


def print_summary(metrics: dict, last_n: int = 10) -> None:
    print("=" * 60)
    print("ATLAS Capability Metrics")
    print("=" * 60)
    print()

    total = metrics["total_resolutions"]
    if total == 0:
        print("  No events recorded yet.")
        print("  Events are written to: .pipeline/capability-events.jsonl")
        print("  They are generated automatically when capabilities are resolved.")
        return

    print(f"  Total resolutions : {total}")
    print(f"  OK rate           : {_ok_rate_str(metrics['resolution_ok_rate'])}")
    print(f"  Fallback used     : {metrics['fallback_count']} times")
    print()

    # Critical status
    print("  Critical capabilities:")
    for cap, status in sorted(metrics["critical_status"].items()):
        mark = "✓" if status == "LIVE" else ("~" if status in ("CONFIG_ONLY", "NO_DATA") else "✗")
        print(f"    [{mark}] {cap:<20} {status}")
    print()

    # By capability
    print("  Resolutions by capability:")
    for cap, count in metrics["by_capability"].items():
        print(f"    {cap:<22} {count:>5}")
    print()

    # By provider
    print("  Resolutions by provider:")
    for prov, count in metrics["by_provider"].items():
        print(f"    {prov:<22} {count:>5}")
    print()

    # By status
    print("  By resolution status:")
    for status, count in metrics["by_status"].items():
        print(f"    {status:<20} {count:>5}")
    print()

    # Unresolved
    if metrics["unresolved"]:
        print(f"  ⚠ Unresolved capabilities: {', '.join(metrics['unresolved'])}")
        print()

    # Last events
    last = metrics["last_events"]
    if last:
        print(f"  Last {len(last)} events:")
        for e in last:
            ts = e.get("timestamp", "")[:19]
            cap = e.get("capability", "?")
            status = e.get("provider_status", "?")
            prov = e.get("provider_selected") or "—"
            fb = " [fallback]" if e.get("fallback_used") else ""
            print(f"    {ts}  {cap:<18} {status:<16} {prov}{fb}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    as_json = "--json" in args
    critical_only = "--critical" in args

    # --last N
    last_n = 10
    if "--last" in args:
        idx = args.index("--last")
        try:
            last_n = int(args[idx + 1])
        except (IndexError, ValueError):
            pass

    # --capability X
    cap_filter = None
    if "--capability" in args:
        idx = args.index("--capability")
        try:
            cap_filter = args[idx + 1]
        except IndexError:
            pass

    events = load_events()

    if cap_filter:
        events = filter_by_capability(events, cap_filter)

    if "--last" in args and not cap_filter and not critical_only:
        events = last_n_events(events, last_n)

    metrics = compute_metrics(events)

    if as_json:
        # Remove non-serializable items
        out = {k: v for k, v in metrics.items() if k != "last_events"}
        out["last_events"] = metrics["last_events"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if critical_only:
        print("Critical capability status:")
        for cap, status in sorted(metrics["critical_status"].items()):
            print(f"  {cap:<20} {status}")
        degraded = [c for c, s in metrics["critical_status"].items()
                    if s not in ("LIVE", "CONFIG_ONLY")]
        return 1 if degraded else 0

    if metrics["total_resolutions"] == 0:
        print_summary(metrics)
        return 2

    print_summary(metrics, last_n=last_n)

    # Exit 1 if any critical capability is not usable
    degraded = [c for c, s in metrics["critical_status"].items()
                if s not in ("LIVE", "CONFIG_ONLY", "NO_DATA")]
    return 1 if degraded else 0


if __name__ == "__main__":
    sys.exit(main())
