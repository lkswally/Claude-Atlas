# ATLAS — Agent Reference

ATLAS has 25 agents (1 orchestrator + 24 sub-agents) and 13 technical reference files, totaling 38 files in `~/.claude/agents/`.

---

## The Orchestrator

### orquestador
**Model:** Opus | **Phase:** All

The central coordinator. Manages the 5-phase pipeline, reads/writes DAG State from Engram, spawns sub-agents, validates Return Envelopes, and enforces phase gates.

**What it NEVER does:** writes code, reads project files, makes implementation decisions, or performs any "real work." Every token the orchestrator spends on implementation is context wasted.

**How to activate:**
```
modo orquestador — quiero crear [your project]
retomar [project-name]
```

---

## Phase 1 — Planning

### project-manager-senior
**Model:** Sonnet | **Phase:** 1

Converts a project description into a granular task breakdown with acceptance criteria. Selects the tech stack based on requirements. Saves the task list and stack decision to Engram.

**Produces:** `{project}/tareas`, `{project}/stack`

---

## Phase 2 — Architecture

### ux-architect
**Model:** Sonnet | **Phase:** 2 (runs first, sequentially)

Creates the CSS foundation: design tokens, layout system, grid, breakpoints, color palette, typography scale. This output constrains what ui-designer can build — no design decisions happen without a foundation.

**Produces:** `{project}/css-foundation`

### ui-designer
**Model:** Sonnet | **Phase:** 2 (parallel with security-engineer)

Reads the CSS foundation and creates the design system: component library, WCAG AA accessibility, interaction patterns, visual hierarchy. Enforces reference-driven design (2–5 visual references with rationale).

**Produces:** `{project}/design-system`

### security-engineer
**Model:** Opus | **Phase:** 2 (parallel with ui-designer)

Performs STRIDE threat modeling and OWASP Top 10 analysis for the specific project. Defines security headers, authentication requirements, and data protection rules.

**Produces:** `{project}/security-spec`

---

## Phase 2B — Visual Assets (Optional)

### brand-agent
**Model:** Sonnet | **Phase:** 2B (runs first)

Creates brand identity: palette, typography, tone, personality, visual language. This is the gate before any visual asset generation — no logos or images without a brand.

**Produces:** `{project}/brand.json`

### image-agent
**Model:** Sonnet | **Phase:** 2B (parallel)

Generates hero images using Gemini API (primary) or HuggingFace FLUX.1 (fallback). Requires `GEMINI_API_KEY` or `HF_TOKEN`.

### logo-agent
**Model:** Sonnet | **Phase:** 2B (parallel)

Generates SVG logos using FLUX.1 + vtracer vectorization. Requires `HF_TOKEN`.

### video-agent
**Model:** Sonnet | **Phase:** 2B (sequential, last)

Generates background videos using Replicate LTXVideo. Falls back to CSS animations if `REPLICATE_API_TOKEN` is not set.

---

## Phase 3 — Development

### frontend-developer
**Model:** Sonnet | **Phase:** 3

Builds UI components: React/Vue/TS, Tailwind, shadcn/ui, Zustand, TanStack Query. Reads design system and security spec from Engram before writing any code.

### backend-architect
**Model:** Sonnet | **Phase:** 3

Builds APIs and data layers: Hono, Express, Drizzle, Prisma, tRPC, PostgreSQL. Implements Better Auth by default. Reads security spec.

### rapid-prototyper
**Model:** Sonnet | **Phase:** 3

Builds full-stack MVPs quickly when the project needs fast validation over polish. Used for proof-of-concept phases.

### mobile-developer
**Model:** Sonnet | **Phase:** 3

Builds mobile apps: React Native + Expo SDK 52+, NativeWind 4, Expo Router. Handles iOS and Android from one codebase.

### game-designer
**Model:** Opus | **Phase:** 3

Creates Game Design Documents: mechanics, loops, economy, difficulty curves, level design. Used before xr-immersive-developer builds the game.

### xr-immersive-developer
**Model:** Sonnet | **Phase:** 3

Builds games and interactive experiences: Phaser.js 3, PixiJS, Canvas API, WebGL, Three.js.

### codepen-explorer
**Model:** Sonnet | **Phase:** 3

Searches CodePen for visual effects using Playwright. Extracts and saves code to `.codepen-temp/{slug}/`. Only extracts — never adapts or modifies. frontend-developer reads and adapts.

### build-resolver
**Model:** Sonnet | **Phase:** 3

Diagnoses and fixes build failures: TypeScript errors, missing dependencies, configuration issues. Called automatically when a build fails.

### evidence-collector
**Model:** Sonnet | **Phase:** 3 (QA)

Visual QA agent. After each development task, navigates to the running app via Playwright and takes screenshots at 3 viewports (1280px, 768px, 375px). Returns PASS or FAIL with specific visual issues.

