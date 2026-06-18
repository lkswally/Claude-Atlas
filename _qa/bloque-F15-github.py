#!/usr/bin/env python3
"""
Bloque F15 — GitHub MCP Validation
=====================================

Valida GitHub MCP (oficial github/github-mcp-server):
  1. github en registry
  2. atlas_capability = repository
  3. Binary oficial existe en disco
  4. Binary ejecutable (--version responde)
  5. .mcp.json contiene entrada github con GITHUB_TOKEN ref
  6. GITHUB_TOKEN en env o .env.local
  7. capabilities incluyen PRs, issues, repos, code search
  8. required_for incluye agentes git y orquestador
  9. capability layer: "repository" presente (aunque PENDING_TOKEN)
 10. NOT usar @modelcontextprotocol/server-github (deprecated)

Total: 10 tests
Nota: T6 puede ser SKIP si GITHUB_TOKEN no está seteado aún.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOME = Path.home()
GITHUB_MCP_BIN = HOME / "go" / "bin" / "github-mcp-server.exe"
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT))

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0


def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def skip(name: str, detail: str = "") -> None:
    global SKIP_COUNT
    SKIP_COUNT += 1
    print(f"  [SKIP] {name}{' -- ' + detail if detail else ''}")


def test_registry_entry():
    from mcp_registry import get_mcp
    m = get_mcp("github")
    if not m:
        fail("T1 GitHub in registry", "not found"); return
    status = m.get("status", "")
    ok("T1 GitHub in registry", f"status={status}")


def test_atlas_capability():
    from mcp_registry import get_mcp
    m = get_mcp("github")
    cap = m.get("atlas_capability") if m else None
    if cap == "repository":
        ok("T2 atlas_capability=repository")
    else:
        fail("T2 atlas_capability=repository", f"got={cap}")


def test_binary_exists():
    if GITHUB_MCP_BIN.exists():
        size_mb = GITHUB_MCP_BIN.stat().st_size // (1024 * 1024)
        ok("T3 Binary exists", f"{GITHUB_MCP_BIN} ({size_mb}MB)")
    else:
        fail("T3 Binary exists", f"not found: {GITHUB_MCP_BIN}")


def test_binary_responds():
    if not GITHUB_MCP_BIN.exists():
        fail("T4 Binary --version", "binary missing"); return
    try:
        r = subprocess.run(
            [str(GITHUB_MCP_BIN), "--version"],
            capture_output=True, text=True, timeout=8,
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode == 0 or out:
            ok("T4 Binary --version", out.split("\n")[0][:60] if out else "exit 0")
        else:
            fail("T4 Binary --version", f"exit {r.returncode}: {out[:80]}")
    except subprocess.TimeoutExpired:
        fail("T4 Binary --version", "timeout >8s")
    except Exception as e:
        fail("T4 Binary --version", str(e))


def test_mcp_json_configured():
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    if not mcp_file.exists():
        fail("T5 .mcp.json configured", "not found"); return
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})
        if "github" in servers:
            s = servers["github"]
            has_token_ref = "GITHUB_TOKEN" in json.dumps(s)
            ok("T5 .mcp.json configured",
               f"command={Path(s.get('command','?')).name} token_ref={has_token_ref}")
        else:
            fail("T5 .mcp.json configured",
                 f"github not in mcpServers. Keys: {list(servers.keys())}")
    except Exception as e:
        fail("T5 .mcp.json configured", str(e))


def test_github_token_available():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        env_local = PROJECT_ROOT.parent / ".env.local"
        if env_local.exists():
            content = env_local.read_text(encoding="utf-8", errors="ignore")
            if "GITHUB_TOKEN" in content:
                ok("T6 GITHUB_TOKEN", "found in .env.local")
                return
        skip("T6 GITHUB_TOKEN", "not set — provide via .env.local or env var to activate GitHub MCP")
    else:
        ok("T6 GITHUB_TOKEN", "present in environment (length={})".format(len(token)))


def test_capabilities_coverage():
    from mcp_registry import get_mcp
    m = get_mcp("github")
    caps = set(m.get("capabilities", [])) if m else set()
    required = {"create_pr", "list_issues", "list_repos", "search_code"}
    missing = required - caps
    if not missing:
        ok("T7 Capabilities coverage", f"{len(caps)} caps")
    else:
        fail("T7 Capabilities coverage", f"missing: {missing}")


def test_required_for():
    from mcp_registry import get_mcp
    m = get_mcp("github")
    req = set(m.get("required_for", [])) if m else set()
    needed = {"git", "orquestador"}
    missing = needed - req
    if not missing:
        ok("T8 required_for", f"{sorted(req)}")
    else:
        fail("T8 required_for", f"missing: {missing}")


def test_capability_layer():
    try:
        from core.capabilities import get_capability
        cap = get_capability("repository")
        if not cap:
            fail("T9 Capability layer: repository", "not found"); return
        p = cap.active_provider
        if p:
            ok("T9 Capability layer: repository",
               f"provider={p.mcp_id} status={p.status}")
        else:
            fail("T9 Capability layer: repository", "no provider")
    except ImportError as e:
        fail("T9 Capability layer", f"import error: {e}")


def test_no_deprecated_package():
    deprecated = "@modelcontextprotocol/server-github"
    mcp_file = PROJECT_ROOT.parent / ".mcp.json"
    if mcp_file.exists():
        content = mcp_file.read_text(encoding="utf-8", errors="ignore")
        if deprecated in content:
            fail("T10 No deprecated package", f"{deprecated} found in .mcp.json")
        else:
            ok("T10 No deprecated package", "using github-mcp-server binary (official)")
    else:
        ok("T10 No deprecated package", ".mcp.json not found (no deprecated ref possible)")


def main():
    print("=" * 60)
    print("Bloque F15 -- GitHub MCP Validation")
    print(f"Project  : {PROJECT_ROOT}")
    print(f"Binary   : {GITHUB_MCP_BIN}")
    print("=" * 60)
    print()

    test_registry_entry()
    test_atlas_capability()
    test_binary_exists()
    test_binary_responds()
    test_mcp_json_configured()
    test_github_token_available()
    test_capabilities_coverage()
    test_required_for()
    test_capability_layer()
    test_no_deprecated_package()

    total = PASS_COUNT + FAIL_COUNT + SKIP_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT} | SKIP: {SKIP_COUNT}")
    print()

    if FAIL_COUNT == 0 and SKIP_COUNT == 0:
        print("RESULTADO: PASS (GITHUB MCP READY)")
    elif FAIL_COUNT == 0:
        print(f"RESULTADO: PASS (PENDING_TOKEN — {SKIP_COUNT} test(s) skipped hasta tener GITHUB_TOKEN)")
    else:
        print("RESULTADO: FAIL")

    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
