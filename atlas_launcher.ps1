# ============================================================
#  Claude Atlas Launcher — AI Factory Entry Point
#  Ubicacion: D:\ProyectosIA\ProyectosClaude\atlas_launcher.ps1
# ============================================================

# Forzar codificacion UTF-8 para caracteres especiales
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ---- Rutas base ----
$BASE_DIR        = "D:\ProyectosIA\ProyectosClaude"
$CLAUDE_ATLAS    = "$BASE_DIR\ClaudeAtlas\claude-vibecoding"
$REYESOFT        = "$BASE_DIR\REYESOFT"
$AUDIT_SCRIPT    = "C:\Users\Lucas\.claude\hooks\audit-system.js"

# ---- Helpers de color ----
function Write-Color {
    param([string]$Text, [ConsoleColor]$Color = "White", [switch]$NoNewLine)
    $prev = [Console]::ForegroundColor
    [Console]::ForegroundColor = $Color
    if ($NoNewLine) { Write-Host $Text -NoNewline } else { Write-Host $Text }
    [Console]::ForegroundColor = $prev
}

function Write-Header {
    Clear-Host
    Write-Color ""
    Write-Color "  ╔══════════════════════════════════════════════════════╗" Cyan
    Write-Color "  ║                                                      ║" Cyan
    Write-Color "  ║         CLAUDE ATLAS  —  AI Factory Launcher         ║" Cyan
    Write-Color "  ║                                                      ║" Cyan
    Write-Color "  ╚══════════════════════════════════════════════════════╝" Cyan
    Write-Color ""
    Write-Color "  Fecha  : $(Get-Date -Format 'yyyy-MM-dd  HH:mm')" DarkGray
    Write-Color "  Sesion : $env:USERNAME @ $env:COMPUTERNAME" DarkGray
    Write-Color ""
}

function Write-Menu {
    Write-Color "  ┌──────────────────────────────────────────────────────┐" DarkCyan
    Write-Color "  │  Elige una opcion:                                   │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  │  " DarkCyan -NoNewLine
    Write-Color " 1 " Yellow -NoNewLine
    Write-Color " Gestionar ClaudeAtlas                           │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  │  " DarkCyan -NoNewLine
    Write-Color " 2 " Green -NoNewLine
    Write-Color " Trabajar en Reyesoft OS                         │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  │  " DarkCyan -NoNewLine
    Write-Color " 3 " Magenta -NoNewLine
    Write-Color " Crear un nuevo proyecto                         │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  │  " DarkCyan -NoNewLine
    Write-Color " 4 " Blue -NoNewLine
    Write-Color " Health Check del sistema (audit-system.js)      │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  │  " DarkCyan -NoNewLine
    Write-Color " 0 " DarkGray -NoNewLine
    Write-Color " Salir                                           │" DarkCyan
    Write-Color "  │                                                      │" DarkCyan
    Write-Color "  └──────────────────────────────────────────────────────┘" DarkCyan
    Write-Color ""
}

# ---- Opcion 1: ClaudeAtlas ----
function Open-ClaudeAtlas {
    Write-Color ""
    Write-Color "  [1] Abriendo ClaudeAtlas..." Yellow
    Write-Color "      Carpeta : $CLAUDE_ATLAS" DarkGray

    if (-not (Test-Path $CLAUDE_ATLAS)) {
        Write-Color "  ERROR: La carpeta no existe: $CLAUDE_ATLAS" Red
        Pause-Return
        return
    }

    # Abrir nueva ventana de PowerShell con claude en la carpeta
    Start-Process powershell -ArgumentList `
        "-NoExit", `
        "-Command", `
        "cd '$CLAUDE_ATLAS'; Write-Host '  Claude Atlas listo. Escribe tus instrucciones.' -ForegroundColor Cyan; claude"

    Write-Color "  Terminal abierta. Puedes cerrar esta ventana o continuar." Green
}

# ---- Opcion 2: Reyesoft OS ----
function Open-ReyesoftOS {
    Write-Color ""
    Write-Color "  [2] Abriendo Reyesoft OS con modo orquestador..." Green
    Write-Color "      Carpeta : $REYESOFT" DarkGray

    if (-not (Test-Path $REYESOFT)) {
        Write-Color "  ERROR: La carpeta no existe: $REYESOFT" Red
        Pause-Return
        return
    }

    # Mensaje que se envia automaticamente al arrancar claude
    $msg = "Activa el modo orquestador"

    # Usar --print para enviar el mensaje inicial y luego continuar interactivo
    # claude acepta -p/--print para un turno, pero queremos sesion interactiva
    # La forma mas limpia: pasar el mensaje como argumento de inicio
    Start-Process powershell -ArgumentList `
        "-NoExit", `
        "-Command", `
        "cd '$REYESOFT'; Write-Host '  Reyesoft OS — Modo Orquestador activado.' -ForegroundColor Green; claude --message 'Activa el modo orquestador'"

    Write-Color "  Terminal abierta con orquestador iniciado." Green
}

