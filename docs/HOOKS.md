# ATLAS — Hook Reference

Hooks are JavaScript files that run before or after Claude tool calls. They enforce security, quality, and workflow policies.

---

## How Hooks Work

When Claude executes a tool (like `Bash` or `Write`), Claude Code/Desktop checks `~/.claude/settings.json` for matching hooks and runs them.

Each hook receives input via stdin as JSON:
```json
{
  "tool_name": "Bash",
  "tool_input": { "command": "git push --force" }
}
```

**Exit code determines behavior:**
- `exit 2` → **BLOCK**: tool call is cancelled, error shown to Claude
- `exit 0` + stderr output → **WARN**: tool proceeds, warning logged
- `exit 0` + no output → **ALLOW**: tool proceeds silently

**Fail-open guarantee:** if a hook crashes, times out, or has a bug, Claude proceeds as if the hook wasn't there. Hooks can only add protection, never break Claude.

---

## Hook Types

| Type | When it runs | ATLAS hooks |
|------|-------------|-------------|
| `PreToolUse` | Before a tool executes | block-no-verify, pipeline-rules, config-protection |
| `PostToolUse` | After a tool executes | quality-gate, console-log-warning, delegation-tracker, qa-auto-audit, cost-tracker, suggest-compact |
| `PreCompact` | Before context compaction | pre-compact-engram |
| `Stop` | When session ends | session-summary, engram-sync |
| `Notification` | When session starts | session-start-context |

---

## Reactive Hooks (13)

These are registered in `settings.json` and run automatically.

### block-no-verify.js
**Type:** PreToolUse | **Matcher:** Bash | **Action:** BLOCK

Blocks commands that have caused data loss in real projects:

| Pattern | Why blocked |
|---------|------------|
| `git push --force` | Overwrites remote history |
| `git -C <dir> push --force` | Same — via directory flag |
| `git --no-verify` | Bypasses pre-commit hooks |
| `git reset --hard` | Discards all local changes |
| `rm -rf` | Recursive delete |
| `DROP TABLE / DROP DATABASE` | Irreversible data loss |
| `chmod 777` / `chmod -R 777` / `chmod 0777` | World-write permissions |
| `chown -R` / `chown --recursive` | Recursive ownership change |
| `curl ... \| sh` | Remote code execution |

**Disable:** `ATLAS_HARD_RULES_DISABLED=1` (set in environment before running Claude)

---

### config-protection.js
**Type:** PreToolUse | **Matcher:** Write/Edit | **Action:** BLOCK / WARN

- **BLOCKS** writes to `.env`, `.pem`, `.key`, credentials files, private keys
- **WARNS** on changes to linting/formatting config (ESLint, Prettier, stylelint)

**Why:** Prevents accidentally overwriting secret files. Config changes need human awareness.

---

### pipeline-rules.js
**Type:** PreToolUse | **Matcher:** Bash | **Action:** BLOCK / WARN

Enforces hard rules from `config/hard-rules.json`:
- **BLOCKS:** force push to main/master
- **BLOCKS:** merging a PR that requires pilots without pilot evidence
- **WARNS:** cross-repo commits (unexpected)
- **WARNS:** using capabilities without consulting skills registry

---

### delegation-tracker.js
**Type:** PostToolUse | **Matcher:** all | **Action:** WARN (async)

Monitors agent delegation patterns. Detects when the orchestrator is looping (same agent spawned 3+ times for the same task). Sets flags: `escalation_needed`, `pause_recommended`, `fresh_review_recommended`.

---

### quality-gate.js
**Type:** PostToolUse | **Matcher:** Write/Edit | **Action:** WARN (async)

Inspects written/edited files for problematic patterns:
- `debugger` statements
- `.only()` in tests (skips other tests)
- `@ts-ignore` (masks type errors)
- Hardcoded secrets (API keys, passwords)
- `TODO/FIXME` comments in non-development files

---

### console-log-warning.js
**Type:** PostToolUse | **Matcher:** Write/Edit | **Action:** WARN (async)

Detects `console.log()`, `console.warn()`, `console.error()` in production code. Ignores test files (`*.test.*`, `*.spec.*`, files in `__tests__/`).

---

### qa-auto-audit.js
**Type:** PostToolUse | **Matcher:** all | **Action:** WARN (async)

After a sub-agent finishes (detected by Agent tool use), audits whether the agent called all mandatory helpers. Warns if expected helpers (like `verify_pre_return_audit`) were skipped.

