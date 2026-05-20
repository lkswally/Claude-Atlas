# Architecture — Lucas Rojo Personal Web

Stack: Next.js 16 App Router · Tailwind 4 · shadcn/ui  
Estética: Dark Tech Editorial  
Audiencia: C-level B2B + reclutadores senior  
Fase: 1 (dark-only, sin toggle light)

Design Intelligence: Dark Mode OLED | Estilo: Tech Editorial  
Anti-patterns (HIGH): Generic design + No immersion — NO usar templates SaaS genéricos, NO colores flat sin profundidad, NO layouts simétricos sin intención editorial

---

## 1. Breakpoints

| Token       | Valor   | Uso                                  |
|-------------|---------|--------------------------------------|
| `sm`        | 640px   | Mobile landscape, small tablets      |
| `md`        | 768px   | Tablet portrait                      |
| `lg`        | 1024px  | Tablet landscape, laptop             |
| `xl`        | 1280px  | Desktop estándar                     |
| `2xl`       | 1440px  | Desktop wide                         |
| `3xl`*      | 1600px  | Ultrawide — cap del container-bold   |

*Tailwind 4: agregar en `@theme { --breakpoint-3xl: 1600px; }` en globals.css

---

## 2. Container Strategy

Mood Dark Tech Editorial → `container-bold`: cap 1600px, bg secciones full-bleed.

**Nivel 1 — Section backgrounds**: SIEMPRE full-bleed (edge to edge). El `<section>` extiende su color/gradiente al 100vw.

**Nivel 2 — Content envelope**:

```
Navbar, footer-grid, hero asimétrico, content blocks:
  max-width: 1280px (--container-xl)
  padding-inline: max(1.25rem, 4vw)
  margin-inline: auto
```

**Texto largo** (bio, casos, párrafos CV):
```
max-width: 72ch (--container-prose)
```

**Tailwind 4 en globals.css**:
```css
@theme inline {
  --container-xl: 1280px;
  --container-prose: 72ch;
  --envelope-px: max(1.25rem, 4vw);
}
```

**Clase utilitaria recomendada** (en layout.css o globals):
```css
.container-editorial {
  width: 100%;
  max-width: var(--container-xl);
  margin-inline: auto;
  padding-inline: var(--envelope-px);
}
```

---

## 3. Tipografía — Escala completa

Fonts: **Geist Sans** (display/body) + **Geist Mono** (code, labels técnicos)  
Instalación: `npm install geist` → usar `GeistSans` y `GeistMono` de `geist/font`

| Nivel        | Token CSS        | Valor clamp                                        | Uso                            |
|--------------|------------------|----------------------------------------------------|-------------------------------|
| Hero XXL     | `--text-hero`    | `clamp(3.5rem, 2.25rem + 3.333vw, 6.5rem)`        | Hero headline principal        |
| Display      | `--text-5xl`     | `clamp(3rem, 2.25rem + 2vw, 4.5rem)`              | Sección highlight, logros      |
| H1           | `--text-4xl`     | `clamp(2.25rem, 1.75rem + 1.333vw, 3rem)`         | Títulos de página interior     |
| H2           | `--text-3xl`     | `clamp(1.75rem, 1.4375rem + 0.833vw, 2.25rem)`    | Secciones del home             |
| H3           | `--text-2xl`     | `clamp(1.375rem, 1.1875rem + 0.5vw, 1.75rem)`     | Sub-secciones, card titles     |
| H4           | `--text-xl`      | `clamp(1.1875rem, 1.0625rem + 0.333vw, 1.375rem)` | Labels de grupo                |
| H5/H6        | `--text-lg`      | `clamp(1.0625rem, 0.9688rem + 0.25vw, 1.1875rem)` | Eyebrows, kickers              |
| Body         | `--text-base`    | `clamp(0.9375rem, 0.875rem + 0.167vw, 1rem)`      | Párrafos generales             |
| Body small   | `--text-sm`      | `0.8125rem` (13px fijo)                           | Captions, meta, timestamps     |
| Micro        | `--text-xs`      | `0.6875rem` (11px fijo)                           | Labels UI, badges              |
| Mono base    | `--text-base`    | mismo que body, font-family: Geist Mono            | Code inline, datos técnicos    |

