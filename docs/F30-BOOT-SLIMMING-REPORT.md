# F30 — CLAUDE.md Boot Loader Slimming Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F29 `adda170`)
**Modo:** reorganización de documentación always-on → referencias lazy. **Sin cambio de comportamiento, sin borrar conocimiento, sin tocar dispatcher/orquestador/agent-protocol/MCPs/CI.**

---

## Resultado (antes / después)

| Métrica | Antes | Después | Δ |
|---------|------:|--------:|---|
| **CLAUDE.md tokens (always-on)** | ~8,728 | **~1,698** | **−81%** |
| CLAUDE.md líneas | 544 | 115 | −79% |
| CLAUDE.md bytes | 34,913 | 6,793 | −81% |
| always_on files (boot profiler) | 1 | 1 | = |

**Objetivo (2,000–2,500 tokens): superado** — quedó en ~1,698, por debajo del rango.

Verificado con `python tools/boot_profiler.py --scan`: `always_on_tokens: 1698`.

---

## Qué quedó inline en CLAUDE.md (boot-essential)

- Identidad breve de ATLAS + estado (v1.0.0-rc2).
- Dos modos de trabajo (cómo activarlos).
- Principios no negociables (regla de oro, memoria, fail-open, QA antes de push).
- Pipeline de 5 fases (vista) + model routing (esencia).
- **Reglas clave (gobernanza) — VERBATIM, sin cambios.**
- Seguridad esencial (resumen de hooks que BLOQUEAN).
- Engram esencia (2-pasos + topic_key + dual-write) + pointer.
- Protocolo de subagentes (pointer a agent-protocol.md).
- **Mapa de referencias** (índice con triggers).
- Comandos mínimos (healthcheck, quick, release, secrets_check).
- Escape hatch.

---

## Qué se movió y a dónde

| Sección original | Tokens aprox. | Destino (lazy) |
|------------------|--------------:|----------------|
| Capacidades operativas post-1K.2 | ~1,700 | `docs/atlas-operational-capabilities.md` |
| Dispatcher Operativo (detalle) | ~1,100 | `docs/atlas-operational-capabilities.md` |
| Design Quality Enforcement | ~1,100 | `docs/atlas-operational-capabilities.md` |
| Hook System (tabla completa) | ~450 | `docs/atlas-operational-capabilities.md` |
| Herramientas por agente | ~600 | `docs/atlas-operational-capabilities.md` |
| Gestión de contexto / **Engram protocol** | ~720 | `docs/atlas-engram-reference.md` |
| Stack adaptable | ~700 | `docs/atlas-build-reference.md` |
| Nothing Design System | ~480 | `docs/atlas-build-reference.md` |
| Better Auth | ~280 | `docs/atlas-build-reference.md` |
| Agentes creativos | ~400 | `docs/atlas-build-reference.md` |
| Best Practices Cross-Cutting | ~520 | `docs/atlas-build-reference.md` |
| Overrides Windows | ~1,200 | `docs/atlas-build-reference.md` (+ 1-línea crítica inline) |

**Docs nuevos (5):** `atlas-boot-reference.md` (autoral), `atlas-operational-capabilities.md`, `atlas-engram-reference.md`, `atlas-release-reference.md` (autoral), `atlas-build-reference.md`. Todos registrados en `config/knowledge.registry.yaml` con `load_policy: lazy` y trigger.

**Cero pérdida de conocimiento:** las secciones operativas/condicionales se movieron **verbatim** (extracción por rango). Las dos referencias autorales (boot, release) consolidan info ya existente (F24/F25/F27 + política de gates).

---

## Reducción de duplicación

El protocolo Engram estaba triplicado (CLAUDE.md + orquestador.md + agent-protocol.md, F29 §5). F30 lo consolidó: CLAUDE.md ahora tiene solo la **esencia (3 líneas) + pointer** a `atlas-engram-reference.md` como fuente única. `duplication_risk` de CLAUDE.md bajado `high → low` en el registry. (orquestador.md y agent-protocol.md no se tocaron — su dedup queda para F31.)

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Claude no carga una ref cuando hace falta | Mapa con triggers explícitos + escape hatch inline; boot-essential y reglas de gobernanza siguen inline |
| Comportamiento Windows (preview_start) se pierde si no se lee la ref | Regla crítica de 1 línea **inline** + pointer al detalle |
| Enforcement de dispatcher depende de markdown | NO — el dispatcher valida en runtime (código), independiente de lo que Claude lea |
| Drift CLAUDE.md ↔ refs | F10 drift + check WARN-only de Knowledge Registry; healthcheck verde |
| Hard rules perdidas | Reglas clave copiadas **verbatim**, verificadas en F30.7 |

---

## Validación

| Check | Resultado |
|-------|-----------|
| boot_profiler --scan always_on | **1,698 tokens** (−81%) |
| F29 suite | 26/26 PASS |
| Quick | 31/31 PASS |
| Release | 34/34 PASS |
| Healthcheck | HEALTHY (Knowledge registry PASS) |
| secrets_check | exit 0 |

---

## Próximo paso (F31, diferido)

Decomposición de `orquestador.md` (core + 1 ref por fase) y `agent-protocol.md`
(core + contratos por clase), y evolución del Capability Router a Knowledge
Resolver. Mayor ahorro absoluto pero solo en sesiones de pipeline y con más
riesgo — después de F30, con la red F24 + Knowledge Registry como respaldo.
