# Orchestrator — Pipeline (5 Phases + 2B)

> Lazy reference extracted from orquestador.md in F32 (knowledge decomposition).
> Load when the orchestrator facade points here. Content verbatim — behavior unchanged.

## Pipeline: 5 Fases + Fase 2B

### Phase Gates (qué debe existir antes de cada fase)
- **Fase 1 requiere**: `{proyecto}/intent` en Engram (generado por Intent Clarifier — ver Paso 0 abajo)
- **Fase 2 requiere**: `{proyecto}/tareas` + `{proyecto}/intent` en Engram
- **Fase 2B requiere**: `{proyecto}/css-foundation`, `{proyecto}/design-system`, `{proyecto}/security-spec`, `{proyecto}/visual-direction` en Engram
- **Fase 3 requiere**: Los cajones de Fase 2 + brand aprobado (si aplica)
- **Fase 4 requiere**: TODAS las `{proyecto}/tarea-{N}` con STATUS: PASS en `{proyecto}/qa-{N}`
- **Fase 5 requiere**: `{proyecto}/certificacion` con STATUS: CERTIFIED

Para verificar un phase gate:
1. Buscar el cajon requerido con `mem_search("{proyecto}/{cajon-requerido}")`
2. Si NO retorna observation_id → FASE BLOQUEADA, no continuar
3. Si retorna → verificar que el contenido tiene el STATUS esperado via `mem_get_observation`

### FASE 1 — Planificación (incluye Request Routing + Intent Clarifier + decisión de stack)

**Paso -0.5 — Request Routing (Bloque 1L.1)** [OBLIGATORIO antes de Paso 0]

Antes de evaluar si el brief es vago o claro, el orquestador debe clasificar QUÉ TIPO DE PEDIDO es el del usuario. Esto desambigua casos como "mejorá la landing" que históricamente caían en "auditoría" cuando el usuario quería un rediseño profundo.

**Acción**:
```python
# El dispatcher expone classify_user_intent(prompt) que retorna:
# {"intent": "audit"|"redesign"|"implement"|"validate"|None,
#  "confidence": "high"|"medium"|"low",
#  "fallback_intent": str|None,
#  "rationale": str,
#  "escalation_question": str|None}
result = dispatcher.classify_user_intent(user_prompt)
```

**Decisión según `confidence`**:
- `high` → Proceder con la ruta indicada por `intent`:
  - `audit` → modo análisis: solo lectura, sin tocar código. Sin Fase 2B/3/5.
  - `redesign` → Pipeline completo Fase 1 + 2 + 2B + 3. Pasar a Paso 0 (Intent Clarifier).
  - `implement` → Saltar Fase 2/2B (diseño ya existente). Ir directo a Fase 3 con las tareas concretas.
  - `validate` → Solo Fase 4 (evidence-collector + reality-checker). Sin dev work.
- `medium` → Proceder igual pero loggear en `{proyecto}/intent-routing` con confidence=medium para auditoría.
- `low` → **ESCALAR AL USUARIO** mostrando `escalation_question`. NO decidir solo. Esperar respuesta antes de seguir.

**Persistencia**: guardar el resultado en `{proyecto}/intent-routing` (cajón Engram + disco). Distinto de `{proyecto}/intent` (que es el brief capture del Paso 0 — ese sigue existiendo).

**Disable** (rollback runtime): `ATLAS_INTENT_CLASSIFIER_DISABLED=1` desactiva 1L.1. El orquestador queda en comportamiento pre-1L (sin routing automático).

**Importante**: Request Routing NO reemplaza el Intent Clarifier (Paso 0). Son ortogonales:
- **Request Routing (Paso -0.5, Bloque 1L.1)**: clasifica qué tipo de pedido es (verbo principal).
- **Intent Clarifier (Paso 0)**: captura el brief de diseño (mood preset, originalidad, referencias).

---

1. Busca proyecto en progreso: `mem_search("{proyecto}/estado")`
2. Si existe → recupera con `mem_get_observation` y reanuda desde donde estaba (el Intent ya fue capturado — saltear Paso 0)
3. Si no existe → **ejecutar Paso 0 (Intent Clarifier) ANTES de decidir stack**:

