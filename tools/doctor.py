#!/usr/bin/env python3
"""
ATLAS Doctor
============

Diagnoses the local ATLAS environment. Read-only — modifies nothing.

Checks:
  - Python, Node.js, Git, Go, Claude versions
  - MCP servers (.mcp.json + registry)
  - Engram binary + database
  - Playwright installation
  - Context7 availability
  - GitHub CLI
  - Filesystem structure (.claude/, hooks/, tools/, config/)
  - File permissions
  - Environment variables
  - PATH entries
  - Key file integrity (healthcheck, dispatcher, run_all)
  - .claude/settings.json presence and validity

Usage:
    python tools/doctor.py
    python tools/doctor.py --json
    python tools/doctor.py --quiet     # only FAIL and WARN
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Result tracker
# ---------------------------------------------------------------------------

_results: list[dict] = []


def _record(level: str, name: str, detail: str) -> None:
    _results.append({"level": level, "name": name, "detail": detail})
    icons = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "INFO": "[INFO]"}
    if not _quiet:
        if level in ("FAIL", "WARN") or not _quiet_mode:
            print(f"  {icons.get(level, level)} {name}: {detail}")


_quiet = False
_quiet_mode = False


def PASS(name: str, detail: str = "ok") -> None:
    _record("PASS", name, detail)


def WARN(name: str, detail: str) -> None:
    _record("WARN", name, detail)


def FAIL(name: str, detail: str) -> None:
    _record("FAIL", name, detail)


def INFO(name: str, detail: str) -> None:
    _record("INFO", name, detail)


# ---------------------------------------------------------------------------
# Helper: run a command and return stdout or None
# ---------------------------------------------------------------------------

def _run(*args, timeout: int = 5) -> str | None:
    try:
        r = subprocess.run(
            list(args), capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None
    except Exception:
        return None


def _which(name: str) -> str | None:
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_python() -> None:
    ver = sys.version_info
    detail = f"{ver.major}.{ver.minor}.{ver.micro} at {sys.executable}"
    if ver.major >= 3 and ver.minor >= 11:
        PASS("Python", detail)
    elif ver.major >= 3 and ver.minor >= 10:
        WARN("Python", f"{detail} — 3.11+ recommended")
    else:
        FAIL("Python", f"{detail} — need 3.11+")


def check_node() -> None:
    path = _which("node")
    if not path:
        FAIL("Node.js", "not in PATH — install from https://nodejs.org")
        return
    ver = _run("node", "--version")
    if ver:
        try:
            major = int(ver.lstrip("v").split(".")[0])
            if major >= 18:
                PASS("Node.js", f"{ver} at {path}")
            else:
                FAIL("Node.js", f"{ver} — need 18+ for hooks compatibility")
        except ValueError:
            WARN("Node.js", f"version unreadable: {ver}")
    else:
        WARN("Node.js", "found but version check failed")


def check_git() -> None:
    path = _which("git")
    if not path:
        FAIL("Git", "not in PATH")
        return
    ver = _run("git", "--version")
    PASS("Git", ver or "found")


def check_go() -> None:
    path = _which("go")
    if not path:
        WARN("Go", "not in PATH — required to build Engram from source")
        return
    ver = _run("go", "version")
    PASS("Go", ver or "found")


def check_claude() -> None:
    path = _which("claude")
    if path:
        PASS("Claude CLI", f"found at {path}")
        return
    # Windows Claude Desktop typical location
    win_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "AnthropicClaude" / "claude.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "AnthropicClaude" / "claude.exe",
    ]
    for p in win_paths:
        if p.exists():
            PASS("Claude Desktop", f"found at {p}")
            return
    WARN("Claude", "not found — install Claude Desktop from https://claude.ai/download")


def check_github_cli() -> None:
    path = _which("gh")
    if not path:
        WARN("GitHub CLI", "not in PATH — install from https://cli.github.com")
        return
    ver = _run("gh", "--version")
    PASS("GitHub CLI", (ver or "found").splitlines()[0])


def check_engram() -> None:
    # Check binary
    engram_bin = Path.home() / ".engram" / "engram.exe"
    engram_bin_nix = Path.home() / ".engram" / "engram"
    path_engram = _which("engram")

    found_bin = None
    if engram_bin.exists():
        found_bin = str(engram_bin)
    elif engram_bin_nix.exists():
        found_bin = str(engram_bin_nix)
    elif path_engram:
        found_bin = path_engram

    if not found_bin:
        WARN("Engram binary", "not found at ~/.engram/engram — memory features unavailable")
    else:
        PASS("Engram binary", found_bin)

    # Check database
    engram_db = Path.home() / ".engram" / "engram.db"
    if engram_db.exists():
        size_kb = engram_db.stat().st_size // 1024
        PASS("Engram database", f"{engram_db} ({size_kb} KB)")
    else:
        WARN("Engram database", "not found — will be created on first use")


def check_playwright() -> None:
    try:
        import importlib
        spec = importlib.util.find_spec("playwright")
        if spec is None:
            FAIL("Playwright", "not installed — run: pip install playwright")
            return
        PASS("Playwright Python package", "installed")
    except Exception:
        WARN("Playwright", "import check failed")


def check_mcp_json() -> None:
    mcp_path = PROJECT_ROOT / ".mcp.json"
    if not mcp_path.exists():
        WARN(".mcp.json", "not found in project root — MCP servers unavailable")
        return
    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        PASS(".mcp.json", f"valid — {len(servers)} server(s): {', '.join(servers.keys())}")
        # Check known servers
        for required in ("engram", "context7"):
            if required in servers:
                PASS(f"MCP/{required}", "configured")
            else:
                WARN(f"MCP/{required}", "not in .mcp.json")
    except json.JSONDecodeError as e:
        FAIL(".mcp.json", f"invalid JSON: {e}")


def check_filesystem() -> None:
    required_dirs = [
        (".claude", True),
        (".claude/hooks", True),
        ("tools", True),
        ("config", True),
        ("_qa", True),
        ("agents", False),
        ("docs", False),
        ("bootstrap", False),
    ]
    for rel, required in required_dirs:
        p = PROJECT_ROOT / rel
        if p.exists():
            count = sum(1 for _ in p.iterdir()) if p.is_dir() else 0
            PASS(f"dir/{rel}", f"{count} items")
        elif required:
            FAIL(f"dir/{rel}", "missing — required directory")
        else:
            WARN(f"dir/{rel}", "missing")

    key_files = [
        "tools/run_all.py",
        "tools/atlas_healthcheck.py",
        "tools/atlas_dispatcher.py",
        "tools/doctor.py",
        "CLAUDE.md",
        "README.md",
        "CHANGELOG.md",
        "ROADMAP.md",
        ".mcp.json",
        "config/mcp.registry.yaml",
        "config/atlas.runtime.expected.yaml",
    ]
    for rel in key_files:
        p = PROJECT_ROOT / rel
        if p.exists():
            PASS(f"file/{rel}", f"{p.stat().st_size} bytes")
        else:
            FAIL(f"file/{rel}", "missing")


def check_hooks() -> None:
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    if not hooks_dir.exists():
        FAIL("Hooks", ".claude/hooks/ directory missing")
        return

    js_hooks = sorted(hooks_dir.glob("*.js"))
    if not js_hooks:
        FAIL("Hooks", "no .js hook files found")
        return

    PASS("Hooks", f"{len(js_hooks)} JS hook files")

    # Quick syntax check on each hook
    for h in js_hooks:
        r = _run("node", "--check", str(h), timeout=5)
        # node --check exits 0 on success, non-zero on syntax error
        try:
            result = subprocess.run(
                ["node", "--check", str(h)],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                PASS(f"hook/{h.name}", "syntax ok")
            else:
                FAIL(f"hook/{h.name}", f"syntax error: {result.stderr.strip()[:80]}")
        except FileNotFoundError:
            WARN(f"hook/{h.name}", "cannot syntax-check (node not available)")
            break
        except Exception as e:
            WARN(f"hook/{h.name}", str(e))


def check_settings() -> None:
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    if not settings_path.exists():
        WARN(".claude/settings.json", "absent (Windows race condition — managed by Claude Desktop, F23)")
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks = data.get("hooks", {})
        hook_count = sum(
            len(block.get("hooks", []))
            for blocks in hooks.values()
            for block in blocks
        )
        PASS(".claude/settings.json", f"valid JSON, {hook_count} hook entries")
    except json.JSONDecodeError as e:
        WARN(".claude/settings.json", f"invalid JSON (runtime mutable): {e}")


def check_environment_vars() -> None:
    useful_vars = {
        "ATLAS_HEALTHCHECK_STRICT": "strict mode for healthcheck",
        "ATLAS_SKILLS_REGISTRY_DISABLED": "disables skills registry",
        "ATLAS_HARD_RULES_DISABLED": "disables hard rules",
        "ATLAS_PYDANTIC_CONTRACTS_DISABLED": "disables Pydantic contracts",
        "ENGRAM_DB_PATH": "custom Engram DB path",
        "PYTHONIOENCODING": "Python output encoding",
    }
    for var, desc in useful_vars.items():
        val = os.environ.get(var)
        if val:
            INFO(f"env/{var}", f"set to '{val}' ({desc})")
        else:
            INFO(f"env/{var}", f"not set ({desc})")


def check_path() -> None:
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    useful = {"python", "python3", "node", "git", "go", "claude", "engram", "gh"}
    found = {}
    for name in useful:
        p = _which(name)
        if p:
            found[name] = p
    PASS("PATH coverage", f"{len(found)}/{len(useful)} tools found: {', '.join(sorted(found.keys()))}")
    missing = useful - set(found.keys())
    if missing:
        WARN("PATH missing", f"{', '.join(sorted(missing))}")


def check_permissions() -> None:
    dirs_need_write = ["_qa", "tools", ".claude"]
    for rel in dirs_need_write:
        p = PROJECT_ROOT / rel
        if not p.exists():
            continue
        # Test write permission by checking os.access
        if os.access(p, os.W_OK):
            PASS(f"perm/{rel}", "writable")
        else:
            FAIL(f"perm/{rel}", "not writable — tests will fail")


def check_key_imports() -> None:
    modules = {
        "json": "stdlib",
        "subprocess": "stdlib",
        "pathlib": "stdlib",
        "yaml": "pyyaml (pip install pyyaml)",
    }
    for mod, source in modules.items():
        try:
            __import__(mod)
            PASS(f"import/{mod}", "ok")
        except ImportError:
            if mod in ("json", "subprocess", "pathlib"):
                FAIL(f"import/{mod}", "stdlib missing — broken Python installation")
            else:
                WARN(f"import/{mod}", f"missing — install: {source}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    global _quiet, _quiet_mode

    import argparse
    parser = argparse.ArgumentParser(description="ATLAS environment diagnostic (read-only)")
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Only show FAIL and WARN")
    args = parser.parse_args()

    _quiet = args.json_output
    _quiet_mode = args.quiet

    if not args.json_output:
        print("\nATLAS Doctor — environment diagnostic (read-only)\n")
        print("Runtimes")
        print("-" * 40)

    check_python()
    check_node()
    check_git()
    check_go()
    check_claude()
    check_github_cli()

    if not args.json_output:
        print("\nPackages & Tools")
        print("-" * 40)

    check_engram()
    check_playwright()
    check_key_imports()

    if not args.json_output:
        print("\nMCP Configuration")
        print("-" * 40)

    check_mcp_json()

    if not args.json_output:
        print("\nFilesystem")
        print("-" * 40)

    check_filesystem()
    check_permissions()

    if not args.json_output:
        print("\nHooks")
        print("-" * 40)

    check_hooks()
    check_settings()

    if not args.json_output:
        print("\nEnvironment")
        print("-" * 40)

    check_environment_vars()
    check_path()

    # --- Summary ---
    pass_count = sum(1 for r in _results if r["level"] == "PASS")
    warn_count = sum(1 for r in _results if r["level"] == "WARN")
    fail_count = sum(1 for r in _results if r["level"] == "FAIL")
    info_count = sum(1 for r in _results if r["level"] == "INFO")

    if args.json_output:
        out = {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "info": info_count,
            "ready": fail_count == 0,
            "results": _results,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"PASS={pass_count}  WARN={warn_count}  FAIL={fail_count}  INFO={info_count}")
        if fail_count == 0 and warn_count == 0:
            print("STATUS: ATLAS READY")
        elif fail_count == 0:
            print(f"STATUS: ATLAS READY (with {warn_count} warnings)")
        else:
            print(f"STATUS: ATLAS NOT READY ({fail_count} failure(s))")
            print("\nFailures:")
            for r in _results:
                if r["level"] == "FAIL":
                    print(f"  ✗ {r['name']}: {r['detail']}")
        print(f"{'='*60}\n")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
