#!/usr/bin/env python3
"""
Bloque F34 — Knowledge Resolver Wiring
======================================

Valida que resolve_knowledge() quedó cableado documentalmente en el flujo
(CLAUDE.md, orquestador, agent-protocol) + doc de contrato, y que las queries
clave resuelven. Wiring documental only — sin runtime.

Tests:
  1  docs/atlas-knowledge-resolver.md existe
  2  CLAUDE.md menciona resolve_knowledge y sigue < 2K tokens
  3  orquestador.md menciona resolve_knowledge
  4  agent-protocol.md menciona resolve_knowledge
  5  query "pipeline phase-1" resuelve a la ref de FASE 1
  6  query "pipeline phase-3" resuelve a la ref de FASE 3
  7  query "qa evidence" resuelve a contrato evidence/QA
  8  query "frontend agent contract" resuelve a contrato/índice
  9  query "release gate" resuelve a release ref
  10 resolver devuelve metadata-only (sin content)
  11 ningún documento grande volvió a always_on (solo CLAUDE.md)
  12 doc registrado en knowledge.registry.yaml
  13 query desconocida → [] (no rompe)

Total: 13 tests
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name, detail=""):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def _read(p):
    return (PROJECT_ROOT / p).read_text(encoding="utf-8", errors="replace")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("Bloque F34 -- Knowledge Resolver Wiring")
    print("=" * 60)
    print()

    import knowledge_resolver as kr
    import boot_profiler as bp

    # T1 doc exists
    if (PROJECT_ROOT / "docs/atlas-knowledge-resolver.md").exists():
        ok("T1 docs/atlas-knowledge-resolver.md exists")
    else:
        fail("T1 doc missing")

    # T2 CLAUDE.md mentions + < 2K tokens
    cm = _read("CLAUDE.md")
    cm_tok = bp.estimate_tokens(len(cm.encode("utf-8")))
    if "resolve_knowledge" in cm and cm_tok < 2000:
        ok("T2 CLAUDE.md wired + < 2K tokens", f"{cm_tok}t")
    else:
        fail("T2 CLAUDE.md", f"mentions={'resolve_knowledge' in cm} tokens={cm_tok}")

    # T3 orquestador mentions
    if "resolve_knowledge" in _read(".claude/agents/orquestador.md"):
        ok("T3 orquestador.md wired")
    else:
        fail("T3 orquestador.md")

    # T4 agent-protocol mentions
    if "resolve_knowledge" in _read(".claude/agents/agent-protocol.md"):
        ok("T4 agent-protocol.md wired")
    else:
        fail("T4 agent-protocol.md")

    # T5-T9 key queries
    def top_path(q):
        r = kr.resolve_knowledge(q)
        return (r[0]["path"] if r else ""), len(r)

    p, n = top_path("pipeline phase-1")
    if p.endswith("orchestrator-pipeline-phase-1.md"):
        ok("T5 'pipeline phase-1' -> FASE 1", f"{n} refs")
    else:
        fail("T5 pipeline phase-1", p)

    p, n = top_path("pipeline phase-3")
    if p.endswith("orchestrator-pipeline-phase-3.md"):
        ok("T6 'pipeline phase-3' -> FASE 3", f"{n} refs")
    else:
        fail("T6 pipeline phase-3", p)

    r = kr.resolve_knowledge("qa evidence")
    if r and any("evidence" in x["path"] for x in r):
        ok("T7 'qa evidence' -> evidence contract", r[0]["path"].split("/")[-1])
    else:
        fail("T7 qa evidence", str([x["path"] for x in r]))

    r = kr.resolve_knowledge("frontend agent contract")
    if r and any("contract" in x["path"] for x in r):
        ok("T8 'frontend agent contract' -> contract", r[0]["path"].split("/")[-1])
    else:
        fail("T8 frontend agent contract", str([x["path"] for x in r]))

    r = kr.resolve_knowledge("release gate")
    if r and any("release" in x["path"] for x in r):
        ok("T9 'release gate' -> release ref", r[0]["path"].split("/")[-1])
    else:
        fail("T9 release gate", str([x["path"] for x in r]))

    # T10 metadata only
    r = kr.resolve_knowledge("pipeline phase-1")
    s = r[0] if r else {}
    if "content" not in s and "body" not in s and "path" in s:
        ok("T10 metadata-only (no content)")
    else:
        fail("T10 metadata", str(s.keys()))

    # T11 only CLAUDE.md always_on
    reg = kr.load_registry()
    always_on = [e["id"] for e in reg if e.get("load_policy") == "always_on"]
    if always_on == ["claude-md"]:
        ok("T11 only CLAUDE.md is always_on")
    else:
        fail("T11 always_on", str(always_on))

    # T12 doc registered
    ids = {e["id"] for e in reg}
    if "atlas-knowledge-resolver" in ids:
        ok("T12 resolver doc registered")
    else:
        fail("T12 registry", "doc not registered")

    # T13 unknown query
    if kr.resolve_knowledge("zzz-nope-xyz") == []:
        ok("T13 unknown query -> [] (no crash)")
    else:
        fail("T13 unknown query")

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
