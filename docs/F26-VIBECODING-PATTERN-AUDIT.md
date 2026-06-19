# F26 — External Architecture Pattern Audit: claude-vibecoding

**Fecha:** 2026-06-19
**Repo auditado:** https://github.com/Emaleo0522/claude-vibecoding (read-only, clon shallow temporal)
**Auditor base:** ATLAS v1.0.0-rc2 (`51e5842` / `afcc4b3`)
**Modo:** análisis y propuesta. **Sin cambios de código, sin commits, sin instalaciones.**

---

## Resumen ejecutivo

`claude-vibecoding` es el **upstream del que ATLAS deriva**. Las dos arquitecturas divergieron en direcciones complementarias:

- **ATLAS** invirtió en la **capa OS / gobernanza**: registries declarativos (MCP/test/projects/skills), capability router + policy engine, healthcheck de 24 checks, test runner con CI + Release Validation, ADR formales (`ADR/`), contracts Pydantic. **En esta capa, ATLAS está por delante del upstream.**
- **claude-vibecoding** invirtió en la **capa de pipeline de diseño y doctrina de trabajo**: Design Intelligence embebida (CSV + BM25), Intent Clarifier interactivo, Visual Direction Checkpoint, hardening anti-falso-positivo más elaborado, y varias doctrinas de DX (Modo Diagnóstico, Simplicity First, Delegation Stop Rules).

**La mayoría de los patrones evaluados ya existen en ATLAS** (heredados o reimplementados): security hooks (idénticos salvo CRLF), `frontend-audit.sh` / `pre-return-audit.sh` (idénticos), Intent Clarifier, Visual Direction, false-positive guardrail, ADR + drift detection. Los **gaps reales son acotados y de bajo riesgo** — principalmente doctrina en `CLAUDE.md` y un gate de QA (No-JS Render Audit).

**Conclusión:** hay **3-4 quick wins seguros** (puro markdown/doctrina, sin tocar código ni dispatcher), **1-2 ADAPT** de valor medio (Design Intelligence self-contained, No-JS audit), y un conjunto claro de **REJECT/DEFER** que no conviene importar (delegación a modelos externos, Engram cloud cross-PC, refs de nicho).

---

## Inventario del repo externo

| Categoría | Contenido | ¿En ATLAS? |
|-----------|-----------|------------|
| **Hooks** | 17 (block-no-verify, config-protection, quality-gate, console-log-warning, cost-tracker/report, pre-compact-engram, session-*, suggest-compact, learning-index, audit-system, engram-sync, **frontend-audit.sh**, **pre-return-audit.sh**, **zen-delegate.js**, **engram-cloud-sync-on-stop.sh**) | Casi todos sí. ATLAS además tiene `delegation-tracker`, `dual-write-sync`, `pipeline-rules`, `qa-auto-audit`. Exclusivos upstream: `zen-delegate.js`, `engram-cloud-sync-on-stop.sh` |
| **Agentes** | 25 agentes + ~22 `*-reference.md` | Núcleo idéntico. Refs exclusivas upstream: `simplicity-first`, `intent-clarifier`, `modo-diagnostico`, `linux-hardening`, `cross-claude-mailbox`, `external-skills`, `orquestador-edge-cases/fase-2b/modificacion` |
| **Docs** | `docs/game-dev-improvements.md`, `AGENTS.md`, `PIPELINE-AGENTS.md`, `UPGRADE_LOG.md`, README bilingüe | ATLAS tiene docs/ más rica (CAPABILITIES, MCP, HOOKS, SKILLS, etc.) |
| **Install scripts** | `install.sh` (wrapper OS-detect) → `install/linux.sh` + `install/windows.md` | **Idéntico** en ATLAS |
| **design-data** | 10 CSV (styles, colors, charts, landing, products, typography, ux-guidelines, ui-reasoning…) + `search.js` (BM25) | **NO en ATLAS** — ATLAS depende de skill externo para Design Intelligence |
| **Templates** | settings.json, settings.local.json, windows-launch.json, windows-mcp-config.json | ATLAS los tiene + `global-claude.md`, `windows-claude.md` |
| **Policies** | En CLAUDE.md (doctrina) | ATLAS las tiene **declarativas** (capability.policy.yaml, hard-rules.json) — más avanzado |
| **QA practices** | Anti-falso-positivo, No-JS audit, Visual Fidelity LLM-judge, E2E flows, network/console | Mayoría en ATLAS (1E/1H series). Gap: No-JS audit |
| **Security practices** | block-no-verify, config-protection, linux-hardening-reference | Hooks idénticos en ATLAS; linux-hardening es ref de nicho |
| **Onboarding** | README bilingüe ES/EN, install wrapper | ATLAS README recién renovado (F25); falta versión EN |

