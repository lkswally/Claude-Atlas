# Claude Atlas System

**An autonomous multi-agent system for building complete software projects from idea to deployment.**

A central orchestrator coordinates 24 specialized AI sub-agents (25 entities total) through a 5-phase pipeline: planning, architecture, development with visual QA, certification, and deployment. 13 reactive hooks enforce security, quality gates, and cost tracking in real time. Persistent memory via Engram MCP enables session continuity and cross-agent coordination.

Compatible with **Linux (Claude Code CLI)** and **Windows (Claude Desktop)**.

---

## Key Features

- **25 specialized agents** -- 1 orchestrator + 24 sub-agents, each with defined tools and responsibilities
- **12 technical references** -- shared protocol, auth, animation, design systems, creative coding, and more
- **5-phase pipeline** -- Planning, Architecture, Dev+QA loop, Certification, Deployment
- **13 reactive hooks** -- Security blocks, quality gates, cost tracking, context management
- **Persistent memory** -- Engram MCP for cross-session state, DAG-based progress tracking
- **Visual agent office** -- Pixel Bridge (optional pixel art visualization of agent activity)
- **Adaptive stack** -- Next.js, React Native, Phaser.js, Hono, Drizzle, and more, chosen per project
- **Creative pipeline** -- AI-generated brand identity, logos, images, and video with fallback chains

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
| -- | `self-auditor` | Validates system health: agents, hooks, settings, protocols |

### Technical References (12 files)

| File | Content |
|------|---------|
| `agent-protocol` | Shared protocol: Engram 2-step reads, Return Envelope, universal rules |
| `better-auth-reference` | Better Auth 1.5 + Supabase + Vercel integration |
| `better-gsap-reference` | GSAP Tier 3: useGSAP, ScrollTrigger, SplitText, Next.js gotchas |
| `react-patterns-reference` | React 19, Next.js 15/16, Tailwind 4, Zustand 5 |
| `redis-patterns-reference` | Cache-aside, Pub/Sub, HyperLogLog, cursor pagination |
| `pocketbase-reference` | PocketBase boolean gotchas, rules, auth, Docker, HTTPS |
| `devops-vps-reference` | Mixed Content HTTPS, Oracle Cloud, nginx, Let's Encrypt |
| `nothing-design-reference` | Nothing Design System v3.0.0 -- tokens, components, platform mapping |
| `scroll-storytelling-reference` | Lenis, GSAP ScrollTrigger pinning, snap, horizontal scroll, parallax |
| `advanced-effects-reference` | Lottie, Rive, cursor effects, magnetic buttons, micro-interactions |
| `creative-coding-reference` | p5.js, GLSL shaders, generative art, particle systems |
| `reactive-audio-reference` | Tone.js, Web Audio API, audio visualization, sound design |

---

## Hook System

13 reactive hooks intercept tool calls in real time. Configured in `~/.claude/settings.json`, scripts live in `~/.claude/hooks/`.

| Hook | Type | Matcher | Action |
|------|------|---------|--------|
| `block-no-verify` | PreToolUse | Bash | **BLOCKS** git --no-verify, rm -rf, git reset --hard, DROP TABLE, chmod 777, curl\|sh |
| `config-protection` | PreToolUse | Write/Edit | **BLOCKS** edits to .env, .pem, .key, credentials. **WARNS** on linting config changes |
| `quality-gate` | PostToolUse | Write/Edit | **WARNS** on debugger, .only(), @ts-ignore, hardcoded secrets |
| `console-log-warning` | PostToolUse | Write/Edit | **WARNS** on console.log/warn/error in production code (ignores tests) |
| `suggest-compact` | PostToolUse | global | **WARNS** every ~50 tool calls with pipeline phase context (async) |
| `pre-compact-engram` | PreCompact | lifecycle | **SAVES** snapshot to disk + **INSTRUCTS** Claude to dual-write DAG State before compaction (v2.2) |
| `cost-tracker` | PostToolUse | global | **LOGS** each tool call with category, sub-agent, model (async) |
| `session-summary` | Stop | lifecycle | **LOGS** session activity in JSONL for recovery (async) |
| `engram-sync` | Stop | lifecycle | **SYNCS** Engram memories to GitHub automatically (async, 60s timeout) |
| `session-start-context` | Notification | lifecycle | **LOADS** previous session context + hook health check at startup |
| `audit-system` | Manual | -- | Validates system integrity: agents, hooks, settings, protocols |
| `cost-report` | Manual | -- | Tool usage breakdown by category, sub-agent, frequency |
| `learning-index` | Manual | -- | Local discovery index with auto-tagging by technology |

---

## Installation

### Prerequisites

Before starting, you need:

