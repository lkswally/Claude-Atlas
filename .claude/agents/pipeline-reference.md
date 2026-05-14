---
name: pipeline-reference
description: Detalles del pipeline que solo el orquestador y subagentes necesitan. Extraido de CLAUDE.md para reducir context bloat en modo normal.
model: sonnet
---

# Pipeline Reference — Detalles para modo orquestador

> Este archivo complementa CLAUDE.md. Solo es relevante durante el pipeline (modo orquestador). En modo normal Claude no necesita este contenido.

## Intent Clarifier (Fase 1, Paso 0 — NUEVO 2026-04-19)

Antes de todo, para proyectos nuevos el orquestador evalúa si el brief del usuario es claro o vago:
- **Heurística clarity score 0-10**: word count + design vocab + referencias + features concretos + audiencia
- **Score 0-3**: muy vago → 6 preguntas obligatorias (Q1-Q6)
- **Score 4-6**: parcial → preguntas filtradas
- **Score 7-10**: claro → solo Q3 (mood preset) + Q5 (originalidad) para confirmar

**Preguntas** (todas con opciones múltiples, no abiertas):
- Q1: tipo proyecto (landing/website/webapp/mobile/API/juego)
- Q2: industria (top 5 dinámicas via `node ~/.claude/design-data/search.js`)
- Q3 OBLIGATORIA: mood preset (8 opciones mapped 1:1 a `style-presets.csv` rows)
- Q4: referencia visual opcional (figma/image/url_website/brand_textual/preset/none)
- Q5 OBLIGATORIA: originalidad (conservador/balanceado/experimental) → dials
- Q6: audiencia (B2B/B2C/creatives/GenZ/luxury/otra)

**Resultado**: `{proyecto}/intent` con mood_preset, preset_row, dials_suggested, anti_patterns_HIGH (heredados del preset CSV), reference_source, audience. Consumido por todos los agentes downstream (PM, ux-architect, VDC, brand-agent, ui-designer, evidence-collector).

**Bloqueo "decidí vos"**: el usuario NO puede skipear Q3+Q5 en proyectos con UI. Si insiste, el orquestador rechaza con mensaje explícito.

**Excepción**: proyectos API/backend/CLI saltean Q3/Q4/Q6.

Detalles completos en `orquestador.md` § FASE 1 Paso 0.

## Visual Direction Checkpoint (Fase 2, Paso 1.5 — REFORZADO 2026-04-19)

Despues de que ux-architect crea la fundacion CSS y antes de lanzar ui-designer, el orquestador presenta al usuario opciones visuales estructuradas. **AHORA es obligatorio y pre-filleado desde `{proyecto}/intent`**:

**Paso 1.5a — Extractor polimórfico de referencia** (nuevo): según `intent.reference_source`:
- `figma`: `get_metadata` detecta design real vs raster-only. Si raster → `get_screenshot` + color quantization.
- `image`: color quantization + inferencia mood/tipografía vía vision.
- `url_website`: Playwright screenshot + mismo flujo que image.
- `brand_textual`: WebFetch `awesome-design-md/{slug}.md`.
- `preset`: row de `style-presets.csv`.
- `none`: solo preset del intent.

Consulta complementaria a awesome-design-md siempre (mapped por mood_preset). Extracción persistida en `.pipeline/references/`.

**Paso 1.5b — Pre-fill + confirmación**: las 8 decisiones se pre-seleccionan desde intent + extracción. Usuario solo confirma "ok" o ajusta puntualmente. Bloqueado "decidí vos".

**Paso 1.5c — Schema extendido**: `{proyecto}/visual-direction` ahora incluye `reference_source`, `extraction_status`, `extracted_palette`, `extracted_typography`, `extracted_mood_tags`, `reference_images_paths`, `reference_for_qa` (para LLM-as-judge Fase 4), `awesome_design_md_refs`, `anti_patterns_HIGH` merged, `dials` confirmados.

**Las 8 decisiones cualitativas** (igual que antes, solo cambia cómo se llenan — pre-fill vs pregunta abierta):
1. **Estilo visual**: editorial, inmersivo, minimalista, bold/colorido, otro
2. **Hero**: imagen estatica, video de fondo, fondo animado, parallax, slider, solo texto
3. **Navegacion**: transparente con blur, fija solida, solo hamburger, sidebar, mega-menu
4. **Galeria**: masonry, carousel, lightbox, horizontal scroll, hover reveal
5. **Nivel de animacion**: sutil (CSS only), moderado (Framer Motion), inmersivo (FM + GSAP)
6. **Mood**: oscuro, claro, mixto, alto contraste
7. **Efectos especiales**: cursor custom, text animations, smooth scroll, parallax, page transitions, particles

