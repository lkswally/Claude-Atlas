# F29 — Boot Profiler Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F28)
**Fuente de datos:** `python tools/boot_profiler.py --scan` (heurística `bytes / 4` tokens)
**Modo:** instrumentación + medición. **Sin refactor de CLAUDE.md/orquestador/agent-protocol/dispatcher.**

> Nota metodológica: el scan incluye tanto `.claude/agents/` (runtime) como el espejo `agents/` (dist), por eso `total_files=100`. Los conteos de archivos en duplicaciones cuentan ambos espejos; el ranking de abajo está deduplicado por nombre de archivo.

---

## 1. Totales del scan

| Métrica | Valor |
|---------|-------|
| Archivos escaneados | 100 (incluye espejo dist) |
| Tokens estimados totales | ~424,252 |
| **always_on (CLAUDE.md)** | **8,728** |
| lazy | 76 archivos / ~365,164 tokens |
| manual | 23 archivos / ~50,360 tokens |

**Lectura:** el **único costo always-on es CLAUDE.md (~8.7K tokens)**. Todo lo demás es lazy (orquestador, agentes, refs) o manual (registries, docs). Esto confirma cuantitativamente la tesis de F28.

---

## 2. Top 20 archivos por tokens estimados (deduplicado)

| tokens | líneas | load_policy | category | path |
|-------:|------:|-------------|----------|------|
| 28,665 | 1988 | lazy | orchestrator | `.claude/agents/orquestador.md` |
| 27,106 | 2451 | lazy | agent-protocol | `.claude/agents/agent-protocol.md` |
| 11,444 | 791 | lazy | agent | `frontend-developer.md` |
| 11,144 | 871 | lazy | agent | `evidence-collector.md` |
| **8,728** | **544** | **always_on** | **system** | **`CLAUDE.md`** |
| 8,392 | 675 | lazy | agent | `reality-checker.md` |
| 8,169 | 572 | lazy | agent | `ui-designer.md` |
| 6,165 | 472 | lazy | agent | `brand-agent.md` |
| 5,447 | 514 | lazy | agent-ref | `nothing-design-reference.md` |
| 5,440 | 440 | lazy | agent | `ux-architect.md` |
| 5,357 | 389 | manual | doc | `docs/F24-COMPLEXITY-AUDIT.md` |
| 5,129 | 584 | manual | registry | `config/mcp.registry.yaml` |
| 4,827 | 311 | lazy | agent-ref | `pipeline-reference.md` |
| 4,753 | 352 | lazy | agent | `seo-discovery.md` |
| 4,524 | 626 | manual | registry | `config/test.registry.yaml` |
| 4,025 | 394 | lazy | agent | `backend-architect.md` |
| 3,906 | 262 | manual | doc | `docs/F28-BOOT-ARCHITECTURE-AUDIT.md` |
| 3,895 | 436 | lazy | agent | `codepen-explorer.md` |
| 3,652 | 317 | manual | doc | `docs/game-dev-improvements.md` |
| 3,564 | 191 | manual | doc | `docs/F26-VIBECODING-PATTERN-AUDIT.md` |

---

## 3. Clasificación always_on / lazy / manual

- **always_on (1 archivo, 8.7K):** `CLAUDE.md`. Pagado en el 100% de las sesiones, incluso triviales.
- **lazy (76 archivos, 365K):** orquestador, agent-protocol, los 25 agentes y sus refs. Solo se pagan al activar modo orquestador o spawnear el agente correspondiente.
- **manual (23 archivos, 50K):** registries y docs. Los consume el tooling/CI, **no** entran al contexto de Claude por defecto.

**Qué entra siempre:** únicamente `CLAUDE.md`. Ese es el blanco de optimización de mayor ROI.

---

## 4. Qué debería salir de CLAUDE.md en F30

`CLAUDE.md` (544 líneas) es ~88% material de referencia/condicional que no se necesita en cada boot. Candidatos a moverse a refs lazy (medición F28 §1):

| Sección | Líneas aprox. | Destino propuesto |
|---------|--------------|-------------------|
| Capacidades operativas post-1K.2 (changelog histórico) | 85 | `claude-capabilities-reference.md` |
| Overrides Windows | 61 | `windows-overrides-reference.md` |
| Dispatcher Operativo | 55 | `dispatcher-reference.md` |
| Design Quality Enforcement | 54 | `design-quality-reference.md` |
| Stack adaptable | 34 | `stack-reference.md` |
| Herramientas por agente | 30 | resolver desde mcp.registry/frontmatter |
| Best Practices Cross-Cutting | 26 | `best-practices-reference.md` |
| Nothing / Better Auth / Creativos | ~58 | refs lazy ya existentes |