| Platform | You need installed first | Download |
|----------|------------------------|----------|
| **Linux** | **Claude Code CLI**, git, Node.js | [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) |
| **Windows** | **Claude Desktop**, Git for Windows (includes Git Bash), Node.js | [Claude Desktop](https://claude.ai/download), [Git](https://git-scm.com/download/win), [Node.js](https://nodejs.org) |

> **Important:** Claude Code (Linux) or Claude Desktop (Windows) must be installed first. This system extends Claude with agents and hooks -- it does not work without it.

### Linux (Claude Code)

Open a terminal and run:
```bash
git clone https://github.com/Emaleo0522/claude-vibecoding.git
cd claude-vibecoding
bash install/linux.sh
```

The script installs agents, hooks, CLAUDE.md, settings, and configures git/GitHub/Vercel authentication. Restart Claude Code when done.

### Windows (Claude Desktop)

Open **Git Bash** (installed with Git for Windows) and run:
```bash
git clone https://github.com/Emaleo0522/claude-vibecoding.git
cd claude-vibecoding
```

Then follow the step-by-step guide in [`install/windows.md`](install/windows.md). It walks you through everything with screenshots-friendly instructions.

### CLAUDE.md -- Where It Lives

CLAUDE.md contains all system instructions. Claude reads it automatically from the **working directory** (project folder).

| Platform | Installed to | Template | Notes |
|----------|-------------|----------|-------|
| **Linux** | `~/CLAUDE.md` (global) | `templates/global-claude.md` | Claude Code reads it from any directory |
| **Windows** | `~/CLAUDE.md` (global) | `templates/windows-claude.md` | Includes Windows overrides (preview servers, ports, launch.json) |

Both versions contain the same core system (pipeline, agents, hooks, Engram, stack). The Windows version adds the `Overrides Windows` section with `preview_start`, `cmd /c` wrappers, and port management via `netstat/taskkill`.

### Post-Install Verification

```bash
# Agents installed (should be 37: 25 agents + 12 references)
ls ~/.claude/agents/*.md | wc -l

# Hooks installed (should be 13)
ls ~/.claude/hooks/*.js | wc -l

# CLAUDE.md present
head -3 ~/CLAUDE.md

# Tools available
git --version && node --version && gh --version && vercel --version

# Full system health check (optional but recommended)
node ~/.claude/hooks/audit-system.js
```

---

## Configuration

### Engram MCP (required)

Engram is the persistent memory system that lets the orchestrator and agents remember decisions, progress, and context across sessions. Without it, every conversation starts from scratch.

It is configured automatically during installation via `settings.json`. On Windows, it also requires downloading the Engram binary separately (see `install/windows.md`).

### Engram Sync (optional)

The `engram-sync` hook automatically pushes Engram memories to a private GitHub repo when a session ends. This enables:
- **Cross-machine continuity** -- start on your desktop, resume on laptop
- **Backup** -- memories survive even if your local Engram DB is deleted

To set it up:
1. Create a private GitHub repo (e.g., `my-engram-sync`)
2. Initialize it in `~/.engram/`: `cd ~/.engram && git init && git remote add origin https://github.com/YOUR_USER/my-engram-sync.git`
3. The `engram-sync` hook (already installed) handles the rest automatically

### Creative Pipeline Environment Variables (optional)

Required only if your project uses AI-generated visual assets (Phase 2B: logos, images, videos).

| Variable | Service | Cost | How to get it |
|----------|---------|------|---------------|
| `GEMINI_API_KEY` | Google AI Studio | ~$0.02-0.04/image | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) -- requires billing enabled |
| `HF_TOKEN` | HuggingFace | Free | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `REPLICATE_API_TOKEN` | Replicate | ~$0.05/video | [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens) |

At least one image key (`GEMINI_API_KEY` or `HF_TOKEN`) is needed for the creative pipeline. If both are set, Gemini is primary with HuggingFace as fallback.

**Where to put them:**
- **Linux:** Add to `~/.bashrc` or `~/.zshrc`: `export GEMINI_API_KEY="your-key-here"`
- **Windows:** Add to system environment variables (Settings -> System -> About -> Advanced system settings -> Environment Variables), or create a file at `~/.claude/.env` with one variable per line: `GEMINI_API_KEY=your-key-here`

### Pixel Bridge (optional)

A pixel art office where agents walk to their desks when assigned tasks, report back to the orchestrator, and idle when inactive. Purely visual, does not affect pipeline operation.

Install during `linux.sh` (prompted) or follow the instructions in `install/windows.md`.

---

## Usage

The system operates in two modes:

| Mode | When to Use | How to Activate |
|------|------------|----------------|
| **Normal** | Questions, fixes, reviews, technical chat | Default -- just talk |
| **Orchestrator** | Complete software projects end-to-end | Say: "modo orquestador", "activa el pipeline", or "nuevo proyecto completo: X" |

### Starting a Project

```
modo orquestador -- quiero crear [your idea]
```

The system handles everything: plans tasks, designs architecture, implements with visual QA (max 3 retries per task), certifies (SEO, API, performance, final gate), and deploys to Vercel -- with your confirmation before git push and deploy.

### Resuming a Project

```
retomar [project-name]
```

The orchestrator reads the DAG State from Engram and resumes exactly where it left off, without re-executing completed phases or re-asking decided questions.

---

## Architecture

