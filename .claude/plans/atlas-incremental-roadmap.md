# ATLAS Incremental Improvement Roadmap
> Plan operativo para añadir mejoras al sistema sin romper nada. Basado en auditoría 2026-05-11.

---

## Estado Actual Verificado

✅ Core operativo:
- ATLAS.md: 4 modos, 5 fases, aprobaciones humanas, garantías
- intent-clarifier.md: Protocolo Paso 0 para briefs vagos
- 38 agentes sincronizados con benchmark (incluyendo T7 envelope strategy)
- 14 hooks operacionales (PreToolUse, PostToolUse, PreCompact, Stop, Notification)
- 4 MCPs: Engram, Playwright, Context7, Magic-21st (todos OK)
- Variables: GEMINI_API_KEY, HF_TOKEN, REPLICATE_API_TOKEN (todas configuradas)
- CLIs: vercel OK + autenticado, gh instalado (no autenticado)

❌ Falta crear:
- contracts/ — especificaciones formales de entrega por fase
- backlog/ — estructura de issues/backlog formal

---

## Categorías de Mejoras

### 1. Core Crítico (Sin estos, ATLAS no escala)
- **contracts/** — Formalizar outputs de cada fase
- **backlog/** — Sistema formal de tracking de issues

### 2. Gobernanza (Mejor gestión sin código nuevo)
- RTK reference — Añadir soporte para Redux Toolkit como opción en stack decisions
- claude-fallback-nvidia — Fallback a NVIDIA NIM para resilencia

### 3. UX/UI (Mejora de flujos creativos)
- ui-ux-pro-max-skill — Skill especializado para diseño avanzado
- Better 21st.dev integration — Optimizar búsqueda y caching de componentes

### 4. Eficiencia (Performance y validación)
- NVIDIA benchmark — Comparar Claude vs NVIDIA en quality/cost/latency

### 5. Opcionales (Nice-to-have, diferir si hay presión)
- HyperFrames — Skill para video avanzado (requiere Node ≥22, FFmpeg)
- Pixel Bridge — Bridge a Photoshop/Figma (deferred until on-demand)

---

## Roadmap por Fases

### Fase 0: Fundación (Semana 1-2) — 0 riesgo

| Mejora | Objetivo | Prioridad | Riesgo | Prerequisito | Validación |
|--------|----------|-----------|--------|--------------|------------|
| **contracts/** | Formalizar outputs de Fase 1→5 (aceptación, formato Engram, handoff) | P0 | Ninguno | Ninguno | Cada agente referencia contrato en handoff |
| **backlog/** | Estructura formal de issues indexada por proyecto/sprint | P0 | Ninguno | Ninguno | Importar ejemplos de evidence-collector y reality-checker |

**Razón:** Pura documentación. No toca código. Usa patrones ya presentes en agent-protocol.md.

---

### Fase 1: UX/UI (Semana 3-4) — Bajo riesgo, alto valor

| Mejora | Objetivo | Prioridad | Riesgo | Prerequisito | Validación |
|--------|----------|-----------|--------|--------------|------------|
| **ui-ux-pro-max-skill** | Workflow especializado para handoffs de diseño (tokens, specs, animaciones) | P1 | Bajo | contracts/ existe | Usado en Fase 2 (Designer → Dev) |
| **Better 21st.dev integration** | Estandarizar búsqueda de componentes, caching, reutilización | P1 | Medio | ui-ux-pro-max-skill | Frontend-developer usa cache; menos hallucinations |

**Razón:** Extienden agentes existentes. No quitan nada. 21st MCP ya integrada; solo optimizar pipeline.

**Pueden correr en paralelo:** Mismo conjunto de agentes (ui-designer, frontend-developer), sin conflictos.

---

### Fase 2: Modelos & Eficiencia (Semana 5-6) — Bajo-medio riesgo

| Mejora | Objetivo | Prioridad | Riesgo | Prerequisito | Validación |
|--------|----------|-----------|--------|--------------|------------|
| **RTK reference** | Añadir redux-toolkit-reference.md para proyectos que necesiten RTK | P1 | Ninguno | Ninguno | Backend-architect refiere en decisiones Fase 1 |
| **claude-fallback-nvidia** | Fallback a NVIDIA NIM en retry 3+ del orquestador | P2 | Medio | NVIDIA_API_KEY en env | Orchestrator intenta NIM; logs fallback usage |

**Razón:** RTK es referencia pura (0 riesgo). NVIDIA fallback añade lógica de retry pero aislada.

---

### Fase 3: Validación (Semana 7-8) — Medio riesgo

| Mejora | Objetivo | Prioridad | Riesgo | Prerequisito | Validación |
|--------|----------|-----------|--------|--------------|------------|
| **NVIDIA benchmark** | Test suite comparando Claude vs NVIDIA en code quality, security, latency, cost | P1 | Medio | claude-fallback-nvidia deployed | Performance-benchmarker incluye NIM en matrix |
| **HyperFrames skill** | Skill opcional para video avanzado (composite, frame-by-frame) | P2 | Alto | Node ≥22 + FFmpeg presentes | Video-agent delega si deps disponibles |

**Razón:** Benchmark valida fallback strategy. HyperFrames es opcional → gate condicional en video-agent.

---

### Fase 4: Deferred (Future)

| Mejora | Objetivo | Estado |
|--------|----------|--------|
| **Pixel Bridge** | Bridge a Photoshop/Figma live sync | Esperar señal de demanda del usuario |

---

## Orden Más Seguro (Minimizar breaking changes) — APROBADO

```
FASE 0 (Semana 1-2) — DOCS PURAS
1. contracts/              ← Pure docs, 0 risk
2. backlog/                ← Pure docs, 0 risk

FASE 1 (Semana 3-4) — UX/UI
3. ui-ux-pro-max-skill     ← Extend, don't remove, 1-2 días
4. Better 21st.dev         ← Optimize existing MCP, 1-2 días

FASE 2 (Semana 5-6) — GOBERNANZA + BENCHMARK
5. RTK reference           ← Reference-only agent, 0 risk (MOVIDO ANTES)
6. NVIDIA benchmark        ← New test matrix, 2-3 días (MOVIDO ANTES)

FASE 3 (Semana 7-8) — FALLBACK + OPCIONAL
7. claude-fallback-nvidia  ← New retry logic, test bien, 2-3 días (DESPUÉS BENCHMARK)
8. HyperFrames             ← Optional gate, 3-5 días (OPCIONAL)

FASE 4 (Deferred)
9. Pixel Bridge            ← Deferred, wait for on-demand
```

**Ajustes aplicados:**
- ✅ RTK reference antes de NVIDIA fallback (benchmark primero)
- ✅ NVIDIA benchmark antes de integrar fallback (validar antes de usar)
- ✅ HyperFrames opcional después
- ✅ Pixel Bridge deferred

**Rationale:** 
- Items 1-3: 0 riesgo, documentación pura. Parallelizables.
- Items 4-5: Extienden agentes. Parallelizables (mismo grupo de agentes).
- Item 6: Requiere testing exhaustivo. Hacer después de gobernanza.
- Item 7: Depende de item 6. Validar fallback antes de benchmarkear.
- Item 8: Opcional, último. Diferir si hay presión.

---

## Parallelization Safety

| Semana | Mejoras | Por qué seguro en paralelo |
|--------|---------|--------------------------|
| **1** | contracts/ + backlog/ | Ambas docs puras; uso de patrones existentes |
| **3** | ui-ux-pro-max + 21st integration | Mismo conjunto de agentes (UI-Designer, Frontend-Developer); sin conflictos |
| **5** | RTK ref + claude-fallback-nvidia | RTK es reference; NVIDIA es lógica aislada de retry |
| **7** | NVIDIA benchmark + HyperFrames | No interacción; benchmark tests existing code; HyperFrames es gate opcional |

---

## Criterios de Validación por Mejora

### contracts/
✅ Cada fase (1-5) tiene documento de salida con:
- Qué se entrega (artifacts, Engram entries, handoff format)
- Criterios de aceptación medibles
- Roles responsables (qué agente produce, quién aprueba)

### backlog/
✅ Estructura `~/.claude/backlog/`:
- `issues/` — Tickets open/closed
- `sprints/` — Asignación por sprint
- `index.md` — Cross-project pattern summary
✅ Engram queries pueden listar issues por proyecto

### ui-ux-pro-max-skill
✅ Skill disponible para invocar desde ui-designer
✅ Produce design tokens JSON + component spec markdown
✅ Frontend-developer puede consumir sin traducción manual

### Better 21st.dev integration
✅ Frontend-developer caching inspirations en `~/.claude/cache/21st-components.json`
✅ Búsqueda de componentes retorna cached results primero
✅ Reducción de API calls a 21st.dev (medir antes/después)

### RTK reference
✅ `~/.claude/agents/redux-toolkit-reference.md` existe
✅ Backend-architect y frontend-developer pueden referir en stack decisions

### claude-fallback-nvidia
✅ Orchestrator tiene retry logic: Claude (x2) → NVIDIA NIM (x1) → fail
✅ Log entries marcan fallback usage
✅ Fallback output es compatible con expected format

### NVIDIA benchmark
✅ performance-benchmarker.md tiene test matrix:
- Test case A: code quality (coverage, linting, security)
- Test case B: latency (token/s, end-to-end time)
- Test case C: cost ($ per 1M tokens)
✅ Report compara Claude vs NVIDIA head-to-head

### HyperFrames
✅ Detecta Node ≥22 + FFmpeg
✅ video-agent delega a HyperFrames si ambas presentes
✅ Falla gracefully si deps no presentes

---

## Archivos Clave a Tocar

| Archivo | Qué Cambiar | Mejoras Afectadas |
|---------|------------|-------------------|
| `~/.claude/agents/orquestador.md` | Añadir retry logic (Claude → NVIDIA) | claude-fallback-nvidia |
| `~/.claude/agents/agent-protocol.md` | Refinar Return Envelope para contracts/ | contracts/ |
| `~/.claude/agents/ui-designer.md` | Link a ui-ux-pro-max-skill | ui-ux-pro-max-skill |
| `~/.claude/agents/frontend-developer.md` | Caching 21st.dev inspirations | Better 21st.dev |
| `~/.claude/agents/performance-benchmarker.md` | Agregar NVIDIA test matrix | NVIDIA benchmark |
| `~/.claude/agents/video-agent.md` | Gate condicional para HyperFrames | HyperFrames |
| **Nueva:** `~/.claude/agents/redux-toolkit-reference.md` | RTK patterns, comparación vs Zustand | RTK reference |
| **Nueva:** `~/.claude/contracts/` | Phase specs (1-5) | contracts/ |
| **Nueva:** `~/.claude/backlog/` | Issues structure + index | backlog/ |

---

## Nota de Implementación

**Sin cambios todavía.** Este es el plan. Cuando apruebes:
1. Ejecutaré Fase 0 (contracts/ + backlog/) con changeset backup
2. Luego Fase 1, 2, 3 en orden
3. Cada fase requiere tu aprobación antes de pasar a la siguiente
4. Cada cambio deja backup en `~/.claude/backups/`
5. Engram persiste todas las decisiones por phase

Pronto: ¿Aprobás este roadmap? ¿Querés cambiar el orden o las categorías?
