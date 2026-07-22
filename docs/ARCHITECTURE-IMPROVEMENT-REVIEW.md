# Architecture Improvement Review — External Audit + Governed Self-Correction

**Fecha:** 2026-07-21
**Repo externo:** https://github.com/Emaleo0522/claude-vibecoding (read-only)
**Comparado contra:** ATLAS actual — `main` @ `602f805`, **v1.0.0-rc2**
**Modo:** análisis + governor. **Sin copiar código. Adopción solo bajo policy gate.**
**Predecesor:** este review extiende y confirma [`docs/F35-VIBECODING-COMPARISON-REVIEW.md`](F35-VIBECODING-COMPARISON-REVIEW.md) (2026-06-19).

> Veredicto ejecutivo: **NO_CHANGE** para los seis candidatos (A–F). ATLAS ya
> implementa cada patrón en forma más madura, o el patrón duplicaría un subsistema
> existente, o requiere aprobación humana / carece de evidencia de fricción real.
> El único entregable es este documento (docs-only, governor `ACCEPT_WITH_LIMITS`,
> risk 0/5). No se tocó runtime, dependencias, contratos ni proyectos.

---

## 1. Baseline (antes de tocar nada)

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Branch / commit | `main` / `602f805` | `git rev-parse` |
| Versión | v1.0.0-rc2 | CLAUDE.md / tags |
| Healthcheck | **24 PASS · 2 WARN · 0 FAIL** / 26 | `atlas_healthcheck.py` |
| Quick suite | **36/36 PASS** (56.7s) | `run_all.py --quick` |
| Secrets | 0/7 configurados — todos PENDING_TOKEN/DEFERRED_PAID (intencional) | `secrets_check.py` |
| Architecture score | **86** | `architecture_audit.py --score` |
| Test registry | 70 entradas, 0 archivos faltantes | probe reconciliación |
| Reconciliación registries | mcp `required_for` orphans: **NONE**; mcp sin `live_tool_prefix`: **NONE** | probe |

**Estado del working tree:** no limpio, pero los cambios son **preexistentes y ajenos
a este review** — trabajo F37 en curso (`docs/F37-RELEASE-READINESS.md`, `run_all*.json`,
`release-report.md`) y proyecto externo `lucas-rojo-web/*` (registrado, intocable).
Ninguno fue incluido en este review ni en su commit.

**Conclusión baseline:** 0 FAIL, CI verde, score 86 → se permite proceder con
adopción de mejoras. No hay reparación preexistente que mezclar.

---

## 2. Auditoría externa (read-only)

**Licencia:** el repo externo pasó de MIT a **PolyForm Noncommercial License 1.0.0**
(2026-05-27). ⇒ prohibido copiar código/agents/hooks/docs. Solo se permite **adoptar
ideas, reimplementar de forma independiente y atribuir**. Esta restricción se respetó.

**Hallazgo de fondo:** `claude-vibecoding` es el **mismo linaje** que ATLAS (sistema
Gentleman-Programming del que ATLAS desciende): mismo pipeline de 25 agentes / 5 fases,
mismo Engram, mismos hooks, mismo Return Envelope, misma Design Intelligence Engine.
**ATLAS es el descendiente más ingenierizado** (capa OS/governance/context-engineering
en Python: healthcheck 26 checks, F10 drift, CI, release gates, boot profiler,
architecture audit, knowledge resolver, MCP registry). vibecoding lidera doctrina de
trabajo + pipeline de diseño; ATLAS lidera gobernanza y observabilidad.

---

## 3. Matriz de decisión — candidatos A–F del pedido

Criterios evaluados por candidato: ¿ATLAS ya lo tiene? · duplicación · beneficio ·
costo · riesgo · reversible · afecta runtime/proyectos · aprobación humana · evidencia.

