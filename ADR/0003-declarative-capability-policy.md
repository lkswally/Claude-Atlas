# ADR-0003: Declarative Capability Policy Engine

**Date:** 2026-06-18
**Status:** ACCEPTED
**Deciders:** Lucas Rojo
**Tags:** capability, architecture, policy

---

## Context

The router (ADR-0001) tells agents *what provider exists*. But agents still had no way to know *whether they should proceed* given that provider's state. A PENDING_TOKEN provider is technically "available" but functionally useless. A critical capability with no LIVE provider should halt the task, not silently degrade.

Without a policy layer, each agent would need its own ad-hoc logic to decide whether to proceed, warn, or abort — duplicated and inconsistent across 24 agents.

## Decision

Introduce `core/capabilities/policy.py` backed by `config/capability.policy.yaml`. Each capability has a declared policy with:
- `critical` (bool): essential to ATLAS core operations
- `required_status`: minimum acceptable provider status (LIVE / CONFIG_ONLY / PENDING_TOKEN)
- `fallback_allowed`: whether a lower-priority provider is acceptable
- `block_if_unavailable`: if true + no usable provider → BLOCK decision
- `severity`: CRITICAL / HIGH / MEDIUM / LOW
- `recovery_hint`: human-readable fix (logged in events, escalated on BLOCK)

Decision outcomes: `ALLOW | WARN | DEGRADED | BLOCK | MISSING_POLICY`

API: `evaluate_capability(name) → PolicyDecision`; `resolve_with_policy(name) → (Resolution, PolicyDecision)`

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Hardcode decisions in each agent | 24 agents with duplicated logic; unmaintainable |
| Extend Resolution with policy fields | Conflates routing (what exists) with policy (what's permitted); harder to test independently |
| Runtime-only evaluation (no YAML) | Can't audit, diff, or review policies without running code |
| TOML instead of YAML | YAML already used for `mcp.registry.yaml`; consistency wins |

## Consequences

### Positive
- Policy changes don't require code changes — edit YAML, restart
- Testable independently of MCP state (mock resolution status in unit tests)
- Policy decisions are emitted to the events log with `metadata.policy_decision`
- Self-documenting: `capability.policy.yaml` is the source of truth for "what happens if X breaks"

### Negative / Trade-offs
- Added YAML dependency (stdlib fallback parser included for environments without PyYAML)
- Two separate concepts (router + policy) that users must understand
- `_policy_cache` is module-level — tests must call `_reset_cache()` between runs

## Rollback

Set `ATLAS_CAPABILITY_POLICY_DISABLED=1`. All `evaluate_capability()` calls return `ALLOW` unconditionally. Router continues working normally (ADR-0001 not affected).

## Related

- Feature blocs: F19 (policy engine)
- Capabilities: `config/capability.policy.yaml` (14 policies)
- QA: `_qa/bloque-F19-capability-policy.py`
- Supersedes: ad-hoc per-agent availability checks
- ADR-0001 (capability router), ADR-0002 (event logging)
