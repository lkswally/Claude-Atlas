#!/usr/bin/env python3
"""
Engram Strategy Pattern (Bloque 1B.1)
=====================================

PROPOSITO HONESTO:
Este modulo NO es "Engram MCP Real Integration" cerrada.
Es preparacion arquitectonica para que 1B.2 conecte el MCP real
sin tener que refactorizar el dispatcher de nuevo.

ESTADO:
- DiskFallbackStrategy: implementacion default — busca en .pipeline/{cajon}.md
  (es el mismo comportamiento que tenia _check_engram_cajon hasta 1A.16)
- EngramStrategy interface: contrato que cualquier implementacion futura debe cumplir
- ProtocolError: excepciones especificas para distinguir error vs not_found

LO QUE FALTA (1B.2):
- MCPBridgeStrategy: implementacion REAL que llama a mem_search() via MCP
  (decision pendiente: Python MCP SDK vs subprocess vs agent-delegation)

CONVENCION DE NAMING:
- NO usar "engram_proxy" — eso era el nombre engañoso anterior
- USAR "disk_fallback" — refleja honestamente lo que es
- USAR "engram_real" SOLO cuando 1B.2 conecte MCP de verdad
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class ProtocolError(Exception):
    """Error de protocolo Engram (timeout, ambiguous_project, etc.).
    Se distingue de 'not_found' para no confundir error con ausencia."""
    pass


class EngramStrategy(ABC):
    """
    Interfaz que cualquier estrategia de Engram debe cumplir.

    Contrato:
    - check_cajon() retorna dict con campo 'status': "found" | "not_found" | "timeout"
    - Puede agregar campos extra: observation_id, source, error, note
    - NUNCA debe raisear excepciones — capturar y mapear a status="timeout"
      (responsabilidad del strategy implementer)
    """

    @abstractmethod
    def check_cajon(self, proyecto: str, cajon: str) -> Dict[str, Any]:
        """Verifica existencia del cajon. Retorna dict con status + metadata."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador honesto de la estrategia (logging + debugging)."""
        raise NotImplementedError

    def get_observation(
        self,
        observation_id: Any,
        cajon: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Bloque 1B.4: segundo paso del 2-step pattern.

        Obtiene el contenido COMPLETO de una observation. Retorna:
        - dict con shape {"status": "found", "content": str, ...} si existe
        - dict con shape {"status": "not_found", ...} si no existe
        - dict con shape {"status": "timeout", ...} si error
        - None si la estrategia NO soporta get_observation (interfaz opcional)

        Default: None (subclase debe implementar si soporta el 2-step).
        Implementaciones que no soportan get_observation deben retornar None
        para que el caller pueda decidir fallback.
        """
        return None


class DiskFallbackStrategy(EngramStrategy):
    """
    DEFAULT strategy: busca en disco como fuente de verdad.

    NO es Engram real. Es disk fallback que coincide con el comportamiento
    pre-1B.1 (cuando _check_engram_cajon leia .pipeline/{cajon}.md).

    Cuando 1B.2 introduzca MCPBridgeStrategy, esta strategy se convertira en
    fallback secundario (cuando el MCP real falla).
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    @property
    def name(self) -> str:
        return "disk_fallback"

    def check_cajon(self, proyecto: str, cajon: str) -> Dict[str, Any]:
        """Verifica si .pipeline/{cajon_name}.md existe en disco."""
        try:
            cajon_name = cajon.split("/")[-1]
            disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"

            if disk_path.exists():
                return {
                    "status": "found",
                    "cajon": cajon,
                    "source": "disk_fallback",
                    "path": str(disk_path),
                }
            else:
                return {
                    "status": "not_found",
                    "cajon": cajon,
                    "source": "disk_fallback",
                }

        except (OSError, IOError) as e:
            return {
                "status": "timeout",
                "cajon": cajon,
                "source": "disk_fallback",
                "error": str(e),
                "note": "Disk I/O error — tratado como timeout",
            }

    def get_observation(
        self,
        observation_id: Any,
        cajon: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Bloque 1B.4: Para disk_fallback, observation_id no aplica directamente
        (los archivos no tienen IDs numericos). Si se pasa el cajon, retornamos
        el contenido del archivo .pipeline/{cajon}.md completo.

        Si solo se pasa observation_id sin cajon -> None (no podemos resolver).
        """
        if cajon is None:
            return None
        try:
            cajon_name = cajon.split("/")[-1]
            disk_path = self.project_root / ".pipeline" / f"{cajon_name}.md"
            if not disk_path.exists():
                return {
                    "status": "not_found",
                    "source": "disk_fallback",
                    "cajon": cajon,
                }
            content = disk_path.read_text(encoding="utf-8", errors="replace")
            return {
                "status": "found",
                "source": "disk_fallback",
                "cajon": cajon,
                "content": content,
                "raw_length": len(content),
                "path": str(disk_path),
                "title": None,  # disk_fallback no expone metadata estructurada
                "type": None,
                "topic_key": cajon,
            }
        except (OSError, IOError) as e:
            return {
                "status": "timeout",
                "source": "disk_fallback",
                "cajon": cajon,
                "error": str(e),
            }


class CallbackStrategy(EngramStrategy):
    """
    Strategy basada en callback inyectable.

    El callback recibe (proyecto, cajon) y retorna dict con 'status' + metadata.
    Si el callback raisea Exception, se captura y se mapea a status="timeout"
    para que el dispatcher pueda fallback a disco.

    Esta strategy es el plugin point para 1B.2: el orquestador (o test) inyecta
    un callback que llama a mem_search() real via MCP.
    """

    def __init__(
        self,
        callback: Callable[[str, str], Dict[str, Any]],
        fallback: Optional[EngramStrategy] = None,
        name: str = "callback",
        get_observation_callback: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ):
        self._callback = callback
        self._fallback = fallback
        self._name = name
        # Bloque 1B.4: callback opcional para mem_get_observation
        self._get_observation_callback = get_observation_callback

    @property
    def name(self) -> str:
        return self._name

    def check_cajon(self, proyecto: str, cajon: str) -> Dict[str, Any]:
        """Invoca el callback. Si falla o retorna timeout, prueba fallback."""
        try:
            result = self._callback(proyecto, cajon)
        except Exception as e:
            # Callback exception → mapear a timeout, intentar fallback
            err_result = {
                "status": "timeout",
                "cajon": cajon,
                "source": self._name,
                "error": f"Callback raised: {type(e).__name__}: {e}",
                "note": "Callback exception — fallback intentado si configurado",
            }
            if self._fallback is not None:
                fb_result = self._fallback.check_cajon(proyecto, cajon)
                # Si fallback encontro algo, usar eso pero anotar el callback fallo
                if fb_result["status"] == "found":
                    fb_result["fallback_used"] = True
                    fb_result["callback_error"] = err_result["error"]
                    return fb_result
            return err_result

        # Validar formato minimo
        if not isinstance(result, dict) or "status" not in result:
            return {
                "status": "timeout",
                "cajon": cajon,
                "source": self._name,
                "error": f"Callback returned invalid format: {result!r}",
            }

        # Status timeout / ambiguous_project / etc → intentar fallback si hay
        if result["status"] in {"timeout", "ambiguous_project"} and self._fallback is not None:
            fb_result = self._fallback.check_cajon(proyecto, cajon)
            if fb_result["status"] == "found":
                fb_result["fallback_used"] = True
                fb_result["callback_status"] = result["status"]
                return fb_result

        # Status normal (found / not_found) o sin fallback configurado
        result.setdefault("source", self._name)
        return result

    def get_observation(
        self,
        observation_id: Any,
        cajon: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Bloque 1B.4: 2-step pattern — segundo paso.

        Si hay get_observation_callback configurado, lo invoca. Si falla o no
        existe, intenta fallback.get_observation(observation_id, cajon).
        timeout/error NUNCA se confunden con not_found.
        """
        if self._get_observation_callback is None:
            # Sin callback de get_observation -> delegate a fallback si soporta
            if self._fallback is not None:
                fb = self._fallback.get_observation(observation_id, cajon)
                if fb is not None:
                    return fb
            return None

        try:
            result = self._get_observation_callback(observation_id)
        except Exception as e:
            err_result = {
                "status": "timeout",
                "source": self._name,
                "id": observation_id,
                "error": f"get_observation callback raised: {type(e).__name__}: {e}",
            }
            if self._fallback is not None and cajon is not None:
                fb = self._fallback.get_observation(observation_id, cajon)
                if fb is not None and fb.get("status") == "found":
                    fb["fallback_used"] = True
                    fb["callback_error"] = err_result["error"]
                    return fb
            return err_result

        if not isinstance(result, dict) or "status" not in result:
            return {
                "status": "timeout",
                "source": self._name,
                "id": observation_id,
                "error": f"get_observation returned invalid format: {result!r}",
            }

        # timeout del callback → intentar fallback
        if result["status"] == "timeout" and self._fallback is not None and cajon is not None:
            fb = self._fallback.get_observation(observation_id, cajon)
            if fb is not None and fb.get("status") == "found":
                fb["fallback_used"] = True
                fb["callback_status"] = "timeout"
                return fb

        result.setdefault("source", self._name)
        return result


# ============================================================
#  MCP BRIDGE STRATEGY (Bloque 1B.2)
# ============================================================

def make_mcp_bridge_strategy(
    binary_path: Optional[str] = None,
    timeout_s: float = 5.0,
    use_disk_fallback: bool = True,
    project_root: Optional[Path] = None,
) -> EngramStrategy:
    """
    Factory para Engram MCP Real Strategy (Bloque 1B.2).

    Crea CallbackStrategy con bridge MCP stdio + DiskFallbackStrategy como
    red de seguridad.

    Args:
        binary_path: Ruta al binario engram. Si None, busca en ENGRAM_MCP_BINARY
                     o PATH.
        timeout_s: Timeout por query (default 5s).
        use_disk_fallback: Si True (default), disk_fallback se activa cuando
                           el bridge falla (binary missing, timeout, crash).
        project_root: Necesario si use_disk_fallback=True.

    Raises:
        EngramBinaryNotFound: Si binary no se encuentra (ANTES de retornar).
                              El caller debe capturar y caer a disk_fallback
                              explicitamente si quiere comportamiento graceful.

    Returns:
        EngramStrategy lista para inyectar en dispatcher.set_engram_callback().
    """
    # Import lazy para no requerir el bridge si no se activa
    from engram_mcp_bridge import EngramMCPBridge

    bridge = EngramMCPBridge(binary_path=binary_path, timeout_s=timeout_s)

    fallback: Optional[EngramStrategy] = None
    if use_disk_fallback:
        if project_root is None:
            raise ValueError(
                "use_disk_fallback=True requiere project_root para DiskFallbackStrategy"
            )
        fallback = DiskFallbackStrategy(project_root)

    def callback(proyecto: str, cajon: str) -> Dict[str, Any]:
        return bridge.mem_search(project=proyecto, topic_key=cajon)

    def get_obs_callback(observation_id: Any) -> Dict[str, Any]:
        # Bloque 1B.4: segundo paso del 2-step pattern
        if not isinstance(observation_id, int):
            try:
                observation_id = int(observation_id)
            except (ValueError, TypeError):
                return {
                    "status": "timeout",
                    "id": observation_id,
                    "error": f"observation_id debe ser entero, recibido {type(observation_id).__name__}",
                }
        return bridge.mem_get_observation(observation_id)

    strategy = CallbackStrategy(
        callback=callback,
        fallback=fallback,
        name="engram_mcp_real",
        get_observation_callback=get_obs_callback,
    )
    # Mantener referencia al bridge para cleanup explicito si se necesita
    strategy._bridge = bridge  # type: ignore
    return strategy
