# Orchestrator Pipeline — FASE 3 (Dev ↔ QA Loop)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

### FASE 3 — Dev ↔ QA Loop

Para **cada tarea** de la lista, en orden:

```
1. Recupera tarea N de Engram: {proyecto}/tareas (protocolo 2 pasos)

2. Selecciona agente según tipo de tarea:
   - UI / componentes / estilos / frontend  → frontend-developer
   - App móvil (iOS/Android con Expo)       → mobile-developer
   - API / base de datos / backend / jobs   → backend-architect
   - API type-safe (tRPC setup, routers)    → backend-architect
   - MVP rápido / validación de hipótesis   → rapid-prototyper
   - Diseño de mecánicas (juego)            → game-designer
   - Implementación de juego (canvas/WebGL) → xr-immersive-developer
   - Setup monorepo / workspace config      → backend-architect (config) + frontend-developer (UI packages)
   **Override mobile**: si DAG State `tipo: mobile`, las tareas con Tipo `frontend` se redirigen a mobile-developer (no frontend-developer). Las tareas Tipo `mobile` siempre van a mobile-developer.

3. Delega al agente con handoff minimo:
   ```
   TAREA: {N}/{Total} — {titulo}
   PROYECTO: {nombre} @ {directorio}
   LEE: {cajon} (usar mem_search → mem_get_observation)
   LEE TAMBIÉN: {proyecto}/visual-direction (elecciones visuales del usuario — estilo, hero, nav, galería, nivel animación, mood, efectos)
   CRITERIO: {criterio exacto — 1-2 lineas}
   GUARDA: {proyecto}/tarea-{N}
   DEVUELVE: Return Envelope Dev (ver seccion Return Envelope Standard)
   DESIGN_SYSTEM: {nothing-full | nothing-partial | custom | none} (si nothing-*, agregar linea siguiente)
   NOTHING_SCOPE: {lista de secciones} (solo si partial — el agente aplica Nothing SOLO a estas secciones)
   COMPONENT_SOURCE: {21st.dev | codepen | custom} (si 21st.dev → frontend-developer usa capability `documentation` para componentes animados/visuales)
   VISUAL_DIRECTION: {resumen 1 línea de las elecciones clave — ej: "inmersivo + aurora bg + nav blur + animación inmersiva + dark"}
   ```

   **Puerto**: el agente dev DEBE reportar el puerto donde corre el servidor (ej: `Servidor necesario: sí (puerto 3000)`). El orquestador pasa este puerto a evidence-collector en el paso 5.

   **OBLIGATORIO si el agente es backend-architect y la tarea crea/modifica endpoints**:
   Agregar al handoff: `EXTRA: Guarda/actualiza {proyecto}/api-spec con contrato de endpoints (metodo, ruta, body, response). Sin esto, api-tester en Fase 4 se BLOQUEA.`
   Verificar al recibir el Return Envelope: si la tarea tocaba endpoints y el agente NO reporto api-spec → re-delegar SOLO la generacion del spec.

   **Cajones por agente dev:** ver tabla "Qué cajón lee cada agente" en sección Engram arriba.

4. **Dev agent retorna su parte de Return Envelope** (Dev PASS ≠ tarea finalizada):
   
   El dev agent devuelve: `STATUS: completado | fallido + archivos + ENGRAM` en Return Envelope Dev.

   **NOTA CRÍTICA**: `STATUS: completado` del dev agent significa **"código listo para validación QA"**, NO **"tarea finalizada"**. La tarea solo queda finalizada cuando evidence-collector también retorna PASS.

   **Pre-QA check — dev agent STATUS: fallido**:
   Si el dev agent retorna `STATUS: fallido`, NO enviar a evidence-collector (desperdicia un retry).
   - Re-delegar al mismo dev agent con el error como contexto adicional
   - Trackear en DAG State: `tareas[N].dev_consecutive_fails++`
   - Si falla 2 veces seguidas sin llegar a QA → escalar al usuario (mismas opciones que escalación 3x)
   - Solo continuar a Paso 5 (evidence-collector) cuando el dev agent retorna `STATUS: completado`

   **Verificación post-return obligatoria (backend-architect)**:
   Si la tarea involucraba endpoints y el Return Envelope NO incluye `ENGRAM: {proyecto}/api-spec`:
   - Llamar `mem_search("{proyecto}/api-spec")` para verificar si existe
   - Si NO existe → re-delegar a backend-architect: "Genera SOLO el api-spec para los endpoints creados. Guarda en Engram: {proyecto}/api-spec"
   - Si existe → continuar normalmente
   Esto previene que api-tester en Fase 4 parsee {proyecto}/tareas como fallback (produce resultados corruptos).

5. **Delega a evidence-collector (QA gate — bloquea de verdad)**:
   
   Ahora el dev-agent ha pasado su parte, pero la tarea NO está cerrada. Invocar evidence-collector con:
   ```
   "Valida tarea {N}/{Total} del proyecto {proyecto}. 
   URL: http://localhost:{puerto} (reportado por dev-agent)
   QA Intento: {intento_actual}/3 (tracked por dispatcher.check_qa_retry_limit, no en memoria del orquestador)
   TIPO_PROYECTO: {web | mobile} (del DAG State)
   Captura screenshots con Playwright MCP.
   Guarda screenshots en /tmp/qa/tarea-{N}-{device}.png (NO inline, solo rutas)
   Lee criterio de aceptación de Engram: {proyecto}/tareas — localiza tarea {N}
   Guarda resultado en Engram: {proyecto}/qa-{N} con Return Envelope QA
   Devuelve: STATUS PASS | FAIL + rutas screenshots + lista de issues (si FAIL)"
   ```
   
   **Validación de Return Envelope QA — STRICT MODE (orquestador, Bloque 1A.10)**:
   
   Evidence-collector DEBE devolver Return Envelope QA válido. El orquestador RECHAZA envelopes malformados.
   
   1. **Validar Return Envelope con dispatcher.validate_return_envelope(qa_response, mode="qa_strict")**
      - Si VÁLIDO: continuar a Paso 6 o 7 según STATUS
      - Si INVÁLIDO: NO avanzar. Redel a evidence-collector con error específico
   
   2. **Validación estricta para QA**:
      - PASS requiere: status=PASS + tarea + engram + archivos (lista NO VACÍA) + NO bloqueadores
        - Si falta: "Return Envelope QA inválido: PASS requiere archivos (lista no vacía)"
      - FAIL requiere: status=FAIL + tarea + engram + bloqueadores (lista NO VACÍA)
        - Si falta: "Return Envelope QA inválido: FAIL requiere bloqueadores (lista no vacía)"
      - STATUS debe ser PASS o FAIL exactamente (no PENDING, CERTIFIED, etc.)
        - Si otro: "Return Envelope QA inválido: status inválido: {valor}, esperado PASS o FAIL"
      - archivos y bloqueadores deben ser listas (si existen)
        - Si no: "Return Envelope QA inválido: {campo} debe ser lista, recibido {type}"
   
   3. **Si Return Envelope inválido**:
      - Redel a evidence-collector con mensaje de error exacto
      - NO marcar como QA FAIL de negocio: llamar `dispatcher.record_qa_attempt(task_id="{proyecto}/tarea-{N}", status="infra_error", reason="envelope invalido")` (no incrementa qa_intento_actual — ver Bloque de enforcement abajo)
      - Reintenta 1x (mismo intento de QA). Si falla validación 2x → escalar al usuario
   
   4. **Si Engram write falla con timeout/error (Engram error, NO formato error)**:
      - NO marcar como FAIL: llamar `dispatcher.record_qa_attempt(task_id="{proyecto}/tarea-{N}", status="infra_error", reason="engram timeout")` (no incrementa contador). Reintenta evidence-collector (mismo intento)
      - Si falla 2x Engram → informar al usuario "Engram timeout — procederá como QA manual" y continuar
   
   5. **Si evidence-collector crashea (zero return)**:
      - Reintenta 1x (mismo intento). Si crashea 2x → escalar al usuario

   **Mobile**: si evidence-collector reporta "QA visual limitada", informar al usuario una vez: "QA de tareas mobile se limita a validación de build — no hay simulador visual disponible."

   **Enforcement mecánico del contador (Architecture Repair 03 — 2026-09-23)**:
   El contador de intentos YA NO es un campo de DAG State llevado solo por
   el razonamiento del orquestador — es `dispatcher.record_qa_attempt()` /
   `dispatcher.check_qa_retry_limit()` (`tools/qa_retry_state.py`,
   persistido en `.pipeline/qa-retry-state.json`, por `task_id`,
   sobrevive reinicio de sesión). `task_id` = `"{proyecto}/tarea-{N}"`
   (string estable, consistente con las claves de Engram ya usadas en este
   documento). El orquestador SIEMPRE llama a `record_qa_attempt` con el
   resultado real de cada intento (ver pasos 6/7/8) en vez de incrementar
   `qa_intento_actual` mentalmente — la cuenta y el límite de 3 ya no
   dependen de que el orquestador no pierda la cuenta en una conversación
   larga. `check_qa_retry_limit(task_id)` es de solo lectura y puede
   consultarse antes de re-delegar sin registrar un intento nuevo.

**Umbral PASS/FAIL:**
- Rating B- o superior → PASS
- Rating C+ o inferior → FAIL (requiere reintento)
- 0 errores en consola es OBLIGATORIO para PASS
- **Mobile responsive OBLIGATORIO para PASS**: 0 failures del "Mobile responsive checklist" de evidence-collector. Cualquier fallo (scroll-h no deseado, inputs <16px, touch targets <44px, sidebar con margin-left en mobile, parallax sin guard) → FAIL automático sin importar el rating general. Aplica a todas las tareas de UI web — excepción única: `TIPO_PROYECTO: mobile` (React Native) que usa QA distinta.

6. **Si QA PASS**:
   - evidence-collector retorna: `STATUS: PASS + ENGRAM: {proyecto}/qa-{N}`
   - Orquestador verifica que `{proyecto}/qa-{N}` existe en Engram (mem_search → mem_get_observation)
   - Llama `dispatcher.record_qa_attempt(task_id="{proyecto}/tarea-{N}", status="pass")` — limpia el contador (loop cerrado para esta tarea)
   - **Actualiza DAG State: `tareas[N].status = "completada"`**
   - Continúa con tarea N+1

7. **Si QA FAIL**:
   - evidence-collector retorna: `STATUS: FAIL + issues`
   - Orquestador llama: `r = dispatcher.record_qa_attempt(task_id="{proyecto}/tarea-{N}", status="fail", reason="{resumen de issues}", agent="{dev agent}")`
   - **Si `r["retry_limit_reached"] == False`** (esto reemplaza el chequeo manual "intento < 3"): pasa feedback específico al dev agent: "QA falló: {lista de issues}. Intento {r['attempt_count']}/3. Arregla y reintenta." Vuelve al paso 3 (re-delega mismo dev agent)
   - **Si `r["retry_limit_reached"] == True`** (esto reemplaza el chequeo manual "intento = 3"): ir al paso 8 — ESCALACIÓN

8. **ESCALACIÓN (tarea NO avanza)**:
   - `dispatcher.record_qa_attempt` devolvió `retry_limit_reached=True` (3er intento fallido, o un state_error — ver Bloque de enforcement: ambos casos bloquean por diseño, fail-closed)
   - Tarea queda bloqueada con estado `{proyecto}/tareas[N].status = "bloqueada"`
   - Opciones presentadas al usuario:
   a) Reasignar: delegar a otro agente dev
   b) Descomponer: partir en sub-tareas más pequeñas
   c) Diferir: marcar con ⚠️ y continuar con otras tareas
   d) Aceptar: documentar limitación y avanzar
   → Pide decisión al usuario, actualiza DAG State
```

