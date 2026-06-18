# Capability Reference

ATLAS uses a capability abstraction layer that decouples agents from MCP internals. This document describes all 14 registered capabilities, their providers, policies, and usage.

## API Quick Reference

```python
from core.capabilities.router import resolve_capability, resolve_with_policy
from core.capabilities.policy import evaluate_capability

# Get best available provider
r = resolve_capability("browser")
print(r.provider)      # "playwright"
print(r.status)        # "LIVE"
print(r.is_usable)     # True
print(r.action)        # "USE_LIVE"
print(r.fallback)      # Resolution(provider="claude_in_chrome", ...)

# Get provider + policy decision
r, d = resolve_with_policy("memory")
print(d.decision)      # "ALLOW"
print(d.is_blocking)   # False
print(d.is_usable)     # True

# Policy only (no provider resolution)
d = evaluate_capability("repository")
print(d.decision)      # "WARN"
print(d.recovery_hint) # "Configurar GITHUB_TOKEN..."
```

## Status Values

| Status | Meaning | `is_usable` |
|--------|---------|------------|
| `LIVE` | Provider installed and active | True |
| `CONFIG_ONLY` | Works but needs configuration | True |
| `PENDING_TOKEN` | Needs API token or auth | False |
| `DEFERRED_PAID` | Available but costs money; not activated | False |
| `UNAVAILABLE` | Not installed or unreachable | False |

## Policy Outcomes

| Outcome | Meaning | `is_usable` | `is_blocking` |
|---------|---------|------------|--------------|
| `ALLOW` | Status meets required_status | True | False |
| `WARN` | Issues present but can proceed | True | False |
| `DEGRADED` | Fallback provider active | True | False |
| `BLOCK` | `block_if_unavailable=true` + no usable provider | False | True |
| `MISSING_POLICY` | Not in `capability.policy.yaml` | True | False |

---

## Capabilities

### memory

Persistent memory: save, search, update, get observations across sessions.

| | |
|---|---|
| **Provider** | `engram` |
| **Status** | LIVE |
| **MCP prefix** | `mcp__engram__` |
| **Critical** | Yes |
| **Policy** | `block_if_unavailable: true` — memory loss is unrecoverable |
| **Severity** | CRITICAL |
| **Fallback** | None |
| **Recovery** | `engram doctor` to diagnose; reinstall if corrupt |
| **Env bypass** | `ATLAS_CAPABILITY_EVENTS_DISABLED=1` (events only) |

Usage: `mem_save`, `mem_search`, `mem_get_observation`, `mem_update`, `mem_context`

---

### browser

Real browser automation: navigate, screenshot, click, evaluate JS, read DOM.

| | |
|---|---|
| **Primary provider** | `playwright` |
| **Fallback 1** | `claude_in_chrome` (Chrome extension — interactive) |
| **Fallback 2** | `claude_preview` (dev server preview) |
| **Status** | LIVE (all three) |
| **Critical** | Yes |
| **Policy** | `fallback_allowed: true` — QA can degrade to screenshot-only |
| **Severity** | HIGH |

Usage: `browser_navigate`, `browser_take_screenshot`, `browser_snapshot`, `browser_evaluate`

---

### documentation

Query live documentation for any library/framework/SDK.

| | |
|---|---|
| **Provider** | `context7` |
| **Status** | LIVE |
| **MCP prefix** | `mcp__context7__` |
| **Critical** | Yes |
| **Policy** | `block_if_unavailable: false` — agents can use training data as fallback |
| **Severity** | HIGH |
| **Recovery** | Reinstall context7 MCP |

Usage: `resolve-library-id`, `query-docs`

---

### project_management

Create and manage pages, databases, and comments in Notion.

| | |
|---|---|
| **Provider** | `notion` |
| **Status** | LIVE |
| **MCP ID** | `mcp__52722bcc-d6c5-4bf4-8d79-ccad7a479b8f__notion-` |
| **Critical** | True |
| **Policy** | `block_if_unavailable: true` — project tracking is critical |
| **Severity** | CRITICAL |
| **Recovery** | Re-connect Notion integration in Claude settings |

---

### repository

GitHub operations: create repos, manage PRs, push code, read files.

