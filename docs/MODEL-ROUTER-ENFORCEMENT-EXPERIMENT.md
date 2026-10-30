# Model Router enforcement experiment (roadmap P3)

**Verdict: `ENFORCEMENT_UNKNOWN` → the router stays `MODEL_ROUTER_ADVISORY_ONLY`.**
Blocker: `EXTERNALLY_BLOCKED` on credentials. The only Claude Code binary reachable from a script here answered `Not logged in · Please run /login` (rc 1, cost $0, hook never invoked), so no model was ever run. Nothing was inferred to fill the gap.

## What has to be true for enforcement (three links)

| # | Link | Status |
|---|---|---|
| 1 | A `PreToolUse` hook on the `Agent` tool can return `hookSpecificOutput.updatedInput` and replace the tool input | **Documented** (hooks reference, fetched 2026-10-29). Not exercised in ATLAS. |
| 2 | A rewritten `model` is the model the subagent actually runs on | **Not documented, not proven.** The docs also say `resolvedModel` can differ from `tool_input.model`. |
| 3 | The effective model is observable independently of the hook | Expected: the subagent's own assistant messages carry `message.model` in `stream-json`, and the final `result` carries `modelUsage`. **Field presence not yet seen in a live run** (R0 aborted before any model call), so the classifier treats absent fields as UNKNOWN. |

## What was built (lab only, wired nowhere)

`tools/lab_model_enforcement/`: `hook_lab.py` (does exactly what `LAB_MODE` says and logs every payload) and `enforcement_lab.py` (runs the real binary, extracts runtime evidence, classifies). Isolation: scratch working dir, `--setting-sources project` (user settings and ATLAS hooks are **not** loaded), a generated hook-only `--settings` file, `--strict-mcp-config`, `--no-session-persistence`, only the `Agent` tool allowed. No ATLAS or Claude configuration is touched, and `templates/settings.json` does not reference the lab (F40 asserts it).

**Verdict rule (`classify`, 4 runs of the same prompt):** control and rewrite for a Sonnet parent, control and rewrite for an Opus parent. `ENFORCEMENT_PROVEN` only if the subagent's own assistant `model` follows the rewrite in **both** directions **and** differs from that direction's no-rewrite control. The hook's log or JSON can never produce PROVEN; it is only used to tell "rewrite ignored" (`UNSUPPORTED`) from "hook never ran" (`UNKNOWN`). A model that merely equals the default or the inherited parent model is not attributable and is not PROVEN.

**Offline proof of the verdict logic:** `_qa/bloque-F40-enforcement-lab.py`, 18 checks (including "the hook claims a rewrite but the runtime shows none" and "the call requested the target model but another ran"), mutation sanity 7/7 caught.

## What was deliberately not done

- No search for, or use of, the desktop app's authentication (another process's environment or credential store). That would be credential extraction.
- No edit to `~/.claude/settings.json` or to this project's settings to register a live hook (modifies live behavior and security configuration).
- No subagent spawned from this session for a side experiment.

## To unblock (owner action, a few minutes)

Authenticate an **isolated** config directory once, so the lab never touches your real Claude login:

```bash
# PowerShell
$env:CLAUDE_CONFIG_DIR = "D:\ProyectosIA\_enforce_lab\cfg"
& "$env:LOCALAPPDATA\Claude-Data\claude_pzs8sxrjxfjjc\claude-code\2.1.309\9078b9c1d466\claude.exe"   # complete /login in the prompt, then /exit
```

Then run the matrix (four tiny headless runs on your own subscription):

```bash
$env:ATLAS_LAB_CLAUDE_CONFIG_DIR = "D:\ProyectosIA\_enforce_lab\cfg"
python tools/lab_model_enforcement/enforcement_lab.py matrix
```

It prints the four case views and one verdict. An `ANTHROPIC_API_KEY` would also work but is pay-per-use, so it is not recommended.

## Decision table

| Verdict | Action |
|---|---|
| `ENFORCEMENT_PROVEN` | Implement the smallest `ModelRoutingEnforcementAdapter` (router decision → `updatedInput`); static agent frontmatter stays the fallback; invalid / disabled / unavailable decisions, hook errors and timeouts all preserve the static default (never an unknown model); tests + mutation sanity |
| `ENFORCEMENT_UNSUPPORTED` | Stay advisory; record that the rewrite is ignored for this Claude Code version |
| `ENFORCEMENT_UNKNOWN` | Stay advisory (current state) |

## Why advisory is safe now

No hook is registered on `Agent`, the router decides nothing at runtime, and all 27 agent frontmatter `model:` defaults are untouched. The only cost of staying advisory is that routing decisions are recommendations.
