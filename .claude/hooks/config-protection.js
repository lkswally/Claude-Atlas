#!/usr/bin/env node
/**
 * Hook: config-protection (PreToolUse)
 * Dos niveles de proteccion:
 *   - BLOCK (exit 2): archivos de secrets/credenciales — nunca deben ser editados por agentes
 *   - WARN (exit 0 + stderr): archivos de config de linting/formatting/typescript
 *
 * Vibecoding v2.1 - Expandido con proteccion de secrets
 */

// Nivel 1: BLOCK — archivos que NUNCA deben ser editados por agentes
const BLOCKED_PATTERNS = [
  /^\.env/,              // .env, .env.local, .env.production, etc.
  /\.pem$/,              // certificados
  /\.key$/,              // private keys
  /^credentials/i,       // credentials.json, credentials.yaml, etc.
  /^\.?secrets?\./i,      // secret.json, .secret, secrets.yaml, etc.
  /secret[_-]?key/i,     // secret_key.json, secret-key.pem, etc.
  /^id_rsa/,             // SSH keys
  /^id_ed25519/,         // SSH keys (ed25519)
  /\.pfx$/,              // certificate bundles
  /\.p12$/,              // PKCS12 certificates
];

// Nivel 2: WARN — archivos de config que se pueden modificar con cuidado
const WARNED_PATTERNS = [
  /\.eslintrc/,
  /eslint\.config/,
  /\.prettierrc/,
  /prettier\.config/,
  /\.stylelintrc/,
  /stylelint\.config/,
  /tsconfig.*\.json$/,
  /biome\.json/,
  /\.editorconfig/,
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

    // Solo Write y Edit pueden modificar archivos
    if (toolName !== 'Write' && toolName !== 'Edit') process.exit(0);

    const filePath = toolInput.file_path || '';
    const fileName = filePath.split('/').pop().split('\\').pop();

    // Nivel 1: BLOCK secrets/credenciales
    for (const pattern of BLOCKED_PATTERNS) {
      if (pattern.test(fileName)) {
        process.stderr.write(
          `BLOCKED: Editing secret/credential file "${fileName}" is not allowed. ` +
          'These files contain sensitive data and must be edited manually by the user. ' +
          'Ask the user for explicit permission if this is intentional.'
        );
        process.exit(2);
      }
    }

    // Nivel 2: WARN configs de linting/formatting
    for (const pattern of WARNED_PATTERNS) {
      if (pattern.test(fileName)) {
        process.stderr.write(
          `WARNING: Modifying config file "${fileName}". ` +
          'Ensure this change does not weaken linting/formatting rules. ' +
          'Config protection is active.'
        );
        process.exit(0);
      }
    }

    process.exit(0);
  } catch (err) {
    process.exit(0);
  }
});
