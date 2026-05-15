---
name: agent-protocol
description: Protocolo compartido para TODOS los subagentes del sistema vibecoding. Engram, Return Envelope, reglas universales.
model: sonnet
---

# Protocolo de Subagentes — Referencia Compartida

Este archivo define los patrones que TODO subagente debe seguir. No dupliques este contenido en tu archivo — referéncialo.

---

## 1. Engram — Lectura (2 pasos OBLIGATORIOS)

NUNCA uses el preview de `mem_search` como dato final. Siempre completa los 2 pasos:

```
Paso 1: resultado = mem_search("{proyecto}/{cajon}")
        → retorna: preview TRUNCADO + observation_id

Paso 2: completo = mem_get_observation(observation_id)
        → retorna: contenido COMPLETO

Usar SOLO completo.content — NUNCA resultado.preview
```

Si `mem_search` no retorna observation_id → el cajón no existe. Manejo universal:

1. **Cajón critico** (inputs que necesitas para trabajar: `estado`, `tareas`, `css-foundation`, `design-system`, `security-spec`, `gdd`):
   - Buscar fallback en disco: `{project_dir}/.pipeline/{cajon}.md`
   - Si existe en disco: usar contenido del archivo y continuar
   - Si NO existe en disco: informar en Return Envelope `STATUS: fallido` con `BLOQUEADORES: [{cajon} no encontrado en Engram ni disco]`
   - NUNCA inventar datos ni usar defaults silenciosos para cajones criticos

2. **Cajón importante (re-delegable)** (`api-spec`):
   - Informar al orquestador que el cajón no existe — el orquestador re-delegará al agente productor (ej: backend-architect para api-spec)
   - NO continuar con defaults silenciosos para estos cajones; el orquestador decide si re-delegar o proceder sin él
   - Informar en NOTAS: "Cajón {cajon} no encontrado, requiere re-delegación"

3. **Cajón opcional** (`branding`, `discovery-*`):
   - Continuar con defaults razonables o sin esa información
   - Informar en NOTAS: "Cajón {cajon} no encontrado, usando defaults"

4. **Cajón de QA** (`qa-{N}`):
   - Marcar como "no validada" — no asumir PASS ni FAIL

---

## 2. Engram — Escritura (SIEMPRE con topic_key)

### Primera vez (crear observación):
```
mem_save(
  title: "{proyecto} — {descripción corta}",
  content: "{contenido estructurado}",
  type: "architecture",  // o decision, bugfix, pattern, discovery
  topic_key: "{proyecto}/{mi-cajon}",
  project: "{proyecto}"
)
```

### Actualizar observación existente:
```
Paso 1: mem_search("{proyecto}/{mi-cajon}") → obtener observation_id
Paso 2: mem_get_observation(observation_id) → leer contenido COMPLETO actual
Paso 3: Merge tu contenido nuevo con el existente (no sobrescribir ciegamente)
Paso 4: mem_update(observation_id, contenido_mergeado)
```

**REGLA CRÍTICA**: `topic_key` es OBLIGATORIO en todo `mem_save`. Sin él, los reintentos crean duplicados y el Engram se fragmenta. NO hay excepciones — si no tienes topic_key, NO llames mem_save.

### Manejo de error `ambiguous_project` (Engram v1.15.9+)

Si `mem_save({proyecto}/...)` retorna error con código `ambiguous_project` o mensaje `Project %q is not backed by known context`:

1. **NO retry inmediato con mismo payload** — fallaría idéntico
2. **Causa**: el proyecto no está enrolled (sin git remote conocido, sin `.engram/config.json`, sin sessions previas)
3. **Quién resuelve**: el orquestador es responsable de enrollment ANTES de delegar al agente. Ver `orquestador.md` § "Project Enrollment"
4. **Si el agente ya recibió la delegación y el orquestador no enrolló**: el error trae `recovery_token` y `available_projects` en el envelope. Reintentar UNA vez con:
   ```
   mem_save(
     title: "...",
     content: "...",
     type: "...",
     topic_key: "{proyecto}/...",
     project: "{proyecto}",
     project_choice_reason: "user_selected_after_ambiguous_project",
     recovery_token: "{token-recibido-en-error}"
   )
   ```
5. Si el reintento también falla → Return Envelope con `BLOQUEADORES: project '{proyecto}' no enrolled — orquestador debe crear .engram/config.json antes de re-delegar`

### Fallback a disco (si Engram no responde)

Si `mem_save` o `mem_update` falla (timeout, MCP no disponible, error):

1. Escribir el contenido a `{project_dir}/.pipeline/{cajon}.md` (crear directorio si no existe)
2. Continuar la tarea normalmente — no bloquearse por fallo de Engram
3. Informar en el Return Envelope: `NOTAS: Engram write failed, fallback to disk: .pipeline/{cajon}.md`

Al retomar un proyecto, el orquestador busca primero en Engram. Si no encuentra, busca en `.pipeline/`.

