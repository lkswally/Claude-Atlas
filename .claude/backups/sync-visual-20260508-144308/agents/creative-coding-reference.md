---
name: creative-coding-reference
description: Referencia de creative coding con p5.js, GLSL shaders, generative art y particle systems para React/Next.js. Consultar cuando frontend-developer o xr-immersive-developer necesitan efectos generativos o shaders custom. No es un agente — es documentacion bajo demanda.
---

# Creative Coding Reference — React/Next.js (2026)

## Cuando consultar esta referencia

Solo cuando la tarea requiere:
- Fondos generativos (noise, flow fields, particulas organicas)
- Shaders custom con GLSL (distorsion, fluid, chromatic aberration)
- Arte algoritmico (patrones geometricos, fractales, L-systems)
- Particle systems en Canvas 2D (no Phaser — eso es xr-immersive-developer)
- Visualizacion de datos artistica (mas alla de charts)

Si el efecto es un simple gradient animado o particulas CSS → usar CSS/Framer Motion. No necesitas esto.

---

## Seccion 1: p5.js en React

### Setup

```bash
npm install p5 react-p5
npm install -D @types/p5
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| p5 | `p5` | ~280KB | Creative coding, canvas 2D/WebGL |
| react-p5 | `react-p5` | ~2KB | Wrapper React lifecycle |

**CRITICO**: p5 es pesado (~280KB). SIEMPRE lazy load:
```tsx
import dynamic from "next/dynamic";
const Sketch = dynamic(() => import("react-p5"), { ssr: false });
```

### Patron principal: Sketch como background

```tsx
"use client";

import dynamic from "next/dynamic";
import type p5Types from "p5";

const Sketch = dynamic(() => import("react-p5"), { ssr: false });

export function GenerativeBackground() {
  let particles: Array<{ x: number; y: number; vx: number; vy: number }> = [];

  const setup = (p5: p5Types, canvasParentRef: Element) => {
    p5.createCanvas(p5.windowWidth, p5.windowHeight).parent(canvasParentRef);
    p5.background(0);

    // Crear particulas
    for (let i = 0; i < 100; i++) {
      particles.push({
        x: p5.random(p5.width),
        y: p5.random(p5.height),
        vx: p5.random(-1, 1),
        vy: p5.random(-1, 1),
      });
    }
  };

  const draw = (p5: p5Types) => {
    p5.background(0, 20); // trail effect (alpha 20)

    particles.forEach((particle) => {
      // Perlin noise para movimiento organico
      const angle = p5.noise(particle.x * 0.005, particle.y * 0.005, p5.frameCount * 0.005) * p5.TWO_PI * 2;
      particle.vx = p5.cos(angle) * 2;
      particle.vy = p5.sin(angle) * 2;

      particle.x += particle.vx;
      particle.y += particle.vy;

      // Wrap around
      if (particle.x < 0) particle.x = p5.width;
      if (particle.x > p5.width) particle.x = 0;
      if (particle.y < 0) particle.y = p5.height;
      if (particle.y > p5.height) particle.y = 0;

      p5.noStroke();
      p5.fill(255, 100);
      p5.ellipse(particle.x, particle.y, 3);
    });
  };

  const windowResized = (p5: p5Types) => {
    p5.resizeCanvas(p5.windowWidth, p5.windowHeight);
  };

  return (
    <div className="fixed inset-0 -z-10" aria-hidden="true">
      <Sketch setup={setup} draw={draw} windowResized={windowResized} />
    </div>
  );
}
```

---

## Seccion 2: Flow fields (patron generativo fundamental)

```tsx
const draw = (p5: p5Types) => {
  const cols = Math.floor(p5.width / 20);
  const rows = Math.floor(p5.height / 20);
  const scale = 20;

  p5.background(0, 10);

  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const angle = p5.noise(x * 0.1, y * 0.1, p5.frameCount * 0.005) * p5.TWO_PI;
      const px = x * scale + scale / 2;
      const py = y * scale + scale / 2;
      const len = scale * 0.4;

      p5.push();
      p5.translate(px, py);
      p5.rotate(angle);
      p5.stroke(255, 80);
      p5.strokeWeight(1);
      p5.line(0, 0, len, 0);
      p5.pop();
    }
  }
};
```

---

## Seccion 3: GLSL Fragment Shaders con Three.js

### Setup (Three.js ya instalado para juegos 3D)

```bash
npm install three @types/three @react-three/fiber @react-three/drei
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| three | `three` | ~150KB | Motor 3D |
| @react-three/fiber | `@react-three/fiber` | ~30KB | React renderer para Three.js |
| @react-three/drei | `@react-three/drei` | ~40KB (tree-shakeable) | Helpers: shaderMaterial, etc |

### Patron: Full-screen shader como background

```tsx
"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const fragmentShader = `
  uniform float uTime;
  uniform vec2 uResolution;
  varying vec2 vUv;

  void main() {
    vec2 uv = vUv;

    // Ondas de color
    float r = sin(uv.x * 10.0 + uTime) * 0.5 + 0.5;
    float g = sin(uv.y * 10.0 + uTime * 0.7) * 0.5 + 0.5;
    float b = sin((uv.x + uv.y) * 8.0 + uTime * 1.3) * 0.5 + 0.5;

    gl_FragColor = vec4(r * 0.3, g * 0.2, b * 0.8, 1.0);
  }
`;

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

function ShaderPlane() {
  const meshRef = useRef<THREE.Mesh>(null);
  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
  }), []);

  useFrame(({ clock }) => {
    uniforms.uTime.value = clock.getElapsedTime();
  });

  return (
    <mesh ref={meshRef}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
      />
    </mesh>
  );
}

export function ShaderBackground() {
  return (
    <div className="fixed inset-0 -z-10" aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0, 1] }}
        gl={{ antialias: false, alpha: false }}
        dpr={[1, 1.5]} // limitar DPR para performance
      >
        <ShaderPlane />
      </Canvas>
    </div>
  );
}
```

