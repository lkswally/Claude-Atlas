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

## 1.5. Engram Strategy en Dispatcher (Bloque 1B.1)

**ESTADO HONESTO**: El dispatcher (`tools/atlas_dispatcher.py`) usa un **strategy pattern** para verificar cajones. **El default es `DiskFallbackStrategy` — NO es Engram MCP real**, es lectura directa de `.pipeline/{cajon}.md`.

Esta es **preparación arquitectónica** para la integración MCP real que llegará en Bloque 1B.2. NO confundir con "Engram operativo".

### Strategies disponibles

| Strategy | Real Engram | Cuándo se usa |
|----------|-------------|---------------|
| `DiskFallbackStrategy` | ❌ Lee `.pipeline/{cajon}.md` | Default — backward compat con 1A.11 |
| `CallbackStrategy` | 🟡 Depende del callback | Cuando el orquestador inyecta uno (futuro 1B.2) |

### Cómo inyectar un callback (preparación para 1B.2)

```python
from atlas_dispatcher import ATLASDispatcher

dispatcher = ATLASDispatcher(project_root)

def mi_callback_mcp(proyecto: str, cajon: str) -> dict:
    # En 1B.2: llamar mem_search() real via MCP
    result = mem_search(cajon, project=proyecto)
    if result.observation_id:
        return {"status": "found", "observation_id": result.observation_id}
    return {"status": "not_found"}

dispatcher.set_engram_callback(mi_callback_mcp, name="engram_mcp_real")
```

### Contrato del callback

- Recibe `(proyecto: str, cajon: str)`
- Retorna `dict` con `status`: `"found"` | `"not_found"` | `"timeout"`
- Puede agregar metadata: `observation_id`, `topic_key`, `error`, etc.
- Si el callback raisea excepción → dispatcher captura, mapea a `timeout`, hace fallback a disco con WARN

### Manejo de fallback

Cuando se inyecta callback con `use_disk_fallback=True` (default):
- Callback retorna `found` → se usa directamente
- Callback retorna `not_found` → se respeta (sin fallback)
- Callback retorna `timeout` o `ambiguous_project` → fallback a disco
- Callback raisea Exception → captura + fallback a disco

### LO QUE NO HACE 1B.1 (responsabilidad de 1B.2)

- ❌ NO conecta el MCP de Engram realmente
- ❌ NO valida cajones cross-machine
- ❌ NO maneja `observation_id` para `mem_get_observation`
- ❌ NO detecta `ambiguous_project` activamente

1B.1 solo prepara el plugin point. La integración real es 1B.2.

---

## 1.6. Engram MCP Real Connection (Bloque 1B.2 + 1B.5)

**ESTADO** (post-1B.5): Engram MCP real **operativo y auto-activado por default**. `ATLASDispatcher.__init__` intenta `enable_engram_mcp()` automáticamente. Si el binario `engram` está disponible, queda activo desde el boot. Si no, cae graceful a `DiskFallbackStrategy` sin romper nada.

### Status visible

Cada dispatcher expone `dispatcher.engram_mcp_status`:

| Valor | Significado |
|-------|-------------|
| `"active"` | Engram MCP real activado |
| `"disabled_by_env"` | `ATLAS_DISABLE_ENGRAM_MCP=1` en entorno |
| `"disabled_by_param"` | Construido con `auto_enable_mcp=False` |
| `"unavailable: {reason}"` | Binary no encontrado u otro error |
| `"disabled_default"` | Estado intermedio (no debería verse en runtime) |

El orquestador puede leer este atributo para decidir si loguear el estado al usuario. No hay logging automático ruidoso.

### Opt-out

Para tests o entornos donde no se quiere Engram MCP:

```python
# Por parámetro
d = ATLASDispatcher(project_root, auto_enable_mcp=False)

# Por env var (afecta a todos los dispatchers en el proceso)
os.environ["ATLAS_DISABLE_ENGRAM_MCP"] = "1"
d = ATLASDispatcher(project_root)
```

### Cómo activar manualmente (post-init)

A partir de 1B.5, el dispatcher activa auto. Si querés re-activar con parámetros distintos (ej. timeout custom):

```python
from atlas_dispatcher import ATLASDispatcher

dispatcher = ATLASDispatcher(project_root)
# Engram MCP ya está auto-activado si binary disponible
print(dispatcher.engram_mcp_status)  # "active" o "unavailable: ..."

# Re-activar con path explícito
success, message = dispatcher.enable_engram_mcp(binary_path="/usr/local/bin/engram")

# Re-activar con timeout custom (default 5s)
success, message = dispatcher.enable_engram_mcp(timeout_s=10.0)

# Re-activar sin disk_fallback (modo estricto — para tests)
success, message = dispatcher.enable_engram_mcp(use_disk_fallback=False)
```

