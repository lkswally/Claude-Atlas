# F28 — Boot Loader Architecture Audit

**Fecha:** 2026-06-19
**Base:** ATLAS v1.0.0-rc2 (`781935d`)
**Modo:** auditoría read-only. **Sin código, sin commits, sin tocar dispatcher/registries/CI/tests.**
**Objetivo:** descubrir el **mínimo cambio arquitectónico** que reduce más tokens efectivos de bootstrap conservando 100% de la gobernanza.

> Tokens estimados con la heurística `chars / 4`. Lo que importa es el **orden de magnitud relativo**, no el valor exacto.

---

## 0. Hallazgo central (TL;DR)

El costo de boot **siempre-activo** de ATLAS es **`CLAUDE.md` (~8.7K tokens), inyectado en el 100% de las sesiones** — incluso en un "¿qué hora es?". De sus 544 líneas, **~63 son boot-esencial y ~480 (≈88%) son material de referencia/condicional** que no se necesita en cada arranque.

Los otros dos pesos pesados — `orquestador.md` (~28.7K) y `agent-protocol.md` (~27.1K) — **no entran al boot base**: se cargan condicionalmente (al activar modo orquestador / al spawnear un subagente). Son grandes, pero su costo se paga solo cuando corresponde.

**Conclusión:** el mínimo cambio de mayor impacto es **convertir `CLAUDE.md` en un boot loader delgado (índice)**, reubicando las secciones de referencia en archivos `*-reference.md` cargados on-demand (patrón que ATLAS **ya usa** para los 12 refs de agente). Esto recorta el boot always-on de **~8.7K → ~1.5K tokens (≈80%)** sin borrar nada: la gobernanza sigue existiendo, solo se carga cuando se la invoca.

---

## 1. Diagrama del bootstrap actual

```
SESIÓN NUEVA (cualquier tipo)
   │
   ▼
[SIEMPRE] CLAUDE.md  ── ~8.7K tokens, auto-inyectado (claudeMd)
   │   ├─ Dos modos (13 ln)            ◄ esencial
   │   ├─ Arquitectura (28 ln)         ◄ esencial
   │   ├─ Reglas clave (14 ln)         ◄ esencial
   │   ├─ Capacidades post-1K.2 (85 ln) ◄ CHANGELOG histórico (ruido always-on)
   │   ├─ Dispatcher Operativo (55 ln) ◄ solo orquestador
   │   ├─ Design Quality (54 ln)       ◄ solo tareas diseño
   │   ├─ Herramientas por agente (30) ◄ solo orquestador
   │   ├─ Stack adaptable (34 ln)      ◄ solo Fase 1
   │   ├─ Nothing/BetterAuth/Creativos ◄ condicional
   │   ├─ Best Practices (26 ln)       ◄ referencia
   │   └─ Overrides Windows (61 ln)    ◄ solo dev server Windows
   │
   ├─ (si "modo orquestador") ──► orquestador.md  ~28.7K tokens (1988 ln)
   │        └─ carga TODO: Boot+Memoria+Mod+Wiring+FASE 1..5+2B+Troubleshoot+Degradation
   │           aunque el usuario esté solo en FASE 1 (~70% prematuro)
   │
   └─ (cada subagente spawneado) ──► agent-protocol.md  ~27.1K tokens (2451 ln)
            └─ carga TODOS los contratos (1A..1L, F1, F2, 1H/1J/1K…)
               aunque el agente solo necesite Envelope + Engram core (~75% irrelevante por agente)
```

**Costo efectivo por tipo de sesión:**

| Tipo de sesión | Contexto de boot | Tokens aprox. |
|----------------|------------------|---------------|
| Pregunta simple / fix puntual (modo normal) | CLAUDE.md completo | **~8.7K** |
| Orquestador, Fase 1 | + orquestador.md completo | ~37.4K |
| Por cada subagente | + agent-protocol.md completo | +27.1K c/u |

---

## 2. Diagrama del bootstrap ideal

