# ATLAS — AI Engineering Operating System

> **Give Claude a nervous system.**

[![CI](https://github.com/lkswally/Claude-Atlas/actions/workflows/ci.yml/badge.svg)](https://github.com/lkswally/Claude-Atlas/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/lkswally/Claude-Atlas?include_prereleases)](https://github.com/lkswally/Claude-Atlas/releases)

---

## 1. What ATLAS Is

ATLAS is an **operating framework for AI-assisted software development** — not an AI model.

It runs **on top of** Claude (via Claude Code CLI or Claude Desktop) and turns a raw Claude session into a structured, disciplined engineering environment: persistent memory, security enforcement, capability abstractions, quality gates, registries, and full observability.

You don't replace Claude with ATLAS. You give Claude a backbone. Claude is the brain; ATLAS is the nervous system — the reflexes, memory, and rules that keep work consistent across sessions.

**What ATLAS is NOT:**
- Not an AI model (it needs Claude to run).
- Not a Python package you `import`. It's a configuration + tooling layer: `CLAUDE.md`, agents, hooks, registries, and CLI tools.
- Not a SaaS — it runs entirely on your machine.
- Not magic — if Claude can't do something, ATLAS can't either. It makes Claude *more reliable*, not more capable.

---

## 2. What Problem It Solves

Anyone who has tried to build something serious with a raw LLM hits the same walls. ATLAS attacks each one with code, not good intentions:

| Problem | ATLAS answer |
|---------|--------------|
| **Context loss** between sessions | Engram persistent memory + disk fallback |
| **No traceability** of what happened | Event logs, metrics, healthcheck, session summaries |
| **Hallucinations** (invented files, fake evidence) | Pre-return audit, screenshot hash verification, drift detection |
| **Weak validation** | Test registry + `run_all` runner + CI/Release Validation |
| **Fragile prompts** | Declarative agents/policies in markdown/YAML, not ad-hoc prompting |
| **No persistent memory** | Engram MCP with `topic_key` writes |
| **No systematic QA** | Visual QA loop (Playwright) gating every dev task |

---

## 3. Real Advantages

These are **enforced invariants**, not features you have to remember to use:

- **Enforcement by code** — a hook fires before every command and blocks `rm -rf`, `git push --force`, `chmod 777`, `curl | sh`, `DROP TABLE`, etc.
- **Hooks** — 13 reactive hooks (block / warn / log) intercepting tool calls in real time.
- **Registries** — declarative catalogs for MCPs, tests, projects, and skills.
- **Healthcheck** — one command validates ~24 aspects of system state.
- **Test runner** — `run_all` with quick / release / full layers, JSON output, CI-ready.
- **MCP registry** — every MCP declared with status, capability, and validation.
- **Capability router** — an abstraction layer for MCP integrations: `resolve_capability("browser")` returns the best available provider with a fallback chain and policy. It's available for new integrations and progressive migration — some agents still reference MCP tools directly (`mcp__…`), which the capability resolves to. Not a completed total migration.
- **Engram memory** — decisions survive across sessions and compactions.
- **Visual QA with Playwright** — screenshots, network, and console inspection.
- **Docs with Context7** — current library documentation on demand.
- **Notion integration** — project management surface.
- **CI / Release Validation** — GitHub Actions gates on every push and tag.
- **Registered projects** — known projects tracked so context survives between sessions.

---

## 4. What You Can Build With It

ATLAS is stack-agnostic and project-agnostic. It helps build and maintain:

- **Web apps** (Next.js, Vite+React, SvelteKit, Astro…)
- **Automations** and scripted workflows
- **AI pipelines** (multi-step, tool-using)
- **Multi-agent systems** (the 5-phase orchestrator itself is one)
- **Visual QA** for existing sites/apps
- **Project audits** (architecture, drift, security review)
- **Technical documentation**
- **Engineering workflows** (CI, release gates, registries)
- **Internal assistants**
- **OS-like systems for managing many projects**

---

## 5. Prerequisites

| Tool | Why | Required? |
|------|-----|-----------|
| **Claude Desktop or Claude Code** | The runtime ATLAS runs on | **Yes** |
| **Git** | Clone repo, version control | **Yes** |
| **Python 3.10+** | Healthcheck, runners, registries | **Yes** |
| **Node.js 18+** | Hooks (JS) and Node-based MCPs | **Yes** |
| **Go 1.21+** | Build/run Engram (persistent memory) | Recommended |
| **GitHub CLI (`gh`)** | CI/release inspection, GitHub MCP | Optional |
| **Playwright** | Visual QA | Optional (QA only) |
| **Engram** | Persistent memory MCP | Recommended (fail-open without it) |
| **Context7** | Live library docs MCP | Optional |
| **Notion** | Project management MCP | Optional |
| **`GITHUB_TOKEN` / `VERCEL_TOKEN`** | GitHub MCP / Vercel deploy | Optional (PENDING_TOKEN until set) |

ATLAS is **fail-open**: missing optional dependencies degrade to WARN/SKIP, never a hard failure.

---

## 6. Install From Scratch

**A.** Install **Claude Desktop** (Windows/macOS) or **Claude Code CLI** (Linux/macOS).
**B.** Install **Git** — https://git-scm.com
**C.** Install **Python 3.10+** — https://python.org
**D.** Install **Node.js 18+** — https://nodejs.org
**E.** Install **Go 1.21+** (for Engram) — https://go.dev

**F.** Clone the repo:
```bash
git clone https://github.com/lkswally/Claude-Atlas.git
cd Claude-Atlas
```

**G.** Install Python dependencies:
```bash
pip install -r requirements.txt
```

**H.** Run the healthcheck:
```bash
python tools/atlas_healthcheck.py
```

**I.** Run quick validation:
```bash
python tools/run_all.py --quick
```

**J.** Run release validation locally:
```bash
python tools/run_all.py --release
```

> An automated installer exists for hooks/agents wiring: `bash install.sh` (Linux/macOS) or follow [`install/windows.md`](install/windows.md). Full guide: [INSTALL.md](INSTALL.md) · post-install: [FIRST_RUN.md](FIRST_RUN.md).

---

## 7. First Prompt — Use ATLAS With Claude

Open Claude in this repository directory and paste:

```
Estoy en el repositorio Claude-Atlas. Quiero que actúes como runtime de ATLAS.
Primero leé README.md, CLAUDE.md, ROADMAP.md, config/mcp.registry.yaml,
config/test.registry.yaml y config/projects.registry.yaml. Luego ejecutá
healthcheck, diagnosticá el estado del entorno y proponé el siguiente paso
sin modificar código todavía.
```

This boots Claude into ATLAS-aware mode: it reads the system contract, inspects the registries, runs the healthcheck, and reports the environment state before touching anything.

---

## 8. Day-to-Day Usage

```bash
# System health (≈24 checks, exit 0 = HEALTHY)
python tools/atlas_healthcheck.py
python tools/atlas_healthcheck.py --strict          # release gate (stable expected config)

# Test runner
python tools/run_all.py --quick                      # fast layer (~30 suites)
python tools/run_all.py --release                    # release layer (+ healthcheck gate)
python tools/run_all.py --release --json --out run_all.json   # machine-readable

# Secrets / tokens
python tools/secrets_check.py                        # what's configured vs pending

# Registry summaries
python tools/test_registry.py --summary
python tools/mcp_registry.py --summary
python tools/projects_registry.py --summary
```

Two interaction modes inside Claude:

| Mode | When | How |
|------|------|-----|
| **Normal** | Questions, fixes, reviews | Just talk to Claude |
| **Orchestrator** | Complete projects end-to-end | Say: *"modo orquestador — quiero crear X"* |

---

## 9. How to Add a Project

Register external/known projects in [`config/projects.registry.yaml`](config/projects.registry.yaml) so context survives between sessions:

1. Add an entry with a unique `id` and human `name`.
2. Set `status`: `active` | `paused` | `archived` | `broken`.
3. Set `path` to the project's absolute directory.
4. Add `risks` / `last_known_phase` notes for continuity.
5. Verify:
   ```bash
   python tools/projects_registry.py --summary
   python tools/atlas_healthcheck.py
   ```

ATLAS only *reads* this catalog — it never modifies external projects.

---

## 10. How to Add an MCP

Register Model Context Protocol servers in [`config/mcp.registry.yaml`](config/mcp.registry.yaml):

1. Add the entry with `id`, `command`/`args`, and `atlas_capability` (e.g. `browser`, `documentation`, `memory`).
2. Set `status`: `LIVE` | `CONFIG_ONLY` | `PENDING_TOKEN` | `DEFERRED_PAID` | `MISSING` | `OPTIONAL`.
3. Add a **smoke test** suite under `_qa/` (mirror an existing `bloque-F15-*.py`).
4. Update the healthcheck only if the MCP needs a dedicated check.
5. **Never hardcode tokens** — reference env vars (e.g. `GITHUB_TOKEN`); store secrets in `.env.local` (gitignored).

Validate: `python tools/mcp_registry.py --summary` and run your new suite. Guide: [docs/MCP.md](docs/MCP.md).

---

## 11. How to Add a Skill

Skills are declared in the skills registry at **`.claude/skills.registry.yaml`**:

1. Add the skill with `id` (`domain.name`), `domain`, `cost_tier`, and `applies_when`.
2. The registry is queried via `tools/skills_registry.py` (`find_skills`, `get_skill`, `list_domains`).
3. Validate:
   ```bash
   python tools/skills_registry.py        # lists / validates
   python tools/atlas_healthcheck.py      # "Skills registry" check must be PASS
   ```

Fail-open: if the registry or PyYAML is missing, queries return `[]` (no crash). Guide: [docs/SKILLS.md](docs/SKILLS.md).

---

## 12. How to Run QA

- **Test registry** ([`config/test.registry.yaml`](config/test.registry.yaml)) declares every suite, its layer, and timeout.
- **Quick** — fast feedback layer (~30 suites): `python tools/run_all.py --quick`
- **Release** — full release gate (active suites + healthcheck): `python tools/run_all.py --release`
- **Full** — includes legacy suites: `python tools/run_all.py --full`
- **Legacy** suites are registered but not all run in quick (kept for regression history).
- **Skips** — suites whose external dependency is absent (e.g. Engram binary, Chromium, `.mcp.json` in clean CI) report `[SKIP]` and do **not** affect exit code.
- **Warnings** — non-blocking notices (e.g. runtime-mutable files); they don't fail a gate.

**When to run which (gate policy):**

| Layer | When | Runs |
|-------|------|------|
| `--quick` | **Daily development** — fast feedback | ~30 suites, ~40s |
| `--release` | **Before publishing / tagging** | active suites + healthcheck gate, ~60s |
| `--full` | **Research / maintenance** | everything, including legacy suites |

You do **not** need `--release` for everyday work — `--quick` is the default loop. CI runs Quick on every push to `main`; Release Validation runs only on tag push. Don't run the heavy layers on every edit.

---

## 13. Important States

| State | Meaning |
|-------|---------|
| **PASS** | Check/suite succeeded |
| **WARN** | Non-blocking notice; does not fail the gate |
| **FAIL** | Blocking failure; non-zero exit |
| **SKIP** | Skipped because an optional dependency is absent (not a failure) |
| **RUNTIME_MUTABLE** | File managed by the runtime (e.g. `.claude/settings.json` by Claude Desktop on Windows) — absence is expected, treated as WARN |
| **PENDING_TOKEN** | Component configured but waiting for a token (e.g. GitHub/Vercel MCP) — not blocking |
| **CONFIG_ONLY** | Declared/configured but not verified live this run |
| **LIVE** | Verified active and responding |

---

## 14. Current Limitations (Honest)

- **GitHub/Vercel MCPs require a token** — without `GITHUB_TOKEN` / `VERCEL_TOKEN` they stay `PENDING_TOKEN` (not validated live).
- **Some dependencies are optional in CI** — Engram binary, Chromium, and runtime `.mcp.json` are absent on clean runners and correctly `SKIP`; live coverage of those paths depends on your local environment.
- **`.claude/settings.json` is runtime-mutable** — it's owned by Claude Desktop on Windows; the stable source of truth is the committed `templates/settings.json` + `config/atlas.runtime.expected.yaml`.
- **Legacy suites are registered but not all run in quick** — use `--full` to include them.
- **ATLAS is at Release Candidate (`v1.0.0-rc2`), not GA.** Expect rough edges; see the roadmap below.

---

## 15. Roadmap

Toward **v1.0 final**:

- **Complete documentation** pass across all docs
- **Bootstrap installer** — one-command setup across platforms
- **`doctor` command** — expand `tools/doctor.py` into a full guided diagnose/repair flow
- **Dispatcher decomposition** — break `atlas_dispatcher.py` into smaller modules
- **Plugin architecture** — third-party extensions
- **Event bus** — decoupled internal events
- **Provider abstraction** — pluggable model/MCP providers
- **v1.0 GA** — once the above stabilize

Full detail: [ROADMAP.md](ROADMAP.md) · latest validation: [docs/F25-INTEGRAL-VALIDATION.md](docs/F25-INTEGRAL-VALIDATION.md).

---

## Architecture (at a glance)

```
Developer
    │
    ▼
Claude Session (Claude Code CLI / Claude Desktop)
    │  reads CLAUDE.md (system contract)
    ▼
Orquestador (Opus) ── coordinates, never does real work
    │  spawns
    ▼
24 Sub-Agents (per role) ── Plan → Architect → Build+QA → Certify → Deploy
    │  call
    ▼
Capability Router → Policy Engine → Metrics
    │  backed by
    ▼
Registries (projects / skills / MCP / tests)
    │  connect to
    ▼
MCP Layer (engram, playwright, context7, github, notion, …)

Every tool call is intercepted by the Hook System (.claude/hooks/):
  block-no-verify (BLOCK destructive) · config-protection (BLOCK secrets)
  quality-gate (WARN) · cost-tracker (LOG) · + 9 more
```

### The 5 Phases

```
Phase 1  Planning       → project-manager-senior
Phase 2  Architecture   → ux-architect → ui-designer + security-engineer
Phase 2B Visual Assets  → brand-agent → logo + image + video (optional)
Phase 3  Dev + QA Loop  → dev-agents ↔ evidence-collector (max 3 retries)
Phase 4  Certification  → seo + api-tester + performance + reality-checker
Phase 5  Deployment     → git (user confirms) → deployer (user confirms)
```

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
| [docs/CAPABILITIES.md](docs/CAPABILITIES.md) | All capabilities, providers, policies |
| [docs/MCP.md](docs/MCP.md) | MCP inventory with install/verify steps |
| [docs/AGENTS.md](docs/AGENTS.md) | All agents, roles, tools |
| [docs/HOOKS.md](docs/HOOKS.md) | All hooks, behavior, writing guide |
| [docs/SKILLS.md](docs/SKILLS.md) | Skills registry, creating skills |
| [docs/F25-INTEGRAL-VALIDATION.md](docs/F25-INTEGRAL-VALIDATION.md) | Latest integral validation report |
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
