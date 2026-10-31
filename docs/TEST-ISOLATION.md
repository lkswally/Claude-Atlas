# Test isolation (roadmap P21)

QA suites must not change the system they are checking. They did: an audit of the 50 Quick suites (per-suite
before/after snapshots of the protected locations, with a 30 s idle control that showed no change) found that **18
wrote to real state**:

| What got written | By | Why it matters |
|---|---|---|
| `.pipeline/invocation-log.jsonl` | 7 suites | it is the evidence `audit_invocations` reads to decide whether a helper really ran; test activity was counted as real activity |
| `.pipeline/capability-events.jsonl` (4 MB, grew with every run) | 9 suites | the capability metrics read it |
| `.claude/logs/skills-registry-usage.jsonl`, `security-signals.jsonl` | 4 suites | real usage / security telemetry |
| `~/.claude/snapshots/cost-log.jsonl`, `session-log.jsonl`, `engram-sync.log`, ... | 7 suites, through the JS hooks | the user's real cost and session history |
| `~/.engram/engram.db-wal` | 6 suites | they spawn the real Engram binary against the user's real database |

## What runs where now

`python tools/run_all.py --quick|--release` builds a **sandbox** (`tools/test_sandbox.py`, ~3 s) and runs every suite and the
healthcheck inside it:

* a **copy of the working tree** (tracked files plus untracked files that are not ignored, so uncommitted edits are tested,
  not the last commit), with its own `git init` and a clean HEAD for the suites that call git. `.pipeline/` is not copied: it
  starts empty. Unrelated projects (`lucas-rojo-web`, `conexo-web`, `Proyectos internos`) are not copied.
* a **disposable HOME** (`HOME`, `USERPROFILE`, `HOMEDRIVE`/`HOMEPATH`): Python's `Path.home()` and Node's `os.homedir()` (every
  hook) both resolve inside it. It holds a *copy* of `~/.claude/settings.json` and a *link* (junction on Windows, symlink
  elsewhere) to `~/go/bin`, so read-only checks of the real install keep working. `~/.claude/snapshots` and `~/.engram`
  start empty.

Why a copy and not an override in each module: the writers are about ten Python path sites and about ten JS hooks, each
computing its path its own way. A copy of the code makes all of them relative to the copy and a different HOME moves all of the rest, with
no change to any production module.

## Guarantees and limits

* The runner snapshots the real repo state before the run and **fails the run** if it changed (`isolation_leaks` in the JSON).
  The real HOME is not guarded at run time, because the host's own hooks write there while a run is in progress; F46 proves
  the HOME property deterministically instead (with a control that shows an unisolated writer does pollute).
* `--no-isolation` / `ATLAS_TEST_ISOLATION=0` run against the real tree and HOME. Use it only to debug a suite that needs the
  real environment.
* A suite that hard-codes an absolute path into the real tree would escape the sandbox. The leak guard is what catches it.
* Not isolated: anything outside the repo and HOME (network, the Windows registry, machine-wide installs).

Proof: `_qa/bloque-F46-test-isolation.py` (43 checks) and its mutation run (19 mutants, 19 caught).
