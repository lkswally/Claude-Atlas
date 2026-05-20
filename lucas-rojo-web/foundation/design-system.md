# Design System — Lucas Rojo Web
**Generado por**: ui-designer  
**Fecha**: 2026-05-11  
**Plataforma**: Web (Next.js + shadcn/ui)

---

## Direccion estetica
**Dark Tech Editorial** — combina la precision tipografica del periodismo de alta gama con la densidad informacional de productos tech. El resultado es un portfolio que comunica seriedad ejecutiva sin caer en el minimalismo inerte ni en la ostentacion de agencias creativas. La oscuridad es el canvas, la tipografia serif es el acento de lujo.

**Mood preset**: `soft-luxury` / `editorial-magazine` (hibrido)  
**Design variance**: 5 (una seccion asimetrica obligatoria)  
**Motion intensity**: 4 (Framer Motion enter/exit + scroll reveals, sin pinning)  
**Visual density**: 3 (espacioso, jerarquia clara, max-width tipografico 65-75ch)

**Landing pattern**: Hero con autoridad → Social proof (metricas) → Casos de estudio → Servicios → CTA contacto  
**CTA placement**: dual en hero (primario + ghost), sticky en nav desktop, drawer CTA en mobile

---

## Anti-patterns (BLOQUEANTES)
- NO teal/cyan como color primario
- NO Inter/Roboto como heading — exclusividad para Instrument Serif
- NO hero centrado con 2 CTAs + 3 cards iguales (SaaS generico)
- NO gradientes multi-color o rainbow
- NO sombras box-shadow genericas (usar shadows con temperatura warma/fria especifica)
- NO border-radius uniformes en 8-16px — usar 0 para structural, 6px para interactive, 999px para pills
- NO animaciones bounce/spring — easing elegante: cubic-bezier(0.25, 0.46, 0.45, 0.94)
- NO textos centrados en bloques de cuerpo largo

---

## Tokens de color

### Paleta base (dark-first)

```css
/* Background layers */
--bg-base:        #0A0A0A;   /* canvas principal */
--bg-surface:     #111111;   /* cards, panels */
--bg-elevated:    #1A1A1A;   /* modales, dropdowns */
--bg-overlay:     #222222;   /* hover states en superficie */

/* Texto */
--text-primary:   #F2F0EB;   /* warm white — no frio puro */
--text-secondary: #8A8680;   /* muted, labels */
--text-tertiary:  #5A5752;   /* placeholder, disabled */
--text-inverse:   #0A0A0A;   /* texto sobre fondos claros */

/* Acento — Warm Gold */
--accent-500:     #C9A96E;   /* base — dorado editorial */
--accent-400:     #D4B97F;   /* hover */
--accent-600:     #B8954A;   /* active/pressed */
--accent-100:     #C9A96E1A; /* bg-subtle (10% opacity) */
--accent-border:  #C9A96E40; /* border decorativo (25% opacity) */

/* Semantic */
--success:        #4A8C6E;
--error:          #C25B4E;
--warning:        #C9A040;
--info:           #4A7C9E;

/* Bordes */
--border-subtle:  #FFFFFF0D; /* 5% white */
--border-default: #FFFFFF1A; /* 10% white */
--border-strong:  #FFFFFF33; /* 20% white */
--border-accent:  #C9A96E40; /* acento sutil */
```

### Variantes semanticas dark/light
```css
/* Dark mode (default) */
--primary-text-emphasis: #D4B97F;   /* tint 40% del acento */
--primary-bg-subtle:     #C9A96E1A; /* shade 80% */
--primary-border-subtle: #C9A96E33; /* shade 60% */
```

### Escala tint/shade — accent
```
accent-100: #F5EDDC  (tint 80%)
accent-200: #E8D8B5  (tint 60%)
accent-300: #DBBF88  (tint 40%)
accent-400: #D4B97F  (tint 20%)
accent-500: #C9A96E  (base)
accent-600: #B8954A  (shade 20%)
accent-700: #9A7B30  (shade 40%)
accent-800: #7A5F18  (shade 60%)
accent-900: #5A430A  (shade 80%)
```

---

## Tokens de tipografia

