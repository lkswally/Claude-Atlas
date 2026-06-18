# Testing

ATLAS has 25+ QA suites in `_qa/` covering every subsystem. All suites are runnable as plain Python scripts.

## Single command

```bash
# Fast local validation (2-5 min)
python tools/run_all.py --quick

# Full validation including live binaries (5-10 min)
python tools/run_all.py --full

# Release validation — required before any version tag (10-20 min)
python tools/run_all.py --release
```

## What each mode runs

| Mode | Suites | Healthcheck | Live binaries | Report |
|------|--------|-------------|---------------|--------|
| `--quick` | all except F13-engram-active | no | no | no |
| `--full` | all | no | yes | no |
| `--release` | all | yes (strict) | yes | yes (`release-report.md`) |

## JSON output

```bash
python tools/run_all.py --quick --json
python tools/run_all.py --release --json --out run_all.json
```

Output structure:
```json
{
  "mode": "quick",
  "total": 28,
  "passed": 28,
  "failed": 0,
  "skipped": 1,
  "elapsed": 127.4,
  "git": { "commit": "...", "tag": "v0.24.0", "dirty": false },
  "healthcheck": null,
  "suites": [{ "suite": "bloque-F4-js-hooks-validation", "passed": true, ... }]
}
```

## Suite catalog

| Suite | What it validates |
|-------|-------------------|
| `bloque-F4` | JS hook syntax and execution |
| `bloque-F5` | settings.json hook wiring |
| `bloque-F6` | runtime hooks validation |
| `bloque-F7` | healthcheck self-validation |
| `bloque-F8` | Engram audit |
| `bloque-F10` | SOT drift (agents/ vs ~/.claude/agents/) |
| `bloque-F11-1` | Return Envelope contract |
| `bloque-F11-5` | Backward compatibility |
| `bloque-F11-skills-registry-runtime` | Skills registry runtime |
| `bloque-F13-engram` | Engram strategy pattern |
| `bloque-F13-engram-active` | Live Engram binary (skipped in --quick) |
| `bloque-F14` | MCP registry |
| `bloque-F15-context7` | Context7 MCP |
| `bloque-F15-github` | GitHub MCP |
| `bloque-F15-notion` | Notion MCP |
| `bloque-F15-playwright` | Playwright MCP |
| `bloque-F16` | Capability router |
| `bloque-F17` | Agent capability migration |
| `bloque-F18` | Capability metrics |
| `bloque-F19` | Capability policy |
| `bloque-F20-security-hooks` | Security hook enforcement |
| `bloque-F20-capability-contracts` | Capability contracts |
| `bloque-F21-1` | Skills registry |
| `bloque-F21-2` | Hard rules |
| `bloque-F21b-1` | Usage logging |
| `bloque-F22-command-audit` | Command audit |
| `bloque-F22-run-all` | run_all.py self-validation |
| `bloque-F22-runtime-truth` | Runtime truth validation |
| `bloque-F22-secrets-check` | Secrets scanner |
| `bloque-F23-runtime-settings-separation` | settings.json race condition (F23) |

## Running a single suite

```bash
python _qa/bloque-F7-healthcheck-validation.py
```

## Timeouts

Most suites finish in under 30 seconds. The F23 suite renames `.claude/settings.json`
multiple times and takes ~3 minutes. `run_all.py` applies a 300-second override automatically.

## Writing a new suite

1. Create `_qa/bloque-FXX-description.py`
2. Use the standard pattern:

```python
#!/usr/bin/env python3
PASS_COUNT = 0; FAIL_COUNT = 0

def PASS(name, detail=""): ...
def FAIL(name, detail=""): ...

def test_01_something():
    ...
    PASS("TC1 name", "detail")

test_01_something()
print(f"\nRESULTADO: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} PASS, {FAIL_COUNT} FAIL")
import sys; sys.exit(0 if FAIL_COUNT == 0 else 1)
```

3. `run_all.py` discovers it automatically (no registration needed)
