#!/usr/bin/env node
/**
 * Hook: block-dangerous (PreToolUse)
 * Bloquea comandos destructivos: git bypasses, rm -rf, DROP TABLE, etc.
 * Exit 2 = BLOCK, Exit 0 = ALLOW
 *
 * Vibecoding v2.1 - Expandido con patrones destructivos
 */

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

    // Solo nos interesa Bash
    if (toolName !== 'Bash') process.exit(0);

    const command = toolInput.command || '';

    // Detectar --no-verify en git commit o git push
    if (/git\s+(commit|push)\s+.*--no-verify/.test(command)) {
      process.stderr.write(
        'BLOCKED: --no-verify detected. Hooks exist for a reason. ' +
        'If you really need this, ask the user for explicit permission.'
      );
      process.exit(2);
    }

    // Detectar --no-gpg-sign (tambien peligroso si hay signing configurado)
    if (/git\s+(commit|tag)\s+.*--no-gpg-sign/.test(command)) {
      process.stderr.write(
        'BLOCKED: --no-gpg-sign detected. ' +
        'If you need to skip GPG signing, ask the user for explicit permission.'
      );
      process.exit(2);
    }

    // Detectar rm -rf con paths peligrosos (/, ~, ., ..)
    if (/\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|.*-rf\s+|.*-fr\s+)(\/|~|\.\.|\.(?:\s|$))/.test(command) ||
        /\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+|.*-rf\s+|.*-fr\s+)\*/.test(command)) {
      process.stderr.write(
        'BLOCKED: Destructive rm command detected (rm -rf on root, home, or wildcard). ' +
        'Ask the user for explicit permission before deleting.'
      );
      process.exit(2);
    }

    // Detectar git reset --hard
    if (/git\s+reset\s+--hard/.test(command)) {
      process.stderr.write(
        'BLOCKED: git reset --hard detected. This discards uncommitted changes permanently. ' +
        'Ask the user for explicit permission.'
      );
      process.exit(2);
    }

    // Detectar git clean -fd (borra archivos untracked)
    if (/git\s+clean\s+(-[a-zA-Z]*f|-f)/.test(command)) {
      process.stderr.write(
        'BLOCKED: git clean -f detected. This deletes untracked files permanently. ' +
        'Ask the user for explicit permission.'
      );
      process.exit(2);
    }

    // Detectar DROP TABLE / DROP DATABASE
    if (/\b(DROP\s+(TABLE|DATABASE|SCHEMA))\b/i.test(command)) {
      process.stderr.write(
        'BLOCKED: DROP TABLE/DATABASE detected. This is irreversible. ' +
        'Ask the user for explicit permission.'
      );
      process.exit(2);
    }

    // Detectar chmod 777 (permisos excesivos)
    if (/\bchmod\s+777\b/.test(command)) {
      process.stderr.write(
        'BLOCKED: chmod 777 detected. This grants full permissions to everyone. ' +
        'Use more restrictive permissions (e.g., 755). Ask the user if 777 is intended.'
      );
      process.exit(2);
    }

    // Detectar curl|sh / wget|bash (ejecucion remota sin inspeccion)
    if (/\b(curl|wget)\s+.*\|\s*(sh|bash|zsh|node|python)/.test(command)) {
      process.stderr.write(
        'BLOCKED: Piping remote content directly to shell detected. ' +
        'Download and inspect the script first. Ask the user for explicit permission.'
      );
      process.exit(2);
    }

    process.exit(0);
  } catch (err) {
    // Fail-open: en caso de error, permitir (no romper el flujo)
    process.exit(0);
  }
});