```css
/* Familias */
--font-display: 'Instrument Serif', Georgia, serif;  /* headings, display, metricas */
--font-body:    'Geist Sans', system-ui, sans-serif; /* body, UI, labels */
--font-mono:    'Geist Mono', 'Courier New', monospace;

/* Escala modular — ratio 1.25 (Major Third) */
--text-xs:   0.75rem;   /* 12px — labels, badges */
--text-sm:   0.875rem;  /* 14px — captions, meta */
--text-base: 1rem;      /* 16px — cuerpo */
--text-lg:   1.125rem;  /* 18px — lead copy */
--text-xl:   1.25rem;   /* 20px */
--text-2xl:  1.563rem;  /* 25px */
--text-3xl:  1.953rem;  /* 31px */
--text-4xl:  2.441rem;  /* 39px — section titles */
--text-5xl:  3.052rem;  /* 49px — hero title */
--text-6xl:  4rem;      /* 64px — display grande */
--text-7xl:  5.5rem;    /* 88px — metric oversized */

/* Line-height */
--leading-tight:  1.1;   /* display headings */
--leading-snug:   1.25;  /* subtitulos */
--leading-normal: 1.5;   /* cuerpo */
--leading-relaxed: 1.75; /* long-form */

/* Tracking */
--tracking-tight:  -0.03em; /* display serif */
--tracking-normal:  0em;
--tracking-wide:    0.08em; /* eyebrow caps */
--tracking-wider:   0.15em; /* labels uppercase */

/* Weight */
--font-light:   300;
--font-regular: 400;
--font-medium:  500;
--font-semibold: 600;
```

---

## Tokens de spacing

```css
/* Escala — visual density 3 (espacioso) */
--space-1:  0.25rem;   /* 4px */
--space-2:  0.5rem;    /* 8px */
--space-3:  0.75rem;   /* 12px */
--space-4:  1rem;      /* 16px */
--space-5:  1.25rem;   /* 20px */
--space-6:  1.5rem;    /* 24px */
--space-8:  2rem;      /* 32px */
--space-10: 2.5rem;    /* 40px */
--space-12: 3rem;      /* 48px */
--space-16: 4rem;      /* 64px */
--space-20: 5rem;      /* 80px */
--space-24: 6rem;      /* 96px */
--space-32: 8rem;      /* 128px */
--space-40: 10rem;     /* 160px */

/* Section padding — espacioso */
--section-py: var(--space-24);     /* 96px vertical */
--section-py-lg: var(--space-32);  /* 128px — hero, separadores */

/* Content envelope */
--container-max: 1400px;   /* container-bold: ultrawide-friendly */
--container-px: max(1.5rem, 5vw);
--prose-max: 68ch;         /* max-width tipografico */
```

---

## Tokens de motion

```css
/* Duraciones */
--duration-instant:   80ms;
--duration-fast:     150ms;
--duration-hover:    200ms;
--duration-normal:   300ms;
--duration-slow:     500ms;
--duration-reveal:   700ms;

/* Easings */
--ease-primary:     cubic-bezier(0.25, 0.46, 0.45, 0.94);  /* Out Quart — elegante */
--ease-in:          cubic-bezier(0.4, 0, 1, 1);
--ease-out:         cubic-bezier(0, 0, 0.2, 1);
--ease-in-out:      cubic-bezier(0.4, 0, 0.2, 1);
--ease-spring-soft: cubic-bezier(0.34, 1.56, 0.64, 1);     /* muy sutil — no bounce */

/* Stagger */
--stagger-delay:    60ms;
--stagger-base:     var(--duration-normal);
```

---

## Tokens de border radius

```css
--radius-none: 0px;     /* structural — cards editoriales */
--radius-sm:   2px;     /* detalle muy fino */
--radius-md:   6px;     /* botones, inputs */
--radius-lg:   8px;     /* cards service */
--radius-pill: 999px;   /* badges, pills */
```

---

## Tokens de sombra

```css
/* Luxury — warm, sin spread agresivo */
--shadow-sm:  0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
--shadow-md:  0 4px 16px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3);
--shadow-lg:  0 12px 40px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4);
--shadow-accent: 0 0 24px rgba(201,169,110,0.15), 0 4px 16px rgba(0,0,0,0.5);
--shadow-glow:   0 0 40px rgba(201,169,110,0.25), 0 8px 32px rgba(0,0,0,0.6);
```

---

## AUTO_AUDIT — Pre-release

