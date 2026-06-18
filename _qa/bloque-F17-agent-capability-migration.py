#!/usr/bin/env python3
"""
Bloque F17 — Agent Capability Migration Tests
==============================================

Verifica que los agentes críticos usan lenguaje de capability abstracto
en lugar de references directas a MCPs concretos en prosa instructiva.

Reglas de clasificación (F17):
  PERMITIDO (no se penaliza):
    - mcp__provider__tool en bloques de código (```...```) o backticks
    - Nombres de provider en listas "Tools:" o "## Tools" (configuración)
    - Nombres de provider en secciones "## Capability Mapping"
    - Referencias en tablas de herramientas-por-agente
    - Referencias históricas/notas técnicas entre paréntesis

  REQUERIDO:
    - Agentes críticos deben tener sección "## Capability Mapping (F16)"
    - Instrucciones de fallback deben usar lenguaje de capability
    - Secciones instructivas deben anotar [capability: X] o "capability X"

Tests:
  T1  evidence-collector tiene Capability Mapping
  T2  codepen-explorer tiene Capability Mapping
  T3  performance-benchmarker tiene Capability Mapping
  T4  reality-checker tiene Capability Mapping
  T5  frontend-developer tiene annotación capability documentation
  T6  ui-designer tiene annotación capability documentation
  T7  orquestador tiene annotación capability en qa_mode
  T8  evidence-collector no usa "via Playwright MCP" en prosa (migrado)
  T9  codepen-explorer no usa "usa Playwright MCP" sin anotación
  T10 performance-benchmarker: fallback usa lenguaje capability
  T11 agent-protocol.md tiene sección F16 capability request (regresión)
  T12 resolve_capability sigue funcionando (regresión F16)
  T13 .claude/agents/ y agents/ sincronizados para archivos migrados
  T14 ningún agente migrado usa "via Context7 MCP" sin annotación

Salida:
  [PASS] / [FAIL] por test
  Resumen y clasificación al final

Exit code: 0 = todo PASS | 1 = al menos un FAIL
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
AGENTS_MIRROR = PROJECT_ROOT / "agents"

sys.path.insert(0, str(PROJECT_ROOT))

_results: list[dict] = []


def PASS(label: str, detail: str = "") -> None:
    _results.append({"status": "PASS", "label": label, "detail": detail})
    print(f"  [PASS] {label}" + (f" -- {detail}" if detail else ""))


def FAIL(label: str, detail: str = "") -> None:
    _results.append({"status": "FAIL", "label": label, "detail": detail})
    print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def _read(agent: str) -> str:
    path = AGENTS_DIR / f"{agent}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _has_capability_mapping(content: str) -> bool:
    return "## Capability Mapping" in content or "Capability Mapping (F16)" in content


# ---------------------------------------------------------------------------
# T1-T4: Capability Mapping sections
# ---------------------------------------------------------------------------

def t1_evidence_collector_mapping() -> None:
    c = _read("evidence-collector")
    if not c:
        FAIL("T1 evidence-collector Capability Mapping", "file not found")
        return
    if _has_capability_mapping(c):
        PASS("T1 evidence-collector Capability Mapping")
    else:
        FAIL("T1 evidence-collector Capability Mapping", "section missing")


def t2_codepen_explorer_mapping() -> None:
    c = _read("codepen-explorer")
    if not c:
        FAIL("T2 codepen-explorer Capability Mapping", "file not found")
        return
    if _has_capability_mapping(c):
        PASS("T2 codepen-explorer Capability Mapping")
    else:
        FAIL("T2 codepen-explorer Capability Mapping", "section missing")


def t3_performance_benchmarker_mapping() -> None:
    c = _read("performance-benchmarker")
    if not c:
        FAIL("T3 performance-benchmarker Capability Mapping", "file not found")
        return
    if _has_capability_mapping(c):
        PASS("T3 performance-benchmarker Capability Mapping")
    else:
        FAIL("T3 performance-benchmarker Capability Mapping", "section missing")


def t4_reality_checker_mapping() -> None:
    c = _read("reality-checker")
    if not c:
        FAIL("T4 reality-checker Capability Mapping", "file not found")
        return
    if _has_capability_mapping(c):
        PASS("T4 reality-checker Capability Mapping")
    else:
        FAIL("T4 reality-checker Capability Mapping", "section missing")


# ---------------------------------------------------------------------------
# T5-T7: Capability annotation in key sections
# ---------------------------------------------------------------------------

def t5_frontend_developer_documentation_capability() -> None:
    c = _read("frontend-developer")
    if not c:
        FAIL("T5 frontend-developer documentation capability", "file not found")
        return
    # Should have capability annotation near 21st.dev section
    markers = [
        "capability `documentation`",
        "capability documentation",
        "[capability: documentation",
    ]
    found = any(m in c for m in markers)
    if found:
        PASS("T5 frontend-developer documentation capability")
    else:
        FAIL("T5 frontend-developer documentation capability", "no capability annotation found for 21st.dev/Context7 section")


def t6_ui_designer_documentation_capability() -> None:
    c = _read("ui-designer")
    if not c:
        FAIL("T6 ui-designer documentation capability", "file not found")
        return
    markers = [
        "capability `documentation`",
        "capability documentation",
        "[capability: documentation",
    ]
    found = any(m in c for m in markers)
    if found:
        PASS("T6 ui-designer documentation capability")
    else:
        FAIL("T6 ui-designer documentation capability", "no capability annotation for Context7 reference")


def t7_orquestador_qa_mode_capability() -> None:
    c = _read("orquestador")
    if not c:
        FAIL("T7 orquestador qa_mode capability", "file not found")
        return
    if "capability browser" in c or "capability `browser`" in c or "resolve_capability" in c:
        PASS("T7 orquestador qa_mode capability annotation")
    else:
        FAIL("T7 orquestador qa_mode capability annotation", "no capability reference for browser in orquestador")


# ---------------------------------------------------------------------------
# T8-T10: Migrated language checks
# ---------------------------------------------------------------------------

def t8_evidence_collector_description_migrated() -> None:
    """description frontmatter should NOT say 'via Playwright MCP' (was migrated)."""
    c = _read("evidence-collector")
    if not c:
        FAIL("T8 evidence-collector description migrated", "file not found")
        return
    # Get the description line
    for line in c.split("\n")[:10]:
        if line.startswith("description:"):
            if "via Playwright MCP" in line:
                FAIL("T8 evidence-collector description migrated",
                     "description still says 'via Playwright MCP' — not migrated")
            elif "capability browser" in line or "capability" in line:
                PASS("T8 evidence-collector description migrated", "uses capability language")
            else:
                PASS("T8 evidence-collector description migrated", "no direct MCP reference in description")
            return
    FAIL("T8 evidence-collector description migrated", "description line not found")


def t9_codepen_explorer_description_migrated() -> None:
    """description frontmatter should NOT say 'via Playwright MCP'."""
    c = _read("codepen-explorer")
    if not c:
        FAIL("T9 codepen-explorer description migrated", "file not found")
        return
    for line in c.split("\n")[:10]:
        if line.startswith("description:"):
            if "via Playwright MCP" in line:
                FAIL("T9 codepen-explorer description migrated",
                     "description still says 'via Playwright MCP'")
            elif "capability browser" in line:
                PASS("T9 codepen-explorer description migrated", "uses capability language")
            else:
                PASS("T9 codepen-explorer description migrated", "no direct MCP in description")
            return
    FAIL("T9 codepen-explorer description migrated", "description line not found")


def t10_performance_benchmarker_fallback_migrated() -> None:
    """Fallback language should use capability, not 'Playwright no disponible'."""
    c = _read("performance-benchmarker")
    if not c:
        FAIL("T10 performance-benchmarker fallback migrated", "file not found")
        return
    # Old pattern: "Si Playwright no disponible"
    # New pattern: "Si capability browser no está LIVE" or similar
    if "Si Playwright no disponible" in c:
        FAIL("T10 performance-benchmarker fallback migrated",
             "still uses 'Si Playwright no disponible' — not migrated")
    elif "capability `browser` no está LIVE" in c or "capability browser" in c:
        PASS("T10 performance-benchmarker fallback migrated")
    else:
        FAIL("T10 performance-benchmarker fallback migrated",
             "neither old nor new pattern found — check migration")


# ---------------------------------------------------------------------------
# T11: Regression — agent-protocol F16 section
# ---------------------------------------------------------------------------

def t11_agent_protocol_f16_section() -> None:
    c = _read("agent-protocol")
    if not c:
        FAIL("T11 agent-protocol F16 section", "file not found")
        return
    if "resolve_capability" in c and "solicitar capability" in c:
        PASS("T11 agent-protocol F16 section (regression)")
    elif "F16" in c or "Capability Router" in c:
        PASS("T11 agent-protocol F16 section (regression)", "F16 section present")
    else:
        FAIL("T11 agent-protocol F16 section (regression)", "F16 capability section missing")


# ---------------------------------------------------------------------------
# T12: Regression — resolve_capability still works
# ---------------------------------------------------------------------------

def t12_resolve_capability_regression() -> None:
    try:
        from core.capabilities.router import resolve_capability
        r = resolve_capability("memory")
        if r.provider == "engram" and r.status == "LIVE":
            PASS("T12 resolve_capability regression", "memory→engram LIVE")
        else:
            FAIL("T12 resolve_capability regression", f"provider={r.provider} status={r.status}")
    except Exception as e:
        FAIL("T12 resolve_capability regression", str(e))


# ---------------------------------------------------------------------------
# T13: Sync check — .claude/agents/ matches agents/ for migrated files
# ---------------------------------------------------------------------------

MIGRATED_AGENTS = [
    "evidence-collector",
    "codepen-explorer",
    "performance-benchmarker",
    "reality-checker",
    "frontend-developer",
    "ui-designer",
    "orquestador",
]


def t13_agents_sync() -> None:
    mismatches = []
    for agent in MIGRATED_AGENTS:
        src = AGENTS_DIR / f"{agent}.md"
        dst = AGENTS_MIRROR / f"{agent}.md"
        if not src.exists():
            mismatches.append(f"{agent}: source missing in .claude/agents/")
            continue
        if not dst.exists():
            mismatches.append(f"{agent}: mirror missing in agents/")
            continue
        if src.read_bytes() != dst.read_bytes():
            mismatches.append(f"{agent}: .claude/agents/ != agents/ (out of sync)")

    if mismatches:
        FAIL("T13 .claude/agents/ ↔ agents/ sync", "; ".join(mismatches))
    else:
        PASS("T13 .claude/agents/ ↔ agents/ sync",
             f"{len(MIGRATED_AGENTS)} migrated agents in sync")


# ---------------------------------------------------------------------------
# T14: No "via Context7 MCP" in instructional prose without annotation
# ---------------------------------------------------------------------------

def t14_no_bare_context7_instructions() -> None:
    """
    Files that have been migrated should not have bare 'via Context7 MCP'
    in instructional prose. Code blocks are exempt.
    """
    targets = ["frontend-developer", "ui-designer", "orquestador"]
    violations = []

    for agent in targets:
        c = _read(agent)
        if not c:
            continue
        # Strip code blocks before checking
        import re
        no_code = re.sub(r"```[\s\S]*?```", "", c)
        # Also strip inline code
        no_code = re.sub(r"`[^`]+`", "", no_code)
        if "via Context7 MCP" in no_code:
            violations.append(agent)

    if violations:
        FAIL("T14 no bare 'via Context7 MCP' in migrated agents",
             f"found in: {violations}")
    else:
        PASS("T14 no bare 'via Context7 MCP' in migrated agents")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("Bloque F17 -- Agent Capability Migration Tests")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    t1_evidence_collector_mapping()
    t2_codepen_explorer_mapping()
    t3_performance_benchmarker_mapping()
    t4_reality_checker_mapping()
    t5_frontend_developer_documentation_capability()
    t6_ui_designer_documentation_capability()
    t7_orquestador_qa_mode_capability()
    t8_evidence_collector_description_migrated()
    t9_codepen_explorer_description_migrated()
    t10_performance_benchmarker_fallback_migrated()
    t11_agent_protocol_f16_section()
    t12_resolve_capability_regression()
    t13_agents_sync()
    t14_no_bare_context7_instructions()

    n_pass = sum(1 for r in _results if r["status"] == "PASS")
    n_fail = sum(1 for r in _results if r["status"] == "FAIL")

    print(f"\nTotal: {len(_results)} | PASS: {n_pass} | FAIL: {n_fail}")
    print()
    print(f"RESULTADO: {'PASS' if n_fail == 0 else 'FAIL'}")
    return 1 if n_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
