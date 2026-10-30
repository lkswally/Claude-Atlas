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
| P3 | Model enforcement V1.1 | BLOCKED → `MODEL_ROUTER_ADVISORY_ONLY` (`ENFORCEMENT_UNKNOWN`) | Isolated lab built; first real run `Not logged in`, so no model ever ran. Verdict logic proven offline: F40 18 checks, mutation 7/7 (a hook's claim can never yield PROVEN). No credential search, no settings edit. `docs/MODEL-ROUTER-ENFORCEMENT-EXPERIMENT.md` | 2e55c06, fcc97af | 41014876868 success |
| P4 | Provider abstraction | KEEP | `core/providers` contract (health / capabilities / guarded `invoke` / failure classification); Anthropic host adapter: health UNKNOWN, `execute` NOT_EXECUTABLE, nothing guessed. F41 47 checks, mutation 15/15. `docs/PROVIDER-ABSTRACTION.md` | 066b2ba | 41016206047 success |
| P5 | Second real provider | KEEP — **Codex CLI** | Only other-vendor tool installed and logged in (presence-only audit). Real captures replayed offline; locked-down invocation (read-only sandbox, stdin prompt, scrubbed env, secret pre-filter, process-tree kill). F42 52 checks, mutation 16/16, `--live` 5/5. Quota/rate-limit wording is synthetic | e48687b | 41018707176 success |
| P6 | Real provider fallback | KEEP | `tools/provider_fallback.py`: hard constraints re-applied after every failure; bounded retry policy; WAITING vs NO_ELIGIBLE; HANDOFF for host-managed. F43 36 checks, mutation 16/16, `--live` 2/2 (Claude out of quota → ran on real Codex; same outage on a HIGH-risk task correctly did not fall back) | 558e30f | 41045046741 success |
| P7 | Reviewer independence | KEEP | `tools/review_independence.py`: levels from facts, registry-derived providers, explicit degradation, human gate on silent self-review. F44 36 checks, mutation 16/16 | b33f4f6 | 41046285069 success |

Deferred until the 80% gate is evaluated: REA, Herdr, Moshi, Archify, SWE-ReX, Web Release Readiness, MAOS adapter, historical adaptive routing.

## Maturity score (criteria-based, rubric unchanged since it was published)

Weights are fixed. Each dimension is a list of checkable criteria; points = weight × (criteria demonstrated ÷ criteria total). Items marked † are carried from earlier audits and were not re-measured. **Blocked** = needs an external decision/credential and is not credited. No criterion was added or reworded after the fact.

| Dimension | Wt | Demonstrated | Not yet demonstrated | Pts | Blocked | Remaining |
|---|---|---|---|---|---|---|
| Core stability | 20 | zero open P1 †; Quick/Release/verify/healthcheck + CI green; QA retry ceiling + envelope enforced; harness independent of host I/O timing | tests isolated from real HOME / `.pipeline` state | 16.0 | – | 4.0 |
| Security | 15 | hooks block destructive/secret writes; pre-push gate; Security Backstop negative tests † | execution sandbox; targeted security audit V2 | 9.0 | – | 6.0 |
| Model routing | 15 | deterministic router, eligibility before scoring; fail-closed on UNKNOWN; fallback chain + honest review plan | mechanical enforcement of the selected model; effective-model verification | 9.0 | **6.0** | – |
| Provider resilience | 15 | provider abstraction; two live providers (Claude host, Codex); health from a real signal (Codex round trips); failure classification + retry-vs-fallback | failure-injection campaign across providers (P16; F43 injects per-class failures with fakes, quota/rate-limit are synthetic, so not credited here) | 12.0 | – | 3.0 |
| Observability | 10 | structured JSONL logs; capability metrics; bounded locked retention (invocation + skills usage); newest-first bounded reads | – | 10.0 | – | – |
| Evidence / QA | 10 | evidence-gated pipeline †; mutation-sanity practice; claim linter | retry-ceiling test 26 accepts stale same-helper entries | 7.5 | – | 2.5 |
| Runtime / recovery | 5 | QA retry state persisted, fail-closed on malformed | restart/crash recovery tested; failure-injection suite | 1.7 | – | 3.3 |
| Replaceability | 5 | ATLAS↔MAOS↔JARVIS directional boundary †; capability router abstracts tools | provider **and runtime** ports (provider port exists; runtime port is P8) | 3.3 | – | 1.7 |
| Capability architecture | 5 | capability router + registry; MCP layer | generic adapter ports for external capabilities (deferred) | 3.3 | – | 1.7 |
| **Total** | **100** | | | **71.8** | **6.0** | **22.2** |

**Current demonstrated maturity: ≈72%** (was ≈55% at the start of the sprint under this same rubric; the owner's prior estimate of 69–70% is not reproduced by a criteria count). **The 80% gate is not met.**

Unscored work (strengthens the system but matches no pre-declared criterion, so it earns no points): reviewer-independence levels and planner (P7), Codex containment and secret pre-filter (P5), the enforcement lab's evidence-only verdict logic (P3), harness hardening, the architecture-audit headroom fix.

**Path to ≥ 80%:** (1) owner authenticates an isolated `CLAUDE_CONFIG_DIR` once, then `enforcement_lab.py matrix` runs; if enforcement is PROVEN the 6.0 blocked points become creditable → ≈77.8%; (2) the P16 failure-injection campaign → +3.0 → ≈80.8%. Alternatively the sandbox + security audit (+6.0) plus restart/recovery (+3.3).

## Open findings

- **P0 / P1:** none known (no new ones surfaced this sprint).
- **P2:** model-routing enforcement unproven (externally blocked, reflected in the score); test suites still append to real `.pipeline` / `.claude/logs` / `~/.claude` state (roadmap P21).
- **P3:** retry-ceiling test 26 can be satisfied by stale same-helper entries; `capability-events.jsonl` unbounded (2.3 MB, locked, trigger > 10 MB); ~57 MB of `*.legacy-*` logs and the 73 MB `pre-fix-archive` are retained pending an operator decision; Codex quota/rate-limit failure wording is synthetic; one unexplained `0xC0000409` in `delegation-tracker.js` (0/300 repro); `gh` resolves the wrong default repo in this checkout (documented, always pass `--repo`).
- **Accepted risks:** the router and review plan are advisory; prompts sent through Codex leave the machine and the secret pre-filter is a heuristic; `invoke()` abandons (cannot kill) a hung worker thread, so adapters must enforce their own I/O timeouts (Codex's does); `context_reused` in a review record is an attestation ATLAS cannot observe.
