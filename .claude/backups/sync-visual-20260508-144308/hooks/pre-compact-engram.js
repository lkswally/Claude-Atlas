#!/usr/bin/env node
/**
 * Hook: pre-compact-engram (PreCompact)
 * Se ejecuta antes de compactar contexto.
 *
 * Dos responsabilidades:
 * 1. Guardar snapshot de sesion a disco (tool count, cwd, timestamp)
 * 2. BLOQUEAR la compactacion via stderr para que Claude haga dual-write
 *    del DAG State ANTES de perder el contexto detallado.
 *
 * NOTA: PreCompact hooks NO pueden llamar a MCPs (Engram).
 * Solo pueden escribir a disco y emitir mensajes via stderr.
 * El mensaje de stderr llega a Claude como contexto — Claude es quien
 * ejecuta el mem_update + disk write antes de que la compactacion proceda.
 *
 * Vibecoding v2.2 — PreCompact blocking (inspirado por MemPalace)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const COUNTER_FILE = path.join(os.tmpdir(), '.claude-tool-call-counter.json');
const SNAPSHOT_DIR = path.join(os.homedir(), '.claude', 'snapshots');
const SNAPSHOT_FILE = path.join(SNAPSHOT_DIR, 'pre-compact-latest.json');
const TRIGGER_FILE = path.join(SNAPSHOT_DIR, 'compaction-pending.json');

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    // Leer el contador de tool calls si existe
    let toolCallCount = 0;
    try {
      const counterData = JSON.parse(fs.readFileSync(COUNTER_FILE, 'utf8'));
      toolCallCount = counterData.count || 0;
    } catch (e) {}

    // Crear directorio de snapshots si no existe
    if (!fs.existsSync(SNAPSHOT_DIR)) {
      fs.mkdirSync(SNAPSHOT_DIR, { recursive: true });
    }

    // Detectar si hay un pipeline activo (buscar .pipeline/ en cwd)
    const cwd = process.cwd();
    let pipelineActive = false;
    let pipelinePhase = '';
    let pipelineTask = '';
    try {
      const estadoPath = path.join(cwd, '.pipeline', 'estado.yaml');
      if (fs.existsSync(estadoPath)) {
        pipelineActive = true;
        const estado = fs.readFileSync(estadoPath, 'utf8');
        const faseMatch = estado.match(/fase_actual:\s*(.+)/);
        const tareaMatch = estado.match(/tarea_actual:\s*(\d+)/);
        const totalMatch = estado.match(/total_tareas:\s*(\d+)/);
        if (faseMatch) pipelinePhase = faseMatch[1].trim();
        if (tareaMatch && totalMatch) pipelineTask = `${tareaMatch[1]}/${totalMatch[1]}`;
      }
    } catch (e) {}

    // Guardar snapshot
    const snapshot = {
      timestamp: new Date().toISOString(),
      event: 'pre-compact',
      toolCallCount,
      cwd,
      pipelineActive,
      pipelinePhase,
      pipelineTask,
      note: 'Context was compacted. DAG State dual-write was requested before compaction.',
    };

    fs.writeFileSync(SNAPSHOT_FILE, JSON.stringify(snapshot, null, 2));

    // Escribir trigger file — Boot Sequence lo detecta y ejecuta dual-write
    // Esto reemplaza la instrucción en stderr que causaba respuestas vacías sin tool calls
    const trigger = {
      timestamp: snapshot.timestamp,
      pipelineActive,
      pipelinePhase,
      pipelineTask,
      cwd,
      instruction: 'dual-write-dag-state',
    };
    fs.writeFileSync(TRIGGER_FILE, JSON.stringify(trigger, null, 2));

    // Reset tool call counter (nuevo contexto despues de compactar)
    try {
      fs.unlinkSync(COUNTER_FILE);
    } catch (e) {}

    // Mensaje informativo (NO instrucción) — solo contexto de diagnóstico
    const pipelineInfo = pipelineActive
      ? ` Pipeline activo: ${pipelinePhase}, tarea ${pipelineTask}.`
      : '';

    process.stderr.write(
      '[pre-compact-engram] Snapshot guardado.' + pipelineInfo +
      ' Trigger file escrito en snapshots/compaction-pending.json.' +
      ' Boot Sequence detectará y ejecutará dual-write al iniciar.'
    );

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
