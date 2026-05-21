#!/usr/bin/env python3
"""
ATLAS Dispatcher — Orchestration Engine
Ejecuta el pipeline de 5 fases con enforcement de gates, QA obligatorio, y Return Envelope validation.
NO hace trabajo real — solo coordina y valida.
"""

import os
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

    def validate_return_envelope(self, response: Dict[str, Any], mode: str = "standard") -> Tuple[bool, List[str]]:
        """
        Validar que la respuesta del subagente sigue el formato Return Envelope.
        Retorna: (is_valid, errores)

        Modos:
        - "standard": validación suave (para creativos, utilidades, etc.)
        - "qa_strict": validación estricta para evidence-collector (QA obligatorio)
        - "dev_strict": validación para dev-agents — requiere pre_return_audit (Bloque 1A.15)
        - "design_strict": validación para ux-architect / ui-designer —
                           requiere design_intelligence consultado (Bloque 1C.1)
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