---

## Evaluación de los patrones solicitados

| # | Patrón | Estado en ATLAS | Veredicto |
|---|--------|-----------------|-----------|
| 1 | **No-JS Render Audit** (reality-checker Paso 4.5) | Ausente (0 refs en reality-checker) | **ADOPT** |
| 2 | **Visual Impact / Visual Direction Checkpoint** | Presente (15 refs en orquestador) | **REJECT** (ya existe) |
| 3 | **Delegation Stop Rules** | Mecanismo presente (`delegation-tracker.js` 1D.1); doctrina de umbrales NORMAL-mode parcial | **ADAPT** |
| 4 | **AUTO_AUDIT pre-return** | Presente (`pre-return-audit.sh`/`frontend-audit.sh` idénticos + 1A.14/1A.15) | **REJECT** (ya existe) |
| 5 | **QA anti-falso-positivo** | Presente (false-positive guardrail ×5, reality-checker re-runs 1E.1, network/console 1H) | **REJECT** (ya existe; upstream solo más verboso) |
| 6 | **ADR en Engram + drift detection** | Presente y **superior** (`ADR/` formal con 5 ADRs + self-auditor drift ×13) | **REJECT** (ATLAS adelante) |
| 7 | **install/bootstrap patterns** | Idéntico (`install.sh` wrapper + linux.sh + windows.md) | **REJECT** (ya existe) |
| 8 | **documentation/onboarding** | ATLAS más rico; falta README en inglés | **DEFER** (README.en.md) |
| 9 | **security hooks** | Idénticos (CRLF aparte) | **REJECT** (ya existe) |
| 10 | **model routing** | Idéntico (Opus/Sonnet por frontmatter) | **REJECT** (ya existe) |
| 11 | **design-data / Design Intelligence** | Ausente self-contained (ATLAS usa skill externo) | **ADAPT** |
| 12 | **Modo Diagnóstico** (read-only doctrine) | Ausente (0 refs) | **ADOPT** |
| 13 | **Simplicity First** (output doctrine) | Ausente (0 refs) | **ADOPT** |
| 14 | **zen-delegate.js** (delegación a modelos Go externos) | Ausente | **REJECT** |
| 15 | **engram-cloud-sync-on-stop + cross-claude-mailbox** | Ausente | **DEFER** |
| 16 | **linux-hardening-reference / external-skills-reference** | Ausente | **DEFER / REJECT** |

---

## Fichas de patrones candidatos (ADOPT / ADAPT)

### P1 — No-JS Render Audit  ·  **ADOPT**
- **Valor:** detecta landings CSR-puro (Vite/CRA) que se rompen sin JS → SEO/accesibilidad. Gate ejecutable en reality-checker Paso 4.5; modo `warn` no bloquea.
- **Riesgo:** bajo. Es doctrina + grep/`<noscript>` check; no dependencias nuevas.
- **Compatibilidad:** alta. ATLAS ya tiene reality-checker y network inspection.
- **Componente afectado:** `.claude/agents/reality-checker.md` (doctrina), opcionalmente una suite `_qa/` que valide la presencia del paso.
- **Tests necesarios:** suite que verifique que reality-checker documenta Paso 4.5; opcional smoke de detección CSR.
- **Healthcheck:** no requiere check nuevo.
- **Rollback:** revertir el bloque markdown.
- **MCP/token:** no.
- **CI:** sin impacto (si se añade suite, registrarla en test.registry).

