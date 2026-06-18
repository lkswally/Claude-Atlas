# ATLAS — AI Development OS

**An autonomous multi-agent system for building complete software projects from idea to deployment.**

A central orchestrator coordinates 24 specialized AI sub-agents (25 entities total) through a 5-phase pipeline: planning, architecture, development with visual QA, certification, and deployment. 13 reactive hooks enforce security, quality gates, and cost tracking in real time. A capability abstraction layer decouples agents from provider internals, with declarative policies and full observability. Persistent memory via Engram MCP enables session continuity and cross-agent coordination.

Compatible with **Linux (Claude Code CLI)** and **Windows (Claude Desktop)**.

---

## Key Features

- **25 specialized agents** — 1 orchestrator + 24 sub-agents, each with defined tools and responsibilities
- **13 references** — shared protocol, auth, animation, design systems, creative coding, and more (38 files total)
- **5-phase pipeline** — Planning, Architecture, Dev+QA loop, Certification, Deployment
- **13 reactive hooks + 3 utilities** — Security blocks, quality gates, cost tracking, context management
- **Capability system** — Stable API over MCPs with fallback chains, policy engine, and metrics (F16–F19)
- **Persistent memory** — Engram MCP for cross-session state, DAG-based progress tracking
- **Python tools layer** — Healthcheck, dispatcher, capability metrics, dependency graph, skills registry
- **Adaptive stack** — Next.js, React Native, Phaser.js, Hono, Drizzle, and more, chosen per project
- **Creative pipeline** — AI-generated brand identity, logos, images, and video with fallback chains

---

## Pipeline

```
Phase 1: Planning        -> project-manager-senior
Phase 2: Architecture    -> ux-architect -> ui-designer + security-engineer
Phase 2B: Visual Assets  -> brand-agent -> (user approval) -> logo + image -> video
Phase 3: Dev <-> QA Loop -> dev-agents <-> evidence-collector (max 3 retries)
Phase 4: Certification   -> seo + api-tester + performance + reality-checker
Phase 5: Deployment      -> git -> deployer (with user confirmation)
```

---

## Agent Catalog

| Phase | Agent | Role |
|:-----:|-------|------|
| * | `orquestador` | Central coordinator, manages all 5 phases, never does real work |
| 1 | `project-manager-senior` | Converts ideas into granular tasks with acceptance criteria |
| 2 | `ux-architect` | CSS foundation: tokens, layout, themes, breakpoints |
| 2 | `ui-designer` | Visual design system, components, WCAG AA accessibility |
| 2 | `security-engineer` | STRIDE threat model, OWASP Top 10, security headers |
| 2B | `brand-agent` | Brand identity: palette, typography, tone, personality |
| 2B | `image-agent` | Hero images via Gemini/HuggingFace FLUX.1 |
| 2B | `logo-agent` | SVG logos (FLUX.1 + vtracer vectorization) |
| 2B | `video-agent` | Background videos (Replicate LTXVideo / CSS fallback) |
| 3 | `frontend-developer` | React/Vue/TS, Tailwind, shadcn/ui, Zustand, TanStack Query |
| 3 | `backend-architect` | Hono/Express, Drizzle/Prisma, tRPC, PostgreSQL, Better Auth |
| 3 | `rapid-prototyper` | Multi-stack MVPs for fast validation |
| 3 | `mobile-developer` | React Native + Expo SDK 52+, NativeWind 4, Expo Router |
| 3 | `game-designer` | Game Design Document: mechanics, loops, economy, balance |
| 3 | `xr-immersive-developer` | Phaser.js, PixiJS, Canvas API, WebGL standalone games |
| 3 | `codepen-explorer` | Searches and extracts visual effects from CodePen via Playwright |
| 3 | `build-resolver` | Diagnoses and fixes build failures automatically |
| 3 | `evidence-collector` | Visual QA with Playwright MCP, screenshots across 3 viewports |
| 4 | `seo-discovery` | SEO audit, meta tags, JSON-LD, sitemap, llms.txt, AI discovery |
| 4 | `api-tester` | Endpoint coverage, OWASP API Top 10, P95 latency |
| 4 | `performance-benchmarker` | Core Web Vitals, Lighthouse, bundle analysis |
| 4 | `reality-checker` | Final pre-production gate with visual evidence |
| 5 | `git` | Commit + push to GitHub, branch management |
| 5 | `deployer` | Deploy to Vercel + Git Integration for auto-deploy |
| -- | `self-auditor` | Validates system health: agents, hooks, Engram, ADRs, architecture drift |

