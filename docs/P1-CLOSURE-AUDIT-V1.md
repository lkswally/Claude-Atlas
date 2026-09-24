# P1 Closure Audit V1

Independent re-audit of every P1-class finding from Architecture Reality Audit V1, Stability Hardening Audit V1, and Repairs 01–05. No remediation prose was trusted as evidence — every closed P1 was re-tested with fresh fixtures, independent of the original repair's own test data, plus mutation-sanity in disposable worktrees. **No runtime code was modified.**

## Baseline (2026-09-24, commit `dc461b0`, `origin/main`, CI `35999940017` success)

Healthcheck 25/1/0 · Quick 42/42 · Release 45/45 · `atlas_verify` 8/8 · `secrets_check` clean · `claim_linter` 51 findings, 0 HIGH/CRITICAL · Architecture score 72/100 (reported only, not a gate — distorted by manual audit-doc size) · boot tokens 1,841 · `git diff --check` clean except the same pre-existing `lucas-rojo-web/CHANGELOG.md` whitespace nit seen all session. All matched exactly.

## P1 Inventory

| ID | Finding | Remediation commit | Status going in |
|---|---|---|---|
| P1-A | Return Envelope casing mismatch | `d08d962` | FIXED (claimed) |
| P1-B | Capability Events JSONL concurrent-write corruption | `d6af073` | FIXED (claimed) |
| P1-C | Dev↔QA retry ceiling lacking mechanical enforcement | `2045bb8` | FIXED, hybrid (claimed, honestly caveated) |
| P1-D | Engram Sync hook alleged runtime failure | — | WITHDRAWN (Repair 04 — never a real bug) |
| P1-E | Security Backstop comment false positives | `dc461b0` | FIXED (claimed) |