**Paso 0 — Intent Clarifier** (obligatorio, solo proyectos nuevos)

Antes de decidir stack o delegar a project-manager-senior, evaluar si el brief del usuario es claro o vago. Esto evita que prompts genéricos generen outputs genéricos — caso típico del falso positivo donde el pipeline infiere defaults SaaS cuando el usuario no especifica.

**Cuándo se ejecuta**: SIEMPRE al iniciar un proyecto nuevo. Si se retoma (existe `{proyecto}/estado` en Engram), saltear — el intent ya está en DAG State.

**Heurística de vaguedad del brief** (clarity score 0-10):
- Word count del brief del usuario:
  - < 20 palabras → -3
  - 20-50 → -1
  - 50-150 → +2
  - > 150 → +3
- Vocabulario de diseño presente (buscar: editorial, minimal, brutalist, luxury, bold, warm, dark, cinematic, immersive, playful, mono, serif, display, whitespace, grid, y nombres de marcas/sitios): cada match +1 (máx +4)
- Referencias mencionadas (URL, "como X", Figma link, path de imagen, nombre de marca): cada una +2 (máx +4)
- Features concretos (menciona 3+ funcionalidades específicas): +2
- Público objetivo mencionado: +1

**Decisión según score**:
- 0-3 → **muy vago** — presentar las 6 preguntas
- 4-6 → **parcial** — presentar solo las que el brief no responde implícitamente
- 7-10 → **claro** — presentar SOLO Q3 (mood preset) y Q5 (originalidad) para confirmar

**Formato de presentación al usuario**:

```
🎯 Entendiendo tu proyecto — {resumen de 1 línea del brief}

Para darte un resultado profesional y no genérico, te hago {N} preguntas
con opciones. Elegí la letra; si ninguna encaja, escribí "otra" + breve
descripción.

Q1. ¿Qué tipo de proyecto es?  (saltar si brief ya lo especifica)
  a) Landing page — 1 pantalla con CTA claro
  b) Sitio web multi-página — contenido + nav
  c) Web app — login + dashboard + features
  d) Mobile app
  e) API / backend puro
  f) Juego navegador
  g) Otra: ___

Q2. ¿En qué industria / rubro se ubica?
  {dinámico: ejecutar `node ~/.claude/design-data/search.js "{brief_keywords}" --limit 5`}
  a-e) Top 5 industrias coincidentes del motor
  f) Otra: ___

Q3. ¿Qué vibe visual te encaja? (OBLIGATORIA — fija paleta, tipografía y motion)
  a) 📰 Editorial premium — serif elegante, whitespace, cálido. Ej: NYTimes, Medium
  b) 🔲 Minimal suizo — grid, mono, funcional, alto contraste. Ej: Linear, Stripe docs
  c) ☁️ Luxury soft — cremas/beiges, serif display, spring motion. Ej: Aesop, Byredo
  d) 🔨 Neo-brutalist — bordes gruesos, primarios vibrantes, shadows hard. Ej: Gumroad
  e) 🎬 Inmersivo cinematic — scroll storytelling, video bg, parallax. Ej: Apple, agencias
  f) 🎨 Playful illustrated — pasteles, formas redondas, mascots. Ej: Notion marketing
  g) 💎 Y2K/retro — chrome, holográfico, translúcido. Ej: portfolios creativos
  h) 🌑 Monochrome industrial — B&W puro, mono, print-inspired. Ej: Berghain, arquitectura
  i) Otra / describí con tus palabras: ___

Q4. ¿Tenés alguna referencia visual para inspirarme? (OPCIONAL pero recomendada)
  a) Figma — pegá la URL
  b) Una imagen — pegá el path local (PNG/JPG) o URL pública
  c) Un sitio que te guste — "como linear.app", "parecido a aesop.com"
  d) Una marca específica — "como Stripe", "como Apple"
  e) No tengo referencia — usá el preset que elegí en Q3

Q5. ¿Nivel de originalidad / riesgo visual? (OBLIGATORIA — calibra los dials)
  a) Conservador — patrón conocido, seguro, no sorprende al usuario
  b) Balanceado — preset con personalidad, memorable pero sin riesgo
  c) Experimental — distintivo, puede dividir opiniones, más tiempo de implementación

Q6. ¿Público objetivo? (opcional, afecta tono y color accent)
  a) B2B / profesional
  b) Consumidor general (B2C)
  c) Creativos / diseñadores / músicos / fotógrafos
  d) Gen Z / jóvenes
  e) Luxury / premium
  f) Mixto / otro: ___
```

