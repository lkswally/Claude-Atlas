# Telemetry retention policy (roadmap P2)

**Rule.** Every append-style log that ATLAS owns must have a size bound, locked appends, and reads that do not deserialize the whole history. The shared mechanism is `tools/bounded_jsonl.py` (`BoundedJsonl`): one current segment plus one archive (`<name>.1.jsonl`), ~2 MB each, rotation and append under one cross-process lock, newest-first reads. It is not a database; queries beyond "last N" / "recent window" are a different tool.

**Retention is bounded by design.** Events older than the archive are discarded. Nothing here claims otherwise. `stats()`-style counts describe the retained window, not history.

## Why (measured 2026-10-30)

| Fact | Evidence |
|---|---|
| `invocation-log.jsonl` was 34.65 MB / 186,111 lines and re-read in full by every audit | cold read on the HDD: 1.5 s idle, ~23 s during a Defender full scan |
| Unlocked appends tear lines on Windows | 165 torn lines (invocation), 472 (skills usage), **0** in the locked `capability-events.jsonl`; disabling the lock in the new helper stored 757 of 900 entries with 5 torn lines |
| Timestamps are not strictly ordered | max backward skew 77 s, so time-window reads cannot stop at the first old entry (120 s slack + 100-consecutive-old stop) |

## Inventory and decision

| Log (ATLAS-owned) | Size now | State before | Decision |
|---|---|---|---|
| `.pipeline/invocation-log.jsonl` | 34.65 MB | UNBOUNDED, FULL_SCAN, CONCURRENT_WRITE unlocked | **Adopted** `BoundedJsonl` (writer + readers) |
| `.claude/logs/skills-registry-usage.jsonl` | 22.47 MB | UNBOUNDED, unlocked; only the `stats` CLI reads it | **Adopted** (writer; `usage_stats` reads current + archive) |
| `.pipeline/capability-events.jsonl` | 2.19 MB | UNBOUNDED but locked, 0 torn lines; readers `capability_metrics`, healthcheck | **Deferred.** No demonstrated cost at this size, and it is the path the recent concurrency P1 fix covers. Trigger: > 10 MB or a measured reader latency, then adopt the same helper |
| `.pipeline/model-router-decisions.jsonl` | ~0 | BOUNDED (500 lines, trimmed to 400), single writer | Keep |
| `~/.claude/snapshots/session-log.jsonl`, `cost-log.jsonl` (JS hooks) | ≤ 0.04 MB | BOUNDED by trim (100→50 / auto-trim) | Keep. The JS trim is read-then-rewrite, not atomic; acceptable at this size |
| `.claude/logs/security-signals.jsonl`, `boot-profile.jsonl`, `~/.claude/snapshots/engram-sync.log` | ≤ 0.15 MB | UNBOUNDED, tiny | Deferred (same trigger) |
| `capability-events.jsonl.pre-fix-archive-2026-09-23` | 73.05 MB | dead weight, read by nothing | Left in place (see below) |
| `~/.claude/projects/*.jsonl` | 100+ MB | Claude Code transcripts | **Out of scope, never touched** |

## Legacy migration and what you may delete

The first append after the upgrade finds an oversized log (> 4× the bound). It keeps the newest 2 MB as the archive and **renames the full original** to `<name>.legacy-<UTC stamp>.jsonl`. ATLAS never deletes or reads those files; deleting them is an operator decision. On this machine: `invocation-log.legacy-20261030T054635Z.jsonl` (34.66 MB, 186,111 lines) and `skills-registry-usage.legacy-20261030T054724Z.jsonl` (22.47 MB), plus the older 73 MB `pre-fix-archive`. All are gitignored.

## Failure behavior (fail-open for the caller, visible to the operator)

| Failure | Behavior |
|---|---|
| Disk full / permission on append | `append()` returns `ok=False` with the error; the caller is never raised at; existing data stays intact |
| Rotation fails (file held open, access denied) | Entry is still stored; `rotation_error` in the result, one stderr line per path per process, retries throttled for 30 s, `status()["over_bound"]` once the file exceeds 2× the bound |
| Lock not acquired in 5 s | append fails fast and writes nothing |
| Crash mid-rotation | Rotation is one atomic `os.replace`; a crash leaves the old or new state. The next append finishes it. A crash in the middle of a legacy migration can briefly duplicate the archive tail; it never hides data |
| Malformed or torn lines | Skipped by every reader |

## Known limits

- A reader that holds the files open blocks rotation on Windows until it closes (rotation reports the error and retries later).
- Test suites still append to the real `.pipeline` / `.claude/logs` files; bounding limits the damage but does not isolate them (roadmap P21).
- Cold-cache behavior on the HDD was measured with unbuffered device reads (see the performance table in the roadmap commit), not with a reproduced Defender full scan.
