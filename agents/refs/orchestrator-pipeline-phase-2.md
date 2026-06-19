# Orchestrator Pipeline — FASE 2 (Arquitectura)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

### FASE 2 — Arquitectura (orden secuencial crítico)

**Límite de reintentos Fase 2**: máximo **2 re-delegaciones** por agente (ux-architect, ui-designer, security-engineer). Si un agente falla 2 veces, escalar al usuario con el error específico. NO re-delegar indefinidamente.

**IMPORTANTE: No es totalmente paralela. ux-architect debe completar antes que ui-designer pueda empezar.**

**Paso 1 — ux-architect** (primero, obligatorio)
- Recibe: spec del proyecto + ruta al cajón `{proyecto}/tareas`
- **Design Intelligence**: ux-architect ejecuta `node ~/.claude/design-data/search.js` como Paso 0 para obtener recomendaciones por industria (estilo, colores, tipografía, anti-patterns). No requiere acción del orquestador — el agente lo hace automáticamente.
- **Si DAG State `tipo: mobile`**: agregar al handoff `TIPO_PROYECTO: mobile` — ux-architect producirá tokens en formato TS/JSON (no CSS)
- **Si `design_system` es `nothing-full` o `nothing-partial`**: agregar al handoff:
  ```
  DESIGN_SYSTEM: {nothing-full | nothing-partial}
  NOTHING_SCOPE: {lista de secciones} (solo si partial)
  REFERENCIA: nothing-design-reference.md
  ```
- Guarda en: `{proyecto}/css-foundation` (incluye campo `Design Intelligence` con categoría, estilo y anti-patterns)
- Devuelve: resumen (tokens CSS, layout, breakpoints)

**Paso 1.5 — Visual Direction Checkpoint** (PAUSA OBLIGATORIA para proyectos con UI)

Después de que ux-architect devuelva, el orquestador refina las decisiones visuales usando el `intent` capturado en Fase 1 Paso 0. Este paso **NO arranca de cero**: pre-fillea las opciones basándose en intent + extracción automática de referencias, y solo pide al usuario confirmación o ajustes puntuales.

**Cuándo se ejecuta**: SIEMPRE que el proyecto tiene frontend (web, landing, app, portfolio) Y `intent.ui_applicable != false`. NO se ejecuta para: APIs puras, CLIs, o backend-only.

**Prerequisitos**: `{proyecto}/intent` debe existir en Engram (obligatorio por Paso 0 de Fase 1). Si no existe, Paso 0 fue saltado — retroceder y ejecutarlo antes de continuar.

---

**Paso 1.5a — Extracción de referencia (POLIMÓRFICO — NUEVO)**

Antes de presentar opciones al usuario, el orquestador procesa la referencia visual capturada en intent (si existe) para extraer paleta, tipografía y mood tags automáticamente. Esto alimenta el pre-fill y queda disponible para el LLM-as-judge de Fase 4.

**Flujo**:

1. Leer `{proyecto}/intent` con `mem_search + mem_get_observation` (2 pasos).
2. Crear `.pipeline/references/` si no existe.
3. Según `intent.reference_source`, ejecutar extractor correspondiente:

| reference_source | Acción del orquestador |
|------------------|------------------------|
| `figma` | (1) `get_metadata(fileKey, nodeId)` para detectar si es design real (tiene frames + variables) o raster-only (una imagen pegada al canvas). (2) Si design real → `get_design_context` y extraer variables como tokens estructurados. (3) Si raster-only → `get_screenshot` → guardar PNG en `.pipeline/references/figma-raster.png` → continuar como tipo `image`. |
| `image` | (1) Copiar/descargar a `.pipeline/references/ref-image.{ext}`. (2) Color quantization: intentar `node ~/.claude/design-data/scripts/extract-palette.js {path}` (fallback: el orquestador inspecciona visualmente la imagen y lista 5-7 hex dominantes). (3) Inferir mood tags (warm/cool, light/dark, editorial/minimal/etc.) vía vision. (4) Inferir familia tipográfica si hay texto legible. |
| `url_website` | (1) `browser_navigate(url)` + `browser_take_screenshot(fullPage)` → guardar en `.pipeline/references/ref-site.png`. (2) Continuar como tipo `image`. |
| `brand_textual` | (1) Normalizar slug de marca (ej. "Linear" → "linear", "Apple" → "apple"). (2) `WebFetch("https://raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/{slug}.md", "extract palette + typography + tone")`. (3) Si falla, intentar variantes del slug (ej. "stripe" → "stripe-dashboard"). (4) Extraer tokens abstractos del DESIGN.md. |
| `preset` | Leer row correspondiente de `~/.claude/design-data/style-presets.csv` usando `intent.preset_row`. Usar columnas "CSS Tokens", "Heading Font", "Body Font", "Color Mood", "Reference Sites" para pre-llenar. |
| `none` | Solo preset del intent. Sin extracción adicional. |