### Timeout guidance para subagentes

No hay timeout explícito en Agent spawns — el agente corre hasta completar o agotar contexto. Si un agente tarda más de lo esperado:
- **Dev agents (frontend, backend, rapid-prototyper)**: tareas normales ~2-5 min. Si >10 min, verificar Engram por resultado parcial.
- **evidence-collector**: ~1-3 min por tarea. Si >5 min, probablemente el servidor de test no respondió.
- **Agentes creativos (image, logo, video)**: ~1-5 min dependiendo de API externa. Timeout de la API es el bottleneck.
- **Agentes de planificación/análisis (PM, security, ux, ui)**: ~1-3 min.

Si un agente parece stuck: NO cancelar manualmente — verificar Engram primero (puede haber completado y solo se perdió el return).

### Recovery: si un subagente no devuelve resultado

Si un agente fue spawneado pero no devolvió STATUS (crash, timeout, context limit):

1. **Verificar Engram**: `mem_search("{proyecto}/tarea-{N}")` — si tiene resultado, el agente completó pero el return se perdió
   → Verificar que los archivos existen en disco → marcar tarea como "pendiente QA" → continuar al paso 5 (evidence-collector)
2. **Si Engram vacío**: el agente crasheó antes de guardar
   → Re-delegar la tarea desde cero (mismo agente, intento 1/3)
   → Si vuelve a fallar: intentar con **un** agente alternativo compatible (ej: frontend-developer → rapid-prototyper)
   → Si el alternativo también falla: **PARAR**. Escalar al usuario con el error. **No probar más agentes** — si 2 agentes distintos crashean en la misma tarea, el problema es la tarea, no el agente.
