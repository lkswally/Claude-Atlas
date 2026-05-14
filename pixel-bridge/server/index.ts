import express from "express";
import { createServer } from "http";
import { WebSocketServer, WebSocket } from "ws";
import { join, dirname } from "path";
import { homedir } from "os";
import { fileURLToPath } from "url";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { JsonlWatcher, type WatchedFile } from "./watcher.js";
import { processTranscriptLine } from "./parser.js";
import {
  loadCharacterSprites,
  loadWallTiles,
  loadFloorTiles,
  loadFurnitureAssets,
  loadDefaultLayout,
} from "./assetLoader.js";
import type { TrackedAgent, ServerMessage } from "./types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = parseInt(process.env.PORT || "3456", 10);
const IDLE_SHUTDOWN_MS = 600_000; // 10 minutes

// ── Permanent agents — always present in the office ─────────────────────────
// These characters always wander; they activate when a real JSONL session
// is detected for their name, and go back to wandering when it ends.
const PERMANENT_AGENTS: Array<{ name: string; id: number }> = [
  { name: "orquestador",             id: 1001 },
  { name: "project_manager_senior",  id: 1002 },
  { name: "ux_architect",            id: 1003 },
  { name: "ui_designer",             id: 1004 },
  { name: "security_engineer",       id: 1005 },
  { name: "frontend_developer",      id: 1006 },
  { name: "backend_architect",       id: 1007 },
  { name: "rapid_prototyper",        id: 1008 },
  { name: "mobile_developer",        id: 1009 },
  { name: "game_designer",           id: 1010 },
  { name: "xr_immersive_developer",  id: 1011 },
  { name: "codepen_explorer",        id: 1012 },
  { name: "build_resolver",          id: 1013 },
  { name: "evidence_collector",      id: 1014 },
  { name: "reality_checker",         id: 1015 },
  { name: "seo_discovery",           id: 1016 },
  { name: "api_tester",              id: 1017 },
  { name: "performance_benchmarker", id: 1018 },
  { name: "brand_agent",             id: 1019 },
  { name: "image_agent",             id: 1020 },
  { name: "logo_agent",              id: 1021 },
  { name: "video_agent",             id: 1022 },
  { name: "git",                     id: 1023 },
  { name: "deployer",                id: 1024 },
  { name: "self_auditor",            id: 1025 },
]

// Normalize agent name for matching: hyphens and underscores are equivalent
function normalizeName(name: string): string {
  return name.toLowerCase().replace(/-/g, "_")
}

// Project directory names that are infrastructure — skip them
const BLOCKED_PROJECT_NAMES = new Set(["subagents", "agents", "tasks", "temp", "tmp", "cache"])

function makePermanentAgent(pa: { name: string; id: number }): TrackedAgent {
  return {
    id: pa.id,
    sessionId: `permanent-${pa.name}`,
    projectDir: "",
    projectName: pa.name,
    jsonlFile: "",
    fileOffset: 0,
    lineBuffer: "",
    activity: "idle",
    activeTools: new Map(),
    activeToolNames: new Map(),
    activeSubagentToolIds: new Map(),
    activeSubagentToolNames: new Map(),
    isWaiting: false,
    permissionSent: false,
    hadToolsInTurn: false,
    lastActivityTime: 0,
  }
}

// State
const agents = new Map<string, TrackedAgent>() // sessionId -> agent
const permanentAgentByName = new Map<string, TrackedAgent>() // normalized name -> agent

// Initialize all permanent agents before the watcher starts
for (const pa of PERMANENT_AGENTS) {
  const agent = makePermanentAgent(pa)
  agents.set(`permanent-${pa.name}`, agent)
  permanentAgentByName.set(normalizeName(pa.name), agent)
}

// Temporary agents (real sessions not matching a permanent agent) use IDs 1–999
let nextAgentId = 1
const clients = new Set<WebSocket>()
let lastActivityTime = Date.now()

// Load assets at startup
const devAssetsRoot = join(__dirname, "..", "webview-ui", "public", "assets")
const prodAssetsRoot = join(__dirname, "public", "assets")
const assetsRoot = existsSync(devAssetsRoot) ? devAssetsRoot : prodAssetsRoot

console.log(`[Server] Loading assets from: ${assetsRoot}`)

const characterSprites = loadCharacterSprites(assetsRoot)
const wallTiles = loadWallTiles(assetsRoot)
const floorTiles = loadFloorTiles(assetsRoot)
const furnitureAssets = loadFurnitureAssets(assetsRoot)

// Persistence directory
const persistDir = join(homedir(), ".pixel-agents")
const persistedLayoutPath = join(persistDir, "layout.json")
const persistedSeatsPath = join(persistDir, "agent-seats.json")

