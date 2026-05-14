---
name: reactive-audio-reference
description: Referencia de audio reactivo con Tone.js y Web Audio API para React/Next.js. Consultar cuando frontend-developer o xr-immersive-developer necesitan audio que responde a interaccion, scroll o datos. No es un agente — es documentacion bajo demanda.
---

# Reactive Audio Reference — React/Next.js (2026)

> Tone.js es el framework mas completo para audio interactivo en web. Web Audio API nativa para casos simples.

## Cuando consultar esta referencia

Solo cuando la tarea requiere:
- Audio que responde a scroll, hover o clicks (sound design interactivo)
- Visualizacion de audio en canvas (waveform, spectrum, bars)
- Sonidos de UI (hover, click, success, error) — mas alla de un simple `<audio>`
- Musica generativa o procedural
- Spatial audio (posicionamiento 3D de fuentes de sonido)

Si solo necesitas un `<audio>` con play/pause → usar HTML nativo. Si necesitas audio para un juego → usar Howler.js (ver xr-immersive-developer). No necesitas Tone.js para eso.

---

## Seccion 1: Tone.js Setup

### Instalacion

```bash
npm install tone
```

| Libreria | Import | Size (~gzip) | Para que |
|----------|--------|-------------|---------|
| tone | `tone` | ~150KB | Sintesis, efectos, scheduling, analisis |

**CRITICO**: Tone.js es pesado. SIEMPRE lazy load:
```tsx
import dynamic from "next/dynamic";
const AudioComponent = dynamic(() => import("@/components/audio-reactive"), { ssr: false });
```

### Regla fundamental: AudioContext requiere gesto del usuario

Los browsers bloquean el AudioContext hasta que el usuario interactua (click, tap, keypress). NUNCA intentar reproducir audio en mount.

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import * as Tone from "tone";

export function AudioStarter({ children }: { children: React.ReactNode }) {
  const [started, setStarted] = useState(false);
  const startedRef = useRef(false);

  const handleStart = useCallback(async () => {
    if (startedRef.current) return;
    await Tone.start(); // NECESARIO — desbloquea AudioContext
    startedRef.current = true;
    setStarted(true);
    console.log("Audio context started");
  }, []);

  return (
    <div onClick={handleStart} onKeyDown={handleStart}>
      {children}
      {!started && (
        <div className="fixed bottom-4 right-4 bg-card px-4 py-2 rounded-full text-sm animate-pulse">
          Click anywhere to enable audio
        </div>
      )}
    </div>
  );
}
```

---

## Seccion 2: UI Sound Effects (hover, click, feedback)

```tsx
"use client";

import { useCallback, useRef } from "react";
import * as Tone from "tone";

// Singleton — un solo synth para todos los sonidos UI
let uiSynth: Tone.Synth | null = null;

function getUISynth() {
  if (!uiSynth) {
    uiSynth = new Tone.Synth({
      oscillator: { type: "sine" },
      envelope: {
        attack: 0.005,
        decay: 0.1,
        sustain: 0,
        release: 0.1,
      },
      volume: -20, // suave — UI sounds no deben ser intrusivos
    }).toDestination();
  }
  return uiSynth;
}

export function useUISound() {
  const hover = useCallback(() => {
    const synth = getUISynth();
    synth.triggerAttackRelease("C6", "32n"); // nota alta, muy corta
  }, []);

  const click = useCallback(() => {
    const synth = getUISynth();
    synth.triggerAttackRelease("E5", "16n");
  }, []);

  const success = useCallback(() => {
    const synth = getUISynth();
    const now = Tone.now();
    synth.triggerAttackRelease("C5", "16n", now);
    synth.triggerAttackRelease("E5", "16n", now + 0.1);
    synth.triggerAttackRelease("G5", "16n", now + 0.2);
  }, []);

  const error = useCallback(() => {
    const synth = getUISynth();
    synth.triggerAttackRelease("A3", "8n");
  }, []);

  return { hover, click, success, error };
}
```

**Uso:**
```tsx
function MyButton() {
  const { hover, click } = useUISound();
  return (
    <button onMouseEnter={hover} onClick={click}>
      Click me
    </button>
  );
}
```

---

## Seccion 3: Audio reactivo al scroll

```tsx
"use client";

