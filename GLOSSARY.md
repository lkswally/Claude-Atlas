# ATLAS — Glossary

Definitions for every ATLAS-specific term.

---

## ADR (Architecture Decision Record)

A document that records a significant architectural decision: what was decided, why, what alternatives were considered, and what the consequences are.

ATLAS stores ADRs in the `ADR/` directory. The self-auditor's T9 check verifies that every ACCEPTED ADR's referenced files still exist on disk (detecting architectural drift).

Format: `ADR/000N-slug.md`. Status: `PROPOSED → ACCEPTED → DEPRECATED / SUPERSEDED`.

→ See: `ADR/0000-adr-template.md`

---

## Agent

A Claude sub-agent: a specialized AI entity with a defined role, specific tools, and a markdown file in `~/.claude/agents/`. Each agent:
- Has a `name`, `description`, and `model` in its YAML frontmatter
- References `agent-protocol.md` for shared behavior
- Has a `## Tools` section listing what it can use
- Returns a **Return Envelope** as its output

ATLAS has 25 agents (1 orchestrator + 24 sub-agents) and 13 technical reference files.

→ See: [docs/AGENTS.md](docs/AGENTS.md)

---

## Capability

An abstract name for a system function: `memory`, `browser`, `documentation`, `repository`, etc.

Agents resolve a capability name through the **Capability Router**, which translates it into the best available **Provider**. This is the recommended path for new integrations; some existing agents still reference MCP tools directly (`mcp__…`), which the capability resolves to — migration is progressive.

The capability abstraction is designed to decouple agents from specific MCP implementations. The goal: when `playwright` is replaced by another browser MCP, agents that go through `resolve_capability` don't change — only the registry does. Agents that still embed raw MCP prefixes would need updating until they migrate.

→ See: [docs/CAPABILITIES.md](docs/CAPABILITIES.md)

---

## Capability Metrics

An append-only log (`.pipeline/capability-events.jsonl`) of every capability resolution. Each event records: timestamp, capability name, provider selected, status, fallback used, resolution success.

Read via: `python tools/capability_metrics.py`

→ See: `core/capabilities/events.py`

---

## Capability Policy

A declarative rule per capability that determines what happens when the provider is not at the ideal status.

Defined in `config/capability.policy.yaml`. Each policy has:
- `critical` (bool): is this essential to ATLAS operations?
- `required_status`: minimum acceptable status
- `fallback_allowed`: can a lower-priority provider be used?
- `block_if_unavailable`: if true + no usable provider → BLOCK
- `severity`: CRITICAL / HIGH / MEDIUM / LOW
- `recovery_hint`: what to do if blocked

→ See: `core/capabilities/policy.py`

---

## Capability Router

The Python module (`core/capabilities/router.py`) that translates `resolve_capability("browser")` into a `Resolution` object containing the provider name, status, fallback chain, and recommended action.

Ranking order: LIVE > CONFIG_ONLY > PENDING_TOKEN > DEFERRED_PAID > UNAVAILABLE.

---

## DAG State

The Directed Acyclic Graph of the current project's progress. Stored in Engram under `{project-name}/estado`.

Contains: current phase, current task, total tasks, stack decisions, completed phases, failed tasks, certifications. The orchestrator reads the DAG State on every boot to know where to resume.

---

## Dispatcher

`tools/atlas_dispatcher.py` — the enforcement engine that validates Return Envelopes, checks Phase Gates, and verifies E2E flows. If an agent returns a malformed envelope, the dispatcher rejects it and asks for a retry.

---

## Engram

The persistent memory MCP used by ATLAS. An agent-based memory system that stores observations with topic keys, supports semantic search, and survives across Claude sessions.

Every significant ATLAS decision is saved to Engram with a permanent `topic_key`. Critical paths have a disk fallback at `.pipeline/{topic}.md`.

→ See: [github.com/Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram)

---

## Fail-open

A design principle: if a hook, tool, or system component crashes or errors, Claude **continues working** rather than stopping. The worst case for a fail-open component is that its protection temporarily doesn't work. The worst case for a fail-closed component is that Claude stops working entirely.

All ATLAS hooks are fail-open. All capabilities have `ATLAS_*_DISABLED=1` escape hatches.

---

## Hard Rules

Declarative rules in `config/hard-rules.json` (or `.claude/hard-rules.json`) that the `pipeline-rules.js` hook enforces. Currently: no force-push to main, no PR merge without pilots, warn on cross-repo commits, warn on unused skills registry.

Distinct from security hooks (which block dangerous commands) — hard rules enforce workflow policies.

---

## Healthcheck

`tools/atlas_healthcheck.py` — a 25-check verification script that validates the entire ATLAS system. Checks: Node.js, Python, npm, settings.json, hooks on disk, hook smoke tests, critical hooks, directory structure, Engram, MCP registry, capabilities, policy engine, metrics, dispatcher.

Exit code: `0` = all PASS, `1` = any FAIL. Run before and after any system change.

---

## Hook

A JavaScript file in `~/.claude/hooks/` that Claude Code/Desktop executes before or after tool calls. ATLAS uses hooks for:

- **PreToolUse**: intercept Bash/Write/Edit calls before they execute
- **PostToolUse**: inspect output after a tool runs
- **PreCompact**: save state before context compaction
- **Stop**: run cleanup when a session ends
- **Notification**: load context when a session starts

