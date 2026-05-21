#!/usr/bin/env python3
"""
File Hash Cache (Bloque 1F.1)
==============================

Cache con SHA256 para que evidence-collector (Fase 3) pueda skip re-ejecucion
de QA cuando los archivos involucrados no cambiaron desde el ultimo PASS.

ALCANCE HONESTO:
- SOLO cachea resultados PASS (FAIL nunca se cachea — puede ser fix-pending)
- Trackea hashes SHA256 + mtime de los archivos del envelope
- NO trackea cambios externos (deps, env, build config) — solo archivos
- Fail-open si cache corrupto (re-ejecuta QA, NO falso PASS)

API:
    cache = FileHashCache(project_root)
    hashes = cache.compute_hashes(["src/foo.ts", "src/bar.ts"])
    hit = cache.get_cached_result(task_id="tarea-3", archivos=[...])
    if hit:
        # usar hit["qa_result"]
    else:
        # ejecutar QA normal, despues:
        cache.cache_result(task_id, archivos, qa_result)

Persistencia:
- {project_root}/.pipeline/qa-cache.json
- Atomic write (tmpfile + os.replace)
- Schema versionado (version: 1)
- Prune automatico de entries > 14 dias

Invalidacion:
- Hash mismatch -> miss
- mtime actual > mtime cacheado -> miss (paranoid)
- Archivo no existe -> miss
"""

import copy
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
#  CONSTANTES
# ============================================================

CACHE_VERSION = 1
DEFAULT_MAX_AGE_DAYS = 14
CHUNK_SIZE = 65536  # 64 KB para SHA256

