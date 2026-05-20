#!/usr/bin/env python3
"""
Delegation Tracker (Bloque 1D.1)
=================================

Tracker que cuenta tool calls del agente y dispara flags cuando se
exceden thresholds. Adaptado del benchmark claude-vibecoding.

Thresholds:
- 5+ Reads consecutivas -> escalation_needed (sugerir Explore o cambio de enfoque)
- 20+ tool calls sin Agent spawn -> pause_recommended
- 2+ archivos modificados no-triviales -> fresh_review_recommended

Reset al detectar tool call de Agent (spawn de subagente).

Persistencia:
- {project_root}/.pipeline/delegation-state.json
- Atomic write (tmpfile + rename)
- Fail-open: si state file corrupto, se recrea con valores default

NO bloquea tool calls. Es advisory — el orquestador (o el usuario)
decide si actuar sobre los flags.

Uso desde hook (PostToolUse):
    python tools/delegation_tracker.py record --tool=Read --file=src/foo.ts

Uso programatico:
    tracker = DelegationTracker(project_root)
    tracker.record_tool_call("Read", {"file_path": "src/foo.ts"})
    state = tracker.get_state()
    if state["flags"]["escalation_needed"]: ...
"""

import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
#  THRESHOLDS (basados en benchmark claude-vibecoding)
# ============================================================

THRESHOLD_CONSECUTIVE_READS = 5
THRESHOLD_TOOL_CALLS_WITHOUT_SPAWN = 20
THRESHOLD_NON_TRIVIAL_FILES_MODIFIED = 2

# Tools que se consideran "lecturas" para el contador de reads consecutivas
READ_TOOLS = {"Read", "Glob", "Grep"}

# Tool de spawn de subagente — resetea contadores
SPAWN_TOOLS = {"Agent", "Task"}

# Tools que modifican archivos — tracked para fresh_review
MUTATING_TOOLS = {"Edit", "Write", "NotebookEdit"}

# Paths excluidos del conteo de "files modificados no-triviales"
# (artefactos de pipeline, tests, configs no son non-trivial en este contexto)
TRIVIAL_PATH_PREFIXES = (
    ".pipeline/",
    "_qa/temp/",
    "node_modules/",
    "dist/",
    "build/",
    ".claude/worktrees/",
    ".next/",
    ".cache/",
)
TRIVIAL_PATH_SUFFIXES = (
    ".md",          # docs
    ".txt",         # plain text
    ".log",         # logs
    ".json",        # configs (json)
    ".yml",         # configs (yaml)
    ".yaml",
    ".lock",        # lockfiles
)


def _is_non_trivial_path(path: str, project_root: Optional[Path] = None) -> bool:
    """Determina si una modificacion en este path cuenta para fresh_review.

    Maneja paths absolutos: si el path empieza con project_root, lo convierte
    a relativo antes de verificar exclusiones.
    """
    if not path:
        return False
    norm = path.replace("\\", "/")
    if norm.startswith("./"):
        norm = norm[2:]

    # Si project_root esta provisto, hacer path relativo
    if project_root is not None:
        try:
            root_norm = str(project_root).replace("\\", "/").rstrip("/") + "/"
            if norm.startswith(root_norm):
                norm = norm[len(root_norm):]
        except Exception:
            pass  # fall through con path original

    if any(norm.startswith(p) for p in TRIVIAL_PATH_PREFIXES):
        return False
    if any(norm.endswith(s) for s in TRIVIAL_PATH_SUFFIXES):
        return False
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
#  TRACKER
# ============================================================

DEFAULT_STATE: Dict[str, Any] = {
    "consecutive_reads": 0,
    "total_tool_calls_since_spawn": 0,
    "files_modified": [],
    "flags": {
        "escalation_needed": False,
        "pause_recommended": False,
        "fresh_review_recommended": False,
    },
    "last_tool": None,
    "last_updated": None,
    "version": 1,
}


