#!/usr/bin/env python3
"""
ATLAS Autonomy Benchmark V1 — Scorer
=======================================

Reads config/autonomy_benchmark_v1.yaml (case definitions + recorded
verdicts) and computes the Autonomy Score. This tool does NOT re-run the
class_b (blind subagent probe) or class_c (session history) cases — those
require either spawning a fresh isolated subagent or citing a real,
already-occurred incident, neither of which is cheaply/deterministically
re-executable on every invocation. It DOES optionally re-verify a subset
of class_a deterministic checks live (--reverify), so the reproducible
portion of the benchmark is genuinely reproducible, not just recorded.

Scoring: PASS=1.0 PARTIAL=0.5 FAIL=0.0. NOT_TESTED and NOT_APPLICABLE are
EXCLUDED from both numerator and denominator (a case that wasn't run is
neither a success nor a failure). Cases with `duplicate_of` are excluded
entirely — they exist for narrative traceability, not to double-count
the same evidence.

CLI:
  python tools/autonomy_benchmark.py                  # score from recorded verdicts
  python tools/autonomy_benchmark.py --reverify        # also live-check a few class_a facts
  python tools/autonomy_benchmark.py --json            # machine-readable to stdout
  python tools/autonomy_benchmark.py --out FILE        # write JSON to FILE
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "autonomy_benchmark_v1.yaml"

VERDICT_POINTS = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0}
EXCLUDED_VERDICTS = {"NOT_TESTED", "NOT_APPLICABLE"}


def load_config() -> dict:
    import yaml
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


def score_dimension(dim_key: str, dim: dict) -> dict:
    """Score one dimension's cases. Returns raw score (0-100) + case detail."""
    cases = dim.get("cases", [])
    scored = []
    excluded = []
    total_points = 0.0
    total_possible = 0.0

    for case in cases:
        verdict = case.get("verdict")
        case_id = case.get("id", "?")

        if case.get("duplicate_of"):
            excluded.append({"id": case_id, "reason": f"duplicate_of {case['duplicate_of']}"})
            continue
        if verdict in EXCLUDED_VERDICTS:
            excluded.append({"id": case_id, "reason": verdict})
            continue
        if verdict not in VERDICT_POINTS:
            excluded.append({"id": case_id, "reason": f"no recorded verdict ({verdict!r})"})
            continue

        points = VERDICT_POINTS[verdict]
        total_points += points
        total_possible += 1.0
        scored.append({
            "id": case_id,
            "verdict": verdict,
            "points": points,
            "methodology": case.get("methodology", "?"),
            "confidence": case.get("confidence", "not_specified"),
        })

    raw_score = (total_points / total_possible * 100.0) if total_possible > 0 else 0.0

    return {
        "dimension": dim_key,
        "weight": dim.get("weight", 0),
        "cases_scored": len(scored),
        "cases_excluded": len(excluded),
        "points_obtenidos": total_points,
        "points_posibles": total_possible,
        "raw_score": raw_score,
        "case_detail": scored,
        "excluded_detail": excluded,
    }


def compute_autonomy_score(config: dict) -> dict:
    dimensions = config.get("dimensions", {})
    weights = config.get("weights", {})

    dim_results = {}
    total_weighted = 0.0
    total_weight = 0.0
    total_cases_scored = 0

    for dim_key, dim in dimensions.items():
        result = score_dimension(dim_key, dim)
        weight = weights.get(dim_key, result["weight"])
        weighted = result["raw_score"] * (weight / 100.0)
        result["weighted_score"] = weighted
        dim_results[dim_key] = result
        total_weighted += weighted
        total_weight += weight
        total_cases_scored += result["cases_scored"]

    # Confidence per §16 of the benchmark spec
    if total_cases_scored >= 40:
        confidence = "HIGH"
    elif total_cases_scored >= 25:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "autonomy_score": round(total_weighted, 1),
        "confidence": confidence,
        "total_cases_scored": total_cases_scored,
        "total_weight_check": total_weight,  # should be 100
        "dimensions": dim_results,
    }