3. **Actualizar DAG State**: marcar tarea con flag `recovered: true`

**Recovery: evidence-collector crash**
Si evidence-collector no retorna o crashea:
1. Verificar que el servidor de test sigue corriendo (`curl -s -o /dev/null -w '%{http_code}' http://localhost:{puerto}`)
2. Re-delegar a evidence-collector (misma tarea, mismo intento — no incrementar contador)
3. Si crashea 2 veces seguidas:
   - **Solo si la tarea NO es UI visible** (ej: config, types, migraciones DB, API routes sin UI, setup de infra): cambiar a `qa_mode: "code-only"` para esa tarea (lint + build check) y continuar.
   - **Si la tarea es UI/frontend** (componentes visibles, layouts, landing, páginas con render): **PROHIBIDO `code-only`**. Escalar al usuario con el error de evidence-collector — lint+build no detecta scroll-h, font-size <16px, touch targets, hover-only, mixed content visual, ni ningún bug de los que esta auditoría encontró. Mejor bloquear que certificar ciego.
4. Marcar la tarea como `qa_parcial: true` en DAG State (solo cuando qa_mode code-only fue aplicado legítimamente).

### QA de assets creativos
evidence-collector verifica assets para artefactos obvios (extremidades de mas, objetos flotando). Esto es complementario a la revision del usuario — la decision estetica final SIEMPRE es del usuario.

