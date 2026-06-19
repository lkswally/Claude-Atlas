# Contributing to ATLAS

Thank you for contributing. ATLAS has layered invariants — a change to one layer can cascade. Read this guide before making any changes.

---

## Before Making Any Change

**Read the architecture first.**

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) — understand the layers
2. Read [GLOSSARY.md](GLOSSARY.md) — understand the terminology
3. Read the relevant ADR in `ADR/` — understand why the design is the way it is
4. Run the baseline: `python tools/atlas_healthcheck.py` — must be 25/25 PASS
5. Run relevant QA suites — all must pass before and after your change

---

## Invariants That Must Never Break

These hold at all times. A PR that violates any of these will not be merged:

1. `python tools/atlas_healthcheck.py` exits 0 (HEALTHY) with no FAIL (documented WARNs are allowed)
2. All `_qa/bloque-F*.py` suites exit 0
3. `agents/` and `~/.claude/agents/` are identical (checked by F10 drift test)
4. `hooks/` and `~/.claude/hooks/` are identical
5. Every ACCEPTED ADR references files that exist on disk (checked by self-auditor T9)
6. `config/capability.policy.yaml` has an entry for every capability in the registry
7. New agent integrations should prefer capability names (`resolve_capability`) over raw MCP prefixes. Existing agents may still reference MCP tools directly (`mcp__…`) — the capability router is a progressive migration, not a completed one. Don't add *new* raw prefixes without reason.
8. Every hook exits 0 on empty input (`echo '{}' | node ~/.claude/hooks/<name>.js`)

---

## Setting Up for Development

```bash
git clone https://github.com/lkswally/Claude-Atlas.git
cd Claude-Atlas

# Install Python dependencies
pip install pyyaml

# Verify baseline
python tools/atlas_healthcheck.py   # must be 25/25 PASS
python _qa/bloque-F20-capability-contracts.py   # must PASS
```

---

## Adding a New Agent

1. Create `.claude/agents/<name>.md` with required frontmatter:
   ```yaml
   ---
   name: my-agent
   description: One-line description of what this agent does
   model: sonnet
   ---
   ```
2. Reference the shared protocol: `> **Shared protocol:** See agent-protocol.md`
3. Add a `## Tools` section
4. Copy to mirror: `cp .claude/agents/<name>.md agents/<name>.md`
5. Add to the agent table in `CLAUDE.md`
6. Add to the agent table in `docs/AGENTS.md`
7. Run drift check: `python _qa/bloque-F10-sot-drift.py` — must PASS

---

## Adding a New Capability

1. Add to `core/capabilities/registry.py` — new `Capability` entry with at least one `Provider`
2. Add to `config/capability.policy.yaml` — a policy entry is **mandatory**
3. Update `core/capabilities/__init__.py` if new public symbols are exported
4. Add contract test in `_qa/bloque-F20-capability-contracts.py`
5. Update `docs/CAPABILITIES.md`
6. Run: `python tools/atlas_healthcheck.py` — must stay 25/25 PASS

---

## Adding a New Hook

1. Create `.claude/hooks/<name>.js`
2. **Must be fail-open**: uncaught exceptions must exit 0, not crash
3. **Must handle empty input**: `echo '{}' | node .claude/hooks/<name>.js` must exit 0
4. Copy to mirror: `cp .claude/hooks/<name>.js hooks/<name>.js`
5. Register in `templates/settings.json` (and `~/.claude/settings.json` for local testing)
6. If hook blocks commands → add tests to `_qa/bloque-F20-security-hooks.py`
7. Add to `docs/HOOKS.md`

---

## Adding a New Python Tool

1. Create `tools/<name>.py` — must run standalone: `python tools/<name>.py --help` works
2. Must fail gracefully on bad input (no unhandled exceptions)
3. Exit code conventions: `0` = OK, `1` = error/warning, `2` = critical
4. Add a healthcheck check in `tools/atlas_healthcheck.py`
5. Document in `README.md` tools table

---

## Writing QA Suites

QA suites are in `_qa/bloque-F<N>-<slug>.py`. Convention:

- **14 tests per suite** (convention, not hard rule)
- Use the PASS/FAIL pattern from existing suites — no external test runner
- Tests must be self-contained: no live MCPs, no network, use `tempfile` for isolation
- Cache resets: call `_reset_cache()` between tests that share module-level state
- Disable via env var: test `ATLAS_*_DISABLED=1` for fail-open behavior

```python
def PASS(name, detail=""): ...
def FAIL(name, detail=""): ...
# Each test: call PASS() or FAIL()
# main() returns: 0 = all PASS, 1 = any FAIL
```

---

## Architecture Decision Records

When making a significant decision (new pattern, replacing existing approach, adding a layer):

1. Copy `ADR/0000-adr-template.md`
2. Number sequentially: `ADR/0005-slug.md`
3. Fill: Date, Status (`PROPOSED`), Context, Decision, Alternatives Considered, Consequences, Rollback
4. Change Status to `ACCEPTED` once implemented and tested
5. Add row to the ADR table in `README.md`
6. Self-auditor T9 will verify referenced files exist at every health check

---

## Sync Mirrors After Any Change

After modifying agents or hooks:
```bash
cp .claude/agents/<modified>.md agents/
cp .claude/hooks/<modified>.js hooks/
python _qa/bloque-F10-sot-drift.py   # must PASS
```

---

## Commit Convention

```
feat(F21): add INSTALL.md and DX documentation
fix(hooks): close chmod bypass in block-no-verify.js
docs: update README with capability system section
test(F20): add TC15 for visualization contract
refactor(capabilities): extract policy cache to separate module
chore: sync agent mirrors after self-auditor update
```

Scope = feature bloc (`F21`), layer (`capabilities`, `hooks`, `tools`), or `docs`/`test`/`chore`.

---

## Final Checklist Before Every Commit

```bash
# Run these all — all must exit 0
python tools/atlas_healthcheck.py
python _qa/bloque-F10-sot-drift.py
python _qa/bloque-F16-capability-router.py
python _qa/bloque-F17-agent-capability-migration.py
python _qa/bloque-F18-capability-metrics.py
python _qa/bloque-F19-capability-policy.py
python _qa/bloque-F20-security-hooks.py
python _qa/bloque-F20-capability-contracts.py
```

One-liner to run all F-series suites:
```bash
for f in _qa/bloque-F*.py; do echo "=== $f ==="; python "$f" 2>/dev/null | grep "RESULTADO"; done
```

---

## What Not to Do

- **Don't skip QA** — even for "trivial" changes. The healthcheck exists for a reason.
- **Don't edit agent files without syncing the mirror** — drift is detected and will fail CI.
- **Don't weaken security hooks** — you can add patterns, never remove them.
- **Don't remove capabilities** — deprecate with `NOT_RECOMMENDED` status first.
- **Don't add optional dependencies** — if Python stdlib doesn't have it, question whether you need it.
- **Don't commit `.env.local`** — it's gitignored for a reason. Double-check before `git add`.

---

## Getting Help

Open an issue with:
- `python tools/atlas_healthcheck.py` output
- The exact change you're trying to make
- What's failing and what you've tried