**Reglas de presentación**:
- Saltar preguntas cuyo valor ya esté en el brief (ej. si dice "landing para clínica dental": Q1=a, Q2=a/salud, solo queda preguntar Q3, Q4, Q5, Q6).
- Q3 y Q5 son SIEMPRE obligatorias aunque el score sea alto — son las que diferencian output genérico de output específico.
- Para Q2, ejecutar `search.js` ANTES de presentar para listar industrias reales del motor (161 industrias indexadas).
- Si el usuario responde "otra" en Q3 con descripción libre, mapear a preset más cercano + anotar customización (ej. "editorial pero oscuro" → `preset: editorial-magazine + customizations: [dark_mode]`).

**NO permitido en Paso 0 (proyectos con UI)**:
- ❌ "decidí vos" sin al menos responder Q3 (mood_preset) y Q5 (originalidad). Si el usuario dice "decidí vos", el orquestador DEBE insistir: "Necesito que elijas al menos el vibe visual (Q3) para no generar algo genérico. ¿Cuál de los 8 encaja mejor?"
- ❌ Defaults automáticos sin consultar al usuario en proyectos con UI.

**Salida de emergencia — loop de "otra"/elusión (NUEVO 2026-04-19 — audit)**:

Si el usuario responde Q3 con "otra" o texto evasivo 2 veces consecutivas sin definir mood_preset claro, o responde Q5 evasivamente 2 veces, el orquestador aplica esta regla:

```
intento = 1:
  mostrar las 8 opciones otra vez con descripciones más ricas (Reference Sites del CSV)
intento = 2:
  decir: "Necesito una dirección concreta para no generar genérico. Elegí una letra (a-h) o
          escribí una frase en el formato: '<editorial|minimal|luxury|brutalist|immersive|
          playful|retro|industrial> + originalidad <conservador|balanceado|experimental>'.
          Si no, uso el default para tu industria: {industria → preset recomendado del search.js}."
intento = 3:
  aplicar default derivado del industry search.js (el motor ya tiene mapeo industria → preset),
  guardar intent con nota "mood_preset: default_industry_fallback",
  avisar al usuario qué eligió para que pueda revisar en Visual Direction Checkpoint.
```

Esto evita que el Intent Clarifier quede bloqueado indefinidamente si el usuario no colabora. El default desde industry search.js es siempre razonable (ej. clínica → editorial-minimal según DI engine).

**Excepciones — proyectos sin UI**:
Si Q1 = `e` (API/backend puro) o `f` (juego sin frontend custom) o el brief explicita "solo backend", "solo API", "CLI":
- Saltear Q3 (mood), Q4 (referencia visual), Q6 (audiencia visual).
- Guardar en intent: `project_type: api | backend | cli`, `mood_preset: "n/a"`, `ui_applicable: false`.
- El Visual Direction Checkpoint y Fase 2B (assets visuales) se saltearán automáticamente downstream (ya existe esa regla en Fase 2 Paso 1.5 y en activación de Fase 2B).

**Interpretar y normalizar respuestas**:

Mapear Q3 a `preset_key` de `~/.claude/design-data/style-presets.csv`:
```
a → editorial-magazine      (row 1)
b → swiss-minimal           (row 2)
c → soft-luxury             (row 3)
d → neo-brutalism           (row 4)
e → immersive-storytelling  (row 7)
f → playful-illustrated     (row 9)
g → y2k-revival             (row 5)
h → monochrome-industrial   (row 10)
i → "custom" + descripción  (usar preset más cercano como base)
```

Mapear Q5 a dials cuantitativos:
```
conservador  → design_variance: 3, motion_intensity: 3
balanceado   → design_variance: 5, motion_intensity: 5
experimental → design_variance: 8, motion_intensity: 7
```
(El dial `visual_density` se toma directamente del preset, columna "Visual Density" del CSV)

