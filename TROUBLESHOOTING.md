# ATLAS — Troubleshooting

Start here: **run the healthcheck first.**

```bash
python tools/atlas_healthcheck.py
```

The healthcheck runs 25 checks and tells you exactly what's failing. Most issues are diagnosed immediately.

---

## Healthcheck is failing

### [FAIL] Python — not found or wrong version

```
[FAIL] Python    not found
```

**Fix:** Install Python 3.10+ and ensure it's in your PATH.

- Windows: Download from [python.org](https://python.org/downloads). During install, check "Add Python to PATH".
- Linux: `sudo apt-get install python3`
- macOS: `brew install python@3.12`

After installing, close and reopen your terminal, then retry.

---

### [FAIL] Node.js — not found or wrong version

```
[FAIL] Node.js   not found
```

**Fix:** Install Node.js 18+ from [nodejs.org](https://nodejs.org).

---

### [FAIL] .claude/settings.json — not found or invalid JSON

```
[FAIL] .claude/settings.json    not found
```

**Fix:** Run the install step again:

```bash
CLAUDE_HOME=$(echo "$HOME/.claude")
sed "s|__CLAUDE_HOME__|$CLAUDE_HOME|g" templates/settings.json > ~/.claude/settings.json
```

Or on Windows Git Bash:
```bash
CLAUDE_HOME=$(cygpath -u "$USERPROFILE/.claude" 2>/dev/null || echo "$HOME/.claude")
sed "s|__CLAUDE_HOME__|$CLAUDE_HOME|g" templates/settings.json > ~/.claude/settings.json
```

---

### [FAIL] Hooks en disco — files missing

```
[FAIL] Hooks en disco    8/13 existen
```

**Fix:** Copy hooks again:
```bash
cp hooks/*.js ~/.claude/hooks/
```

---

### [FAIL] Hooks smoke test — hook crashes on empty input

```
[FAIL] Hooks smoke test    block-no-verify.js exits non-zero
```

**Fix:** A hook is crashing. Test it manually:
```bash
echo '{}' | node ~/.claude/hooks/block-no-verify.js
echo $?   # should be 0
```

If it's not 0, the hook has a syntax error. Re-copy from the repo:
```bash
cp hooks/block-no-verify.js ~/.claude/hooks/
```

---

### [FAIL] Engram — not connected {#engram}

```
[FAIL] Engram    binary not found / DB not reachable
```

**Possible causes:**

**1. Engram binary not installed or not in PATH:**
```bash
engram --version   # if this fails, binary isn't in PATH
```

Fix: Download binary from [github.com/Gentleman-Programming/engram/releases](https://github.com/Gentleman-Programming/engram/releases) and place it in your PATH.

Linux/macOS:
```bash
sudo mv engram-linux-amd64 /usr/local/bin/engram
sudo chmod +x /usr/local/bin/engram
```

Windows Git Bash:
```bash
mkdir -p ~/bin
mv engram-windows-amd64.exe ~/bin/engram.exe
# Then add ~/bin to your Windows PATH environment variable
```

**2. Engram not configured as an MCP in Claude:**

Linux/macOS — check `~/.claude/settings.json` has:
```json
"enabledPlugins": { "engram@engram": true }
```

Windows — check `%APPDATA%\Claude\claude_desktop_config.json` has the engram MCP server entry. See [INSTALL.md#step-9](INSTALL.md).

**3. Engram database is corrupt:**
```bash
engram doctor
```

---

### [FAIL] Capabilities layer — import error

```
[FAIL] Capabilities layer    ModuleNotFoundError: No module named 'core'
```

**Fix:** The healthcheck must run from the ATLAS project directory:
```bash
cd /path/to/atlas
python tools/atlas_healthcheck.py
```

---

### [FAIL] Capability policy — critical capability BLOCKED

```
[FAIL] Capability policy    memory BLOCK
```

**Fix:** The memory capability is BLOCKED, which means Engram is not available. Fix Engram first (see above).

---

### [WARN] MCP Registry — missing-required

```
[WARN] MCP Registry    11 LIVE, 4 missing-required
```

This is a warning, not a failure. It means some MCPs in the registry are marked as required but aren't in your `.mcp.json`. Common culprits:

- **GitHub MCP:** needs `GITHUB_TOKEN`. Register in `.mcp.json` or set the token.
- **Vercel MCP:** needs `VERCEL_TOKEN`.

These are optional for basic usage.

---

## Claude Issues

### Claude doesn't recognize agents

**Symptom:** Claude ignores `modo orquestador` or says it doesn't have specialized agents.

**Fix:**
1. Verify agent files are in the right place:
   ```bash
   ls ~/.claude/agents/*.md | wc -l   # should be 38
   ```
2. Restart Claude (Desktop or Code CLI).
3. Make sure `~/CLAUDE.md` exists:
   ```bash
   head -3 ~/CLAUDE.md   # should show ATLAS instructions
   ```

---

### Claude says "I don't have access to Engram"

**Symptom:** Memory operations fail, Claude doesn't recognize `mem_save` or `mem_search`.

**Fix:**
- Claude Desktop (Windows): Check `%APPDATA%\Claude\claude_desktop_config.json` — Engram must be in `mcpServers`.
- Claude Code (Linux): Check `~/.claude/settings.json` — `enabledPlugins.engram@engram` must be `true`.
- Restart Claude after any config changes.

---

### Hooks aren't firing

**Symptom:** You can run `git push --force` without being blocked.

**Fix:**
1. Verify `~/.claude/settings.json` exists and is valid JSON:
   ```bash
   python -c "import json; json.load(open('$HOME/.claude/settings.json')); print('OK')"
   ```
2. Verify hooks are in `~/.claude/hooks/`:
   ```bash
   ls ~/.claude/hooks/*.js | wc -l   # should be 16
   ```
3. Restart Claude.

---

### Pipeline seems stuck at a phase

**Symptom:** Orchestrator keeps re-doing the same phase.

**Fix:** Check what's in memory:
```
mem_search "[project-name]/estado"
```

If the state shows the wrong phase, or shows `null`, the state may be corrupt. You can manually advance:
```
El estado en Engram dice fase 1 completada pero está atascado. Por favor leer el estado actual y continuar desde fase 2.
```

---

## Python / Tool Issues

### `python` not found on Linux/macOS

```bash
python3 --version   # try python3 instead
```

If your system uses `python3`, create an alias:
```bash
echo "alias python=python3" >> ~/.bashrc && source ~/.bashrc
```

---

### `pip install pyyaml` fails

```bash
pip3 install pyyaml   # try pip3
# or:
python -m pip install pyyaml
```

---

### Import errors in QA suites

```
ModuleNotFoundError: No module named 'core'
```

All `_qa/*.py` and `tools/*.py` scripts must run from the ATLAS project root:
```bash
cd /path/to/atlas
python _qa/bloque-F20-capability-contracts.py
```

---

## Windows-Specific Issues

### `preview_start` fails with ENOENT

Check `~/.claude/launch.json` uses `cmd /c` format:
```json
{
  "runtimeExecutable": "cmd",
  "runtimeArgs": ["/c", "cd my-project && npm run dev"],
  "port": 3000
}
```

---

### Git Bash shows `python: command not found`

Python on Windows sometimes installs as `python` only in Command Prompt, not Git Bash. Fix:

1. In **System Properties > Environment Variables**, find Python in the PATH.
2. In Git Bash: `alias python='winpty python'` → add to `~/.bashrc`.

Or use: `py tools/atlas_healthcheck.py` (Python Launcher for Windows).

---

### `cygpath` not available

The install script uses `cygpath` for path conversion. If it's not available:
```bash
CLAUDE_HOME="$HOME/.claude"
sed "s|__CLAUDE_HOME__|$CLAUDE_HOME|g" templates/settings.json > ~/.claude/settings.json
```

---

### Claude Desktop MCPs don't appear

1. Verify `%APPDATA%\Claude\claude_desktop_config.json` is valid JSON.
2. Verify the `command` paths exist (use `where npx` in CMD to find correct path).
3. Restart Claude Desktop completely (not just reload).
4. Check Claude Desktop logs: open Developer Tools from the Help menu.

---

## Getting More Help

1. Run `python tools/atlas_healthcheck.py` and share the output.
2. Run `node ~/.claude/hooks/audit-system.js` and share the output.
3. Check [FAQ.md](FAQ.md) for common questions.
4. Open an issue with the healthcheck output and your OS/platform details.
