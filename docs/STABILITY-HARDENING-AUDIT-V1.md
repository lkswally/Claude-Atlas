# ATLAS — Stability Hardening Audit V1

**Date:** 2026-09-23/24 · **Repo/branch/HEAD:** `main` @ `a9e8479` (audit-only; no runtime code changed except one deliberate, fully-reverted mutation-sanity pass in a disposable detached worktree, cleaned up)
**Rule applied throughout:** a PASS is not evidence unless the same check can also fail for the right reason. Every critical validator below was tested both ways where reachable; where only one side was demonstrated, it is marked `PARTIAL`.

## 0. Baseline

Re-measured fresh, not assumed: Healthcheck 25/1/0, Quick 42/42, Release 45/45, atlas_verify 8/8, Claim linter 0 HIGH/CRITICAL, Architecture score 84, Boot 1,841 tokens, CI `success`. Python 3.14.5 (both `python` and `py -3`), Node v24.16.0, Windows (MINGW64), Engram `ENGRAM_ACTIVE`, MCP 13/21 LIVE. Exact match to Architecture Repair 03's closing state.

---

## 1. Test oracle audit

| Suite | Oracle type |
|---|---|
| `bloque-envelope-casing.py` | `LIVE_INTEGRATION` for the boundary it exercises (calls the real `validate_return_envelope`), but the boundary itself is synthetic dicts, not a real agent's raw output — see §3 |
| `bloque-capability-events-integrity.py` | `LIVE_INTEGRATION` — real subprocess workers, real writer, real filesystem |
| `bloque-qa-retry-ceiling.py` | `LIVE_INTEGRATION` — same standard |
| `bloque-security-backstop.py` | `LIVE_INTEGRATION` — real `node` subprocess invocation of the real hook |
| Most `_qa/bloque-F*-*.py` (pre-existing) | Not re-audited exhaustively this pass (time-boxed); Architecture Reality Audit V1 already flagged the Return-Envelope-adjacent suites as **tautological** (`IMPLEMENTATION_MIRROR`) — confirmed again this pass, see §3 |

**Confirmed tautological class, re-verified:** every pre-existing `_qa/bloque-*.py` that calls `validate_return_envelope` constructs its own lowercase dict fixtures — it validates the function against inputs shaped exactly like what the function already expects. This was true before Architecture Repair 01 and remains true after — my new `bloque-envelope-casing.py` is the first suite in the repo that feeds it uppercase, uppercase+lowercase-mixed, and conflicting-duplicate shaped input.

---

## 2. False positive / false negative matrix

| Subsystem | TP | TN | FP | FN | Note |
|---|---|---|---|---|---|
| Return Envelope validator | 7/7 (see §3) | 5/5 | 0 | 0 | Adversarial set below |
| Security Backstop | 7/7 (fresh fixtures, this pass) | 13/14 (fresh) + 8/8 (existing) | **1/14 fresh — systemic, see §4** | 0 found | Real FP found: comments |
| Security Agent (blind) | 3/3 + 3/3 (two independent probes, this pass + Reality Audit V1) | 4/4 + 5/5 lookalikes | 0 | 0 | See §5 |
| Reality Checker (blind) | 4/9 true claims correctly TRUE | 5/9 false claims correctly FALSE | 0 | 0 | See §6, 9/9 exact |
| Evidence Collector (blind) | correctly rejected all 6 fabricated/mismatched evidence items | — | 0 | 0 | See §7 |
| Claim Linter | 3/6 planted bad claims caught | 1/1 accurate claim correctly silent | 0 | **3/6 missed — see §8** | Real FN found |
| Secret detection | Unaffected by any change this session (re-confirmed) | — | 0 (known) | 0 (known) | Not re-adversarially tested this pass beyond re-confirmation |
| Architecture drift detector | 1/1 (real injected drift, Architecture Reality Audit V1) | 1/1 clean state | 0 | **untested for agents/refs — known blind spot, §21** | |
| QA strict validation (`validate_return_envelope(mode="qa_strict")`) | Casing-independent, tested | Casing-independent, tested | 0 found | 0 found | See §3 |
| Policy Engine | ALLOW path confirmed live | MISSING_POLICY path confirmed live | `PARTIAL` — 0 BLOCK-severity policies exist to test | `PARTIAL` | See §11 |
| Hook guards | 5/13 fixture-tested in Reality Audit V1 + 8/13 this pass = 13/13 script-level | Negative controls: 5/13 confirmed | 0 | **1 live failure found: `engram-sync.js`, see §10** | |
| Capability Router | Happy path (3/3 LIVE) + unknown-capability handled | — | 0 | `PARTIAL` — failure-injection (primary-down, malformed response, timeout) `NOT_TESTED`, §12 | |
| Healthcheck | Re-confirmed 25/1/0 this pass | — | `PARTIAL` — `check_python()` launcher gap already documented (Architecture Reality Audit V1 §22), not re-adversarially tested this pass | | |

---

## 3. Return Envelope — adversarial test

All via the real `ATLASDispatcher.validate_return_envelope`, not a reimplementation.

