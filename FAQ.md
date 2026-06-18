# ATLAS — Frequently Asked Questions

## General

### What exactly is ATLAS?

ATLAS is a configuration layer that runs on top of Claude Code (Linux/macOS) or Claude Desktop (Windows). It adds:

- A structured 5-phase pipeline for software projects
- 25 specialized agents with defined roles
- 13 security hooks that block destructive commands
- A capability abstraction layer over MCPs
- Persistent memory via Engram MCP
- A healthcheck with 25 automated checks

ATLAS doesn't replace Claude. It gives Claude structure and discipline.

---

### Do I need to pay for ATLAS?

ATLAS itself is free and open source (MIT). You do need:

- An Anthropic account (Claude Code subscription or Claude Desktop with API access)
- Your own API keys for optional features (GitHub, Vercel, Google AI, HuggingFace, Replicate)

The main cost is Claude API usage — complex projects can use significant tokens. ATLAS includes a cost tracker so you always know.

---

### Does ATLAS work on macOS?

Yes. The Linux install script (`bash install.sh`) works on macOS. Claude Code CLI runs on macOS. Use homebrew to install dependencies.

---

### Does ATLAS work with Claude.ai (web)?

No. ATLAS requires Claude Code CLI or Claude Desktop — the local applications that support hooks, agents, and MCP configuration. The web version of Claude (claude.ai) doesn't support these.

---

### Can I use ATLAS with other AI models?

No. ATLAS is built specifically for Claude. The agents, hooks, and MCP configuration all depend on Claude's specific features (sub-agent spawning, hook interception, MCP tool calls).

---

## Installation

### The healthcheck says 23/25 PASS. Is that OK?

It depends which checks are failing. Run:
```bash
python tools/atlas_healthcheck.py
```

Read the FAIL lines. Common acceptable partial states:
- **WARN on MCP Registry** — some MCPs are optional and may not be installed
- **FAIL on Engram** — memory won't persist across sessions; fix this before real projects

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for each check.

---

### Can I install ATLAS without Engram?

Yes, but sessions won't persist. Each time you start Claude, it starts fresh. You won't be able to resume projects or have agents share state. Engram is strongly recommended.

---

### What happens if I run the install script on an existing ATLAS installation?

It overwrites:
- Agent files in `~/.claude/agents/`
- Hook files in `~/.claude/hooks/`
- `~/.claude/settings.json`
- `~/.claude/settings.local.json`
- `~/CLAUDE.md`

Your Engram memory and project files are **not** affected. Backup `~/.claude/settings.json` if you've customized it.

---

### Do I need to reinstall after `git pull`?

Yes, if agent or hook files changed. Run:
```bash
git pull origin main
bash install.sh
python tools/atlas_healthcheck.py
```

---

## Using ATLAS

### How do I start a new project?

```
modo orquestador — quiero crear [describe your project]
```

Be specific. The more context you give, the better the task breakdown. Examples:

```
modo orquestador — quiero crear un SaaS de gestión de tareas con autenticación, equipos, y exportación a PDF

modo orquestador — quiero crear una landing page para una app de meditación, con hero animado, pricing, y testimonios

modo orquestador — quiero crear un juego de plataformas 2D en Phaser.js con 3 niveles
```

---

### How do I resume a project?

```
retomar [project-name]
```

Or:
```
¿qué proyectos tengo en progreso?
```

---

### Can I stop the pipeline mid-project?

Yes. Just close Claude. When you come back:
```
retomar [project-name]
```

The orchestrator reads the DAG State from Engram and continues from the last completed phase.

---

### The orchestrator keeps re-doing Phase 1. Why?

The phase gate requires that Phase 1 artifacts exist in Engram before advancing. If they're not being saved, check Engram connectivity:
```bash
python tools/atlas_healthcheck.py   # look for Engram check
```

---

### Can I tell the orchestrator to skip a phase?

You can, but it's not recommended. Phase gates exist because skipping architecture usually causes problems in development. If you genuinely need to skip:

```
Salta la fase 2 de arquitectura — ya tenemos la arquitectura definida en [file]. Ir directo a fase 3.
```

The orchestrator will ask for confirmation.

---

### How many tokens does a typical project use?

Very rough estimates:
- Simple landing page: 50K–150K tokens
- Medium SaaS (10 features): 500K–2M tokens
- Complex project with creative pipeline: 1M–5M tokens

