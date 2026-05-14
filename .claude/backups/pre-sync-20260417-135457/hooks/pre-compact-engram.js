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

    // Reset tool call counter (nuevo contexto despues de compactar)
    try {
      fs.unlinkSync(COUNTER_FILE);
    } catch (e) {}

    // MENSAJE CRITICO: instruir a Claude a hacer dual-write ANTES de compactar
    // Este mensaje llega via stderr y Claude lo recibe como contexto
    const pipelineInfo = pipelineActive
      ? ` Pipeline activo: ${pipelinePhase}, tarea ${pipelineTask}.`
      : '';

    process.stderr.write(
      'COMPACTION IMMINENT — SAVE STATE NOW. ' +
      'Before compaction proceeds, you MUST:' +
      ' (1) Save DAG State to Engram via mem_update("{proyecto}/estado", currentDagState).' +
      ' (2) Write DAG State to disk at {project_dir}/.pipeline/estado.yaml.' +
      ' (3) If you have unsaved discoveries or task progress, save them with mem_save.' +
      ' After saving, compaction is safe — Boot Sequence will recover from Engram or disk.' +
      pipelineInfo +
      ' Snapshot saved to disk. Counter reset.'
    );

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
