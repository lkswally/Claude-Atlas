# ATLAS — Request Flows

How a request moves through the system from user input to output.

---

## Flow 1: New Project

```
User: "modo orquestador — quiero crear un SaaS de gestión de tareas"
```

### Phase 0 — Boot

```
Orquestador (Opus)
  │
  ├─ mem_context(scope="personal")     # load user profile
  ├─ mem_search("tareas-saas/boot-state")  # check if project exists
  │    → NOT_FOUND → new project
  └─ Determine: FULL boot mode
```

### Phase 1 — Planning

```
Orquestador → spawn project-manager-senior
  │
  │  project-manager-senior (Sonnet)
  │    ├─ mem_search("tareas-saas/requisitos")
  │    ├─ Creates task breakdown (granular, with acceptance criteria)
  │    ├─ mem_save("tareas-saas/tareas", content=task_list)
  │    └─ Return Envelope: STATUS: completado | ENGRAM: tareas-saas/tareas
  │
  ├─ Orquestador validates Return Envelope (dispatcher)
  └─ Phase Gate: tareas-saas/tareas exists? → YES → advance to Phase 2
```

### Phase 2 — Architecture

```
Orquestador → spawn ux-architect (sequential first)
  │
  │  ux-architect (Sonnet)
  │    ├─ mem_search("tareas-saas/tareas") → mem_get_observation(id)
  │    ├─ Creates CSS foundation: tokens, layout, breakpoints
  │    ├─ mem_save("tareas-saas/css-foundation", ...)
  │    └─ Return Envelope: STATUS: completado
  │
  └─ spawn ui-designer + security-engineer (parallel)
       │
       │  ui-designer (Sonnet)
       │    ├─ Reads css-foundation from Engram
       │    ├─ Creates design system, components
       │    └─ mem_save("tareas-saas/design-system", ...)
       │
       │  security-engineer (Opus)
       │    ├─ STRIDE threat model
       │    ├─ OWASP Top 10 analysis
       │    └─ mem_save("tareas-saas/security-spec", ...)
       │
       └─ Phase Gate: all three drawers exist → advance to Phase 3
```

### Phase 3 — Development Loop

```
For each task in tareas-saas/tareas:
  │
  ├─ Orquestador → spawn frontend-developer (or backend-architect, etc.)
  │    │
  │    │  developer (Sonnet)
  │    │    ├─ Read design-system, security-spec from Engram
  │    │    ├─ Implement feature
  │    │    └─ Return Envelope: STATUS: completado | ARCHIVOS: [src/...]
  │    │
  │    ├─ HOOK: quality-gate fires on Write/Edit
  │    │    → warns on debugger, .only(), hardcoded secrets
  │    │
  │    └─ Orquestador → spawn evidence-collector
  │         │
  │         │  evidence-collector (Sonnet)
  │         │    ├─ resolve_capability("browser") → playwright LIVE
  │         │    ├─ browser_navigate → browser_take_screenshot (3 viewports)
  │         │    ├─ Screenshots saved to /tmp/qa/ (never in context)
  │         │    └─ Return Envelope: STATUS: PASS | ARCHIVOS: [/tmp/qa/...]
  │         │
  │         ├─ PASS → advance to next task
  │         └─ FAIL → retry (max 3) → escalate to orquestador
  │
  └─ All tasks done → Phase Gate → advance to Phase 4
```

### Phase 4 — Certification

```
Orquestador → spawn (parallel):
  ├─ seo-discovery      → meta tags, JSON-LD, sitemap, llms.txt
  ├─ api-tester         → endpoint coverage, OWASP API Top 10, P95 latency
  ├─ performance-benchmarker → Core Web Vitals, Lighthouse, bundle size
  └─ reality-checker (Opus)   → final visual gate
       │
       ├─ All PASS → advance to Phase 5
       └─ Any FAIL → reality-checker returns NEEDS WORK
            → orquestador returns to Phase 3 for affected tasks only
```

### Phase 5 — Deployment

