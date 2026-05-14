---
name: advanced-effects-reference
description: Referencia de Lottie, Rive, cursor effects y micro-interactions para React/Next.js. Consultar cuando frontend-developer necesita animaciones vectoriales complejas o micro-interactions avanzadas. No es un agente — es documentacion bajo demanda.
---

# Advanced Effects Reference — React/Next.js (2026)

## Cuando consultar esta referencia

Solo cuando la tarea requiere:
- Animaciones vectoriales exportadas de After Effects (Lottie)
- Animaciones interactivas de Rive (state machines)
- Cursor custom con seguimiento suave
- Botones magneticos (se atraen al cursor)
- Hover elastico (deformacion + rebote)
- Text reveal con mascara o clip-path

Si la animacion es CSS transition, Framer Motion o GSAP timeline → usar esos tiers. No necesitas esto.

---

## Seccion 1: Lottie en React

### Setup

```bash
npm install lottie-react
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| lottie-react | `lottie-react` | ~40KB | Wrapper React sobre lottie-web (light) |

### Patron principal

```tsx
"use client";

import Lottie from "lottie-react";
import animationData from "@/animations/loading.json"; // archivo .json de After Effects

export function LoadingAnimation() {
  return (
    <Lottie
      animationData={animationData}
      loop={true}
      autoplay={true}
      style={{ width: 200, height: 200 }}
    />
  );
}
```

### Con control programatico

```tsx
"use client";

import { useRef } from "react";
import Lottie, { LottieRefCurrentProps } from "lottie-react";
import checkAnimation from "@/animations/check.json";

export function SuccessCheck({ play }: { play: boolean }) {
  const lottieRef = useRef<LottieRefCurrentProps>(null);

  // Controlar playback
  const handleComplete = () => {
    lottieRef.current?.goToAndStop(0, true); // reset al terminar
  };

  return (
    <Lottie
      lottieRef={lottieRef}
      animationData={checkAnimation}
      loop={false}
      autoplay={play}
      onComplete={handleComplete}
      style={{ width: 120, height: 120 }}
    />
  );
}
```

### Lottie con scroll (GSAP)

```tsx
"use client";

import { useRef, useState } from "react";
import Lottie, { LottieRefCurrentProps } from "lottie-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import animationData from "@/animations/scroll-story.json";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function ScrollLottie() {
  const container = useRef<HTMLDivElement>(null);
  const lottieRef = useRef<LottieRefCurrentProps>(null);

  useGSAP(() => {
    const totalFrames = animationData.op; // ultimo frame

    ScrollTrigger.create({
      trigger: container.current,
      start: "top center",
      end: "bottom center",
      scrub: 1,
      onUpdate: (self) => {
        const frame = Math.floor(self.progress * totalFrames);
        lottieRef.current?.goToAndStop(frame, true);
      },
    });
  }, { scope: container });

  return (
    <div ref={container} className="h-[200vh]">
      <div className="sticky top-0 h-screen flex items-center justify-center">
        <Lottie
          lottieRef={lottieRef}
          animationData={animationData}
          autoplay={false}
          loop={false}
          style={{ width: 500, height: 500 }}
        />
      </div>
    </div>
  );
}
```

### Donde conseguir archivos Lottie
- **LottieFiles**: https://lottiefiles.com — biblioteca gratuita, filtrar por "free"
- **After Effects → Bodymovin plugin**: exporta animaciones AE como JSON
- Los archivos `.json` van en `public/animations/` o se importan directamente si son <100KB

---

## Seccion 2: Rive en React

### Setup

```bash
npm install @rive-app/react-canvas
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| @rive-app/react-canvas | `@rive-app/react-canvas` | ~60KB | Runtime Rive con Canvas renderer |

### Patron principal

```tsx
"use client";

import { useRive } from "@rive-app/react-canvas";

export function RiveAnimation() {
  const { RiveComponent } = useRive({
    src: "/animations/character.riv",  // archivo .riv en public/
    stateMachines: "idle",             // nombre del state machine en Rive
    autoplay: true,
  });

  return <RiveComponent style={{ width: 300, height: 300 }} />;
}
```