Exit code: `2` = BLOCK (tool call is cancelled) | `0` + stderr = WARN (logged, tool proceeds) | `0` + no output = ALLOW (silent pass)

→ See: [docs/HOOKS.md](docs/HOOKS.md)

---

## MCP (Model Context Protocol)

A protocol that lets Claude call external tools and services. Each MCP server provides tools accessible as `mcp__<server-name>__<tool-name>`.

ATLAS uses MCPs for memory (engram), browser automation (playwright), documentation (context7), GitHub (github), and more. MCPs are registered in `~/.claude/settings.json` (Claude Code) or `%APPDATA%\Claude\claude_desktop_config.json` (Claude Desktop).

→ See: [docs/MCP.md](docs/MCP.md)

---

## MCP Registry

`config/mcp.registry.yaml` — ATLAS's catalog of all known MCPs with their status, required credentials, and notes. Distinct from the Claude config — this is ATLAS's inventory, not the actual connection configuration.

---

## Orchestrator

The central coordinator agent (`~/.claude/agents/orquestador.md`). It:
- Manages the 5-phase pipeline
- Reads DAG State from memory to know where to resume
- Spawns sub-agents for specific tasks
- Never does real work (no code, no files, no architecture)
- Validates Return Envelopes from sub-agents
- Enforces phase gates

---

## Phase Gate

A check the dispatcher performs before advancing from one pipeline phase to the next. It verifies that all required Engram drawers exist and have the correct STATUS. If the gate fails, the phase is BLOCKED until the missing artifacts are created.

---

## Policy Decision

The output of `evaluate_capability()`: a `PolicyDecision` object with fields `decision` (ALLOW/WARN/DEGRADED/BLOCK/MISSING_POLICY), `is_usable`, `is_blocking`, `recovery_hint`, `severity`.

---

## Policy Outcome

One of: `ALLOW` | `WARN` | `DEGRADED` | `BLOCK` | `MISSING_POLICY`

- **ALLOW**: provider is at required status, task can proceed normally
- **WARN**: provider has issues, task can proceed with awareness
- **DEGRADED**: fallback provider is active, reduced functionality
- **BLOCK**: `block_if_unavailable=true` and no usable provider — task must stop
- **MISSING_POLICY**: capability not declared in `capability.policy.yaml` — treated as ALLOW

---

## Projects Registry

`config/projects.registry.yaml` — ATLAS's catalog of known projects: name, status (active/archived), directory, last activity. Allows `retomar [project-name]` to work without specifying the full path.

---

## Provider

A specific MCP or service that satisfies a capability. The `browser` capability has three providers: `playwright` (primary), `claude_in_chrome` (fallback 1), `claude_preview` (fallback 2).

Provider status: `LIVE` | `CONFIG_ONLY` | `PENDING_TOKEN` | `DEFERRED_PAID` | `UNAVAILABLE`

---

## Registry

Generic term for ATLAS's catalog files. ATLAS has:
- **Capability registry**: `core/capabilities/registry.py` — all 14 capabilities and their providers
- **MCP registry**: `config/mcp.registry.yaml` — all known MCPs
- **Projects registry**: `config/projects.registry.yaml` — all projects
- **Skills registry**: `.claude/skills.registry.yaml` — all skills

---

## Resolution

The output of `resolve_capability()`: a `Resolution` object with `provider`, `status`, `action`, `fallback`, and `is_usable`.

---

## Return Envelope

The structured output format every sub-agent must return:

```
STATUS: completado | fallido | PASS | FAIL
TAREA: {description}
ARCHIVOS: [file1, file2]
ENGRAM: {proyecto}/{cajon}
NOTAS: {summary}
```

The dispatcher validates this format and rejects malformed envelopes.

---

## Self-Auditor

The `self-auditor` agent (`~/.claude/agents/self-auditor.md`) — a meta-agent that validates the ATLAS system itself. It runs 9 checks (T1–T9) covering: agent catalog sync, hook integrity, Engram connectivity, protocol compliance, return envelope format, hook performance, cross-reference integrity, settings structure, and architecture drift (T9).

Run it by asking Claude: `ejecuta self-auditor`

---

## Skills

Reusable knowledge units in `.claude/skills.registry.yaml`. Each skill has a domain, applies-when conditions, and instructions for when to activate it. Example skills: `ui-ux-pro-max`, `qa-strict`, `branding`, `orchestration`.

→ See: [docs/SKILLS.md](docs/SKILLS.md)

---

## Skills Registry

`.claude/skills.registry.yaml` — catalog of 10 skills with their domain, trigger conditions, and usage patterns. The orchestrator and ux-architect consult this to decide which skill applies to a given task.

---

## topic_key

The Engram key format for persistent memory: `{project-name}/{drawer}`. Examples: `mi-proyecto/estado`, `mi-proyecto/tareas`, `mi-proyecto/css-foundation`.

Every ATLAS memory write uses a topic_key to prevent duplicates and enable upsert patterns.

---

## v0.x → v1.0

ATLAS follows a feature-bloc versioning system: `v0.16.0-atlas-capability-router`, `v0.19.0-atlas-capability-policy`, etc.

`v1.0.0` is planned once: install automation works end-to-end, first-run experience is smooth, three external developers have used it successfully, and all healthcheck checks are green (no FAIL) on a fresh install.

→ See: [ROADMAP.md](ROADMAP.md)
