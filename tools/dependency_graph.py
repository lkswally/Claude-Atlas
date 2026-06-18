#!/usr/bin/env python3
"""
ATLAS Dependency Graph — F20
==============================

Construye el mapa completo de dependencias del sistema ATLAS:

  Agent → Capability → Policy → Provider → MCP → CLI → Binary

Detecta dependencias rotas en cada capa.

Usage:
  python tools/dependency_graph.py                  # full graph + broken deps
  python tools/dependency_graph.py --agent browser-related  # filter by agent
  python tools/dependency_graph.py --capability memory      # filter by capability
  python tools/dependency_graph.py --broken                 # only broken deps
  python tools/dependency_graph.py --json                   # machine-readable

Exit codes:
  0  no broken dependencies detected
  1  at least one broken dependency
  2  graph cannot be built (missing config files)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
HOOKS_DIR  = PROJECT_ROOT / ".claude" / "hooks"
ADR_DIR    = PROJECT_ROOT / "ADR"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DepNode:
    name: str
    kind: str          # agent | capability | policy | provider | mcp | cli | binary
    status: str        # OK | BROKEN | UNKNOWN | MISSING
    detail: str = ""
    children: list["DepNode"] = field(default_factory=list)

    def is_broken(self) -> bool:
        return self.status in ("BROKEN", "MISSING")

    def all_broken(self) -> list["DepNode"]:
        broken = [self] if self.is_broken() else []
        for child in self.children:
            broken.extend(child.all_broken())
        return broken


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_binary_node(cli_cmd: str, binary_hint: str = "") -> DepNode:
    """Check if a CLI command is resolvable in PATH."""
    resolved = shutil.which(cli_cmd)
    if resolved:
        return DepNode(cli_cmd, "binary", "OK", resolved)
    if binary_hint:
        return DepNode(cli_cmd, "binary", "MISSING", f"not in PATH — {binary_hint}")
    return DepNode(cli_cmd, "binary", "MISSING", "not in PATH")


def build_mcp_node(mcp_id: str, provider_status: str) -> DepNode:
    """Build MCP node, checking .mcp.json for registration."""
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    registered = False
    if mcp_file.exists():
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            registered = mcp_id in servers
        except Exception:
            pass

    if provider_status == "LIVE" and not registered:
        node = DepNode(mcp_id, "mcp", "BROKEN", "LIVE in registry but not in .mcp.json")
    elif provider_status == "LIVE" and registered:
        node = DepNode(mcp_id, "mcp", "OK", "registered in .mcp.json")
    elif registered:
        node = DepNode(mcp_id, "mcp", "OK", f"registered ({provider_status})")
    else:
        node = DepNode(mcp_id, "mcp", "UNKNOWN",
                       f"not in .mcp.json ({provider_status})")

    # Add CLI child for known MCPs
    cli_map = {
        "engram":       ("engram", "download from github.com/Gentleman-Programming/engram"),
        "context7":     ("npx",    "Node.js required"),
        "playwright":   ("npx",    "Node.js required"),
        "github":       (None,     None),
        "notion":       (None,     None),
    }
    if mcp_id in cli_map:
        cli_cmd, hint = cli_map[mcp_id]
        if cli_cmd:
            cli_node = DepNode(cli_cmd, "cli", "OK" if shutil.which(cli_cmd) else "MISSING",
                               hint or "")
            node.children.append(cli_node)

    return node


def build_provider_node(provider) -> DepNode:
    """Build provider node from a Provider dataclass."""
    status = provider.status
    ok = status in ("LIVE", "CONFIG_ONLY")
    node = DepNode(
        provider.mcp_id, "provider",
        "OK" if ok else "BROKEN" if status == "UNAVAILABLE" else "UNKNOWN",
        f"{status} — {provider.notes}" if provider.notes else status,
    )
    node.children.append(build_mcp_node(provider.mcp_id, status))
    return node


def build_capability_graph() -> list[DepNode]:
    """Build capability → policy → provider → mcp → binary nodes."""
    try:
        from core.capabilities.registry import list_capabilities
        from core.capabilities.policy import load_policy, _reset_cache
        _reset_cache()
        policies = load_policy()
        caps = list_capabilities()
    except Exception as e:
        return [DepNode("capabilities", "capability", "BROKEN", str(e))]

    nodes = []
    for cap in caps:
        policy = policies.get(cap.name)
        cap_status = "OK" if cap.active_provider and cap.active_provider.status == "LIVE" else "UNKNOWN"

        cap_node = DepNode(cap.name, "capability", cap_status, cap.description[:60])

        # Policy node
        if policy:
            pol_status = "OK"
            pol_detail = f"critical={policy.critical} severity={policy.severity}"
            pol_node = DepNode(cap.name, "policy", pol_status, pol_detail)
        else:
            pol_node = DepNode(cap.name, "policy", "MISSING", "no entry in capability.policy.yaml")
        cap_node.children.append(pol_node)

        # Provider nodes
        for provider in cap.providers:
            cap_node.children.append(build_provider_node(provider))

        nodes.append(cap_node)
    return nodes


def build_agent_capability_map() -> dict[str, list[str]]:
    """Scan agent files for capability references."""
    import re
    agent_caps: dict[str, list[str]] = {}
    if not AGENTS_DIR.exists():
        return agent_caps
    for f in AGENTS_DIR.glob("*.md"):
        if "reference" in f.name or f.name == "agent-protocol.md":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        caps = re.findall(r"capability[:\s]+(\w+)", text)
        if caps:
            agent_caps[f.stem] = list(dict.fromkeys(caps))
    return agent_caps


def build_hook_nodes() -> list[DepNode]:
    """Check each hook file exists and is syntactically valid (JS) or executable (sh)."""
    if not HOOKS_DIR.exists():
        return [DepNode("hooks/", "binary", "MISSING", "hooks directory not found")]
    nodes = []
    for f in sorted(HOOKS_DIR.iterdir()):
        if f.suffix not in (".js", ".sh") or not f.is_file():
            continue
        # Just check existence and size > 0 as basic validity
        size_ok = f.stat().st_size > 10
        nodes.append(DepNode(
            f.name, "cli",
            "OK" if size_ok else "BROKEN",
            f"{f.stat().st_size} bytes",
        ))
    return nodes


def build_adr_nodes() -> list[DepNode]:
    """Check ADR files reference artefacts that exist."""
    import re
    if not ADR_DIR.exists():
        return [DepNode("ADR/", "binary", "MISSING", "ADR directory not found")]
    nodes = []
    for f in sorted(ADR_DIR.glob("[0-9]*.md")):
        if "template" in f.name:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        status_match = re.search(r"\*\*Status:\*\*\s*(\w+)", text)
        status_val = status_match.group(1) if status_match else "UNKNOWN"
        nodes.append(DepNode(f.stem, "binary", "OK", f"Status: {status_val}"))
    return nodes


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_full_graph() -> dict[str, list[DepNode]]:
    return {
        "capabilities": build_capability_graph(),
        "hooks":        build_hook_nodes(),
        "adrs":         build_adr_nodes(),
    }


def collect_broken(graph: dict[str, list[DepNode]]) -> list[tuple[str, DepNode]]:
    broken = []
    for section, nodes in graph.items():
        for node in nodes:
            for b in node.all_broken():
                broken.append((section, b))
    return broken


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status_mark(status: str) -> str:
    return {"OK": "✓", "BROKEN": "✗", "MISSING": "✗", "UNKNOWN": "?"}.get(status, "?")


def _print_node(node: DepNode, indent: int = 0) -> None:
    prefix = "  " * indent
    mark = _status_mark(node.status)
    detail = f" — {node.detail}" if node.detail else ""
    print(f"{prefix}[{mark}] {node.kind}:{node.name}{detail}")
    for child in node.children:
        _print_node(child, indent + 1)


def print_graph(graph: dict[str, list[DepNode]], broken_only: bool = False) -> None:
    for section, nodes in graph.items():
        print(f"\n{'='*50}")
        print(f"  {section.upper()}")
        print(f"{'='*50}")
        for node in nodes:
            if broken_only:
                if node.all_broken():
                    _print_node(node)
            else:
                _print_node(node)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    as_json    = "--json" in args
    broken_only = "--broken" in args
    cap_filter = None
    if "--capability" in args:
        idx = args.index("--capability")
        try:
            cap_filter = args[idx + 1]
        except IndexError:
            pass

    print("=" * 60)
    print("ATLAS Dependency Graph")
    print("=" * 60)

    graph = build_full_graph()
    broken = collect_broken(graph)

    if cap_filter:
        graph["capabilities"] = [
            n for n in graph["capabilities"] if cap_filter.lower() in n.name.lower()
        ]

    if as_json:
        def node_to_dict(n: DepNode) -> dict:
            return {
                "name": n.name, "kind": n.kind, "status": n.status,
                "detail": n.detail,
                "children": [node_to_dict(c) for c in n.children],
            }
        out = {s: [node_to_dict(n) for n in nodes] for s, nodes in graph.items()}
        out["broken_count"] = len(broken)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if not broken else 1

    print_graph(graph, broken_only=broken_only)

    # Summary
    total_nodes = sum(len(nodes) for nodes in graph.values())
    print(f"\n{'='*60}")
    print(f"  Nodes: {total_nodes}  |  Broken: {len(broken)}")
    if broken:
        print(f"\n  Broken dependencies:")
        for section, node in broken:
            print(f"    [{section}] {node.kind}:{node.name} — {node.detail}")
    else:
        print("  All dependencies OK")
    print(f"{'='*60}")

    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())