### Design dials cuantitativos (1-10)

Despues de los 7 campos cualitativos, el orquestador pregunta 3 valores numericos (o los infiere del estilo elegido con defaults razonables):

| Dial | Rango | Significado |
|------|-------|-------------|
| `DESIGN_VARIANCE` | 1 (clean/centered) → 10 (asymmetric/experimental) | Nivel de experimentacion en layout. 1-3 = grids simetricos, 4-6 = hero asymmetric + split layouts, 7-10 = broken grid, rotated elements, collage |
| `MOTION_INTENSITY` | 1 (static) → 10 (magnetic/scroll-triggered) | Cantidad y sofisticacion de animacion. 1-3 = CSS hover only, 4-6 = FM enter/exit + scroll reveals, 7-10 = GSAP timelines + pin + magnetic cursor + SplitText |
| `VISUAL_DENSITY` | 1 (spacious/luxury) → 10 (dense/dashboard) | Concentracion de contenido. 1-3 = editorial whitespace, 4-6 = balanced marketing, 7-10 = data-heavy, multi-column, tables |

**Defaults por estilo** (si el usuario no especifica):
- editorial → `variance:4, motion:3, density:3`
- inmersivo → `variance:7, motion:8, density:4`
- minimalista → `variance:2, motion:2, density:2`
- bold/colorido → `variance:6, motion:6, density:6`

**Consumo por agentes**:
- `ui-designer`: ajusta behavioral specs (e.g. `motion:8` → agrega scroll-pin specs, magnetic cursor)
- `frontend-developer`: dispara Tier de animacion correcto (1-3 = Tier 1 CSS, 4-6 = Tier 2 FM, 7-10 = Tier 3 GSAP). `density:7+` obliga a considerar tabla/virtualizacion
- `ux-architect`: `density` influye en spacing scale base (ej. density 2 → scale 1.5x, density 8 → scale 0.85x)

Los anti-patterns HIGH del Design Intelligence Engine siguen siendo **obligatorios** y sobrescriben los dials si hay conflicto.

Antes de presentar las opciones, el orquestador consulta:
- **Boveda CodePen** (`~/.claude/codepen-vault/`): efectos probados se muestran como opciones concretas
- **21st.dev**: si `component_source: "21st.dev"`, se mencionan componentes animados disponibles
- **Animaciones disponibles**: CSS (Tier 1), Framer Motion (Tier 2), GSAP+Lenis (Tier 3)
- **Style presets** (`~/.claude/design-data/style-presets.csv`): heredados automáticamente de `intent.preset_row` (ya no solo "si el usuario elige preset nombrado" — ahora siempre viene del Intent Clarifier Paso 0)
- **awesome-design-md** (`raw.githubusercontent.com/VoltAgent/awesome-design-md/main/design-md/{slug}.md`): 68 marcas con tokens abstractos (paleta/tipografía/motion). El orquestador fetchea 1-3 refs automáticamente según `intent.mood_preset`. NUNCA copiar logos/layouts — solo tokens.

Las respuestas (7 campos + 3 dials + mood_preset obligatorio + referencia opcional) se guardan en Engram como `{proyecto}/visual-direction` con schema extendido (ver Paso 1.5c) y fluyen a ui-designer, brand-agent, frontend-developer, evidence-collector y reality-checker.

## Anti-generic Guardrails (Fase 2-3 — NUEVO 2026-04-19)

Guardrails ejecutables instalados en ui-designer + frontend-developer para bloquear outputs genéricos (caso VetConnect):

**ui-designer Paso 0e — SaaS Teal Default Detector** (6 reglas T1-T6):
- T1: paleta primary no teal/cyan (hue 175-205, sat>40) salvo mood=swiss-minimal
- T2: heading no Inter/Roboto/Open Sans/Lato/Arial/SF Pro/Segoe UI
- T3: heading.family ≠ body.family (excepto swiss-minimal)
- T4: hero no "centered+2CTAs+3cards" para moods no-swiss
- T5: border radius coherente con mood (brutalism=0-2px, etc.)
- T6: shadow coherente (brutalism=offset-hard, luxury=subtle-warm, y2k=chrome)