4. **Consulta complementaria de awesome-design-md** (SIEMPRE, independiente del reference_source):
   - Según `intent.mood_preset`, fetchear 1-3 DESIGN.md de marcas reales como **referencia de tokens abstractos** (nunca copiar logos ni layouts):
     - `editorial-magazine` → nytimes, medium, the-verge
     - `swiss-minimal` → linear, stripe, vercel
     - `soft-luxury` → aesop, byredo, jacquemus
     - `neo-brutalism` → gumroad, basecamp
     - `immersive-storytelling` → apple, igloo
     - `playful-illustrated` → notion, dropbox, mailchimp
     - `y2k-revival` → (sin mapeo estándar — solo preset)
     - `monochrome-industrial` → (sin mapeo estándar — solo preset)
   - Guardar slugs fetcheados con éxito en `awesome_design_md_refs` del visual-direction.
   - Si WebFetch falla, no bloquear — continuar con preset.

5. **Persistir extracción en disco**:
   ```
   .pipeline/references/
   ├── ref-image.{ext}           # imagen original si aportó
   ├── figma-raster.png          # si Figma era raster-only
   ├── ref-site.png              # screenshot si url_website
   ├── extracted-palette.json    # {colors: [{hex, dominance}], confidence}
   ├── extracted-typography.json # {heading, body, accent, confidence}
   └── awesome-refs/             # DESIGN.md de marcas consultadas
       ├── linear.md
       └── stripe.md
   ```

6. **Si la extracción falla completamente** (imagen corrupta, URL inaccesible, Figma privado sin permisos): informar al usuario concretamente ("No pude acceder al Figma porque está privado — ¿podés cambiar a público o aportar screenshot?"), ofrecer 3 alternativas (preset puro del intent, imagen alternativa, continuar sin referencia con extracción vacía). NO bloquear el pipeline indefinidamente.

---

**Paso 1.5b — Presentación al usuario con pre-fill**

Con intent + extracción listas, presentar las 8 decisiones con **opciones pre-seleccionadas**. El usuario solo confirma o ajusta puntualmente.

**Reglas de pre-fill** (cómo derivar cada opción del intent + extracción):

| Pregunta | Fuente del pre-fill |
|----------|---------------------|
| 1. Estilo visual | `intent.mood_preset` → mapped (editorial-magazine→"a", immersive→"b", swiss-minimal→"c", neo-brutalism→"d", soft-luxury→variante "a"+warm, playful→"d" variante, y2k→"e" custom, monochrome-industrial→"e" custom) |
| 2. Hero | Según project_type + dials: landing + motion≥7 → "c" fondo animado; landing + motion<5 → "a" imagen estática; immersive → "b" video; bold → "f" texto hero puro |
| 3. Navegación | Según mood_preset: minimal/dashboard → "b" fija sólida; luxury/editorial → "a" transparente blur; brutalist → "b" fija bold; immersive → "a" transparente |
| 4. Galería | project_type=portfolio → "a" masonry; webapp → "n/a"; ecommerce → "b" carrusel drag |
| 5. Nivel animación | `intent.dials_suggested.motion_intensity`: 1-3→"a", 4-6→"b", 7-10→"c" |
| 6. Mood | `extracted_mood_tags`: dark→"a", light→"b", mixed→"c", high-contrast→"d". Fallback al preset "Color Mood" del CSV |
| 7. Tipografía | `extracted_typography` o preset "Heading Font": serif→"b" elegante/serif, sans geom→"d" neutro, display→"a", mono→"c" técnico |
| 8. Efectos especiales | dials + motion_intensity: smooth-scroll si ≥5, parallax si immersive preset, magnetic si brutalist/bold, text-reveal si editorial/luxury |