**Reglas editoriales:**
- Hero/H1/H2: `tracking: -0.025em` a `-0.04em`, `weight: 700-800`
- Body: `tracking: 0.01em`, `leading: 1.6`
- EYEBROW/overline: `tracking: 0.12em`, `uppercase`, `weight: 500`, color `--text-secondary`
- Números/métricas clave: Geist Mono o Geist Sans Bold + color `--color-accent`

---

## 4. Layout Patterns

### Header sticky con backdrop-blur

```tsx
// components/layout/header.tsx
<header
  className="fixed top-0 left-0 right-0 z-[--z-sticky]"
  style={{
    backdropFilter: `blur(var(--blur-header))`,
    backgroundColor: `var(--bg-overlay)`,
    borderBottom: `1px solid var(--border-subtle)`,
  }}
>
  <div className="container-editorial h-16 flex items-center justify-between">
    {/* Logo | Nav | CTA */}
  </div>
</header>
```

**Comportamiento GSAP recomendado:**
- Inicio: `opacity: 0, y: -8` → `opacity: 1, y: 0` tras 200ms de scroll
- On scroll down rápido: hide (translateY -100%) con `duration: 300ms ease-in-expo`
- On scroll up: show (translateY 0) con `duration: 400ms ease-out-expo`

### Sección Full-Bleed

```tsx
<section className="relative w-full py-[--space-section]">
  {/* Background full-bleed */}
  <div className="absolute inset-0 bg-[--bg-secondary]" aria-hidden="true" />
  {/* Content en container */}
  <div className="container-editorial relative z-[--z-raised]">
    {/* contenido */}
  </div>
</section>
```

### Sección Container normal

```tsx
<section className="w-full py-[--space-section]">
  <div className="container-editorial">
    {/* contenido */}
  </div>
</section>
```

### Grid Home — Scroll narrativo (section order)

```
1. Hero          — Full-bleed, full-height, bg: --bg-primary (negro base)
2. Lo que hago   — Container, bg: --bg-primary
3. Framework D→D→D→D — Full-bleed, bg: --bg-secondary, grid asimétrico
4. Logros        — Full-bleed, bg: --bg-primary, metrics en grid 3-cols
5. Casos         — Container, cards con --bg-secondary
6. Servicios     — Full-bleed, bg: --bg-secondary
7. Sobre         — Container, dos columnas (40/60)
8. CTA contacto  — Full-bleed, bg: --bg-primary, centered
```

### Footer minimal

```tsx
<footer className="border-t border-[--border-subtle] py-[--space-8]">
  <div className="container-editorial flex flex-col md:flex-row items-center justify-between gap-4">
    {/* Logo | Nav links | Social | Copyright */}
  </div>
</footer>
```

---

## 5. Motion Guidelines

### Stack
- **Framer Motion**: componentes React, animaciones en mount/unmount, hover
- **GSAP ScrollTrigger**: scroll-driven reveals, parallax sutil, contador de métricas
- **Lenis**: smooth scroll — inicializar antes de GSAP en el layout root

### Inicialización Lenis (layout.tsx o provider)

```ts
// lib/lenis.ts
import Lenis from '@studio-freight/lenis'
import gsap from 'gsap'
import ScrollTrigger from 'gsap/ScrollTrigger'

export function initLenis() {
  const lenis = new Lenis({
    duration: 1.2,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // expo ease
    touchMultiplier: 2,
  })

  lenis.on('scroll', ScrollTrigger.update)

  gsap.ticker.add((time) => {
    lenis.raf(time * 1000)
  })
  gsap.ticker.lagSmoothing(0)

  return lenis
}
```

### Duraciones y usos

| Nombre             | Valor  | Cuándo                                       |
|--------------------|--------|----------------------------------------------|
| `--duration-fast`  | 150ms  | Hover buttons, focus rings, color transitions |
| `--duration-base`  | 300ms  | Modals open/close, nav dropdowns, state change |
| `--duration-slow`  | 600ms  | Page transitions, sección reveals              |
| `--duration-scroll`| 900ms  | ScrollTrigger entrances (y: 40 → 0)           |
| `--duration-cinematic` | 1200ms | Hero intro, secuencias narrativas         |
| `--stagger-base`   | 80ms   | Listas, cards en grid                         |