### P2 — Modo Diagnóstico (read-only doctrine)  ·  **ADOPT**
- **Valor:** modo de auditoría read-only con reglas inviolables + template de reporte. Gobernanza/DX. **Esta misma auditoría F26 es exactamente ese caso de uso.**
- **Riesgo:** bajo. Es doctrina en `CLAUDE.md`; no enforceable técnicamente (auto-restricción), pero alinea comportamiento.
- **Compatibilidad:** alta. Complementa Plan/Explore sin solaparlos.
- **Componente afectado:** `CLAUDE.md` (nueva sección) + opcional `modo-diagnostico-reference.md` on-demand.
- **Tests necesarios:** ninguno técnico; opcional lint de que la sección existe.
- **Healthcheck:** no.
- **Rollback:** quitar la sección.
- **MCP/token:** no.
- **CI:** sin impacto.

### P3 — Simplicity First (output doctrine)  ·  **ADOPT**
- **Valor:** TL;DR-first, baja fricción, menos tokens. Mejora DX transversal a los 4 modos.
- **Riesgo:** muy bajo. Doctrina pura.
- **Compatibilidad:** total.
- **Componente afectado:** `CLAUDE.md` + opcional `simplicity-first-reference.md`.
- **Tests/healthcheck/CI:** ninguno.
- **Rollback:** quitar sección.
- **MCP/token:** no.

### P4 — Delegation Stop Rules (tabla de umbrales NORMAL-mode)  ·  **ADAPT**
- **Valor:** umbrales deterministas (5+ lecturas, 20+ tool calls, antes de commit no-trivial…) para sugerir escalar al pipeline. Complementa `delegation-tracker.js`.
- **Riesgo:** bajo, pero **solape parcial** con 1D.1 — requiere conciliar doctrina (CLAUDE.md) con el mecanismo existente para no duplicar/contradecir.
- **Compatibilidad:** media-alta; necesita rediseño para mapear a la nomenclatura ATLAS.
- **Componente afectado:** `CLAUDE.md` (doctrina), referencia a `delegation-tracker.js`.
- **Tests:** opcional, verificar coherencia doctrina↔tracker.
- **Healthcheck/CI:** sin impacto.
- **Rollback:** quitar tabla.
- **MCP/token:** no.

### P5 — Design Intelligence self-contained (design-data + search.js)  ·  **ADAPT**
- **Valor:** elimina la dependencia de un skill externo para Design Intelligence; conocimiento de diseño versionado en repo (BM25 sobre CSV). Reproducible, sin red.
- **Riesgo:** medio. ~10 CSV + `search.js` (Node) = superficie nueva; hay que decidir ownership, validación y si reemplaza o complementa el skill actual (1C.1/1L.x esperan `design_intelligence.queried`).
- **Compatibilidad:** media. Requiere wiring con `consult_design_intelligence` / `verify_design_intelligence_real`.
- **Componente afectado:** nuevo `design-data/`, posible tool `tools/design_search.py` o reuso de `search.js`, registry de skills, healthcheck (check de presencia de data).
- **Tests:** suite que valide carga de CSV + query BM25 determinista.
- **Healthcheck:** nuevo check "Design Intelligence data".
- **Rollback:** quitar `design-data/` + check; volver a skill externo.
- **MCP/token:** no (pero Node requerido).
- **CI:** añade suite → registrar en test.registry; verificar que corre sin el skill externo.

---

## Ranking por impacto / riesgo

| Rank | Patrón | Impacto | Riesgo | Esfuerzo |
|------|--------|---------|--------|----------|
| 1 | **Simplicity First** | Medio-alto (DX diaria) | Muy bajo | Trivial |
| 2 | **Modo Diagnóstico** | Medio-alto (gobernanza/audits) | Bajo | Bajo |
| 3 | **No-JS Render Audit** | Medio (SEO/a11y) | Bajo | Bajo-medio |
| 4 | **Delegation Stop Rules** | Medio | Bajo (solape) | Bajo |
| 5 | **Design Intelligence self-contained** | Alto (quita dep externa) | Medio | Medio-alto |
| 6 | **README.en.md** | Bajo-medio (alcance) | Muy bajo | Bajo |

---

## Quick wins seguros (puro markdown, sin código/dispatcher/hooks)