### Resolución del binario (en este orden)

1. Parámetro `binary_path=` explícito
2. Env var `ENGRAM_MCP_BINARY`
3. `shutil.which("engram")` en PATH

Si ninguno funciona, `enable_engram_mcp()` retorna `(False, error_msg)` y **mantiene `DiskFallbackStrategy`** — no rompe el dispatcher.

### Comportamiento del bridge

| Resultado | Acción |
|-----------|--------|
| Engram retorna `found` | Source = `engram_mcp_real`, dispatcher usa directamente |
| Engram retorna `not_found` | Source = `engram_mcp_real`, autoritativo |
| Engram timeout (>5s default) | Status `timeout` → fallback a disk si `use_disk_fallback=True` |
| Subprocess crash | Retry 1 vez → si falla, status `timeout` → fallback |
| Binary no encontrado al activar | `enable_engram_mcp()` retorna `False`, mantiene disk |
| Handshake JSON-RPC falla | Subprocess se mata, retorna `timeout` → fallback |

### Garantías honestas

- ✅ **Backward compat total**: si no se llama `enable_engram_mcp()`, comportamiento idéntico a 1B.1
- ✅ **Opt-in explícito**: nada se activa automáticamente
- ✅ **Disk fallback como red de seguridad**: timeout/crash/binary missing NO se confunden con `not_found`
- ✅ **Singleton lazy**: subprocess se lanza solo al primer query, no en init
- ✅ **Cleanup**: `atexit` registra terminación limpia del subprocess

### Activación recomendada en orquestador

El orquestador debería llamar `enable_engram_mcp()` al boot:

```python
# En el flujo del orquestador (al inicializar el dispatcher)
success, msg = dispatcher.enable_engram_mcp()
if success:
    log("Engram MCP real activo")
else:
    log(f"Engram MCP no disponible, usando disk_fallback: {msg}")
# Sea cual sea el resultado, el dispatcher sigue operativo
```

### LO QUE NO HACE 1B.2 (gaps remanentes honestos)

- ❌ NO maneja `ambiguous_project` ni `recovery_token` (queda para 1B.3)
- ❌ NO hace cross-machine sync activamente (Engram lo soporta nativo, pero ATLAS no lo invoca aún)
- ❌ Heurística de parseo de output de Engram es text-based + `structuredContent` opcional — robusta pero no perfecta

### Bloque 1B.4: 2-step pattern real (mem_search + mem_get_observation)

A partir de 1B.4 el bridge expone también `mem_get_observation(observation_id)`, segundo paso del patrón canónico. El dispatcher provee el helper consolidado:

```python
full = dispatcher.get_cajon_full("atlas-audit", "atlas/bloque-1a16-file-declaration")
# full["status"] in {"found", "not_found", "timeout", "inconsistent"}
# full["content"] = texto completo (NO preview truncado)
# full["title"], full["type"], full["topic_key"] cuando found
# full["step"] indica en qué paso terminó (search | get_observation | search_only)
```

**Reglas operativas**:
- `not_found` en step 1 → NO se invoca step 2 (skip optimization)
- `timeout` o `error` en cualquier paso → NUNCA se confunde con `not_found` (status explícito)
- Si search retorna `found` pero get_observation retorna `not_found` → status `inconsistent` (race condition / stale state, NO silenciado)
- Strategies que no soportan get_observation (ej. `DiskFallbackStrategy` sin cajón) → degrada a preview de search con `step="search_only"`

**LO QUE NO HACE 1B.4 (gaps que siguen abiertos)**:
- ❌ NO integra `get_cajon_full()` automáticamente desde el orquestador (los agentes deben invocarlo cuando necesiten contenido completo)
- ❌ NO expone `mem_save` / `mem_update` desde Python (los subagentes Claude escriben vía su runtime MCP)
- ❌ NO resuelve `ambiguous_project` (sigue siendo 1B.3)
- ❌ NO cachea resultados — cada `get_cajon_full()` hace 2 round-trips

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

## 3.6. Return Envelope QA — Estándar para evidence-collector (Bloque 1A.10)

Evidence-collector (agente de QA) usa una variante del Return Envelope Standard optimizada para validación. **STRICT MODE OBLIGATORIO** — el orquestador rechaza envelopes malformados.

### Formato OBLIGATORIO (evidence-collector, modo strict QA)

