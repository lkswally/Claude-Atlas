# ATLAS — Backlog

Trabajo planeado para ATLAS core, ordenado por fase del roadmap operativo.

**Ámbito**: solo ATLAS core (`D:\ProyectosIA\ProyectosClaude\`). Items de otros repos se marcan explícitamente con `repo: external/<nombre>`.

## Schema de cada item

```
ID:          identificador único (FASE.SUBID-slug)
título:      una línea, accionable
estado:      open | in_progress | pending_pilot | blocked | done
prioridad:   critical | high | medium | low
introducido: bloque/sesión/PR donde se identificó
resuelve_en: fase o bloque planeado para cerrarlo
repo:        ATLAS-core | external/<nombre>
tipo:        infra | docs | research | pilot | bug | deferred
notas:       contexto breve relevante
```

## Estados

- `open` — registrado, sin trabajo iniciado
- `in_progress` — alguien lo está ejecutando
- `pending_pilot` — código listo, esperando validación en proyecto real
- `blocked` — espera input externo (usuario, otro item, datos)
- `done` — cerrado, dejado para histórico

---

## Fase 0 — Bloqueadores actuales

### B0-1L-pilot-P1
- **título**: 1L Piloto P1 — landing nueva from scratch
- **estado**: pending_pilot
- **prioridad**: critical
- **introducido**: PR #25 (cierre 1L.4, 2026-05-29)
- **resuelve_en**: Fase 0 cierre
- **repo**: ATLAS-core
- **tipo**: pilot
- **notas**: Activa 4 sub-bloques en un run. Mide HIGH=0, ≤2 iteraciones ui-designer, juicio humano "se siente menos IA". Requiere proyecto real del usuario.

### B0-1L-pilot-P2
- **título**: 1L Piloto P2 — rediseño de landing existente
- **estado**: pending_pilot
- **prioridad**: high
- **introducido**: PR #25
- **resuelve_en**: Fase 0 cierre
- **repo**: ATLAS-core
- **tipo**: pilot
- **notas**: Valida intent classifier sobre prompt ambiguo. Mide confidence + tasa de escalación.

### B0-1L-pilot-P3
- **título**: 1L Piloto P3 — audit puro
- **estado**: pending_pilot
- **prioridad**: high
- **introducido**: PR #25
- **resuelve_en**: Fase 0 cierre
- **repo**: ATLAS-core
- **tipo**: pilot
- **notas**: Verifica que enforcers (1L.2/1L.3/1L.4) NO se activan en intent=audit. Backward compat check.

### B0-1L-merge
- **título**: Merge `feature/1L-design-criterion` → `main`
- **estado**: blocked
- **prioridad**: critical
- **introducido**: PR #25
- **resuelve_en**: Fase 0 cierre (post pilotos)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Bloqueado por C3-C7. Sin pilotos PASS no se mergea. Tag intermedio `v0.6.1-1L`.

### B0-v07-stable
- **título**: Tag `v0.7-stable`
- **estado**: blocked
- **prioridad**: medium
- **introducido**: PR #25
- **resuelve_en**: Fase 0 cierre + 2 semanas post-merge
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Requiere C8 (2 semanas sin regressions post-merge).

### B0-MKT-3F-commit
- **título**: MKT-3F commit (pipeline orchestrator)
- **estado**: blocked
- **prioridad**: high
- **introducido**: trabajo no commiteado en MARKETING-AGENCY-OS
- **resuelve_en**: fuera de scope ATLAS — repo separado
- **repo**: external/MARKETING-AGENCY-OS
- **tipo**: bug
- **notas**: 1 bug en `orchestrator.py:125` (strict_failure hardcoded). 30/31 tests PASS. Solo referenciado — NO se resuelve desde ATLAS.

---

## Fase 1 — Gobernanza

### F12-backlog-formal
- **título**: F1.2 — Backlog formal (este archivo + PENDING.md)
- **estado**: in_progress
- **prioridad**: high
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F1.2
- **repo**: ATLAS-core
- **tipo**: docs
- **notas**: Excepción aprobada para correr en paralelo con Fase 0. 100% docs, sin tocar código.

### F11-contracts-formales
- **título**: F1.1 — Contracts formales (envelope, phase-gate, audit trail, claim audit)
- **estado**: partially_done (Envelope.v1 reducido mergeado en PR #27)
- **prioridad**: medium (lo crítico ya está)
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F1.1.b/c/d futuros (PhaseGate / AuditTrail / ClaimAudit) solo si surge caso concreto
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: F1.1 reducido (Envelope.v1) mergeado a main vía PR #27. PhaseGate / AuditTrail / ClaimAudit diferidos a F1.1.b/c/d.

### F21-skills-registry-hard-rules
- **título**: F2.1 — Skills Registry + Hard Rules MVP
- **estado**: done (mergeado en PR #28, SHA 11705b4)
- **prioridad**: high
- **introducido**: análisis multiagente 2026-06-03
- **resuelve_en**: F2.1 (mergeado)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Catálogo declarativo + reglas pipeline-level. Sin tocar dispatcher ni subagentes. 43 tests verde. Disable runtime via env vars. Criterio de fracaso explícito (§ 4.20.4 de agent-protocol).

### F21b-registry-consumption-hints
- **título**: F2.1.b — Registry Consumption Hints (usage logging + hints + stats CLI)
- **estado**: in_progress (branch `feature/F2-1-b-registry-consumption-hints`)
- **prioridad**: medium
- **introducido**: 2026-06-05 (post-F2.1, mitigar riesgo de "registry decorativo")
- **resuelve_en**: F2.1.b (esta branch)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Append-only JSONL en `.claude/logs/` (gitignored) + CLI stats + hints 1 línea en 2 agentes. Hace medible el éxito/fracaso de F2.1. Fail-open total.

---

## Fase 2 — Eficiencia

### F31-rtk-install
- **título**: F3.1 — RTK (Rust Token Killer) install + hook PreToolUse
- **estado**: open
- **prioridad**: medium
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F3.1 (post F1.1)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Comprime Bash outputs 60-90%. Target sesiones 4-6h → 12h+. Riesgo: puede romper tool output si compresión agresiva. Fallback a raw output requerido.

---

## Fase 3 — Investigación pre-fallback

### F41-nvidia-benchmark
- **título**: F4.1 — Benchmark NVIDIA NIM vs Claude (Opus, Sonnet)
- **estado**: open
- **prioridad**: low-medium
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F4.1 (post F3.1)
- **repo**: ATLAS-core
- **tipo**: research
- **notas**: 3-4 proyectos reales con ambos modelos. Doc `.claude/NVIDIA-BENCHMARK.md`. Métricas: code quality, latency, cost ($/1M tok), context handoff viability.

---

## Fase 4 — Fallback

### F51-fallback-nvidia
- **título**: F5.1 — claude-fallback-nvidia (retry logic + context handoff)
- **estado**: blocked
- **prioridad**: low-medium
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F5.1 (solo si F4.1 da verdict positivo)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Bloqueado por F4.1. Riesgo crítico: context handoff Claude→NVIDIA sin pérdida. Diseño previo obligatorio en `.claude/FALLBACK-CONTEXT-HANDOFF.md`. Opt-in via `ATLAS_FALLBACK_NVIDIA_ENABLED=1`.

---

## Fase 5 — n8n

### n8n-evaluation
- **título**: Evaluación de `n8n-mcp` / `n8n-skills` como capa de ejecución opt-in
- **estado**: blocked
- **prioridad**: low
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: post-F5.1 con fallback estable
- **repo**: ATLAS-core
- **tipo**: research
- **notas**: NO entra al core. Solo capa externa opt-in. Evaluar mantenimiento, permisos granulares, fail-open. Si pasa evaluación, abrir bloque específico.

---

## Fase 6 — UX/UI continuación

### F21-skill-better-use
- **título**: F2.1 — Mejor uso de `ui-ux-pro-max-skill` por dimensión
- **estado**: blocked
- **prioridad**: medium-high
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F2.1 (post Fase 0 cierre + 1L validado)
- **repo**: ATLAS-core
- **tipo**: docs
- **notas**: Bloqueado por pilotos 1L. Datos de pilotos dicen dónde el skill se sub-utiliza. Cambios sólo en `.md` de `ux-architect` y `ui-designer` + 1 helper validación.

### F22-21st-dev-curado
- **título**: F2.2 — 21st.dev Magic MCP integración curada
- **estado**: blocked
- **prioridad**: medium
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: F2.2 (post F2.1)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Activación opt-in para styles con personalidad (brutalism, editorial). Componentes generados deben pasar 1L.2 + 1L.4 sin whitelisting. Requiere API key 21st.dev.

---

## Fase 7 — Opcionales

### F61-hyperframes
- **título**: F6.1 — HyperFrames (scope a definir)
- **estado**: open
- **prioridad**: low
- **introducido**: roadmap operativo 2026-05-30
- **resuelve_en**: TBD
- **repo**: ATLAS-core
- **tipo**: deferred
- **notas**: Scope no definido en roadmap. Requiere aclaración del usuario antes de fasear.

### F62-pixel-bridge
- **título**: F6.2 — Pixel Bridge (Figma → CSS tokens)
- **estado**: open
- **prioridad**: low
- **introducido**: subdir `pixel-bridge/` preexistente en repo
- **resuelve_en**: on-demand
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Opt-in pasivo. Activar solo si surge proyecto que requiera input de Figma. Probable design-token-bridge wrapper.

---

## Items diferidos a futuros bloques

### Bloque 1M (post-pilotos 1L)

#### M-firecrawl-references
- **título**: Reference extraction con Firecrawl MCP
- **estado**: open
- **prioridad**: medium-high
- **introducido**: evaluación MCPs externos 2026-05-29
- **resuelve_en**: Bloque 1M (post-pilotos 1L)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Único MCP externo con valor estructural verificado. Convierte `brand.references` declaradas a specs extraídos reales (palette/typo/layout). Disparador: si pilotos 1L muestran que brand-agent sigue componiendo desde memoria pese a tener URLs declaradas. Free tier 500 páginas/mes suficiente.

#### M-copy-hardening
- **título**: Copy quality hardening (anti AI-tell)
- **estado**: open
- **prioridad**: medium
- **introducido**: diagnóstico 1L (causa A.4, peso ~10%)
- **resuelve_en**: Bloque 1M (post-pilotos 1L)
- **repo**: ATLAS-core
- **tipo**: infra
- **notas**: Diferido explícitamente de 1L scope. Detectar "empower/streamline/unlock/seamless" + estructuras paralelas en copy generado.

---

## MCPs evaluados (cerrado 2026-05-29)

### MCP-perplexity (postergado)
- **estado**: deferred
- **prioridad**: low
- **resuelve_en**: re-evaluar si research es cuello de botella post-1L
- **notas**: WebSearch + WebFetch cubren 80% del valor. Postergado.

### MCP-playwright (integrado)
- **estado**: done
- **notas**: Ya integrado vía `mcp__playwright__*`. No requiere acción.

### MCP-chrome-devtools (postergado)
- **estado**: deferred
- **prioridad**: low
- **notas**: Solapamiento con Playwright + `Claude_in_Chrome` ya disponible. Re-evaluar si surge necesidad de Lighthouse traces.

### MCP-glif (descartado)
- **estado**: done (descartado)
- **notas**: Redundante con `image-agent` (Gemini + HF FLUX). No aporta.

### MCP-21st-magic
- **estado**: deferred
- **prioridad**: medium
- **resuelve_en**: F2.2
- **notas**: Ver `F22-21st-dev-curado` arriba.