```
mood_preset: editorial-magazine / soft-luxury hybrid
T1_palette_not_teal: PASS (#C9A96E — warm gold, hue ~38deg)
T2_heading_not_generic: PASS (Instrument Serif)
T3_typographic_contrast: PASS (Instrument Serif != Geist Sans)
T4_hero_structure_varied: PASS (asimetrico — ver Hero spec abajo)
T5_radius_coherent_with_mood: PASS (0px structural, 6px interactive, 999px pills)
T6_shadow_coherent_with_mood: PASS (shadow-warm con rgba opacity baja, glow acento)
T7_envelope_strategy: PASS (container-bold 1400px, bg full-bleed por section)
differentiation_checklist:
  typography_rationale: PRESENT — Instrument Serif serif display por editorial warmth + autoridad C-level
  asymmetric_section: PRESENT — Hero 60/40 split + metricas offset; section de casos asimetrica
  custom_shapes_if_needed: PRESENT — underline-draw en links, reveal de textos serif
  micro_interactions_3plus: PRESENT — magnetic button, tilt card, letter-spacing nav, underline sweep
```

---

## Componentes

---

### 1. Button

**Atomic level**: Atom  
**Base**: shadcn/ui `Button` con variantes custom

#### Anatomia
```
[prefix-icon?] [label] [suffix-icon?]
padding-x: var(--space-5) md / var(--space-4) sm / var(--space-6) lg
padding-y: derivado del height
```

#### Variantes y tamanos

| Variante    | Background       | Text             | Border             | Border-radius |
|-------------|-----------------|------------------|--------------------|---------------|
| primary     | `--accent-500`  | `--text-inverse` | none               | `--radius-md` |
| secondary   | transparent     | `--text-primary` | `--border-default` | `--radius-md` |
| ghost       | transparent     | `--text-secondary`| none              | `--radius-md` |
| link        | none            | `--accent-500`   | none               | 0             |

| Tamano | Height | Font-size      | Font            | Tracking |
|--------|--------|----------------|-----------------|---------- |
| sm     | 32px   | `--text-xs`    | Geist Sans 500  | wide      |
| md     | 40px   | `--text-sm`    | Geist Sans 500  | wide      |
| lg     | 52px   | `--text-base`  | Geist Sans 500  | wide      |

Labels: UPPERCASE en sm/md. Title case en lg primary.

#### Estados

**Primary**:
- `default`: bg accent-500, texto negro
- `hover`: bg accent-400 + `--shadow-glow` + `translateY(-1px)` — duracion `--duration-hover` ease `--ease-primary`
- `active/pressed`: bg accent-600 + `translateY(0)` + shadow-sm — 80ms
- `focus-visible`: outline `2px solid var(--accent-500)` + offset `2px`
- `disabled`: opacity 0.35, cursor not-allowed, sin transform
- `loading`: icono spinner (Lucide `Loader2` rotating 1s linear infinite) + label permanece

**Secondary**:
- `hover`: border `--border-strong` + bg `--bg-overlay` + `translateY(-1px)`
- `active`: border `--border-strong` + bg `--bg-elevated`
- `focus-visible`: outline `2px solid var(--accent-500)`

**Ghost**:
- `hover`: bg `--bg-overlay` + text `--text-primary`
- `active`: bg `--bg-elevated`

**Link**:
- `hover`: underline animado (ver micro-interaccion) + `--accent-400`
- `active`: `--accent-600`

#### Micro-interaccion — Magnetic Effect (solo primary CTA)

El boton principal de hero tiene efecto magnetico en desktop:

```
onMouseMove: calcular offset del cursor relativo al centro del boton
  → translateX(dx * 0.3) translateY(dy * 0.3)
  → transition: none (seguimiento directo sin lag)
onMouseLeave:
  → reset a translate(0,0)
  → transition: var(--duration-normal) var(--ease-spring-soft)
```

Implementacion sugerida para frontend-developer: custom hook `useMagneticEffect(ref, strength=0.3)`.

Desactivar en `@media (hover: none)` — no aplica en touch.

#### Mobile (touch)
```css
@media (hover: none) {
  button:active { transform: scale(0.96); opacity: 0.85; transition: 80ms; }
}
```

---

### 2. Card (3 variantes)

**Atomic level**: Molecule

---

#### 2A. Case Study Card

**Anatomia**:
```
┌────────────────────────────────────────┐
│ [thumbnail image — 16:9 o 3:2]        │ ← overflow hidden
│                                        │
├────────────────────────────────────────┤
│ [categoria badge]        [año]         │
│ [titulo del caso — Instrument Serif]   │
│ [descripcion breve — 2 lineas max]     │
│                                        │
│ [metrica destacada: numero + label]    │ ← Instrument Serif display
│                                        │
│ [CTA link → "Ver caso"]               │
└────────────────────────────────────────┘
```