**Guardar resultado en Engram**:
```
mem_save(
  title: "{proyecto}/intent",
  topic_key: "{proyecto}/intent",
  type: "decision",
  project: "{proyecto}",
  content: """
project_type: {Q1}
industry: {Q2}
mood_preset: {Q3 mapeado a preset_key}
preset_row: {número de row en style-presets.csv}
preset_customizations: [{si Q3=i o describió customizaciones}]
reference_source: {figma | image | url_website | brand_textual | preset | none}
reference_payload: "{Q4 value raw}"
originality: {conservador | balanceado | experimental}
dials_suggested:
  design_variance: {3|5|8}
  motion_intensity: {3|5|7}
  visual_density: {del preset CSV}
audience: {Q6}
anti_patterns_HIGH: {heredados del preset, columna 'Anti Patterns' del CSV, parseados a lista}
css_tokens_inherited: {del preset, columna 'CSS Tokens'}
reference_sites_inspiration: {del preset, columna 'Reference Sites'}
clarity_score_initial: {0-10}
user_brief_raw: "{primeras 200 chars del brief del usuario}"
intent_version: 1
"""
)
```

**Efecto cascada** (qué agentes consumirán `{proyecto}/intent`):
- **project-manager-senior** (este Paso 4 abajo): recibe `intent.project_type` + `intent.industry` + `intent.audience` para scope tareas
- **ux-architect** (Fase 2 Paso 1): recibe `intent.mood_preset` + `intent.dials_suggested` para parametrizar CSS tokens (NO defaults minimal si preset es editorial)
- **Visual Direction Checkpoint** (Fase 2 Paso 1.5): PRE-FILLS las 7 preguntas del checkpoint basándose en `intent`, el usuario solo confirma/ajusta (no arranca de cero)
- **brand-agent** (Fase 2B): recibe `intent.mood_preset` + `intent.reference_source/payload` + `intent.anti_patterns_HIGH` para generar `brand.json` no-genérico
- **ui-designer** (Fase 2 Paso 2): consume `intent.mood_preset` via `style-presets.csv` (ya tiene lógica Paso 0b-bis, ahora queda auto-activada)
- **evidence-collector / reality-checker** (Fases 3 y 4): comparan output vs `intent.reference_payload` (si hay imagen/URL) como visual fidelity check

---

4. Con `{proyecto}/intent` guardado, continuar con **decidir stack y estructura**:

   **Decisión de stack** (el orquestador decide, NO el PM):
   - Si el usuario especificó stack → usar ese
   - Si no → aplicar tabla resumen:

     | Tipo proyecto | Stack base | Estructura |
     |--------------|-----------|------------|
     | Landing/portfolio/web estática | Vite + React + Tailwind (Astro si content-heavy) | Single-repo |
     | Frontend + backend separados | Next.js/SvelteKit + Hono + Drizzle + tRPC | Monorepo |
     | MVP/prototipo rápido | rapid-prototyper elige (ver su matriz) | Single-repo |
     | App móvil (iOS/Android) | React Native + Expo SDK 52+ + Expo Router | Single-repo |
     | Juego de navegador | Phaser.js/PixiJS + Vite + TypeScript | Single-repo |
     | API pura | Hono + Drizzle + PostgreSQL + Zod | Single-repo |

     Addons: +Socket.IO/PartyKit (real-time) | +BullMQ/Inngest (background jobs)

   **Decisión de design system** (el orquestador decide junto con stack):
   - Si el usuario dice "estilo Nothing", "Nothing design", "Nothing phone style", "nada design" → `design_system: "nothing-full"`
   - Si el usuario pide Nothing solo para una sección (ej: "hero estilo Nothing", "dashboard Nothing style", "stats con estilo Nothing") → `design_system: "nothing-partial"` + `nothing_scope: ["hero"]` (lista de secciones)
   - Si no menciona Nothing → `design_system: "custom"` (comportamiento por defecto, ux-architect + ui-designer crean design propio)
   - Si dice "sin design system" → `design_system: "none"`

   **Referencia**: `nothing-design-reference.md` — archivo de referencia cargado condicionalmente por agentes de Fase 2 y Fase 3.

   **Decisión de component source** (el orquestador decide junto con stack):
   - Si el usuario pide "visual", "impactante", "animado", "wow", "21st.dev", "componentes animados" → `component_source: "21st.dev"`
   - Si el usuario pide efectos específicos de CodePen o dice "busca en CodePen" → `component_source: "codepen"`
   - Si no menciona ninguno → `component_source: "custom"` (default — todo se construye manual)
   - `component_source` NO es excluyente: frontend-developer puede consultar 21st.dev puntualmente aunque no sea el source principal
   
   **21st.dev via capability `documentation`** (provider: context7, library ID `/websites/21st_dev_community_components`): frontend-developer lo consulta directamente — no necesita agente intermediario (a diferencia de CodePen que usa codepen-explorer).

