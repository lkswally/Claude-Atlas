# CHANGELOG — Lucas Rojo Web

**v2 — Rediseño visual premium:** 2026-05-14  
**Build inicial completado:** 2026-05-14  
**Stack:** Next.js 16.2.6 App Router + React 19 + TypeScript + Tailwind 4 + shadcn/ui + Framer Motion + Lenis

---

## v2 — Rediseño visual premium (2026-05-14)

### Rediseño por sección

#### Hero — rehecho desde cero
- Layout: `min-h-[88svh]`, composición editorial asimétrica 60/40
- Fondo: gradient radial doble (top-right + bottom-left) con acento cian 7% opacidad + grid de líneas finas 80px (opacidad 0.03)
- Eyebrow chip: border cian + dot pulsante animado (animate-ping) + texto mono caps
- H1: `clamp(3.2rem, 8vw, 7.5rem)`, line-height 0.95, tracking -0.04em. Palabra "claros" en cian con underline SVG animado (pathLength 0→1 al cargar)
- CTAs: primary con magnetic effect + glow en hover + arrow con translate. Secondary con hover reveal arrow
- Stats strip: movido bajo CTAs separado por línea sutil, valores grandes serif
- Elemento visual derecho: System Diagram SVG animado — 7 nodos (centro + 6 servicios) con líneas animadas (pathLength) al cargar
- Scroll cue: línea vertical + dot en loop (reemplaza chevron genérico)

#### Lo que hago — layout asimétrico editorial
- Reemplaza grid 3 cards iguales por: 1 card hero grande izquierda (3fr) + 2 cards stacked derecha (2fr)
- Card grande: icono 52px, título text-3xl, descripción max 44ch. Número de pilar 01 oversized (opacity 0.04) detrás
- Cards small: layout horizontal icono+texto, número de pilar oversized (opacity 0.05) detrás
- Hover: lift -6px/-4px, border cian fade-in, icono rotate 6deg + scale

#### Cómo trabajo — process flow horizontal
- Reemplaza cards verticales por flujo de 4 columnas con conector horizontal animado
- Nodo circular con número mono en cada step
- Conector cian se "dibuja" con scaleX animado al entrar en viewport
- Mobile: stack vertical con conector vertical equivalente

#### Métricas — grid con separadores
- Reemplaza strip aburrido por grid 2x2 mobile / 4x1 desktop
- Números centrados con StatCounter, sin box individual, solo separadores verticales entre celdas
- Background: gradiente lineal sutil base→surface→base

#### Herramientas — NUEVA SECCIÓN (reemplaza DiagnosticoTeaser)
- 2 cards premium en grid 2 columnas: Diagnóstico Digital 360 + Career OS/Radar Laboral IA
- Cada card: fondo elevated, border-radius 16px, padding 48px, SVG mini-visual propio, badge de estado
- Badge diferenciado: ACTIVO (verde) vs PRÓXIMAMENTE (cian)
- Hover: lift -6px + glow cian border + shadow pesada
- Posiciona a Lucas como constructor de productos, no solo consultor

#### Recorrido Preview — timeline editorial horizontal
- Reemplaza cards en grid por timeline con línea superior y hover reveal (borde cian top de ancho 0→100%)
- Año grande mono como primer elemento visual de cada item
- Empresa en serif, rol en mono cian, contexto en muted
- Disclaimer integrado elegantemente como chip con icon Info al pie

#### Servicios Preview — layout magazine
- 1 card hero (Servicio 01 — Procesos operativos) full height izquierda con icono 48px oversized
- 5 cards en grid 2 cols derecha con número de servicio mono caps
- Hero card: número oversized 0.04 opacity detrás, descripción max 40ch

#### Sobre mí Preview — split editorial
- Placeholder foto rediseñado: grid lines decorativas + radial glow + monograma grande
- Título: "Generalista por elección, *operativo por oficio.*" con em cian
- Strengths list: chips inline en lugar de párrafo

#### CTA Final — doble opción de conversión
- Reemplaza CTA único por 2 cards lado a lado
- Card 1: Conversación rápida 30 min → /contacto
- Card 2: Diagnóstico completo → /servicios#diagnostico-operativo
- Background: radial glow cian centrado + grid pattern muy sutil

