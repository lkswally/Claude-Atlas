# ATLAS — Security Architecture

ATLAS is not an AI safety system. It is a disciplined engineering system that prevents common developer mistakes from being automated at AI speed.

Every security layer in ATLAS has a **documented reason** and a **fail-open escape hatch**. This document explains what each layer does, why it exists, and how to override it when needed.

---

## Security Layers

ATLAS has 6 security layers. Each is independent — disabling one does not affect the others.

| Layer | Where | What it prevents | Escape hatch |
|-------|-------|-----------------|--------------|
| Hard Rules | `block-no-verify.js` | Destructive git/filesystem commands | `ATLAS_HARD_RULES_DISABLED=1` |
| Security Hooks | `config-protection.js`, `pipeline-rules.js` | Secret file writes, force push to main | `ATLAS_CAPABILITY_POLICY_DISABLED=1` |
| Capability Policies | `capability.policy.yaml` | Using blocked capabilities | `ATLAS_CAPABILITY_POLICY_DISABLED=1` |
| Architecture Drift | self-auditor T9 | Silent removal of required artefacts | N/A (read-only warning) |
| Capability Contracts | `_qa/bloque-F20-capability-contracts.py` | Regression in capability routing | N/A (QA must pass manually) |
| Healthcheck | `tools/atlas_healthcheck.py` | System misconfiguration | N/A (diagnostic only) |

---

## Layer 1 — Hard Rules

**File:** `hooks/block-no-verify.js`  
**Type:** PreToolUse (Bash) — **BLOCKS** (exit 2)

Hard rules block commands that have caused data loss in real projects. The list is documented in `config/hard-rules.json` and checked on every Bash tool call.

**Blocked patterns and why:**

| Command | Reason |
|---------|--------|
| `git push --force` | Overwrites remote history without review |
| `git --no-verify` | Bypasses pre-commit hooks that enforce quality |
| `git reset --hard` | Discards all uncommitted changes irreversibly |
| `rm -rf` | Recursive delete with no confirmation |
| `DROP TABLE` / `DROP DATABASE` | Irreversible data loss |
| `chmod 777` | World-write permissions open security holes |
| `curl ... \| sh` | Remote code execution without verification |

**Why fail-open exists:**  
Some legitimate workflows require these commands (e.g., `git reset --hard` to undo an AI mistake, `rm -rf` in a temp directory, `curl | sh` for a known installer). Rather than forcing developers to disable ATLAS entirely, a single env var disables only the hard rules:

```bash
ATLAS_HARD_RULES_DISABLED=1 claude
```

**What "fail-open" means:** if `block-no-verify.js` itself crashes or times out, Claude proceeds as if the hook wasn't there. The hook can only add protection, never break Claude.

---

## Layer 2 — Security Hooks

**Files:** `hooks/config-protection.js`, `hooks/pipeline-rules.js`

### config-protection.js

**Blocks** writes to:
- `.env`, `.env.local`, `.env.production` — environment secrets
- `.pem`, `.key`, `id_rsa`, `*.private` — private keys
- `credentials.json`, `serviceAccount.json` — credential files

**Warns** on changes to:
- ESLint, Prettier, Stylelint configuration — formatting changes affect the whole team

**Why:** AI-generated code frequently overwrites `.env` files with template values when instructed to "create configuration." This hook requires explicit human intent for any secret file write.

### pipeline-rules.js

**Blocks:**
- Force push to `main` or `master` branch
- Merging PRs that required pilot evidence without any evidence present

**Warns:**
- Cross-repo commits (unexpected — may indicate a path bug)
- Using capabilities without querying skills registry in `design_strict` mode

---

## Layer 3 — Capability Policies

**File:** `config/capability.policy.yaml`  
**Enforced by:** `core/capabilities/policy_engine.py`

Every capability in the registry has a **policy** that determines its behavior when a provider isn't available:

