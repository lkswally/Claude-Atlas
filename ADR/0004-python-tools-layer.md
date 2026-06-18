# ADR-0004: Python Tools Layer for Complex Runtime Logic

**Date:** 2026-06-18
**Status:** ACCEPTED
**Deciders:** Lucas Rojo
**Tags:** architecture, tooling

---

## Context

ATLAS inherited a JS hook system from its upstream (claude-vibecoding). JS hooks are excellent for reactive, event-driven interception of tool calls (PreToolUse, PostToolUse, lifecycle). However, they are poor for:

- Complex data processing (registry lookups, metrics aggregation, graph traversal)
- Testability (no standard test runner; hard to mock tool inputs)
- Type safety and data modeling
- Cross-module imports and shared state

As ATLAS grew a capabilities layer, metrics, policy engine, dispatcher, and registry system, the gap between "what a JS hook can do" and "what the feature needs" became the main constraint.

## Decision

Maintain two runtime layers with clear separation of concerns:

**JS hooks** (`~/.claude/hooks/`): reactive tool call interception. PreToolUse/PostToolUse/lifecycle. Stateless, fast, fail-open. No complex logic.

**Python tools** (`tools/`): batch processing, registries, metrics, validation, graph analysis, health checks. Invoked by Claude via Bash tool, not automatically triggered.

The Python layer also owns `core/` for shared library code (capabilities, policy, events) imported by multiple tools.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Keep everything in JS hooks | JS lacks native dataclasses, YAML parsing, type hints, pytest; hook model not suited for batch ops |
| Use TypeScript with ts-node | Adds build step; complicates install; no real advantage over Python for data processing |
| Shell scripts for batch ops | Limited for complex logic; no native JSON schema validation; hard to test |
| Single-file scripts per feature | No code reuse; `core/capabilities/` can't be imported across scripts |

## Consequences

### Positive
- Python's stdlib covers YAML, JSON, pathlib, threading, dataclasses with zero dependencies
- `pytest`-compatible test suites in `_qa/` (though we use our own runner pattern)
- `core/capabilities/` is importable from any tool without circular deps
- `tools/atlas_healthcheck.py` is the canonical system health gate (25 checks, exit codes)

### Negative / Trade-offs
- Two languages to understand (JS for hooks, Python for tools)
- Python must be in PATH on Windows (currently Python 3.14 confirmed)
- Tools are invoked explicitly (Bash tool), not automatically — Claude must know to call them

## Rollback

Tools can be ignored — Claude can bypass them and use raw MCP calls. The hook system remains fully functional without the Python layer. `core/capabilities/` fallback: set `ATLAS_CAPABILITIES_DISABLED=1`.

## Related

- Feature blocs: F7 (healthcheck), F16-F19 (capabilities stack), F20 (security + graph)
- Tools: `tools/atlas_healthcheck.py`, `tools/capability_metrics.py`, `tools/dependency_graph.py`
- QA: all `_qa/bloque-F*.py` suites
