# ATLAS — AI Engineering Operating System

> **Give Claude a nervous system.**

ATLAS is not a chatbot wrapper. It's not a prompt template. It's not another collection of agent definitions.

ATLAS is an **operating system layer** built on top of Claude that transforms it into a structured, disciplined, multi-agent engineering team — with memory, security enforcement, capability abstractions, quality gates, and full observability.

You describe what you want to build. ATLAS plans it, architects it, builds it with visual QA, certifies it, and deploys it — without you writing a single line of code.

---

## The Problem

Claude is extraordinarily capable. But raw Claude has no memory between sessions, no team coordination, no security enforcement, no quality gates, no deployment pipeline, and no way to reliably build a complete software project without constant human steering.

Every developer who has tried to build something serious with Claude has hit the same wall:

- You lose context after 30 minutes
- Claude starts doing architecture when it should be writing tests
- Nobody is enforcing that QA passes before code ships
- One session starts over what the last one decided
- There's no way to know if the system is healthy

ATLAS exists to eliminate that wall.

---

## What ATLAS Is

**An orchestration and enforcement layer** that runs on top of Claude Code or Claude Desktop.

It adds:

| What | How |
|------|-----|
| **Persistent memory** | Engram MCP — decisions survive across sessions |
| **Team structure** | 25 specialized agents with defined roles and boundaries |
| **5-phase pipeline** | Plan → Architect → Build+QA → Certify → Deploy |
| **Security enforcement** | 13 hooks blocking destructive commands in real time |
| **Capability abstraction** | Stable API over MCPs with fallback chains |
| **Policy engine** | Declarative rules per capability — ALLOW / WARN / BLOCK |
| **Quality gates** | Every task goes through visual QA before advancing |
| **Full observability** | Healthcheck, metrics, dependency graph, event log |

---

## What ATLAS Is NOT

- **Not a replacement for Claude.** ATLAS extends Claude; it requires Claude Code or Claude Desktop.
- **Not a framework you import.** It's a configuration layer — agents, hooks, CLAUDE.md.
- **Not opinionated about your stack.** It adapts: Next.js, React Native, Phaser.js, Hono, Drizzle, whatever the project needs.
- **Not magic.** If Claude can't do something, ATLAS can't either. It makes Claude more reliable, not more capable.
- **Not a SaaS.** It runs entirely locally.

---

## Why This Is Not Just "Another Agent System"

Most agent repositories are collections of prompts. They add agents, but not discipline.

ATLAS adds **structural guarantees**:

1. **A hook that fires before every command** — and blocks `git push --force`, `rm -rf`, `chmod 777`, and other destructive patterns before they execute.
2. **A capability router** — so agents never call `mcp__playwright__browser_navigate` directly. They call `resolve_capability("browser")` and the system selects the best available provider with fallback.
3. **A policy engine** — so if the browser MCP goes down, ATLAS knows whether to WARN, DEGRADE, or BLOCK based on a declared policy, not per-agent ad-hoc logic.
4. **Phase gates** — the pipeline cannot advance from Architecture to Development until Architecture artifacts exist in memory. No skipping.
5. **A healthcheck with 25 checks** that validates the entire system state in one command.
6. **Architecture Decision Records** monitored by the self-auditor — if a decision's referenced files disappear, drift is detected automatically.

These aren't features you configure. They're invariants the system enforces.

---

## ATLAS vs. Everything Else

| | Claude Code | Cursor / Copilot | Other agent repos | **ATLAS** |
|---|---|---|---|---|
| Persistent memory | No | No | Rarely | Yes (Engram MCP) |
| Multi-agent pipeline | No | No | Sometimes | Yes (25 agents, 5 phases) |
| Security hooks | No | No | No | Yes (13 hooks, real-time) |
| Capability abstraction | No | No | No | Yes (F16–F19) |
| Policy engine | No | No | No | Yes (declarative YAML) |
| Phase gates | No | No | No | Yes (enforced) |
| Observability | No | No | No | Yes (metrics, graph, healthcheck) |
| Visual QA | No | No | No | Yes (Playwright, 3 viewports) |
| Architecture drift detection | No | No | No | Yes (ADR + self-auditor T9) |

