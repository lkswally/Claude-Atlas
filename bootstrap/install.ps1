# ATLAS Bootstrap — Windows (PowerShell)
# Verifies prerequisites and configures ATLAS for use with Claude Desktop on Windows.
#
# Usage:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\bootstrap\install.ps1

$ErrorActionPreference = "Stop"

$PASS_COUNT = 0
$WARN_COUNT = 0
$FAIL_COUNT = 0
$ISSUES = @()

function Write-Pass($msg) {
    $script:PASS_COUNT++
    Write-Host "  [PASS] $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    $script:WARN_COUNT++
    $script:ISSUES += "WARN: $msg"
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
}

function Write-Fail($msg) {
    $script:FAIL_COUNT++
    $script:ISSUES += "FAIL: $msg"
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ATLAS Bootstrap — Windows" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# --- Python ---
Write-Host "Checking prerequisites..." -ForegroundColor White
try {
    $pyver = python --version 2>&1
    if ($pyver -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 11) {
            Write-Pass "Python $major.$minor"
        } else {
            Write-Fail "Python $major.$minor — need 3.11+. Install from https://python.org"
        }
    } else {
        Write-Fail "Python version unreadable: $pyver"
    }
} catch {
    Write-Fail "Python not found. Install from https://python.org"
}

# --- Node.js ---
try {
    $nodever = node --version 2>&1
    if ($nodever -match "v(\d+)") {
        $major = [int]$Matches[1]
        if ($major -ge 18) {
            Write-Pass "Node.js $nodever"
        } else {
            Write-Fail "Node.js $nodever — need 18+. Install from https://nodejs.org"
        }
    }
} catch {
    Write-Fail "Node.js not found. Install from https://nodejs.org"
}

# --- Git ---
try {
    $gitver = git --version 2>&1
    Write-Pass "Git: $gitver"
} catch {
    Write-Fail "Git not found. Install from https://git-scm.com"
}

# --- Go ---
try {
    $gover = go version 2>&1
    Write-Pass "Go: $gover"
} catch {
    Write-Warn "Go not found (required for Engram binary). Install from https://go.dev"
}

# --- Claude ---
$claudePaths = @(
    "$env:LOCALAPPDATA\AnthropicClaude\claude.exe",
    "$env:PROGRAMFILES\AnthropicClaude\claude.exe",
    (Get-Command claude -ErrorAction SilentlyContinue)?.Source
)
$claudeFound = $false
foreach ($p in $claudePaths) {
    if ($p -and (Test-Path $p)) {
        Write-Pass "Claude Desktop found: $p"
        $claudeFound = $true
        break
    }
}
if (-not $claudeFound) {
    try {
        claude --version 2>&1 | Out-Null
        Write-Pass "Claude CLI found in PATH"
    } catch {
        Write-Warn "Claude Desktop/Code not found. Install from https://claude.ai/download"
    }
}

Write-Host ""
Write-Host "Checking Python packages..." -ForegroundColor White

# --- PyYAML ---
try {
    python -c "import yaml" 2>&1 | Out-Null
    Write-Pass "PyYAML available"
} catch {
    Write-Host "  Installing PyYAML..."
    pip install pyyaml -q
    Write-Pass "PyYAML installed"
}

# --- Playwright ---
try {
    python -c "import playwright" 2>&1 | Out-Null
    Write-Pass "Playwright Python package available"
} catch {
    Write-Host "  Installing Playwright..."
    pip install playwright -q
    python -m playwright install chromium --with-deps 2>&1 | Out-Null
    Write-Pass "Playwright installed"
}

Write-Host ""
Write-Host "Checking ATLAS configuration..." -ForegroundColor White

$projectRoot = Split-Path $PSScriptRoot -Parent

