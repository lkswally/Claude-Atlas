"""
ATLAS Knowledge Resolver — F33
===============================

First formal `resolve_knowledge()`: given an intention/capability/query, select
the relevant knowledge refs from config/knowledge.registry.yaml. METADATA ONLY —
returns path/reason/estimated_tokens/load_policy, never the file content. The
caller decides whether to actually read a ref.

This generalizes the index→resolver→load pattern (already used informally) into a
declarative, testable resolver alongside the MCP capability router (F16). It does
NOT change runtime: it's a lookup helper over the registry.

CLI:
  python tools/knowledge_resolver.py --list
  python tools/knowledge_resolver.py --resolve <query>
  python tools/knowledge_resolver.py --json <query>

Matching (case-insensitive), scored by signal strength:
  id exact / id substring · category · trigger · tags · path/notes substring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_REGISTRY = _PROJECT_ROOT / "config" / "knowledge.registry.yaml"


def load_registry(path: Path | None = None) -> list[dict]:
    """Load knowledge entries. Fail-open → [] if missing/invalid/no PyYAML."""
    target = path or _REGISTRY
    if not target.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    entries = data.get("knowledge", []) if isinstance(data, dict) else []
    return [e for e in entries if isinstance(e, dict)]


def _meta(entry: dict, reason: str, score: int) -> dict:
    """Project an entry to metadata only (no content)."""
    return {
        "id": entry.get("id"),
        "path": str(entry.get("path", "")),
        "category": entry.get("category"),
        "load_policy": entry.get("load_policy"),
        "estimated_tokens": entry.get("estimated_tokens", 0),
        "trigger": entry.get("trigger"),
        "tags": entry.get("tags", []),
        "reason": reason,
        "score": score,
    }


def resolve_knowledge(query: str, registry: list[dict] | None = None, limit: int = 8) -> list[dict]:
    """
    Resolve a query to ranked knowledge refs (metadata only). Higher score = better.
    Never raises; unknown query → []. Does NOT read file content.
    """
    entries = registry if registry is not None else load_registry()
    if not query:
        return []
    q = query.strip().lower()
    hits: list[dict] = []

    for e in entries:
        eid = str(e.get("id", "")).lower()
        cat = str(e.get("category", "")).lower()
        trig = str(e.get("trigger", "")).lower()
        tags = [str(t).lower() for t in (e.get("tags") or [])]
        path = str(e.get("path", "")).lower()
        notes = str(e.get("notes", "")).lower()

        score = 0
        reasons = []
        if q == eid:
            score += 100; reasons.append("id exact")
        elif q in eid:
            score += 50; reasons.append("id match")
        if q == cat:
            score += 40; reasons.append("category exact")
        elif q in cat:
            score += 20; reasons.append("category match")
        if q in trig:
            score += 30; reasons.append("trigger match")
        if q in tags:
            score += 35; reasons.append("tag exact")
        elif any(q in t for t in tags):
            score += 18; reasons.append("tag match")
        if q in Path(path).name:
            score += 15; reasons.append("path match")
        if q in notes:
            score += 8; reasons.append("notes match")

        if score > 0:
            hits.append(_meta(e, " + ".join(reasons), score))

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raw = sys.argv[1:]
    as_json = "--json" in raw

    if "--list" in raw:
        entries = load_registry()
        if as_json:
            print(json.dumps([_meta(e, "list", 0) for e in entries], ensure_ascii=False, indent=2))
            return
        print(f"Knowledge registry: {len(entries)} entries")
        for e in entries:
            print(f"  {str(e.get('load_policy','?')):<10} {e.get('estimated_tokens',0):>6}t  "
                  f"{e.get('id'):<32} {e.get('path')}")
        return

    # --resolve <query>  or  --json <query>
    query = None
    for flag in ("--resolve", "--json"):
        if flag in raw:
            i = raw.index(flag)
            if i + 1 < len(raw) and not raw[i + 1].startswith("--"):
                query = raw[i + 1]
                break
    # also accept a bare positional query
    if query is None:
        pos = [a for a in raw if not a.startswith("--")]
        query = pos[0] if pos else None

    if not query:
        print("Usage: knowledge_resolver.py --list | --resolve <query> | --json <query>",
              file=sys.stderr)
        sys.exit(1)

    results = resolve_knowledge(query)
    if as_json:
        print(json.dumps({"query": query, "results": results}, ensure_ascii=False, indent=2))
        return
    print(f"resolve_knowledge({query!r}) → {len(results)} ref(s):")
    for r in results:
        print(f"  [{r['score']:>3}] {r['load_policy']:<10} {r['estimated_tokens']:>6}t  "
              f"{r['path']}  ({r['reason']})")
    if not results:
        print("  (no match — unknown query, nothing loaded)")


if __name__ == "__main__":
    _cli()
