# Stability Phase 2 Remediations

Concise remediation log for P2/P3-class findings raised in `docs/P1-CLOSURE-AUDIT-V1.md`. Kept separate and short by design, so it doesn't distort the `architecture_audit.py` size heuristic the way `STABILITY-HARDENING-AUDIT-V1.md` already does.

## Stability Repair 06 — Dev↔QA Retry Invocation Enforcement (2026-09-24)

**Source:** `docs/P1-CLOSURE-AUDIT-V1.md`, Dev↔QA Retry Ceiling section — reclassified **P2 — STRUCTURAL / LOAD-BEARING / BYPASSABLE**. The retry *mechanism* (counting, persistence, fail-closed) was independently confirmed correct; nothing mechanically forced `record_qa_attempt()`/`check_qa_retry_limit()` to be called at all, and 10 consecutive QA FAIL envelopes were demonstrated passing through the normal validation path with zero retry-state interaction.

**Pre-fix reproduction (fresh):** a brand-new `task_id`, 4 consecutive `validate_return_envelope(mode="qa_strict")` FAIL calls — `.pipeline/qa-retry-state.json` never gained an entry for the task, confirmed by direct read before/after.

**Mandatory boundary chosen:** `validate_return_envelope(mode="qa_strict")` itself — not the generic validator (used by `dev_strict`/`design_strict`/`standard` for unrelated agents, 45 files reference it), but specifically the `qa_strict` mode, which `protocol-agent-contract-core.md`'s own Runtime Wiring Contract table documents as used **exclusively** "tras recibir envelope de evidence-collector" — i.e., only the Dev↔QA loop.

**Fix:** `validate_return_envelope()` gained one new optional parameter, `task_id: Optional[str] = None`. Default behavior (parameter omitted) is byte-identical to before — verified against every mode and every existing caller. When `mode == "qa_strict"` **and** `task_id` is supplied, the same call that the orchestrator already cannot skip (it must know if the envelope is valid) now also performs the exact accounting `record_qa_attempt()` always did — invalid envelope → `infra_error`, `STATUS=PASS` → `pass`, `STATUS=FAIL` → `fail` — and attaches the result to `response["_dispatcher_qa_retry"]` (same in-place-mutation pattern as `_dispatcher_warnings`/`_dispatcher_enforcement`).

**Double-counting protection:** `.claude/agents/refs/orchestrator-pipeline-phase-3.md` (SOT) and its `agents/refs/` mirror updated — the orchestrator now passes `task_id` at the one validation call it already makes, and the previously-separate manual `record_qa_attempt` calls in steps 3/6/7 were removed from the contract (replaced with reading `qa_response["_dispatcher_qa_retry"]`). Step 4's Engram-write-failure case (detected *after* envelope validation, a genuinely separate failure point) still calls `record_qa_attempt` manually, unchanged — correct, since it can never be folded into the envelope-validation call. **Residual, disclosed risk:** `record_qa_attempt` remains directly callable (by design — step 4 needs it), so a stray legacy manual call alongside the new automatic path would still double-count; confirmed by direct test. This is an `INTERNAL_API_BYPASS`-class risk (requires the orchestrator to actively call a function its own updated contract no longer instructs it to call), not the `NORMAL_RUNTIME_BYPASS` this repair closes (forgetting to do anything extra at all).

**Tests:** `_qa/bloque-qa-retry-ceiling.py` grew from 13 to 28 tests — 15 new integration tests (14–28) exercising the real `ATLASDispatcher.validate_return_envelope` runtime path: auto-count on FAIL, ceiling reached at 3, PASS resets, new task starts fresh, invalid envelope classified as non-counting `infra_error`, persistence across a fresh dispatcher instance and a fresh OS process, no double-counting on a single call, `phase_gate_retries` unaffected, invocation logging confirmed, malformed state fails closed, and casing parity preserved. **28/28 PASS.** Separately verified (ad hoc, not a permanent test): task identity is stable under completely rephrased `TAREA`/`BLOQUEADORES` text for the same `task_id`.

**Mutation sanity (disposable worktree, 3 mutations, all reverted):**
- A — automatic accounting call disabled → 13/28 FAIL, including the direct bypass-regression test.
- B — ceiling comparison in `qa_retry_state.py` forced to `False` → 4/28 FAIL, exactly the ceiling-dependent tests.
- C — invalid-envelope classification forced to `"fail"` instead of `"infra_error"` → 2/28 FAIL, exactly the classification tests.

No mutation left the suite green.

**Concurrency:** the Dev↔QA loop is architecturally sequential per orchestrator session (one evidence-collector delegation in flight at a time for a given `task_id`); no new concurrency primitive was added. The underlying `QARetryState` cross-process lock (unchanged, already proven safe under 10 concurrent OS processes in the pre-existing test 13) still protects the theoretical cross-session case.

**Full validation:** Healthcheck 25/1/0, Quick 42/42, Release 45/45, `atlas_verify` 8/8, secrets clean, claim linter 0 HIGH/CRITICAL, boot tokens 1,841 unchanged, CI green.

**Files modified:** `tools/atlas_dispatcher.py`, `_qa/bloque-qa-retry-ceiling.py`, `.claude/agents/refs/orchestrator-pipeline-phase-3.md` (SOT) + `agents/refs/orchestrator-pipeline-phase-3.md` (dist, manually synced — this subdirectory is outside `sync_dist.py`'s coverage, a pre-existing known gap).

**Status:** P2 finding **CLOSED**. `QA_RETRY_INVOCATION_FIX_KEEP`.