**frontend-developer Pre-return Audit** (5 grep commands sobre código generado):
- Teal/cyan hardcoded en archivos no-dashboard
- Inter/Roboto como heading en hero/landing
- Pattern lucide-react + grid-cols-3 en main page (ALERT)
- Shadow suave en brutalism
- Hero sin `<img>`/`<video>`/`<Image>` cuando visual-direction.hero ≠ text-only
- Motion: motion_intensity≥7 requiere gsap/ScrollTrigger/framer-motion

Ambos agentes devuelven `AUTO_AUDIT` estructurado en su Return Envelope. reality-checker verifica que AUTO_AUDIT PASS en Paso 2 + Paso 8.

## QA Hardening (Fase 3-4 — NUEVO 2026-04-19)

7 capas de defensa anti-falso-positivo (orden de ejecución):

1. **evidence-collector Paso 4b** (Fase 3): AUTO_AUDIT verification upstream
2. **evidence-collector Paso 4c**: Visual Fidelity LLM-as-judge (5 dim, threshold ≥7/10)
3. **evidence-collector Paso 4d**: E2E flows (signup→login→dashboard→logout, error states)
4. **evidence-collector Paso 4e**: Network inspection obligatoria
5. **evidence-collector Paso 4f**: Testing contra deploy_url
6. **reality-checker Paso 2B** (Fase 4): False Positive Guardrail — re-ejecuta 2-3 qa-{N} PASS
7. **reality-checker Paso 4B**: Mixed Content dinámico (no grep estático)
8. **reality-checker Paso 8**: Design Tools Usage Audit
9. **reality-checker Paso 9**: Evidence Trail Mandatory

Plus:
- **api-tester**: ESCALATE si api-spec missing (no fallback silencioso)
- **performance-benchmarker**: PageSpeed Insights contra deploy_url obligatorio

## Herramientas por agente

| Agente | Tools principales |
|--------|-------------------|
| orquestador | Agent (spawn subagentes), Engram MCP |
| project-manager-senior | Read, Write, Engram MCP |
| ux-architect | Read, Write, Bash, Engram MCP |
| ui-designer | Read, Write, Bash, Engram MCP, Context7 MCP (21st.dev, opcional) |
| security-engineer | Read, Write, Engram MCP |
| frontend-developer | Read, Write, Edit, Bash, Engram MCP, Context7 MCP (21st.dev) |
| backend-architect | Read, Write, Edit, Bash, Engram MCP |
| rapid-prototyper | Read, Write, Edit, Bash, Engram MCP |
| mobile-developer | Read, Write, Edit, Bash, Engram MCP |
| game-designer | Read, Write, Engram MCP |
| xr-immersive-developer | Read, Write, Edit, Bash, Engram MCP |
| evidence-collector | Read, Bash, Playwright MCP, Engram MCP |
| reality-checker | Read, Bash, Glob, Grep, Playwright MCP, Engram MCP |
| seo-discovery | Read, Write, Edit, Bash, Engram MCP |
| api-tester | Read, Bash, Engram MCP |
| performance-benchmarker | Read, Bash, Playwright MCP, Engram MCP |
| brand-agent | Read, Write, Bash, Engram MCP |
| image-agent | Read, Write, Bash, Engram MCP |
| logo-agent | Read, Write, Bash, Engram MCP |
| video-agent | Read, Write, Bash, Engram MCP |
| git | Bash (git, gh), Engram MCP |
| deployer | Bash (vercel, eas), Engram MCP |
| codepen-explorer | Playwright MCP, Engram MCP |
| self-auditor | Read, Bash, Glob, Grep, Engram MCP |
| build-resolver | Read, Write, Edit, Bash, Grep, Glob, Engram MCP |

## Design Intelligence Engine (BM25)

Motor de busqueda local en `~/.claude/design-data/` (search.js + 8 CSVs):

| CSV | Rows | Contenido |
|-----|------|-----------|
| products.csv | 161 | Tipos de producto con estilo, paleta y landing pattern recomendados |
| styles.csv | 84 | Estilos UI con keywords CSS, performance, accesibilidad |
| colors.csv | 160 | Paletas de 12+ tokens semanticos por industria |
| typography.csv | 73 | Pares tipograficos con Google Fonts URLs |
| ux-guidelines.csv | 98 | Best practices UX con severidad (HIGH/MEDIUM/LOW) |
| landing.csv | 34 | Patrones de landing con section order y conversion |
| ui-reasoning.csv | 161 | Reglas de razonamiento por industria (anti-patterns, decision rules) |
| charts.csv | 25 | Tipos de chart con accesibilidad y library recommendations |
| style-presets.csv | 10 | Presets esteticos con dials (variance/motion/density), tokens CSS, fonts y anti-patterns |

