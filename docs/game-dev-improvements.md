# Mejoras para Game Development — Compilado de 13 Repos

> Documento de referencia. NO aplicar hasta aprobacion del usuario.
> Fuentes: PixiJS, libGDX, Cocos2d-x, Magic Tools, Luanti, Cocos Engine, Awesome YouTubers, GameFramework, GameDevMind, Hilo, Defold, GameDev Resources, Awesome GBDev.

---

## Estado actual de nuestros agentes de juegos

### game-designer (GDD)
- Design pillars, core loops (3 niveles), mecanicas documentadas, economia/balance, onboarding
- Variables de tuning como PLACEHOLDER hasta playtest
- GDD es contrato: si no esta, no se implementa

### xr-immersive-developer (implementacion)
- 2D: Phaser.js 3, PixiJS, Canvas API
- 3D: Three.js, Babylon.js, WebGL
- Audio: Web Audio API, Howler.js
- Input: keyboard, mouse, touch, gamepad
- Sistemas: game loop, rendering, fisica, input, audio, UI, state machine, tilemap, animacion
- WebGL: deteccion previa, fallback UI, context lost handler
- 60 FPS target desktop, 30 FPS mobile

---

## MEJORAS IDENTIFICADAS (priorizadas por impacto)

### PRIORIDAD ALTA — Arquitectura core

#### 1. Sistema de subsistemas modulares (de GameFramework)
**Que falta**: El GDD no especifica que subsistemas necesita el juego. GameFramework define 19 subsistemas tipo checklist.

**Subsistemas aplicables a juegos web**:
| Subsistema | Descripcion | Cuando aplica |
|------------|-------------|---------------|
| Config | Settings de solo lectura (dificultad, constantes) | Siempre |
| Data Table | Datos tabulares (items, enemigos, niveles) | RPG, strategy |
| Entity | Ciclo de vida de objetos (spawn/despawn/init/update/delete) | Siempre |
| Event | Pub-sub para desacoplar modulos | Siempre |
| FSM | Maquina de estados (menu/playing/paused/gameover) | Siempre |
| Object Pool | Reciclaje de objetos frecuentes (balas, particulas) | Siempre en web (evita GC pauses) |
| Resource | Carga asincrona de assets con progreso | Juegos > 5MB |
| Scene | Gestion multi-escena con transiciones | Siempre |
| Sound | Audio 2D/3D por categoria (musica, SFX, UI) | Siempre |
| Localization | Multi-idioma (texto + assets por region) | Si es multi-region |
| Network | Comunicacion cliente-servidor | Multijugador |
| Procedure | FSM del ciclo de vida completo del juego | Juegos complejos |
| UI | Framework de UI desacoplado del engine | Siempre |
| Debugger | Visualizacion de estado en runtime | Dev mode |

**Donde aplicar**: game-designer debe incluir checklist de subsistemas en el GDD.

#### 2. Arquitectura de mensajes entre game objects (de Defold)
**Que falta**: xr-immersive-developer no documenta patron de comunicacion entre objetos.

**Patron**:
```
enemy -> [hit message] -> player
player -> [damage message] -> healthbar
healthbar -> [death message] -> game-manager
```

**Beneficios**: Desacoplamiento, testabilidad, modularidad. Cada objeto solo conoce los mensajes que envia/recibe, no las implementaciones.

**Donde aplicar**: xr-immersive-developer como patron de arquitectura obligatorio.

#### 3. Scene graph jerarquico (de Cocos2d-x + Hilo)
**Que falta**: No hay especificacion de estructura de escenas.

**Patron**:
```
Root Scene
  ├── Background Layer (parallax)
  ├── Game Layer
  │   ├── Tilemap
  │   ├── Enemies (entity pool)
  │   └── Player
  ├── HUD Layer
  └── Pause Overlay
```

Cada escena tiene lifecycle: `create → enter → update → exit → dispose`.
Parent-child: transforms se heredan (posicion, escala, rotacion).

**Donde aplicar**: game-designer define estructura de escenas en GDD. xr-immersive-developer implementa.

