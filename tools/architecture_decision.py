"""
ATLAS Architecture Decision Governor — F35
===========================================

READ-ONLY decision aid. Given a proposal (text or file), it classifies the change
per config/architecture.decision-policy.yaml and returns: state, risk, impact,
affected components, required tests, rollback, whether human approval is needed,
and a final recommendation.

Purpose: ATLAS evaluates proposals on evidence/risk instead of executing on
request. It changes NOTHING — it only advises.

CLI:
  python tools/architecture_decision.py --text "Add Engram Cloud sync"
  python tools/architecture_decision.py --proposal docs/SOME-PROPOSAL.md
  python tools/architecture_decision.py --text "..." --json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_POLICY = _PROJECT_ROOT / "config" / "architecture.decision-policy.yaml"

# Fail-open defaults mirroring the policy (used if YAML missing).
_DEFAULT_SIGNALS = {
    "new_dependency": ["dependency", "install", "pip install", "npm install", "package", "library", "sdk", "requirements"],
    "external_service": ["cloud", "external service", "remote", "saas", "api key", "token", "network call", "third-party", "upstream", "opencode"],
    "security_sensitive": ["secret", "credential", "auth", "permission", "hook bypass", "disable security"],
    "touches_runtime": ["dispatcher", "runtime logic", "atlas_dispatcher", "agent logic", "agent semantics", "hook code", "mcp server"],
    "increases_boot": ["always_on", "always-on", "boot token", "inflate context", "load at boot", "into claude.md", "system prompt"],
    "over_engineering": ["plugin architecture", "event bus", "framework", "generic abstraction", "provider abstraction", "new layer", "microservice"],
    "docs_only": ["doc", "documentation", "readme", "reference", "comment", "report", "clarify wording", "rename doc"],
    "knowledge_move": ["move to ref", "lazy ref", "decompose", "slim", "extract section", "knowledge registry", "resolve_knowledge"],
    "tests_only": ["test", "coverage", "suite", "qa check", "healthcheck check", "assertion"],
    "reversible": ["reversible", "revert", "rollback", "behind flag", "disabled by default"],
}

_DEFAULT_RULES = [
    {"id": "external-or-dependency", "when_any": ["new_dependency", "external_service"], "state": "NEEDS_HUMAN_APPROVAL",
     "reason": "Adds a dependency or external/cloud surface — boundary crossing, needs human sign-off."},
    {"id": "security", "when_any": ["security_sensitive"], "state": "NEEDS_HUMAN_APPROVAL",
     "reason": "Security-sensitive — never auto-accept; human approval required."},
    {"id": "touches-runtime", "when_any": ["touches_runtime"], "state": "NEEDS_EVIDENCE",
     "reason": "Touches dispatcher/runtime/agent semantics — requires audit + tests before deciding."},
    {"id": "increases-boot", "when_any": ["increases_boot"], "state": "DEFER",
     "reason": "Increases always-on/boot cost — defer unless measured net benefit."},
    {"id": "over-engineering", "when_any": ["over_engineering"], "state": "REJECT",
     "reason": "Over-engineering signal without a concrete current need — prefer not adding the layer."},
    {"id": "docs-or-tests-only", "when_any": ["docs_only", "knowledge_move", "tests_only"],
     "when_not": ["new_dependency", "external_service", "touches_runtime", "increases_boot"],
     "state": "ACCEPT_WITH_LIMITS",
     "reason": "Docs/tests/knowledge-move only, no runtime/dependency — safe within limits."},
    {"id": "default-cautious", "when_any": [], "state": "NEEDS_EVIDENCE",
     "reason": "No strong signal either way — gather evidence before acting."},
]


def load_policy(path: Path | None = None) -> dict:
    target = path or _POLICY
    pol = {"signals": _DEFAULT_SIGNALS, "rules": _DEFAULT_RULES}
    if not target.exists():
        return pol
    try:
        import yaml
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        if isinstance(data.get("signals"), dict):
            pol["signals"] = data["signals"]
        if isinstance(data.get("rules"), list) and data["rules"]:
            pol["rules"] = data["rules"]
    except Exception:
        pass
    return pol


def detect_signals(text: str, signals: dict) -> list[str]:
    low = text.lower()
    found = []
    for name, kws in signals.items():
        if any(kw.lower() in low for kw in kws):
            found.append(name)
    return found


_COMPONENT_HINTS = {
    "dispatcher": "tools/atlas_dispatcher.py (runtime)",
    "claude.md": "CLAUDE.md (always-on boot)",
    "orquestador": ".claude/agents/orquestador.md",
    "agent-protocol": ".claude/agents/agent-protocol.md",
    "hook": ".claude/hooks/",
    "registry": "config/*.registry.yaml",
    "ci": ".github/workflows/",
    "engram": "Engram MCP / memory",
    "mcp": "config/mcp.registry.yaml / MCP layer",
    "test": "_qa/ suites",
}


def _affected(text: str) -> list[str]:
    low = text.lower()
    return sorted({v for k, v in _COMPONENT_HINTS.items() if k in low})


def evaluate(proposal: str, policy: dict | None = None) -> dict:
    """Classify a proposal. Pure analysis — never writes, never network."""
    pol = policy or load_policy()
    signals = detect_signals(proposal, pol["signals"])
    sigset = set(signals)

    decision = None
    reason = ""
    rule_id = ""
    for rule in pol["rules"]:
        when_any = set(rule.get("when_any") or [])
        when_not = set(rule.get("when_not") or [])
        if when_not & sigset:
            continue
        if not when_any or (when_any & sigset):
            decision = rule["state"]
            reason = rule.get("reason", "")
            rule_id = rule.get("id", "")
            break
    if decision is None:
        decision = "NEEDS_EVIDENCE"
        reason = "No matching rule — default cautious."
        rule_id = "fallback"

    # Risk / impact heuristics (0-5)
    risk = 0
    if "new_dependency" in sigset or "external_service" in sigset:
        risk += 3
    if "security_sensitive" in sigset:
        risk += 3
    if "touches_runtime" in sigset:
        risk += 2
    if "increases_boot" in sigset:
        risk += 1
    if "over_engineering" in sigset:
        risk += 2
    if "reversible" in sigset:
        risk = max(0, risk - 1)
    risk = min(5, risk)

    impact = 0
    low = proposal.lower()
    for kw in ("reduce", "slim", "simplify", "fewer tokens", "faster", "secure", "stability", "coverage", "decompose"):
        if kw in low:
            impact += 1
    impact = min(5, impact)

    required_tests = []
    if "touches_runtime" in sigset:
        required_tests.append("dispatcher/runtime regression suite (run_all --release)")
    if "increases_boot" in sigset:
        required_tests.append("boot_profiler --scan (always-on budget)")
    if {"docs_only", "knowledge_move"} & sigset:
        required_tests.append("F10 drift + knowledge registry healthcheck")
    if "tests_only" in sigset:
        required_tests.append("the new/updated suite + quick")
    if not required_tests:
        required_tests.append("quick + healthcheck (baseline)")

    rollback = ("git revert of the change" if "reversible" in sigset or {"docs_only", "knowledge_move", "tests_only"} & sigset
                else "git revert + verify no runtime/state migration needed")

    human = decision == "NEEDS_HUMAN_APPROVAL" or risk >= 4

    return {
        "decision": decision,
        "rule": rule_id,
        "reason": reason,
        "risk": risk,
        "impact": impact,
        "signals": signals,
        "affected_components": _affected(proposal),
        "required_tests": required_tests,
        "rollback": rollback,
        "requires_human_approval": human,
        "recommendation": _recommend(decision, risk, impact),
    }


def _recommend(decision: str, risk: int, impact: int) -> str:
    base = {
        "ACCEPT": "Proceed.",
        "ACCEPT_WITH_LIMITS": "Proceed within limits (docs/tests/refs only); validate with quick + healthcheck.",
        "DEFER": "Do not do now; revisit when there is measured net benefit.",
        "REJECT": "Do not do; no net benefit or over-engineering.",
        "NEEDS_EVIDENCE": "Run an audit/measurement first; do not implement blind.",
        "NEEDS_HUMAN_APPROVAL": "Stop and ask the human; do not auto-execute.",
    }.get(decision, "Gather evidence.")
    return f"{base} (risk={risk}/5, impact={impact}/5)"


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

    text = None
    if "--text" in raw:
        i = raw.index("--text")
        if i + 1 < len(raw):
            text = raw[i + 1]
    elif "--proposal" in raw:
        i = raw.index("--proposal")
        if i + 1 < len(raw):
            p = Path(raw[i + 1])
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"Cannot read proposal file: {e}", file=sys.stderr)
                sys.exit(1)

    if not text:
        print("Usage: architecture_decision.py --text \"<proposal>\" | --proposal <file> [--json]",
              file=sys.stderr)
        sys.exit(1)

    result = evaluate(text)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 64)
    print("ATLAS Architecture Decision Governor")
    print("=" * 64)
    print(f"DECISION: {result['decision']}   (rule: {result['rule']})")
    print(f"risk: {result['risk']}/5   impact: {result['impact']}/5   "
          f"human approval: {result['requires_human_approval']}")
    print(f"reason: {result['reason']}")
    print(f"signals: {result['signals'] or '—'}")
    print(f"affected: {result['affected_components'] or '—'}")
    print(f"required tests: {result['required_tests']}")
    print(f"rollback: {result['rollback']}")
    print(f"\n>> {result['recommendation']}")


if __name__ == "__main__":
    _cli()
