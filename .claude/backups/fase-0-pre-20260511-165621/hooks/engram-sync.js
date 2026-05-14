#!/usr/bin/env node
/**
 * engram-sync.js — Sincroniza memorias de Engram con el repo remoto
 *
 * Flujo completo:
 * 1. git pull (importar cambios de otras PCs)
 * 2. engram sync --import (si hay chunks nuevos del pull)
 * 3. engram sync --all (exportar memorias nuevas como chunk)
 * 4. Copiar chunks + manifest al repo
 * 5. git add + commit + push
 *
 * Uso:
 *   node engram-sync.js              # Sync completo (pull + export + push)
 *   node engram-sync.js --export     # Solo exportar (no push)
 *   node engram-sync.js --import     # Solo importar (pull + import, no push)
 *   node engram-sync.js --status     # Mostrar estado sin hacer nada
 *   node engram-sync.js --hook       # Modo hook (stdin, silencioso, async-safe)
 *
 * Vibecoding v2.0
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOME = os.homedir();
const ENGRAM_DIR = path.join(HOME, '.engram');
// The engram tool stores chunks/manifest in a nested .engram/ subdirectory
// inside the git repo root (~/.engram/.engram/), not at the repo root itself.
const REPO_CHUNKS_DIR = path.join(ENGRAM_DIR, '.engram', 'chunks');
const REPO_MANIFEST = path.join(ENGRAM_DIR, '.engram', 'manifest.json');
const LOG_FILE = path.join(HOME, '.claude', 'snapshots', 'engram-sync.log');

const args = process.argv.slice(2);
const MODE = args.includes('--export') ? 'export'
  : args.includes('--import') ? 'import'
  : args.includes('--status') ? 'status'
  : args.includes('--hook') ? 'hook'
  : 'full';

const LOG_MAX_LINES = 2000;

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  if (MODE !== 'hook') console.log(line);
  try {
    const dir = path.dirname(LOG_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    // Atomic append-with-trim: read → append in memory → write temp → rename.
    // Evita race condition cuando varias instancias del hook corren en paralelo.
    const tmpFile = LOG_FILE + '.tmp.' + process.pid;
    try {
      let lines = [];
      if (fs.existsSync(LOG_FILE)) {
        const existing = fs.readFileSync(LOG_FILE, 'utf8').trim();
        if (existing) lines = existing.split('\n').filter(l => l.trim());
      }
      lines.push(line);
      if (lines.length > LOG_MAX_LINES) {
        lines = lines.slice(-Math.floor(LOG_MAX_LINES * 0.8));
      }
      fs.writeFileSync(tmpFile, lines.join('\n') + '\n');
      fs.renameSync(tmpFile, LOG_FILE);
    } catch (inner) {
      try { fs.unlinkSync(tmpFile); } catch (_) {}
      // Fallback: append simple si el atomic pattern falla (ej. filesystem sin rename)
      fs.appendFileSync(LOG_FILE, line + '\n');
    }
  } catch (e) {}
}

function run(cmd, opts = {}) {
  try {
    return execSync(cmd, {
      cwd: ENGRAM_DIR,
      timeout: opts.timeout || 30000,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      ...opts,
    }).trim();
  } catch (e) {
    const stderr = (e.stderr || '').toString().trim();
    const stdout = (e.stdout || '').toString().trim();
    if (opts.allowFail) return stdout || stderr || '';
    throw new Error(`Command failed: ${cmd}\n${stderr || stdout}`);
  }
}

function isGitRepo() {
  return fs.existsSync(path.join(ENGRAM_DIR, '.git'));
}

function getLocalChunkHashes() {
  if (!fs.existsSync(REPO_CHUNKS_DIR)) return [];
  return fs.readdirSync(REPO_CHUNKS_DIR)
    .filter(f => f.endsWith('.jsonl.gz'))
    .map(f => f.replace('.jsonl.gz', ''));
}

function getManifestChunks() {
  if (!fs.existsSync(REPO_MANIFEST)) return [];
  try {
    return JSON.parse(fs.readFileSync(REPO_MANIFEST, 'utf8')).chunks || [];
  } catch (e) { return []; }
}

// ============================================================
// STEP 1: Git Pull (import remote changes)
// Windows workaround: engram.db may be locked by the running engram process
// and may exist in old commits. We fetch + checkout only .engram/ files.
// ============================================================
function gitPull() {
  log('Pulling remote changes...');
  try {
    // Fetch first
    run('git fetch origin', { allowFail: true, timeout: 20000 });

    // Check if behind
    const localHead = run('git rev-parse HEAD', { allowFail: true });
    const remoteHead = run('git rev-parse origin/main', { allowFail: true });

    if (localHead === remoteHead) {
      log('Already up to date with remote.');
      return false;
    }

    // Try normal pull first
    const result = run('git pull --rebase origin main', { allowFail: true, timeout: 20000 });

    if (result.includes('unable to unlink') || result.includes('Could not reset')) {
      // engram.db lock issue — checkout only the files we need
      log('DB lock detected, using selective checkout...');
      run('git checkout origin/main -- .engram/', { allowFail: true });
      // Try to get other safe files
      run('git checkout origin/main -- README.md .gitignore', { allowFail: true });
      // Update branch ref to remote without touching working tree
      run('git reset --soft origin/main', { allowFail: true });
      log('Selective checkout complete (skipped locked engram.db).');
      return true;
    }

    if (result.includes('Already up to date')) {
      log('Already up to date with remote.');
      return false;
    }

    log(`Pulled: ${result.split('\n')[0]}`);
    return true;
  } catch (e) {
    log(`Pull failed (will continue): ${e.message.split('\n')[0]}`);
    return false;
  }
}

// ============================================================
// STEP 2: Import chunks from pull
// ============================================================
function engramImport() {
  log('Importing new chunks into local DB...');
  try {
    const result = run('engram sync --import', { allowFail: true, timeout: 15000 });
    log(`Import: ${result || 'done'}`);
    return true;
  } catch (e) {
    log(`Import failed: ${e.message.split('\n')[0]}`);
    return false;
  }
}

// ============================================================
// STEP 3: Export new memories as chunk
// ============================================================
function engramExport() {
  log('Exporting new memories...');
  try {
    const result = run('engram sync --all', { timeout: 30000 });
    log(`Export: ${result || 'done'}`);

    // Check if new chunks were created (REPO_CHUNKS_DIR: ~/.engram/chunks)
    if (!fs.existsSync(REPO_CHUNKS_DIR)) {
      // Chunks directory not found — export may have stored elsewhere
      return true;
    }
    return true;
  } catch (e) {
    log(`Export failed: ${e.message.split('\n')[0]}`);
    return false;
  }
}

// ============================================================
// STEP 4: Git add + commit + push
// ============================================================
function gitCommitAndPush() {
  // Check if there are changes to commit
  const status = run('git status --porcelain', { allowFail: true });
  if (!status.trim()) {
    log('No new changes to sync.');
    return false;
  }

  log(`Changes detected:\n${status}`);

  // Get stats for commit message
  const manifest = getManifestChunks();
  const totalMemories = manifest.reduce((sum, c) => sum + (c.memories || 0), 0);
  const totalChunks = manifest.length;
  const pcName = os.hostname();
  const date = new Date().toISOString().split('T')[0];

  // Stage .engram/ directory only (never engram.db)
  run('git add .engram/', { allowFail: true });

  // Verify something is staged
  const staged = run('git diff --cached --stat', { allowFail: true });
  if (!staged.trim()) {
    log('Nothing staged after git add.');
    return false;
  }

  // Count new memories since last commit
  const diffFiles = run('git diff --cached --name-only', { allowFail: true });
  const newChunks = diffFiles.split('\n').filter(f => f.includes('.jsonl.gz')).length;

  const commitMsg = `sync: auto-sync from ${pcName} (${date})

${newChunks} new chunk(s), ${totalChunks} total chunks, ${totalMemories} total memories

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`;

  try {
    // Write commit msg to temp file to avoid shell quoting issues
    const tmpMsg = path.join(os.tmpdir(), '.engram-commit-msg.txt');
    fs.writeFileSync(tmpMsg, commitMsg);
    run(`git commit -F "${tmpMsg}"`, { timeout: 10000 });
    fs.unlinkSync(tmpMsg);
    log('Committed successfully.');
  } catch (e) {
    log(`Commit failed: ${e.message.split('\n')[0]}`);
    return false;
  }

  // Push — with one pull-retry if rejected (handles two-PC race condition)
  try {
    log('Pushing to remote...');
    const pushResult = run('git push origin main', { timeout: 30000 });
    log(`Pushed: ${pushResult || 'success'}`);
    return true;
  } catch (e) {
    log(`Push failed: ${e.message.split('\n')[0]}`);
    log('Retrying: pull --rebase then push...');
    try {
      // Another PC may have pushed between our commit and push — rebase on top
      const pullResult = run('git pull --rebase origin main', { allowFail: true, timeout: 20000 });
      if (pullResult.includes('unable to unlink') || pullResult.includes('Could not reset')) {
        // DB still locked — selective checkout fallback
        log('DB lock on retry, using selective checkout...');
        run('git checkout origin/main -- .engram/', { allowFail: true });
        run('git reset --soft origin/main', { allowFail: true });
      } else {
        log(`Rebased: ${pullResult.split('\n')[0]}`);
      }
      const retryResult = run('git push origin main', { timeout: 30000 });
      log(`Pushed (after retry): ${retryResult || 'success'}`);
      return true;
    } catch (e2) {
      log(`Push failed after retry: ${e2.message.split('\n')[0]}`);
      log('Commit saved locally — will push on next session.');
      return false;
    }
  }
}

// ============================================================
// STATUS: Show current state
// ============================================================
function showStatus() {
  console.log('\n=== ENGRAM SYNC STATUS ===\n');

  if (!isGitRepo()) {
    console.log('ERROR: ~/.engram is not a git repository');
    process.exit(1);
  }

  // Git status
  const gitStatus = run('git status --short', { allowFail: true });
  const branch = run('git branch --show-current', { allowFail: true });
  console.log(`Branch: ${branch}`);
  console.log(`Uncommitted changes: ${gitStatus ? gitStatus.split('\n').length : 0}`);

  // Engram stats
  const stats = run('engram sync --status', { allowFail: true });
  console.log(`\nEngram sync status:\n${stats}`);

  // Manifest
  const chunks = getManifestChunks();
  const totalMem = chunks.reduce((s, c) => s + (c.memories || 0), 0);
  console.log(`\nManifest: ${chunks.length} chunks, ${totalMem} memories`);
  if (chunks.length > 0) {
    const latest = chunks[chunks.length - 1];
    console.log(`Latest chunk: ${latest.id} by ${latest.created_by} (${latest.created_at})`);
  }

  // Local DB
  const dbStats = run('engram stats', { allowFail: true });
  console.log(`\nLocal DB:\n${dbStats}`);

  // Log tail
  if (fs.existsSync(LOG_FILE)) {
    const logLines = fs.readFileSync(LOG_FILE, 'utf8').trim().split('\n');
    console.log(`\nLast 5 sync events:`);
    logLines.slice(-5).forEach(l => console.log(`  ${l}`));
  }

  console.log('');
}

// ============================================================
// MAIN
// ============================================================
function main() {
  if (!isGitRepo()) {
    log('ERROR: ~/.engram is not a git repository. Cannot sync.');
    process.exit(1);
  }

  if (MODE === 'status') {
    showStatus();
    return;
  }

  if (MODE === 'import') {
    try {
      gitPull();
      engramImport();
      log('Import complete.');
    } catch (e) {
      log(`Import error: ${e.message}`);
      process.exit(1);
    }
    return;
  }

  if (MODE === 'export') {
    try {
      engramExport();
      log('Export complete (not pushed).');
    } catch (e) {
      log(`Export error: ${e.message}`);
      process.exit(1);
    }
    return;
  }

  if (MODE === 'hook') {
    // Consume stdin (hook protocol) then run silently
    let input = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { input += chunk; });
    process.stdin.on('end', () => {
      try {
        gitPull();
        engramImport();
        engramExport();
        gitCommitAndPush();
        log('Auto-sync complete.');
      } catch (e) {
        log(`Auto-sync error: ${e.message}`);
      }
      process.exit(0);
    });
    return;
  }

  // MODE === 'full'
  try {
    log('=== Starting full sync ===');
    gitPull();
    engramImport();
    engramExport();
    gitCommitAndPush();
    log('=== Sync complete ===');
  } catch (e) {
    log(`Full sync error: ${e.message}`);
    process.exit(1);
  }
}

main();
