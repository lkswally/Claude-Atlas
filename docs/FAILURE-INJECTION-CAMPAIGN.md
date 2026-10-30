# Failure-injection campaign (roadmap P16)

Goal: show that ATLAS behaves safely when its critical dependencies fail, using failures injected at real
boundaries (a real subprocess that hangs or lies, a real unwritable file, a real killed writer), not only
mocked return values.

**Pre-registration.** Section 2 was written and saved BEFORE any scenario was run. Results are in section 4, and
every place where the system differed from a pre-registered expectation is listed in section 5 with what was
done about it (the system was fixed, or the expectation was amended with a stated reason). Expectations were
not edited to match behaviour.

## 1. Success rule (all eight must hold, per scenario)

| # | Rule | How it is checked |
|---|---|---|
| R1 | the failure is **detected** | the pre-registered detection signal is present in the result/status |
| R2 | **no false success** | terminal state is never SUCCEEDED/ok/found unless the work truly happened; no text/content is fabricated |
| R3 | recovery is **bounded** | execution/attempt/spawn counts and wall-clock are within the pre-registered ceiling |
| R4 | an **unsafe fallback is rejected** | whatever ran or was handed off is in the set the task's hard constraints allow (HIGH never reaches a provider that is not eligible for HIGH) |
| R5 | **evidence** records what happened | result fields / status / log entry name the failure class and the path taken |
| R6 | retries **do not loop** | counters never exceed the policy; the scenario ends without an external timeout |
| R7 | **security policy stays active** | after the failure, the secret-prompt pre-filter still blocks, the `block-no-verify` hook still blocks, hard eligibility still excludes ineligible models |
| R8 | **cost policy stays active** | nothing outside `cost_tier: configured_free` is ever selected or executed |

Task profiles used below: **T_LOW** = CODE / LOW risk (eligible: sonnet, opus, codex). **T_HIGH** = CODE / HIGH
risk (sonnet, opus; codex is not eligible). **T_CRIT** = CODE / CRITICAL risk (opus only). Direction **A** =
Claude fails (host-reported through `known_failures`; ATLAS cannot execute Claude). Direction **B** = Codex fails
(a real subprocess).

## 2. Pre-registered expectations

Provider failures (FI-01 … FI-08). Same shape per class; the class decides retry and the terminal state.

| ID | Injected failure | Detection | Owner | A: Claude fails, T_LOW | A: T_HIGH / T_CRIT | B: Codex fails (ATLAS-executable only) | Retry | Human gate | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| FI-01 | Claude timeout (host reports "timed out") | `classify_failure` -> TIMEOUT; `provider_health[model] = TIMEOUT` | host executes, ATLAS routes | SUCCEEDED on codex, `fallback_used` | WAITING_PROVIDER (no Codex) | n/a | 0 (ATLAS did not run it) | none; WAITING is handed to the orchestrator | `attempts`, `provider_health`, `blockers` |
| FI-02 | Codex timeout (fake binary hangs; its child process too) | runner timeout, TIMEOUT, process tree **dead** afterwards | `CodexCliProvider` + fallback executor | n/a | n/a | WAITING_PROVIDER after exactly 2 spawns (1 + 1 retry); then a Claude re-route yields HANDOFF to a Claude model eligible for the task (CRITICAL: opus only) | 1 same-provider retry, only if idempotent | none | `attempts` (2), spawn counter, no surviving process |
| FI-03 | provider rate limit | RATE_LIMITED | executor | fallback to codex | WAITING_PROVIDER | WAITING_PROVIDER, 1 spawn | 0 | none | class + state in `attempts` |
| FI-04 | provider quota exhausted | QUOTA_EXHAUSTED | executor | fallback to codex | WAITING_PROVIDER | WAITING_PROVIDER, 1 spawn | 0 | none | class + state |
| FI-05 | provider auth failure | AUTH_FAILED | executor | fallback to codex | NO_ELIGIBLE_PROVIDER (persistent) | NO_ELIGIBLE_PROVIDER, 1 spawn | **never** | **yes**: credentials are the owner's | class + state |
| FI-06 | model unavailable | MODEL_UNAVAILABLE | executor | fallback to codex | NO_ELIGIBLE_PROVIDER | NO_ELIGIBLE_PROVIDER, 1 spawn | 0 | none | class + state |
| FI-07 | malformed provider response (exit 0 with garbage; wrong result type from a provider object) | INVALID_RESPONSE; garbage never returned as `text` | `invoke()` guard / `CodexCliProvider` | n/a | n/a | WAITING_PROVIDER after 2 spawns | 1 | none | class, no `text` |
| FI-08 | both providers unavailable (Claude host-reported + Codex quota) | per-provider classes | executor | WAITING_PROVIDER, no text | WAITING_PROVIDER | same | each provider tried at most per policy | none | `blockers` names both |

