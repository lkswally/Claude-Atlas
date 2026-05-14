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

# Copiar assets al pixel-bridge
cp -r /tmp/pixel-agents-src/assets/sprites ~/.claude/pixel-bridge/webview-ui/public/assets/sprites
cp -r /tmp/pixel-agents-src/assets/fonts   ~/.claude/pixel-bridge/webview-ui/public/assets/fonts

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

## Instalación (Claude Code — Linux)

### Requisitos
- Node.js 18+

### Pasos

```bash
# 1. Copiar a ~/.claude/pixel-bridge/
cp -r pixel-bridge ~/.claude/pixel-bridge

# 2. Instalar dependencias del servidor
cd ~/.claude/pixel-bridge
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
npm start
```

Abrí `http://localhost:3456` en el navegador.

### Auto-inicio con hook (Claude Code — Linux)

Claude Code soporta hooks que se ejecutan al inicio de sesión. Agregá esto a `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/pixel-bridge/start.sh"
          }
        ]
      }
    ]
  }
}
```

El script `start.sh` se instala automáticamente con pixel-bridge. Si necesitás crearlo manualmente:

```bash
cat > ~/.claude/pixel-bridge/start.sh << 'EOF'
#!/bin/bash
# Pixel Bridge — auto-start on Claude Code session
PIXEL_DIR="$HOME/.claude/pixel-bridge"
PIDFILE="$PIXEL_DIR/.pixel-bridge.pid"
LOG="$PIXEL_DIR/pixel-bridge.log"

# Check if already running
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  exit 0
fi

# Start in background
cd "$PIXEL_DIR" || exit 1
nohup node dist/server.js > "$LOG" 2>&1 &
echo $! > "$PIDFILE"
EOF
chmod +x ~/.claude/pixel-bridge/start.sh
```

---

## Cómo funciona con Claude Code

A diferencia de Claude Desktop (VS Code), Claude Code almacena sesiones así:

```
~/.claude/projects/{project-dir}/
├── {session-uuid}.jsonl              ← sesión principal (→ orquestador)
└── {session-uuid}/
    └── subagents/
        └── agent-{hex-id}.jsonl      ← subagentes spawneados
```

**Mapeo de agentes:**
1. La sesión principal se asigna al **orquestador** (el coordinador)
2. Cuando el orquestador llama a `Agent` con `subagent_type`, se registra el mapeo
3. Los `progress` messages revelan el `agentId` que corresponde a cada `subagent_type`
4. Cuando aparece `agent-{id}.jsonl`, se activa el personaje permanente correcto

Los **22 agentes siempre están en la oficina**, incluso inactivos:
- Cuando un agente trabaja: camina a su escritorio, se sienta y muestra aura verde
- Cuando termina: camina al orquestador a reportar con burbuja de chat, luego vuelve a deambular
- Los agentes inactivos deambulan, descansan en sillas y charlan entre sí

---

## Puerto

Por defecto: `3456`. Cambiar con variable de entorno:

```bash
PORT=4000 npm start
```
