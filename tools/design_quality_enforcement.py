#!/usr/bin/env python3
"""
Design Quality Enforcement — Anti-Generic Detector
Detecta outputs genéricos (colores, fonts, layouts) y asigna severidades sin bloqueo.
Severidad: HIGH (degrada posture) | MEDIUM (warning) | LOW (nota)
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

# ============================================================
#  ANTI-GENERIC PATTERNS (Librería de patrones genéricos)
# ============================================================

class AntiGenericPatterns:
    """Patrones de outputs genéricos a detectar"""

    # Fuentes genéricas (evitar como primera opción)
    GENERIC_FONTS = {
        "inter": "HIGH",  # Demasiado moderna/ubícua
        "roboto": "HIGH",  # Android default, genérica
        "open sans": "HIGH",  # Google font genérica
        "lato": "MEDIUM",  # Overused
        "arial": "HIGH",  # Web safe pero sin personalidad
        "helvetica": "HIGH",  # Corporativo aburrido
        "times new roman": "HIGH",  # Anticuada
        "verdana": "HIGH",  # Vieja web
        "system-ui": "MEDIUM",  # Platform default, sin personalidad
        "sans-serif": "MEDIUM",  # Fallback genérico (si es la principal)
    }

    # Paletas genéricas (colores corporativos aburridos)
    GENERIC_COLORS = {
        r"#3[bB]82[fF]6": "HIGH",  # Azul corporativo Tailwind
        r"#[eE][fF]4444": "HIGH",  # Rojo corporativo genérico
        r"#10[bB]981": "HIGH",  # Verde corporativo genérico
        r"#[fF]59[eE]0[bB]": "HIGH",  # Naranja corporativo
        r"#8[bB]5[cC][fF]6": "MEDIUM",  # Púrpura Tailwind genérico
        r"#6[bB]7280": "MEDIUM",  # Gris neutral sin carácter
        r"#d1d5db": "MEDIUM",  # Gris muy plano
        r"#f[3f]f4f6": "MEDIUM",  # Gris background muy plano
    }

    # Valores de opacity genéricos
    GENERIC_OPACITY = {
        "0.8": "MEDIUM",  # opacity para hover genérico
        "0.5": "MEDIUM",  # opacity predecible
        "0.75": "MEDIUM",  # opacity estándar
    }

    # Duraciones de animación genéricas
    GENERIC_DURATIONS = {
        "300ms": "LOW",  # Predecible
        "500ms": "LOW",  # Estándar
        "1s": "LOW",  # Muy genérico
    }

    # Valores de border-radius genéricos
    GENERIC_BORDER_RADIUS = {
        "8px": "MEDIUM",  # Tailwind default, overused
        "4px": "MEDIUM",  # Bootstrap default
        "12px": "MEDIUM",  # Shadcn default
        "999px": "LOW",  # Pill button genérico
    }

    # Palabras clave en nombres de clases/componentes que indican boilerplate
    GENERIC_COMPONENT_NAMES = {
        r"\bButton\b": "LOW",  # Nombre genérico sin personalidad
        r"\bCard\b": "LOW",  # Demasiado genérico
        r"\bContainer\b": "LOW",  # Muy común
        r"\bBox\b": "LOW",  # Sin significado
        r"\bWrapper\b": "MEDIUM",  # Indica estructura débil
    }

    # Layouts predecibles sin diferenciación
    GENERIC_LAYOUT_PATTERNS = {
        r"grid\s+grid-cols-3": "LOW",  # 3 columnas aburridas
        r"flex\s+justify-center\s+items-center": "LOW",  # Centro perfecto, muy predecible
        r"max-w-\[1200px\]": "MEDIUM",  # Width corporativo estándar
        r"mx-auto": "LOW",  # Centrado predecible
    }


@dataclass
class AntiGenericFinding:
    """Un hallazgo de patrón genérico"""
    severity: str  # HIGH | MEDIUM | LOW
    pattern_type: str  # font, color, opacity, duration, border-radius, component, layout
    pattern: str  # patrón detectado
    location: str  # dónde se encontró (línea, archivo)
    suggestion: str  # sugerencia de mejora
    file_path: str = ""
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def format_report(self) -> str:
        severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}
        return f"{severity_emoji.get(self.severity, '⚪')} [{self.severity}] {self.pattern_type}: {self.pattern} → {self.suggestion}"


# ============================================================
#  DETECTOR ENGINE
# ============================================================

class DesignQualityEnforcer:
    """Motor de detección y reporte de patrones genéricos"""

    def __init__(self):
        self.patterns = AntiGenericPatterns()
        self.findings: List[AntiGenericFinding] = []

    def analyze_file(self, file_path: Path) -> List[AntiGenericFinding]:
        """Analizar un archivo CSS/TSX/JS para patrones genéricos"""
        findings = []

        if not file_path.exists():
            return findings

        try:
            content = file_path.read_text(encoding="utf-8")
        except:
            return findings

        file_str = str(file_path)

        # Detectar fuentes genéricas
        findings.extend(self._detect_fonts(content, file_str))

        # Detectar colores genéricos
        findings.extend(self._detect_colors(content, file_str))

        # Detectar opacidades genéricas
        findings.extend(self._detect_opacity(content, file_str))

        # Detectar duraciones genéricas
        findings.extend(self._detect_durations(content, file_str))

        # Detectar border-radius genéricos
        findings.extend(self._detect_border_radius(content, file_str))

        # Detectar nombres de componentes genéricos
        findings.extend(self._detect_component_names(content, file_str))

        # Detectar layouts predecibles
        findings.extend(self._detect_layouts(content, file_str))

        return findings

    def _detect_fonts(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for font, severity in self.patterns.GENERIC_FONTS.items():
            # Buscar en font-family declarations
            patterns = [
                rf"font-family\s*:\s*['\"]?{font}",
                rf"fontFamily\s*:\s*['\"]?{font}",
                rf"@import.*{font}",
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    findings.append(
                        AntiGenericFinding(
                            severity=severity,
                            pattern_type="font",
                            pattern=font,
                            location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                            suggestion=f"Usar fonts con personalidad: Syne, Clash Display, Bricolage Grotesque, Fraunces, Cabinet Grotesk, etc.",
                            file_path=file_path,
                            line_number=content[:match.start()].count("\n") + 1,
                        )
                    )
        return findings

    def _detect_colors(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for color_pattern, severity in self.patterns.GENERIC_COLORS.items():
            matches = re.finditer(color_pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(
                    AntiGenericFinding(
                        severity=severity,
                        pattern_type="color",
                        pattern=match.group(),
                        location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                        suggestion="Usar paleta con dominante + acento sharp, no colores corporativos genéricos",
                        file_path=file_path,
                        line_number=content[:match.start()].count("\n") + 1,
                    )
                )
        return findings

    def _detect_opacity(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for opacity, severity in self.patterns.GENERIC_OPACITY.items():
            patterns = [
                rf"opacity\s*:\s*{re.escape(opacity)}",
                rf"opacity-\[{re.escape(opacity)}\]",
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    findings.append(
                        AntiGenericFinding(
                            severity=severity,
                            pattern_type="opacity",
                            pattern=opacity,
                            location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                            suggestion=f"Usar opacidad con personalidad: {opacity} es muy predecible. Considera valores como 0.87, 0.65, etc.",
                            file_path=file_path,
                            line_number=content[:match.start()].count("\n") + 1,
                        )
                    )
        return findings

    def _detect_durations(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for duration, severity in self.patterns.GENERIC_DURATIONS.items():
            patterns = [
                rf"transition\s*:\s*.*{re.escape(duration)}",
                rf"duration-\[{re.escape(duration)}\]",
                rf"animation.*{re.escape(duration)}",
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    findings.append(
                        AntiGenericFinding(
                            severity=severity,
                            pattern_type="duration",
                            pattern=duration,
                            location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                            suggestion=f"Duraciones predecibles. Considera: 250ms, 350ms, 425ms, 600ms para singularidad",
                            file_path=file_path,
                            line_number=content[:match.start()].count("\n") + 1,
                        )
                    )
        return findings

    def _detect_border_radius(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for radius, severity in self.patterns.GENERIC_BORDER_RADIUS.items():
            patterns = [
                rf"border-radius\s*:\s*{re.escape(radius)}",
                rf"rounded-\[{re.escape(radius)}\]",
            ]
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    findings.append(
                        AntiGenericFinding(
                            severity=severity,
                            pattern_type="border-radius",
                            pattern=radius,
                            location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                            suggestion=f"{radius} es default de muchos frameworks. Personalizar: {self._suggest_radius()}",
                            file_path=file_path,
                            line_number=content[:match.start()].count("\n") + 1,
                        )
                    )
        return findings

    def _detect_component_names(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for name_pattern, severity in self.patterns.GENERIC_COMPONENT_NAMES.items():
            matches = re.finditer(name_pattern, content)
            for match in matches:
                findings.append(
                    AntiGenericFinding(
                        severity=severity,
                        pattern_type="component",
                        pattern=match.group(),
                        location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                        suggestion="Nombres genéricos. Usa nombres específicos: PrimaryButton, HeroSection, FeatureCard, etc.",
                        file_path=file_path,
                        line_number=content[:match.start()].count("\n") + 1,
                    )
                )
        return findings

    def _detect_layouts(self, content: str, file_path: str) -> List[AntiGenericFinding]:
        findings = []
        for layout_pattern, severity in self.patterns.GENERIC_LAYOUT_PATTERNS.items():
            matches = re.finditer(layout_pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(
                    AntiGenericFinding(
                        severity=severity,
                        pattern_type="layout",
                        pattern=match.group(),
                        location=f"{file_path}:{content[:match.start()].count(chr(10)) + 1}",
                        suggestion="Layout predecible/boilerplate. Diseña estructuras únicas al brand.",
                        file_path=file_path,
                        line_number=content[:match.start()].count("\n") + 1,
                    )
                )
        return findings

    @staticmethod
    def _suggest_radius() -> str:
        return "6px, 10px, 14px, 16px, 20px (según necesidad)"

    def report(self) -> Dict[str, Any]:
        """Generar reporte de severidades"""
        high = [f for f in self.findings if f.severity == "HIGH"]
        medium = [f for f in self.findings if f.severity == "MEDIUM"]
        low = [f for f in self.findings if f.severity == "LOW"]

        # HIGH degrada posture
        posture = "NEEDS WORK" if high else ("ACCEPTABLE" if medium else "GOOD")

        return {
            "posture": posture,
            "total_findings": len(self.findings),
            "by_severity": {
                "HIGH": len(high),
                "MEDIUM": len(medium),
                "LOW": len(low),
            },
            "findings": {
                "HIGH": [f.to_dict() for f in high],
                "MEDIUM": [f.to_dict() for f in medium],
                "LOW": [f.to_dict() for f in low],
            },
        }

    def format_report(self) -> str:
        """Generar reporte legible"""
        report = self.report()
        lines = [
            f"Design Quality Report — Anti-Generic Severity",
            f"==========================================",
            f"Posture: {report['posture']}",
            f"Total findings: {report['total_findings']}",
            f"  HIGH: {report['by_severity']['HIGH']} (degrada posture)",
            f"  MEDIUM: {report['by_severity']['MEDIUM']} (warnings)",
            f"  LOW: {report['by_severity']['LOW']} (notes)",
            f"",
        ]

        if report["findings"]["HIGH"]:
            lines.append("[HIGH] SEVERITY (Posture degraded):")
            for f in report["findings"]["HIGH"]:
                lines.append(f"  - {f['pattern_type']}: {f['pattern']} @ {f['location']}")
                lines.append(f"    -> {f['suggestion']}")
            lines.append("")

        if report["findings"]["MEDIUM"]:
            lines.append("[MEDIUM] SEVERITY (Warnings):")
            for f in report["findings"]["MEDIUM"]:
                lines.append(f"  - {f['pattern_type']}: {f['pattern']} @ {f['location']}")
            lines.append("")

        if report["findings"]["LOW"]:
            lines.append("[LOW] SEVERITY (Notes):")
            for f in report["findings"]["LOW"]:
                lines.append(f"  - {f['pattern_type']}: {f['pattern']}")

        return "\n".join(lines)


# ============================================================
#  CLI ENTRY POINT
# ============================================================

def main():
    """Punto de entrada CLI"""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python tools/design_quality_enforcement.py <file_or_dir> [--json]")
        sys.exit(1)

    path = Path(sys.argv[1])
    as_json = "--json" in sys.argv

    enforcer = DesignQualityEnforcer()

    if path.is_file():
        enforcer.findings = enforcer.analyze_file(path)
    elif path.is_dir():
        # Analizar todos los archivos CSS, TSX, JS en el directorio
        for ext in ["*.css", "*.tsx", "*.ts", "*.jsx", "*.js"]:
            for file in path.rglob(ext):
                enforcer.findings.extend(enforcer.analyze_file(file))

    if as_json:
        report = enforcer.report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(enforcer.format_report())

    # Exit code: 0 si ok, 1 si hay HIGH (pero sin bloqueo — es solo info)
    sys.exit(0)


if __name__ == "__main__":
    main()
