#!/bin/bash
# Pixel Bridge — Auto-start script
# Called by SessionStart hook or manually
# Starts the standalone server if not already running

PIXEL_DIR="$HOME/.claude/pixel-bridge/standalone"
PID_FILE="$HOME/.pixel-agents/server.pid"
LOG_FILE="$HOME/.pixel-agents/server.log"
PORT="${PIXEL_BRIDGE_PORT:-3456}"

mkdir -p "$HOME/.pixel-agents"

# Check if already running
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    # Already running, nothing to do
    exit 0
  fi
  # Stale PID file, clean up
  rm -f "$PID_FILE"
fi

# Check if port is in use (another instance)
if command -v lsof &>/dev/null; then
  if lsof -i ":$PORT" &>/dev/null; then
    exit 0
  fi
elif command -v netstat &>/dev/null; then
  if netstat -ano 2>/dev/null | grep -q ":$PORT.*LISTEN"; then
    exit 0
  fi
fi

# Check if dist/server.js exists
if [ ! -f "$PIXEL_DIR/dist/server.js" ]; then
  echo "[pixel-bridge] dist/server.js not found, skipping auto-start" >&2
  exit 0
fi

# Start server in background
cd "$PIXEL_DIR"
nohup node dist/server.js >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

exit 0