# ---- Opcion 3: Nuevo proyecto ----
function New-Project {
    Write-Color ""
    Write-Color "  [3] Crear nuevo proyecto" Magenta
    Write-Color ""
    Write-Color "  Nombre del proyecto (sin espacios, usa guiones): " White -NoNewLine
    $projectName = Read-Host

    if ([string]::IsNullOrWhiteSpace($projectName)) {
        Write-Color "  Nombre vacio. Cancelando." DarkGray
        Pause-Return
        return
    }

    # Sanitizar nombre: reemplazar espacios por guiones, minusculas
    $projectName = $projectName.Trim() -replace '\s+', '-'
    $projectPath = "$BASE_DIR\$projectName"

    if (Test-Path $projectPath) {
        Write-Color ""
        Write-Color "  La carpeta ya existe: $projectPath" DarkYellow
        Write-Color "  Abrir Claude en ese directorio? [S/N]: " White -NoNewLine
        $confirm = Read-Host
        if ($confirm -notin @("S","s","Y","y")) {
            Write-Color "  Cancelado." DarkGray
            Pause-Return
            return
        }
    } else {
        New-Item -ItemType Directory -Path $projectPath | Out-Null
        Write-Color ""
        Write-Color "  Carpeta creada : $projectPath" Green
    }

    # Crear CLAUDE.md minimo
    $claudeMdPath = "$projectPath\CLAUDE.md"
    if (-not (Test-Path $claudeMdPath)) {
        @"
# $projectName

Proyecto creado via Claude Atlas Launcher — $(Get-Date -Format 'yyyy-MM-dd').

## Descripcion
<!-- Describe el proyecto aqui -->

## Stack
<!-- Stack tecnologico elegido -->
"@ | Set-Content -Path $claudeMdPath -Encoding UTF8
        Write-Color "  CLAUDE.md creado  : $claudeMdPath" DarkGray
    }

    Start-Process powershell -ArgumentList `
        "-NoExit", `
        "-Command", `
        "cd '$projectPath'; Write-Host '  Proyecto: $projectName  |  Listo para trabajar.' -ForegroundColor Magenta; claude"

    Write-Color "  Terminal abierta para '$projectName'." Green
}

# ---- Opcion 4: Health Check ----
function Run-HealthCheck {
    Write-Color ""
    Write-Color "  [4] Ejecutando Health Check del sistema..." Blue
    Write-Color "      Script : $AUDIT_SCRIPT" DarkGray
    Write-Color ""

    if (-not (Test-Path $AUDIT_SCRIPT)) {
        Write-Color "  ERROR: No se encontro audit-system.js en:" Red
        Write-Color "         $AUDIT_SCRIPT" Red
        Pause-Return
        return
    }

    Write-Color "  ─────────────────────────────────────────────────────" DarkGray
    Write-Color ""

    # Ejecutar y capturar salida en la misma ventana
    $result = node $AUDIT_SCRIPT 2>&1
    $result | ForEach-Object {
        $line = $_.ToString()
        if     ($line -match "HEALTHY|OK|PASS|✓")  { Write-Color "  $line" Green }
        elseif ($line -match "ERROR|FAIL|✗|BLOCK")  { Write-Color "  $line" Red }
        elseif ($line -match "WARN|⚠")              { Write-Color "  $line" Yellow }
        else                                         { Write-Color "  $line" Gray }
    }

    Write-Color ""
    Write-Color "  ─────────────────────────────────────────────────────" DarkGray
    Write-Color ""
    Write-Color "  Health Check completado." Blue
    Pause-Return
}

# ---- Helper: pausa antes de volver al menu ----
function Pause-Return {
    Write-Color ""
    Write-Color "  Presiona ENTER para volver al menu..." DarkGray
    Read-Host | Out-Null
}

# ============================================================
#  Loop principal
# ============================================================
do {
    Write-Header
    Write-Menu

    Write-Color "  Tu eleccion: " White -NoNewLine
    $choice = Read-Host

    switch ($choice.Trim()) {
        "1" { Open-ClaudeAtlas   }
        "2" { Open-ReyesoftOS    }
        "3" { New-Project        }
        "4" { Run-HealthCheck    }
        "0" {
            Write-Color ""
            Write-Color "  Hasta luego. AI Factory cerrada." DarkGray
            Write-Color ""
            Start-Sleep -Seconds 1
            exit 0
        }
        default {
            Write-Color ""
            Write-Color "  Opcion no valida. Intenta de nuevo." Red
            Start-Sleep -Seconds 1
        }
    }

} while ($true)