### Rive interactivo (state machines)

```tsx
"use client";

import { useRive, useStateMachineInput } from "@rive-app/react-canvas";

export function InteractiveButton() {
  const { rive, RiveComponent } = useRive({
    src: "/animations/button.riv",
    stateMachines: "button-sm",
    autoplay: true,
  });

  // Inputs definidos en el state machine de Rive
  const isHovered = useStateMachineInput(rive, "button-sm", "isHovered");
  const isPressed = useStateMachineInput(rive, "button-sm", "isPressed");

  return (
    <RiveComponent
      style={{ width: 200, height: 60, cursor: "pointer" }}
      onMouseEnter={() => isHovered && (isHovered.value = true)}
      onMouseLeave={() => isHovered && (isHovered.value = false)}
      onMouseDown={() => isPressed && isPressed.fire()}
    />
  );
}
```

### Lottie vs Rive — cuando usar cual

| Criterio | Lottie | Rive |
|----------|--------|------|
| Interactividad | Solo play/pause/seek | State machines, inputs, condicionales |
| Origen | After Effects + Bodymovin | Rive Editor (web) |
| Formato | JSON (~grande) | .riv (binario, mas compacto) |
| Mejor para | Iconos animados, loaders, ilustraciones | Botones interactivos, personajes, onboarding gamificado |
| Runtime | Canvas (lottie-web) | Canvas o WebGL |
| Costo editor | AE = $$$, Lottie player = gratis | Rive Editor = gratis (community plan) |

---

## Seccion 3: Cursor custom con seguimiento suave

```tsx
"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";

export function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const followerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cursor = cursorRef.current!;
    const follower = followerRef.current!;

    const moveCursor = (e: MouseEvent) => {
      // Cursor principal: sigue instantaneamente
      gsap.set(cursor, { x: e.clientX, y: e.clientY });

      // Follower: sigue con delay (inercia)
      gsap.to(follower, {
        x: e.clientX,
        y: e.clientY,
        duration: 0.6,
        ease: "power3.out",
      });
    };

    window.addEventListener("mousemove", moveCursor);

    // Escalar al hover sobre links/botones
    const interactives = document.querySelectorAll("a, button, [data-cursor-hover]");
    interactives.forEach((el) => {
      el.addEventListener("mouseenter", () => {
        gsap.to(follower, { scale: 2, opacity: 0.5, duration: 0.3 });
      });
      el.addEventListener("mouseleave", () => {
        gsap.to(follower, { scale: 1, opacity: 1, duration: 0.3 });
      });
    });

    return () => {
      window.removeEventListener("mousemove", moveCursor);
    };
  }, []);

  return (
    <>
      {/* Dot central */}
      <div
        ref={cursorRef}
        className="fixed top-0 left-0 w-2 h-2 bg-primary rounded-full pointer-events-none z-[9999] -translate-x-1/2 -translate-y-1/2 mix-blend-difference"
      />
      {/* Follower ring */}
      <div
        ref={followerRef}
        className="fixed top-0 left-0 w-10 h-10 border border-primary rounded-full pointer-events-none z-[9998] -translate-x-1/2 -translate-y-1/2 mix-blend-difference"
      />
    </>
  );
}
```

**Regla**: SIEMPRE ocultar en mobile/touch. Detectar con `@media (hover: hover)` o `window.matchMedia("(hover: hover)")`.

```tsx
// En el componente, solo renderizar si hay mouse:
const [hasHover, setHasHover] = useState(false);
useEffect(() => {
  setHasHover(window.matchMedia("(hover: hover)").matches);
}, []);
if (!hasHover) return null;
```

---

## Seccion 4: Botones magneticos

Boton que se "atrae" al cursor cuando esta cerca.

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";