Review and system failures.

| ID | Injected failure | Detection | Owner | Expected state | Fallback | Retry | Human gate | Evidence |
|---|---|---|---|---|---|---|---|---|
| FI-09 | reviewer unavailable (the model(s) that would review are RATE_LIMITED / AUTH_FAILED) | `plan_review` excludes unhealthy reviewers | `review_independence` | `degraded: true` with a reason; never a pass at the required level; **no reviewer -> `reviewer_model` None** | a weaker reviewer only if it is eligible AND the plan says so | 0 | **required whenever HIGH/CRITICAL cannot reach its required level** (not only for a silent self-review) | `plan_review` fields; `verify_review_record.meets_policy` false |
| FI-10 | Engram unavailable: binary missing; binary hangs in `initialize`; exits at once; replies with malformed JSON; replies with a JSON-RPC error; replies `ambiguous_project` | bridge status `timeout` / `ambiguous_project`; `dispatcher.engram_mcp_status` starts with `unavailable` | dispatcher + `EngramStrategy` | **phase gate: DEGRADED_CONTINUE only if the dual-write disk copy exists (source says `disk_fallback`), otherwise FAIL_CLOSED (cannot proceed).** `ambiguous_project` and unknown statuses are FAIL_CLOSED, never a pass. `get_cajon_full`: `timeout` is never `not_found`. State owned elsewhere (QA retry, delegation, router decisions) is unaffected and never reads Engram | disk copy only | 0 beyond the bridge's single crash retry | on FAIL_CLOSED (existing "PENDING: user confirms") | status field, `source` |
| FI-11 | MCP server unreachable, reported by the host (e.g. `context7` CONNECT_TIMEOUT, `github` CONNECTION_CLOSED) | the capability router accepts a host-reported failure | capability router | the failed provider is **not** reported LIVE / `use`; result is UNAVAILABLE unless a *different* provider of the same capability is not itself reported failed; a fallback is labelled **declared**, never verified | different declared provider of the same capability only | 0 | policy decides (BLOCK or WARN), never ALLOW | `Resolution` fields + capability event |
| FI-12 | capability unavailable / health UNKNOWN / malformed: unknown name; `ATLAS_CAPABILITIES_DISABLED`; empty provider list; provider with a malformed status; malformed or missing policy file; malformed events file | `resolve_capability` / `evaluate_capability` | capability router + policy | UNAVAILABLE, `provider None`, no tool prefix; never ALLOW; never raises; malformed events lines skipped | none invented | 0 | policy | `Resolution`, `PolicyDecision` |
| FI-13 | telemetry append fails (target is a directory; read-only file; unwritable) | `AppendResult.ok == False` with a reason, one stderr notice, `status()` | `bounded_jsonl` | the **business operation continues** (documented fail-open) but its result never states or implies the event was recorded; no entry is created that could be read as success | none | bounded by the 30 s retry throttle | none | `AppendResult`, `status()` |
| FI-14 | telemetry rotation fails (archive path is a directory; rotation lock held by another process; malformed archive) | rotation error surfaced; `status().over_bound` | `bounded_jsonl` | append still safe, no line lost or torn; `over_bound` true while rotation cannot proceed; a malformed archive never breaks reads | none | bounded | none | `status()` |
| FI-15 | malformed execution state: `qa-retry-state.json` (truncated; empty array; wrong version; negative / non-numeric counts; tasks not an object; binary); `delegation-state.json` (same) | load result | `qa_retry_state` (FAIL_CLOSED by documented policy), `delegation_tracker` (advisory, documented DEGRADED_CONTINUE) | QA retry: `retry_limit_reached: true` with `state_error` for **every** variant, and the unreadable file is **not silently overwritten with defaults**. Delegation: continues with defaults, never raises | none | 0 | QA retry: the existing escalation | `state_error` |
| FI-16 | duplicates: same QA failure recorded twice; the same `attempt_id` twice; concurrent recorders; same provider `request_id` twice; one model retried twice inside a run | counters | `qa_retry_state`, executor | counter is monotonic, bounded, no lost update; **a repeated `attempt_id` does not count twice**; an un-ided duplicate counts (safe direction: earlier escalation) and is documented; the executor never exceeds `max_attempts` and never re-runs a model it learned is failed; a repeated provider `request_id` is **not detectable** (stateless executor) and is recorded as an accepted gap, not claimed as handled | none | each model: policy retries only | none | counters |
| FI-17 | checkpoint interruption: writer killed between the temp write and the rename (delegation); killed mid-write (QA retry); killed during telemetry rotation | file contents afterwards | `delegation_tracker`, `qa_retry_state`, `bounded_jsonl` | delegation: previous valid state intact. QA retry: **never** read as "no attempts" (fail-closed with `state_error` at worst). Telemetry: current + archive both parseable. Provider executor persists no checkpoint, so there is nothing to interrupt (NOT_APPLICABLE, stated) | none | 0 | QA retry torn file: owner repairs, documented | file contents |