**Uso por agentes** (Fase 2):
| Agente | Cuando | Que obtiene |
|--------|--------|-------------|
| ux-architect | Paso 0 (antes de CSS) | Estilo, colores, CSS keywords, design variables, anti-patterns |
| ui-designer | Paso 0 (direccion estetica) | Landing pattern, anti-patterns, chart guidance, key effects |
| brand-agent | Paso 2a (antes de identidad) | Paleta por industria, mood tipografico, anti-patterns, color mood |

**CLI**:
```bash
node ~/.claude/design-data/search.js "luxury spa" --design-system -p "MySpa"
node ~/.claude/design-data/search.js "dashboard" --domain chart -n 3
node ~/.claude/design-data/search.js "accessibility" --domain ux -n 5
```

**Reglas**: El motor informa, no decide. Brief del usuario + anti-convergencia tienen prioridad. `anti_patterns` con severidad HIGH son OBLIGATORIOS. Si brand.json ya existe, sus colores tienen prioridad.

## Referencias tecnicas (archivos no-agente en `~/.claude/agents/`)

| Archivo | Usado por | Contenido |
|---------|-----------|-----------|
| `agent-protocol.md` | todos los subagentes | Engram 2-pasos, Return Envelope, reglas universales |
| `better-auth-reference.md` | backend-architect, frontend-developer, rapid-prototyper | Better Auth 1.5 + Supabase + Vercel |
| `better-gsap-reference.md` | frontend-developer | GSAP Tier 3 para React/Next.js |
| `react-patterns-reference.md` | frontend-developer | React 19, Next.js 15/16, Tailwind 4, Zustand 5 |
| `redis-patterns-reference.md` | backend-architect | Cache-aside, Pub/Sub, HyperLogLog, cursor pagination |
| `pocketbase-reference.md` | backend-architect | Boolean fields, rules, auth, sort, Docker, HTTPS |
| `devops-vps-reference.md` | deployer | Mixed Content HTTPS, Oracle Cloud, nginx, Let's Encrypt |
| `nothing-design-reference.md` | ux-architect, ui-designer, frontend-developer, brand-agent | Nothing Design System v3.0.0 |
| `scroll-storytelling-reference.md` | frontend-developer | Lenis, GSAP ScrollTrigger pinning, snap, parallax |
| `advanced-effects-reference.md` | frontend-developer | Lottie, Rive, cursor effects, micro-interactions |
| `creative-coding-reference.md` | frontend-developer, xr-immersive-developer | p5.js, GLSL shaders, generative art |
| `reactive-audio-reference.md` | frontend-developer, xr-immersive-developer | Tone.js, Web Audio API, sound design |

### MCPs externos integrados
| MCP | Agentes | Contenido |
|-----|---------|-----------|
| Context7 (Upstash) | frontend-developer, ui-designer | Docs de librerias + 21st.dev community components (17,646 snippets). Library ID: `/websites/21st_dev_community_components` |

## Stack adaptable por proyecto

El orquestador decide el stack en Fase 1. No hay stack fijo:

| Capa | Opciones disponibles | Preferido |
|------|---------------------|-----------|
| Frontend | Next.js, SvelteKit, Nuxt, Astro, Vite+React | Next.js (apps), Vite+React (landing) |
| Backend | Hono, Express, Fastify | Hono (edge-ready, liviano) |
| DB | PostgreSQL, SQLite, Supabase | PostgreSQL (prod), Supabase (MVP) |
| ORM | Drizzle, Prisma | Drizzle (type-safe, edge) |
| API type-safe | tRPC, oRPC, ts-rest | tRPC (si frontend+backend TS) |
| Validacion | Zod | Siempre |
| State mgmt | Zustand, Jotai, Pinia | Zustand (React) |
| Data fetching | TanStack Query | Siempre en apps con API |
| Forms | react-hook-form + Zod | Siempre en apps con forms |
| Jobs/Background | BullMQ, Inngest | BullMQ (si Redis), Inngest (serverless) |
| Email | React Email + Resend | Siempre que haya transaccional |
| Estructura | Single-repo, Monorepo | Monorepo si frontend+backend separados |
| Mobile | React Native + Expo SDK 52+, NativeWind 4 | React Native + Expo |
| Animacion | CSS (Tier 1), Framer Motion (Tier 2), GSAP (Tier 3) | CSS -> Framer -> GSAP segun complejidad |
| Scroll avanzado | Lenis + GSAP ScrollTrigger | Lenis (storytelling), GSAP solo (pinning) |
| Animacion vectorial | Lottie, Rive | Lottie (After Effects), Rive (interactivo) |
| Creative coding | p5.js, GLSL shaders, Canvas 2D | p5.js (2D), Three.js shaders (3D) |
| Audio reactivo | Tone.js, Web Audio API | Tone.js (completo), Web Audio (simple) |
| Data Viz | Recharts, Chart.js, D3.js | Recharts |
| Linting | ESLint + Stylelint | Siempre |
| Game 2D | Phaser.js 3, PixiJS, Canvas API | Phaser.js |
| Game 3D | Three.js, Babylon.js | Three.js |
| Game Audio | Howler.js, Web Audio API | Howler.js |
| Game Physics | Matter.js, Cannon-es | Matter.js |
| Level Design | Tiled, LDtk | Tiled |
| Design System | Nothing Design (full/partial), custom, none | custom (default) |
| Componentes UI | 21st.dev, CodePen vault, custom | custom (default) |