5. Delega a **project-manager-senior**:
   - Pasa: spec del usuario (texto directo) + **stack decidido** + **estructura** (monorepo/single) + **`{proyecto}/intent` topic_key** (para que PM lea project_type + industry + audience y dimensione tareas apropiadamente)
   - Pide que guarde en Engram: `{proyecto}/tareas`
   - Criterio: lista granular de tareas (30–60 min c/u) con criterios de aceptación exactos. El scope debe reflejar intent.project_type (una landing NO tiene 40 tareas — son 5-8; una webapp sí tiene 30-60).
6. Actualiza DAG State en `{proyecto}/estado` (incluir stack, estructura, y referencia a `{proyecto}/intent`)
7. Muestra al usuario: resumen de N tareas + stack elegido + resumen del intent capturado (preset + originalidad + referencia)

8. **PAUSA OBLIGATORIA — Aprobación de scope antes de Fase 2:**
   ```
   ✅ Planificación lista — {nombre-proyecto}

   Intent:
     • Tipo: {project_type}
     • Industria: {industry}
     • Vibe visual: {mood_preset}
     • Originalidad: {originality}
     • Referencia: {reference_source — figma/image/url_website/brand_textual/preset/none}
     • Dials: variance={design_variance}, motion={motion_intensity}, density={visual_density}

   Stack: {stack elegido}
   Estructura: {monorepo | single-repo}
   Design System: {nothing-full | nothing-partial (scope: [...]) | custom | none}
   Componentes: {21st.dev | codepen | custom}
   {N} tareas identificadas

   ¿Empezamos con la arquitectura y el desarrollo?
     s) Sí, continuar
     c) Quiero cambiar algo del scope, stack o intent
   ```
   → Si pide cambios: si el cambio es de intent (preset/originalidad/referencia), re-ejecutar Paso 0 con las correcciones y re-delegar PM. Si es de scope/stack, solo re-delegar PM con correcciones, actualizar DAG State, volver al paso 7.
   → Si aprueba: continuar a Fase 2

---

**Phase Gate → Fase 2** (ENFORCED — REAL Engram Integration, Bloque 1A.11):

Antes de delegar a ux-architect, ejecutar `enforce_phase_gate("{proyecto}", "fase_2", ["{proyecto}/tareas", "{proyecto}/intent"])` desde dispatcher:

```
python tools/atlas_dispatcher.py check-phase fase_1 fase_2
```

**NOTA**: A partir de Bloque 1A.11, enforce_phase_gate() busca REALMENTE en Engram (no simulación):
- Si cajón existe → found → OK, continúa
- Si cajón falta → not_found → BLOQUEADO
- Si Engram timeout → timeout → intenta fallback disco
  - Disk existe → OK, continúa
  - Disk también falta → PENDING (requiere confirmación usuario)

**Validación obligatoria**:
- Si `{proyecto}/intent` NO existe → FASE BLOQUEADA. Mensaje: "Fase 2 blocked: {proyecto}/intent missing. Paso 0 (Intent Clarifier) fue saltado indebidamente — volver a ejecutarlo."
- Si `{proyecto}/tareas` NO existe → FASE BLOQUEADA. Mensaje: "Fase 2 blocked: {proyecto}/tareas missing. Fase 1 falló silenciosamente — re-delegar a project-manager-senior."
- Si Engram timeout → PENDING. Usuario debe confirmar manualmente que ambos cajones existen.

**Si ALL checks PASS** → desbloquea Fase 2, delega a ux-architect
**Si FALLA** → halt, devuelve BLOQUEADORES message, NO continuar

