#!/usr/bin/env node
/**
 * Hook: session-start-context (Notification)
 * Se ejecuta al inicio de sesion. Lee el snapshot pre-compact mas reciente
 * y emite un resumen via stderr para que Claude tenga contexto inmediato.
 *
 * Tambien lee el cost-log para dar metricas de la sesion anterior.
 *
 * Vibecoding v2.1 - Con health check de hooks async
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const SNAPSHOTS_DIR = path.join(os.homedir(), '.claude', 'snapshots');
const SNAPSHOT_FILE = path.join(SNAPSHOTS_DIR, 'pre-compact-latest.json');
const SESSION_LOG = path.join(SNAPSHOTS_DIR, 'session-log.jsonl');
const COST_LOG = path.join(SNAPSHOTS_DIR, 'cost-log.jsonl');

let input = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const messages = [];

    // 1. Check for pre-compact snapshot
    if (fs.existsSync(SNAPSHOT_FILE)) {
      try {
        const snapshot = JSON.parse(fs.readFileSync(SNAPSHOT_FILE, 'utf8'));
        const age = Date.now() - new Date(snapshot.timestamp).getTime();
        const ageHours = (age / (1000 * 60 * 60)).toFixed(1);

        if (age < 24 * 60 * 60 * 1000) { // Less than 24h old
          messages.push(
            `Previous session (${ageHours}h ago): ${snapshot.toolCallCount || 0} tool calls, ` +
            `cwd: ${snapshot.cwd || 'unknown'}. Context was compacted.`
          );
        }
      } catch (e) {}
    }

    // 2. Quick cost summary from last session
    if (fs.existsSync(COST_LOG)) {
      try {
        const lines = fs.readFileSync(COST_LOG, 'utf8').trim().split('\n');
        const entries = lines.slice(-50).map(l => { try { return JSON.parse(l); } catch(e) { return null; } }).filter(Boolean);

        if (entries.length > 0) {
          const agents = entries.filter(e => e.category === 'agent');
          if (agents.length > 0) {
            const types = {};
            agents.forEach(a => { types[a.subagent || 'general'] = (types[a.subagent || 'general'] || 0) + 1; });
            const top = Object.entries(types).sort((a,b) => b[1] - a[1]).slice(0, 3);
            messages.push(
              `Recent activity: ${entries.length} tool calls, ${agents.length} agent invocations. ` +
              `Top agents: ${top.map(([t,c]) => `${t}(${c})`).join(', ')}.`
            );
          }
        }
      } catch (e) {}
    }

    // 3. Health check de hooks async (cost-tracker, session-summary)
    const staleHooks = [];
    const STALE_THRESHOLD = 48 * 60 * 60 * 1000; // 48h — generous threshold

    if (fs.existsSync(COST_LOG)) {
      try {
        const stat = fs.statSync(COST_LOG);
        if (Date.now() - stat.mtimeMs > STALE_THRESHOLD) {
          staleHooks.push('cost-tracker');
        }
      } catch (e) {}
    } else {
      staleHooks.push('cost-tracker (no log file)');
    }

    if (fs.existsSync(SESSION_LOG)) {
      try {
        const stat = fs.statSync(SESSION_LOG);
        if (Date.now() - stat.mtimeMs > STALE_THRESHOLD) {
          staleHooks.push('session-summary');
        }
      } catch (e) {}
    } else {
      staleHooks.push('session-summary (no log file)');
    }

    if (staleHooks.length > 0) {
      messages.push(`HOOK HEALTH WARNING: ${staleHooks.join(', ')} may be dead — last write >48h ago or missing log file.`);
    }

    // 4. Emit context if there's anything useful
    if (messages.length > 0) {
      process.stderr.write('Session context: ' + messages.join(' | '));
    }

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
