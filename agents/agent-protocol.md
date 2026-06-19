---
name: agent-protocol
description: Protocolo compartido para TODOS los subagentes del sistema vibecoding. Engram, Return Envelope, reglas universales.
model: sonnet
---

# Protocolo de Subagentes — Referencia Compartida (Fachada)

Este archivo define los patrones que TODO subagente debe seguir. No dupliques este contenido en tu archivo — referéncialo.

> **F32 — Knowledge Decomposition.** Fachada delgada: contrato base inline + mapa de
> contratos por tipo de agente. El detalle se movió **verbatim** a
> `.claude/agents/refs/protocol-*.md`. Comportamiento sin cambios. **Escape hatch:
> si tu tarea requiere un contrato específico (QA, diseño, capability, etc.) y no lo
> tenés en contexto, leé la referencia correspondiente ANTES de actuar.**

---

## Contrato base (inline — todos los subagentes)

### Engram en 2 pasos (OBLIGATORIO)
```
result = mem_search("{proyecto}/{cajon}")
if result.observation_id:
    full = mem_get_observation(result.observation_id)   # usar full.content, NUNCA preview
else:
    # cajón no existe — informar al orquestador
```
Escritura SIEMPRE con `topic_key` (evita duplicados). Detalle completo:
`refs/protocol-memory-engram.md`.

### Return Envelope (formato estándar)
```
STATUS: completado | fallido | PASS | FAIL
TAREA: {descripción}
ARCHIVOS: [lista]
ENGRAM: {proyecto}/{cajon}
VERIFICACION: layout | typo | config | none
BLOQUEADORES: [lista opcional]
NOTAS: {texto}
```
El dispatcher rechaza envelopes mal formados. Modos de validación
(standard/qa_strict/dev_strict/design_strict) y detalle: `refs/protocol-envelope-audit.md`.

### Límites universales (lo que NINGÚN subagente hace)
- No commitea/pushea (solo **git**), no despliega (solo **deployer**).
- No spawnea otros subagentes (solo el orquestador coordina).
- Devuelve handoff mínimo (STATUS + archivos + issues), nunca código completo inline.
- Screenshots a disco, pasar rutas — nunca imágenes inline.

Reglas universales completas: `refs/protocol-core-universal.md`.

---

## Mapa de contratos por responsabilidad (leer el que aplique)

| Tu tarea involucra… | Leé |
|---------------------|-----|
| Engram: lectura/escritura, strategy, MCP real connection | `.claude/agents/refs/protocol-memory-engram.md` |
| Return Envelope detallado, Pre-Return Audit, Delegation Stop Rules | `.claude/agents/refs/protocol-envelope-audit.md` |
| Contratos por agente: proactive saves, design intel, QA cache, runtime wiring, skills/hard-rules, hardening, screenshot/visual evidence, network/console | `.claude/agents/refs/protocol-agent-contracts.md` |
| Reglas universales, Design Intelligence queries, anti-generic 21st.dev, límites, anti-loop intra-sesión | `.claude/agents/refs/protocol-core-universal.md` |
| Capability Router (`resolve_capability`) / Metrics / Policy Engine (F16/F18/F19) — para **solicitar capability** providers | `.claude/agents/refs/protocol-capability.md` |

## Reglas críticas inline (no negociables)

- **Engram 2-pasos** siempre (nunca preview truncada).
- **topic_key** obligatorio en toda escritura.
- **Return Envelope** en toda respuesta de subagente (fase 3+).
- **evidence-collector**: STATUS PASS/FAIL exclusivos + archivos no-vacíos.
- **dev-agents**: pre_return_audit + file declaration superset del `git diff`.
- Nunca exponer secretos; nunca código completo inline en handoffs.

## Escape hatch

Si tu tarea requiere un contrato específico (QA estricta, design_strict, capability
resolution, anti-loop) y **no lo tenés en contexto**, leé primero la referencia del
mapa. Las refs contienen el contrato completo verbatim — no improvises desde memoria.
