#!/usr/bin/env node
/**
 * QA Auto-Audit Hook (Bloque 1K.1)
 * ==================================
 *
 * PostToolUse hook que, cuando un Agent (subagent spawn) termina, audita
 * automaticamente si los helpers obligatorios del dispatcher fueron
 * invocados durante esa sesion para ese tipo de subagente.
 *
 * Si faltan invocaciones criticas, emite WARN en stderr para que el
 * agente principal lo vea. NO bloquea — es advisory.
 *
 * INPUT (stdin JSON):
 *   {
 *     "tool_name": "Agent" | "Task",
 *     "tool_input": {"subagent_type": "evidence-collector", ...},
 *     "cwd": "C:\\path\\to\\project"
 *   }
 *
 * FLOW:
 *   1. Solo procesar si tool_name in {"Agent", "Task"}
 *   2. Extraer subagent_type de tool_input
 *   3. Invocar `python tools/atlas_dispatcher.py audit-agent --agent=TYPE`
 *   4. Si exit_code=1 (incomplete) -> emitir WARN en stderr con missing helpers
 *   5. Exit 0 SIEMPRE (fail-open: no bloquea el flujo)
 */

const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

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
    process.exit(0);  // input malformado, fail-open
  }

  const toolName = payload.tool_name || payload.toolName;
  const toolInput = payload.tool_input || payload.toolInput || {};
  const cwd = payload.cwd || process.cwd();

  // Solo procesar Agent/Task tool calls
  if (toolName !== "Agent" && toolName !== "Task") {
    process.exit(0);
  }

  // Extraer subagent_type
  const agentType = toolInput.subagent_type || toolInput.subagentType;
  if (!agentType) {
    process.exit(0);  // sin tipo, no podemos auditar
  }

  // Resolver path del dispatcher
  const normalizedCwd = path.normalize(cwd);
  const dispatcherPath = path.join(normalizedCwd, "tools", "atlas_dispatcher.py");
  if (!fs.existsSync(dispatcherPath)) {
    process.exit(0);  // proyecto sin dispatcher, fail-open
  }

  // Detectar python (Windows vs Unix)
  const pythonCmd = process.platform === "win32" ? "python" : "python3";

  // Invocar audit-agent
  const result = spawnSync(pythonCmd, [
    dispatcherPath,
    "audit-agent",
    `--agent=${agentType}`,
    "--since=600",
  ], {
    cwd: normalizedCwd,
    timeout: 5000,  // 5s max
    encoding: "utf-8",
    shell: true,
  });

  if (result.error) {
    // Error invocando subprocess, fail-open
    process.exit(0);
  }

  // Si exit_code = 1 (incomplete), parsear output y emitir WARN
  if (result.status === 1) {
    try {
      const audit = JSON.parse(result.stdout);
      const missing = audit.missing || [];
      if (missing.length > 0) {
        const message =
          `[qa-auto-audit] WARN: subagente '${agentType}' termino sin invocar ` +
          `helpers obligatorios: ${missing.join(", ")}. ` +
          `Considerar invocar manualmente via dispatcher en el siguiente paso.`;
        process.stderr.write(message + "\n");
      }
    } catch (e) {
      // Output no parseable, ignorar
    }
  }

  // SIEMPRE exit 0 — hook es advisory, no bloquea
  process.exit(0);
}

main();
