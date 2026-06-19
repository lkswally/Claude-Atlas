# ATLAS — Operational Capabilities Reference

> Moved from CLAUDE.md in F30 (boot slimming). Load this when you need the full
> operational detail: capability history, dispatcher enforcement, design-quality
> detector, hook system table, and per-agent tools. Behavior is unchanged.

## Capacidades operativas post-1K.2 (paridad ~92-97% con benchmark)

ATLAS pasó por 23 bloques de mejora consolidados en `main` el 2026-05-21. Capabilities reales operativas:

### Pipeline + Enforcement (serie 1A)
- **Phase Gates operativos** (1A.7) con anti-loop intra-sesión (1A.12)
- **Pre-Return Audit** (1A.14) con 6 reglas auto-ejecutables (debugger, breakpoint, .only/.skip, secrets, console.*, TODO/FIXME)
- **Audit Enforcement** (1A.15) — dispatcher re-ejecuta audit y rechaza envelopes que mienten
- **File Change Declaration** (1A.16) — `archivos` declarado debe ser superset real de `git diff`

### Engram MCP real (serie 1B)
- **Strategy Pattern** (1B.1) con `disk_fallback` honesto
- **MCP Real Connection** (1B.2) — JSON-RPC stdio inline, sin dependencia externa SDK
- **Auto-boot en dispatcher** (1B.5) — Engram MCP activa al construir el dispatcher
- **2-step pattern real** (1B.4) — `mem_search` + `mem_get_observation` para contenido completo
- **ambiguous_project handling** (1B.3) — detecta y propaga `unknown_project`/`ambiguous_project` con `available_projects` + `recovery_token`

### Skills + Design (serie 1C)
- **UI-UX Pro Max Skill Enforcement** (1C.1) — `mode="design_strict"` exige `design_intelligence.queried=true` en envelope

### Anti-Loop Coordination (serie 1D + 1I)
- **Delegation Stop Rules** (1D.1) — flags `escalation_needed` / `pause_recommended` / `fresh_review_recommended`
- **Anti-Loop INTER-Sesión** (1I.1) — append-only history detecta loops persistentes 3+ sesiones

### Certificación + QA Loop (serie 1E)
- **Reality-Checker Random Re-runs** (1E.1) — sampler reproducible con seed, detecta falsos PASS

### Performance + Tokens (serie 1F)
- **File Hash Caching para QA** (1F.1) — SHA256 + mtime + atomic write, ~70-80% token savings

### Runtime Wiring + Enforcement (serie 1G)
- **Documental** (1G.1) — runtime helpers wiring documentado en orquestador.md
- **Runtime Invocation Tracking** (1G.2) — 15 helpers instrumentados con `_record_invocation()`, audit via `audit_invocations()`

### Multi-Layer QA (serie 1H)
- **Network Inspection** (1H.1) — detecta 5xx, mixed content, redirects >3, 4xx en assets críticos
- **Console Log Analysis** (1H.2) — Uncaught, CORS, CSP, hydration mismatch, null access
- **Visual Fidelity Checker** (1H.3) — compara palette/typography/mood/anti-patterns con tolerancia RGB

### Visual Evidence Verification (serie 1J)
- **Design Intelligence Re-verification** (1J.1) — re-invoca skill independientemente, detecta industrias/styles inventados
- **Screenshot Hash Verification** (1J.2) — verifica archivo existente + SHA256 coincide, detecta evidencia fantasma y tampering

### Auto-Audit Hook (serie 1K)
- **QA Auto-Audit PostToolUse Hook** (1K.1) — al terminar subagent spawn, audita automáticamente helpers obligatorios y emite WARN si faltan

### Design Criterion Hardening (serie 1L)
- **Intent Classifier** (1L.1) — `classify_user_intent(prompt)` clasifica el pedido en 4 buckets (audit/redesign/implement/validate) con confidence high/medium/low. En `low` escala al usuario. Heurística pura ES+EN, sin LLM.
- **design_quality bloqueante en design_strict** (1L.2) — HIGH findings rechazan envelope con error accionable (file:line + suggestion). Whitelist anti-disguise por `brand.style`: solo fonts canónicas en {brutalism, editorial-raw, neo-grotesque} se degradan. Colors / layouts / opacity / radius **nunca** se whitelistan.
- **reference-driven-design obligatorio** (1L.3) — `brand.references` schema estricto (2-5 entries con `url`, `rationale`≥10 chars, `take[]` no-vacío). ui-designer DEBE citar `references_used` como subset estricto. NO se valida URL viva.
- **Refuerzo editorial obligatorio** (1L.4) — `editorial_compliance` con 5 sub-campos verificables: asymmetric_section, typography_mix (anti-monotypo: display≠body), references_cited (subset de references_used), boilerplate_avoided, whitespace_intentional. Rationales ≥20 chars (anti-teatro).
- **Cascada en design_strict**: 1C.1 → 1L.2 → 1L.3 → 1L.4 → 1K.3/1K.4 (si aplica). Backward compat estricto en otros modos.
- **Rollback por capas**: param `enforce_*=False`, env vars `ATLAS_*_DISABLED=1`, git revert por sub-bloque.

