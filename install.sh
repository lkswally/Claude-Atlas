#!/bin/bash
# Wrapper — detecta SO y ejecuta el script correcto
set -e

OS=$(uname -s)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$OS" in
  Linux*)
    echo "Detectado: Linux"
    bash "$SCRIPT_DIR/install/linux.sh"
    ;;
  MINGW*|CYGWIN*|MSYS*)
    echo "Detectado: Windows (Git Bash)"
    echo "Segui las instrucciones en install/windows.md"
    echo "O abri Claude Desktop en esta carpeta y decile: 'Instalate el sistema de este repo'"
    ;;
  Darwin*)
    echo "Detectado: macOS"
    echo "El script de Linux deberia funcionar. Ejecuta: bash install/linux.sh"
    ;;
  *)
    echo "SO no reconocido: $OS"
    echo "Proba con: bash install/linux.sh"
    ;;
esac