```
SESIÓN NUEVA
   │
   ▼
[SIEMPRE] CLAUDE.md (boot loader delgado)  ── ~1.5K tokens
   │   ├─ Dos modos de trabajo
   │   ├─ Regla de oro + Reglas clave (resumidas)
   │   ├─ Arquitectura (1 diagrama)
   │   └─ ÍNDICE → punteros a refs on-demand:
   │        claude-capabilities-reference.md  (changelog/capacidades)
   │        dispatcher-reference.md           (dispatcher ops)
   │        design-quality-reference.md
   │        stack-reference.md
   │        windows-overrides-reference.md
   │        best-practices-reference.md
   │        agent-tools-reference.md
   │
   ├─ (modo orquestador) ──► orquestador-core.md (~6K: Boot+Memoria+Regla oro+índice de fases)
   │        └─ resuelve fase → carga SOLO esa fase:
   │             fase-1-reference.md / fase-2 / fase-2b / fase-3 / fase-4 / fase-5
   │             modificacion-reference.md · troubleshooting-reference.md · degradation-reference.md
   │
   └─ (subagente) ──► agent-protocol-core.md (~5K: Engram 2-pasos + Envelope + reglas/límites universales)
            └─ resuelve clase de agente → carga SOLO sus contratos:
                 qa-contracts.md (1H/1J/1K) · design-contracts.md (1C/1L) · dev-contracts.md …
```

**Principio:** el boot carga un **índice + núcleo mínimo**; el conocimiento específico se resuelve por demanda (igual que el Capability Router resuelve MCPs hoy).

---

## 3. Árbol de dependencias (Boot → carga → recarga → innecesario)

```
CLAUDE.md  [SIEMPRE, ~8.7K]
 ├── apunta a orquestador.md (lazy, modo orquestador)
 ├── apunta a agent-protocol.md (lazy, subagentes)
 ├── apunta a 12× *-reference.md (lazy, ya correcto ✔)
 ├── DUPLICA con orquestador.md:
 │     · "Regla de oro" (CLAUDE.md §Arquitectura ≈ orquestador.md §212 Identidad)
 │     · Pipeline 5 fases (tabla en CLAUDE.md ≈ orquestador.md §629)
 │     · Engram protocolo (CLAUDE.md §Gestión de contexto ≈ orquestador.md §266 ≈ agent-protocol §1-2)
 │     · Hooks table (CLAUDE.md §Hook System ≈ healthcheck output)
 └── contiene DATOS DE REGISTRY en prosa (Herramientas por agente, Stack) que YA viven en
       config/*.yaml y podrían resolverse en vez de inlinearse.

orquestador.md  [lazy, ~28.7K]
 ├── recarga Engram protocol (ya en CLAUDE.md y agent-protocol)  ← TRIPLICADO
 ├── FASE 1..5 + 2B: solo 1 fase activa a la vez → ~70% prematuro
 └── Troubleshooting/Degradation: solo en error → casi nunca al boot

agent-protocol.md  [lazy por subagente, ~27.1K]
 ├── §1-3,5,8 núcleo universal (~25%)  ← lo único que todo subagente necesita
 └── §1H/1J/1K/1C/1L/F1/F2 contratos por clase (~75%)  ← un dev-agent no usa contratos de QA visual
```

**Duplicaciones detectadas:**
1. **Protocolo Engram (2-pasos + topic_key)** aparece en CLAUDE.md, orquestador.md y agent-protocol.md → **triplicado**. Debería vivir en un solo `engram-protocol-reference.md`.
2. **Regla de oro / Identidad del orquestador** en CLAUDE.md y orquestador.md.
3. **Pipeline de 5 fases** (tabla) en CLAUDE.md y orquestador.md.
4. **Tabla "Herramientas por agente"** en CLAUDE.md duplica datos de los frontmatter de cada agente + mcp.registry.
5. **Hook System table** en CLAUDE.md duplica lo que healthcheck ya reporta en runtime.

---

## 4. Tokens estimados por etapa

| Archivo | Chars | Tokens aprox. | Cuándo se paga | Esencial al boot | Reducible |
|---------|-------|---------------|----------------|------------------|-----------|
| **CLAUDE.md** | 34,913 | **~8,700** | **siempre (100% sesiones)** | ~1,000 (≈12%) | **~7,700** |
| orquestador.md | 114,661 | ~28,700 | modo orquestador | ~6,000 (Boot+core) | ~22,700 |
| agent-protocol.md | 108,426 | ~27,100 | cada subagente | ~6,800 (núcleo) | ~20,300 |
| pipeline-reference.md | 19,309 | ~4,800 | Fase 1 (stack) | — | parcial |
| mcp.registry.yaml | 20,518 | ~5,100 | on resolve | — | ya lazy ✔ |
| test.registry.yaml | 17,777 | ~4,400 | run_all/CI | — | ya lazy ✔ |
| capability.policy.yaml | 5,549 | ~1,400 | on resolve | — | ya lazy ✔ |