**NOTA**: Este fallback es un patrón que cada agente implementa individualmente (los agentes son prompts, no código — no hay forma de compartir un módulo). El patrón es simple: try mem_save → catch → fs.writeFile. No crear una utilidad compartida por esto.

### Topic_key: Formato y Ejemplos (OBLIGATORIO Phase 0.6A+)

A partir de Phase 0.6A, `topic_key` es OBLIGATORIO. No es una sugerencia.

**Formato**: `{proyecto}/{categoría}-{descripción-slug}`

**Ejemplos válidos**:
```
atlas/decision-boot-sequence-light-mode
atlas/discovery-dual-write-race-condition
atlas/bugfix-return-envelope-formatting
atlas/architecture-session-lifecycle
atlas/pattern-topic-key-upsert-strategy
atlas/config-engram-disk-fallback
```

**Estructura**:
- **{proyecto}**: nombre del proyecto (ej: `atlas`, `reyesoft`)
- **{categoría}**: tipo de observación (`decision`, `discovery`, `bugfix`, `architecture`, `pattern`, `config`, `learning`)
- **{descripción-slug}**: kebab-case, 2-4 palabras, descriptivo

**Por qué es obligatorio**:
1. Previene duplicados en reintentos
2. Facilita upserts (actualizar vs crear)
3. Hace searchable la memoria persistente
4. El orquestador usa topic_key para continuidad entre sesiones

**Si olvidas topic_key**:
- mem_save debe fallar o advertir: "topic_key is required. Format: {proyecto}/{categoría}-{descripción}"
- NO continuar con mem_save sin topic_key
- Informar en Return Envelope como bloqueador

---

## 3. Return Envelope — Formato estándar

Todo subagente retorna al orquestador con este formato EXACTO:

```
STATUS: completado | fallido | PASS | FAIL | CERTIFIED | NEEDS WORK
TAREA: {descripción corta de lo que se hizo}
ARCHIVOS: [lista de paths creados/modificados]
ENGRAM: {proyecto}/{mi-cajon} (topic_key usado)
SERVIDOR: puerto {N} (solo si levantaste servidor)
VERIFICACION: typo | layout | config | none
BLOQUEADORES: [lista] (solo si hay impedimentos para continuar)
NOTAS: {texto libre, máx 3 líneas}
```

- **STATUS** es el primer campo, siempre
- **ARCHIVOS** lista paths SIEMPRE relativos al proyecto (ej: `src/app/page.tsx`, NO `/home/user/project/src/app/page.tsx`)
- **ENGRAM** indica el cajón donde guardaste tu resultado
- **VERIFICACION** indica qué nivel de verificación requiere el cambio (ver tabla abajo)
- Omitir campos vacíos (no poner "SERVIDOR: N/A")

### Tabla de valores para VERIFICACION

| Valor | Cuándo usarlo | Acción del orquestador |
|-------|--------------|----------------------|
| `layout` | Cambios de UI, estilos, componentes, lógica nueva | Workflow completo: snapshot → navigate → screenshot |
| `typo` | Corrección de texto/copy en string estático, empty state, texto condicional | Un solo `preview_eval`: `document.body.innerText.includes("texto_nuevo")` → si `true`, PASS |
| `config` | Cambios en archivos no-UI: configs, tipos, API routes, env vars | Saltar verificación completamente |
| `none` | Sin servidor de preview activo, o cambio no observable en browser | Saltar verificación completamente |

**Agentes utilitarios** (codepen-explorer) pueden usar STATUS operacionales adicionales:
`OK | SAVED | FOUND | NOT_FOUND | BLOCKED` — siempre dentro del mismo formato de envelope.

---

## 3.5. Return Envelope Standard — Adopción Obligatoria

A partir de Phase 0.6A, el Return Envelope NO es opcional. Es el protocolo OBLIGATORIO de handoff entre orquestador y subagentes.

### Formato OBLIGATORIO (Estructura exacta)

```
STATUS: {valor}
TAREA: {descripción}
ARCHIVOS: {lista}
ENGRAM: {topic_key}
[SERVIDOR: puerto {N}]
[VERIFICACION: {nivel}]
[BLOQUEADORES: {lista}]
[NOTAS: {texto}]
```

**Orden de campos**: STATUS SIEMPRE primero. Otros campos en orden mostrado. Omitir campos vacíos (no poner "N/A").

### Ejemplos de Return Envelope correcto

**Ejemplo 1: Frontend development — PASS**
```
STATUS: PASS
TAREA: Implementé auth UI con Better Auth, validación de forms, error handling
ARCHIVOS: src/app/(auth)/login/page.tsx, src/components/LoginForm.tsx, src/lib/auth-client.ts
ENGRAM: atlas/phase-3-frontend-auth
VERIFICACION: layout
NOTAS: Todos los tests pasan. UI responsive en mobile. Ready para QA.
```