**Auto-format opt-in**: Si el proyecto tiene `.prettierrc`, `biome.json`, o `eslint.config` con reglas de fix, el orquestador indica a los agentes dev que ejecuten el formatter despues de cada archivo escrito. No es un hook global — se decide por proyecto en Fase 1 y se incluye como instruccion en el handoff a agentes dev: `"formatter": "npx prettier --write"` (o `npx biome check --fix`, segun el stack).

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
   QA Intento: {intento_actual}/3 (tracked en DAG State)
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
      - NO marcar como QA FAIL de negocio (no incrementa qa_intento_actual)
      - Reintenta 1x (mismo intento de QA). Si falla validación 2x → escalar al usuario
   
   4. **Si Engram write falla con timeout/error (Engram error, NO formato error)**:
      - NO marcar como FAIL. Reintenta evidence-collector (mismo intento, no incrementa contador)
      - Si falla 2x Engram → informar al usuario "Engram timeout — procederá como QA manual" y continuar
   
   5. **Si evidence-collector crashea (zero return)**:
      - Reintenta 1x (mismo intento). Si crashea 2x → escalar al usuario

   **Mobile**: si evidence-collector reporta "QA visual limitada", informar al usuario una vez: "QA de tareas mobile se limita a validación de build — no hay simulador visual disponible."
   **El orquestador mantiene el contador de intentos en DAG State** en `tareas[N].qa_intento_actual`, incrementándolo SOLO en fallos funcionales de QA, NO en fallos de Engram.

**Umbral PASS/FAIL:**
- Rating B- o superior → PASS
- Rating C+ o inferior → FAIL (requiere reintento)
- 0 errores en consola es OBLIGATORIO para PASS
- **Mobile responsive OBLIGATORIO para PASS**: 0 failures del "Mobile responsive checklist" de evidence-collector. Cualquier fallo (scroll-h no deseado, inputs <16px, touch targets <44px, sidebar con margin-left en mobile, parallax sin guard) → FAIL automático sin importar el rating general. Aplica a todas las tareas de UI web — excepción única: `TIPO_PROYECTO: mobile` (React Native) que usa QA distinta.

6. **Si QA PASS**:
   - evidence-collector retorna: `STATUS: PASS + ENGRAM: {proyecto}/qa-{N}`
   - Orquestador verifica que `{proyecto}/qa-{N}` existe en Engram (mem_search → mem_get_observation)
   - **Actualiza DAG State: `tareas[N].status = "completada"` + `tareas[N].qa_intento_actual = {final count}`**
   - Continúa con tarea N+1

7. **Si QA FAIL (intento < 3)**:
   - evidence-collector retorna: `STATUS: FAIL + issues`
   - Orquestador incrementa: `tareas[N].qa_intento_actual++`
   - Pasa feedback específico al dev agent: "QA falló: {lista de issues}. Intento {qa_intento_actual}/3. Arregla y reintenta."
   - Vuelve al paso 3 (re-delega mismo dev agent)

8. **Si QA FAIL (intento = 3) → ESCALACIÓN (tarea NO avanza)**:
   - evidence-collector ha fallado 3 veces tras arreglos del dev
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

### FASE 4 — SEO + Certificacion Final (secuencia con tiers)

Solo ejecutar cuando TODAS las tareas estan en PASS o aceptadas con limitacion.

**La Fase 4 se ejecuta en 4 pasos secuenciales para evitar re-trabajo:**

```
Paso 1: seo-discovery (tier: "structural")
  Solo lo que NO cambia si el contenido se modifica:
  robots.txt, sitemap.xml, semantic HTML, heading hierarchy, lang attr

Paso 2: api-tester + performance-benchmarker (paralelo)
  Endpoints + Core Web Vitals + bundle analysis

Paso 3: seo-discovery (tier: "full")
  Todo lo que DEPENDE del contenido final:
  meta tags, JSON-LD, keyword mapping+intent, OG images,
  llms.txt, analisis competitivo, GEO scoring

Paso 4: reality-checker (gate final)
  Lee todos los cajones y certifica
```

**Por que 2 pasadas de SEO**: si reality-checker dice NEEDS WORK y volvemos a Fase 3,
solo hay que re-ejecutar `tier: "full"` (el structural ya esta hecho). Ahorra ~1000 tokens por ronda.

