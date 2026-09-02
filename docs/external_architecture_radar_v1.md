# External Architecture Radar v1 — Gentle AI v2.5.0 + GitHub Trending

**Fecha:** 2026-08-24
**Repo objetivo:** Claude-Atlas (`D:\ProyectosIA\ProyectosClaude`), `main`, HEAD final `34483fe`

> **Nota de premisa (importante).** El prompt original de esta tarea describía un
> "Contexto actual de Atlas" con capacidades (Decision Benchmark, Dangerous Command
> Policy, Diagnostic Mode, Failure Registry, Architecture State Model, Benchmark
> Karpathy V1, Controlled Experiment Loop) que **no existen en este repositorio**
> (verificado con grep exhaustivo, cero matches) y que tampoco corresponde al nombre
> usado en esta sesión ("ATLAS"/"Claude-Atlas", no "Codex-Atlas"). Se confirmó con el
> usuario que este es el repo correcto y que esa sección estaba mal — se procedió con
> el **estado real** de Claude-Atlas como baseline, no con la lista fabricada.

---

## 1. Baseline (protegido)

| Check | Resultado |
|-------|-----------|
| HEAD inicial | `43e54bd`, sync con origin |
| Working tree | Solo cambios externos preexistentes (`lucas-rojo-web/*`), excluidos de todo commit |
| Healthcheck | HEALTHY — 24 PASS / 2 WARN / 0 FAIL |
| Quick | 36/36 PASS |
| Secrets | exit 0 |

---

## 2. Estado real de Atlas (reemplaza la premisa fabricada)

Capacidades reales verificadas en este repo (usadas como base de comparación en vez
de la lista del prompt original):

| Capacidad real | Archivo | Rol |
|-----------------|---------|-----|
| Architecture Decision Governor | `tools/architecture_decision.py` | Clasifica propuestas ACCEPT_WITH_LIMITS/NEEDS_EVIDENCE/NEEDS_HUMAN_APPROVAL/DEFER/REJECT |
| Architecture Intelligence | `tools/architecture_audit.py` | Score de arquitectura, hotspots, decompose candidates |
| Claim Linter | `tools/claim_linter.py` | Flags de claims documentales sin evidencia (HIGH/CRITICAL) |
| Capability Router | `core/capabilities/router.py` (`resolve_capability`) | task→provider abstracto, con fallback |
| Capability Presence | `core/capabilities/registry.py` + `config/mcp.registry.yaml` + `tools/mcp_registry.py` | Estados LIVE/CONFIG_ONLY/CLI_ONLY/PENDING_TOKEN/DEFERRED_PAID/MISSING/NOT_RECOMMENDED |
| Dangerous Command blocking | `.claude/hooks/block-no-verify.js` | Bloquea `rm -rf`, `git --no-verify`, `DROP TABLE`, `chmod 777`, `curl\|sh` |
| Delegation Stop Rules | `tools/delegation_tracker.py` | Flags de escalación/pausa/fresh-review (Bloque 1D.1) |
| Boot Profiler | `tools/boot_profiler.py` | Costo de tokens always-on |
| Knowledge Resolver | `tools/knowledge_resolver.py` | Resolución lazy de refs por intención |
| Healthcheck | `tools/atlas_healthcheck.py` | 26 checks |
| CI | `.github/workflows/ci.yml`, `release.yml` | Verde, confirmado en múltiples pushes esta sesión |

**No existen:** un sistema de "Model Routing" dinámico por clase de tarea (solo
declaración estática Opus/Sonnet en frontmatter de cada agente), un "Diagnostic Mode"
nombrado como subsistema unificado, ni un "Failure Registry" estructurado persistente.

---

## 3. Gentle AI v2.5.0 — Reality Check

**Fuente:** `Gentleman-Programming/gentle-ai` release v2.5.0 (commit `f5dd1a6c`, MIT,
código público e inspeccionable — `cmd/`, `internal/`, `contracts/`, `skills/`, `e2e/`).