Pre-registered bounds: Codex spawns <= 2 for TIMEOUT / INVALID_RESPONSE, == 1 for every other class; executor
`attempts` <= `max_attempts` (4); a scenario must finish without an external timeout; process trees must be
dead within 5 s of the timeout.

## 3. Method

* Offline, deterministic, no network, no Codex tokens: `_qa/bloque-F45-failure-injection.py`. A fake `codex`
  and a fake `engram` are real executables launched through the real runners, so process handling, timeouts,
  tree-kill, stdin, and environment scrubbing are the production code paths.
* `--live` repeats three provider failures against the real Codex CLI (bad model, empty `CODEX_HOME`, 1.5 s
  timeout) through the routed executor.
* Mutation sanity over the files that carry the behaviour; any surviving critical mutant is TEST_FALSE_CONFIDENCE.

## 4. Results

`python _qa/bloque-F45-failure-injection.py`: **124 checks, 106 judged scenarios, 0 failures, ~37 s** (Quick suite;
runs on Linux CI). `--live` adds 3 scenarios against the real Codex CLI (all pass, ~9 s, three tiny requests).

| Family | Scenarios judged | Notes |
|---|---|---|
| FI-01..FI-08 provider failures | 33 | A (Claude, host-reported) and B (Codex, real subprocess) for TIMEOUT, RATE_LIMITED, QUOTA_EXHAUSTED, AUTH_FAILED, MODEL_UNAVAILABLE, INVALID_RESPONSE (garbage, no turn, empty), crash; HIGH/CRITICAL variants; both-unavailable; Claude hand-off after Codex fails; a healthy PAID model that must never run |
| FI-07 provider object faults | 7 | `None`, a dict, another request's result, `ok=True` with an error class, an exception, a result with no class, a provider that hangs |
| FI-09 reviewer | 5 | plus the healthy control |
| FI-10 Engram | 25 | 9 failure modes x disk copy present/absent, 2 healthy controls, unknown strategy statuses, operational state never consults Engram |
| FI-11 / FI-12 capabilities | 14 | host-reported failures, unknown health, malformed reports, disabled, empty, malformed status, malformed/missing policy, malformed events file |
| FI-13 / FI-14 telemetry | 13 | directory / read-only / missing parent / unserialisable, tracker, broken tracker (3), router log, rotation impossible, lock held elsewhere, malformed archive |
| FI-15 state | 11 + 1 | 11 QA-retry-state shapes, delegation state |
| FI-16 duplicates | 4 | concurrent writers, un-ided duplicate, `attempt_id`, repeated `request_id` (accepted gap) |
| FI-17 interrupted writes | 4 + 1 | delegation rename, QA retry mid-write (torn file proven), telemetry rotation before/after the rename, executor statelessness |