---

### cost-tracker.js
**Type:** PostToolUse | **Matcher:** all | **Action:** LOG (async)

Logs each tool call to `.claude/logs/cost-tracker.jsonl`:
- Tool name
- Category (bash, file-op, agent-spawn, mcp)
- Model used (if detectable)
- Sub-agent context

View with: `node ~/.claude/hooks/cost-report.js`

---

### suggest-compact.js
**Type:** PostToolUse | **Matcher:** all | **Action:** WARN (async)

Every ~50 tool calls, suggests running `/compact` to manage context window. Includes current pipeline phase context so the suggestion is informative.

---

### pre-compact-engram.js
**Type:** PreCompact | **Action:** SAVE + WARN

Before context compaction:
1. Saves a snapshot to `~/.claude/pre-compact-snapshot.json` (tool count, cwd, pipeline status, timestamp)
2. Emits to stderr: `COMPACTION IMMINENT — SAVE STATE NOW`

Claude reads this message before compaction and immediately saves DAG State to Engram and disk.

---

### session-summary.js
**Type:** Stop | **Action:** LOG (async)

When a session ends, logs a summary to `.claude/logs/session-summary.jsonl`: session duration, tool count, active project, last phase.

---

### engram-sync.js
**Type:** Stop | **Action:** SYNC (async, 60s timeout)

When a session ends, pushes Engram memories to a connected GitHub repo (if configured). Enables cross-machine continuity.

**Setup:**
```bash
cd ~/.engram
git init
git remote add origin https://github.com/YOUR_USER/my-engram-sync.git
```

---

### session-start-context.js
**Type:** Notification | **Action:** LOAD

When a session starts:
1. Reads `~/.claude/pre-compact-snapshot.json` (if it exists)
2. Loads the previous session context
3. Runs a hook health check

Enables Claude to know which project was active and resume intelligently.

---

## Manual Utilities (3)

These are NOT in `settings.json` — run them explicitly when needed.

### audit-system.js
**Purpose:** System integrity check (6 checks)

```bash
node ~/.claude/hooks/audit-system.js
```

Validates: agents exist, hooks exist, settings.json is valid, Engram is connected, CLAUDE.md is present, protocol compliance.

### cost-report.js
**Purpose:** Token/tool usage breakdown

```bash
node ~/.claude/hooks/cost-report.js
node ~/.claude/hooks/cost-report.js --since=7   # last 7 days
```

Shows: total tool calls by category, most-used tools, per-session summaries.

### learning-index.js
**Purpose:** Discovery index

```bash
node ~/.claude/hooks/learning-index.js
```

Builds a searchable index of discoveries and learnings from past sessions, tagged by technology.

---

## Writing a Safe Hook

Hooks run in every Claude session. A bad hook can cause problems. Follow these rules:

### 1. Always fail-open

```javascript
process.on('uncaughtException', (err) => {
  // Log to stderr (WARN) but always exit 0
  process.stderr.write(`[hook-name] error: ${err.message}\n`);
  process.exit(0);
});
```

### 2. Parse stdin defensively

```javascript
let input = {};
try {
  const raw = require('fs').readFileSync('/dev/stdin', 'utf8');
  input = JSON.parse(raw);
} catch {
  process.exit(0);  // fail-open on bad input
}
```

### 3. Check ATLAS_*_DISABLED env vars

```javascript
if (process.env.ATLAS_MY_FEATURE_DISABLED === '1') {
  process.exit(0);
}
```

### 4. Be fast for blocking hooks

Blocking hooks (PreToolUse exit 2) delay the user. Keep them under 100ms. Never make network calls in blocking hooks.

### 5. Use async for logging

```javascript
// Good: don't block on I/O
fs.appendFile(logFile, entry, () => {});
process.exit(0);
```

### 6. Test with empty input

```bash
echo '{}' | node ~/.claude/hooks/my-hook.js
echo $?   # must be 0
```

### 7. Register in settings.json

After creating `~/.claude/hooks/my-hook.js`:
```json
{
  "PostToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "node __CLAUDE_HOME__/hooks/my-hook.js", "timeout": 5, "async": true }
      ]
    }
  ]
}
```

### 8. Copy to mirror

```bash
cp ~/.claude/hooks/my-hook.js hooks/my-hook.js
python _qa/bloque-F10-sot-drift.py   # verify sync
```
