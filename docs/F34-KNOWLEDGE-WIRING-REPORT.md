# F34 — Knowledge Resolver Wiring Report

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (post-F33 `fd22f50`)
**Modo:** wiring documental de `resolve_knowledge()` en el flujo. **Sin tocar dispatcher/runtime/MCPs/CI; sin nuevos agentes; reversible.**

---

## Qué cambió

`resolve_knowledge()` pasa de ser un lookup aislado (F33) a **mecanismo oficial de
carga contextual**, cableado en los 3 puntos de entrada + documentado:

1. **`docs/atlas-knowledge-resolver.md`** (nuevo) — contrato: problema que resuelve,
   `resolve_capability()` vs `resolve_knowledge()`, cuándo usarlo, entradas, salida
   metadata-only, qué NO hace, ejemplos, mapa intención→query.
2. **`CLAUDE.md`** — bloque corto (preferir resolver antes de cargar refs grandes) +
   fila en el mapa de referencias. CLAUDE.md sigue **<2K tokens** (~1,841).
3. **`orquestador.md`** (fachada) — sección "Carga contextual con resolve_knowledge()":
   no cargar `orchestrator-pipeline.md` entero; tabla intención→query→carga.
4. **`agent-protocol.md`** (fachada) — no cargar `protocol-agent-contracts.md` entero;
   resolver el contrato por concern/clase.
5. **`config/knowledge.registry.yaml`** — entrada del doc resolver con tags/trigger.

**Mejora del resolver** (para soportar el wiring): `resolve_knowledge()` ahora
**tokeniza** queries multi-palabra y scorea por término (entradas que matchean más
términos rankean más alto). Single-term sigue idéntico (backward-compatible, F33 14/14).

---

## Queries soportadas (verificadas)

| Query | Top ref |
|-------|---------|
| `pipeline phase-1` | `orchestrator-pipeline-phase-1.md` |
| `pipeline phase-3` | `orchestrator-pipeline-phase-3.md` |
| `qa evidence` | `protocol-agent-contract-evidence.md` |
| `frontend agent contract` | `protocol-agent-contracts.md` (índice) → core |
| `release gate` | `atlas-release-reference.md` |
| `engram` | `protocol-memory-engram.md` |
| `zzz-nope` | `[]` (no rompe) |

Mapa intención→query documentado en CLAUDE.md, orquestador y el doc del resolver.

---

## Architecture Score antes / después

| | F33 | **F34** |
|---|---:|---:|
| Architecture Score | 86/100 | **86/100** |

Estable: F34 es wiring documental, no cambia tamaños de refs. El score se mantiene en
el nivel ganado por la descomposición de F33.

---

## Estado de boot tokens

| | Antes F34 | Después F34 |
|---|---:|---:|
| CLAUDE.md (always-on) | ~1,698 | ~1,841 |
| always_on total | 1,698 | **1,841** |

+143 tokens por el bloque de wiring (preferir resolver). Sigue **muy por debajo** del
budget de 2,500 (F30). Único archivo always-on: CLAUDE.md.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| El resolver no se usa (sigue siendo opcional) | Wiring en los 3 puntos de entrada + mapa intención→query; doc de contrato. Adopción es de comportamiento, no forzada por código (no se toca runtime) |
| Query ambigua devuelve ref incorrecto | Scoreado por señal + bonus multi-término; metadata-only, el caller decide |
| CLAUDE.md crece con el wiring | Medido: +143t, sigue <2K |
| Tokenización rompe F33 | Verificado backward-compatible (F33 14/14 PASS) |

---

## Qué queda pendiente

- **Wiring en runtime real:** hoy el resolver es lookup CLI/librería y el flujo lo
  invoca por convención documental. Integrarlo en el dispatcher/boot del orquestador
  (cargar el ref resuelto automáticamente) es trabajo futuro fuera del scope F34
  (rompería "no tocar dispatcher/runtime").
- Atacar los 5 `large` agent-docs (6–12K) si se busca subir el score por encima de 86.

---

## Validación

| Check | Resultado |
|-------|-----------|
| F34 wiring suite | 13/13 PASS |
| F33 resolver suite | 14/14 PASS (tokenización backward-compat) |
| F29 / F31 | PASS |
| CLAUDE.md tokens | ~1,841 (<2K) |
| Architecture Score | 86 |
| Quick | 34/34 PASS |
| Release | 37/37 PASS |
| Healthcheck | HEALTHY |
| secrets / dispatcher diff | exit 0 / vacío |