Rule application over the 106 scenarios: R1, R2, R3, R5, R7 apply to all; R4 to 79; R6 to 70; R8 to 33. A rule that
cannot apply is reported `NA`, never counted as held. The judge is itself checked against fabricated bad results (O1..O9:
a success with no text, an ineligible model, a logged-but-undone retry, a dropped retry, too many spawns, a surviving
process, a non-free model, a failed security probe, a failure reported as success): each must be judged FALSE.

**Mutation sanity: 41 mutants, 41 caught, 0 survivors** over provider health filtering, hard eligibility, the fallback
ceiling and retry budgets, failure classification, the `invoke()` guards, the secret pre-filter, the cost policy,
reviewer independence, the Engram gate and bridge, telemetry failure handling, QA-state validation, the lock and the
capability port. Two mutants survived the first pass and were treated as TEST_FALSE_CONFIDENCE, not explained away:
P15 (no `invoke()` timeout backstop) was pointed at the wrong section by the mutation script, and E5 (a reply with the
wrong JSON-RPC id accepted) was masked because the fake's stale reply carried unclassifiable text, so the tightened
parser turned it into a timeout anyway; the fake now sends a plausible "Found 1 memories" payload. Both are caught.

## 5. Divergences and decisions

Baseline: the runs against the unmodified system failed 34 scenarios (33 caused by the system, 1 by a bug in the
harness). Each defect is listed with what was done.
No pre-registered expectation was relaxed. Two things were made STRICTER while writing the harness: R6 is checked as
the exact spawn count (the pre-registered text said "<= bound"), and the human gate for a degraded review is an R4
(unsafe-fallback) condition.

