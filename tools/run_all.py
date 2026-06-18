#!/usr/bin/env python3
"""
ATLAS — Unified QA Runner
=========================

Single command to validate everything. Covers:
  - Healthcheck (runtime, hooks, MCP, capabilities, skills, projects)
  - All _qa/bloque-F*.py suites (security, secrets, dispatcher, smoke tests, etc.)
  - Release report generation (release-report.md)
  - Structured JSON output for CI consumption

Usage:
    python tools/run_all.py                     # same as --quick
    python tools/run_all.py --quick             # local suites, no live binaries (default)
    python tools/run_all.py --full              # quick + live binary tests
    python tools/run_all.py --release           # full validation required before tagging
    python tools/run_all.py --json              # machine-readable JSON to stdout
    python tools/run_all.py --out run_all.json  # save JSON to file
    python tools/run_all.py --list              # list suites without running
    python tools/run_all.py --timeout 120       # per-suite timeout override

Exit codes:
    0  all selected suites passed
    1  one or more suites failed
    2  no suites found
"""

import argparse
import datetime
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
# All suites tolerate the Windows/Claude Desktop race condition.

# Per-suite timeout overrides (seconds).
# Use when a suite legitimately takes longer than the default.
SUITE_TIMEOUTS: dict[str, int] = {
    "bloque-F23-runtime-settings-separation": 300,  # renames settings.json multiple times
    "bloque-F11-skills-registry-runtime": 180,       # imports dispatcher which is slow to start
    "bloque-F15-context7": 120,                      # context7 MCP startup takes up to 90s
    "bloque-F15-playwright": 120,                    # playwright MCP startup takes time
    "bloque-F15-github": 120,                        # github MCP startup takes time
    "bloque-F15-notion": 120,                        # notion MCP startup takes time
    "bloque-F17-agent-capability-migration": 120,   # imports dispatcher — slow cold start
    "bloque-F18-capability-metrics": 120,            # imports dispatcher — slow cold start
    "bloque-F19-capability-policy": 120,             # imports dispatcher — slow cold start
    "bloque-F20-capability-contracts": 120,          # imports dispatcher — slow cold start
    "bloque-F13-engram": 90,                         # engram MCP startup + DB check
    "bloque-F20-security-hooks": 120,               # spawns node processes for hook tests
    "bloque-F22-run-all": 600,                       # runs run_all.py --json internally multiple times
}

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
QA_DIR = PROJECT_ROOT / "_qa"


def discover_suites() -> list[Path]:
    """Return all bloque-F*.py suite files sorted by name."""
    return sorted(QA_DIR.glob("bloque-F*.py"))


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

    suite_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=suite_env,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.monotonic() - start
        passed = result.returncode == 0

        # Secondary check: if returncode=0 but suite output contains actual failure markers,
        # mark as failed. Be specific to avoid false positives on "FAIL: 0" or "FAIL=0".
        if passed:
            combined = result.stdout + result.stderr
            has_failure_marker = (
                "[FAIL]" in combined          # ATLAS suite marker
                or "RESULTADO: FAIL" in combined  # ATLAS summary
                or "FAILED (failures=" in combined  # unittest
                or "FAILED (errors=" in combined    # unittest
            )
            if has_failure_marker:
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
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(PROJECT_ROOT),
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return {
            "suite": "healthcheck",
            "passed": False,
            "returncode": -1,
            "elapsed": round(elapsed, 2),
            "stdout": "",
            "stderr": "TIMEOUT after 45s",
            "summary": "TIMEOUT",
        }

    elapsed = time.monotonic() - start
    passed = result.returncode == 0 and "FAIL=0" in result.stdout

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
# Git metadata
# ---------------------------------------------------------------------------