**Reportes de progreso** — cada 3 tareas completadas:
```
[Fase 3] Progreso: {N}/{Total}
✓ Completadas: tareas 1, 2, 3
→ En progreso: tarea 4 (intento 1/3)
○ Pendientes: tareas 5...{Total}
```

---

### Flujo CodePen en Fase 3

Cuando el usuario pide un efecto de CodePen o el orquestador detecta una URL de CodePen:

```
1. BUSQUEDA (si no hay URL directa):
   → spawn codepen-explorer (search): "busca efecto de {descripcion}"
   → recibe 3 opciones (recomendada + 2 alternativas)
   → presenta al usuario → usuario elige

2. EXTRACCION:
   → spawn codepen-explorer (extract): "{url_elegida}, project_dir={dir}"
   → recibe STATUS + EXTRACTED_TO path + DEPS + NOTES

3. APROBACION PRE-IMPLEMENTACION:
   → mostrar al usuario: link al pen original + deps + notas
   → si hay brand.json: "Adapto colores/fonts al brand manteniendo la mecanica?"
   → si NO hay brand: "Lo implemento tal cual o queres ajustes?"
   → solo tras aprobacion → pasar a frontend-developer

4. IMPLEMENTACION:
   → spawn frontend-developer: "integra efecto de {path_temp}, adapta al brand, deps: {lista}"
   → frontend-developer lee de disco, adapta, implementa
   → evidence-collector valida (como cualquier otra tarea)

4. CHECKPOINT POST-EFECTOS (al terminar TODOS los efectos CodePen):
   → mostrar pagina completa al usuario
   → "Todos los efectos de CodePen estan aplicados. Queres cambiar alguno antes de certificar?"
   → si el usuario quiere cambiar uno → solo rehacer ese (busqueda → extraccion → implementacion)

5. BOVEDA (post-checkpoint, si el usuario aprueba):
   → "Te gustaron estos efectos? Cuales guardamos en la boveda?"
   → spawn codepen-explorer (vault-save) para los aprobados
   → frontend-developer guarda adapted.json en la boveda
```

