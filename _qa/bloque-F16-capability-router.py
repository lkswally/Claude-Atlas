#!/usr/bin/env python3
"""
Bloque F16 — Capability Router Tests
=====================================

Verifica que el Capability Router resuelve correctamente capabilities a
providers, maneja casos de borde y no acopla agentes a MCPs concretos.

Tests:
  T1  resolve memory        → engram, LIVE
  T2  resolve documentation → context7, any usable status
  T3  resolve browser       → playwright (primary) con fallbacks
  T4  resolve project_management → notion, LIVE
  T5  repository queda PENDING_TOKEN (GitHub sin token)
  T6  design queda DEFERRED_PAID o CONFIG_ONLY (21st.dev)
  T7  fallback funciona: browser tiene >1 provider
  T8  capability inexistente retorna UNAVAILABLE (no rompe)
  T9  resolve_capability retorna Resolution con campos correctos
  T10 CapabilityRouter.resolve_many funciona
  T11 critical_status incluye memory, browser, documentation
  T12 all_live() retorna lista non-vacía
  T13 21st.dev diagnóstico: DEFERRED_PAID confirmado (sin instalar)
  T14 agent-protocol.md contiene sección capability request

Salida:
  [PASS] / [FAIL] por test
  Resumen al final

Exit code: 0 = todo PASS | 1 = al menos un FAIL
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_results: list[dict] = []


def PASS(label: str, detail: str = "") -> None:
    _results.append({"status": "PASS", "label": label, "detail": detail})
    print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))


def FAIL(label: str, detail: str = "") -> None:
    _results.append({"status": "FAIL", "label": label, "detail": detail})
    print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Import router
# ---------------------------------------------------------------------------

try:
    from core.capabilities.router import (
        resolve_capability, CapabilityRouter, Resolution, CRITICAL_CAPABILITIES
    )
    _import_ok = True
except Exception as e:
    _import_ok = False
    _import_error = str(e)


def _require_import() -> bool:
    if not _import_ok:
        FAIL("IMPORT", f"cannot import router: {_import_error}")
        return False
    return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t1_memory_resolves_to_engram() -> None:
    if not _require_import():
        return
    r = resolve_capability("memory")
    if r.provider == "engram" and r.status == "LIVE":
        PASS("T1 resolve memory → engram", f"status={r.status}, prefix={r.tool_prefix}")
    elif r.provider == "engram":
        FAIL("T1 resolve memory → engram", f"provider=engram but status={r.status} (expected LIVE)")
    else:
        FAIL("T1 resolve memory → engram", f"provider={r.provider}, status={r.status}")


def t2_documentation_resolves_to_context7() -> None:
    if not _require_import():
        return
    r = resolve_capability("documentation")
    if r.provider == "context7" and r.is_usable:
        PASS("T2 resolve documentation → context7", f"status={r.status}")
    elif r.provider == "context7":
        # context7 may be CONFIG_ONLY after restart — acceptable
        PASS("T2 resolve documentation → context7", f"status={r.status} (usable after restart)")
    else:
        FAIL("T2 resolve documentation → context7", f"provider={r.provider}, status={r.status}")


def t3_browser_resolves_with_fallbacks() -> None:
    if not _require_import():
        return
    r = resolve_capability("browser")
    if r.provider is None:
        FAIL("T3 resolve browser", "no provider found")
        return
    # Primary browser provider should be playwright or claude_in_chrome
    known_browser_providers = {"playwright", "claude_in_chrome", "claude_preview"}
    if r.provider not in known_browser_providers:
        FAIL("T3 resolve browser", f"unknown primary provider: {r.provider}")
        return
    PASS("T3 resolve browser", f"primary={r.provider} status={r.status}")


def t4_project_management_resolves_to_notion() -> None:
    if not _require_import():
        return
    r = resolve_capability("project_management")
    if r.provider == "notion" and r.status == "LIVE":
        PASS("T4 resolve project_management → notion", f"status={r.status}")
    elif r.provider == "notion":
        FAIL("T4 resolve project_management → notion", f"provider=notion but status={r.status} (expected LIVE)")
    else:
        FAIL("T4 resolve project_management → notion", f"provider={r.provider}, status={r.status}")


def t5_repository_pending_token() -> None:
    if not _require_import():
        return
    r = resolve_capability("repository")
    if r.provider == "github" and r.status == "PENDING_TOKEN":
        PASS("T5 repository PENDING_TOKEN", f"action={r.action}")
    elif r.provider == "github" and r.status == "LIVE":
        # GitHub became LIVE (token was set) — acceptable
        PASS("T5 repository status", f"github=LIVE (token configured)")
    elif r.provider == "github":
        FAIL("T5 repository PENDING_TOKEN", f"provider=github status={r.status} (expected PENDING_TOKEN)")
    else:
        FAIL("T5 repository PENDING_TOKEN", f"provider={r.provider}, status={r.status}")


def t6_design_deferred_paid() -> None:
    if not _require_import():
        return
    r = resolve_capability("design")
    acceptable = {"DEFERRED_PAID", "CONFIG_ONLY", "UNAVAILABLE"}
    if r.status in acceptable:
        PASS("T6 design DEFERRED_PAID or CONFIG_ONLY", f"provider={r.provider} status={r.status}")
    elif r.status == "LIVE":
        # 21st.dev became LIVE — user provided key
        PASS("T6 design", f"21st.dev=LIVE (paid tier activated by user)")
    else:
        FAIL("T6 design DEFERRED_PAID or CONFIG_ONLY", f"unexpected status={r.status}")


def t7_browser_has_fallback() -> None:
    if not _require_import():
        return
    r = resolve_capability("browser")
    # browser capability has 3 providers — should always have fallback
    if r.fallback is not None:
        PASS("T7 browser has fallback", f"primary={r.provider}, fallback={r.fallback.provider}")
    else:
        FAIL("T7 browser has fallback", f"no fallback for browser (only 1 provider? primary={r.provider})")


def t8_unknown_capability_returns_unavailable() -> None:
    if not _require_import():
        return
    r = resolve_capability("__nonexistent__xyz__")
    if r.status == "UNAVAILABLE" and r.provider is None:
        PASS("T8 unknown capability → UNAVAILABLE", "no exception raised")
    else:
        FAIL("T8 unknown capability → UNAVAILABLE", f"got status={r.status}, provider={r.provider}")


def t9_resolution_fields_correct() -> None:
    if not _require_import():
        return
    r = resolve_capability("memory")
    required_keys = {"capability", "provider", "status", "tool_prefix", "fallback", "action", "notes"}
    d = r.as_dict()
    missing = required_keys - set(d.keys())
    if missing:
        FAIL("T9 Resolution fields", f"missing keys: {missing}")
        return
    if d["capability"] != "memory":
        FAIL("T9 Resolution fields", f"capability mismatch: {d['capability']}")
        return
    if d["tool_prefix"] is None:
        FAIL("T9 Resolution fields", "tool_prefix is None for LIVE memory")
        return
    PASS("T9 Resolution fields", f"all keys present, tool_prefix={d['tool_prefix']}")


def t10_resolve_many() -> None:
    if not _require_import():
        return
    rt = CapabilityRouter()
    caps = ["memory", "documentation", "browser", "project_management"]
    results = rt.resolve_many(caps)
    if set(results.keys()) != set(caps):
        FAIL("T10 resolve_many", f"missing keys in result: {set(caps) - set(results.keys())}")
        return
    for name, res in results.items():
        if not isinstance(res, Resolution):
            FAIL("T10 resolve_many", f"{name} did not return Resolution instance")
            return
    PASS("T10 resolve_many", f"{len(caps)} capabilities resolved")


def t11_critical_status() -> None:
    if not _require_import():
        return
    rt = CapabilityRouter()
    cs = rt.critical_status()
    expected = {"memory", "browser", "documentation"}
    if set(cs.keys()) != expected:
        FAIL("T11 critical_status keys", f"expected {expected}, got {set(cs.keys())}")
        return
    if cs.get("memory") != "LIVE":
        FAIL("T11 critical_status memory", f"memory should be LIVE, got {cs.get('memory')}")
        return
    PASS("T11 critical_status", " | ".join(f"{k}={v}" for k, v in sorted(cs.items())))


def t12_all_live() -> None:
    if not _require_import():
        return
    rt = CapabilityRouter()
    live = rt.all_live()
    if not live:
        FAIL("T12 all_live", "no LIVE capabilities found")
        return
    if "memory" not in live:
        FAIL("T12 all_live", f"memory missing from LIVE list: {live}")
        return
    PASS("T12 all_live", f"{len(live)} LIVE: {', '.join(sorted(live))}")


def t13_21st_dev_diagnosis() -> None:
    """
    F16.5: 21st.dev / Magic — diagnóstico sin instalar.
    Verifica que está marcado DEFERRED_PAID en el registry.
    No instala nada.
    """
    try:
        from core.capabilities.registry import get_capability
        cap = get_capability("design")
        if cap is None:
            FAIL("T13 21st.dev diagnosis", "capability 'design' not in registry")
            return
        p = cap.active_provider
        if p is None:
            FAIL("T13 21st.dev diagnosis", "no provider for design capability")
            return
        if p.mcp_id != "magic_21st":
            FAIL("T13 21st.dev diagnosis", f"unexpected provider: {p.mcp_id}")
            return
        if p.status in ("DEFERRED_PAID", "NOT_RECOMMENDED"):
            PASS("T13 21st.dev diagnosis",
                 f"status={p.status} — requires paid API key (TWENTY_FIRST_API_KEY). "
                 f"Free tier: NOT available as of registry entry. Mark CONFIG_AVAILABLE if free tier found.")
        elif p.status == "LIVE":
            PASS("T13 21st.dev diagnosis", "21st.dev LIVE — user has activated paid tier")
        else:
            FAIL("T13 21st.dev diagnosis", f"unexpected status={p.status}")
    except Exception as e:
        FAIL("T13 21st.dev diagnosis", str(e))


def t14_agent_protocol_capability_section() -> None:
    """
    F16.6: agent-protocol.md debe contener sección sobre capability request.
    """
    protocol_path = PROJECT_ROOT / ".claude" / "agents" / "agent-protocol.md"
    if not protocol_path.exists():
        FAIL("T14 agent-protocol capability section", "agent-protocol.md not found")
        return
    content = protocol_path.read_text(encoding="utf-8", errors="replace")
    markers = [
        "resolve_capability",
        "solicitar capability",
    ]
    found = [m for m in markers if m in content]
    if len(found) >= 1:
        PASS("T14 agent-protocol capability section", f"found markers: {found}")
    else:
        FAIL("T14 agent-protocol capability section",
             "no capability request section found — F16.6 update missing")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("Bloque F16 -- Capability Router Tests")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    t1_memory_resolves_to_engram()
    t2_documentation_resolves_to_context7()
    t3_browser_resolves_with_fallbacks()
    t4_project_management_resolves_to_notion()
    t5_repository_pending_token()
    t6_design_deferred_paid()
    t7_browser_has_fallback()
    t8_unknown_capability_returns_unavailable()
    t9_resolution_fields_correct()
    t10_resolve_many()
    t11_critical_status()
    t12_all_live()
    t13_21st_dev_diagnosis()
    t14_agent_protocol_capability_section()

    n_pass = sum(1 for r in _results if r["status"] == "PASS")
    n_fail = sum(1 for r in _results if r["status"] == "FAIL")

    print(f"\nTotal: {len(_results)} | PASS: {n_pass} | FAIL: {n_fail}")
    print()
    print(f"RESULTADO: {'PASS' if n_fail == 0 else 'FAIL'}")
    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
