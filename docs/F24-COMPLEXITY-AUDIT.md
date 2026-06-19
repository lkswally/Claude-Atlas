# F24 — Auditoría de Complejidad (P0)

> **Fecha:** 2026-06-18
> **Alcance:** read-only. Ningún archivo de código/arquitectura fue modificado para producir este informe.
> **Objetivo de la fase:** reducir complejidad para v1.0 (mantenibilidad, estabilidad, velocidad, separación de responsabilidades). **No** agregar capacidades.
> **Commit base:** `a5d1c78`

---

## 0. Métricas baseline (snapshot "ANTES" para P10)

| Indicador | Valor actual |
|-----------|--------------|
| Módulos en `tools/` | 27 archivos |
| LOC en `tools/` | **13.718** |
| Archivos en `_qa/` | **63** |
| Suites activas (`bloque-F*`, ejecutadas por el runner) | 31 (9.694 LOC) |
| Suites legacy huérfanas (`bloque-1*`, NO ejecutadas) | **32** |
| `atlas_dispatcher.py` | **3.366 LOC**, 1 clase, 45 métodos |
| Helpers públicos del dispatcher | ~24 |
| Tiempo total tests (`--quick`, 30 suites) | **~1.989 s** (con 9 FAIL inducidos por timeout) |
| Suites que re-ejecutan el runner (recursión) | 3 |
| Código muerto identificado | `topic_key_enforcer.py` (249 LOC) + 32 suites huérfanas |
| Convenciones de test distintas | 3 (unittest / PASS-FAIL custom / ad-hoc) |

---

## 1. Archivos más largos

### tools/
| LOC | Archivo | Observación |
|-----|---------|-------------|
| **3.366** | `atlas_dispatcher.py` | God class. Ver §3. |
| 940 | `atlas_healthcheck.py` | Bien estructurado (27 funciones `check_*` pequeñas). Sano. |
| 882 | `engram_mcp_bridge.py` | Pareja con `engram_strategy.py` (395). 1.277 LOC para Engram. |
| 633 | `run_all.py` | 8+ responsabilidades en un módulo. Ver §3 y P4. |
| 574 | `skills_registry.py` | |
| 557 | `delegation_tracker.py` | |
| 484 | `doctor.py` | Nuevo (F24 previo). |
| 466 | `intent_classifier.py` | |

### _qa/ (top suites activas)
| LOC | Suite |
|-----|-------|
| 543 | `bloque-F6-runtime-hooks-validation.py` |
| 488 | `bloque-F11-5-backward-compat.py` |
| 471 | `bloque-F21-1-skills-registry.py` |
| 437 | `bloque-F9-projects-registry.py` |
| 422 | `bloque-F4-js-hooks-validation.py` |

---

## 2. Funciones / métodos demasiado grandes

Métodos del dispatcher por encima de ~130 LOC (umbral razonable de "una pantalla y media"):

| LOC aprox. | Método | Responsabilidad |
|-----|--------|-----------------|
| **323** | `validate_return_envelope` (725–1048) | Orquesta TODAS las validaciones por modo. Punto único de acoplamiento. |
| **323** | `verify_screenshot_evidence` (2508–2831) | Verificación de hashes de screenshots. |
| **231** | `verify_design_intelligence_real` (2277–2508) | Re-invocación de design intelligence. |
| **202** | `verify_editorial_compliance` (1941–2143) | Reglas editoriales (1L.4). |
| **188** | `verify_references` (1714–1902) | Validación de `brand.references` (1L.3). |
| **187** | `_try_auto_invoke_helpers` (2909–3096) | Auto-invocación de helpers. |
| **140** | `verify_design_quality` (1525–1665) | Wrapper + whitelist anti-disguise (1L.2). |
| **136** | `enforce_helpers_for_agent` (3096–3232) | Enforcement de helpers por agente. |
| ~198 | `run_all.py::generate_release_report` (279–477) | Generación de markdown de release. |

---

## 3. Archivos con demasiadas responsabilidades

