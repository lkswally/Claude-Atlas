#!/usr/bin/env node
/**
 * Hook: quality-gate (PostToolUse)
 * Despues de editar/escribir archivos TS/JS, emite warnings sobre
 * patrones problematicos detectados en el contenido.
 *
 * PostToolUse hooks NO bloquean — solo advierten via stderr.
 *
 * Vibecoding v2.1 - Expandido con deteccion de secrets hardcodeados
 * Vibecoding v2.2 (Autonomy Improvement V2, Improvement A) - Deterministic
 * Security Backstop. Gap demostrado: Autonomy Benchmark V1 Security = 18.8%
 * (6/8 fixtures reales sin deteccion: eval, SQLi, CORS, missing-auth, IDOR,
 * unsafe upload). security-engineer (unico agente con juicio semantico para
 * estas categorias) solo se invoca en Fase 2 del pipeline completo — ausente
 * del modo "Claude normal" (default). Este backstop NO reemplaza a
 * security-engineer: detecta señales, no corrige, no decide arquitectura, no
 * genera patches. missing-authorization/IDOR genericos quedan
 * DELIBERADAMENTE fuera — son problemas de ausencia (negative-space) que un
 * regex no puede detectar sin ruido masivo; siguen siendo responsabilidad de
 * security-engineer. Ver docs/AUTONOMY-IMPROVEMENT-V2.md.
 */

const fs = require('fs');
const path = require('path');

const JS_TS_EXTENSIONS = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'];