**Propiedades**:
- bg: `--bg-surface`
- border: `1px solid var(--border-subtle)`
- border-radius: `--radius-none` (0px — editorial)
- padding: `var(--space-6)`
- thumbnail: width 100%, aspect-ratio 16/9, object-fit cover

**Estados**:
- `default`: border-subtle, shadow-sm
- `hover`:
  - card: `translateY(-6px)` + `--shadow-lg` + border `--border-accent`
  - thumbnail: `scale(1.04)` (overflow hidden sobre el contenedor)
  - metrica: color `--accent-400`
  - CTA: underline visible
  - duration: `--duration-slow` ease `--ease-primary`
- `focus-visible`: outline `2px solid var(--accent-500)` en el card como region

**Micro-interaccion**: thumbnail parallax sutil en hover — el thumbnail escala y el contenido hace lift. La metrica cambia de color con delay de 100ms.

**Mobile**: `active:scale-[0.99] active:brightness-95` (tactile feedback). Hover effects desactivados.

---

#### 2B. Service Card

**Anatomia**:
```
┌──────────────────────────────────┐
│ [icono — monolínea Lucide 24px]  │
│                                  │
│ [titulo — Instrument Serif 24px] │
│ [scope — lista de items 3-4]     │
│                                  │
│ [CTA ghost button]               │
└──────────────────────────────────┘
```

**Propiedades**:
- bg: `--bg-surface`
- border: `1px solid var(--border-subtle)`
- border-radius: `--radius-lg` (8px — menos rigido que case study)
- padding: `var(--space-8)`
- icono: color `--accent-500`, size 24px, stroke-width 1.5

**Estados**:
- `default`: icono accent-500
- `hover`:
  - border: `--border-accent`
  - bg: `--bg-elevated`
  - icono: `rotate(8deg) scale(1.1)` — duration 200ms
  - titulo: color `--text-primary`
  - duration: `--duration-hover` ease `--ease-primary`

**Mobile**: `active:border-accent active:bg-elevated`

---

#### 2C. Metric Card

**Anatomia**:
```
┌──────────────────────┐
│                      │
│  [numero grande]     │ ← Instrument Serif --text-7xl (88px)
│  [label descriptivo] │ ← Geist Sans --text-sm --text-secondary
│  [contexto/fuente]   │ ← --text-xs --text-tertiary (opcional)
│                      │
└──────────────────────┘
```

**Propiedades**:
- bg: transparent (se integra a la seccion de fondo)
- border-left: `3px solid var(--accent-500)` — linea editorial
- padding-left: `var(--space-6)`
- numero: color `--text-primary`, font Instrument Serif, letter-spacing `--tracking-tight`

**Estados**: sin hover propio — animacion es el Stat Counter (ver componente 9).

---

### 3. Navigation

**Atomic level**: Organism

#### Anatomia — Header desktop

```
[logo "LR"] ─────────────────────── [Trabajo] [Servicios] [Sobre] [CV] ─ [Hablemos →]
```

- height: 64px
- bg: `transparent` (inicial) → `rgba(10,10,10,0.85) backdrop-blur(20px)` al scroll
- border-bottom: none (inicial) → `1px solid var(--border-subtle)` al scroll
- position: `sticky top-0 z-50`
- padding-x: `var(--container-px)` con max `--container-max`
- transition: bg + border + blur en `--duration-slow` `--ease-primary`

#### Logo "LR" — Monograma

- Tipografia: Instrument Serif, ~28px, color `--text-primary`
- Alternativa: SVG custom con las iniciales en composicion ligada
- hover: color `--accent-500` — duration `--duration-hover`
- El monograma NO lleva border ni contenedor — es pura tipografia

#### Nav links

- Font: Geist Sans 400 `--text-sm`
- Color: `--text-secondary`
- Tracking: `--tracking-wide` (ligero espaciado — refinado)
- Gap entre links: `var(--space-8)`
- hover:
  - color: `--text-primary`
  - underline animado: pseudo-elemento `::after` width 0 → 100%, height 1px, color `--accent-500`, `--duration-hover` ease `--ease-primary`
- active/current: color `--text-primary` + underline permanente `--accent-500`
- focus-visible: outline `2px solid var(--accent-500)` offset 4px

#### CTA "Hablemos"

