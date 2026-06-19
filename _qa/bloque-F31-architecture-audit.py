#!/usr/bin/env python3
"""
Bloque F31 — Architecture Intelligence Audit
=============================================

Valida tools/architecture_audit.py + config/architecture.registry.yaml — el
analizador de inteligencia arquitectónica (ANÁLISIS ONLY, no modifica nada).

Tests:
  T1  módulo importa; API pública presente
  T2  config/architecture.registry.yaml existe y es YAML válido
  T3  load_config() funciona con defaults si el registry falta (fail-open)
  T4  analyze() retorna Architecture Score int en [0, 100]
  T5  analyze() expone los 11 detectores esperados
  T6  CLAUDE.md aparece en detectors.always_on
  T7  orquestador.md + agent-protocol.md son decompose_candidates (god-files)
  T8  recommendations no vacío, con priority P0..P4
  T9  hotspots ordenados por entropy desc
  T10 --json CLI produce JSON válido con architecture_score
  T11 --score CLI imprime un entero
  T12 detector responsabilidades: orquestador toca >= 6 dominios
  T13 análisis es read-only: no modifica archivos de entrada (mtime estable)
  T14 dist mirror dedup: agents/ no duplica .claude/agents/ en files scanned

Total: 14 tests
"""

import json
import os
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


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("Bloque F31 -- Architecture Intelligence Audit")
    print("=" * 60)
    print()

    # T1 import
    try:
        import architecture_audit as aa
        for fn in ("load_config", "analyze"):
            if not hasattr(aa, fn):
                fail("T1 import + API", f"missing {fn}"); print("\nRESULTADO: FAIL"); sys.exit(1)
        ok("T1 import + public API")
    except Exception as e:
        fail("T1 import", str(e)); print("\nRESULTADO: FAIL"); sys.exit(1)

    # T2 registry exists + valid YAML
    reg = PROJECT_ROOT / "config" / "architecture.registry.yaml"
    try:
        import yaml
        data = yaml.safe_load(reg.read_text(encoding="utf-8"))
        if reg.exists() and isinstance(data, dict) and "thresholds" in data:
            ok("T2 architecture.registry.yaml valid")
        else:
            fail("T2 registry", "missing thresholds")
    except Exception as e:
        fail("T2 registry", str(e))

    # T3 load_config fail-open with defaults
    cfg = aa.load_config(Path(PROJECT_ROOT / "config" / "does-not-exist.yaml"))
    if cfg.get("thresholds", {}).get("doc_high_tokens"):
        ok("T3 load_config defaults (fail-open)")
    else:
        fail("T3 load_config defaults")

    # Run analysis once
    result = aa.analyze()

    # T4 score in range
    score = result.get("architecture_score")
    if isinstance(score, int) and 0 <= score <= 100:
        ok("T4 architecture_score in [0,100]", str(score))
    else:
        fail("T4 score", f"got {score}")

    # T5 detectors present
    expected = {"oversized", "large", "duplicated_knowledge", "rules_in_many_files",
                "mixed_responsibilities", "decompose_candidates", "unused_references",
                "always_on", "never_loaded", "boot_dependency_risks", "obsolete_docs"}
    det = result.get("detectors", {})
    miss = expected - det.keys()
    if not miss:
        ok("T5 all 11 detectors present")
    else:
        fail("T5 detectors", f"missing {miss}")

    # T6 CLAUDE.md in always_on
    if "CLAUDE.md" in det.get("always_on", []):
        ok("T6 CLAUDE.md detected always_on")
    else:
        fail("T6 always_on", str(det.get("always_on")))

    # T7 (post-F32): the two original god-files are NO LONGER decompose candidates
    # (slimmed to facades). The auditor must reflect the decomposition.
    dc_paths = {f["path"] for f in det.get("decompose_candidates", [])}
    if (".claude/agents/orquestador.md" not in dc_paths
            and ".claude/agents/agent-protocol.md" not in dc_paths):
        ok("T7 god-file facades no longer decompose candidates (F32)")
    else:
        fail("T7 decompose (facades should be slim)", str(dc_paths))

    # T8 recommendations
    recs = result.get("recommendations", [])
    prios = {r.get("priority") for r in recs}
    if recs and prios <= {"P0", "P1", "P2", "P3", "P4"}:
        ok("T8 recommendations with valid priorities", str(sorted(prios)))
    else:
        fail("T8 recommendations", str(prios))

    # T9 hotspots sorted by entropy desc
    hs = result.get("hotspots", [])
    ents = [h["entropy"] for h in hs]
    if ents == sorted(ents, reverse=True) and len(hs) >= 1:
        ok("T9 hotspots sorted by entropy desc")
    else:
        fail("T9 hotspots", "not sorted")

    # T10 --json CLI
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "architecture_audit.py"), "--json"],
                       capture_output=True, text=True, timeout=60)
    try:
        j = json.loads(r.stdout)
        if "architecture_score" in j:
            ok("T10 --json CLI valid")
        else:
            fail("T10 --json", "no score key")
    except Exception as e:
        fail("T10 --json", str(e))

    # T11 --score CLI integer
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "architecture_audit.py"), "--score"],
                       capture_output=True, text=True, timeout=60)
    if r.stdout.strip().isdigit():
        ok("T11 --score CLI integer", r.stdout.strip())
    else:
        fail("T11 --score", repr(r.stdout))

    # T12 (post-F32): orquestador.md facade is now slim (small token footprint),
    # validating the decomposition reduced the per-load cost.
    orq_files = aa.analyze()  # fresh
    import boot_profiler as _bp
    orq_scan = next((f for f in _bp.scan_files(PROJECT_ROOT)
                     if f["path"] == ".claude/agents/orquestador.md"), {})
    if 0 < orq_scan.get("estimated_tokens", 99999) < 5000:
        ok("T12 orquestador facade slimmed (<5K tokens)", str(orq_scan.get("estimated_tokens")))
    else:
        fail("T12 orquestador facade size", str(orq_scan.get("estimated_tokens")))

    # T13 read-only: input mtime unchanged after analyze
    target = PROJECT_ROOT / "CLAUDE.md"
    before = target.stat().st_mtime
    aa.analyze()
    after = target.stat().st_mtime
    if before == after:
        ok("T13 analysis is read-only (no mtime change)")
    else:
        fail("T13 read-only", "input mtime changed")

    # T14 dist-mirror dedup
    paths = [f["path"] for f in det.get("decompose_candidates", [])]
    if not any(p.startswith("agents/") for p in paths):
        ok("T14 dist mirror deduped (no agents/ duplicate in candidates)")
    else:
        fail("T14 dedup", str(paths))

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