#### 4. Separacion timestep fijo vs variable (de Cocos2d-x + awesome-gbdev)
**Que falta**: Solo decimos "60 FPS target" pero no separamos update loops.

**Patron**:
- **Fixed timestep** (16.67ms): fisica, colisiones, logica de juego
- **Variable timestep** (requestAnimationFrame): rendering, animaciones visuales
- **Interpolacion**: render interpola entre estados fisicos para suavidad visual

**Donde aplicar**: xr-immersive-developer como regla obligatoria.

---

### PRIORIDAD MEDIA — Pipeline de assets

#### 5. Pipeline de audio para juegos (GAP: no existe agente de audio)
**Que falta**: No tenemos ningun flujo para audio de juegos. image-agent genera imagenes, logo-agent genera logos, pero audio = nada.

**Herramientas recomendadas**:
| Herramienta | Tipo | Costo | Uso |
|-------------|------|-------|-----|
| Bfxr / jfxr | SFX generator (retro/chiptune) | Gratis | Prototipos rapidos |
| ChipTone | SFX generator (online) | Gratis | SFX web-based |
| Bosca Ceoil | Musica retro | Gratis | Chiptune BGM |
| LMMS | DAW completo | Gratis | Musica compleja |
| Freesound | Libreria de sonidos CC | Gratis | SFX realistas |
| Howler.js | Audio engine web | Gratis | Playback en browser |

**Especificacion de audio en GDD**:
- Formato: .ogg (Chrome/Firefox) + .mp3 (Safari fallback)
- Sample rate: 44.1kHz stereo (musica), 22kHz mono (SFX)
- Budget: < 2MB total musica, < 500KB total SFX
- Categorias: BGM, SFX, UI sounds, ambient
- Volumen: controlable por categoria

**Decision**: No crear agente nuevo. Extender xr-immersive-developer con seccion de audio. game-designer documenta requisitos de audio en GDD.

#### 6. Level design con herramientas estandar (de Magic Tools + GameDev Resources)
**Que falta**: El GDD no referencia herramientas de level design.

**Herramientas**:
| Herramienta | Tipo | Formato | Soporte Phaser |
|-------------|------|---------|----------------|
| Tiled | Tilemap editor (industria standard) | JSON/TMX | Nativo |
| LDtk | Level designer moderno | JSON | Plugin |
| OGMO Editor | Level editor FOSS | JSON | Manual |

**Donde aplicar**: game-designer especifica herramienta de level design en GDD si el juego tiene mapas/niveles. xr-immersive-developer implementa parser.

#### 7. Sprite sheets y texture atlas (de Defold + Magic Tools)
**Que falta**: image-agent genera hero images pero NO sprite sheets para juegos.

**Herramientas de creacion**:
- Aseprite (paid, industria standard) / LibreSprite (FOSS)
- Piskel (online, gratis)
- Pixel Composer (FOSS)

**Pipeline de atlas**:
1. Artista crea sprites individuales o en Aseprite
2. TexturePacker o Shoebox genera atlas + JSON descriptor
3. xr-immersive-developer carga atlas con Phaser `this.load.atlas()`

**Donde aplicar**: game-designer menciona asset pipeline en GDD. xr-immersive-developer carga atlas.

#### 8. Abstraccion de input unificada (de libGDX + Hilo)
**Que falta**: xr-immersive-developer lista inputs pero no documenta capa de abstraccion.

**Patron**:
```typescript
// Input abstraction layer
interface GameInput {
  move: { x: number, y: number }  // normalized -1 to 1
  action: boolean                   // primary action
  cancel: boolean                   // secondary/cancel
  pause: boolean                    // menu/pause
}

// Adapters
KeyboardAdapter  → GameInput
TouchAdapter     → GameInput (virtual joystick + tap zones)
GamepadAdapter   → GameInput (analog sticks + buttons)
PointerAdapter   → GameInput (mouse click + drag)
```

Un solo sistema de input, multiples adaptadores. El juego solo lee `GameInput`.

**Donde aplicar**: xr-immersive-developer como patron de arquitectura.

---

### PRIORIDAD MEDIA-BAJA — Optimizacion y rendering