### Recetas de shaders comunes

**Noise distorsion (ondas organicas):**
```glsl
// Agregar al fragment shader
float noise(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
  vec2 uv = vUv;
  float n = noise(uv * 5.0 + uTime * 0.3);
  uv += n * 0.05; // distorsion sutil
  // ... usar uv distorsionado para colores
}
```

**Chromatic aberration:**
```glsl
void main() {
  vec2 uv = vUv;
  vec2 center = vec2(0.5);
  vec2 dir = uv - center;
  float dist = length(dir);
  float offset = dist * 0.02; // intensidad

  float r = texture2D(uTexture, uv + dir * offset).r;
  float g = texture2D(uTexture, uv).g;
  float b = texture2D(uTexture, uv - dir * offset).b;

  gl_FragColor = vec4(r, g, b, 1.0);
}
```

**Gradient animado suave (alternativa a CSS gradient animation):**
```glsl
void main() {
  vec2 uv = vUv;
  float t = uTime * 0.2;

  vec3 color1 = vec3(0.1, 0.0, 0.3); // violeta oscuro
  vec3 color2 = vec3(0.0, 0.3, 0.5); // azul
  vec3 color3 = vec3(0.0, 0.1, 0.2); // dark teal

  float blend = sin(uv.x * 3.0 + t) * cos(uv.y * 2.0 + t * 0.7) * 0.5 + 0.5;
  vec3 color = mix(mix(color1, color2, blend), color3, sin(t + uv.y) * 0.5 + 0.5);

  gl_FragColor = vec4(color, 1.0);
}
```

---

## Seccion 4: Particle system en Canvas 2D (sin p5.js)

Mas ligero que p5.js cuando solo necesitas particulas.

```tsx
"use client";

import { useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
}

export function ParticleCanvas({ count = 200, color = "rgba(255,255,255," }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let animId: number;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    // Inicializar particulas
    const particles: Particle[] = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      life: Math.random() * 100,
      maxLife: 100 + Math.random() * 100,
      size: 1 + Math.random() * 2,
    }));

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.life++;

        // Reset
        if (p.life > p.maxLife) {
          p.x = Math.random() * canvas.width;
          p.y = Math.random() * canvas.height;
          p.life = 0;
        }

        // Fade based on life
        const alpha = 1 - p.life / p.maxLife;
        ctx.fillStyle = `${color}${alpha.toFixed(2)})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });

      // Conexiones entre particulas cercanas
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 100) {
            ctx.strokeStyle = `${color}${(1 - dist / 100).toFixed(2)})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, [count, color]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 -z-10 pointer-events-none"
      aria-hidden="true"
    />
  );
}
```

---

## Seccion 5: Simplex noise (alternativa a Perlin de p5)

Cuando necesitas noise sin cargar p5 completo.

```bash
npm install simplex-noise
```

```tsx
import { createNoise2D, createNoise3D } from "simplex-noise";

const noise2D = createNoise2D(); // 2D: texturas, terreno
const noise3D = createNoise3D(); // 3D: 2D + animacion temporal

// Uso en Canvas:
const value = noise2D(x * 0.01, y * 0.01); // rango -1 a 1
const animated = noise3D(x * 0.01, y * 0.01, time * 0.001); // 3er param = tiempo

// Normalizar a 0-1:
const normalized = (value + 1) / 2;
```

| Size | ~1KB gzip | Noise 2D, 3D, 4D sin dependencias |
|------|-----------|-----------------------------------|

---

## Anti-patterns

- **NO importar p5 sin lazy load** — 280KB bloqueando el render inicial. SIEMPRE `dynamic(() => import("react-p5"), { ssr: false })`
- **NO usar `noLoop()` de p5 como optimizacion general** — si el efecto es estatico, renderizar una vez y usar una imagen. p5 sin loop sigue consumiendo memoria del canvas
- **NO crear shaders con uniforms que cambian en cada frame sin necesidad** — solo actualizar `uTime` y derivar el resto en el shader. Cada uniform upload es un GPU call
- **NO hacer particle connections con O(n^2) con mas de 300 particulas** — usar spatial hashing o grid-based neighbor lookup
- **NO usar Three.js Canvas para un shader 2D simple** — es overkill. Un `<canvas>` con `getContext("2d")` + requestAnimationFrame pesa 0KB extra
- **NO olvidar `cancelAnimationFrame` en cleanup** — memory leak garantizado en SPA/Next.js
- **NO asumir WebGL disponible** — verificar con `document.createElement("canvas").getContext("webgl2")` y proveer fallback CSS

## Performance

- **p5.js**: lazy load SIEMPRE. Considerar `p5.min.js` (~280KB) vs `<canvas>` nativo (~0KB) para efectos simples
- **Three.js shaders**: limitar DPR a 1.5 (`dpr={[1, 1.5]}`). En retina, un shader fullscreen a DPR 3 renderiza 9x mas pixeles
- **Canvas 2D particles**: >500 particulas con connections = bajada de FPS en mobile. Reducir a 100 en mobile
- **requestAnimationFrame**: SIEMPRE usar deltaTime para framerate-independent animation. No asumir 60fps
- **Off-screen canvas**: para efectos pesados, renderizar en OffscreenCanvas y transferir al visible (Web Workers)

```tsx
// Deteccion de mobile para reducir efecto:
const isMobile = typeof window !== "undefined" && window.innerWidth < 768;
const particleCount = isMobile ? 50 : 200;
```