### Technical References (13 files)

| File | Content |
|------|---------|
| `agent-protocol` | Shared protocol: Engram 2-step reads, Return Envelope, capability API |
| `better-auth-reference` | Better Auth 1.5 + Supabase + Vercel integration |
| `better-gsap-reference` | GSAP Tier 3: useGSAP, ScrollTrigger, SplitText, Next.js gotchas |
| `react-patterns-reference` | React 19, Next.js 15/16, Tailwind 4, Zustand 5 |
| `redis-patterns-reference` | Cache-aside, Pub/Sub, HyperLogLog, cursor pagination |
| `pocketbase-reference` | PocketBase boolean gotchas, rules, auth, Docker, HTTPS |
| `devops-vps-reference` | Mixed Content HTTPS, Oracle Cloud, nginx, Let's Encrypt |
| `nothing-design-reference` | Nothing Design System v3.0.0 — tokens, components, platform mapping |
| `scroll-storytelling-reference` | Lenis, GSAP ScrollTrigger pinning, snap, horizontal scroll, parallax |
| `advanced-effects-reference` | Lottie, Rive, cursor effects, magnetic buttons, micro-interactions |
| `creative-coding-reference` | p5.js, GLSL shaders, generative art, particle systems |
| `reactive-audio-reference` | Tone.js, Web Audio API, audio visualization, sound design |
| `agent-protocol` | Capability system usage, Return Envelope, event log, policy decisions |

---

## Capability System (F16–F19)

ATLAS uses a **capability abstraction layer** that decouples agents from MCP internals. Instead of calling `mcp__playwright__browser_navigate`, agents call `resolve_capability("browser")` and get a `Resolution` with the best available provider, its status, and an optional fallback.

```python
from core.capabilities.router import resolve_capability, resolve_with_policy

# Basic: get best available provider
resolution = resolve_capability("browser")
# -> Resolution(provider="playwright", status="LIVE", fallback=..., action="USE_LIVE")

# Policy-aware: includes decision outcome
resolution, decision = resolve_with_policy("memory")
# -> decision.is_usable  # True for ALLOW/WARN/DEGRADED
# -> decision.is_blocking  # True for BLOCK only
```

### Capability Status

| Status | Meaning |
|--------|---------|
| `LIVE` | Provider is installed and active |
| `CONFIG_ONLY` | Provider works but needs configuration |
| `PENDING_TOKEN` | Needs API token or auth |
| `DEFERRED_PAID` | Available but costs money; not activated by default |
| `UNAVAILABLE` | Not installed or unreachable |

### Policy Outcomes

Declared in `config/capability.policy.yaml`. Each capability has `critical`, `block_if_unavailable`, `severity`, and `recovery_hint`.

| Outcome | Meaning |
|---------|---------|
| `ALLOW` | Provider is LIVE and policy is satisfied |
| `WARN` | Provider has issues but the task can proceed with care |
| `DEGRADED` | Fallback provider active — reduced functionality |
| `BLOCK` | `block_if_unavailable=true` and no usable provider |
| `MISSING_POLICY` | Capability not declared in policy file |

### Metrics

```bash
python tools/capability_metrics.py            # summary of all resolution events
python tools/capability_metrics.py --critical  # check critical capabilities only
python tools/capability_metrics.py --json      # machine-readable output
```

---

## Hook System

13 reactive hooks intercept tool calls in real time. 3 additional utilities run on demand. Configured in `~/.claude/settings.json`, scripts live in `~/.claude/hooks/`.

### Reactive Hooks

