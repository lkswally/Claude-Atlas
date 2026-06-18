"""
ATLAS Capability Registry
=========================

Single source of truth for capability → MCP provider mapping.
Add new capabilities here when new MCPs are integrated.

Capabilities:
    memory              engram (LIVE)
    project_management  notion (LIVE)
    documentation       context7 (LIVE)
    browser             playwright (LIVE) | claude_in_chrome (LIVE) | claude_preview (LIVE)
    computer_control    computer_use (LIVE)
    repository          github (PENDING_TOKEN)
    deployment          vercel (PENDING_TOKEN)
    database            supabase (NOT_RECOMMENDED — needs eval)
    design              magic_21st (DEFERRED_PAID)
    messaging           slack (NOT_RECOMMENDED — no clear ATLAS use case)
    storage             gdrive (NOT_RECOMMENDED — no clear ATLAS use case)
    visualization       visualize (LIVE)
    scheduling          scheduled_tasks (LIVE)
    filesystem          filesystem (NOT_RECOMMENDED — Claude Code covers this)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from .base import Capability, Provider

DISABLED = os.environ.get("ATLAS_CAPABILITIES_DISABLED") == "1"

# ---------------------------------------------------------------------------
# Capability definitions
# ---------------------------------------------------------------------------

_CAPABILITIES: list[Capability] = [
    Capability(
        name="memory",
        description="Persistent memory: save, search, recall observations across sessions",
        providers=[Provider("engram", "Engram", "LIVE", "mcp__engram__")],
        required_by=["orquestador", "project-manager-senior", "evidence-collector", "reality-checker"],
    ),
    Capability(
        name="project_management",
        description="Create/update/search pages, databases, comments in Notion",
        providers=[Provider("notion", "Notion", "LIVE", "mcp__52722bcc-d6c5-4bf4-8d79-ccad7a479b8f__notion-")],
        required_by=["orquestador", "project-manager-senior"],
    ),
    Capability(
        name="documentation",
        description="Fetch up-to-date library docs: React, Next.js, Playwright, Prisma, FastAPI, etc.",
        providers=[Provider("context7", "Context7", "LIVE", "mcp__context7__")],
        required_by=["frontend-developer", "backend-architect", "ux-architect"],
    ),
    Capability(
        name="browser",
        description="Real browser: navigate, screenshot, click, evaluate JS, read DOM, network monitoring",
        providers=[
            Provider("playwright", "Playwright MCP", "LIVE", "mcp__playwright__",
                     notes="Headless chromium — QA automation, E2E"),
            Provider("claude_in_chrome", "Claude in Chrome", "LIVE", "mcp__Claude_in_Chrome__",
                     notes="Chrome extension — interactive browsing"),
            Provider("claude_preview", "Claude Preview", "LIVE", "mcp__Claude_Preview__",
                     notes="Dev server preview — frontend verification"),
        ],
        required_by=["evidence-collector", "reality-checker", "performance-benchmarker", "codepen-explorer"],
    ),
    Capability(
        name="computer_control",
        description="Desktop control: screenshot, click, type, scroll, open applications",
        providers=[Provider("computer_use", "Computer Use", "LIVE", "mcp__computer-use__")],
        required_by=[],
    ),
    Capability(
        name="repository",
        description="GitHub: repos, issues, PRs, code search, releases, workflows",
        providers=[Provider("github", "GitHub MCP", "PENDING_TOKEN",
                            "mcp__github__", notes="Needs GITHUB_TOKEN in .env.local")],
        required_by=["git", "orquestador", "self-auditor", "build-resolver"],
    ),
    Capability(
        name="deployment",
        description="Vercel: deployments, preview URLs, env vars, logs",
        providers=[Provider("vercel", "Vercel MCP", "PENDING_TOKEN",
                            "mcp__vercel__", notes="Needs VERCEL_TOKEN in .env.local")],
        required_by=["deployer", "orquestador"],
    ),
    Capability(
        name="visualization",
        description="Render SVG, HTML widgets, charts inline in conversation",
        providers=[Provider("visualize", "Visualize", "LIVE", "mcp__visualize__")],
        required_by=["ui-designer", "brand-agent"],
    ),
    Capability(
        name="scheduling",
        description="Create and manage scheduled cloud tasks/routines",
        providers=[Provider("scheduled_tasks", "Scheduled Tasks", "LIVE", "mcp__scheduled-tasks__")],
        required_by=[],
    ),
    Capability(
        name="design",
        description="AI-generated UI components from 21st.dev design system",
        providers=[Provider("magic_21st", "21st.dev Magic", "DEFERRED_PAID",
                            "mcp__21st_magic__", notes="Requires paid API key from 21st.dev")],
        required_by=["ui-designer", "frontend-developer"],
    ),
    Capability(
        name="database",
        description="Supabase: SQL queries, storage, auth, migrations, logs",
        providers=[Provider("supabase", "Supabase MCP", "NOT_RECOMMENDED",
                            "mcp__supabase__",
                            notes="Needs project URL + service key per project. Value unclear vs direct SQL.")],
        required_by=["backend-architect"],
    ),
    Capability(
        name="filesystem",
        description="Read/write/list files on the filesystem",
        providers=[Provider("filesystem", "MCP Filesystem", "NOT_RECOMMENDED",
                            "mcp__filesystem__",
                            notes="Claude Code already provides Read/Write/Edit/Glob/Grep natively.")],
        required_by=[],
    ),
    Capability(
        name="storage",
        description="Google Drive: read, create, search documents",
        providers=[Provider("gdrive", "Google Drive MCP", "NOT_RECOMMENDED",
                            "mcp__gdrive__",
                            notes="Needs OAuth flow. No clear use case in current ATLAS agents.")],
        required_by=[],
    ),
    Capability(
        name="messaging",
        description="Send/receive messages via Slack or Telegram",
        providers=[Provider("slack", "Slack MCP", "NOT_RECOMMENDED",
                            "mcp__slack__",
                            notes="Useful for alerts/reports but needs Slack token. Low priority.")],
        required_by=[],
    ),
]

_index: dict[str, Capability] = {c.name: c for c in _CAPABILITIES}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_capability(name: str) -> Capability | None:
    """Return a capability by name, or None if unknown."""
    if DISABLED:
        return None
    return _index.get(name)


def list_capabilities(available_only: bool = False) -> list[Capability]:
    """List all capabilities, optionally filtering to available-only."""
    if DISABLED:
        return []
    caps = list(_CAPABILITIES)
    if available_only:
        caps = [c for c in caps if c.is_available]
    return caps


def capability_status() -> dict:
    """Return a summary dict for healthcheck/reporting."""
    caps = list_capabilities()
    live = [c.name for c in caps if c.active_provider and c.active_provider.status == "LIVE"]
    pending = [c.name for c in caps if c.active_provider and c.active_provider.status in ("PENDING_TOKEN", "CONFIG_ONLY")]
    deferred = [c.name for c in caps if not c.is_available or (c.active_provider and c.active_provider.status in ("DEFERRED_PAID", "NOT_RECOMMENDED"))]
    return {
        "total": len(caps),
        "live": live,
        "pending": pending,
        "deferred": deferred,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    s = capability_status()
    print(f"Capabilities: {s['total']} total")
    print(f"  LIVE ({len(s['live'])}): {', '.join(s['live'])}")
    print(f"  PENDING ({len(s['pending'])}): {', '.join(s['pending'])}")
    print(f"  DEFERRED/NOT_RECOMMENDED ({len(s['deferred'])}): {', '.join(s['deferred'])}")
    print()
    for cap in list_capabilities():
        p = cap.active_provider
        status = p.status if p else "UNAVAILABLE"
        provider = p.mcp_id if p else "—"
        print(f"  {cap.name:<22} {status:<18} provider={provider}")