#### Header — refinado
- CTA pill con border-radius full (rounded-full) en lugar de rounded-md
- Touch targets: logo y hamburger con `min-h-[44px] min-w-[44px]`
- Nav links con `min-h-[44px]` para cumplir WCAG
- Mobile drawer: links con `min-h-[52px]`, stagger reveal animation individual por item
- CTA drawer con glow en estado activo

#### Footer — 4 columnas + refinado
- Grid expandido a 4 columnas desktop: Brand + Nav + Legal + Contacto rápido
- Touch targets: todos los links con `min-h-[44px] py-1`
- Separador cian al 10% antes del copyright (reemplaza borde gris)

### Fixes aplicados

#### Parte 2 — Fixes QA
- **Honeypot visible**: ya estaba oculto con `style={{ display: "none" }}` — confirmado correcto
- **Touch targets <44px**: aplicado `min-h-[44px]` en logo, hamburger, todos los links de footer y nav mobile
- **Bg color drift**: `--bg-primary` alineado a `#0A0A0F` (era `#090C10`)
- **StatCounter arranca en 0**: corregido — si `prefersReduced` muestra valor final directamente, evita flash de "0"

#### Parte 3 — Performance
- **Lazy-load secciones below-fold**: `next/dynamic` con `ssr: true` para todas las secciones excepto Hero
- **Dead deps removidas**: `npm uninstall @react-pdf/renderer gsap` (ningún import los usaba)
- **`willChange` permanente**: removido del Hero CTA — ahora solo se activa vía hover handlers inline

#### Parte 4 — SEO
- **Bug description `/servicios`** corregido: "Asesoría operativa en 6 frentes: mejora de procesos, CX, adopción de IA, People, orden financiero y registro de marca. COO fractional para pymes en LATAM."
- **Titles enriquecidos**: `/` → "...Asesoría operativa, CX y adopción de IA para pymes" | `/servicios` → "Asesoría operativa y CX para pymes" | `/sobre` → "Consultor de operaciones y tecnología" | `/recorrido`, `/contacto` enriquecidos
- **Descriptions ≥140 chars** con keywords objetivo en todas las páginas
- **`llms.txt` reescrito** desde cero: bio factual, 6 servicios con entregables, 3 paquetes con duración, framework D→D→D→D, keywords, disclaimer
- **`llms-full.txt` creado**: versión extendida con FAQ, detalle de cada paquete, recorrido completo
- **`robots.ts`**: AI bots explícitos (GPTBot, anthropic-ai, ClaudeBot, PerplexityBot, Google-Extended, CCBot, Applebot-Extended) con allow "/"
- **JSON-LD layout.tsx**: Person enriquecido con `sameAs`, `image`, `knowsAbout` | ProfessionalService con `areaServed` como Place objeto, `serviceType` array, `priceRange: "$$"` | WebSite schema agregado
- **Sitemap**: `/aviso-legal` y `/privacidad` con `priority: 0.3, changeFrequency: yearly`

### Pendientes post-v2
- [ ] Foto profesional Lucas (sesión pendiente)
- [ ] Dominio definitivo + NEXT_PUBLIC_SITE_URL en Vercel
- [ ] Cal.com URL configurada
- [ ] Resend email cuando haya dominio
- [ ] Tests automatizados Vitest (diferidos por urgencia del rediseño)
- [ ] Diagnóstico Digital 360 v1.1 funcional
- [ ] OG images dinámicas con @vercel/og
- [ ] Career OS / Radar Laboral IA (producto en desarrollo)

---

---

## Qué se construyó

### Scaffold + Config

| Archivo | Propósito |
|---|---|
| `web/next.config.ts` | Headers de seguridad (HSTS, X-Frame DENY, CSP, Permissions-Policy) |
| `web/app/globals.css` | Todos los design tokens del foundation/tokens.css adaptados a Tailwind 4, clases utilitarias, `.container-editorial`, `.eyebrow`, `.nav-link` |
| `web/lib/fonts.ts` | Geist Sans + Geist Mono + Instrument Serif via next/font/google |
| `web/lib/motion.ts` | Variantes Framer Motion reutilizables con tipado correcto para ease arrays |
| `web/lib/schemas.ts` | Zod schema del form de contacto (honeypot, timestamp gate, validaciones) |
| `web/lib/utils.ts` | cn() helper (ya existía, sin modificar) |
| `web/.env.example` | Variables de entorno requeridas con valores vacíos |