#### 9. Dual renderer WebGL + WebGPU (de PixiJS + Cocos Engine)
**Que falta**: Solo documentamos WebGL con fallback a Canvas. WebGPU es el futuro.

**Estrategia de fallback**:
```
WebGPU (si disponible, mejor performance)
  ↓ fallback
WebGL 2.0 (standard moderno)
  ↓ fallback
WebGL 1.0 (legacy)
  ↓ fallback
Canvas 2D (ultimo recurso)
  ↓ fallback
Mensaje "Tu navegador no soporta este juego"
```

**Donde aplicar**: xr-immersive-developer documenta cadena de fallback. No implementar WebGPU hoy, pero preparar la arquitectura.

#### 10. Optimizaciones de tile y paleta (de awesome-gbdev)
**Que falta**: Tecnicas de optimizacion de memoria para mobile web.

**Tecnicas aplicables**:
- **Tile-based rendering**: Dividir visuals en tiles 16x16 reutilizables. Reduce atlas 3-5x.
- **Palette cycling**: Sprites en escala de grises, colorizar con shader/CSS filter en runtime. Reduce atlas 4-8x.
- **Dirty rectangle rendering**: Solo redibujar areas que cambiaron. Reduce draw calls.
- **Asset streaming por nivel**: Cargar assets por chunks (nivel/mundo), no todo al inicio. Critico para mobile.
- **Indexed PNG**: Exportar sprites con paleta de 4-8 colores, no RGBA. 4-8x mas chico.
- **Animacion por tilemap reference**: Definir animaciones como secuencias de tile IDs `[A, B, A, C]`, no imagenes separadas.

**Donde aplicar**: xr-immersive-developer como checklist de optimizacion para mobile.

#### 11. Object pooling obligatorio (de GameFramework + Cocos2d-x)
**Que falta**: Mencionamos object pooling pero no es obligatorio.

**Patron**: Pre-instanciar N objetos, reciclar en vez de crear/destruir. Evita GC pauses que causan frame drops en browsers.

**Aplicar a**: balas, particulas, enemigos spawneados, efectos visuales, sonidos SFX.

**Donde aplicar**: xr-immersive-developer como regla no negociable para todo objeto frecuente.

---

### PRIORIDAD BAJA — Herramientas y recursos

#### 12. Catalogo de herramientas por etapa (de Magic Tools + GameDev Resources)
**Que falta**: No tenemos referencia de herramientas recomendadas por categoria.

**Catalogo para juegos web**:

| Categoria | Herramienta | Tipo | Nota |
|-----------|-------------|------|------|
| **2D Engine** | Phaser.js 3 | Framework | Principal |
| **2D Renderer** | PixiJS | Renderer | Cuando Phaser es demasiado |
| **3D Engine** | Three.js | Library | Principal 3D |
| **3D Engine** | Babylon.js | Framework | Alternativa con mas features |
| **Physics 2D** | Matter.js | Library | Integrado con Phaser |
| **Physics 3D** | Cannon-es | Library | Para Three.js |
| **Audio** | Howler.js | Library | Cross-browser audio |
| **Audio** | Tone.js | Library | Sintesis de audio |
| **Sprites** | Aseprite | Editor | Industria standard (paid) |
| **Sprites** | LibreSprite | Editor | FOSS alternativa |
| **Sprites** | Piskel | Editor | Online, gratis |
| **Level Design** | Tiled | Editor | Industria standard |
| **Level Design** | LDtk | Editor | Moderno, pixel art |
| **3D Models** | Blender | Editor | FOSS, completo |
| **3D Assets** | Sketchfab | Libreria | CC-licensed models |
| **3D Assets** | Poly Pizza | Libreria | 6000+ low-poly gratis |
| **Texturas** | TextureHaven | Libreria | PBR gratis |
| **SFX** | Bfxr / jfxr | Generator | Retro SFX |
| **SFX** | ChipTone | Generator | Online |
| **Musica** | Bosca Ceoil | Composer | Retro/chiptune |
| **Musica** | LMMS | DAW | FOSS completo |
| **Sonidos** | Freesound | Libreria | CC-licensed |
| **Game Assets** | OpenGameArt | Libreria | FOSS sprites/tiles |
| **Atlas** | TexturePacker | Empaquetador | Atlas + JSON |
| **Animacion** | DragonBones | Skeleton anim | 2D esqueletica |
| **Narrativa** | Twine | Editor | Juegos narrativos |