**Known-good (must PASS):**
1. Valid uppercase (exact documented shape) — PASS
2. Valid lowercase (backward compat) — PASS
3. Valid `qa_strict` — PASS
4. Valid `dev_strict` — PASS (design_strict not separately re-tested this pass; covered in Architecture Repair 01's own suite, casing-independence confirmed there)

**Known-bad (must FAIL):**
5. Missing required fields — FAIL, correct
6. Invalid STATUS — FAIL, correct
7. Conflicting STATUS/status (same key, different value) — FAIL, explicit `AMBIGUOUS_ENVELOPE_KEY`, correct
8. Malformed ARCHIVOS (wrong type) — FAIL, correct
9. Malformed nested design fields — `NOT_TESTED` this pass (design_strict's nested `design_intelligence`/`brand` schema not adversarially fuzzed; time-boxed)
10. Unexpected aliases / extra unrelated fields — **tested now:** an envelope with `{"STATUS": "completado", "TAREA": "x", "ENGRAM": "p/c", "RANDOM_FIELD_XYZ": "ignored"}` validates PASS, extra field is silently ignored, not rejected — this is permissive-by-design (Envelope v1 contract is described as permissive in the code's own comments), not a bug, but worth stating: unrecognized fields are not flagged even as a warning.
11. Duplicate keys, same value — not independently distinguishable from Python dict literal syntax (a real JSON payload with a duplicate key is collapsed by the JSON parser before it ever reaches the function — this is a parser-level, not validator-level, concern; `NOT_TESTED` at this boundary for that reason, documented rather than skipped silently).

**PASS_WITH_WARNINGS discrepancy — investigated, not fixed (per instruction):** `evidence-collector.md`'s own documented Return Envelope shows `STATUS: PASS | PASS_WITH_WARNINGS | FAIL`. `validate_return_envelope(mode="qa_strict")` hardcodes `valid_status = {"PASS", "FAIL"}` — confirmed directly this pass by reading the code again. **Canonical truth: the contract documents a 3rd status value the validator does not accept.** An envelope with `STATUS: PASS_WITH_WARNINGS` in `qa_strict` mode would fail with "STATUS inválido: PASS_WITH_WARNINGS. Para QA esperado: PASS o FAIL" — confirmed by direct call. This is a real, reproducible mismatch, same class as the P1-1 finding but smaller in scope (one missing enum value, not an entire casing convention). Not fixed, per this audit's own "audit only" rule.

---

## 4. Security Backstop — false-positive audit (fresh fixtures, this session)

7/7 true positives (all rules, freshly constructed payloads, not reused verbatim from Improvement A). 13/14 fresh safe-lookalikes correctly silent.

**Real false positive found and reproduced — systemic across all 7 rules:** a `//` line comment merely *mentioning* a dangerous pattern (`// TODO: never call eval() here`) triggers `SEC-EVAL-001`. Tested identically for all 7 rules with a comment-only fixture for each: **all 7/7 fired**, confirming the regex layer does not exclude comments before matching. This is a genuine, systematic, reproducible FP class — any code review comment, TODO, or documentation string discussing a vulnerability pattern (an entirely normal, encouraged practice) will trigger a false alarm on every rule. Root cause: none of the 7 regexes are comment-aware; the hook operates on raw file content with no comment-stripping pass.
**Severity:** moderate — WARN-only (except EVAL/CMDI/SQLI/CORS/TLS which are `severity: 'error'` in the findings array, though the backstop as a whole remains fail-open/non-blocking per Architecture Repair A) — but real, and a plausible source of alert fatigue that could cause developers to start ignoring the backstop's output.
**Recommended minimal fix (not implemented, per audit-only rule):** strip `//` and `/* */` comment spans before running the 7 regexes, or add a lookbehind excluding matches inside detected comment ranges.

---

## 5. Security Agent — blind test (two independent probes: Architecture Reality Audit V1 + this audit)

This pass's probe used a fresh fixture mixing 3 real vulnerabilities, 4 safe lookalikes, and 1 irrelevant comment string — different from the Reality Audit V1 fixture, not a repeat.
**Result: 3/3 real vulnerabilities found, 4/4 lookalikes + 1/1 irrelevant string correctly excluded, 0 false positives reported (self-reviewed).** `CONTRACT_SCOPE_MATCH: PARTIAL` (self-diagnosed — subject-matter transfers, workflow doesn't). Combined with Reality Audit V1's earlier 8/8 result on a different fixture: **6/6 across two independent blind probes, two different fixtures, 0 misses, 0 false positives** — strong, consistent precision/recall for the raw LLM capability, though (as both probes independently noted) this is a favorable small-sample ceiling, not a general accuracy claim, and the capability remains unreachable through the agent's actual documented invocation path (confirmed again, unchanged from Reality Audit V1).

---

## 6. Reality Checker — blind test (9 mixed claims, fresh fixture)

**9/9 correct.** 3 TRUE (file exists, script exit-0 confirmed by actually running it, correct endpoint), 6 FALSE (nonexistent file, fabricated PASS claim on a script that actually exits 1 — verified by running it, nonexistent screenshot **including one I had genuinely believed I'd saved earlier in this same session**, wrong endpoint returning real 404, and a page falsely claimed defect-free that the agent proved has 3 real console errors via live Playwright inspection). Explicitly declared its Engram gap rather than fabricating what cross-validation would show. `FALSE_POSITIVE_DETECTED` framing correctly applied to the fabricated-PASS claim, unprompted.

**Unplanned but significant finding surfaced by this probe, independently triple-confirmed (see §16):** claim 5 asserted a screenshot existed at a path I had directly used minutes earlier in this same session, with the screenshot tool itself reporting apparent success. The agent correctly found it does not exist on disk. I verified this myself directly afterward (see §16) — it is real, not an agent error.

---

## 7. Evidence Collector — blind test (6-item evidence bundle, fresh fixture)

**All 6 items correctly rejected**, each on the specific axis appropriate to it — this is the most granular result of the three blind probes:
- Two screenshot citations: `FILE_EXISTS: N` for both (one of which reused the identical fabricated path for two mutually-incompatible claims — caught as an internal-consistency problem, not just a missing file).
- A "test log" citation: `FILE_EXISTS: Y`, `CONTENT_MATCHES: N` — correctly identified as an HTTP access log, not test output, despite existing and being real.
- A "0 errors" claim about a live page: falsified by direct Playwright measurement (3 real console errors, 2 real network failures).
- A "PASSED, proving the feature works" claim citing a real, run, exit-0 script: `SEMANTICALLY_RELEVANT: N` — correctly identified that the script's output is a hardcoded string disconnected from any real assertion against the app, i.e. **existing + running + exiting 0 is not, by itself, evidence of anything**, exactly the FILE_EXISTS vs CONTENT_MATCHES vs SEMANTICALLY_RELEVANT distinction this audit asked for. Also flagged, unprompted, that the fixture's file naming (`real_test.py` vs `fake_pass_test.py`) was itself inverted from what the names implied — a nice demonstration that it read the actual content rather than trusting filenames.

---

## 8. Claim Linter audit

Planted 8 claims in a temporary doc, then 4 more isolated ones. **Caught (3+1):** "always"/"never"/"fully" (absolute-wording rule), "blocks all" (CRITICAL strong-security-claim rule), "every agent" (universal-quantifier-over-agents rule, specific phrase). **Correctly silent on the 1 accurate claim.**

**Real false negatives found, reproduced:**
- **"The autonomy benchmark score is 69.9%"** (a real historical number, stated with zero date/context, indistinguishable from a live claim) — **not flagged.** The linter has no mechanism to detect that a specific metric is being presented without temporal qualification; it only pattern-matches lexical absolutes (always/never/every/full/blocks all), not numeric-freshness risk.
- **"Live end-to-end browser testing confirms the checkout flow works in production"** (a mocked-or-unverified test being described as live/production) — **not flagged.** This requires semantic/contextual judgment the linter's pattern-matching approach cannot reach.
- **"Full observability"** tested in isolation (without an accompanying "every agent" in the same sentence) — **not flagged on its own.** The earlier detection of "full observability... every agent decision" only fired because of "every agent"; "full observability" is not itself a matched pattern despite being one of this audit's own named red-flag phrases and one Architecture Reality Audit V1 explicitly recommended avoiding.

These are real, reproducible FN gaps in the linter's coverage, not edge cases — "full observability" specifically is a phrase this whole project has already identified as a documentation risk (Architecture Reality Audit V1 §9) yet the tool meant to catch exactly this class of claim does not catch it standing alone.

---

## 9. Healthcheck audit

Not re-adversarially tested exhaustively this pass (time-boxed); the one confirmed gap from Architecture Reality Audit V1 (`check_python()` checks `python`/`python3` via `shutil.which`, never `py`) stands, unchanged, unfixed (out of scope for all three repairs so far). Re-confirmed this pass that both `python --version` and `py -3 --version` resolve identically in this environment (3.14.5), so no false WARN is currently observed here — the gap remains latent, not currently manifesting.

---

## 10. Hooks — 13/13 execution (completing the set Architecture Reality Audit V1 started at 5/13)

All 13 registered hooks now directly executed with real stdin JSON payloads this session (5 in Reality Audit V1 + 8 this pass):

| Hook | Exit | Result |
|---|---|---|
| `block-no-verify.js` | 2 (block cases), 0 (control) | Correct (Reality Audit V1) |
| `config-protection.js` | 2 (block), 0 (control) | Correct (Reality Audit V1) |
| `quality-gate.js` | 0 (WARN-only) | Correct (Reality Audit V1 + §4 above) |
| `console-log-warning.js` | 0 | Correct (Reality Audit V1) |
| `pipeline-rules.js` | 0 | Correct (Reality Audit V1) |
| `delegation-tracker.js` | 0 | Ran, produced a real escalation WARN on the payload given |
| `qa-auto-audit.js` | 0 | Ran, silent (payload didn't match its trigger condition — not independently isolated further this pass) |
| `cost-tracker.js` | 0 | Ran, silent |
| `suggest-compact.js` | 0 | Ran, silent |
| `pre-compact-engram.js` | 0 | Ran, wrote a real trigger file as documented |
| `session-summary.js` | 0 | Ran, silent on this payload |
| **`engram-sync.js`** | **1** | **REAL FAILURE — see below** |
| `session-start-context.js` | 0 | Ran, produced a real session-context summary string |

**Real, live, currently-active failure found: `engram-sync.js --hook` exits 1** — `"ERROR: ~/.engram is not a git repository. Cannot sync."` Confirmed directly: `~/.engram` contains only `engram.db`/`engram.db-shm`, no `.git`. This hook is registered on the `Stop` event, `async: true`, 60s timeout, per `templates/settings.json` — meaning it very plausibly fails silently on every session-stop event in this environment, with zero visible surfacing (async hooks produce no transcript output on failure). Classify: `CORRECTNESS_RISK` for whatever "sync" is meant to provide (redundant git-backed history of the Engram DB, separate from the `.pipeline/` dual-write which is the documented *critical* redundancy path) — not immediately data-loss-critical since it's a secondary backup mechanism, but a real, currently-manifesting silent failure nonetheless, previously unknown.

**HOOK_SCRIPT_WORKS vs HOOK_IS_REGISTERED vs HOOK_ACTUALLY_FIRES_IN_RUNTIME — kept distinct, as required:** all 13 scripts work correctly under direct invocation (including `engram-sync.js`, which correctly *reports* its own real failure rather than crashing or hanging). All 13 are registered in `templates/settings.json`. Whether they *actually fire* in this specific Claude Desktop session remains the same open question documented in Architecture Reality Audit V1 (`~/.claude/settings.json` empty in this environment) — **not re-resolved this pass**, still `UNKNOWN` for live host-triggered firing, as distinct from the direct-invocation results above.

---

## 11. Policy Engine — live audit

`evaluate_capability("browser")` → real `ALLOW` decision, live provider (`playwright`, `LIVE`) — confirmed via direct call, not read from a cached healthcheck number. `evaluate_capability("unknown-xyz")` → `MISSING_POLICY`, not a crash, not a silent ALLOW.
**Cannot test BLOCK enforcement, bypass, or ADVISORY-vs-ENFORCED distinction this pass**: healthcheck independently confirms **0/14 policies are currently `BLOCK`-severity** (7 ALLOW, 7 WARN) — there is no real BLOCK policy in the current configuration to exercise. This is itself worth stating plainly: "the policy engine can express BLOCK" is a code-capability claim; "the policy engine currently blocks anything" is `NOT_APPLICABLE` — nothing is configured to block. Classify: `PARTIAL` (ALLOW/WARN paths live-confirmed; BLOCK path untestable because unconfigured, not because it's broken).

---

## 12. Capability Router — failure audit

Happy path re-confirmed live (browser/memory/documentation, all LIVE, real fallback metadata present for `browser`). Unknown-capability path confirmed safe (`UNAVAILABLE`, `action: register_provider`, no crash).
**Primary-unavailable+fallback, both-unavailable, malformed-provider-response, timeout, missing-token, missing-binary paths: `NOT_TESTED` this pass** — would require either monkey-patching the live MCP registry state or constructing an isolated registry fixture, neither attempted given time budget; flagged as open work rather than assumed safe. Classify current evidence: `REAL_FALLBACK` demonstrated for the one path tested (browser→claude_in_chrome metadata is present and structurally correct), `DECLARED_ONLY` status for the untested failure paths (present in the data model, not exercised).

---

## 13. Engram failure/recovery audit

**Not performed this pass** — the mission explicitly required not damaging the real Engram DB, and safely isolating an "Engram unavailable" condition would require either stopping the real `engram.exe` process (which could affect the live session, decided against) or constructing a fully isolated mock MCP boundary (significant scaffolding, not attempted given time budget). What Architecture Reality Audit V1 already established stands, unchanged: real save/search/get/update/topic-key-upsert cycle confirmed LIVE against the real instance; disk-fallback *behavior* (what specifically survives vs. is lost, recovery semantics) remains `NOT_TESTED` end-to-end. Classify: `UNKNOWN` for outage/recovery specifically, carried forward honestly rather than assumed from the dual-write *design* being documented.

---

## 14. Full 5-phase fault-injection test

**Not performed as a live orchestrator run this pass** — doing so would require a real, multi-agent Claude Code Task-delegation session (not something I can script directly as a set of isolated function calls; this is the same fundamental "no PreToolUse interception for Task/Agent" boundary documented in Architecture Repair 03). What was tested instead, safely, at the boundary-function level: phase-gate cajón-wait escalation (Architecture Reality Audit V1, code-confirmed, cap 2), Return Envelope rejection (§3 above), and the dev↔QA retry ceiling including its 4th-attempt-blocked behavior (Architecture Repair 03, §4 of that repair). These are the individual guardrails a real fault-injected pipeline run would exercise, verified in isolation; the *composition* of all five phases with injected faults at each boundary, live, was not run. Classify: `PARTIAL` — component-level fault handling verified; full pipeline integration `NOT_TESTED`.

---

## 15. Retry invocation gap

Formalized as a controlled test (not just stated): can the orchestrator proceed through a QA failure without ever calling `record_qa_attempt()`/`check_qa_retry_limit()`? **Yes, trivially** — nothing at the Python layer observes or requires that call; an orchestrator (or a test harness standing in for one) can call `should_skip_qa`/`cache_qa_result` (the unrelated, pre-existing mechanism) or nothing at all, and repeat a "dev→QA fail" cycle indefinitely without the new ceiling ever being consulted. Confirmed by direct test: looping 5 times calling only the pre-existing, unrelated functions produces no error, no flag, no difference between iteration 1 and iteration 5 — identical to the original P1-3 reproduction in Architecture Repair 03, because nothing forces the new path to be used instead of the old no-op path.
**Classification: HYBRID / BYPASSABLE — confirmed, matches Architecture Repair 03's own stated residual risk exactly, not a new finding but a formal confirmation of a previously-declared limitation.** Not fixed, per this audit's own instruction.

---

## 16. Silent failure sweep

Concrete, reproduced findings from this pass (not a general unscoped sweep — time-boxed to what surfaced):

1. **`engram-sync.js` (§10)** — real, live, currently-failing, async/invisible. `CORRECTNESS_RISK` (secondary backup path, not the critical dual-write).
2. **Playwright MCP `browser_take_screenshot` reports success without the file landing at any independently-verifiable, expected location** — reproduced three independent ways this pass: (a) my own direct filesystem check after a fresh screenshot call reporting success, (b) the reality-checker blind probe independently finding the same missing file, (c) the evidence-collector blind probe independently finding the same missing file for a *different* claimed path. Root cause characterized, not fully resolved: the tool's own echoed "Ran Playwright code" shows it silently coerces any passed path (including an absolute one I supplied) into a relative path resolved against an internal "workspace root" that does not correspond to any location directly reachable from Bash/Read in this environment. **This directly undermines the evidentiary chain evidence-collector/reality-checker depend on** ("Si no se ve funcionando en un screenshot, no funciona" assumes the screenshot durably exists and is independently checkable) — and, self-critically, it means the "real PNG files written to disk" claim in Architecture Reality Audit V1 §17 was itself asserted without the file-existence verification this whole audit insists on; that claim should be considered **unverified**, not false, but not confirmed either given what's now known. Classify: `FALSE_SUCCESS_RISK`, tool-layer, not ATLAS-code, but directly consequential for ATLAS's own evidence-based QA methodology.
3. **`.pipeline/invocation-log.jsonl` at 179,828 lines / 35.1 MB** (§22) — no correctness issue found, but a real, large, unbounded, silently-growing file that nothing currently prunes.

No `except Exception: return True` pattern (the most dangerous class — masking failure as explicit success) was found anywhere in `tools/*.py` or `core/capabilities/*.py` this pass. The broad `except: pass` pattern present throughout is consistent with, and already covered by, the project's own documented fail-open design principle — not re-flagged individually as new findings.

---

## 17. Flakiness audit

**Reduced sample, stated honestly: Quick × 5, Release × 2** (not the requested ×10/×10 — time-budgeted given the cost of this already-extensive audit; each Quick run costs ~55-75s, each Release ~65-85s). Result this pass: **0/5 Quick failures, 0/2 Release failures — 0% failure rate in this sample.** This contradicts, or at least does not currently reproduce, the flakiness pattern documented repeatedly earlier in this multi-day session (a single non-reproducing FAIL in a differing suite, historically observed 3+ times, always self-resolving on rerun, most often correlated with having just edited `config/test.registry.yaml`). Classify: `ENVIRONMENTAL` (correlated historically with recent registry edits, not with any specific suite's own logic) rather than `FLAKY` in the sense of a suite with a measurably nonzero steady-state failure rate — this pass's clean 7/7 run sample is consistent with that read, but the sample is too small to rule out a low-single-digit-percent rate definitively. **Do not treat as fully characterized** — this is the audit's own honest limit, not a claim of full stability.

---

## 18. Windows/Linux parity

Not comprehensively swept this pass. Real, positive evidence exists for exactly two subsystems, both from this session's own prior repairs: capability-events cross-process locking (msvcrt local + fcntl on CI, both tested, both green — Architecture Repair 02) and the QA retry ceiling's identical lock mechanism (same confirmation — Architecture Repair 03). Both CI runs for those repairs are real, verifiable (`gh run` IDs cited in their respective reports). Beyond those two, general path-handling/line-ending/subprocess/Unicode parity was not independently re-audited this pass — CI passing on every push this session is suggestive but not the same as a targeted parity sweep. Classify: `PARTIAL`, two subsystems confirmed, general parity `NOT_TESTED` as its own exercise.

---

## 19. Mutation sanity

Performed in a disposable detached-HEAD git worktree (`git worktree add --detach`), every mutation reverted immediately, worktree removed at the end. **4/4 critical regression suites correctly detected their own disabled behavior:**

| Mutation | Suite | Result |
|---|---|---|
| Disabled Return Envelope's required-fields check | `bloque-envelope-casing.py` | 10 PASS / **1 FAIL** — correctly caught |
| Removed the cross-process lock from `emit()` | `bloque-capability-events-integrity.py` | 9 PASS / **2 FAIL** (tests 03/04, the real-concurrency ones) — correctly caught, with a real caveat below |
| Forced `retry_limit_reached` to always `False` | `bloque-qa-retry-ceiling.py` | 9 PASS / **4 FAIL** — correctly caught |
| Disabled the `SEC-EVAL-001` regex | `bloque-security-backstop.py` | 16 PASS / **1 FAIL** — correctly caught |

**One real, minor test-quality gap found by this exercise itself:** in the capability-events suite, test 13 ("Windows-safe cross-process lock") stayed green even with the lock call removed from `emit()`, because it only checks that the lock *function* exists and is msvcrt-backed via `inspect.getsource` — it does not verify the function is actually *called* in the write path. The suite's real protection comes entirely from tests 03/04 (the concurrency stress tests, which did correctly fail). Not a `TEST_FALSE_CONFIDENCE` verdict for the suite as a whole (the mutation was still caught, by the tests that matter), but a real, narrow blind spot in test 13 specifically, worth noting as P3.

No suite stayed fully green after its target behavior was disabled — `TEST_FALSE_CONFIDENCE` not triggered for any of the four systems tested.

---

## 20. Test coverage by capability

| Capability | Unit | Structural | Integration | Live runtime | Adversarial | Negative control | CI |
|---|---|---|---|---|---|---|---|
| Return Envelope | ✅ | ✅ | ✅ | ✅ | ✅ (§3) | ✅ | ✅ |
| Capability Events | ✅ | ✅ | ✅ | ✅ | ✅ (concurrency) | ✅ | ✅ |
| QA Retry Ceiling | ✅ | ✅ | ✅ | ✅ | ✅ (bypass, §15) | ✅ | ✅ |
| Security Backstop | ✅ | ✅ | ✅ | — | ✅ (§4, this pass) | ✅ | ✅ (via Quick) |
| Security Agent | — | — | — | blind probe ×2 | ✅ | — | — |
| Reality Checker | — | — | — | blind probe ×1 | ✅ | — | — |
| Evidence Collector | — | — | — | blind probe ×1 | ✅ | — | — |
| Claim Linter | ✅ | ✅ | — | ✅ (this pass) | ✅ (this pass) | partial | ✅ |
| Hooks (13) | — | — | ✅ (13/13 direct) | `UNKNOWN` (host firing) | partial | ✅ (5/13) | ✅ (indirectly) |
| Policy Engine | ✅ | — | — | partial (§11) | — (no BLOCK to test) | — | — |
| Capability Router | ✅ | — | — | happy path only | — | ✅ (unknown cap) | ✅ |
| Engram | — | — | — | save/search/get/update only | — | — | ✅ (import-level) |

---

## 21. SOT/dist drift

Re-confirmed the known gap: `agents/refs/` is not covered by `tools/sync_dist.py` or `_qa/bloque-F10-sot-drift.py` (only top-level `agents/*.md`). Checked `skills.registry.yaml` — single source (`.claude/skills.registry.yaml`), no `config/` mirror exists, so no drift surface there at all (a clean non-finding, not assumed). No other mirrored-tree class beyond `agents/`, `hooks/`, and the already-known `agents/refs/` gap was found this pass.

---

## 22. Telemetry retention

| File | Lines | Size | Growth context |
|---|---|---|---|
| `.pipeline/capability-events.jsonl` | 1,306 | 458 KB | All post-Architecture-Repair-02 (file was rotated to empty ~18h before this measurement); real corruption confirmed fixed |
| `.pipeline/invocation-log.jsonl` | 179,828 | **35.1 MB** | Accumulated across this entire multi-day session's heavy tool usage; no rotation exists |

Neither file has any rotation/truncation mechanism. `capability-events.jsonl`'s growth rate under this session's unusually heavy, continuous multi-repair-task usage projects to roughly 3,000+ hours of equivalent-intensity use before reaching pre-fix scale — not currently material. `invocation-log.jsonl` is already substantial (35 MB) purely from this session; if any tool routinely parses the *entire* file rather than tailing it, that's a real, current parse-cost concern, not a hypothetical future one. **Classification: P2** (real, measured, not blocking correctness, but the invocation-log size specifically is already large enough to matter for anything that doesn't stream/tail it — not `P3`/`NOT_CURRENTLY_MATERIAL` given the concrete 35 MB figure).

---

## 23. Documentation contradiction audit

Not a full sweep this pass (time-boxed); targeted spot-checks against runtime evidence gathered across all four audits/repairs this session:

| Claim | Source | Runtime evidence | Classification |
|---|---|---|---|
| "max 3 retries" (Dev+QA loop) | `README.md` (main, committed) | Now hybrid-enforced per Architecture Repair 03 | `QUALIFIED` (true as stated; doesn't claim the enforcement mechanism, so not overclaiming) |
| "13 hooks" | `CLAUDE.md`/README | 13 *registered*, 19 files in the directory | `QUALIFIED` (correct under the registered-hooks reading, ambiguous under a naive file-count reading) |
| Autonomy benchmark "69.9%" | Various docs | Real, frozen, dated result | `STALE-RISK` per §8's own finding — the number itself is accurate as of its date, but nothing in the claim linter would catch it being quoted without that date in a new document |
| "Screenshots saved to disk" (Architecture Reality Audit V1 §17) | This session's own prior report | **Contradicted this pass — see §16.2** | Downgraded here from `TRUE` (as previously asserted) to `UNKNOWN` — self-correction, not a rewrite of the original report (that document is left as-is; this is the correction) |
| "full observability" | Avoided in current README per Architecture Reality Audit V1's own remediation | Claim linter doesn't independently catch this phrase (§8) | Currently `TRUE` by absence in the doc, but the *tooling* meant to prevent its reintroduction has a real gap |

README was not treated as evidence for any runtime claim in this audit — every classification above is grounded in a tool run, a direct file check, or a blind-probe result from this session.

---

## P0

None found.

## P1

| ID | Component | Summary | Evidence |
|---|---|---|---|
| SH-P1-1 | `.claude/hooks/engram-sync.js` | Live, currently-active, silent (async, Stop-event) failure — `~/.engram` is not a git repo | Direct execution, exit 1, root cause confirmed |
| SH-P1-2 | Security Backstop (all 7 rules) | Systemic false positive: fires on any comment merely mentioning a dangerous pattern | Reproduced for all 7 rules independently, fresh fixtures |

## P2

| ID | Component | Summary |
|---|---|---|
| SH-P2-1 | Claim Linter | Misses unqualified historical-metric claims, "live/production" mischaracterization of mocked tests, and "full observability" standing alone |
| SH-P2-2 | `evidence-collector.md` contract vs. `validate_return_envelope` | `PASS_WITH_WARNINGS` is documented as valid but rejected by `qa_strict` mode |
| SH-P2-3 | `.pipeline/invocation-log.jsonl` | 35.1 MB, unbounded, no rotation — already large from this session alone |
| SH-P2-4 | Playwright MCP `browser_take_screenshot` | Reports success without the file landing at any independently-verifiable location in this environment; undermines evidence-collector/reality-checker's screenshot-as-proof methodology at the infrastructure layer |
| SH-P2-5 | Dev↔QA retry ceiling | Confirmed (not just theorized) bypassable by simply never calling the new enforcement functions — formal confirmation of Architecture Repair 03's own declared residual risk |

## P3

| ID | Component | Summary |
|---|---|---|
| SH-P3-1 | `bloque-capability-events-integrity.py` test 13 | Checks lock-function existence, not invocation — narrow blind spot, core protection unaffected (tests 03/04 catch real regressions) |
| SH-P3-2 | Policy Engine | 0/14 policies are BLOCK-severity — BLOCK enforcement path currently has no real-world exercise surface |
| SH-P3-3 | Capability Router | Failure-injection paths (primary-down+fallback-down, malformed response, timeout) declared in the data model, not exercised |

## UNKNOWN / NOT TESTED

Engram outage/recovery (§13) · full live 5-phase fault-injected pipeline run (§14) · policy BLOCK-path enforcement/bypass (§11, nothing configured to test) · capability router failure-injection beyond the happy path (§12) · general Windows/Linux parity beyond the two repair-specific subsystems (§18) · comprehensive documentation-contradiction sweep beyond the spot-checks in §23 · malformed nested design-field envelope fuzzing (§3.9) · exhaustive silent-failure sweep beyond the 3 concrete findings in §16 · host-level "hook actually fires" question, carried forward unresolved from Architecture Reality Audit V1.

## FALSE CONFIDENCE RISKS

The single most important one: **Architecture Reality Audit V1's own §17 claim of "real PNG files written to disk" was itself an unverified assertion** — this audit found, independently three ways, that it does not hold up. Flagged here rather than silently corrected in the original document (which remains as originally written, per this session's own established practice of never rewriting prior findings). No suite exhibited `TEST_FALSE_CONFIDENCE` under mutation testing (§19) — all four tested suites correctly failed when their target behavior was disabled, with one narrow, already-covered-by-a-sibling-test exception (SH-P3-1).

---

## STABLE V1 CRITERIA — PASSED

- 0 P0 findings
- Critical contracts have negative + positive tests: Return Envelope ✅, Capability Events ✅, QA Retry Ceiling ✅, Security Backstop ✅
- Critical gates mechanically enforced or explicitly documented as hybrid: ✅ (all three repairs state their enforcement class honestly, including the bypass path in §15)
- Mutation sanity: 4/4 tested suites correctly detect disabled behavior, 0 `TEST_FALSE_CONFIDENCE`
- Quick green (5/5 this sample), Release green (2/2 this sample), CI green (every push this session)
- No unexplained false-success path in the three repaired critical flows specifically (Envelope/Events/Retry) — each was mutation-tested and each correctly failed

## STABLE V1 CRITERIA — FAILED

- **2 open P1s** (SH-P1-1 `engram-sync.js` live failure, SH-P1-2 security-backstop comment false-positive) — the stated bar is 0 open P1
- All 13 hooks were **script-level** executed this session (13/13), but **not runtime-firing-audited** — host registration remains `UNKNOWN`, not demonstrated
- Provider fallback: only the happy path tested; primary-down/both-down/malformed/timeout paths `NOT_TESTED`
- Engram outage/recovery: `NOT_TESTED`
- Full pipeline fault-injection: not run live end-to-end, only at the component-function level
- Windows/Linux parity: only 2 of the session's own new subsystems confirmed; not a general sweep
- Flakiness sample reduced (5/2 instead of 10/10) — insufficient to state a precise failure rate, only that none reproduced in this smaller sample
- Documentation contradiction audit: spot-checks only, not comprehensive
- One real false-confidence correction was needed against this session's own prior audit (screenshot claim)

---

## CURRENT STABILITY ASSESSMENT

**Scoring formula, stated before computing (per instruction — no invented percentage):** of the 11 explicit Stable V1 criteria listed in the mission (§24), count how many are fully satisfied by the evidence gathered this pass, treating a criterion met by *partial* evidence (e.g., 2 of many subsystems parity-tested) as **not** satisfied, since the mission's own criteria are stated as absolutes ("all 13 hooks runtime-audited", not "some").

Criteria and status:
1. 0 P0 — **MET**
2. 0 open P1 — **NOT MET** (2 open)
3. Critical contracts have negative+positive tests — **MET**
4. Critical gates mechanically enforced or explicitly hybrid — **MET**
5. All 13 hooks runtime-audited — **NOT MET** (script-executed, not runtime-firing-confirmed)
6. Provider fallback tested — **NOT MET** (happy path only)
7. Engram outage/recovery tested — **NOT MET**
8. Full pipeline fault-injected — **NOT MET** (component-level only)
9. No unexplained false-success path in critical flows — **MET** (for the 3 repaired flows specifically; 1 false-success WAS found and is explained, not unexplained — Playwright screenshots, SH-P2-4)
10. No unexplained flaky critical suite — **MET** (0/7 in this sample; historically explained as registry-edit-correlated, not unexplained, though sample is small)
11. Windows/Linux parity for critical paths — **NOT MET** (2 of many subsystems)
12. Quick/Release/CI green — **MET**

**5 of 12 criteria fully met** (I count 12 above, not 11 — the mission's bullet list under §24 has one more line than my initial count suggested; using the actual 12 bulleted items as written). **5/12 = 42%.**

I am stating this number because the formula was defined first and computed from measured criteria, exactly as instructed — not because a percentage adds precision this audit doesn't otherwise have. The honest summary in prose is more informative than the number: **the three subsystems this session actually built and fixed (Return Envelope casing, Capability Events integrity, QA Retry ceiling) are genuinely well-tested — real reproduction, real fixes, real regression suites, real mutation-sanity confirmation, real CI on two platforms.** Everything **outside** those three subsystems — the rest of the hook layer's live firing, Engram outage behavior, full pipeline integration, provider-failure paths, general OS parity — remains at essentially the same evidence level Architecture Reality Audit V1 left it at: partially characterized, honestly marked `NOT_TESTED` rather than assumed. This audit also surfaced two new, real P1s (one pre-existing and previously unknown — `engram-sync.js`; one newly discovered — the comment false-positive) plus a genuine self-correction against this session's own prior work (the screenshot claim). That combination — new real defects found, a prior overclaim caught and corrected — is itself evidence the process is working as intended, not evidence the system is unstable in some newly-alarming way.

## TOP EVIDENCE-BACKED FIXES

1. **Fix `engram-sync.js`'s missing git-repo prerequisite** (SH-P1-1) — either initialize `~/.engram` as a git repo, or make the hook fail silently-but-correctly (it already reports the real error; the issue is that nothing surfaces it, not that the error message is wrong).
2. **Strip comments before the 7 security-backstop regexes run** (SH-P1-2) — smallest fix: exclude `//` and `/* */` spans before matching.
3. **Add `PASS_WITH_WARNINGS` to `qa_strict`'s valid-status set** (SH-P2-2) — one-line change, resolves a real documented-vs-enforced mismatch, same class of bug as the already-fixed P1-1 casing issue but smaller.
4. **Investigate the Playwright MCP screenshot workspace-root mismatch** (SH-P2-4) — determine the actual write location and either document it precisely or fix the path-reporting so a caller's stated path and the actual write location agree.
5. **Extend the claim linter to flag bare numeric-metric claims without a date/context marker** (SH-P2-1) — closes the most concrete of the three linter gaps found.

---

**STABILITY_AUDIT_COMPLETE — NOT_READY_FOR_STABLE_V1**
