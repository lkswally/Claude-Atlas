# Instalacion en Windows — Claude Desktop

Esta guia te lleva paso a paso desde cero hasta tener el sistema completo funcionando en Windows con Claude Desktop.

---

## Lo que vas a instalar

- **37 archivos de agentes** (25 agentes + 12 referencias tecnicas): los especialistas del sistema + documentacion tecnica que usan internamente
- **13 hooks reactivos**: interceptan operaciones en tiempo real para seguridad y calidad
- **CLAUDE.md global**: le dice a Claude como coordinar el pipeline de 5 fases
- **MCPs**: Engram (memoria persistente), Context7 (docs), Playwright (QA visual)
- **Node.js + npm**: para levantar previews locales
- **Git + GitHub CLI**: para guardar y publicar codigo
- **Vercel CLI**: para publicar en internet

Tiempo estimado: 20-30 minutos.

---

## Requisito previo: Claude Desktop

Antes de empezar, necesitas tener **Claude Desktop** instalado:

1. Ir a [claude.ai/download](https://claude.ai/download)
2. Descargar e instalar la version de Windows
3. Iniciar sesion con tu cuenta de Anthropic

> Sin Claude Desktop, nada de lo que sigue funciona. Este sistema le agrega capacidades a Claude — no lo reemplaza.

---

## Paso 1: Instalar Git para Windows (incluye Git Bash)

1. Ir a [git-scm.com/download/win](https://git-scm.com/download/win)
2. Descargar el instalador (64-bit)
3. Instalarlo con las opciones por defecto
4. Verificar: abri **Git Bash** y escribi `git --version`

> **Git Bash** es la terminal que vas a usar para todos los comandos de esta guia. Buscala en el menu Inicio como "Git Bash".

---

## Paso 2: Instalar Node.js

1. Ir a [nodejs.org](https://nodejs.org)
2. Descargar la version **LTS** (la recomendada)
3. Instalarlo con opciones por defecto
4. Verificar en Git Bash: `node --version` y `npm --version`

---

## Paso 3: Instalar GitHub CLI

1. Ir a [cli.github.com](https://cli.github.com)
2. Descargar el instalador para Windows
3. Instalarlo
4. En Git Bash, autenticarte:
   ```bash
   gh auth login
   ```
   - Elegir: **GitHub.com** -> **HTTPS** -> **Login with a web browser**

---

## Paso 4: Instalar Vercel CLI

En Git Bash:
```bash
npm install -g vercel
vercel login
```

---

## Paso 5: Configurar git

En Git Bash:
```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
git config --global init.defaultBranch main
```

---

## Paso 6: Descargar el sistema

En Git Bash, navega a tu Escritorio (o donde prefieras guardar el repo):
```bash
cd ~/Desktop
git clone https://github.com/Emaleo0522/claude-vibecoding.git
cd claude-vibecoding
```

> Esto descarga todos los archivos del sistema a una carpeta llamada `claude-vibecoding` en tu Escritorio.

---

## Paso 7: Copiar los 37 archivos de agentes (25 agentes + 12 referencias)

En Git Bash, **dentro de la carpeta `claude-vibecoding`**:
```bash
# Crear la carpeta de agentes
mkdir -p ~/.claude/agents/skills

# Copiar los 37 archivos
cp agents/*.md ~/.claude/agents/

# Copiar skills si hay
cp agents/skills/*.md ~/.claude/agents/skills/ 2>/dev/null

# Verificar — debe decir 37
ls ~/.claude/agents/*.md | wc -l
```

Los 25 agentes: orquestador, project-manager-senior, ux-architect, ui-designer, security-engineer, frontend-developer, backend-architect, rapid-prototyper, mobile-developer, game-designer, xr-immersive-developer, codepen-explorer, build-resolver, brand-agent, image-agent, logo-agent, video-agent, evidence-collector, reality-checker, seo-discovery, api-tester, performance-benchmarker, git, deployer, self-auditor.

Las 12 referencias: agent-protocol, better-auth-reference, better-gsap-reference, react-patterns-reference, redis-patterns-reference, pocketbase-reference, devops-vps-reference, nothing-design-reference, scroll-storytelling-reference, advanced-effects-reference, creative-coding-reference, reactive-audio-reference.

---

## Paso 7b: Copiar hooks reactivos

```bash
# Crear la carpeta de hooks
mkdir -p ~/.claude/hooks

# Copiar los 13 hooks
cp hooks/*.js ~/.claude/hooks/

# Verificar — debe decir 13
ls ~/.claude/hooks/*.js | wc -l
```

Los hooks interceptan operaciones en tiempo real: bloquean comandos peligrosos (git --no-verify, rm -rf), advierten sobre debugger/.only()/@ts-ignore, trackean costos, y gestionan contexto automaticamente.

---

## Paso 7c: Configurar settings.json y permisos

```bash
# Instalar settings.json (hooks + Engram MCP)
# El template usa __CLAUDE_HOME__ como placeholder — hay que reemplazarlo con tu ruta real
CLAUDE_HOME=$(cygpath -u "$USERPROFILE/.claude" 2>/dev/null || echo "$HOME/.claude")
sed "s|__CLAUDE_HOME__|$CLAUDE_HOME|g" templates/settings.json > ~/.claude/settings.json

# Instalar permisos para agentes
cp templates/settings.local.json ~/.claude/settings.local.json
```

> Esto configura los 10 hooks automaticos (los otros 3 son manuales) y los permisos para que los agentes puedan usar sus herramientas.

> **Si ya tenias una instalacion anterior**: los archivos existentes se sobreescriben. Si los habias personalizado, hace un backup antes: `cp ~/.claude/settings.json ~/.claude/settings.json.bak`

---

## Paso 8: Instalar CLAUDE.md global

```bash
cp templates/windows-claude.md ~/CLAUDE.md
```

> Este archivo contiene todas las instrucciones del sistema. Claude lo lee automaticamente cada vez que abris una conversacion. Incluye reglas de Windows (preview servers, puertos, etc.).

---

## Paso 9: Configurar MCPs para Claude Desktop

En Windows, los MCPs se configuran en un archivo especifico de Claude Desktop — **diferente** al de Linux.

### Paso 9a: Instalar Engram

Engram es la memoria persistente del sistema. Sin el, cada conversacion empieza de cero y no se puede retomar un proyecto donde se dejo.

1. Ir a [github.com/Gentleman-Programming/engram/releases](https://github.com/Gentleman-Programming/engram/releases)
2. Descargar `engram-windows-amd64.exe` (o el que corresponda a tu arquitectura)
3. Crear la carpeta y mover el ejecutable:
   ```bash
   mkdir -p ~/bin
   mv ~/Downloads/engram-windows-amd64.exe ~/bin/engram.exe
   ```

### Paso 9b: Configurar claude_desktop_config.json

Abri el archivo de configuracion de Claude Desktop:
```
%APPDATA%\Claude\claude_desktop_config.json
```

En Git Bash:
```bash
# Crear o editar el archivo
code "$APPDATA/Claude/claude_desktop_config.json"
# Si no tenes VS Code: notepad "$APPDATA/Claude/claude_desktop_config.json"
```

Pega este contenido (reemplaza `{TU_USUARIO}` con tu nombre de usuario de Windows):

```json
{
  "mcpServers": {
    "engram": {
      "command": "C:\\Users\\{TU_USUARIO}\\bin\\engram.exe",
      "args": ["mcp", "--tools=agent"]
    },
    "context7": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    "playwright": {
      "command": "C:\\Program Files\\nodejs\\npx.cmd",
      "args": ["playwright-mcp"]
    }
  }
}
```

> Template disponible en `templates/windows-mcp-config.json`

> **Nota sobre rutas**: Si Node.js esta en una ubicacion diferente, buscala con `where npx` en CMD.

### Paso 9c: Reiniciar Claude Desktop

Cerrar y volver a abrir Claude Desktop para que cargue los MCPs.

### MCPs opcionales (via Claude Desktop Extensions)

Dentro de Claude Desktop puedes instalar MCPs adicionales desde **Settings > Extensions**:
- **Vercel MCP** — gestionar deployments
- **Netlify MCP** — alternativa de deploy
- **Gmail / Google Calendar** — integraciones de productividad

---

## Paso 10: Configurar preview servers (launch.json)

Para que `preview_start` funcione correctamente en Windows:

```bash
mkdir -p ~/.claude
cp templates/windows-launch.json ~/.claude/launch.json
```

Edita `~/.claude/launch.json` y cambia `"mi-proyecto"` por el nombre de tu proyecto cuando lo necesites.

---

## Paso 11: Variables de entorno para assets creativos (opcional)

Si tu proyecto va a usar el pipeline creativo (logos, imagenes, videos generados con IA), necesitas configurar al menos una de estas API keys:

| Variable | Servicio | Costo | Como obtener |
|----------|----------|-------|-------------|
| `GEMINI_API_KEY` | Google AI Studio | ~$0.02-0.04/imagen (requiere billing) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `HF_TOKEN` | HuggingFace | Gratis | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `REPLICATE_API_TOKEN` | Replicate | ~$0.05/video | [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens) |

**Como configurarlas en Windows:**

Opcion A — Variables de entorno del sistema:
1. Buscar "Variables de entorno" en el menu Inicio
2. Click en "Variables de entorno..."
3. En "Variables de usuario", click "Nueva"
4. Nombre: `GEMINI_API_KEY`, Valor: tu key
5. Repetir para cada variable

Opcion B — Archivo `.env` en `~/.claude/`:
```bash
echo "GEMINI_API_KEY=tu-key-aqui" >> ~/.claude/.env
echo "HF_TOKEN=tu-token-aqui" >> ~/.claude/.env
```

> **Si no configuras estas variables**, el sistema funciona normalmente pero no podra generar logos, imagenes ni videos con IA. Podes agregarlas despues.

---

## Paso 12: Verificar la instalacion

En Git Bash:
```bash
# Agentes instalados (deben ser 37)
ls ~/.claude/agents/*.md | wc -l

# Hooks instalados (deben ser 13)
ls ~/.claude/hooks/*.js | wc -l

# CLAUDE.md global
head -5 ~/CLAUDE.md

# Herramientas disponibles
git --version
node --version
gh --version
vercel --version
```

**Verificacion completa (opcional pero recomendado):**
```bash
node ~/.claude/hooks/audit-system.js
```
Esto valida agentes, hooks, settings y protocolos. Resultado esperado: `HEALTHY (6/6)`.

En Claude Desktop: abri una nueva conversacion y escribi `modo orquestador — hola` — si responde describiendo el pipeline de 5 fases, todo funciona.

---

## Listo! Primer uso

El sistema tiene dos modos. Elegis explicitamente cual usar:

**Modo normal** (preguntas, fixes, chat tecnico) — simplemente habla con Claude.

**Modo orquestador** (proyecto completo con pipeline de 5 fases):

```
modo orquestador — quiero crear [tu idea, ej: una app de lista de tareas]
```

Otras frases que tambien activan el pipeline:
```
activa el pipeline — [tu idea]
nuevo proyecto completo: [tu idea]
```

El sistema se encarga del resto:
1. Planifica las tareas (project-manager-senior)
2. Crea la arquitectura (ux-architect + ui-designer + security-engineer)
3. Implementa con QA visual (dev-agents + evidence-collector)
4. Certifica (seo-discovery + api-tester + performance-benchmarker + reality-checker)
5. Publica (git + deployer) — con tu confirmacion

---

## Problemas frecuentes

**Claude no reconoce los agentes**
-> Reinicia Claude Desktop. Los agentes se cargan al iniciar.

**No aparecen los 37 archivos de agentes**
-> Verifica con `ls ~/.claude/agents/*.md | wc -l`. Debe dar **37** (25 agentes + 12 referencias).

**MCPs no aparecen en Claude Desktop**
-> Verifica que `claude_desktop_config.json` tenga JSON valido y reinicia. Verificar rutas absolutas.

**`gh auth login` falla**
-> Proba con: `gh auth login --web`

**`vercel login` no abre el navegador**
-> Proba: `vercel login --github`

**`preview_start` falla con ENOENT**
-> Verificar que `launch.json` usa `"runtimeExecutable": "cmd"` con `"runtimeArgs": ["/c", "cd proyecto && npm run dev"]`

**GitHub pide seleccionar cuenta en un popup cada vez**
-> Ejecutar en Git Bash: `git config --global credential.guiPrompt false`

---

## Estructura instalada

```
~/CLAUDE.md                                      <- instrucciones globales del sistema
~/.claude/
|-- launch.json                                  <- configuracion de preview servers
|-- agents/                                      <- 25 agentes + 12 referencias = 37 archivos
|   |-- orquestador.md                           <- coordinador central
|   |-- project-manager-senior.md                <- Fase 1: spec a tareas
|   |-- ux-architect.md                          <- Fase 2: CSS tokens, layout
|   |-- ui-designer.md                           <- Fase 2: design system visual
|   |-- security-engineer.md                     <- Fase 2: STRIDE, OWASP
|   |-- frontend-developer.md                    <- Fase 3: React/Vue/TS
|   |-- backend-architect.md                     <- Fase 3: Hono/Express
|   |-- rapid-prototyper.md                      <- Fase 3: MVPs multi-stack
|   |-- mobile-developer.md                      <- Fase 3: React Native + Expo
|   |-- game-designer.md                         <- Fase 3: GDD, mecanicas
|   |-- xr-immersive-developer.md                <- Fase 3: Phaser.js, WebGL
|   |-- codepen-explorer.md                      <- Fase 3: busca/extrae efectos CodePen
|   |-- build-resolver.md                        <- Fase 3: resuelve errores de build
|   |-- brand-agent.md                           <- Fase 2B: brand.json
|   |-- image-agent.md                           <- Fase 2B: hero images
|   |-- logo-agent.md                            <- Fase 2B: logo SVG
|   |-- video-agent.md                           <- Fase 2B: video loop
|   |-- evidence-collector.md                    <- Fase 3 QA: Playwright, screenshots
|   |-- reality-checker.md                       <- Fase 4: gate final
|   |-- seo-discovery.md                         <- Fase 4: SEO + AI discovery
|   |-- api-tester.md                            <- Fase 4: endpoints, OWASP API
|   |-- performance-benchmarker.md               <- Fase 4: Core Web Vitals
|   |-- git.md                                   <- Fase 5: commit + push
|   |-- deployer.md                              <- Fase 5: Vercel CLI
|   |-- self-auditor.md                          <- auditor del sistema
|   |-- agent-protocol.md                        <- ref: protocolo compartido
|   |-- better-auth-reference.md                 <- ref: Better Auth 1.5
|   |-- better-gsap-reference.md                 <- ref: GSAP Tier 3
|   |-- react-patterns-reference.md              <- ref: React 19, Next.js 15/16
|   |-- redis-patterns-reference.md              <- ref: Redis patterns
|   |-- pocketbase-reference.md                  <- ref: PocketBase gotchas
|   |-- devops-vps-reference.md                  <- ref: VPS, nginx, HTTPS
|   |-- nothing-design-reference.md              <- ref: Nothing Design System
|   |-- scroll-storytelling-reference.md         <- ref: Lenis, scroll pinning
|   |-- advanced-effects-reference.md            <- ref: Lottie, Rive, cursor effects
|   |-- creative-coding-reference.md             <- ref: p5.js, GLSL, generative art
|   |-- reactive-audio-reference.md              <- ref: Tone.js, Web Audio
|-- hooks/
|   |-- block-no-verify.js                       <- bloquea git --no-verify, rm -rf
|   |-- config-protection.js                     <- protege .env, secrets
|   |-- quality-gate.js                          <- advierte debugger, .only()
|   |-- console-log-warning.js                   <- advierte console.log en produccion
|   |-- suggest-compact.js                       <- sugiere /compact cada ~50 calls
|   |-- cost-tracker.js                          <- registra uso de herramientas
|   |-- cost-report.js                           <- reporte de costos (manual)
|   |-- pre-compact-engram.js                    <- snapshot antes de compactar
|   |-- session-summary.js                       <- log de sesion
|   |-- session-start-context.js                 <- carga contexto al inicio
|   |-- engram-sync.js                           <- sync memorias a GitHub
|   |-- audit-system.js                          <- auditor del sistema (manual)
|   |-- learning-index.js                        <- indice de descubrimientos (manual)
%APPDATA%\Claude\
|-- claude_desktop_config.json                   <- MCPs (Engram, Context7, Playwright)
~/bin/
|-- engram.exe                                   <- binario de Engram MCP
```

---

## Paso Opcional: Sistema Visual de Agentes (Pixel Art)

Una oficina en pixel art donde los 25 agentes se mueven en tiempo real. Cuando uno recibe una tarea, camina a su escritorio y se pone a trabajar. Cuando termina, camina a reportarle al orquestador con una burbuja de chat, y vuelve a deambular.

> **100% opcional.** El sistema de vibecoding funciona perfectamente sin esto.

**Lo que necesita el sistema visual:**
- Node.js (ya instalado en Paso 2)
- Assets de sprites/tiles/furniture del repo [pixel-agents](https://github.com/pablodelucca/pixel-agents)
- Un servidor local en `http://localhost:3456` (se instala automaticamente)

**Como instalar:** En Claude Desktop, en una nueva conversacion, pega este mensaje:

```
Instala el sistema visual de pixel art para Claude Desktop.
Crea un servidor standalone Node.js+Express en ~/.claude/pixel-bridge/standalone/
que lea ~/.claude/projects/*.jsonl en tiempo real y sirva la UI en http://localhost:3456.
Los 25 agentes del sistema de vibecoding deben estar siempre presentes
en la oficina aunque esten inactivos.
Baja los assets (sprites, tiles, furniture, fonts) de la carpeta assets/
de https://github.com/pablodelucca/pixel-agents
```

Claude va a:
1. Crear el servidor Node.js+TypeScript con WebSocket
2. Crear la UI React+Canvas con los personajes pixel art
3. Descargar los assets (sprites, tiles, fuentes) del repo original
4. Compilar todo y dejarlo listo

Una vez instalado, para ver la oficina: abri `http://localhost:3456` en el navegador.
Para que arranque automaticamente, Claude puede configurar un entry en `~/.claude/launch.json`.

**Troubleshooting:**

**El servidor no arranca**
-> Verifica que Node.js este instalado: `node --version`
-> Desde Git Bash: `cd ~/.claude/pixel-bridge/standalone && node dist/server/index.js`

**No se ven los sprites / pantalla en negro**
-> Los assets no se descargaron correctamente. Decile a Claude: `"Volve a descargar los assets de pixel-bridge desde https://github.com/pablodelucca/pixel-agents"`

**Que es el proyecto original?**
-> [pixel-agents](https://github.com/pablodelucca/pixel-agents) de [@pablodelucca](https://github.com/pablodelucca), disenado como extension de VS Code. Esta version es una adaptacion standalone que funciona en el navegador sin VS Code.
