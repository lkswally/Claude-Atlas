# ADR-0002: JSONL Append-Only Event Logging for Capability Observability

**Date:** 2026-06-18
**Status:** ACCEPTED
**Deciders:** Lucas Rojo
**Tags:** capability, architecture, tooling

---

## Context

After introducing the capability router (ADR-0001), we needed a way to observe resolution behavior over time: which capabilities are resolved, which providers win, how often fallbacks are used, what the failure rate is. Without this, the router is a black box.

ATLAS already had JSONL logs for other subsystems (`invocation-log.jsonl`, `skills-registry-usage.jsonl`). Extending the pattern was the natural choice.

## Decision

Every call to `resolve_capability()` emits a `CapabilityEvent` to `.pipeline/capability-events.jsonl` (append-only, one JSON object per line). The `tools/capability_metrics.py` reader aggregates these into summary reports.

Format: `{"timestamp", "capability", "requested_by", "provider_selected", "provider_status", "fallback_used", "resolution_ok", "action", "metadata"}`.

Disable: `ATLAS_CAPABILITY_EVENTS_DISABLED=1`.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Structured DB (SQLite) | Overkill; harder to inspect with standard tools; complicates testing |
| In-memory metrics only | Lost on restart; no historical analysis possible |
| stdout/stderr logging | Lost after session; unstructured; hard to aggregate |
| Prometheus-style metrics | External dependency; overkill for current scale |

## Consequences

### Positive
- Every resolution is permanently observable
- `capability_metrics.py --json` is machine-readable for CI integration
- Thread-safe via `threading.Lock()`; no data corruption on concurrent writes
- `.pipeline/` already `.gitignore`'d — no accidental secret exposure

### Negative / Trade-offs
- File grows unbounded — no rotation yet (acceptable at current volume)
- Adds I/O per resolution call (mitigated by emit=False option)
- Policy events also write to same file (metadata.policy_decision field) — slightly mixed concerns

## Rollback

Set `ATLAS_CAPABILITY_EVENTS_DISABLED=1`. File stops being written; `capability_metrics.py` returns "no events" cleanly. No structural changes needed.

## Related

- Feature blocs: F18 (metrics), F19 (policy events added to same log)
- QA: `_qa/bloque-F18-capability-metrics.py`
- Supersedes: no prior logging for capabilities