**Ejemplo 2: Backend API — Bloqueado**
```
STATUS: fallido
TAREA: Intenté implementar API de pagos con Stripe, pero falta STRIPE_SECRET_KEY en Engram
ARCHIVOS: [ninguno — no mergueado]
BLOQUEADORES: [stripe-key-missing] — STRIPE_SECRET_KEY debe estar en {proyecto}/security-spec
NOTAS: Esperando que security-engineer proporcione la key. Cambios en rama feature/stripe-api, listos para merge una vez desbloqueado.
```

**Ejemplo 3: Design — Descubrimiento con resultado**
```
STATUS: completado
TAREA: Validé design system contra 5 verticales usando ui-ux-pro-max-skill
ARCHIVOS: .claude/design-data/reasoning.csv (actualizado)
ENGRAM: atlas/discovery-design-consistency-b2b
NOTAS: Found 2 anti-patterns en B2B vertical. Documentado en reasoning.csv. ux-architect debe revisar antes de Fase 2B.
```

**Ejemplo 4: QA — CERTIFIED**
```
STATUS: CERTIFIED
TAREA: Reality-checker re-validó proyecto sobre 3 QA tests. Todos PASS. Listo para producción.
ARCHIVOS: [ninguno — cambios documentados en histórico]
ENGRAM: atlas/qa-reality-checker-phase-4
VERIFICACION: none
NOTAS: Mixed Content headers OK. Core Web Vitals >90. SEO score 92/100. Listo para Fase 5.
```

### Qué NO hacer en Return Envelope

❌ **NO hacer**:
```
STATUS: PASS

[Solo STATUS, sin más info — el orquestador no sabe qué se hizo]
```

❌ **NO hacer**:
```
STATUS: completado
ARCHIVOS: /home/user/proyecto/src/app/page.tsx, /home/user/proyecto/package.json

[Paths ABSOLUTOS — deben ser relativos: src/app/page.tsx, package.json]
```

❌ **NO hacer**:
```
STATUS: PASS
TAREA: Hice cambios varios
ARCHIVOS: [muchos archivos]
NOTAS: Ver el código para más detalles

[Demasiado vago — TAREA debe ser específica, ARCHIVOS debe ser lista concreta, NOTAS no debe remitir al código]
```

❌ **NO hacer**:
```
STATUS: PASS
BLOQUEADORES: [ninguno]
NOTAS: Sin notas

[Omitir campos vacíos — no poner "ninguno", "N/A", "Sin..."]
```

### Agentes que deben adoptar primero (Phase 0.6A)

Estos agentes lideran la adopción. El orquestador validará que usen Return Envelope Standard:

1. **ux-architect** (Fase 2, primer handoff)
2. **backend-architect** (Fase 3, APIs)
3. **frontend-developer** (Fase 3, UI)
4. **evidence-collector** (Fase 3, QA)

Los demás agentes adoptarán progresivamente en reintentos o siguientes tareas.

---

## 4. Proactive Saves (descubrimientos)

Si durante tu trabajo descubres algo no obvio (gotcha, incompatibilidad, patrón útil), guárdalo inmediatamente:

```
mem_save(
  title: "{proyecto} — {descubrimiento corto}",
  content: "**What**: {qué descubriste}\n**Why**: {por qué importa}\n**Where**: {archivos afectados}",
  type: "discovery",
  topic_key: "{proyecto}/discovery-{slug-descriptivo}",
  project: "{proyecto}"
)
```

No esperes al final de la tarea. Guarda al momento.

**NOTA**: Los discoveries se guardan para búsqueda futura via `mem_search`. No hay un agente agregador — el orquestador o el usuario pueden buscar discoveries con `mem_search("{proyecto}/discovery")` cuando necesiten contexto. También accesibles via `node ~/.claude/hooks/learning-index.js --search=keyword`.

---

## 5. Reglas universales (todos los subagentes)

1. **No arrancar servidores con Bash** → usar `preview_start` (solo aplica en Windows/Claude Desktop; en Linux/Claude Code CLI, usar Bash normalmente)
2. **No hacer git commit/push** → solo el agente `git` hace esto
3. **No deployar** → solo el agente `deployer` hace esto
4. **No usar imágenes de placeholder** (picsum.photos, lorem picsum, etc.) → usar assets reales del proyecto o generar con agentes creativos
5. **Asumir que no hay proceso corriendo en el puerto** → verificar/matar antes de levantar servidor
6. **Resúmenes cortos al orquestador** → nunca código completo, nunca archivos enteros
7. **No duplicar lo que ya está en Engram** → pasar topic_key, no contenido

---

## 6. Límites universales (lo que NINGÚN subagente hace)

- No tomar decisiones de arquitectura que no te correspondan
- No modificar archivos fuera del scope de tu tarea
- No instalar dependencias no solicitadas
- No leer cajones de Engram que no necesitas (lee solo los listados en tu sección "Inputs")
- No crear archivos de documentación (README, CHANGELOG) salvo que la tarea lo pida
