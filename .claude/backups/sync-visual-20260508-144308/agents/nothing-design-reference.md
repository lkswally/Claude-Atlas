---
name: nothing-design-reference
description: Referencia completa del Nothing Design System (tokens, componentes, platform mapping). Cargado condicionalmente por ux-architect, ui-designer y frontend-developer cuando design_system incluye "nothing". Basado en github.com/dominikmartn/nothing-design-skill v3.0.0.
---

# Nothing Design System — Referencia Completa

> **Cuándo cargar este archivo**: Solo si el handoff del orquestador incluye `DESIGN_SYSTEM: nothing-full` o `DESIGN_SYSTEM: nothing-partial`.
> En modo `nothing-partial`, aplicar SOLO a los componentes/secciones listados en `NOTHING_SCOPE`.
> En modo `nothing-full`, aplicar a todo el proyecto.

---

## Modo Parcial — Reglas de Coexistencia

Cuando `DESIGN_SYSTEM: nothing-partial`, el proyecto tiene un design system propio (custom) y Nothing se aplica solo a secciones específicas.

### Estrategia de aislamiento
- **CSS scoping**: todos los tokens Nothing van bajo un selector `.nd` o `[data-design="nothing"]`
- **No contaminar el global**: NUNCA poner tokens Nothing en `:root` si es parcial — usar `.nd { --nd-black: #000; ... }`
- **Prefijo `nd-`**: en modo parcial, todas las variables CSS llevan prefijo `--nd-` para evitar colisiones con el design system principal
- **Fuentes**: las Google Fonts de Nothing (Space Grotesk, Space Mono, Doto) se cargan igual, pero solo se aplican dentro de `.nd`
- **Componentes mixtos**: un componente Nothing puede vivir dentro de un layout custom, pero NUNCA mezclar tokens Nothing con tokens custom en el mismo componente

### Ejemplo de scope parcial
```html
<!-- Sección con Nothing Design -->
<section class="nd" data-design="nothing">
  <h2 style="font-family: 'Doto'">78%</h2>
  <div class="nd-progress-bar">...</div>
</section>

<!-- Sección con design system del proyecto -->
<section>
  <h2>Nuestros servicios</h2>
  <p>Texto normal del proyecto</p>
</section>
```

### Qué hereda y qué no
| Aspecto | Modo full | Modo parcial |
|---------|-----------|-------------|
| Tokens en `:root` | Sí | NO — van bajo `.nd` |
| Prefijo variables | Sin prefijo (`--black`) | Con prefijo (`--nd-black`) |
| Google Fonts | Global | Global (compartidas, no molestan) |
| Reglas prohibidas (no shadows, etc.) | Todo el proyecto | Solo dentro de `.nd` |
| Anti-patterns | Todo el proyecto | Solo dentro de `.nd` |
| Dark/light mode | Global toggle | El contenedor `.nd` respeta el toggle global |

---

# 1. FILOSOFÍA DE DISEÑO

- **Restar, no sumar.** Cada elemento debe ganarse su pixel. Default: eliminar.
- **La estructura es el ornamento.** Exponer el grid, los datos, la jerarquía misma.
- **Monocromo es el lienzo.** El color es un evento, no un default — excepto para status de datos.
- **La tipografía hace el trabajo pesado.** Escala, peso y espaciado crean jerarquía — no color, ni iconos, ni bordes.
- **Ambos modos son de primera clase.** Dark: OLED negro. Light: off-white cálido. Ninguno es "derivado".
- **Calidez industrial.** Técnico y preciso, pero nunca frío.

## 1.1 Regla de Tres Capas (por pantalla)

| Capa | Qué | Cómo |
|------|-----|------|
| **Primaria** | LO principal que el usuario ve primero (número, headline, estado) | Doto o Space Grotesk display. `--text-display`. 48-96px de aire |
| **Secundaria** | Contexto de soporte (labels, descripciones) | Space Grotesk body. `--text-primary`. Agrupado tight (8-16px) |
| **Terciaria** | Metadata, nav, info del sistema | Space Mono caption/label. `--text-secondary`. ALL CAPS. En bordes |

**Test**: entrecerrar los ojos. Si dos cosas compiten → una se achica, se apaga, o se mueve.

