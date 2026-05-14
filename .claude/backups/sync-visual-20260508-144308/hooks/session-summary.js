#!/usr/bin/env node
/**
 * Hook: session-summary (Stop)
 * Se ejecuta despues de cada respuesta de Claude (fase Stop).
 * Mantiene un log de sesion con archivos modificados para recovery.
 *
 * NO genera resumen completo en cada Stop (seria muy costoso).
 * En cambio, mantiene un archivo de tracking incremental que el
 * PreCompact hook y Engram pueden usar.
 *
 * Vibecoding v2.0 - Inspirado en ECC session-summary
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const SESSION_FILE = path.join(os.homedir(), '.claude', 'snapshots', 'session-log.jsonl');
const SNAPSHOTS_DIR = path.join(os.homedir(), '.claude', 'snapshots');

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    // Asegurar directorio
    if (!fs.existsSync(SNAPSHOTS_DIR)) {
      fs.mkdirSync(SNAPSHOTS_DIR, { recursive: true });
    }

    input = input.trim();
    if (!input) {
      // Stop hook sin input = respuesta completada
      const entry = {
        timestamp: new Date().toISOString(),
        event: 'stop',
        cwd: process.cwd(),
      };

      // Append al log de sesion (JSONL format)
      fs.appendFileSync(SESSION_FILE, JSON.stringify(entry) + '\n');

      // Si el log supera 100 lineas, truncar a las ultimas 50
      try {
        const lines = fs.readFileSync(SESSION_FILE, 'utf8').trim().split('\n');
        if (lines.length > 100) {
          const trimmed = lines.slice(-50);
          fs.writeFileSync(SESSION_FILE, trimmed.join('\n') + '\n');
        }
      } catch (e) {}

      process.exit(0);
    }

    // Si hay input (tool_result), loguear
    let data;
    try {
      data = JSON.parse(input);
    } catch (e) {
      process.exit(0);
    }

    const entry = {
      timestamp: new Date().toISOString(),
      event: 'stop',
      tool: data.tool_name || 'unknown',
      cwd: process.cwd(),
    };

    fs.appendFileSync(SESSION_FILE, JSON.stringify(entry) + '\n');
    process.exit(0);
  } catch (err) {
    // Fail-open
    process.exit(0);
  }
});