Claude Code is the runtime. ATLAS is the operating system on top of it.

---

## Philosophy

**1. Fail-open.** Every feature has an `ATLAS_*_DISABLED=1` env var. Nothing ATLAS adds can break your base Claude. If a hook crashes, Claude proceeds. If a capability resolves wrong, the escape hatch is always available.

**2. Declarative over imperative.** Policies are YAML files. Agent behaviors are markdown files. Hard rules are JSON. No hidden logic in unreachable code paths.

**3. Invariants over best practices.** A QA suite, a healthcheck, and a drift detector that runs on every audit are worth more than a style guide that nobody reads.

**4. No agent does real work.** The orchestrator only coordinates. It never writes code, reads files, or makes architectural decisions. Every token the orchestrator uses inline is context wasted.

**5. Memory or it didn't happen.** Every significant decision goes into Engram with a `topic_key`. Every agent writes its result before returning. Every critical path has a disk fallback.

---

## Architecture

```
Developer
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Claude Session (Claude Code CLI / Claude Desktop)              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CLAUDE.md — System instructions (auto-read by Claude)  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Orquestador (Opus)                                    │    │
│  │  Central coordinator — runs the 5-phase pipeline       │    │
│  │  Reads DAG State from memory. Never does real work.    │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ spawns                                  │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  24 Sub-Agents (Sonnet/Opus, per role)                 │    │
│  │  Phase 1: project-manager-senior                       │    │
│  │  Phase 2: ux-architect, ui-designer, security-engineer │    │
│  │  Phase 3: dev-agents ↔ evidence-collector (QA loop)   │    │
│  │  Phase 4: seo, api-tester, performance, reality-check  │    │
│  │  Phase 5: git, deployer                                │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ calls                                   │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capability Router  (core/capabilities/router.py)      │    │
│  │  resolve_capability("browser")                         │    │
│  │    → Resolution(provider, status, fallback, action)    │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ evaluates                               │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Policy Engine  (core/capabilities/policy.py)          │    │
│  │  evaluate_capability("browser")                        │    │
│  │    → PolicyDecision(ALLOW | WARN | DEGRADED | BLOCK)   │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ logs to                                 │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capability Metrics  (.pipeline/capability-events.jsonl)│   │
│  │  python tools/capability_metrics.py                    │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ backed by                               │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Registries                                            │    │
│  │  • Projects Registry  (config/projects.registry.yaml)  │    │
│  │  • Skills Registry    (config/skills.registry.yaml)    │    │
│  │  • MCP Registry       (config/mcp.registry.yaml)       │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ connects to                             │
│                       ▼                                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  MCP Layer                                             │    │
│  │  • engram (memory)       • playwright (browser)        │    │
│  │  • context7 (docs)       • github (repository)         │    │
│  │  • computer-use (desktop) • notion (projects)          │    │
│  └────────────────────┬───────────────────────────────────┘    │
│                       │ invokes                                 │
│                       ▼                                         │
│  Provider → CLI → Runtime                                       │
└─────────────────────────────────────────────────────────────────┘
         │
         │  every tool call intercepted by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Hook System  (.claude/hooks/)                                  │
│  block-no-verify.js  — BLOCKS destructive commands             │
│  config-protection.js — BLOCKS secret file writes              │
│  quality-gate.js     — WARNS on debugger / @ts-ignore          │
│  cost-tracker.js     — LOGS every tool call                    │
│  + 9 more reactive hooks                                        │
└─────────────────────────────────────────────────────────────────┘
```

### The 5 Phases

```
Phase 1  Planning       → project-manager-senior
                          Tasks, acceptance criteria, stack decision

Phase 2  Architecture   → ux-architect → ui-designer + security-engineer (parallel)
                          CSS foundation, design system, threat model

Phase 2B Visual Assets  → brand-agent → logo + image + video (optional)
                          Brand identity, AI-generated assets

Phase 3  Dev + QA Loop  → dev-agents ↔ evidence-collector
                          Build → Visual QA → Fix → Repeat (max 3 retries)

Phase 4  Certification  → seo-discovery + api-tester + performance + reality-checker
                          SEO, API coverage, Core Web Vitals, final gate

Phase 5  Deployment     → git (user confirms) → deployer (user confirms)
                          Commit, push, deploy to Vercel
```