const PATTERNS = [
  { regex: /(?::\s*any\b|<any>|\bas\s+any\b)/g, msg: 'TypeScript `any` type detected — consider using a specific type', severity: 'warn' },
  { regex: /\/\/\s*@ts-ignore/g, msg: '@ts-ignore detected — prefer @ts-expect-error with explanation', severity: 'warn' },
  { regex: /\/\/\s*@ts-nocheck/g, msg: '@ts-nocheck detected — this disables type checking for the entire file', severity: 'warn' },
  { regex: /\.only\s*\(/g, msg: '.only() in test — will skip other tests if committed', severity: 'error' },
  { regex: /debugger;/g, msg: 'debugger statement found — remove before committing', severity: 'error' },
  { regex: /TODO|FIXME|HACK|XXX/g, msg: 'TODO/FIXME/HACK marker found — track or resolve', severity: 'info' },
  { regex: /(?:api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"]{8,}/ig, msg: 'Possible hardcoded secret/API key detected — use environment variables instead', severity: 'error', excludeEnvPatterns: true },
  { regex: /(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{4,}/ig, msg: 'Possible hardcoded password detected — use environment variables instead', severity: 'error', excludeEnvPatterns: true },
];

// ---------------------------------------------------------------------------
// Security Backstop rules (Autonomy Improvement V2, Improvement A).
// Each rule is deliberately narrow to avoid mass false positives (explicit
// requirement). "FIND, DON'T FIX": these only ever WARN (severity 'error'
// here means the existing WARN-with-red-label UX, not a hook exit-code
// change — the hook remains exit 0 / fail-open, matching CLAUDE.md's
// documented behavior for quality-gate). Each rule also carries a stable
// `id`/`category`/`confidence` for the structured security_signals log.
// ---------------------------------------------------------------------------
const SECURITY_PATTERNS = [
  {
    id: 'SEC-EVAL-001',
    category: 'code_execution',
    confidence: 'high',
    // \beval\s*\( requires the literal "eval(" — does NOT match "evaluate("
    // (the "uate" between eval and "(" breaks the match). new Function() is
    // the equally-dangerous dynamic-code sibling.
    regex: /\beval\s*\(|new\s+Function\s*\(/g,
    msg: 'Unsafe dynamic code execution (eval/new Function) detected',
    severity: 'error',
  },
  {
    id: 'SEC-CMDI-001',
    category: 'injection',
    confidence: 'medium',
    // Requires an explicit child_process/cp qualifier before exec/execSync
    // PLUS a concatenation/interpolation marker inside the call — this is
    // what excludes the extremely common (and harmless) RegExp.exec(str).
    regex: /(?:child_process|cp)\.(?:exec|execSync)\s*\([^)]*?(?:\+|\$\{)/g,
    msg: 'Possible command injection — child_process.exec with string concatenation/interpolation',
    severity: 'error',
  },
  {
    id: 'SEC-SQLI-001',
    category: 'injection',
    confidence: 'medium',
    // A .query()/.raw() call whose string argument contains a SQL keyword
    // AND a concatenation/interpolation marker. Parameterized queries
    // (placeholders + a separate params array) do not match, since the
    // string literal itself has no '+' or '${'.
    regex: /\.(?:query|raw)\s*\(\s*[`"'][^)]*?(?:SELECT|INSERT|UPDATE|DELETE)[^)]*?(?:\+|\$\{)/ig,
    msg: 'Possible SQL injection — string concatenation inside a query call (use parameterized queries)',
    severity: 'error',
  },
  {
    id: 'SEC-XSS-001',
    category: 'xss',
    confidence: 'medium',
    // innerHTML assigned from something that is NOT a literal starting
    // immediately with a quote/backtick (i.e., a variable/expression).
    // \s in the negative lookahead too (not just the quote chars) — \s*
    // is backtrackable, so without it the engine can retry with zero
    // whitespace consumed and land the lookahead on the space itself,
    // which trivially isn't a quote and would defeat the check.
    // dangerouslySetInnerHTML/v-html are flagged on presence, matching
    // their own framework-level "danger" naming.
    regex: /\.innerHTML\s*=\s*(?![\s'"`])[^;\n]|dangerouslySetInnerHTML|v-html\s*=/g,
    msg: 'Unsafe HTML injection point (innerHTML/dangerouslySetInnerHTML/v-html) — verify input is sanitized',
    severity: 'warn',
  },
  {
    id: 'SEC-CORS-001',
    category: 'access_control',
    confidence: 'high',
    // Wildcard origin AND credentials:true within the same ~150-char
    // window (same config object in practice) — the combination is the
    // actual vulnerability, not either flag alone.
    regex: /origin\s*:\s*['"]\*['"][\s\S]{0,150}?credentials\s*:\s*true|credentials\s*:\s*true[\s\S]{0,150}?origin\s*:\s*['"]\*['"]/g,
    msg: 'Insecure CORS: wildcard origin combined with credentials:true',
    severity: 'error',
  },
  {
    id: 'SEC-TLS-001',
    category: 'crypto',
    confidence: 'high',
    regex: /rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['"]?0/g,
    msg: 'TLS certificate verification disabled',
    severity: 'error',
  },
  {
    id: 'SEC-UPLOAD-001',
    category: 'path_traversal',
    confidence: 'medium',
    // A file-write-like call whose path/argument uses the original
    // uploaded filename directly (classic Multer path-traversal idiom).
    regex: /(?:writeFileSync|writeFile|createWriteStream|rename|copyFile)\s*\([^)]*\.(?:originalname|name)\b/g,
    msg: 'Unsafe file upload — writing with the original/user-supplied filename directly (path traversal risk)',
    severity: 'warn',
  },
];

// ---------------------------------------------------------------------------
// Comment masking for the Security Backstop only (Stability Repair 05).
// Root cause of SH-P1-2: the 7 SECURITY_PATTERNS regexes ran directly
// against raw file content, so a `// TODO: never call eval(userInput)`
// comment fired SEC-EVAL-001 exactly like the real call would. A naive
// `content.replace(/\/\/.*/g, '')`-style strip was rejected: it would
// corrupt string literals containing `//` (e.g. "https://example.com") and,
// worse, several of these rules (SEC-CMDI-001, SEC-SQLI-001,
// SEC-UPLOAD-001) are DESIGNED to match a dangerous payload embedded inside
// a string/template argument to exec()/query()/writeFileSync() — blanking
// string content would silently create new false negatives there.
//
// maskComments() is a single-pass lexical scanner (JS/TS/JSX/TSX only —
// the only extensions this hook ever scans, per JS_TS_EXTENSIONS) that
// replaces `//...` and `/* ... */` comment interiors with spaces, leaving
// every other character — including string, template and regex literals —
// byte-for-byte in place. Because length and newlines are preserved
// exactly, character offsets computed against the masked string still
// point at the correct location in the original content, so
// lineNumberOf() needs no changes.
//
// Only the SECURITY_PATTERNS loop below scans the masked content. The
// general PATTERNS loop (TODO/FIXME/@ts-ignore/etc.) still scans raw
// `content`, since those patterns exist specifically to find comment
// markers and would break if comments were blanked first.
// ---------------------------------------------------------------------------
const REGEX_CONTEXT_TOKENS = new Set([
  '', '(', ',', '=', ':', ';', '!', '&', '|', '?', '{', '[', '+', '-', '*',
  '%', '^', '~', '<', '>',
  'return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void',
  'throw', 'case', 'yield', 'do', 'else',
]);

/** Scans a regex literal starting at content[start] === '/'. Returns chars
 * consumed (body + flags), or 0 if this doesn't look like a valid regex
 * literal (caller falls back to treating '/' as an ordinary character). */
function scanRegexLiteral(content, start) {
  const n = content.length;
  let i = start + 1;
  if (i < n && (content[i] === '/' || content[i] === '*')) return 0; // // or /* — not a regex
  let inClass = false;
  while (i < n) {
    const c = content[i];
    if (c === '\\') { i += 2; continue; }
    if (c === '\n') return 0; // regex literals can't span lines
    if (c === '[') { inClass = true; i++; continue; }
    if (c === ']') { inClass = false; i++; continue; }
    if (c === '/' && !inClass) {
      i++;
      while (i < n && /[a-z]/i.test(content[i])) i++; // flags
      return i - start;
    }
    i++;
  }
  return 0; // never closed — not a regex literal
}

/** Replaces // and /* *‌/ comment interiors with spaces; strings, template
 * literals and regex literals pass through untouched. Same length as the
 * input, newlines preserved, so downstream offsets stay valid. */
function maskComments(content) {
  const n = content.length;
  const out = new Array(n);
  let i = 0;
  let state = 'code'; // code | line-comment | block-comment | sq | dq | tpl
  let lastToken = '';
  const tplBraceStack = [];
  let braceDepth = 0;

  const isWordChar = (c) => /[A-Za-z0-9_$]/.test(c);

  while (i < n) {
    const c = content[i];
    const c2 = i + 1 < n ? content[i + 1] : '';

    if (state === 'code') {
      if (c === '/' && c2 === '/') {
        out[i] = ' '; out[i + 1] = ' ';
        i += 2; state = 'line-comment'; continue;
      }
      if (c === '/' && c2 === '*') {
        out[i] = ' '; out[i + 1] = ' ';
        i += 2; state = 'block-comment'; continue;
      }
      if (c === '"') { out[i] = c; i++; state = 'dq'; lastToken = '"'; continue; }
      if (c === "'") { out[i] = c; i++; state = 'sq'; lastToken = "'"; continue; }
      if (c === '`') { out[i] = c; i++; state = 'tpl'; lastToken = '`'; continue; }
      if (c === '/' && REGEX_CONTEXT_TOKENS.has(lastToken)) {
        const consumed = scanRegexLiteral(content, i);
        if (consumed > 0) {
          for (let k = 0; k < consumed; k++) out[i + k] = content[i + k];
          i += consumed; lastToken = '/'; continue;
        }
      }
      if (c === '{' && tplBraceStack.length > 0) braceDepth++;
      if (c === '}' && tplBraceStack.length > 0) {
        if (braceDepth === 0) {
          out[i] = c; i++;
          braceDepth = tplBraceStack.pop();
          state = 'tpl'; lastToken = '}'; continue;
        }
        braceDepth--;
      }
      out[i] = c;
      if (isWordChar(c)) {
        let j = i;
        while (j < n && isWordChar(content[j])) { out[j] = content[j]; j++; }
        lastToken = content.slice(i, j);
        i = j; continue;
      }
      if (!/\s/.test(c)) lastToken = c;
      i++; continue;
    }

    if (state === 'line-comment') {
      if (c === '\n') { out[i] = '\n'; state = 'code'; }
      else out[i] = ' ';
      i++; continue;
    }

    if (state === 'block-comment') {
      if (c === '*' && c2 === '/') {
        out[i] = ' '; out[i + 1] = ' ';
        i += 2; state = 'code'; continue;
      }
      out[i] = c === '\n' ? '\n' : ' ';
      i++; continue;
    }

    if (state === 'dq' || state === 'sq') {
      if (c === '\\' && i + 1 < n) {
        out[i] = c; out[i + 1] = content[i + 1];
        i += 2; continue;
      }
      out[i] = c;
      i++;
      if ((state === 'dq' && c === '"') || (state === 'sq' && c === "'")) state = 'code';
      continue;
    }

    if (state === 'tpl') {
      if (c === '\\' && i + 1 < n) {
        out[i] = c; out[i + 1] = content[i + 1];
        i += 2; continue;
      }
      if (c === '`') { out[i] = c; i++; state = 'code'; lastToken = '`'; continue; }
      if (c === '$' && c2 === '{') {
        out[i] = '$'; out[i + 1] = '{';
        i += 2;
        tplBraceStack.push(braceDepth);
        braceDepth = 0;
        state = 'code'; lastToken = '{';
        continue;
      }
      out[i] = c;
      i++; continue;
    }
  }

  return out.join('');
}

const SECURITY_LOG_FILE = path.join('.claude', 'logs', 'security-signals.jsonl');

// Patterns that indicate the match is an env var reference (not a hardcoded secret)
const ENV_REFERENCE_PATTERNS = [
  /process\.env\./,
  /import\.meta\.env\./,
  /Deno\.env\./,
  /Bun\.env\./,
  /\.env\?\./,      // optional chaining on env object
  /ENV\[/,          // Ruby/Node style ENV lookups
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
        } else if (pattern.excludeEnvPatterns) {
          // Para secrets/passwords: verificar que cada match NO esté en línea con env var reference
          const realMatches = matches.filter((match) => {
            // Find the line containing this match
            const idx = content.indexOf(match);
            if (idx === -1) return true;
            const lineStart = content.lastIndexOf('\n', idx) + 1;
            const lineEnd = content.indexOf('\n', idx);
            const line = content.slice(lineStart, lineEnd === -1 ? undefined : lineEnd);
            // Si la línea referencia process.env.*/import.meta.env.*/etc → no es hardcoded
            return !ENV_REFERENCE_PATTERNS.some((re) => re.test(line));
          });
          if (realMatches.length > 0) {
            warnings.push(`[${pattern.severity}] ${pattern.msg} (${realMatches.length}x)`);
          }
        } else {
          warnings.push(`[${pattern.severity}] ${pattern.msg} (${matches.length}x)`);
        }
      }
    }

    // Security Backstop scan (Improvement A). Separate loop: findings need
    // line numbers for the structured signal log, and use their own `id`
    // so a future Verification Router can reference them stably.
    // Scans `contentForSecurity` (comments masked — see maskComments above),
    // not raw `content`, so a comment merely mentioning a dangerous pattern
    // no longer fires (Stability Repair 05 / SH-P1-2). Masking preserves
    // length and newlines exactly, so `m.index` still maps to the correct
    // line in the real file.
    const contentForSecurity = maskComments(content);
    const securityFindings = [];
    for (const rule of SECURITY_PATTERNS) {
      // Fresh regex per content scan — patterns are /g, and .exec() with a
      // /g regex is stateful (lastIndex), so reset before each file.
      rule.regex.lastIndex = 0;
      let m;
      while ((m = rule.regex.exec(contentForSecurity)) !== null) {
        securityFindings.push({
          id: rule.id,
          category: rule.category,
          severity: rule.severity === 'error' ? 'HIGH' : 'MEDIUM',
          path: filePath,
          line: lineNumberOf(content, m.index),
          evidence: m[0].slice(0, 120).trim(),
          confidence: rule.confidence,
          msg: rule.msg,
        });
        // Avoid infinite loop on zero-length matches
        if (m.index === rule.regex.lastIndex) rule.regex.lastIndex++;
      }
    }

    if (securityFindings.length > 0) {
      // Dedupe by rule id for the terminal summary (one line per rule,
      // count of occurrences) — the full per-occurrence detail still goes
      // to the JSONL log.
      const byRule = {};
      for (const f of securityFindings) {
        byRule[f.id] = byRule[f.id] || { msg: f.msg, severity: f.severity, count: 0 };
        byRule[f.id].count++;
      }
      for (const id of Object.keys(byRule)) {
        const r = byRule[id];
        const sev = r.severity === 'HIGH' ? 'error' : 'warn';
        warnings.push(`[${sev}] [security:${id}] ${r.msg} (${r.count}x)`);
      }
      appendSecuritySignals(securityFindings);
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

/** 1-indexed line number of a character offset within `content`. */
function lineNumberOf(content, index) {
  let line = 1;
  for (let i = 0; i < index && i < content.length; i++) {
    if (content[i] === '\n') line++;
  }
  return line;
}

/**
 * Append structured security signals to .claude/logs/security-signals.jsonl
 * (gitignored runtime log, same convention as cost-tracker.js/
 * session-summary.js). Fail-open: a logging failure must never affect the
 * hook's exit code or block the tool call it's observing.
 */
function appendSecuritySignals(findings) {
  try {
    const dir = path.dirname(SECURITY_LOG_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const ts = new Date().toISOString();
    const lines = findings
      .map((f) => JSON.stringify({ timestamp: ts, ...f }))
      .join('\n') + '\n';
    fs.appendFileSync(SECURITY_LOG_FILE, lines);
  } catch (e) {
    // fail-open — never let logging break the hook
  }
}
