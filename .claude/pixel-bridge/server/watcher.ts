import { watch } from "chokidar";
import { statSync, readdirSync, openSync, readSync, closeSync, readFileSync } from "fs";
import { join, basename, dirname } from "path";
import { homedir } from "os";
import { EventEmitter } from "events";

const CLAUDE_PROJECTS_DIR = join(homedir(), ".claude", "projects");
const ACTIVE_THRESHOLD_MS = 600_000; // 10 minutes — Claude can think for 5+ min without writing
const POLL_INTERVAL_MS = 1000;

export interface WatchedFile {
  path: string;
  sessionId: string;
  projectName: string;
  agentName: string; // extracted from metadata line, empty if unknown
  offset: number;
  lineBuffer: string;
}

export class JsonlWatcher extends EventEmitter {
  private files = new Map<string, WatchedFile>();
  private watcher: ReturnType<typeof watch> | null = null;
  private pollInterval: ReturnType<typeof setInterval> | null = null;

  start(): void {
    this.scanForActiveFiles();

    this.watcher = watch(CLAUDE_PROJECTS_DIR, {
      ignoreInitial: true,
      depth: 3,
      usePolling: true,
      interval: 1000,
    });

    this.watcher.on("add", (filePath: string) => {
      if (filePath.endsWith(".jsonl")) {
        this.addFile(filePath);
      }
    });

    // When a file is deleted, remove it from tracking so a subsequent
    // "add" (recreate) is handled cleanly with offset reset to 0.
    this.watcher.on("unlink", (filePath: string) => {
      const file = this.files.get(filePath);
      if (file) {
        this.files.delete(filePath);
        this.emit("fileRemoved", file);
      }
    });

    this.pollInterval = setInterval(() => this.pollFiles(), POLL_INTERVAL_MS);
  }

  stop(): void {
    this.watcher?.close();
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  private scanForActiveFiles(): void {
    try {
      const dirs = readdirSync(CLAUDE_PROJECTS_DIR, { withFileTypes: true });
      for (const dir of dirs) {
        if (!dir.isDirectory()) continue;
        const dirPath = join(CLAUDE_PROJECTS_DIR, dir.name);
        try {
          this.scanDirectory(dirPath, 0);
        } catch {
          /* skip unreadable dirs */
        }
      }
    } catch {
      /* projects dir may not exist */
    }
  }

  // Recursive scan up to depth 3 (matching chokidar depth)
  private scanDirectory(dirPath: string, depth: number): void {
    if (depth > 3) return;
    try {
      const entries = readdirSync(dirPath, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = join(dirPath, entry.name);
        if (entry.isFile() && entry.name.endsWith(".jsonl")) {
          try {
            const stat = statSync(fullPath);
            if (Date.now() - stat.mtimeMs < ACTIVE_THRESHOLD_MS) {
              this.addFile(fullPath);
            }
          } catch { /* skip */ }
        } else if (entry.isDirectory() && depth < 3) {
          this.scanDirectory(fullPath, depth + 1);
        }
      }
    } catch { /* skip unreadable */ }
  }

  // Try to extract agent_name from the first line of a JSONL file
  // bridge.js writes: {"type":"metadata","agent_name":"frontend_developer","session_id":"..."}
  private extractAgentName(filePath: string): string {
    try {
      const fd = openSync(filePath, "r");
      // Read first 512 bytes — metadata line is short
      const buf = Buffer.alloc(512);
      const bytesRead = readSync(fd, buf, 0, 512, 0);
      closeSync(fd);
      if (bytesRead === 0) return "";

      const text = buf.toString("utf-8", 0, bytesRead);
      const firstLine = text.split("\n")[0];
      if (!firstLine) return "";

      const parsed = JSON.parse(firstLine);
      if (parsed.type === "metadata" && parsed.agent_name) {
        return parsed.agent_name;
      }
    } catch {
      /* not a metadata line or file unreadable */
    }
    return "";
  }

  // Extract agent name from filename pattern: {agent_name}-px.jsonl
  private extractAgentNameFromFilename(filename: string): string {
    if (filename.endsWith("-px.jsonl")) {
      return filename.replace(/-px\.jsonl$/, "");
    }
    return "";
  }

  private addFile(filePath: string): void {
    if (this.files.has(filePath)) return;

    const filename = basename(filePath);
    const sessionId = basename(filePath, ".jsonl");

    // Try to identify the agent:
    // 1. From filename pattern (agent_name-px.jsonl)
    // 2. From first-line metadata in the file
    // 3. Fallback to directory-based extraction (legacy behavior)
    let agentName = this.extractAgentNameFromFilename(filename);
    if (!agentName) {
      agentName = this.extractAgentName(filePath);
    }

    // projectName: use agentName if found, otherwise extract from directory (legacy)
    let projectName = agentName;
    if (!projectName) {
      const projectDirName = basename(dirname(filePath));
      const parts = projectDirName.split("-").filter(Boolean);
      projectName = sessionId.slice(0, 8);
      for (let i = parts.length - 1; i >= 0; i--) {
        if (!/^\d+$/.test(parts[i])) {
          projectName = parts[i];
          break;
        }
      }
    }

    const file: WatchedFile = {
      path: filePath,
      sessionId,
      projectName,
      agentName,
      offset: 0,
      lineBuffer: "",
    };

    this.files.set(filePath, file);
    this.emit("fileAdded", file);

    // Read existing content to catch up
    this.readNewLines(file);
  }

  private pollFiles(): void {
    for (const [path, file] of this.files) {
      try {
        const stat = statSync(path);
        if (stat.size > file.offset) {
          this.readNewLines(file);
        }
        // Remove stale files
        if (Date.now() - stat.mtimeMs > ACTIVE_THRESHOLD_MS) {
          this.files.delete(path);
          this.emit("fileRemoved", file);
        }
      } catch {
        this.files.delete(path);
        this.emit("fileRemoved", file);
      }
    }
  }

  private readNewLines(file: WatchedFile): void {
    try {
      const stat = statSync(file.path);
      if (stat.size <= file.offset) return;

      const buf = Buffer.alloc(stat.size - file.offset);
      const fd = openSync(file.path, "r");
      readSync(fd, buf, 0, buf.length, file.offset);
      closeSync(fd);

      file.offset = stat.size;
      const text = file.lineBuffer + buf.toString("utf-8");
      const lines = text.split("\n");

      // Last element is incomplete line (buffer it)
      file.lineBuffer = lines.pop() || "";

      for (const line of lines) {
        if (line.trim()) {
          // Skip metadata lines — already processed during addFile
          try {
            const parsed = JSON.parse(line);
            if (parsed.type === "metadata") continue;
          } catch { /* not JSON, emit anyway */ }

          this.emit("line", file, line);
        }
      }
    } catch {
      /* file may have been deleted */
    }
  }

  getActiveFiles(): WatchedFile[] {
    return Array.from(this.files.values());
  }
}
