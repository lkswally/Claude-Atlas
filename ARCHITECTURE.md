# ATLAS Architecture

ATLAS is an AI Development OS built on Claude Code. It transforms a raw Claude session into a structured multi-agent pipeline with security enforcement, persistent memory, and a stable capability API.

## System Layers

```
┌─────────────────────────────────────────────────────────────┐
│  User / Claude Session                                      │
├─────────────────────────────────────────────────────────────┤
│  CLAUDE.md — System instructions (auto-read by Claude)      │
├─────────────────────────────────────────────────────────────┤
│  Orquestador (Opus) — Central coordinator                   │
│    Runs the 5-phase pipeline. Never does real work.         │
├──────────────────────────────┬──────────────────────────────┤
│  24 Sub-Agents (Sonnet/Opus) │  JS Hook System (16 files)  │
│  Phase 1: PM                 │  PreToolUse: block-no-verify │
│  Phase 2: UX/UI/Security     │  PreToolUse: config-protect  │
│  Phase 2B: Brand/Logo/Image  │  PreToolUse: pipeline-rules  │
│  Phase 3: Dev / QA           │  PostToolUse: quality-gate   │
│  Phase 4: Cert               │  PostToolUse: cost-tracker   │
│  Phase 5: Git / Deploy       │  Stop: engram-sync           │
│  Utility: self-auditor       │  Notification: session-start │
├──────────────────────────────┴──────────────────────────────┤
│  Python Tools Layer (tools/)                                │
│    atlas_healthcheck.py   — 25-check health gate           │
│    atlas_dispatcher.py    — Phase gates, envelope validation│
│    capability_metrics.py  — Resolution event reader        │
│    dependency_graph.py    — Full dependency tree           │
│    skills_registry.py     — Skills catalog                 │
│    design_quality_enforcement.py — Anti-generic detector   │
├─────────────────────────────────────────────────────────────┤
│  Capability System (core/capabilities/)                     │
│    registry.py  — 14 capabilities, provider definitions     │
│    router.py    — resolve_capability(), resolve_with_policy │
│    events.py    — JSONL append-only event log              │
│    policy.py    — YAML-backed policy evaluator             │
├─────────────────────────────────────────────────────────────┤
│  MCP Layer                                                  │
│    engram          — Persistent memory                     │
│    playwright      — Browser automation                    │
│    context7        — Documentation queries                 │
│    github          — Repository operations (token needed)  │
│    computer-use    — Desktop control                       │
│    notion          — Project management                    │
│    + 8 more (visualize, scheduled-tasks, etc.)            │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
ProyectosClaude/                  # ATLAS project root
├── CLAUDE.md                     # System instructions
├── README.md                     # This document's sibling
├── ARCHITECTURE.md               # This file
├── .gitattributes                # LF-only line endings
│
├── core/
│   └── capabilities/
│       ├── __init__.py           # Public API exports
│       ├── registry.py           # 14 capabilities, Provider dataclasses
│       ├── router.py             # resolve_capability(), resolve_with_policy()
│       ├── events.py             # CapabilityEvent, emit(), read_events()
│       └── policy.py             # PolicyDecision, evaluate_capability()
│
├── config/
│   ├── capability.policy.yaml    # 14 declarative capability policies
│   ├── mcp.registry.yaml         # MCP inventory
│   └── phase_playbook.json       # E2E flows per pipeline phase
│
├── tools/
│   ├── atlas_healthcheck.py      # 25-check system health gate
│   ├── atlas_dispatcher.py       # Pipeline enforcement
│   ├── capability_metrics.py     # Resolution event CLI
│   ├── dependency_graph.py       # Dependency tree visualization
│   ├── skills_registry.py        # Skills catalog + usage log
│   ├── design_quality_enforcement.py
│   └── contracts/
│       └── envelope_v1.py        # Pydantic envelope model
│
├── _qa/
│   ├── bloque-F16-*.py           # Capability router tests
│   ├── bloque-F17-*.py           # Capability protocol tests
│   ├── bloque-F18-*.py           # Metrics tests
│   ├── bloque-F19-*.py           # Policy engine tests
│   ├── bloque-F20-security-hooks.py
│   └── bloque-F20-capability-contracts.py
│
├── ADR/
│   ├── 0000-adr-template.md
│   ├── 0001-capability-router-abstraction.md
│   ├── 0002-jsonl-event-logging.md
│   ├── 0003-declarative-capability-policy.md
│   └── 0004-python-tools-layer.md
│
├── agents/                       # Mirror of ~/.claude/agents/
│   └── *.md                      # Drift-detected vs runtime copy
│
├── hooks/                        # Mirror of ~/.claude/hooks/
│   └── *.js                      # Drift-detected vs runtime copy
│
└── .pipeline/                    # Runtime state (gitignored)
    ├── capability-events.jsonl   # Append-only resolution log
    └── estado.yaml               # DAG State fallback
```