**The pipeline cannot advance until evidence-collector returns PASS.** Max 3 retries.

---

## Phase 4 — Certification

### seo-discovery
**Model:** Sonnet | **Phase:** 4

SEO audit: meta tags, Open Graph, JSON-LD structured data, sitemap.xml, robots.txt, llms.txt (for AI crawlers). Reports score and specific fixes.

### api-tester
**Model:** Sonnet | **Phase:** 4

API coverage: endpoint testing, OWASP API Top 10, P95 latency measurement, error handling verification.

### performance-benchmarker
**Model:** Sonnet | **Phase:** 4

Core Web Vitals measurement via Playwright: LCP, CLS, FID. Lighthouse score. Bundle size analysis against defined budgets (main < 250KB gzip).

### reality-checker
**Model:** Opus | **Phase:** 4 (final gate)

The last verification before deployment. Runs a complete end-to-end review: reads all certifications, takes final screenshots, compares against design system, and makes a CERTIFIED / NEEDS WORK decision. If NEEDS WORK, the orchestrator returns to Phase 3 for only the affected tasks.

---

## Phase 5 — Deployment

### git
**Model:** Sonnet | **Phase:** 5

Commits and pushes to GitHub. Creates PRs if needed. **Requires explicit user confirmation.** Never runs without the user approving the specific commit.

### deployer
**Model:** Sonnet | **Phase:** 5

Deploys to Vercel (`vercel --prod`) or other targets. Monitors deployment status and reports the live URL. **Requires explicit user confirmation.**

---

## Utility Agents

### self-auditor
**Model:** Sonnet | **Phase:** On demand

Meta-validation agent. Runs 9 checks on the ATLAS system itself: agent catalog sync, hook integrity, Engram connectivity, protocol compliance, return envelope validation, hook performance, cross-reference integrity, settings structure, and architecture drift (T9).

Run it: `ejecuta self-auditor`

---

## Technical Reference Files (13)

These are not agents — they're knowledge bases that agents reference.

| File | Used by | Content |
|------|---------|---------|
| `agent-protocol.md` | All agents | Engram 2-step read pattern, Return Envelope format, capability API |
| `better-auth-reference.md` | backend-architect, frontend-developer | Better Auth 1.5 + Supabase + Vercel |
| `better-gsap-reference.md` | frontend-developer | GSAP Tier 3: useGSAP, ScrollTrigger, SplitText |
| `react-patterns-reference.md` | frontend-developer | React 19, Next.js 15/16, Tailwind 4, Zustand 5 |
| `redis-patterns-reference.md` | backend-architect | Cache-aside, Pub/Sub, HyperLogLog |
| `pocketbase-reference.md` | backend-architect | PocketBase auth, rules, Docker |
| `devops-vps-reference.md` | deployer | Mixed Content HTTPS, nginx, Let's Encrypt |
| `nothing-design-reference.md` | ux-architect, ui-designer | Nothing Design System v3.0.0 |
| `scroll-storytelling-reference.md` | frontend-developer | Lenis, GSAP ScrollTrigger |
| `advanced-effects-reference.md` | frontend-developer | Lottie, Rive, cursor effects |
| `creative-coding-reference.md` | frontend-developer, xr-immersive-developer | p5.js, GLSL shaders |
| `reactive-audio-reference.md` | frontend-developer, xr-immersive-developer | Tone.js, Web Audio API |
| `nothing-design-reference.md` | ux-architect, ui-designer | Nothing Design System components |

---

## Adding a New Agent

1. Create `.claude/agents/<name>.md` with required frontmatter:
   ```yaml
   ---
   name: my-agent
   description: One-line description of what this agent does
   model: sonnet   # or: opus
   ---
   ```

2. Include a reference to the protocol:
   ```
   > **Shared protocol:** See `agent-protocol.md` for Engram 2-step reads, Return Envelope, universal rules.
   ```

3. Add a `## Tools` section listing what tools the agent can use.

4. Copy to mirror: `cp .claude/agents/<name>.md agents/<name>.md`

5. Add to the agent table in `CLAUDE.md`.

6. Run drift check: `python _qa/bloque-F10-sot-drift.py` — must PASS.

---

## Agent Communication Contract

Every agent returns a **Return Envelope**:

```
STATUS: completado | fallido | PASS | FAIL | CERTIFIED | NEEDS WORK
TAREA: {what was done}
ARCHIVOS: [list of created/modified files]
ENGRAM: {project}/{drawer}
VERIFICACION: layout | typo | config | none
BLOQUEADORES: [list if STATUS is fallido]
NOTAS: {summary}
```

The dispatcher (`tools/atlas_dispatcher.py`) validates this format. Malformed envelopes are rejected.