function loadLayout(): Record<string, unknown> | null {
  if (existsSync(persistedLayoutPath)) {
    try {
      const content = readFileSync(persistedLayoutPath, "utf-8")
      const layout = JSON.parse(content) as Record<string, unknown>
      console.log(`[Server] Loaded persisted layout from ${persistedLayoutPath}`)
      return layout
    } catch (err) {
      console.warn(`[Server] Failed to load persisted layout: ${err instanceof Error ? err.message : err}`)
    }
  }
  return loadDefaultLayout(assetsRoot)
}

function loadPersistedSeats(): Record<number, { palette: number; hueShift: number; seatId: string | null }> | null {
  if (existsSync(persistedSeatsPath)) {
    try {
      const content = readFileSync(persistedSeatsPath, "utf-8")
      return JSON.parse(content)
    } catch {
      return null
    }
  }
  return null
}

let currentLayout = loadLayout()
const persistedSeats = loadPersistedSeats()

// Express + WebSocket
const app = express()
app.use(express.static(join(__dirname, "public")))
const server = createServer(app)
const wss = new WebSocketServer({ server })

// Ping/pong heartbeat — keeps clients Set accurate for shutdown guard
setInterval(() => {
  for (const ws of clients) {
    if ((ws as unknown as Record<string, boolean>).__isAlive === false) {
      clients.delete(ws)
      ws.terminate()
      continue
    }
    (ws as unknown as Record<string, boolean>).__isAlive = false
    ws.ping()
  }
}, 30_000)

function broadcast(msg: ServerMessage): void {
  const data = JSON.stringify(msg)
  for (const client of clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(data)
    }
  }
}

function sendInitialData(ws: WebSocket): void {
  ws.send(JSON.stringify({ type: "settingsLoaded", soundEnabled: false }))

  if (characterSprites) {
    ws.send(JSON.stringify({ type: "characterSpritesLoaded", characters: characterSprites.characters }))
  }
  if (wallTiles) {
    ws.send(JSON.stringify({ type: "wallTilesLoaded", sprites: wallTiles.sprites }))
  }
  if (floorTiles) {
    ws.send(JSON.stringify({ type: "floorTilesLoaded", sprites: floorTiles.sprites }))
  }
  if (furnitureAssets) {
    ws.send(JSON.stringify({
      type: "furnitureAssetsLoaded",
      catalog: furnitureAssets.catalog,
      sprites: furnitureAssets.sprites,
    }))
  }

  // All agents: permanent (always) + any active temporary sessions
  const agentList = Array.from(agents.values())
  const agentIds = agentList.map((a) => a.id)
  const folderNames: Record<number, string> = {}
  const agentMeta: Record<number, { palette?: number; hueShift?: number; seatId?: string }> = {}
  for (const a of agentList) {
    folderNames[a.id] = a.projectName
    if (persistedSeats?.[a.id]) {
      const s = persistedSeats[a.id]
      agentMeta[a.id] = { palette: s.palette, hueShift: s.hueShift, seatId: s.seatId ?? undefined }
    }
  }
  ws.send(JSON.stringify({ type: "existingAgents", agents: agentIds, folderNames, agentMeta }))

  // Layout must come AFTER existingAgents — the hook buffers agents until layout arrives
  if (currentLayout) {
    ws.send(JSON.stringify({ type: "layoutLoaded", layout: currentLayout, version: 1 }))
  } else {
    ws.send(JSON.stringify({ type: "layoutLoaded", layout: null, version: 0 }))
  }
}

wss.on("connection", (ws) => {
  (ws as unknown as Record<string, boolean>).__isAlive = true
  ws.on("pong", () => { (ws as unknown as Record<string, boolean>).__isAlive = true })
  clients.add(ws)

  ws.on("message", (raw) => {
    try {
      const msg = JSON.parse(raw.toString())
      if (msg.type === "webviewReady" || msg.type === "ready") {
        sendInitialData(ws)
      } else if (msg.type === "saveLayout") {
        try {
          mkdirSync(persistDir, { recursive: true })
          writeFileSync(persistedLayoutPath, JSON.stringify(msg.layout, null, 2))
          currentLayout = msg.layout as Record<string, unknown>
          const data = JSON.stringify({ type: "layoutLoaded", layout: msg.layout, version: 1 })
          for (const client of clients) {
            if (client !== ws && client.readyState === WebSocket.OPEN) {
              client.send(data)
            }
          }
        } catch (err) {
          console.error(`[Server] Failed to save layout: ${err instanceof Error ? err.message : err}`)
        }
      } else if (msg.type === "saveAgentSeats") {
        try {
          mkdirSync(persistDir, { recursive: true })
          writeFileSync(persistedSeatsPath, JSON.stringify(msg.seats, null, 2))
        } catch (err) {
          console.error(`[Server] Failed to save agent seats: ${err instanceof Error ? err.message : err}`)
        }
      }
    } catch {
      /* ignore invalid messages */
    }
  })

  ws.on("close", () => clients.delete(ws))
})