def reverify_live_facts() -> dict:
    """
    Live re-check of the cheap, genuinely reproducible class_a facts:
    security hook fixtures + qa_strict envelope gate. Does not touch any
    real project. Returns a dict comparing live results to what the
    config recorded, for transparency (does not overwrite the config).
    """
    results = {}

    # Security fixture: hardcoded secret -> quality-gate.js should detect (warn)
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "src/config.js",
            "content": 'const apiKey = "sk_live_51H8x7ZKq9vN3mP2rTyUw4X6aB9cDeFgHiJkLmNoPqRs";',
        },
    })
    try:
        r = subprocess.run(
            ["node", str(PROJECT_ROOT / ".claude" / "hooks" / "quality-gate.js")],
            input=payload, capture_output=True, text=True, timeout=10,
        )
        results["SEC1_secret_detected_live"] = "hardcoded secret" in (r.stdout + r.stderr).lower() or "secret" in r.stdout.lower()
    except Exception as e:
        results["SEC1_secret_detected_live"] = f"error: {e}"

    # Security fixture: eval() -> should NOT be detected (confirms the gap still exists)
    payload2 = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": "src/utils.js", "content": "function run(x) { return eval(x); }"},
    })
    try:
        r2 = subprocess.run(
            ["node", str(PROJECT_ROOT / ".claude" / "hooks" / "quality-gate.js")],
            input=payload2, capture_output=True, text=True, timeout=10,
        )
        results["SEC3_eval_gap_confirmed_live"] = (r2.stdout.strip() == "" and r2.returncode == 0)
    except Exception as e:
        results["SEC3_eval_gap_confirmed_live"] = f"error: {e}"

    # QA5: fabricated PASS envelope should still pass qa_strict structurally
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        import os
        os.environ.setdefault("ATLAS_DISABLE_ENGRAM_MCP", "1")
        from atlas_dispatcher import ATLASDispatcher
        d = ATLASDispatcher(project_root=str(PROJECT_ROOT))
        fake = {"status": "PASS", "tarea": "x", "archivos": ["x.js"], "engram": "p/qa-1", "verificacion": "layout"}
        is_valid, errores = d.validate_return_envelope(fake, mode="qa_strict")
        results["QA5_fabricated_pass_gap_confirmed_live"] = bool(is_valid)
    except Exception as e:
        results["QA5_fabricated_pass_gap_confirmed_live"] = f"error: {e}"

    return results


def print_report(result: dict) -> None:
    print("=" * 70)
    print("ATLAS AUTONOMY BENCHMARK V1")
    print("=" * 70)
    print(f"\nAUTONOMY SCORE: {result['autonomy_score']}%")
    print(f"CONFIDENCE: {result['confidence']}")
    print(f"Cases scored: {result['total_cases_scored']}")
    print()
    print(f"{'Dimension':<38} {'Raw':>6} {'Weight':>7} {'Weighted':>9} {'Cases':>6}")
    print("-" * 70)
    for key, d in result["dimensions"].items():
        print(f"{key:<38} {d['raw_score']:>5.1f}% {d['weight']:>6}% {d['weighted_score']:>8.2f}% {d['cases_scored']:>6}")
    print("-" * 70)
    print(f"{'TOTAL':<38} {'':>6} {'':>7} {result['autonomy_score']:>8.2f}%")


def main():
    args = sys.argv[1:]
    config = load_config()
    result = compute_autonomy_score(config)

    if "--reverify" in args:
        result["live_reverification"] = reverify_live_facts()

    if "--json" in args:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)
        if "--reverify" in args:
            print("\nLive re-verification (class_a facts, run just now):")
            for k, v in result["live_reverification"].items():
                print(f"  {k}: {v}")

    if "--out" in args:
        idx = args.index("--out")
        out_path = Path(args[idx + 1])
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[written] {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
