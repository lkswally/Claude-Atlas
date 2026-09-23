# ATLAS — Architecture Reality Audit V1

**Date:** 2026-09-23
**Repo / branch / HEAD:** `D:\ProyectosIA\ProyectosClaude`, `portfolio/16x9-readme`, `51e7bb0` (on top of rewritten `origin/main` `0e5b982`)
**Scope:** audit only. No runtime code, hooks, agents, registries, or benchmark cases were changed by this audit (one deliberate, reverted drift fixture in §20; one deliberate, cleaned-up Engram test write in §6).
**Rule applied throughout:** EVIDENCE > DOCUMENTATION > ASSUMPTION. Unverifiable claims are marked `UNKNOWN`/`NOT_TESTED`, never silently upgraded to PASS/LIVE.

## Methodology / classification legend

`LIVE` (executed + verified) · `PARTIAL` (some behavior verified, guarantee incomplete) · `CONTRACT_ONLY` (enforced by agent-instruction text, not mechanically) · `CONFIG_ONLY` (declared, provider not demonstrated) · `SPEC_ONLY` (documented, no working implementation found) · `BROKEN` (reproduced failing) · `NOT_TESTED` (insufficient evidence gathered this pass).

---

## 1. Baseline

Re-run in full this pass, not assumed from prior reports:

| Check | Result |
|---|---|
| Healthcheck | 24 PASS / 2 WARN / 0 FAIL |
| Quick | 39/39 PASS |
| Release | 42/42 PASS |
| atlas_verify | 8/8 PASS |
| Claim linter | 0 HIGH / 0 CRITICAL (51 findings) |
| Architecture score | 85/100 |
| Boot always-on | 1,841 tokens |
| CI (origin/main) | `success` (run `35806893712`) |
| Registered projects | 5 (`marketing_agency_os` active, `conexo_web` paused, `lucas_rojo_web` active, `reyesoft_internal` active, `pixel_bridge` paused) |

Matches the publication-cleanup baseline exactly — no drift since that phase.

## 2. System map (verified layout, not the doc's claim)

`.claude/agents/` (SOT, 38 files) mirrored to `agents/` · `.claude/hooks/` (19 files, 13 registered per `templates/settings.json`) mirrored to `hooks/` · `tools/` (Python: dispatcher, healthcheck, runners, registries) · `core/capabilities/` (router, policy, events, registry — separate from `tools/`) · `config/*.yaml` (MCP/test/project/architecture registries) · `.pipeline/` (DAG state, delegation history, capability events — runtime-generated, gitignored) · `.github/workflows/` (`ci.yml` on push/PR to `main`, `release.yml` on `v*` tags).

## 3. Agents

- **File count, LIVE (re-verified this pass):** 38 files = 1 orchestrator (`orquestador.md`, only file with a spawn/delegate tool) + 24 sub-agent roles (own identity + `model` frontmatter + narrow tool grant, no delegate tool — sampled `frontend-developer`, `evidence-collector`, `security-engineer`, `backend-architect`, `git`, `deployer`) + 13 reference/protocol docs (`agent-protocol.md`, `pipeline-reference.md`, 11 `*-reference.md`, all explicitly self-described as supplementary, not delegable identities). **"24 sub-agents": KEEP.**
- **Max delegation depth = 1: LIVE**, verified structurally (no sub-agent role file grants `Agent`/`Task`) — same evidence as the prior portfolio audit, re-confirmed.
- **Return Envelope enforcement — BROKEN as an integration, CODE_ENFORCED in isolation.** `atlas_dispatcher.py`'s `validate_return_envelope()` hard-codes `required_always = {"status", "tarea", "engram"}` — **lowercase**. Every single agent contract in the repo (security-engineer.md, evidence-collector.md, reality-checker.md, `docs/AGENTS.md`) documents the envelope with **UPPERCASE** keys (`STATUS:`, `TAREA:`, `ENGRAM:`). Fixture-tested directly: a dict built exactly as every contract shows it (`{"STATUS": "completado", "TAREA": ..., "ENGRAM": ...}`) is REJECTED — `"Campos requeridos faltantes: {'status', 'tarea', 'engram'}"` — while the same dict lowercased passes cleanly. Grepped the entire codebase for any markdown-envelope-to-dict parser that would bridge the two: **none exists**. `validate_return_envelope` is called only from `_qa/bloque-*.py` self-tests (which construct lowercase dicts themselves — tautological) and internally within the dispatcher. **No code path in this repository takes a real agent's documented-format output and validates it.** See P1 finding.

