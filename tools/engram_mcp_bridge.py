#!/usr/bin/env python3
"""
Engram MCP Bridge (Bloque 1B.2)
================================

Cliente JSON-RPC stdio que habla MCP con `engram mcp --tools=agent`.

Sin dependencia externa: implementa el subset minimo del protocolo MCP
necesario para llamar a `mem_search`. Esto preserva backward compat con
entornos sin `pip install mcp`.

Lifecycle:
- Singleton lazy: subprocess spawn al primer mem_search()
- Handshake JSON-RPC (initialize + initialized notification)
- Reuso de sesion para multiples queries
- Cleanup explicito via close() o atexit

Manejo de errores:
- BinaryNotFound: engram no en PATH ni en ENGRAM_MCP_BINARY → exception explicita
- Timeout: subprocess no responde en N segundos → status="timeout"
- Crash: subprocess murio → retry 1 vez, despues timeout
- JSON parse error: respuesta malformada → status="timeout"

Activacion:
- dispatcher.enable_engram_mcp() en el orquestador
- env var ENGRAM_MCP_BINARY para override del path
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================
#  EXCEPCIONES
# ============================================================

class EngramBridgeError(Exception):
    """Error base del bridge."""
    pass


class EngramBinaryNotFound(EngramBridgeError):
    """El binario de Engram no se encuentra ni en PATH ni en ENGRAM_MCP_BINARY."""
    pass


class EngramHandshakeError(EngramBridgeError):
    """Fallo en el handshake MCP (initialize)."""
    pass


class EngramTimeout(EngramBridgeError):
    """Engram no respondio dentro del timeout."""
    pass


# ============================================================
#  BRIDGE
# ============================================================

class EngramMCPBridge:
    """
    Bridge MCP stdio para Engram.

    Uso:
        bridge = EngramMCPBridge()
        result = bridge.mem_search(project="atlas", topic_key="atlas/tareas")
        # result: {"status": "found"|"not_found"|"timeout", ...}
        bridge.close()  # opcional, atexit lo limpia
    """

    DEFAULT_TIMEOUT_S = 5.0
    HANDSHAKE_TIMEOUT_S = 3.0
    DEFAULT_TOOLS_PROFILE = "agent"

    def __init__(
        self,
        binary_path: Optional[str] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        tools_profile: str = DEFAULT_TOOLS_PROFILE,
    ):
        self._binary = self._resolve_binary(binary_path)
        self._timeout = timeout_s
        self._tools_profile = tools_profile
        self._proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._initialized = False
        self._closed = False

        # Cleanup automatico al salir
        atexit.register(self.close)

    # --------------------------------------------------------
    #  Binary resolution
    # --------------------------------------------------------

    @staticmethod
    def _resolve_binary(binary_path: Optional[str]) -> str:
        """Resuelve la ruta al binario engram. Raisea si no se encuentra."""
        # 1. Parametro explicito
        if binary_path:
            if not Path(binary_path).exists():
                raise EngramBinaryNotFound(
                    f"Binario especificado no existe: {binary_path}"
                )
            return binary_path

        # 2. Env var
        env_path = os.environ.get("ENGRAM_MCP_BINARY")
        if env_path:
            if not Path(env_path).exists():
                raise EngramBinaryNotFound(
                    f"ENGRAM_MCP_BINARY apunta a archivo inexistente: {env_path}"
                )
            return env_path

        # 3. PATH (busca 'engram' y 'engram.exe' en Windows)
        found = shutil.which("engram")
        if found:
            return found

        raise EngramBinaryNotFound(
            "engram binary no encontrado. Opciones:\n"
            "  1. Instalar: go install github.com/Gentleman-Programming/engram/cmd/engram@latest\n"
            "  2. Setear ENGRAM_MCP_BINARY a la ruta absoluta\n"
            "  3. Agregar engram al PATH"
        )

    # --------------------------------------------------------
    #  Subprocess lifecycle
    # --------------------------------------------------------

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start_subprocess(self) -> None:
        """Lanza `engram mcp --tools=<profile>` como subprocess stdio."""
        args = [self._binary, "mcp", f"--tools={self._tools_profile}"]
        try:
            self._proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,  # unbuffered, importante para stdio MCP
                text=True,
                encoding="utf-8",
            )
        except OSError as e:
            raise EngramBridgeError(f"No se pudo lanzar engram mcp subprocess: {e}")

    def _handshake(self) -> None:
        """Ejecuta initialize + initialized del protocolo MCP."""
        try:
            init_response = self._send_request_raw(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "atlas-dispatcher", "version": "1.0"},
                },
                timeout=self.HANDSHAKE_TIMEOUT_S,
            )
            if "result" not in init_response:
                raise EngramHandshakeError(
                    f"Initialize sin 'result': {init_response}"
                )

            # Notificacion initialized (sin esperar respuesta)
            self._send_notification("notifications/initialized", {})
            self._initialized = True

        except Exception as e:
            self._kill_subprocess()
            raise EngramHandshakeError(f"Handshake MCP fallo: {e}")

    def _ensure_started(self) -> None:
        """Asegura que el subprocess este corriendo + handshake completado."""
        with self._lock:
            if self._closed:
                raise EngramBridgeError("Bridge cerrado")
            if self._is_alive() and self._initialized:
                return
            # Restart si murio
            if self._proc and not self._is_alive():
                self._cleanup_dead_subprocess()
            self._start_subprocess()
            self._handshake()

    def _kill_subprocess(self) -> None:
        """Termina el subprocess sin esperar (uso interno post-error)."""
        if self._proc:
            try:
                self._proc.kill()
                self._proc.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, OSError):
                pass
        self._proc = None
        self._initialized = False

    def _cleanup_dead_subprocess(self) -> None:
        """Limpia referencias a subprocess muerto."""
        if self._proc:
            try:
                self._proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self._initialized = False

    # --------------------------------------------------------
    #  JSON-RPC core
    # --------------------------------------------------------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_request_raw(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Envia request JSON-RPC y espera respuesta."""
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise EngramBridgeError("Subprocess no esta corriendo")

        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        line = json.dumps(request) + "\n"

        # Escribir request
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise EngramBridgeError(f"No se pudo escribir request: {e}")

        # Leer response con timeout
        timeout_s = timeout if timeout is not None else self._timeout
        response_line = self._read_line_with_timeout(timeout_s)

        if not response_line:
            raise EngramTimeout(
                f"Sin respuesta de Engram para {method} en {timeout_s}s"
            )

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            raise EngramBridgeError(
                f"Respuesta MCP malformada: {e}\nLinea: {response_line[:200]}"
            )

        # Verificar que id coincide
        if response.get("id") != req_id:
            # Puede llegar una notificacion en medio — re-leer una vez
            response_line2 = self._read_line_with_timeout(timeout_s)
            if response_line2:
                try:
                    response = json.loads(response_line2)
                    if response.get("id") != req_id:
                        raise EngramBridgeError(
                            f"Response id mismatch: esperado {req_id}, "
                            f"recibido {response.get('id')}"
                        )
                except json.JSONDecodeError:
                    raise EngramBridgeError("Respuesta MCP malformada (segundo intento)")

        return response

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Envia notification JSON-RPC (sin id, sin respuesta esperada)."""
        if self._proc is None or self._proc.stdin is None:
            raise EngramBridgeError("Subprocess no esta corriendo")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        line = json.dumps(notification) + "\n"
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise EngramBridgeError(f"No se pudo escribir notification: {e}")

    def _read_line_with_timeout(self, timeout_s: float) -> Optional[str]:
        """Lee una linea de stdout con timeout. Retorna None si timeout."""
        if self._proc is None or self._proc.stdout is None:
            return None

        result_holder: list = [None]
        exception_holder: list = [None]

        def reader():
            try:
                result_holder[0] = self._proc.stdout.readline()
            except Exception as e:
                exception_holder[0] = e

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(timeout=timeout_s)

        if t.is_alive():
            # Timeout — el thread sigue bloqueado en readline()
            return None

        if exception_holder[0]:
            raise EngramBridgeError(f"Read error: {exception_holder[0]}")

        return result_holder[0]

    # --------------------------------------------------------
    #  High-level: tool calls
    # --------------------------------------------------------

    def _call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Llama un MCP tool y retorna el result envelope."""
        response = self._send_request_raw(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

        if "error" in response:
            err = response["error"]
            raise EngramBridgeError(
                f"Tool {tool_name} retorno error: {err.get('message', err)}"
            )

        if "result" not in response:
            raise EngramBridgeError(f"Response sin result: {response}")

        return response["result"]

    def mem_search(
        self,
        project: str,
        topic_key: str,
        retry_on_crash: bool = True,
    ) -> Dict[str, Any]:
        """
        Busca un cajon en Engram. Retorna dict compatible con EngramStrategy.

        Retorna:
        - {"status": "found", "observation_id": ..., "source": "engram_mcp_real"}
        - {"status": "not_found", "source": "engram_mcp_real"}
        - {"status": "timeout", "error": ..., "source": "engram_mcp_real"}
        """
        try:
            self._ensure_started()
            result = self._call_tool(
                "mem_search",
                {
                    "query": topic_key,
                    "project": project,
                    "limit": 1,
                },
            )
            return self._parse_search_result(result, topic_key)

        except EngramTimeout as e:
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "error": str(e),
                "note": "MCP timeout — fallback aplicable",
            }

        except (EngramHandshakeError, EngramBridgeError) as e:
            # Subprocess pudo haber muerto. Reintentar UNA vez.
            if retry_on_crash:
                self._kill_subprocess()
                try:
                    return self.mem_search(project, topic_key, retry_on_crash=False)
                except Exception as retry_err:
                    return {
                        "status": "timeout",
                        "source": "engram_mcp_real",
                        "error": f"Retry fallo: {retry_err}",
                        "note": "Subprocess crash + retry fallo",
                    }
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "error": str(e),
            }

    @staticmethod
    def _parse_search_result(
        result: Dict[str, Any],
        topic_key: str,
    ) -> Dict[str, Any]:
        """
        Parsea la respuesta de mem_search MCP a formato EngramStrategy.

        MCP tools/call result tiene shape:
        - {"content": [{"type": "text", "text": "..."}], "isError": bool}
        - O con structuredContent si Engram lo expone

        Heuristica:
        - Si content text contiene "No memories found" / "0 memorias" → not_found
        - Si contiene "Found N memories" o tiene observation IDs → found
        - Otherwise → not_found (conservador)
        """
        if result.get("isError"):
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "error": f"isError=true: {result}",
            }

        # Intento 1: structuredContent (MCP 2025+)
        sc = result.get("structuredContent")
        if isinstance(sc, dict):
            observations = sc.get("observations") or sc.get("results") or []
            if observations:
                obs = observations[0] if isinstance(observations, list) else observations
                obs_id = obs.get("id") or obs.get("observation_id") if isinstance(obs, dict) else None
                return {
                    "status": "found",
                    "source": "engram_mcp_real",
                    "observation_id": obs_id,
                    "topic_key": topic_key,
                }
            else:
                return {
                    "status": "not_found",
                    "source": "engram_mcp_real",
                    "topic_key": topic_key,
                }

        # Intento 2: parse content[].text
        content = result.get("content", [])
        if not isinstance(content, list):
            content = []
        full_text = " ".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).lower()

        if "no memories found" in full_text or "no observations" in full_text:
            return {
                "status": "not_found",
                "source": "engram_mcp_real",
                "topic_key": topic_key,
            }

        # Heuristica: si menciona "found" o tiene un ID-like pattern → found
        if "found" in full_text or "#" in full_text:
            return {
                "status": "found",
                "source": "engram_mcp_real",
                "topic_key": topic_key,
                "raw_text_preview": full_text[:200],
            }

        # Conservador: si no podemos parsear, asumir not_found pero anotar
        return {
            "status": "not_found",
            "source": "engram_mcp_real",
            "topic_key": topic_key,
            "note": "Respuesta MCP no clasificable, asumido not_found",
        }

    # --------------------------------------------------------
    #  Cleanup
    # --------------------------------------------------------

    def close(self) -> None:
        """Termina el subprocess limpiamente. Idempotente."""
        if self._closed:
            return
        self._closed = True

        if self._proc is None:
            return

        try:
            if self._is_alive():
                # Intentar shutdown limpio
                try:
                    self._send_notification("shutdown", {})
                except Exception:
                    pass
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=1.0)
        except Exception:
            pass
        finally:
            self._proc = None
            self._initialized = False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
