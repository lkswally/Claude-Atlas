#!/usr/bin/env node
/**
 * Hook: console-log-warning (PostToolUse)
 * Detecta console.log/warn/error/debug olvidados en archivos JS/TS.
 * Ignora archivos de test, config, y scripts de build.
 *
 * Vibecoding v2.0 - Inspirado en ECC
 */

const path = require('path');

const JS_TS_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'];

// Archivos donde console.log es aceptable
const IGNORED_PATTERNS = [
  /\.test\./,
  /\.spec\./,
  /\.config\./,
  /[\/\\]__tests__[\/\\]/,  // Jest __tests__/ directories
  /[\/\\]test[\/\\]/,       // /test/ directories
  /scripts\//,
  /hooks\//,
  /\.claude\//,
  /node_modules\//,
  /logger\./,
  /debug\./,
];

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    input = input.trim();
    if (!input) process.exit(0);

    const data = JSON.parse(input);
    const toolName = data.tool_name || '';
    const toolInput = data.tool_input || {};

    if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

    const filePath = toolInput.file_path || '';
    const ext = path.extname(filePath).toLowerCase();

    if (!JS_TS_EXTENSIONS.includes(ext)) process.exit(0);

    // Ignorar archivos donde console es aceptable
    for (const pattern of IGNORED_PATTERNS) {
      if (pattern.test(filePath)) process.exit(0);
    }

    const content = toolInput.content || toolInput.new_string || '';
    if (!content) process.exit(0);

    // Detectar console.log/warn/error/debug (no console.time/timeEnd)
    const consoleMatches = content.match(/console\.(log|warn|error|debug|info)\s*\(/g);

    if (consoleMatches && consoleMatches.length > 0) {
      const fileName = path.basename(filePath);
      process.stderr.write(
        `Console Warning [${fileName}]: ${consoleMatches.length} console statement(s) detected. ` +
        'Consider removing before production or replacing with a proper logger.'
      );
    }

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