### Skills Registry + Hard Rules (serie F2)
- **Skills Registry MVP** (F2.1) — catálogo declarativo en `.claude/skills.registry.yaml` (10 skills iniciales: design / qa / branding / orchestration). API en `tools/skills_registry.py`: `find_skills(domain, agent, applies_when)`, `get_skill(id)`, `list_domains()`, `validate_registry()`. Disable: `ATLAS_SKILLS_REGISTRY_DISABLED=1`. Fail-open: registry missing / PyYAML missing → retorna `[]`.
- **Hard Rules MVP** (F2.1) — reglas declarativas en `.claude/hard-rules.json` (4 reglas iniciales: no-merge-pr25-without-pilots [block], no-force-push-main [block], warn-cross-repo-commit [warn], warn-skill-registry-unused [warn]). Hook PreToolUse `.claude/hooks/pipeline-rules.js`. Disable global: `ATLAS_HARD_RULES_DISABLED=1`. Bypass per-rule via env var documentada. Fail-open absoluto.
- **Registry usage logging + hints** (F2.1.b) — `find_skills`/`get_skill`/`list_domains` registran cada invocación en `.claude/logs/skills-registry-usage.jsonl` (gitignored, append-only). CLI `python tools/skills_registry.py stats [--since=N]` muestra invocaciones / top skills / top filters. Hint mínimo de 1 línea en `ux-architect.md` + `evidence-collector.md` apuntando al registry. Disable: `ATLAS_SKILLS_USAGE_LOG_DISABLED=1`. Fail-open total. Permite medir si F2.1 aporta valor real a 14/30 días.
- **Diferidos en F2.1** (no incluidos): Activation Contracts, Output Contracts por agente, Decision Gates con audit trail, Token Budgets — solo si surge caso concreto.
- **Criterio explícito de éxito o fracaso** documentado en `.claude/agents/agent-protocol.md` § 4.20.4.

### Contracts formales (serie F1)
- **Envelope.v1 Pydantic** (F1.1 reducido) — modelo formal versionado en `tools/contracts/` con coerción bidireccional transparente. `validate_return_envelope` acepta dict legacy O instancia `Envelope` indistintamente. Per-mode validations (qa_strict / dev_strict / design_strict / standard) intactas.
- **Backward compat estricto**: subagentes, hooks, tests existentes sin cambios. Mutaciones downstream (`_dispatcher_warnings`) preservadas vía referencia.
- **Fail-open + disable runtime**: `ATLAS_PYDANTIC_CONTRACTS_DISABLED=1` o `tools/contracts/` ausente → path dict puro sin error.
- **Diferidos** (F1.1.b/c/d futuros): `PhaseGate.v1`, `AuditTrail.v1`, `ClaimAudit.v1` — solo si surge caso concreto.

### Tests operativos
218+ tests en `_qa/` cubriendo todos los bloques. Regression sweep en main consolidado: **100% verde**.

### Helpers públicos del dispatcher (20)
`validate_return_envelope(mode)`, `verify_pre_return_audit`, `verify_declared_files`, `verify_design_intelligence`, `verify_design_intelligence_real`, `verify_screenshot_evidence`, `consult_design_intelligence`, `get_cajon_full`, `resolve_ambiguous_project`, `should_skip_qa`, `cache_qa_result`, `run_certification_re_runs`, `inspect_network_requests`, `analyze_console_messages`, `check_visual_fidelity`, `record_session_summary`, `check_cross_session_loops`, `audit_invocations`, `audit_helpers_for_agent`, `classify_user_intent` (1L.1), `verify_design_quality` (1L.2), `verify_references` (1L.3), `verify_editorial_compliance` (1L.4).

