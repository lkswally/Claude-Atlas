# F27 — Architecture Criticism Verification + Capability Router Claim Audit

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (`afcc4b3`)
**Modo:** verificación de evidencia + correcciones documentales mínimas. **Sin features nuevas, sin refactor de dispatcher, sin migración masiva de agentes, sin borrar suites.**

---

## Resumen ejecutivo

Se verificaron 6 críticas externas contra evidencia real del repo. **3 son ciertas y se corrigen ahora** (todas documentales), **2 están mitigadas/son falsas y se documentan**, **1 es cierta pero diferida a v1.1** (sin bloquear el RC).

Ninguna crítica reveló un defecto funcional. Los problemas reales eran de **honestidad documental**: el README, CONTRIBUTING y GLOSSARY contenían afirmaciones absolutas ("no agent references raw MCP prefixes", "agents don't change") que la evidencia contradice.

---

## Veredicto por crítica

| # | Crítica | Veredicto | Acción |
|---|---------|-----------|--------|
| 1 | README afirma "no raw MCP" pero agentes contienen `mcp__` | **CIERTA (doc)** | Corregido wording en README/CONTRIBUTING/GLOSSARY |
| 2 | Migración del capability router incompleta | **CIERTA (esperado)** | Documentado como migración progresiva, no total |
| 3 | Test runner caótico / suites legacy | **MITIGADA (F24)** | Documentado estado actual; sin renombrar/borrar |
| 4 | Release gate sobrediseñado/pesado | **FALSA (matizada)** | Política de gates clarificada en README |
| 5 | Dispatcher monolítico | **CIERTA (diferida)** | Entrada ROADMAP v1.1, sin refactor ahora |
| 6 | Docs prometen más de lo que cumple | **CIERTA (puntual)** | Corregidos 4 claims; resto verificado OK |

---

## F27.2 — Auditoría real de prefijos `mcp__`

**Total: 36 ocurrencias en 6 archivos** (idénticas en `.claude/agents/` runtime y `agents/` dist, por el espejo F10).

| Archivo | Refs | Tipo | ¿Rompe invariante? |
|---------|------|------|--------------------|
| `evidence-collector.md` | 15 | Agente runtime QA (browser) | No — capability `browser` resuelve a `mcp__playwright__`; el agente documenta los tools que usa |
| `reality-checker.md` | 9 | Agente runtime QA (browser) | No — ídem, QA visual |
| `performance-benchmarker.md` | 5 | Agente runtime QA (browser) | No — ídem |
| `agent-protocol.md` | 4 | Documentación del protocolo | No — ejemplos del patrón capability + tool |
| `codepen-explorer.md` | 2 | Agente runtime (browser) | No — extracción CodePen vía Playwright |
| `frontend-developer.md` | 1 | Agente runtime (dev) | No — referencia puntual |

**Análisis:** todas las referencias están en **agentes de QA/browser** donde la capability `browser` resuelve precisamente a `mcp__playwright__*`, más `agent-protocol.md` que documenta el patrón. Son **uso legítimo documentado**, no llamadas crudas que evadan el router. **Ninguna rompe un invariante.** El router existe y funciona (suites F16-F20 verdes); lo que no existe es una migración 1:1 que elimine todo prefijo crudo — y nunca se prometió que existiera, salvo en el wording corregido aquí.

**Qué se corrige ahora:** solo documentación (ver F27.1). **Qué queda como deuda futura:** migración progresiva opcional de los agentes QA a un wrapper de capability (no urgente; el acoplamiento actual a Playwright es aceptable y está aislado en 6 archivos).

---

## F27.1 — Claims corregidos

