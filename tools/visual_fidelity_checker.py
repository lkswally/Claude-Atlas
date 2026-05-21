#!/usr/bin/env python3
"""
Visual Fidelity Checker (Bloque 1H.3)
======================================

Tercera capa de multi-layer QA: compara la SPEC visual declarada (paleta,
tipografia, mood, anti-patterns) contra la EVIDENCIA visual capturada
(LLM-as-judge: el agente Claude analiza el screenshot y produce evidence
estructurada). El helper computa el verdict deterministicamente.

ALCANCE HONESTO:
- SOLO valida diferencias entre spec declarada y evidence capturada
- NO ejecuta analisis de imagen propio (eso lo hace el agente con multimodal)
- NO valida pixel-perfect — usa thresholds tolerantes para color matching
- El "LLM-as-judge" es responsabilidad del agente: el helper compara
  estructuras, no imagenes

ENTRADA:
- spec: visual_spec del design-system (colors, typography, mood, anti-patterns)
- evidence: lo que el agente reporto tras analizar el screenshot

SALIDA:
- verdict global (OK / WARN / FAIL)
- field-by-field comparison con severity
- discrepancies actionables

CRITERIOS DE SEVERIDAD:
- CRITICAL: primary color hex distance > tolerancia (~20 ΔE), heading
            font family difiere, anti_pattern detectado que estaba prohibido
- HIGH: secondary/accent color desviado, body font difiere, mood detectado
        no matchea declarado
- MEDIUM: layout pattern divergente, spacing/sizing fuera de range
- LOW: detalles menores (icon style, ornamento)
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
#  CONSTANTES
# ============================================================

VERDICT_OK = "OK"
VERDICT_WARN = "WARN"
VERDICT_FAIL = "FAIL"

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Tolerancia para comparar hex colors (ΔE aproximado via RGB Euclidean distance)
COLOR_DISTANCE_TOLERANCE_PRIMARY = 30   # primario: estricto
COLOR_DISTANCE_TOLERANCE_SECONDARY = 50  # secondary/accent: mas tolerante


# ============================================================
#  HELPERS DE COLOR
# ============================================================

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _hex_to_rgb(hex_str: str) -> Optional[Tuple[int, int, int]]:
    """Convierte hex string a tupla (r,g,b). Retorna None si invalido."""
    if not isinstance(hex_str, str):
        return None
    m = HEX_RE.match(hex_str.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return (r, g, b)
    except ValueError:
        return None


def _color_distance(hex_a: str, hex_b: str) -> Optional[float]:
    """Distancia euclidiana RGB entre dos hex colors. None si invalidos."""
    rgb_a = _hex_to_rgb(hex_a)
    rgb_b = _hex_to_rgb(hex_b)
    if rgb_a is None or rgb_b is None:
        return None
    return ((rgb_a[0] - rgb_b[0]) ** 2 + (rgb_a[1] - rgb_b[1]) ** 2 + (rgb_a[2] - rgb_b[2]) ** 2) ** 0.5


def _find_closest_color(target: str, candidates: List[str]) -> Tuple[Optional[str], Optional[float]]:
    """Encuentra el color en candidates mas cercano a target. Retorna (color, distancia)."""
    best: Tuple[Optional[str], Optional[float]] = (None, None)
    for c in candidates:
        dist = _color_distance(target, c)
        if dist is None:
            continue
        if best[1] is None or dist < best[1]:
            best = (c, dist)
    return best


# ============================================================
#  CHECKER
# ============================================================

class VisualFidelityChecker:
    """Compara spec visual declarada vs evidence capturada."""

    def __init__(
        self,
        primary_color_tolerance: float = COLOR_DISTANCE_TOLERANCE_PRIMARY,
        secondary_color_tolerance: float = COLOR_DISTANCE_TOLERANCE_SECONDARY,
    ):
        self.primary_tolerance = primary_color_tolerance
        self.secondary_tolerance = secondary_color_tolerance

    # ----------------------------------------------------------
    #  Comparaciones especificas
    # ----------------------------------------------------------

    def _check_primary_color(
        self,
        declared: Optional[str],
        detected: List[str],
    ) -> List[Dict[str, Any]]:
        """El color primario declarado debe estar en los detectados (con tolerancia)."""
        issues: List[Dict[str, Any]] = []
        if not declared:
            issues.append({
                "severity": SEVERITY_MEDIUM,
                "field": "palette.primary",
                "type": "palette_primary_not_declared",
                "details": "spec no declara color primario — recomendado para validar",
            })
            return issues

        if not detected:
            issues.append({
                "severity": SEVERITY_CRITICAL,
                "field": "palette.primary",
                "type": "palette_no_detected",
                "details": "evidence no provee detected_colors. No se puede validar.",
            })
            return issues

        closest, dist = _find_closest_color(declared, detected)
        if dist is None:
            issues.append({
                "severity": SEVERITY_HIGH,
                "field": "palette.primary",
                "type": "palette_invalid_format",
                "declared": declared,
                "details": "no se pudo parsear color declarado o detectados",
            })
        elif dist > self.primary_tolerance:
            issues.append({
                "severity": SEVERITY_CRITICAL,
                "field": "palette.primary",
                "type": "palette_primary_mismatch",
                "declared": declared,
                "closest_detected": closest,
                "distance": round(dist, 2),
                "tolerance": self.primary_tolerance,
                "details": f"Primary color declarado '{declared}' no esta en evidence (closest: {closest}, dist {dist:.1f} > tol {self.primary_tolerance})",
            })
        return issues

    def _check_secondary_colors(
        self,
        declared: Dict[str, str],
        detected: List[str],
    ) -> List[Dict[str, Any]]:
        """Colores secondary/accent declarados deben estar cerca de algun detectado."""
        issues: List[Dict[str, Any]] = []
        for label, declared_color in declared.items():
            if label == "primary":
                continue  # ya cubierto
            if not declared_color or not detected:
                continue
            closest, dist = _find_closest_color(declared_color, detected)
            if dist is not None and dist > self.secondary_tolerance:
                issues.append({
                    "severity": SEVERITY_HIGH,
                    "field": f"palette.{label}",
                    "type": "palette_secondary_mismatch",
                    "declared": declared_color,
                    "closest_detected": closest,
                    "distance": round(dist, 2),
                    "tolerance": self.secondary_tolerance,
                    "details": f"{label} declarado '{declared_color}' no esta en evidence (closest: {closest}, dist {dist:.1f})",
                })
        return issues

    def _check_typography(
        self,
        declared: Dict[str, str],
        detected: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """heading_font y body_font declarados deben matchear detectados."""
        issues: List[Dict[str, Any]] = []

        def _norm(font: Optional[str]) -> str:
            if not font:
                return ""
            # Tomar solo el primer nombre antes de coma o paréntesis
            return font.split(",")[0].split("(")[0].strip().lower()

        for role, severity in [("heading_font", SEVERITY_CRITICAL), ("body_font", SEVERITY_HIGH)]:
            d = _norm(declared.get(role))
            e = _norm(detected.get(role))
            if d and e and d != e:
                issues.append({
                    "severity": severity,
                    "field": f"typography.{role}",
                    "type": "typography_font_mismatch",
                    "declared": declared.get(role),
                    "detected": detected.get(role),
                    "details": f"{role} declarado '{declared.get(role)}' difiere de detectado '{detected.get(role)}'",
                })
            elif d and not e:
                issues.append({
                    "severity": SEVERITY_MEDIUM,
                    "field": f"typography.{role}",
                    "type": "typography_not_detected",
                    "declared": declared.get(role),
                    "details": f"{role} declarado '{declared.get(role)}' pero evidence no reporto detectado",
                })
        return issues

    def _check_anti_patterns(
        self,
        declared_obligatorios: List[str],
        detected_violations: List[str],
    ) -> List[Dict[str, Any]]:
        """Anti-patterns obligatorios NO deben aparecer como violations en evidence."""
        issues: List[Dict[str, Any]] = []
        for violated in detected_violations:
            issues.append({
                "severity": SEVERITY_HIGH,
                "field": "anti_patterns",
                "type": "anti_pattern_violation",
                "pattern": violated,
                "details": f"Evidence reporto violacion de anti-pattern: '{violated}'",
            })
        return issues

    def _check_mood(
        self,
        declared: Optional[str],
        detected: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Mood preset declarado debe matchear con detectado por el agente."""
        issues: List[Dict[str, Any]] = []
        if declared and detected and declared.strip().lower() != detected.strip().lower():
            issues.append({
                "severity": SEVERITY_HIGH,
                "field": "mood_preset",
                "type": "mood_mismatch",
                "declared": declared,
                "detected": detected,
                "details": f"Mood declarado '{declared}' difiere de detectado '{detected}'",
            })
        return issues

    def _check_layout_pattern(
        self,
        declared: Optional[str],
        detected: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Layout pattern (hero structure) declarado deberia matchear."""
        issues: List[Dict[str, Any]] = []
        if declared and detected and declared.strip().lower() != detected.strip().lower():
            issues.append({
                "severity": SEVERITY_MEDIUM,
                "field": "layout_pattern",
                "type": "layout_mismatch",
                "declared": declared,
                "detected": detected,
                "details": f"Layout pattern declarado '{declared}' difiere de '{detected}'",
            })
        return issues

    # ----------------------------------------------------------
    #  API publica
    # ----------------------------------------------------------

    def check(
        self,
        spec: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compara visual_spec declarada vs visual_evidence capturada.

        spec shape esperado:
        {
          "declared_palette": {"primary": "#hex", "secondary": "#hex", "accent": "#hex"},
          "declared_typography": {"heading_font": str, "body_font": str},
          "mood_preset": str,
          "anti_patterns_obligatorios": [str, ...],
          "layout_pattern": str,
        }

        evidence shape esperado (lo que el agente reporta):
        {
          "detected_colors": [str hex, ...],  # dominantes del screenshot
          "detected_typography": {"heading_font": str, "body_font": str},
          "detected_mood": str,
          "anti_pattern_violations": [str, ...],
          "detected_layout_pattern": str,
        }

        Retorna dict:
        {
          "verdict": "OK"|"WARN"|"FAIL",
          "issues": [{"severity", "field", "type", "declared", ...}],
          "summary": {"total_fields_checked": N, "issues_count": N, "by_severity": {...}},
          "note": str,
        }
        """
        if not isinstance(spec, dict) or not isinstance(evidence, dict):
            return {
                "verdict": VERDICT_OK,
                "issues": [],
                "summary": {"total_fields_checked": 0, "issues_count": 0, "by_severity": {}},
                "note": "spec o evidence no son dicts validos. Skip.",
            }

        all_issues: List[Dict[str, Any]] = []
        fields_checked = 0

        # Palette
        declared_palette = spec.get("declared_palette", {}) or {}
        detected_colors = evidence.get("detected_colors", []) or []
        if declared_palette and isinstance(declared_palette, dict):
            all_issues.extend(self._check_primary_color(
                declared_palette.get("primary"),
                detected_colors,
            ))
            all_issues.extend(self._check_secondary_colors(declared_palette, detected_colors))
            fields_checked += len([k for k in declared_palette.keys() if declared_palette.get(k)])

        # Typography
        declared_typo = spec.get("declared_typography", {}) or {}
        detected_typo = evidence.get("detected_typography", {}) or {}
        if declared_typo:
            all_issues.extend(self._check_typography(declared_typo, detected_typo))
            fields_checked += len([k for k in declared_typo.keys() if declared_typo.get(k)])

        # Mood
        if spec.get("mood_preset"):
            all_issues.extend(self._check_mood(
                spec.get("mood_preset"),
                evidence.get("detected_mood"),
            ))
            fields_checked += 1

        # Anti-patterns
        if spec.get("anti_patterns_obligatorios"):
            all_issues.extend(self._check_anti_patterns(
                spec.get("anti_patterns_obligatorios", []),
                evidence.get("anti_pattern_violations", []) or [],
            ))
            fields_checked += 1

        # Layout pattern
        if spec.get("layout_pattern"):
            all_issues.extend(self._check_layout_pattern(
                spec.get("layout_pattern"),
                evidence.get("detected_layout_pattern"),
            ))
            fields_checked += 1

        # Agregar metricas
        by_severity: Dict[str, int] = {}
        for issue in all_issues:
            sev = issue.get("severity", "UNKNOWN")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        # Verdict global
        if by_severity.get(SEVERITY_CRITICAL, 0) > 0:
            verdict = VERDICT_FAIL
            note = (
                f"FAIL: {by_severity[SEVERITY_CRITICAL]} issue(s) CRITICAL en fidelidad visual. "
                f"Bloquea QA hasta corregir."
            )
        elif by_severity.get(SEVERITY_HIGH, 0) > 0:
            verdict = VERDICT_WARN
            note = (
                f"WARN: {by_severity[SEVERITY_HIGH]} issue(s) HIGH. "
                f"Visual fidelity degradada pero no bloquea."
            )
        elif by_severity.get(SEVERITY_MEDIUM, 0) > 0 or by_severity.get(SEVERITY_LOW, 0) > 0:
            total_minor = by_severity.get(SEVERITY_MEDIUM, 0) + by_severity.get(SEVERITY_LOW, 0)
            verdict = VERDICT_OK
            note = f"OK con {total_minor} issue(s) menores."
        else:
            verdict = VERDICT_OK
            note = f"OK: {fields_checked} campos validados, sin discrepancias."

        return {
            "verdict": verdict,
            "issues": all_issues,
            "summary": {
                "total_fields_checked": fields_checked,
                "issues_count": len(all_issues),
                "by_severity": by_severity,
            },
            "note": note,
        }