### Modos de validate_return_envelope
- `standard` — validación suave (creativos, utilidades)
- `qa_strict` — evidence-collector con PASS/FAIL exclusivos + archivos no-vacíos
- `dev_strict` — dev-agents con pre_return_audit + file declaration superset
- `design_strict` — ux-architect/ui-designer con design_intelligence + 1L.2 + 1L.3 + 1L.4 (cascada completa)

### Hooks operativos
13 hooks pre-existentes + 2 nuevos (1D.1 `delegation-tracker.js`, 1K.1 `qa-auto-audit.js`).

### Tag de rollback de consolidación
`pre-1K2-consolidation` (apunta a `c8f7b9c`, estado pre-merge). Permite revertir toda la cascada si surge regresión crítica.

## Dispatcher Operativo (Phase 0.6A+)

El `tools/atlas_dispatcher.py` es el **motor de enforcement** que transforma la arquitectura documentada en sistema operativo. Automatiza:

### 1. Validación de Return Envelope
Todo subagente DEBE devolver respuesta en formato estándar (fase 3+):
```
STATUS: completado | fallido | PASS | FAIL
TAREA: {descripción}
ARCHIVOS: [lista]
ENGRAM: {proyecto}/{cajon}
VERIFICACION: layout | typo | config | none
BLOQUEADORES: [lista opcional]
NOTAS: {texto}
```
El dispatcher **rechaza respuestas mal formateadas** y pide al subagente re-enviar.

### 2. Phase Gates (control de transiciones)
Antes de avanzar a la siguiente fase, el dispatcher verifica:
- ¿Existen todos los cajones requeridos en Engram/disco?
- ¿Tienen el STATUS esperado?
- ¿Se completaron todos los E2E flows?

Si falta algo → FASE BLOQUEADA. No continuar hasta resolver bloqueadores.

Comandos:
```bash
# Verificar si se puede transicionar
python tools/atlas_dispatcher.py check-phase fase_1 fase_2

# Retorna:
# {
#   "ok": true/false,
#   "bloqueadores": [lista de bloqueadores si ok=false]
# }
```

### 3. E2E Flows Obligatorios
Definidos en `config/phase_playbook.json` para cada fase. Ejemplos:
- **Fase 2**: ux-architect design review
- **Fase 3**: evidence-collector QA después de cada tarea
- **Fase 4**: seo-discovery + api-tester + performance-benchmarker + reality-checker

El dispatcher no deja avanzar si un E2E flow requerido falla.

### 4. Validación de Respuestas
Comandos:
```bash
# Validar que la respuesta de un agente sigue el formato
echo '{ "status": "completado", "tarea": "...", ... }' | python tools/atlas_dispatcher.py validate-envelope

# Retorna:
# { "ok": true/false, "errores": [...] }
```

## Design Quality Enforcement — Anti-Generic Detector (Phase 0.6A+)

El `tools/design_quality_enforcement.py` detecta outputs "genéricos" (colores corporativos, fonts aburridas, layouts predecibles) y asigna severidades **SIN BLOQUEO**:

### Severidad: HIGH → MEDIUM → LOW