| Archivo | Antes | Después |
|---------|-------|---------|
| `README.md:52` | "agents call `resolve_capability(...)`, **not a raw MCP tool**" | Abstracción disponible para nuevas integraciones + migración progresiva; algunos agentes aún referencian MCP directo, que la capability resuelve. No es migración total completada. |
| `CONTRIBUTING.md:29` | "**No agent file references raw MCP tool prefixes** — always use capability names" | Nuevas integraciones prefieren capability names; agentes existentes pueden referenciar MCP directo; migración progresiva. No agregar *nuevos* prefijos sin razón. |
| `CONTRIBUTING.md:23` | "exits 0 with **all 25 checks PASS**" | "exits 0 (HEALTHY) con **no FAIL** (WARNs documentados permitidos)" — healthcheck tiene 24 checks y admite WARNs |
| `GLOSSARY.md:39` | "If playwright is replaced, **agents don't change**" | Objetivo de diseño; agentes que usan `resolve_capability` no cambian; los que embeben prefijos crudos sí, hasta migrar |
| `GLOSSARY.md:275` | "**all 25 healthcheck checks** are green" | "all healthcheck checks are green (no FAIL)" |

Todos los demás usos de "never/always/all agents" revisados en README/CLAUDE.md/docs resultaron correctos o describían reglas reales (no sobrepromesas).

---

## F27.3 — Test runner / legacy (crítica MITIGADA por F24)

Estado verificado:
- **Runner declarativo:** `config/test.registry.yaml` declara cada suite, layer y timeout (32 active / 32 legacy).
- **Layers separados:** `--quick` = 30 suites (2 skipped por entorno), `--release` = 33 (active + healthcheck), `--full` incluye legacy.
- **Legacy registradas, no borradas:** 32 suites legacy conservadas para historia de regresión; no corren en quick.
- **CI verde:** CI Quick (push) y Release Validation (tag) en success sobre `v1.0.0-rc2`.

**Conclusión:** el "zoológico de tests" previo a F24 está **mitigado**. La crítica fue cierta históricamente; F24 la resolvió (registry declarativo + naming `bloque-F*` + layers). No se renombra ni borra nada en F27.

---

## F27.4 — Release gate (crítica FALSA, matizada)

El gate **no** es una carga innecesaria; tiene separación correcta de responsabilidades:

| Layer | Uso | Costo |
|-------|-----|-------|
| `--quick` | Desarrollo diario | ~40s |
| `--release` | Antes de publicar/taggear | ~60s |
| `--full` | Investigación/mantenimiento | mayor |
| CI Quick | Cada push a main | automático |
| Release Validation | Solo en push de tag | automático |

Se añadió al README (§12) una tabla explícita de **cuándo correr cada layer**, aclarando que `--release` **no** se necesita en el loop diario. Antes el README listaba ambos sin jerarquía clara; ahora la política es explícita.

---

## F27.5 — Dispatcher monolítico (CIERTA, diferida a v1.1)

- `tools/atlas_dispatcher.py` = **3.366 LOC**, el tool más grande del repo (siguiente: healthcheck 1.026).
- Mezcla validación de envelope, phase gates, E2E flows, design-quality y ~24 helpers públicos.
- **No bloquea v1.0.0-rc2:** estable, cubierto por la red de tests F24 (envelope/phase/contract verdes), comportamiento correcto. Es deuda de mantenibilidad, no defecto.
- **Precondición cumplida:** la red de regresión necesaria para un refactor seguro se construyó en F24.
- **Acción:** entrada **"v1.1 — Dispatcher Decomposition"** agregada a `ROADMAP.md` (split por módulos detrás de la misma API pública, una extracción a la vez validada contra suites F24). **No se refactoriza ahora.**

---

## Cambios aplicados en F27

**Solo documentación** (mínimos, seguros, reversibles con `git revert`):
- `README.md` — claim del capability router + tabla de política de gates
- `CONTRIBUTING.md` — claim de raw MCP + criterio de healthcheck
- `GLOSSARY.md` — abstracción del router + conteo de checks
- `ROADMAP.md` — entrada v1.1 Dispatcher Decomposition
- `docs/F27-CAPABILITY-ROUTER-CLAIM-AUDIT.md` — este informe

**No tocado:** código de agentes, dispatcher, suites, registries, CI, tags, releases.

---

## Deuda futura registrada (no bloquea RC)

1. **Migración progresiva** de los 6 agentes QA/browser a un wrapper de capability (opcional).
2. **Dispatcher decomposition** → v1.1 (ROADMAP).
3. Revisar periódicamente claims absolutos en docs nuevas (lint de "never/always/all" sugerido a futuro).