## 1.2 Disciplina Tipográfica (por pantalla)

Máximo:
- **2 familias** (Space Grotesk + Space Mono. Doto solo para hero moments)
- **3 tamaños** (uno grande, uno medio, uno chico)
- **2 pesos** (Regular + uno más — Light o Medium, rara vez Bold)

## 1.3 Espaciado como Significado

```
Tight (4-8px)   = "Pertenecen juntos" (ícono + label, número + unidad)
Medium (16px)    = "Mismo grupo, items distintos" (list items, form fields)
Wide (32-48px)   = "Nuevo grupo" (section breaks)
Vast (64-96px)   = "Nuevo contexto" (hero a contenido, divisiones mayores)
```

Si se necesita una línea divisora, el espaciado probablemente está mal.

## 1.4 Color como Jerarquía

Máx 4 niveles de gris por pantalla:
```
--text-display (100%)  → Hero numbers. Uno por pantalla.
--text-primary (90%)   → Body text, contenido principal.
--text-secondary (60%) → Labels, captions, metadata.
--text-disabled (40%)  → Disabled, timestamps, hints.
```

**Rojo (#D71921) NO es parte de la jerarquía.** Es una interrupción — "mirá ACÁ, AHORA."

## 1.5 Una Sorpresa por Pantalla

Ser consistente en: familias, labels (siempre Space Mono CAPS), ritmo de espaciado, roles de color, formas.
**Romper el patrón en exactamente UN lugar**: un número oversized, un widget circular entre rectángulos, un acento rojo entre grises, un headline Doto.

## 1.6 Asimetría > Simetría

- **Grande izquierda, chico derecha**: Hero metric + metadata stack
- **Top-heavy**: Headline grande arriba, contenido sparse abajo
- **Anclado a bordes**: Elementos importantes en bordes, espacio negativo en centro

## 1.7 El Vibe Nothing

1. Confianza a través del vacío. Grandes áreas de background sin interrumpir.
2. Precisión en lo pequeño. Letter-spacing, grises exactos, gaps de 4px.
3. Los datos como belleza. `36GB/s` en Space Mono a 48px ES el visual.
4. Honestidad mecánica. Los controles parecen controles físicos.
5. Un momento de sorpresa. Dot-matrix, widget circular, punto rojo.
6. Percusivo, no fluido. Click no swoosh, tick no chime.

---

# 2. ANTI-PATTERNS — NUNCA HACER

- No gradientes en UI chrome
- No sombras. No blur. Superficies planas, separación por bordes.
- No skeleton loading. Usar `[LOADING...]` texto o spinner segmentado.
- No toast popups. Usar status inline: `[SAVED]`, `[ERROR: ...]`
- No ilustraciones sad-face, mascotas, o empty states de varios párrafos
- No zebra striping en tablas
- No íconos filled, multi-color, ni emoji como UI
- No parallax, scroll-jacking, ni animación gratuita
- No easing spring/bounce. Solo ease-out sutil.
- No border-radius > 16px en cards. Botones: pill (999px) o técnico (4-8px).
- Data viz: diferenciar con **opacidad** (100%/60%/30%) o **patrón** (solid/striped/dotted) antes de color.

---

# 3. TOKENS

## 3.1 Tipografía

### Font Stack

| Rol | Font | Fallback | Peso |
|-----|------|----------|------|
| **Display** | `"Doto"` | `"Space Mono", monospace` | 400-700, variable dot-size |
| **Body / UI** | `"Space Grotesk"` | `"DM Sans", system-ui, sans-serif` | Light 300, Regular 400, Medium 500, Bold 700 |
| **Data / Labels** | `"Space Mono"` | `"JetBrains Mono", "SF Mono", monospace` | Regular 400, Bold 700 |

### Google Fonts (declarar siempre)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;700&family=Space+Mono:wght@400;700&family=Doto:wght@400;700&display=swap" rel="stylesheet">
```

### Escala Tipográfica

| Token | Size | Line Height | Letter Spacing | Uso |
|-------|------|-------------|----------------|-----|
| `--display-xl` | 72px | 1.0 | -0.03em | Hero numbers, time displays |
| `--display-lg` | 48px | 1.05 | -0.02em | Section heroes, porcentajes |
| `--display-md` | 36px | 1.1 | -0.02em | Page titles |
| `--heading` | 24px | 1.2 | -0.01em | Section headings |
| `--subheading` | 18px | 1.3 | 0 | Subsections |
| `--body` | 16px | 1.5 | 0 | Body text |
| `--body-sm` | 14px | 1.5 | 0.01em | Secondary body |
| `--caption` | 12px | 1.4 | 0.04em | Timestamps, footnotes |
| `--label` | 11px | 1.2 | 0.08em | ALL CAPS monospace labels |

### Reglas tipográficas
- **Doto**: solo 36px+, tracking tight, nunca para body
- **Labels**: siempre Space Mono, ALL CAPS, 0.06-0.1em spacing, 11-12px
- **Data/Números**: siempre Space Mono. Unidades como `--label`, adjacent
- **Jerarquía**: display (Doto) > heading (Space Grotesk) > label (Space Mono caps) > body (Space Grotesk). Máx 4 niveles.

## 3.2 Sistema de Color

### Paleta Primaria (Dark Mode)

| Token | Hex | Contraste en #000 | Rol |
|-------|-----|-------------------|-----|
| `--black` | `#000000` | — | Background primario (OLED) |
| `--surface` | `#111111` | 1.3:1 | Superficies elevadas, cards |
| `--surface-raised` | `#1A1A1A` | 1.5:1 | Elevación secundaria |
| `--border` | `#222222` | — | Divisores sutiles (solo decorativos) |
| `--border-visible` | `#333333` | — | Bordes intencionales |
| `--text-disabled` | `#666666` | 4.0:1 | Texto disabled, decorativo |
| `--text-secondary` | `#999999` | 6.3:1 | Labels, captions, metadata |
| `--text-primary` | `#E8E8E8` | 16.5:1 | Body text |
| `--text-display` | `#FFFFFF` | 21:1 | Headlines, hero numbers |

### Colores de Acento y Status

| Token | Hex | Uso |
|-------|-----|-----|
| `--accent` | `#D71921` | Señal: estados activos, destructivo, urgente. Uno por pantalla. Nunca decorativo. |
| `--accent-subtle` | `rgba(215,25,33,0.15)` | Tint backgrounds de acento |
| `--success` | `#4A9E5C` | Confirmado, completado, conectado |
| `--warning` | `#D4A843` | Precaución, pendiente, degradado |
| `--error` | `#D71921` | Comparte rojo acento — errores SON el momento de acento |
| `--info` | `#999999` | Usa color de texto secundario |
| `--interactive` | `#007AFF` / `#5B9BF6` | Texto tappable: links, picker values. No para botones. |

### Dark / Light Mode

| Token | Dark | Light |
|-------|------|-------|
| `--black` | `#000000` | `#F5F5F5` |
| `--surface` | `#111111` | `#FFFFFF` |
| `--surface-raised` | `#1A1A1A` | `#F0F0F0` |
| `--border` | `#222222` | `#E8E8E8` |
| `--border-visible` | `#333333` | `#CCCCCC` |
| `--text-disabled` | `#666666` | `#999999` |
| `--text-secondary` | `#999999` | `#666666` |
| `--text-primary` | `#E8E8E8` | `#1A1A1A` |
| `--text-display` | `#FFFFFF` | `#000000` |
| `--interactive` | `#5B9BF6` | `#007AFF` |

**Idénticos en ambos modos**: Rojo acento, colores de status, labels ALL CAPS, fuentes, escala tipográfica, espaciado, formas de componentes.

## 3.3 Espaciado (base 8px)

| Token | Valor | Uso |
|-------|-------|-----|
| `--space-2xs` | 2px | Ajustes ópticos solamente |
| `--space-xs` | 4px | Gaps ícono-label, padding tight |
| `--space-sm` | 8px | Spacing interno de componentes |
| `--space-md` | 16px | Padding estándar, gaps entre elementos |
| `--space-lg` | 24px | Separación de grupos |
| `--space-xl` | 32px | Márgenes de sección |
| `--space-2xl` | 48px | Breaks de sección mayor |
| `--space-3xl` | 64px | Ritmo vertical de página |
| `--space-4xl` | 96px | Breathing room hero |

## 3.4 Motion e Interacción

- **Duración**: 150-250ms micro, 300-400ms transiciones
- **Easing**: `cubic-bezier(0.25, 0.1, 0.25, 1)` — ease-out sutil. No spring/bounce.
- Preferir opacidad sobre posición. Los elementos hacen fade, no slide.
- Hover: borde/texto se ilumina. No scale, no sombras.

## 3.5 Iconografía

- Monolínea, 1.5px stroke, sin fill. 24x24 base, 20x20 área activa. Round caps/joins.
- Color hereda el color de texto. Máx 5-6 strokes.
- Preferidas: Lucide (thin), Phosphor (thin). Nunca filled o multi-color.

## 3.6 Motivo Dot-Matrix

**Cuándo usar**: tipografía hero (Doto), backgrounds decorativos, data viz dot-grid, indicadores de carga, empty states.

```css
.dot-grid {
  background-image: radial-gradient(circle, var(--border-visible) 1px, transparent 1px);
  background-size: 16px 16px;
}
.dot-grid-subtle {
  background-image: radial-gradient(circle, var(--border) 0.5px, transparent 0.5px);
  background-size: 12px 12px;
}
```

Dots 1-2px, grid uniforme 12-16px. Opacidad 0.1-0.2 para backgrounds, full para data. Nunca como borde de contenedor o estilo de botón.

---

# 4. COMPONENTES

## 4.1 Cards / Superficies

- Background: `--surface` o `--surface-raised`
- Borde: `1px solid --border`, o ninguno. Radius: 12-16px cards, 8px compact, 4px técnico
- Padding: 16-24px. Sin sombras. Superficies planas, separación por bordes.

## 4.2 Botones

| Variante | Background | Borde | Texto | Radius |
|----------|-----------|-------|-------|--------|
| Primary | `--text-display` (#FFF) | ninguno | `--black` | 999px (pill) |
| Secondary | transparent | `1px solid --border-visible` | `--text-primary` | 999px |
| Ghost | transparent | ninguno | `--text-secondary` | 0 |
| Destructive | transparent | `1px solid --accent` | `--accent` | 999px |

Todos: `Space Mono`, 13px, ALL CAPS, letter-spacing 0.06em, padding 12px 24px. Min height 44px.

## 4.3 Inputs

- Underline preferido (`1px solid --border-visible` bottom) o borde completo 8px radius
- Label arriba: estilo `--label` (Space Mono, ALL CAPS, `--text-secondary`)
- Focus: borde → `--text-primary`. Error: borde → `--accent`, mensaje debajo en `--accent`
- Campos de entrada de datos: `Space Mono` para input text

## 4.4 Listas / Data Rows

- Divisores: `1px solid --border`, full-width. Row padding: 12-16px vertical
- Izquierda: label (Space Mono caps, `--text-secondary`). Derecha: valor (`--text-primary`)
- Nunca backgrounds alternos. Usar divisores.

**Stat rows**: Label izq (Space Mono, ALL CAPS, `--text-secondary`), valor der (color = status color), unidad adjacent en `--label`. Trend arrow mismo color que valor.

## 4.5 Tablas / Data Grids

- Header: estilo `--label`, borde inferior `--border-visible`
- Celda: `Space Mono` numérico, `Space Grotesk` texto. Padding: 12px 16px
- Números derecha, texto izquierda. Sin zebra striping, sin backgrounds de celda.
- Row activo: `--surface-raised` bg, `2px solid --accent` indicador izquierdo

## 4.6 Navegación

- Bottom bar mobile, barra horizontal de texto desktop
- Labels: Space Mono, ALL CAPS. Activo: `--text-display` + dot/underline. Inactivo: `--text-disabled`
- Bracket `[ HOME ]  GALLERY  INFO` o pipe `HOME | GALLERY | INFO`
- **Back button**: circular 40-44px, `--surface` bg, chevron thin `<`, top-left 16px de bordes

## 4.7 Tags / Chips

- Borde: `1px solid --border-visible`, sin fill. Texto: Space Mono, `--caption`, ALL CAPS
- Radius: 999px (pill) o 4px (técnico). Padding: 4px 12px. Activo: `--text-display` borde+texto

## 4.8 Segmented Control

- Container: `1px solid --border-visible`, pill o 8px rounded
- Activo: `--text-display` bg, `--black` texto (invertido). Inactivo: transparent, `--text-secondary`
- Texto: Space Mono, ALL CAPS, `--label` size. Height: 36-44px. Transición: 200ms ease-out
- Máx 2-4 segmentos

## 4.9 Toggles / Switches

- Pill track, circle thumb. Off: `--border-visible` track, `--text-disabled` thumb
- On: `--text-display` track, `--black` thumb. Min touch target: 44px

## 4.10 Barras de Progreso Segmentadas (firma Nothing)

La visualización de datos firma. Bloques discretos — mecánico, como instrumento.

**Anatomía**: Label + valor arriba, barra full-width de segmentos rectangulares discretos con gaps de 2px.

**Segmentos**: Bloques square-ended, sin border-radius. Filled = color de status sólido. Empty = `--border` (dark) / `#E0E0E0` (light).

| Estado | Fill | Cuándo |
|--------|------|--------|
| Neutral | `--text-display` | Dentro de rango normal |
| Over limit | `--accent` | Excede target |
| Good | `--success` | Rango saludable |
| Moderate | `--warning` | Zona de precaución |

**Overflow**: segmentos filled continúan pasada la marca "full" en color de status (típicamente rojo).
**Tamaños**: Hero 16-20px, Standard 8-12px, Compact 4-6px height.

Siempre acompañar con readout numérico. Barra = proporción, número = precisión.

## 4.11 Otras Visualizaciones de Datos

- **Bar charts**: verticales, fill blanco, `--border` remainder. Square ends.
- **Gauges**: círculos stroke thin + tick marks, readout numérico centrado/adjacent.
- **Dot grids**: variar opacidad/tamaño para heat maps. Spacing uniforme.
- **Diferenciación de categorías**: opacidad → patrón → estilo de línea → color (último recurso).
- Siempre mostrar valor numérico junto a cualquier visual.

**Charts**: línea 1.5-2px `--text-display`, promedio dashed 1px `--text-secondary`. Axis labels: Space Mono, `--caption`. Grid: `--border`, solo horizontal. Sin area fill, sin legend boxes — etiquetar líneas directamente.

## 4.12 Widgets (Dashboard Cards)

- `--surface` bg, 16px radius. Hero metric: Doto/Space Mono grande, left-aligned
- Unidad: `--label` size, adjacent. Categoría: ALL CAPS Space Mono top-left
- Gauges de instrumento: brújula, termómetro, dial motifs

## 4.13 Overlays y Capas

Sin sombras. Capas mediante contraste de background y bordes.

- **Modales**: backdrop `rgba(0,0,0,0.8)`, dialog `--surface` + `1px solid --border-visible` + 16px radius, centrado max 480px. Close: `[ X ]` ghost button top-right.
- **Bottom sheets**: `--surface`, handle bar 2px centrado, 16px top radius, drag-to-dismiss.
- **Dropdowns**: `--surface-raised`, `1px solid --border-visible` 8px radius, items 44px. Selected: barra 2px accent izquierda. Sin sombra.
- **Toasts**: NO. Usar status inline: `[SAVED]`, `[ERROR: ...]`. Space Mono, `--caption`, cerca del trigger.

## 4.14 Patrones de Estado

- **Error**: borde input → `--accent` + mensaje debajo. Form-level: summary box `1px solid --accent`. Inline: prefijo `[ERROR]`. Nunca backgrounds rojos ni alert banners.
- **Empty**: centrado, 96px+ padding. Headline `--text-secondary`, 1 oración `--text-disabled`. Opcional: ilustración dot-matrix. Sin mascotas.
- **Loading**: spinner segmentado (estilo hardware), o barra segmentada + porcentaje. Sin skeletons — usar texto `[LOADING]` entre brackets.
- **Disabled**: opacidad 0.4 o `--text-disabled`. Bordes → `--border`.

---

# 5. PLATFORM MAPPING

## 5.1 HTML / CSS / Web

Cargar fuentes via Google Fonts `<link>`. Usar CSS custom properties, `rem` para tipo, `px` para spacing/bordes. Dark/light via `prefers-color-scheme` o class toggle.

### Variables CSS completas (modo full — en `:root`)
```css
:root {
  /* Nothing Design — Color (Dark Mode default) */
  --black: #000000;
  --surface: #111111;
  --surface-raised: #1A1A1A;
  --border: #222222;
  --border-visible: #333333;
  --text-disabled: #666666;
  --text-secondary: #999999;
  --text-primary: #E8E8E8;
  --text-display: #FFFFFF;
  --accent: #D71921;
  --accent-subtle: rgba(215,25,33,0.15);
  --success: #4A9E5C;
  --warning: #D4A843;
  --interactive: #5B9BF6;

  /* Nothing Design — Spacing */
  --space-2xs: 2px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;
  --space-4xl: 96px;

  /* Nothing Design — Motion */
  --ease-nd: cubic-bezier(0.25, 0.1, 0.25, 1);
  --duration-micro: 150ms;
  --duration-normal: 250ms;
  --duration-transition: 350ms;
}
```

### Variables CSS (modo parcial — bajo `.nd`)
```css
.nd, [data-design="nothing"] {
  --nd-black: #000000;
  --nd-surface: #111111;
  --nd-surface-raised: #1A1A1A;
  --nd-border: #222222;
  --nd-border-visible: #333333;
  --nd-text-disabled: #666666;
  --nd-text-secondary: #999999;
  --nd-text-primary: #E8E8E8;
  --nd-text-display: #FFFFFF;
  --nd-accent: #D71921;
  --nd-accent-subtle: rgba(215,25,33,0.15);
  --nd-success: #4A9E5C;
  --nd-warning: #D4A843;
  --nd-interactive: #5B9BF6;
  --nd-space-xs: 4px;
  --nd-space-sm: 8px;
  --nd-space-md: 16px;
  --nd-space-lg: 24px;
  --nd-space-xl: 32px;

  font-family: 'Space Grotesk', sans-serif;
  background: var(--nd-black);
  color: var(--nd-text-primary);
}
```

## 5.2 SwiftUI / iOS

Registrar fuentes en Info.plist, bundlear archivos `.ttf`. Usar `@Environment(\.colorScheme)` para cambio de modo.

```swift
extension Color {
    static let ndBlack = Color(hex: "000000")
    static let ndSurface = Color(hex: "111111")
    static let ndSurfaceRaised = Color(hex: "1A1A1A")
    static let ndBorder = Color(hex: "222222")
    static let ndBorderVisible = Color(hex: "333333")
    static let ndTextDisabled = Color(hex: "666666")
    static let ndTextSecondary = Color(hex: "999999")
    static let ndTextPrimary = Color(hex: "E8E8E8")
    static let ndTextDisplay = Color.white
    static let ndAccent = Color(hex: "D71921")
    static let ndSuccess = Color(hex: "4A9E5C")
    static let ndWarning = Color(hex: "D4A843")
    static let ndInteractive = Color(hex: "5B9BF6")
}
```

Valores light mode en la tabla Dark/Light de § 3.2. Font extension con `.custom("Doto"/"SpaceGrotesk-Regular"/"SpaceMono-Regular", size:)`.

## 5.3 React Native / Expo

Para mobile-developer, aplicar los mismos tokens via StyleSheet:
```typescript
const NothingTokens = {
  colors: {
    black: '#000000',
    surface: '#111111',
    surfaceRaised: '#1A1A1A',
    border: '#222222',
    borderVisible: '#333333',
    textDisabled: '#666666',
    textSecondary: '#999999',
    textPrimary: '#E8E8E8',
    textDisplay: '#FFFFFF',
    accent: '#D71921',
    success: '#4A9E5C',
    warning: '#D4A843',
    interactive: '#5B9BF6',
  },
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  fonts: {
    display: 'Doto',
    body: 'SpaceGrotesk-Regular',
    mono: 'SpaceMono-Regular',
  },
} as const;
```

Bundlear fuentes con `expo-font`. Usar `useColorScheme()` de React Native para dark/light.
