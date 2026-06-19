# Protocol — Agent Contracts (Índice)

> **F33 — second-layer decomposition.** Este archivo es ahora un **índice** de los
> contratos por concern. El detalle se movió **verbatim** a
> `protocol-agent-contract-*.md`. Comportamiento sin cambios.
> **Escape hatch: cargá la ref del contrato que aplica a tu tarea ANTES de actuar.**

## Contrato base (recordatorio)

Todo subagente: Engram 2-pasos, `topic_key` obligatorio, Return Envelope estándar,
handoff mínimo, no commitea/despliega/spawnea. Base completa en `agent-protocol.md`
y `protocol-envelope-audit.md`.

## Mapa de contratos por concern (cargar el que aplique)

| Tu tarea involucra… | Leé |
|---------------------|-----|
| Proactive saves, Design Intelligence (1C.1), reality-checker re-runs (1E.1), QA cache (1F.1), runtime wiring (1G.1) | `protocol-agent-contract-core.md` |
| Skills Registry + Hard Rules (F2.1), envelope contract formal (F1.1), design hardening (1L.1–1L.4), auto-invoke (1K.4), hard escalation (1K.3) | `protocol-agent-contract-enforcement.md` |
| Screenshot hash (1J.2), visual evidence verification (1J.1), invocation tracking (1G.2), anti-loop inter-sesión (1I.1), visual fidelity (1H.3), console (1H.2), network (1H.1) | `protocol-agent-contract-evidence.md` |

**Por clase de agente (orientativo):**
- **evidence-collector / reality-checker (QA):** `protocol-agent-contract-evidence.md` + core (QA cache).
- **ui-designer / ux-architect (design):** core (Design Intelligence) + enforcement (design hardening).
- **dev-agents (frontend/backend/rapid):** core (runtime wiring) + enforcement (envelope/auto-invoke).
- **todos:** enforcement (skills/hard-rules), evidence (invocation tracking, anti-loop).

## Reglas críticas inline (no negociables)
- **evidence-collector:** STATUS PASS/FAIL exclusivos + archivos no-vacíos + evidence trail.
- **dev-agents:** pre_return_audit + file declaration superset del `git diff`.
- **design_strict:** `design_intelligence.queried=true` + cascada 1L.
- Auto-invoke de helpers faltantes (1K.4) + escalación dura (1K.3) son OBLIGATORIOS.

## Escape hatch
Si tu tarea requiere un contrato específico y no lo tenés en contexto, **leé primero
la ref del mapa**. Las refs tienen el contrato completo verbatim — no improvises.