import { useEffect, useRef } from "react";
import * as Tone from "tone";

export function ScrollAudio() {
  const filterRef = useRef<Tone.Filter | null>(null);
  const playerRef = useRef<Tone.Player | null>(null);

  useEffect(() => {
    // Crear cadena de audio
    const filter = new Tone.Filter({
      frequency: 200,
      type: "lowpass",
      rolloff: -24,
    });
    const player = new Tone.Player({
      url: "/audio/ambient.mp3", // audio en public/
      loop: true,
      volume: -10,
    }).connect(filter);
    filter.toDestination();

    filterRef.current = filter;
    playerRef.current = player;

    // Scroll handler
    const handleScroll = () => {
      const progress = window.scrollY / (document.body.scrollHeight - window.innerHeight);
      // Mapear scroll (0-1) a frecuencia del filtro (200Hz - 5000Hz)
      const freq = 200 + progress * 4800;
      filter.frequency.rampTo(freq, 0.1);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", handleScroll);
      player.dispose();
      filter.dispose();
    };
  }, []);

  const togglePlay = async () => {
    await Tone.start();
    const player = playerRef.current;
    if (player?.state === "started") {
      player.stop();
    } else {
      player?.start();
    }
  };

  return (
    <button onClick={togglePlay} className="fixed bottom-4 right-4 z-50 p-3 rounded-full bg-card">
      Toggle ambient audio
    </button>
  );
}
```

---

## Seccion 4: Audio visualization (waveform + spectrum)

```tsx
"use client";

import { useEffect, useRef } from "react";
import * as Tone from "tone";

export function AudioVisualizer({ src }: { src: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const analyserRef = useRef<Tone.Analyser | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let animId: number;

    // Waveform analyser
    const waveform = new Tone.Analyser("waveform", 256);
    // FFT analyser (spectrum)
    const fft = new Tone.Analyser("fft", 64);

    const player = new Tone.Player(src).fan(waveform, fft).toDestination();
    analyserRef.current = waveform;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();

    const draw = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);

      // Dibujar waveform
      const waveValues = waveform.getValue() as Float32Array;
      ctx.beginPath();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
      ctx.lineWidth = 2;

      waveValues.forEach((val, i) => {
        const x = (i / waveValues.length) * w;
        const y = ((val as number) + 1) / 2 * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Dibujar barras FFT
      const fftValues = fft.getValue() as Float32Array;
      const barWidth = w / fftValues.length;

      fftValues.forEach((val, i) => {
        const dbValue = val as number;
        const barHeight = ((dbValue + 100) / 100) * h; // normalizar dB a pixels
        ctx.fillStyle = `hsl(${(i / fftValues.length) * 360}, 70%, 60%)`;
        ctx.fillRect(i * barWidth, h - barHeight, barWidth - 1, barHeight);
      });

      animId = requestAnimationFrame(draw);
    };

    // Solo empezar a dibujar cuando el audio este listo
    player.loaded.then(() => draw());

    return () => {
      cancelAnimationFrame(animId);
      player.dispose();
      waveform.dispose();
      fft.dispose();
    };
  }, [src]);

  const handlePlay = async () => {
    await Tone.start();
    // player ya esta conectado, solo necesitamos start
  };

  return (
    <div>
      <canvas
        ref={canvasRef}
        className="w-full h-48 bg-black rounded-lg"
        onClick={handlePlay}
      />
      <p className="text-sm text-muted-foreground mt-2">Click to start</p>
    </div>
  );
}
```

---

## Seccion 5: Musica generativa simple

```tsx
"use client";

import { useCallback } from "react";
import * as Tone from "tone";

