---
name: pipeline-reference
description: Detalles del pipeline que solo el orquestador y subagentes necesitan. Extraido de CLAUDE.md para reducir context bloat en modo normal.
model: sonnet
---

# Pipeline Reference — Detalles para modo orquestador

> Este archivo complementa CLAUDE.md. Solo es relevante durante el pipeline (modo orquestador). En modo normal Claude no necesita este contenido.

## Visual Direction Checkpoint (Fase 2, Paso 1.5)

Despues de que ux-architect crea la fundacion CSS y antes de lanzar ui-designer, el orquestador presenta al usuario opciones visuales estructuradas:
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
- **Style presets** (`~/.claude/design-data/style-presets.csv`): si el usuario elige un preset nombrado (brutalist, editorial, soft-luxury, etc.), los dials se setean automaticamente desde el CSV

Las respuestas (7 campos + 3 dials + preset opcional) se guardan en Engram como `{proyecto}/visual-direction` y fluyen a ui-designer (behavioral specs) y frontend-developer (design decision tree).

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
