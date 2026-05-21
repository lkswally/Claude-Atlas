#!/usr/bin/env python3
"""
Invocation Tracker (Bloque 1G.2)
=================================

Append-only log de invocaciones de helpers del dispatcher. Permite auditar
en runtime si el orquestador/agentes realmente invocaron los helpers
obligatorios que documenta el agent-protocol (1G.1).

PATRON:
- Cada helper obligatorio del dispatcher registra su invocacion automaticamente
- El log es append-only en .pipeline/invocation-log.jsonl
- Audit query lee el log y compara contra una lista de helpers esperados

DIFERENCIA CON 1G.1:
- 1G.1 documenta en prompts (anti-regresion documental, no garantia runtime)
- 1G.2 instrumenta el codigo Python (garantia real: si el helper fue llamado,
  queda registro; si no fue llamado, queda evidencia objetiva)

ALCANCE HONESTO:
- SOLO trackea helpers del dispatcher Python — NO trackea tool calls
  Read/Edit/Write del agente (eso es delegation_tracker 1D.1)
- Requiere que el dispatcher se invoque desde Python — si el agente no
  pasa por el dispatcher (ej. salta directo a herramientas), no hay log
- Audit es opt-in: el orquestador debe consultar `audit_invocations()`
  en momentos clave
"""

import copy
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ============================================================
#  CONSTANTES
# ============================================================

LOG_VERSION = 1

# Helpers que se trackean automaticamente al ser invocados desde dispatcher
TRACKED_HELPERS = {
    "validate_return_envelope",
    "verify_pre_return_audit",
    "verify_declared_files",
    "verify_design_intelligence",
    "consult_design_intelligence",
    "get_cajon_full",
    "resolve_ambiguous_project",
    "should_skip_qa",
    "cache_qa_result",
    "run_certification_re_runs",
    "inspect_network_requests",
    "analyze_console_messages",
    "check_visual_fidelity",
    "record_session_summary",
    "check_cross_session_loops",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
#  TRACKER
# ============================================================

class InvocationTracker:
    """Append-only log de invocaciones de helpers."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.log_dir = self.project_root / ".pipeline"
        self.log_path = self.log_dir / "invocation-log.jsonl"

    def record(
        self,
        helper_name: str,
        context: Optional[Dict[str, Any]] = None,
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registra una invocacion del helper.

        Args:
            helper_name: nombre del helper invocado (ej. "validate_return_envelope")
            context: metadata opcional (mode, task_id, phase, etc.)
            outcome: "ok" | "error" | "fallback" | etc.

        Retorna dict con la entry escrita o error.

        Fail-open: si I/O falla, NO rompe la operacion original.
        """
        try:
            entry = {
                "version": LOG_VERSION,
                "helper": helper_name,
                "timestamp": _now_iso(),
                "context": context or {},
                "outcome": outcome,
            }
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
            return {"ok": True, "entry": entry}
        except (OSError, IOError) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _read_log(self, max_lines: int = 10000) -> List[Dict[str, Any]]:
        """Lee el log con cap de seguridad. Saltea entries malformadas."""
        if not self.log_path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-max_lines:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
        except (OSError, IOError):
            return []
        return entries

    def get_recent(
        self,
        since_seconds: int = 300,
        helper_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retorna invocaciones recientes (default ultimo 5 min).

        Args:
            since_seconds: ventana de tiempo desde ahora
            helper_filter: si se especifica, solo retorna esos helpers
        """
        entries = self._read_log()
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=since_seconds)
        filter_set = set(helper_filter) if helper_filter else None

        recent: List[Dict[str, Any]] = []
        for e in entries:
            ts_str = e.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
            if ts < cutoff:
                continue
            if filter_set and e.get("helper") not in filter_set:
                continue
            recent.append(e)
        return recent

    def audit_invocations(
        self,
        required_helpers: List[str],
        since_seconds: int = 300,
        context_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Audita si los helpers requeridos fueron invocados en la ventana de tiempo.

        Args:
            required_helpers: lista de helpers que DEBERIAN haberse invocado
            since_seconds: ventana temporal (default 5 min)
            context_filter: si se especifica, solo cuenta invocaciones cuyo
                            context matchea (ej. {"phase": "fase_3"})

        Retorna dict:
        {
          "verdict": "complete" | "incomplete",
          "required": [...],
          "invoked": [...],
          "missing": [...],
          "extra": [...],  # invocaciones presentes que no estaban requeridas
          "total_invocations": N,
          "window_seconds": N,
          "note": str,
        }
        """
        recent = self.get_recent(since_seconds=since_seconds)

        # Aplicar context_filter si existe
        if context_filter:
            filtered = []
            for e in recent:
                ctx = e.get("context") or {}
                if all(ctx.get(k) == v for k, v in context_filter.items()):
                    filtered.append(e)
            recent = filtered

        invoked_set: Set[str] = set()
        for e in recent:
            helper = e.get("helper")
            if helper:
                invoked_set.add(helper)

        required_set = set(required_helpers)
        missing = sorted(required_set - invoked_set)
        extra = sorted(invoked_set - required_set)

        verdict = "complete" if not missing else "incomplete"
        if missing:
            note = (
                f"Helpers requeridos NO invocados en ventana de {since_seconds}s: "
                f"{missing}. Verificar cumplimiento del agent-protocol § 4.8."
            )
        else:
            note = (
                f"Todos los helpers requeridos invocados ({len(required_set)}) "
                f"en ventana de {since_seconds}s."
            )

        return {
            "verdict": verdict,
            "required": sorted(required_set),
            "invoked": sorted(invoked_set),
            "missing": missing,
            "extra": extra,
            "total_invocations": len(recent),
            "window_seconds": since_seconds,
            "note": note,
        }

    def stats(self) -> Dict[str, Any]:
        """Estadisticas del log (para debugging)."""
        entries = self._read_log()
        helpers_count: Dict[str, int] = {}
        for e in entries:
            h = e.get("helper")
            if h:
                helpers_count[h] = helpers_count.get(h, 0) + 1
        return {
            "total_entries": len(entries),
            "unique_helpers": len(helpers_count),
            "invocations_by_helper": helpers_count,
            "log_path": str(self.log_path),
            "exists": self.log_path.exists(),
        }

    def clear(self) -> None:
        """Elimina el log (uso para tests o reset explicito)."""
        try:
            if self.log_path.exists():
                self.log_path.unlink()
        except OSError:
            pass
