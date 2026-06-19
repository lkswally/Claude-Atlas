# Orchestrator — Pipeline (Índice)

> **F33 — second-layer decomposition.** Este archivo es ahora un **índice** del
> pipeline. El detalle de cada fase se movió **verbatim** a
> `orchestrator-pipeline-phase-*.md`. Comportamiento sin cambios.
> **Escape hatch: cargá la ref de la fase activa ANTES de ejecutarla.**

## Pipeline: 5 Fases + Fase 2B (resumen)

```
Fase 1  Planificación   → project-manager-senior (Intent Clarifier, stack)
Fase 2  Arquitectura    → ux-architect → ui-designer + security-engineer
Fase 2B Assets visuales → brand-agent → logo + image + video (opcional)
Fase 3  Dev ↔ QA Loop  → dev-agents ↔ evidence-collector (3 reintentos)
Fase 4  Certificación   → seo + api-tester + performance + reality-checker
Fase 5  Publicación     → git (confirmación) → deployer (confirmación)
```

## Phase Gates (qué debe existir antes de cada fase) — INLINE crítico
- **Fase 1 requiere**: `{proyecto}/intent` en Engram (Intent Clarifier).
- **Fase 2 requiere**: `{proyecto}/tareas` + `{proyecto}/intent`.
- **Fase 2B requiere**: `{proyecto}/css-foundation`, `design-system`, `security-spec`, `visual-direction`.
- **Fase 3 requiere**: cajones de Fase 2 + brand aprobado (si aplica).
- **Fase 4 requiere**: TODAS las `tarea-{N}` con STATUS PASS en `qa-{N}`.
- **Fase 5 requiere**: `{proyecto}/certificacion` con STATUS CERTIFIED.

Verificar un gate: `mem_search("{proyecto}/{cajon}")` → si no hay observation_id → **FASE BLOQUEADA**. Si hay → validar STATUS via `mem_get_observation`.

## Mapa de fases (cargar la ref de la fase activa)

| Fase | Ref |
|------|-----|
| FASE 1 — Planificación (Request Routing, Intent Clarifier, stack) | `orchestrator-pipeline-phase-1.md` |
| FASE 2 — Arquitectura (orden secuencial crítico) | `orchestrator-pipeline-phase-2.md` |
| FASE 2B — Assets Visuales (+ manejo de errores creativos) | `orchestrator-pipeline-phase-2b.md` |
| FASE 3 — Dev ↔ QA Loop (timeouts, recovery, CodePen, build-resolver) | `orchestrator-pipeline-phase-3.md` |
| FASE 4 — SEO + Certificación (tiers) | `orchestrator-pipeline-phase-4.md` |
| FASE 5 — Publicación (git + deployer, con confirmación) | `orchestrator-pipeline-phase-5.md` |

## Reglas críticas inline (no negociables)
- No avanzar de fase sin su Phase Gate satisfecho (cajones + STATUS).
- Fase 3: cada `tarea-{N}` pasa por evidence-collector (máx 3 reintentos); **NO** git hasta PASS.
- Fase 5: git y deployer solo con confirmación del usuario (o autorización implícita).

## Escape hatch
Si vas a ejecutar una fase y no tenés su detalle en contexto, **leé primero
`orchestrator-pipeline-phase-N.md`**. No improvises la fase desde memoria.
