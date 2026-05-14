---
name: scroll-storytelling-reference
description: Referencia de scroll storytelling con Lenis + GSAP ScrollTrigger. Consultar cuando frontend-developer necesita smooth scroll, pinning multi-seccion, snap, horizontal scroll o parallax avanzado. No es un agente — es documentacion bajo demanda.
---

# Scroll Storytelling Reference — React/Next.js (2026)

> Lenis es el smooth scroll mas ligero y compatible con GSAP. Reemplaza Locomotive Scroll (obsoleto).

## Cuando consultar esta referencia

Solo cuando la tarea requiere:
- Smooth scroll nativo reemplazado por scroll suavizado (Lenis)
- Secciones pinned que cuentan una historia (scroll storytelling tipo Apple)
- Horizontal scroll dentro de una seccion vertical
- Snap points entre secciones (scroll se detiene en cada seccion)
- Parallax avanzado (mas de 2 capas o con velocidades variables)
- Progress bars vinculados al scroll

Si la animacion es un simple scroll reveal (fade-in al entrar en viewport) → usar GSAP ScrollTrigger basico de `better-gsap-reference.md`. No necesitas Lenis para eso.

---

## Setup: Lenis + GSAP

```bash
npm install lenis gsap @gsap/react
```

```tsx
"use client";

import { useEffect } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| Lenis | `lenis` | ~5KB | Smooth scroll, inercia, touch |
| GSAP Core | `gsap` | 33KB | Tweens, timelines |
| ScrollTrigger | `gsap/ScrollTrigger` | 12KB | Pinning, scrub, snap |

---

## Patron principal: Lenis + ScrollTrigger sincronizados

```tsx
"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function SmoothScrollProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,         // suavizado — 1.0-1.4 rango ideal
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // easeOutExpo
      touchMultiplier: 2,    // velocidad en touch devices
    });

    // Sync Lenis con GSAP ScrollTrigger
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0); // evita saltos en scroll lento

    return () => {
      lenis.destroy();
      gsap.ticker.remove(lenis.raf);
    };
  }, []);

  return <>{children}</>;
}
```

**Uso en layout.tsx:**
```tsx
import { SmoothScrollProvider } from "@/components/smooth-scroll-provider";

export default function RootLayout({ children }) {
  return (
    <html lang="es" dir="ltr">
      <body>
        <SmoothScrollProvider>{children}</SmoothScrollProvider>
      </body>
    </html>
  );
}
```

**Regla critica**: Lenis REEMPLAZA el scroll nativo. Cualquier `scrollTo`, `scrollIntoView`, `window.scrollTo` debe pasar por Lenis:
```tsx
// MAL — bypasea Lenis, el scroll "salta"
window.scrollTo({ top: 0, behavior: "smooth" });

// BIEN — usa Lenis
lenis.scrollTo(0);
lenis.scrollTo("#seccion", { offset: -80 }); // con offset de header
```

---

## Receta 1: Scroll storytelling con pinning (tipo Apple)

Seccion fija mientras el usuario scrollea, revelando contenido progresivamente.

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function StorytellingSection() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const panels = gsap.utils.toArray<HTMLElement>(".story-panel");

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".story-wrapper",
        start: "top top",
        end: () => `+=${panels.length * 100}%`,
        pin: true,
        scrub: 1,
        snap: {
          snapTo: 1 / (panels.length - 1),
          duration: { min: 0.2, max: 0.5 },
          ease: "power2.inOut",
        },
      },
    });

    panels.forEach((panel, i) => {
      if (i === 0) return; // primer panel ya visible
      tl.fromTo(panel,
        { opacity: 0, y: 60 },
        { opacity: 1, y: 0, duration: 1 },
        i // posicion en la timeline
      );
      // Ocultar panel anterior
      tl.to(panels[i - 1],
        { opacity: 0, y: -30, duration: 0.5 },
        i - 0.5
      );
    });
  }, { scope: container });

  return (
    <div ref={container}>
      <section className="story-wrapper relative h-screen overflow-hidden">
        <div className="story-panel absolute inset-0 flex items-center justify-center">
          <h2>Paso 1: El problema</h2>
        </div>
        <div className="story-panel absolute inset-0 flex items-center justify-center opacity-0">
          <h2>Paso 2: La solucion</h2>
        </div>
        <div className="story-panel absolute inset-0 flex items-center justify-center opacity-0">
          <h2>Paso 3: El resultado</h2>
        </div>
      </section>
    </div>
  );
}
```

---

