"""
ATLAS Claim Linter — F36
=========================

READ-ONLY documentation truthfulness gate. Scans Markdown for risky claims —
absolute wording and unverified invariants (e.g. "no raw MCP", "all tests pass",
"fully secure") — classifies severity, and maps each HIGH/CRITICAL claim to a
suggested verifier. WARN-only: it flags doc risk, it does not judge style and does
not block anything.

Why: pre-F27, README/CONTRIBUTING claimed "no agent references raw MCP prefixes" —
false, yet CI/healthcheck were green because nothing validated claims against
evidence. The Architecture Decision Governor (F35) recommended this linter.

CLI:
  python tools/claim_linter.py --scan              # default doc set, human summary
  python tools/claim_linter.py --summary           # counts by severity
  python tools/claim_linter.py --json              # machine-readable
  python tools/claim_linter.py --file README.md    # one file
  python tools/claim_linter.py --all               # include historical reports
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_REGISTRY = _PROJECT_ROOT / "config" / "claim-linter.registry.yaml"

_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

_DEFAULT_SCAN = [
    "README.md", "CONTRIBUTING.md", "GLOSSARY.md", "CLAUDE.md",
    "docs/atlas-boot-reference.md", "docs/atlas-release-reference.md",
    "docs/atlas-engram-reference.md", "docs/atlas-build-reference.md",
    "docs/atlas-operational-capabilities.md", "docs/atlas-knowledge-resolver.md",
]


def load_registry(path: Path | None = None) -> dict:
    target = path or _REGISTRY
    if not target.exists():
        return {"claims": [], "scan_default": _DEFAULT_SCAN, "verifiers": {}, "whitelist_context": []}
    try:
        import yaml
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"claims": [], "scan_default": _DEFAULT_SCAN, "verifiers": {}, "whitelist_context": []}
    data.setdefault("claims", [])
    data.setdefault("scan_default", _DEFAULT_SCAN)
    data.setdefault("verifiers", {})
    data.setdefault("whitelist_context", [])
    return data


def _auto_probe(claim_id: str) -> bool | None:
    """
    Light, offline auto-probe of evidence availability for a few claims.
    Returns True/False/None (unknown). Never raises, never writes.
    """
    try:
        if claim_id == "no-raw-mcp":
            # evidence is "available" because we CAN grep; report whether raw prefixes exist
            agents = _PROJECT_ROOT / ".claude" / "agents"
            for md in agents.glob("*.md"):
                if "mcp__" in md.read_text(encoding="utf-8", errors="replace"):
                    return True  # evidence exists (and the claim would be false)
            return True
    except Exception:
        return None
    return None


def lint_text(text: str, registry: dict, source: str = "<text>") -> list[dict]:
    """Return findings for a block of text. Pure analysis."""
    claims = registry.get("claims", [])
    whitelist = [w.lower() for w in registry.get("whitelist_context", [])]
    findings: list[dict] = []

    for lineno, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if not low.strip() or low.lstrip().startswith(("#", ">", "|", "-", "*")) and len(low) < 4:
            pass  # still scan; markdown structure lines can carry claims
        line_whitelisted = any(w in low for w in whitelist)
        for c in claims:
            for pat in c.get("patterns", []):
                if pat.lower() in low:
                    sev = c.get("severity", "LOW")
                    if line_whitelisted and sev != "CRITICAL":
                        sev = "LOW"
                    findings.append({
                        "id": c.get("id"),
                        "category": c.get("category"),
                        "severity": sev,
                        "match": pat,
                        "file": source,
                        "line": lineno,
                        "text": line.strip()[:160],
                        "evidence_verifier": (registry.get("verifiers", {}).get(c.get("evidence"))
                                              if c.get("evidence") else None),
                        "evidence_available": _auto_probe(c.get("id")) if sev in ("HIGH", "CRITICAL") else None,
                        "risk_reason": c.get("risk_reason", ""),
                    })
                    break  # one match per claim per line
    return findings


def lint_file(path: Path, registry: dict) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    try:
        rel = str(path.relative_to(_PROJECT_ROOT))
    except (ValueError, Exception):
        rel = str(path)
    return lint_text(text, registry, source=rel)


def scan(registry: dict | None = None, include_all: bool = False) -> dict:
    """Scan the default doc set (or all docs). Returns findings + summary."""
    reg = registry or load_registry()
    files: list[Path] = []
    for rel in reg.get("scan_default", _DEFAULT_SCAN):
        p = _PROJECT_ROOT / rel
        if p.exists():
            files.append(p)
    if include_all:
        for p in sorted((_PROJECT_ROOT / "docs").glob("*.md")):
            if p not in files:
                files.append(p)

    all_findings: list[dict] = []
    for f in files:
        all_findings.extend(lint_file(f, reg))

    by_sev = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for fd in all_findings:
        by_sev[fd["severity"]] = by_sev.get(fd["severity"], 0) + 1
    critical_no_evidence = [f for f in all_findings
                            if f["severity"] == "CRITICAL" and not f.get("evidence_verifier")]

    return {
        "files_scanned": len(files),
        "total_findings": len(all_findings),
        "by_severity": by_sev,
        "critical_without_evidence": len(critical_no_evidence),
        "findings": all_findings,
    }


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
    include_all = "--all" in raw
    reg = load_registry()

    if "--file" in raw:
        i = raw.index("--file")
        if i + 1 < len(raw):
            findings = lint_file(_PROJECT_ROOT / raw[i + 1], reg)
            result = {"file": raw[i + 1], "total_findings": len(findings), "findings": findings}
            if as_json:
                print(json.dumps(result, ensure_ascii=False, indent=2)); return
            print(f"{raw[i+1]}: {len(findings)} finding(s)")
            for fd in sorted(findings, key=lambda x: -_SEVERITY_ORDER[x["severity"]]):
                print(f"  [{fd['severity']:<8}] L{fd['line']}: '{fd['match']}'  -> {fd['risk_reason']}")
            return

    result = scan(reg, include_all=include_all)

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2)); return

    if "--summary" in raw:
        print(f"Claim Linter: {result['files_scanned']} files, {result['total_findings']} findings")
        print(f"  by severity: {result['by_severity']}")
        print(f"  CRITICAL without evidence: {result['critical_without_evidence']}")
        return

    # default --scan
    print("=" * 68)
    print("ATLAS Claim Linter (WARN-only)")
    print("=" * 68)
    print(f"files: {result['files_scanned']}  findings: {result['total_findings']}  "
          f"by_severity: {result['by_severity']}")
    print()
    for fd in sorted(result["findings"], key=lambda x: (-_SEVERITY_ORDER[x["severity"]], x["file"])):
        if fd["severity"] in ("HIGH", "CRITICAL"):
            ev = fd.get("evidence_verifier") or "—"
            print(f"  [{fd['severity']:<8}] {fd['file']}:{fd['line']}  '{fd['match']}'")
            print(f"            verifier: {ev}")


if __name__ == "__main__":
    _cli()