Deteccion de URLs de CodePen en mensajes del usuario:
- Si el usuario dice "usa este pen: codepen.io/..." → saltar paso 1, ir directo a extraccion
- Regex: `codepen\.io\/[\w-]+\/pen\/[\w]+`

**Phase Gate → Fase 4** (QA GATE — BLOQUEA DE VERDAD):

Antes de avanzar a Fase 4, verificar que TODAS las tareas pasaron QA. Este gate BLOQUEA la transición — no hay way around.

**Validación obligatoria**:
1. **Para CADA tarea N en {proyecto}/tareas**:
   - Verificar que existe `{proyecto}/qa-{N}` en Engram (mem_search + mem_get_observation, 2-pasos)
   - Si NO existe → GATE BLOQUEADO. Informar: "Tarea {N} no tiene QA. Evidence-collector no fue ejecutado o su resultado no está en Engram. Resolver antes de continuar a Fase 4."
   - Si existe → verificar que `qa-{N}.status = "PASS"` (leer contenido completo)
   - Si status ≠ PASS → GATE BLOQUEADO. Informar: "Tarea {N} tiene QA status: {status}. Debe ser PASS. Aceptados: PASS solamente. Reintenta QA o escala."

2. **Si Engram timeout/error al leer qa-{N}** (MCP no responde):
   - NO marcar como cajon faltante ni como FAIL
   - Reintenta 1x con mem_search
   - Si sigue fallando → informar al usuario: "Engram no responde al verificar QA de tarea {N}. No puedo bloqueador/permitir avance. Intenta de nuevo en un momento."
   - NO avanzar automáticamente (gate se queda en PENDING, esperando Engram)

3. **Si hay tareas backend**: verificar que `{proyecto}/api-spec` existe en Engram

4. **Si se usaron efectos CodePen**: checkpoint post-efectos debe estar completado en Engram o DAG State

5. **Build production**: `npm run build && npm start` → verificar con `curl -s -o /dev/null -w '%{http_code}' http://localhost:{puerto}` (expect 200)

**Si ALL checks PASS** → desbloquea transición a Fase 4
**Si ALGÚN check FALLA** → gate BLOQUEADO. Devuelve BLOQUEADORES al usuario con lista exacta de qué falta

### Build failures → build-resolver
Si `npm run build` falla en cualquier fase (Fase 3, Fase 4, o Phase Gate):
1. Delegar a build-resolver con el output completo del error + `project_dir` + ruta a `{proyecto}/tareas`
2. build-resolver tiene máx 3 intentos internos de resolución
3. Si build-resolver retorna `STATUS: completado` → continuar normalmente
4. Si build-resolver retorna `STATUS: fallido` → escalar al usuario con el diagnóstico completo
5. NO re-intentar manualmente lo que build-resolver ya intentó

