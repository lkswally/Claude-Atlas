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
    ):
        self._callback = callback
        self._fallback = fallback
        self._name = name

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
