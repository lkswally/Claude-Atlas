# Protocol — Engram (read, strategy, MCP, write)

> Lazy reference extracted from agent-protocol.md in F32 (knowledge decomposition).
> Load when the protocol facade points here. Content verbatim — behavior unchanged.

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
- ❌ NO cachea resultados — cada `get_cajon_full()` hace 2 round-trips

### Bloque 1B.3: ambiguous_project / Project Enrollment Handling

A partir de 1B.3, el bridge detecta y propaga el caso en que Engram no puede resolver el proyecto del query (proyecto inexistente, ambiguo, o no enrolled). NO se confunde con `not_found` ni con `timeout`.

**Status nuevo**: `"ambiguous_project"` con metadata:

```python
result = dispatcher._check_engram_cajon("proyecto-x", "atlas/tareas")
# {
#   "status": "ambiguous_project",
#   "source": "engram_mcp_real",
#   "topic_key": "atlas/tareas",
#   "project_attempted": "proyecto-x",
#   "available_projects": ["atlas-audit", "claude-atlas", ...],
#   "recovery_token": "rt-abc123",  # si Engram lo provee
#   "engram_error_code": "unknown_project" | "ambiguous_project" | "not_enrolled",
#   "hint": "Use one of the available_projects values...",
#   "message": "Project '...' not found in store",
#   "note": "Engram no pudo resolver el proyecto..."
# }
```

**Resolución explícita** (`dispatcher.resolve_ambiguous_project`):

```python
# Tras recibir ambiguous_project, el caller elige un proyecto y reintenta
resolved = dispatcher.resolve_ambiguous_project(
    cajon="atlas/tareas",
    chosen_project="atlas-audit",  # de available_projects
    recovery_token="rt-abc123",    # opcional
)
# resolved["recovered_from_ambiguous"] = True
# resolved["chosen_project"] = "atlas-audit"
# resolved["status"] in {"found", "not_found", ...}  # ya resuelto
```

**Reglas operativas**:
- `ambiguous_project` se propaga **LIMPIO** por default — la `CallbackStrategy` NO cae a disk_fallback automáticamente (sería un parche silencioso falso). El caller decide qué hacer.
- Opt-in: `make_mcp_bridge_strategy(disk_fallback_on_ambiguous=True)` activa fallback en ese caso (la metadata original queda preservada en `ambiguous_project_metadata`).
- El parser detecta vía `error_code` canónico (`unknown_project`, `ambiguous_project`, `not_enrolled`, `project_not_found`) o vía heurística de texto (`"not backed by known context"`, `"ambiguous project"`, etc.).
- Otros `isError: true` NO se confunden con ambiguous (ej. `internal_error` se propaga como `EngramBridgeError → timeout`).

**LO QUE NO HACE 1B.3 (gaps que siguen abiertos)**:
- ❌ NO enrola proyectos nuevos automáticamente (sigue requiriendo intervención manual del usuario o de un bloque futuro 1B.6)
- ❌ NO resuelve proactivamente el warning del doctor (`session_project_directory_mismatch`) — solo detecta y propaga
- ❌ NO conecta el nuevo status con el flujo del orquestador agente (capability disponible pero los agentes no la consumen todavía)
- ❌ NO cambia comportamiento ante queries con proyecto explícito y enrolled (que es el caso mayoritario hoy)

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

