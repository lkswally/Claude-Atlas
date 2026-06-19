# ATLAS — Boot Reference

> Extended boot/load detail. `CLAUDE.md` is the slim always-on loader; this is the
> full explanation it points to. Load when you need to understand *why* the boot
> works the way it does, or how lazy loading is decided.

## Why CLAUDE.md is slim (F30)

`CLAUDE.md` is auto-injected into **every** session — it is the only always-on
context cost (measured ~8.7K tokens before F30; F28/F29 audits). ~88% of it was
reference/conditional material not needed at every boot. F30 moved that into lazy
reference docs and left CLAUDE.md as a thin loader + index, cutting the always-on
cost without removing any knowledge or changing behavior.

## Load model

| Load type | What | When |
|-----------|------|------|
| **always_on** | `CLAUDE.md` only | every session (auto) |
| **lazy** | `orquestador.md`, `agent-protocol.md`, agent files, these references | when a mode/agent/trigger needs them |
| **manual** | registries, reports | read by tools/CI, not into Claude context by default |

The authoritative catalog of what loads when is `config/knowledge.registry.yaml`
(see `tools/boot_profiler.py --scan`).

## Reference map (load on demand)

| When you need… | Read |
|----------------|------|
| Operational internals: capability history, dispatcher enforcement, design-quality detector, hook table, per-agent tools | `docs/atlas-operational-capabilities.md` |
| Engram memory protocol (2-step read, topic_key, dual-write, resilience) | `docs/atlas-engram-reference.md` |
| Release gates, RC status, CI, allowed warnings | `docs/atlas-release-reference.md` |
| Project build knowledge: stack, Nothing DS, Better Auth, creative agents, best practices, Windows overrides | `docs/atlas-build-reference.md` |
| Orchestrator pipeline behavior (5 phases, boot sequence) | `.claude/agents/orquestador.md` |
| Subagent contract (Engram 2-step, Return Envelope, universal rules) | `.claude/agents/agent-protocol.md` |
| Agent-specific references (GSAP, React, PocketBase, etc.) | `.claude/agents/*-reference.md` |

## Escape hatch

If you are about to act and lack the operational detail for the task at hand,
**read the matching reference above before acting** — do not improvise governance,
release, Engram, or Windows-specific behavior from memory. The references hold the
full rules; CLAUDE.md holds only the essentials + this map.

## Boot sequence (normal mode)

1. `CLAUDE.md` is auto-loaded (essentials + index).
2. Optionally call `mem_context(scope="personal")` for personal profile.
3. If the task matches a reference trigger, load that reference.
4. If "modo orquestador" is activated, the orchestrator's own boot sequence in
   `.claude/agents/orquestador.md` takes over (light/full mode, DAG state).