```
STATUS: PASS | FAIL
TAREA: Validé tarea {N}: {título corto}
ENGRAM: {proyecto}/qa-{N}
ARCHIVOS: {lista de rutas a screenshots: /tmp/qa/tarea-{N}-desktop.png, ...} [OBLIGATORIO si PASS; OPCIONAL si FAIL]
BLOQUEADORES: [lista de issues encontrados] [OBLIGATORIO si FAIL; PROHIBIDO si PASS]
VERIFICACION: layout
NOTAS: {resumen ejecutivo: qué pasó y qué no}
```

### Reglas estrictas (ENFORCEMENT)

**Si STATUS = PASS:**
- ✅ OBLIGATORIO: `status = "PASS"` (exacto)
- ✅ OBLIGATORIO: `tarea` (string)
- ✅ OBLIGATORIO: `engram` (string, formato `{proyecto}/qa-{N}`)
- ✅ OBLIGATORIO: `archivos` (lista NO VACÍA — al menos 1 screenshot)
- ❌ PROHIBIDO: `bloqueadores` (no incluir, o [] = ERROR)
- ⚠️ OPCIONAL: `verificacion`, `notas`

**Si STATUS = FAIL:**
- ✅ OBLIGATORIO: `status = "FAIL"` (exacto)
- ✅ OBLIGATORIO: `tarea` (string)
- ✅ OBLIGATORIO: `engram` (string, formato `{proyecto}/qa-{N}`)
- ✅ OBLIGATORIO: `bloqueadores` (lista NO VACÍA — al menos 1 issue)
- ⚠️ OPCIONAL: `archivos` (puede estar vacío)
- ⚠️ OPCIONAL: `verificacion`, `notas`

### Validación (qué sucede si hay error)

| Condición | Error exacto | Acción |
|-----------|------|--------|
| PASS sin `archivos` | "Return Envelope QA inválido: PASS requiere archivos (lista no vacía)" | Redel evidence-collector |
| PASS con `archivos: []` | "Return Envelope QA inválido: PASS requiere archivos (lista no vacía)" | Redel evidence-collector |
| PASS con `bloqueadores` ≠ null | "Return Envelope QA inválido: PASS prohibe bloqueadores" | Redel evidence-collector |
| FAIL sin `bloqueadores` | "Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)" | Redel evidence-collector |
| FAIL con `bloqueadores: []` | "Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)" | Redel evidence-collector |
| `status` ∉ {PASS, FAIL} | "Return Envelope QA inválido: status inválido: {valor}, esperado PASS o FAIL" | Redel evidence-collector |
| `archivos` no es lista | "Return Envelope QA inválido: archivos debe ser lista, recibido {type}" | Redel evidence-collector |
| `bloqueadores` no es lista | "Return Envelope QA inválido: bloqueadores debe ser lista, recibido {type}" | Redel evidence-collector |

**Campos obligatorios para evidence-collector**:
- **STATUS**: PASS o FAIL solamente. Nada de "CERTIFIED", "PENDING", etc. PASS = todas las validaciones pasaron. FAIL = al menos un criterio de aceptación falló.
- **TAREA**: Identificar qué tarea se validó (ej: "Tarea 3: Auth UI — Login form")
- **ARCHIVOS**: Rutas a screenshots (en /tmp/qa/, no inline). Si mobile, incluir screenshot de mobile también.
- **ENGRAM**: Guardar resultado en `{proyecto}/qa-{N}` con todo el contenido: screenshots (rutas), issues (si FAIL), rating, checklist results.
- **BLOQUEADORES**: Si FAIL, listar issues concretos (ej: "scroll-h no deseado en mobile", "font-size < 16px en inputs", "Mixed Content warning en consola"). Sin esto, el dev-agent no sabe qué arreglar.

### Ejemplo 1: QA PASS

```
STATUS: PASS
TAREA: Validé tarea 2: Hero section con animación Aurora
ARCHIVOS: /tmp/qa/tarea-2-desktop.png, /tmp/qa/tarea-2-mobile.png
ENGRAM: atlas/qa-2
VERIFICACION: layout
NOTAS: Rating A. Mobile responsive OK. Aurora animation smooth 60fps. 0 console errors. Ready para siguiente tarea.
```

### Ejemplo 2: QA FAIL

```
STATUS: FAIL
TAREA: Validé tarea 5: Navigation — componente Navbar
ARCHIVOS: /tmp/qa/tarea-5-desktop.png, /tmp/qa/tarea-5-mobile.png, /tmp/qa/tarea-5-mobile-scroll.png
ENGRAM: atlas/qa-5
VERIFICACION: layout
BLOQUEADORES: [scroll-h-unintended-mobile, touch-targets-too-small, color-contrast-wcag-fail-on-dark]
NOTAS: Rating C+. Mobile: horizontal scroll cuando no debería (nav items overflow). Touch targets 32px (min 44px requerido). Color contrast en dark mode viola WCAG AA. Requiere reintento.
```

