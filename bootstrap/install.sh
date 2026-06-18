#!/usr/bin/env bash
# ATLAS Bootstrap — Linux / macOS
# Verifies prerequisites and configures ATLAS.
#
# Usage:
#   bash bootstrap/install.sh

set -euo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
ISSUES=()

GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
CYAN='\033[36m'
RESET='\033[0m'

pass() { PASS_COUNT=$((PASS_COUNT+1)); echo -e "  ${GREEN}[PASS]${RESET} $1"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); ISSUES+=("WARN: $1"); echo -e "  ${YELLOW}[WARN]${RESET} $1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); ISSUES+=("FAIL: $1"); echo -e "  ${RED}[FAIL]${RESET} $1"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ""
echo -e "${CYAN}======================================${RESET}"
echo -e "${CYAN}  ATLAS Bootstrap — Linux/macOS${RESET}"
echo -e "${CYAN}======================================${RESET}"
echo ""
echo "Checking prerequisites..."

# --- Python ---
if command -v python3 &>/dev/null; then
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYMAJOR=$(echo "$PYVER" | cut -d. -f1)
    PYMINOR=$(echo "$PYVER" | cut -d. -f2)
    if [ "$PYMAJOR" -ge 3 ] && [ "$PYMINOR" -ge 11 ]; then
        pass "Python $PYVER"
    else
        fail "Python $PYVER — need 3.11+. Install from https://python.org"
    fi
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    pass "Python $PYVER"
    PYTHON=python
else
    fail "Python not found. Install from https://python.org"
    PYTHON=python3
fi

# --- Node.js ---
if command -v node &>/dev/null; then
    NODEVER=$(node --version)
    NODEMAJOR=$(echo "$NODEVER" | tr -d 'v' | cut -d. -f1)
    if [ "$NODEMAJOR" -ge 18 ]; then
        pass "Node.js $NODEVER"
    else
        fail "Node.js $NODEVER — need 18+. Install from https://nodejs.org"
    fi
else
    fail "Node.js not found. Install from https://nodejs.org"
fi

# --- Git ---
if command -v git &>/dev/null; then
    pass "Git: $(git --version)"
else
    fail "Git not found. Install via package manager"
fi

# --- Go ---
if command -v go &>/dev/null; then
    pass "Go: $(go version)"
else
    warn "Go not found (required for Engram binary). Install from https://go.dev"
fi

# --- Claude ---
if command -v claude &>/dev/null; then
    pass "Claude CLI found: $(which claude)"
else
    warn "Claude CLI not found. Install Claude Desktop from https://claude.ai/download"
fi

echo ""
echo "Checking Python packages..."

# --- PyYAML ---
if $PYTHON -c "import yaml" &>/dev/null 2>&1; then
    pass "PyYAML available"
else
    echo "  Installing PyYAML..."
    pip3 install pyyaml -q
    pass "PyYAML installed"
fi

# --- Playwright ---
if $PYTHON -c "import playwright" &>/dev/null 2>&1; then
    pass "Playwright Python package available"
else
    echo "  Installing Playwright..."
    pip3 install playwright -q
    $PYTHON -m playwright install chromium --with-deps &>/dev/null
    pass "Playwright installed"
fi

echo ""
echo "Checking ATLAS configuration..."

# --- .mcp.json ---
MCP_PATH="$PROJECT_ROOT/.mcp.json"
if [ -f "$MCP_PATH" ]; then
    if $PYTHON -c "import json; json.load(open('$MCP_PATH'))" &>/dev/null 2>&1; then
        pass ".mcp.json valid"
    else
        fail ".mcp.json invalid JSON"
    fi
else
    warn ".mcp.json not found — MCP servers will not be available"
fi

# --- Engram ---
ENGRAM_PATH="$HOME/.engram/engram"
if [ -f "$ENGRAM_PATH" ]; then
    pass "Engram binary: $ENGRAM_PATH"
elif command -v engram &>/dev/null; then
    pass "Engram in PATH: $(which engram)"
else
    warn "Engram binary not found — memory features unavailable"
fi

# --- Context7 ---
if [ -f "$MCP_PATH" ] && grep -q "context7" "$MCP_PATH" 2>/dev/null; then
    pass "Context7 MCP configured"
else
    warn "Context7 not in .mcp.json — documentation queries unavailable"
fi

# --- .claude/ ---
CLAUDE_DIR="$PROJECT_ROOT/.claude"
if [ -d "$CLAUDE_DIR" ]; then
    pass ".claude/ directory present"
else
    fail ".claude/ directory missing — run from ATLAS project root"
fi

# --- hooks ---
HOOKS_DIR="$CLAUDE_DIR/hooks"
if [ -d "$HOOKS_DIR" ]; then
    HOOK_COUNT=$(find "$HOOKS_DIR" -name "*.js" | wc -l | tr -d ' ')
    pass ".claude/hooks/ — $HOOK_COUNT JS hooks"
else
    fail ".claude/hooks/ missing"
fi

echo ""
echo "Running healthcheck..."

HC_PATH="$PROJECT_ROOT/tools/atlas_healthcheck.py"
if [ -f "$HC_PATH" ]; then
    if $PYTHON "$HC_PATH" &>/dev/null 2>&1; then
        pass "Healthcheck passed"
    else
        SUMMARY=$($PYTHON "$HC_PATH" 2>&1 | grep -E "RESULTADO|STATUS" | head -1 || echo "see output above")
        warn "Healthcheck: $SUMMARY"
    fi
else
    fail "tools/atlas_healthcheck.py not found"
fi

echo ""
echo -e "${CYAN}======================================${RESET}"

if [ "$FAIL_COUNT" -eq 0 ] && [ "$WARN_COUNT" -eq 0 ]; then
    echo -e "  ${GREEN}ATLAS READY${RESET}"
elif [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "  ${YELLOW}ATLAS READY (with $WARN_COUNT warning(s))${RESET}"
    for issue in "${ISSUES[@]}"; do echo "    $issue"; done
else
    echo -e "  ${RED}ATLAS NOT READY${RESET}"
    for issue in "${ISSUES[@]}"; do echo "    $issue"; done
fi

echo "  PASS=$PASS_COUNT  WARN=$WARN_COUNT  FAIL=$FAIL_COUNT"
echo "======================================"
echo ""

[ "$FAIL_COUNT" -eq 0 ]