Searched `git log --all --oneline \| grep -i "P1\|P0"` and both audit docs for any additional P0/P1 beyond these 5 — none found. `ARCHITECTURE-REALITY-AUDIT-V1.md` P0 section: none found (by design, that audit's own rubric). No sixth finding exists.

## Return Envelope (P1-A) — CLOSED

13 fresh fixtures (new literal data, not reused from Repair 01): uppercase→PASS, lowercase→PASS, conflicting `STATUS`/`status`→FAIL, missing required field→FAIL, invalid status→FAIL, qa_strict PASS/FAIL validity rules, dev_strict/design_strict wrong-vocabulary rejection, and explicit **casing-parity** checks (uppercase vs. lowercase envelope produce byte-identical error lists under dev_strict/design_strict's *other* substantive requirements). **13/13 matched expectation.**

Note: dev_strict and design_strict enforce real requirements beyond casing (`pre_return_audit`, a live `git status` superset check, `design_intelligence` consultation, `brand.references`) — a minimal fixture satisfying only casing correctly fails those separately. Not a bug; the parity tests isolate casing from those other gates correctly.

**Mutation sanity:** disposable worktree, casing-normalization block gutted → a real, correctly-formed uppercase envelope (exactly as every agent contract documents) is rejected with `Campos requeridos faltantes: {status, engram, tarea}` — the exact original P1-A symptom, reproduced on demand. Reverted, worktree removed.

## Capability Events (P1-B) — CLOSED

Real production `emit()` writer, fresh disposable temp file, independent corpus (`capability="p1-closure-audit-probe"`, distinct from Repair 02's fixtures), 20 events/process at **1, 5, 25, 50** concurrent real OS processes:

| n_processes | expected | valid_json | invalid_json | lost | duplicates |
|---|---|---|---|---|---|
| 1 | 20 | 20 | 0 | 0 | 0 |
| 5 | 100 | 100 | 0 | 0 | 0 |
| 25 | 500 | 500 | 0 | 0 | 0 |
| 50 | 1000 | 1000 | 0 | 0 | 0 |

**Mutation sanity:** disposable worktree, cross-process lock removed → same 50-process trial: expected 1000, only 893 raw lines, 870 valid, **3 invalid JSON, 107 events lost outright**. Corruption reproduces on demand. Reverted, worktree removed.

**Real runtime:** `.pipeline/capability-events.jsonl` — 3,800 lines, **0 invalid JSON anywhere in the file**, most recent entry timestamped during this very audit session. Healthcheck run mid-audit added 7 more real events, all valid, no corruption, no lock contention observed.

## Dev↔QA Retry Ceiling (P1-C) — RETRY_MECHANISM: CLOSED · INVOCATION_ENFORCEMENT: NOT CODE-ENFORCED (confirmed, reclassified P2)

**RETRY_MECHANISM**, fresh `task_id`, isolated temp `project_root`, direct `QARetryState` calls: attempt 1/2 → not reached, attempt 3 → `retry_limit_reached=True`, read-only recheck → still blocked, **persists across a fresh `QARetryState` instance and a fresh OS process** (subprocess re-read confirmed `3 True`), PASS clears the counter, a second unrelated `task_id` starts fresh, `infra_error` does not increment, and a hand-corrupted state file **fails closed** (blocks rather than silently permitting unlimited retries). **11/11 PASS.**

**INVOCATION_ENFORCEMENT**, tested directly against the real API surface: `grep` confirms `record_qa_attempt`/`check_qa_retry_limit`/`reset_qa_retry_state` are called from **zero** hook files and from no other mandatory dispatcher method (not wired into `validate_return_envelope` or any other call every QA cycle must make). Demonstrated concretely: 10 consecutive well-formed `qa_strict` FAIL envelopes for the same task, calling `validate_return_envelope` only, were **all accepted with no blocking, no warning, and no side-effect on the retry counter** — the exact bypass the original honest disclosure described, now reproduced on demand rather than assumed.

**Severity reassessment (not carried over automatically):** `.claude/agents/refs/orchestrator-pipeline-phase-3.md` shows the call is more than a discardable side-effect — step 7 (QA FAIL) calls `record_qa_attempt` and the orchestrator's *very next decision* (re-delegate vs. escalate) is read directly from that call's return value (`r["retry_limit_reached"]`). An orchestrator that skips the call cannot correctly decide what to do next through its own documented playbook — skipping isn't a free bypass, it requires the LLM to also improvise a substitute decision procedure, a more visibly-broken failure mode than a silently-dropped bookkeeping call. No `PreToolUse`-style interception point exists in this architecture to close the gap further (confirmed by prior audits and re-confirmed here); this is a structural limit of prompt-orchestrated delegation, not a fixable oversight. Given: (a) a real, demonstrated bypass exists, but (b) it's architecturally load-bearing rather than optional, (c) it's the same enforcement class as several other already-accepted CONTRACTUAL-only mechanisms in this system (phase ordering, agent selection), and (d) no mechanical fix is available under current constraints — this is reclassified **P2** (down from what would read as P1 in isolation), not silently held at its prior rating and not waved off as `ACCEPTED_LIMITATION` either, since it remains a legitimate target for a future interception mechanism if one becomes architecturally possible.

## Engram Sync (P1-D) — INDEPENDENTLY RECONFIRMED: NO_BUG

Both modes retested directly: `node engram-sync.js` (no flag) → exit 1 with an `ERROR` log line (correct, by design, for interactive/CLI use). `node engram-sync.js --hook` → **exit 0**, silent. Real registration source re-read: `templates/settings.json:52` confirms the exact registered string is `node __CLAUDE_HOME__/hooks/engram-sync.js --hook`.

**Mutation sanity, independently reproduced (not trusted from Repair 04's prose):** disposable worktree, hook-mode fail-open branch removed → `--hook` now exits 1 (the original bug, reproduced), and `_qa/bloque-F8-engram-audit.py` catches it: **8/10 PASS, 2 FAIL**, including `test_09_stop_chain_no_crash`. Reverted, worktree removed.

**Determination: BUG_EXISTS = NO.** Confirmed independently, not assumed from the prior repair's own account.

## Security Backstop (P1-E) — CLOSED

Brand-new 26-case corpus (different function/variable names and wording from Repair 05's own `_qa/bloque-security-backstop.py`), covering all 7 rules × {real vulnerability, comment lookalike, safe control} plus URL strings, a documentation string inside a template literal, a regex literal adjacent to real code, an escaped-quote string preceding real code, and a multi-line JSX block comment: **TP=9, TN=17, FP=0, FN=0.**

**Mutation sanity (both directions, different specific mutation targets than Repair 05 used):**
- Comment masking disabled → this independent corpus's own 7 comment-lookalike cases all fire → **FP=7**, detected.
- `SEC-CORS-001`'s regex neutered (Repair 05's own mutation used `SEC-EVAL-001` — deliberately different here) → the CORS vulnerability case → **FN=1**, detected.

Both reverted, worktree removed. Confirms detection power independent of the original repair's specific test choices.

## Cross-Fix Interactions — all 5 clean

1. **Envelope + QA retry**, same task, in sequence: both correct at every step, no shared-state interference.
2. **QA retry + invocation logging**: real dispatcher `record_qa_attempt()` (which internally calls both `_record_invocation` and `QARetryState`) — both succeed, invocation audit confirms the call was logged, no recursion. Test task reset afterward, no residue.
3. **Capability events + healthcheck**: healthcheck itself emits real capability events (3,800 → 3,807 lines during this audit) — all valid JSON, healthcheck still PASS=25/WARN=1/FAIL=0.
4. **Security Backstop + hook execution**: `quality-gate.js` and `console-log-warning.js` run against the same Write payload (both `async`, same PostToolUse matcher) — both fire correctly and independently; `console-log-warning.js` never touches `security-signals.jsonl`, so no shared-file risk.
5. **Engram hook + session Stop config**: `_qa/bloque-F8-engram-audit.py`'s Stop-chain test (`session-summary.js` + `engram-sync.js --hook` together) re-run fresh on `main`: clean, no crash.

## False Success Check

Every verdict above was checked against a real artifact, not printed text: `validate_return_envelope`'s actual boolean/list return values; the real `.pipeline/capability-events.jsonl` and `.pipeline/qa-retry-state.json` contents parsed as JSON; real subprocess exit codes (`$?`) for `engram-sync.js`; and a spot-check of `.claude/logs/security-signals.jsonl` confirming a real independent-corpus finding has every required field (`id/category/severity/path/line/evidence/confidence/msg/timestamp`) with no gaps.

## Local / CI

No code was changed in this audit, so no new commit or CI run was needed. Local baseline (this document's own §Baseline) was measured against `dc461b0`, the same commit already confirmed green on CI (run `35999940017`) at the end of Stability Repair 05 — consistent.

## Residual Limitations / Accepted

- **Dev↔QA invocation enforcement** — P2 (see above), not code-enforced, structurally unfixable under current architecture, load-bearing in the documented control flow.
- **Security Backstop string-literal ambiguity** — a string literal quoting real vulnerable syntax as documentation prose can still fire (e.g. a comment-like sentence embedded in a string rather than a `//`/`/* */` comment). Deliberately left unfixed since suppressing string content would reintroduce false negatives for the exact payloads several rules exist to catch. `ACCEPTED_LIMITATION` / P3 — over-detection, not under-detection; already documented in `docs/HOOKS.md`.
- **`agents/refs/` SOT/dist sync gap** (pre-existing, flagged during Repair 03, not part of this P1 inventory) — noted for completeness, not reclassified here; out of this audit's scope.

## Reclassified Findings

| Finding | Prior status | This audit | Change |
|---|---|---|---|
| P1-A Return Envelope | FIXED (claimed) | **CLOSED** (independently verified) | confirmed |
| P1-B Capability Events | FIXED (claimed) | **CLOSED** (independently verified) | confirmed |
| P1-C retry *mechanism* | FIXED, hybrid | **CLOSED** (independently verified) | confirmed |
| P1-C invocation *enforcement* | implicitly bundled into "hybrid" | **P2**, split out explicitly | reclassified, made explicit |
| P1-D Engram Sync | WITHDRAWN | **NO_BUG**, independently reconfirmed | confirmed |
| P1-E Security Backstop | FIXED (claimed) | **CLOSED** (independently verified) | confirmed |

## Open P0

None.

## Open P1

**None.**

## Open P2

- Dev↔QA invocation enforcement not code-enforced (see above).

## Open P3

- Security Backstop string-literal ambiguity (see Accepted, below — functionally P3/accepted, listed here for completeness).

## Accepted Limitations

- Security Backstop string-literal ambiguity (over-detection only, deliberate, documented).
- Dev↔QA invocation enforcement has no available mechanical fix under the current Claude Code architecture (no `PreToolUse`-style interception point for Agent/Task delegation exists); tracked as P2 rather than accepted outright, since a future architectural change could close it.

## P1 Closure Verdict

**P1_CLOSURE_CONFIRMED — ZERO_OPEN_P1**