**Consultar recursos disponibles antes de mostrar** (mantener lógica existente):
1. Bóveda CodePen: `mem_search("codepen-vault")` → listar matches relevantes
2. 21st.dev: si `component_source="21st.dev"` → categorías aplicables
3. Design Intelligence: ya en css-foundation

**Template de presentación**:

```
🎨 Dirección Visual — {nombre-proyecto}

Pre-llené las opciones basándome en tu intent de Fase 1:
  • Preset: {mood_preset} ({label})
  • Originalidad: {originality}
  • Referencia: {reference_source}{ — {payload resumido}}

💡 EXTRAÍDO AUTOMÁTICAMENTE (si aplica):
{si extraction_status=success}:
  • Paleta detectada: {5-7 hex chips con label}
  • Tipografía inferida: {heading family + body family} (confianza: {%})
  • Mood tags: {editorial, warm, serif-driven, ...}
{si Figma raster-only detectado}:
  • ⚠️ Tu Figma es solo una imagen pegada (no design con frames/variables).
    Extraje paleta desde el raster — si querés un extracción más precisa,
    recreá el mockup con auto-layout + variables y pasame la URL de nuevo.
{si awesome-design-md fetch exitoso}:
  • Referencias abstractas consultadas: {linear, stripe, aesop, ...}
  • (NO copiaré logos ni composiciones — solo tokens: paleta, tipografía, motion)
{si extraction_status=failed}:
  • ⚠️ No pude extraer de la referencia: {motivo}. Uso el preset como base.

💡 RECURSOS DISPONIBLES:
{si bóveda tiene matches}: • Bóveda de efectos: {lista con tipo}
{si 21st.dev}: • Componentes animados (aurora, parallax, magnetic, gradient text, ...)
{siempre}: • Motion: CSS básico / Framer moderado / GSAP+Lenis inmersivo

═══════════════════════════════════════════════════
PRE-FILL (derivado de tu intent + extracción):

1. ESTILO VISUAL:    [ {a/b/c/d/e} ] → {label}
2. HERO:             [ {a-g} ] → {label}
3. NAVEGACIÓN:       [ {a-e} ] → {label}
4. GALERÍA:          [ {a-f o n/a} ] → {label}
5. NIVEL ANIMACIÓN:  [ {a/b/c} ] → {label}  (dial motion={N}/10)
6. MOOD ATMÓSFERA:   [ {a/b/c/d} ] → {label}
7. TIPOGRAFÍA:       [ {a-e} ] → {label}
8. EFECTOS:          [ {lista checkboxes activos} ]
═══════════════════════════════════════════════════

¿Confirmás todo? Respuestas válidas:
  • "ok" / "s" / "sí"           → guardar pre-fill tal como está
  • "cambiar 2 a f, 5 a c"      → ajustes puntuales
  • "rehacer el preset"         → volver a Paso 0 (Intent Clarifier)
  • "cambiar referencia"        → volver a Paso 0 con nueva ref
```

**Reglas del checkpoint (actualizadas — NO MÁS "decidí vos")**:
- El pre-fill SIEMPRE existe porque `intent` es obligatorio desde Paso 0. El usuario confirma o ajusta — nunca arranca de cero.
- Si responde "ok" / "s" → guardar el pre-fill sin cambios.
- Si ajusta puntualmente ("cambiar 2 a f") → aplicar cambio, re-mostrar resumen corto, volver a preguntar confirmación.
- Si dice "rehacer el preset" → re-ejecutar Paso 0 de Fase 1 con ajustes y re-entrar a Paso 1.5 con nuevo intent.
- **Límite anti-loop (NUEVO 2026-04-19 — audit)**: máximo 3 re-iteraciones de "rehacer el preset" por proyecto. A la 3ra, el orquestador responde: "Ya reelegimos el preset 3 veces. Para no dar vueltas, voy a fijar el último elegido ({mood_preset}) y avanzamos a Fase 2B. Si después querés cambios finos, vamos en Modo Modificación sobre un output concreto." Avanzar sin re-elegir.
- Si el brief original fijó un valor (ej. "quiero video de fondo"), marcarlo `[fijado por brief]` y no permitir cambio tácito.
- ❌ NO aceptar "decidí vos" — si el usuario lo dice, responder: "Ya decidí el pre-fill con tu intent. Revisá las 8 opciones y confirmá con 'ok' o ajustá las que quieras cambiar. No hay atajo — necesito tu confirmación explícita para no generar genérico."

---