# --- .mcp.json ---
$mcpPath = Join-Path $projectRoot ".mcp.json"
if (Test-Path $mcpPath) {
    try {
        $mcp = Get-Content $mcpPath -Raw | ConvertFrom-Json
        Write-Pass ".mcp.json valid"
    } catch {
        Write-Fail ".mcp.json invalid JSON: $_"
    }
} else {
    Write-Warn ".mcp.json not found — MCP servers will not be available"
}

# --- Engram ---
$engramPaths = @(
    "$env:USERPROFILE\.engram\engram.exe",
    (Get-Command engram -ErrorAction SilentlyContinue)?.Source
)
$engramFound = $false
foreach ($p in $engramPaths) {
    if ($p -and (Test-Path $p)) {
        Write-Pass "Engram binary: $p"
        $engramFound = $true
        break
    }
}
if (-not $engramFound) {
    Write-Warn "Engram binary not found at ~/.engram/engram.exe — memory features unavailable"
}

# --- Context7 in .mcp.json ---
if (Test-Path $mcpPath) {
    $mcpContent = Get-Content $mcpPath -Raw
    if ($mcpContent -match "context7") {
        Write-Pass "Context7 MCP configured"
    } else {
        Write-Warn "Context7 not in .mcp.json — documentation queries unavailable"
    }
}

# --- .claude/ ---
$claudeDir = Join-Path $projectRoot ".claude"
if (Test-Path $claudeDir) {
    Write-Pass ".claude/ directory present"
} else {
    Write-Fail ".claude/ directory missing — run from ATLAS project root"
}

# --- hooks ---
$hooksDir = Join-Path $claudeDir "hooks"
if (Test-Path $hooksDir) {
    $hookCount = (Get-ChildItem $hooksDir -Filter "*.js").Count
    Write-Pass ".claude/hooks/ — $hookCount JS hooks"
} else {
    Write-Fail ".claude/hooks/ missing"
}

# --- PATH check ---
$pathDirs = $env:PATH -split ";"
$hasNode = $pathDirs | Where-Object { Test-Path (Join-Path $_ "node.exe") } | Select-Object -First 1
$hasPy   = $pathDirs | Where-Object { Test-Path (Join-Path $_ "python.exe") } | Select-Object -First 1
if ($hasNode) { Write-Pass "node in PATH: $hasNode" } else { Write-Warn "node not found in PATH" }
if ($hasPy)   { Write-Pass "python in PATH: $hasPy" } else { Write-Warn "python not found in PATH" }

Write-Host ""
Write-Host "Running healthcheck..." -ForegroundColor White

$hcPath = Join-Path $projectRoot "tools\atlas_healthcheck.py"
if (Test-Path $hcPath) {
    try {
        $hcOut = python $hcPath 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Healthcheck passed"
        } else {
            $hcSummary = $hcOut | Where-Object { $_ -match "RESULTADO|STATUS" } | Select-Object -First 1
            Write-Warn "Healthcheck: $hcSummary"
        }
    } catch {
        Write-Warn "Healthcheck could not run: $_"
    }
} else {
    Write-Fail "tools/atlas_healthcheck.py not found"
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan

if ($FAIL_COUNT -eq 0 -and $WARN_COUNT -eq 0) {
    Write-Host "  ATLAS READY" -ForegroundColor Green
} elseif ($FAIL_COUNT -eq 0) {
    Write-Host "  ATLAS READY (with $WARN_COUNT warning(s))" -ForegroundColor Yellow
    foreach ($issue in $ISSUES) { Write-Host "    $issue" -ForegroundColor Yellow }
} else {
    Write-Host "  ATLAS NOT READY" -ForegroundColor Red
    foreach ($issue in $ISSUES) {
        $color = if ($issue.StartsWith("FAIL")) { "Red" } else { "Yellow" }
        Write-Host "    $issue" -ForegroundColor $color
    }
}

Write-Host "  PASS=$PASS_COUNT  WARN=$WARN_COUNT  FAIL=$FAIL_COUNT"
Write-Host "======================================"
Write-Host ""

if ($FAIL_COUNT -gt 0) { exit 1 } else { exit 0 }
