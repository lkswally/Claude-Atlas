# Orchestrator Pipeline — FASE 2B (Assets Visuales)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

### FASE 2B — Assets Visuales (solo si el proyecto tiene landing page, logo, o imágenes de marca)

Ejecutar en paralelo a Fase 2 o antes de Fase 3, según cuándo se necesiten los assets.

**¿Cuándo activar?** Si el proyecto incluye landing page, hero section, logo, o video de fondo.

**Orden obligatorio — NO saltear pasos:**

```
1. Delega a brand-agent:
   - Pasa: project_dir, project_name, brief (style/tone/colores si el usuario los especificó),
           asset_needs (["logo","hero_image"] siempre + "bg_video" solo si el usuario lo pidió),
           **topic_keys obligatorios a leer: `{proyecto}/intent` + `{proyecto}/visual-direction`** (brand-agent hace 2-pasos read y deriva colors/typography desde la extracción del Paso 1.5a si existió, o del preset del intent si no)
   - **Si `design_system` es `nothing-full`**: agregar `DESIGN_SYSTEM: nothing-full` al handoff — brand-agent alinea paleta/tipografía a Nothing (Space Grotesk/Mono/Doto, OLED blacks, accent red)
   - **Si `design_system` es `nothing-partial`**: agregar `DESIGN_SYSTEM: nothing-partial` + `NOTHING_SCOPE: {nothing_scope}` — brand-agent crea identidad propia pero documenta en brand.json que secciones en `nothing_scope` usan tokens Nothing
   - Guarda en Engram: {proyecto}/branding (schema v2 — ver brand-agent.md § "Estructura de brand.json (schema v2)")
   - Devuelve: STATUS + resumen de identidad (nombre, paleta, tipografía, style_tags, mood_vector, reference_ids)

2. **PAUSA** — Presentar propuesta (nombre, paleta hex, tipografía, estilo) al usuario
   → Cambios: re-delegar brand-agent con correcciones → volver aquí
   → Aprueba: actualizar Engram `{proyecto}/branding` con `user_approved: true` + `approved_version: {N}` (incrementar en cada aprobacion). Esto permite verificar que image-agent usa la version aprobada, no una anterior.

   **GATE OBLIGATORIO**: NO avanzar al paso 2B ni al paso 3 hasta que `user_approved: true` esté confirmado en Engram Y brand.json en disco sea la versión aprobada. Si se rechazó y brand-agent regeneró, verificar que el nuevo brand.json coincide con lo aprobado antes de lanzar image-agent/logo-agent. Esto previene race condition donde image-agent lee un brand.json viejo mientras brand-agent escribe el nuevo.

2B. **ELEGIR BACKEND DE IMÁGENES** — Preguntar al usuario:
   ```
   ¿Qué motor de imágenes querés usar para generar los assets?

     a) HuggingFace (gratis, no requiere configuración extra)
        Usa FLUX.1-schnell / SDXL. Requiere HF_TOKEN.

     b) Google Gemini (mejor calidad, ~$0.02-0.04 por imagen)
        Requiere cuenta en Google AI Studio con billing habilitado.
        Si no lo tenés configurado, te guío paso a paso.
   ```
   → Si elige **a) HuggingFace**:
     - Verificar que `HF_TOKEN` existe (`echo $HF_TOKEN | wc -c`)
     - Si no existe: "Necesitás un token de HuggingFace. Creá uno gratis en https://huggingface.co/settings/tokens y ejecutá: export HF_TOKEN=hf_tu_token"
     - Pasar `backend: "huggingface"` a image-agent y logo-agent

   → Si elige **b) Gemini**:
     - Verificar que `GEMINI_API_KEY` existe (`echo $GEMINI_API_KEY | wc -c`)
     - Si NO existe → guiar setup:
       ```
       Para configurar Gemini necesitás:

       1. Ir a https://aistudio.google.com/apikey
       2. Crear una API key (se crea un proyecto Google Cloud automáticamente)
       3. IMPORTANTE: habilitar billing en ese proyecto:
          → https://console.cloud.google.com/billing
          → Asociar una tarjeta (se cobra solo por uso, ~$0.02-0.04 por imagen)
       4. Copiar la API key y ejecutar:
          export GEMINI_API_KEY="tu_api_key_aqui"

       ¿Ya tenés la key configurada? (s/n)
       ```
     - Si dice sí: verificar la key haciendo un test rápido:
       ```bash
       curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | head -5
       ```
       Si retorna modelos → OK. Si retorna error → mostrar el error y ofrecer usar HuggingFace como fallback.
     - Pasar `backend: "gemini"` a image-agent y logo-agent

   → Guardar la elección en DAG State: `image_backend: "gemini" | "huggingface"`
   → En proyectos futuros, si hay key guardada, preguntar: "La última vez usaste {backend}. ¿Seguimos con ese?"

3. **(paralelo)** logo-agent + image-agent — ambos reciben `{ "project_dir": "...", "backend": "gemini|huggingface" }`, leen brand.json del filesystem
   - logo → `{project_dir}/assets/logo/` (guarda en `{proyecto}/creative-logos`) | image → `{project_dir}/assets/images/` (guarda en `{proyecto}/creative-images`)
   - Sin conflictos: cada agente escribe en su propio cajon de Engram.

4. **Consultar video** al usuario (NO auto-generar): "¿Video de fondo para hero? (~$0.03-0.10 en Replicate)"
   → Sí: video-agent → `{project_dir}/assets/video/` | No: marcar DAG `video → "no-requerido"`

5. **PAUSA** — Presentar assets al usuario (mostrar todas las imágenes/videos con clasificación SAFE/MEDIUM/RISKY)
   Opciones: a) Aprobar todas, b) Aprobar/rechazar selectivo, c) Rechazar todas
   **Si rechaza**: máx 3 reintentos por imagen (1: ajustar prompt, 2: cambiar composición, 3: alternativa completamente diferente o placeholder)

6. Verificar cajones en Engram: `{proyecto}/creative-logos`, `{proyecto}/creative-images`, `{proyecto}/creative-video` (cada uno actualizado por su agente)

7. **COPIAR a public/** — assets/ → public/ (frameworks solo sirven desde public/)
   - Monorepo: `cp -r assets/{images,logo,video}/* apps/web/public/{images,logo,video}/`
   - Single-repo: `cp -r assets/* public/`
   - **Favicons a public/ RAÍZ** (browsers los buscan ahí), rutas en código relativas a public/: `"/images/hero.png"`

8. Actualizar DAG State: assets_creativos → "listo"
```

**Si brand.json ya existe con `user_approved: true`** → saltar pasos 1-2.

**Cost tracking**: después de Fase 2B, guardar/actualizar `{proyecto}/costs` en Engram con costo estimado acumulado. Los agentes creativos reportan el costo en su STATUS. Formato: `"images: $0.04 (Gemini), logo: $0 (HF), video: $0.05 (Replicate) — total: $0.09"`

### Manejo de errores en pipeline creativo

**brand-agent falla** (STATUS: fallido):
1. Re-intentar 1 vez con prompt simplificado (solo nombre + paleta + tipografía)
2. Si falla de nuevo → preguntar al usuario: "No se pudo generar la identidad visual. ¿Continuar sin assets visuales?"
3. Si acepta → marcar `creative_pipeline: "skipped"` en DAG State, saltar a Fase 3

**image-agent falla** (STATUS: fallido):
1. Si logo-agent tuvo éxito → continuar sin hero images
2. video-agent se salta (necesita hero.png)
3. Informar al usuario qué assets faltan y continuar

**TODAS las APIs de imagen fallan** (no GEMINI_API_KEY ni HF_TOKEN):
1. Informar: "No hay API keys configuradas para generación de imágenes"
2. Ofrecer: continuar sin assets visuales O pausar para configurar keys
3. Si continúa → marcar `creative_pipeline: "skipped"` en DAG State

**Regla general**: el pipeline creativo es OPCIONAL. Un proyecto puede avanzar a Fase 3 sin assets visuales. El orquestador nunca debe bloquearse indefinidamente por falta de APIs creativas.

---

**Phase Gate → Fase 2B** (si assets creativos fueron solicitados):
- `{proyecto}/branding` debe existir con `user_approved: true`
- `{proyecto}/creative-logos` debe existir (si logo fue solicitado)
- `{proyecto}/creative-images` debe existir (si imagenes fueron solicitadas)
- Si video fue solicitado: `{proyecto}/creative-video` debe existir O tener fallback CSS
- Assets copiados a public/ (verificar que existen en filesystem)
Si alguno falta, NO avanzar. Resolver primero.

**Phase Gate → Fase 3** (ENFORCED — HARD BLOCK):

Antes de delegar a primer dev-agent, ejecutar `enforce_phase_gate("{proyecto}", "fase_3", ["{proyecto}/css-foundation", "{proyecto}/design-system", "{proyecto}/security-spec", "{proyecto}/tareas"])`:

```
python tools/atlas_dispatcher.py check-phase fase_2b fase_3
```

**Validación obligatoria — CADA cajón**:
- `{proyecto}/css-foundation` — si falta → FASE BLOQUEADA. Mensaje: "Fase 3 blocked: {proyecto}/css-foundation missing. Re-delegar ux-architect."
- `{proyecto}/design-system` — si falta → FASE BLOQUEADA. Mensaje: "Fase 3 blocked: {proyecto}/design-system missing. Re-delegar ui-designer."
- `{proyecto}/security-spec` — si falta → FASE BLOQUEADA. Mensaje: "Fase 3 blocked: {proyecto}/security-spec missing. Re-delegar security-engineer."
- `{proyecto}/tareas` — si falta → FASE BLOQUEADA. Mensaje: "Fase 3 blocked: {proyecto}/tareas missing. Fase 1 o Fase 2 falló — investigar."

**Anti-loop enforcement**:
- Cada re-delegación por Phase Gate falla CUENTA contra límite de 2 re-delegaciones de Fase 2
- Si un cajón sigue faltando después de 2 re-delegaciones → escalar al usuario (no continuar)
- Trackear `phase_gate_retries` en DAG State
- **NUNCA** re-delegar más de 2 veces total por cajón faltante

**Si ALL checks PASS** → desbloquea Fase 3, comienza dev loop
**Si ALGÚN check FALLA** → halt, devuelve BLOQUEADORES exactos

