# ATLAS — Maturity Roadmap (tracker)

90% (and the 80% sprint gate) are **planning heuristics**. Correct behavior beats the number; a capability shown to be unnecessary is REJECTED, not built. Every phase closes a demonstrated gap and ends KEEP / REVERT with evidence. One implementation phase active at a time.

Principles: JARVIS owns lifecycle, ATLAS owns technical execution, ATLAS never depends on JARVIS. External systems (MAOS, REA, Herdr…) only through generic ports/adapters, replaceable, never mandatory for core startup. Models propose, policies constrain, deterministic executors act, evidence proves. CODE PASS ≠ RUNTIME PASS ≠ PHYSICAL PASS. UNKNOWN is never hidden.

Statuses: NOT_STARTED · AUDIT · IMPLEMENTING · VALIDATING · BLOCKED · KEEP · REVERT · ACCEPTED_RISK. CI evidence is read from the GitHub API for the exact pushed SHA, never from a watcher's exit code.

## Phases

| Phase | Name | Status | Evidence | Commits | CI (run, verified on SHA) |
|---|---|---|---|---|---|
| P0 | Host / repo baseline | KEEP | HEAD == origin/main; WIP backups byte-identical; Defender + servicing idle | – | – |
| P1 | Close Model Router V1 | KEEP | Harness patches 20/20 (old fails / new passes / neg-control); Quick 3× green; Release, verify, healthcheck ×2 green; mutation 4/4; router 0.078 ms/route, output byte-identical across processes | c43fa2c, 1c4cb8d, b1673d3 | 41009462151 success |
| P2 | Observability retention | KEEP | `invocation-log` was 34.65 MB / 186,111 lines unbounded with 165 torn lines (skills log 472; the locked capability-events 0). `tools/bounded_jsonl.py`: warm audit 93 → 0.5 ms; cold device read 34.66 MB / 472 ms → 1.91 MB / 19 ms. F39 57 checks, mutation 12/12. Policy: `docs/TELEMETRY-RETENTION-POLICY.md` | a6dabd8, 6ce09a2 | 41012105942 **failed** (Linux-only regression, fixed) → 41013173798 success |
| P3 | Model enforcement V1.1 | BLOCKED → `MODEL_ROUTER_ADVISORY_ONLY` (`ENFORCEMENT_UNKNOWN`) | Isolated lab built; first real run `Not logged in`, so no model ever ran. Verdict logic proven offline: F40 18 checks, mutation 7/7 (a hook's claim can never yield PROVEN). No credential search, no settings edit. `docs/MODEL-ROUTER-ENFORCEMENT-EXPERIMENT.md`. Re-attempt after the owner reported the isolated login done: the documented `D:\ProyectosIA\_enforce_lab\cfg` does not exist (and no `ATLAS_LAB_CLAUDE_CONFIG_DIR` is set at user or machine level), so the matrix was not run; the login was not searched for | 2e55c06, fcc97af | 41014876868 success |
| P4 | Provider abstraction | KEEP | `core/providers` contract (health / capabilities / guarded `invoke` / failure classification); Anthropic host adapter: health UNKNOWN, `execute` NOT_EXECUTABLE, nothing guessed. F41 47 checks, mutation 15/15. `docs/PROVIDER-ABSTRACTION.md` | 066b2ba | 41016206047 success |
| P5 | Second real provider | KEEP — **Codex CLI** | Only other-vendor tool installed and logged in (presence-only audit). Real captures replayed offline; locked-down invocation (read-only sandbox, stdin prompt, scrubbed env, secret pre-filter, process-tree kill). F42 52 checks, mutation 16/16, `--live` 5/5. Quota/rate-limit wording is synthetic | e48687b | 41018707176 success |
| P6 | Real provider fallback | KEEP | `tools/provider_fallback.py`: hard constraints re-applied after every failure; bounded retry policy; WAITING vs NO_ELIGIBLE; HANDOFF for host-managed. F43 36 checks, mutation 16/16, `--live` 2/2 (Claude out of quota → ran on real Codex; same outage on a HIGH-risk task correctly did not fall back) | 558e30f | 41045046741 success |
| P7 | Reviewer independence | KEEP | `tools/review_independence.py`: levels from facts, registry-derived providers, explicit degradation, human gate on silent self-review. F44 36 checks, mutation 16/16 | b33f4f6 | 41046285069 success |
| P16 | Failure-injection campaign | KEEP | Expectations pre-registered before any run (`docs/FAILURE-INJECTION-CAMPAIGN.md`). F45: 106 scenarios / 124 checks judged by 8 rules at real boundaries (fake `codex`/`engram` subprocesses, torn files, killed writers); judge self-checked (O1-O9); mutation 41/41 after two survivors were fixed as test gaps; `--live` 3/3 against the real Codex. The unmodified system failed 33 scenarios: **9 defects fixed** (dropped TIMEOUT retry, no human gate on degraded HIGH review, Engram `ambiguous_project`/unknown status/wrong-id/"not found" all passing the phase gate, invocation audit "complete" on tracker failure, QA retry state silently reset, no host-reported MCP failure input) and 10 gaps recorded (AG-1..AG-10) | ea65e00, 964cb22, d6b6a19, 27349cd, 9e2a9cc | 41147490340 success (F45 124/124 and Quick 50/50 on the Linux runner) |

Deferred until the 80% gate is evaluated: REA, Herdr, Moshi, Archify, SWE-ReX, Web Release Readiness, MAOS adapter, historical adaptive routing.

## Maturity score (criteria-based, rubric unchanged since it was published)

Weights are fixed. Each dimension is a list of checkable criteria; points = weight × (criteria demonstrated ÷ criteria total). Items marked † are carried from earlier audits and were not re-measured. **Blocked** = needs an external decision/credential and is not credited. No criterion was added or reworded after the fact.

| Dimension | Wt | Demonstrated | Not yet demonstrated | Pts | Blocked | Remaining |
|---|---|---|---|---|---|---|
| Core stability | 20 | zero open P1 †; Quick/Release/verify/healthcheck + CI green; QA retry ceiling + envelope enforced; harness independent of host I/O timing | tests isolated from real HOME / `.pipeline` state | 16.0 | – | 4.0 |
| Security | 15 | hooks block destructive/secret writes; pre-push gate; Security Backstop negative tests † | execution sandbox; targeted security audit V2 | 9.0 | – | 6.0 |
| Model routing | 15 | deterministic router, eligibility before scoring; fail-closed on UNKNOWN; fallback chain + honest review plan | mechanical enforcement of the selected model; effective-model verification | 9.0 | **6.0** | – |
| Provider resilience | 15 | provider abstraction; two live providers (Claude host, Codex); health from a real signal (Codex round trips); failure classification + retry-vs-fallback; **failure-injection campaign across providers (P16, F45, CI-verified; Claude failures are host-reported by construction and Codex rate-limit/quota wording is synthetic, AG-7/AG-8)** | – | 15.0 | – | – |
| Observability | 10 | structured JSONL logs; capability metrics; bounded locked retention (invocation + skills usage); newest-first bounded reads | – | 10.0 | – | – |
| Evidence / QA | 10 | evidence-gated pipeline †; mutation-sanity practice; claim linter | retry-ceiling test 26 accepts stale same-helper entries | 7.5 | – | 2.5 |
| Runtime / recovery | 5 | QA retry state persisted, fail-closed on malformed (now also on any unreadable shape); **failure-injection suite (F45: Engram, MCP/capability, telemetry, state, duplicates, killed writers)** | restart/process-resume recovery (interrupted writes are tested; resuming a run after a restart is not, AG-10) | 3.3 | – | 1.7 |
| Replaceability | 5 | ATLAS↔MAOS↔JARVIS directional boundary †; capability router abstracts tools | provider **and runtime** ports (provider port exists; runtime port is P8) | 3.3 | – | 1.7 |
| Capability architecture | 5 | capability router + registry; MCP layer | generic adapter ports for external capabilities (deferred) | 3.3 | – | 1.7 |
| **Total** | **100** | | | **76.5** | **6.0** | **17.5** |

**Current demonstrated maturity: 76.5%** (71.8% before P16; ≈55% at the start of the sprint under this same rubric). **The 80% gate is not met.** P16 moved two pre-declared criteria that read differently but describe the same artifact: provider resilience "failure-injection campaign across providers" (+3.0) and runtime "failure-injection suite" (+1.7). The third runtime criterion, restart/crash recovery, is NOT credited: F45 proves interrupted writes fail safe, not that a run resumes after a restart. If a reviewer holds that F45 can satisfy only one of the two, the figure is 74.8%.

Unscored work (strengthens the system but matches no pre-declared criterion, so it earns no points): reviewer-independence levels and planner (P7), Codex containment and secret pre-filter (P5), the enforcement lab's evidence-only verdict logic (P3), harness hardening, the architecture-audit headroom fix.

**Path to ≥ 80% (needs +3.5):** the single largest non-blocked criterion is core stability "tests isolated from real HOME / `.pipeline` state" (+4.0 → 80.5%). Other options: execution sandbox or security audit V2 (+3.0 each), retry-ceiling test 26 (+2.5), restart/process-resume recovery (+1.7). Separately, if the owner supplies the authenticated isolated `CLAUDE_CONFIG_DIR`, `enforcement_lab.py matrix` can run and PROVEN would make the 6.0 blocked points creditable (→ 82.5%). The path the owner said was authenticated, `D:\ProyectosIA\_enforce_lab\cfg`, does not exist.

## Open findings

- **P0 / P1:** none known. P16 found and fixed 9 false-success / fail-open defects (see `docs/FAILURE-INJECTION-CAMPAIGN.md` D1-D9); none remains open.
- **P2:** model-routing enforcement unproven (externally blocked, reflected in the score); test suites still append to real `.pipeline` / `.claude/logs` / `~/.claude` state (roadmap P21).
- **P3:** retry-ceiling test 26 can be satisfied by stale same-helper entries; `capability-events.jsonl` unbounded (2.3 MB, locked, trigger > 10 MB); ~57 MB of `*.legacy-*` logs and the 73 MB `pre-fix-archive` are retained pending an operator decision; Codex quota/rate-limit failure wording is synthetic; one unexplained `0xC0000409` in `delegation-tracker.js` (0/300 repro); `gh` resolves the wrong default repo in this checkout (documented, always pass `--repo`).
- **P3 (from P16, `docs/FAILURE-INJECTION-CAMPAIGN.md` section 5):** nothing feeds the capability router's host-report port automatically (AG-5: until then MCP status is *declared* and labelled so); a repeated provider `request_id` is not deduplicated (AG-1); a QA-retry write torn mid-way needs manual repair (AG-2); one stray temp file after an interrupted delegation write (AG-3); a hard-killed ATLAS leaves a running Codex child (AG-4); no restart/resume test (AG-10).
- **Accepted risks:** the router and review plan are advisory; prompts sent through Codex leave the machine and the secret pre-filter is a heuristic; `invoke()` abandons (cannot kill) a hung worker thread, so adapters must enforce their own I/O timeouts (Codex's does); `context_reused` in a review record is an attestation ATLAS cannot observe.