| Hook | Type | Action |
|------|------|--------|
| `block-no-verify` | PreToolUse | **BLOCKS** `git --no-verify`, `rm -rf`, `git reset --hard`, `DROP TABLE`, `chmod 777`, `curl\|sh`, force-push with `-C` flag, `chown -R` |
| `config-protection` | PreToolUse | **BLOCKS** edits to `.env`, `.pem`, `.key`, credentials. **WARNS** on linting config changes |
| `pipeline-rules` | PreToolUse | **BLOCKS** hard rule violations (force-push main, cross-repo commits). **WARNS** on unused skills registry |
| `delegation-tracker` | PreToolUse | **WARNS** on agent delegation loops: `escalation_needed`, `pause_recommended`, `fresh_review_recommended` |
| `quality-gate` | PostToolUse | **WARNS** on debugger, `.only()`, `@ts-ignore`, hardcoded secrets |
| `console-log-warning` | PostToolUse | **WARNS** on `console.log/warn/error` in production code (ignores tests) |
| `cost-tracker` | PostToolUse | **LOGS** each tool call with category, sub-agent, model (async) |
| `qa-auto-audit` | PostToolUse | **AUDITS** mandatory helpers after agent spawn; emits WARN if missing |
| `suggest-compact` | PostToolUse | **WARNS** every ~50 tool calls with pipeline phase context (async) |
| `pre-compact-engram` | PreCompact | **SAVES** snapshot to disk + **INSTRUCTS** Claude to dual-write DAG State before compaction |
| `session-summary` | Stop | **LOGS** session activity in JSONL for recovery (async) |
| `engram-sync` | Stop | **SYNCS** Engram memories to GitHub automatically (async, 60s timeout) |
| `session-start-context` | Notification | **LOADS** previous session context + hook health check at startup |

### Manual Utilities

| Utility | Command | Purpose |
|---------|---------|---------|
| `audit-system` | `node ~/.claude/hooks/audit-system.js` | Validates system integrity: agents, hooks, settings, protocols |
| `cost-report` | `node ~/.claude/hooks/cost-report.js` | Tool usage breakdown by category, sub-agent, frequency |
| `learning-index` | `node ~/.claude/hooks/learning-index.js` | Local discovery index with auto-tagging by technology |

**Behavior**: Exit 2 = BLOCK | Exit 0 + stderr = WARN | Fail-open (never breaks the flow)

---

## Python Tools

The `tools/` layer handles complex runtime logic that JS hooks cannot: registries, metrics, graph analysis, health checks, dispatch validation.

| Tool | Command | Purpose |
|------|---------|---------|
| `atlas_healthcheck.py` | `python tools/atlas_healthcheck.py` | 25-check system health gate (capabilities, hooks, MCPs, QA) |
| `atlas_dispatcher.py` | `python tools/atlas_dispatcher.py check-phase ...` | Phase gate enforcement, Return Envelope validation, E2E flows |
| `capability_metrics.py` | `python tools/capability_metrics.py` | Resolution event reader: rates, fallback usage, critical status |
| `dependency_graph.py` | `python tools/dependency_graph.py` | Agent→Capability→Policy→Provider→MCP→CLI→Binary tree |
| `skills_registry.py` | `python tools/skills_registry.py stats` | Skills catalog lookup and usage logging |
| `design_quality_enforcement.py` | `python tools/design_quality_enforcement.py src/` | Anti-generic detector: fonts, colors, layouts, patterns |

### Healthcheck

```bash
# Full system health (25 checks)
python tools/atlas_healthcheck.py

# Expected output: 25/25 PASS, exit code 0
# Any FAIL = something needs attention before production use
```

---

## Architecture

```
~/.claude/
├── agents/            # 25 agents + 13 references = 38 files
├── hooks/             # 13 reactive hooks + 3 manual utilities
├── settings.json      # hook config + Engram MCP
├── settings.local.json  # agent permissions
└── codepen-vault/     # approved CodePen effects

{working-directory}/   # ATLAS project root
├── core/
│   └── capabilities/  # F16-F19: registry, router, events, policy
├── tools/             # Python tools layer
├── config/            # capability.policy.yaml, phase_playbook.json
├── _qa/               # QA suites (bloque-F*.py)
├── ADR/               # Architecture Decision Records
├── agents/            # mirror of ~/.claude/agents/ (drift-detected)
├── hooks/             # mirror of ~/.claude/hooks/
└── CLAUDE.md          # system instructions (auto-read by Claude)
```

