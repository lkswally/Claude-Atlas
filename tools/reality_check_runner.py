#!/usr/bin/env python3
"""
Reality Check Runner (Bloque 1E.1)
===================================

Sampler aleatorio reproducible + re-ejecutor + comparador para que
reality-checker (Fase 4) revalide muestras de QA PASS antes de certificar.

ALCANCE HONESTO:
- SOLO cubre random re-runs de tareas QA PASS antes de certificacion
- NO cubre re-runs de E2E flows complejos
- NO modifica evidence-collector ni su contrato
- NO valida cobertura — 3 muestras de N tareas sigue siendo bajo coverage,
  pero es mejora incremental honesta sobre confianza ciega

ARQUITECTURA:
- El runner es generico: acepta lista de QA results + callable que sabe
  como re-ejecutar UNA tarea
- El callable lo provee el caller (reality-checker o test). Esto desacopla
  el runner de cualquier QA-flow especifico (Playwright, network, etc.)

API:
    runner = RealityCheckRunner(seed=42)
    verdict = runner.run_re_runs(
        qa_results=[{"tarea": "T1", "status": "PASS", ...}, ...],
        rerun_callback=my_rerun_fn,
        sample_size=3,
    )
    # verdict = {
    #   "verdict": "CONFIRMED" | "DISCREPANCY" | "INCONCLUSIVE",
    #   "sample_size": int,
    #   "total_qa_pass": int,
    #   "rerun_results": [...],
    #   "discrepancies": [...],
    #   ...
    # }

Sample size:
- Default: 3
- Override: env var ATLAS_REALITY_SAMPLE_SIZE
- Si N qa_results < sample_size → toma todos los disponibles
- Si N qa_results == 0 → verdict "INCONCLUSIVE" con warning

Seed:
- Default: None (no determinista)
- Param: seed=int para reproducibilidad (tests, debugging)
- Env var: ATLAS_REALITY_SEED para fijar global
"""

import os
import random
from typing import Any, Callable, Dict, List, Optional


# ============================================================
#  CONSTANTES
# ============================================================

DEFAULT_SAMPLE_SIZE = 3

VALID_VERDICTS = {"CONFIRMED", "DISCREPANCY", "INCONCLUSIVE"}
VALID_RERUN_OUTCOMES = {"CONFIRMED", "DISCREPANCY", "INCONCLUSIVE"}


# ============================================================
#  RUNNER
# ============================================================

