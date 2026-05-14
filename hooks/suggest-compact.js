#!/usr/bin/env node
/**
 * Hook: suggest-compact (PostToolUse)
 * Cuenta tool calls y sugiere compactar cada ~50 llamadas.
 * Lee estado del pipeline desde disco para dar contexto util.
 *
 * Vibecoding v2.1 - Mensaje contextual con fase/tarea del pipeline
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const COUNTER_FILE = path.join(os.tmpdir(), '.claude-tool-call-counter.json');
const THRESHOLD = 50;
const REMINDER_INTERVAL = 25;

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    // Leer contador actual
    let counter = { count: 0, lastReminder: 0, sessionStart: Date.now() };
    try {
      const existing = fs.readFileSync(COUNTER_FILE, 'utf8');
      const parsed = JSON.parse(existing);

      // Validar estructura antes de usar
      if (parsed && typeof parsed.count === 'number' && typeof parsed.sessionStart === 'number') {
        counter = parsed;
      }

      // Reset si el archivo tiene mas de 6 horas (nueva sesion probable)
      if (Date.now() - counter.sessionStart > 6 * 60 * 60 * 1000) {
        counter = { count: 0, lastReminder: 0, sessionStart: Date.now() };
      }
    } catch (e) {
      // Archivo no existe o corrupto, usar defaults
    }

    // Incrementar
    counter.count++;

    // Verificar si debemos sugerir compactacion
    if (counter.count >= THRESHOLD) {
      const sinceLastReminder = counter.count - counter.lastReminder;

      if (counter.lastReminder === 0 || sinceLastReminder >= REMINDER_INTERVAL) {
        counter.lastReminder = counter.count;

        // Intentar leer contexto del pipeline desde disco
        let pipelineContext = '';
        try {
          const cwd = process.cwd();
          const pipelineDir = path.join(cwd, '.pipeline');
          const estadoFile = path.join(pipelineDir, 'estado.yaml');
          if (fs.existsSync(estadoFile)) {
            const estado = fs.readFileSync(estadoFile, 'utf8');
            const faseMatch = estado.match(/fase_actual:\s*(.+)/);
            // DAG State YAML uses tarea_actual and total_tareas (not "completadas" / "total")
            const tareaActualMatch = estado.match(/tarea_actual:\s*(\d+)/);
            const totalTareasMatch = estado.match(/total_tareas:\s*(\d+)/);
            if (faseMatch) {
              pipelineContext = ` Pipeline: Fase ${faseMatch[1].trim()}`;
              if (tareaActualMatch && totalTareasMatch) {
                pipelineContext += `, tarea ${tareaActualMatch[1]}/${totalTareasMatch[1]}`;
              }
              pipelineContext += '.';
            }
          }
        } catch (e) {}

        process.stderr.write(
          `Context reminder: ${counter.count} tool calls in this session.${pipelineContext} ` +
          'Consider running /compact to free up context window. ' +
          'State is saved in Engram — safe to compact.'
        );
      }
    }

    // Guardar contador
    fs.writeFileSync(COUNTER_FILE, JSON.stringify(counter));

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