- Variante: Button secondary sm (outline)
- Etiqueta: "Hablemos" con icono flecha `→` suffix
- En scroll: cambia a Button primary sm con efecto glow sutil

#### Scroll behavior

- Threshold: 80px scroll
- Transicion de estado: bg blur activa + shrink height 64px → 56px
- Logo: sin cambio de tamano (estabilidad editorial)

#### Mobile — Drawer

- Trigger: icono hamburger `Menu` (Lucide) en el header mobile
- Drawer: full-height desde la derecha, width 280px
- bg: `--bg-elevated`
- border-left: `1px solid var(--border-default)`
- Entrada: `translateX(100%) → translateX(0)` — `--duration-slow` `--ease-primary`
- Overlay: `rgba(0,0,0,0.6)` con fade-in
- Links en drawer: verticales, font `--text-xl`, Instrument Serif, gap `--space-6`
- CTA en drawer: Button primary lg, width 100%, al fondo
- Close: icono `X` en esquina superior derecha

---

### 4. Hero

**Atomic level**: Organism / Template

#### Layout — Split 60/40 (asimetrico)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  [col izquierda — 60%]          [col derecha — 40%]             │
│                                                                  │
│  [eyebrow]                      [imagen/grafico flotante]        │
│  [display title — 2-3 lineas]   [stats en columna]              │
│  [subtitle — 1-2 lineas]                                        │
│                                                                  │
│  [CTA primary]  [CTA ghost]                                     │
│                                                                  │
│  [scroll cue — abajo]                                            │
└──────────────────────────────────────────────────────────────────┘
```

Notas de layout:
- Grid: `grid-cols-[3fr_2fr]` en desktop, `grid-cols-1` en mobile
- min-height: `100svh`
- padding-top: `96px` (nav height + espacio) + `--section-py`
- La columna derecha esta verticalmente centrada con `align-items: center`
- En mobile: columna derecha va debajo, colapsada y sin imagen (estadisticas en row)

#### Eyebrow

- Texto: ej. "Director de Producto · Buenos Aires"
- Font: Geist Sans 400 `--text-xs`
- Color: `--text-secondary`
- Tracking: `--tracking-wider`
- Decorador: linea horizontal antes `——` (em dash repeat) o linea CSS 24px accent-500

#### Display title

- Font: Instrument Serif 400 (no bold — la gracia del serif es el peso inherente)
- Size: `--text-6xl` → `--text-5xl` en tablet → `--text-4xl` en mobile
- Color: `--text-primary`
- Letter-spacing: `--tracking-tight`
- Line-height: `--leading-tight`
- Max-width: 14ch (fuerza el salto de linea en punto narrativo elegido)
- La palabra o frase clave puede tener color `--accent-500` (una sola, no varias)

#### Subtitle

- Font: Geist Sans 300
- Size: `--text-lg`
- Color: `--text-secondary`
- Max-width: `--prose-max` (68ch)
- Line-height: `--leading-relaxed`

#### CTAs duales

- Primario: Button primary lg con magnetic effect
- Secundario: Button ghost lg (ej. "Ver trabajo")
- Gap: `var(--space-4)`
- Alineacion: left-aligned (no centrado — editorial)

#### Scroll cue

- Posicion: absolute bottom `var(--space-8)`, centered-x
- Anatomia: icono `ChevronDown` (Lucide) + texto "Scroll" opcional `--text-xs`
- Animacion: `translateY(0) → translateY(8px) → translateY(0)` — 2s ease-in-out infinite
- Color: `--text-tertiary`
- Desaparece: `opacity: 0` cuando el usuario hace scroll > 100px

#### Reveal animation (Framer Motion)

Secuencia de entrada con stagger:
1. Eyebrow: `fade-in + translateY(16px)` — delay 0
2. Title: `fade-in + translateY(24px)` — delay `--stagger-delay` (60ms)
3. Subtitle: `fade-in + translateY(16px)` — delay 120ms
4. CTAs: `fade-in + translateY(12px)` — delay 200ms
5. Columna derecha (imagen/stats): `fade-in + translateX(24px)` — delay 300ms

Todos con duration `--duration-reveal` (700ms) ease `--ease-primary`.

---

### 5. Section Header

**Atomic level**: Molecule

#### Anatomia

```
[eyebrow — CAPS]
[titulo — Instrument Serif grande]
[descripcion — Geist Sans, opcional]
```

#### Especificaciones

**Eyebrow**:
- Font: Geist Sans 400
- Size: `--text-xs`
- Color: `--accent-500`
- Tracking: `--tracking-wider`
- Transform: uppercase
- Decorador: `──` antes del texto (em-dash 16px linea accent-500 via pseudo o SVG)

**Titulo**:
- Font: Instrument Serif 400
- Size: `--text-4xl` → `--text-3xl` en mobile
- Color: `--text-primary`
- Tracking: `--tracking-tight`
- Line-height: `--leading-tight`
- Max-width: 22ch (para saltos de linea elegantes)

**Descripcion** (opcional):
- Font: Geist Sans 300
- Size: `--text-base`
- Color: `--text-secondary`
- Max-width: `--prose-max`
- Line-height: `--leading-relaxed`
- Margin-top: `var(--space-4)`

#### Variantes

| Variante    | Alineacion | Uso                          |
|-------------|------------|------------------------------|
| `left`      | left       | Secciones de contenido       |
| `centered`  | center     | Solo metricas / CTA final    |
| `editorial` | left       | Con numero de seccion offset |

Variante `editorial`: numero de seccion (`01`, `02`...) en Instrument Serif `--text-7xl` opacity 0.05, posicionado absolute top-right o top-left del section header. Crea profundidad sin ruido.

#### Reveal

Fade-up en IntersectionObserver con threshold 0.2. Eyebrow primero (delay 0), titulo (delay 60ms), descripcion (delay 120ms).

---

### 6. Form Inputs

**Atomic level**: Atom (Input, Textarea, Select)

**Base**: shadcn/ui `Input`, `Textarea`, con custom CSS tokens

#### Anatomia — Input text

```
[label — arriba, siempre visible]
[placeholder / valor]
[helper text / error message — abajo]
```

**Propiedades base**:
- bg: `--bg-surface`
- border: `1px solid var(--border-default)`
- border-radius: `--radius-md` (6px)
- padding: `var(--space-3) var(--space-4)`
- height: 44px (accesibilidad — target minimo)
- font: Geist Sans 400 `--text-base`
- color: `--text-primary`
- placeholder color: `--text-tertiary`

**Label**:
- Font: Geist Sans 500 `--text-sm`
- Color: `--text-secondary`
- Margin-bottom: `var(--space-2)`
- Tracking: `--tracking-wide`
- Transform: uppercase (opcional — estilo editorial)

#### Estados

- `default`: border `--border-default`
- `hover`: border `--border-strong`
- `focus`:
  - border: `1px solid var(--accent-500)`
  - box-shadow: `0 0 0 3px var(--accent-100)` — glow warmgold sutil
  - bg: `--bg-elevated`
  - transition: border + box-shadow `--duration-hover` `--ease-primary`
- `filled` (valor ingresado): label sube a 12px / usa label flotante si se prefiere
- `error`:
  - border: `1px solid var(--error)`
  - box-shadow: `0 0 0 3px rgba(194,91,78,0.15)`
  - mensaje debajo: Geist Sans `--text-xs` color `--error`
- `disabled`:
  - bg: `--bg-overlay`
  - border: `--border-subtle`
  - cursor: not-allowed
  - opacity: 0.5

#### Textarea

Identico a Input con:
- min-height: 120px
- resize: vertical (solo vertical)
- padding: `var(--space-4)`

#### Select

- Identico a Input con icono `ChevronDown` al final
- Dropdown: bg `--bg-elevated`, border `--border-default`, border-radius `--radius-md`
- Option hover: bg `--bg-overlay`
- Option selected: color `--accent-500`

#### Micro-interaccion focus

El glow de focus se expande con keyframe:
```css
@keyframes focus-ring-expand {
  from { box-shadow: 0 0 0 0px var(--accent-100); }
  to   { box-shadow: 0 0 0 3px var(--accent-100); }
}
```
Duration: `--duration-fast` (150ms).

---

### 7. Badge / Pill

**Atomic level**: Atom

#### Anatomia

```
[icono-prefix? 12px] [etiqueta]
```

- border-radius: `--radius-pill` (999px)
- padding: `var(--space-1) var(--space-3)` (4px 12px)
- font: Geist Sans 500 `--text-xs`
- tracking: `--tracking-wide`
- height: 24px

#### Variantes

| Variante  | bg                | text               | border              |
|-----------|-------------------|--------------------|---------------------|
| `default` | `--bg-elevated`   | `--text-secondary` | `--border-default`  |
| `accent`  | `--accent-100`    | `--accent-400`     | `--accent-border`   |
| `skill`   | `--bg-overlay`    | `--text-primary`   | `--border-subtle`   |
| `category`| `--accent-100`    | `--accent-500`     | none                |
| `success` | rgba(74,140,110,0.1) | `--success`    | rgba(74,140,110,0.3)|
| `outline` | transparent       | `--text-secondary` | `--border-default`  |

#### Hover (badges interactivos)

- bg: `--bg-overlay` → `--accent-100`
- border: `--border-default` → `--accent-border`
- color: `--text-secondary` → `--accent-400`
- transition: `--duration-fast` `--ease-primary`

#### Grupo de skills

Cuando multiples badges se muestran como grupo (skill tags):
- `display: flex; flex-wrap: wrap; gap: var(--space-2)`
- Reveal: cada badge con stagger 30ms (muy sutil)

---

### 8. Timeline

**Atomic level**: Organism

**Uso**: historial de experiencia laboral en /sobre o /cv

#### Anatomia

```
[linea vertical — 1px border-default, left-margin 16px]

  ◆  [empresa + rol — inline]
     [periodo — text-secondary text-sm]
     [descripcion — body]
     [badges de skills/tecnologias]

  ◆  [siguiente item...]