**Boot-esencial que se queda inline (~63 líneas):** Dos modos, Arquitectura (1 diagrama), Regla de oro, Reglas clave, e **índice** con triggers a las refs.

**Proyección:** CLAUDE.md always-on de ~8.7K → ~1.5K tokens (**≈80%**), sin borrar nada (todo se reubica a refs cargadas por trigger).

---

## 5. Duplicaciones doctrinales detectadas (F29.4 — solo detección)

| Keyword | Archivos | Ocurrencias | Candidato |
|---------|---------:|------------:|-----------|
| Engram | 75 | 1005 | ✔ |
| MCP | 74 | 561 | ✔ |
| QA | 55 | 846 | ✔ |
| pipeline | 44 | 243 | ✔ |
| capability | 33 | 276 | ✔ |
| registry | 28 | 201 | ✔ |
| release | 14 | 182 | ✔ |
| regla de oro | 8 | 13 | ✔ |
| hard rules | 8 | 18 | ✔ |

**Hallazgo crítico:** el **protocolo Engram** aparece en CLAUDE.md, orquestador.md y agent-protocol.md (triplicado, confirmado en F28 §3). "regla de oro" en 8 archivos. Estas son las duplicaciones de mayor valor para consolidar en un único `engram-protocol-reference.md` durante F30.

> No se eliminó ninguna duplicación (regla F29). Solo detección.

---

## 6. Riesgos

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Mover refs y que Claude no las cargue cuando hace falta | Media | Índice con triggers explícitos (patrón ya probado con 12 refs); mantener boot-esencial inline |
| Drift entre CLAUDE.md índice y refs | Baja | Test F10 (sot-drift) + check WARN-only de Knowledge Registry ya añadido |
| Romper espejo `.claude/agents/` ↔ `agents/` | Baja | `sync_dist.py` + F10 lo vigilan |
| `estimated_tokens` es heurístico (bytes/4) | Baja | Suficiente para ranking relativo; no se usa para gates |
| Knowledge Registry queda desactualizado | Baja | Check WARN-only avisa; refrescar con `--scan` |

**Riesgo de no actuar:** el costo always-on de CLAUDE.md crece monótonamente con cada bloc nuevo (la sección "Capacidades" ya es la más grande).

---

## 7. Recomendación objetiva

La evidencia confirma F28 con números: **el 100% del costo always-on es CLAUDE.md (~8.7K tokens), del cual ~88% es referencia reubicable.** Los monolitos grandes (orquestador 28.7K, agent-protocol 27.1K) ya son lazy — su optimización es valiosa pero secundaria y más riesgosa.

**Recomendación:** proceder con **F30 = CLAUDE.md boot loader + índice** como el mínimo cambio de mayor impacto. Es reubicación de markdown (no lógica), reversible, con la red F24 + el Knowledge Registry como respaldo de verificación.

---

## 8. Propuesta F30 (basada en evidencia)

**F30 — CLAUDE.md → boot loader delgado**
1. Crear las refs lazy listadas en §4 (mover secciones tal cual, sin reescribir).
2. Dejar en CLAUDE.md: modos, regla de oro, reglas clave, 1 diagrama de arquitectura, e **índice** con triggers (`cargá X cuando Y`).
3. Consolidar el protocolo Engram (triplicado) en `engram-protocol-reference.md`, referenciado desde los 3.
4. Registrar cada ref nueva en `config/knowledge.registry.yaml` con su `load_policy` y `trigger`.
5. Validar: `boot_profiler --scan` debe mostrar always_on ≈ 1.5K; healthcheck Knowledge Registry PASS; F10 drift verde; quick/release 0 FAIL.
6. **Criterio de éxito:** ~80% de reducción del always-on **sin** pérdida de capacidad (cada sección sigue existiendo, cargada por trigger).

**Diferido a F31:** decomposición de orquestador.md (core + 1 ref por fase) y agent-protocol.md (core + contratos por clase); evolución del Capability Router a Knowledge Resolver. Mayor ahorro absoluto, mayor riesgo — después de F30.