---

**Paso 1 — seo-discovery (structural)**
- Pasa al agente: `tier: "structural"`, project_dir, URL
- Implementa: robots.txt, sitemap.xml, semantic HTML check, heading hierarchy
- Guarda en: `{proyecto}/seo` con `seo_tier: "structural"`
- Devuelve: Return Envelope con archivos creados

**Paso 2 — api-tester + performance-benchmarker** (paralelo, despues del paso 1)

**api-tester** (CONDICIONAL — solo si hay backend/API)
- **Skip condition**: si DAG State `stack.backend: "none"` Y no hay tareas de tipo `backend` en `{proyecto}/tareas` → SALTAR api-tester completamente. Marcar `api_tester: "skipped-no-backend"` en DAG State. Esto aplica a: landing pages, portfolios, sitios estáticos, juegos client-side.
- Lee: `{proyecto}/api-spec` (generado por backend-architect; **sin fallback** — tareas tiene formato incompatible)
- **ANTES de lanzar**: verificar `mem_search("{proyecto}/api-spec")`. Si no existe y hay tareas backend → re-delegar a backend-architect para que genere SOLO el api-spec. NO lanzar api-tester sin api-spec.
- Handoff: `PROYECTO: {nombre}, PROJECT_DIR: {directorio}, URL: http://localhost:{puerto}, LEE: {proyecto}/api-spec`
- Guarda en: `{proyecto}/api-qa`
- Devuelve: N endpoints validados, issues criticos

**performance-benchmarker**
- Handoff: `PROYECTO: {nombre}, URL: http://localhost:{puerto}`
- Guarda en: `{proyecto}/perf-report`
- Devuelve: Core Web Vitals, tiempos de carga, bottlenecks

**Paso 3 — seo-discovery (full)**
- Pasa al agente: `tier: "full"`, project_dir, URL
- Implementa: meta tags, JSON-LD, keyword mapping+intent, OG images, llms.txt+llms-full.txt, analisis competitivo (si aplica), GEO scoring (si aplica)
- Guarda en: `{proyecto}/seo` con `mem_update` (upsert sobre structural), `seo_tier: "full"`
- Devuelve: Return Envelope con score completo

**Paso 4 — reality-checker** (ejecutar AL FINAL, despues de los 3 pasos)
- Handoff: `PROYECTO: {nombre}, PROJECT_DIR: {directorio}, URL: http://localhost:{puerto}`
- Lee: `{proyecto}/qa-*`, `{proyecto}/seo` (espera tier=full), `{proyecto}/api-qa`, `{proyecto}/perf-report`
- Guarda en: `{proyecto}/certificacion`
- Devuelve: **CERTIFIED** | **NEEDS WORK** (con lista de blockers)

**Si un agente Fase 4 retorna fallido:**
- seo-discovery fallido → continuar sin SEO score (warn usuario), reality-checker evalúa sin `{proyecto}/seo`
- api-tester fallido → continuar sin API QA (warn usuario), reality-checker evalúa sin `{proyecto}/api-qa`
- performance-benchmarker fallido → continuar sin perf report (warn usuario)
- reality-checker fallido → BLOQUEAR. Re-intentar 1 vez. Si falla de nuevo, escalar al usuario
- Los agentes fallidos se reportan en el resumen final como "no evaluado"

Si **NEEDS WORK** → evaluar blockers:
  - Fixes menores (< 3 tareas): volver a Fase 3 solo para esas tareas, luego **re-ejecutar solo Paso 3 (seo full) + Paso 4 (reality-checker)** — el structural (Paso 1) y api+perf (Paso 2) NO se repiten
  - Estructurales: presentar al usuario para decision (fix vs aceptar con deuda tecnica documentada)
  No avanzar a Fase 5.

**Límite de re-certificación**: máximo **3 ciclos** de NEEDS WORK -> fix -> re-certify.
Si después de 3 ciclos sigue NEEDS WORK:
1. Presentar al usuario el reporte completo de reality-checker
2. Preguntar: "¿Publicar con limitaciones conocidas o seguir iterando manualmente?"
3. Si elige publicar → marcar `certified_with_caveats: true` + lista de issues abiertos en DAG State
4. Trackear `recertification_cycles` en DAG State (incrementar en cada ciclo)

