# MCP Reference

MCP (Model Context Protocol) servers provide tools that ATLAS agents call. This document inventories all MCPs used, their status, and how to install/verify each.

> **Note:** Agents should not call MCP tools directly. Use `resolve_capability()` from `core.capabilities.router` — it selects the right provider and logs the event.

---

## MCP Inventory

| MCP | Capability | Status | Required |
|-----|-----------|--------|---------|
| engram | memory | LIVE | Yes |
| playwright | browser (primary) | LIVE | For visual QA |
| claude_in_chrome | browser (fallback 1) | LIVE | No |
| claude_preview | browser (fallback 2) | LIVE | No |
| context7 | documentation | LIVE | Recommended |
| notion | project_management | LIVE | No |
| github | repository | PENDING_TOKEN | For git ops |
| vercel | deployment | PENDING_TOKEN | For deploy |
| computer-use | computer_control | LIVE | No |
| visualize | visualization | LIVE | No |
| scheduled-tasks | scheduling | LIVE | No |
| magic_21st | design | DEFERRED_PAID | No |
| supabase | database | NOT_RECOMMENDED | No |

---

## Engram (memory)

**Purpose:** Persistent memory across sessions. Used by virtually every agent for reading/writing project state.

**Install:**
1. Download binary from [github.com/Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram/releases)
2. Place in PATH (e.g., `~/.local/bin/engram` on Linux, `C:\tools\engram.exe` on Windows)
3. Register in `~/.claude/settings.json`:
   ```json
   "mcpServers": {
     "engram": {
       "command": "engram",
       "args": ["mcp"]
     }
   }
   ```

**Verify:**
```bash
engram doctor
# Expected: all checks green

# From Claude: mem_save + mem_search should round-trip correctly
```

**Test:** Self-auditor T3 (`node ~/.claude/hooks/audit-system.js`) runs a ping/save/search/get cycle.

---

## Playwright (browser)

**Purpose:** Headless browser automation — navigate, screenshot, click, evaluate JS. Used by evidence-collector, reality-checker, performance-benchmarker, codepen-explorer.

**Install:**
```bash
npx playwright install chromium
```

Playwright MCP is registered automatically when Claude Code is configured. Verify it appears in `.mcp.json` as `playwright`.

**Verify:**
```bash
# From Claude session, resolve_capability("browser") should return playwright
python -c "from core.capabilities.router import resolve_capability; r=resolve_capability('browser'); print(r.provider, r.status)"
# Expected: playwright LIVE
```

---

## Claude in Chrome (browser fallback)

**Purpose:** Interactive Chrome extension — real user-facing browsing, not headless.

**Install:** Install the Claude extension from Chrome Web Store. It appears as `Claude_in_Chrome` in the MCP list when connected.

**When used:** When playwright is not available or when interactive browsing is needed.

---

## Claude Preview (browser fallback 2)

**Purpose:** Preview dev server output inside Claude conversation.

**When used:** For frontend verification during active development on Windows (dev server running via `preview_start`).

---

## Context7 (documentation)

**Purpose:** Query live documentation for any library/framework — React, Next.js, Drizzle, Better Auth, etc.

**Install:**
Context7 is available as an MCP. Register with:
```json
"context7": {
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp"]
}
```

**Verify:**
```bash
python -c "from core.capabilities.router import resolve_capability; r=resolve_capability('documentation'); print(r.provider, r.status)"
# Expected: context7 LIVE
```

**Usage in agents:**
```
resolve-library-id → query-docs
```

---

## Notion (project_management)

**Purpose:** Create and manage Notion pages, databases, comments. Used for project tracking.

**Install:** Connect Notion integration in Claude settings. The MCP ID is a long UUID.

**Verify:**
```bash
python -c "from core.capabilities.router import resolve_capability; r=resolve_capability('project_management'); print(r.provider, r.status)"
```

---

## GitHub (repository)

**Purpose:** Repository operations — create repos, push code, manage PRs, read files.

**Status:** PENDING_TOKEN — requires a personal access token.

**Setup:**
1. Create token at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo` scope
2. Add to `.env.local`: `GITHUB_TOKEN=ghp_...`
3. Restart Claude

**Verify:**
```bash
python -c "from core.capabilities.policy import evaluate_capability; d=evaluate_capability('repository',_emit=False); print(d.decision)"
# With token: ALLOW
# Without token: WARN (not BLOCK — fallback to git CLI)
```

---

## Vercel (deployment)

**Purpose:** Deploy to Vercel — create deployments, manage domains, set environment variables.

**Status:** PENDING_TOKEN — requires a Vercel API token.

**Setup:**
1. Create token at [vercel.com/account/tokens](https://vercel.com/account/tokens)
2. Add to `.env.local`: `VERCEL_TOKEN=...`
3. Restart Claude

**Note:** The `deployer` agent uses the Vercel CLI (`vercel --prod`) as primary, not this MCP. MCP is for programmatic project management.

---

## Computer Use (computer_control)

**Purpose:** Desktop control — screenshot, click, type, scroll, open applications.

**Status:** LIVE — built-in to Claude on supported platforms.

**When used:** Automated desktop workflows, native app interaction, cross-app operations.

---

## Visualize (visualization)

**Purpose:** Render SVG and HTML widgets inline in conversation.

**Status:** LIVE — built-in to Claude.

**When used:** Dependency graphs, flowcharts, dashboards, interactive tools.

---

## Scheduled Tasks (scheduling)

**Purpose:** Create and manage scheduled cloud tasks/routines.

**Status:** LIVE — built-in to Claude.

---

## Not Recommended MCPs

These are registered in the capability registry but marked NOT_RECOMMENDED. They work but ATLAS agents should prefer alternatives.

| MCP | Capability | Reason |
|-----|-----------|--------|
| supabase | database | Use Drizzle/Prisma in code; direct MCP access bypasses type safety |
| filesystem | filesystem | Use Read/Write/Edit tools; MCP adds no value here |
| gdrive | cloud_storage | Not used in current pipeline |
| slack | communication | Not used in current pipeline |

---

## Healthcheck

`python tools/atlas_healthcheck.py` checks each MCP's functional status:

- `check_engram_connectivity()` — mem_save round-trip
- `check_playwright_availability()` — import and basic invocation
- `check_capability_metrics()` — events infrastructure
- `check_capability_policy()` — policy YAML + evaluator

Run after any MCP configuration change to confirm the system is healthy.
