#!/usr/bin/env python3
"""
ATLAS — Secrets Validator
=========================

Reads .env.local and validates token presence without printing values.

Usage:
    python tools/secrets_check.py
    python tools/secrets_check.py --json
    python tools/secrets_check.py --env path/to/.env.local

Exit codes:
    0  all REQUIRED tokens present
    1  one or more REQUIRED tokens missing
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Token catalogue
# ---------------------------------------------------------------------------

# Format: (env_var, category, description)
# category: REQUIRED | OPTIONAL | PENDING_TOKEN | DEFERRED_PAID
TOKENS = [
    ("GITHUB_TOKEN",        "PENDING_TOKEN",  "GitHub MCP — repos, issues, PRs, code search"),
    ("VERCEL_TOKEN",        "PENDING_TOKEN",  "Vercel MCP — deployments, preview URLs, logs"),
    ("GEMINI_API_KEY",      "OPTIONAL",       "Creative assets — image generation via Gemini"),
    ("HF_TOKEN",            "OPTIONAL",       "Creative assets — HuggingFace image generation"),
    ("REPLICATE_API_TOKEN", "OPTIONAL",       "Creative assets — video generation via Replicate"),
    ("NOTION_TOKEN",        "OPTIONAL",       "Notion MCP override — usually configured via plugin"),
    ("MAGIC_21ST_KEY",      "DEFERRED_PAID",  "21st.dev Magic MCP — AI UI components (paid)"),
]

# Tokens that must be present for the system to be considered "ready"
REQUIRED_TOKENS: set[str] = set()  # currently no token is strictly REQUIRED for basic ATLAS

# Capability → token mapping (for documentation)
CAPABILITY_TOKENS = {
    "repository":    "GITHUB_TOKEN",
    "deployment":    "VERCEL_TOKEN",
    "design":        "MAGIC_21ST_KEY",
}

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file and return variable dict. Does not override os.environ."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                env[k] = v
    return env


def check_tokens(env: dict[str, str]) -> list[dict]:
    """Check each token and return results (never including the actual value)."""
    results = []
    for var, category, description in TOKENS:
        value = env.get(var) or os.environ.get(var, "")
        present = bool(value and value.strip())
        results.append({
            "var": var,
            "category": category,
            "description": description,
            "present": present,
            "status": _status(category, present),
        })
    return results


def _status(category: str, present: bool) -> str:
    if present:
        return "SET"
    if category == "REQUIRED":
        return "MISSING"
    if category == "PENDING_TOKEN":
        return "PENDING_TOKEN"
    if category == "DEFERRED_PAID":
        return "DEFERRED_PAID"
    return "NOT_SET"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"

def _c(color: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


STATUS_COLOR = {
    "SET":           GREEN,
    "MISSING":       RED,
    "PENDING_TOKEN": YELLOW,
    "DEFERRED_PAID": CYAN,
    "NOT_SET":       YELLOW,
}


def print_results(results: list[dict], env_path: Path) -> None:
    print(f"\nATLAS Secrets Check — {env_path}")
    print("=" * 60)

    by_category: dict[str, list] = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r)

    order = ["REQUIRED", "PENDING_TOKEN", "OPTIONAL", "DEFERRED_PAID"]
    for cat in order:
        items = by_category.get(cat, [])
        if not items:
            continue
        print(f"\n  {cat}:")
        for r in items:
            color = STATUS_COLOR.get(r["status"], RESET)
            status_str = _c(color, f"[{r['status']}]")
            print(f"    {status_str:<25} {r['var']}")
            print(f"                          {r['description']}")

    # Summary
    missing_required = [r for r in results if r["status"] == "MISSING"]
    pending = [r for r in results if r["status"] == "PENDING_TOKEN"]
    deferred = [r for r in results if r["status"] == "DEFERRED_PAID"]
    ready = [r for r in results if r["status"] == "SET"]

    print(f"\n{'='*60}")
    print(f"  Configured: {len(ready)}/{len(results)}")
    if missing_required:
        print(f"  {_c(RED, 'MISSING REQUIRED:')} {', '.join(r['var'] for r in missing_required)}")
    if pending:
        print(f"  {_c(YELLOW, 'PENDING_TOKEN:')}  {', '.join(r['var'] for r in pending)} — add to .env.local")
    if deferred:
        print(f"  {_c(CYAN, 'DEFERRED_PAID:')}  {', '.join(r['var'] for r in deferred)} — optional paid services")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="ATLAS secrets validator")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Machine-readable JSON output")
    parser.add_argument("--env", default=None,
                        help="Path to .env file (default: .env.local in project root)")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    env_path = Path(args.env) if args.env else project_root / ".env.local"

    env = load_env_file(env_path)
    results = check_tokens(env)

    missing_required = [r for r in results if r["status"] == "MISSING"]

    if args.json_output:
        output = {
            "env_file": str(env_path),
            "env_file_exists": env_path.exists(),
            "tokens": [
                {k: v for k, v in r.items()}
                for r in results
            ],
            "missing_required": [r["var"] for r in missing_required],
            "ok": len(missing_required) == 0,
        }
        print(json.dumps(output, indent=2))
    else:
        print_results(results, env_path)

    return 1 if missing_required else 0


if __name__ == "__main__":
    sys.exit(main())