#### 13. Scaffolding de proyecto de juego
**Que falta**: No tenemos template para iniciar un proyecto de juego. Hilo usa Yeoman generator.

**Propuesta**: El orquestador, al detectar proyecto tipo juego en Fase 1, estructura:
```
game-project/
  src/
    game/          ← game loop, scenes, entities
    systems/       ← fisica, input, audio, rendering
    assets/        ← sprites, audio, tilemaps
    config/        ← constantes de tuning del GDD
    ui/            ← HUD, menus, overlays
  public/
    assets/        ← assets compilados
  package.json     ← Vite + Phaser/PixiJS/Three.js
```

#### 14. Licenciamiento de assets (de Magic Tools)
**Que falta**: No documentamos requisitos de licencia para assets de juegos.

**Regla**: Todo asset externo debe ser CC0, CC-BY, o compatible con la licencia del proyecto. game-designer especifica en GDD. xr-immersive-developer valida al integrar.

---

## RESUMEN: Que agregar y donde

| # | Mejora | Agente destino | Prioridad |
|---|--------|---------------|-----------|
| 1 | Checklist de subsistemas modulares | game-designer | ALTA |
| 2 | Message-based event architecture | xr-immersive-developer | ALTA |
| 3 | Scene graph jerarquico con lifecycle | game-designer + xr-immersive | ALTA |
| 4 | Fixed vs variable timestep | xr-immersive-developer | ALTA |
| 5 | Pipeline de audio (especificacion + herramientas) | game-designer + xr-immersive | MEDIA |
| 6 | Level design con Tiled/LDtk | game-designer | MEDIA |
| 7 | Sprite sheet pipeline (Aseprite → atlas → engine) | xr-immersive-developer | MEDIA |
| 8 | Input abstraction layer | xr-immersive-developer | MEDIA |
| 9 | Cadena de fallback WebGL→WebGPU preparada | xr-immersive-developer | MEDIA-BAJA |
| 10 | Optimizaciones tile/paleta para mobile | xr-immersive-developer | MEDIA-BAJA |
| 11 | Object pooling obligatorio | xr-immersive-developer | MEDIA-BAJA |
| 12 | Catalogo de herramientas por categoria | CLAUDE.md o referencia | BAJA |
| 13 | Scaffolding de proyecto de juego | orquestador | BAJA |
| 14 | Licenciamiento de assets | game-designer | BAJA |

---

## Repos analizados y su aporte

| Repo | Aporte principal |
|------|-----------------|
| **PixiJS** | Dual renderer WebGL/WebGPU, asset loader streaming |
| **libGDX** | Input abstraction, cross-platform architecture, no-prescriptive patterns |
| **Cocos2d-x** | Scene graph, action system, scheduler (fixed timestep), memory mgmt |
| **Magic Tools** | Catalogo completo de herramientas: sprites, audio, level design, physics |
| **Luanti** | Namespace isolation, mod load order, metadata separation |
| **Cocos Engine** | TypeScript game engine architecture, rendering pipeline abstraction |
| **Awesome YouTubers** | Recursos de aprendizaje (The Coding Train, Chris Courses) |
| **GameFramework** | 19 subsistemas modulares, event-driven architecture, object pooling, async resources |
| **GameDevMind** | 6 knowledge domains, critical problem-solving checklist |
| **Hilo** | 3-tier renderer (Canvas/WebGL/DOM), camera system, visual object hierarchy |
| **Defold** | Message-based game objects, hot reload, sprite atlasing pipeline |
| **GameDev Resources** | Ecosystem mapping de herramientas web (Phaser, PixiJS, Three.js positioning) |
| **awesome-gbdev** | Tile optimization, palette cycling, dirty rect rendering, asset streaming, indexed PNG |