### Model Routing

| Model | Agents | Criteria |
|-------|--------|----------|
| **Opus** | orchestrator, project-manager-senior, security-engineer, game-designer, reality-checker | Complex architectural decisions, planning, threat modeling, final certification |
| **Sonnet** | All others (20 agents) | Defined task execution, QA, utilities, creative |

### Key Rules

- The orchestrator **never** does real work — only coordinates
- Sub-agents return **only short summaries** (status + files + issues)
- Only `evidence-collector` and `reality-checker` perform visual QA
- Only `git` makes commits/pushes — never a dev agent
- Only `deployer` deploys to Vercel
- `git` and `deployer` act **only with user confirmation**
- Each dev task passes through `evidence-collector` before advancing (max 3 retries)
- The orchestrator does not activate `git` until `evidence-collector` returns PASS

---

## Installation

### Prerequisites

| Platform | Required | Download |
|----------|----------|----------|
| **Linux** | Claude Code CLI, git, Node.js, Python 3.10+ | [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) |
| **Windows** | Claude Desktop, Git for Windows (includes Git Bash), Node.js, Python 3.10+ | [Claude Desktop](https://claude.ai/download) |

> Claude Code (Linux) or Claude Desktop (Windows) must be installed first. This system extends Claude with agents and hooks.

### CLAUDE.md — Where It Lives

CLAUDE.md contains all system instructions. Claude reads it automatically from the **working directory** (project folder).

| Platform | Installed to | Notes |
|----------|-------------|-------|
| **Linux** | `~/CLAUDE.md` (global) | Claude Code reads it from any directory |
| **Windows** | `~/CLAUDE.md` (global) | Includes Windows overrides (preview servers, ports, launch.json) |

### Post-Install Verification

```bash
# Agents installed (should be 38: 25 agents + 13 references)
ls ~/.claude/agents/*.md | wc -l

# Hooks installed (should be 16: 13 reactive + 3 utilities)
ls ~/.claude/hooks/*.js | wc -l

# System health check
python tools/atlas_healthcheck.py

# Tools available
git --version && node --version && python --version

# Manual audit
node ~/.claude/hooks/audit-system.js
```

---

## Configuration

### Engram MCP (required)

Engram is the persistent memory system that lets the orchestrator and agents remember decisions, progress, and context across sessions. Configured automatically during installation via `settings.json`.

### Engram Sync (optional)

The `engram-sync` hook automatically pushes Engram memories to a private GitHub repo when a session ends.

1. Create a private GitHub repo (e.g., `my-engram-sync`)
2. Initialize: `cd ~/.engram && git init && git remote add origin https://github.com/YOUR_USER/my-engram-sync.git`
3. The hook handles the rest automatically

### Creative Pipeline (optional)

Required only for Phase 2B (AI-generated logos, images, videos).

| Variable | Service | Cost |
|----------|---------|------|
| `GEMINI_API_KEY` | Google AI Studio | ~$0.02–0.04/image |
| `HF_TOKEN` | HuggingFace | Free tier |
| `REPLICATE_API_TOKEN` | Replicate | ~$0.05/video |

At least one image key (`GEMINI_API_KEY` or `HF_TOKEN`) required. Gemini is primary; HuggingFace is fallback.

### Environment Variables — Escape Hatches

All major features support `ATLAS_*_DISABLED=1` for emergency bypass:

| Variable | Disables |
|----------|---------|
| `ATLAS_CAPABILITIES_DISABLED=1` | Capability router (raw MCP calls only) |
| `ATLAS_CAPABILITY_POLICY_DISABLED=1` | Policy engine (all caps return ALLOW) |
| `ATLAS_CAPABILITY_EVENTS_DISABLED=1` | Event logging |
| `ATLAS_HARD_RULES_DISABLED=1` | Hard rules hook |
| `ATLAS_SKILLS_REGISTRY_DISABLED=1` | Skills registry |

---

## Usage

| Mode | When to Use | How to Activate |
|------|------------|----------------|
| **Normal** | Questions, fixes, reviews, technical chat | Default — just talk |
| **Orchestrator** | Complete software projects end-to-end | Say: "modo orquestador", "activa el pipeline", or "nuevo proyecto completo: X" |

```
modo orquestador -- quiero crear [your idea]
retomar [project-name]   # resume from where it left off
```

---

## Pipeline Resilience

| Mechanism | What It Solves |
|-----------|---------------|
| **Phase Gates** | Verifies outputs from the previous phase exist before advancing |
| **Capability Fallbacks** | If primary MCP fails, router selects next provider automatically |
| **Policy Engine** | Declarative BLOCK/WARN/DEGRADED decisions without per-agent logic |
| **Error Recovery** | Agent crash → orchestrator checks Engram, recovers, re-delegates |
| **Graceful Degradation** | Engram down → local disk fallback; Playwright unavailable → code-only QA |
| **Rejection Workflows** | Up to 3 retries for rejected creative assets with strategy changes |
| **NEEDS WORK Flow** | reality-checker fails → orchestrator returns to Phase 3 for affected tasks only |

---

## Adaptive Stack

| Layer | Options | Default |
|-------|---------|---------|
| Frontend | Next.js, SvelteKit, Nuxt, Astro, Vite+React | Next.js (apps), Vite+React (landing) |
| Backend | Hono, Express, Fastify | Hono (edge-ready) |
| Database | PostgreSQL, SQLite, Supabase | PostgreSQL (prod), Supabase (MVP) |
| ORM | Drizzle, Prisma | Drizzle (type-safe, edge) |
| Auth | Better Auth | Always (unless project has existing auth) |
| Mobile | React Native + Expo SDK 52+ | Expo (iOS + Android from one repo) |
| Games 2D | Phaser.js 3, PixiJS, Canvas API | Phaser.js |
| Games 3D | Three.js, Babylon.js | Three.js |
| Animation | CSS (Tier 1), Framer Motion (Tier 2), GSAP (Tier 3) | Escalate by complexity |
| Scroll | Lenis + GSAP ScrollTrigger | Lenis (storytelling), GSAP (pinning) |
| Creative | p5.js, GLSL shaders, Canvas 2D | p5.js (2D), Three.js shaders (3D) |
| Audio | Tone.js, Web Audio API | Tone.js (complete), Web Audio (simple) |

---

## Context Window Management

### Progressive DAG State Loading

| Level | What it loads | Tokens | When |
|-------|--------------|--------|------|
| **Light boot** | Current phase, task, stack, timestamp | ~50–100 | Always on resume |
| **Full boot** | Complete DAG State | ~500–2000 | Phase transitions, scope changes, certification |

### Dual-Write Pattern

```
Primary:  Engram MCP  ->  {proyecto}/estado  (searchable, cross-session)
Fallback: Local disk  ->  {project_dir}/.pipeline/estado.yaml
```

### Token Budget Strategy

| Mechanism | Tokens Saved |
|-----------|-------------|
| Light vs full boot | ~400–1900 per resume |
| Short return envelopes | ~500–2000 per delegation |
| Screenshots to disk | ~5000+ per QA cycle |
| PreCompact save-then-compact | 100% context recovery |

---

## Architecture Decision Records

Significant architectural decisions are documented in `ADR/` with status, context, alternatives, and rollback plan.

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](ADR/0001-capability-router-abstraction.md) | Capability Router Abstraction | ACCEPTED |
| [0002](ADR/0002-jsonl-event-logging.md) | JSONL Append-Only Event Logging | ACCEPTED |
| [0003](ADR/0003-declarative-capability-policy.md) | Declarative Capability Policy Engine | ACCEPTED |
| [0004](ADR/0004-python-tools-layer.md) | Python Tools Layer for Complex Logic | ACCEPTED |

---

## Credits

- [Engram](https://github.com/Gentleman-Programming/engram) by Gentleman Programming — persistent memory MCP
- [pixel-agents](https://github.com/pablodelucca/pixel-agents) by @pablodelucca — pixel art office (Pixel Bridge adapted from this)
- [Agency Agents](https://github.com/msitarzewski/agency-agents) — specialized agents with metrics (inspiration)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) — DAG State, minimal handoffs, Engram (inspiration)

---

## License

MIT