### Validación de tarea en evidence-collector

Checklist mínimo que evidence-collector DEBE verificar antes de devolver PASS:

1. **Build**: `npm run build` sin errores (si la tarea lo requiere)
2. **Server**: URL reportada por dev-agent responde con 200
3. **Console**: 0 console errors (warnings OK, pero flagear en NOTAS si hay muchos)
4. **Responsive**: Mobile responsive checklist:
   - ✅ Sin scroll horizontal no deseado
   - ✅ Font size ≥ 16px en inputs (móvil)
   - ✅ Touch targets ≥ 44px × 44px (móvil)
   - ✅ No parallax sin guard en mobile (parallax fijo causa scroll-h)
5. **Accessibility**: WCAG 2.1 AA mínimo (heading hierarchy, alt text, color contrast, focus states)
6. **Spec**: Criterios de aceptación de {proyecto}/tareas[N].acceptance_criteria — todos cubiertos
7. **Visual**: Matches visual-direction choices (colores, tipografía, nivel animación)

Si ALGÚN checklist item falla → STATUS: FAIL + BLOQUEADORES con lista concreta.

### Integración con Fase 3 loop

Evidence-collector es invocado por el orquestador en Paso 5 del loop Fase 3 (ver orquestador.md línea 1247). El Return Envelope QA es leído por el orquestador para decidir:
- PASS → avanzar a siguiente tarea (tarea N completada)
- FAIL → re-delegar a dev-agent con feedback (intento N+1)
- FAIL × 3 → escalar al usuario

---

## 3.7. Pre-Return Audit — OBLIGATORIO + ENFORCED (Bloque 1A.14 + 1A.15 + 1A.16)

Todo dev-agent (frontend-developer, backend-architect, rapid-prototyper, mobile-developer, xr-immersive-developer, build-resolver) DEBE:

1. Ejecutar `tools/pre_return_audit.py` sobre los archivos modificados ANTES de emitir el Return Envelope (Bloque 1A.14)
2. Incluir el resultado del audit como campo `pre_return_audit` en el Return Envelope (Bloque 1A.15)
3. El dispatcher re-verifica independientemente — si el agente miente o salta el audit, el envelope es rechazado (Bloque 1A.15)
4. **El campo `archivos` debe ser un SUPERSET real de los archivos modificados según git** (Bloque 1A.16): el dispatcher ejecuta `git diff --name-only HEAD` + untracked files y exige que cada archivo modificado (post-exclusiones) esté declarado. Over-declaration permitida; under-declaration rechazada.

### Reglas para `archivos` (Bloque 1A.16)

- **Listar TODO archivo modificado**: incluso si solo agregaste un import, debe estar en la lista
- **Untracked files cuentan**: archivos nuevos no committed también deben declararse
- **Paths excluidos automáticamente**: `.pipeline/`, `_qa/temp/`, `node_modules/`, `dist/`, `build/`, `.claude/worktrees/`, `.next/`, `.cache/` — estos NO necesitan declararse
- **Over-declaration OK**: si declarás un archivo que no modificaste, no falla
- **Sin git → soft-fail**: si el entorno no es repo git, la verificación se omite con WARN (no BLOCK)

### Qué hace

Audita los archivos listados en `archivos` del envelope aplicando 6 reglas:

**BLOCK (impiden el envelope — corregir antes de devolver):**
1. `debugger` / `debugger;` en archivos NO-test
2. `breakpoint()` en archivos Python NO-test
3. `.only(` / `.skip(` en archivos test/spec
4. Hardcoded secrets (api_key, password, secret, Bearer, sk-*, ghp_*, AKIA*)

**WARN (informativos — incluir en `notas`):**
5. `console.log/warn/error` fuera de tests y dev-utilities (`tools/`, `_qa/`, `scripts/`, `.claude/`)
6. `TODO` / `FIXME` / `HACK` recién agregados (detectado vía `git diff HEAD`)

### Cómo invocarlo

```bash
# Auditar archivos del envelope
python tools/pre_return_audit.py src/foo.ts src/bar.tsx

# O leer la lista del envelope JSON
python tools/pre_return_audit.py --files-from envelope.json
```

### Salida (JSON a stdout)

```json
{
  "ok": true,
  "block_findings": [],
  "warn_findings": [
    {"rule": "console_log", "severity": "WARN", "file": "src/foo.ts", "line": 17, "match": "console.log(...)"}
  ],
  "files_audited": ["src/foo.ts", "src/bar.tsx"],
  "summary": "PASS (0 blocks, 1 warns)"
}
```