- **HIGH**: Degrada posture a "NEEDS WORK" (colores genéricos #3B82F6, fonts Inter/Roboto, layouts boilerplate)
- **MEDIUM**: Warnings que se reportan (opacidades predecibles 0.8, border-radius Tailwind defaults 8px)
- **LOW**: Notas sobre mejoras (duraciones 300ms, nombres componentes genéricos Button/Card)

### Patrones Detectados

| Categoría | Ejemplos | Severidad |
|-----------|----------|-----------|
| **Fonts** | Inter, Roboto, Open Sans, Arial | HIGH |
| **Colors** | #3B82F6 (Tailwind), #EF4444 (corporativo) | HIGH |
| **Paletas** | Gradiente púrpura, grises neutros planos | HIGH |
| **Opacity** | 0.8 (hover), 0.5, 0.75 | MEDIUM |
| **Border-radius** | 8px (Tailwind), 4px (Bootstrap), 12px (Shadcn) | MEDIUM |
| **Durations** | 300ms, 500ms, 1s | LOW |
| **Layouts** | grid-cols-3, max-w-1200px, mx-auto, justify-center items-center | LOW |
| **Components** | Button, Card, Container, Box, Wrapper | LOW |

### Comandos

```bash
# Analizar archivo individual
python tools/design_quality_enforcement.py src/styles/button.css

# Analizar directorio completo
python tools/design_quality_enforcement.py src/ --json

# Salida JSON para integración
python tools/design_quality_enforcement.py src/ --json > design-report.json
```

### Reporte Ejemplo

```
Posture: NEEDS WORK (4 HIGH findings)
Total findings: 12
  HIGH: 4 (degrada posture)
  MEDIUM: 5 (warnings)
  LOW: 3 (notes)

[HIGH] SEVERITY (Posture degraded):
  - font: inter @ src/styles.css:5
    -> Usar fonts con personalidad: Syne, Clash Display, Fraunces, etc.
  - color: #3B82F6 @ src/button.css:14
    -> Paleta con dominante + acento sharp
```

**Nota**: Sin bloqueo duro — es informativo. Los agentes deben leer el reporte y mejorar, pero pueden enviar sin arreglarlo (aún).


## Hook System (13 hooks, auditados 2026-04-12 — 11/11 HEALTHY)

Hooks interceptan tool calls en tiempo real. Configurados en `~/.claude/settings.json`. Scripts en `~/.claude/hooks/`.

| Hook | Accion |
|------|--------|
| `block-no-verify` | **BLOQUEA** git --no-verify, rm -rf, git reset --hard, DROP TABLE, chmod 777, curl\|sh |
| `config-protection` | **BLOQUEA** secrets (.env, .pem, .key). **ADVIERTE** configs de linting |
| `quality-gate` | **ADVIERTE** debugger, .only(), @ts-ignore, secrets hardcodeados |
| `console-log-warning` | **ADVIERTE** console.log/warn/error en produccion (ignora tests) |
| `suggest-compact` | **ADVIERTE** cada ~50 tool calls (async) |
| `pre-compact-engram` | **GUARDA** snapshot a disco antes de compactar (v2.2) |
| `cost-tracker` | **REGISTRA** tool calls por categoria (async) |
| `session-summary` | **LOGUEA** actividad en JSONL (async) |
| `engram-sync` | **SINCRONIZA** Engram con GitHub al parar sesion (async, 60s) |
| `session-start-context` | **CARGA** contexto de sesion anterior al iniciar |
| `dual-write-sync` | **ESCRIBE** a .pipeline/{cajon}.md en paralelo a Engram (fallback si Engram timeout). Phase 0.6A+ |

**Comportamiento**: Exit 2 = BLOCK | Exit 0 + stderr = WARN | Fail-open (nunca rompe el flujo)

**Utilidades manuales**: `node ~/.claude/hooks/audit-system.js` (health check) | `cost-report.js` (uso de tools) | `learning-index.js` (discoveries)

## Herramientas por agente

| Agente | Tools principales |
|--------|-------------------|
| orquestador | Agent (spawn subagentes), Engram MCP |
| project-manager-senior | Read, Write, Engram MCP |
| ux-architect | Read, Write, Engram MCP |
| ui-designer | Read, Write, Engram MCP |
| security-engineer | Read, Write, Engram MCP |
| frontend-developer | Read, Write, Edit, Bash, Engram MCP |
| backend-architect | Read, Write, Edit, Bash, Engram MCP |
| rapid-prototyper | Read, Write, Edit, Bash, Engram MCP |
| mobile-developer | Read, Write, Edit, Bash, Engram MCP |
| game-designer | Read, Write, Engram MCP |
| xr-immersive-developer | Read, Write, Edit, Bash, Engram MCP |
| evidence-collector | Read, Bash, Playwright MCP, Engram MCP |
| reality-checker | Read, Bash, Glob, Grep, Playwright MCP, Engram MCP |
| seo-discovery | Read, Write, Edit, Bash, Engram MCP |
| api-tester | Read, Bash, Engram MCP |
| performance-benchmarker | Read, Bash, Playwright MCP, Engram MCP |
| brand-agent | Read, Write, Bash, Engram MCP |
| image-agent | Read, Write, Bash, Engram MCP |
| logo-agent | Read, Write, Bash, Engram MCP |
| video-agent | Read, Write, Bash, Engram MCP |
| git | Bash (git, gh), Engram MCP |
| deployer | Bash (vercel, eas), Engram MCP |
| codepen-explorer | Playwright MCP (browser_navigate, browser_evaluate, browser_snapshot, browser_click, browser_wait_for, browser_take_screenshot), Engram MCP |
| self-auditor | Read, Bash, Glob, Grep, Engram MCP |
| build-resolver | Read, Write, Edit, Bash, Grep, Glob, Engram MCP |