| Outcome | Meaning | Agent can use? |
|---------|---------|----------------|
| `ALLOW` | Fully available | Yes |
| `WARN` | Available with caveats | Yes |
| `DEGRADED` | Working but reduced quality | Yes |
| `BLOCK` | Must not proceed | No |

**Critical capabilities** (`memory`, `browser`, `documentation`) are explicitly marked as requiring at least `WARN`-level availability. A `BLOCK` on any critical capability causes the agent to halt and explain what's missing.

**Why:** without policies, agents silently proceed without required capabilities and produce incomplete work. Policies make the capability contract explicit and observable.

```bash
# View current policy decisions for all capabilities
python tools/capability_metrics.py --report
```

**Escape hatch:**
```bash
ATLAS_CAPABILITY_POLICY_DISABLED=1 claude
```

---

## Layer 4 — Architecture Drift Detection

**Tool:** self-auditor T9 (`agents/self-auditor.md`)  
**Checked by:** `python tools/atlas_healthcheck.py`

The self-auditor reads all `ADR/*.md` files and verifies:
- Every file referenced in an ACCEPTED ADR exists on disk
- No ADR has been `ACCEPTED` for >90 days without review
- No artefact referenced by the pipeline has silently disappeared

**Drift states:**
- `DRIFT` — a file referenced in an ADR no longer exists
- `OVERDUE` — ADR accepted >90 days ago without re-evaluation
- `RECONSIDERED` — decision context changed since ADR was written

**Why:** large codebases evolve and people forget to update ADRs. Drift detection catches "a hook was deleted but the ADR still says it exists" before it causes a silent failure.

**No escape hatch** — drift detection is read-only (it generates warnings, never blocks). There's nothing to disable.

---

## Layer 5 — Capability Contracts

**File:** `_qa/bloque-F20-capability-contracts.py`  
**14 tests** covering:

1. Critical capabilities resolve to LIVE providers
2. Fallback chains work when primary provider is unavailable
3. Policy decisions match provider status
4. Events are written with all required fields
5. No capability is left without a policy (no orphans)
6. `block_if_unavailable=true` actually blocks

**Why:** capability routing has several moving parts (registry, policy engine, event emitter). Without contract tests, a change to any one of them could silently break another. The contracts test the observable behavior, not the implementation.

```bash
python _qa/bloque-F20-capability-contracts.py
```

**No escape hatch** — these are QA tests, not runtime behavior. They must pass before every commit.

---

## Layer 6 — Healthcheck

**File:** `tools/atlas_healthcheck.py`  
**25 checks** covering:

- Python version and dependencies
- All 25 agent files present
- All 13 reference files present
- All 16 hook files present (13 reactive + 3 manual)
- `settings.json` validity and hook registration
- MCP registry file present
- Capability registry importable
- Policy YAML loadable
- All critical capabilities have policies
- Engram connection (if configured)
- `.pipeline/` directory structure
- ADR directory exists

**Why:** before any session, ATLAS verifies its own configuration. A broken setup produces confusing behavior — the healthcheck converts silent failures into clear diagnostic output.

```bash
python tools/atlas_healthcheck.py
```

**Expected output:**
```
[PASS] Python version: 3.11.2
[PASS] PyYAML available
[PASS] 25 agent files found
...
[RESULT] 25/25 PASS
```

---

## What ATLAS Does NOT Do

ATLAS does not provide:

- **Content filtering** — it won't refuse to write code based on what the code does
- **Authentication** — no user accounts, sessions, or access control
- **Network security** — no firewall, no traffic inspection
- **Secrets management** — `.env.local` is local-only, no vault integration
- **Audit logging for compliance** — cost-tracker.js logs tool calls, not for compliance purposes

If you need any of these, they belong at a different layer (your CI/CD pipeline, your infrastructure, your secrets manager).

---

## Security Philosophy

The design principle behind ATLAS security is:

> **Make accidental mistakes hard, intentional overrides easy, and silent failures impossible.**

Every blocked action has an explicit escape hatch. Every failure produces a visible diagnostic. Every security invariant is tested in QA. Nothing fails silently.