Exit code: `0` si `ok=true`, `1` si hay BLOCK findings, `2` si error de uso.

### Reglas de enforcement (Bloque 1A.15)

| Resultado | Acción del dev-agent | Acción del dispatcher (validate_return_envelope mode="dev_strict") |
|-----------|---------------------|----------------------|
| `ok=true`, sin warns | Emitir envelope con campo `pre_return_audit` | Re-verifica audit, acepta si coincide |
| `ok=true`, con warns | Emitir envelope con `pre_return_audit` + warns en `notas` | Re-verifica audit, acepta si no hay blocks |
| `ok=false` (blocks) | **Corregir blocks primero, NO emitir envelope** | Rechaza envelope ("dev-agent debió corregir blocks ANTES") |
| `pre_return_audit` ausente | (no debe ocurrir) | Rechaza envelope ("pre_return_audit obligatorio") |
| Agente miente: declara `ok=true` sin correr audit | (no debe ocurrir) | Rechaza envelope ("MISMATCH: dispatcher encontró N blocks") |

### Campo obligatorio en Return Envelope (modo dev_strict)

```json
{
  "status": "completado",
  "tarea": "...",
  "archivos": ["src/foo.ts"],
  "engram": "atlas/tareas",
  "verificacion": "layout",
  "bloqueadores": [],
  "pre_return_audit": {
    "ok": true,
    "summary": "PASS (0 blocks, 1 warns)",
    "block_findings": [],
    "warn_findings": [{"rule": "console_log", "file": "src/foo.ts", "line": 17}]
  }
}
```

El campo `pre_return_audit` debe ser **idéntico** al output JSON de `tools/pre_return_audit.py` para los archivos listados en `archivos`. El dispatcher re-corre el audit y compara — si hay desajuste, rechaza.

### Ejemplo de integración en flow del dev-agent

```python
# Después de implementar la tarea
archivos_modificados = ["src/components/Header.tsx", "src/lib/api.ts"]

# OBLIGATORIO: correr audit antes de envelope
result = subprocess.run(
    ["python", "tools/pre_return_audit.py"] + archivos_modificados,
    capture_output=True, text=True
)
audit_report = json.loads(result.stdout)

if not audit_report["ok"]:
    # Hay BLOCK findings — corregir antes de emitir envelope
    # NO devolver envelope todavía
    for finding in audit_report["block_findings"]:
        # fix the issue at finding["file"]:finding["line"]
        ...
    # re-correr audit hasta que ok=true

# Incluir warns en notas si los hay
notas = ""
if audit_report["warn_findings"]:
    notas = f"Pre-Return Audit warns: {len(audit_report['warn_findings'])} (ver detalle en log)"

# Ahora sí emitir envelope
envelope = {
    "status": "completado",
    "archivos": archivos_modificados,
    "notas": notas,
    ...
}
```

### Casos exentos

El audit IGNORA automáticamente:
- Líneas de comentario (`//`, `#` al inicio) para reglas debugger/breakpoint/console
- Archivos test/spec (matches `(test|tests|spec|__tests__|.spec.|.test.)`) para regla debugger/breakpoint
- Archivos en `tools/`, `_qa/`, `scripts/`, `.claude/` para regla console.*
- Archivos no modificados (solo audita la lista pasada como args)

### Por qué importa

Sin este audit:
- Bugs triviales (debugger statements) llegan a evidence-collector → QA falla → retry caro
- Secrets hardcodeados pueden filtrarse a Git → security incident
- `.only()` en tests deja el test suite incompleto sin que nadie se entere

Con este audit ejecutado ANTES del envelope:
- 90%+ de issues triviales se atrapan en segundos (no minutos de QA)
- Ciclo dev↔QA se reduce (menos retries)
- Calidad mínima garantizada por enforcement, no por disciplina humana

---

## 3.8. Delegation Stop Rules (Bloque 1D.1)

ATLAS tiene un tracker advisory que cuenta tool calls del agente y activa flags cuando se exceden thresholds. **No bloquea** — emite WARN por stderr y persiste flags en `.pipeline/delegation-state.json`.

### Thresholds

| Threshold | Flag | Sugerencia |
|-----------|------|-----------|
| 5+ Reads consecutivas | `escalation_needed` | Considerar Explore agent o cambio de enfoque |
| 20+ tool calls sin Agent spawn | `pause_recommended` | Considerar delegar a subagente |
| 2+ archivos no-triviales modificados | `fresh_review_recommended` | Re-leer dependencias |

### Comportamiento

