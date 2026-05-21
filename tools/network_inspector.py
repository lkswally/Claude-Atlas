#!/usr/bin/env python3
"""
Network Inspector (Bloque 1H.1)
================================

Capa de QA que analiza requests HTTP capturados por Playwright (o cualquier
fuente compatible) y clasifica issues por severidad. Detecta falsos PASS
producidos por requests rotos, status codes problematicos, mixed content,
redirects malos.

ALCANCE HONESTO:
- SOLO cubre inspeccion de network requests (capa 1 de multi-layer QA)
- NO cubre console logs (sera 1H.2)
- NO cubre visual fidelity LLM-as-judge (sera 1H.3)
- NO inspecciona response bodies — solo metadata de cada request

CLASIFICACION DE SEVERIDAD:
- CRITICAL: status 5xx, network errors, mixed content (security)
- HIGH: 4xx en same-origin asset, redirect chain > 3, navigations failed
- MEDIUM: 4xx en cross-origin (tracking deshabilitado puede dar esto),
         slow requests > 5s
- LOW: asset cache miss, third-party warnings

VERDICT:
- CRITICAL presente -> FAIL (bloquea QA PASS)
- Solo HIGH -> WARN (no bloquea, se reporta)
- Solo MEDIUM/LOW -> OK con info
- Lista vacia -> OK con warning de no-data

API:
    inspector = NetworkInspector(page_origin="https://example.com")
    report = inspector.inspect(requests=[
        {"url": "...", "status": 200, "method": "GET", ...},
        ...
    ])
    # report = {
    #   "verdict": "OK" | "WARN" | "FAIL",
    #   "issues": [{"severity": "...", "type": "...", "url": "...", ...}],
    #   "summary": {"total": N, "by_severity": {...}, "by_type": {...}},
    #   "note": str,
    # }
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


# ============================================================
#  CONSTANTES
# ============================================================

# Status codes 4xx que NO se consideran severos por si solos
# (un 404 a un favicon o tracking puede ser esperado)
EXPECTED_4XX_CODES = {404, 410}

# Threshold para redirect chains
MAX_REDIRECT_CHAIN = 3

# Threshold para slow requests (ms)
SLOW_REQUEST_THRESHOLD_MS = 5000

# Asset types que SI son criticos si fallan (same-origin)
CRITICAL_SAME_ORIGIN_PATHS = re.compile(
    r"\.(js|mjs|css|html|json|wasm)$|"
    r"/api/|/auth/|/login|/signup",
    re.IGNORECASE,
)

# Verdicts y severidades
VERDICT_OK = "OK"
VERDICT_WARN = "WARN"
VERDICT_FAIL = "FAIL"

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


# ============================================================
#  INSPECTOR
# ============================================================

class NetworkInspector:
    """Inspector de network requests para detectar issues que pasan como QA PASS."""

    def __init__(
        self,
        page_origin: Optional[str] = None,
        max_redirect_chain: int = MAX_REDIRECT_CHAIN,
        slow_request_threshold_ms: int = SLOW_REQUEST_THRESHOLD_MS,
    ):
        """
        Args:
            page_origin: URL base de la pagina (ej. "https://example.com").
                         Usado para determinar same-origin vs cross-origin.
                         Si None, todas son tratadas como cross-origin (menos severo).
            max_redirect_chain: redirect chains mas largas se marcan HIGH
            slow_request_threshold_ms: requests > este threshold se marcan MEDIUM
        """
        self.page_origin = page_origin
        self.page_scheme = None
        self.page_host = None
        if page_origin:
            parsed = urlparse(page_origin)
            self.page_scheme = parsed.scheme.lower() if parsed.scheme else None
            self.page_host = parsed.netloc.lower() if parsed.netloc else None
        self.max_redirect_chain = max_redirect_chain
        self.slow_request_threshold_ms = slow_request_threshold_ms

    def _is_same_origin(self, url: str) -> bool:
        """Determina si una URL es same-origin con la pagina actual."""
        if not self.page_host or not url:
            return False
        try:
            parsed = urlparse(url)
            return (parsed.netloc.lower() == self.page_host)
        except Exception:
            return False

    def _is_critical_same_origin_resource(self, url: str) -> bool:
        """Es un recurso crítico same-origin (JS, CSS, API, auth)?"""
        if not self._is_same_origin(url):
            return False
        try:
            parsed = urlparse(url)
            return bool(CRITICAL_SAME_ORIGIN_PATHS.search(parsed.path or ""))
        except Exception:
            return False

    def _check_mixed_content(self, url: str) -> bool:
        """Pagina HTTPS cargando recurso HTTP es mixed content (CRITICAL)."""
        if self.page_scheme != "https":
            return False
        try:
            parsed = urlparse(url)
            return parsed.scheme.lower() == "http"
        except Exception:
            return False

    def _inspect_single_request(self, req: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Inspecciona un request y retorna issues encontradas."""
        issues: List[Dict[str, Any]] = []
        url = req.get("url", "")
        status = req.get("status")
        method = req.get("method", "GET")
        duration_ms = req.get("duration_ms") or req.get("timing", {}).get("duration", 0)
        error = req.get("error") or req.get("failure")
        redirect_count = req.get("redirect_count", 0)

        # Network error / failed request
        if error:
            issues.append({
                "severity": SEVERITY_CRITICAL,
                "type": "network_error",
                "url": url,
                "method": method,
                "details": f"Request fallo: {error}",
            })
            return issues  # sin status, no podemos analizar mas

        # Mixed content (HTTPS page -> HTTP resource)
        if self._check_mixed_content(url):
            issues.append({
                "severity": SEVERITY_CRITICAL,
                "type": "mixed_content",
                "url": url,
                "method": method,
                "details": "HTTPS page cargando recurso HTTP (browser bloqueara o degradara)",
            })

        # Status codes
        if isinstance(status, int):
            if 500 <= status <= 599:
                issues.append({
                    "severity": SEVERITY_CRITICAL,
                    "type": "http_5xx",
                    "url": url,
                    "method": method,
                    "status": status,
                    "details": f"Server error {status}",
                })
            elif 400 <= status <= 499:
                if status in EXPECTED_4XX_CODES and not self._is_critical_same_origin_resource(url):
                    # 404 en cross-origin (ej. tracking script no presente) -> LOW
                    issues.append({
                        "severity": SEVERITY_LOW,
                        "type": "http_4xx_expected",
                        "url": url,
                        "method": method,
                        "status": status,
                        "details": f"4xx esperado {status} en recurso no-critico",
                    })
                elif self._is_critical_same_origin_resource(url):
                    # 4xx en JS/CSS/API propio -> HIGH (asset roto)
                    issues.append({
                        "severity": SEVERITY_HIGH,
                        "type": "http_4xx_critical_asset",
                        "url": url,
                        "method": method,
                        "status": status,
                        "details": f"Asset critico same-origin fallo con {status}",
                    })
                elif self._is_same_origin(url):
                    # 4xx en same-origin no-critico -> MEDIUM
                    issues.append({
                        "severity": SEVERITY_MEDIUM,
                        "type": "http_4xx_same_origin",
                        "url": url,
                        "method": method,
                        "status": status,
                        "details": f"4xx en same-origin {status}",
                    })
                else:
                    # 4xx en cross-origin -> MEDIUM (puede ser tracking)
                    issues.append({
                        "severity": SEVERITY_MEDIUM,
                        "type": "http_4xx_cross_origin",
                        "url": url,
                        "method": method,
                        "status": status,
                        "details": f"4xx en cross-origin {status}",
                    })

        # Redirect chain larga
        if isinstance(redirect_count, int) and redirect_count > self.max_redirect_chain:
            issues.append({
                "severity": SEVERITY_HIGH,
                "type": "long_redirect_chain",
                "url": url,
                "redirect_count": redirect_count,
                "details": f"Redirect chain de {redirect_count} (max recomendado {self.max_redirect_chain})",
            })

        # Slow request
        try:
            duration_int = int(duration_ms or 0)
            if duration_int > self.slow_request_threshold_ms:
                issues.append({
                    "severity": SEVERITY_MEDIUM,
                    "type": "slow_request",
                    "url": url,
                    "duration_ms": duration_int,
                    "details": f"Request lento: {duration_int}ms (threshold {self.slow_request_threshold_ms}ms)",
                })
        except (ValueError, TypeError):
            pass

        return issues

    def inspect(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inspecciona una lista de requests y produce reporte agregado.

        Retorna dict con shape:
        {
          "verdict": "OK" | "WARN" | "FAIL",
          "issues": [...],
          "summary": {
            "total_requests": int,
            "issues_count": int,
            "by_severity": {CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N},
            "by_type": {http_5xx: N, mixed_content: N, ...},
          },
          "note": str,
        }
        """
        if not requests:
            return {
                "verdict": VERDICT_OK,
                "issues": [],
                "summary": {
                    "total_requests": 0,
                    "issues_count": 0,
                    "by_severity": {},
                    "by_type": {},
                },
                "note": "No hay requests para inspeccionar. WARN: si esperabas trafico de red, verificar fuente.",
            }

        all_issues: List[Dict[str, Any]] = []
        for req in requests:
            if not isinstance(req, dict):
                continue
            all_issues.extend(self._inspect_single_request(req))

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
                f"FAIL: {by_severity[SEVERITY_CRITICAL]} issue(s) CRITICAL detectadas. "
                f"QA debe bloquear hasta resolver."
            )
        elif by_severity.get(SEVERITY_HIGH, 0) > 0:
            verdict = VERDICT_WARN
            note = (
                f"WARN: {by_severity[SEVERITY_HIGH]} issue(s) HIGH detectadas. "
                f"No bloquea pero requiere revision."
            )
        elif by_severity.get(SEVERITY_MEDIUM, 0) > 0 or by_severity.get(SEVERITY_LOW, 0) > 0:
            total_minor = by_severity.get(SEVERITY_MEDIUM, 0) + by_severity.get(SEVERITY_LOW, 0)
            verdict = VERDICT_OK
            note = f"OK con {total_minor} issue(s) MEDIUM/LOW informativas."
        else:
            verdict = VERDICT_OK
            note = f"OK: {len(requests)} requests inspeccionados, sin issues."

        return {
            "verdict": verdict,
            "issues": all_issues,
            "summary": {
                "total_requests": len(requests),
                "issues_count": len(all_issues),
                "by_severity": by_severity,
                "by_type": by_type,
            },
            "note": note,
        }
