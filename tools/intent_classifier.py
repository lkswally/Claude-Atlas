"""
Intent Classifier (Bloque 1L.1)
================================

Clasifica el prompt inicial del usuario en uno de 4 buckets antes de delegar a
project-manager-senior, para que el orquestador elija la ruta correcta:

    audit      -> analisis sin tocar codigo
    redesign   -> Fase 2 completa + Fase 3 (rediseno profundo)
    implement  -> solo Fase 3 (tareas concretas sobre diseno existente)
    validate   -> solo evidence-collector + reality-checker

ALCANCE HONESTO
---------------
- Heuristica por keywords + patrones (ES + EN). NO usa LLM.
- Threshold conservador: cuando hay ambiguedad real, devuelve confidence='low'
  para que el orquestador escale al usuario en vez de decidir solo.
- NO clasifica intenciones que no son de pipeline (chat, preguntas tecnicas,
  fixes triviales). En ese caso devuelve intent=None con rationale claro.
- NO modifica DAG state. Solo retorna estructura inmutable.

API
---
    result = classify_user_intent(prompt: str, context: dict = None) -> dict
    result = {
        "intent": "audit" | "redesign" | "implement" | "validate" | None,
        "confidence": "high" | "medium" | "low",
        "signals": [{"bucket": str, "keyword": str, "weight": int}, ...],
        "fallback_intent": str | None,
        "rationale": str,
        "escalation_question": str | None,  # if confidence=='low'
    }

INTEGRACION
-----------
El orquestador lo invoca en paso 0.5 del Boot Sequence. Si confidence='low',
DEBE escalar al usuario con escalation_question antes de delegar.

OPT-IN
------
Default ON. El dispatcher puede desactivarlo via flag
`intent_classifier_enabled=False` para tests o rollback en runtime.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# =====================================================================
#  TABLAS DE SENALES
# =====================================================================
# Cada keyword tiene un peso (1=debil, 2=medio, 3=fuerte).
# Match case-insensitive con bordes de palabra (\b) para evitar substrings.
#
# DISENO CONSERVADOR:
# - keywords altamente ambiguas ("mejorar", "improve") NO entran aqui.
#   Se manejan en el matcher post-process como "ambiguous boosters".
# - "landing" / "web" / "site" solo no son senales — son objeto, no accion.

_AUDIT_KEYWORDS: List[Tuple[str, int]] = [
    (r"\baudit\w*\b", 3),
    (r"\banaliz\w*\b", 2), (r"\banalyze\b", 2), (r"\banalysis\b", 2),
    (r"\brevis\w*\b", 2), (r"\breview\b", 2),
    (r"\bdiagn[oó]stico\b", 3), (r"\bdiagnose\b", 3),
    (r"\bevalu\w*\b", 2), (r"\bevaluate\b", 2), (r"\bassessment\b", 2),
    (r"\bqu[eé] onda\b", 1),
    (r"\bchequ\w*\b", 2),
    (r"\bcheckea\w*\b", 2),
    (r"\binspec\w*\b", 2),
    (r"\bver qu[eé]\b", 1),
    (r"\bopini[oó]n\b", 1), (r"\bsecond opinion\b", 2),
    (r"\bdetect\w*\b", 1),
    (r"\bidentif\w*\b", 1),
]

_REDESIGN_KEYWORDS: List[Tuple[str, int]] = [
    (r"\bredise[nñ]\w*\b", 3), (r"\bredesign\w*\b", 3),
    (r"\brehac\w*\b", 3), (r"\brebuild\b", 3),
    (r"\bdesde cero\b", 3), (r"\bfrom scratch\b", 3),
    (r"\bnueva versi[oó]n\b", 2), (r"\bnew version\b", 2),
    (r"\breconstr\w*\b", 3), (r"\breconstruct\w*\b", 3),
    (r"\breimagin\w*\b", 3),
    (r"\boverhaul\b", 3),
    (r"\brenova\w*\b", 2),
    (r"\brefactor (?:visual|de dise[nñ]o)\b", 2),
    (r"\bnuevo dise[nñ]o\b", 3), (r"\bnew design\b", 3),
    (r"\brebrand\w*\b", 3),
    (r"\bcambio total\b", 2),
    (r"\bdar vuelta\b", 2),
    (r"\bidentidad visual\b", 2),
]

_IMPLEMENT_KEYWORDS: List[Tuple[str, int]] = [
    (r"\bimplement\w*\b", 3),
    (r"\bagreg\w*\b", 2), (r"\badd\b", 2), (r"\badded\b", 2), (r"\badding\b", 2),
    (r"\bcrea\w*\b", 2), (r"\bcreate\w*\b", 2),
    (r"\bconstru\w*\b", 2), (r"\bbuild\w*\b", 2),
    (r"\bdesarroll\w*\b", 2), (r"\bdevelop\w*\b", 2),
    (r"\bfix\w*\b", 2), (r"\barregl\w*\b", 2),
    (r"\bcorrig\w*\b", 2), (r"\bcorrij\w*\b", 2),
    (r"\bcomplet\w*\b", 1), (r"\bfinish\w*\b", 1),
    (r"\bpendiente\b", 1),
    (r"\btarea\b", 1), (r"\btask\b", 1),
    (r"\bfeature\b", 1),
    (r"\bcomponente\b", 1), (r"\bcomponent\b", 1),
    (r"\bendpoint\b", 1),
    (r"\binteg(?:rar|rate)\w*\b", 2),
    (r"\bnueva (?:funci[oó]n|feature|p[aá]gina|secci[oó]n)\b", 2),
    (r"\bnew (?:feature|page|section|function)\b", 2),
]

_VALIDATE_KEYWORDS: List[Tuple[str, int]] = [
    (r"\bvalid\w*\b", 3),
    (r"\bverific\w*\b", 3), (r"\bverify\b", 3), (r"\bverified\b", 3),
    (r"\btest\w*\b", 2),
    (r"\bprob\w*\b", 2),
    (r"\bse ve bien\b", 2),
    (r"\bfunciona(?:l)?\b", 1),
    (r"\bok\?\b", 1),
    (r"\bqa\b", 3),
    (r"\bregression\b", 2),
    (r"\bsmoke test\b", 2),
    (r"\bcomprob\w*\b", 2),
    (r"\bconfirm\w*\b", 1),
    (r"\bcheck (?:if|que|si)\b", 2),
    (r"\bcumple\b", 1),
    (r"\baccessibility check\b", 2), (r"\baccesibilidad\b", 1),
]

# Boosters ambiguos: si aparecen SOLOS (sin otro bucket dominante),
# fuerzan low confidence + escalacion. NO suman peso por si mismos.
_AMBIGUOUS_KEYWORDS: List[str] = [
    r"\bmejor\w*\b",
    r"\bimprove\w*\b",
    r"\benhanc\w*\b",
    r"\boptim\w*\b",
    r"\bperfeccion\w*\b",
    r"\bpul[ií]\w*\b", r"\bpolish\w*\b",
    r"\bactualiz\w*\b", r"\bupdate\w*\b",
    r"\bmoderniz\w*\b",
    r"\barreglar el dise[nñ]o\b",
    r"\bfix the design\b",
    r"\blook better\b",
    r"\bse vea mejor\b",
]

# Senales contextuales de objeto (no clasifican por si solas).
# Si aparecen junto a un bucket, validan el match.
_OBJECT_KEYWORDS: List[str] = [
    r"\blanding\b", r"\bweb(?:site)?\b", r"\bsite\b",
    r"\bp[aá]gina\b", r"\bpage\b", r"\bui\b", r"\bux\b",
    r"\bhome\b", r"\bhero\b", r"\bsecci[oó]n\b", r"\bsection\b",
    r"\bdise[nñ]o\b", r"\bdesign\b",
    r"\bbrand\b", r"\bbranding\b", r"\bidentidad\b",
]


# =====================================================================
#  THRESHOLDS
# =====================================================================
# Conservadores adrede: subir el listo para "high" evita decisiones automaticas
# en prompts ambiguos.

_HIGH_CONFIDENCE_MIN_SCORE = 4  # >= 4 puntos en un solo bucket
_HIGH_CONFIDENCE_DOMINANCE = 2  # ventaja minima sobre segundo bucket
_MEDIUM_CONFIDENCE_MIN_SCORE = 2

# Empty / triviales
_MIN_PROMPT_LENGTH = 3
_MAX_PROMPT_LENGTH_FOR_SCAN = 20000  # truncar prompts gigantes


# =====================================================================
#  FUNCION PRINCIPAL
# =====================================================================

def classify_user_intent(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Clasifica el prompt del usuario en uno de 4 buckets.

    Args:
        prompt: texto crudo del usuario (string).
        context: dict opcional con info del DAG state. No requerido.
                 Se reserva para futuro (ej: si hay rediseno reciente,
                 "mejorar" leans implement). HOY no se usa para decidir,
                 solo se loggea en rationale si esta presente.

    Returns:
        dict con shape:
        {
            "intent": "audit" | "redesign" | "implement" | "validate" | None,
            "confidence": "high" | "medium" | "low",
            "signals": [{"bucket": str, "keyword": str, "weight": int}, ...],
            "fallback_intent": str | None,
            "rationale": str,
            "escalation_question": str | None,
        }

    Reglas de decision:
    - Si prompt vacio / muy corto / None -> intent=None, confidence=low.
    - Si solo aparecen "ambiguous boosters" sin bucket claro -> low + escalar.
    - Si un bucket gana por >= dominance_min y score >= high_min -> high.
    - Si un bucket gana sin la dominancia minima -> medium.
    - Si dos buckets empatan -> low + escalar.
    """
    # --- Sanitize input -------------------------------------------------
    if prompt is None:
        return _empty_result("prompt is None")
    if not isinstance(prompt, str):
        return _empty_result(f"prompt is not str: {type(prompt).__name__}")
    cleaned = prompt.strip()
    if len(cleaned) < _MIN_PROMPT_LENGTH:
        return _empty_result(f"prompt too short ({len(cleaned)} chars)")
    if len(cleaned) > _MAX_PROMPT_LENGTH_FOR_SCAN:
        cleaned = cleaned[:_MAX_PROMPT_LENGTH_FOR_SCAN]
        # No retornamos error — clasificamos sobre el truncado.

    lower = cleaned.lower()

    # --- Match buckets --------------------------------------------------
    bucket_scores: Dict[str, int] = {
        "audit": 0,
        "redesign": 0,
        "implement": 0,
        "validate": 0,
    }
    signals: List[Dict[str, Any]] = []

    for bucket, table in (
        ("audit", _AUDIT_KEYWORDS),
        ("redesign", _REDESIGN_KEYWORDS),
        ("implement", _IMPLEMENT_KEYWORDS),
        ("validate", _VALIDATE_KEYWORDS),
    ):
        for pattern, weight in table:
            try:
                matches = re.findall(pattern, lower, flags=re.IGNORECASE)
            except re.error:
                continue
            if matches:
                hits = len(matches)
                bucket_scores[bucket] += weight * hits
                signals.append({
                    "bucket": bucket,
                    "keyword": pattern,
                    "weight": weight,
                    "hits": hits,
                })

    # --- Detect ambiguous boosters --------------------------------------
    ambiguous_hits: List[str] = []
    for pattern in _AMBIGUOUS_KEYWORDS:
        try:
            if re.search(pattern, lower, flags=re.IGNORECASE):
                ambiguous_hits.append(pattern)
        except re.error:
            continue

    has_object = any(
        re.search(p, lower, flags=re.IGNORECASE)
        for p in _OBJECT_KEYWORDS
    )

    # --- Decide -----------------------------------------------------------
    # Ordenar buckets por score (mayor primero)
    ranked = sorted(
        bucket_scores.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )
    top_bucket, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # CASO 1: ningun bucket clasico marca. Solo ambiguous boosters.
    if top_score == 0:
        if ambiguous_hits and has_object:
            return {
                "intent": None,
                "confidence": "low",
                "signals": signals,
                "fallback_intent": "redesign",  # apuesta conservadora SOLO si user confirma
                "rationale": (
                    f"Prompt contiene ambiguous boosters "
                    f"({len(ambiguous_hits)}) y referencia a objeto visual, "
                    f"pero sin verbo claro de accion."
                ),
                "escalation_question": _build_escalation_question(
                    "redesign", "audit", "implement",
                ),
            }
        if ambiguous_hits and not has_object:
            return {
                "intent": None,
                "confidence": "low",
                "signals": signals,
                "fallback_intent": None,
                "rationale": (
                    "Prompt contiene verbos ambiguos pero sin objeto claro "
                    "(landing/web/UI). No clasificable."
                ),
                "escalation_question": (
                    "Tu pedido no especifica que parte tocar. "
                    "Decime: (a) que componente/pagina, (b) que tipo de cambio "
                    "(auditar, rediseno, implementar feature, validar)."
                ),
            }
        return {
            "intent": None,
            "confidence": "low",
            "signals": signals,
            "fallback_intent": None,
            "rationale": "Sin senales clasificables. Probable chat o pregunta tecnica.",
            "escalation_question": None,  # No escalar — probable mensaje no-pipeline
        }

    # CASO 2: dos buckets empatan en score > 0
    if top_score == second_score and top_score > 0:
        tied = [b for b, s in ranked if s == top_score]
        return {
            "intent": None,
            "confidence": "low",
            "signals": signals,
            "fallback_intent": tied[0],
            "rationale": (
                f"Empate entre buckets: {tied}. "
                f"Score top={top_score}. Requiere desambiguacion."
            ),
            "escalation_question": _build_escalation_question(*tied[:3]),
        }

    # CASO 3: ambiguous booster presente y bucket ganador tiene score bajo
    # -> degradar a low aunque haya un bucket ganador
    if ambiguous_hits and top_score < _MEDIUM_CONFIDENCE_MIN_SCORE:
        return {
            "intent": None,
            "confidence": "low",
            "signals": signals,
            "fallback_intent": top_bucket,
            "rationale": (
                f"Bucket dominante '{top_bucket}' (score={top_score}) "
                f"pero con ambiguous boosters presentes. Conservador: escalar."
            ),
            "escalation_question": _build_escalation_question(
                top_bucket, ranked[1][0], ranked[2][0] if len(ranked) > 2 else None,
            ),
        }

    # CASO 4: bucket ganador con score y dominancia altos -> HIGH
    dominance = top_score - second_score
    if top_score >= _HIGH_CONFIDENCE_MIN_SCORE and dominance >= _HIGH_CONFIDENCE_DOMINANCE:
        return {
            "intent": top_bucket,
            "confidence": "high",
            "signals": signals,
            "fallback_intent": None,
            "rationale": (
                f"Bucket '{top_bucket}' dominante con score={top_score}, "
                f"dominance={dominance}."
                + (f" Context provisto: {sorted(context.keys())}" if context else "")
            ),
            "escalation_question": None,
        }

    # CASO 5: bucket ganador con score medio -> MEDIUM
    if top_score >= _MEDIUM_CONFIDENCE_MIN_SCORE:
        return {
            "intent": top_bucket,
            "confidence": "medium",
            "signals": signals,
            "fallback_intent": ranked[1][0] if second_score > 0 else None,
            "rationale": (
                f"Bucket '{top_bucket}' (score={top_score}, dominance={dominance}). "
                f"Confidence medium — orquestador puede proceder pero deberia loggear."
            ),
            "escalation_question": None,
        }

    # CASO 6: score muy bajo -> low + escalar
    return {
        "intent": None,
        "confidence": "low",
        "signals": signals,
        "fallback_intent": top_bucket,
        "rationale": (
            f"Bucket '{top_bucket}' (score={top_score}) por debajo de minimo "
            f"({_MEDIUM_CONFIDENCE_MIN_SCORE}). Escalar al usuario."
        ),
        "escalation_question": _build_escalation_question(
            top_bucket,
            ranked[1][0] if len(ranked) > 1 else None,
        ),
    }