// ── File watcher ─────────────────────────────────────────────────────────────
const watcher = new JsonlWatcher()

watcher.on("fileAdded", (file: WatchedFile) => {
  if (agents.has(file.sessionId)) return

  // Skip infrastructure/system directories
  if (BLOCKED_PROJECT_NAMES.has(normalizeName(file.projectName))) return

  lastActivityTime = Date.now()

  // Check if this matches a permanent agent by agent name first, then by project name
  // agentName comes from JSONL metadata or filename pattern (bridge.js writes these)
  const agentKey = file.agentName ? normalizeName(file.agentName) : normalizeName(file.projectName)
  const normalized = agentKey
  const permanent = permanentAgentByName.get(normalized)

  if (permanent && permanent.sessionId.startsWith("permanent-")) {
    // Remove old permanent-key entry, register under the real sessionId
    agents.delete(permanent.sessionId)
    permanent.sessionId = file.sessionId
    permanent.jsonlFile = file.path
    permanent.projectDir = dirname(file.path)
    permanent.fileOffset = 0
    permanent.lineBuffer = ""
    permanent.lastActivityTime = Date.now()
    agents.set(file.sessionId, permanent)
    // No agentCreated broadcast — character already exists and is wandering
    console.log(`Agent ${permanent.id} activated: ${permanent.projectName} (${file.sessionId.slice(0, 8)})`)
    return
  }

  // Temporary / unknown agent — create a new character
  const agent: TrackedAgent = {
    id: nextAgentId++,
    sessionId: file.sessionId,
    projectDir: dirname(file.path),
    projectName: file.projectName,
    jsonlFile: file.path,
    fileOffset: 0,
    lineBuffer: "",
    activity: "idle",
    activeTools: new Map(),
    activeToolNames: new Map(),
    activeSubagentToolIds: new Map(),
    activeSubagentToolNames: new Map(),
    isWaiting: false,
    permissionSent: false,
    hadToolsInTurn: false,
    lastActivityTime: Date.now(),
  }
  agents.set(file.sessionId, agent)
  broadcast({ type: "agentCreated", id: agent.id, folderName: agent.projectName })
  console.log(`Agent ${agent.id} joined: ${agent.projectName} (${file.sessionId.slice(0, 8)})`)
})

watcher.on("fileRemoved", (file: WatchedFile) => {
  const agent = agents.get(file.sessionId)
  if (!agent) return

  const isPermanent = PERMANENT_AGENTS.some((pa) => pa.id === agent.id)

  if (isPermanent) {
    // Keep agent in office — reset state and re-register under permanent key so it wanders
    agents.delete(file.sessionId)
    agent.sessionId = `permanent-${agent.projectName}`
    agent.jsonlFile = ""
    agent.fileOffset = 0
    agent.lineBuffer = ""
    agent.activity = "idle"
    agent.activeTools.clear()
    agent.activeToolNames.clear()
    agent.activeSubagentToolIds.clear()
    agent.activeSubagentToolNames.clear()
    agent.isWaiting = false
    agent.permissionSent = false
    agent.hadToolsInTurn = false
    agents.set(agent.sessionId, agent)

    // Tell client: clear tools and go idle so the character stands up and wanders
    broadcast({ type: "agentToolsClear", id: agent.id })
    broadcast({ type: "agentStatus", id: agent.id, status: "idle" })
    console.log(`Agent ${agent.id} deactivated: ${agent.projectName}`)
    return
  }

  agents.delete(file.sessionId)
  broadcast({ type: "agentClosed", id: agent.id })
  console.log(`Agent ${agent.id} left: ${agent.projectName}`)
})

watcher.on("line", (file: WatchedFile, line: string) => {
  const agent = agents.get(file.sessionId)
  if (!agent) return
  lastActivityTime = Date.now()
  processTranscriptLine(line, agent, broadcast)
})

// Start watcher (synchronous scan) then open HTTP server
watcher.start()
server.listen(PORT, () => {
  console.log(`Pixel Agents server running at http://localhost:${PORT}`)
  console.log(`Watching ~/.claude/projects/ for active sessions...`)
})

// Idle shutdown — only if no real sessions AND no browser clients connected
// If the user has the browser open, keep running so they see the office
setInterval(() => {
  const hasActiveSessions = Array.from(agents.values()).some(
    (a) => !a.sessionId.startsWith("permanent-")
  )
  if (!hasActiveSessions && clients.size === 0 && Date.now() - lastActivityTime > IDLE_SHUTDOWN_MS) {
    console.log("No active sessions or clients for 10 minutes, shutting down...")
    watcher.stop()
    server.close()
    process.exit(0)
  }
}, 30_000)

process.on("SIGINT", () => {
  watcher.stop()
  server.close()
  process.exit(0)
})
