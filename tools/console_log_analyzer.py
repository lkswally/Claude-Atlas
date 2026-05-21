#!/usr/bin/env python3
"""
Console Log Analyzer (Bloque 1H.2)
===================================

Capa 2 de multi-layer QA: analiza mensajes de console capturados por
Playwright (browser_console_messages) y clasifica issues por severidad.

ALCANCE HONESTO:
- SOLO cubre console log analysis (capa 2 de 3 planeadas)
- NO cubre network inspection (1H.1) ni visual fidelity (1H.3)
- NO ejecuta el codigo de los mensajes — solo analiza texto
- NO valida call stacks completos — solo el mensaje + tipo

CLASIFICACION DE SEVERIDAD:
- CRITICAL: errors no atrapados (Uncaught), CORS errors, CSP violations,
            React/Next.js hydration mismatch, "Cannot read properties of"
- HIGH: console.error general, deprecation warnings de APIs criticas,
        React warnings (key, hooks rules, act())
- MEDIUM: console.warn general, source map warnings
- LOW: console.log/info, devtools messages, third-party noise

VERDICT:
- CRITICAL presente -> FAIL (bloquea QA PASS)
- Solo HIGH -> WARN (no bloquea, se reporta)
- Solo MEDIUM/LOW -> OK con info

API:
    analyzer = ConsoleLogAnalyzer()
    report = analyzer.analyze(messages=[
        {"type": "error", "text": "...", "location": {"url": "...", "lineNumber": 42}},
        ...
    ])
"""

import re
from typing import Any, Dict, List, Optional


# ============================================================
#  CONSTANTES
# ============================================================

VERDICT_OK = "OK"
VERDICT_WARN = "WARN"
VERDICT_FAIL = "FAIL"

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


# Patrones CRITICAL — errores no recuperables
CRITICAL_PATTERNS = [
    # Uncaught exceptions
    (re.compile(r"\b(Uncaught|Unhandled)\b", re.IGNORECASE), "uncaught_exception"),
    # CORS
    (re.compile(r"\b(CORS|Cross-Origin Request Blocked|Access-Control-Allow-Origin)\b", re.IGNORECASE), "cors_error"),
    # CSP
    (re.compile(r"\b(Content Security Policy|Refused to (load|execute|connect))\b", re.IGNORECASE), "csp_violation"),
    # React/Next hydration errors
    (re.compile(r"\b(Hydration failed|Text content does not match|did not match server)\b", re.IGNORECASE), "hydration_mismatch"),
    # Common JS runtime errors
    (re.compile(r"Cannot read propert(y|ies) of (null|undefined)", re.IGNORECASE), "null_undefined_access"),
    (re.compile(r"\bis not a function\b", re.IGNORECASE), "not_a_function"),
    (re.compile(r"\bReferenceError\b", re.IGNORECASE), "reference_error"),
    # Auth-related
    (re.compile(r"\b(401|403|Unauthorized|Forbidden)\b.*\b(auth|session|token)\b", re.IGNORECASE), "auth_error_logged"),
]

# Patrones HIGH — warnings sobre APIs/practicas criticas
HIGH_PATTERNS = [
    # React warnings importantes
    (re.compile(r"Each child in a list should have a unique \"?key\"?", re.IGNORECASE), "react_missing_key"),
    (re.compile(r"\b(Invalid hook call|Rules of Hooks)\b", re.IGNORECASE), "react_hooks_violation"),
    (re.compile(r"\bact\(\)\b.*not wrapped", re.IGNORECASE), "react_act_warning"),
    # Deprecation
    (re.compile(r"\b(deprecated|will be removed)\b.*\b(API|method|function)\b", re.IGNORECASE), "deprecation"),
    # Memory leaks
    (re.compile(r"memory leak|leaked", re.IGNORECASE), "memory_leak_warning"),
]

# Patrones LOW — noise comun que se ignora
LOW_NOISE_PATTERNS = [
    re.compile(r"\b(DevTools|extension|chrome-extension://)\b", re.IGNORECASE),
    re.compile(r"\bsource map(ping)?\b.*\b(not found|missing|invalid)\b", re.IGNORECASE),
    re.compile(r"\bDownload the React DevTools\b", re.IGNORECASE),
    re.compile(r"\bGoogle Analytics\b.*\bnot loaded\b", re.IGNORECASE),
]


# ============================================================
#  ANALYZER
# ============================================================