- **Sticky flags**: una vez activado, queda `True` hasta el próximo `Agent`/`Task` spawn (que resetea todos los flags y contadores)
- **Tools de lectura**: `Read`, `Glob`, `Grep` cuentan para `consecutive_reads`. Otras tools resetean el contador.
- **Tools de spawn**: `Agent`, `Task` resetean todo
- **Paths triviales excluidos** del conteo de archivos modificados: `.pipeline/`, `_qa/temp/`, `node_modules/`, `dist/`, `build/`, `.claude/worktrees/`, `.next/`, `.cache/`, `*.md`, `*.json`, `*.yml`, `*.txt`, `*.log`, `*.lock`
- **Path absoluto vs relativo**: el tracker normaliza paths absolutos contra `project_root` antes de chequear exclusiones
- **Fail-open**: si el tracker falla (state corrupto, subprocess error), NO rompe el flujo del agente

### Cómo leer el estado

```bash
# Status actual
python tools/delegation_tracker.py status

# Reset manual (uso en debugging)
python tools/delegation_tracker.py reset
```

O programáticamente:
```python
from delegation_tracker import DelegationTracker
tracker = DelegationTracker(project_root)
state = tracker.get_state()
if state["flags"]["escalation_needed"]:
    # ... reaccionar
warnings = tracker.active_warnings()
```

### Hook PostToolUse

Registrado en `.claude/settings.json` como `node .claude/hooks/delegation-tracker.js` con `async: true`. Se ejecuta tras cada tool call. **Fail-open por diseño** — si el subprocess Python falla o tarda >3s, no bloquea.

### LO QUE 1D.1 NO HACE

- ❌ NO bloquea tool calls (es advisory, emite WARN no error)
- ❌ NO integra con el orquestador agente automáticamente para reaccionar a los flags (capability disponible, falta wirear lectura desde el prompt)
- ❌ NO persiste contadores entre sesiones de manera intencional (`.pipeline/delegation-state.json` se sobrevive pero el spawn de Agent resetea, así que típicamente arranca en 0 cada sesión)

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

## 6. Design Intelligence Queries — Patrón Universal

### Qué es

Design Intelligence es un motor local (BM25) que recomendaciones de diseño basadas en la industria/tipo de proyecto. Vive en `~/.claude/design-data/search.js` con 8 CSVs de datos: styles, colors, typography, charts, landing, products, ux-guidelines, reasoning.

**Úsalo cuando**:
- ux-architect necesita fondación CSS parametrizada (Paso 0)
- ui-designer necesita dirección estética y componentes (Paso 0a-0b)
- frontend-developer necesita specs de motion/animation tiers (consultas opcionales)

**NO usar Design Intelligence para**:
- Componentes específicos (eso es 21st.dev)
- Refactoring de código existente
- Optimizaciones de performance

### Patrón de invocación

```bash
node ~/.claude/design-data/search.js "{tipo}" [opciones] -p "{proyecto}"
```

**Argumentos obligatorios**:
- `{tipo}`: industria/tipo de producto (ej: "mental-health", "e-commerce", "finance", "saas")
- `-p {proyecto}`: nombre del proyecto (para contexto de guardado)

**Opciones comunes**:
- `--design-system`: retorna recomendaciones de CSS foundation (default)
- `--domain chart`: retorna recomendaciones de data visualization (charts, SVG, canvas thresholds)
- `--domain ux`: retorna UX guidelines (accessibility, forms, interactions)
- `--domain preset`: retorna preset específico (mood_preset como argumento primario, ej: `"swiss-minimal"`)
- `--strict`: descarta sugerencias genéricas (teal-saas, default patterns)
- `-n {N}`: número máximo de resultados (default 1)

### Validación de resultado

**SIEMPRE validar** antes de usar:

```
Validación A — JSON bien formado
  IF JSON parse error:
    ❌ Reintenta query con --strict
    ❌ Si falla de nuevo, usa defaults + documentar fallback

Validación B — Campos obligatorios presentes
  REQUERIDOS: anti_patterns (array), style.name (string), colors (object)
  IF alguno missing:
    ❌ BLOQUEAR — el motor retornó respuesta incompleta

Validación C — No-generic check (SOLO para moods audaces)
  IF intent.mood_preset NOT IN [swiss-minimal, dashboard-dense]:
    AND style.name IN [teal-saas, minimal-generic, default-bootstrap]:
      ⚠️ ADVERTENCIA — proceder pero esperar guardrails T1-T7 (ui-designer línea 94)
      ALTERNATIVA: re-ejecutar con --strict --mood={mood_preset}

Validación D — Anti-patterns no-vacío
  IF anti_patterns.length == 0:
    ❌ BLOQUEAR — re-ejecutar con --strict
```

