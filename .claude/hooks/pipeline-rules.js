#!/usr/bin/env node
/**
 * pipeline-rules.js — Hard Rules evaluator (Bloque F2.1 MVP)
 * ===========================================================
 *
 * Hook PreToolUse que evalua reglas declarativas de .claude/hard-rules.json
 * sobre tool calls de Bash. Severity:
 *   - "block" -> exit 2 (Claude Code aborta la tool call)
 *   - "warn"  -> exit 0 + mensaje en stderr (Claude Code procede)
 *
 * FAIL-OPEN ESTRICTO: cualquier error interno del hook (archivo missing,
 * JSON malformado, regex invalida, etc.) -> exit 0 silencioso. JAMAS
 * bloquear por bugs propios.
 *
 * DECISION DE FORMATO: JSON nativo (no YAML). JSON es parseable con
 * JSON.parse, sin parser custom ni dep nueva. Skills registry usa YAML
 * porque su loader es Python (PyYAML disponible). Hard rules es Node-only.
 *
 * DISABLE:
 *   ATLAS_HARD_RULES_DISABLED=1 -> hook no-op total
 *
 * BYPASS PER-RULE:
 *   Cada regla puede declarar bypass_env. Si esa env var = "1", la regla
 *   se saltea (con log informativo).
 *
 * INPUT (stdin JSON, formato Claude Code hooks):
 *   {
 *     "tool_name": "Bash",
 *     "tool_input": { "command": "...", "description": "..." },
 *     ...
 *   }
 *
 * SCOPE: por ahora solo evalua tool_name=Bash. Otras tools = exit 0.
 *
 * NO ES:
 *   - Motor de reglas custom (es predicate evaluator simple)
 *   - Audit trail formal (eso es C.5 diferido)
 *   - Reemplazo de hooks existentes (es complementario)
 */

'use strict';

const fs = require('fs');
const path = require('path');

const RULES_FILENAME = 'hard-rules.json';
const PROJECT_DIR = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const RULES_DEFAULT_PATH = path.join(PROJECT_DIR, '.claude', RULES_FILENAME);

const DISABLE_ENV = 'ATLAS_HARD_RULES_DISABLED';

const SEV_BLOCK = 'block';
const SEV_WARN = 'warn';

const EXIT_OK = 0;
const EXIT_BLOCK = 2;

// =====================================================================
//  Entry point
// =====================================================================

(async function main() {
  try {
    if (isTruthyEnv(DISABLE_ENV)) {
      process.exit(EXIT_OK);
    }

    const payload = await readStdinJSON();
    if (!payload || typeof payload !== 'object') {
      process.exit(EXIT_OK);
    }

    if (payload.tool_name !== 'Bash') {
      process.exit(EXIT_OK);
    }

    const command = (payload.tool_input && payload.tool_input.command) || '';
    if (typeof command !== 'string' || command.length === 0) {
      process.exit(EXIT_OK);
    }

    const rules = loadRules(RULES_DEFAULT_PATH);
    if (rules.length === 0) {
      process.exit(EXIT_OK);
    }

    let shouldBlock = false;
    for (const rule of rules) {
      const result = evaluateRule(rule, command);
      if (result.skipped) {
        process.stderr.write(
          `[pipeline-rules] SKIP rule=${rule.rule_id} (bypass via ${rule.bypass_env})\n`,
        );
        continue;
      }
      if (!result.matched) {
        continue;
      }
      const sev = rule.severity;
      const msg = (rule.message || '').trim() || `rule ${rule.rule_id} matched`;
      const prefix = sev === SEV_BLOCK ? 'BLOCK' : 'WARN';
      process.stderr.write(
        `[pipeline-rules] ${prefix} rule=${rule.rule_id}\n${msg}\n`,
      );
      if (sev === SEV_BLOCK) {
        shouldBlock = true;
      }
    }

    process.exit(shouldBlock ? EXIT_BLOCK : EXIT_OK);
  } catch (e) {
    try {
      process.stderr.write(
        `[pipeline-rules] internal error (fail-open): ${e && e.message || e}\n`,
      );
    } catch (_) {}
    process.exit(EXIT_OK);
  }
})();

// =====================================================================
//  Loader (JSON nativo)
// =====================================================================

function loadRules(filePath) {
  if (!fs.existsSync(filePath)) return [];
  let content;
  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch (_) {
    return [];
  }
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch (_) {
    return [];
  }
  if (!parsed || !Array.isArray(parsed.rules)) {
    return [];
  }
  return parsed.rules.filter(isValidRule);
}

function isValidRule(r) {
  if (!r || typeof r !== 'object') return false;
  if (typeof r.rule_id !== 'string') return false;
  if (r.severity !== SEV_BLOCK && r.severity !== SEV_WARN) return false;
  if (!r.predicate || typeof r.predicate !== 'object') return false;
  if (typeof r.predicate.type !== 'string') return false;
  return true;
}

// =====================================================================
//  Evaluator
// =====================================================================

function evaluateRule(rule, command) {
  if (rule.bypass_env && isTruthyEnv(rule.bypass_env)) {
    return { matched: false, skipped: true };
  }

  const predicateMatches = evaluatePredicate(rule.predicate, command);
  if (!predicateMatches) {
    return { matched: false, skipped: false };
  }

  if (!rule.condition) {
    return { matched: true, skipped: false };
  }
  const conditionMet = evaluateCondition(rule.condition);
  return { matched: conditionMet, skipped: false };
}

function evaluatePredicate(pred, command) {
  try {
    if (pred.type === 'command_match') {
      const re = new RegExp(pred.pattern, 'i');
      return re.test(command);
    }
    return false;
  } catch (_) {
    return false;
  }
}

function evaluateCondition(cond) {
  try {
    if (cond.type === 'always') {
      return true;
    }
    if (cond.type === 'file_contains') {
      const filePath = resolveProjectPath(cond.path);
      if (!fs.existsSync(filePath)) {
        return cond.invert === true ? true : false;
      }
      const content = fs.readFileSync(filePath, 'utf-8');
      const re = new RegExp(cond.must_contain_regex, 'i');
      const matches = re.test(content);
      return cond.invert === true ? !matches : matches;
    }
    if (cond.type === 'file_exists') {
      const filePath = resolveProjectPath(cond.path);
      const exists = fs.existsSync(filePath);
      return cond.invert === true ? !exists : exists;
    }
    if (cond.type === 'env_var_unset') {
      const value = process.env[cond.var_name];
      return !value;
    }
    return false;
  } catch (_) {
    return false;
  }
}

function resolveProjectPath(p) {
  if (path.isAbsolute(p)) return p;
  return path.join(PROJECT_DIR, p);
}

// =====================================================================
//  Helpers
// =====================================================================

function isTruthyEnv(name) {
  const v = process.env[name];
  if (!v) return false;
  return ['1', 'true', 'yes'].includes(String(v).toLowerCase());
}

function readStdinJSON() {
  return new Promise((resolve) => {
    let data = '';
    let resolved = false;
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve(null);
      }
    }, 1500);

    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timeout);
      if (!data.trim()) return resolve(null);
      try {
        resolve(JSON.parse(data));
      } catch (_) {
        resolve(null);
      }
    });
    process.stdin.on('error', () => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timeout);
      resolve(null);
    });
  });
}
