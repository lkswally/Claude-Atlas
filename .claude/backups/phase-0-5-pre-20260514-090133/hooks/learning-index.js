#!/usr/bin/env node
/**
 * Learning Index — Mantiene un indice local de discoveries de Engram
 * Ejecutar: node learning-index.js [--search=keyword] [--list] [--add title|content]
 *
 * Este NO es un hook automatico — es una utilidad manual que complementa
 * los proactive saves de Engram. Mantiene un indice local rapido para
 * buscar discoveries sin hacer mem_search.
 *
 * Vibecoding v2.0 - Version ligera de continuous learning de ECC
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const INDEX_FILE = path.join(os.homedir(), '.claude', 'snapshots', 'learning-index.json');

// Parse args
const args = process.argv.slice(2);
const searchArg = args.find(a => a.startsWith('--search='));
const listMode = args.includes('--list');
const addMode = args.includes('--add');

function loadIndex() {
  try {
    return JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8'));
  } catch (e) {
    return { entries: [], lastUpdated: null };
  }
}

function saveIndex(index) {
  index.lastUpdated = new Date().toISOString();
  const dir = path.dirname(INDEX_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2));
}

if (listMode) {
  const index = loadIndex();
  console.log(`\n=== LEARNING INDEX (${index.entries.length} entries) ===\n`);
  if (index.entries.length === 0) {
    console.log('  No entries yet. Use --add "title|content" to add discoveries.');
  } else {
    index.entries.forEach((e, i) => {
      console.log(`  [${i + 1}] ${e.title}`);
      console.log(`      ${e.content.slice(0, 100)}${e.content.length > 100 ? '...' : ''}`);
      console.log(`      Added: ${e.added} | Tags: ${(e.tags || []).join(', ') || 'none'}\n`);
    });
  }
  process.exit(0);
}

if (searchArg) {
  const keyword = (searchArg.split('=')[1] || '').trim().toLowerCase();
  if (!keyword) {
    console.error('Usage: node learning-index.js --search=keyword');
    process.exit(1);
  }
  const index = loadIndex();
  const matches = index.entries.filter(e =>
    e.title.toLowerCase().includes(keyword) ||
    e.content.toLowerCase().includes(keyword) ||
    (e.tags || []).some(t => t.toLowerCase().includes(keyword))
  );

  console.log(`\n=== SEARCH: "${keyword}" (${matches.length} matches) ===\n`);
  matches.forEach((e, i) => {
    console.log(`  [${i + 1}] ${e.title}`);
    console.log(`      ${e.content.slice(0, 150)}${e.content.length > 150 ? '...' : ''}\n`);
  });
  process.exit(0);
}

if (addMode) {
  const rawContent = args.slice(args.indexOf('--add') + 1).join(' ');
  const parts = rawContent.split('|');
  const title = (parts[0] || '').trim();
  const content = (parts[1] || '').trim();

  if (!title) {
    console.error('Usage: node learning-index.js --add "Title|Content description"');
    process.exit(1);
  }

  const index = loadIndex();

  // Extract tags from content (words after **What**, **Where**, etc.)
  const tags = [];
  const tagMatches = content.match(/\b(React|Next\.js|TypeScript|Tailwind|Prisma|Drizzle|Hono|Express|PostgreSQL|Supabase|Vercel|Playwright|GSAP|Zustand|Zod|Better Auth)\b/gi);
  if (tagMatches) tags.push(...[...new Set(tagMatches.map(t => t.toLowerCase()))]);

  index.entries.push({
    title,
    content: content || title,
    added: new Date().toISOString(),
    tags,
  });

  // Cap at 200 entries
  if (index.entries.length > 200) {
    index.entries = index.entries.slice(-200);
  }

  saveIndex(index);
  console.log(`Added: "${title}" (${tags.length} tags auto-extracted)`);
  process.exit(0);
}

// Default: show help
console.log(`
Learning Index — Local discovery cache for vibecoding system

Usage:
  node learning-index.js --list              List all discoveries
  node learning-index.js --search=keyword    Search discoveries
  node learning-index.js --add "Title|Content"  Add a discovery

The index complements Engram proactive saves with a fast local lookup.
Entries are auto-tagged based on technology mentions.
`);