1. **Simplicity First** → sección en `CLAUDE.md` (+ ref on-demand opcional).
2. **Modo Diagnóstico** → sección en `CLAUDE.md` (+ `modo-diagnostico-reference.md`).
3. **No-JS Render Audit** → bloque en `reality-checker.md` (modo `warn`, no bloqueante).
4. **Delegation Stop Rules** → tabla de umbrales en `CLAUDE.md`, referenciando el tracker existente.

Ninguno toca: dispatcher, hooks ejecutables, registries de código, CI. Todos reversibles con `git revert` del bloque.

---

## Patrones rechazados (REJECT)

| Patrón | Por qué |
|--------|---------|
| **zen-delegate.js** | Delega tareas a modelos Go externos (opencode.ai) → nueva dependencia de red, costo por token, superficie de seguridad y cuota. Viola "no instalar nada / no nuevos tokens". El valor (ahorro de tokens) no compensa el riesgo para un RC. |
| **Visual Direction Checkpoint, AUTO_AUDIT, false-positive QA, ADR drift, security hooks, model routing, install** | **Ya existen en ATLAS** (varios con implementación superior). Importarlos sería ruido/duplicación. |
| **external-skills-reference** (`npx skills add`) | Mecanismo para sumar knowledge packs comunitarios → cadena de suministro no auditada. Contra el principio ATLAS de enforcement verificable. |

---

## Deuda que NO conviene importar

- **Doctrina dispersa en un CLAUDE.md de 45KB**: el upstream concentra políticas en prosa dentro de `CLAUDE.md`. ATLAS ya migró a **policies declarativas** (`capability.policy.yaml`, `hard-rules.json`); importar prosa sería un retroceso. Adoptar **solo** las doctrinas de comportamiento (Simplicity/Diagnóstico), no las que ATLAS ya tiene como YAML.
- **Engram cloud cross-PC** (`engram-cloud-sync-on-stop.sh` + `cross-claude-mailbox-reference`): acoplan a Engram cloud y a un protocolo de mailbox opt-in. Tocan hooks (prohibido en esta fase) y añaden estado distribuido frágil. **DEFER** hasta tener un caso real multi-PC.
- **Referencias de nicho** (`linux-hardening`, `orquestador-fase-2b/edge-cases/modificacion`): útiles en el contexto de pipeline del upstream, pero son peso muerto para el foco OS de ATLAS salvo que se reactive ese pipeline de diseño intensivamente. **DEFER**.

---

## Plan de integración por fases (propuesto — requiere aprobación)

> Cada fase respeta la regla ATLAS: **toda adopción pasa por registry → healthcheck → tests → documentación**, y cada cambio se valida con `run_all --quick` + healthcheck antes de commit.

**Fase F26.A — Quick wins de doctrina (markdown puro)**
- Añadir a `CLAUDE.md`: Simplicity First, Modo Diagnóstico, Delegation Stop Rules.
- Validación: lint/grep de secciones; `run_all --quick`; healthcheck.
- Rollback: `git revert`. Sin impacto CI.

**Fase F26.B — No-JS Render Audit**
- Añadir Paso 4.5 a `reality-checker.md` (modo warn).
- Suite `_qa/` opcional + registrar en `test.registry.yaml`.
- Validación: quick + release; confirmar exit codes.

**Fase F26.C — Design Intelligence self-contained (mayor)**
- Decisión previa: ¿reemplaza o complementa el skill externo?
- Importar `design-data/` (data, no binarios), tool de búsqueda, check de healthcheck, suite de tests, registro en skills registry.
- Validación completa: quick + release + healthcheck + CI verde con y sin skill externo.

**Fase F26.D — Onboarding (opcional)**
- `README.en.md` derivado del README F25.

**No incluido en ningún plan:** zen-delegate, Engram cloud sync, external-skills, refs de nicho.

---

## Notas de cierre

- ATLAS no necesita "ponerse al día" con el upstream en lo OS — ahí lidera. El valor a rescatar es **doctrina de trabajo** (3 quick wins) y, con más cuidado, **independencia de Design Intelligence**.
- Ningún patrón ADOPT requiere MCP, token, ni toca el dispatcher/hooks/CI.
- **Pendiente de tu aprobación** antes de cualquier commit o implementación (F26.A–D).