```
~/.claude/
|-- agents/            # 25 agents + 12 references = 37 files
|-- hooks/             # 13 reactive hooks
|-- settings.json      # hook config + Engram MCP
|-- settings.local.json # agent permissions
|-- codepen-vault/     # approved CodePen effects
|-- pixel-bridge/      # optional visual system
{working-directory}/
|-- CLAUDE.md          # system instructions (auto-read by Claude from the project dir)
```

### Model Routing

| Model | Agents | Criteria |
|-------|--------|----------|
| **Opus** | orchestrator, project-manager-senior, security-engineer, game-designer, reality-checker | Complex architectural decisions, planning, threat modeling, final certification |
| **Sonnet** | All others (20 agents) | Defined task execution, QA, utilities, creative |

### Key Rules

- The orchestrator **never** does real work -- only coordinates
- Sub-agents return **only short summaries** (status + files + issues)
- Only `evidence-collector` and `reality-checker` perform visual QA
- Only `git` makes commits/pushes -- never a dev agent
- Only `deployer` deploys to Vercel
- `git` and `deployer` act **only with user confirmation**
- Each dev task passes through `evidence-collector` before advancing (max 3 retries)
- The orchestrator does not activate `git` until `evidence-collector` returns PASS

---

## Adaptive Stack

The orchestrator selects the stack in Phase 1 based on project requirements. There is no fixed stack.

| Layer | Options | Default Preference |
|-------|---------|--------------------|
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

## Pipeline Resilience

| Mechanism | What It Solves |
|-----------|---------------|
| **Phase Gates** | Verifies outputs from the previous phase exist before advancing. Re-delegates if missing. |
| **Error Recovery** | If an agent crashes without returning a result, the orchestrator checks Engram, recovers what it can, and re-delegates. |
| **Graceful Degradation** | If Engram is down, uses local disk as fallback. If Playwright is unavailable, performs code-only QA. |
| **Rejection Workflows** | Up to 3 retries for rejected creative assets with escalating strategy changes. |
| **NEEDS WORK Flow** | If reality-checker does not certify, the orchestrator returns to Phase 3 only for affected tasks. |

---

## Context Window Management (v2.2)

The system uses several mechanisms to protect the context window from bloat and ensure state survives compaction events.

### Progressive DAG State Loading

The DAG State (project progress tracker) can grow to 10+ KB for advanced projects. Instead of loading it fully on every interaction, the orchestrator uses 2 levels:

| Level | What it loads | Tokens | When |
|-------|--------------|--------|------|
| **Light boot** | Current phase, current task/total, stack (1-liner), last save timestamp | ~50-100 | Always on resume |
| **Full boot** | Entire DAG State (completed phases, failed tasks, certifications, all decisions) | ~500-2000 | Phase transitions, escalations, scope changes, certification |

The orchestrator reads the full DAG State once at startup to extract the light summary, then retains only the summary + the observation ID. It re-reads the full state on demand when decisions require it.

### PreCompact Blocking (v2.2)

When Claude's context is about to be compacted (context window nearing capacity), the `pre-compact-engram` hook intercepts the event and:

1. **Saves a session snapshot** to disk (tool count, working directory, pipeline status)
2. **Emits a critical message** via stderr: `COMPACTION IMMINENT -- SAVE STATE NOW`

This message instructs the orchestrator to immediately:
1. Save DAG State to Engram via `mem_update`
2. Write DAG State to disk at `{project_dir}/.pipeline/estado.yaml`
3. Save any unsaved discoveries or task progress

After saving, compaction is safe -- the Boot Sequence recovers from Engram or disk on the next interaction.

> **Why this matters:** Before v2.2, the hook only saved metadata (tool count, cwd). If the orchestrator hadn't done a dual-write recently, task progress could be lost during compaction. Now the hook actively forces a save before context is lost.

### Dual-Write Pattern

Critical state is always written to two locations:

```
Primary:  Engram MCP  ->  {proyecto}/estado  (searchable, cross-session)
Fallback: Local disk  ->  {project_dir}/.pipeline/estado.yaml
```

On recovery, the Boot Sequence checks Engram first, then falls back to disk. This survives MCP failures, network issues, and database locks.

### Token Budget Strategy

| Mechanism | Tokens Saved | How |
|-----------|-------------|-----|
| Light boot vs full boot | ~400-1900 per resume | Only load full DAG when decisions needed |
| Short return envelopes | ~500-2000 per delegation | Sub-agents return status + files + issues, never full code |
| Screenshots to disk | ~5000+ per QA cycle | Images saved as files, only paths passed in context |
| Selective drawer reads | ~200-500 per agent | Each agent reads only its relevant Engram drawers |
| PreCompact save-then-compact | 100% context recovery | State persisted before compaction, nothing lost |

---

## Credits

- [Engram](https://github.com/Gentleman-Programming/engram) by Gentleman Programming -- persistent memory MCP
- [pixel-agents](https://github.com/pablodelucca/pixel-agents) by @pablodelucca -- pixel art office (Pixel Bridge adapted from this)
- [Agency Agents](https://github.com/msitarzewski/agency-agents) -- specialized agents with metrics (inspiration)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) -- DAG State, minimal handoffs, Engram (inspiration)

---

## License

MIT