### Guardar a Engram (OBLIGATORIO)

```
mem_save(
  title: "{proyecto}/design-intelligence",
  topic_key: "{proyecto}/design-intelligence",
  type: "discovery",
  content: """
  **Tipo consultado**: {tipo}
  **Estilo detectado**: {style.name}
  **Validación**: {PASS | FALLBACK}
  
  Anti-patterns (OBLIGATORIOS):
  {listar array}
  
  Colores recomendados:
  {listar objeto}
  
  Tipografía:
  {pares tipográficos}
  """,
  project: "{proyecto}"
)
```

**Formato alternativo corto** (si memória está tight):
```
mem_save(
  title: "{proyecto}/design-intelligence",
  topic_key: "{proyecto}/design-intelligence",
  type: "discovery",
  content: "[JSON result stringified]",
  project: "{proyecto}"
)
```

### Manejo de errores

| Escenario | Acción |
|-----------|--------|
| Query retorna JSON vacío | Re-ejecutar con `--strict`. Si sigue vacío, usar defaults (Minimalism) + documentar fallback en Engram |
| Anti-patterns vacío | BLOQUEAR — el motor está roto. Informar a orquestador |
| Style genérico para mood audaz | ADVERTENCIA en Engram + proceder bajo responsabilidad. Guardrails T1-T7 pueden bloquear |
| Brand.json existe pero style incoherente | Consultar a orquestador antes de proceder (guardar issue en Engram) |

---

## 7. Anti-Generic 21st.dev Validation — Patrón Universal

### Qué es

21st.dev es un marketplace de componentes React. Los componentes son versátiles pero pueden ser genéricos (teal SaaS, default patterns) si se usan sin validación.

**Para evitar componentes genéricos**: aplicar validación PRE y POST consulta contra mood_preset, brand.json, anti_patterns.

### Cuándo usar 21st.dev

**Úsalo cuando**:
- frontend-developer necesita inspiración de componentes interactivos (hover states, micro-interactions)
- El handoff incluye `COMPONENT_SOURCE: 21st.dev`
- Proyecto requiere motion/animation tiers ≥4 (Framer Motion o GSAP)

**NO usar para**:
- Componentes básicos (botones, inputs) — generar custom
- Componentes que existan en shadcn/ui
- Clon de designs existentes sin creatividad

### Patrón de validación PRE-consulta (frontend-developer responsibility)

Antes de consultar 21st.dev, validar:

```
Validación 1 — Coherencia con Brand
  IF brand.json existe:
    VERIFICAR que mood_vector es audaz (luxury, editorial, immersive, etc.)
                OR design_variance ≥ 5
    IF mood_vector es minimal/corporate (ej: {swiss: 8, minimal: 6, luxury: 1}):
      ⚠️ 21st.dev puede ser overkill — usa custom CSS + Framer Motion simple
      PROCEED ONLY IF animation_intensity ≥ 4 AND no hay anti_patterns HIGH

Validación 2 — Anti-patterns
  READ anti_patterns array desde Design Intelligence
  IF consulting 21st.dev would violate any:
    ❌ SKIP 21st.dev — implementar custom
    EXAMPLE: si anti_patterns = ["gradient-overuse", "shadow-gloss"]
             y 21st.dev result tiene ambos → rechazar

Validación 3 — Motion tier coherence
  IF motion_intensity ≤ 3:
    ❌ SKIP 21st.dev (probablemente overengineered) — usar CSS + Framer Motion simple
  IF motion_intensity 4-6:
    ✅ 21st.dev OK pero validar que sea Framer Motion o CSS, no GSAP
  IF motion_intensity ≥ 7:
    ✅ 21st.dev OK, puede ser GSAP + Lenis + SplitText
```

### Patrón de consulta

```
Paso 1: Resolver library ID
resolve-library-id("21st.dev") → {library_id}

Paso 2: Consultar con constraints
query-docs(
  libraryId: {library_id},
  query: "{tipo de componente} hover state animation {mood_preset}"
)

EJEMPLO: "card component with scale hover animation for editorial design"
```

### Patrón de validación POST-consulta (adaptación)

Después de obtener componente de 21st.dev:

```
Paso 1 — Extraer código
  Leer el component code del resultado

Paso 2 — Verificar contra anti_patterns
  FOR each anti_pattern IN anti_patterns_HIGH:
    IF component contiene anti_pattern:
      ❌ RECHAZAR — no usar componente, implementar custom
      EJEMPLO: si anti_pattern="gradient-overuse"
               y component tiene `background: linear-gradient(...)`:
               → rechazar y avisar a user

Paso 3 — Adaptar colores a brand.json
  FOR each color property EN component:
    REEMPLAZAR con tokens de brand.json
    EJEMPLO: `--color-primary: #...` → `--color-primary: var(--brand-primary)`

