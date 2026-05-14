import { watch } from "chokidar";
import { statSync, readdirSync, openSync, readSync, closeSync } from "fs";
import { join, basename } from "path";
import { homedir } from "os";
import { EventEmitter } from "events";

const WATCH_DIR = join(homedir(), ".claude", "projects", "reyesoft-os", "sessions");
const PROJECT_NAME = "reyesoft-os";
const ACTIVE_THRESHOLD_MS = 600_000; // 10 minutes — Claude can think for 5+ min without writing
const POLL_INTERVAL_MS = 1000;

export interface WatchedFile {
  path: string;
  sessionId: string;
  projectName: string;
  offset: number;
  lineBuffer: string;
}

export class JsonlWatcher extends EventEmitter {
  private files = new Map<string, WatchedFile>();
  private watcher: ReturnType<typeof watch> | null = null;
  private pollInterval: ReturnType<typeof setInterval> | null = null;

  start(): void {
    this.scanForActiveFiles();

    this.watcher = watch(WATCH_DIR, {
      ignoreInitial: true,
      depth: 0,
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
      const files = readdirSync(WATCH_DIR);
      for (const f of files) {
        if (!f.endsWith(".jsonl")) continue;
        const filePath = join(WATCH_DIR, f);
        const stat = statSync(filePath);
        if (Date.now() - stat.mtimeMs < ACTIVE_THRESHOLD_MS) {
          this.addFile(filePath);
        }
      }
    } catch {
      /* sessions dir may not exist */
    }
  }

  private addFile(filePath: string): void {
    if (this.files.has(filePath)) return;

    const sessionId = basename(filePath, ".jsonl");
    const normalized = sessionId.toLowerCase();
    const projectName = normalized === PROJECT_NAME ? "orquestador" : normalized;

    const file: WatchedFile = {
      path: filePath,
      sessionId,
      projectName,
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
