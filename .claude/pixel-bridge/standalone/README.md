# Pixel Bridge — Standalone Office Viewer

Visualización en tiempo real de los 22 agentes del sistema claude-vibecoding como personajes en una oficina pixel art.

Un servidor Node.js + React lee los archivos JSONL de `~/.claude/projects/` y proyecta la actividad de cada agente como animaciones en el navegador (`http://localhost:3456`).

> Adaptación standalone de [pixel-agents](https://github.com/pablodelucca/pixel-agents) de [@pablodelucca](https://github.com/pablodelucca), diseñado originalmente como extensión de VS Code. Esta versión funciona en cualquier navegador, sin VS Code.

---

## Assets requeridos (descargar de pixel-agents)

Los sprites, tiles de suelo, paredes y muebles **no están incluidos** en este repo por tamaño. Necesitás descargarlos del repo original:

```bash
# Clonar pixel-agents solo para copiar sus assets
git clone --depth=1 https://github.com/pablodelucca/pixel-agents /tmp/pixel-agents-src

# Copiar assets al standalone
cp -r /tmp/pixel-agents-src/assets/sprites ~/.claude/pixel-bridge/standalone/webview-ui/public/assets/sprites
cp -r /tmp/pixel-agents-src/assets/fonts   ~/.claude/pixel-bridge/standalone/webview-ui/public/assets/fonts

# Limpiar
rm -rf /tmp/pixel-agents-src
```

**Estructura esperada de assets:**
```
webview-ui/public/assets/
├── sprites/
│   ├── characters/    ← sprites de personajes (ya incluidos: char_0.png … char_5.png)
│   ├── tiles/         ← floor tiles, wall tiles (descargar de pixel-agents)
│   └── furniture/     ← escritorios, sillas, plantas, etc. (descargar de pixel-agents)
└── fonts/
    └── FSPixelSansUnicode-Regular.ttf  (descargar de pixel-agents)
```

---

## Instalación

### Requisitos
- Node.js 18+

### Pasos

```bash
# 1. Copiar a ~/.claude/pixel-bridge/
cp -r pixel-bridge ~/.claude/pixel-bridge

# 2. Instalar dependencias del servidor
cd ~/.claude/pixel-bridge/standalone
npm install

# 3. Instalar dependencias del frontend
cd webview-ui
npm install

# 4. Compilar el frontend
npm run build
cd ..

# 5. Compilar el servidor
npm run build

# 6. Descargar assets (ver sección Assets arriba)

# 7. Iniciar el servidor
node dist/server/index.js
```

Abrí `http://localhost:3456` en el navegador.

### Auto-inicio con launch.json (Claude Desktop / Windows)

Agregá esta entrada a `~/.claude/launch.json`:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "pixel-bridge-viewer",
      "runtimeExecutable": "cmd",
      "runtimeArgs": ["/c", "cd /d %USERPROFILE%\\.claude\\pixel-bridge\\standalone && node dist\\server\\index.js"],
      "port": 3456
    }
  ]
}
```

---

## Qué hace

- Lee `~/.claude/projects/*/sessions/*.jsonl` en tiempo real
- Detecta cuando un agente inicia/termina una sesión
- Los **22 agentes del sistema siempre están en la oficina**, incluso inactivos
- Cuando un agente trabaja: camina a su escritorio, se sienta y muestra aura verde
- Cuando termina: camina al orquestador a reportar con burbuja de chat, luego vuelve a deambular
- Los agentes inactivos deambulan, descansan en sillas y charlan entre sí

## Puerto

Por defecto: `3456`. Cambiar con variable de entorno:

```bash
PORT=4000 node dist/server/index.js
```
