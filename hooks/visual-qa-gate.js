#!/usr/bin/env node
/**
 * visual-qa-gate.js — Gate de QA visual antes de merge/deploy
 * ===========================================================
 *
 * Hook PreToolUse (Bash). Implementa el enforcement de
 * policies/visual-qa-protocol.md: en un proyecto con interfaz visual, BLOQUEA
 * merge/deploy si el ultimo QA visual no es PASS para el commit actual.
 *
 * Comandos gateados:
 *   gh pr merge · vercel deploy / vercel --prod · netlify deploy
 *   git push ... main|master
 *
 * Proyecto visual = package.json con un framework de UI (next, react, vue,
 * svelte, astro, vite, nuxt, @angular/core, solid-js, preact, gatsby, remix)
 * o index.html en la raiz. Otros proyectos: no-op.
 *
 * Evidencia requerida: <proyecto>/qa/visual/latest.json (lo escribe
 * tools/visual_qa.py run/review) con verdict PASS y git_head == HEAD.
 *
 * Exit 2 = BLOCK. Exit 0 = permitido.
 * Fail-open SOLO ante errores internos del hook (stdin vacio, JSON roto): un
 * reporte ausente o no-PASS NO es un error interno, es un bloqueo.
 *
 * DISABLE / BYPASS (solo con autorizacion explicita del usuario):
 *   ATLAS_VISUAL_QA_BYPASS=1
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const EXIT_OK = 0;
const EXIT_BLOCK = 2;

const GATED = [
  /(^|[;&|]\s*|\s)gh\s+pr\s+merge\b/i,
  /(^|[;&|]\s*|\s)vercel\b[^\n;&|]*(\bdeploy\b|--prod\b)/i,
  /(^|[;&|]\s*|\s)netlify\s+deploy\b/i,
  /(^|[;&|]\s*|\s)git\s+push\b[^\n;&|]*\b(main|master)\b/i,
];

const UI_DEPS = ['next', 'react', 'vue', 'svelte', 'astro', 'vite', 'nuxt', '@angular/core', 'solid-js', 'preact', 'gatsby', '@remix-run/react'];

function isGated(command) {
  return GATED.some((re) => re.test(command || ''));
}

function isVisualProject(dir) {
  try {
    const pkgPath = path.join(dir, 'package.json');
    if (fs.existsSync(pkgPath)) {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
      const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
      if (UI_DEPS.some((d) => d in deps)) return true;
    }
    return fs.existsSync(path.join(dir, 'index.html'));
  } catch (_) {
    return false;
  }
}

function gitHead(dir) {
  try {
    return execFileSync('git', ['-C', dir, 'rev-parse', 'HEAD'], { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 3000 }).trim();
  } catch (_) {
    return null;
  }
}

function checkGate(dir) {
  const latest = path.join(dir, 'qa', 'visual', 'latest.json');
  if (!fs.existsSync(latest)) {
    return { allowed: false, reason: `no hay QA visual (${path.relative(dir, latest)} no existe)` };
  }
  let report;
  try {
    report = JSON.parse(fs.readFileSync(latest, 'utf-8'));
  } catch (e) {
    return { allowed: false, reason: `reporte de QA visual ilegible: ${e.message}` };
  }
  if (report.verdict !== 'PASS') {
    return { allowed: false, reason: `ultimo QA visual = ${report.verdict} (estado ${report.task_status || 'BLOCKED'})` };
  }
  const head = gitHead(dir);
  if (head && report.git_head && head !== report.git_head) {
    return { allowed: false, reason: `el PASS es del commit ${String(report.git_head).slice(0, 8)} y HEAD es ${head.slice(0, 8)}` };
  }
  return { allowed: true, reason: 'QA visual PASS para el commit actual' };
}

function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    setTimeout(() => finish(data), 2000);
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (c) => { data += c; });
    process.stdin.on('end', () => finish(data));
    process.stdin.on('error', () => finish(''));
  });
}

async function main() {
  try {
    const text = await readStdin();
    if (!text || !text.trim()) process.exit(EXIT_OK);
    const payload = JSON.parse(text);
    if (payload.tool_name !== 'Bash') process.exit(EXIT_OK);
    const command = (payload.tool_input && payload.tool_input.command) || '';
    if (!isGated(command)) process.exit(EXIT_OK);

    const dir = payload.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();
    if (!isVisualProject(dir)) process.exit(EXIT_OK);

    if (['1', 'true', 'yes'].includes(String(process.env.ATLAS_VISUAL_QA_BYPASS || '').toLowerCase())) {
      process.stderr.write('[visual-qa-gate] BYPASS activo (ATLAS_VISUAL_QA_BYPASS=1): merge/deploy sin QA visual. Documentar el motivo.\n');
      process.exit(EXIT_OK);
    }

    const res = checkGate(dir);
    if (res.allowed) process.exit(EXIT_OK);
    process.stderr.write(
      `BLOQUEADO por protocolo de QA visual (policies/visual-qa-protocol.md): ${res.reason}.\n` +
      'Ninguna tarea visual pasa a merge/deploy sin QA real en navegador y evidencia del commit actual.\n' +
      `Correr: python <ATLAS>/tools/visual_qa.py run --url <url> --project "${dir}" --reference <diseno>\n` +
      'Bypass solo con autorizacion explicita del usuario: ATLAS_VISUAL_QA_BYPASS=1\n'
    );
    process.exit(EXIT_BLOCK);
  } catch (_) {
    process.exit(EXIT_OK); // fail-open ante errores internos del hook
  }
}

if (require.main === module) main();

module.exports = { isGated, isVisualProject, checkGate };