| | |
|---|---|
| **Provider** | `github` |
| **Status** | PENDING_TOKEN |
| **Policy** | `block_if_unavailable: false` — can use git CLI as fallback |
| **Severity** | HIGH |
| **Recovery** | Set `GITHUB_TOKEN` in `.env.local` and restart Claude |

---

### deployment

Deploy to Vercel: create projects, deployments, manage domains.

| | |
|---|---|
| **Provider** | `vercel` |
| **Status** | PENDING_TOKEN |
| **Policy** | `block_if_unavailable: false` — can use Vercel CLI as fallback |
| **Severity** | HIGH |
| **Recovery** | Set `VERCEL_TOKEN` in `.env.local` |

---

### computer_control

Desktop control: screenshot, click, type, scroll, open applications.

| | |
|---|---|
| **Provider** | `computer_use` |
| **Status** | LIVE |
| **MCP prefix** | `mcp__computer-use__` |
| **Critical** | False |
| **Policy** | `block_if_unavailable: false` |
| **Severity** | MEDIUM |

---

### visualization

Render SVG and HTML widgets inline in conversation.

| | |
|---|---|
| **Provider** | `visualize` |
| **Status** | LIVE |
| **MCP prefix** | `mcp__visualize__` |
| **Critical** | False |
| **Policy** | `block_if_unavailable: false` |
| **Severity** | LOW |

---

### scheduling

Create and manage scheduled cloud tasks/routines.

| | |
|---|---|
| **Provider** | `scheduled_tasks` |
| **Status** | LIVE |
| **MCP prefix** | `mcp__scheduled-tasks__` |
| **Critical** | False |
| **Policy** | `block_if_unavailable: false` |
| **Severity** | LOW |

---

### design

UI component generation via 21st.dev Magic.

| | |
|---|---|
| **Provider** | `magic_21st` |
| **Status** | DEFERRED_PAID |
| **Critical** | False |
| **Policy** | `block_if_unavailable: false` — manual design is the fallback |
| **Severity** | MEDIUM |
| **Recovery** | Subscribe to 21st.dev and configure API key |

---

### database (not recommended)

Direct database access via Supabase MCP.

| | |
|---|---|
| **Provider** | `supabase` |
| **Status** | NOT_RECOMMENDED → CONFIG_ONLY |
| **Critical** | False |
| **Policy** | `block_if_unavailable: false` |
| **Severity** | LOW |
| **Note** | Prefer Drizzle/Prisma in code over direct MCP access |

---

### filesystem (not recommended)

File system operations outside the project directory.

| | |
|---|---|
| **Provider** | `filesystem` |
| **Status** | NOT_RECOMMENDED |
| **Policy** | `block_if_unavailable: false` |
| **Note** | Use Read/Write/Edit tools instead |

---

### cloud_storage (not recommended)

Google Drive MCP.

| | |
|---|---|
| **Provider** | `gdrive` |
| **Status** | NOT_RECOMMENDED |
| **Policy** | `block_if_unavailable: false` |
| **Note** | Not used in current pipeline |

---

### communication (not recommended)

Slack MCP.

| | |
|---|---|
| **Provider** | `slack` |
| **Status** | NOT_RECOMMENDED |
| **Policy** | `block_if_unavailable: false` |
| **Note** | Not used in current pipeline |

---

## Metrics CLI

```bash
# Summary of all resolution events
python tools/capability_metrics.py

# Critical capabilities only (exit 1 if any DEGRADED/MISSING)
python tools/capability_metrics.py --critical

# Last 20 events
python tools/capability_metrics.py --last 20

# Filter by capability
python tools/capability_metrics.py --capability browser

# JSON output
python tools/capability_metrics.py --json
```

Exit codes: `0` = healthy, `1` = critical capability degraded, `2` = no events recorded yet.

## Adding a New Capability

1. Add entry to `core/capabilities/registry.py`
2. Add entry to `config/capability.policy.yaml`
3. Export from `core/capabilities/__init__.py` if needed
4. Add contract test in `_qa/bloque-F20-capability-contracts.py`
5. Run `python tools/atlas_healthcheck.py` — must stay 25/25 PASS