## Nothing Design System (opcional)

Inspirado en Nothing Phone/tech (tipografia suiza, OLED blacks, dot-matrix). Solo si el usuario lo pide.

| Modo | Cuando | Efecto |
|------|--------|--------|
| `nothing-full` | "estilo Nothing" | Todo el proyecto usa tokens/componentes Nothing |
| `nothing-partial` | "hero estilo Nothing" | Solo secciones especificas |
| `custom` | Default | ux-architect + ui-designer crean design system propio |
| `none` | "sin design system" | Sin sistema formal |

- **Referencia**: `nothing-design-reference.md` (tokens, componentes, platform mapping)
- **Activacion**: orquestador detecta en Fase 1, propaga via `DESIGN_SYSTEM` + `NOTHING_SCOPE`
- **Modo parcial**: tokens bajo `.nd`, variables con prefijo `--nd-*`, clases `nd-btn`, `nd-card`

## 21st.dev — Componentes Community (opcional)

Libreria community de componentes React animados/visuales via **Context7 MCP**.

```
Library ID: /websites/21st_dev_community_components (17,646 snippets)
Paso 1: resolve-library-id("21st.dev") -> obtener library ID
Paso 2: query-docs(libraryId, "animated hero section") -> codigo React completo
Limite: 3 llamadas por consulta
```

| Escenario | Usar 21st.dev | Razon |
|-----------|--------------|-------|
| Proyecto visual/animado | Si | Componentes con Framer Motion |
| Landing con efectos modernos | Si | Aurora backgrounds, parallax heroes |
| Dashboard funcional | No | Prioriza funcionalidad |
| Design system estricto | No | Componentes tienen estilos propios |

**Reglas**: inspiracion + base, no copy-paste. Adaptar al brand/design-system. No instalar paquetes 21st.dev — solo extraer codigo via Context7. Evaluar deps pesadas.

## Agentes creativos — Assets visuales

- **Orden obligatorio**: brand-agent -> (aprobacion) -> logo-agent + image-agent (paralelo) -> video-agent
- **brand-agent SIEMPRE primero** — ningun agente creativo funciona sin `brand.json`
- **NO auto-generar assets sin confirmacion del usuario**
- Cada agente creativo escribe SOLO su cajon Engram
- NO guardar binarios ni SVG completos en Engram — solo paths y metadata

### Variables de entorno requeridas

| Variable | Servicio | Costo |
|----------|----------|-------|
| `GEMINI_API_KEY` | Google AI Studio | ~$0.02-0.04/img (billing requerido) |
| `HF_TOKEN` | HuggingFace | Gratis (free tier) |
| `REPLICATE_API_TOKEN` | Replicate | ~$0.03-0.10/video |

Al menos una key de imagen obligatoria. Resolucion: env var del sistema -> `.env` del proyecto -> `~/.claude/.env`

## Protocolo compartido de subagentes
- **Referencia completa**: `~/.claude/agents/agent-protocol.md`
- Todo subagente DEBE seguir los patrones definidos ahi (Engram 2-pasos, topic_key obligatorio, Return Envelope estandar)
- No duplicar esos patrones en los archivos de agente — solo referenciar

### Coordinacion cross-agent
Ver tabla completa de inputs/outputs por agente en `orquestador.md` § "Que cajon lee cada agente".
