# Orchestrator — Recovery, Validation, Format, Health, Troubleshooting, Enrollment, Degradation

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Recuperacion Post-Compactacion

**Cubierto por el Boot Sequence** (ver seccion al inicio del archivo).

Si detectas que no hay historial de conversacion pero el usuario menciona un proyecto:
1. Ejecutar Boot Sequence → buscar DAG State en Engram
2. Informar al usuario que se retomo
4. Continuar — NO re-preguntar decisiones ya tomadas

Si el Boot Sequence no se ejecuto (ej: la compactación fue mid-conversacion):
1. Ejecutar Boot Sequence completo — no intentar recordar contexto previo.
2. `mem_search("{proyecto}/estado")` → `mem_get_observation(id)` → leer DAG State
3. Continuar desde la tarea/fase indicada en DAG State

## Validación post-retorno de subagente

> Formato del Return Envelope: `agent-protocol.md` §3.

Después de que un subagente retorna:
1. Verificar STATUS valido (dev/QA: completado/fallido/PASS/FAIL/CERTIFIED/NEEDS WORK; utilitarios: +OK/SAVED/FOUND/NOT_FOUND/BLOCKED)
2. Si ARCHIVOS → verificar existen. Si ENGRAM → confirmar con mem_search
3. Si invalido → max 2 intentos de reformateo. Si falla → loguear en `{proyecto}/discovery-envelope-fail-{agente}`, escalar
4. Solo entonces actualizar DAG State

---

## Formato de Respuesta al Usuario

**Inicio de proyecto:**
```
Proyecto: [nombre]
Tipo: [web | app | juego | api]
Modo: Vibecoding Pipeline

Fase 1 en progreso — delegando a Senior PM...
```

**Solicitud de decisión (escalación):**
```
⚠ DECISIÓN REQUERIDA

Tarea {N}: "{descripción}" falló 3 veces.
Último error: {qué falló}

Opciones:
  a) Reasignar a otro agente
  b) Descomponer en sub-tareas
  c) Diferir y continuar
  d) Aceptar con limitación documentada

¿Qué hacemos?
```

---

## Handoff Minimo a Subagentes

Template de handoff: ver Fase 3, paso 3. NUNCA pasar: historico de conversacion, resultados de otros agentes, codigo inline.

---

## Context Health Check (antes de CADA delegacion en Fase 3)

Antes de spawnear un subagente, verificar estos 3 puntos (~50 tokens):

1. **DAG State fresco**: ¿la tarea anterior ya esta registrada como completada en `{proyecto}/estado`?
   → Si no: hacer `mem_update` del DAG State ANTES de delegar la siguiente tarea
2. **Tarea actual marcada**: ¿la tarea que voy a delegar esta en `tareas_en_progreso` del DAG?
   → Si no: actualizar DAG State con `tarea_actual: {N}`

**Este check previene el caso critico**: delego tarea 6, olvido registrar que tarea 5 completo, la sesion se compacta → tarea 5 se pierde. Con el health check, tarea 5 SIEMPRE esta guardada antes de que tarea 6 arranque.

---

## Troubleshooting

- **Puerto ocupado**: indicar al subagente `lsof -ti:PORT && kill $(lsof -ti:PORT) || true` (Windows: `netstat -ano | findstr :PORT` + `taskkill /PID <pid> /F`)
- **Permisos Bash en background**: si subagente falla por permisos, ejecutar desde contexto principal
- **SEO → Frontend loop**: seo-discovery reporta issues → orquestador lanza frontend-developer → evidence-collector valida → seo-discovery re-verifica. **Máximo 2 iteraciones** (seo-discovery → fix → seo-discovery). Si después de 2 iteraciones el score no alcanza el mínimo, loguear issues pendientes en `{proyecto}/seo` y continuar a reality-checker con los issues documentados.
- **Subagente devuelve formato invalido**: pedir que reformatee usando su Return Envelope (max 2 intentos, luego escalar al usuario)
- **Engram timeout/lento**: si `mem_search` tarda >10s, verificar que Engram MCP server esta corriendo. Fallback: usar disco (`.pipeline/`)
- **Subagente crashea mid-tarea**: verificar Engram (`mem_search("{proyecto}/tarea-{N}")`) — si guardo resultado, continuar con QA. Si no guardo, re-delegar
- **Mixed Content en Fase 4**: si reality-checker detecta `http://` en codigo, verificar que el backend tiene HTTPS antes de re-deployar
- **api-spec faltante en Fase 4**: pedir a backend-architect que lo genere como tarea dedicada (no como parte de otra tarea)

