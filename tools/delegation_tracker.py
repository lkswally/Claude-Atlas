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


# ============================================================
#  DETERMINISTIC NEXT TRANSITION (external_safe_adoption_design_v1)
# ============================================================
#
# Adaptado de un patrón observado en Gentle AI v2.5.0 (Receipt-Driven
# Development): el consumidor de un estado no debe reconstruir la acción
# a partir de flags/prosa ambiguos — debe recibir un único next-step
# determinístico. Ver docs/external_safe_adoption_design_v1.md.
#
# Antes: orchestrator-delegation.md §6 dejaba la decisión en manos de
# interpretar 3 booleans independientes ("if escalation_needed: # ...").
# Ahora: esta función deriva UN string determinístico de esos mismos
# flags. Advisory only — no cambia el enforcement del dispatcher, y
# `flags` se preserva sin cambios para compatibilidad y detalle.

NEXT_TRANSITIONS = ("CONTINUE", "RETRY_WITH_NEW_EVIDENCE", "BLOCK")


def derive_next_transition(flags: Optional[Dict[str, Any]]) -> str:
    """
    Deriva un único next-step determinístico a partir de delegation-state flags.

    Precedencia (más a menos severo):
      pause_recommended
        -> "BLOCK"
      escalation_needed o fresh_review_recommended
        -> "RETRY_WITH_NEW_EVIDENCE"
      ninguno activo
        -> "CONTINUE"

    Pura función de flags -> string. Sin side effects, sin I/O, sin excepciones
    (flags ausente/None/corrupto cae a CONTINUE via .get() con default False).

    Subconjunto deliberado de los 6 estados que describe la referencia externa
    (CONTINUE | RETRY_WITH_NEW_EVIDENCE | BLOCK | HUMAN_APPROVAL | ROLLBACK |
    COMPLETE): HUMAN_APPROVAL ya está cubierto por la confirmación git/deployer
    existente; ROLLBACK y COMPLETE son conceptos de fase/dispatcher, no de
    delegation-state — no se fuerza una correspondencia falsa aquí.
    """
    flags = flags or {}
    if flags.get("pause_recommended"):
        return "BLOCK"
    if flags.get("escalation_needed") or flags.get("fresh_review_recommended"):
        return "RETRY_WITH_NEW_EVIDENCE"
    return "CONTINUE"

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
        # Bloque 1I.1: append-only log para anti-loop INTER-sesion
        self.history_path = self.state_dir / "delegation-history.jsonl"

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
        # Deterministic Next Transition (external_safe_adoption_design_v1):
        # se recalcula en cada escritura para que siempre refleje `flags`.
        state["next_transition"] = derive_next_transition(state.get("flags"))
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

    # ----------------------------------------------------------
    #  Bloque 1I.1: Anti-Loop INTER-sesion (persistencia historica)
    # ----------------------------------------------------------

    def record_session_summary(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bloque 1I.1: Append-only snapshot del state actual al history log.

        Llamar al cerrar una sesion o al cerrar trabajo sobre una task_id
        especifica. La entry queda en `.pipeline/delegation-history.jsonl`
        para consulta cross-session.

        Args:
            session_id: identificador de la sesion (ej. ISO timestamp o UUID)
            task_id: opcional, task especifica que se cierra (ej. "atlas/tarea-3")

        Retorna dict con la entry escrita + ok/error status.

        Fail-open: si I/O falla, retorna {"ok": False, "error": ...} sin
        romper. La caller decide si actuar sobre el error.
        """
        try:
            state = self._load_state()
            entry = {
                "session_id": session_id,
                "task_id": task_id,
                "timestamp": _now_iso(),
                "flags": dict(state.get("flags", {})),
                "consecutive_reads": state.get("consecutive_reads", 0),
                "total_tool_calls_since_spawn": state.get("total_tool_calls_since_spawn", 0),
                "files_modified_count": len(state.get("files_modified", [])),
                "files_modified": list(state.get("files_modified", []))[:20],  # cap para no inflar log
                "last_tool": state.get("last_tool"),
                "version": 1,
            }

            self.state_dir.mkdir(parents=True, exist_ok=True)
            # Append-only: simple append en jsonl (atomic enough para append corto)
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return {"ok": True, "entry": entry, "path": str(self.history_path)}
        except (OSError, IOError) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "session_id": session_id}

    def _read_history(self, max_lines: int = 1000) -> List[Dict[str, Any]]:
        """Lee history log con max_lines de seguridad. Saltea entries malformadas."""
        if not self.history_path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Tomar las ultimas max_lines
            for line in lines[-max_lines:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue  # skip malformed
        except (OSError, IOError):
            return []
        return entries

    def cross_session_flags(
        self,
        task_id: str,
        recent_sessions: int = 3,
    ) -> Dict[str, Any]:
        """
        Bloque 1I.1: Analiza historial de las ultimas N sesiones para detectar
        loops persistentes en una task_id especifica.

        Si una flag (escalation_needed / pause_recommended / fresh_review_recommended)
        aparece en >= 2 de las ultimas `recent_sessions` entries de esta task_id,
        se marca como sticky cross-session.

        Args:
            task_id: identificador de tarea para filtrar history
            recent_sessions: cuantas sesiones recientes considerar (default 3)

        Retorna dict:
        {
          "task_id": str,
          "sessions_analyzed": N,
          "flags_sticky": {
            "escalation_needed_sticky": bool,
            "pause_recommended_sticky": bool,
            "fresh_review_recommended_sticky": bool,
          },
          "verdict": "ok" | "loop_detected",
          "loop_count": {flag_name: count_across_sessions},
          "note": str,
          "history_entries": [...],
        }

        Reglas:
        - Si task_id NO aparece en history -> verdict=ok, sin flags
        - Si task_id aparece pero ninguna flag dispara -> verdict=ok
        - Si una flag aparece >= 2 veces en las ultimas N sesiones -> sticky=True
        - Si cualquier flag es sticky -> verdict=loop_detected
        """
        if not task_id:
            return {
                "task_id": task_id,
                "sessions_analyzed": 0,
                "flags_sticky": {
                    "escalation_needed_sticky": False,
                    "pause_recommended_sticky": False,
                    "fresh_review_recommended_sticky": False,
                },
                "verdict": "ok",
                "loop_count": {},
                "note": "task_id vacio — no se puede analizar",
                "history_entries": [],
            }

        all_entries = self._read_history()
        # Filtrar por task_id, ordenar por timestamp descendente
        task_entries = [
            e for e in all_entries
            if isinstance(e, dict) and e.get("task_id") == task_id
        ]
        # Las ultimas N (asumimos que el log ya esta cronologico — append-only)
        recent = task_entries[-recent_sessions:]

        loop_count = {
            "escalation_needed": 0,
            "pause_recommended": 0,
            "fresh_review_recommended": 0,
        }
        for entry in recent:
            flags = entry.get("flags", {})
            for flag_name in loop_count.keys():
                if flags.get(flag_name):
                    loop_count[flag_name] += 1

        # Sticky si aparece >= 2 veces (mayoria en 3 sesiones)
        stickiness_threshold = max(2, len(recent) // 2 + 1) if len(recent) >= 2 else 99
        flags_sticky = {
            f"{name}_sticky": (count >= stickiness_threshold)
            for name, count in loop_count.items()
        }

        any_sticky = any(flags_sticky.values())
        verdict = "loop_detected" if any_sticky else "ok"

        if any_sticky:
            sticky_names = [k for k, v in flags_sticky.items() if v]
            note = (
                f"LOOP cross-session detectado en task '{task_id}': flags {sticky_names} "
                f"presentes en >= {stickiness_threshold} de las ultimas {len(recent)} sesiones. "
                f"Escalar inmediatamente — no esperar nuevos triggers intra-sesion."
            )
        elif len(recent) == 0:
            note = f"task '{task_id}' no tiene entries en history. Primera vez vista."
        else:
            note = (
                f"task '{task_id}' analizada en {len(recent)} sesiones recientes. "
                f"Sin flags persistentes — operacion normal."
            )

        return {
            "task_id": task_id,
            "sessions_analyzed": len(recent),
            "flags_sticky": flags_sticky,
            "verdict": verdict,
            "loop_count": loop_count,
            "note": note,
            "history_entries": recent,
        }

    def history_stats(self) -> Dict[str, Any]:
        """Estadisticas del history log (para debugging / observabilidad ligera)."""
        entries = self._read_history()
        task_ids = sorted(set(e.get("task_id") for e in entries if e.get("task_id")))
        sessions = sorted(set(e.get("session_id") for e in entries if e.get("session_id")))
        return {
            "total_entries": len(entries),
            "unique_task_ids": len(task_ids),
            "unique_sessions": len(sessions),
            "history_path": str(self.history_path),
            "exists": self.history_path.exists(),
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