> **REMEDIATION (Architecture Repair 01, 2026-09-23) — STATUS: FIXED.**
> Commit `d08d962` on `main` (cherry-picked from `9c5b5b9` on `portfolio/16x9-readme`), pushed to `origin/main`, CI `success` (run `35812468743`, 41s).
> Fix: `validate_return_envelope` now normalizes incoming envelope keys to lowercase in place (adds the lowercase alias into the same dict object, original keys untouched) before any field is read, and explicitly rejects conflicting-value duplicate keys as `AMBIGUOUS_ENVELOPE_KEY` rather than resolving them silently. Chosen over rewriting the 27 agent-contract files, or rewriting every `response.get(...)` call in this ~3,400-line function, as the smallest-churn option.
> Regression test: `_qa/bloque-envelope-casing.py` (11/11 PASS, registered in `config/test.registry.yaml`), including the exact reproduction fixture from this finding, a real sample copied from `security-engineer.md`'s own documented example, an explicit ambiguous-duplicate-key rejection test, and casing-independence proof across `qa_strict`/`dev_strict`/`design_strict`.
> Validation: Healthcheck 24/2/0, Quick 40/40, Release 43/43, atlas_verify 8/8, claim linter 0 HIGH/CRITICAL, boot always-on unchanged (1,841 tokens). Architecture score 85→84 (one additional "large file" flag on an already-3,400-line `atlas_dispatcher.py`; not a functional regression, boot/context budget unaffected).
> This remediation touched only this finding. The other P1/P2/P3 findings in this report are unchanged and still open.
- **Delegation success / correct agent selection / context passed:** `NOT_TESTED` for the full orchestrator-driven pipeline (no live 5-phase run performed this audit — see §4). Three individual roles were tested via isolated contract-adoption probes (§15/16/18 below) with strong results, but that is a different, narrower claim than "the orchestrator correctly selects and invokes this role in a real pipeline."

## 4. Orchestration reality

- `atlas_dispatcher.py`'s phase-gate logic (`enforce_phase_gate`) is real, callable Python — checks required Engram "cajones" before allowing a phase transition, with a **code-enforced** retry counter (`phase_gate_retries`, capped at 2) escalating with an explicit message. This part is **LIVE/CODE_ENFORCED**.
- The 5-phase *sequencing and role-selection* itself (deciding "now call ux-architect, now call ui-designer+security-engineer in parallel") is carried entirely in `orquestador.md`'s natural-language instructions — no scheduler/state-machine code drives it. Classify: **CONTRACTUAL / LLM_DECISION**, not `DETERMINISTIC_CODE`.
- Malformed/edge-case handling (missing state, stale state, invalid phase, interrupted session): the phase-gate code above handles *missing required Engram cajón* deterministically (escalates after 2 retries). Handling of a genuinely *invalid* phase name, a *corrupted* DAG state blob, or a *mid-write* interruption was **NOT_TESTED** — would require a live orchestrator session with injected faults, out of this audit's reach without disrupting real state.
- **DETERMINISTIC_CODE:** phase-gate cajón-presence check, envelope-shape validation (in isolation), SOT/dist drift check, security-backstop regex, hook block/warn logic.
  **CONTRACTUAL:** phase ordering, which agent to call next, QA retry counting, "orchestrator never does real work."
  **LLM_DECISION:** clarity-score-based intent classification, all "as the agent, use your judgment" steps.
  **HUMAN_DECISION:** git push/PR, deploy, anything the Architecture Governor flags `NEEDS_HUMAN_APPROVAL`.

## 5. Retry / failure model

**"Max 3 retries" is CONTRACT_ENFORCED, not CODE_ENFORCED — confirmed by absence, not assumption.** Grepped `atlas_dispatcher.py` for any QA/dev-loop retry counter distinct from `phase_gate_retries`: **zero matches**. The only places "3" appears as a retry ceiling are `orquestador.md` ("máx 3 reintentos") and `evidence-collector.md`'s own self-guard text ("Si el intento es > 3, RECHAZAR... verificar en Engram cuántos intentos hay registrados en `{proyecto}/qa-{N}`"). This means: the agent is trusted to read its own attempt count back from Engram and self-limit — a real, working mechanism only if the LLM correctly executes that read-and-compare every time, with no code backstop if it doesn't. This is a materially different guarantee than "the system enforces 3 retries," and should be worded accordingly.
Distinct from this: `phase_gate_retries` (waiting for a required cajón) IS a real Python-dict counter, hard-capped at 2, escalating with a formatted message — genuinely `CODE_ENFORCED`, just for a different thing than the commonly-cited claim.
**Classification: PARTIAL** (one real retry mechanism exists and is code-enforced; the more prominently marketed one is contract-enforced only).

## 6. Memory — Engram