Use `node ~/.claude/hooks/cost-report.js` to see actual usage. Claude's token costs vary by model — the cost tracker logs per-model.

---

### Can I use ATLAS for non-web projects?

Yes. ATLAS adapts to the project:
- Mobile: React Native + Expo
- Games: Phaser.js, Three.js, PixiJS
- APIs: Hono, Express, Drizzle
- Data: Python, SQL, analysis tools

The stack is decided in Phase 1 based on your requirements.

---

## Capabilities and MCPs

### What's the difference between a Capability and an MCP?

An **MCP** is a specific implementation: `playwright`, `engram`, `context7`. It has a specific tool prefix and specific tool names.

A **Capability** is an abstraction: `browser`, `memory`, `documentation`. It can be satisfied by multiple MCPs, has fallbacks, and has a policy (ALLOW/WARN/BLOCK).

Agents use capabilities, not MCP names. This means if `playwright` is unavailable, the browser capability automatically falls back to `claude_in_chrome` without any agent code changes.

---

### Why is [capability] showing as WARN instead of ALLOW?

A WARN means the capability is usable but not at the ideal status. Common reasons:
- `repository`: GITHUB_TOKEN not set → PENDING_TOKEN status
- `deployment`: VERCEL_TOKEN not set → PENDING_TOKEN status
- `design`: 21st.dev Magic not subscribed → DEFERRED_PAID status

Check `python tools/capability_metrics.py --critical` for the critical ones. WARNs on optional capabilities are fine.

---

### Can I add my own MCP?

Yes. See [docs/MCP.md](docs/MCP.md) for the full process. Short version:
1. Register in `config/mcp.registry.yaml`
2. Add a capability in `core/capabilities/registry.py`
3. Add a policy in `config/capability.policy.yaml`
4. Add to `.mcp.json`
5. Run healthcheck to verify

---

## Hooks and Security

### Why is [command] being blocked?

ATLAS blocks commands that have caused data loss or security issues in real projects:

| Blocked pattern | Why |
|---|---|
| `git push --force` | Overwrites remote history, loses other devs' work |
| `git --no-verify` | Bypasses pre-commit hooks, ships broken code |
| `git reset --hard` | Discards all local changes permanently |
| `rm -rf` | Recursive delete, no recovery |
| `DROP TABLE / DROP DATABASE` | Irreversible data loss |
| `chmod 777 / chmod -R 777` | Opens world-write permissions |
| `chown -R` | Recursive ownership change, can lock you out |
| `curl ... \| sh` | Pipes remote code directly to shell |

---

### How do I bypass a blocked command when I genuinely need it?

Set the feature flag for that specific session:
```bash
ATLAS_HARD_RULES_DISABLED=1 your-command
```

Or for the entire session, temporarily rename the hook:
```bash
mv ~/.claude/hooks/block-no-verify.js ~/.claude/hooks/block-no-verify.js.bak
# run your command
mv ~/.claude/hooks/block-no-verify.js.bak ~/.claude/hooks/block-no-verify.js
```

The hooks are yours to control. They're there to protect you, not restrict you.

---

### What does "fail-open" mean?

If a hook crashes or times out, Claude **ignores it and continues**. Hooks never block Claude from working — they only block specific dangerous patterns. If the hook code has a bug, the worst outcome is that a protection temporarily doesn't work, not that Claude stops functioning.

---

## Contributing

### How do I add a new agent?

See [CONTRIBUTING.md#adding-a-new-agent](CONTRIBUTING.md). Short version:
1. Create `.claude/agents/<name>.md` with the required frontmatter
2. Copy to `agents/<name>.md` (mirror)
3. Add to the agent table in `CLAUDE.md`
4. Run drift test: `python _qa/bloque-F10-sot-drift.py`

---

### Can I modify the orchestrator's behavior?

Yes, edit `.claude/agents/orquestador.md`. But be careful — the orchestrator coordinates the entire pipeline. Breaking its behavior breaks all projects.

Always test after modifying: run the healthcheck and try a simple project end-to-end.

---

### How do I run the QA suites?

```bash
cd atlas/

# Run individual suite
python _qa/bloque-F20-capability-contracts.py

# Run all suites (pipe output to see summary)
for f in _qa/bloque-F*.py; do python "$f" 2>/dev/null | grep "RESULTADO"; done
```

All suites must pass before committing.
