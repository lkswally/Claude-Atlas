#!/usr/bin/env python3
"""
ATLAS Dispatcher — Orchestration Engine
Ejecuta el pipeline de 5 fases con enforcement de gates, QA obligatorio, y Return Envelope validation.
NO hace trabajo real — solo coordina y valida.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# ============================================================
#  DATA MODELS
# ============================================================

@dataclass
class ReturnEnvelope:
    """Formato estandarizado de respuesta de subagentes"""
    status: str  # completado | fallido | PASS | FAIL | CERTIFIED | NEEDS WORK
    tarea: str
    archivos: List[str]
    engram: str
    verificacion: str  # layout | typo | config | none
    servidor: Optional[str] = None
    bloqueadores: List[str] = None
    notas: str = ""

    def __post_init__(self):
        if self.bloqueadores is None:
            self.bloqueadores = []

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ============================================================
#  DISPATCHER CORE
# ============================================================

class ATLASDispatcher:
    """Orquestador central del pipeline vibecoding"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.phase_playbook = self._load_phase_playbook()
        self.config_dir = self.project_root / "config"

    def _load_phase_playbook(self) -> Dict[str, Any]:
        """Cargar la definición de fases y E2E flows"""
        playbook_path = self.project_root / "config" / "phase_playbook.json"
        if not playbook_path.exists():
            raise FileNotFoundError(f"phase_playbook.json no encontrado en {playbook_path}")

        with open(playbook_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def check_phase_gate(self, from_phase: str, to_phase: str) -> Tuple[bool, List[str]]:
        """
        Validar que la transición de fase es posible.
        Retorna: (can_proceed, bloqueadores)
        """
        if to_phase not in self.phase_playbook:
            return False, [f"Fase desconocida: {to_phase}"]

        phase_config = self.phase_playbook[to_phase]
        required_cajones = self._get_required_cajones(to_phase)
        bloqueadores = []

        for cajon in required_cajones:
            # TODO: Implementar búsqueda en Engram
            # Por ahora, marcar como pendiente
            bloqueadores.append(f"CAJON REQUERIDO: {cajon} (Engram/disco)")

        can_proceed = len(bloqueadores) == 0
        return can_proceed, bloqueadores

    def _get_required_cajones(self, phase: str) -> List[str]:
        """Retornar cajones requeridos para entrar a la fase"""
        cajon_map = {
            "fase_2": ["proyecto/tareas"],
            "fase_2b": ["proyecto/css-foundation", "proyecto/design-system", "proyecto/security-spec"],
            "fase_3": ["proyecto/css-foundation", "proyecto/design-system", "proyecto/security-spec", "proyecto/tareas"],
            "fase_4": ["proyecto/estado"],  # requiere todas las QA PASS en estado
            "fase_5": ["proyecto/certificacion"],
        }
        return cajon_map.get(phase, [])

    def validate_return_envelope(self, response: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validar que la respuesta del subagente sigue el formato Return Envelope.
        Retorna: (is_valid, errores)
        """
        required_fields = {"status", "tarea", "archivos", "engram"}
        errores = []

        missing = required_fields - set(response.keys())
        if missing:
            errores.append(f"Campos requeridos faltantes: {missing}")

        valid_status = {"completado", "fallido", "PASS", "FAIL", "CERTIFIED", "NEEDS WORK"}
        if response.get("status") not in valid_status:
            errores.append(f"STATUS inválido: {response.get('status')}. Esperado: {valid_status}")

        if not isinstance(response.get("archivos"), list):
            errores.append("ARCHIVOS debe ser lista")

        if not isinstance(response.get("bloqueadores"), (list, type(None))):
            errores.append("BLOQUEADORES debe ser lista o null")

        return len(errores) == 0, errores

    def report(self, command: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generar reporte estandarizado de una ejecución de comando.
        Incluye envelope, verificaciones de gates, y E2E flows.
        """
        phase = result.get("current_phase", "unknown")
        phase_config = self.phase_playbook.get(phase, {})

        e2e_required = phase_config.get("e2e_required", [])
        e2e_posture = {
            "phase": phase,
            "total_required": len(e2e_required),
            "completed": result.get("e2e_completed", 0),
            "missing": len(e2e_required) - result.get("e2e_completed", 0),
            "flows": e2e_required,
            "next_action": e2e_required[0].get("flow") if e2e_required else "ninguno",
        }

        return {
            "ok": result.get("ok", False),
            "command": command,
            "current_phase": phase,
            "stack": result.get("stack", {}),
            "envelope": result.get("envelope", {}),
            "e2e_flows_posture": e2e_posture,
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================
#  ENTRY POINT
# ============================================================

def main():
    """Punto de entrada del dispatcher"""
    if len(sys.argv) < 2:
        print("Uso: python tools/atlas_dispatcher.py <command> [args...]")
        print("Comandos: check-phase FROM_PHASE TO_PHASE, validate-envelope, report")
        sys.exit(1)

    command = sys.argv[1]
    project_root = Path.cwd()  # Siempre usar directorio actual

    try:
        dispatcher = ATLASDispatcher(project_root)

        if command == "check-phase":
            from_phase = sys.argv[2] if len(sys.argv) > 2 else "bootstrap"
            to_phase = sys.argv[3] if len(sys.argv) > 3 else "build"
            can_proceed, bloqueadores = dispatcher.check_phase_gate(from_phase, to_phase)

            result = {
                "ok": can_proceed,
                "from_phase": from_phase,
                "to_phase": to_phase,
                "bloqueadores": bloqueadores,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif command == "validate-envelope":
            # Lee respuesta del agente desde stdin
            response = json.load(sys.stdin)
            is_valid, errores = dispatcher.validate_return_envelope(response)

            result = {
                "ok": is_valid,
                "errores": errores,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif command == "report":
            # Lee resultado de comando desde stdin
            result = json.load(sys.stdin)
            report = dispatcher.report(sys.argv[2] if len(sys.argv) > 2 else "unknown", result)
            print(json.dumps(report, ensure_ascii=False, indent=2))

        else:
            print(f"Comando desconocido: {command}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        error_result = {
            "ok": False,
            "error": str(e),
            "command": command,
        }
        print(json.dumps(error_result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
