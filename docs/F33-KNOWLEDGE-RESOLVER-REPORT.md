# F33 — Knowledge Resolver + Second-Layer Decomposition Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F32 `aec6752`)
**Modo:** descomposición de 2ª capa + primer `resolve_knowledge()`. **Sin cambio de comportamiento, sin borrar conocimiento, sin tocar dispatcher/runtime/MCPs/CI.**

---

## Tokens antes / después (los 2 refs grandes)

| Ref | Antes | Después (índice) | Reducción |
|-----|------:|-----------------:|-----------|
| `orchestrator-pipeline.md` | ~17,961 | **~673** | **−96%** |
| `protocol-agent-contracts.md` | ~13,134 | **~566** | **−96%** |

Ambos índices muy por debajo del objetivo (<3K). El contenido se conservó **verbatim** en refs por fase/concern, cargados solo cuando se necesitan.

---

## Architecture Score antes / después

| | F31 | F32 | **F33** |
|---|---:|---:|---:|
| Architecture Score | 62/100 | 62/100 | **86/100** |
| oversized files | 2 | 2 | **0** |
| decompose_candidates | 2 | 2 | **0** |

**+24 puntos, honesto:** F32 movió los god-files a 2 refs grandes (sin bajar el score porque el contenido seguía concentrado). F33 descompuso esos 2 refs en piezas single-purpose, **todas bajo el umbral oversized** → desaparecen `oversized` y `decompose_candidates`. El boot profiler escanea `refs/` (incluido en F32), así que la mejora **no** es por ocultar contenido — las piezas son medibles y simplemente más pequeñas. Penalizaciones restantes: 5 `large` (agent-docs pre-existentes 6–12K) + 9 `duplication` (vocabulario inherente).

---

## Nuevos refs (contenido verbatim)

**orchestrator-pipeline → 6 fases** (`.claude/agents/refs/`):
`orchestrator-pipeline-phase-1.md` (FASE 1, 314 ln) · `-phase-2.md` (FASE 2, 332) ·
`-phase-2b.md` (FASE 2B, 148) · `-phase-3.md` (FASE 3, 261) · `-phase-4.md` (FASE 4, 105) ·
`-phase-5.md` (FASE 5, 72). Índice retiene Phase Gates inline + mapa + reglas críticas + escape hatch.

**protocol-agent-contracts → 3 concerns**:
`protocol-agent-contract-core.md` (saves, design intel, reality re-runs, QA cache, wiring, 293 ln) ·
`-enforcement.md` (skills/hard-rules, envelope, design hardening, auto-invoke, escalation, 481) ·
`-evidence.md` (screenshot, visual evidence, invocation tracking, anti-loop, fidelity, console, network, 398).
Índice retiene contrato base + mapa por concern/clase + reglas críticas.

> Nota honesta: los contratos están organizados por **concern** (blocs 4.x), no por
> clase de agente — no existen secciones per-frontend/backend/research en el archivo.
> Se descompuso por concern (la estructura real); el índice mapea concerns → clases
> de agente de forma orientativa.

---

## Knowledge Resolver (`tools/knowledge_resolver.py`)

Primer `resolve_knowledge()` formal: dado intención/capability/query, selecciona refs
del registry. **Metadata only** (path/reason/estimated_tokens/load_policy) — nunca
contenido. Matching scoreado por id/category/trigger/tags/path/notes.

CLI: `--list` · `--resolve <query>` · `--json <query>`. Ejemplos verificados:
- `pipeline` → índice + 6 fases
- `phase-1` → `orchestrator-pipeline-phase-1.md`
- `frontend` → `protocol-agent-contract-core.md` (tag frontend)
- `qa` → phase-3 + contract-core + contract-evidence
- query desconocida → `[]` (no rompe, nada cargado)

Convive con el Capability Router (F16) — mismo patrón, dominio distinto (conocimiento vs MCPs).

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| No cargar la fase/contrato correcto | Índices con mapa + triggers + escape hatch; Phase Gates y reglas críticas quedan inline |
| Drift refs ↔ dist | `sync_dist` + F10 (top-level); refs espejados a `agents/refs/` |
| Resolver da falso positivo | Scoreado por señal; metadata only, el caller decide leer |
| estimated_tokens de phase refs en 0 en el registry | Refrescables con `boot_profiler --scan`; no se usan para gates |

---

## Qué queda pendiente (futuro)

- Penalización `large` (5 agent-docs 6–12K: frontend-developer, evidence-collector,
  reality-checker, ui-designer, brand-agent) — opcional, bajo valor.
- `duplication` de vocabulario (Engram/MCP/QA) — inherente, no accionable.
- Wiring real de `resolve_knowledge()` dentro del flujo del orquestador/subagentes
  (hoy es lookup CLI/librería; el runtime sigue cargando refs por el mapa de índices).

---

## Validación

| Check | Resultado |
|-------|-----------|
| orchestrator-pipeline / protocol-agent-contracts | índices −96% / −96%, <3K ✓ |
| Architecture Score | 62 → **86** |
| F33 resolver suite | 14/14 PASS |
| F29 boot profiler | PASS |
| F31 architecture audit | PASS |
| F10 drift | 5/5 PASS |
| Quick | 33/33 PASS |
| Release | 36/36 PASS |
| Healthcheck | HEALTHY |
| secrets / dispatcher diff | exit 0 / vacío |

Próximo paso recomendado: wiring de `resolve_knowledge()` en el boot del orquestador, o atacar los 5 `large` agent-docs si se busca subir más el score.
