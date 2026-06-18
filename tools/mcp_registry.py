#!/usr/bin/env python3
"""
tools/mcp_registry.py — ATLAS MCP Registry Loader
====================================================

Carga y consulta config/mcp.registry.yaml.

API pública:
  load_registry()                         -> list[dict]
  get_mcp(id: str)                        -> dict | None
  find_mcps(status=None, required_for=None, capability=None) -> list[dict]
  list_live()                             -> list[dict]
  list_missing_required()                 -> list[dict]
  validate_registry()                     -> list[str]   # errores
  summary()                               -> dict

CLI:
  python tools/mcp_registry.py
  python tools/mcp_registry.py --status LIVE
  python tools/mcp_registry.py --id engram
  python tools/mcp_registry.py --validate
  python tools/mcp_registry.py --summary
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_FILE = PROJECT_ROOT / "config" / "mcp.registry.yaml"

DISABLED = os.environ.get("ATLAS_MCP_REGISTRY_DISABLED") == "1"

_cache: list[dict] | None = None


def _yaml_load(text: str) -> dict:
    """Minimal YAML parser for the registry format (no external deps)."""
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        pass
    # Fallback: use PyYAML if available, otherwise parse manually
    # For the registry format, we rely on PyYAML; fail-open if absent
    raise ImportError("PyYAML required: pip install pyyaml")


def load_registry() -> list[dict]:
    """Load and cache the MCP registry. Returns [] on any error (fail-open)."""
    global _cache
    if _cache is not None:
        return _cache

    if DISABLED:
        return []

    if not REGISTRY_FILE.exists():
        return []

    try:
        data = _yaml_load(REGISTRY_FILE.read_text(encoding="utf-8"))
        _cache = data.get("mcps", [])
        return _cache
    except Exception:
        return []


def get_mcp(id: str) -> dict | None:
    """Return a single MCP entry by id, or None."""
    for entry in load_registry():
        if entry.get("id") == id:
            return entry
    return None


def find_mcps(
    status: str | None = None,
    required_for: str | None = None,
    capability: str | None = None,
) -> list[dict]:
    """Filter MCPs by status, required_for agent, or capability."""
    results = load_registry()

    if status:
        results = [m for m in results if m.get("status") == status]

    if required_for:
        results = [
            m for m in results
            if required_for in (m.get("required_for") or [])
        ]

    if capability:
        results = [
            m for m in results
            if capability in (m.get("capabilities") or [])
        ]

    return results


def list_live() -> list[dict]:
    """Return all MCPs with status LIVE."""
    return find_mcps(status="LIVE")


def list_missing_required() -> list[dict]:
    """Return MCPs that are required by at least one agent but not LIVE.
    Excludes NOT_RECOMMENDED and DEFERRED_PAID (intentional non-installs).
    """
    excluded = {"NOT_RECOMMENDED", "DEFERRED_PAID"}
    results = []
    for m in load_registry():
        status = m.get("status", "")
        if status != "LIVE" and status not in excluded and m.get("required_for"):
            results.append(m)
    return results


def find_by_capability(capability: str) -> list[dict]:
    """Return all MCPs for a given atlas_capability, ordered LIVE first."""
    order = ["LIVE", "CONFIG_ONLY", "CLI_ONLY", "PENDING_TOKEN", "DEFERRED_PAID", "NOT_RECOMMENDED", "MISSING"]
    results = [m for m in load_registry() if m.get("atlas_capability") == capability]
    results.sort(key=lambda m: order.index(m.get("status", "MISSING")) if m.get("status") in order else 99)
    return results


def validate_registry() -> list[str]:
    """Validate registry integrity. Returns list of error strings."""
    errors = []
    registry = load_registry()

    if not registry:
        if REGISTRY_FILE.exists():
            errors.append("Registry exists but loaded 0 entries")
        else:
            errors.append(f"Registry file not found: {REGISTRY_FILE}")
        return errors

    seen_ids: set[str] = set()
    valid_statuses = {
        "LIVE", "CONFIG_ONLY", "CLI_ONLY", "MISSING", "OPTIONAL",
        "PENDING_TOKEN", "DEFERRED_PAID", "NOT_RECOMMENDED",
    }

    for i, m in enumerate(registry):
        mid = m.get("id", f"[{i}]")

        if not m.get("id"):
            errors.append(f"Entry {i}: missing 'id'")
        elif mid in seen_ids:
            errors.append(f"Duplicate id: {mid}")
        seen_ids.add(mid)

        if not m.get("name"):
            errors.append(f"{mid}: missing 'name'")

        if not m.get("status"):
            errors.append(f"{mid}: missing 'status'")
        elif m["status"] not in valid_statuses:
            errors.append(f"{mid}: invalid status '{m['status']}'")

        if not m.get("live_tool_prefix"):
            errors.append(f"{mid}: missing 'live_tool_prefix'")

    return errors


def summary() -> dict:
    """Return a summary dict with counts by status."""
    registry = load_registry()
    by_status: dict[str, int] = {}
    for m in registry:
        s = m.get("status", "UNKNOWN")
        by_status[s] = by_status.get(s, 0) + 1

    live = [m["id"] for m in registry if m.get("status") == "LIVE"]
    missing_required = [
        m["id"] for m in list_missing_required()
    ]

    return {
        "total": len(registry),
        "by_status": by_status,
        "live": live,
        "missing_required": missing_required,
        "registry_file": str(REGISTRY_FILE),
        "disabled": DISABLED,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    args = sys.argv[1:]

    if "--validate" in args:
        errors = validate_registry()
        if errors:
            for e in errors:
                print(f"  [ERR] {e}")
            sys.exit(1)
        else:
            reg = load_registry()
            print(f"  [OK] Registry valid: {len(reg)} entries")
            sys.exit(0)

    if "--summary" in args:
        s = summary()
        print(json.dumps(s, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--id" in args:
        idx = args.index("--id")
        mcp_id = args[idx + 1] if idx + 1 < len(args) else None
        if not mcp_id:
            print("Usage: --id <mcp_id>")
            sys.exit(1)
        m = get_mcp(mcp_id)
        if m:
            print(json.dumps(m, indent=2, ensure_ascii=False))
        else:
            print(f"MCP '{mcp_id}' not found")
            sys.exit(1)
        sys.exit(0)

    status_filter = None
    if "--status" in args:
        idx = args.index("--status")
        status_filter = args[idx + 1] if idx + 1 < len(args) else None

    registry = load_registry()
    if status_filter:
        registry = [m for m in registry if m.get("status") == status_filter]

    if not registry:
        print("No entries found")
        sys.exit(0)

    # Table output
    header = f"{'ID':<20} {'STATUS':<14} {'NAME':<30} {'LIVE_PREFIX'}"
    print(header)
    print("-" * len(header))
    for m in registry:
        print(
            f"{m.get('id','?'):<20} "
            f"{m.get('status','?'):<14} "
            f"{m.get('name','?'):<30} "
            f"{m.get('live_tool_prefix','')}"
        )


if __name__ == "__main__":
    _cli()