## Project Enrollment (OBLIGATORIO antes del primer mem_save de un proyecto nuevo)

Desde Engram v1.15.9+ la validación rechaza `mem_save` con `project=` para proyectos no enrolled en el store/session/config. Para proyectos NUEVOS (sin git remote conocido ni `.engram/config.json`), el primer save fallará con `ambiguous_project` error.

**Acción obligatoria del orquestador en Fase 1, ANTES del primer `mem_save({proyecto}/...)`** (que típicamente es `{proyecto}/intent` en Paso 0):

1. Crear el directorio del proyecto si no existe: `mkdir -p {project_dir}`
2. Crear `.engram/config.json` para enrollment:
   ```bash
   mkdir -p {project_dir}/.engram
   echo '{"project_name": "{proyecto}"}' > {project_dir}/.engram/config.json
   ```
3. (Opcional, recomendado) inicializar git si va a ser un repo: `cd {project_dir} && git init`
4. Confirmar enrollment leyendo el archivo: `cat {project_dir}/.engram/config.json`
5. Recién entonces hacer el primer `mem_save` con `project: "{proyecto}"`

**Si el primer mem_save de todos modos retorna `ambiguous_project` error** (caso edge):
- El error trae `recovery_token` y `available_projects` en el envelope
- Reintentar el `mem_save` con: `project_choice_reason: "user_selected_after_ambiguous_project"`, `project: "{proyecto}"`, y el `recovery_token` recibido
- El reintento debe hacerse en la misma sesión (token corto-vivido)

**Para proyectos EXISTENTES** (ya con buckets en Engram, ej: `vetconnect`, `kahntus`, `dashboard-pm`): este paso es **innecesario** — el bucket ya está enrolled. Solo aplicar para proyectos cuyo nombre nunca apareció antes en `engram projects list`.

**Verificación rápida antes del Paso 0**: `engram projects list 2>/dev/null | grep -w "{proyecto}"` — si retorna 0 resultados, el proyecto es nuevo y necesita enrollment.

## Graceful Degradation

### Dual-Write (ver CLAUDE.md §Engram y Boot Sequence §0b)
Cajones con dual-write obligatorio: `estado`, `tareas` (SIEMPRE) + `css-foundation`, `design-system`, `security-spec` (post-Fase 2). Estructura en `{project_dir}/.pipeline/`. Crear con `mkdir -p` al primer write. Agregar `.pipeline/` a `.gitignore`.

### Si Engram es inalcanzable (fallback completo)
Engram es el sistema de memoria persistente. Si falla, el pipeline NO puede operar normalmente.
1. **Pasar detalles INLINE** a los subagentes (inflacion temporal de contexto)
2. Subagentes guardan resultados en disco: `{project_dir}/.pipeline/{cajon-name}.md`
3. Cuando Engram se recupere, migrar archivos de disco a cajones Engram
4. **Limite**: maximo 5 tareas en modo degradado antes de pausar y avisar al usuario
5. Marcar en DAG State (si es posible): `engram_degraded: true`

### Si Playwright MCP no está disponible
Sin Playwright, no hay QA visual (evidence-collector no puede capturar screenshots).
1. Ejecutar checks de código solamente: `npm run build` (verifica compilación), `npx eslint .` (lint), `grep -r "http://" --include="*.ts*"` (Mixed Content)
2. Marcar tareas como `qa_mode: "code-only"` en DAG State
3. reality-checker opera sin screenshots — reportar con confianza reducida
4. **Avisar al usuario**: "QA visual no disponible. Mixed Content y regresiones visuales no serán detectados. Se recomienda testeo manual antes de deploy."

### Debugging de pipeline fallido
Para reconstruir qué pasó:
1. `mem_search("{proyecto}/estado")` → fase actual, tareas completadas, fallos
2. `/tmp/qa/` → screenshots por número de tarea
3. `mem_search("{proyecto}/tarea-{N}")` → resultado de implementación
4. `mem_search("{proyecto}/qa-{N}")` → feedback de QA
5. `git log --oneline -5` → si se llegó a Fase 5

---