### Hallazgo principal: Receipt-Driven Development (RDD) — estable en v2.5.0

- **Proof-bounded review, versión real:** "One frozen candidate, one record. START
  freezes the candidate and one compact authority record." Pero — hallazgo clave —
  **v2.5.0 retira los compact receipts y el gate FINALIZE-after-evidence** (breaking
  change #1): "Delivery follows your repository's ordinary policy: hooks, tests, CI."
  El propio proyecto fuente se está alejando de la maquinaria pesada de receipts hacia
  delegar en CI/hooks estándar — **refuerza** la conclusión ya alcanzada en
  `docs/GENTLE-AI-V1.49-ARCHITECTURE-REVIEW.md` (NO_CHANGE/DEFER sobre receipts).
- **Deterministic Next Transition — real y verificado:** "START hands you the way
  back in... returns `start/v4` with `next_transition.execute(review.status)`... the
  orchestrator runs what the provider returned; it never reconstructs selectors from
  prose." Patrón concreto: el consumidor recibe UN paso ejecutable, no interpreta
  flags/prosa. **Este es el gap real confirmado en Atlas** (ver §9).
- **Provider Contract — real y maduro:** "Claude Code, Codex, OpenCode, and Pi share
  the Go provider contract" (bundle v1.1.0). Corroborado independientemente por
  `openclaude` (Trending, §4) — abstracción proveedor↔modelo probada en más de un
  proyecto real.
- **Release provenance:** archivos de provenance firmados (Minisign), "a local build
  reports that it has no provenance". Modelo de distribución de binario compilado —
  no aplica a Atlas (capa de configuración sobre Claude Code, no CLI binario firmado).
- **Fail-closed envelope versioning:** "gentle-pi builds up to 2.2.0... refuse this
  provider's envelopes by design" — filosofía fail-closed, opuesta al fail-open que
  Atlas adopta deliberadamente en todo el sistema (`ATLAS_*_DISABLED=1` en cada
  feature). Conflicto de filosofía, no solo de patrón.
- **Capability presence:** "Doctor classifies dangling ancestor symlinks..." — Atlas
  ya tiene una versión más granular (7 estados vs pass/fail simple).

---

## 4. GitHub Trending Radar

Filtrado estricto por categoría (agent orchestration/evaluation/verification/
guardrails/MCP/memory/observability/self-improvement/model routing/token
optimization/failure learning), **no por popularidad**. De 14 repos vistos en
`trending?since=daily`, solo 2 pasaron el filtro temático — el resto (PDF inspector,
video downloader, math animation engine, YouTube frontend, patent docs, LLM
from-scratch training) queda fuera de scope por categoría, no se forzó a 15
candidatos para llenar un cupo.

*Nota:* los star-counts reportados por la extracción inicial resultaron implausibles
para "trending diario" (ej. 245k/112k stars) — probable artefacto de resumen de la
página, no se usaron como señal de decisión; solo la descripción temática filtró.

| Candidato | Qué es | Relevancia | Clasificación |
|-----------|--------|------------|----------------|
| **openclaude** (`Gitlawb/openclaude`) | CLI de coding agent, 20+ providers unificados (MIT, real: 1,196 commits, CI real) | Corrobora que "Provider Contract" es un patrón maduro en otro proyecto independiente | **WATCH** — señal, no candidato de adopción directa (sería reemplazar/competir con Claude Code, fuera de alcance) |
| **ECC** (`affaan-m/ECC`) | Framework tipo-vibecoding para Claude Code: 68 agentes, 286 skills, memoria persistente. "Optimize the context window. Persist everything else." | Misma familia arquitectónica que Atlas — igual patrón ya visto en `claude-vibecoding` y `gentle-ai` | **WATCH** — mismo resultado que las 2 revisiones previas de esta sesión (Atlas ya tiene versiones equivalentes o más maduras de la mayoría del feature-set); no se justifica un tercer deep-dive feature-by-feature sin fricción real observada |

Análisis profundo: 3 (Gentle AI v2.5.0 + los 2 candidatos anteriores) de 5 permitidos —
no se forzaron 2 análisis adicionales sin relevancia real.

---

## 5. Matriz de comparación (FASE 3)

| Candidato | Fuente | Gap real Atlas | Atlas ya lo tiene | Beneficio | Riesgo | Complejidad | Tokens | Seguridad | Decisión |
|-----------|--------|-----------------|--------------------|-----------|--------|--------------|--------|-----------|----------|
| Deterministic Next Transition | Gentle AI v2.5.0 | **Sí, confirmado en código** (3 flags booleanos independientes, sin next-step único) | No | Alto (elimina ambigüedad real) | Bajo | Baja | ~0 | Ninguno | **ADAPT** ✅ implementado |
| Durable Review Receipts | Gentle AI v2.5.0 | Parcial | Evidence-collector + hooks + CI ya cubren delivery | Teórico | Medio | Media-Alta | Bajo | Ninguno | **REJECT** (el propio v2.5.0 los retira; ya DEFER en revisión v1.49) |
| Provider Contract / model routing dinámico | Gentle AI v2.5.0 + openclaude | Sí (solo declaración estática por agente) | Parcial (capability router existe para MCPs, no para modelos) | Alto potencial | Alto (toca selección de modelo en cada invocación) | Alta | Bajo | Ninguno directo, pero **prohibido por restricciones** de esta tarea ("no multi-model default") | **WATCH** — diseño futuro, no implementación ahora |
| Proof-Bounded Verification (QA) | Gentle AI v2.5.0 | Parcial (claim_linter cubre docs, no veredictos QA estructurados) | Parcial | Medio | Medio (toca contrato de evidence-collector) | Media | Bajo | Ninguno | **WATCH** — candidato válido para una futura adopción aislada, no esta vez (una mejora por commit) |
| Capability Presence Verification | Gentle AI v2.5.0 | No | **Sí, más maduro** (7 estados vs pass/fail) | — | — | — | — | — | **DUPLICATED** |
| Release Provenance / signing | Gentle AI v2.5.0 | No aplica (modelo de distribución distinto) | N/A | Bajo para Atlas | — | Alta | — | — | **REJECT** |
| Fail-closed envelope versioning | Gentle AI v2.5.0 | Conflicto filosófico (Atlas = fail-open por diseño) | — | — | Alto (rompe principio no-negociable) | — | — | Debilitaría fail-open | **REJECT** |
| Provider abstraction (openclaude) | Trending | Señal corroborante, no un recurso a adoptar | — | — | — | — | — | — | **WATCH** |
| ECC (framework completo) | Trending | Ninguno nuevo vs revisiones previas de esta sesión | Mayormente sí | — | — | — | — | — | **WATCH** |

---

## 6. Safe Adoption Gate — aplicado

Único candidato que pasó **todos** los gates de FASE 4: **Deterministic Next
Transition**. Detalle gate-por-gate:

| Gate | Resultado |
|------|-----------|
| Resuelve gap real | ✅ confirmado en código (3 flags sin next-step único) |
| No duplica capacidad madura | ✅ se deriva de flags existentes, no crea 6º sistema |
| No debilita Governance/Evidence/Dangerous Command Policy | ✅ no las toca |
| No rompe modo de análisis read-only | ✅ función pura, sin I/O más allá del state existente |
| No aumenta agentes | ✅ 0 agentes nuevos/modificados en prompt |
| No aumenta tokens sin beneficio | ✅ boot 1841→1841 (sin cambio) |
| Sin side effects implícitos | ✅ advisory-only, dispatcher no lo enforce |
| Sin hooks globales / auto-deploy / auto-commit / runtime autónomo | ✅ ninguno |
| Tests claros | ✅ 10 casos, test_11 |
| Rollback claro | ✅ `git revert`, campo aditivo en JSON |
| Implementable aislado | ✅ 1 función pura + 1 wiring point |

Provider Contract dinámico y Proof-Bounded QA fallaron el gate de "una mejora por
commit" / restricciones explícitas — quedan documentados como backlog (§9).

---

## 7. Candidato seleccionado (FASE 6)

**Deterministic Next Transition.** `adoption_score` cualitativo: beneficio real alto
(elimina una ambigüedad de código confirmada, no hipotética) + riesgo bajo +
complejidad baja + costo operacional ~0 — el criterio explícito de la tarea
("elegir el más seguro y útil, no necesariamente el más innovador") lo favorece
claramente sobre Provider Contract (más innovador, pero prohibido por las
restricciones de esta tarea y de mayor riesgo/complejidad).

---

## 8. Diseño, implementación, tests, KEEP/REVERT

Ver documento dedicado: **`docs/external_safe_adoption_design_v1.md`** (candidato,
gap, contrato, invariantes, failure modes, rollback — escrito ANTES de tocar código,
per FASE 7).

**Implementación (FASE 8):**
- `tools/delegation_tracker.py` — `derive_next_transition(flags) -> str`, wired en
  `_save_state()`.
- `.claude/agents/refs/orchestrator-delegation.md` §6 — ejemplo concreto reemplaza
  el `# ...` ambiguo.
- `_qa/bloque-1d1-validation.py` — `test_11_deterministic_next_transition`, 10 casos.

**Tests (FASE 9):**

| Suite | Resultado |
|-------|-----------|
| `_qa/bloque-1d1-validation.py` (incl. test_11 nuevo) | **11/11 PASS** |
| `run_all.py --quick` | **36/36 PASS**, sin regresión |
| `run_all.py --release` | **39/39 PASS**, sin regresión |
| `atlas_healthcheck.py` | HEALTHY — 24 PASS/2 WARN/0 FAIL, sin regresión |
| `secrets_check.py` | exit 0 |
| `claim_linter.py --summary` | 0 HIGH/0 CRITICAL — idéntico a baseline |
| `boot_profiler.py --report` (impacto tokens) | `always_on: 1841` — **idéntico** a baseline |
| `compileall` | exit 0 |
| `git diff --check` (archivos Atlas) | limpio |
| `atlas_verify.py` | 7/8 — **1 FAIL preexistente, no relacionado, confirmado con `git stash`** (ver §10) |

**KEEP/REVERT (FASE 10): KEEP.** Todos los criterios de éxito se cumplieron; el único
FAIL observado (`atlas_verify.py`) se confirmó preexistente en HEAD limpio antes de
cualquier cambio de esta tarea (mismo mensaje de error con y sin mis cambios) y no
está integrado al gate de CI/`run_all.py` — no se mezcló su reparación con esta
adopción, per regla explícita de la tarea.

---

## 9. ADOPT / ADAPT / WATCH / REJECT / DUPLICATED — resumen

- **ADOPT:** ninguno (ningún patrón se copió literalmente, todo lo implementado es
  reimplementación independiente sobre tooling propio).
- **ADAPT (implementado):** Deterministic Next Transition.
- **WATCH (backlog futuro, sin implementar):** Provider Contract / model routing
  dinámico por clase de tarea; Proof-Bounded Verification para veredictos QA
  estructurados; openclaude (señal, no recurso); ECC (mismo resultado que revisiones
  previas — sin gap nuevo).
- **REJECT:** Durable Review Receipts (el propio gentle-ai los retira en v2.5.0);
  Release Provenance/signing (modelo de distribución no aplica); Fail-closed envelope
  versioning (conflicto con el principio fail-open no-negociable de Atlas).
- **DUPLICATED:** Capability Presence Verification (Atlas ya tiene una versión más
  granular y madura — `mcp_registry.py` + `core/capabilities/router.py`).

---

## 10. Riesgos residuales

| Riesgo | Severidad | Nota |
|--------|-----------|------|
| `atlas_verify.py` `orquestador_boot_sequence` FAIL preexistente ("Paso 4a-4d" ausentes en `orquestador.md`) | LOW-MEDIUM | Confirmado preexistente (con y sin mis cambios), no forma parte del gate de `run_all.py`/CI. **No se corrigió en esta tarea** — mezclarlo hubiera violado la regla de "una mejora por commit" y "no mezclar reparación preexistente con cambios nuevos". Requiere una tarea separada de diagnóstico. |
| `next_transition` es advisory-only | INFO | El dispatcher no lo enforce todavía — es deliberado (fase de adopción incremental); una futura fase podría considerar hacerlo un check WARN-only en el healthcheck, solo si aparece fricción real de que el orquestador lo ignora en la práctica. |

Ningún riesgo introducido por el cambio implementado — ambos son preexistentes o
deliberadamente fuera de alcance.

---

## 11. Backlog futuro (NO implementar sin fricción real)

1. **Diagnosticar y corregir** `atlas_verify.py::orquestador_boot_sequence` — tarea
   separada, aislada, con su propio baseline/design/tests.
2. **Provider Contract / model routing dinámico** — solo si aparece evidencia
   concreta de que la asignación estática Opus/Sonnet por agente genera costo o
   calidad subóptima en un proyecto real. Diseño previo obligatorio (toca selección
   de modelo, gate MEDIUM-HIGH risk bajo el Architecture Decision Governor).
2. **Proof-Bounded Verification estructurado para evidence-collector** — solo si un
   veredicto QA demuestra afirmar más de lo que su evidencia soporta en un proyecto
   real (hoy no hay ese incidente documentado).
3. Reconsiderar `next_transition` como enforcement (no solo advisory) únicamente si
   se observa que el orquestador lo ignora en la práctica.

---

## 12. Entrega final

| Punto | Estado |
|-------|--------|
| Objetivo | Evaluar Gentle AI v2.5.0 + GitHub Trending, adoptar como máximo una mejora segura |
| Gentle AI analizado | ✅ release + código público (MIT) + breaking changes + contratos reales |
| Trending candidates | 2 (filtrado estricto por categoría, no por popularidad; resto excluido por fuera de scope) |
| Candidatos deep review | 3 (Gentle AI v2.5.0, openclaude, ECC) de 5 permitidos |
| ADOPT | Ninguno (0 código copiado) |
| ADAPT | Deterministic Next Transition (implementado) |
| WATCH | Provider Contract, Proof-Bounded QA, openclaude, ECC |
| REJECT | Durable Review Receipts, Release Provenance, Fail-closed envelope versioning |
| Candidato seleccionado | Deterministic Next Transition |
| Gap resuelto | 3 flags booleanos independientes sin next-step único → función determinística `derive_next_transition()` |
| Implementación | `tools/delegation_tracker.py` + `orchestrator-delegation.md` + tests |
| Impacto seguridad | Ninguno |
| Impacto estabilidad | Ninguno (advisory-only, 0 regresiones) |
| Impacto tokens/contexto | 0 (boot 1841→1841 idéntico) |
| Tests focales | 11/11 PASS (`bloque-1d1-validation.py`) |
| Decision Benchmark | No existe como sistema nombrado en este repo — N/A (ver §2 nota de premisa) |
| Suite global | Quick 36/36, Release 39/39 |
| KEEP / REVERT | **KEEP** |
| Commit/push | `34483fe`, pusheado a `origin/main` |
| Atlas CI | **success** (confirmado vía GitHub Actions API) |
| Riesgos residuales | 1 FAIL preexistente no relacionado (`atlas_verify.py`), documentado, no corregido a propósito |
| Próximo paso recomendado | Diagnóstico aislado de `atlas_verify.py::orquestador_boot_sequence` como tarea separada; el resto del backlog (§11) espera fricción real |
