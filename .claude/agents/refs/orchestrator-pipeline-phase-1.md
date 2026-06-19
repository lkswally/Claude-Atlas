# Orchestrator Pipeline — FASE 1 (Planificación)

> Lazy phase ref extracted from orchestrator-pipeline.md in F33. Verbatim — behavior unchanged.
> Load via the pipeline index when this phase is active.

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