**Lectura clave:** el ahorro de mayor ROI no está en los archivos más grandes, sino en el **único always-on**: recortar CLAUDE.md ahorra ~7.7K tokens en **cada** sesión. Recortar orquestador/agent-protocol ahorra más en absoluto, pero solo en sesiones de pipeline.

---

## 5. Responsabilidades mezcladas

**`CLAUDE.md` hoy hace de:**
- Boot loader (modos, identidad) ✔ correcto
- Manual de referencia (stack, best practices, Windows, design quality) ✘ debería ser lazy
- Changelog histórico (Capacidades post-1K.2) ✘ no es contrato operativo
- Espejo de registries (herramientas por agente, hooks) ✘ duplica fuentes de verdad

**`orquestador.md` mezcla (esto valida la crítica F27.5 a nivel knowledge, no solo dispatcher):**
- **Bootstrap** (Boot Sequence, variables de estado)
- **Routing** (Request Routing, Phase Gates)
- **Policies** (qué debe existir antes de cada fase)
- **Prompting** (instrucciones detalladas por fase)
- **Knowledge** (stack, intent clarifier, edge cases)
- **Execution** (wiring de helpers, formato de respuesta)

Las 6 responsabilidades en un archivo de 1988 líneas que se carga entero.

**`agent-protocol.md` mezcla:** núcleo universal (Engram/Envelope/límites) con ~20 contratos específicos por bloc/clase de agente.

---

## 6. Oportunidades de lazy-loading (por impacto)

