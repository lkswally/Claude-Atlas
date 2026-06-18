# Configuration

ATLAS is configured through a set of declarative files. No environment variables are required for basic operation.

## Core config files

### `.mcp.json` (project root)

Configures MCP servers for Claude Desktop/Code. Created automatically if missing.

```json
{
  "mcpServers": {
    "engram": {
      "command": "path/to/engram",
      "args": ["mcp-server"],
      "env": { "ENGRAM_DB_PATH": "~/.engram/engram.db" }
    },
    "context7": { "command": "npx", "args": ["-y", "@upstash/context7-mcp"] },
    "playwright": { "command": "npx", "args": ["@playwright/mcp@latest"] },
    "github": { "command": "npx", "args": ["@modelcontextprotocol/server-github"],
                "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." } }
  }
}
```

### `config/mcp.registry.yaml`

Declarative inventory of all 21 MCP servers: status (`LIVE`, `CONFIG_ONLY`, `PENDING_TOKEN`, `DEFERRED_PAID`), required tokens, and capabilities.

### `config/capability.policy.yaml`

14 capability policies. Each declares whether to `ALLOW`, `WARN`, or `BLOCK` when the capability is unavailable. Also configures criticality and fallback behavior.

### `config/atlas.runtime.expected.yaml`

The stable reference for what hooks and MCP servers are expected at runtime. Used by F23 to avoid false failures when `.claude/settings.json` is absent.

### `config/phase_playbook.json`

E2E flows required by the dispatcher before each pipeline phase transition. Checked by `atlas_dispatcher.py check-phase`.

### `.claude/hard-rules.json`

Declarative enforcement rules: block, warn, or allow specific git operations, skill usage patterns, and cross-repo commits. Loaded by `pipeline-rules.js` hook.

### `.claude/skills.registry.yaml`

Catalog of 10 skills across 4 domains (design, qa, branding, orchestration). The dispatcher reads this to match capabilities to the right skill.

## Environment variables

These are optional. ATLAS is fail-open — unset variables use safe defaults.

| Variable | Effect | Default |
|----------|--------|---------|
| `ATLAS_HEALTHCHECK_STRICT` | `=1` makes settings.json absent → FAIL | `0` (WARN) |
| `ATLAS_SKILLS_REGISTRY_DISABLED` | `=1` disables skills registry | off |
| `ATLAS_HARD_RULES_DISABLED` | `=1` disables hard rules enforcement | off |
| `ATLAS_PYDANTIC_CONTRACTS_DISABLED` | `=1` falls back to dict validation | off |
| `ATLAS_SKILLS_USAGE_LOG_DISABLED` | `=1` disables usage logging | off |
| `ENGRAM_DB_PATH` | Custom Engram database path | `~/.engram/engram.db` |
| `PYTHONIOENCODING` | Set to `utf-8` for Windows | system default |

## Hook configuration

Hooks are JS scripts in `.claude/hooks/`. They're registered in `.claude/settings.json` (managed by Claude Desktop). Do not edit `settings.json` directly — Claude Desktop may overwrite it.

The stable reference is `templates/settings.json` (with `__CLAUDE_HOME__` placeholders).

See [HOOKS.md](HOOKS.md) for the full hook inventory.