export function useGenerativeMusic() {
  const start = useCallback(async () => {
    await Tone.start();

    // Escala pentatonica (siempre suena "bien")
    const notes = ["C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5"];

    const synth = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: {
        attack: 0.1,
        decay: 0.3,
        sustain: 0.2,
        release: 1.5,
      },
      volume: -15,
    }).toDestination();

    const reverb = new Tone.Reverb({ decay: 4, wet: 0.5 });
    synth.connect(reverb);
    reverb.toDestination();

    // Pattern aleatorio cada 0.5s
    const loop = new Tone.Loop((time) => {
      const note = notes[Math.floor(Math.random() * notes.length)];
      synth.triggerAttackRelease(note, "8n", time);
    }, "4n");

    Tone.getTransport().bpm.value = 72;
    loop.start(0);
    Tone.getTransport().start();

    return () => {
      loop.stop();
      Tone.getTransport().stop();
      synth.dispose();
      reverb.dispose();
    };
  }, []);

  return { start };
}
```

---

## Seccion 6: Web Audio API nativa (sin Tone.js)

Para casos simples donde 150KB de Tone.js no se justifica.

```tsx
"use client";

import { useCallback, useRef } from "react";

export function useSimpleSound() {
  const ctxRef = useRef<AudioContext | null>(null);

  const getContext = useCallback(() => {
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext();
    }
    return ctxRef.current;
  }, []);

  // Beep simple (sin dependencias)
  const beep = useCallback((frequency = 440, duration = 0.1, volume = 0.1) => {
    const ctx = getContext();
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.frequency.value = frequency;
    oscillator.type = "sine";
    gainNode.gain.value = volume;

    // Fade out para evitar click
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + duration);
  }, [getContext]);

  // Reproducir archivo de audio con Web Audio API
  const playFile = useCallback(async (url: string, volume = 0.5) => {
    const ctx = getContext();
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

    const source = ctx.createBufferSource();
    const gainNode = ctx.createGain();

    source.buffer = audioBuffer;
    source.connect(gainNode);
    gainNode.connect(ctx.destination);
    gainNode.gain.value = volume;

    source.start();
  }, [getContext]);

  return { beep, playFile };
}
```

---

## Anti-patterns

- **NO reproducir audio en mount** — los browsers lo bloquean. SIEMPRE esperar un gesto del usuario + `Tone.start()` o `new AudioContext()`
- **NO crear multiples AudioContext** — limite de ~6 por tab en la mayoria de browsers. Usar un singleton
- **NO olvidar `.dispose()` en cleanup** — Tone.js crea nodos Web Audio que no se garbage-collectan solos. Memory leak garantizado en SPA
- **NO usar audio auto-play en landing pages** — UX hostil. Ofrecer toggle visible (icono speaker) y empezar en mute
- **NO asumir que el usuario quiere sonido** — SIEMPRE ofrecer un control de mute/volumen visible y persistir la preferencia en localStorage
- **NO conectar analyser en cada frame** — crear la cadena de audio una vez en setup, leer valores en el draw loop
- **NO ignorar `{ passive: true }` en scroll listeners** — sin passive, el scroll se traba esperando al handler de audio

## Accesibilidad

- **SIEMPRE** ofrecer forma de silenciar (`Mute` / icono speaker)
- **Respetar `prefers-reduced-motion`** — si esta activo, no iniciar audio automaticamente
- **No depender del audio para transmitir informacion** — feedback visual siempre presente ademas del sonoro
- Guardar preferencia de audio en `localStorage` y respetarla entre visitas

```tsx
// Respetar preferencia de movimiento reducido
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (prefersReducedMotion) {
  // No iniciar audio generativo ni reactivo automaticamente
  // Solo permitir play manual via boton explicito
}
```

## Performance

- **Tone.js**: lazy load SIEMPRE (~150KB). No incluir en el bundle principal
- **Web Audio API nativa**: 0KB — ya esta en el browser. Preferir para sonidos simples (beeps, clicks)
- **Archivos de audio**: usar formatos comprimidos (MP3 ~128kbps para ambient, OGG como fallback)
- **Analyser buffer size**: 256 para waveform es suficiente para visualizacion. 2048+ solo para analisis de pitch
- **Throttle scroll handlers**: si el audio reacciona al scroll, throttle a 60fps con `requestAnimationFrame`
- **Dispose pattern**: todo Player, Synth, Effect creado DEBE ser disposed en el cleanup del useEffect
