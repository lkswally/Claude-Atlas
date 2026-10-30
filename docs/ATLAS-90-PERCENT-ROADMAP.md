# ATLAS — Maturity Roadmap (tracker)

90% (and the 80% sprint gate) are **planning heuristics**. Correct behavior beats the number; a capability shown to be unnecessary is REJECTED, not built. Every phase closes a demonstrated gap and ends KEEP / REVERT with evidence. One implementation phase active at a time.

Principles: JARVIS owns lifecycle, ATLAS owns technical execution, ATLAS never depends on JARVIS. External systems (MAOS, REA, Herdr…) only through generic ports/adapters, replaceable, never mandatory for core startup. Models propose, policies constrain, deterministic executors act, evidence proves. CODE PASS ≠ RUNTIME PASS ≠ PHYSICAL PASS. UNKNOWN is never hidden.

Statuses: NOT_STARTED · AUDIT · IMPLEMENTING · VALIDATING · BLOCKED · KEEP · REVERT · ACCEPTED_RISK.

## Phases

| Phase | Name | Status | Depends on | Evidence | Commit | CI | Blocker / next |
|---|---|---|---|---|---|---|---|
| P0 | Host / repo baseline | KEEP | – | HEAD == origin/main; WIP backups byte-identical; Defender + servicing idle; node 24.22.2 / npm 11.19.1 / py 3.14.7 / git 2.56.0 | – | – | – |
| P1 | Close Model Router V1 | KEEP | P0 | Harness patches 20/20 old→fail / new→pass / neg-control; affected suites 45/45; Quick 3× 43/43; Release 46/46; verify 8/8; healthcheck 25/1/0 ×2; claim-linter 0 HIGH; mutation 4/4 on final code; router 0.078 ms/route, CLI output byte-identical ×8 per input | c43fa2c, 1c4cb8d, b1673d3 | run 41009462151 success (SHA verified) | Router stays ADVISORY |
| P2 | Observability retention | KEEP | P1 | invocation-log 34.65 MB / 186,111 lines unbounded, full-file read per audit; unlocked appends left 165 / 472 torn lines (locked capability-events: 0). New `tools/bounded_jsonl.py`: warm audit 93 ms → 0.5 ms, cold device read 34.66 MB / 472 ms → 1.91 MB / 19 ms; F39 57/57, mutation 12/12, Quick 3× 44/44, Release 47/47. Post-upgrade locked writes: 0 malformed in 1,596 lines. Policy: `docs/TELEMETRY-RETENTION-POLICY.md` | a6dabd8, 6ce09a2 | 41012105942 **failed** (Linux-only: the new writer created missing dirs, `?` is illegal on Windows so it passed locally) → fixed → 41013173798 success (SHA verified) | capability-events deferred (2.2 MB, locked, trigger >10 MB) |
| P3 | Model enforcement V1.1 | BLOCKED → `MODEL_ROUTER_ADVISORY_ONLY` (verdict `ENFORCEMENT_UNKNOWN`) | P1 | Isolated lab built (`tools/lab_model_enforcement/`); first real run: `Not logged in · Please run /login`, rc 1, $0, hook never invoked. Verdict logic proven offline: F40 18/18, mutation 7/7 (hook claim can never yield PROVEN; attribution to a no-rewrite control required). No credential hunting, no settings edit, no side-spawned subagents. Details: `docs/MODEL-ROUTER-ENFORCEMENT-EXPERIMENT.md` | see git log | – | **EXTERNALLY_BLOCKED:** needs a one-time `/login` of an isolated `CLAUDE_CONFIG_DIR` (owner action), then `enforcement_lab.py matrix` |
| P4 | Provider abstraction | NOT_STARTED | P3 | – | – | – | – |
| P5 | Second real provider | NOT_STARTED | P4 | – | – | – | Audit environment first; EXTERNALLY_BLOCKED if no usable credential |
| P6 | Real provider fallback | NOT_STARTED | P5 | – | – | – | Needs two live providers |
| P7 | Reviewer independence | NOT_STARTED | P4 | – | – | – | – |

Deferred until the 80% gate is evaluated: REA, Herdr, Moshi, Archify, SWE-ReX, Web Release Readiness, MAOS adapter, historical adaptive routing.

## Maturity score (criteria-based)

Weights are fixed. Each dimension is a list of checkable criteria; score = weight × (criteria demonstrated ÷ criteria total). Items marked † are carried from earlier audits and were not re-measured in this sprint. "Blocked" = needs an external decision/credential.

| Dimension | Wt | Demonstrated | Criteria not yet demonstrated | Pts |
|---|---|---|---|---|
| Core stability | 20 | zero open P1 †; Quick/Release/verify/healthcheck + CI green; QA retry ceiling + envelope enforced; harness independent of host I/O timing | tests isolated from real HOME / `.pipeline` state (P3 residual) | 16.0 |
| Security | 15 | hooks block destructive/secret writes; pre-push gate; Security Backstop negative tests † | execution sandbox; targeted security audit V2 | 9.0 |
| Model routing | 15 | deterministic router, eligibility before scoring; fail-closed on UNKNOWN; fallback chain + honest review plan | **mechanical enforcement of the selected model; effective-model verification** | 9.0 |
| Provider resilience | 15 | – | provider abstraction; ≥2 live providers (blocked: credentials); health from real signals; failure classification + retry-vs-fallback; failure injection | 0.0 |
| Observability | 10 | structured JSONL logs; capability metrics; bounded locked retention for the invocation + skills-usage logs; newest-first bounded reads on the audit hot path | capability-events not yet bounded (2.2 MB, deferred with a trigger) | 10.0 |
| Evidence / QA | 10 | evidence-gated pipeline †; mutation-sanity practice; claim linter | retry-ceiling test 26 accepts stale same-helper entries (P3) | 7.5 |
| Runtime / recovery | 5 | QA retry state persisted, fail-closed on malformed | restart/crash recovery tested; failure-injection suite | 1.7 |
| Replaceability | 5 | ATLAS↔MAOS↔JARVIS directional boundary †; capability router abstracts tools | provider/runtime ports | 3.3 |
| Capability architecture | 5 | capability router + registry; MCP layer | generic adapter ports for external capabilities (deferred) | 3.3 |
| **Total** | **100** | | | **59.8** |

**Blocked score (external constraint, not credited):** Model routing 6.0 pts (mechanical enforcement + effective-model verification need an authenticated Claude Code binary, see P3). Provider resilience will carry the same kind of blocker if no second provider is already configured (P5).

**Current demonstrated maturity: ≈60%** (was ≈55% before P2; 3 of 23 phases KEEP; P3 closed as honest ADVISORY_ONLY, no points added). This criteria count does not reproduce the owner's 69–70% estimate; the 80% gate is evaluated with this rubric. It is reachable only if routing enforcement is proven **and** a second real provider is usable — both are tracked as potentially externally blocked, and a blocked item is reported as blocked, not credited.
