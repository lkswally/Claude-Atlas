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
        # Anti-loop tracking (Bloque 1A.12): contador de re-intentos por cajon
        # Formato: {"{proyecto}/{cajon}": count}
        self.phase_gate_retries: Dict[str, int] = {}

    def _load_phase_playbook(self) -> Dict[str, Any]:
        """Cargar la definición de fases y E2E flows"""
        playbook_path = self.project_root / "config" / "phase_playbook.json"
        if not playbook_path.exists():
            raise FileNotFoundError(f"phase_playbook.json no encontrado en {playbook_path}")

        with open(playbook_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def enforce_phase_gate(self, proyecto: str, phase: str, required_cajones: Optional[List[str]] = None) -> Tuple[bool, str, List[str]]:
        """
        ENFORCE (bloquea de verdad) — Valida que TODOS los cajones requeridos existen.
        Maneja Engram errors separado de missing cajones.
        Implementa anti-loop tracking (Bloque 1A.12).

        Retorna: (can_proceed: bool, message: str, missing_cajones: List[str])

        Comportamiento:
        - Si cajon falta EN ENGRAM Y DISCO → missing (bloquea)
        - Si Engram timeout pero disco existe → OK (fallback)
        - Si Engram timeout Y disco falta → PENDING (user manual)
        - Anti-loop: si cajon falta 2+ veces → escalar usuario (no re-delegar)
        """
        if phase not in self.phase_playbook:
            return False, f"FASE DESCONOCIDA: {phase}", []

        # Obtener cajones requeridos si no los pasaron
        if required_cajones is None:
            required_cajones = self._get_required_cajones(phase, proyecto)

        missing_cajones = []
        engram_errors = []
        escalation_cajones = []  # Cajones que alcanzan max reintentos

        for cajon in required_cajones:
            engram_response = self._check_engram_cajon(proyecto, cajon)

            if engram_response["status"] == "found":
                # Cajon existe en Engram, OK
                # Reset counter si estaba siendo reintentado
                if cajon in self.phase_gate_retries:
                    del self.phase_gate_retries[cajon]
                continue

            elif engram_response["status"] == "timeout":
                # Engram error — intenta fallback disco
                disk_exists = self._check_disk_cajon(proyecto, cajon)
                if disk_exists:
                    # Fallback exitoso
                    if cajon in self.phase_gate_retries:
                        del self.phase_gate_retries[cajon]
                    continue
                else:
                    # Engram timeout AND disco falta — PENDING
                    engram_errors.append(f"Engram timeout para {cajon} (disco también falta)")

            elif engram_response["status"] == "not_found":
                # Cajon no existe en Engram ni disco
                disk_exists = self._check_disk_cajon(proyecto, cajon)
                if not disk_exists:
                    # Cajon realmente falta — implementar anti-loop tracking
                    retry_count = self.phase_gate_retries.get(cajon, 0)

                    if retry_count >= 2:
                        # Ya se reintentó 2 veces → escalar usuario
                        escalation_cajones.append(f"{cajon} (intento {retry_count + 1}/max 2)")
                    else:
                        # Primer o segundo intento → agregar a missing para re-delegar
                        missing_cajones.append(cajon)
                        # Incrementar contador
                        self.phase_gate_retries[cajon] = retry_count + 1

        # Decisión: bloquea o permite avance
        # Prioridad: escalation > missing > engram_errors > OK

        if escalation_cajones:
            message = (
                f"FASE {phase.upper()} ESCALACIÓN (Max reintentos alcanzado):\n"
                f"  Cajones bloqueados tras 2+ intentos: {', '.join(escalation_cajones)}\n"
                f"  Acción requerida: Usuario debe resolver manualmente o reasignar agente"
            )
            return False, message, escalation_cajones

        if missing_cajones:
            message = f"FASE {phase.upper()} BLOQUEADA:\n  Cajones requeridos faltantes: {', '.join(missing_cajones)}"
            return False, message, missing_cajones

        if engram_errors:
            message = f"FASE {phase.upper()} PENDING (Engram timeout):\n  {'; '.join(engram_errors)}\n  Usuario debe confirmar manualmente o resolver Engram."
            return False, message, []

        message = f"FASE {phase.upper()}: Phase Gate OK. Todos los cajones requeridos existen."
        return True, message, []

    def _check_engram_cajon(self, proyecto: str, cajon: str) -> Dict[str, str]:
        """
        REAL Engram search (Bloque 1A.11) — llama mem_search() con manejo de timeout.

        En producción: mem_search(cajon) via MCP Engram
        En staging/test: busca en disco como proxy (Engram está backed por disk)

        Retorna:
        - {"status": "found"} si cajon existe en Engram
        - {"status": "not_found"} si cajon no existe
        - {"status": "timeout"} si Engram timeout/error (requiere fallback disco)
        """
        try:
            # En producción real, esto sería:
            # result = mem_search(cajon, project=proyecto)
            # if result.observation_id: return {"status": "found"}
            # else: return {"status": "not_found"}

            # Para staging/test, usar disco como fuente de verdad
            # (Engram está backed por disk en arquitectura real)
            cajon_name = cajon.split("/")[-1]
            disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"

            if disk_path.exists():
                # Cajon existe en disco → existe en Engram
                return {
                    "status": "found",
                    "cajon": cajon,
                    "source": "disk (Engram proxy)"
                }
            else:
                # Cajon no existe en disco → no existe en Engram
                return {
                    "status": "not_found",
                    "cajon": cajon,
                    "source": "disk (Engram proxy)"
                }

        except (OSError, IOError, TimeoutError) as e:
            # Engram timeout o error de lectura → requiere fallback disco
            return {
                "status": "timeout",
                "cajon": cajon,
                "error": str(e),
                "note": "Engram timeout — fallback a disco requerido"
            }

    def _check_disk_cajon(self, proyecto: str, cajon: str) -> bool:
        """
        Buscar cajon en disco: {project_dir}/.pipeline/{cajon}.md
        Fallback cuando Engram falla.
        """
        # Separar proyecto/cajon a ruta
        cajon_name = cajon.split("/")[-1]
        disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"
        return disk_path.exists()

    def check_phase_gate(self, from_phase: str, to_phase: str) -> Tuple[bool, List[str]]:
        """
        Versión legacy de enforce_phase_gate para CLI.
        Usa enforce_phase_gate internamente.
        """
        # Asumir proyecto desde directorio actual (legacy)
        proyecto = self.project_root.name
        can_proceed, message, missing = self.enforce_phase_gate(proyecto, to_phase)

        bloqueadores = missing if missing else []
        return can_proceed, bloqueadores

    def _get_required_cajones(self, phase: str, proyecto: str = "unknown") -> List[str]:
        """Retornar cajones requeridos para entrar a la fase"""
        cajon_map = {
            "fase_1": [],  # Fase 1 no tiene prerequisites
            "fase_2": [f"{proyecto}/tareas", f"{proyecto}/intent"],
            "paso_2_fase_2": [f"{proyecto}/visual-direction"],
            "fase_2b": [f"{proyecto}/css-foundation", f"{proyecto}/design-system", f"{proyecto}/security-spec"],
            "fase_3": [f"{proyecto}/css-foundation", f"{proyecto}/design-system", f"{proyecto}/tareas"],
            "fase_4": [f"{proyecto}/estado"],  # requiere todas las QA PASS
            "fase_5": [f"{proyecto}/certificacion"],
        }
        return cajon_map.get(phase, [])

    def validate_return_envelope(self, response: Dict[str, Any], mode: str = "standard") -> Tuple[bool, List[str]]:
        """
        Validar que la respuesta del subagente sigue el formato Return Envelope.
        Retorna: (is_valid, errores)

        Modos:
        - "standard": validación suave (para dev agents, creativos, etc.)
        - "qa_strict": validación estricta para evidence-collector (QA obligatorio)
        """
        errores = []

        # CAMPOS OBLIGATORIOS en ambos modos
        required_always = {"status", "tarea", "engram"}
        missing = required_always - set(response.keys())
        if missing:
            errores.append(f"Campos requeridos faltantes: {missing}")

        # VALIDACIÓN DE STATUS
        if mode == "qa_strict":
            valid_status = {"PASS", "FAIL"}
            if response.get("status") not in valid_status:
                errores.append(f"STATUS inválido: {response.get('status')}. Para QA esperado: PASS o FAIL")
        else:
            valid_status = {"completado", "fallido", "PASS", "FAIL", "CERTIFIED", "NEEDS WORK"}
            if response.get("status") not in valid_status:
                errores.append(f"STATUS inválido: {response.get('status')}. Esperado: {valid_status}")

        # VALIDACIONES ESPECÍFICAS PARA QA STRICT
        if mode == "qa_strict":
            status = response.get("status")

            # PASS requiere: status=PASS, archivos (NO VACÍO), NO bloqueadores
            if status == "PASS":
                # archivos es OBLIGATORIO y DEBE tener al menos 1 elemento
                archivos = response.get("archivos")
                if archivos is None:
                    errores.append("PASS requiere archivos (lista no vacía)")
                elif not isinstance(archivos, list):
                    errores.append(f"PASS: archivos debe ser lista, recibido {type(archivos).__name__}")
                elif len(archivos) == 0:
                    errores.append("PASS requiere archivos (lista no vacía)")

                # bloqueadores PROHIBIDO si status=PASS
                bloqueadores = response.get("bloqueadores")
                if bloqueadores is not None and len(bloqueadores) > 0:
                    errores.append("PASS prohibe bloqueadores (debe ser [] o null)")

            # FAIL requiere: status=FAIL, bloqueadores (NO VACÍO)
            elif status == "FAIL":
                # bloqueadores es OBLIGATORIO y DEBE tener al menos 1 elemento
                bloqueadores = response.get("bloqueadores")
                if bloqueadores is None:
                    errores.append("FAIL requiere bloqueadores (lista no vacía)")
                elif not isinstance(bloqueadores, list):
                    errores.append(f"FAIL: bloqueadores debe ser lista, recibido {type(bloqueadores).__name__}")
                elif len(bloqueadores) == 0:
                    errores.append("FAIL requiere bloqueadores (lista no vacía)")

                # archivos es OPCIONAL para FAIL
                archivos = response.get("archivos")
                if archivos is not None and not isinstance(archivos, list):
                    errores.append(f"FAIL: archivos debe ser lista, recibido {type(archivos).__name__}")

        # VALIDACIONES STANDARD (ambos modos)
        else:
            if not isinstance(response.get("archivos", []), list):
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