**Paso 1.5c — Guardar en Engram con schema extendido**

```
mem_save(
  title: "{proyecto}/visual-direction",
  topic_key: "{proyecto}/visual-direction",
  type: "architecture",
  project: "{proyecto}",
  content: """
# Vínculo con intent de Fase 1
intent_observation_id: {id}
mood_preset: {heredado de intent}
originality: {heredado de intent}
reference_source: {heredado de intent}
reference_payload: "{heredado de intent}"

# Extracción automática (Paso 1.5a)
extraction_status: success | failed | skipped
extracted_palette: [{hex, dominance}]       # 5-7 colors
extracted_typography: {heading, body, accent, confidence}
extracted_mood_tags: [editorial, warm, serif-driven, ...]
reference_images_paths: [.pipeline/references/...]
awesome_design_md_refs: [linear, stripe, aesop]
figma_raster_detected: true | false         # solo si reference_source=figma

# Decisiones VDC (Paso 1.5b, confirmadas o ajustadas por el usuario)
estilo: {label completo con mapeo}
hero: {label}
nav: {label}
galeria: {label | n/a}
animacion_nivel: sutil | moderado | inmersivo
mood_atmosfera: oscuro | claro | mixto | alto-contraste
tipografia_familia: display | elegante | tecnico | neutro | custom
efectos_especiales: [lista]

# Dials finales (heredados del intent, ajustables en este paso)
dials:
  design_variance: {1-10}
  motion_intensity: {1-10}
  visual_density: {1-10}

# Recursos concretos elegidos (para frontend-developer)
recursos_elegidos: [vault:slug, 21st:component-type]

# Anti-patterns ejecutables (heredados de intent.anti_patterns_HIGH + preset CSV)
anti_patterns_HIGH: [lista de strings bloqueantes]

# Referencia para LLM-as-judge de Fase 4
reference_for_qa: .pipeline/references/{ref-file}  # path absoluto si hay imagen
"""
)
```

**Phase Gate → Paso 2 de Fase 2** (ENFORCED):

Antes de delegar a ui-designer, ejecutar `enforce_phase_gate("{proyecto}", "paso_2_fase_2", ["{proyecto}/visual-direction"])`:

```
python tools/atlas_dispatcher.py check-phase paso_1_fase_2 paso_2_fase_2
```

**Validación obligatoria**:
- Si `{proyecto}/visual-direction` NO existe → FASE BLOQUEADA. Mensaje: "Paso 2 Fase 2 blocked: {proyecto}/visual-direction missing. Paso 1.5 no fue completado correctamente — re-ejecutar completo."
- Verificar que `visual_direction.extraction_status ∈ [success, failed, skipped]` (si existe cajon)
- Verificar que decisiones VDC fueron confirmadas por usuario (booleano en contenido)

**Si ALL checks PASS** → desbloquea Paso 2 Fase 2, delega a ui-designer
**Si FALLA** → halt, devuelve BLOQUEADORES message

---

**Qué presenta al usuario** (bloque legacy — ahora cubierto por Paso 1.5b, mantenido como referencia de las 8 preguntas y sus opciones exhaustivas):

