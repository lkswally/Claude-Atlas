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
            // Parser seguro: ignora comentarios, quita quotes, solo top-level keys.
            const extractYamlField = (content, key) => {
              const lines = content.split('\n');
              for (const line of lines) {
                if (/^\s*#/.test(line) || /^\s/.test(line)) continue;
                const m = line.match(new RegExp(`^${key}\\s*:\\s*(.*)$`));
                if (m) {
                  let value = m[1].replace(/\s*#.*$/, '').trim();
                  if ((value.startsWith('"') && value.endsWith('"')) ||
                      (value.startsWith("'") && value.endsWith("'"))) {
                    value = value.slice(1, -1);
                  }
                  return value;
                }
              }
              return null;
            };
            const fase = extractYamlField(estado, 'fase_actual');
            const tarea = extractYamlField(estado, 'tarea_actual');
            const total = extractYamlField(estado, 'total_tareas');
            if (fase) {
              pipelineContext = ` Pipeline: Fase ${fase}`;
              if (tarea && total && /^\d+$/.test(tarea) && /^\d+$/.test(total)) {
                pipelineContext += `, tarea ${tarea}/${total}`;
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
