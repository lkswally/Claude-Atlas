# F32 — Pipeline Knowledge Decomposition Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F31 `4b0973a`)
**Modo:** descomposición de conocimiento por responsabilidad. **Sin cambio de comportamiento, sin borrar conocimiento, sin tocar dispatcher/runtime/MCPs/CI.**

---

## Tokens antes / después (per-load)

| Archivo | Antes | Después | Reducción |
|---------|------:|--------:|-----------|
| `.claude/agents/orquestador.md` | ~28,665 | **~1,207** | **−96%** |
| `.claude/agents/agent-protocol.md` | ~27,106 | **~890** | **−97%** |

Ambas fachadas muy por debajo del objetivo (<10K) y del 60% pedido. **El win central de F32 es el costo por carga:** abrir el orquestador ahora cuesta ~1.2K (antes 28.7K); el detalle de cada fase/contrato se carga **solo cuando se necesita**.

---

## Nuevos refs lazy (contenido movido VERBATIM)

**orquestador.md → 6 refs** (`.claude/agents/refs/`):
| ref | contenido | líneas |
|-----|-----------|-------:|
| `orchestrator-routing.md` | Boot Sequence & routing | 202 |
| `orchestrator-memory-engram.md` | session lifecycle + Engram cajones | 168 |
| `orchestrator-modification.md` | modo modificación | 95 |
| `orchestrator-delegation.md` | runtime helpers wiring + handoff | 146 |
| `orchestrator-pipeline.md` | **pipeline 5 fases + 2B** | 1222 |
| `orchestrator-operations.md` | recovery/validación/formato/troubleshooting/enrollment/degradation | 145 |

**agent-protocol.md → 5 refs**:
| ref | contenido | líneas |
|-----|-----------|-------:|
| `protocol-memory-engram.md` | Engram read/strategy/MCP/write | 359 |
| `protocol-envelope-audit.md` | Return Envelope + pre-return audit + delegation stop | 450 |
| `protocol-agent-contracts.md` | contratos por agente (QA cache, design, hardening, evidence…) | 1162 |
| `protocol-core-universal.md` | reglas universales + anti-generic + límites + anti-loop | 304 |
| `protocol-capability.md` | capability router/metrics/policy (F16/F18/F19) | 189 |

Todos registrados en `config/knowledge.registry.yaml` (`load_policy: lazy`, con trigger). Espejados a `agents/refs/` para el dist.

---

## Fachadas compatibles (qué quedó inline)

- **orquestador.md:** frontmatter, identidad + **Regla de Oro (verbatim)**, cuándo usarlo, routing mínimo, mapa de 6 refs, reglas no negociables (QA gate, git/deployer, phase gates), `resolve_capability("browser")` para qa_mode, escape hatch, tools.
- **agent-protocol.md:** frontmatter, **contrato base inline** (Engram 2-pasos, Return Envelope, límites universales), mapa de 5 refs por responsabilidad, reglas críticas, escape hatch.

Ambas mantienen el **escape hatch**: "si te falta el detalle, leé la ref antes de actuar".

---

## Architecture Score antes / después

| | Antes (F31) | Después (F32) |
|---|---:|---:|
| Architecture Score | 62/100 | **62/100** |
| decompose_candidates | orquestador.md, agent-protocol.md | orchestrator-pipeline.md, protocol-agent-contracts.md |

**Por qué el score no sube:** el auditor mide **tamaño total**, y el conocimiento no se borró — se reorganizó. Los 2 god-files monolíticos (8/8 dominios cada uno) se convirtieron en **fachadas + refs single-purpose**; los 2 refs más grandes (`pipeline` ~18K, `agent-contracts` ~13K) son ahora los **candidatos de la siguiente capa** (F33: pipeline por fase, contratos por clase = la granularidad de `resolve_knowledge()`).

> El boot profiler fue extendido para escanear `refs/` — por honestidad, el contenido movido sigue siendo visible y medible (no "desapareció" del análisis).

**Métrica real de éxito de F32** (per-load, no total): orquestador −96%, agent-protocol −97%.

---

## God-files restantes / próxima capa

- `orchestrator-pipeline.md` (~18K, multi-fase) → F33: 1 ref por fase (FASE 1–5 + 2B).
- `protocol-agent-contracts.md` (~13K, multi-contrato) → F33: 1 ref por clase de agente (QA/design/dev).

Estos habilitan `resolve_knowledge(intent|class)` → cargar solo la fase/contrato necesario.

---

## Qué NO se tocó

- `tools/atlas_dispatcher.py` y todo el runtime Python (diff vacío).
- MCPs, CI, workflows, proyectos externos.
- Semántica de agentes: el contrato y las reglas siguen idénticas, solo reubicadas.
- Knowledge: cero borrado (extracción verbatim por rango).

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Agente/orquestador no carga un ref necesario | Mapa con triggers + escape hatch inline; reglas críticas y Regla de Oro quedan inline |
| Drift fachada ↔ dist | `sync_dist.py` + F10 (5/5 PASS); refs espejados a `agents/refs/` |
| Tests que validaban el estado viejo | Actualizados a la nueva intención (F16 T14, F17 T7/T11, F31 T7/T12) sin debilitar cobertura |
| Pérdida de markers de capability en la fachada | Reañadidos `resolve_capability`/`solicitar capability` inline (la fachada señala capability awareness) |

---

## Validación

| Check | Resultado |
|-------|-----------|
| orquestador.md / agent-protocol.md | facades −96% / −97%, existen ✓ |
| 11 ref links | resuelven ✓ |
| F10 drift | 5/5 PASS |
| F29 boot profiler | PASS |
| F31 architecture audit | PASS (tests actualizados) |
| F16 / F17 capability | PASS (markers inline) |
| Quick | 32/32 PASS |
| Release | 35/35 PASS |
| Healthcheck | HEALTHY (Knowledge registry 29 entradas) |
| secrets_check | exit 0 |
| dispatcher / runtime | diff vacío ✓ |

Próximo paso recomendado: **F33** — descomponer `orchestrator-pipeline.md` (por fase) y `protocol-agent-contracts.md` (por clase), y formalizar `resolve_knowledge()`.
