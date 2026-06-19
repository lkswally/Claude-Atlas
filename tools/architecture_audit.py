"""
ATLAS Architecture Audit — F31 (Architecture Intelligence)
===========================================================

ANALYSIS ONLY. Detects architectural problems that CI, healthcheck, and drift
detection do not surface — and emits objective evidence (Architecture Score,
tech-debt ranking, hotspots, prioritized recommendations) to guide FUTURE
refactors. It changes nothing at runtime.

Inputs (read-only):
  - config/architecture.registry.yaml  (thresholds, weights, domains)
  - config/knowledge.registry.yaml      (load policies, ownership)
  - config/test.registry.yaml, mcp.registry.yaml, projects.registry.yaml
  - ADR/  + reports docs/F26/F28/F29/F30
  - tools/boot_profiler.py              (static scan + duplication)

Detectors answer:
  oversized / large docs · duplicated knowledge · rules in many files ·
  mixed responsibilities · decompose candidates · unused references ·
  always-on knowledge · never-loaded knowledge · boot dependency risks ·
  obsolete docs · architectural entropy hotspots.

CLI:
  python tools/architecture_audit.py --report     # human report
  python tools/architecture_audit.py --json       # machine-readable
  python tools/architecture_audit.py --score      # just the number
  python tools/architecture_audit.py --hotspots   # entropy ranking
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

_ARCH_REGISTRY = _PROJECT_ROOT / "config" / "architecture.registry.yaml"

# Default thresholds/weights — used if the registry is missing (fail-open).
_DEFAULTS = {
    "thresholds": {
        "doc_warn_tokens": 6000,
        "doc_high_tokens": 12000,
        "always_on_budget_tokens": 2500,
        "duplication_min_files": 5,
        "mixed_responsibility_min": 6,
        "decompose_min_tokens": 12000,
    },
    "responsibility_domains": {
        "boot": ["boot", "startup", "always_on", "index"],
        "memory": ["engram", "topic_key", "mem_search", "dual-write"],
        "pipeline": ["fase ", "phase", "orquestador", "pipeline", "dispatcher"],
        "qa": ["evidence-collector", "reality-checker", "qa", "healthcheck"],
        "security": ["hook", "block-no-verify", "secrets"],
        "release": ["release", "ci", "tag", "gate"],
        "build": ["stack", "next.js", "better auth", "nothing", "vercel"],
        "capability": ["capability", "resolve_capability", "mcp", "registry"],
    },
    "score_weights": {
        "oversized_file": 6, "large_file": 1, "duplication_candidate": 1,
        "mixed_responsibility": 0, "decompose_candidate": 6, "unused_reference": 3,
        "boot_dependency_risk": 12, "obsolete_doc": 2, "always_on_over_budget": 10,
    },
}


# ---------------------------------------------------------------------------
# Config + inputs
# ---------------------------------------------------------------------------

def load_config(path: Path | None = None) -> dict:
    target = path or _ARCH_REGISTRY
    cfg = json.loads(json.dumps(_DEFAULTS))  # deep copy
    if not target.exists():
        return cfg
    try:
        import yaml
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return cfg
    for key in ("thresholds", "responsibility_domains", "score_weights"):
        if isinstance(data.get(key), dict):
            cfg[key].update(data[key])
    cfg["inputs"] = data.get("inputs", {})
    cfg["obsolete"] = data.get("obsolete", {})
    return cfg


def _load_yaml(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _knowledge_entries() -> list[dict]:
    data = _load_yaml(_PROJECT_ROOT / "config" / "knowledge.registry.yaml")
    if isinstance(data, dict):
        k = data.get("knowledge", [])
        return [e for e in k if isinstance(e, dict)]
    return []


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def _responsibilities(text: str, domains: dict) -> list[str]:
    """
    A domain counts as 'present' only with a meaningful footprint — at least 2
    distinct keywords from that domain, OR a single keyword appearing >= 3 times.
    This avoids flagging every file that mentions "test" or "registry" once.
    """
    low = text.lower()
    hit = []
    for domain, kws in domains.items():
        distinct = sum(1 for kw in kws if kw.lower() in low)
        strongest = max((low.count(kw.lower()) for kw in kws), default=0)
        if distinct >= 2 or strongest >= 3:
            hit.append(domain)
    return sorted(hit)


def analyze(project_root: Path | None = None, config: dict | None = None) -> dict:
    """Run all detectors and compute the Architecture Score. Pure analysis."""
    root = project_root or _PROJECT_ROOT
    cfg = config or load_config()
    th = cfg["thresholds"]
    domains = cfg["responsibility_domains"]
    weights = cfg["score_weights"]

    import boot_profiler as bp
    all_files = bp.scan_files(root)
    dups = bp.scan_duplications(root)

    # Dedup the dist mirror: `agents/<x>` is a generated copy of `.claude/agents/<x>`.
    # Keep the runtime source, drop the mirror, so scoring isn't double-counted.
    claude_basenames = {Path(f["path"]).name for f in all_files
                        if f["path"].startswith(".claude/agents/")}
    files = [f for f in all_files
             if not (f["path"].startswith("agents/")
                     and Path(f["path"]).name in claude_basenames)]

    know = _knowledge_entries()
    know_paths = {str(e.get("path", "")).replace("\\", "/") for e in know}

    # Per-file responsibility + entropy
    per_file = []
    for r in files:
        try:
            text = (root / r["path"]).read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        resp = _responsibilities(text, domains)
        tok = r["estimated_tokens"]
        # entropy: normalized size (cap at high threshold) + responsibility spread
        size_norm = min(tok / max(th["doc_high_tokens"], 1), 2.0)
        entropy = round(size_norm * 1.0 + len(resp) * 0.5, 3)
        per_file.append({**r, "responsibilities": resp, "entropy": entropy})

    # 1/11 oversized + large
    oversized = [f for f in per_file if f["estimated_tokens"] >= th["doc_high_tokens"]]
    large = [f for f in per_file
             if th["doc_warn_tokens"] <= f["estimated_tokens"] < th["doc_high_tokens"]]

    # 2/3 duplicated knowledge + rules in many files
    duplicated = [d for d in dups if d["file_count"] >= th["duplication_min_files"]]
    rule_keywords = {"regla de oro", "hard rules", "release", "qa"}
    rules_spread = [d for d in dups if d["keyword"].lower() in rule_keywords and d["file_count"] > 1]

    # 4 mixed responsibilities + 5 decompose candidates
    mixed = [f for f in per_file if len(f["responsibilities"]) >= th["mixed_responsibility_min"]]
    decompose = [f for f in per_file
                 if f["estimated_tokens"] >= th["decompose_min_tokens"]
                 and len(f["responsibilities"]) >= th["mixed_responsibility_min"]]

    # 6 unused references: registry docs never mentioned by any scanned file
    all_text = ""
    for f in per_file:
        try:
            all_text += (root / f["path"]).read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass
    unused_refs = []
    for e in know:
        p = str(e.get("path", "")).replace("\\", "/")
        if e.get("load_policy") in ("lazy", "manual") and p.endswith(".md"):
            name = Path(p).name
            # referenced if its path or filename appears in some OTHER file
            mentions = all_text.count(p) + all_text.count(name)
            if mentions <= 1:  # only its own occurrence (or none)
                unused_refs.append({"id": e.get("id"), "path": p, "mentions": mentions})

    # 7 always-on knowledge
    always_on = [e for e in know if e.get("load_policy") == "always_on"]
    always_on_tokens = sum(f["estimated_tokens"] for f in per_file
                           if f["path"] in {str(e.get("path", "")).replace("\\", "/") for e in always_on})

    # 8 never-loaded: docs/ + config/ files on disk not in knowledge registry
    never_loaded = []
    for f in per_file:
        p = f["path"]
        if (p.startswith("docs/") or p.startswith("config/")) and p not in know_paths:
            never_loaded.append(p)

    # 9 boot dependency risks: paths referenced by always-on files that don't exist
    boot_risks = []
    for e in always_on:
        ap = root / str(e.get("path", ""))
        if not ap.exists():
            continue
        try:
            txt = ap.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in re.findall(r"`?(docs/[\w./-]+\.md|\.claude/agents/[\w./-]+\.md)`?", txt):
            if not (root / m).exists():
                boot_risks.append({"from": str(e.get("path")), "missing": m})

    # 10 obsolete docs: registry paths missing on disk + unreferenced loose docs
    obsolete = []
    for e in know:
        p = root / str(e.get("path", ""))
        if not p.exists():
            obsolete.append({"id": e.get("id"), "reason": "registry path missing on disk"})
    obsolete += [{"path": u["path"], "reason": "unreferenced doc (orphan)"} for u in unused_refs]

    # 11 entropy ranking (hotspots)
    hotspots = sorted(per_file, key=lambda f: f["entropy"], reverse=True)[:15]

    # --- Architecture Score --------------------------------------------------
    penalties = {
        "oversized_file": len(oversized) * weights["oversized_file"],
        "large_file": len(large) * weights["large_file"],
        "duplication_candidate": len(duplicated) * weights["duplication_candidate"],
        "mixed_responsibility": len(mixed) * weights["mixed_responsibility"],
        "decompose_candidate": len(decompose) * weights["decompose_candidate"],
        "unused_reference": len(unused_refs) * weights["unused_reference"],
        "boot_dependency_risk": len(boot_risks) * weights["boot_dependency_risk"],
        "obsolete_doc": len(obsolete) * weights["obsolete_doc"],
        "always_on_over_budget": (weights["always_on_over_budget"]
                                  if always_on_tokens > th["always_on_budget_tokens"] else 0),
    }
    total_penalty = sum(penalties.values())
    score = max(0, min(100, 100 - total_penalty))

    recommendations = _recommendations(oversized, decompose, duplicated, boot_risks,
                                       unused_refs, always_on_tokens, th)

    return {
        "architecture_score": score,
        "penalties": penalties,
        "total_penalty": total_penalty,
        "always_on_tokens": always_on_tokens,
        "always_on_budget": th["always_on_budget_tokens"],
        "detectors": {
            "oversized": [_slim(f) for f in oversized],
            "large": [_slim(f) for f in large],
            "duplicated_knowledge": duplicated,
            "rules_in_many_files": rules_spread,
            "mixed_responsibilities": [_slim(f) for f in mixed],
            "decompose_candidates": [_slim(f) for f in decompose],
            "unused_references": unused_refs,
            "always_on": [str(e.get("path")) for e in always_on],
            "never_loaded": never_loaded,
            "boot_dependency_risks": boot_risks,
            "obsolete_docs": obsolete,
        },
        "hotspots": [_slim(f) for f in hotspots],
        "recommendations": recommendations,
        "totals": {"files_scanned": len(per_file)},
    }


def _slim(f: dict) -> dict:
    return {
        "path": f["path"],
        "estimated_tokens": f["estimated_tokens"],
        "lines": f["lines"],
        "responsibilities": f.get("responsibilities", []),
        "entropy": f.get("entropy", 0),
    }


def _recommendations(oversized, decompose, duplicated, boot_risks, unused_refs,
                     always_on_tokens, th) -> list[dict]:
    recs = []
    if boot_risks:
        recs.append({"priority": "P0", "area": "boot",
                     "action": f"Fix {len(boot_risks)} broken always-on dependency link(s) — could break boot",
                     "evidence": boot_risks[:3]})
    if always_on_tokens > th["always_on_budget_tokens"]:
        recs.append({"priority": "P0", "area": "boot",
                     "action": f"always-on {always_on_tokens}t exceeds budget {th['always_on_budget_tokens']}t",
                     "evidence": always_on_tokens})
    if decompose:
        recs.append({"priority": "P1", "area": "decomposition",
                     "action": f"Decompose {len(decompose)} oversized+mixed file(s) (F31→F32 candidates)",
                     "evidence": [d["path"] for d in decompose]})
    if duplicated:
        top = sorted(duplicated, key=lambda d: d["file_count"], reverse=True)[:3]
        recs.append({"priority": "P1", "area": "duplication",
                     "action": "Consolidate doctrinal duplication into single-source references",
                     "evidence": [f"{d['keyword']} in {d['file_count']} files" for d in top]})
    if oversized:
        recs.append({"priority": "P2", "area": "size",
                     "action": f"Review {len(oversized)} oversized file(s) for splitting",
                     "evidence": [o["path"] for o in oversized]})
    if unused_refs:
        recs.append({"priority": "P3", "area": "cleanup",
                     "action": f"Verify {len(unused_refs)} unreferenced doc(s): wire into an index or archive",
                     "evidence": [u["path"] for u in unused_refs]})
    if not recs:
        recs.append({"priority": "P4", "area": "none", "action": "No high-signal architectural debt detected", "evidence": []})
    return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raw = sys.argv[1:]
    result = analyze()

    if "--json" in raw:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if "--score" in raw:
        print(result["architecture_score"])
        return
    if "--hotspots" in raw:
        print("Architectural entropy hotspots:")
        for f in result["hotspots"][:10]:
            print(f"  entropy={f['entropy']:<6} {f['estimated_tokens']:>7}t  "
                  f"{f['path']}  resp={f['responsibilities']}")
        return

    # default: --report
    d = result["detectors"]
    print("=" * 72)
    print("ATLAS Architecture Intelligence — F31")
    print("=" * 72)
    print(f"Architecture Score: {result['architecture_score']}/100  "
          f"(penalty {result['total_penalty']})")
    print(f"always-on: {result['always_on_tokens']}t / budget {result['always_on_budget']}t")
    print(f"files scanned: {result['totals']['files_scanned']}")
    print()
    print("Detector summary:")
    print(f"  oversized:             {len(d['oversized'])}")
    print(f"  large:                 {len(d['large'])}")
    print(f"  duplicated knowledge:  {len(d['duplicated_knowledge'])}")
    print(f"  rules in many files:   {len(d['rules_in_many_files'])}")
    print(f"  mixed responsibilities:{len(d['mixed_responsibilities'])}")
    print(f"  decompose candidates:  {len(d['decompose_candidates'])}")
    print(f"  unused references:     {len(d['unused_references'])}")
    print(f"  never loaded:          {len(d['never_loaded'])}")
    print(f"  boot dependency risks: {len(d['boot_dependency_risks'])}")
    print(f"  obsolete docs:         {len(d['obsolete_docs'])}")
    print()
    print("Top decompose candidates:")
    for f in d["decompose_candidates"][:5]:
        print(f"  {f['estimated_tokens']:>7}t  {f['path']}  resp={f['responsibilities']}")
    print()
    print("Prioritized recommendations:")
    for r in result["recommendations"]:
        print(f"  [{r['priority']}] {r['area']}: {r['action']}")


if __name__ == "__main__":
    _cli()