export function MagneticButton({ children }: { children: React.ReactNode }) {
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleMouseMove = (e: React.MouseEvent) => {
    const button = buttonRef.current!;
    const rect = button.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;

    gsap.to(button, {
      x: x * 0.3,  // 0.3 = fuerza de atraccion (0.1-0.5)
      y: y * 0.3,
      duration: 0.3,
      ease: "power2.out",
    });
  };

  const handleMouseLeave = () => {
    gsap.to(buttonRef.current, {
      x: 0,
      y: 0,
      duration: 0.5,
      ease: "elastic.out(1, 0.5)", // rebote al soltar
    });
  };

  return (
    <button
      ref={buttonRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative px-8 py-4 bg-primary text-primary-foreground rounded-full"
    >
      {children}
    </button>
  );
}
```

---

## Seccion 5: Hover elastico (scale + rebote)

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";

export function ElasticCard({ children }: { children: React.ReactNode }) {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleEnter = () => {
    gsap.to(cardRef.current, {
      scale: 1.05,
      duration: 0.4,
      ease: "elastic.out(1, 0.5)",
    });
  };

  const handleLeave = () => {
    gsap.to(cardRef.current, {
      scale: 1,
      duration: 0.5,
      ease: "elastic.out(1, 0.3)",
    });
  };

  return (
    <div
      ref={cardRef}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      className="p-6 bg-card rounded-xl cursor-pointer"
    >
      {children}
    </div>
  );
}
```

---

## Seccion 6: Text reveal con clip-path

```tsx
"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function TextReveal({ text }: { text: string }) {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".reveal-text", {
      clipPath: "inset(0 100% 0 0)",  // oculto desde la derecha
      duration: 1.2,
      ease: "power4.inOut",
      stagger: 0.15,
      scrollTrigger: {
        trigger: container.current,
        start: "top 80%",
        once: true,
      },
    });
  }, { scope: container });

  return (
    <div ref={container}>
      {text.split("\n").map((line, i) => (
        <div key={i} className="overflow-hidden">
          <p className="reveal-text text-4xl font-bold">{line}</p>
        </div>
      ))}
    </div>
  );
}
```

**Variante: reveal desde abajo (mas comun)**
```tsx
gsap.from(".reveal-text", {
  clipPath: "inset(100% 0 0 0)",  // oculto desde abajo
  y: 20,
  duration: 0.8,
  ease: "power3.out",
  stagger: 0.1,
});
```

---

## Anti-patterns

- **NO usar Lottie para iconos simples** — un SVG animado con CSS es 40KB mas ligero. Lottie brilla en animaciones complejas (20+ capas, mascaras, path animations)
- **NO cargar Rive runtime si solo hay 1 animacion simple** — el runtime pesa 60KB. Justifica su peso con state machines
- **NO hacer el cursor custom muy grande** — 8-12px dot + 32-40px follower es el rango. Mas grande obstruye contenido
- **NO olvidar `pointer-events: none` en cursores custom** — sin esto, el cursor custom bloquea los clicks
- **NO usar magnetic buttons sin area minima** — el area de click del boton magnetico es su `getBoundingClientRect`, no el centro visual. Asegurar padding suficiente
- **NO animar `clip-path` en elementos con muchos hijos** — es costoso en layout. Preferir en textos o imagenes individuales, no en containers con docenas de hijos
- **NO usar `mix-blend-difference` en fondos con color medio (gris ~50%)** — el cursor desaparece. Funciona bien con fondos claros u oscuros

## Performance

- **Lottie JSON**: los archivos pueden ser grandes (500KB+). Minificar con `lottie-minify` o usar formato `.lottie` (comprimido)
- **Rive .riv**: ya binario y compacto. No necesita compresion extra
- **Cursor custom**: usar `gsap.set` (sin tween) para el dot, `gsap.to` (con tween) para el follower. Nunca animar ambos con tween — el dot debe ser instantaneo
- **Lazy load animaciones**: importar JSON/riv con `next/dynamic` o `React.lazy` si no estan en el viewport inicial
- **`will-change: transform`**: aplicar al follower del cursor y a botones magneticos durante la interaccion. Remover despues con `onComplete: () => el.style.willChange = "auto"`