| # | Found by | Defect (reproduced on the unmodified system) | Decision |
|---|---|---|---|
| D1 | FI-02B, FI-07B-crash | A `TIMEOUT` was logged as `action: RETRY` but the retry never ran: the provider's own health memory (`TIMEOUT`) made the router exclude it on the next pass, so the policy "one same-model retry" silently became zero retries (1 spawn instead of 2). Fakes in F43 never exposed it because their health was static. | **Fixed** (`tools/provider_fallback.py`): a same-model retry re-runs the model just selected for the same task and does not go back through the health filter. Confirmed live (L3). |
| D2 | FI-09a | A HIGH-risk review degraded to a same-model reviewer needed no human gate (only a silent self-review did). | **Fixed** (`tools/review_independence.py`): HIGH/CRITICAL needs the gate whenever the required level is not reached. |
| D3 | FI-10 (3 scenarios) | `enforce_phase_gate` had no branch for `ambiguous_project` or any unknown status, so the phase gate PASSED with no verified cajon and no disk copy. | **Fixed** (`tools/atlas_dispatcher.py`): only found / not_found answer the question; anything else takes the disk-copy-or-PENDING path. |
| D4 | FI-10 weird_found | "Memory not found for that topic" was classified `found` because the text contains "found"; an unclassifiable reply was assumed `not_found`, which triggers re-delegation. | **Fixed** (`tools/engram_mcp_bridge.py`): `found` needs a result id or a "Found N memories" header (the real format, checked against a live `mem_search`); an unclassifiable reply is an error (`timeout`), never an absence. |
| D5 | FI-10 wrongid | A reply whose JSON-RPC id did not match the request was accepted as its answer when nothing followed. | **Fixed** (same file): protocol error, retried once by the existing crash path, then `timeout`. |
| D6 | FI-11 (7), FI-12 R5 (6) | The capability router answers from a STATIC registry and has no way to be told a server failed: this very session reported `context7 CONNECT_TIMEOUT` and `github CONNECTION_CLOSED` while `documentation` would have resolved `LIVE` / `use`. | **Fixed with a port** (`core/capabilities/router.py`, `policy.py`): `resolve_capability(..., observed=)` and `evaluate_capability(..., observed=)` take host-reported provider states, fail CLOSED on unrecognised values, never select a provider reported down, and label every answer `evidence: declared` or `host_reported`. **Not closed: nothing feeds the port automatically yet (AG-5).** |
| D7 | FI-13f/g/h | `ATLASDispatcher.audit_invocations` returned `verdict: "complete"` when the tracker could not be imported or raised, and `enforce_helpers_for_agent` then reported hard enforcement `passed` for a CRITICAL agent: a telemetry failure became evidence of success. | **Fixed** (`tools/atlas_dispatcher.py`): fail CLOSED (`incomplete`, every required helper missing, `audit_error` visible). |
| D8 | FI-15 (6 of 11) | A QA-retry state file that parsed as JSON but was not a state (an array, `null`, a string, another version, `tasks` a list, a negative count) was silently replaced by defaults, RESETTING every attempt counter, and the next record overwrote the file: the unlimited-retries outcome the module exists to prevent. Malformed JSON already failed closed. | **Fixed** (`tools/qa_retry_state.py`): `_validate_state`; unreadable state fails closed like malformed JSON and the file is left untouched. |
| D9 | FI-16c | No way to make a repeated QA outcome idempotent. | **Added** an optional `attempt_id` (`tools/qa_retry_state.py`); without one every `fail` counts, which only brings escalation earlier (FI-16b). |
| H1 | FI-14b | Harness bug, not a system defect: the test patched a second copy of `bounded_jsonl`. | Harness fixed. |

Accepted gaps, stated so they are not mistaken for coverage:

* **AG-1** A repeated provider `request_id` is not detected (the executor is stateless). Each call stays bounded and truthful (FI-16e).
* **AG-2** A QA-retry write torn mid-way leaves the file unreadable; the system fails closed (proven, FI-17b) and a human must repair or delete it. No automatic recovery.
* **AG-3** An interrupted delegation-state write leaves one stray temp file (FI-17a). Harmless, not cleaned.
* **AG-4** If the ATLAS process is hard-killed while a Codex request is running, the Codex child keeps running until it ends by itself (no job object). Not asserted.
* **AG-5** There is no automatic producer of host-reported MCP state. Until one exists, the capability router answers from declared status, now clearly labelled `declared`, which is what it always was.
* **AG-6** `dispatcher.engram_mcp_status` is set when the dispatcher is built; a bridge that fails later is visible per call (`source`, `status`), not in that field.
* **AG-7** Claude models cannot be executed or health-checked by ATLAS, so "Claude fails" is always HOST-REPORTED (`known_failures`), never ATLAS-observed.
* **AG-8** Codex rate-limit and quota wording in the fakes is synthetic; the live cases cover only a missing model, a missing login and a timeout, because those can be produced safely.
* **AG-9** The delegation tracker resets a malformed advisory state to defaults (documented DEGRADED_CONTINUE) and rewrites the file on its next save.
* **AG-10** Process restart / resume of an orchestrated run is not tested (the architecture has no resumable executor state); only interrupted writes are.
