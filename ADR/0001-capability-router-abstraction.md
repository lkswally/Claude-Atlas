# ADR-0001: Capability Router Abstraction Layer

**Date:** 2026-06-18
**Status:** ACCEPTED
**Deciders:** Lucas Rojo
**Tags:** capability, architecture

---

## Context

ATLAS agents were coupling directly to MCP tool prefixes (e.g., "usar `mcp__context7__`", "usar `mcp__playwright__`"). This created three problems:

1. **Fragility**: renaming or swapping an MCP broke every agent that referenced it
2. **Opacity**: no single place knew which MCPs were live vs config-only vs pending
3. **No fallback logic**: if `playwright` was down, there was no automatic path to `claude_in_chrome`

## Decision

Introduce `core/capabilities/` as an abstraction layer. Agents request **capability names** ("browser", "memory", "documentation") rather than MCP IDs. The router resolves the best available provider at runtime.

Key API: `resolve_capability(name) → Resolution(provider, status, fallback, action)`

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Keep MCPs hardcoded in agent prose | Fragile; drift inevitable as MCP landscape changes |
| Central config YAML only (no router) | Static; can't account for runtime availability |
| Agent-level if/else fallback | Duplicated logic in 24+ agents; impossible to maintain |

## Consequences

### Positive
- Swap a provider without touching any agent file
- Fallback chains declared once in `registry.py`
- Observability: every resolution is emitted to JSONL (F18)
- Policy enforcement: evaluate each resolution against declared rules (F19)

### Negative / Trade-offs
- Added Python module (`core/capabilities/`) — new layer to understand
- Agents must use capability language in prose (F17 migration required)
- `resolve_capability` is called at task time, not at boot (small latency per call)

## Rollback

Set `ATLAS_CAPABILITIES_DISABLED=1`. All `resolve_capability()` calls return UNAVAILABLE silently. Agents fall back to MCP tools referenced directly in their prose (pre-F16 behavior). No code deletion required.

## Related

- Feature blocs: F16 (router), F17 (agent migration), F18 (metrics), F19 (policy)
- Capabilities: all 14 in `config/capability.policy.yaml`
- QA: `_qa/bloque-F16-capability-router.py`, `_qa/bloque-F17-agent-capability-migration.py`