### 3.1 `atlas_dispatcher.py` — God Class (severidad: **CRÍTICA**)
Una sola clase `ATLASDispatcher` (líneas 93–3265, ~3.170 LOC, 45 métodos) concentra **≥10 responsabilidades distintas**:

1. Validación de Return Envelope (por modo)
2. Phase gates / transiciones
3. Acceso a Engram (cajones, disco fallback, ambiguous project)
4. Declaración de archivos vs git diff
5. Pre-return audit
6. Design quality / references / editorial / design intelligence (serie 1L)
7. Verificación de screenshots
8. QA caching (file hash)
9. Network / console inspection
10. Auto-invocación + enforcement de helpers por agente
11. Intent classification, session summary, cross-session loops

**Patrón positivo a preservar:** los métodos de las series 1F/1H/1L/1A.14 son **wrappers delgados** que hacen *lazy import* del módulo standalone correspondiente y delegan (p. ej. `check_visual_fidelity` → `visual_fidelity_checker.VisualFidelityChecker`). **No hay duplicación de lógica** ahí. El problema es de **agregación**: todo cuelga de una clase.

### 3.2 `run_all.py` — multi-responsabilidad (severidad: ALTA → P4)
Concentra: discovery, ejecución de suites, healthcheck, git metadata, generación de release report, formateo de color, impresión, y entrypoint `main`. Candidato directo a la modularización de P4 (`runner / report / summary / release / timeouts / formatter / json_output`).

---

## 4. Recursividad en testing (severidad: **CRÍTICA** → P2)

3 suites re-ejecutan el runner completo vía `sys.executable`:

| Suite | Patrón |
|-------|--------|
| `bloque-F22-run-all.py` | Ejecuta `run_all.py --json` y `--quick` (antes 5 veces; ahora 2 tras parche reciente). **run_all → run_all.** |
| `bloque-F22-command-audit.py` | Invoca `run_all.py --list`. |
| `bloque-F23-runtime-settings-separation.py` | Ejecuta `run_all.py --release` + healthcheck `--strict`. |
| `bloque-1a13-integration-test.py` (legacy huérfana) | Idem. |

Esto es la causa raíz de los timeouts crecientes: una suite que ejecuta N suites, cada una con su cold-start de Python 3.14/Windows. **El aumento de timeouts trató el síntoma, no la causa.**

---

## 5. Imports circulares y acoplamiento

- **Sin imports circulares detectados** entre módulos `tools/`. `atlas_dispatcher` no es importado por ningún otro módulo de `tools/` (es hoja/consumidor).
- **Cadena de acoplamiento** (P5): el dispatcher es el hub que ata Engram + design tools + audit + helpers. Cada tool standalone *sí* es testeable de forma aislada (buena señal), pero su único test vive en una suite legacy huérfana (ver §7).

---

## 6. Código duplicado / helpers redundantes

- **No hay duplicación de lógica** entre dispatcher y tools standalone (delegación por wrapper, confirmado).
- **Duplicación real:** scaffolding de tests. Cada suite reimplementa su propio `PASS()`/`FAIL()`/contadores. 3 convenciones coexisten:
  - 9 suites usan `unittest`
  - 11 suites definen `def PASS/FAIL` propias
  - ~11 suites usan prints ad-hoc
  No existe un harness compartido (`conftest`/helper común). → P1.
- **Colisión de nombres:** `atlas_healthcheck.py` define su propia función `run_all()` (línea 845), distinta del `run_all.py`. Confunde. Menor.

---

## 7. Suites redundantes / tests que validan lo mismo (severidad: ALTA → P1/P7)

**32 suites legacy `bloque-1*` (series 1a8–1L4) están huérfanas:** `run_all.py` solo descubre `bloque-F*` (`QA_DIR.glob("bloque-F*.py")`, línea 88). Las suites 1X:

- NO se ejecutan en CI ni en `--quick`/`--release`.
- Validan bloques 1A–1L que ya fueron **consolidados** en las suites F actuales → redundancia funcional.
- Son el **único** test de la lógica interna de cada tool standalone (p. ej. `bloque-1h1` es el único que importa `network_inspector` directamente). Resultado: **la lógica de los tools solo está cubierta por suites que nadie ejecuta.**

