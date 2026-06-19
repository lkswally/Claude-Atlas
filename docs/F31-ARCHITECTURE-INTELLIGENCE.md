# F31 — Architecture Intelligence

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F30 `a1f5ebd`)
**Modo:** **análisis only.** No modifica CLAUDE.md, dispatcher ni agentes. Solo evidencia objetiva para decidir refactors futuros.
**Herramienta:** `python tools/architecture_audit.py` · config: `config/architecture.registry.yaml`

---

## Architecture Score: **62 / 100**

Penalización total 38. ATLAS está **estable y sin riesgos críticos de boot**; la deuda está **concentrada en pocos archivos** (no dispersa). El score no es bajo por fragilidad — es bajo por dos god-files conocidos.

| Penalización | Puntos | Origen |
|--------------|-------:|--------|
| decompose_candidate | 12 | 2 god-files (orquestador, agent-protocol) |
| oversized_file | 12 | 2 archivos > 12K tokens |
| duplication_candidate | 9 | 9 keywords doctrinales muy esparcidos |
| large_file | 5 | 5 agent-docs entre 6K–12K tokens |
| **boot_dependency_risk** | **0** | **sin enlaces always-on rotos ✓** |
| always_on_over_budget | 0 | 1.698t < 2.500t (post-F30) ✓ |

---

## Qué detecta (preguntas respondidas automáticamente)

| Pregunta | Detector | Hallazgo |
|----------|----------|----------|
| ¿Qué documentos crecieron demasiado? | oversized / large | 2 oversized + 5 large |
| ¿Qué conocimiento está duplicado? | duplicated_knowledge | 9 candidatos (Engram, MCP, QA…) |
| ¿Qué reglas aparecen en varios archivos? | rules_in_many_files | 4 (regla de oro, hard rules, release, QA) |
| ¿Qué responsabilidades están mezcladas? | mixed_responsibilities | 27 (informativo); 2 críticos |
| ¿Qué archivos deberían descomponerse? | decompose_candidates | **orquestador.md, agent-protocol.md** |
| ¿Qué referencias nunca se usan? | unused_references | 0 (sano post-F30) |
| ¿Qué conocimiento siempre se carga? | always_on | CLAUDE.md (1.698t) |
| ¿Qué conocimiento jamás se carga? | never_loaded | 19 docs/config no en knowledge registry |
| ¿Qué dependencias podrían romper el boot? | boot_dependency_risks | **0 ✓** |
| ¿Qué documentación quedó obsoleta? | obsolete_docs | 0 |
| ¿Qué archivos tienen alta entropía? | hotspots | ranking abajo |

---

## Ranking de deuda técnica (decompose candidates)

| tokens | dominios | archivo | acción futura |
|-------:|---------:|---------|---------------|
| 28,665 | 8/8 | `.claude/agents/orquestador.md` | split core + 1 ref por fase (F32) |
| 27,106 | 8/8 | `.claude/agents/agent-protocol.md` | split core + contratos por clase (F32) |

Ambos tocan **los 8 dominios** (boot, build, capability, memory, pipeline, qa, release, security) — separación de concerns nula. Son los mismos candidatos que F28/F29 anticiparon; ahora cuantificados.

## Hotspots por entropía arquitectónica

| entropy | tokens | archivo |
|--------:|-------:|---------|
| 6.00 | 28,665 | `orquestador.md` |
| 6.00 | 27,106 | `agent-protocol.md` |
| 4.95 | 11,444 | `frontend-developer.md` |
| 4.43 | 11,144 | `evidence-collector.md` |
| 4.33 | 3,906 | `docs/F28-BOOT-ARCHITECTURE-AUDIT.md` |

## Duplicación doctrinal (spread por keyword)

| keyword | archivos |
|---------|---------:|
| Engram | 83 |
| MCP | 81 |
| QA | 61 |
| pipeline | 50 |
| capability | 40 |

Engram/MCP/QA/capability son **vocabulario inherente** (aparecen en casi todo) — duplicación blanda. La señal accionable es la doctrina concentrada (`regla de oro`, `hard rules`) que F30 ya empezó a consolidar; el resto es ruido esperable.

> Nota: el conteo de duplicación incluye el espejo `agents/` (dist), por eso los números son ~2×. Los detectores por-archivo sí deduplican el espejo (70 archivos efectivos).

---

## Recomendaciones priorizadas

- **P0 — ninguna.** Sin riesgos de boot ni budget excedido. El sistema es seguro.
- **P1 — decomposition:** descomponer `orquestador.md` y `agent-protocol.md` (core + refs por fase/clase). Es el **único** ítem de alto valor; ya planificado como **F32**. Requiere la red F24 + boot profiler como respaldo.
- **P1 — duplication:** consolidar doctrina restante (regla de oro, hard rules) en fuente única (parcialmente hecho en F30 con Engram).
- **P2 — size:** revisar los 5 agent-docs `large` (frontend-developer, evidence-collector, reality-checker, ui-designer, brand-agent) para posibles refs lazy — bajo valor, opcional.
- **P3 — cleanup:** registrar en knowledge registry o archivar los 19 docs `never_loaded` (informes históricos, docs sueltos) — higiene, no urgente.

---

## Riesgos

| Riesgo | Severidad |
|--------|-----------|
| god-files (orquestador/agent-protocol) acumulan más responsabilidades con cada bloc | Media — mitigado: son lazy, no always-on |
| Heurística `bytes/4` y keyword-matching son aproximados | Baja — sirve para ranking relativo, no para gates |
| Score puede variar al agregar docs | Baja — es observabilidad, no un gate de release |

---

## Conclusión

ATLAS no tiene deuda arquitectónica dispersa ni fragilidad de boot: **Score 62/100 con cero P0**. Toda la deuda accionable se reduce a **2 archivos** (orquestador.md, agent-protocol.md), que el roadmap ya tiene como **F32 — Pipeline Knowledge Decomposition**. F31 entrega el instrumento (`architecture_audit.py`) para medir el progreso de ese refactor objetivamente, corrida a corrida.

**F31 no modificó runtime.** Próximo paso recomendado: F32 (decomposición de los 2 god-files), usando este Architecture Score como métrica de éxito (objetivo: subir el score reduciendo decompose_candidates).