class ConsoleLogAnalyzer:
    """Analizador de console messages para detectar issues que pasan como QA PASS."""

    def __init__(self, third_party_origin_patterns: Optional[List[str]] = None):
        """
        Args:
            third_party_origin_patterns: lista de regex strings que matchean
                URLs de origen third-party. Mensajes que vienen de esos
                origins se degradan a LOW automaticamente. Default: None.
        """
        if third_party_origin_patterns:
            self._third_party_res = [
                re.compile(p, re.IGNORECASE) for p in third_party_origin_patterns
            ]
        else:
            self._third_party_res = []

    def _is_low_noise(self, text: str) -> bool:
        """Verifica si el mensaje matchea patrones de noise comun."""
        return any(p.search(text) for p in LOW_NOISE_PATTERNS)

    def _is_third_party(self, location_url: str) -> bool:
        """Verifica si la URL de origen del mensaje es third-party."""
        if not location_url:
            return False
        return any(p.search(location_url) for p in self._third_party_res)

    def _classify_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Clasifica un mensaje individual.

        Retorna issue dict si se considera issue, None si se ignora.

        msg shape (compatible con Playwright):
        {
          "type": "log"|"info"|"warning"|"error"|"debug"|...,
          "text": "mensaje completo",
          "location": {"url": "...", "lineNumber": N, "columnNumber": N},
        }
        """
        msg_type = (msg.get("type") or "").lower()
        text = msg.get("text") or ""
        location = msg.get("location") or {}
        location_url = location.get("url", "")

        if not text.strip():
            return None

        # Noise filters (ignorar)
        if self._is_low_noise(text):
            return None

        # Third-party degrada a LOW
        is_third = self._is_third_party(location_url)

        # Check CRITICAL patterns
        for pattern, type_name in CRITICAL_PATTERNS:
            if pattern.search(text):
                severity = SEVERITY_LOW if is_third else SEVERITY_CRITICAL
                return {
                    "severity": severity,
                    "type": type_name,
                    "message_type": msg_type,
                    "text": text[:300],
                    "location_url": location_url,
                    "line": location.get("lineNumber"),
                    "third_party_degraded": is_third,
                }

        # Check HIGH patterns
        for pattern, type_name in HIGH_PATTERNS:
            if pattern.search(text):
                severity = SEVERITY_LOW if is_third else SEVERITY_HIGH
                return {
                    "severity": severity,
                    "type": type_name,
                    "message_type": msg_type,
                    "text": text[:300],
                    "location_url": location_url,
                    "line": location.get("lineNumber"),
                    "third_party_degraded": is_third,
                }

        # Default por tipo
        if msg_type == "error":
            severity = SEVERITY_LOW if is_third else SEVERITY_HIGH
            return {
                "severity": severity,
                "type": "console_error_generic",
                "message_type": msg_type,
                "text": text[:300],
                "location_url": location_url,
                "line": location.get("lineNumber"),
                "third_party_degraded": is_third,
            }
        elif msg_type in ("warning", "warn"):
            return {
                "severity": SEVERITY_MEDIUM,
                "type": "console_warning_generic",
                "message_type": msg_type,
                "text": text[:300],
                "location_url": location_url,
                "line": location.get("lineNumber"),
                "third_party_degraded": is_third,
            }
        elif msg_type in ("log", "info", "debug"):
            return {
                "severity": SEVERITY_LOW,
                "type": "console_log",
                "message_type": msg_type,
                "text": text[:300],
                "location_url": location_url,
                "line": location.get("lineNumber"),
                "third_party_degraded": is_third,
            }

        # Tipo desconocido — LOW
        return {
            "severity": SEVERITY_LOW,
            "type": "console_unknown_type",
            "message_type": msg_type,
            "text": text[:300],
        }

    def analyze(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza una lista de console messages y produce reporte agregado.

        Retorna dict:
        {
          "verdict": "OK" | "WARN" | "FAIL",
          "issues": [...],
          "summary": {
            "total_messages": int,
            "issues_count": int,
            "by_severity": {...},
            "by_type": {...},
          },
          "note": str,
        }
        """
        if not messages:
            return {
                "verdict": VERDICT_OK,
                "issues": [],
                "summary": {
                    "total_messages": 0,
                    "issues_count": 0,
                    "by_severity": {},
                    "by_type": {},
                },
                "note": "No hay console messages. WARN: si esperabas logs, verificar fuente.",
            }

        all_issues: List[Dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            issue = self._classify_message(msg)
            if issue is not None:
                all_issues.append(issue)

        # Agregar metricas
        by_severity: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for issue in all_issues:
            sev = issue.get("severity", "UNKNOWN")
            t = issue.get("type", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1

        # Verdict global
        if by_severity.get(SEVERITY_CRITICAL, 0) > 0:
            verdict = VERDICT_FAIL
            note = (
                f"FAIL: {by_severity[SEVERITY_CRITICAL]} console error(es) CRITICAL "
                f"detectado(s). QA debe bloquear hasta resolver."
            )
        elif by_severity.get(SEVERITY_HIGH, 0) > 0:
            verdict = VERDICT_WARN
            note = (
                f"WARN: {by_severity[SEVERITY_HIGH]} console error/warning(s) HIGH. "
                f"No bloquea pero requiere revision."
            )
        elif by_severity.get(SEVERITY_MEDIUM, 0) > 0 or by_severity.get(SEVERITY_LOW, 0) > 0:
            total_minor = by_severity.get(SEVERITY_MEDIUM, 0) + by_severity.get(SEVERITY_LOW, 0)
            verdict = VERDICT_OK
            note = f"OK con {total_minor} message(s) MEDIUM/LOW informativo(s)."
        else:
            verdict = VERDICT_OK
            note = f"OK: {len(messages)} console messages analizados, sin issues."

        return {
            "verdict": verdict,
            "issues": all_issues,
            "summary": {
                "total_messages": len(messages),
                "issues_count": len(all_issues),
                "by_severity": by_severity,
                "by_type": by_type,
            },
            "note": note,
        }