# =====================================================================
#  HELPERS INTERNOS
# =====================================================================

def _empty_result(reason: str) -> Dict[str, Any]:
    return {
        "intent": None,
        "confidence": "low",
        "signals": [],
        "fallback_intent": None,
        "rationale": reason,
        "escalation_question": None,
    }


_LABELS = {
    "audit": "auditar (analizar sin tocar codigo)",
    "redesign": "rediseno (Fase 2 + 3 completas)",
    "implement": "implementar (Fase 3 sobre diseno actual)",
    "validate": "validar (QA + reality-check)",
}


def _build_escalation_question(*buckets: Optional[str]) -> str:
    options = []
    seen = set()
    for b in buckets:
        if not b or b in seen:
            continue
        seen.add(b)
        if b in _LABELS:
            options.append(f"{b} = {_LABELS[b]}")
    if not options:
        return (
            "No pude clasificar tu pedido. "
            "Decime que tipo de tarea queres: auditar, rediseno, implementar o validar."
        )
    return (
        "Tu pedido es ambiguo. "
        "Cual de estas opciones describe mejor lo que queres?\n  - "
        + "\n  - ".join(options)
    )


# =====================================================================
#  CLI (debugging / testing manual)
# =====================================================================

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print(
            "usage: python intent_classifier.py '<prompt>'\n"
            "       echo '<prompt>' | python intent_classifier.py -",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.argv[1] == "-":
        prompt = sys.stdin.read()
    else:
        prompt = " ".join(sys.argv[1:])

    result = classify_user_intent(prompt)
    print(json.dumps(result, indent=2, ensure_ascii=False))