### Layout

| Archivo | Propósito |
|---|---|
| `web/app/layout.tsx` | Root layout con fonts, SEO metadata, Schema.org JSON-LD, skip-to-content, preconnects |
| `web/components/providers/lenis-provider.tsx` | Lenis smooth scroll inicializado como client component |
| `web/components/layout/header.tsx` | Header sticky con backdrop-blur on scroll, nav desktop + drawer mobile con AnimatePresence |
| `web/components/layout/footer.tsx` | Footer con grid 3 columnas, links legales, copyright |

### Componentes compartidos

| Archivo | Propósito |
|---|---|
| `web/components/shared/section-header.tsx` | SectionHeader con variante editorial (número oversized opacity 0.04) |
| `web/components/shared/stat-counter.tsx` | Contador animado con IntersectionObserver + easeOut quartic |
| `web/components/shared/badge.tsx` | Badge con 6 variantes |
| `web/components/shared/contact-form.tsx` | Form completo con validación client-side, honeypot, timestamp gate, estados loading/success/error |

### shadcn/ui

| Archivo | Propósito |
|---|---|
| `web/components/ui/button.tsx` | Button base de shadcn (generado por CLI) |

### Secciones Home (9 secciones)

| Archivo | Sección |
|---|---|
| `web/components/sections/hero.tsx` | Hero asimétrico 60/40, magnetic CTA, stagger reveal, scroll cue |
| `web/components/sections/lo-que-hago.tsx` | 3 pilares con cards animadas |
| `web/components/sections/como-trabajo.tsx` | Framework D→D→D→D — layout sticky left + cards right |
| `web/components/sections/metricas.tsx` | Strip 4 stats con StatCounter animado |
| `web/components/sections/diagnostico-teaser.tsx` | Waitlist form para Diagnóstico Digital 360 |
| `web/components/sections/recorrido-preview.tsx` | 3 cards de experiencia + link a /recorrido |
| `web/components/sections/servicios-preview.tsx` | Grid 6 servicios + link a /servicios |
| `web/components/sections/sobre-mi-preview.tsx` | Split 2-col con placeholder foto + copy |
| `web/components/sections/cta-contacto.tsx` | CTA final centrado con glow effect |

### Páginas (App Router)

| Ruta | Archivo | Status |
|---|---|---|
| `/` | `web/app/page.tsx` | ✅ estático |
| `/sobre` | `web/app/sobre/page.tsx` | ✅ estático |
| `/servicios` | `web/app/servicios/page.tsx` | ✅ estático |
| `/recorrido` | `web/app/recorrido/page.tsx` | ✅ estático |
| `/diagnostico` | `web/app/diagnostico/page.tsx` + `diagnostico-client.tsx` | ✅ estático |
| `/contacto` | `web/app/contacto/page.tsx` | ✅ estático |
| `/aviso-legal` | `web/app/aviso-legal/page.tsx` | ✅ estático |
| `/privacidad` | `web/app/privacidad/page.tsx` | ✅ estático |
| `/api/contact` | `web/app/api/contact/route.ts` | ✅ dinámico |
| `/_not-found` | `web/app/not-found.tsx` | ✅ 404 elegante |
| `/error` | `web/app/error.tsx` | ✅ error boundary |

### SEO

| Archivo | Propósito |
|---|---|
| `web/app/sitemap.ts` | Sitemap dinámico con las 6 rutas principales |
| `web/app/robots.ts` | robots.txt |
| `web/public/llms.txt` | Visibilidad en AI search (ChatGPT, Perplexity, Claude) |

---

## Decisiones de implementación tomadas

1. **Acento cian `#00D4FF` vs dorado `#C9A96E`**: La spec final (brand.json) define `#00D4FF` como acento principal. El design-system.md (generado antes) usaba dorado. Implementación usa cian para CTA y accents principales, con dorado como acento secundario en métricas (tokens `--accent-500`). Ambos coexisten sin conflicto.