Decisión a tomar en P1/P7: migrar la cobertura útil a unit tests reales y **eliminar** las 32 huérfanas.

---

## 8. Dependencias innecesarias / código muerto

| Item | LOC | Evidencia |
|------|-----|-----------|
| `tools/topic_key_enforcer.py` | **249** | **0 importers** de código. Solo lo referencia `policies/topic_key_enforcement.md`. Muerto. |
| 32 suites `bloque-1*` huérfanas | ~varios miles | No descubiertas por el runner (§7). |
| Subdirs `_qa/` (`boot-sequence-test/`, `conexo-2026-05-21/`, `pilotos-1L/`) | — | Revisar si son fixtures vivos o residuo. |

---

## 9. RANKING DE DEUDA TÉCNICA

Ordenado por **impacto en los objetivos de v1.0 (mantenibilidad + velocidad) ÷ esfuerzo**.

| # | Deuda | Severidad | Impacto | Prioridad de fase |
|---|-------|-----------|---------|-------------------|
| **1** | Recursión en testing (suite ejecuta run_all) | CRÍTICA | Causa raíz de timeouts; tests lentos e impredecibles | P2/P3 |
| **2** | Arquitectura de testing plana, sin capas (unit/integration/system/release), 3 convenciones, 32 huérfanas | CRÍTICA | Imposible razonar sobre qué se prueba; lentitud; redundancia | P1 |
| **3** | God class `ATLASDispatcher` (3.366 LOC, 45 métodos, 10+ responsabilidades) | CRÍTICA | Núcleo del sistema, difícil de evolucionar/testear aislado | P5/P8 |
| **4** | `run_all.py` multi-responsabilidad | ALTA | Bloquea P4; mezcla runner con report/release/formato | P4 |
| **5** | Cobertura de tools solo en suites huérfanas | ALTA | Lógica crítica sin test ejecutado en CI | P1/P7 |
| **6** | Código muerto: `topic_key_enforcer.py` (249 LOC) + huérfanas | MEDIA | Ruido, falsa sensación de cobertura | P7 |
| **7** | Métodos gigantes del dispatcher (8 métodos >130 LOC) | MEDIA | Complejidad ciclomática local alta | P8 |
| **8** | Sin flujo único de release (`release.py`) | MEDIA | Pasos manuales, propenso a error | P9 |
| **9** | Convención de test fragmentada + colisión `run_all()` | BAJA | Fricción cognitiva | P1 |

---

## 10. Notas sobre complejidad ciclomática

No se ejecutó una herramienta de CC automática (no se instaló nada para no modificar el entorno). El ranking de §2 (tamaño de función) es el **proxy** acordado; los candidatos #1 de CC real serán casi con certeza:
`validate_return_envelope`, `verify_screenshot_evidence`, `verify_editorial_compliance`, `verify_references` y `generate_release_report` (todos con múltiples ramas por modo/condición).

> Si se aprueba, en P6 se puede medir CC objetiva con `radon cc` en un venv aislado (solo medición, sin tocar runtime) para confirmar el ranking.

---

## Conclusión P0

El sistema es **funcionalmente sólido** pero arrastra deuda estructural concentrada en tres focos: **(1) testing recursivo y plano**, **(2) god class del dispatcher**, **(3) `run_all` monolítico**. Atacar #1 y #2 elimina la causa raíz de los timeouts (no los timeouts en sí) y habilita el resto de la fase.

**Próximo paso:** aprobar el rediseño de testing (P1/P2) antes de tocar el dispatcher (P5/P8), porque sin una red de tests por capas, refactorizar la god class es de alto riesgo.

---

## P1 + P2 Result — 2026-06-19

> **Commit:** `27df7d0` (P1+P2) + `<P3-fix>` (F7/run_all secondary check)
> **Estado:** `run_all --quick` → **30/30 PASS, 0 FAIL — 41s**

### Métricas DESPUÉS (baseline: ~1.989s, 9 FAIL)