```

Cada nodo:
- Dot: 8px x 8px, border-radius 50%, bg `--accent-500`, borde 2px solid `--bg-base`
- La linea vertical conecta los dots: `border-left: 1px solid var(--border-default)`
- El dot del item actual/mas reciente: size 10px, glow `0 0 0 3px var(--accent-100)`

#### Propiedades de item

**Empresa + Rol**:
- Empresa: Geist Sans 600 `--text-base` color `--text-primary`
- Separador: `·` color `--text-tertiary`
- Rol: Geist Sans 400 `--text-base` color `--text-secondary`

**Periodo**:
- Geist Sans 400 `--text-sm` color `--text-tertiary`
- Format: "Ene 2022 — Present" o rango

**Descripcion**:
- Geist Sans 400 `--text-base` color `--text-secondary`
- Max-width: `--prose-max`
- Line-height: `--leading-relaxed`
- Margin-top: `var(--space-2)`

**Skills**:
- Grupo de badges variante `skill`
- Margin-top: `var(--space-3)`

**Gap entre items**: `var(--space-10)` (40px)

#### Micro-interaccion

Reveal scroll: cada item hace `fade-in + translateX(-16px) → translateX(0)` al entrar en viewport, con stagger de 100ms entre items. La linea vertical se "dibuja" desde arriba hacia abajo usando un pseudo-elemento `::before` con height animada de 0% a 100% al primer item visible.

---

### 9. Stat Counter

**Atomic level**: Molecule

**Uso**: metricas animadas en hero o seccion dedicada

#### Anatomia

```
[numero animado — Instrument Serif display]
[label — Geist Sans sm]
[descripcion/fuente — Geist Sans xs, opcional]
```

#### Propiedades

**Numero**:
- Font: Instrument Serif 400
- Size: `--text-7xl` (88px) en display grande / `--text-5xl` en compacto
- Color: `--text-primary`
- Letter-spacing: `--tracking-tight`
- Font-variant-numeric: tabular-nums (para que el contador no salte de ancho)

**Label**:
- Font: Geist Sans 400
- Size: `--text-sm`
- Color: `--text-secondary`
- Tracking: `--tracking-wide`
- Margin-top: `var(--space-2)`

**Prefijo/sufijo** (ej. "$", "%", "+"):
- Mismo font que el numero pero `--text-3xl`
- Color: `--accent-500`
- Vertical-align: top (alineado al top del numero, no baseline)

#### Animacion de conteo

Trigger: IntersectionObserver con threshold 0.5 (el usuario ve el numero antes de que empiece).

Algoritmo de easing para el conteo:
```
easeOut: t => 1 - Math.pow(1 - t, 4)
duration: 1800ms (1.8s — suficiente para el drama sin exasperacion)
frames: requestAnimationFrame loop
```

El numero empieza en 0 (o desde un valor inicial definido) y llega al valor final.
Para numeros con decimales: mostrar un decimal al llegar al 95% del recorrido, entero hasta ese punto.

**Formato de salida**:
- < 1000: sin separador (ej. "230")
- 1000-9999: con punto (ej. "3.500")
- ≥ 10000: abreviado "15M", "2.3K" — no numero crudo

**Retrigger**: la animacion no se repite si ya se ejecuto (flag interno). Nunca en loop infinito.

---

### 10. Footer

**Atomic level**: Organism

#### Anatomia

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  [Monograma "LR"]        [Links internos]  [Redes sociales]    │
│  [tagline breve]                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [copyright] ──────────────────── [email contact / CTA minimal]│
└─────────────────────────────────────────────────────────────────┘
```