| # | Candidato | ¿ATLAS ya lo tiene? | Governor | Decisión |
|---|-----------|---------------------|----------|----------|
| **A** | Contract Reconciliation Gate | **Sí** — `architecture_audit.py` (F31) reconcilia doc/knowledge (orphans, unused, never-loaded); `validate_registry()` en mcp; probes muestran 0 orphans | NEEDS_EVIDENCE → sin defecto real | **NO_CHANGE** |
| **B** | Memory Lifecycle / needs_review | **Sí** — Engram nativo: `mem_review`, `mem_judge`, conflict surfacing (`judgment_required`, `supersedes`/`conflicts_with`); registries con `last_confirmed_live` | — (duplicaría Engram) | **NO_CHANGE** |
| **C** | Clarity + Resilience Review | **Parcial** — `design_quality_enforcement`, `console_log_analyzer` (uncaught/CORS/CSP), `network_inspector` (5xx/mixed-content/fallback), `pre_return_audit` | "measure first" (risk 0, sin evidencia) | **DEFER** |
| **D** | Trigger + skip_when en refs | **Sí** — `knowledge.registry.yaml` (F29) ya tiene `trigger`, `estimated_tokens`, `owner`, `load_policy`, `duplication_risk` | ACCEPT_WITH_LIMITS pero churn sin beneficio | **NO_CHANGE** |
| **E** | Structured Code Retrieval (Codegraph) | No — pero hay Explore/grep suficiente | **NEEDS_HUMAN_APPROVAL** (dep externa, risk 3/5) | **REJECT** (re-proponer con evidencia) |
| **F** | Anti-repetition Design Memory | **Parcial** — Design Intelligence Engine + `visual_fidelity_checker` | sin evidencia de repetición real | **DEFER** |

### Detalle por candidato

**A — Contract Reconciliation Gate → NO_CHANGE.**
La necesidad (estados emitidos vs aceptados, campos obligatorios vs consumidos,
capabilities sin provider, valores huérfanos) ya está cubierta: `architecture_audit.py`
(F31) detecta orphans/unused/never-loaded en la capa knowledge; `mcp_registry.validate_registry()`
valida el registry de MCPs; el dispatcher valida Return Envelope por modo. **Probes de
reconciliación ejecutados en este review:** `required_for → agente` 0 huérfanos (38
agents), `test.registry → archivo` 0 faltantes (70), `mcp sin live_tool_prefix` 0.
Construir un subsistema de reconciliación nuevo duplicaría F31 + validators **sin un solo
defecto actual que lo justifique**. El pedido mismo dice "integrar al tooling existente,
no crear otro sistema"; el tooling existente ya lo hace y no reporta inconsistencias.

**B — Memory Lifecycle → NO_CHANGE.**
Engram provee de forma nativa el ciclo de vida: `mem_review`, `mem_judge`, y conflict
surfacing con relaciones `supersedes` / `conflicts_with` / `related` y `judgment_required`.
Los registries ATLAS ya llevan `last_confirmed_live`. La auto-memory lleva metadata de
tipo/estado. Una capa de lifecycle del lado ATLAS (CURRENT/NEEDS_REVIEW/SUPERSEDED/…)
duplicaría el mecanismo de Engram e inflaría el boot. La regla "una memoria recuperada
no es evidencia final; prevalece el repo" ya se practica (este review lo hace: verificó
cada afirmación contra el repo, no contra memoria).

**C — Clarity + Resilience Review → DEFER.**
La única pieza nueva que valdría (No-JS Render Audit) ya fue marcada **ADAPT** en F35 y
sigue pendiente por ser cambio de QA en `evidence-collector`/`reality-checker`
(toca semántica de agente). El governor sobre "hacer que un flujo crítico sin manejo de
error sea blocker duro" devolvió *"run an audit/measurement first; do not implement blind"*.
No hay fallo observado que lo motive. DEFER hasta que un proyecto real exponga la fricción.

**D — Trigger + skip_when en refs → NO_CHANGE.**
`knowledge.registry.yaml` (F29) ya declara `trigger`, `estimated_tokens`, `owner`,
`load_policy` (que codifica cuándo cargar) y `duplication_risk`. `knowledge_resolver.py`
(F33/F34) resuelve qué ref cargar por intención. Faltan solo `skip_when` y `last_reviewed`
literales — marginal; `load_policy: lazy` + `trigger` ya evitan carga indiscriminada.
Añadir dos campos a 20+ entradas es churn sin beneficio medible.

**E — Structured Code Retrieval (Codegraph) → REJECT (por ahora).**
Nueva dependencia + provider externo. Governor: **NEEDS_HUMAN_APPROVAL** (risk 3/5,
regla `external-or-dependency`). Mismo perfil que `zen-delegate` (REJECT en F35). El
pedido admite adoptarlo "solo si el índice reduce tool calls de forma medible" — no hay
esa evidencia y los proyectos actuales son chicos/medianos donde Explore/grep alcanza.
Re-proponer cuando un proyecto grande muestre overhead real de grep.

**F — Anti-repetition Design Memory → DEFER.**
Idea legítima pero sin evidencia de que proyectos distintos repitan estructura visual.
Añade una memoria + señales + recomendación (superficie nueva) para un problema no
observado. La regla final del pedido es explícita: las mejoras deben originarse en
fricción observada. Ninguna lo hizo aún. DEFER.

