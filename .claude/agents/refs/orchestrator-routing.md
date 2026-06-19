# Orchestrator — Boot Sequence & Routing

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Boot Sequence (PRIMERA accion de CADA interaccion)

**Ejecutar SIEMPRE al inicio, antes de cualquier otra cosa.**

### Carga progresiva del DAG State (Light vs Full Mode — Phase 0.6A+)

El DAG State puede ser grande (10+ KB en proyectos avanzados). Para no inflar el contexto innecesariamente, se carga en 2 niveles:

| Modo | Contenido | Cuándo activar | Tokens aprox | Mejora |
|------|-----------|----------------|--------------|---------|
| **Boot LIGHT** | fase_actual, tarea_actual/total, stack (1 linea), ultimo_save | Retomar sesión anterior sin cambios | ~50-100 | -70% vs full |
| **Boot FULL** | DAG State entero (fases_completadas, tareas_fallidas, decisiones, certificacion) | Decisiones de orquestación, cambios de fase, escalaciones | ~500-2000 | 100% contexto |

**Lógica de selección (OBLIGATORIA Phase 0.6A+)**:

```
_boot_light() ← USAR CUANDO:
  ✅ session_id == last_session_id
  ✅ intento_actual < 3 (reintentos aún disponibles)
  ✅ No hay cambio de fase solicitado
  ✅ No hay escalación

_boot_full() ← USAR CUANDO:
  ✅ session_id != last_session_id (nueva sesión)
  ✅ intento_actual >= 3 (escalación — necesita DAG completo)
  ✅ Cambio de fase (Fase 1 → 2, 3 → 4, etc.)
  ✅ Decisión crítica de arquitectura/stack
  ✅ Usuario solicita revisión de contexto histórico
```

### Variables de estado para Boot Sequence (PERSISTIDAS en Engram)

```yaml
# Topic_key: {proyecto}/boot-state (OBLIGATORIO guardar aquí)

session_id: "vibecoding-atlas-20260514-143022"  # UUID unico por sesión
last_session_id: "vibecoding-atlas-20260514-093015"  # Sesión anterior (para detectar continuidad)
intento_actual: 2  # Contador 1-3 (reset en nueva sesión o escalación)
boot_mode_used: "light"  # "light" o "full" (para debugging)
timestamp_boot: "2026-05-14T14:30:22Z"  # Cuándo se hizo el último boot
```

**Ciclo de vida**:
1. Sesión nueva: `session_id` ← nuevo UUID, `intento_actual` ← 1
2. Retomar misma sesión: `session_id` == `last_session_id`, `intento_actual` += 1
3. Cambio de sesión (usuario cierra y reabre): `last_session_id` ← anterior, `session_id` ← nuevo, `intento_actual` ← 1
4. Escalación (intento_actual ≥ 3): Pasar a `_boot_full()` automáticamente

**Guardar después de cada boot**:
```
mem_save(
  title: "{proyecto} — boot state",
  content: "session_id: {session_id}\nlast_session_id: {last_session_id}\nintento_actual: {intento_actual}\n...",
  type: "config",
  topic_key: "{proyecto}/boot-state",
  project: "{proyecto}"
)
```

**Regla de oro**: El boot ligero es suficiente para informar al usuario y continuar tarea en progreso. El boot completo solo se necesita cuando:
- Se completa una fase y hay que decidir la siguiente
- Una tarea falla 3 veces (`intento_actual ≥ 3`) y hay que escalar
- El usuario pide cambiar scope/stack/prioridades
- Se inicia Fase 4 (certificacion) o Fase 5 (publicacion)

### Secuencia de inicio

0. **Cargar perfil personal del usuario** (SIEMPRE, antes de cualquier otra cosa):
   `mem_context(scope="personal")` — carga el perfil de Leonardo Emanuel Mansilla (@Tio / PM en Reyesoft)
   **NOTA**: El hook `session-start-context` NO puede hacer esto (los hooks no tienen acceso a MCPs).
   Esta llamada es responsabilidad del orquestador al inicio de cada sesión.

0b. **Verificar trigger de compactación pendiente** (solo si hay proyecto activo):
   Leer `~/.claude/snapshots/compaction-pending.json` via Bash/Read.
   - Si existe → compactación ocurrió sin dual-write: ejecutar inmediatamente:
     1. `mem_update({proyecto}/estado, currentDagState)` — guardar estado en Engram
     2. Escribir `.pipeline/estado.yaml` en disco
     3. Eliminar el trigger file (`rm ~/.claude/snapshots/compaction-pending.json`)
   - Si no existe → continuar normalmente (caso habitual)
   
   **Por qué**: el hook `pre-compact-engram.js` ya NO emite instrucciones via stderr (causaban respuestas vacías sin tool calls). En su lugar escribe este trigger file. El Boot Sequence es el único lugar donde se actúa sobre él.

1. Si el usuario menciona un nombre de proyecto → `mem_search("{proyecto}/estado")`
   - **Si existe en Engram**: SESION ANTERIOR o COMPACTACION DETECTADA
     - `mem_get_observation(id)` → leer DAG State completo (necesario en primera carga para extraer resumen)
     - Extraer **resumen ligero** para contexto inmediato:
       ```
       fase: {fase_actual}
       tarea: {tarea_actual}/{total_tareas}
       stack: {frontend} + {backend} + {db}
       ultimo_save: {timestamp}
       ```
     - Mantener en memoria de trabajo SOLO el resumen ligero
     - Guardar el observation_id del DAG State para re-leer el completo cuando se necesite
     - Marcar `recovered: true` en DAG State
     - Informar al usuario: "Retomando {proyecto} — Fase {X}, tarea {N}/{Total}. Ultima actividad: {ultimo_save}"
     - Continuar desde donde estaba — NO re-preguntar decisiones ya tomadas
   - **Si NO existe en Engram** → intentar fallback disco:
     - Buscar `{project_dir}/.pipeline/estado.yaml` (campo `backup_disk` del DAG)
     - Si existe en disco: leer, migrar a Engram con `mem_save`, continuar
     - Si no existe en disco: PROYECTO NUEVO → proceder con Fase 1

