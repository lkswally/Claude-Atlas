#!/usr/bin/env python3
"""
Topic Key Enforcer — Valida que todo mem_save en agent prompts usa topic_key
Sin bloqueo duro — es una validación de compliance
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, asdict

# ============================================================
#  DATA MODELS
# ============================================================

@dataclass
class TopicKeyViolation:
    """Una violation de topic_key requirement"""
    agent_file: str
    line_number: int
    severity: str  # HIGH (mem_save sin topic_key) | LOW (ambiguo/falso positivo)
    pattern: str  # el mem_save encontrado
    suggestion: str  # qué hacer
    context: str  # líneas alrededor

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def format_report(self) -> str:
        severity_symbol = "ERROR" if self.severity == "HIGH" else "WARN"
        return f"[{severity_symbol}] {self.agent_file}:{self.line_number} → {self.suggestion}"


# ============================================================
#  ENFORCER ENGINE
# ============================================================

class TopicKeyEnforcer:
    """Validador de topic_key obligatorio en agentes"""

    def __init__(self):
        self.violations: List[TopicKeyViolation] = []

    def analyze_agent_file(self, file_path: Path) -> List[TopicKeyViolation]:
        """Analizar un archivo de agente para violations de topic_key"""
        violations = []

        if not file_path.exists():
            return violations

        try:
            content = file_path.read_text(encoding="utf-8")
        except:
            return violations

        lines = content.split("\n")
        file_str = str(file_path.relative_to(file_path.parent.parent))

        # Buscar bloques de mem_save
        for i, line in enumerate(lines, 1):
            # Pattern 1: mem_save( sin topic_key en el bloque
            if "mem_save(" in line:
                violations.extend(
                    self._check_mem_save_block(lines, i - 1, file_str)
                )

            # Pattern 2: mem_update( sin topic_key (también debería tener)
            if "mem_update(" in line:
                violations.extend(
                    self._check_mem_update_block(lines, i - 1, file_str)
                )

        return violations

    def _check_mem_save_block(
        self, lines: List[str], start_idx: int, file_str: str
    ) -> List[TopicKeyViolation]:
        """Verificar un bloque mem_save tiene topic_key"""
        violations = []

        # Extraer el bloque completo (hasta el closing parenthesis)
        block_lines = []
        open_parens = 0
        found_opening = False

        for i in range(start_idx, min(start_idx + 20, len(lines))):
            line = lines[i]
            block_lines.append(line)

            # Contar parenthesis
            for char in line:
                if char == "(":
                    open_parens += 1
                    found_opening = True
                elif char == ")":
                    open_parens -= 1

            # Si encontramos el cierre del mem_save
            if found_opening and open_parens == 0:
                break

        block_text = "\n".join(block_lines)

        # Verificar si hay topic_key
        has_topic_key = re.search(r"topic_key\s*:", block_text, re.IGNORECASE)

        if not has_topic_key:
            violations.append(
                TopicKeyViolation(
                    agent_file=file_str,
                    line_number=start_idx + 1,
                    severity="HIGH",
                    pattern="mem_save(...) sin topic_key",
                    suggestion="OBLIGATORIO: agregar topic_key: '{proyecto}/{cajon}' al mem_save",
                    context=block_text[:100] + "...",
                )
            )

        return violations

    def _check_mem_update_block(
        self, lines: List[str], start_idx: int, file_str: str
    ) -> List[TopicKeyViolation]:
        """Verificar que mem_update usa observation_id (que implica topic_key ya existe)"""
        violations = []

        # mem_update debería tener observation_id como primer parámetro
        line = lines[start_idx]

        # Pattern: mem_update(observation_id_var, ...)
        if "mem_update(" in line:
            has_observation_id = re.search(
                r"mem_update\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*,",
                line,
            )

            if not has_observation_id:
                violations.append(
                    TopicKeyViolation(
                        agent_file=file_str,
                        line_number=start_idx + 1,
                        severity="LOW",
                        pattern="mem_update(...) unclear observation_id",
                        suggestion="Asegurate que mem_update recibe observation_id de mem_search previo",
                        context=line[:80],
                    )
                )

        return violations

    def analyze_agents_directory(self, agents_dir: Path) -> Dict[str, Any]:
        """Analizar todos los archivos de agentes"""
        all_violations = []

        if not agents_dir.is_dir():
            return {"error": f"Directory not found: {agents_dir}"}

        agent_files = list(agents_dir.glob("*.md"))

        for agent_file in agent_files:
            violations = self.analyze_agent_file(agent_file)
            all_violations.extend(violations)

        # Categorizar
        high = [v for v in all_violations if v.severity == "HIGH"]
        low = [v for v in all_violations if v.severity == "LOW"]

        # Compliance score
        total_agents = len(agent_files)
        compliant_agents = total_agents - len(set(v.agent_file for v in high))
        compliance_pct = (compliant_agents / total_agents * 100) if total_agents > 0 else 0

        return {
            "total_agents": total_agents,
            "total_violations": len(all_violations),
            "by_severity": {
                "HIGH": len(high),
                "LOW": len(low),
            },
            "compliance_pct": round(compliance_pct, 1),
            "compliance_status": "PASS" if len(high) == 0 else "NEEDS WORK",
            "violations": {
                "HIGH": [v.to_dict() for v in high],
                "LOW": [v.to_dict() for v in low],
            },
        }

    def format_report(self, analysis: Dict[str, Any]) -> str:
        """Generar reporte legible"""
        if "error" in analysis:
            return f"Error: {analysis['error']}"

        lines = [
            "Topic Key Enforcement Report",
            "=============================",
            f"Compliance: {analysis['compliance_status']} ({analysis['compliance_pct']}%)",
            f"Agents analyzed: {analysis['total_agents']}",
            f"Total violations: {analysis['total_violations']}",
            f"  HIGH (mem_save sin topic_key): {analysis['by_severity']['HIGH']}",
            f"  LOW (ambiguo/falso positivo): {analysis['by_severity']['LOW']}",
            "",
        ]

        if analysis["violations"]["HIGH"]:
            lines.append("HIGH SEVERITY — mem_save sin topic_key:")
            for v in analysis["violations"]["HIGH"]:
                lines.append(f"  {v['agent_file']}:{v['line_number']}")
                lines.append(f"    → {v['suggestion']}")
            lines.append("")

        if analysis["violations"]["LOW"]:
            lines.append("LOW SEVERITY — Ambiguo/falso positivo:")
            for v in analysis["violations"]["LOW"]:
                lines.append(f"  {v['agent_file']}:{v['line_number']}")

        return "\n".join(lines)


# ============================================================
#  CLI ENTRY POINT
# ============================================================

def main():
    """Punto de entrada CLI"""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python tools/topic_key_enforcer.py <agents_dir> [--json]")
        sys.exit(1)

    agents_dir = Path(sys.argv[1])
    as_json = "--json" in sys.argv

    enforcer = TopicKeyEnforcer()
    analysis = enforcer.analyze_agents_directory(agents_dir)

    if as_json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
    else:
        print(enforcer.format_report(analysis))

    # Exit code: 0 si compliance ok, 1 si hay HIGH violations
    exit_code = 0 if analysis.get("compliance_status") == "PASS" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
