#!/usr/bin/env node
/**
 * Delegation Tracker Hook (Bloque 1D.1)
 * =====================================
 *
 * PostToolUse hook que registra el tool call en el tracker Python.
 *
 * Recibe stdin con JSON:
 *   {
 *     "tool_name": "Read|Edit|Write|Agent|...",
 *     "tool_input": { ... },
 *     "cwd": "C:\\path\\to\\project"
 *   }
 *
 * Llama a `python tools/delegation_tracker.py record` con los args.
 * Fail-open: si el subprocess falla, no rompemos el flujo del agente.
 *
 * Si hay warnings activos (escalation, pause, fresh_review), los emite
 * por stderr para que el agente los vea, pero NO bloquea.
 */

const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// Leer stdin (hook input)
function readStdin() {
  try {
    return fs.readFileSync(0, "utf-8");
  } catch (e) {
    return "";
  }
}

function main() {
  const rawInput = readStdin();
  let payload;
  try {
    payload = JSON.parse(rawInput);
  } catch (e) {
    // Input malformado — fail-open silencioso
    process.exit(0);
  }

  const toolName = payload.tool_name || payload.toolName;
  const toolInput = payload.tool_input || payload.toolInput || {};
  const cwd = payload.cwd || process.cwd();

  if (!toolName) {
    // Sin tool_name no hay nada que registrar — fail-open
    process.exit(0);
  }

  // Normalizar cwd (Claude Code puede pasar paths con backslash o forward slash)
  // Usamos path.normalize para que path.join use el separador correcto del OS
  const normalizedCwd = path.normalize(cwd);

  // Resolver path del tracker (relativo al cwd del proyecto)
  const trackerPath = path.join(normalizedCwd, "tools", "delegation_tracker.py");
  if (!fs.existsSync(trackerPath)) {
    // Si el proyecto no tiene tracker, no hacer nada
    process.exit(0);
  }

  // Construir args: --tool=NAME [--file=PATH]
  const args = [trackerPath, "record", `--tool=${toolName}`];
  const filePath = toolInput.file_path || toolInput.notebook_path;
  if (filePath) {
    args.push(`--file=${filePath}`);
  }

  // Detectar python ejecutable (Windows vs Unix)
  const pythonCmd = process.platform === "win32" ? "python" : "python3";

  // Ejecutar tracker como subprocess.
  // shell: true es importante para que el PATH del sistema se use (Windows
  // a veces no resuelve "python" sin shell).
  const result = spawnSync(pythonCmd, args, {
    cwd: normalizedCwd,
    timeout: 3000,  // 3s max — fail-open si tarda demasiado
    encoding: "utf-8",
    shell: true,
  });

  // Fail-open: si el subprocess falla por cualquier razon, exit 0
  if (result.error || result.status !== 0) {
    process.exit(0);
  }

  // Si hubo warnings (vienen por stderr del tracker), reenviarlos
  if (result.stderr && result.stderr.trim()) {
    process.stderr.write(result.stderr);
  }

  // Exit 0 — nunca bloquea
  process.exit(0);
}

main();