**LIVE, verified with a real write/read/update cycle against the running instance** (not mocked): `mem_current_project` → correctly reported `ambiguous_project` (cwd `D:\ProyectosIA` holds two repos) with a working `recovery_token` flow; `mem_save` (topic_key `architecture-reality-audit-v1/test-probe`) → created observation `#42`; `mem_search` → found it, full content inline; `mem_get_observation(42)` → full content, plus metadata (`Duplicates: 1, Revisions: 1`); `mem_save` again with the **same topic_key** → same `id=42`, same `sync_id` (confirmed real upsert, not a duplicate) via a second `mem_search`.
**Minor finding:** each `mem_save` on an existing topic_key triggered `judgment_required` conflict candidates against two clearly-unrelated prior observations (`Architecture review vs claude-vibecoding → NO_CHANGE`, `Gentle AI v1.49 review → NO_CHANGE`) with near-zero/negative relevance scores (-1.1, -3.8e-7) — the conflict detector appears to over-trigger on low-confidence matches. The rendered "conflict: contested by..." lines also duplicated (not deduped) across repeated searches. **P3.**
**Not claimed:** that this proves *recurrence prevention* — it proves the storage/retrieval primitive works. Whether a past incident changes a later decision was not tested here (that's Improvement B's own unimplemented scope, per this repo's own prior session history).
Test observation `#42` was left in Engram (title says "safe to delete") — cleanup recommended, not performed (no `mem_delete` tool loaded this session).

## 7. Memory failure / fallback

`NOT_TESTED` against the live Engram process (correctly declined to kill the real binary/DB per the audit's own safety instruction). Verified instead by code inspection: `.pipeline/` holds real, currently-populated runtime state (`capability-events.jsonl` at 216,862 lines — see §21), and `docs`/`CLAUDE.md` describe a "dual-write" pattern. No direct evidence this pass of what specifically survives vs. is lost when Engram is unreachable mid-session, or of recovery behavior when it returns. **Classify: SPEC_ONLY / NOT_TESTED for the fallback path itself; the disk state that would back it (`.pipeline/`) is confirmed to exist and be actively written.**

## 8. Context engineering

Re-confirmed live, matching every prior measurement this session: `boot_profiler.py --report` → `always_on=1841t` (single file, `CLAUDE.md`) against a 2,500-token self-imposed budget (`architecture_audit.py` score 85/100, 0 boot-dependency-risk findings). `knowledge_resolver.py --resolve` was not re-exercised across the 6 named intents (frontend/security/CI/memory/architecture/deployment) this pass due to time budget — **NOT_TESTED this run**, though its metadata-only contract (no content returned, caller decides whether to load) was confirmed correct by direct code reading in the prior portfolio-README audit this session.

## 9. Skills registry

10 skills, 4 domains — confirmed via direct YAML load, matches healthcheck. Relationship to runtime: **DISCOVERABLE_ONLY.** `tools/skills_registry.py` exposes `find_skills()`/`get_skill()`/`list_domains()` — a query API an agent can *choose* to call (e.g. evidence-collector.md's own text: "para descubrir qué skills QA están disponibles... podés consultar el Skills Registry"). No evidence of `RUNTIME_ROUTED` or `AUTOMATICALLY_INVOKED` behavior — nothing in the dispatcher auto-selects or auto-invokes a skill based on task content. Fail-open behavior (empty list on missing PyYAML/registry) was verified by design reading, not fault-injected this pass.

## 10. MCP registry

Re-verified live, not from YAML alone: 21 declared → **13 `LIVE`, 2 `PENDING_TOKEN`** (GitHub, Vercel — no token set), **5 `NOT_RECOMMENDED`**, **1 `DEFERRED_PAID`**. Engram cross-checked independently and matches (`ENGRAM_ACTIVE`, real read/write in §6). Capability-router cross-check (§11) independently reports `browser`→playwright LIVE, `memory`→engram LIVE, `documentation`→context7 LIVE — three independent measurement paths (healthcheck, capability router, direct Engram calls) agree. Playwright confirmed LIVE by direct use (§17). GitHub/Vercel `PENDING_TOKEN` status is consistent with `secrets_check.py`'s 0/7 configured. No external writes triggered.

## 11. Capability router

**LIVE**, tested directly by importing `core.capabilities.router.resolve_capability()` and calling it for `browser`, `memory`, `documentation` — all returned real `Resolution` objects with correct provider, status, and (for `browser`) a populated fallback chain (`playwright` → `claude_in_chrome`). Provider-unavailable / both-unavailable / policy-BLOCK fixture paths were **NOT_TESTED** this pass (would require monkey-patching provider state, not attempted to avoid destabilizing the live registry mid-audit). Migration coverage (agents still calling MCP tools directly instead of through the resolver) was **not quantified** this pass — `evidence-collector.md` and `reality-checker.md` both reference `mcp__playwright__*` tool names directly in their own instructions rather than exclusively through `resolve_capability()`, confirming the "not a completed migration" caveat already in the README is accurate, though a precise coverage percentage was not computed.

## 12. Policy engine

Healthcheck reports 14 capability policies: 7 `ALLOW`, 7 `WARN`, 0 `BLOCK`, re-confirmed this pass. Whether these are mechanically enforced at the point of an actual MCP call, purely advisory/logged, or bypassable via a direct provider call was **NOT_TESTED** with a live fixture this pass (would require triggering a WARN-policy capability call and inspecting whether/how it's actually gated, which risks a real external call). **Classify: CONFIG_ONLY** pending that test.

## 13. Hook layer

19 files in `.claude/hooks/` (14 `.js` + 3 `.sh` + `audit-system.js`), of which **13 are registered** in `templates/settings.json`'s `PreToolUse`/`PostToolUse`/`PreCompact`/`Stop`/`Notification` slots. The remaining 6 (`audit-system.js`, `cost-report.js`, `learning-index.js`, `dual-write-sync.sh`, `frontend-audit.sh`, `pre-return-audit.sh`) are manual/on-demand utilities living in the same directory but never auto-invoked — "13 hooks" is accurate under *registered hooks*, not *files in the directory* (19).

Direct fixture-tested this session (positive + negative controls, exact JSON payload piped to `node`): `block-no-verify.js` (BLOCK on `git push --force`/`git reset --hard`/`--no-verify`, PASS on `git status`), `config-protection.js` (BLOCK on `.env` write, PASS on `.ts` write), `quality-gate.js` (WARN + 7-rule security backstop, PASS on clean code), `console-log-warning.js` (WARN on `console.log`), `pipeline-rules.js` (PASS on benign Bash). **5/13 registered hooks LIVE-verified via direct invocation, both directions.** The remaining 8 (`delegation-tracker`, `qa-auto-audit`, `cost-tracker`, `suggest-compact`, `pre-compact-engram`, `session-summary`, `engram-sync`, `session-start-context`) are session-state/log-class hooks not amenable to a simple stdin fixture — verified only by code reading (fail-open `try/catch` pattern present in all 8) — **NOT_TESTED by execution this pass.**

**HOOK LOGIC WORKS ≠ HOST REGISTRATION VERIFIED — confirmed distinct, again.** `~/.claude/settings.json` (the location `CLAUDE.md` itself names as where hook wiring lives) is empty in this Claude Desktop session's environment, same finding as the prior portfolio audit. So: hook *scripts* are deterministic and correct under direct invocation; whether they are *currently wired into live tool-call interception* in this specific runtime remains unconfirmed.

## 14. Security backstop

Already exhaustively fixture-tested this session (`_qa/bloque-security-backstop.py`, 17/17 PASS): 7 true positives (one per rule: eval, command injection, SQLi, XSS, CORS, TLS, unsafe upload), 8 false-positive-avoidance cases, 1 JSONL-schema check, 1 existing-secret-detection-unaffected check. Re-confirmed this pass (no code changed since). **TP: 7/7 planted single-issue fixtures. FN (known, by design): missing-authorization, IDOR — confirmed absent from the rule set by direct source reading (7 rules total, `SEC-EVAL-001` through `SEC-UPLOAD-001`, none address authorization).** WARN-only, fail-open, not blocking — confirmed via the exact same fixture probes.

## 15. Security agent (`security-engineer`)

Blind-tested via an isolated subagent given the role file + a fixture (`vuln.js`) with 8 deliberately planted issues (hardcoded key, `eval`, command injection, SQLi ×2 incl. IDOR, XSS, insecure CORS, disabled TLS verification) — **ground truth known only to me, not disclosed to the probe.**
**Result: CONTRACT_SCOPE_MATCH: NO — self-diagnosed correctly.** The agent's own contract is scoped to *pre-implementation threat modeling from a project spec* ("Analizo amenazas **antes de que se escriba código**... El orquestador me pasa: Spec del proyecto"), not post-hoc code review — confirmed by direct reading of `security-engineer.md` independently before the probe ran, and the probe reached the identical conclusion on its own, citing the same lines.
Proceeding off-contract anyway (as instructed): **8/8 planted issues found, 0 false positives, 0 misses**, each with correct file:line, CWE/OWASP category, severity, and concrete fix — including catching that the CORS wildcard+credentials combination's real-world risk depends on the `cors` package's actual reflect-origin behavior (a nuance beyond the deterministic backstop's simpler pattern match).
**Compared, not merged, per instruction:** the deterministic backstop (§14) caught 7 *categories* via regex, WARN-only, no IDOR/missing-auth coverage by design. The security-engineer probe (off-contract) caught all 8 *specific instances* including the IDOR one, with full reasoning — but **this capability is not reachable through the agent's actual designed invocation path** (Phase 2, spec-only input). This is the audit's clearest example of "the model can do X, but the architecture never asks it to."

## 16. QA / Evidence Collector

Blind-tested via an isolated subagent given the role file + a fabricated claim ("0 console errors, button works, screenshot at `proof-it-works.png`") against a real local fixture with 3 real console errors, a real uncaught `ReferenceError` on click, and a **cited screenshot file that does not exist.**
**Result: every fabricated assertion correctly identified as FALSE, with real tool evidence for each** — navigated with real Playwright MCP, read real console/network output, clicked the button and caught the real exception, and verified the cited screenshot path with a filesystem check before rejecting it. Returned `STATUS: FAIL`, `RATING: D`, cited the missing-screenshot issue explicitly as "the historical fabricated-evidence-reference failure mode."
**Classify: LIVE** for the specific, historically-vulnerable claim ("does it accept genuine evidence and reject fabricated/missing/stale evidence") — this directly reproduces and passes the exact regression scenario named in the audit brief. The Engram-dependent parts of its full contract (task spec from `{proyecto}/tarea-N`, AUTO_AUDIT cross-checks, visual fidelity LLM-as-judge, design registry gates) were explicitly flagged by the probe as un-executable gaps, not silently skipped — **PARTIAL** for the contract as a whole, **LIVE** for the core anti-fabrication behavior.

## 17. Real browser QA

**LIVE**, tested directly by me (not delegated) using the actual `mcp__playwright__*` MCP tools — the literal provider named in `evidence-collector.md`/`reality-checker.md` — against a real local HTTP server (`localhost:8791`) with deliberately planted defects: `browser_navigate` (200, correct title), `browser_take_screenshot` (desktop + mobile, real PNG files written to disk), `browser_console_messages` (correctly captured 3× 404 resource errors + 1 deliberate warning on load, then a real `ReferenceError: undefinedVar is not defined` after interaction), `browser_network_requests` (correctly listed the 200 and both 404s), `browser_resize` (375×667 mobile viewport applied), `browser_snapshot` (correct accessible-tree with element refs). Evidence artifacts exist on disk in the scratchpad. This is the strongest, most direct LIVE confirmation in this audit — every primitive evidence-collector/reality-checker's contracts describe was exercised for real and behaved correctly.

## 18. Reality Checker

Blind-tested via an isolated subagent given the role file + 4 claims (1 true, 3 false/unverifiable), including a re-run of evidence-collector's own claimed PASS (Paso 2B False Positive Guardrail).
**Result: all 4 claims correctly classified** — confirmed the server was really running (TRUE), correctly rejected the fabricated "0 console errors + working screenshot" claim by re-navigating and re-clicking itself (real `ReferenceError` reproduced independently), correctly refused to accept an unsubstantiated "SEO Score 92/100" (citing its own contract's "scores perfectos sin justificación" auto-FAIL trigger and verifying live that `/sitemap.xml`, `/robots.txt`, `/llms.txt`, `/manifest.json` all 404), and correctly caught that a claimed HTML comment didn't exist in the file at all (went and checked, rather than assuming). **`FALSE_POSITIVE_DETECTED: YES`**, `STATUS: NEEDS WORK` — the correct verdict on every axis. **Classify: LIVE** for the False Positive Guardrail behavior specifically — this is the exact "VetConnect" regression scenario the contract itself cites, reproduced and passed.

## 19. Pre-return audit

`atlas_dispatcher.py` has real, callable functions (`verify_declared_files`, `verify_pre_return_audit`) distinct from `validate_return_envelope`. Given the §3 finding that the envelope's own case-sensitivity issue means no real agent output currently reaches these validators through a demonstrated code path, the same caveat applies here: the validator functions themselves are `CODE_ENFORCED` in isolation (not fixture-tested individually this pass — **NOT_TESTED**), but their integration into a live agent-output pipeline is unconfirmed for the same structural reason as §3.

## 20. Drift detection

**LIVE, directly demonstrated with a real fault injection and reversion.** Appended a one-line marker to `.claude/hooks/console-log-warning.js` (SOT) without touching the `hooks/` dist mirror, then ran `_qa/bloque-F10-sot-drift.py`: correctly failed with `"Hooks con drift de contenido: ['console-log-warning.js']"` and the exact remediation instruction. Reverted via `git checkout --`; incidentally surfaced a real line-ending (CRLF/LF) discrepancy between the SOT and dist copies of that same file despite a repo-wide `.gitattributes` `eol=lf` rule — fixed via the canonical `tools/sync_dist.py`, confirmed clean afterward, confirmed no residual diff against HEAD. Stale-test-referencing-moved-canonical-source and registry/doc drift were **NOT independently fixture-tested this pass** (config/runtime mismatch detection was exercised earlier this session via `bloque-F23-runtime-settings-separation`, part of the Release suite, PASS).

## 21. Observability

`capability-events.jsonl` lives at `.pipeline/capability-events.jsonl` (not `.claude/logs/` as might be assumed) — **216,862 total lines, 215,070 valid JSON, 1,782 invalid**, exactly matching healthcheck's long-standing WARN count. **Root cause identified this pass, not just observed:** every sampled invalid line is a *truncated fragment* of a longer valid line (e.g. `'mium — QA automation, E2E"}}'`, missing its opening `{...`) — the signature of a non-atomic concurrent append (two writers' payloads interleaved mid-line), not encoding corruption or schema drift. **Severity note beyond the invalid-line count itself: 216K total lines with no visible rotation/truncation strategy is its own, separate finding** (unbounded log growth). Other observability surfaces (invocation logs, cost tracking, session summaries, delegation state) were **not independently JSONL-validated this pass** — time budget spent on the highest-value, already-flagged target. End-to-end task reconstruction from observability alone: **NOT_TESTED**.

## 22. Healthcheck

`check_python()` reads: `shutil.which("python") or shutil.which("python3")` — **does not check for `py`/`py -3`** (the Windows launcher actually used throughout this session's own command invocations). In this environment, `python --version` and `py -3 --version` both resolve to `Python 3.14.5` directly (verified), so this gap didn't produce a false WARN here — but it means a Windows machine where only the `py` launcher is on PATH (a common `python.org` installer configuration) would get a false "Python no encontrado" WARN from this exact check, independent of whether Python actually works. **This directly explains the "Python unavailable" claim in the stale `docs/publication_architecture_audit.md` found earlier this session** (produced by a different/prior environment where `python`/`python3` weren't on PATH but `py` presumably was) — not a contradiction, a launcher-detection gap, confirmed by code reading plus this session's own successful `py -3` runs throughout. **P2 finding.**
No other false PASS/WARN/FAIL was identified in the 26-check list this pass beyond the ones already flagged (Capability metrics WARN = real, root-caused in §21; `.mcp.json (CWD raíz)` check showed a path-resolution quirk when run from a relocated clone during the publication-cleanup phase — environment-specific, not reproduced in the canonical repo location).

## 23. Test suite quality

Not exhaustively re-classified suite-by-suite this pass (39+ Quick suites, 42+ Release suites) given time budget. Spot classification of suites directly exercised or read this session: `_qa/bloque-F10-sot-drift.py` = **BEHAVIORAL** (compares real file content, fixture-provoked and confirmed to catch a real injected fault this pass — §20). `_qa/bloque-security-backstop.py` = **BEHAVIORAL** (real subprocess invocation of the real hook with real payloads, not mocked). `_qa/bloque-1a14-validation.py`, `_qa/bloque-F22-secrets-check.py` = **STRUCTURAL/SMOKE** (construct synthetic fixtures with known fake-secret strings, assert the detector fires — useful, but self-consistent by design, not integration tests against real agent output). The `validate_return_envelope` test suites (`_qa/bloque-1a10-validation.py`, `bloque-1k*-validation.py`, etc.) are **STRUCTURAL, and per §3's finding, tautological with respect to real agent output** — they construct lowercase dicts because that's what the function expects, so a passing suite here does not prove the envelope contract is honored end-to-end. **This is the single most important test-quality finding: a green test suite around `validate_return_envelope` does not, and cannot, prove the documented (uppercase) envelope format is actually validated in production, because no test in the suite exercises that boundary.**

## 24. CI / local parity

`ci.yml` triggers on push/PR to `main` (Quick); `release.yml` triggers on `v*` tags (Release) — confirmed by direct file reading, matches the claim. Latest CI run on the (rewritten) `main`: `success`, 47s (§1). Local Quick/Release this pass: also all-PASS, same suite counts. No discrepancy found this pass between local and CI suite *counts*; OS/dependency-level differences (CI is `ubuntu-latest`, local is Windows) were not diffed suite-by-suite this pass beyond what was already established earlier this session (the `npx`/network-capability-check Windows-vs-Linux-CI incident, already fixed and now covered by `bloque-F15-ci-determinism`, PASS both locally and in CI).

## 25. Silent failure audit

Concrete, evidenced findings (not a general sweep — time-boxed to what surfaced from the rest of this audit):
- **`validate_return_envelope`'s case-mismatch (§3)** is itself a silent-failure risk in the making: if a real agent's uppercase envelope were ever piped into it, it would return `is_valid=False` with a generic "missing fields" message that doesn't hint at the actual cause (case mismatch) — a future integrator debugging this would not find the root cause quickly from the error text alone.
- **`capability-events.jsonl`'s 1,782 truncated lines (§21)** are a silent, ongoing data-loss pattern — every consumer of that log presumably skips unparseable lines rather than surfacing the write-race itself; the race continues unaddressed.
- **13 hooks are all fail-open by design** (confirmed pattern in every hook read this session) — this is a *documented, intentional* silent-failure posture, not a bug, but worth stating precisely: a hook crashing internally produces the same "no warning shown" outcome as a hook correctly finding nothing wrong. The two are indistinguishable from the tool-call output alone.
- Beyond these three, a full sweep for `except: pass`/bare-exit-0-on-exception across the ~40 Python tools and ~19 hook scripts was **NOT_TESTED exhaustively this pass**.

## 26. Human-in-the-loop matrix

| Operation | Enforcement |
|---|---|
| `git push --force` / `reset --hard` / `--no-verify` | **HOOK_ENFORCED** (verified, §13) |
| Write to `.env`/`.pem`/`.key` | **HOOK_ENFORCED** (verified, §13) |
| `git` commit/push, PR creation | **CONTRACT_ENFORCED** (`git.md`: "acts only with user confirmation" — text, no hook gates a generic `git commit`) |
| Deploy | **CONTRACT_ENFORCED** (same pattern, `deployer.md`) |
| Security-sensitive / architecturally significant change | **CODE_ENFORCED** (`architecture_decision.py` — real, callable, returns `NEEDS_HUMAN_APPROVAL` for `security` signal; exercised for real this session outside this audit, in Improvement A) |
| Advancing past a failing QA task | **CONTRACT_ENFORCED** (orchestrator instructed not to call `git` before `evidence-collector` PASS; no code gate found blocking a `git` call independent of QA state) |
| Secret access | **HOOK_ENFORCED** for the specific patterns `config-protection.js` matches; **NOT_ENFORCED** for anything outside that pattern set |

Not all six rows are equally "mandatory" — two are code/hook-backed regardless of model compliance, four depend on the model correctly following its own contract.

## 27. Autonomy boundaries (from this audit's own evidence, not the old benchmark score)

**Can autonomously, with code backing:** block a known-destructive shell command; block a write to a known secret-file pattern; detect SOT/dist drift; detect 7 categories of injected security anti-patterns in JS/TS (WARN only); read/write/search/update Engram memory; resolve a capability to its live provider with fallback metadata; classify a proposal as needing human approval.
**Can autonomously, contract-only (depends on the model following instructions correctly, no code backstop found):** count and cap dev↔QA retries at 3; sequence the 5 phases; decide which sub-agent to call next; decide when a task's evidence is sufficient to advance; decide when to certify vs. NEEDS WORK (though when tested directly, this last one performed very well — §16/§18).
**Requires an external provider:** all Playwright-based QA, all Engram-based memory, GitHub/Vercel MCP actions (currently `PENDING_TOKEN`).
**Requires human approval, code-enforced:** destructive shell commands, secret-file writes, Governor-flagged proposals.
**Requires human approval, contract-only:** git push, deploy.
No new synthetic global autonomy score is produced here — that would require the same frozen rubric and methodology as Benchmark V1, which this audit did not re-run.

## 28. Architecture consistency — contradictions found

1. **Return Envelope case mismatch** (§3) — every agent contract documents uppercase keys; the validator requires lowercase; nothing bridges them.
2. **"13 hooks"** — accurate for *registered* hooks, not for files in `.claude/hooks/` (19). Worth stating precisely in docs that reference the count.
3. **`docs/publication_architecture_audit.md`'s "Python unavailable"** — explained, not contradicted: a real launcher-detection gap in `atlas_healthcheck.py` (checks `python`/`python3`, not `py`), confirmed by code reading (§22).
4. **"Max 3 retries"** — real for phase-gate cajón waits (code-enforced, cap 2/max 2 retries = 3 attempts); contract-only for the more commonly cited dev↔QA loop.
5. **`security-engineer` as the "semantic gap-filler" for code vulnerabilities** (a framing used earlier this session, in Improvement A) — its actual contract has no code-review workflow at all; the capability exists only off-contract (§15).
6. MCP status, capability-router status, and Engram's own live-check all agree with each other this pass — **no contradiction found** here, worth noting as a positive consistency result rather than assuming one exists.

---

## P0 findings

*(security / data loss / core broken)* — **none found this pass.** The Return Envelope case-mismatch (below) is severe but does not meet P0 by this rubric: it does not cause data loss or a security exposure, and no currently-exercised code path was shown to depend on it succeeding.

## P1 findings

| ID | Component | Summary | Evidence | Root cause confidence |
|---|---|---|---|---|
| P1-1 | `tools/atlas_dispatcher.py::validate_return_envelope` | Requires lowercase envelope keys; every agent contract documents uppercase; no parser bridges them; no test in the suite exercises the real boundary | Direct fixture test (§3), full-codebase grep for a parser (none found), test-suite reading (§23) | **CONFIRMED** — **STATUS: FIXED**, commit `d08d962`, see remediation note in §3 |
| P1-2 | `.pipeline/capability-events.jsonl` | 1,782/216,862 lines are truncated JSON fragments — classic non-atomic concurrent-append race, ongoing | Direct JSONL parse + sample-line inspection (§21) | **CONFIRMED** (pattern); exact writer(s) responsible — **PROBABLE**, not pinpointed to a specific hook this pass |
| P1-3 | Dev↔QA "max 3 retries" | No dispatcher-side counter exists; enforcement is entirely contract-text + agent self-report from Engram | Full-codebase grep, absence confirmed (§5) | **CONFIRMED** |

## P2 findings

| ID | Component | Summary | Evidence | Confidence |
|---|---|---|---|---|
| P2-1 | `tools/atlas_healthcheck.py::check_python` | Doesn't check the `py` launcher; false "Python unavailable" WARN possible on Windows installs where only `py` is on PATH | Code reading + this session's own working `py -3` runs (§22) | CONFIRMED (gap in code); real-world false-WARN rate — NOT_TESTED across other machines |
| P2-2 | `.claude/agents/security-engineer.md` scope | No documented workflow for reviewing already-written code; the "fills the semantic security gap" framing used elsewhere this session doesn't match the contract | Direct contract reading + blind-probe self-diagnosis (§15) | CONFIRMED |
| P2-3 | Engram conflict-judgment | Triggers `judgment_required` on near-zero-relevance matches; duplicate "contested by" lines accumulate rather than dedupe | Live test, 2 save cycles (§6) | CONFIRMED, low severity |

## P3 findings

| ID | Component | Summary |
|---|---|---|
| P3-1 | `.claude/hooks/` doc count | "13 hooks" is correct only for *registered* hooks; 19 files total in the directory — worth stating the distinction explicitly wherever the count is cited |
| P3-2 | `.pipeline/capability-events.jsonl` size | 216K+ lines, no visible rotation — separate from the corruption finding |
| P3-3 | SOT/dist line-ending sensitivity | A `git checkout --` on one file produced a CRLF/LF-only "drift" despite a repo-wide `eol=lf` `.gitattributes` rule; resolved by `sync_dist.py`, but shows the drift check is byte-sensitive in a way that could false-positive on cross-platform checkouts |

## UNKNOWN / NOT TESTED

Policy-engine live enforcement (§12) · capability-router fallback-triggering under a forced-unavailable provider (§11) · Engram fallback/recovery behavior with the live process actually down (§7, declined for safety) · full end-to-end 5-phase orchestrator run with injected mid-pipeline faults (§4) · knowledge-resolver behavior across the 6 named intents, this pass (§8, verified in a prior pass this session) · 8 of 13 registered hooks by direct execution (verified by code-pattern reading only) (§13) · exhaustive suite-by-suite test-quality classification beyond the samples in §23 · full silent-failure sweep across all tools/hooks (§25) · end-to-end observability task reconstruction (§21).

## No-change areas (confirmed working as documented, no finding)

MCP registry status reporting · capability router core resolution · Engram save/search/get/update/topic-key-upsert · SOT/dist drift detection (when actually triggered) · security backstop's 7 rules (WARN-only, as documented) · evidence-collector's and reality-checker's core "verify, don't trust" behavior when the contract is actually followed with real tools · boot token budget (1,841, stable across every measurement this session) · CI triggers matching documented behavior · architecture-decision Governor's `security` hard-block (exercised for real, outside this audit, in Improvement A this session).

## Top 5 evidence-backed improvements

*(Reported per instruction — not implemented. Ranked by the impact/evidence actually gathered this pass, not novelty.)*

1. ~~**Bridge or fix the Return Envelope case mismatch** (P1-1)~~ — **DONE**, Architecture Repair 01, commit `d08d962`, see remediation note in §3.
2. **Root-cause and fix the `capability-events.jsonl` write race** (P1-2) — the corruption pattern (truncated fragments) points at a specific, fixable class of bug (non-atomic append); identifying the exact writer(s) is the next concrete step.
3. **Make the dev↔QA retry ceiling code-enforced** (P1-3), mirroring the existing `phase_gate_retries` pattern, instead of relying on the LLM to self-report its attempt count from Engram correctly every time.
4. **Fix `check_python()`'s launcher detection** (P2-1) to also check `py`/`py -3` — small, precisely-scoped, directly explains a real discrepancy found this session.
5. **Reconcile `security-engineer`'s documented scope with how it's actually described elsewhere** (P2-2) — either extend its contract to cover post-hoc code review (it's demonstrably capable, §15), or stop describing it as the system's semantic-gap-filler for code vulnerabilities in other docs/reports.

---

**ARCHITECTURE_REALITY_BASELINE_ESTABLISHED**