```
Orquestador: "¿Confirmas git push y deploy?"
User: "sí"

Orquestador → spawn git
  ├─ git add -A
  ├─ git commit -m "..."
  ├─ git push
  └─ Return Envelope: STATUS: completado

Orquestador → spawn deployer
  ├─ vercel --prod
  ├─ Monitors deploy status
  └─ Return Envelope: STATUS: completado | URL: https://...
```

---

## Flow 2: Resume Session

```
User: "retomar tareas-saas"
```

```
Orquestador
  ├─ mem_context(scope="personal")
  ├─ mem_search("tareas-saas/boot-state")
  │    → FOUND (observation_id=abc123)
  ├─ mem_get_observation("abc123")
  │    → { phase: 3, current_task: 5, total_tasks: 12 }
  │
  └─ LIGHT boot: "Retomando fase 3, tarea 5/12"
       → continue Phase 3 loop from task 5
```

---

## Flow 3: Capability Resolution

```
evidence-collector needs a browser
```

```python
resolution = resolve_capability("browser", requested_by="evidence-collector")
```

```
capability router
  │
  ├─ registry: browser has 3 providers
  │    playwright        (LIVE)
  │    claude_in_chrome  (LIVE)
  │    claude_preview    (LIVE)
  │
  ├─ select highest-rank LIVE provider → playwright
  │
  ├─ events.py: emit to .pipeline/capability-events.jsonl
  │    { timestamp, capability: "browser", provider: "playwright", status: "LIVE" }
  │
  └─ Resolution(provider="playwright", status="LIVE",
                action="USE_LIVE", fallback=Resolution("claude_in_chrome"...))

evidence-collector uses mcp__playwright__browser_navigate
```

If playwright is not registered:
```
router falls back to claude_in_chrome
→ Resolution(provider="claude_in_chrome", status="LIVE",
             action="USE_LIVE", fallback=Resolution("claude_preview"...))
```

---

## Flow 4: Hook Interception

```
User asks Claude to run: git push --force
```

```
Claude invokes Bash tool
  │
  └─ PreToolUse: block-no-verify.js fires
       input: { tool_name: "Bash", tool_input: { command: "git push --force" } }
       
       regex match: /git\s+push\s+.*--force/ → true
       
       process.exit(2)  ← BLOCK signal
       
Claude receives: tool blocked by hook
Claude responds: "This command is blocked by security policy. Use git push without --force..."
```

Bypass gap also covered: `git -C /some/dir push --force` is caught by second regex.

---

## Flow 5: Policy Block

```
An agent tries to use "memory" but Engram is not running
```

```python
resolution, decision = resolve_with_policy("memory")
```

```
router: engram → UNAVAILABLE (not in .mcp.json or not responding)

policy evaluator:
  memory.block_if_unavailable = true
  resolution.status = UNAVAILABLE
  → _apply_policy: BLOCK

PolicyDecision(
  decision="BLOCK",
  recovery_hint="Revisar Engram MCP: engram doctor...",
  is_blocking=True,
  is_usable=False
)
```

Agent receives BLOCK, escalates to orchestrator:
```
Return Envelope:
  STATUS: fallido
  BLOQUEADORES: [memory BLOCK — Engram not available. Hint: engram doctor]
  NOTAS: cannot proceed without memory capability
```

Orchestrator surfaces to user: "Engram needs to be running. Run `engram doctor` to diagnose."

---

## Flow 6: Compaction Safety

```
Context window at 95% capacity
```

```
Claude Code fires PreCompact lifecycle event
  │
  └─ pre-compact-engram.js fires
       ├─ Saves snapshot to disk: ~/.claude/pre-compact-snapshot.json
       │    { tool_count, cwd, timestamp, pipeline_status }
       │
       └─ Emits to stderr: "COMPACTION IMMINENT — SAVE STATE NOW"

Claude sees the stderr message (before compaction)
Claude executes:
  ├─ mem_update(dag_state_id, full_dag_state_json)
  └─ Write(".pipeline/estado.yaml", dag_state_yaml)

Compaction happens — context truncated

Next user message triggers session-start-context.js:
  ├─ Reads ~/.claude/pre-compact-snapshot.json
  └─ Claude knows which project was active, resumes in light-boot mode
```