Grid: `grid-cols-[2fr_1fr_1fr]` en desktop → `grid-cols-1` en mobile (vertical, centrado)

#### Propiedades

**Seccion superior**:
- bg: `--bg-surface`
- border-top: `1px solid var(--border-subtle)`
- padding: `var(--space-16) 0 var(--space-10)`
- Container: `--container-max` con `--container-px`

**Monograma**:
- Instrument Serif 400 28px color `--text-primary`
- Hover: color `--accent-500`

**Tagline**:
- Geist Sans 300 `--text-sm` color `--text-tertiary`
- Max-width: 28ch
- Margin-top: `var(--space-3)`

**Links internos**:
- Label de grupo: Geist Sans 500 `--text-xs` uppercase tracking-wider `--text-tertiary`
- Links: Geist Sans 400 `--text-sm` `--text-secondary`
- hover: `--text-primary` + underline sweep `--accent-500` — `--duration-hover`
- Gap entre links: `var(--space-3)`

**Redes sociales**:
- Iconos: Lucide (o SVG brand) 18px, stroke 1.5
- Color: `--text-secondary`
- hover: color `--accent-500` + `scale(1.15)` — `--duration-fast`
- Redes: LinkedIn, GitHub, X/Twitter (segun preferencia de Lucas)
- Disposicion: row con `gap: var(--space-4)`