Si **CERTIFIED** → evaluar si el usuario ya pre-autorizó git/deploy:

**Detección de pre-autorización** (leer el mensaje original del usuario):
- Si contiene "sube", "push", "git", "deploy", "publica", "lanza" → **pre-autorizado: proceder directamente a Fase 5 sin preguntar**
- Si NO contiene ninguna de esas palabras → mostrar resumen y pedir confirmación:

```
✅ PROYECTO CERTIFICADO

Reality Checker aprobó [nombre-proyecto].
Resumen: {N} tareas completadas | {issues} issues menores documentados

¿Subimos a GitHub y desplegamos en Vercel?
  s) Sí, hacer commit + push + deploy
  n) No por ahora, quedarse en local
  g) Solo git (commit + push, sin deploy)
```

---

### FASE 5 — Publicación (solo con confirmación del usuario)

#### Si el usuario elige "s" o "g" — Git

Delega a **git**:
- Recibe: nombre del proyecto + rama (`main` siempre) + mensaje de commit sugerido
- Hace: verifica branch es `main` (renombra si es `master`) + `git add` + `git commit` + `git push` + setea default branch en GitHub
- Devuelve: STATUS + URL del repo + hash del commit + **info para deployer** (repo URL, branch, primer push sí/no)
- Guarda en Engram: `{proyecto}/git-commit`

Muestra al usuario:
```
✓ Commit subido
Repo: {url-github}
Commit: {hash} — "{mensaje}"
Branch: main (default)
```

#### Si el usuario eligió "s" — Deploy (solo después del git exitoso)

**Routing por tipo de proyecto:**
- **Web (DAG State `tipo` ≠ `mobile`)**: deployer en modo Vercel (default)
- **Mobile (DAG State `tipo: mobile`)**: deployer en modo EAS Build

**Modo Vercel** (web):
Delega directamente a **deployer** sin pedir confirmación adicional (el usuario ya eligió "s" o pre-autorizó el deploy):
- Recibe: directorio del proyecto + nombre + **info del git** (repo URL, branch, primer push) + `deploy_mode: "vercel"`
- Si es primer deploy: `vercel deploy --prod` + `vercel git connect` (activa auto-deploy)
- Si ya tiene Git Integration: verifica que el auto-deploy se disparó correctamente
- Devuelve: URL limpia del proyecto + estado de Git Integration + auto-deploy activo/no
- Guarda en Engram: `{proyecto}/deploy-url`

**Modo EAS Build** (mobile):
Delega a **deployer** con:
- Recibe: directorio del proyecto + nombre + `deploy_mode: "eas"` + `platform: "android" | "ios" | "both"` (preguntar al usuario si no especificó)
- Primer build: configura EAS + build preview
- Devuelve: URL de descarga del build en EAS + plataformas buildeadas
- Guarda en Engram: `{proyecto}/deploy-url`
- **Nota**: submit a stores requiere confirmación explícita adicional del usuario

**Handoff git→deployer**: el orquestador pasa la info que git devolvió directamente al deployer. Esto permite que deployer sepa si necesita conectar Git Integration o si ya está activa.

Muestra al usuario:
```
Deployado en {Vercel | EAS Build}
URL: {url-limpia | url-descarga-build}
```

**Si git retorna fallido:**
1. Presentar error al usuario (auth, conflict, remote, etc.)
2. Ofrecer: a) reintentar, b) cambiar remote/branch, c) exportar archivos sin git

**Si deployer retorna fallido:**
1. Presentar error al usuario (auth, build, config, etc.)
2. Ofrecer: a) reintentar, b) deploy manual (`vercel deploy --prod`), c) generar instrucciones de deploy paso a paso

Actualiza DAG State: fase_actual → "completado"

#### Resumen final del proyecto
Al completar Fase 5 (o si el usuario dice "terminamos"), presentar:
- Total de tareas completadas / total
- URL del repo (si git) + URL del deploy (si deployer)
- Si existe `{proyecto}/costs` en Engram: mostrar desglose de costos del pipeline creativo
- Llamar `mem_session_summary` + `mem_session_end`

---

