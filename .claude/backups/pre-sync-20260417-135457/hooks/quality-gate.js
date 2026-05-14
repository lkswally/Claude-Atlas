#!/usr/bin/env node
/**
 * Hook: quality-gate (PostToolUse)
 * Despues de editar/escribir archivos TS/JS, emite warnings sobre
 * patrones problematicos detectados en el contenido.
 *
 * PostToolUse hooks NO bloquean — solo advierten via stderr.
 *
 * Vibecoding v2.1 - Expandido con deteccion de secrets hardcodeados
 */

const path = require('path');

const JS_TS_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'];

const PATTERNS = [
  { regex: /(?::\s*any\b|<any>|\bas\s+any\b)/g, msg: 'TypeScript `any` type detected — consider using a specific type', severity: 'warn' },
  { regex: /\/\/\s*@ts-ignore/g, msg: '@ts-ignore detected — prefer @ts-expect-error with explanation', severity: 'warn' },
  { regex: /\/\/\s*@ts-nocheck/g, msg: '@ts-nocheck detected — this disables type checking for the entire file', severity: 'warn' },
  { regex: /\.only\s*\(/g, msg: '.only() in test — will skip other tests if committed', severity: 'error' },
  { regex: /debugger;/g, msg: 'debugger statement found — remove before committing', severity: 'error' },
  { regex: /TODO|FIXME|HACK|XXX/g, msg: 'TODO/FIXME/HACK marker found — track or resolve', severity: 'info' },
  { regex: /(?:api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"]{8,}/ig, msg: 'Possible hardcoded secret/API key detected — use environment variables instead', severity: 'error' },
  { regex: /(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{4,}/ig, msg: 'Possible hardcoded password detected — use environment variables instead', severity: 'error' },
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

    // Solo Write y Edit
    if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

    const filePath = toolInput.file_path || '';
    const ext = path.extname(filePath).toLowerCase();

    // Solo archivos JS/TS
    if (!JS_TS_EXTENSIONS.includes(ext)) process.exit(0);

    // Para Write, chequeamos el contenido directamente
    // Para Edit, chequeamos el new_string
    const content = toolInput.content || toolInput.new_string || '';
    if (!content || content.length < 5) process.exit(0);

    const warnings = [];

    for (const pattern of PATTERNS) {
      const matches = content.match(pattern.regex);
      if (matches && matches.length > 0) {
        // Filtrar: 'any' en comentarios o strings es OK, pero dificil de detectar sin AST
        // Ser conservador: solo reportar si hay multiples matches
        if (pattern.msg.includes('`any` type')) {
          if (matches.length >= 3) {
            warnings.push(`[${pattern.severity}] ${pattern.msg} (${matches.length}x)`);
          }
        } else {
          warnings.push(`[${pattern.severity}] ${pattern.msg} (${matches.length}x)`);
        }
      }
    }

    if (warnings.length > 0) {
      const fileName = path.basename(filePath);
      process.stderr.write(
        `Quality Gate [${fileName}]: ${warnings.join(' | ')}`
      );
    }

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
