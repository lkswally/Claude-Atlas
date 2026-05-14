#!/bin/bash
# frontend-audit.sh — Ejecutable Pre-return Audit para frontend-developer
# Usage: bash frontend-audit.sh --mood={preset} --hero={type} --motion={N} --files="file1 file2..."
#
# Output:
#   - stdout: AUTO_AUDIT YAML (saas_teal_check, heading_font_check, hero_media_check, motion_coherent, shadow_coherent)
#   - exit 0 = all PASS
#   - exit 1 = al menos un FAIL (frontend-developer debe regenerar)
#
# Diseñado para cero overhead en token: corre local, devuelve resultado estructurado.

set -u

MOOD=""
HERO=""
MOTION="0"
FILES=""

for arg in "$@"; do
  case "$arg" in
    --mood=*) MOOD="${arg#*=}" ;;
    --hero=*) HERO="${arg#*=}" ;;
    --motion=*) MOTION="${arg#*=}" ;;
    --files=*) FILES="${arg#*=}" ;;
  esac
done

if [ -z "$FILES" ]; then
  echo "AUTO_AUDIT:" >&2
  echo "  error: no se pasaron --files" >&2
  exit 1
fi

FAIL_COUNT=0
declare -A RESULTS

# Helper: grep solo en files que existen
safe_grep() {
  local pattern="$1"
  shift
  for f in "$@"; do
    [ -f "$f" ] && grep -lE "$pattern" "$f" 2>/dev/null
  done
}

# T1 — SaaS teal default (solo en moods NO swiss-minimal/dashboard-dense)
if [[ "$MOOD" != "swiss-minimal" && "$MOOD" != "dashboard-dense" ]]; then
  MATCH=$(safe_grep "text-teal-|bg-teal-|text-cyan-|bg-cyan-|border-teal-|border-cyan-" $FILES)
  if [ -n "$MATCH" ]; then
    RESULTS[saas_teal_check]="FAIL: teal/cyan hardcoded en mood $MOOD ($(echo "$MATCH" | head -3 | tr '\n' ' '))"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    RESULTS[saas_teal_check]="PASS"
  fi
else
  RESULTS[saas_teal_check]="SKIP (mood $MOOD permite teal)"
fi

# T2 — Heading font genérico (Inter/Roboto/Open Sans/Lato/Arial/SF Pro/Segoe UI)
if [[ "$MOOD" != "swiss-minimal" ]]; then
  MATCH=$(safe_grep 'font-family:[^;]*\b(Inter|Roboto|Open Sans|Lato|Arial|SF Pro|Segoe UI)\b' $FILES)
  if [ -n "$MATCH" ]; then
    # Solo FAIL si aparece como heading (h1-h3 o clase display/heading)
    for f in $MATCH; do
      if grep -qE '(h1|h2|h3|\.heading|\.display|\.hero)' "$f" 2>/dev/null; then
        RESULTS[heading_font_check]="FAIL: heading usa font genérico en mood $MOOD ($f)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        break
      fi
    done
    [ -z "${RESULTS[heading_font_check]:-}" ] && RESULTS[heading_font_check]="PASS (fonts genéricos solo en body)"
  else
    RESULTS[heading_font_check]="PASS"
  fi
else
  RESULTS[heading_font_check]="SKIP (swiss-minimal permite Inter)"
fi

# T3 — Hero con media (si hero != text-only)
if [[ "$HERO" != "text-only" && -n "$HERO" ]]; then
  # Buscar imagen/video en archivos que parecen hero
  HERO_FILES=""
  for f in $FILES; do
    if echo "$f" | grep -qiE "hero|landing|home|page\.(t|j)sx?$"; then
      HERO_FILES="$HERO_FILES $f"
    fi
  done
  if [ -n "$HERO_FILES" ]; then
    MATCH=$(safe_grep '<img|<video|<Image|next/image|background-image:|bg-\[url' $HERO_FILES)
    if [ -z "$MATCH" ]; then
      RESULTS[hero_media_check]="FAIL: hero sin media pese a visual-direction.hero=$HERO"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    else
      RESULTS[hero_media_check]="PASS"
    fi
  else
    RESULTS[hero_media_check]="SKIP (no hay archivos hero en esta tarea)"
  fi
else
  RESULTS[hero_media_check]="SKIP (hero=text-only o no definido)"
fi

# T4 — Motion coherente con dial
if [[ "$MOTION" =~ ^[0-9]+$ ]] && [ "$MOTION" -ge 7 ]; then
  MATCH=$(safe_grep 'gsap|ScrollTrigger|useScroll|framer-motion|motion\.' $FILES)
  if [ -z "$MATCH" ]; then
    RESULTS[motion_coherent]="FAIL: motion_intensity=$MOTION requiere GSAP/Framer pero no se encontró"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    RESULTS[motion_coherent]="PASS"
  fi
elif [[ "$MOTION" =~ ^[0-9]+$ ]] && [ "$MOTION" -le 3 ]; then
  MATCH=$(safe_grep 'gsap|ScrollTrigger' $FILES)
  if [ -n "$MATCH" ]; then
    RESULTS[motion_coherent]="WARN: motion_intensity=$MOTION (bajo) pero usa GSAP — revisar"
  else
    RESULTS[motion_coherent]="PASS"
  fi
else
  RESULTS[motion_coherent]="PASS (motion_intensity=$MOTION moderado)"
fi

# T5 — Shadow coherente con mood
if [[ "$MOOD" == "neo-brutalism" ]]; then
  MATCH=$(safe_grep 'shadow-(sm|md|lg|xl)\b|box-shadow:[^;]*0\.[0-9]+' $FILES)
  HARD_MATCH=$(safe_grep 'shadow-\[.*#.*_.*\]|box-shadow:[^;]*[0-9]+px[^;]*[0-9]+px[^;]*0' $FILES)
  if [ -n "$MATCH" ] && [ -z "$HARD_MATCH" ]; then
    RESULTS[shadow_coherent]="FAIL: shadow suave en neo-brutalism (usar offset-hard tipo shadow-[6px_6px_0_#000])"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    RESULTS[shadow_coherent]="PASS"
  fi
else
  RESULTS[shadow_coherent]="PASS (mood $MOOD no requiere shadow brutalista)"
fi

# Output YAML estructurado
echo "AUTO_AUDIT:"
for key in saas_teal_check heading_font_check hero_media_check motion_coherent shadow_coherent; do
  echo "  $key: ${RESULTS[$key]}"
done
echo "  fail_count: $FAIL_COUNT"
echo "  verdict: $([ "$FAIL_COUNT" -eq 0 ] && echo "PASS" || echo "FAIL")"

exit $([ "$FAIL_COUNT" -eq 0 ] && echo 0 || echo 1)