DEFAULT_STATE: Dict[str, Any] = {
    "version": CACHE_VERSION,
    "entries": {},  # {task_id: {hashes, mtimes, qa_result, cached_at}}
    "last_pruned": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(path: str) -> str:
    """Normaliza path: backslash -> slash, sin './' inicial."""
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


# ============================================================
#  CACHE
# ============================================================

class FileHashCache:
    """Cache SHA256 de archivos para skip de QA redundante."""

    def __init__(
        self,
        project_root: Path,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ):
        self.project_root = Path(project_root)
        self.cache_dir = self.project_root / ".pipeline"
        self.cache_path = self.cache_dir / "qa-cache.json"
        self.max_age_days = max_age_days

    # ----------------------------------------------------------
    #  Hashing
    # ----------------------------------------------------------

    def compute_hashes(
        self,
        archivos: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Computa SHA256 + mtime para cada archivo.

        Retorna dict: {file_path_normalized: {"sha256": str, "mtime": float}}
        Si un archivo no existe o falla I/O, NO se incluye en el resultado
        (caller debe detectar y tratar como cache miss).
        """
        result: Dict[str, Dict[str, Any]] = {}
        for raw_path in archivos:
            norm = _normalize_path(raw_path)
            full = self.project_root / norm if not Path(norm).is_absolute() else Path(norm)

            try:
                if not full.exists() or not full.is_file():
                    continue
                stat = full.stat()
                h = hashlib.sha256()
                with open(full, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        h.update(chunk)
                result[norm] = {
                    "sha256": h.hexdigest(),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                }
            except (OSError, IOError):
                # Skip archivo problematico — no rompe el cache
                continue
        return result

    # ----------------------------------------------------------
    #  Persistencia
    # ----------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        """Carga state desde disco. Si corrupto/ausente, retorna default."""
        if not self.cache_path.exists():
            return copy.deepcopy(DEFAULT_STATE)
        try:
            content = self.cache_path.read_text(encoding="utf-8")
            state = json.loads(content)
            if not isinstance(state, dict) or state.get("version") != CACHE_VERSION:
                return copy.deepcopy(DEFAULT_STATE)
            # Merge defaults para forward-compat
            merged = copy.deepcopy(DEFAULT_STATE)
            merged.update(state)
            if "entries" not in state or not isinstance(state["entries"], dict):
                merged["entries"] = {}
            return merged
        except (OSError, json.JSONDecodeError, ValueError):
            # Fail-open: cache corrupto -> reset
            return copy.deepcopy(DEFAULT_STATE)

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Guarda state atomicamente."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.cache_dir),
            delete=False,
            prefix=".qa-cache-",
            suffix=".tmp",
        )
        try:
            json.dump(state, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, self.cache_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    # ----------------------------------------------------------
    #  API principal
    # ----------------------------------------------------------

    def get_cached_result(
        self,
        task_id: str,
        archivos: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta cache para un task_id + archivos.

        Retorna None si:
        - No hay entry para task_id
        - Algun archivo no existe en disco
        - Algun hash NO coincide (archivo cambio)
        - Algun mtime es mas nuevo que el cacheado (paranoid mode)
        - Entry expirada (> max_age_days)

        Retorna dict si hit:
        {"qa_result": {...}, "cached_at": iso, "task_id": str,
         "hash_version": int, "from_cache": True}
        """
        try:
            state = self._load_state()
        except Exception:
            return None

        entry = state.get("entries", {}).get(task_id)
        if not entry:
            return None

        # Check expiracion
        cached_at_str = entry.get("cached_at")
        if cached_at_str:
            try:
                cached_at = datetime.fromisoformat(cached_at_str)
                age = datetime.now(timezone.utc) - cached_at
                if age > timedelta(days=self.max_age_days):
                    return None
            except (ValueError, TypeError):
                return None

        # Re-computar hashes actuales y comparar
        current_hashes = self.compute_hashes(archivos)
        cached_hashes = entry.get("hashes", {})

        # Normalizar archivos pedidos
        requested = {_normalize_path(a) for a in archivos}

        # Si algun archivo pedido no aparece en current_hashes → miss
        # (archivo no existe → no podemos confirmar coincidencia)
        for f in requested:
            if f not in current_hashes:
                return None

        # Si el set de archivos cacheados no coincide con el pedido → miss
        if set(cached_hashes.keys()) != requested:
            return None

        # Comparar hashes Y mtimes
        for f, cached_meta in cached_hashes.items():
            current_meta = current_hashes.get(f)
            if not current_meta:
                return None
            if cached_meta.get("sha256") != current_meta.get("sha256"):
                return None
            # Paranoid: si mtime actual > cacheado, invalidar aunque hash coincida
            cached_mtime = cached_meta.get("mtime", 0)
            current_mtime = current_meta.get("mtime", 0)
            if current_mtime > cached_mtime + 0.001:  # tolerancia float
                return None

        # HIT
        return {
            "qa_result": entry.get("qa_result"),
            "cached_at": entry.get("cached_at"),
            "task_id": task_id,
            "hash_version": entry.get("hash_version", 1),
            "from_cache": True,
        }

    def cache_result(
        self,
        task_id: str,
        archivos: List[str],
        qa_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Cachea un resultado QA. SOLO si qa_result["status"] == "PASS".

        Retorna dict con metadata del cache write:
        {"cached": bool, "reason": str (si no cached), "task_id": str,
         "files_cached": int}
        """
        if not isinstance(qa_result, dict):
            return {
                "cached": False,
                "reason": f"qa_result debe ser dict, recibido {type(qa_result).__name__}",
                "task_id": task_id,
            }

        status = qa_result.get("status")
        if status != "PASS":
            return {
                "cached": False,
                "reason": f"Solo se cachean PASS, recibido status={status}",
                "task_id": task_id,
            }

        try:
            current_hashes = self.compute_hashes(archivos)
            if not current_hashes:
                return {
                    "cached": False,
                    "reason": "No se pudo hashear ningun archivo (no existen o I/O error)",
                    "task_id": task_id,
                }

            # Cargar state, agregar/actualizar entry, guardar
            state = self._load_state()
            state.setdefault("entries", {})
            state["entries"][task_id] = {
                "hashes": current_hashes,
                "qa_result": qa_result,
                "cached_at": _now_iso(),
                "hash_version": 1,
            }
            self._save_state(state)

            return {
                "cached": True,
                "task_id": task_id,
                "files_cached": len(current_hashes),
                "cached_at": state["entries"][task_id]["cached_at"],
            }
        except Exception as e:
            return {
                "cached": False,
                "reason": f"Error al cachear: {type(e).__name__}: {e}",
                "task_id": task_id,
            }

    def invalidate(self, task_id: str) -> bool:
        """Elimina entry de un task_id especifico. Retorna True si elimino algo."""
        try:
            state = self._load_state()
            if task_id in state.get("entries", {}):
                del state["entries"][task_id]
                self._save_state(state)
                return True
            return False
        except Exception:
            return False

    def clear(self) -> None:
        """Resetea todo el cache."""
        self._save_state(copy.deepcopy(DEFAULT_STATE))

    def prune_old(self, max_age_days: Optional[int] = None) -> int:
        """
        Elimina entries > max_age_days.

        Retorna numero de entries eliminadas.
        Fail-open: si error de I/O, retorna 0.
        """
        if max_age_days is None:
            max_age_days = self.max_age_days

        try:
            state = self._load_state()
            entries = state.get("entries", {})
            if not entries:
                return 0

            cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
            removed = 0
            to_remove = []
            for task_id, entry in entries.items():
                cached_at_str = entry.get("cached_at")
                if not cached_at_str:
                    to_remove.append(task_id)
                    continue
                try:
                    cached_at = datetime.fromisoformat(cached_at_str)
                    if cached_at < cutoff:
                        to_remove.append(task_id)
                except (ValueError, TypeError):
                    to_remove.append(task_id)

            for task_id in to_remove:
                del entries[task_id]
                removed += 1

            if removed > 0:
                state["last_pruned"] = _now_iso()
                self._save_state(state)

            return removed
        except Exception:
            return 0

    def stats(self) -> Dict[str, Any]:
        """Retorna estadisticas del cache (para debugging/observabilidad)."""
        try:
            state = self._load_state()
            entries = state.get("entries", {})
            return {
                "total_entries": len(entries),
                "version": state.get("version"),
                "last_pruned": state.get("last_pruned"),
                "cache_path": str(self.cache_path),
                "task_ids": sorted(entries.keys()),
            }
        except Exception as e:
            return {"error": str(e)}
