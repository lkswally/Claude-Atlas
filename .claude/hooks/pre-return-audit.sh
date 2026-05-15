#!/bin/bash
# pre-return-audit.sh — Reglas UNIVERSALES de auditoría CSS/HTML/JSX
# Complementa frontend-audit.sh (que requiere --mood/--hero/--motion del agent).
# Este hook NO requiere parámetros — corre sobre files pasados y reporta warnings.
#
# Modos de invocación:
#   1. PostToolUse hook automático (vía settings.json):
#      stdin recibe JSON con tool_input.file_path → audita si extensión es relevante.
#   2. Manual / Modo Modificación:
#      bash pre-return-audit.sh --files="file1.css file2.html"
#
# Output: YAML con WARN/FAIL/PASS por regla.
# Exit codes:
#   0 = todo PASS o solo WARNs → NO bloquea
#   1 = manual mode: usado como señal a quien invoca (no aplica a hook automático)
# Hook fail-open: NUNCA exit 2 (no rompe el flujo del usuario).

set -u

# ─── Detectar modo invocación ──────────────────────────────────────────────
FILES=""
HOOK_MODE=0

if [ -p /dev/stdin ] || [ ! -t 0 ]; then
  # Probable hook: leer stdin JSON
  STDIN_JSON=$(cat)
  if [ -n "$STDIN_JSON" ]; then
    HOOK_MODE=1
    # Extraer file_path del JSON sin jq (fail-soft)
    FILE_FROM_HOOK=$(echo "$STDIN_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")
    [ -n "$FILE_FROM_HOOK" ] && FILES="$FILE_FROM_HOOK"
  fi
fi

# Modo CLI (override stdin)
for arg in "$@"; do
  case "$arg" in
    --files=*) FILES="${arg#*=}" ;;
  esac
done

# Si no hay files, salir limpio (hook automático en tools no-edit)
[ -z "$FILES" ] && exit 0

# Filtrar por extensión relevante (CSS/HTML/JSX/TSX/SCSS/Vue/Svelte)
RELEVANT=""
for f in $FILES; do
  case "$f" in
    *.css|*.scss|*.html|*.htm|*.jsx|*.tsx|*.vue|*.svelte|*.astro)
      [ -f "$f" ] && RELEVANT="$RELEVANT $f"
      ;;
  esac
done

[ -z "$RELEVANT" ] && exit 0

# ─── Reglas universales ────────────────────────────────────────────────────
WARN_COUNT=0
declare -a FINDINGS=()

# Helper
add_finding() {
  FINDINGS+=("$1")
  WARN_COUNT=$((WARN_COUNT + 1))
}

# R1 — container max ≤1280 (SaaS feel). Permite excepciones documentadas (prose, form).
for f in $RELEVANT; do
  case "$f" in *.css|*.scss)
    # Buscar max-width:1[01]XXpx o --max:1[01]XXpx en :root o equivalente
    HITS=$(grep -nE '(max-width|--max|--envelope-max|--container-xl):\s*1[01][0-9][0-9]px' "$f" 2>/dev/null | grep -vE 'prose|2xl|form|input|--container-(sm|md|lg)' | head -3)
    if [ -n "$HITS" ]; then
      add_finding "R1[container-cap-saas-feel]: $f → max-width 1180-1280px detectado en container global. Regla ux-architect.md: usar 1600-1920px para moods bold. Excepciones: max-w-prose (texto), forms. Líneas: $(echo "$HITS" | head -1 | cut -d: -f1)"
    fi
    ;;
  esac
done