```
🎨 Dirección Visual — {nombre-proyecto}

Basado en el análisis de industria ({categoría del Design Intelligence}),
necesito tu input en estas decisiones clave:

💡 RECURSOS DISPONIBLES (lo que ya tenemos listo):
{si hay efectos en bóveda CodePen}:
  • Bóveda de efectos probados: {lista con nombre + tipo, ej: "Liquid Morphology Slideshow (slider 3D)",
    "Draggable Image Gallery (galería con drag)", "Elastic Accordion Cards (cards animadas)"}
{si component_source es 21st.dev}:
  • 21st.dev: biblioteca de componentes animados React (aurora backgrounds, parallax heroes,
    gradient text, magnetic buttons, animated cards, etc.)
{siempre}:
  • Animaciones: CSS (básico), Framer Motion (moderado), GSAP + Lenis (inmersivo)
  • Efectos creativos: partículas, shaders, cursor custom, text reveal, smooth scroll

Podés elegir cualquiera de estos o describir lo que imaginás:

1. ESTILO VISUAL
   a) Editorial/magazine — layouts asimétricos, tipografía protagonista, whitespace generoso
   b) Inmersivo/cinematic — full-bleed, video/parallax, scroll storytelling
   c) Minimalista/funcional — clean, mucho aire, contenido primero
   d) Bold/colorido — colores vibrantes, formas atrevidas, gradientes llamativos
   e) Otro: ___

2. HERO / PRIMER IMPACTO
   a) Imagen estática con overlay de texto
   b) Video de fondo en loop
   c) Fondo animado (aurora, partículas, gradient mesh)
   d) Parallax multi-capa (imagen + texto con profundidad)
   e) Slider/carrusel de imágenes
   f) Texto hero puro (sin imagen, tipografía impactante)
   {si bóveda tiene slider/hero}: g) 🗄️ De la bóveda: {nombre del efecto} — {descripción corta}

3. NAVEGACIÓN
   a) Transparente con blur al scroll (luxury/modern)
   b) Fija sólida con logo + links
   c) Hamburger minimalista (siempre, incluso en desktop)
   d) Sidebar lateral
   e) Mega-menu con sub-secciones

4. GALERÍA / SHOWCASE (si aplica)
   a) Grid masonry (Pinterest-style)
   b) Carrusel horizontal con drag
   c) Lightbox con zoom
   d) Scroll horizontal full-width
   e) Grid con hover reveal (info aparece al pasar el mouse)
   {si bóveda tiene galería/cards}: f) 🗄️ De la bóveda: {nombre del efecto} — {descripción corta}

5. NIVEL DE ANIMACIÓN
   a) Sutil — fade-in al scroll, hovers suaves (rápido de implementar)
   b) Moderado — stagger reveals, parallax suave, transiciones entre secciones
   c) Inmersivo — scroll-triggered animations, parallax multi-capa, efectos de cursor, 
      animaciones de texto (más tiempo de implementación)

6. MOOD / ATMÓSFERA
   a) Oscuro (dark mode primario)
   b) Claro (light mode primario)
   c) Mixto (secciones que alternan)
   d) Alto contraste (blanco/negro con accent color fuerte)

7. TIPOGRAFÍA (influye en el mood general)
   a) Display/impactante — fonts grandes, bold, protagonistas (Clash Display, Syne, Bricolage)
   b) Elegante/serif — serif moderno, editorial (Fraunces, Newsreader, Playfair)
   c) Técnico/mono — fuentes monospace o grotescas (Space Mono, JetBrains, IBM Plex)
   d) Neutro/funcional — sans-serif limpia, no protagonista (sin preferencia especial)
   e) Otro: ___

8. EFECTOS ESPECIALES (opcional, elegir 0-3)
   [ ] Cursor personalizado / efecto magnetic en botones
   [ ] Texto animado (typewriter, gradient shimmer, split reveal)
   [ ] Smooth scroll (Lenis)
   [ ] Parallax en imágenes/secciones
   [ ] Transiciones de página / morphing entre secciones
   [ ] Fondo con partículas / generativo
   {si bóveda tiene efectos relevantes}: [ ] 🗄️ {nombre}: {descripción corta}
   [ ] Otro: ___

Si no estás seguro de algo, puedo sugerir lo que mejor encaja con tu proyecto.
Los items marcados con 🗄️ ya están probados y listos para adaptar a tu proyecto.
```

**NOTA — lógica de bóveda CodePen + reglas del checkpoint**: cubiertas en Paso 1.5a (consulta) y Paso 1.5b (pre-fill + confirmación). El bloque legacy de arriba existe solo para referenciar el listado exhaustivo de opciones cuando pre-fill necesita expandir una elección.

**Paso 2 — ui-designer + security-engineer** (paralelo, DESPUÉS del Visual Direction Checkpoint)
- **ui-designer**: Recibe spec + rutas a `{proyecto}/css-foundation` + **`{proyecto}/visual-direction`** + **`{proyecto}/intent`** (para acceder a preset_row, anti_patterns_HIGH, dials, reference_source) + mismos campos DESIGN_SYSTEM/NOTHING_SCOPE/REFERENCIA si aplica + TIPO_PROYECTO si mobile → Guarda en: `{proyecto}/design-system` → Devuelve: resumen (componentes clave, paleta, tipografía, **behavioral specs alineados a visual-direction + intent**)
- **security-engineer**: Recibe spec del proyecto → Guarda en: `{proyecto}/security-spec` → Devuelve: resumen (amenazas identificadas, headers requeridos)

Actualiza DAG State. Informa al usuario: "Arquitectura lista. N tareas listas para desarrollo."

---

