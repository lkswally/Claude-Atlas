# ATLAS — Installation Guide

This guide takes you from zero to a working ATLAS installation. Follow every step in order.

**Estimated time:** 20–40 minutes (most of it waiting for downloads)

---

## Platform Requirements

| | Linux / macOS | Windows |
|---|---|---|
| **Claude runtime** | Claude Code CLI | Claude Desktop |
| **Terminal** | Any | Git Bash (comes with Git for Windows) |
| **Shell** | bash / zsh | Git Bash (not PowerShell, not cmd) |

> All commands in this guide assume you are in **Git Bash** on Windows, or **bash/zsh** on Linux/macOS.

---

## Step 0 — Install Claude

Everything else depends on Claude being installed first.

**Linux / macOS:**
Install [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/overview) and make sure `claude` is in your PATH.

```bash
claude --version  # verify
```

**Windows:**
Install [Claude Desktop](https://claude.ai/download). Sign in with your Anthropic account.

---

## Step 1 — Install Git

**Linux:**
```bash
sudo apt-get install git    # Debian/Ubuntu
sudo dnf install git        # Fedora
sudo pacman -S git          # Arch
```

**macOS:**
```bash
brew install git
```

**Windows:**
Download and install [Git for Windows](https://git-scm.com/download/win) with default options.
This also installs **Git Bash** — use it for all commands in this guide.

```bash
git --version  # verify — should print 2.x or higher
```

---

## Step 2 — Install Python 3.10+

Python powers all ATLAS tools: healthcheck, dispatcher, capability stack, metrics, dependency graph.

**Linux:**
```bash
sudo apt-get install python3 python3-pip   # Debian/Ubuntu
# or: sudo dnf install python3            # Fedora
```

**macOS:**
```bash
brew install python@3.12
```

**Windows:**
Download from [python.org/downloads](https://www.python.org/downloads/). During install, **check "Add Python to PATH"**.

```bash
python --version   # verify — must be 3.10 or higher
# On Linux/macOS you may need: python3 --version
```

**Install PyYAML** (required for capability policy parsing):
```bash
pip install pyyaml
# or: pip3 install pyyaml
```

---

## Step 3 — Install Node.js 18+

Required for hooks (JavaScript) and MCP servers (npx).

Download the **LTS version** from [nodejs.org](https://nodejs.org).

```bash
node --version   # verify — must be 18 or higher
npm --version    # verify
```

---

## Step 4 — Install Go 1.21+ (for Engram)

Engram (persistent memory) requires Go to build from source, OR you can download a pre-built binary.

**Option A — Download pre-built binary (recommended):**
Go to [github.com/Gentleman-Programming/engram/releases](https://github.com/Gentleman-Programming/engram/releases) and download the binary for your platform.

```bash
# Linux/macOS — place in PATH
mv engram-linux-amd64 /usr/local/bin/engram
chmod +x /usr/local/bin/engram

# Windows (Git Bash) — place in ~/bin/
mkdir -p ~/bin
mv engram-windows-amd64.exe ~/bin/engram.exe
# Add ~/bin to PATH in Windows environment variables
```

**Option B — Build from source:**
```bash
# Install Go from golang.org/dl/
go install github.com/Gentleman-Programming/engram@latest
```

```bash
engram --version   # verify
```

---

## Step 5 — Install GitHub CLI (optional, recommended)

Required for the `git` agent to push to GitHub and manage PRs.

```bash
# Linux
sudo apt-get install gh     # Debian/Ubuntu
# macOS
brew install gh
# Windows: download from cli.github.com
```

```bash
gh auth login    # authenticate with GitHub
gh --version     # verify
```

---

## Step 6 — Install Vercel CLI (optional)

Required only if you plan to deploy to Vercel via the `deployer` agent.

```bash
npm install -g vercel
vercel login
vercel --version   # verify
```

---

## Step 7 — Clone ATLAS

```bash
cd ~/Desktop    # or wherever you want to keep it
git clone https://github.com/your-org/atlas.git
cd atlas
```

> Replace the URL with the actual repository URL.

---

## Step 8 — Run Install Script

**Linux / macOS:**
```bash
bash install.sh
```

The script:
- Copies 38 agent files to `~/.claude/agents/`
- Copies 16 hook files to `~/.claude/hooks/`
- Installs `settings.json` (hooks wiring) to `~/.claude/`
- Installs `settings.local.json` (agent permissions) to `~/.claude/`
- Copies `CLAUDE.md` globally to `~/CLAUDE.md`
- Configures git user settings

**Windows:**
The install script doesn't run on Windows. Copy files manually:

```bash
# From Git Bash, inside the atlas/ directory:

# 1. Agent files (38 files: 25 agents + 13 references)
mkdir -p ~/.claude/agents
cp agents/*.md ~/.claude/agents/

# 2. Hook files (16 files: 13 reactive + 3 utilities)
mkdir -p ~/.claude/hooks
cp hooks/*.js ~/.claude/hooks/

# 3. settings.json (hook wiring)
CLAUDE_HOME=$(cygpath -u "$USERPROFILE/.claude" 2>/dev/null || echo "$HOME/.claude")
sed "s|__CLAUDE_HOME__|$CLAUDE_HOME|g" templates/settings.json > ~/.claude/settings.json

# 4. Agent permissions
cp templates/settings.local.json ~/.claude/settings.local.json

# 5. CLAUDE.md global
cp templates/windows-claude.md ~/CLAUDE.md
```

---

## Step 9 — Configure MCPs

MCPs (Model Context Protocol servers) give Claude access to memory, browser automation, documentation, and more.

### Engram MCP (required — persistent memory)

**Linux / macOS — add to `~/.claude/settings.json`:**

The install script handles this. Verify `~/.claude/settings.json` has:
```json
"enabledPlugins": {
  "engram@engram": true
}
```

**Windows — configure `claude_desktop_config.json`:**

Open (create if it doesn't exist):
```
%APPDATA%\Claude\claude_desktop_config.json
```

In Git Bash:
```bash
code "$APPDATA/Claude/claude_desktop_config.json"
# or: notepad "$APPDATA/Claude/claude_desktop_config.json"
```

Paste this content (replace `{YOUR_USERNAME}` with your Windows username):
```json
{
  "mcpServers": {
    "engram": {
      "command": "C:\\Users\\{YOUR_USERNAME}\\bin\\engram.exe",
      "args": ["mcp", "--tools=agent"]
    },
    "context7": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    "playwright": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["playwright-mcp"]
    }
  }
}
```

> A ready-made template is at `templates/windows-mcp-config.json`.

> If Node.js is in a different location, find it with `where npx` in Command Prompt.

**Restart Claude** (Desktop or Code) after editing MCP config.

### Playwright MCP (required for visual QA)

```bash
npx playwright install chromium
```

### Context7 MCP (recommended — live documentation)

No API key needed. Registered via `npx` in the MCP config above.

---

## Step 10 — Create .env.local (optional tokens)

Copy the template and fill in what you have:

```bash
cp .env.example .env.local
```

Edit `.env.local`:
```bash
# Required for GitHub operations (git push, PR management)
GITHUB_TOKEN=ghp_...

# Required for AI-generated images (Phase 2B)
GEMINI_API_KEY=...   # OR HF_TOKEN=... (at least one)
HF_TOKEN=...

# Required for AI-generated videos (Phase 2B)
REPLICATE_API_TOKEN=...

# Required for Vercel deploy via API
VERCEL_TOKEN=...
```

You can leave unused tokens empty or absent — ATLAS degrades gracefully and tells you what's missing.

---

## Step 11 — Run Healthcheck

This is your first real verification that everything installed correctly.

```bash
python tools/atlas_healthcheck.py
```

Expected output:
```
============================================================
ATLAS Runtime Healthcheck
============================================================
[PASS] Node.js            v24.x
[PASS] Python             3.1x
[PASS] npm                ...
[PASS] .claude/settings.json    JSON válido, 13 hooks registrados
[PASS] Hooks en disco           13/13 existen
...
[PASS] Capability policy (F19)  14 policies | ALLOW=7 WARN=7 BLOCK=0
...
============================================================
RESULTADO : PASS=25  WARN=0  FAIL=0  / 25 checks
STATUS    : HEALTHY
```

If any checks FAIL, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Step 12 — First Use

Read [FIRST_RUN.md](FIRST_RUN.md) for what to do next.

Short version:
```
# In Claude, say:
modo orquestador — quiero crear [your project idea]
```

---

## Dependency Reference

| Dependency | Version | Required | Purpose |
|-----------|---------|---------|---------|
| Claude Code CLI / Claude Desktop | Latest | **Yes** | Runtime — ATLAS has no effect without it |
| Git | 2.x+ | **Yes** | Version control, install script |
| Python | 3.10+ | **Yes** | All tools: healthcheck, dispatcher, capabilities |
| PyYAML | Any | **Yes** | Capability policy YAML parsing |
| Node.js | 18+ | **Yes** | Hooks (JavaScript), npx for MCPs |
| Go | 1.21+ | If building Engram | Build Engram from source |
| Engram binary | Latest | **Yes** | Persistent memory across sessions |
| Playwright Chromium | Latest | For visual QA | Browser automation in evidence-collector |
| GitHub CLI (gh) | Any | For GitHub ops | Push code, manage PRs |
| Vercel CLI | Any | For deployment | Deploy to Vercel |
| GEMINI_API_KEY | — | For AI images | Phase 2B image generation |
| HF_TOKEN | — | For AI images (fallback) | Phase 2B via HuggingFace |
| REPLICATE_API_TOKEN | — | For AI video | Phase 2B video generation |
| GITHUB_TOKEN | — | For GitHub MCP | Repository operations via MCP |
| VERCEL_TOKEN | — | For Vercel MCP | Deployment via MCP |

---

## Updating ATLAS

```bash
cd atlas/
git pull origin main
bash install.sh    # re-run to update agents and hooks
python tools/atlas_healthcheck.py   # verify after update
```

---

## Uninstalling

ATLAS only adds files to `~/.claude/`. To remove:

```bash
# Remove agents
rm ~/.claude/agents/*.md

# Remove hooks
rm ~/.claude/hooks/*.js

# Remove settings (this will remove all Claude tool permissions)
rm ~/.claude/settings.json
rm ~/.claude/settings.local.json

# Remove CLAUDE.md
rm ~/CLAUDE.md
```

Your projects and Engram memory are not affected.
