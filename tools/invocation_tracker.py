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
- RETENCION (roadmap P2): acotado a un segmento actual + un archivo
  (invocation-log.1.jsonl), ~2 MB cada uno, via tools/bounded_jsonl.py. Los
  eventos mas viejos que el archivo se descartan por diseno. Appends con lock
  cross-process (el log sin lock tenia 165 lineas truncadas). Las lecturas
  (get_recent / _read_log) van del final hacia atras y no deserializan todo el
  historial. Un log legacy gigante se migra una vez: sus ultimos 2 MB quedan
  como archivo y el original se renombra a invocation-log.legacy-*.jsonl
  (nunca se borra ni se lee por codigo).
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

try:  # tools/ is on sys.path for the dispatcher and the suites
    from bounded_jsonl import BoundedJsonl
except ImportError:  # package-style import
    from tools.bounded_jsonl import BoundedJsonl


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
        # Retention (roadmap P2): current segment stays at log_path; one archive
        # (invocation-log.1.jsonl). Appends are cross-process locked.
        self._store = BoundedJsonl(self.log_path)

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
            res = self._store.append(entry)
            if not res.ok:
                return {"ok": False, "error": res.error}
            out = {"ok": True, "entry": entry}
            if res.rotation_error:
                out["rotation_error"] = res.rotation_error
            return out
        except (OSError, IOError) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _read_log(self, max_lines: int = 10000) -> List[Dict[str, Any]]:
        """Ultimas `max_lines` lineas (oldest -> newest) leidas desde el final del log,
        sin deserializar el historial completo. Saltea entries malformadas."""
        try:
            return self._store.tail_entries(max_lines)
        except (OSError, IOError):
            return []

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
        # Cutoff is fixed BEFORE any I/O: a slow (cold) read must not shift the window.
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=since_seconds)
        filter_set = set(helper_filter) if helper_filter else None
        try:
            window = self._store.recent_entries(cutoff, ts_key="timestamp")
        except (OSError, IOError):
            return []
        if filter_set:
            return [e for e in window if e.get("helper") in filter_set]
        return window

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
            # Counts cover the RETAINED window only (current + one archive segment).
            "total_entries": len(entries),
            "unique_helpers": len(helpers_count),
            "invocations_by_helper": helpers_count,
            "log_path": str(self.log_path),
            "exists": self._store.exists(),
            "retention": self._store.status(),
        }

    def clear(self) -> None:
        """Elimina el log y su segmento de archivo (uso para tests o reset explicito)."""
        self._store.clear()