class RealityCheckRunner:
    """
    Sampler + re-ejecutor + comparador para certificacion (Fase 4).

    Generico: el caller provee el rerun_callback que sabe como re-ejecutar
    una tarea. El runner solo orquesta: samplea, invoca el callback,
    compara, agrega resultados.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        sample_size: Optional[int] = None,
    ):
        # Resolver sample_size (param > env > default)
        if sample_size is None:
            env_val = os.environ.get("ATLAS_REALITY_SAMPLE_SIZE")
            if env_val:
                try:
                    sample_size = int(env_val)
                except (ValueError, TypeError):
                    sample_size = DEFAULT_SAMPLE_SIZE
            else:
                sample_size = DEFAULT_SAMPLE_SIZE
        if sample_size < 1:
            sample_size = 1
        self.sample_size = sample_size

        # Resolver seed (param > env > None)
        if seed is None:
            env_seed = os.environ.get("ATLAS_REALITY_SEED")
            if env_seed:
                try:
                    seed = int(env_seed)
                except (ValueError, TypeError):
                    seed = None
        self.seed = seed
        self._rng = random.Random(seed) if seed is not None else random.Random()

    def sample(
        self,
        qa_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Selecciona una muestra aleatoria de qa_results con status='PASS'.

        Comportamiento:
        - Filtra solo los que tienen status='PASS'
        - Si hay <= sample_size, retorna todos
        - Si hay mas, samplea sin reemplazo
        - Con seed fija → reproducible
        - Si lista vacia → retorna []
        """
        if not qa_results:
            return []

        pass_results = [
            r for r in qa_results
            if isinstance(r, dict) and r.get("status") == "PASS"
        ]

        if not pass_results:
            return []

        if len(pass_results) <= self.sample_size:
            # Devolver TODOS sin sampleo (no podemos hacer sample > N)
            # Mantenemos orden estable para que la verificacion sea predecible
            return list(pass_results)

        # Sample sin reemplazo
        return self._rng.sample(pass_results, self.sample_size)

    def run_re_runs(
        self,
        qa_results: List[Dict[str, Any]],
        rerun_callback: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Ejecuta re-runs sobre muestra aleatoria de qa_results.

        Args:
            qa_results: lista de resultados de QA con status PASS/FAIL/...
            rerun_callback: funcion que recibe un qa_result y retorna un
                            dict con shape:
                            {"status": "PASS"|"FAIL"|"INCONCLUSIVE",
                             "details": str, ...}

        Retorna dict con shape:
            {
              "verdict": "CONFIRMED" | "DISCREPANCY" | "INCONCLUSIVE",
              "sample_size": int,
              "total_qa_pass": int,
              "rerun_results": [{
                "tarea": str,
                "original": str,
                "rerun": str,
                "verdict": "CONFIRMED"|"DISCREPANCY"|"INCONCLUSIVE",
                "details": str,
              }, ...],
              "discrepancies": [...],
              "seed": int|None,
              "note": str,
            }

        Reglas de verdict global:
        - Sin QA PASS disponible → INCONCLUSIVE (warning, no block)
        - Algun rerun retorna FAIL distinto a PASS original → DISCREPANCY
        - Todos los reruns confirman el PASS original → CONFIRMED
        - Reruns que arrojan INCONCLUSIVE → si todos los demas CONFIRMED,
          verdict global es CONFIRMED (los INCONCLUSIVE no bloquean por
          si solos, solo se reportan)

        IMPORTANTE: Si rerun_callback raisea excepcion, se captura y la
        rerun se marca como INCONCLUSIVE con la excepcion en details.
        """
        pass_results = [
            r for r in qa_results
            if isinstance(r, dict) and r.get("status") == "PASS"
        ]
        total_qa_pass = len(pass_results)

        if total_qa_pass == 0:
            return {
                "verdict": "INCONCLUSIVE",
                "sample_size": 0,
                "total_qa_pass": 0,
                "rerun_results": [],
                "discrepancies": [],
                "seed": self.seed,
                "note": (
                    "No hay QA results con status=PASS. Reality-checker no puede "
                    "revalidar — certificacion debe escalar al usuario."
                ),
            }

        sample = self.sample(qa_results)
        rerun_results: List[Dict[str, Any]] = []
        discrepancies: List[Dict[str, Any]] = []

        for qa in sample:
            tarea = qa.get("tarea", qa.get("task", "<sin tarea>"))
            original_status = qa.get("status", "<unknown>")

            try:
                rerun_response = rerun_callback(qa)
            except Exception as e:
                rerun_results.append({
                    "tarea": tarea,
                    "original": original_status,
                    "rerun": "INCONCLUSIVE",
                    "verdict": "INCONCLUSIVE",
                    "details": f"rerun_callback raised: {type(e).__name__}: {e}",
                })
                continue

            if not isinstance(rerun_response, dict) or "status" not in rerun_response:
                rerun_results.append({
                    "tarea": tarea,
                    "original": original_status,
                    "rerun": "INCONCLUSIVE",
                    "verdict": "INCONCLUSIVE",
                    "details": f"rerun_callback retorno formato invalido: {rerun_response!r}",
                })
                continue

            rerun_status = rerun_response.get("status", "<unknown>")
            details = rerun_response.get("details", "")

            # Determinar verdict por rerun
            if rerun_status == "INCONCLUSIVE":
                rerun_verdict = "INCONCLUSIVE"
            elif rerun_status == original_status:
                rerun_verdict = "CONFIRMED"
            else:
                rerun_verdict = "DISCREPANCY"

            entry = {
                "tarea": tarea,
                "original": original_status,
                "rerun": rerun_status,
                "verdict": rerun_verdict,
                "details": details,
            }
            rerun_results.append(entry)

            if rerun_verdict == "DISCREPANCY":
                discrepancies.append(entry)

        # Verdict global:
        # - Cualquier DISCREPANCY → DISCREPANCY (bloquea)
        # - Sin DISCREPANCY y al menos 1 CONFIRMED → CONFIRMED
        # - Solo INCONCLUSIVE → INCONCLUSIVE (warning)
        if discrepancies:
            global_verdict = "DISCREPANCY"
            note = (
                f"{len(discrepancies)} de {len(rerun_results)} reruns "
                f"presentan discrepancia. Certificacion debe bloquearse "
                f"hasta resolver."
            )
        elif any(r["verdict"] == "CONFIRMED" for r in rerun_results):
            global_verdict = "CONFIRMED"
            note = (
                f"{len(rerun_results)} reruns ejecutados, "
                f"{sum(1 for r in rerun_results if r['verdict'] == 'CONFIRMED')} "
                f"CONFIRMED, {sum(1 for r in rerun_results if r['verdict'] == 'INCONCLUSIVE')} "
                f"INCONCLUSIVE. Sample size {len(rerun_results)} de {total_qa_pass} QA PASS."
            )
        else:
            global_verdict = "INCONCLUSIVE"
            note = (
                f"Todos los reruns ({len(rerun_results)}) fueron INCONCLUSIVE. "
                f"Reality-checker no pudo revalidar — recomendado escalar."
            )

        return {
            "verdict": global_verdict,
            "sample_size": len(rerun_results),
            "total_qa_pass": total_qa_pass,
            "rerun_results": rerun_results,
            "discrepancies": discrepancies,
            "seed": self.seed,
            "note": note,
        }