**Linea divisora**:
- `border-top: 1px solid var(--border-subtle)`
- Margin: `var(--space-8) 0`

**Seccion inferior** (copyright + contact):
- bg: mismo que superior (no cambiar)
- Font: Geist Sans 400 `--text-xs` `--text-tertiary`
- Copyright: "© 2026 Lucas Rojo. Todos los derechos reservados."
- Email: link `--text-secondary` hover `--accent-500` con underline
- Layout: space-between en desktop, centered stack en mobile

---

## Jerarquia Atomic Design — Resumen

| Nivel      | Componentes                                              |
|------------|----------------------------------------------------------|
| Atoms      | Button, Input, Textarea, Select, Badge/Pill              |
| Molecules  | FormField, NavItem, Metric Card, Stat Counter, Section Header |
| Organisms  | Header/Nav, Hero, Case Study Card, Service Card, Timeline, Footer |
| Templates  | PageLayout (hero + sections + footer)                    |

---

## Notas de implementacion para frontend-developer

1. **shadcn/ui**: instalar con `--style=new-york` y `--base-color=zinc`. Sobreescribir `--primary` con `--accent-500` en `globals.css`.
2. **Magnetic button**: implementar como wrapper React que escucha `mousemove` sobre `ref`, calcula offset y aplica `transform` via state + inline style. `will-change: transform` en el elemento.
3. **Stat Counter**: usar `useInView` de Framer Motion (threshold: 0.5) para trigger. El conteo es CSS-only si el numero es simple; para decimales y formato usar requestAnimationFrame.
4. **Timeline reveal**: `motion.div` de Framer Motion con `initial: { opacity: 0, x: -16 }` y `whileInView: { opacity: 1, x: 0 }` + `viewport={{ once: true }}`.
5. **Nav blur**: CSS `backdrop-filter: blur(20px)` + `background-color: rgba(10,10,10,0.85)`. Activar con clase JS al detectar `window.scrollY > 80`.
6. **Fonts**: Instrument Serif via Google Fonts (`display: swap`). Geist Sans y Geist Mono via `next/font/google` (zero-layout-shift).
7. **Dark mode**: todo el sistema es dark-first. Si se implementa light mode futuro, crear un layer `[data-theme="light"]` con overrides de tokens (no duplicar componentes).
8. **focus-visible**: siempre usar `:focus-visible` (nunca `:focus`) para no mostrar outline en clicks de mouse.
9. **touch targets**: `min-height: 44px` en todos los elementos interactivos. Verificar en DevTools mobile.
10. **Reduced motion**: envolver todas las animaciones en `@media (prefers-reduced-motion: no-preference)` o usar el hook `useReducedMotion` de Framer Motion.

---

*Design System v1.0 — Lucas Rojo Web — ui-designer*
