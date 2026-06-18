# Getting Started with ATLAS

ATLAS is an AI Engineering Operating System built on Claude. This guide gets you from zero to a running pipeline in under 15 minutes.

## Prerequisites

| Tool | Required version | Install |
|------|-----------------|---------|
| Python | ≥ 3.11 | https://python.org |
| Node.js | ≥ 18 | https://nodejs.org |
| Git | any | https://git-scm.com |
| Go | ≥ 1.21 | https://go.dev (for Engram) |
| Claude Desktop | latest | https://claude.ai/download |

## 1. Clone and verify

```bash
git clone <your-atlas-repo> atlas
cd atlas
python tools/doctor.py
```

The doctor checks all prerequisites and reports `ATLAS READY` or lists what to fix.

## 2. Bootstrap (one command)

```powershell
# Windows
Set-ExecutionPolicy Bypass -Scope Process -Force
.\bootstrap\install.ps1
```

```bash
# Linux / macOS
bash bootstrap/install.sh
```

This installs Python packages (PyYAML, Playwright), checks Engram, and runs the healthcheck.

## 3. Open in Claude Desktop

ATLAS uses Claude Desktop on Windows. The `.mcp.json` in the project root configures MCP servers automatically when you open the project folder.

1. Launch Claude Desktop
2. Open the ATLAS project folder as your working directory
3. Claude reads `CLAUDE.md` automatically — ATLAS is now active

## 4. Activate the pipeline

Tell Claude:

```
activa el pipeline
```

or

```
nuevo proyecto completo: [your project description]
```

ATLAS enters orchestrator mode and runs the 5-phase pipeline: Plan → Architect → Dev+QA → Certify → Deploy.

## 5. Validate your setup

```bash
python tools/run_all.py --quick
```

All suites should exit with `ALL PASS`. This takes 2–5 minutes.

## Next steps

- [Installation](INSTALLATION.md) — detailed setup for each OS
- [Configuration](CONFIGURATION.md) — hooks, MCP, settings
- [Testing](TESTING.md) — running and writing QA suites
- [Release](RELEASE.md) — tagging and release validation
- [Troubleshooting](TROUBLESHOOTING.md) — common issues and fixes