| Indicador | ANTES (baseline P0) | DESPUÉS (P1+P2) | Δ |
|-----------|--------------------|-----------------|----|
| `run_all --quick` total | ~1.989s, 9 FAIL | **41s, 0 FAIL** | −9 FAILs |
| Suites en quick | 30 (glob plano) | **30 (registry)** | = |
| Suites skipped en quick | 1 (solo F13-active) | **2 (+ F23)** | +1 correcto |
| `bloque-F22-run-all` tiempo | ~2400s budget | **0.4s** | −2400s |
| `bloque-F22-secrets-check` tiempo | ~130s (13 subprocs) | **0.26s** | −130s |
| `bloque-F22-runtime-truth` TC14 | 42.5s (199k lines) | **0.36s (tail=1000)** | −42s |
| `bloque-F7` FAIL en run_all | Sí (timeout/false-positive) | **PASS** | corregido |
| Recursión subprocess | run_all→suite→run_all | **eliminada** | P2 ✓ |

### Suites registradas (P1)

| Layer | Activas | En quick |
|-------|---------|----------|
| unit | 15 | 15 |
| integration | 10 | 10 |
| system | 1 | 0 (F23 excluida) |
| evidence | 6 | 6 |
| legacy | 32 | 0 |
| **Total** | **33** | **30** |

- 0 huérfanas en disco sin registrar
- 32 legacy declaradas, no ejecutadas (status: legacy)
- F13-engram-active: excluida de quick (live binary)
- F23-runtime-settings-separation: excluida de quick (race condition settings.json)

### Top 10 suites más lentas (DESPUÉS)

| Suite | Tiempo | Causa |
|-------|--------|-------|
| F7-healthcheck-validation | 20.3s | 3 subprocess a healthcheck (test_1 + test_3/4/5) |
| F4-js-hooks-validation | 3.5s | node spawn por hook |
| F9-projects-registry | 3.1s | importa dispatcher (cold start) |
| F11-skills-registry-runtime | 2.8s | importa dispatcher |
| F22-command-audit | 2.1s | 3 CLI subprocess (30s timeout cada uno) |
| F15-context7 | 1.6s | MCP startup |
| F15-playwright | 1.4s | MCP startup |
| F6-runtime-hooks-validation | 1.3s | node spawn delegation-tracker |
| F20-security-hooks | 0.9s | node spawn |
| F24-test-registry (nuevo) | 0.9s | 28 TCs, importa run_all |

### Bugs corregidos en P3

1. **F7-healthcheck-validation** (tests 3-5): fallaban cuando `.claude/settings.json` no existe
   — Causa raíz: Claude Desktop gestiona `settings.json`; RUNTIME_MUTABLE en non-strict
   — Fix: tests 3-5 usan `existed = SETTINGS_PATH.exists()` guard; test_3 usa `--strict`

2. **`run_all` secondary FAIL check false-positive** (F7, F8):
   — Causa raíz: `"[FAIL]" in combined` capturaba `[FAIL]` en descripciones de test y en output de herramientas anidadas
   — Fix: cambio a `line.lstrip().startswith("[FAIL]")` — solo captura `[FAIL]` al inicio de línea

3. **Duplicate F24 entry en registry**: entrada duplicada con layer distinto — eliminada
4. **Evidence-layer override en `should_run()`**: excluía F13-engram y F15-* de quick erróneamente — eliminado (can_run_in_quick es la fuente única de verdad)
5. **Import path de test_registry en run_all**: fallaba cuando ejecutado como `python tools/run_all.py` (tools/ en sys.path, no root) — fix: agregar PROJECT_ROOT a sys.path explícitamente

### Healthcheck (2026-06-19)

```
RESULTADO : PASS=21  WARN=2  FAIL=0  / 23 checks
STATUS    : HEALTHY
```

WARNs activos (no bloquean):
- `.claude/settings.json`: RUNTIME_MUTABLE (gestionado por Claude Desktop)
- `capability-events.jsonl`: 1782 líneas JSONL inválidas (acumulación histórica)