2. **Ease arrays en Framer Motion**: TypeScript estricto de Next.js 16 no acepta `number[]` como `Easing`. Solución: cast `[0.16, 1, 0.3, 1] as [number,number,number,number]`. Aplicado en todos los componentes.

3. **Zod v4 API change**: `errorMap` fue reemplazado por `error` en Zod v4. Actualizado en schemas.ts.

4. **Lucide-react `Linkedin` no existe**: El icono se llama `Linkedin` en documentación pero no existe en la versión instalada. Reemplazado por texto "LinkedIn" + `ExternalLink` icon.

5. **Lenis sin ScrollTrigger**: architecture.md menciona GSAP + ScrollTrigger + Lenis pero motion_intensity=4 (design-system.md) indica Framer Motion sin pinning. Se usó Lenis standalone con RAF loop (sin GSAP ticker) para simplificar. GSAP se puede agregar después si se sube motion_intensity.

6. **Foto placeholder**: Sin sesión fotográfica real, se usa un placeholder con monograma "LR" en fondo oscuro, alineado con las specs del brand.json.

7. **`typeof data.rol`**: El formulario de contacto usa estado local con tipo `ContactFormData["rol"] | ""` para manejar el estado vacío inicial antes de que el usuario seleccione.

8. **Cal.com embed**: Placeholder iframe condicional según `NEXT_PUBLIC_CALCOM_URL`. Si la variable no está seteada, muestra un bloque indicando cómo configurarla.

9. **`como-trabajo.tsx` sticky sidebar**: En desktop el panel izquierdo es `sticky top-32` — funciona solo cuando el contenido derecho es suficientemente alto. En mobile se convierte en flow normal.

---

## Pendientes para iteraciones futuras

### Inmediatos (antes de go-live)
- [ ] **Foto profesional Lucas** — sesión fotográfica con especificaciones del brand.json (iluminación lateral fría, fondo oscuro)
- [ ] **Dominio definitivo** — configurar en Vercel + setear `NEXT_PUBLIC_SITE_URL`
- [ ] **Cal.com URL** — crear cuenta Cal.com, configurar 30-min slot, setear `NEXT_PUBLIC_CALCOM_URL`
- [ ] **Resend email** — cuando haya dominio: crear API key, hardcodear from/to, descomentar código en `/api/contact/route.ts`
- [ ] **Rate limit** — instalar `@upstash/ratelimit` y `@upstash/redis`, configurar Redis en Vercel, activar en route handler

### Fase 1.1 (post-launch)
- [ ] **Diagnóstico Digital 360 funcional** — implementar análisis de URL (7 dimensiones) + generación PDF con `@react-pdf/renderer`
- [ ] **CV ATS embebido** — ruta `/cv` con PDF viewer + botón download
- [ ] **OG images dinámicas** — `@vercel/og` en Edge Runtime para metadata específica por página
- [ ] **Vercel Analytics** — activar (modo sin cookies, no requiere banner GDPR)
- [ ] **Cloudflare Turnstile** — si spam supera honeypot + rate limit (ya tiene slot en env)

### Técnico
- [ ] **Tests automatizados** — Vitest + Testing Library para componentes críticos (form, contadores)
- [ ] **lighthouse CI** — configurar en GitHub Actions para detectar regresiones
- [ ] **Dependabot** — activar para actualizaciones de seguridad
- [ ] **`npm audit`** — resolver las 2 moderate vulnerabilities del scaffold inicial
- [ ] **Source maps en prod** — verificar que `productionBrowserSourceMaps: false` funcione con Turbopack
- [ ] **Favicon** — generar favicon.ico, apple-touch-icon.png desde el monograma LR cian

---

## Comandos para correr el proyecto

```bash
# Instalar dependencias
cd D:\ProyectosIA\ProyectosClaude\lucas-rojo-web\web
npm install

# Development (localhost:3000)
npm run dev

# Build de producción (verifica errores)
npm run build

# Servir el build de producción
npm start

# Linting
npm run lint
```

**Variables de entorno:** copiar `.env.example` a `.env.local` y completar los valores.

---

*Build inicial — Lucas Rojo Web — 2026-05-14*