### Easings y usos

| Variable               | Curva                              | Uso                          |
|------------------------|------------------------------------|------------------------------|
| `--ease-out-expo`      | `cubic-bezier(0.16, 1, 0.3, 1)`   | Entradas scroll, reveals     |
| `--ease-in-out-quart`  | `cubic-bezier(0.76, 0, 0.24, 1)`  | Scroll transitions, morphs   |
| `--ease-in-out-cubic`  | `cubic-bezier(0.65, 0, 0.35, 1)`  | Estado a estado               |
| `--ease-out-cubic`     | `cubic-bezier(0.33, 1, 0.68, 1)`  | Hovers rápidos               |
| `--ease-in-expo`       | `cubic-bezier(0.7, 0, 0.84, 0)`   | Salidas (exit animations)    |

### Patrones Framer Motion recurrentes

```ts
// Reveal desde abajo — entrada estándar de sección
export const revealUp = {
  hidden:  { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] } },
}

// Stagger container
export const staggerContainer = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.08 } },
}

// Fade in — para elementos que no se mueven
export const fadeIn = {
  hidden:  { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.6, ease: 'easeOut' } },
}

// Reveal de línea — hero headline por palabra
export const revealWord = {
  hidden:  { y: '110%' },
  visible: { y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } },
}
```

### Reduced Motion

En todos los componentes con Framer Motion:
```tsx
import { useReducedMotion } from 'framer-motion'

const prefersReduced = useReducedMotion()
// Usar variants planos (solo opacity) si prefersReduced === true
```

---

## 6. A11y Baseline