## Capability System Design

The capability system solves the "MCP coupling" problem: agents previously hardcoded MCP tool prefixes (`mcp__playwright__browser_navigate`). If the MCP changed IDs, all agents broke.

### Resolution Flow

```
resolve_capability("browser")
    │
    ├─ registry.py: find Capability("browser")
    │    providers = [playwright(LIVE), claude_in_chrome(LIVE), claude_preview(LIVE)]
    │
    ├─ router.py: select best provider by status rank
    │    LIVE > CONFIG_ONLY > PENDING_TOKEN > DEFERRED_PAID > UNAVAILABLE
    │
    ├─ events.py: emit CapabilityEvent to .pipeline/capability-events.jsonl
    │
    └─ Resolution(provider="playwright", status="LIVE",
                  action="USE_LIVE", fallback=Resolution("claude_in_chrome"...))
```

### Policy Evaluation Flow

```
evaluate_capability("memory")
    │
    ├─ policy.py: load config/capability.policy.yaml
    │    memory: { critical: true, block_if_unavailable: true, required_status: LIVE }
    │
    ├─ router.py: resolve_capability("memory") → Resolution
    │
    ├─ _apply_policy(policy, resolution):
    │    if UNAVAILABLE and block_if_unavailable → BLOCK
    │    if UNAVAILABLE and critical → WARN
    │    if status >= required_status → ALLOW
    │    if fallback_allowed and fallback >= required_status → DEGRADED
    │    else → WARN
    │
    └─ PolicyDecision(capability="memory", decision="ALLOW", ...)
```

## Hook Execution Model

Hooks run as Node.js processes, invoked by Claude Code for each matching tool call. They are **fail-open**: if a hook crashes or times out, the tool call proceeds normally.

```
Claude invokes Bash("git push --force")
    │
    └─ PreToolUse hook: block-no-verify.js
         input = { tool_name: "Bash", tool_input: { command: "git push --force" } }
         
         match /git\s+push\s+.*--force/ → exit 2 (BLOCK)
         
         Claude sees: ToolResult with error = hook blocked this command
         Claude does NOT execute the Bash command
```

Security patterns checked by `block-no-verify.js`:
- `git push --force` / `git push -f` / `git -C <dir> push --force`
- `git --no-verify`
- `git reset --hard`
- `rm -rf`
- `DROP TABLE` / `DROP DATABASE`
- `chmod 777` / `chmod 0777` / `chmod -R 777`
- `chown -R` / `chown --recursive`
- `curl ... | sh` (pipe to shell)

## Agent Communication

All agents communicate via **Return Envelopes** — structured text blocks in their response:

```
STATUS: completado | fallido | PASS | FAIL
TAREA: {description}
ARCHIVOS: [file1, file2]
ENGRAM: {proyecto}/{cajon}
NOTAS: {summary}
```

The dispatcher (`atlas_dispatcher.py`) enforces this format and rejects malformed responses. Agents read shared state from Engram using a mandatory 2-step pattern:

```python
result = mem_search("{proyecto}/{cajon}")
if result.observation_id:
    full = mem_get_observation(result.observation_id)  # never use preview
```

## Drift Detection

Two mirrors are maintained in sync with the runtime directories:
- `agents/` mirrors `~/.claude/agents/`
- `hooks/` mirrors `~/.claude/hooks/`

QA suite `bloque-F10-sot-drift.py` detects when the mirrors diverge. The self-auditor's T9 checks that all ACCEPTED ADRs still have their referenced artefacts on disk.

## Invariants

These must hold at all times:

1. `tools/atlas_healthcheck.py` exits 0 with all checks PASS
2. All `_qa/bloque-F*.py` suites exit 0
3. `agents/` and `~/.claude/agents/` are byte-for-byte identical
4. Every ACCEPTED ADR has its referenced files on disk
5. `config/capability.policy.yaml` has an entry for every capability in the registry
6. No agent file references a raw MCP tool prefix (use capability names)
