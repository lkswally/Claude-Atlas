#!/usr/bin/env node
/**
 * Pixel Bridge — Claude Code Hooks → Pixel Agents JSONL
 *
 * Reads Claude Code hook JSON from stdin.
 * Writes synthetic flat JSONL files so Pixel Agents shows
 * one animated character per agent (including subagents).
 *
 * Hook events handled: PreToolUse, PostToolUse, Stop
 *
 * Key fixes:
 * - Writes agent_name into JSONL metadata so watcher can identify permanent agents
 * - Uses deterministic toolId (hash of session+tool+timestamp) persisted via temp file
 *   so PostToolUse matches PreToolUse
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// Temp dir for persisting toolIds between Pre/Post invocations
const TOOL_ID_DIR = path.join(os.tmpdir(), 'pixel-bridge-tools');

let input = '';
process.stdin.on('data', chunk => (input += chunk));
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const { hook_event_name, session_id, tool_name, tool_input, transcript_path } = data;

    if (!session_id || !transcript_path) return;

    // transcript_path may use Unix-style (/c/Users/...) or Windows (C:\Users\...)
    const normalizedPath = transcript_path.replace(/\\/g, '/');
    const projectMatch = normalizedPath.match(/projects\/([^\/]+)/);
    if (!projectMatch) return;
    const projectFolder = projectMatch[1];

    const projectDir = path.join(os.homedir(), '.claude', 'projects', projectFolder);

    const isSubagent = normalizedPath.includes('/subagents/');
    const isDesktopManual = session_id.startsWith('desktop-');

    // Main sessions already have a real JSONL that Pixel Agents reads.
    // Only bridge subagents and manual Desktop sessions.
    if (!isSubagent && !isDesktopManual) return;

    // Extract agent name from the subagent session path
    // Pattern: .../projects/{project}/subagents/{session_id}/...
    // The agent_type comes from Claude Code's spawn — we extract it from tool_input
    // or from the session metadata. For subagents, Claude Code passes the agent type
    // in the hook data under tool_input.subagent_type or we derive from session context.
    let agentName = '';
    if (data.tool_input && data.tool_input.subagent_type) {
      agentName = data.tool_input.subagent_type;
    } else if (data.agent_type) {
      agentName = data.agent_type;
    } else if (data.subagent_type) {
      agentName = data.subagent_type;
    }
    // Normalize: hyphens to underscores, lowercase
    agentName = agentName.toLowerCase().replace(/-/g, '_');

    // Bridge file: named by agent name if available, otherwise session_id
    // Using agent name allows watcher to match permanent agents
    const filePrefix = agentName || session_id;
    const bridgeFile = path.join(projectDir, `${filePrefix}-px.jsonl`);

    // Write agent_name as first line metadata if file is new
    if (agentName && !fs.existsSync(bridgeFile)) {
      fs.mkdirSync(projectDir, { recursive: true });
      const meta = { type: 'metadata', agent_name: agentName, session_id: session_id };
      fs.appendFileSync(bridgeFile, JSON.stringify(meta) + '\n');
    }

    if (hook_event_name === 'PreToolUse') {
      // Generate toolId and persist it for the matching PostToolUse
      const toolId = `tu-${Date.now()}-${crypto.randomBytes(3).toString('hex')}`;

      // Save toolId mapped to session+tool for PostToolUse to find
      try {
        fs.mkdirSync(TOOL_ID_DIR, { recursive: true });
        const toolIdFile = path.join(TOOL_ID_DIR, `${session_id}-latest.txt`);
        fs.writeFileSync(toolIdFile, toolId);
      } catch (_) { /* best effort */ }

      const filePath =
        tool_input?.file_path ||
        tool_input?.command ||
        tool_input?.query ||
        tool_input?.pattern ||
        tool_input?.description ||
        '';

      const entry = {
        type: 'assistant',
        message: {
          content: [{
            type: 'tool_use',
            id: toolId,
            name: tool_name,
            input: { file_path: String(filePath).slice(0, 200) },
          }],
        },
      };

      fs.mkdirSync(projectDir, { recursive: true });
      fs.appendFileSync(bridgeFile, JSON.stringify(entry) + '\n');

    } else if (hook_event_name === 'PostToolUse') {
      // Retrieve the toolId from the matching PreToolUse
      let toolId = `tu-fallback-${Date.now()}`;
      try {
        const toolIdFile = path.join(TOOL_ID_DIR, `${session_id}-latest.txt`);
        if (fs.existsSync(toolIdFile)) {
          toolId = fs.readFileSync(toolIdFile, 'utf-8').trim();
          fs.unlinkSync(toolIdFile); // Clean up
        }
      } catch (_) { /* use fallback */ }

      const entry = {
        type: 'user',
        message: {
          content: [{ type: 'tool_result', tool_use_id: toolId, content: 'ok' }],
        },
      };
      fs.appendFileSync(bridgeFile, JSON.stringify(entry) + '\n');

    } else if (hook_event_name === 'Stop') {
      const entry = { type: 'system', subtype: 'turn_duration', duration_ms: 1000 };
      fs.appendFileSync(bridgeFile, JSON.stringify(entry) + '\n');

      // Clean up any leftover toolId files for this session
      try {
        const toolIdFile = path.join(TOOL_ID_DIR, `${session_id}-latest.txt`);
        if (fs.existsSync(toolIdFile)) fs.unlinkSync(toolIdFile);
      } catch (_) { /* best effort */ }
    }

  } catch (_) {
    // Never block Claude on bridge errors
  }
});