# R2 — Fuentes custom declaradas sin <link rel> ni @font-face
# Buscamos: font-family que mencione fuente custom típica
CUSTOM_FONT_RE='font-family:[^;]*\b(Space Grotesk|Plus Jakarta|Sora|Manrope|Cascadia|Geist|Satoshi|Clash|General Sans|Bricolage|Instrument|Recoleta|Tobias|Editorial)\b'
for f in $RELEVANT; do
  case "$f" in *.css|*.scss)
    HITS=$(grep -nE "$CUSTOM_FONT_RE" "$f" 2>/dev/null | head -1)
    if [ -n "$HITS" ]; then
      FONT_NAME=$(echo "$HITS" | grep -oE '(Space Grotesk|Plus Jakarta|Sora|Manrope|Cascadia|Geist|Satoshi|Clash|General Sans|Bricolage|Instrument|Recoleta|Tobias|Editorial)' | head -1)
      # ¿Hay carga? Buscar en HTML siblings o en este file @font-face
      LOADED=0
      if grep -qE "@font-face|@import.*fonts" "$f" 2>/dev/null; then LOADED=1; fi
      # Buscar HTML hermano(s)
      DIR=$(dirname "$f")
      if grep -rE "fonts\.googleapis|fonts\.bunny|@font-face" "$DIR"/*.html 2>/dev/null | grep -qi "${FONT_NAME// /\\+}"; then LOADED=1; fi
      [ "$LOADED" -eq 0 ] && add_finding "R2[font-declared-not-loaded]: $f declara \"$FONT_NAME\" pero no encuentro <link href=fonts.googleapis> ni @font-face en este archivo ni en HTML cercanos. Resultado: fallback a system-ui."
    fi
    ;;
  esac
done

# R3 — anchor scroll con sticky header sin scroll-padding-top
for f in $RELEVANT; do
  case "$f" in *.css|*.scss)
    if grep -qE 'position:\s*sticky\s*;?[^}]*top:' "$f" 2>/dev/null; then
      if ! grep -qE 'scroll-padding-top|scroll-padding\s*:' "$f" 2>/dev/null; then
        add_finding "R3[sticky-no-scroll-padding]: $f tiene position:sticky en header pero falta scroll-padding-top en <html>. Anchor jumps quedarán ocultos detrás del header. Aplicar: html { scroll-padding-top: var(--scroll-pad-top); }"
      fi
    fi
    ;;
  esac
done

# R4 — navbar mobile sin patrón hamburger toggle
for f in $RELEVANT; do
  case "$f" in *.html|*.jsx|*.tsx|*.vue|*.svelte|*.astro)
    # Si hay nav con links Y no hay aria-expanded ni hamburger toggle
    if grep -qE '<nav\b|class="nav-links"' "$f" 2>/dev/null; then
      if ! grep -qE 'aria-expanded|nav-toggle|hamburger|menu-toggle|MenuIcon|HamburgerMenu' "$f" 2>/dev/null; then
        # Solo warning si parece ser landing/marketing (no admin/dashboard)
        if grep -qiE 'landing|hero|marketing|home|index' "$f" 2>/dev/null || [ "$(basename "$f")" = "index.html" ]; then
          add_finding "R4[nav-mobile-no-hamburger]: $f tiene <nav> pero sin aria-expanded/nav-toggle/hamburger. Revisar que en mobile (<768px) no quede el menú permanentemente desplegado."
        fi
      fi
    fi
    ;;
  esac
done

# R5 — prefers-reduced-motion: si hay >5 keyframes/transiciones, debería existir media query
for f in $RELEVANT; do
  case "$f" in *.css|*.scss)
    ANIM_COUNT=$(grep -cE '@keyframes|animation:|transition:' "$f" 2>/dev/null)
    ANIM_COUNT=${ANIM_COUNT:-0}
    if [ "$ANIM_COUNT" -gt 5 ] 2>/dev/null; then
      if ! grep -qE 'prefers-reduced-motion' "$f" 2>/dev/null; then
        add_finding "R5[reduced-motion-missing]: $f tiene $ANIM_COUNT animaciones/transiciones pero falta @media (prefers-reduced-motion: reduce). Usuarios con sensibilidad vestibular afectados."
      fi
    fi
    ;;
  esac
done

# ─── Output ────────────────────────────────────────────────────────────────
if [ "$WARN_COUNT" -eq 0 ]; then
  # En hook mode: silencio si todo OK. En CLI: confirmar PASS.
  if [ "$HOOK_MODE" -eq 0 ]; then
    echo "PRE_RETURN_AUDIT:"
    echo "  verdict: PASS"
    echo "  files_audited: $(echo "$RELEVANT" | wc -w | tr -d ' ')"
  fi
  exit 0
fi

# Hay warnings: imprimir a stderr (visible en hook mode sin bloquear)
{
  echo ""
  echo "⚠️  PRE_RETURN_AUDIT — $WARN_COUNT warning(s):"
  for finding in "${FINDINGS[@]}"; do
    echo "  • $finding"
  done
  echo ""
  echo "  (Hook fail-open: no bloquea. Revisar antes de devolver al usuario.)"
} >&2

# Hook mode: exit 0 (fail-open). CLI mode: exit 1 (señal para que el invocador decida).
[ "$HOOK_MODE" -eq 1 ] && exit 0 || exit 1
