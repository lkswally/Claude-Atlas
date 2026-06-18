# ATLAS — First Run Guide

You've installed ATLAS and the healthcheck passes. Now what?

---

## Before Your First Project

### 1. Verify Engram is working

Engram is the memory system. Without it, every session starts from scratch.

In Claude, type:
```
mem_save con título "atlas-test", contenido "primera prueba", topic_key "system/test"
```

Then:
```
mem_search "system/test"
```

If you get a result back, Engram is working.

If not, see [TROUBLESHOOTING.md#engram](TROUBLESHOOTING.md#engram).

### 2. Run the system audit

Type in Claude:
```
ejecuta self-auditor
```

This runs 9 checks: agent catalog sync, hook integrity, Engram connectivity, protocol compliance, return envelope validation, hook performance, cross-references, settings structure, and architecture drift. All should PASS.

### 3. Understand the two modes

**Normal mode** — the default. Claude answers questions, helps with code, does reviews. No pipeline. No phases.

**Orchestrator mode** — activates the full 5-phase pipeline. Claude becomes a coordinator, not a doer. It spawns specialized agents for each task.

You choose. Claude doesn't activate orchestrator mode automatically.

---

## Your First Project

In Claude, say:

```
modo orquestador — quiero crear una landing page para una app de meditacion
```

What happens:

1. **Orchestrator activates** — reads any prior context from memory, starts in Phase 1
2. **Phase 1: Planning** — `project-manager-senior` creates a task breakdown with acceptance criteria
3. **Phase 2: Architecture** — `ux-architect` designs the CSS foundation; `ui-designer` and `security-engineer` work in parallel
4. **Phase 3: Development** — dev agents build each task; `evidence-collector` does visual QA (screenshots across 3 viewports) after each
5. **Phase 4: Certification** — SEO, API, performance, and final reality-checker review
6. **Phase 5: Deployment** — orchestrator asks you to confirm before `git push` and `vercel deploy`

Each phase is gated — the pipeline cannot skip forward if the previous phase is incomplete.

---

## Resuming a Project

If you come back to a project the next day:

```
retomar [project-name]
```

The orchestrator reads the DAG State from Engram and picks up exactly where it left off.

If the project name isn't clear:
```
¿qué proyectos tengo en progreso?
```

---

## Understanding What's Happening

### Agent activity

When the orchestrator spawns an agent, you'll see something like:
```
[Spawning frontend-developer: implement login form with validation]
```

Each agent returns a **Return Envelope**:
```
STATUS: completado
TAREA: implementar login form
ARCHIVOS: [src/components/LoginForm.tsx]
ENGRAM: mi-proyecto/login-form
NOTAS: Implemented with react-hook-form + Zod validation
```

If an agent returns `STATUS: fallido`, the orchestrator will retry or escalate.

### QA loop

After each development task, `evidence-collector` takes screenshots:
- Desktop (1280px)
- Tablet (768px)
- Mobile (375px)

If QA fails, the orchestrator sends the developer back with the specific visual issues. Maximum 3 retries before escalating.

### Security hooks

While the system runs, hooks fire silently in the background. If you see a command blocked:
```
🚫 Blocked by block-no-verify.js: git push --force
```

This is expected behavior. The hook stopped a destructive command. If you genuinely need to force push, you can explicitly override — but the hook exists because force pushes have destroyed work before.

---

## What to Configure Next

### If you're building web apps:

Configure Vercel CLI:
```bash
vercel login
```

Configure GitHub CLI:
```bash
gh auth login
```

### If you need AI-generated assets (logos, images, videos):

Fill in `.env.local`:
```bash
cp .env.example .env.local
# Edit .env.local with your API keys
```

At minimum, set `GEMINI_API_KEY` or `HF_TOKEN` for images.

### If you need documentation queries:

Context7 MCP should already be configured (it was in your MCP config). Test it:
```
¿cómo funciona useEffect en React 19?
```

Claude should answer using live documentation, not training data.

---

## Key Commands (Run in Terminal)

```bash
# System health (run this whenever something seems wrong)
python tools/atlas_healthcheck.py

# Capability status (are all MCPs working?)
python tools/capability_metrics.py --critical

# Full dependency tree (what's connected to what)
python tools/dependency_graph.py

# Manual utilities
node ~/.claude/hooks/audit-system.js   # system audit
node ~/.claude/hooks/cost-report.js    # token usage breakdown
```

---

## What ATLAS Can't Do

- **Build without Claude's API usage counting** — every agent spawn uses tokens. A complex project can cost a few dollars in API usage. ATLAS includes a cost tracker so you always know.
- **Guarantee Claude won't make mistakes** — QA catches most issues, but the reality-checker is the last gate before deployment. Trust it.
- **Replace your judgment** — the orchestrator asks for your confirmation before git push and deploy. This is intentional.
- **Work offline** — Claude requires API access. Engram and hooks work locally, but the Claude API doesn't.

---

## If Something Breaks

Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first.

Most issues fall into one of:
1. Engram not running
2. A MCP not configured in the right config file
3. Python not in PATH
4. Agent files not in `~/.claude/agents/`

The healthcheck (`python tools/atlas_healthcheck.py`) usually identifies the exact problem.
