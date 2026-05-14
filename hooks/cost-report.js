#!/usr/bin/env node
/**
 * Cost Report — Lee cost-log.jsonl y genera reporte de uso
 * Ejecutar: node cost-report.js [--last=N] [--agents-only]
 *
 * Vibecoding v2.0
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const COST_LOG = path.join(os.homedir(), '.claude', 'snapshots', 'cost-log.jsonl');

// Parse args
const args = process.argv.slice(2);
const lastN = args.find(a => a.startsWith('--last='));
const agentsOnly = args.includes('--agents-only');
const parsedLimit = lastN ? parseInt(lastN.split('=')[1], 10) : Infinity;
const limit = Number.isNaN(parsedLimit) ? Infinity : parsedLimit;

try {
  if (!fs.existsSync(COST_LOG)) {
    console.log('No cost log found. Run some tool calls first.');
    process.exit(0);
  }

  let lines = fs.readFileSync(COST_LOG, 'utf8').trim().split('\n');
  if (limit < lines.length) lines = lines.slice(-limit);

  const entries = lines.map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);

  if (agentsOnly) {
    const agentEntries = entries.filter(e => e.category === 'agent');
    console.log(`\n=== AGENT INVOCATIONS (${agentEntries.length} total) ===\n`);

    // Group by subagent type
    const byType = {};
    for (const e of agentEntries) {
      const key = e.subagent || 'general-purpose';
      if (!byType[key]) byType[key] = { count: 0, models: new Set(), descs: [] };
      byType[key].count++;
      byType[key].models.add(e.model || 'inherited');
      byType[key].descs.push(e.desc || '');
    }

    for (const [type, data] of Object.entries(byType).sort((a, b) => b[1].count - a[1].count)) {
      console.log(`  ${type}: ${data.count}x (models: ${[...data.models].join(', ')})`);
    }
    console.log('');
    return;
  }

  // Full report
  console.log(`\n=== COST REPORT ===`);
  console.log(`Period: ${entries[0]?.ts || 'N/A'} to ${entries[entries.length - 1]?.ts || 'N/A'}`);
  console.log(`Total tool calls: ${entries.length}\n`);

  // By category
  const byCat = {};
  for (const e of entries) {
    const cat = e.category || 'other';
    byCat[cat] = (byCat[cat] || 0) + 1;
  }

  console.log('By category:');
  for (const [cat, count] of Object.entries(byCat).sort((a, b) => b[1] - a[1])) {
    const pct = ((count / entries.length) * 100).toFixed(1);
    const bar = '#'.repeat(Math.ceil(count / entries.length * 30));
    console.log(`  ${cat.padEnd(10)} ${String(count).padStart(4)} (${pct}%) ${bar}`);
  }

  // Agent breakdown
  const agentEntries = entries.filter(e => e.category === 'agent');
  if (agentEntries.length > 0) {
    console.log(`\nAgent invocations (${agentEntries.length}):`);
    const byType = {};
    for (const e of agentEntries) {
      const key = e.subagent || 'general-purpose';
      byType[key] = (byType[key] || 0) + 1;
    }
    for (const [type, count] of Object.entries(byType).sort((a, b) => b[1] - a[1])) {
      console.log(`  ${type}: ${count}x`);
    }
  }

  // Heaviest tools (most calls)
  const byTool = {};
  for (const e of entries) {
    byTool[e.tool] = (byTool[e.tool] || 0) + 1;
  }
  console.log('\nTop tools:');
  Object.entries(byTool).sort((a, b) => b[1] - a[1]).slice(0, 10).forEach(([tool, count]) => {
    console.log(`  ${tool}: ${count}x`);
  });

  console.log('');
} catch (err) {
  console.error('Error reading cost log:', err.message);
  process.exit(1);
}