## Receta 2: Horizontal scroll dentro de seccion vertical

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function HorizontalScroll() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    const sections = gsap.utils.toArray<HTMLElement>(".h-panel");
    const totalWidth = sections.length * 100; // % del viewport

    gsap.to(sections, {
      xPercent: -100 * (sections.length - 1),
      ease: "none",
      scrollTrigger: {
        trigger: ".h-scroll-wrapper",
        start: "top top",
        end: () => `+=${totalWidth}%`,
        pin: true,
        scrub: 1,
        snap: 1 / (sections.length - 1),
        invalidateOnRefresh: true, // recalcula en resize
      },
    });
  }, { scope: container });

  return (
    <div ref={container}>
      <div className="h-scroll-wrapper overflow-hidden">
        <div className="flex w-[400vw]"> {/* 4 paneles = 400vw */}
          <div className="h-panel w-screen h-screen flex-shrink-0">Panel 1</div>
          <div className="h-panel w-screen h-screen flex-shrink-0">Panel 2</div>
          <div className="h-panel w-screen h-screen flex-shrink-0">Panel 3</div>
          <div className="h-panel w-screen h-screen flex-shrink-0">Panel 4</div>
        </div>
      </div>
    </div>
  );
}
```

---

## Receta 3: Parallax multi-capa con velocidades variables

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function ParallaxHero() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    // Cada capa se mueve a velocidad diferente
    const layers = [
      { selector: ".parallax-bg", speed: 0.3 },      // mas lento = mas lejos
      { selector: ".parallax-mid", speed: 0.6 },
      { selector: ".parallax-fg", speed: 1.0 },       // velocidad normal
      { selector: ".parallax-text", speed: 1.3 },     // mas rapido = mas cerca
    ];

    layers.forEach(({ selector, speed }) => {
      gsap.to(selector, {
        yPercent: -50 * speed,
        ease: "none",
        scrollTrigger: {
          trigger: ".parallax-container",
          start: "top bottom",
          end: "bottom top",
          scrub: 1,
        },
      });
    });
  }, { scope: container });

  return (
    <div ref={container}>
      <section className="parallax-container relative h-[150vh] overflow-hidden">
        <div className="parallax-bg absolute inset-0">
          {/* Imagen de fondo */}
        </div>
        <div className="parallax-mid absolute inset-0">
          {/* Elementos medios */}
        </div>
        <div className="parallax-fg absolute inset-0">
          {/* Elementos cercanos */}
        </div>
        <div className="parallax-text absolute inset-0 flex items-center justify-center">
          <h1>Titulo con parallax</h1>
        </div>
      </section>
    </div>
  );
}
```

---

## Receta 4: Progress bar vinculado al scroll

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function ScrollProgress() {
  const progressRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.to(progressRef.current, {
      scaleX: 1,
      ease: "none",
      scrollTrigger: {
        trigger: document.documentElement,
        start: "top top",
        end: "bottom bottom",
        scrub: 0.3,
      },
    });
  });

  return (
    <div
      ref={progressRef}
      className="fixed top-0 left-0 right-0 h-1 bg-primary origin-left z-50"
      style={{ transform: "scaleX(0)" }}
    />
  );
}
```

---

## Receta 5: Snap scroll entre secciones full-screen

```tsx
useGSAP(() => {
  const sections = gsap.utils.toArray<HTMLElement>(".snap-section");

  ScrollTrigger.create({
    trigger: ".snap-container",
    start: "top top",
    end: `+=${sections.length * 100}vh`,
    pin: true,
    snap: {
      snapTo: 1 / (sections.length - 1),
      duration: { min: 0.3, max: 0.6 },
      delay: 0,
      ease: "power1.inOut",
    },
  });

  // Animar entrada de cada seccion
  sections.forEach((section) => {
    ScrollTrigger.create({
      trigger: section,
      start: "top center",
      onEnter: () => {
        gsap.from(section.querySelectorAll(".reveal"), {
          y: 40, opacity: 0, stagger: 0.1, duration: 0.6
        });
      },
      once: true,
    });
  });
}, { scope: container });
```

---

## Lenis — API rapida

```tsx
// Instancia global (si necesitas acceso fuera del provider)
import Lenis from "lenis";

const lenis = new Lenis();

// Scroll a elemento
lenis.scrollTo("#about", { offset: -80, duration: 1.2 });

// Scroll a posicion
lenis.scrollTo(0); // top

// Pausar scroll (modal abierto)
lenis.stop();

// Reanudar scroll
lenis.start();

// Escuchar scroll
lenis.on("scroll", ({ scroll, limit, velocity, direction, progress }) => {
  // scroll: posicion actual
  // progress: 0 a 1
  // direction: 1 (down) o -1 (up)
  // velocity: velocidad actual
});
```

---

## Anti-patterns

- **NO usar Lenis + CSS `scroll-behavior: smooth`** — conflicto. Lenis reemplaza el smooth scroll nativo. Eliminar `html { scroll-behavior: smooth; }` del CSS
- **NO usar `position: sticky` con Lenis para storytelling** — usar GSAP pin. Sticky y smooth scroll se pelean por el control del layout
- **NO crear mas de 20 ScrollTriggers en una pagina** — agrupar en timelines. Cada ST tiene un listener de scroll
- **NO animar el scroll wrapper de Lenis** — animar hijos. Lenis usa `transform: translate3d` en el wrapper
- **NO llamar `ScrollTrigger.refresh()` en un loop** — solo despues de que el DOM se estabilice (imagenes cargadas, fonts renderizadas). Usar `ScrollTrigger.refresh()` una vez, no por cada imagen
- **NO ignorar `invalidateOnRefresh: true`** en horizontal scroll — sin esto, el resize de ventana rompe los calculos

## Mobile

- **Lenis `touchMultiplier`**: ajustar entre 1.5-2.5. Muy alto = scroll incontrolable en iOS
- **Desactivar Lenis en mobile si no es necesario**: si el smooth scroll no agrega valor en mobile, usar media query para instanciarlo solo en desktop
- **iOS Safari barra de direccion**: con Lenis + ScrollTrigger, agregar `ScrollTrigger.normalizeScroll(true)` para compensar el resize de la barra
- **Reducir pinning en mobile**: secciones pinned largas en mobile frustran al usuario. Considerar reemplazar por scroll normal con reveals

## Performance

- **Lenis duration**: 1.0-1.4 es el rango optimo. Menos de 0.8 se siente nervioso. Mas de 1.6 se siente pesado
- **ScrollTrigger markers**: SIEMPRE desarrollar con `markers: true` y remover antes de produccion
- **Lazy refresh**: si hay imagenes lazy-load, usar `ScrollTrigger.refresh()` despues del `onLoad` de la ultima imagen
- **Cleanup**: Lenis.destroy() + gsap.ticker.remove() en el unmount del provider. Memory leak asegurado si no se limpia