Paso 4 — Adaptar tipografía
  IF typography.family en component != brand.json.typography_pair:
    REEMPLAZAR con brand fonts + sizes

Paso 5 — Adaptar spacing/sizing a design-foundation
  MAPEAR `padding`, `margin`, `gap` a escalas de css-foundation
  EJEMPLO: `padding: 24px` → `padding: var(--space-6)` (si --space-6 = 24px)

Paso 6 — Guardar descobrimiento
  mem_save(
    title: "{proyecto}/component-adaptation-21st.dev",
    topic_key: "{proyecto}/discovery-21st-{component-name}",
    type: "discovery",
    content: """
    **Componente**: {nombre}
    **Adaptaciones**: {lista}
    **Anti-patterns validados**: {PASS | FALLIDO}
    **Brand alignment**: {PASS | FALLIDO}
    """,
    project: "{proyecto}"
  )
```

### Manejo de bloqueos

| Caso | Acción |
|------|--------|
| 21st.dev component contiene anti_pattern | Rechazar componente. Implementar custom. Informar en Return Envelope |
| Colores no adaptables a brand | Implementar custom. Anti-generic guardrail es HARD |
| Motion tier incoherente (ej: GSAP para motion≤3) | Descartar y usar librería más simple (CSS, Framer simple) |
| Componente es SaaS generic pattern | Validar contra T1-T7 guardrails (ui-designer). Si falla, rechazar |

---

## 8. Límites universales (lo que NINGÚN subagente hace)

- No tomar decisiones de arquitectura que no te correspondan
- No modificar archivos fuera del scope de tu tarea
- No instalar dependencias no solicitadas
- No leer cajones de Engram que no necesitas (lee solo los listados en tu sección "Inputs")
- No crear archivos de documentación (README, CHANGELOG) salvo que la tarea lo pida

---

## 9. Anti-Loop Tracking (Intra-Sesión) — Enforcement (Bloque 1A.12)

**NIVEL**: Intra-sesión (previene loops dentro de la sesión actual). NO persiste entre sesiones aún.

**QUÉ ES**: Mecanismo para prevenir reintentos infinitos si un cajon falta persistentemente durante una sesión.

**CÓMO FUNCIONA**:
- Dispatcher mantiene contador `phase_gate_retries` por cajon
- Si cajon falta en enforce_phase_gate():
  - Intento 1: falta → añade a missing_cajones, incrementa counter
  - Intento 2: falta → añade a missing_cajones, incrementa counter
  - Intento 3+: falta → ESCALACIÓN (no re-delega, escala a usuario)

**COMPORTAMIENTO POR INTENTO**:

| Intento | Contador | Acción | Resultado |
|---------|----------|--------|-----------|
| 1 | 0 → 1 | Añade cajon a missing, redel agente | Re-delegación con feedback |
| 2 | 1 → 2 | Añade cajon a missing, redel agente | Re-delegación con feedback |
| 3+ | 2+ | ESCALACIÓN (no añade a missing) | Requiere intervención usuario |

**ESCALACIÓN**: Si cajon sigue faltando tras 2+ intentos:
```
FASE X ESCALACIÓN (Max reintentos alcanzado):
  Cajones bloqueados tras 2+ intentos: {proyecto}/tareas (intento 3/max 2)
  Acción requerida: Usuario debe resolver manualmente o reasignar agente
```

**RESET DEL CONTADOR**:
- Si cajon aparece (found) después de falta → contador se resetea a 0
- Si Engram timeout + disk fallback existe → contador se resetea a 0
- Cuando cajon está OK en la siguiente gate check, el contador desaparece

**RESPONSABILIDAD**:
- Dispatcher: mantiene contador y decide escalación
- Orquestador: lee escalación_cajones y presenta opciones al usuario
- Usuario: resuelve (ej: crear cajon manualmente, reasignar agente, diferir tarea)

**LIMITACIÓN ACTUAL**:
- Counter es session-local (memoria del dispatcher)
- Si sesión termina → counter se pierde
- Si usuario retoma proyecto en sesión nueva → counter = 0 (reinicia)

**ANTI-LOOP ENTRE SESIONES** (futuro):
- Persistir counter en Engram/DAG State
- Cargar counter en Boot Sequence
- Detectar si cajon ya falló 2+ veces en sesión anterior
- Bloque 1A.13+: implementará persistencia entre sesiones
