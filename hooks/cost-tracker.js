#!/usr/bin/env node
/**
 * Hook: cost-tracker (PostToolUse)
 * Registra cada tool call con timestamp, tipo de tool, y archivo afectado.
 * Enfoque especial en Agent calls (subagentes) para medir uso del pipeline.
 *
 * Output: ~/.claude/snapshots/cost-log.jsonl (append-only, auto-trim)
 *
 * Vibecoding v2.0 - Inspirado en ECC cost-tracker
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const SNAPSHOTS_DIR = path.join(os.homedir(), '.claude', 'snapshots');
const COST_LOG = path.join(SNAPSHOTS_DIR, 'cost-log.jsonl');
const MAX_LINES = 500;

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    if (!fs.existsSync(SNAPSHOTS_DIR)) {
      fs.mkdirSync(SNAPSHOTS_DIR, { recursive: true });
    }

    input = input.trim();
    if (!input) process.exit(0);

    let data;
    try {
      data = JSON.parse(input);
    } catch (e) {
      process.exit(0);
    }

    const toolName = data.tool_name || 'unknown';
    const toolInput = data.tool_input || {};

    // Construir entry segun tipo de tool
    const entry = {
      ts: new Date().toISOString(),
      tool: toolName,
    };

    if (toolName === 'Agent') {
      // Subagente: registrar tipo y descripcion
      entry.subagent = toolInput.subagent_type || 'general-purpose';
      entry.desc = (toolInput.description || '').slice(0, 80);
      entry.model = toolInput.model || 'inherited';
      entry.background = toolInput.run_in_background || false;
      entry.category = 'agent';
    } else if (toolName === 'Bash') {
      // Bash: registrar comando (primeras 100 chars)
      entry.cmd = (toolInput.command || '').slice(0, 100);
      entry.category = 'exec';
    } else if (toolName === 'Write' || toolName === 'Edit') {
      // File ops: registrar path
      entry.file = toolInput.file_path ? path.basename(toolInput.file_path) : 'unknown';
      entry.category = 'file';
    } else if (toolName === 'Read' || toolName === 'Glob' || toolName === 'Grep') {
      entry.category = 'search';
    } else if (toolName.startsWith('mcp__engram')) {
      entry.category = 'memory';
    } else if (toolName.startsWith('mcp__playwright')) {
      entry.category = 'browser';
    } else {
      entry.category = 'other';
    }

    // Atomic append-with-trim: read → append in memory → write to temp → rename.
    // Evita race condition read-write entre append y trim cuando corren hooks paralelos.
    const tmpFile = COST_LOG + '.tmp.' + process.pid;
    try {
      let lines = [];
      if (fs.existsSync(COST_LOG)) {
        const existing = fs.readFileSync(COST_LOG, 'utf8').trim();
        if (existing) lines = existing.split('\n').filter(l => l.trim());
      }
      lines.push(JSON.stringify(entry));
      // Trim si supera MAX_LINES (keep 80% to avoid frequent trims)
      if (lines.length > MAX_LINES) {
        lines = lines.slice(-Math.floor(MAX_LINES * 0.8));
      }
      fs.writeFileSync(tmpFile, lines.join('\n') + '\n');
      fs.renameSync(tmpFile, COST_LOG);  // rename es atómico en mismo filesystem
    } catch (e) {
      try { fs.unlinkSync(tmpFile); } catch (_) {}
    }

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
