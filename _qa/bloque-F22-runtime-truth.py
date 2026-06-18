#!/usr/bin/env python3
"""
Bloque F22 — Runtime Truth Audit
==================================

Validates that what ATLAS claims to have actually exists and works:
capabilities, MCPs, policies, registry consistency.

TC1:  capability registry imports (list_capabilities works)
TC2:  all capabilities have at least one provider
TC3:  policy YAML loads and has entries for all capabilities
TC4:  no capability is in registry without a policy entry
TC5:  no capability has a policy without a registry entry (orphan policy)
TC6:  MCP registry YAML loads
TC7:  every LIVE capability has a matching LIVE entry in MCP registry
TC8:  PENDING_TOKEN capabilities are documented as such in MCP registry
TC9:  resolve_capability('memory') returns LIVE
TC10: resolve_capability('browser') returns LIVE
TC11: resolve_capability('documentation') returns LIVE
TC12: resolve_capability('repository') returns PENDING_TOKEN (not BLOCK)
TC13: evaluate_capability('memory') returns ALLOW or WARN (not BLOCK)
TC14: capability_metrics imports and can read_events()
"""

import io
import os
import subprocess
import sys
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fix Windows charmap encoding for stdout
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PASS_COUNT = 0
FAIL_COUNT = 0


def PASS(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    msg = f"  [PASS] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def FAIL(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


# TC1 — capability registry imports
try:
    from core.capabilities.registry import list_capabilities
    caps = list_capabilities()
    if caps and len(caps) > 0:
        PASS("TC1 capability registry imports", f"{len(caps)} capabilities")
    else:
        FAIL("TC1 capability registry imports", "empty list")
except Exception as e:
    FAIL("TC1 capability registry imports", str(e))
    caps = []

# TC2 — all capabilities have at least one provider
try:
    no_provider = [c.name for c in caps if not c.providers]
    if not no_provider:
        PASS("TC2 all capabilities have at least one provider")
    else:
        FAIL("TC2 all capabilities have at least one provider", f"no provider: {no_provider}")
except Exception as e:
    FAIL("TC2 all capabilities have provider", str(e))

# TC3 — policy YAML loads
policy_caps: set[str] = set()
try:
    policy_data = yaml.safe_load(open(PROJECT_ROOT / "config/capability.policy.yaml"))
    policy_caps = set(policy_data.keys()) if isinstance(policy_data, dict) else set()
    if policy_caps:
        PASS("TC3 policy YAML loads", f"{len(policy_caps)} entries")
    else:
        FAIL("TC3 policy YAML loads", "no entries or wrong format")
except Exception as e:
    FAIL("TC3 policy YAML loads", str(e))

# TC4 — no capability without a policy
try:
    cap_names = {c.name for c in caps}
    missing_policy = cap_names - policy_caps
    if not missing_policy:
        PASS("TC4 all capabilities have a policy entry")
    else:
        FAIL("TC4 all capabilities have a policy entry", f"missing: {missing_policy}")
except Exception as e:
    FAIL("TC4 capabilities have policy", str(e))

# TC5 — no orphan policies (policy entry with no registry capability)
try:
    cap_names = {c.name for c in caps}
    orphan = policy_caps - cap_names
    if not orphan:
        PASS("TC5 no orphan policy entries")
    else:
        FAIL("TC5 no orphan policy entries", f"orphan: {orphan}")
except Exception as e:
    FAIL("TC5 no orphan policies", str(e))

# TC6 — MCP registry loads
mcp_registry: list = []
try:
    mcp_data = yaml.safe_load(open(PROJECT_ROOT / "config/mcp.registry.yaml"))
    mcp_registry = mcp_data.get("mcps", []) if isinstance(mcp_data, dict) else []
    if mcp_registry:
        PASS("TC6 MCP registry YAML loads", f"{len(mcp_registry)} MCPs")
    else:
        FAIL("TC6 MCP registry YAML loads", "empty or wrong format")
except Exception as e:
    FAIL("TC6 MCP registry YAML loads", str(e))

# TC7 — every LIVE capability has matching LIVE MCP entry
try:
    mcp_ids_live = {m["id"] for m in mcp_registry if m.get("status") == "LIVE"}
    live_caps = [c for c in caps if any(p.status == "LIVE" for p in c.providers)]
    mismatches = []
    for cap in live_caps:
        live_providers = [p for p in cap.providers if p.status == "LIVE"]
        if not any(p.mcp_id in mcp_ids_live for p in live_providers):
            # Check if any provider is registered (may have different ID format)
            provider_ids = {p.mcp_id for p in live_providers}
            # Allow partial match (e.g. "claude_in_chrome" vs "claude_preview")
            if not provider_ids.intersection(mcp_ids_live):
                mismatches.append(f"{cap.name}({provider_ids})")
    if not mismatches:
        PASS("TC7 LIVE capabilities have LIVE MCP registry entry")
    else:
        FAIL("TC7 LIVE capabilities have LIVE MCP registry entry", f"mismatches: {mismatches[:3]}")
except Exception as e:
    FAIL("TC7 LIVE/MCP consistency", str(e))

# TC8 — PENDING_TOKEN capabilities documented as such in MCP registry
try:
    mcp_status = {m["id"]: m.get("status") for m in mcp_registry}
    pending_caps = [c for c in caps if any(p.status == "PENDING_TOKEN" for p in c.providers)]
    errors = []
    for cap in pending_caps:
        pending_providers = [p for p in cap.providers if p.status == "PENDING_TOKEN"]
        for p in pending_providers:
            mcp_s = mcp_status.get(p.mcp_id)
            if mcp_s and mcp_s not in ("PENDING_TOKEN", "CONFIG_ONLY"):
                errors.append(f"{cap.name}/{p.mcp_id}: registry={mcp_s}, cap=PENDING_TOKEN")
    if not errors:
        PASS("TC8 PENDING_TOKEN capabilities consistent in MCP registry")
    else:
        FAIL("TC8 PENDING_TOKEN consistency", f"{errors[:2]}")
except Exception as e:
    FAIL("TC8 PENDING_TOKEN consistency", str(e))

def _resolve_capability_json(cap_name: str) -> dict:
    """Run resolve_capability in subprocess with UTF-8 to avoid Windows charmap issues."""
    code = (
        "import sys, io, json; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8');"
        "sys.path.insert(0,'.'); from core.capabilities.router import resolve_capability;"
        f"r = resolve_capability('{cap_name}', emit=False);"
        "print(json.dumps({'provider': r.provider, 'status': r.status}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=10, cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit {result.returncode}")
    return json.loads(result.stdout.strip())


import json

# TC9 — resolve_capability('memory') → LIVE
try:
    data = _resolve_capability_json("memory")
    if data["status"] == "LIVE":
        PASS("TC9 resolve_capability('memory') -> LIVE", f"provider={data['provider']}")
    else:
        FAIL("TC9 resolve_capability('memory') -> LIVE", f"got status={data['status']}")
except Exception as e:
    FAIL("TC9 resolve_capability memory", str(e))

# TC10 — resolve_capability('browser') → LIVE
try:
    data = _resolve_capability_json("browser")
    if data["status"] == "LIVE":
        PASS("TC10 resolve_capability('browser') -> LIVE", f"provider={data['provider']}")
    else:
        FAIL("TC10 resolve_capability('browser') -> LIVE", f"got status={data['status']}")
except Exception as e:
    FAIL("TC10 resolve_capability browser", str(e))

# TC11 — resolve_capability('documentation') → LIVE
try:
    data = _resolve_capability_json("documentation")
    if data["status"] == "LIVE":
        PASS("TC11 resolve_capability('documentation') -> LIVE", f"provider={data['provider']}")
    else:
        FAIL("TC11 resolve_capability('documentation') -> LIVE", f"got status={data['status']}")
except Exception as e:
    FAIL("TC11 resolve_capability documentation", str(e))

# TC12 — resolve_capability('repository') → PENDING_TOKEN (not BLOCK)
try:
    data = _resolve_capability_json("repository")
    if data["status"] == "PENDING_TOKEN":
        PASS("TC12 resolve_capability('repository') -> PENDING_TOKEN")
    else:
        FAIL("TC12 resolve_capability('repository') -> PENDING_TOKEN", f"got status={data['status']}")
except Exception as e:
    FAIL("TC12 resolve_capability repository", str(e))

# TC13 — evaluate_capability('memory') → ALLOW or WARN (not BLOCK)
try:
    from core.capabilities.policy import evaluate_capability
    d = evaluate_capability("memory", _emit=False)
    if d.decision in ("ALLOW", "WARN", "DEGRADED"):
        PASS("TC13 evaluate_capability('memory') is usable", f"decision={d.decision}")
    else:
        FAIL("TC13 evaluate_capability('memory') is usable", f"got decision={d.decision}")
except Exception as e:
    FAIL("TC13 evaluate_capability memory", str(e))

# TC14 — capability_metrics can read_events
try:
    from core.capabilities.events import read_events
    events = read_events()
    if isinstance(events, list):
        PASS("TC14 capability events read_events()", f"{len(events)} events in log")
    else:
        FAIL("TC14 capability events read_events()", f"unexpected type: {type(events)}")
except Exception as e:
    FAIL("TC14 capability events read_events", str(e))


print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