def get_git_metadata() -> dict:
    def git(*args) -> str:
        try:
            r = subprocess.run(
                ["git"] + list(args),
                capture_output=True, text=True, timeout=5,
                cwd=str(PROJECT_ROOT), encoding="utf-8", errors="replace",
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    commit = git("rev-parse", "HEAD")
    short = git("rev-parse", "--short", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    tag = git("describe", "--tags", "--exact-match", "HEAD")
    if not tag:
        tag = git("describe", "--tags", "--abbrev=0")
    dirty = git("status", "--porcelain") != ""

    return {
        "commit": commit,
        "short": short,
        "branch": branch,
        "tag": tag or "untagged",
        "dirty": dirty,
    }


# ---------------------------------------------------------------------------
# Release report generator
# ---------------------------------------------------------------------------

def _suite_category(stem: str) -> str:
    cats = {
        "bloque-F4": "hooks", "bloque-F5": "hooks", "bloque-F6": "hooks",
        "bloque-F7": "healthcheck", "bloque-F8": "engram",
        "bloque-F10": "runtime", "bloque-F11": "envelope",
        "bloque-F13": "engram", "bloque-F14": "mcp",
        "bloque-F15": "mcp", "bloque-F16": "capabilities",
        "bloque-F17": "capabilities", "bloque-F18": "capabilities",
        "bloque-F19": "capabilities", "bloque-F20": "security",
        "bloque-F21": "skills", "bloque-F22": "runtime",
        "bloque-F23": "runtime",
    }
    for prefix, cat in cats.items():
        if stem.startswith(prefix):
            return cat
    return "other"


def generate_release_report(
    output: dict,
    hc_result: dict | None,
    run_start: float,
    run_end: float,
    out_path: Path,
) -> None:
    git = output.get("git", {})
    now = datetime.datetime.now(datetime.timezone.utc)
    duration = run_end - run_start
    suites = output.get("suites", [])
    failed_suites = [s for s in suites if not s["passed"]]
    passed_suites = [s for s in suites if s["passed"]]

    # count individual tests from RESULTADO lines
    total_tests = 0
    for s in suites:
        combined = s.get("stdout", "") + s.get("stderr", "")
        for line in combined.splitlines():
            if "RESULTADO:" in line or "RESULTADO :" in line:
                import re
                m = re.search(r"(\d+)/\d+\s+PASS", line)
                if m:
                    total_tests += int(m.group(1).split("/")[0].strip()) if "/" not in m.group(1) else 0
                m2 = re.search(r"(\d+)/(\d+)", line)
                if m2:
                    total_tests += int(m2.group(2))
                    break

    # Build category summary
    by_cat: dict[str, dict] = {}
    for s in suites:
        cat = _suite_category(s["suite"])
        if cat not in by_cat:
            by_cat[cat] = {"pass": 0, "fail": 0}
        by_cat[cat]["pass" if s["passed"] else "fail"] += 1

    hc_pass = hc_result["passed"] if hc_result else None
    hc_summary = hc_result.get("summary", "") if hc_result else "not run"

    overall_failed = output.get("failed", 0)
    overall_pass = output.get("passed", 0)
    overall_total = output.get("total", 0)
    if overall_failed == 0:
        status_str = "PASS"
    else:
        status_str = "FAIL"

    known_risks = [
        "`.claude/settings.json` is managed by Claude Desktop on Windows — absent during test runs (WARN, not FAIL by design, F23)",
        "Dispatcher check times out on first invocation — cold-start penalty, documented WARN",
        "`.pipeline/` write test fails if another process holds a file lock (transient WinError 32)",
    ]

    lines = [
        f"# ATLAS Release Report",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Version | v0.24.0-rc1 |",
        f"| Git commit | `{git.get('commit', 'unknown')[:12]}` |",
        f"| Git tag | `{git.get('tag', 'untagged')}` |",
        f"| Branch | `{git.get('branch', 'unknown')}` |",
        f"| Dirty tree | {'yes ⚠️' if git.get('dirty') else 'no ✅'} |",
        f"| Date | {now.strftime('%Y-%m-%d %H:%M:%S UTC')} |",
        f"| Duration | {duration:.1f}s |",
        f"| Mode | {output.get('mode', 'release')} |",
        f"| Suites run | {overall_total} |",
        f"| Individual tests (approx) | {total_tests} |",
        f"| **PASS** | {overall_pass} |",
        f"| **FAIL** | {overall_failed} |",
        f"| Overall | **{status_str}** |",
        f"",
        f"## Healthcheck",
        f"",
    ]

    if hc_result:
        hc_icon = "✅" if hc_pass else "❌"
        lines += [
            f"Status: {hc_icon} {'PASS' if hc_pass else 'FAIL'}",
            f"",
            f"```",
            hc_summary,
            f"```",
            f"",
        ]
    else:
        lines += ["Status: ⚠️ not run in this mode", ""]

    lines += [
        f"## Runtime",
        f"",
        f"| Check | Status |",
        f"|-------|--------|",
    ]
    runtime_checks = {
        "hooks": "F4/F5/F6",
        "healthcheck": "F7",
        "engram": "F8/F13",
        "mcp": "F14/F15",
        "capabilities": "F16/F17/F18/F19",
        "security": "F20",
        "skills": "F21",
        "runtime": "F22/F23",
        "envelope": "F11",
    }
    for cat, suites_ref in runtime_checks.items():
        info = by_cat.get(cat, None)
        if info is None:
            icon = "—"
            detail = "not run"
        elif info["fail"] == 0:
            icon = "✅"
            detail = f"{info['pass']} suites PASS"
        else:
            icon = "❌"
            detail = f"{info['fail']} FAIL / {info['pass']} PASS"
        lines.append(f"| {cat} ({suites_ref}) | {icon} {detail} |")

    lines += [
        f"",
        f"## Suites Detail",
        f"",
        f"| Suite | Status | Time |",
        f"|-------|--------|------|",
    ]
    for s in suites:
        icon = "✅" if s["passed"] else "❌"
        lines.append(f"| {s['suite']} | {icon} | {s['elapsed']}s |")

    if failed_suites:
        lines += [
            f"",
            f"## Failures",
            f"",
        ]
        for s in failed_suites:
            lines.append(f"### {s['suite']}")
            lines.append(f"")
            stderr = s.get("stderr", "").strip()
            stdout = s.get("stdout", "").strip()
            detail = stderr or stdout
            if detail:
                last_lines = "\n".join(detail.splitlines()[-10:])
                lines.append(f"```")
                lines.append(last_lines)
                lines.append(f"```")
            lines.append(f"")

    lines += [
        f"## Known Risks",
        f"",
    ]
    for risk in known_risks:
        lines.append(f"- {risk}")

    lines += [
        f"",
        f"## Pending",
        f"",
        f"- bloque-F13-engram-active requires live Engram binary — skipped in --quick/--release",
        f"- Network suites skipped unless `--no-network` is NOT set and external services are live",
        f"",
        f"## Executive Summary",
        f"",
    ]

    if overall_failed == 0:
        lines += [
            f"All {overall_total} suites passed. Healthcheck: {'PASS' if hc_pass else 'WARN (see above)'}.",
            f"ATLAS is **ready for tagging**.",
        ]
    else:
        lines += [
            f"**{overall_failed} suite(s) failed.** Review failures above before tagging.",
            f"Do not tag until all failures are resolved.",
        ]

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Generated by `python tools/run_all.py --release` on {now.strftime('%Y-%m-%d %H:%M UTC')}*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  [report] {out_path}")


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
        description="ATLAS unified QA runner — single command to validate everything",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Exit codes:")[1] if "Exit codes:" in __doc__ else "",
    )
    parser.add_argument("--quick", action="store_true", default=True,
                        help="Local suites only, no live binaries (default)")
    parser.add_argument("--full", action="store_true",
                        help="Include suites that need live binaries")
    parser.add_argument("--release", action="store_true",
                        help="Full validation required before tagging: strict healthcheck + all suites + release report")
    parser.add_argument("--no-network", action="store_true",
                        help="Skip suites that make network calls")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="Output machine-readable JSON to stdout")
    parser.add_argument("--out", metavar="FILE",
                        help="Save JSON output to FILE (implies --json)")
    parser.add_argument("--report", metavar="FILE", default="release-report.md",
                        help="Release report output path (default: release-report.md, only in --release mode)")
    parser.add_argument("--list", action="store_true",
                        help="List suites without running")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Per-suite timeout in seconds (default: 60)")
    args = parser.parse_args()

    if args.out:
        args.json_output = True

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
    run_start = time.monotonic()
    results = []
    hc_result = None

    mode = "release" if args.release else ("full" if args.full else "quick")

    if not args.json_output:
        print(f"\n{_c(BOLD, 'ATLAS QA Runner')} — mode: {mode}")
        print(f"Running {len(selected)} suites ({len(skipped)} skipped)\n")

    # Healthcheck always runs in --release mode (strict: settings.json FAIL not WARN)
    if args.release:
        if not args.json_output:
            print("  [....] healthcheck", end="\r", flush=True)
        hc_result = run_healthcheck(strict=True)
        if not args.json_output:
            print_result(hc_result)

    for suite_path in selected:
        stem = suite_stem(suite_path)
        if not args.json_output:
            print(f"  [....] {stem}", end="\r", flush=True)
        suite_timeout = SUITE_TIMEOUTS.get(stem, args.timeout)
        r = run_suite(suite_path, timeout=suite_timeout)
        results.append(r)
        if not args.json_output:
            print_result(r)

    run_end = time.monotonic()

    # --- summary ---
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    total_time = sum(r["elapsed"] for r in results)

    if hc_result:
        if not hc_result["passed"]:
            failed += 1
        total += 1
        passed = total - failed

    git_meta = get_git_metadata() if args.release else {}

    output = {
        "mode": mode,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": len(skipped),
        "elapsed": round(total_time, 2),
        "git": git_meta,
        "healthcheck": hc_result,
        "suites": results,
    }

    if args.json_output:
        json_str = json.dumps(output, indent=2)
        print(json_str)
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            print(f"\n  [json]   {args.out}", file=sys.stderr)
    else:
        status_color = GREEN if failed == 0 else RED
        print(f"\n{'='*60}")
        print(f"RESULTADO : {_c(GREEN, f'PASS={passed}')}  {_c(RED, f'FAIL={failed}') if failed else _c(GREEN, 'FAIL=0')}  / {total} suites")
        print(f"TIME      : {total_time:.2f}s total")
        print(f"STATUS    : {_c(status_color, 'ALL PASS' if failed == 0 else f'{failed} FAILED')}")
        if skipped:
            print(f"SKIPPED   : {len(skipped)} suites (use --full to include)")
        print(f"{'='*60}\n")

    # Auto-generate release report in --release mode
    if args.release:
        report_path = PROJECT_ROOT / args.report
        generate_release_report(output, hc_result, run_start, run_end, report_path)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