class DelegationTracker:
    """Tracker persistente con reglas del benchmark claude-vibecoding."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.state_dir = self.project_root / ".pipeline"
        self.state_path = self.state_dir / "delegation-state.json"

    # ----------------------------------------------------------
    #  Persistencia
    # ----------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        """Carga state desde disco. Si corrupto o ausente, retorna default."""
        if not self.state_path.exists():
            return copy.deepcopy(DEFAULT_STATE)
        try:
            content = self.state_path.read_text(encoding="utf-8")
            state = json.loads(content)
            # Validacion minima: si version no coincide o falta campo, reset
            if not isinstance(state, dict) or state.get("version") != 1:
                return copy.deepcopy(DEFAULT_STATE)
            # Merge con defaults para campos faltantes (forward-compat)
            merged = copy.deepcopy(DEFAULT_STATE)
            merged.update(state)
            if "flags" not in state or not isinstance(state.get("flags"), dict):
                merged["flags"] = dict(DEFAULT_STATE["flags"])
            else:
                merged_flags = dict(DEFAULT_STATE["flags"])
                merged_flags.update(state["flags"])
                merged["flags"] = merged_flags
            return merged
        except (OSError, json.JSONDecodeError, ValueError):
            # State corrupto: log y reset a default (fail-open)
            return copy.deepcopy(DEFAULT_STATE)

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Guarda state atomicamente (tmpfile + rename)."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = _now_iso()
        # Atomic write: escribir a tmpfile en mismo directorio, despues rename
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.state_dir),
            delete=False,
            prefix=".delegation-state-",
            suffix=".tmp",
        )
        try:
            json.dump(state, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            # Rename atomico
            os.replace(tmp.name, self.state_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    # ----------------------------------------------------------
    #  API publica
    # ----------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Lee state actual desde disco."""
        return self._load_state()

    def reset(self) -> None:
        """Resetea state a default (uso para tests o nuevo agent spawn)."""
        self._save_state(copy.deepcopy(DEFAULT_STATE))

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Registra un tool call y actualiza contadores + flags.

        Retorna el state actualizado.

        NO raisea — fail-open por diseño (no rompemos el flujo del agente).
        """
        try:
            state = self._load_state()

            # Reset al spawn de Agent/Task
            if tool_name in SPAWN_TOOLS:
                state["consecutive_reads"] = 0
                state["total_tool_calls_since_spawn"] = 0
                state["files_modified"] = []
                state["flags"] = dict(DEFAULT_STATE["flags"])
                state["last_tool"] = tool_name
                self._save_state(state)
                return state

            # Contador de tool calls totales (todos excepto Agent)
            state["total_tool_calls_since_spawn"] = state.get("total_tool_calls_since_spawn", 0) + 1

            # Contador de Reads consecutivas
            if tool_name in READ_TOOLS:
                state["consecutive_reads"] = state.get("consecutive_reads", 0) + 1
            else:
                state["consecutive_reads"] = 0

            # Tracking de archivos modificados no-triviales
            if tool_name in MUTATING_TOOLS and isinstance(tool_input, dict):
                file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
                if file_path and _is_non_trivial_path(file_path, project_root=self.project_root):
                    if file_path not in state.get("files_modified", []):
                        state.setdefault("files_modified", []).append(file_path)

            # Evaluar flags STICKY: una vez activados, quedan True hasta el
            # proximo Agent spawn (que los resetea). Evita que un Edit puntual
            # desactive escalation_needed cuando el agente acaba de hacer 5
            # Reads consecutivas.
            flags = state.get("flags", copy.deepcopy(DEFAULT_STATE["flags"]))
            flags["escalation_needed"] = (
                flags.get("escalation_needed", False)
                or state["consecutive_reads"] >= THRESHOLD_CONSECUTIVE_READS
            )
            flags["pause_recommended"] = (
                flags.get("pause_recommended", False)
                or state["total_tool_calls_since_spawn"] >= THRESHOLD_TOOL_CALLS_WITHOUT_SPAWN
            )
            flags["fresh_review_recommended"] = (
                flags.get("fresh_review_recommended", False)
                or len(state.get("files_modified", [])) >= THRESHOLD_NON_TRIVIAL_FILES_MODIFIED
            )
            state["flags"] = flags

            state["last_tool"] = tool_name
            self._save_state(state)
            return state

        except Exception as e:
            # Fail-open: si tracker falla, no debe romper el flujo del agente
            return {
                "error": f"DelegationTracker failed: {type(e).__name__}: {e}",
                "tool_name": tool_name,
            }

    def active_warnings(self) -> List[str]:
        """Retorna lista de warnings activos (para reportar al usuario/agente)."""
        state = self._load_state()
        flags = state.get("flags", {})
        warnings = []
        if flags.get("escalation_needed"):
            warnings.append(
                f"escalation_needed: {state['consecutive_reads']} reads consecutivas "
                f"(threshold {THRESHOLD_CONSECUTIVE_READS}). Considerar Explore agent o cambio de enfoque."
            )
        if flags.get("pause_recommended"):
            warnings.append(
                f"pause_recommended: {state['total_tool_calls_since_spawn']} tool calls sin spawn "
                f"(threshold {THRESHOLD_TOOL_CALLS_WITHOUT_SPAWN}). Considerar delegar a subagente."
            )
        if flags.get("fresh_review_recommended"):
            files = state.get("files_modified", [])
            warnings.append(
                f"fresh_review_recommended: {len(files)} archivos no-triviales modificados "
                f"(threshold {THRESHOLD_NON_TRIVIAL_FILES_MODIFIED}). Considerar re-leer dependencias."
            )
        return warnings


# ============================================================
#  CLI (para uso desde hook)
# ============================================================

def main() -> int:
    """
    Uso CLI:
        python tools/delegation_tracker.py record --tool=Read --file=src/foo.ts
        python tools/delegation_tracker.py status
        python tools/delegation_tracker.py reset
    """
    if len(sys.argv) < 2:
        print("Uso: delegation_tracker.py {record|status|reset} [args]", file=sys.stderr)
        return 2

    project_root = Path.cwd()
    tracker = DelegationTracker(project_root)

    cmd = sys.argv[1]

    if cmd == "record":
        # Parsear flags simples
        tool_name = None
        file_path = None
        for arg in sys.argv[2:]:
            if arg.startswith("--tool="):
                tool_name = arg[len("--tool="):]
            elif arg.startswith("--file="):
                file_path = arg[len("--file="):]

        if not tool_name:
            print("Error: --tool=TOOL_NAME requerido", file=sys.stderr)
            return 2

        tool_input = {"file_path": file_path} if file_path else None
        state = tracker.record_tool_call(tool_name, tool_input)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        # Exit 0 siempre (fail-open). Si hay warnings los emitimos por stderr.
        for w in tracker.active_warnings():
            print(f"[delegation-tracker] WARN: {w}", file=sys.stderr)
        return 0

    elif cmd == "status":
        state = tracker.get_state()
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "reset":
        tracker.reset()
        print("Reset OK")
        return 0

    else:
        print(f"Comando desconocido: {cmd}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
