#!/usr/bin/env python3
"""
Bloque F33 — Knowledge Resolver + Second-Layer Decomposition
============================================================

Valida tools/knowledge_resolver.py + la descomposición de segunda capa
(pipeline por fase, contracts por concern). ANÁLISIS/lookup only — no runtime.

Tests:
  T1  knowledge_resolver.py existe + API (load_registry, resolve_knowledge)
  T2  --list funciona (CLI)
  T3  --resolve pipeline devuelve el índice y/o fases
  T4  --resolve phase-1 devuelve la ref de FASE 1
  T5  --resolve frontend devuelve un contrato (dev/frontend)
  T6  --resolve qa devuelve contrato QA/evidence
  T7  resultados son metadata only (sin contenido de archivo)
  T8  todos los paths resueltos existen en disco
  T9  query desconocida → [] sin romper
  T10 --json produce JSON válido
  T11 registry mantiene CLAUDE.md always_on
  T12 orquestador.md y agent-protocol.md siguen lazy
  T13 índices nuevos (pipeline, contracts) < 3K tokens
  T14 refs de fase/contrato existen + contenido conservado (verbatim markers)

Total: 14 tests
"""

import json
import subprocess
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


def _resolver(*args):
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "knowledge_resolver.py"), *args],
                       capture_output=True, text=True, timeout=60)
    return r


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("Bloque F33 -- Knowledge Resolver")
    print("=" * 60)
    print()

    # T1 import + API
    try:
        import knowledge_resolver as kr
        if hasattr(kr, "load_registry") and hasattr(kr, "resolve_knowledge"):
            ok("T1 import + API")
        else:
            fail("T1 API", "missing functions"); print("\nRESULTADO: FAIL"); sys.exit(1)
    except Exception as e:
        fail("T1 import", str(e)); print("\nRESULTADO: FAIL"); sys.exit(1)

    # T2 --list
    r = _resolver("--list")
    if r.returncode == 0 and "Knowledge registry" in r.stdout:
        ok("T2 --list works")
    else:
        fail("T2 --list", f"rc={r.returncode}")

    # T3 resolve pipeline
    res = kr.resolve_knowledge("pipeline")
    paths = [x["path"] for x in res]
    if any("orchestrator-pipeline" in p for p in paths):
        ok("T3 resolve pipeline -> index/phases", f"{len(res)} refs")
    else:
        fail("T3 pipeline", str(paths))

    # T4 resolve phase-1
    res = kr.resolve_knowledge("phase-1")
    if res and res[0]["path"].endswith("orchestrator-pipeline-phase-1.md"):
        ok("T4 resolve phase-1 -> FASE 1 ref")
    else:
        fail("T4 phase-1", str([x["path"] for x in res]))

    # T5 resolve frontend
    res = kr.resolve_knowledge("frontend")
    if res and any("contract" in x["path"] or "build" in x["path"] for x in res):
        ok("T5 resolve frontend -> contract/build", res[0]["path"])
    else:
        fail("T5 frontend", str([x["path"] for x in res]))

    # T6 resolve qa
    res = kr.resolve_knowledge("qa")
    if res and any("evidence" in x["path"] or "phase-3" in x["path"] or "contract" in x["path"] for x in res):
        ok("T6 resolve qa -> QA/evidence", f"{len(res)} refs")
    else:
        fail("T6 qa", str([x["path"] for x in res]))

    # T7 metadata only (no content)
    res = kr.resolve_knowledge("pipeline")
    sample = res[0] if res else {}
    if "path" in sample and "estimated_tokens" in sample and "content" not in sample and "body" not in sample:
        ok("T7 metadata only (no content field)")
    else:
        fail("T7 metadata", str(sample.keys()))

    # T8 resolved paths exist
    res = kr.resolve_knowledge("pipeline") + kr.resolve_knowledge("contracts")
    missing = [x["path"] for x in res if not (PROJECT_ROOT / x["path"]).exists()]
    if not missing:
        ok("T8 all resolved paths exist")
    else:
        fail("T8 paths exist", str(missing))

    # T9 unknown query
    res = kr.resolve_knowledge("zzz-nonexistent-query")
    if res == []:
        ok("T9 unknown query -> [] (no crash)")
    else:
        fail("T9 unknown", str(res))

    # T10 --json valid
    r = _resolver("--json", "pipeline")
    try:
        d = json.loads(r.stdout)
        if d.get("query") == "pipeline" and isinstance(d.get("results"), list):
            ok("T10 --json valid")
        else:
            fail("T10 --json", "bad shape")
    except Exception as e:
        fail("T10 --json", str(e))

    # T11 CLAUDE.md always_on
    reg = {e["id"]: e for e in kr.load_registry()}
    if reg.get("claude-md", {}).get("load_policy") == "always_on":
        ok("T11 CLAUDE.md always_on")
    else:
        fail("T11 always_on", str(reg.get("claude-md", {}).get("load_policy")))

    # T12 orquestador + protocol lazy
    if (reg.get("orquestador", {}).get("load_policy") == "lazy"
            and reg.get("agent-protocol", {}).get("load_policy") == "lazy"):
        ok("T12 orquestador + agent-protocol lazy")
    else:
        fail("T12 lazy", "facades not lazy")

    # T13 new indexes < 3K tokens
    import boot_profiler as bp
    idx_ok = True
    sizes = {}
    for p in (".claude/agents/refs/orchestrator-pipeline.md",
              ".claude/agents/refs/protocol-agent-contracts.md"):
        b, _ = bp.measure_file(PROJECT_ROOT / p)
        tok = bp.estimate_tokens(b)
        sizes[Path(p).name] = tok
        if tok >= 3000:
            idx_ok = False
    if idx_ok:
        ok("T13 new indexes < 3K tokens", str(sizes))
    else:
        fail("T13 index size", str(sizes))

    # T14 phase/contract refs exist + content preserved
    must_exist = [
        ".claude/agents/refs/orchestrator-pipeline-phase-1.md",
        ".claude/agents/refs/orchestrator-pipeline-phase-5.md",
        ".claude/agents/refs/protocol-agent-contract-core.md",
        ".claude/agents/refs/protocol-agent-contract-evidence.md",
    ]
    miss = [p for p in must_exist if not (PROJECT_ROOT / p).exists()]
    # content preserved: phase-1 should contain "FASE 1", evidence should mention "screenshot" or "network"
    p1 = (PROJECT_ROOT / ".claude/agents/refs/orchestrator-pipeline-phase-1.md").read_text(encoding="utf-8", errors="replace")
    ev = (PROJECT_ROOT / ".claude/agents/refs/protocol-agent-contract-evidence.md").read_text(encoding="utf-8", errors="replace")
    content_ok = ("FASE 1" in p1) and ("Network" in ev or "Screenshot" in ev or "network" in ev)
    if not miss and content_ok:
        ok("T14 phase/contract refs exist + content preserved")
    else:
        fail("T14 refs/content", f"missing={miss} content_ok={content_ok}")

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