---

## Quick Start

**Prerequisites:** Claude Code CLI (Linux/macOS) or Claude Desktop (Windows), Python 3.10+, Node.js 18+, Go 1.21+ (for Engram), git

```bash
# 1. Clone
git clone https://github.com/your-org/atlas.git
cd atlas

# 2. Install
bash install.sh          # Linux/macOS
# Windows: follow install/windows.md

# 3. Verify
python tools/atlas_healthcheck.py

# 4. Start
# Open Claude in this directory and say:
# "modo orquestador — quiero crear [your idea]"
```

→ Full installation guide: [INSTALL.md](INSTALL.md)
→ Post-install checklist: [FIRST_RUN.md](FIRST_RUN.md)
→ Troubleshooting: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Usage

The system has two modes:

| Mode | When | How |
|------|------|-----|
| **Normal** | Questions, fixes, reviews | Just talk to Claude |
| **Orchestrator** | Complete projects end-to-end | Say: *"modo orquestador — quiero crear X"* |

**New project:**
```
modo orquestador — quiero crear un SaaS de gestión de inventario
```

**Resume existing project:**
```
retomar [project-name]
```

The orchestrator reads project state from memory and resumes exactly where it left off.

---

## System Health

At any time:

```bash
# Full system health (25 checks, exit 0 = healthy)
python tools/atlas_healthcheck.py

# Capability status (all 14 capabilities)
python tools/capability_metrics.py --critical

# Dependency tree
python tools/dependency_graph.py --broken

# Architecture drift (ADRs vs. runtime)
# → Self-auditor T9, run via Claude: "ejecuta self-auditor"
```

---

## Extend ATLAS

| What to extend | Where | Guide |
|---|---|---|
| Add a new agent | `.claude/agents/` | [docs/AGENTS.md](docs/AGENTS.md) |
| Add a new capability | `core/capabilities/registry.py` | [docs/CAPABILITIES.md](docs/CAPABILITIES.md) |
| Add a new MCP | `config/mcp.registry.yaml` | [docs/MCP.md](docs/MCP.md) |
| Add a new hook | `.claude/hooks/` | [docs/HOOKS.md](docs/HOOKS.md) |
| Add a new skill | `config/skills.registry.yaml` | [docs/SKILLS.md](docs/SKILLS.md) |
| Record an architecture decision | `ADR/` | [ADR/0000-adr-template.md](ADR/0000-adr-template.md) |

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| [VISION.md](VISION.md) | Why ATLAS exists and where it's going |
| [INSTALL.md](INSTALL.md) | Complete installation guide (all platforms) |
| [FIRST_RUN.md](FIRST_RUN.md) | What to do right after installing |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Internal design, layers, invariants |
| [FLOWS.md](FLOWS.md) | End-to-end request flows with diagrams |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common problems and fixes |
| [FAQ.md](FAQ.md) | Frequently asked questions |
| [GLOSSARY.md](GLOSSARY.md) | Definitions for all ATLAS concepts |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [ROADMAP.md](ROADMAP.md) | What's coming and what blocks v1.0 |
| [docs/CAPABILITIES.md](docs/CAPABILITIES.md) | All 14 capabilities, providers, policies |
| [docs/MCP.md](docs/MCP.md) | MCP inventory with install/verify steps |
| [docs/AGENTS.md](docs/AGENTS.md) | All 25 agents, roles, tools |
| [docs/HOOKS.md](docs/HOOKS.md) | All 16 hooks, behavior, writing guide |
| [docs/SKILLS.md](docs/SKILLS.md) | Skills registry, creating skills |
| [ADR/](ADR/) | Architecture Decision Records |

---

## Credits

- [Engram](https://github.com/Gentleman-Programming/engram) — persistent memory MCP by Gentleman Programming
- [pixel-agents](https://github.com/pablodelucca/pixel-agents) — pixel art office (Pixel Bridge adapted from this)
- [Agency Agents](https://github.com/msitarzewski/agency-agents) — specialized agents inspiration
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) — DAG State pattern inspiration

---

## License

MIT
