#!/usr/bin/env python3
"""
ATLAS Dispatcher — Orchestration Engine
Ejecuta el pipeline de 5 fases con enforcement de gates, QA obligatorio, y Return Envelope validation.
NO hace trabajo real — solo coordina y valida.
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# Bloque 1A.15: Pre-Return Audit re-validation
_dispatcher_dir = Path(__file__).parent
if str(_dispatcher_dir) not in sys.path:
    sys.path.insert(0, str(_dispatcher_dir))
try:
    from pre_return_audit import audit_files as _audit_files
except ImportError:
    _audit_files = None  # disponible solo si pre_return_audit.py esta presente

# Bloque 1B.1: Engram Strategy Pattern (preparacion para MCP real en 1B.2)
# Por defecto se usa DiskFallbackStrategy — NO es Engram real, es disk fallback.
# El orquestador puede inyectar un callback (CallbackStrategy) que conecte
# Engram MCP real cuando 1B.2 este implementado.
from engram_strategy import (
    EngramStrategy,
    DiskFallbackStrategy,
    CallbackStrategy,
    ProtocolError,
)

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

    def __init__(
        self,
        project_root: Path,
        auto_enable_mcp: Optional[bool] = None,
    ):
        """
        Args:
            project_root: Raiz del proyecto ATLAS.
            auto_enable_mcp: Si True (default), intenta activar Engram MCP
                             automaticamente al construir (Bloque 1B.5).
                             - True: intenta auto-enable (binary detection)
                             - False: queda con DiskFallbackStrategy puro
                             - None: respeta env var ATLAS_DISABLE_ENGRAM_MCP
                                     (=1 fuerza off, sino True)
        """
        self.project_root = Path(project_root)
        self.phase_playbook = self._load_phase_playbook()
        self.config_dir = self.project_root / "config"
        # Anti-loop tracking (Bloque 1A.12): contador de re-intentos por cajon
        # Formato: {"{proyecto}/{cajon}": count}
        self.phase_gate_retries: Dict[str, int] = {}
        # Bloque 1B.1: Engram Strategy (default = disk_fallback)
        self._engram_strategy: EngramStrategy = DiskFallbackStrategy(self.project_root)

        # Bloque 1B.5: status visible (sin logging ruidoso)
        # Valores: "active" | "disabled_by_env" | "disabled_by_param" |
        #          "unavailable: {reason}" | "disabled_default"
        self.engram_mcp_status: str = "disabled_default"

        # Bloque 1B.5: auto-enable de Engram MCP al construir.
        # Decision matrix:
        #   auto_enable_mcp=False -> opt-out explicito por param
        #   ATLAS_DISABLE_ENGRAM_MCP=1 -> opt-out por env var
        #   auto_enable_mcp=None y env no seteada -> auto-enable (default)
        #   auto_enable_mcp=True -> forzar auto-enable
        env_disabled = os.environ.get("ATLAS_DISABLE_ENGRAM_MCP", "").lower() in ("1", "true", "yes")

        if auto_enable_mcp is False:
            self.engram_mcp_status = "disabled_by_param"
        elif env_disabled:
            self.engram_mcp_status = "disabled_by_env"
        else:
            # Intentar auto-enable. Si falla, disk_fallback queda activo (graceful).
            success, message = self.enable_engram_mcp()
            if success:
                self.engram_mcp_status = "active"
            else:
                # message tipo "Engram MCP no activado: EngramBinaryNotFound: ..."
                # Lo normalizamos a "unavailable: {short_reason}"
                short_reason = message.split(":", 2)[-1].strip() if ":" in message else message
                self.engram_mcp_status = f"unavailable: {short_reason[:120]}"

    def enable_engram_mcp(
        self,
        binary_path: Optional[str] = None,
        timeout_s: float = 5.0,
        use_disk_fallback: bool = True,
    ) -> Tuple[bool, str]:
        """
        Bloque 1B.2: Activa Engram MCP Real Connection.

        OPT-IN EXPLICITO. Si no se llama, dispatcher sigue usando DiskFallbackStrategy.

        Comportamiento:
        - Resuelve el binario (param > ENGRAM_MCP_BINARY > PATH)
        - Si encuentra binario: lanza subprocess lazy en primer query
        - Si NO encuentra: mantiene disk_fallback como strategy activa
          (NO rompe el dispatcher, devuelve (False, error_msg))

        Args:
            binary_path: Ruta al binario engram (opcional)
            timeout_s: Timeout por query MCP (default 5s)
            use_disk_fallback: disk_fallback como red de seguridad (default True)

        Returns:
            (success: bool, message: str)
            - (True, "Engram MCP activado") si bridge OK
            - (False, "razon") si binary missing — disk_fallback queda activo
        """
        try:
            from engram_strategy import make_mcp_bridge_strategy
            strategy = make_mcp_bridge_strategy(
                binary_path=binary_path,
                timeout_s=timeout_s,
                use_disk_fallback=use_disk_fallback,
                project_root=self.project_root,
            )
            self._engram_strategy = strategy
            # Bloque 1B.5: actualizar status si se llama manualmente
            if hasattr(self, "engram_mcp_status"):
                self.engram_mcp_status = "active"
            return (True, f"Engram MCP real activado (timeout={timeout_s}s)")

        except Exception as e:
            # Binary missing u otro error → MANTENER disk_fallback activo
            # (no romper backward compat)
            return (
                False,
                f"Engram MCP no activado: {type(e).__name__}: {e}. "
                f"Manteniendo DiskFallbackStrategy."
            )

    def set_engram_callback(
        self,
        callback: Optional[callable] = None,
        name: str = "engram_callback",
        use_disk_fallback: bool = True,
    ) -> None:
        """
        Bloque 1B.1: Inyecta una estrategia de Engram custom.

        El callback recibe (proyecto, cajon) y debe retornar dict con 'status'.
        Si use_disk_fallback=True (default), se usa DiskFallbackStrategy como
        secundario cuando el callback retorna timeout/error.

        IMPORTANTE: 1B.1 NO conecta MCP real — solo provee el plugin point.
        La implementacion MCP real es responsabilidad de 1B.2 (orquestador o
        Python MCP client).

        Llamar sin callback (None) restaura DiskFallbackStrategy pura.
        """
        if callback is None:
            self._engram_strategy = DiskFallbackStrategy(self.project_root)
            return

        fallback = DiskFallbackStrategy(self.project_root) if use_disk_fallback else None
        self._engram_strategy = CallbackStrategy(
            callback=callback,
            fallback=fallback,
            name=name,
        )

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
        Verifica existencia del cajon delegando en la EngramStrategy configurada.

        Bloque 1B.1: Refactor a strategy pattern.
        - Default strategy: DiskFallbackStrategy (NO es Engram real, es disk fallback)
        - Custom strategy: inyectada via set_engram_callback() — pluggable para 1B.2

        IMPORTANTE: el default sigue siendo lectura de disco. Esto NO es
        "Engram MCP Real Integration" — es preparacion arquitectonica.
        La integracion MCP real es responsabilidad de 1B.2.

        Retorna dict con 'status': "found" | "not_found" | "timeout" + metadata.
        """
        return self._engram_strategy.check_cajon(proyecto, cajon)

    def get_cajon_full(self, proyecto: str, cajon: str) -> Dict[str, Any]:
        """
        Bloque 1B.4: 2-step pattern real (search -> get_observation).

        Retorna el CONTENIDO COMPLETO de un cajon (no preview truncado).

        Flujo:
        1. mem_search(cajon) -> obtiene observation_id
        2. mem_get_observation(observation_id) -> contenido completo

        Retorna dict con shape:
        - {"status": "found", "content": "<texto completo>", "title": ...,
           "type": ..., "topic_key": ..., "source": ..., ...}
        - {"status": "not_found", ...} si el cajon no existe
        - {"status": "timeout", ...} si error en cualquier paso
        - {"status": "inconsistent", ...} si search dice found pero
          get_observation dice not_found (race condition o stale state)

        IMPORTANTE:
        - timeout/error NUNCA se confunden con not_found
        - Si la strategy no soporta get_observation (ej. disk_fallback),
          intenta obtener contenido del disco directamente con el cajon
        """
        self._record_invocation("get_cajon_full", context={"proyecto": proyecto, "cajon": cajon})
        # Paso 1: search
        search_result = self._engram_strategy.check_cajon(proyecto, cajon)

        if search_result["status"] == "not_found":
            return {
                "status": "not_found",
                "step": "search",
                "topic_key": cajon,
                "source": search_result.get("source"),
            }

        if search_result["status"] == "timeout":
            return {
                "status": "timeout",
                "step": "search",
                "topic_key": cajon,
                "error": search_result.get("error"),
                "source": search_result.get("source"),
            }

        # Bloque 1B.3: ambiguous_project se propaga sin step 2
        if search_result["status"] == "ambiguous_project":
            return {
                "status": "ambiguous_project",
                "step": "search",
                "topic_key": cajon,
                "project_attempted": search_result.get("project_attempted", proyecto),
                "available_projects": search_result.get("available_projects", []),
                "recovery_token": search_result.get("recovery_token"),
                "engram_error_code": search_result.get("engram_error_code"),
                "hint": search_result.get("hint"),
                "message": search_result.get("message"),
                "source": search_result.get("source"),
                "note": search_result.get("note"),
            }

        # status == found: extraer observation_id
        observation_id = search_result.get("observation_id")

        # Paso 2: get_observation
        # Pasamos tambien el cajon para que disk_fallback pueda resolverlo si toca
        obs_result = self._engram_strategy.get_observation(
            observation_id,
            cajon=cajon,
        )

        if obs_result is None:
            # Strategy no soporta get_observation y no hay fallback -> degradar
            # Devolvemos lo que tenemos del search (con preview)
            return {
                "status": "found",
                "step": "search_only",
                "topic_key": cajon,
                "observation_id": observation_id,
                "content": search_result.get("raw_text_preview"),
                "source": search_result.get("source"),
                "note": "Strategy no soporta get_observation — solo preview disponible",
            }

        # Detectar inconsistencia: search found pero get_observation not_found
        if obs_result.get("status") == "not_found":
            return {
                "status": "inconsistent",
                "step": "get_observation",
                "topic_key": cajon,
                "observation_id": observation_id,
                "note": "search retorno found pero get_observation retorno not_found (race condition o stale state)",
                "source": obs_result.get("source"),
            }

        if obs_result.get("status") == "timeout":
            return {
                "status": "timeout",
                "step": "get_observation",
                "topic_key": cajon,
                "observation_id": observation_id,
                "error": obs_result.get("error"),
                "source": obs_result.get("source"),
            }

        # found: contenido completo disponible
        return obs_result

    def resolve_ambiguous_project(
        self,
        cajon: str,
        chosen_project: str,
        recovery_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1B.3: Reintenta un query despues de un ambiguous_project.

        El caller debe haber recibido previamente un status="ambiguous_project"
        con available_projects. Esta funcion reintenta la query usando un
        proyecto explicito de esa lista.

        Args:
            cajon: topic_key a buscar
            chosen_project: proyecto a usar (deberia estar en available_projects)
            recovery_token: opcional, para trackear el reintento

        Retorna mismo shape que _check_engram_cajon, con flags adicionales:
        - "recovered_from_ambiguous": True
        - "recovery_token_used": el token si se paso
        - "chosen_project": chosen_project (para trazabilidad)

        Si la strategy actual no es CallbackStrategy con bridge MCP (ej.
        DiskFallbackStrategy puro), retorna {"status": "timeout"} con error
        explicito.
        """
        self._record_invocation("resolve_ambiguous_project", context={"cajon": cajon, "chosen_project": chosen_project})
        # Caso preferido: bridge MCP soporta mem_search_with_recovery
        bridge = getattr(self._engram_strategy, "_bridge", None)
        if bridge is not None and hasattr(bridge, "mem_search_with_recovery"):
            result = bridge.mem_search_with_recovery(
                topic_key=cajon,
                chosen_project=chosen_project,
                recovery_token=recovery_token,
            )
            result["chosen_project"] = chosen_project
            return result

        # Fallback: query directa con proyecto explicito via strategy normal.
        # Esto cubre el caso donde la strategy no es CallbackStrategy o el
        # bridge no esta accesible (ej. tests con mocks).
        result = self._engram_strategy.check_cajon(chosen_project, cajon)
        result["recovered_from_ambiguous"] = True
        result["chosen_project"] = chosen_project
        if recovery_token:
            result["recovery_token_used"] = recovery_token
        return result

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

    # Bloque 1A.16: Paths excluidos de la verificacion de archivos declarados.
    _DECLARED_FILES_EXCLUSIONS = (
        ".pipeline/",
        "_qa/temp/",
        "_qa/.",
        "node_modules/",
        "dist/",
        "build/",
        ".claude/worktrees/",
        ".next/",
        ".cache/",
    )

    def _normalize_path(self, path: str) -> str:
        """Normaliza path para comparacion cross-platform (Bloque 1A.16).
        OJO: lstrip('./') comeria el '.' de '.pipeline/' — usar startswith en vez."""
        norm = path.replace("\\", "/")
        if norm.startswith("./"):
            norm = norm[2:]
        return norm

    def _is_excluded_path(self, path: str) -> bool:
        """Determina si un path debe excluirse de la verificacion (Bloque 1A.16)"""
        norm = self._normalize_path(path)
        return any(norm.startswith(prefix) for prefix in self._DECLARED_FILES_EXCLUSIONS)

    def _get_git_changed_files(self) -> Tuple[List[str], Optional[str]]:
        """
        Bloque 1A.16: Obtiene lista de archivos modificados via git.

        Incluye modified tracked + untracked. Retorna (changed, soft_fail_reason).
        Si soft_fail_reason no es None, no se pudo determinar (no es repo git, etc).
        """
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if diff_result.returncode != 0:
                return ([], f"git diff fallo (rc={diff_result.returncode}): {diff_result.stderr.strip()[:100]}")

            modified = [l.strip() for l in diff_result.stdout.splitlines() if l.strip()]

            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            untracked: List[str] = []
            if untracked_result.returncode == 0:
                untracked = [l.strip() for l in untracked_result.stdout.splitlines() if l.strip()]

            all_changed = sorted({*modified, *untracked})
            return (all_changed, None)

        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            return ([], f"git no disponible: {e}")

    def verify_declared_files(self, response: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """
        Bloque 1A.16: Verifica que 'archivos' declarados sea SUPERSET real de los
        archivos modificados segun git diff + untracked.

        Retorna: (errores, warnings)
        - errores: blocks duros (envelope rechazado)
        - warnings: avisos blandos (soft-fail si no es repo git)

        Reglas:
        - Cambios git (post-exclusiones) subset de declarados -> OK
        - Cambios git fuera de la lista -> error con undeclared
        - Sin git / no es repo -> warning, no error
        - Over-declaration permitida; under-declaration NO
        """
        errores: List[str] = []
        warnings: List[str] = []

        archivos_declarados = response.get("archivos", []) or []
        if not isinstance(archivos_declarados, list):
            errores.append("archivos debe ser lista para verificar declaracion")
            return (errores, warnings)

        declarados_norm = {self._normalize_path(a) for a in archivos_declarados}

        changed_files, soft_fail_reason = self._get_git_changed_files()

        if soft_fail_reason is not None:
            warnings.append(f"file declaration verification omitida ({soft_fail_reason})")
            return (errores, warnings)

        changed_relevant = [f for f in changed_files if not self._is_excluded_path(f)]
        changed_norm = {self._normalize_path(f) for f in changed_relevant}

        undeclared = sorted(changed_norm - declarados_norm)

        if undeclared:
            errores.append(
                f"archivos declarados NO es superset de cambios git: "
                f"{len(undeclared)} archivo(s) modificado(s) sin declarar: {undeclared}. "
                f"El dev-agent debe listar TODOS los archivos modificados en 'archivos' "
                f"(over-declaration permitida; under-declaration NO)."
            )

        return (errores, warnings)

    def verify_pre_return_audit(self, response: Dict[str, Any]) -> List[str]:
        """
        Bloque 1A.15: Re-verifica independientemente el campo pre_return_audit
        del Return Envelope contra el estado real de los archivos en disco.

        Retorna: lista de errores (vacia si todo coincide).

        Comportamiento:
        - Si falta campo pre_return_audit -> error "obligatorio"
        - Si campo presente pero malformado -> error de formato
        - Si agente declara ok=true pero dispatcher encuentra blocks -> mismatch
        - Si agente declara ok=false -> error "no debio emitir envelope"
        - Si archivos=[] -> trivially OK (no hay nada que auditar)
        """
        errores: List[str] = []

        # 1. Campo obligatorio
        audit = response.get("pre_return_audit")
        if audit is None:
            errores.append("pre_return_audit obligatorio (Bloque 1A.15): dev-agent debe correr tools/pre_return_audit.py e incluir resultado en envelope")
            return errores

        # 2. Formato
        if not isinstance(audit, dict):
            errores.append(f"pre_return_audit debe ser objeto, recibido {type(audit).__name__}")
            return errores

        if "ok" not in audit:
            errores.append("pre_return_audit.ok obligatorio (bool)")
            return errores

        if not isinstance(audit.get("ok"), bool):
            errores.append(f"pre_return_audit.ok debe ser bool, recibido {type(audit.get('ok')).__name__}")
            return errores

        # 3. Si agente declara ok=false, no debio emitir envelope
        if audit["ok"] is False:
            block_findings = audit.get("block_findings", [])
            errores.append(
                f"pre_return_audit.ok=false: dev-agent debio corregir blocks ANTES de emitir envelope. "
                f"Blocks declarados: {len(block_findings)}"
            )
            return errores

        # 4. Re-ejecutar audit independientemente sobre los archivos del envelope
        archivos = response.get("archivos", [])
        if not isinstance(archivos, list):
            errores.append("archivos debe ser lista para verificar pre_return_audit")
            return errores

        if len(archivos) == 0:
            # Trivially OK: no hay archivos que auditar
            return errores

        if _audit_files is None:
            errores.append("pre_return_audit module no disponible — no se puede re-verificar (instalar tools/pre_return_audit.py)")
            return errores

        # Re-ejecutar el audit con el mismo motor
        try:
            dispatcher_report = _audit_files(archivos, self.project_root)
        except Exception as e:
            errores.append(f"Error re-ejecutando pre_return_audit: {e}")
            return errores

        # 5. Comparar claim vs reality
        if dispatcher_report["ok"] is False and audit["ok"] is True:
            block_count = len(dispatcher_report["block_findings"])
            blocked_rules = sorted({f["rule"] for f in dispatcher_report["block_findings"]})
            errores.append(
                f"Pre-return audit MISMATCH: agente declaro ok=true, "
                f"pero dispatcher encontro {block_count} blocks ({', '.join(blocked_rules)}). "
                f"El agente debe correr el audit REAL antes de emitir envelope."
            )

        return errores

    def validate_return_envelope(
        self,
        response: Dict[str, Any],
        mode: str = "standard",
        enforce_helpers: bool = False,
        agent_name: Optional[str] = None,
        try_auto_invoke: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Validar que la respuesta del subagente sigue el formato Return Envelope.
        Retorna: (is_valid, errores)

        Modos:
        - "standard": validación suave (para creativos, utilidades, etc.)
        - "qa_strict": validación estricta para evidence-collector (QA obligatorio)
        - "dev_strict": validación para dev-agents — requiere pre_return_audit (Bloque 1A.15)
        - "design_strict": validación para ux-architect / ui-designer —
                           requiere design_intelligence consultado (Bloque 1C.1)

        Bloque 1K.3 — Hard Enforcement Escalation (opt-in):
        - enforce_helpers=True + agent_name in CRITICAL_AGENTS:
            si faltan helpers obligatorios para ese agente, el envelope se
            rechaza (is_valid=False) con error explicito y se marca el
            envelope con _dispatcher_enforcement.
        - enforce_helpers=False (default): comportamiento idéntico a pre-1K.3.
          Backward compat estricto.
        - enforce_helpers=True + agente NO critico: enforcement skipped,
          validacion sigue su curso normal.
        - enforce_helpers=True + agent_name=None: no aplicable, sin enforcement.
        """
        # Bloque 1G.2: registrar invocacion
        self._record_invocation(
            "validate_return_envelope",
            context={"mode": mode, "enforce_helpers": enforce_helpers, "agent_name": agent_name},
        )
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
        elif mode == "dev_strict":
            # Dev agents devuelven status "completado" o "fallido"
            valid_status = {"completado", "fallido"}
            if response.get("status") not in valid_status:
                errores.append(f"STATUS inválido: {response.get('status')}. Para dev_strict esperado: completado o fallido")
        elif mode == "design_strict":
            # Bloque 1C.1: ux-architect / ui-designer devuelven completado o fallido
            valid_status = {"completado", "fallido"}
            if response.get("status") not in valid_status:
                errores.append(f"STATUS inválido: {response.get('status')}. Para design_strict esperado: completado o fallido")
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

        # Bloque 1A.15 + 1A.16: dev_strict requiere pre_return_audit + file declaration
        if mode == "dev_strict":
            # Solo aplica si status=completado (fallido no requiere audit — el agente fallo)
            if response.get("status") == "completado":
                # 1A.15: re-verificar pre_return_audit
                audit_errores = self.verify_pre_return_audit(response)
                errores.extend(audit_errores)

                # 1A.16: verificar que archivos sea superset real de cambios git
                decl_errores, decl_warnings = self.verify_declared_files(response)
                errores.extend(decl_errores)
                # Warnings (soft-fail) NO bloquean — solo se exponen
                if decl_warnings:
                    response.setdefault("_dispatcher_warnings", []).extend(decl_warnings)

            # archivos debe ser lista (igual que standard)
            if not isinstance(response.get("archivos", []), list):
                errores.append("archivos debe ser lista")

            if not isinstance(response.get("bloqueadores"), (list, type(None))):
                errores.append("bloqueadores debe ser lista o null")

        # Bloque 1C.1: design_strict requiere design_intelligence consultado
        if mode == "design_strict":
            if response.get("status") == "completado":
                design_errores, design_warnings = self.verify_design_intelligence(response)
                errores.extend(design_errores)
                if design_warnings:
                    response.setdefault("_dispatcher_warnings", []).extend(design_warnings)

            if not isinstance(response.get("archivos", []), list):
                errores.append("archivos debe ser lista")
            if not isinstance(response.get("bloqueadores"), (list, type(None))):
                errores.append("bloqueadores debe ser lista o null")

        # Bloque 1K.3 + 1K.4: Hard Enforcement Escalation con auto-invoke opcional
        # Solo aplica si enforce_helpers=True Y se proveyo agent_name.
        # Para agentes en CRITICAL_AGENTS con helpers faltantes:
        # - try_auto_invoke=False (default): bloquea con missing list (1K.3)
        # - try_auto_invoke=True (1K.4): intenta resolver via auto-invocacion
        #   antes de bloquear. Si resuelve todos -> ACCEPT.
        if enforce_helpers and agent_name and isinstance(response, dict):
            enforcement = self.enforce_helpers_for_agent(
                response, agent_name, try_auto_invoke=try_auto_invoke
            )
            verdict = enforcement.get("verdict")
            if verdict == "incomplete":
                missing = enforcement.get("missing_helpers", [])
                if try_auto_invoke:
                    # Detallar que se intento auto-invoke pero quedaron missing
                    auto_inv = enforcement.get("auto_invoked", [])
                    errores.append(
                        f"Hard enforcement (Bloque 1K.3/1K.4): agente critico "
                        f"'{agent_name}' tiene helpers faltantes tras intento de "
                        f"auto-invocacion. Auto-invocados: {[a['helper'] for a in auto_inv]}. "
                        f"Aun faltan: {missing}. Re-delegar."
                    )
                else:
                    errores.append(
                        f"Hard enforcement (Bloque 1K.3): agente critico "
                        f"'{agent_name}' termino sin invocar helpers obligatorios: "
                        f"{missing}. Re-delegar o invocar helpers explicitamente."
                    )
            # verdict == "auto_fixed" -> NO agrega error, envelope queda con detalle
            # verdict == "passed" / "skipped" -> sin cambios

        return len(errores) == 0, errores

    def verify_design_intelligence(
        self,
        response: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        """
        Bloque 1C.1: Verifica que el envelope incluya evidencia de consulta
        real a ui-ux-pro-max-skill (design intelligence).

        Retorna (errores, warnings):
        - errores: bloquean el envelope (campos faltantes, queried=false)
        - warnings: no bloquean (anti_generic_validated=false, etc.)

        Campos esperados en response["design_intelligence"]:
        - queried: bool (OBLIGATORIO True)
        - industry: str (recomendado)
        - style: str (recomendado)
        - verified_against: list[str] (recomendado)
        - anti_generic_validated: bool (recomendado True)
        """
        errores: List[str] = []
        warnings: List[str] = []

        di = response.get("design_intelligence")
        if di is None:
            errores.append(
                "design_intelligence obligatorio (Bloque 1C.1): el agente debe "
                "consultar ui-ux-pro-max-skill y declarar la consulta. Ver "
                "tools/skills_invocation.py o agent-protocol.md § 5."
            )
            return errores, warnings

        if not isinstance(di, dict):
            errores.append(
                f"design_intelligence debe ser objeto, recibido {type(di).__name__}"
            )
            return errores, warnings

        if "queried" not in di:
            errores.append("design_intelligence.queried obligatorio (bool)")
            return errores, warnings

        if not isinstance(di.get("queried"), bool):
            errores.append(
                f"design_intelligence.queried debe ser bool, recibido {type(di.get('queried')).__name__}"
            )
            return errores, warnings

        if di["queried"] is False:
            errores.append(
                "design_intelligence.queried=false: el agente DEBE consultar "
                "ui-ux-pro-max-skill antes de emitir output de diseño"
            )
            return errores, warnings

        # Campos recomendados (warnings, no errors)
        if not di.get("industry"):
            warnings.append("design_intelligence.industry recomendado (string)")
        if not di.get("style"):
            warnings.append("design_intelligence.style recomendado (string)")

        verified = di.get("verified_against")
        if verified is None:
            warnings.append("design_intelligence.verified_against recomendado (lista de CSVs/domains consultados)")
        elif not isinstance(verified, list):
            warnings.append(
                f"design_intelligence.verified_against debe ser lista, recibido {type(verified).__name__}"
            )
        elif len(verified) == 0:
            warnings.append("design_intelligence.verified_against esta vacio")

        agv = di.get("anti_generic_validated")
        if agv is None:
            warnings.append("design_intelligence.anti_generic_validated recomendado (bool)")
        elif agv is False:
            warnings.append("design_intelligence.anti_generic_validated=false (output puede ser generico)")

        return errores, warnings

    def consult_design_intelligence(
        self,
        query: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1C.1: Helper para que ux-architect / ui-designer consulten la
        skill desde el dispatcher.

        Retorna el resultado del SkillsInvocation.query() (ver
        tools/skills_invocation.py).

        Si la skill no esta disponible, retorna status="unavailable" — el
        caller decide si emitir envelope con `queried=false` (sera rechazado
        en design_strict) o si abortar.
        """
        self._record_invocation("consult_design_intelligence", context={"query": query[:50], "domain": domain})
        try:
            from skills_invocation import SkillsInvocation
        except ImportError as e:
            return {
                "status": "unavailable",
                "reason": f"skills_invocation no importable: {e}",
            }

        inv = SkillsInvocation()
        return inv.query(query, domain=domain)

    def run_certification_re_runs(
        self,
        qa_results: List[Dict[str, Any]],
        rerun_callback: callable,
        sample_size: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1E.1: Helper para que reality-checker invoque random re-runs
        antes de certificar.

        Toma muestra aleatoria reproducible de QA PASS, invoca rerun_callback
        para cada uno, agrega resultado.

        Args:
            qa_results: lista de QA results de Fase 3 (con campo "status")
            rerun_callback: funcion (qa_result) -> {"status": str, "details": str}
            sample_size: override (default 3 o ATLAS_REALITY_SAMPLE_SIZE)
            seed: para reproducibilidad (default None o ATLAS_REALITY_SEED)

        Retorna el verdict del runner (ver tools/reality_check_runner.py).

        Reglas operativas:
        - verdict "CONFIRMED" -> reality-checker puede certificar
        - verdict "DISCREPANCY" -> certificacion debe bloquearse
        - verdict "INCONCLUSIVE" -> no bloquea pero advierte (escalar al usuario)

        Fallback controlado: si reality_check_runner no se puede importar,
        retorna verdict "INCONCLUSIVE" con error en note. NO rompe el pipeline.
        """
        self._record_invocation("run_certification_re_runs", context={"sample_size": sample_size, "qa_count": len(qa_results) if qa_results else 0})
        try:
            from reality_check_runner import RealityCheckRunner
        except ImportError as e:
            return {
                "verdict": "INCONCLUSIVE",
                "sample_size": 0,
                "total_qa_pass": len([r for r in qa_results if isinstance(r, dict) and r.get("status") == "PASS"]),
                "rerun_results": [],
                "discrepancies": [],
                "seed": seed,
                "note": f"reality_check_runner no importable: {e}",
            }

        runner = RealityCheckRunner(seed=seed, sample_size=sample_size)
        return runner.run_re_runs(qa_results, rerun_callback)

    # ============================================================
    #  Bloque 1F.1: File Hash Caching para QA
    # ============================================================

    def should_skip_qa(
        self,
        task_id: str,
        archivos: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Bloque 1F.1: Consulta el cache de QA. Si hit, retorna el resultado
        cacheado para que evidence-collector pueda skip re-ejecucion.

        Retorna None si:
        - Cache no disponible / corrupto
        - No hay entry para task_id
        - Algun archivo cambio (hash o mtime)

        Retorna dict si hit:
        {"qa_result": {...}, "from_cache": True, "cached_at": iso, ...}

        Fail-open: si file_hash_cache no importable, retorna None (re-ejecuta QA).
        """
        self._record_invocation("should_skip_qa", context={"task_id": task_id, "archivos_count": len(archivos) if archivos else 0})
        try:
            from file_hash_cache import FileHashCache
        except ImportError:
            return None

        try:
            cache = FileHashCache(self.project_root)
            return cache.get_cached_result(task_id, archivos)
        except Exception:
            return None

    def cache_qa_result(
        self,
        task_id: str,
        archivos: List[str],
        qa_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Bloque 1F.1: Cachea un resultado QA PASS para skip futuro.

        SOLO cachea status=PASS. FAIL nunca se cachea (puede ser fix-pending).

        Fail-open: si file_hash_cache no importable, retorna
        {"cached": False, "reason": "module not importable"}.
        """
        self._record_invocation("cache_qa_result", context={"task_id": task_id, "status": qa_result.get("status") if isinstance(qa_result, dict) else None})
        try:
            from file_hash_cache import FileHashCache
        except ImportError as e:
            return {
                "cached": False,
                "reason": f"file_hash_cache no importable: {e}",
                "task_id": task_id,
            }

        try:
            cache = FileHashCache(self.project_root)
            return cache.cache_result(task_id, archivos, qa_result)
        except Exception as e:
            return {
                "cached": False,
                "reason": f"Error al cachear: {type(e).__name__}: {e}",
                "task_id": task_id,
            }

    # ============================================================
    #  Bloque 1H.1: Network Inspection
    # ============================================================

    def inspect_network_requests(
        self,
        requests: List[Dict[str, Any]],
        page_origin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1H.1: Inspecciona network requests capturados durante QA.

        Analiza requests por severidad y produce verdict:
        - CRITICAL (5xx, mixed content, network errors) -> FAIL
        - HIGH (4xx en assets criticos, redirects > 3) -> WARN
        - MEDIUM/LOW informativos -> OK

        Args:
            requests: lista de dicts con shape compatible con Playwright HAR
                      {"url": str, "status": int, "method": str,
                       "duration_ms"?: int, "error"?: str, "redirect_count"?: int}
            page_origin: URL base de la pagina (ej. "https://example.com")
                         para distinguir same-origin de cross-origin

        Retorna dict del NetworkInspector.inspect() (ver tools/network_inspector.py).

        Fail-open: si network_inspector no importable, retorna verdict OK
        con error en note. NO rompe pipeline.
        """
        self._record_invocation("inspect_network_requests", context={"requests_count": len(requests) if requests else 0, "page_origin": page_origin})
        try:
            from network_inspector import NetworkInspector
        except ImportError as e:
            return {
                "verdict": "OK",
                "issues": [],
                "summary": {"total_requests": len(requests) if requests else 0},
                "note": f"network_inspector no importable: {e}. Skip de inspeccion.",
            }

        inspector = NetworkInspector(page_origin=page_origin)
        return inspector.inspect(requests)

    # ============================================================
    #  Bloque 1H.2: Console Log Analysis
    # ============================================================

    def analyze_console_messages(
        self,
        messages: List[Dict[str, Any]],
        third_party_origin_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1H.2: Analiza console messages capturados durante QA.

        Clasifica issues por severidad:
        - CRITICAL (Uncaught, CORS, CSP, hydration mismatch, null access) -> FAIL
        - HIGH (console.error generico, React warnings criticos) -> WARN
        - MEDIUM (console.warn generico) -> OK informativo
        - LOW (console.log/info, third-party, noise) -> OK informativo

        Args:
            messages: lista de console messages con shape compatible con Playwright
                      {"type": "error|warning|log|...", "text": str,
                       "location": {"url": str, "lineNumber": int}}
            third_party_origin_patterns: regex de URLs third-party a degradar a LOW

        Retorna dict del ConsoleLogAnalyzer.analyze() (ver tools/console_log_analyzer.py).

        Fail-open: si console_log_analyzer no importable, retorna OK con note.
        """
        self._record_invocation("analyze_console_messages", context={"messages_count": len(messages) if messages else 0})
        try:
            from console_log_analyzer import ConsoleLogAnalyzer
        except ImportError as e:
            return {
                "verdict": "OK",
                "issues": [],
                "summary": {"total_messages": len(messages) if messages else 0},
                "note": f"console_log_analyzer no importable: {e}. Skip de analisis.",
            }

        analyzer = ConsoleLogAnalyzer(third_party_origin_patterns=third_party_origin_patterns)
        return analyzer.analyze(messages)

    # ============================================================
    #  Bloque 1H.3: Visual Fidelity Checker (LLM-as-judge)
    # ============================================================

    def check_visual_fidelity(
        self,
        spec: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Bloque 1H.3: Compara spec visual declarada vs evidence visual capturada.

        El agente (Claude multimodal) analiza el screenshot y produce evidence
        estructurada. Este helper compara deterministicamente contra spec y
        produce verdict.

        Args:
            spec: visual_spec del design-system con palette/typography/mood/etc.
            evidence: lo que el agente reporto tras analizar el screenshot

        Retorna dict del VisualFidelityChecker.check() (ver visual_fidelity_checker.py).

        Fail-open: si visual_fidelity_checker no importable, retorna OK con note.
        """
        self._record_invocation("check_visual_fidelity", context={"has_spec": bool(spec), "has_evidence": bool(evidence)})
        try:
            from visual_fidelity_checker import VisualFidelityChecker
        except ImportError as e:
            return {
                "verdict": "OK",
                "issues": [],
                "summary": {"total_fields_checked": 0, "issues_count": 0, "by_severity": {}},
                "note": f"visual_fidelity_checker no importable: {e}. Skip de validacion.",
            }

        checker = VisualFidelityChecker()
        return checker.check(spec, evidence)

    # ============================================================
    #  Bloque 1I.1: Anti-Loop INTER-Sesion
    # ============================================================

    def record_session_summary(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1I.1: Snapshot del delegation state al history log para
        deteccion de loops cross-session.

        Invocar al cerrar trabajo sobre una task o al cerrar sesion.
        Fail-open: errores de I/O no rompen el pipeline.
        """
        self._record_invocation("record_session_summary", context={"session_id": session_id, "task_id": task_id})
        try:
            from delegation_tracker import DelegationTracker
        except ImportError as e:
            return {"ok": False, "error": f"delegation_tracker no importable: {e}"}
        try:
            tracker = DelegationTracker(self.project_root)
            return tracker.record_session_summary(session_id, task_id)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def check_cross_session_loops(
        self,
        task_id: str,
        recent_sessions: int = 3,
    ) -> Dict[str, Any]:
        """
        Bloque 1I.1: Consulta history de las ultimas N sesiones para detectar
        si una task_id viene loopeando.

        Si una flag (escalation_needed / pause_recommended / fresh_review_recommended)
        aparece en mayoria de las ultimas sesiones para esta task -> sticky=True.

        Retorna dict con verdict ("ok" | "loop_detected") + flags_sticky.

        Fail-open: si delegation_tracker no importable, retorna verdict=ok
        con error en note. NO rompe pipeline.
        """
        self._record_invocation("check_cross_session_loops", context={"task_id": task_id, "recent_sessions": recent_sessions})
        try:
            from delegation_tracker import DelegationTracker
        except ImportError as e:
            return {
                "task_id": task_id,
                "sessions_analyzed": 0,
                "flags_sticky": {},
                "verdict": "ok",
                "loop_count": {},
                "note": f"delegation_tracker no importable: {e}",
                "history_entries": [],
            }
        try:
            tracker = DelegationTracker(self.project_root)
            return tracker.cross_session_flags(task_id, recent_sessions=recent_sessions)
        except Exception as e:
            return {
                "task_id": task_id,
                "sessions_analyzed": 0,
                "flags_sticky": {},
                "verdict": "ok",
                "loop_count": {},
                "note": f"Error en cross-session check: {type(e).__name__}: {e}",
                "history_entries": [],
            }

    # ============================================================
    #  Bloque 1G.2: Runtime Invocation Tracking
    # ============================================================

    def _record_invocation(
        self,
        helper_name: str,
        context: Optional[Dict[str, Any]] = None,
        outcome: Optional[str] = None,
    ) -> None:
        """
        Bloque 1G.2: Registra una invocacion de helper en el invocation log.
        Fail-open: silencioso si tracker no disponible o I/O falla.
        """
        try:
            from invocation_tracker import InvocationTracker
            tracker = InvocationTracker(self.project_root)
            tracker.record(helper_name, context=context, outcome=outcome)
        except Exception:
            pass  # fail-open: tracking no debe romper el helper original

    def audit_invocations(
        self,
        required_helpers: List[str],
        since_seconds: int = 300,
        context_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1G.2: Audita si los helpers requeridos fueron invocados en
        la ventana de tiempo especificada.

        Retorna dict con verdict ("complete" | "incomplete") + missing list.
        Fail-open: si tracker no importable, retorna verdict=complete con note.
        """
        try:
            from invocation_tracker import InvocationTracker
        except ImportError as e:
            return {
                "verdict": "complete",
                "required": sorted(required_helpers),
                "invoked": [],
                "missing": [],
                "extra": [],
                "total_invocations": 0,
                "window_seconds": since_seconds,
                "note": f"invocation_tracker no importable: {e}. Audit skipped.",
            }
        try:
            tracker = InvocationTracker(self.project_root)
            return tracker.audit_invocations(
                required_helpers=required_helpers,
                since_seconds=since_seconds,
                context_filter=context_filter,
            )
        except Exception as e:
            return {
                "verdict": "complete",
                "required": sorted(required_helpers),
                "invoked": [],
                "missing": [],
                "extra": [],
                "total_invocations": 0,
                "window_seconds": since_seconds,
                "note": f"Audit error (fail-open): {type(e).__name__}: {e}",
            }

    # ============================================================
    #  Bloque 1J.1: Visual Evidence Independent Verification
    # ============================================================

    def verify_design_intelligence_real(
        self,
        envelope: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Bloque 1J.1: Re-verificacion INDEPENDIENTE del campo design_intelligence
        declarado por el agente. Cierra el gap de "honestidad supuesta".

        Patron analogo a verify_pre_return_audit (Bloque 1A.15) pero para
        design intelligence: el dispatcher re-invoca skills_invocation con
        la misma industry/query que el agente declaro y verifica que el
        style declarado realmente aparezca en los resultados del skill.

        Args:
            envelope: Return Envelope con campo design_intelligence

        Retorna dict:
        {
          "verdict": "match" | "mismatch" | "unverifiable",
          "checks": [{"field": str, "status": str, "details": str}],
          "discrepancies": [...],   # subset de checks con problemas
          "skill_query_result": dict | None,
          "note": str,
        }

        Reglas de severidad:
        - Skill unavailable -> verdict=unverifiable (no rompe pipeline)
        - design_intelligence ausente o queried=false -> verdict=unverifiable
          (eso ya lo cubre verify_design_intelligence de 1C.1)
        - industry declarada NO retorna resultados del skill -> mismatch CRITICAL
          (agente declaro industria inexistente en catalogo)
        - style declarado NO aparece en results para esa industry -> mismatch HIGH
          (agente posiblemente invento el style)
        - Todo coincide -> verdict=match
        """
        self._record_invocation("verify_design_intelligence_real")
        checks: List[Dict[str, Any]] = []
        discrepancies: List[Dict[str, Any]] = []

        di = envelope.get("design_intelligence")
        if not isinstance(di, dict):
            return {
                "verdict": "unverifiable",
                "checks": [],
                "discrepancies": [],
                "skill_query_result": None,
                "note": (
                    "design_intelligence ausente o no es dict. Esto ya es "
                    "responsabilidad de validate_return_envelope(mode='design_strict') "
                    "via verify_design_intelligence (1C.1)."
                ),
            }

        if not di.get("queried", False):
            return {
                "verdict": "unverifiable",
                "checks": [],
                "discrepancies": [],
                "skill_query_result": None,
                "note": "design_intelligence.queried=false. Nada que re-verificar.",
            }

        industry = (di.get("industry") or "").strip()
        style = (di.get("style") or "").strip()

        if not industry:
            checks.append({
                "field": "design_intelligence.industry",
                "status": "missing",
                "details": "Agente no declaro industry. No se puede re-verificar.",
            })
            return {
                "verdict": "unverifiable",
                "checks": checks,
                "discrepancies": [],
                "skill_query_result": None,
                "note": "Sin industry declarada no es posible re-invocar skill.",
            }

        # Re-invocar skill con los mismos args
        try:
            from skills_invocation import SkillsInvocation
            inv = SkillsInvocation()
            if not inv.is_available():
                return {
                    "verdict": "unverifiable",
                    "checks": checks,
                    "discrepancies": [],
                    "skill_query_result": None,
                    "note": "ui-ux-pro-max-skill no disponible para re-verificacion. Skip.",
                }
            skill_result = inv.query(industry, domain="product")
        except Exception as e:
            return {
                "verdict": "unverifiable",
                "checks": checks,
                "discrepancies": [],
                "skill_query_result": None,
                "note": f"Error invocando skill: {type(e).__name__}: {e}",
            }

        if skill_result.get("status") != "ok":
            return {
                "verdict": "unverifiable",
                "checks": checks,
                "discrepancies": [],
                "skill_query_result": skill_result,
                "note": f"Skill retorno status={skill_result.get('status')}. Skip.",
            }

        # Check 1: industria devuelve resultados
        results = skill_result.get("results", [])
        count = skill_result.get("count", len(results) if isinstance(results, list) else 0)

        industry_check = {
            "field": "design_intelligence.industry",
            "declared": industry,
            "results_count": count,
        }
        if count == 0:
            industry_check["status"] = "mismatch_critical"
            industry_check["severity"] = "CRITICAL"
            industry_check["details"] = (
                f"Agente declaro industry='{industry}' pero el skill no retorno "
                f"resultados. La industria puede no existir en el catalogo "
                f"(161 industrias). Posible invencion."
            )
            discrepancies.append(industry_check)
        else:
            industry_check["status"] = "ok"
            industry_check["details"] = f"Skill encontro {count} resultado(s) para '{industry}'."
        checks.append(industry_check)

        # Check 2: style declarado aparece en resultados
        if style and count > 0:
            # Buscar style en los resultados (en Primary Style Recommendation o Secondary Styles)
            style_normalized = style.lower().strip()
            style_found = False
            matching_result = None
            for r in results:
                if not isinstance(r, dict):
                    continue
                primary = (r.get("Primary Style Recommendation") or "").lower()
                secondary = (r.get("Secondary Styles") or "").lower()
                if style_normalized in primary or style_normalized in secondary:
                    style_found = True
                    matching_result = r
                    break
                # Tambien aceptar match parcial (cada token del style declarado)
                # Esto cubre casos donde declarado="Glassmorphism" y skill dice "Glassmorphism + Flat Design"
                style_tokens = [t.strip() for t in re.split(r"[+,]", style_normalized) if t.strip()]
                if style_tokens:
                    primary_tokens = primary
                    secondary_tokens = secondary
                    if any(tok in primary_tokens or tok in secondary_tokens for tok in style_tokens):
                        style_found = True
                        matching_result = r
                        break

            style_check = {
                "field": "design_intelligence.style",
                "declared": style,
            }
            if style_found:
                style_check["status"] = "ok"
                style_check["matched_product"] = matching_result.get("Product Type") if matching_result else None
                style_check["details"] = (
                    f"Style '{style}' confirmado en resultados de skill para industry '{industry}'."
                )
            else:
                style_check["status"] = "mismatch_high"
                style_check["severity"] = "HIGH"
                style_check["available_styles"] = [
                    r.get("Primary Style Recommendation")
                    for r in results
                    if isinstance(r, dict) and r.get("Primary Style Recommendation")
                ][:5]
                style_check["details"] = (
                    f"Agente declaro style='{style}' para industry='{industry}', "
                    f"pero el skill NO lo recomienda. Posible style inventado/incorrecto."
                )
                discrepancies.append(style_check)
            checks.append(style_check)

        # Check 3: verified_against (informativo, no critico)
        verified_against = di.get("verified_against")
        if isinstance(verified_against, list):
            valid_csvs = {"styles.csv", "colors.csv", "typography.csv", "charts.csv",
                          "landing.csv", "products.csv", "ui-reasoning.csv", "ux-guidelines.csv"}
            invalid = [c for c in verified_against if c not in valid_csvs]
            if invalid:
                checks.append({
                    "field": "design_intelligence.verified_against",
                    "status": "warning",
                    "severity": "LOW",
                    "details": f"CSVs declarados que no existen en el skill: {invalid}",
                })

        # Verdict global
        has_critical_or_high = any(
            d.get("severity") in ("CRITICAL", "HIGH") for d in discrepancies
        )
        if has_critical_or_high:
            verdict = "mismatch"
            note = (
                f"MISMATCH: {len(discrepancies)} discrepancia(s) detectada(s) entre "
                f"design_intelligence declarado y skill real. Re-delegar al agente."
            )
        else:
            verdict = "match"
            note = (
                f"MATCH: design_intelligence verificado contra skill real. "
                f"Industry '{industry}' y style '{style}' confirmados."
            )

        return {
            "verdict": verdict,
            "checks": checks,
            "discrepancies": discrepancies,
            "skill_query_result": {
                "count": count,
                "domain": skill_result.get("domain"),
                "query": skill_result.get("query"),
            },
            "note": note,
        }

    # ============================================================
    #  Bloque 1J.2: Screenshot Hash Verification
    # ============================================================

    def verify_screenshot_evidence(
        self,
        evidence: Dict[str, Any],
        expected_path: Optional[str] = None,
        screenshot_path_key: str = "screenshot_path",
        screenshot_hash_key: str = "screenshot_hash",
    ) -> Dict[str, Any]:
        """
        Bloque 1J.2: Verifica que la visual_evidence reportada por el agente
        tenga un screenshot real en disco con hash verificable.

        Detecta agentes que reportan evidencia visual sin haber capturado
        realmente el screenshot. Cierra el ultimo gap honesto de
        "evidencia visual sin verificacion independiente".

        Args:
            evidence: dict con campo screenshot_path (y opcionalmente
                      screenshot_hash declarado por el agente)
            expected_path: opcional, ruta esperada (si caller sabe donde
                           deberia estar el screenshot)
            screenshot_path_key: key para path (default 'screenshot_path')
            screenshot_hash_key: key para hash declarado (default 'screenshot_hash')

        Retorna dict:
        {
          "verdict": "ok" | "mismatch" | "unverifiable",
          "checks": [{"field", "status", "details", ...}],
          "discrepancies": [...],
          "computed_hash": str | None,
          "file_exists": bool,
          "file_size": int | None,
          "note": str,
        }

        Reglas:
        - screenshot_path ausente -> unverifiable (no detecta nada)
        - File no existe -> mismatch CRITICAL (evidencia fantasma)
        - File existe + hash declarado != computado -> mismatch CRITICAL
        - File existe + sin hash declarado -> ok (compute y reporta)
        - expected_path provisto y difiere -> mismatch HIGH (screenshot incorrecto)
        - File existe + tamaño 0 bytes -> mismatch HIGH (screenshot vacio)
        - File existe + hash match (si declarado) -> ok
        """
        self._record_invocation("verify_screenshot_evidence")
        import hashlib

        checks: List[Dict[str, Any]] = []
        discrepancies: List[Dict[str, Any]] = []

        if not isinstance(evidence, dict):
            return {
                "verdict": "unverifiable",
                "checks": [],
                "discrepancies": [],
                "computed_hash": None,
                "file_exists": False,
                "file_size": None,
                "note": "evidence no es dict. Nada que verificar.",
            }

        declared_path = evidence.get(screenshot_path_key)
        declared_hash = evidence.get(screenshot_hash_key)

        if not declared_path or not isinstance(declared_path, str):
            return {
                "verdict": "unverifiable",
                "checks": [],
                "discrepancies": [],
                "computed_hash": None,
                "file_exists": False,
                "file_size": None,
                "note": (
                    f"evidence no declara {screenshot_path_key}. "
                    f"No se puede verificar."
                ),
            }

        # Resolver path: absoluto o relativo al project_root
        norm_path = declared_path.replace("\\", "/")
        if norm_path.startswith("./"):
            norm_path = norm_path[2:]
        path_obj = Path(norm_path)
        if not path_obj.is_absolute():
            path_obj = self.project_root / norm_path

        # Check 1: existe el archivo?
        file_exists = path_obj.exists() and path_obj.is_file()
        path_check = {
            "field": screenshot_path_key,
            "declared": declared_path,
            "resolved": str(path_obj),
            "exists": file_exists,
        }

        if not file_exists:
            path_check["status"] = "mismatch_critical"
            path_check["severity"] = "CRITICAL"
            path_check["details"] = (
                f"Agente declaro screenshot_path='{declared_path}' pero el archivo "
                f"NO existe en disco. Evidencia fantasma — el screenshot no se capturo."
            )
            checks.append(path_check)
            discrepancies.append(path_check)
            return {
                "verdict": "mismatch",
                "checks": checks,
                "discrepancies": discrepancies,
                "computed_hash": None,
                "file_exists": False,
                "file_size": None,
                "note": "Screenshot declarado no existe. MISMATCH CRITICAL.",
            }

        path_check["status"] = "ok"
        checks.append(path_check)

        # Check 2: expected_path si se provee
        if expected_path:
            exp_norm = expected_path.replace("\\", "/")
            if exp_norm.startswith("./"):
                exp_norm = exp_norm[2:]
            # Comparar absoluto vs absoluto
            exp_obj = Path(exp_norm)
            if not exp_obj.is_absolute():
                exp_obj = self.project_root / exp_norm
            same = (str(exp_obj.resolve()) == str(path_obj.resolve()))
            exp_check = {
                "field": f"{screenshot_path_key}_expected_match",
                "expected": expected_path,
                "declared": declared_path,
                "match": same,
            }
            if not same:
                exp_check["status"] = "mismatch_high"
                exp_check["severity"] = "HIGH"
                exp_check["details"] = (
                    f"expected_path='{expected_path}' difiere de declarado "
                    f"'{declared_path}'. Screenshot incorrecto o nombre divergente."
                )
                discrepancies.append(exp_check)
            else:
                exp_check["status"] = "ok"
            checks.append(exp_check)

        # Check 3: tamaño del archivo
        try:
            file_size = path_obj.stat().st_size
        except (OSError, IOError) as e:
            return {
                "verdict": "unverifiable",
                "checks": checks,
                "discrepancies": discrepancies,
                "computed_hash": None,
                "file_exists": True,
                "file_size": None,
                "note": f"No se pudo leer stat: {type(e).__name__}: {e}",
            }

        size_check = {
            "field": "file_size",
            "size_bytes": file_size,
        }
        if file_size == 0:
            size_check["status"] = "mismatch_high"
            size_check["severity"] = "HIGH"
            size_check["details"] = "Archivo existe pero tiene 0 bytes. Screenshot vacio."
            discrepancies.append(size_check)
        elif file_size < 1024:
            # Menor a 1KB es sospechoso para un screenshot real
            size_check["status"] = "warning"
            size_check["severity"] = "LOW"
            size_check["details"] = f"Archivo muy pequeño ({file_size} bytes). Sospechoso para screenshot."
        else:
            size_check["status"] = "ok"
        checks.append(size_check)

        # Check 4: computar hash
        try:
            h = hashlib.sha256()
            with open(path_obj, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            computed_hash = h.hexdigest()
        except (OSError, IOError) as e:
            return {
                "verdict": "unverifiable",
                "checks": checks,
                "discrepancies": discrepancies,
                "computed_hash": None,
                "file_exists": True,
                "file_size": file_size,
                "note": f"No se pudo computar hash: {type(e).__name__}: {e}",
            }

        # Check 5: comparar hash declarado si existe
        if declared_hash:
            hash_check = {
                "field": screenshot_hash_key,
                "declared": declared_hash,
                "computed": computed_hash,
            }
            # Permitir formato con prefijo "sha256:" opcional
            declared_clean = declared_hash.replace("sha256:", "").strip().lower()
            if declared_clean == computed_hash.lower():
                hash_check["status"] = "ok"
                hash_check["match"] = True
            else:
                hash_check["status"] = "mismatch_critical"
                hash_check["severity"] = "CRITICAL"
                hash_check["match"] = False
                hash_check["details"] = (
                    f"Hash declarado '{declared_hash}' != computado '{computed_hash}'. "
                    f"El agente puede haber modificado o cacheado un screenshot diferente."
                )
                discrepancies.append(hash_check)
            checks.append(hash_check)
        else:
            checks.append({
                "field": screenshot_hash_key,
                "status": "not_declared",
                "details": "Agente no declaro hash. Computado disponible para que caller lo cachee.",
                "computed": computed_hash,
            })

        # Verdict global
        has_critical = any(d.get("severity") == "CRITICAL" for d in discrepancies)
        has_high = any(d.get("severity") == "HIGH" for d in discrepancies)

        if has_critical:
            verdict = "mismatch"
            note = f"MISMATCH CRITICAL: {len(discrepancies)} discrepancia(s) graves. Bloquear evidencia."
        elif has_high:
            verdict = "mismatch"
            note = f"MISMATCH HIGH: {len(discrepancies)} discrepancia(s). Evidencia sospechosa."
        else:
            verdict = "ok"
            if declared_hash:
                note = f"Screenshot verificado: existe, tamaño OK, hash coincide ({file_size} bytes)."
            else:
                note = f"Screenshot existe ({file_size} bytes). Hash computado disponible para tracking futuro."

        return {
            "verdict": verdict,
            "checks": checks,
            "discrepancies": discrepancies,
            "computed_hash": computed_hash,
            "file_exists": True,
            "file_size": file_size,
            "note": note,
        }

    # ============================================================
    #  Bloque 1K.1: Helper Requirements Map por Subagente
    # ============================================================

    # Bloque 1K.3: Set de agentes criticos para Hard Enforcement Escalation.
    # Para estos agentes, si faltan helpers obligatorios y enforce_helpers=True
    # en validate_return_envelope, el envelope se rechaza con error explicito.
    # Otros agentes (creativos, utilidades) NO estan sujetos a este enforcement
    # — el audit sigue siendo advisory para ellos.
    CRITICAL_AGENTS = {
        "evidence-collector",  # QA Fase 3
        "reality-checker",     # Certificacion Fase 4
        "ux-architect",        # Design Fase 2
        "ui-designer",         # Design Fase 2
    }

    # Mapping subagente -> helpers obligatorios que DEBERIAN haberse invocado
    # cuando termina ese subagente. Usado por audit_helpers_for_agent().
    AGENT_HELPER_REQUIREMENTS = {
        # QA / Fase 3
        "evidence-collector": [
            "validate_return_envelope",   # qa_strict mode
            "should_skip_qa",              # cache check antes de QA
            "inspect_network_requests",    # capa 1 multi-layer QA
            "analyze_console_messages",    # capa 2
            "check_visual_fidelity",       # capa 3 (solo si verificacion=layout)
            "verify_screenshot_evidence",  # evidencia visual real (1J.2)
        ],

        # Dev agents / Fase 3
        "frontend-developer": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],
        "backend-architect": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],
        "rapid-prototyper": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],
        "mobile-developer": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],
        "xr-immersive-developer": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],
        "build-resolver": ["validate_return_envelope", "verify_pre_return_audit", "verify_declared_files"],

        # Design / Fase 2
        "ux-architect": [
            "validate_return_envelope",            # design_strict
            "consult_design_intelligence",
            "verify_design_intelligence_real",     # 1J.1
        ],
        "ui-designer": [
            "validate_return_envelope",
            "consult_design_intelligence",
            "verify_design_intelligence_real",
        ],

        # Certificacion / Fase 4
        "reality-checker": [
            "validate_return_envelope",
            "run_certification_re_runs",
        ],

        # Sin requerimientos obligatorios (creativos, utilidades, etc.)
        "project-manager-senior": [],
        "security-engineer": [],
        "brand-agent": [],
        "image-agent": [],
        "logo-agent": [],
        "video-agent": [],
        "codepen-explorer": [],
        "git": [],
        "deployer": [],
        "self-auditor": [],
        "game-designer": [],
        "api-tester": [],
        "performance-benchmarker": [],
        "seo-discovery": [],
    }

    def audit_helpers_for_agent(
        self,
        agent_name: str,
        since_seconds: int = 600,
    ) -> Dict[str, Any]:
        """
        Bloque 1K.1: Audit automatico de helpers obligatorios por subagente.

        Usado por hook PostToolUse (qa-auto-audit.js) cuando un Agent spawn
        retorna. Identifica el tipo de subagente y verifica si invoco los
        helpers esperados para ese flujo.

        Args:
            agent_name: nombre del subagente (de tool_input.subagent_type)
            since_seconds: ventana temporal (default 10 min para cubrir
                           subagentes largos)

        Retorna dict del audit_invocations() + metadata del agente:
        {
          "agent_name": str,
          "agent_known": bool,
          "required_for_agent": [...],
          "verdict": "complete" | "incomplete" | "skipped",
          ...
        }

        Comportamiento:
        - Agente desconocido (no en map) -> verdict=skipped
        - Agente con required=[] -> verdict=skipped (creativos, utilidades)
        - Agente con required helpers -> audit_invocations() y retorna verdict
        """
        self._record_invocation("audit_helpers_for_agent", context={"agent": agent_name})

        required = self.AGENT_HELPER_REQUIREMENTS.get(agent_name)
        if required is None:
            return {
                "agent_name": agent_name,
                "agent_known": False,
                "required_for_agent": [],
                "verdict": "skipped",
                "note": f"Subagente '{agent_name}' no esta en AGENT_HELPER_REQUIREMENTS. Skip.",
            }

        if len(required) == 0:
            return {
                "agent_name": agent_name,
                "agent_known": True,
                "required_for_agent": [],
                "verdict": "skipped",
                "note": f"Subagente '{agent_name}' sin helpers obligatorios. Skip.",
            }

        audit = self.audit_invocations(
            required_helpers=required,
            since_seconds=since_seconds,
        )
        audit["agent_name"] = agent_name
        audit["agent_known"] = True
        audit["required_for_agent"] = sorted(required)
        return audit

    # ============================================================
    #  Bloque 1K.3: Hard Enforcement Escalation
    # ============================================================

    # Bloque 1K.4: Set de helpers que NO se auto-invocan (auto-referentes,
    # requieren contexto no inferible, o pueden generar loops).
    # NOTA: validate_return_envelope se excluye para evitar recursion.
    NON_AUTO_INVOCABLE_HELPERS = {
        "validate_return_envelope",      # auto-referente, loop guard
        "inspect_network_requests",      # requiere lista de requests, no inferible
        "analyze_console_messages",      # requiere lista de messages, no inferible
        "check_visual_fidelity",         # requiere spec+evidence detallados
        "run_certification_re_runs",     # requiere qa_results + callback
        "verify_pre_return_audit",       # requiere campo pre_return_audit (1A.15)
        "verify_declared_files",         # requiere git diff context
    }

    def _try_auto_invoke_helpers(
        self,
        envelope: Dict[str, Any],
        missing_helpers: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Bloque 1K.4: Intenta auto-invocar helpers faltantes usando contexto
        inferible del envelope. Solo invoca si el contexto es suficiente.

        NUNCA inventa datos. Si el contexto no esta o es insuficiente, el
        helper queda en still_missing.

        Retorna dict:
        {
          "auto_invoked": [{helper, outcome, args_inferred}, ...],
          "auto_invoke_failed": [{helper, reason}, ...],
          "not_auto_invocable": [...],
          "still_missing": [...],
        }
        """
        auto_invoked: List[Dict[str, Any]] = []
        auto_invoke_failed: List[Dict[str, Any]] = []
        not_auto_invocable: List[str] = []
        still_missing: List[str] = []

        if not isinstance(envelope, dict):
            return {
                "auto_invoked": [],
                "auto_invoke_failed": [],
                "not_auto_invocable": [],
                "still_missing": list(missing_helpers),
            }

        # Inferencias compartidas
        task_id = envelope.get("tarea") or envelope.get("task_id")
        archivos = envelope.get("archivos")
        if archivos is not None and not isinstance(archivos, list):
            archivos = None

        for helper in missing_helpers:
            # Loop guard + helpers no auto-invocables
            if helper in self.NON_AUTO_INVOCABLE_HELPERS:
                not_auto_invocable.append(helper)
                still_missing.append(helper)
                continue

            # Estrategia por helper
            try:
                if helper == "should_skip_qa":
                    if not task_id or archivos is None:
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "Contexto insuficiente: requiere tarea + archivos en envelope",
                        })
                        still_missing.append(helper)
                        continue
                    self.should_skip_qa(task_id, archivos)
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "args_inferred": {"task_id": task_id, "archivos": archivos},
                    })

                elif helper == "cache_qa_result":
                    status = envelope.get("status")
                    if status != "PASS":
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": f"Solo se cachean PASS, status='{status}'. No invocado.",
                        })
                        still_missing.append(helper)
                        continue
                    if not task_id or archivos is None:
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "Contexto insuficiente: requiere tarea + archivos",
                        })
                        still_missing.append(helper)
                        continue
                    self.cache_qa_result(task_id, archivos, envelope)
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "args_inferred": {"task_id": task_id, "archivos_count": len(archivos)},
                    })

                elif helper == "verify_screenshot_evidence":
                    # Buscar screenshot_path en envelope o sub-dicts comunes
                    sp = (
                        envelope.get("screenshot_path")
                        or (envelope.get("evidence") or {}).get("screenshot_path")
                        or (envelope.get("visual_evidence") or {}).get("screenshot_path")
                    )
                    if not sp:
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "Sin screenshot_path en envelope ni en evidence/visual_evidence",
                        })
                        still_missing.append(helper)
                        continue
                    evidence_dict = {"screenshot_path": sp}
                    # Pasar hash si existe
                    sh = (
                        envelope.get("screenshot_hash")
                        or (envelope.get("evidence") or {}).get("screenshot_hash")
                        or (envelope.get("visual_evidence") or {}).get("screenshot_hash")
                    )
                    if sh:
                        evidence_dict["screenshot_hash"] = sh
                    result = self.verify_screenshot_evidence(evidence_dict)
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "verdict": result.get("verdict"),
                        "args_inferred": {"screenshot_path": sp},
                    })

                elif helper == "verify_design_intelligence_real":
                    di = envelope.get("design_intelligence")
                    if not isinstance(di, dict) or not di.get("queried"):
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "design_intelligence ausente o queried=false en envelope",
                        })
                        still_missing.append(helper)
                        continue
                    result = self.verify_design_intelligence_real(envelope)
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "verdict": result.get("verdict"),
                        "args_inferred": {"industry": di.get("industry"), "style": di.get("style")},
                    })

                elif helper == "consult_design_intelligence":
                    di = envelope.get("design_intelligence") or {}
                    industry = di.get("industry") if isinstance(di, dict) else None
                    if not industry:
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "Sin industry en design_intelligence — query no inferible",
                        })
                        still_missing.append(helper)
                        continue
                    self.consult_design_intelligence(industry, domain="product")
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "args_inferred": {"query": industry, "domain": "product"},
                    })

                elif helper == "verify_design_intelligence":
                    # 1C.1 verify (chequeo de formato del campo design_intelligence)
                    di = envelope.get("design_intelligence")
                    if not isinstance(di, dict):
                        auto_invoke_failed.append({
                            "helper": helper,
                            "reason": "design_intelligence ausente o no es dict",
                        })
                        still_missing.append(helper)
                        continue
                    self.verify_design_intelligence(envelope)
                    auto_invoked.append({
                        "helper": helper,
                        "outcome": "ok",
                        "args_inferred": {"envelope_has_di": True},
                    })

                else:
                    # Helper no contemplado en estrategia -> tratar como no auto-invocable
                    not_auto_invocable.append(helper)
                    still_missing.append(helper)

            except Exception as e:
                auto_invoke_failed.append({
                    "helper": helper,
                    "reason": f"Excepcion durante auto-invoke: {type(e).__name__}: {e}",
                })
                still_missing.append(helper)

        return {
            "auto_invoked": auto_invoked,
            "auto_invoke_failed": auto_invoke_failed,
            "not_auto_invocable": not_auto_invocable,
            "still_missing": still_missing,
        }

    def enforce_helpers_for_agent(
        self,
        envelope: Dict[str, Any],
        agent_name: str,
        since_seconds: int = 600,
        try_auto_invoke: bool = False,
    ) -> Dict[str, Any]:
        """
        Bloque 1K.3 + 1K.4: Hard enforcement para agentes criticos con
        auto-invocacion opcional de helpers faltantes (1K.4).

        Si agent_name esta en CRITICAL_AGENTS y faltan helpers obligatorios:
        - Si try_auto_invoke=False (default, 1K.3 puro): marca envelope con
          _dispatcher_enforcement y retorna verdict "incomplete".
        - Si try_auto_invoke=True (1K.4): intenta auto-invocar helpers
          faltantes usando contexto del envelope. Tras auto-invoke, re-audita.
          Si todos resueltos -> verdict "auto_fixed". Si quedan no resueltos
          -> verdict "incomplete" con detalle de auto_invoked / auto_invoke_failed.

        Para agentes NO criticos, retorna "skipped" sin afectar el envelope.

        Args:
            envelope: Return Envelope del subagente
            agent_name: nombre del subagente
            since_seconds: ventana del audit
            try_auto_invoke: Bloque 1K.4 — intentar resolver missing helpers

        Retorna dict con verdict "passed" | "auto_fixed" | "incomplete" | "skipped".
        """
        self._record_invocation(
            "enforce_helpers_for_agent",
            context={"agent_name": agent_name, "try_auto_invoke": try_auto_invoke},
        )

        is_critical = agent_name in self.CRITICAL_AGENTS

        if not is_critical:
            return {
                "verdict": "skipped",
                "agent_name": agent_name,
                "is_critical": False,
                "missing_helpers": [],
                "severity": None,
                "note": (
                    f"Agente '{agent_name}' no esta en CRITICAL_AGENTS "
                    f"(set: {sorted(self.CRITICAL_AGENTS)}). Enforcement skipped."
                ),
            }

        # Audit del agente critico
        audit = self.audit_helpers_for_agent(agent_name, since_seconds=since_seconds)

        if audit.get("verdict") != "incomplete":
            return {
                "verdict": "passed",
                "agent_name": agent_name,
                "is_critical": True,
                "missing_helpers": [],
                "severity": None,
                "note": (
                    f"Hard enforcement PASSED para '{agent_name}': "
                    f"{audit.get('note', 'all required helpers invoked')}"
                ),
            }

        # verdict == "incomplete"
        missing = audit.get("missing", [])

        # Bloque 1K.4: si try_auto_invoke=True, intentar resolver missing
        # invocando helpers con contexto del envelope antes de bloquear.
        auto_invoke_result = None
        if try_auto_invoke and missing:
            auto_invoke_result = self._try_auto_invoke_helpers(envelope, missing)
            # Re-auditar tras auto-invoke
            still_missing = auto_invoke_result["still_missing"]
            if not still_missing:
                # Todos los missing resueltos via auto-invoke
                resolved_record = {
                    "verdict": "auto_fixed",
                    "agent_name": agent_name,
                    "is_critical": True,
                    "missing_helpers": [],
                    "severity": "RESOLVED",
                    "note": (
                        f"Auto-invocation (Bloque 1K.4): {len(auto_invoke_result['auto_invoked'])} "
                        f"helper(s) auto-invocados con contexto del envelope. "
                        f"Originalmente faltaban: {missing}."
                    ),
                    "audit": {
                        "required_for_agent": audit.get("required_for_agent", []),
                        "invoked": audit.get("invoked", []),
                        "originally_missing": missing,
                        "window_seconds": audit.get("window_seconds"),
                    },
                    "auto_invoked": auto_invoke_result["auto_invoked"],
                    "auto_invoke_failed": auto_invoke_result["auto_invoke_failed"],
                    "not_auto_invocable": auto_invoke_result["not_auto_invocable"],
                }
                if isinstance(envelope, dict):
                    envelope["_dispatcher_enforcement"] = dict(resolved_record)
                return resolved_record

            # Hay still_missing -> bloqueo persistente, pero con detalle de intento
            missing = still_missing  # actualizar para el record

        enforcement_record = {
            "verdict": "incomplete",
            "agent_name": agent_name,
            "is_critical": True,
            "missing_helpers": missing,
            "severity": "HARD_BLOCK",
            "note": (
                f"Hard enforcement BLOCKED: agente critico '{agent_name}' "
                f"termino sin invocar helpers obligatorios: {missing}. "
                f"Envelope rechazado — re-delegar o invocar helpers explicitamente."
            ),
            "audit": {
                "required_for_agent": audit.get("required_for_agent", []),
                "invoked": audit.get("invoked", []),
                "missing": missing,
                "window_seconds": audit.get("window_seconds"),
            },
        }

        # Bloque 1K.4: incluir detalle del intento de auto-invoke si se hizo
        if auto_invoke_result is not None:
            enforcement_record["auto_invoked"] = auto_invoke_result["auto_invoked"]
            enforcement_record["auto_invoke_failed"] = auto_invoke_result["auto_invoke_failed"]
            enforcement_record["not_auto_invocable"] = auto_invoke_result["not_auto_invocable"]

        # Marcar el envelope (mutacion controlada — no destructiva)
        if isinstance(envelope, dict):
            envelope["_dispatcher_enforcement"] = dict(enforcement_record)

        return enforcement_record

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

        elif command == "audit-agent":
            # Bloque 1K.1: usado por hook PostToolUse para auditar helpers
            # obligatorios tras retorno de Agent spawn.
            agent_name = None
            since_seconds = 600
            for arg in sys.argv[2:]:
                if arg.startswith("--agent="):
                    agent_name = arg[len("--agent="):]
                elif arg.startswith("--since="):
                    try:
                        since_seconds = int(arg[len("--since="):])
                    except (ValueError, TypeError):
                        pass
            if not agent_name:
                print(json.dumps({
                    "verdict": "skipped",
                    "error": "missing --agent=NAME",
                }, ensure_ascii=False), file=sys.stderr)
                sys.exit(0)  # fail-open
            audit = dispatcher.audit_helpers_for_agent(agent_name, since_seconds=since_seconds)
            print(json.dumps(audit, ensure_ascii=False, indent=2))
            # Exit code: 0 si complete/skipped, 1 si incomplete
            if audit.get("verdict") == "incomplete":
                sys.exit(1)

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