---

## 4. Mejoras implementadas

**Ninguna de código/runtime.** Único artefacto: **este documento** (registro de decisión).
Governor sobre "crear reporte docs-only sin cambio de runtime": `ACCEPT_WITH_LIMITS`,
risk 0/5, sin aprobación humana → *"proceed within limits; validate with quick +
healthcheck"*. Cumplido.

## 5. Mejoras rechazadas / diferidas

- **REJECT:** E (Codegraph) — dep externa sin evidencia.
- **DEFER:** C (Clarity/Resilience — medir primero), F (Anti-repetition — sin fricción observada).
- **NO_CHANGE:** A, B, D — ya implementados o duplicarían subsistemas existentes.
- **Heredado de F35 (pendiente, no en este alcance):** No-JS Render Audit (ADAPT),
  engram-cloud-sync (DEFER), Modo Diagnóstico / Simplicity First (ADOPT doctrina).

## 6–10. Costo-beneficio · Riesgos · Evidencia · Tests · Compatibilidad

- **Costo-beneficio:** implementar cualquiera de A–F tiene beneficio marginal ≤ costo
  (duplicación, boot, superficie) dado el estado v1.0.0-rc2. Beneficio neto **negativo**
  para adopción; **positivo** para documentar la decisión (evita re-litigar en una 3ª pasada).
- **Riesgos residuales:** ninguno introducido — cambio docs-only. Los WARN de baseline
  (2) son preexistentes y benignos.
- **Evidencia:** healthcheck, quick 36/36, score 86, 3 probes de reconciliación limpios,
  lectura de `architecture_decision.py`, `knowledge.registry.yaml`, F35, `.gitattributes`
  (ya existente — la falsa fricción CRLF/LF ya estaba resuelta).
- **Tests:** no se añadió código ⇒ no requiere tests nuevos. Validación: healthcheck +
  claim_linter + `compileall` (docs-only, proporcionalidad).
- **Compatibilidad proyectos:** 0 archivos de proyectos registrados tocados. Routing,
  paths, registries, hooks, output contracts y boot **sin cambios**.

## 11. Aprendizajes

1. El repo externo y ATLAS son **el mismo linaje**; ATLAS ya lo superó en la capa OS.
   "Converger hacia vibecoding" sería un retroceso.
2. **F35 ya había hecho esta comparación.** El valor de esta pasada fue *verificar con
   probes* que los candidatos A–F no abrieron ningún gap nuevo — y no re-implementar.
3. La mejor decisión de arquitectura, con el sistema estable, fue **no cambiar nada** y
   dejar registro para no repetir el análisis.

## 12. Memorias actualizadas

- Engram (proyecto `proyectosclaude`, obs id 27): aprendizaje confirmado guardado
  (source=este review, confidence=high, lifecycle=active). Conflict candidate no
  relacionado resuelto como `not_conflict`.
- Auto-memory: **nueva** entrada `architecture-review-vibecoding-nochange` (registro de
  esta decisión). **No** se modificó `atlas-vibecoding-unification` — al leerla completa
  resultó ser un deliverable distinto (paquete instalable "Atlas OS v2/v3" en
  `D:\ProyectosIA\atlas`, pendiente de install a `~/.claude`), ajeno a esta comparación.

## 13. Pendientes que requieren aprobación humana

| Item | Por qué | Governor |
|------|---------|----------|
| No-JS Render Audit (ADAPT) | toca QA de `evidence-collector`/`reality-checker` | measure-first |
| Codegraph / structured retrieval | dependencia + servicio externo | NEEDS_HUMAN_APPROVAL |
| engram-cloud-sync | acopla cloud + estado distribuido | NEEDS_HUMAN_APPROVAL |

## 14. Recomendación final

**ATLAS está estable (v1.0.0-rc2, CI verde, score 86) y no requiere ninguna de las
mejoras propuestas.** Las próximas mejoras deben originarse en **fricción real observada
en proyectos**, no en revisiones de auto-mejora. Recomendación: **detener el ciclo de
self-improvement de tooling** y priorizar uso en proyectos. Si en un proyecto concreto
aparece (a) grep costoso en repo grande → reconsiderar E; (b) flujo crítico sin manejo de
error → reconsiderar C/No-JS audit; (c) proyectos con misma estructura visual → reconsiderar F.
Hasta entonces: **NO_CHANGE**.