| # | Oportunidad | Mecanismo | Ahorro always-on | Riesgo |
|---|-------------|-----------|------------------|--------|
| 1 | **CLAUDE.md → boot loader + índice** | mover 11 secciones de referencia a `*-reference.md` | **~7.7K/sesión** | Bajo |
| 2 | Eliminar changelog "Capacidades post-1K.2" del boot | → `claude-capabilities-reference.md` | ~1.7K/sesión | Muy bajo |
| 3 | Dedup protocolo Engram (triplicado) | 1 solo `engram-protocol-reference.md` | ~varios K en pipeline | Bajo |
| 4 | orquestador.md → core + 1 ref por fase | resolver fase → cargar 1 fase | ~22K en orquestador | Medio |
| 5 | agent-protocol.md → core + contratos por clase | resolver clase de agente | ~20K por subagente | Medio |
| 6 | Tablas registry-mirror (herramientas/hooks) | resolver desde config/*.yaml en vez de inlinear | ~1K/sesión | Bajo |

**Las oportunidades 1, 2, 6 son "OS-layer": no tocan dispatcher ni pipeline behavior.** Son reubicación de markdown + índice. Las 4 y 5 tocan el conocimiento del pipeline (más valor absoluto, más cuidado).

---

## 7. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| **Pérdida de capacidad** si una ref no se carga cuando hace falta | El índice en CLAUDE.md debe tener **triggers explícitos** ("cargá X cuando Y"), como ya hacen los 12 refs actuales. Nada se borra; solo se reubica. |
| **Claude no sigue el índice** (no lee la ref) | Mantener boot-esencial inline (modos, reglas de oro, límites); refs solo para detalle. Los contratos *enforced* (dispatcher) no dependen de que Claude lea markdown — el dispatcher valida en runtime. |
| **Drift entre boot loader y refs** | El test F10 (sot-drift) ya vigila `.claude/` vs `agents/`; extender un check de "índice ↔ refs existentes" al healthcheck. |
| **Romper espejo `.claude/agents/` ↔ `agents/`** | Cualquier split debe respetar F10; sync_dist.py ya mantiene el espejo. |
| **Regresión silenciosa de gobernanza** | Cada fase valida con la red F24 (quick/release) + healthcheck antes de aceptar. |

**Riesgo de NO hacer nada:** el costo always-on crece con cada bloc nuevo agregado a CLAUDE.md; ya está en ~8.7K y la sección "Capacidades" crece monótonamente.

---

## 8. Capability Router → Knowledge Resolver (evaluación, sin implementar)

**Hoy:** `resolve_capability("browser")` → `Resolution(provider, status, fallback, action)` — abstrae **MCPs**.

**Evolución compatible (aditiva):** un segundo resolver con la misma forma:

```
Intent → resolve_knowledge("design") → KnowledgePack(ref_file, triggers, status) → Read on-demand
```

- **Por qué encaja:** el patrón índice→resolver→carga ya existe informalmente (los 12 `*-reference.md` con triggers en `AGENTS.md`/`CLAUDE.md`). Formalizarlo como `resolve_knowledge()` lo vuelve **declarativo y testeable** (igual que el MCP router tiene suites F16-F19).
- **Compatibilidad:** **no rompe nada** — es un módulo nuevo (`core/knowledge/resolver.py`) junto al de capabilities; los refs siguen siendo markdown. El boot loader llama al resolver en vez de inlinear.
- **No implementar ahora.** Es el destino de F31, habilitado una vez que el knowledge esté en packs (F29/F30).

**Veredicto:** sí, el router puede evolucionar a Knowledge Resolver sin romper compatibilidad, pero es el **último** paso, no el primero. El primer paso (CLAUDE.md índice) ni siquiera lo necesita.

---

## Plan evolutivo en fases (sin romper compatibilidad)

> Cada fase: cambio reubicación-only → validar quick+release+healthcheck → confirmar paridad de comportamiento → recién entonces avanzar. Reversible con `git revert`.

**F29 — CLAUDE.md como boot loader (mínimo cambio, máximo impacto)**
- Mover 11 secciones de referencia de `CLAUDE.md` a `*-reference.md` con triggers explícitos en un índice.
- Mantener inline: modos, regla de oro, reglas clave, arquitectura (1 diagrama), índice.
- **Resultado esperado:** boot always-on ~8.7K → ~1.5K (**≈80%**), cero capacidad perdida.
- **Validación:** healthcheck + check nuevo "índice ↔ refs existen"; F10 drift; quick/release.
- **No toca:** dispatcher, registries, CI, tests, pipeline behavior.

**F30 — Decomposición de conocimiento del orquestador**
- `orquestador-core.md` (Boot+Memoria+Regla oro+índice de fases) + 1 ref por fase + modificacion/troubleshooting/degradation.
- Dedup del protocolo Engram a un solo `engram-protocol-reference.md` (consumido por los 3).
- **Resultado:** orquestador carga ~6K core + 1 fase, no 28.7K.
- **Validación:** correr un proyecto de prueba por las 5 fases verificando que cada fase resuelve su ref.

**F31 — Knowledge Resolver formal**
- `core/knowledge/resolver.py` con `resolve_knowledge(intent|class)` → KnowledgePack; suites tipo F16-F19.
- agent-protocol.md → core + contratos por clase resueltos por el resolver.
- Capability Router y Knowledge Resolver conviven (mismo patrón, dos dominios).
- **Resultado:** subagentes cargan núcleo + sus contratos; boot de pipeline minimizado end-to-end.

---

## Comparación con la dirección de la industria (punto 8 del pedido)

| Sistema | Estrategia de contexto | ATLAS hoy | ATLAS post-F29/31 |
|---------|------------------------|-----------|-------------------|
| **Claude Code** | CLAUDE.md mínimo + Read on-demand + subagentes con contexto propio | CLAUDE.md pesado | ✔ alineado (índice + lazy) |
| **Cursor** | reglas cortas + retrieval por relevancia | inline monolítico | ✔ se acerca (resolver) |
| **Devin / agentes** | planner liviano + carga incremental por tarea | orquestador carga todo | ✔ core + fase-on-demand |
| **Vibecoding (upstream)** | refs con triggers + orquestador dividido | consolidado en monolitos | ✔ converge, **conservando** la capa OS que vibecoding no tiene |

ATLAS no necesita copiar vibecoding: necesita aplicar **context engineering** (índice + lazy + resolver) **sobre** su capa OS superior. El resultado es lo mejor de ambos: gobernanza declarativa (registries/CI/healthcheck/ADR) **+** boot liviano por demanda.

---

## Recomendación final

**El mínimo cambio de mayor impacto es F29: convertir `CLAUDE.md` en un boot loader delgado con índice.**

- Ataca el **único costo pagado en el 100% de las sesiones**.
- ~80% de reducción del boot always-on con **riesgo bajo** (reubicación de markdown, no lógica).
- **Cero pérdida de gobernanza**: todo sigue existiendo, cargado por demanda con triggers.
- Es la **precondición** natural para F30/F31 y para la evolución a Knowledge Resolver.
- No toca dispatcher, registries, CI ni tests — respeta todas las restricciones.

F30 y F31 son mayores en ahorro absoluto pero solo se pagan en sesiones de pipeline y conllevan más riesgo; van después, con la red F24 como respaldo.

**Pendiente de tu aprobación** antes de cualquier implementación (F29+).