2. Si el usuario NO menciona nombre de proyecto → preguntar:
   "¿Es un proyecto nuevo o retomamos uno existente?"
   - Si existente: pedir nombre → buscar en Engram
   - Si nuevo: Fase 1

3. Si hay una sesion anterior abierta en Engram (no cerrada por crash/Ctrl+C) → cerrarla:
   `mem_session_end(id: "{sesion_anterior_id}")` — previene acumulacion de sesiones huerfanas.

4. **Determinar boot mode (LLAMAR HELPER REAL)**:
   
   **Paso 4a**: Leer boot-state anterior (si existe)
   ```
   prev_boot_state = mem_search("{proyecto}/boot-state")
   if prev_boot_state found:
     prev_boot = mem_get_observation(prev_boot_state.observation_id)
     state_dict = parse_yaml(prev_boot.content)
   else:
     state_dict = None
   ```
   
   **Paso 4b**: Ejecutar decisión real
   ```python
   from tools.boot_sequence_integration import BootSequenceIntegrator
   
   integrator = BootSequenceIntegrator()
   result = integrator.run_boot_decision(
     proyecto="{proyecto}",
     session_id="{session_id}",
     phase_actual="{fase_actual}",
     prev_boot_state=state_dict  # None if not found
   )
   # result.mode = "light" | "full"
   # result.boot_state = dict ready to persist
   # result.context_savings = token estimates
   ```
   
   **Paso 4c**: Guardar nueva decisión
   ```
   mem_save(
     title: "{proyecto} — boot state",
     content: yaml_dump(result["boot_state"]),
     type: "config",
     topic_key: "{proyecto}/boot-state",
     project: "{proyecto}"
   )
   ```
   
   **Paso 4d**: Usar decisión en Paso 5
   ```
   boot_mode = result["mode"]  # "light" | "full"
   ```

5. `mem_session_start(id: "vibecoding-{proyecto}-{timestamp}", project: "{proyecto}")`

### Re-lectura bajo demanda del DAG State completo

Cuando el orquestador necesita el DAG State completo:
```
mem_get_observation(dag_state_observation_id) → leer completo
Tomar la decision
mem_update(dag_state_observation_id, updated_dag) → guardar cambios
Volver a retener solo el resumen ligero
```

Esto evita mantener el YAML completo en contexto durante toda la sesion.

**Restricción v2.3 — NUNCA re-leer DAG State más de una vez por fase:**

| Situación | Re-lectura completa | Usar resumen ligero |
|-----------|--------------------|--------------------|
| Cambio de fase (ej: Fase 3 → 4) | ✅ SÍ | |
| Escalación (3 reintentos fallidos) | ✅ SÍ | |
| Decisión crítica de arquitectura | ✅ SÍ | |
| Transición entre tareas dentro de la misma fase | | ✅ NO re-leer |
| Handoff rutinario a subagente | | ✅ NO re-leer |
| Phase gate check (¿cumple requisitos para avanzar?) | | ✅ Resumen + `mem_search` puntual |

Si ves que ya leíste el DAG State completo en la misma fase → **usa el resumen en contexto, no vuelvas a llamar `mem_get_observation`**.

**NUNCA asumir que un proyecto es nuevo sin verificar Engram primero.**
**NUNCA re-preguntar stack, estructura, o decisiones que ya estan en el DAG State.**

**NOTA sobre pre-compact snapshot**: `session-start-context.js` (hook de Notification) ya lee `~/.claude/snapshots/pre-compact-latest.json` al inicio y emite contexto via stderr. Esto es independiente del Boot Sequence — el snapshot es metadata de sesion (tool count, cwd), NO el DAG State del proyecto. El DAG State se recupera de Engram o `.pipeline/`.

**NOTA sobre PreCompact hook (v2.3)**: `pre-compact-engram.js` escribe un trigger file en `~/.claude/snapshots/compaction-pending.json` antes de compactar. El Boot Sequence (paso 0b) detecta este archivo y ejecuta el dual-write. Ya NO emite instrucciones via stderr — ese patrón causaba respuestas vacías sin tool calls ("Lo continúo ahora:" sin ejecutar nada).

**NOTA sobre Engram MCP auto-activación (Bloque 1B.5)**: cada vez que se construye `ATLASDispatcher(project_root)`, el dispatcher intenta activar Engram MCP automáticamente. Estado visible en `dispatcher.engram_mcp_status`:
- `"active"` → Engram MCP real conectado, queries van vía `mem_search` real
- `"unavailable: {reason}"` → binario engram no encontrado, dispatcher cae a `disk_fallback` (graceful)
- `"disabled_by_env"` / `"disabled_by_param"` → opt-out explícito

**Responsabilidad del orquestador**: si necesitás reportar el estado al usuario, leé `engram_mcp_status` y mencionalo. NO hay logging automático ruidoso — vos decidís cuándo es relevante mostrarlo. Para tests aislados, setear `ATLAS_DISABLE_ENGRAM_MCP=1` antes de instanciar.

---

