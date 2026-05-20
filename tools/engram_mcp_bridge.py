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
import re
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
    def _extract_observation_id_from_text(text: str) -> Optional[int]:
        """
        Extrae el observation_id (entero) del texto de respuesta de mem_search.

        Formato observado en Engram v1.15.10:
            '[1] #33 (decision) — Title...'
            '[1] #obs-xxx (decision) — Title...' (fallback hex)

        Retorna el primer ID encontrado como int (preferido) o None si no parsea.
        """
        # Buscar #<entero> (formato actual de Engram)
        m = re.search(r"#(\d+)\b", text)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, OverflowError):
                pass
        return None

    @staticmethod
    def _parse_search_result(
        result: Dict[str, Any],
        topic_key: str,
    ) -> Dict[str, Any]:
        """
        Parsea la respuesta de mem_search MCP a formato EngramStrategy.

        Bloque 1B.4: parser mejorado para extraer observation_id real (entero)
        del preview text. Eso habilita el segundo paso del 2-step pattern.

        MCP tools/call result shape:
        - {"content": [{"type": "text", "text": "<JSON-encoded string>"}], "isError": bool}
        - El text es JSON con campos {project, result, ...}
        - result es texto humano con preview + observation_ids como #<int>
        """
        if result.get("isError"):
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "error": f"isError=true: {result}",
            }

        # Intento 1: structuredContent (MCP 2025+, no usado por Engram v1.15.10 aun)
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

        # Intento 2: parse content[].text (formato actual de Engram v1.15.10)
        content = result.get("content", [])
        if not isinstance(content, list):
            content = []
        raw_text = " ".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
        # raw_text es JSON-encoded — intentar decodificar para extraer .result
        result_text = raw_text
        try:
            inner = json.loads(raw_text)
            if isinstance(inner, dict) and "result" in inner:
                result_text = inner["result"]
        except (json.JSONDecodeError, ValueError):
            pass  # raw_text no es JSON, usar tal cual

        result_text_lower = result_text.lower()

        if "no memories found" in result_text_lower or "no observations" in result_text_lower:
            return {
                "status": "not_found",
                "source": "engram_mcp_real",
                "topic_key": topic_key,
            }

        # Found: extraer observation_id del preview
        obs_id = EngramMCPBridge._extract_observation_id_from_text(result_text)

        if "found" in result_text_lower or obs_id is not None:
            return {
                "status": "found",
                "source": "engram_mcp_real",
                "observation_id": obs_id,
                "topic_key": topic_key,
                "raw_text_preview": result_text[:200],
            }

        # Conservador: si no podemos parsear, asumir not_found pero anotar
        return {
            "status": "not_found",
            "source": "engram_mcp_real",
            "topic_key": topic_key,
            "note": "Respuesta MCP no clasificable, asumido not_found",
        }

    # --------------------------------------------------------
    #  Bloque 1B.4: mem_get_observation (2-step pattern)
    # --------------------------------------------------------

    def mem_get_observation(
        self,
        observation_id: int,
        retry_on_crash: bool = True,
    ) -> Dict[str, Any]:
        """
        Bloque 1B.4: Segundo paso del patron 2-step.

        Llama al tool `mem_get_observation` de Engram MCP para obtener el
        contenido COMPLETO (no truncado) de una observation previamente
        ubicada via mem_search.

        Args:
            observation_id: ID entero retornado por mem_search.
            retry_on_crash: Si True (default), reintenta UNA vez si el
                            subprocess se cayo.

        Retorna dict con shape:
        - {"status": "found", "content": "<texto completo>", "id": int,
           "raw_result": "...", "source": "engram_mcp_real", ...}
        - {"status": "not_found", "id": int, ...} si observation no existe
        - {"status": "timeout", "error": ..., ...} en timeout/error

        IMPORTANTE: timeout y error NO se confunden con not_found.
        """
        try:
            self._ensure_started()
            result = self._call_tool(
                "mem_get_observation",
                {"id": observation_id},
            )
            return self._parse_get_observation_result(result, observation_id)

        except EngramTimeout as e:
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "id": observation_id,
                "error": str(e),
                "note": "mem_get_observation timeout",
            }

        except (EngramHandshakeError, EngramBridgeError) as e:
            if retry_on_crash:
                self._kill_subprocess()
                try:
                    return self.mem_get_observation(observation_id, retry_on_crash=False)
                except Exception as retry_err:
                    return {
                        "status": "timeout",
                        "source": "engram_mcp_real",
                        "id": observation_id,
                        "error": f"Retry fallo: {retry_err}",
                    }
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "id": observation_id,
                "error": str(e),
            }

    @staticmethod
    def _parse_get_observation_result(
        result: Dict[str, Any],
        observation_id: int,
    ) -> Dict[str, Any]:
        """
        Parsea respuesta de mem_get_observation MCP.

        Formato observado en Engram v1.15.10:
        - content[0].text es JSON-encoded
        - inner JSON tiene {project, project_path, result}
        - result es texto completo (~2-3KB para decisions)
        - Empieza con "#<id> [<type>] <title>" seguido del content completo
        """
        if result.get("isError"):
            return {
                "status": "timeout",
                "source": "engram_mcp_real",
                "id": observation_id,
                "error": f"isError=true: {result}",
            }

        content = result.get("content", [])
        if not isinstance(content, list):
            content = []
        raw_text = " ".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )

        # Intentar decodificar JSON envelope
        result_text = raw_text
        project = None
        try:
            inner = json.loads(raw_text)
            if isinstance(inner, dict):
                result_text = inner.get("result", raw_text)
                project = inner.get("project")
        except (json.JSONDecodeError, ValueError):
            pass

        if not result_text or not result_text.strip():
            return {
                "status": "not_found",
                "source": "engram_mcp_real",
                "id": observation_id,
                "note": "Respuesta vacia — observation puede no existir",
            }

        # Detectar errores semanticos comunes
        rt_lower = result_text.lower()
        if "not found" in rt_lower or "no such observation" in rt_lower or "does not exist" in rt_lower:
            return {
                "status": "not_found",
                "source": "engram_mcp_real",
                "id": observation_id,
            }

        # Extraer metadata del result (formato Engram v1.15.10):
        #   "#<id> [<type>] <title>\n<body>\n...Session:...\nTopic:...\n..."
        type_match = re.match(r"#\d+\s*\[([^\]]+)\]\s*(.+?)(?:\n|$)", result_text)
        obs_type = type_match.group(1).strip() if type_match else None
        title = type_match.group(2).strip() if type_match else None

        topic_match = re.search(r"^Topic:\s*(.+)$", result_text, re.MULTILINE)
        topic_key = topic_match.group(1).strip() if topic_match else None

        return {
            "status": "found",
            "source": "engram_mcp_real",
            "id": observation_id,
            "content": result_text,  # texto completo
            "title": title,
            "type": obs_type,
            "topic_key": topic_key,
            "project": project,
            "raw_length": len(result_text),
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
