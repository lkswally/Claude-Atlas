---
name: better-gsap-reference
description: Referencia de GSAP para React/Next.js. Consultar cuando frontend-developer decide usar Tier 3 (timeline, scroll pin, SplitText, SVG). No es un agente — es documentacion bajo demanda.
---

# GSAP Reference — React/Next.js (2026)

> Desde abril 2025, GSAP es 100% gratis (todos los plugins incluidos). `npm install gsap` trae todo.

## Cuando consultar esta referencia

Solo cuando el frontend-developer decidio usar **Tier 3** de animacion:
- Timeline con 5+ elementos sincronizados
- Scroll con pinning (seccion fija mientras scrolleas)
- Animacion de texto por letra/palabra (SplitText)
- SVG morphing o path follow
- Canvas/WebGL/Three.js tweening

Si la animacion es simple (hover, fade, toggle) → usar CSS o Framer Motion. No necesitas esto.

---

## Setup basico

```bash
npm install gsap @gsap/react
```

```tsx
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);
```

**Regla de imports**: importar SOLO los plugins que uses. No importar `gsap/all`.

| Plugin | Import | Size (~gzip) | Para que |
|--------|--------|-------------|---------|
| Core | `gsap` | 33KB | Tweens, timelines, easing |
| ScrollTrigger | `gsap/ScrollTrigger` | 12KB | Scroll-driven, pinning, snap |
| SplitText | `gsap/SplitText` | 5KB | Animacion por letra/palabra/linea |
| Flip | `gsap/Flip` | 8KB | Animar entre estados de layout |
| DrawSVG | `gsap/DrawSVG` | 3KB | Animar stroke de SVG |
| MorphSVG | `gsap/MorphSVG` | 6KB | Morphing entre paths SVG |
| Draggable | `gsap/Draggable` | 7KB | Drag and drop con momentum |

---

## Patron principal: useGSAP hook

```tsx
"use client"; // OBLIGATORIO en Next.js App Router

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

export function HeroSection() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    // Todo lo de adentro se auto-limpia al desmontar
    gsap.from(".hero-title", { y: 50, opacity: 0, duration: 0.8 });
    gsap.from(".hero-subtitle", { y: 30, opacity: 0, duration: 0.6, delay: 0.3 });
  }, { scope: container }); // scope limita selectores a este container

  return (
    <div ref={container}>
      <h1 className="hero-title">...</h1>
      <p className="hero-subtitle">...</p>
    </div>
  );
}
```

**Reglas del useGSAP:**
- `scope` es OBLIGATORIO — sin el, `.hero-title` matchea en TODA la app
- Todo tween/ScrollTrigger creado dentro se limpia automaticamente al desmontar
- Para animaciones en event handlers, usar `contextSafe`:

```tsx
const { contextSafe } = useGSAP(() => {}, { scope: container });

const handleClick = contextSafe(() => {
  gsap.to(".box", { rotation: 360, duration: 0.5 });
});
```

---

## ScrollTrigger — Patron con pinning

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function PinnedSection() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".pin-wrapper",
        start: "top top",
        end: "+=200%",
        pin: true,
        scrub: 1, // NUNCA scrub: true en mobile (1 = suavizado)
      },
    });

    tl.from(".step-1", { opacity: 0, y: 50 })
      .from(".step-2", { opacity: 0, y: 50 }, "+=0.2")
      .from(".step-3", { opacity: 0, y: 50 }, "+=0.2");
  }, { scope: container });

  return (
    <div ref={container}>
      <div className="pin-wrapper">
        <div className="step-1">...</div>
        <div className="step-2">...</div>
        <div className="step-3">...</div>
      </div>
    </div>
  );
}
```

**Regla de pinning**: NUNCA animar el mismo elemento que esta pinned. Pinear el wrapper, animar los hijos.

---

## SplitText — Animacion de texto

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { SplitText } from "gsap/SplitText";

gsap.registerPlugin(useGSAP, SplitText);

export function AnimatedHeading() {
  const heading = useRef<HTMLHeadingElement>(null);

  useGSAP(() => {
    const split = SplitText.create(heading.current!, { type: "chars" });
    gsap.from(split.chars, {
      y: 30,
      opacity: 0,
      stagger: 0.03,
      duration: 0.5,
      ease: "power2.out",
    });
    // split.revert() se llama automaticamente via useGSAP cleanup
  });

  return <h1 ref={heading}>Texto animado por letra</h1>;
}
```

---

## Timeline con labels

```tsx
useGSAP(() => {
  const tl = gsap.timeline({ defaults: { duration: 0.6, ease: "power2.out" } });

  tl.from(".logo", { scale: 0, rotation: -180 })
    .from(".nav-item", { y: -20, opacity: 0, stagger: 0.1 }, "-=0.3") // overlap
    .addLabel("navDone")
    .from(".hero-image", { x: 100, opacity: 0 }, "navDone")
    .from(".hero-text", { x: -100, opacity: 0 }, "navDone+=0.2");
}, { scope: container });
```

---

## Next.js gotchas

1. **`"use client"` obligatorio** en todo componente con useGSAP
2. **ScrollTrigger.refresh() despues de cambios de ruta**:
   ```tsx
   import { usePathname } from "next/navigation";

   const pathname = usePathname();
   useGSAP(() => {
     // animaciones...
     return () => ScrollTrigger.getAll().forEach(t => t.kill());
   }, { dependencies: [pathname] });
   ```
3. **Contenido dinamico** (API data, imagenes lazy): llamar `ScrollTrigger.refresh()` despues de que el contenido se renderice — si no, los trigger points son incorrectos
4. **NO usar** `useLayoutEffect` directo — `useGSAP` ya usa `useIsomorphicLayoutEffect` internamente

---

## Mobile — Reglas de performance

- **`scrub: 1`** (suavizado), NUNCA `scrub: true` (1:1 tracking) — demasiado costoso en mobile
- **Limitar ScrollTriggers**: agrupar reveals similares en 1 ScrollTrigger con `stagger`, no 1 por elemento
- **iOS Safari**: la barra de direccion al hacer scroll dispara eventos que confunden pinning. Si hay problemas, agregar `ScrollTrigger.normalizeScroll(true)`
- **SVG pesado en mobile**: simplificar paths o convertir a Canvas
- **`will-change`**: NO usar globalmente. Solo en elementos a punto de animar con compositing complejo. Remover despues de la animacion

---

## Que NO hacer

- No importar `gsap/all` (trae 100KB+ innecesarios)
- No usar selectores globales sin `scope` (anima elementos de otros componentes)
- No animar `width`, `height`, `top`, `left` (trigger layout/paint). Usar `x`, `y`, `scale`, `opacity`
- No crear ScrollTrigger fuera de `useGSAP` o `contextSafe` (memory leak)
- No pinear y animar el mismo elemento (rompe calculo de posicion)
- No hacer `scrub: true` en mobile (lag visible)
