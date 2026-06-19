# F35 — External Pattern Review: claude-vibecoding (vs current ATLAS)

**Fecha:** 2026-06-19
**Repo:** https://github.com/Emaleo0522/claude-vibecoding (read-only, clon temporal)
**Comparación:** contra **ATLAS actual** (post-F34), no contra ATLAS viejo.
**Modo:** análisis. **Sin copiar nada. Sin incorporar nada automáticamente.**

> Cada patrón clasificado por el propio Architecture Decision Governor (F35.4) y
> revisado contra 10 criterios estrictos.

---

## Estado relativo

vibecoding creció desde F26: ahora tiene 49 agents, 20 hooks, `tests/`,
`mcp.registry.json`, y observability propia (healthcheck.js, drift-check.js,
mcp-registry.js). **Pero esas capacidades ATLAS ya las tiene** — en Python, más
maduras (healthcheck 25 checks, F10 drift, mcp.registry.yaml, CI, release gates,
boot profiler, architecture audit, knowledge resolver). **ATLAS lidera la capa
OS/governance/context-engineering; vibecoding lidera doctrina de trabajo + pipeline
de diseño.** Esto confirma y actualiza F26.

---

## Tabla de patrones (criterios estrictos)

Criterios: (1)↓complejidad (2)↓tokens (3)↑seguridad (4)↑estabilidad (5)↑calidad
(6)rompe compat (7)+deps (8)+carga entrada (9)testeable (10)rollback.

| Patrón | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Governor | Veredicto |
|--------|---|---|---|---|---|---|---|---|---|----|----------|-----------|
| **Modo Diagnóstico** (doctrina read-only audit) | = | = | + | + | + | no | no | + | sí | sí | ACCEPT_WITH_LIMITS | **ADOPT** |
| **Simplicity First** (doctrina de output) | + | + | = | = | + | no | no | = | sí | sí | ACCEPT_WITH_LIMITS | **ADOPT** |
| **No-JS Render Audit** (gate SEO/a11y) | = | = | + | + | + | no | no | = | sí | sí | ACCEPT_WITH_LIMITS | **ADAPT** |
| **design-data self-contained** (CSV+search.js) | − | − | = | = | + | no | (node) | + | sí | sí | NEEDS_EVIDENCE | **DEFER** |
| **zen-delegate** (modelos Go externos) | − | +? | − | − | =? | no | **sí** | = | parcial | sí | NEEDS_HUMAN_APPROVAL | **REJECT** |
| **engram-cloud-sync** (memoria cross-PC) | − | = | − | − | = | no | **sí (cloud)** | = | difícil | parcial | NEEDS_HUMAN_APPROVAL | **DEFER** |
| **external-skills** (`npx skills add`) | − | = | **−** | − | =? | no | **sí** | = | no | sí | NEEDS_HUMAN_APPROVAL | **REJECT** |
| healthcheck.js / drift-check.js / mcp-registry.js (JS) | = | = | = | = | = | — | dup | = | sí | sí | — | **REJECT** (ya existe en Python) |
| mcp.registry.json + tests/ | = | = | = | = | = | — | dup | = | sí | sí | — | **REJECT** (paridad ya cubierta) |

---

## ADOPT (bajo riesgo, valor claro)

- **Modo Diagnóstico**: doctrina read-only con template de reporte. ATLAS no la tiene;
  mejora gobernanza/auditorías. Markdown puro, reversible. (Este F35 ya opera en ese
  espíritu.)
- **Simplicity First**: doctrina de output TL;DR-first. ↓tokens, ↑DX. Markdown puro.

## ADAPT

- **No-JS Render Audit**: gate de render sin JS (SEO/a11y) en la ref de reality-checker,
  modo warn. Útil, requiere redacción propia (no copiar).

## DEFER

- **design-data self-contained**: quitaría la dependencia del skill externo de Design
  Intelligence, pero añade ~10 CSV + search.js (node) y superficie nueva → medir antes
  (NEEDS_EVIDENCE). No ahora.
- **engram-cloud-sync**: cross-PC útil, pero acopla a Engram cloud + toca hooks +
  estado distribuido frágil → DEFER hasta caso real multi-PC.

## REJECT

- **zen-delegate**: delega a modelos Go externos (opencode) → nueva dependencia, costo,
  superficie de seguridad. Riesgo > beneficio para un RC.
- **external-skills** (`npx skills add`): knowledge packs comunitarios → cadena de
  suministro no auditada. Contra el principio de enforcement verificable.
- **healthcheck.js/drift-check.js/mcp-registry.js/mcp.registry.json/tests JS**: ATLAS
  ya tiene equivalentes Python más maduros. Importarlos sería duplicación/ruido.

---

## Deuda que NO conviene importar

- Doctrina dispersa en un CLAUDE.md grande (ATLAS ya migró a policies declarativas +
  boot loader delgado — importar prosa sería retroceso).
- Segundo stack de observability en JS (colisiona con el Python existente).
- Refs de nicho (linux-hardening, mailbox cross-PC) — peso muerto para el foco actual.

---

## Conclusión

Nada se incorpora automáticamente. De vibecoding solo vale la pena rescatar **doctrina
de trabajo** (Modo Diagnóstico, Simplicity First) y, con cuidado, **No-JS Render Audit**
— todo markdown, ACCEPT_WITH_LIMITS por el governor. El resto es DEFER/REJECT por
dependencias, duplicación o cadena de suministro. ATLAS no debe converger hacia
vibecoding: debe mantener su capa OS superior y tomar solo las piezas de doctrina que
pasan el policy gate.
