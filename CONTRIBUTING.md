# Contributing to ATLAS

## Before Making Changes

**Read the architecture first.** ATLAS has layered invariants. A change to one layer can cascade:

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) — understand the layers
2. Read the relevant ADR in `ADR/` — understand why the design is the way it is
3. Run the healthcheck: `python tools/atlas_healthcheck.py` — baseline must be 25/25 PASS
4. Run relevant QA suites — all must pass before and after your change

## Invariants That Must Never Break

- `python tools/atlas_healthcheck.py` exits 0 with all 25 checks PASS
- All `_qa/bloque-F*.py` suites exit 0
- `agents/` and `~/.claude/agents/` are identical (checked by F10 drift test)
- `hooks/` and `~/.claude/hooks/` are identical
- Every ACCEPTED ADR references files that exist on disk
- `config/capability.policy.yaml` has an entry for every capability in the registry
- No agent file uses raw MCP tool prefixes — use capability names

## Adding a New Agent

1. Create `.claude/agents/<name>.md` with frontmatter: `name`, `description`, `model`
2. Reference `agent-protocol.md` in the file
3. Add a `## Tools` section
4. Copy to mirror: `cp .claude/agents/<name>.md agents/<name>.md`
5. Add to the agent table in `CLAUDE.md`
6. Run `_qa/bloque-F10-sot-drift.py` — must pass

## Adding a New Capability

1. Add to `core/capabilities/registry.py` — new `Capability` entry with providers
2. Add to `config/capability.policy.yaml` — mandatory policy entry
3. Update `core/capabilities/__init__.py` if new public symbols are added
4. Add contract test in `_qa/bloque-F20-capability-contracts.py` (or new suite)
5. Run all F16–F19 QA suites

## Adding a New Hook

1. Create `.claude/hooks/<name>.js`
2. Hook must be **fail-open**: uncaught exceptions must not block tool calls
3. Test with empty input: `echo '{}' | node .claude/hooks/<name>.js` must exit 0
4. Copy to mirror: `cp .claude/hooks/<name>.js hooks/<name>.js`
5. Register in `~/.claude/settings.json`
6. If the hook blocks commands, add tests to `_qa/bloque-F20-security-hooks.py`

## Adding a New Tool

Tools live in `tools/`. They are Python scripts invoked via Bash by Claude.

- Must be runnable standalone: `python tools/<name>.py --help`
- Must fail gracefully (no unhandled exceptions on bad input)
- Exit code conventions: 0 = OK, 1 = error/warning, 2 = critical
- Add a healthcheck check in `tools/atlas_healthcheck.py`

## Writing QA Suites

Each feature bloc (`F16`, `F17`, ...) has a corresponding QA suite in `_qa/bloque-F<N>-<slug>.py`.

- **14 tests per suite** (convention — not enforced)
- Use the PASS/FAIL pattern from existing suites (no external test runner)
- Tests must be self-contained: no live MCPs, no network, use `tempfile` for isolation
- Cache resets: call `_reset_cache()` between tests that share module-level state
- Disable via env var: set `ATLAS_*_DISABLED=1` to test fail-open behavior

## Architecture Decision Records

When making a significant architectural decision (new pattern, replacing an existing approach, adding a layer):

1. Copy `ADR/0000-adr-template.md`
2. Number sequentially, add a descriptive slug
3. Fill: Date, Status (ACCEPTED / DEPRECATED / SUPERSEDED), Context, Decision, Alternatives, Consequences, Rollback
4. Status starts as PROPOSED; change to ACCEPTED once implemented and tested
5. Add a row to the ADR table in `README.md`
6. Self-auditor T9 will verify referenced files exist at every health check

## Commit Convention

```
feat(F21): add X
fix(F19): resolve Y
docs: update README capability counts
test(F20): add TC15 for Z
refactor(capabilities): extract W to separate module
```

Scope = feature bloc (`F20`), layer (`capabilities`, `hooks`, `tools`), or `docs`/`test`.

## Sync Mirrors After Any Change

After modifying agents or hooks:
```bash
cp .claude/agents/<modified>.md agents/
cp .claude/hooks/<modified>.js hooks/
python _qa/bloque-F10-sot-drift.py  # must pass
```

## Final Checklist Before Committing

```bash
python tools/atlas_healthcheck.py          # 25/25 PASS
python _qa/bloque-F10-sot-drift.py        # no drift
python _qa/bloque-F16-capability-router.py
python _qa/bloque-F17-capability-protocol.py
python _qa/bloque-F18-capability-metrics.py
python _qa/bloque-F19-capability-policy.py
python _qa/bloque-F20-security-hooks.py
python _qa/bloque-F20-capability-contracts.py
```

All must exit 0 before pushing.
