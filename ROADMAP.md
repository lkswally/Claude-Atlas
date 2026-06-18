# ATLAS Roadmap

## Current State — v0.20.0

**Architecture maturity: ~72%**

### What's Solid (production-ready)
- 5-phase pipeline with phase gates and retry logic
- 25-agent catalog with defined tools and responsibilities
- Capability abstraction layer (F16–F19): router, registry, events, policy
- Security enforcement: 13 reactive hooks, 22/22 security contract tests
- 218+ QA tests across all feature blocs — 100% green
- ADR system with self-auditor drift detection
- Python tools layer: healthcheck (25 checks), dispatcher, metrics, dependency graph
- Engram MCP: persistent memory, dual-write, cross-session continuity

### What's Incomplete
- No public install script (installation is manual)
- Context7 and GitHub MCP require manual token configuration
- Python tools are invoked manually (no auto-trigger on agent completion)
- No automated regression suite that runs all QA suites end-to-end

---

## What Would Block v1.0.0 Stable

### P0 — Must Have
1. **Install automation** — `install/linux.sh` and `install/windows.md` are outdated (reference wrong clone URL). A working one-command install script for both platforms.
2. **Secrets management** — currently tokens go in `.env.local` with no validation. Should have a `setup-tokens` command that validates each token before accepting it.
3. **Full QA suite runner** — a single `python _qa/run_all.py` that runs all bloque-F* suites and reports overall pass/fail with timing.
4. **First-run experience** — after installation, `python tools/atlas_healthcheck.py` should guide the user through fixing any WARN/FAIL items.

### P1 — Should Have
5. **Capability auto-discovery** — instead of hardcoding 14 capabilities in `registry.py`, detect which MCPs are registered in `.mcp.json` and build the registry dynamically.
6. **Policy hot-reload** — currently policy changes require restarting Claude. Should watch `config/capability.policy.yaml` for changes.
7. **Agent output contracts** — formal schema per agent for what they're allowed to write/save. Currently only the envelope format is enforced.
8. **Token budget per agent** — set hard limits on how many tokens each sub-agent can use per task, with automatic escalation if exceeded.

### P2 — Nice to Have
9. **Web dashboard** — render the dependency graph and capability status in a browser UI (could use `tools/dependency_graph.py --json` as the backend).
10. **Replay mode** — given a `.pipeline/capability-events.jsonl`, replay the session and show what decisions were made and why.
11. **MCP auto-install** — if a capability is PENDING_TOKEN or CONFIG_ONLY, generate the exact setup command for the user.

---

## Planned Feature Blocs

### F21 — Automated Regression Suite
- `_qa/run_all.py`: discovers all `bloque-F*.py` files, runs them in parallel, reports totals
- Exit code: 0 = all pass, 1 = any fail
- GitHub Actions integration template

### F22 — Capability Auto-Discovery
- `registry.py` reads `.mcp.json` at startup and supplements hardcoded entries
- New capabilities added dynamically without code changes
- Policy file supports `*` wildcard for unknown capabilities

### F23 — Agent Output Contracts
- Per-agent schema: what drawers they write, what files they touch
- Dispatcher validates agent output against contract
- Violations logged to `.pipeline/contract-violations.jsonl`

### F24 — Token Budget Enforcement
- Per-agent token limits in `config/agent-budgets.yaml`
- Dispatcher tracks tokens per delegation
- Auto-escalate to orchestrator when budget exceeded

---

## Version History

| Version | Tag | Focus |
|---------|-----|-------|
| v0.20.0 | `v0.20.0-atlas-architecture-hardening` | Architecture hardening, docs, ADRs, security |
| v0.19.0 | `v0.19.0-atlas-capability-policy` | Capability Policy Engine |
| v0.18.0 | `v0.18.0-atlas-capability-metrics` | Capability Runtime Metrics |
| v0.17.0 | `v0.17.0-atlas-capability-protocol` | Agent protocol compliance |
| v0.16.0 | `v0.16.0-atlas-capability-router` | Capability Router Abstraction |
| v0.15.x | Skills Registry + Hard Rules (F2) |
| v0.14.x | Envelope v1 Pydantic (F1) |
| v0.13.x | Design Criterion Hardening (1L) |
| ≤v0.12.x | Core pipeline, Engram, QA loops, hooks (1A–1K) |
