#!/usr/bin/env python3
"""
ATLAS — Unified QA Runner
=========================

Discovers and runs all _qa/bloque-F*.py suites.

Usage:
    python tools/run_all.py                     # same as --quick
    python tools/run_all.py --quick             # local, no network, no tokens
    python tools/run_all.py --full              # quick + live binary tests
    python tools/run_all.py --full --no-network # full but skip network-dependent
    python tools/run_all.py --release           # everything before a release tag
    python tools/run_all.py --json              # machine-readable JSON output
    python tools/run_all.py --list              # list suites without running

Exit codes:
    0  all selected suites passed
    1  one or more suites failed
    2  no suites found
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Suite classification
# ---------------------------------------------------------------------------

# Suites that need a live Engram binary or DB — skip in --quick
LIVE_BINARY_SUITES = {
    "bloque-F13-engram-active",  # needs engram.exe + DB
}

# Suites that need network/external APIs — skip with --no-network
NETWORK_SUITES: set[str] = set()  # currently none hit real network in test mode

# F23: .claude/settings.json race condition resolved.
# Healthcheck now WARNs (not FAILs) when settings.json is absent in non-strict mode.
# All suites that previously depended on a stable settings.json now tolerate
# the Windows/Claude Desktop race condition and run without special handling.

# Suites that are "live session only" (validate MCP tools registered in Claude)
# These can't be run standalone — they document their own skip
LIVE_SESSION_ONLY: set[str] = set()

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
QA_DIR = PROJECT_ROOT / "_qa"


def discover_suites() -> list[Path]:
    """Return all bloque-F*.py suite files sorted by name."""
    suites = sorted(QA_DIR.glob("bloque-F*.py"))
    return suites


def suite_stem(path: Path) -> str:
    return path.stem


def should_run(stem: str, args: argparse.Namespace) -> bool:
    """Decide whether to run a suite given the current mode flags."""
    if stem in LIVE_BINARY_SUITES and not args.full:
        return False
    if stem in NETWORK_SUITES and args.no_network:
        return False
    return True


def run_suite(path: Path, timeout: int = 60) -> dict:
    """
    Run a single suite and return a result dict.
    Relies on exit code: 0 = PASS, non-zero = FAIL.
    """
    stem = path.stem
    start = time.monotonic()

    # Ensure UTF-8 output so unicode characters in suite output don't cause
    # encoding errors on Windows (charmap codec issue)
    suite_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=suite_env,
        )
        elapsed = time.monotonic() - start
        passed = result.returncode == 0

        # Secondary check: look for explicit FAIL in output
        combined = result.stdout + result.stderr
        if "FAIL" in combined.upper() and "0 FAIL" not in combined and "0 failures" not in combined:
            passed = False

        return {
            "suite": stem,
            "passed": passed,
            "returncode": result.returncode,
            "elapsed": round(elapsed, 2),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return {
            "suite": stem,
            "passed": False,
            "returncode": -1,
            "elapsed": round(elapsed, 2),
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        return {
            "suite": stem,
            "passed": False,
            "returncode": -2,
            "elapsed": round(elapsed, 2),
            "stdout": "",
            "stderr": str(e),
        }


# ---------------------------------------------------------------------------
# Healthcheck integration
# ---------------------------------------------------------------------------

def run_healthcheck(strict: bool = False) -> dict:
    hc_path = PROJECT_ROOT / "tools" / "atlas_healthcheck.py"
    start = time.monotonic()
    cmd = [sys.executable, str(hc_path)]
    if strict:
        cmd.append("--strict")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(PROJECT_ROOT),
    )
    elapsed = time.monotonic() - start
    passed = result.returncode == 0 and "FAIL=0" in result.stdout

    # extract summary line
    summary = ""
    for line in result.stdout.splitlines():
        if "RESULTADO" in line or "STATUS" in line:
            summary = line.strip()
            break

    return {
        "suite": "healthcheck",
        "passed": passed,
        "returncode": result.returncode,
        "elapsed": round(elapsed, 2),
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"

def _c(color: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{RESET}"


def print_result(r: dict) -> None:
    icon = _c(GREEN, "PASS") if r["passed"] else _c(RED, "FAIL")
    elapsed = f"{r['elapsed']:5.2f}s"
    print(f"  [{icon}] {elapsed}  {r['suite']}")
    if not r["passed"]:
        # Print last 3 lines of output to help diagnose
        stderr = r.get("stderr", "").strip()
        stdout = r.get("stdout", "").strip()
        detail = stderr or stdout
        if detail:
            for line in detail.splitlines()[-3:]:
                print(f"           {_c(YELLOW, line)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS unified QA runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--quick", action="store_true", default=True,
                        help="Local suites only, no live binaries (default)")
    parser.add_argument("--full", action="store_true",
                        help="Include suites that need live binaries")
    parser.add_argument("--release", action="store_true",
                        help="Full suite + healthcheck — required before tagging")
    parser.add_argument("--no-network", action="store_true",
                        help="Skip suites that make network calls")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output machine-readable JSON")
    parser.add_argument("--list", action="store_true",
                        help="List suites without running")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-suite timeout in seconds (default: 60)")
    args = parser.parse_args()

    # --release implies --full
    if args.release:
        args.full = True

    suites = discover_suites()
    if not suites:
        print("ERROR: no suites found in _qa/", file=sys.stderr)
        return 2

    selected = [s for s in suites if should_run(suite_stem(s), args)]
    skipped = [s for s in suites if not should_run(suite_stem(s), args)]

    if args.list:
        print(f"Selected ({len(selected)}):")
        for s in selected:
            print(f"  {s.stem}")
        if skipped:
            print(f"\nSkipped ({len(skipped)}):")
            for s in skipped:
                print(f"  {s.stem}")
        return 0

    # --- run ---
    results = []
    hc_result = None

    if not args.json_output:
        mode = "release" if args.release else ("full" if args.full else "quick")
        print(f"\n{_c(BOLD, 'ATLAS QA Runner')} — mode: {mode}")
        print(f"Running {len(selected)} suites ({len(skipped)} skipped)\n")

    # Healthcheck first in release mode (--strict: settings.json FAIL not WARN)
    if args.release and not args.json_output:
        print("  [....] healthcheck", end="\r", flush=True)
        hc_result = run_healthcheck(strict=True)
        print_result(hc_result)

    for suite_path in selected:
        stem = suite_stem(suite_path)
        if not args.json_output:
            print(f"  [....] {stem}", end="\r", flush=True)
        r = run_suite(suite_path, timeout=args.timeout)
        results.append(r)
        if not args.json_output:
            print_result(r)

    # --- summary ---
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    total_time = sum(r["elapsed"] for r in results)

    if hc_result:
        if not hc_result["passed"]:
            failed += 1
        total += 1

    if args.json_output:
        output = {
            "mode": "release" if args.release else ("full" if args.full else "quick"),
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": len(skipped),
            "elapsed": round(total_time, 2),
            "healthcheck": hc_result,
            "suites": results,
        }
        print(json.dumps(output, indent=2))
    else:
        status_color = GREEN if failed == 0 else RED
        print(f"\n{'='*60}")
        print(f"RESULTADO : {_c(GREEN, f'PASS={passed}')}  {_c(RED, f'FAIL={failed}') if failed else _c(GREEN, 'FAIL=0')}  / {total} suites")
        print(f"TIME      : {total_time:.2f}s total")
        print(f"STATUS    : {_c(status_color, 'ALL PASS' if failed == 0 else f'{failed} FAILED')}")
        if skipped:
            print(f"SKIPPED   : {len(skipped)} suites (use --full to include)")
        print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