- **Contraste**: todos los tokens de texto satisfacen WCAG AA (4.5:1 mínimo para texto, 3:1 para UI).
  - `--text-primary` (#F0F4F8) sobre `--bg-primary` (#090C10): ratio ~15:1
  - `--text-secondary` (#94A3B8) sobre `--bg-primary`: ratio ~7.2:1
  - `--color-primary` (#63B3ED) — usar solo para elementos interactivos, no texto de párrafo largo
- **Focus rings**: `--focus-ring` visible en todos los elementos interactivos. Ver tokens.css.
- **Skip-to-content**: link oculto que aparece en `:focus`, implementado en tokens.css.
- **ARIA**: `aria-label` en iconos sin texto, `aria-current="page"` en nav activo.
- **Heading order**: nunca saltar niveles — H1 solo en hero/page title, luego H2 por sección.
- **Imágenes**: `alt` descriptivo siempre; `alt=""` para imágenes decorativas.
- **Reduced motion**: respetado globalmente vía `@media (prefers-reduced-motion: reduce)` en tokens.css y `useReducedMotion()` en Framer Motion.
- **Color scheme**: `color-scheme: dark` declarado en `:root` y `<html>` para que inputs, scrollbars y UI del sistema sean consistentes.
- **Semántica**: usar `<main>`, `<nav>`, `<section aria-label>`, `<article>`, `<aside>` correctamente.

---

## 7. Estructura de Carpetas Next.js 16 (App Router)

```
lucas-rojo-web/
├── app/
│   ├── layout.tsx              # Root layout — fonts, providers, metadata
│   ├── page.tsx                # Home (scroll narrativo)
│   ├── globals.css             # @import tokens.css + @theme Tailwind 4
│   ├── sobre/
│   │   └── page.tsx
│   ├── servicios/
│   │   └── page.tsx
│   ├── casos/
│   │   ├── page.tsx            # Listado casos
│   │   └── [slug]/
│   │       └── page.tsx        # Caso detalle
│   ├── cv/
│   │   └── page.tsx
│   └── contacto/
│       └── page.tsx
│
├── components/
│   ├── layout/
│   │   ├── header.tsx          # Sticky header con backdrop-blur
│   │   ├── footer.tsx          # Footer minimal
│   │   ├── nav.tsx             # Navegación principal
│   │   └── skip-to-content.tsx # A11y
│   ├── sections/               # Secciones del home (un archivo por sección)
│   │   ├── hero.tsx
│   │   ├── what-i-do.tsx
│   │   ├── framework.tsx       # D→D→D→D
│   │   ├── metrics.tsx         # Logros con contadores GSAP
│   │   ├── cases-preview.tsx
│   │   ├── services.tsx
│   │   ├── about-preview.tsx
│   │   └── contact-cta.tsx
│   ├── ui/                     # shadcn/ui components (generados por CLI)
│   │   ├── button.tsx
│   │   ├── badge.tsx
│   │   └── ...
│   └── shared/                 # Componentes reutilizables custom
│       ├── case-card.tsx
│       ├── service-card.tsx
│       ├── metric-counter.tsx
│       └── animated-text.tsx
│
├── lib/
│   ├── fonts.ts                # Geist Sans + Geist Mono via next/font
│   ├── lenis.ts                # Inicialización Lenis + GSAP ticker
│   ├── motion.ts               # Variantes Framer Motion reutilizables
│   ├── gsap.ts                 # Registro plugins GSAP (ScrollTrigger, etc.)
│   └── utils.ts                # cn() helper (clsx + tailwind-merge)
│
├── content/                    # Contenido estático (MDX o JSON)
│   ├── casos/
│   │   └── [slug].mdx
│   └── servicios.ts
│
├── public/
│   ├── fonts/                  # Si se usan fonts locales (fallback)
│   ├── images/
│   └── og/                     # Open Graph images
│
├── foundation/                 # Este directorio — tokens y arquitectura
│   ├── tokens.css
│   └── architecture.md
│
├── next.config.ts
├── tailwind.config.ts          # Tailwind 4 — mínimo, @theme en globals.css
├── tsconfig.json
└── package.json
```

### globals.css (estructura recomendada para Tailwind 4)

```css
@import "tailwindcss";
@import "../foundation/tokens.css";

@theme inline {
  /* Exponer tokens como variables Tailwind 4 */
  --color-bg-primary: var(--bg-primary);
  --color-bg-secondary: var(--bg-secondary);
  --color-text-primary: var(--text-primary);
  --color-text-secondary: var(--text-secondary);
  --color-primary: var(--color-primary);
  --color-accent: var(--color-accent);
  --color-border: var(--border-color);

  --radius-sm: var(--radius-sm);
  --radius-base: var(--radius-base);
  --radius-lg: var(--radius-lg);

  --font-sans: "Geist Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;

  --breakpoint-3xl: 1600px;

  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-quart: cubic-bezier(0.76, 0, 0.24, 1);
}
```

### layout.tsx root (estructura)

```tsx
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import LenisProvider from '@/components/providers/lenis-provider'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <a href="#main-content" className="skip-to-content">
          Ir al contenido principal
        </a>
        <LenisProvider>
          <Header />
          <main id="main-content">
            {children}
          </main>
          <Footer />
        </LenisProvider>
      </body>
    </html>
  )
}
```

---

## 8. shadcn/ui — Configuración para dark-only

En `components.json`:
```json
{
  "style": "default",
  "tailwind": { "baseColor": "slate", "cssVariables": true },
  "rsc": true,
  "tsx": true
}
```

Sobreescribir variables shadcn en globals.css para apuntar a los tokens:
```css
/* Mapeo shadcn → tokens propios */
:root {
  --background:   var(--bg-primary);
  --foreground:   var(--text-primary);
  --muted:        var(--bg-secondary);
  --muted-foreground: var(--text-secondary);
  --border:       var(--border-color);
  --ring:         var(--focus-ring-color);
  --primary:      var(--color-primary);
  --primary-foreground: var(--bg-primary);
  --radius: var(--radius-base);
}
```

---

## 9. Performance y SEO

- **Fonts**: `display=swap` + preload del subset latin en `<head>`
- **Images**: Next.js `<Image>` con `priority` en hero, lazy en el resto
- **Code splitting**: cada sección del home como componente independiente
- **GSAP**: lazy import en useEffect (no SSR) — `const { gsap } = await import('gsap')`
- **Framer Motion**: usar `LazyMotion + domAnimation` para reducir bundle size
- **Metadata**: `generateMetadata()` por ruta con OG images específicas

---

*Generado: 2026-05-11 | Fase 1 — dark-only, sin toggle light*
