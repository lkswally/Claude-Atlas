#!/usr/bin/env python3
"""
Bloque F15 CI Determinism — regression guard
================================================

Regression suite for the 2026-09-03 CI-determinism fix in
bloque-F15-context7.py and bloque-F15-playwright.py. Root cause: T4 used
`npx -y <pkg> --version` (no --offline) with a 30s timeout — a NETWORK
round-trip disguised as a capability check. On this repo's actual CI
(.github/workflows/ci.yml `setup-node@v4` has no `cache:` param — confirmed,
npm cache is genuinely empty every run, not a transient flake), that
structurally exceeded 30s in 3 consecutive runs. Fix: split PACKAGE_AVAILABLE
(deterministic, offline, fast — SKIP not FAIL when absent) from
LIVE_REACHABLE (network, opt-in, informational, never blocking). See
docs/F15-CI-DETERMINISM-FIX.md.

Runs the real bloque-F15-*.py files as subprocesses with controlled
environment, so this suite validates actual CI-facing behavior, not an
internal mock of it. Demonstrates exactly the 5 properties requested:

  1. clean runner, package absent  -> SKIP (not FAIL), overall PASS
  2. package installed             -> PASS
  3. network/timeout failure       -> no false FAIL when capability is optional
  4. registry broken               -> FAIL real (detection NOT neutered)
  5. provider mapping broken       -> FAIL real (detection NOT neutered)

Total: 6 tests (property 1 covered by both F15 files = 2 assertions)
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def skip(name: str, detail: str = "") -> None:
    """Non-blocking: environment dependency absent (e.g. clean CI runner).
    Does not affect PASS_COUNT/FAIL_COUNT/exit code."""
    print(f"  [SKIP] {name}{' -- ' + detail if detail else ''}")


def run_suite(script: str, env_overrides: dict, timeout: int = 40) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "_qa" / script)],
        capture_output=True, text=True, timeout=timeout, env=env,
        cwd=str(PROJECT_ROOT),
    )


# ---------------------------------------------------------------------------
# Property 1: clean runner (package absent) -> SKIP not FAIL, overall PASS
# ---------------------------------------------------------------------------
def test_clean_runner_skips_not_fails():
    with tempfile.TemporaryDirectory() as empty_cache:
        for script, pkg in (
            ("bloque-F15-playwright.py", "playwright"),
            ("bloque-F15-context7.py", "context7"),
        ):
            r = run_suite(script, {"NPM_CONFIG_CACHE": empty_cache})
            has_skip = "[SKIP] T4 package available" in r.stdout
            has_fail_t4 = "[FAIL] T4" in r.stdout
            overall_pass = "RESULTADO: PASS" in r.stdout
            if has_skip and not has_fail_t4 and overall_pass and r.returncode == 0:
                ok(f"P1 clean runner ({pkg})", "T4=SKIP, overall PASS, exit 0")
            else:
                fail(f"P1 clean runner ({pkg})",
                     f"skip={has_skip} fail_t4={has_fail_t4} overall_pass={overall_pass} exit={r.returncode}")


# ---------------------------------------------------------------------------
# Property 2: package installed (warm cache) -> PASS
#
# Adaptive by design, mirroring the exact PACKAGE_AVAILABLE philosophy this
# whole fix establishes: this property can only be DEMONSTRATED where a warm
# cache genuinely exists (a dev machine with prior local use). On a clean CI
# runner there is, by definition, nothing cached to demonstrate against --
# asserting PASS there would be the same "assumed ambient state" mistake the
# original T4 made, just relocated into the regression test instead of fixed.
# So: probe availability first (same --offline mechanism as the real check),
# then SKIP (not FAIL) if this environment has nothing cached, or assert the
# real PASS behavior if it does.
# ---------------------------------------------------------------------------
def test_package_installed_passes():
    import shutil
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        probe = subprocess.run(
            [npx, "--offline", "-y", "@playwright/mcp", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        available = probe.returncode == 0
    except Exception:
        available = False

    if not available:
        skip("P2 package installed -> PASS",
             "no package cached in this environment (clean runner) -- "
             "cannot demonstrate PASS without ambient state; P1/P4/P5 "
             "already cover the SKIP and real-FAIL paths deterministically")
        return

    r = run_suite("bloque-F15-playwright.py", {})
    if "[PASS] T4 package available (offline)" in r.stdout and "RESULTADO: PASS" in r.stdout:
        ok("P2 package installed -> PASS", "warm local cache, T4 PASS")
    else:
        fail("P2 package installed -> PASS", r.stdout[-300:])


# ---------------------------------------------------------------------------
# Property 3: network/timeout failure -> no false FAIL (capability optional)
#
# Two complementary checks, deliberately NOT a live simulated network hang:
# a real unreachable-registry probe on Windows can spawn orphaned npx/node
# grandchildren that keep stdout/stderr pipes open past the parent's own
# timeout (a documented subprocess.run(timeout=) limitation on this platform,
# observed firsthand while writing this suite -- not a property of the fix
# under test). That pitfall would make THIS TEST flaky for reasons unrelated
# to bloque-F15-*.py's correctness. Instead:
#   3a. empirical: default (network-diagnostic OFF, the quick/release path)
#       stays fast and PASS even with cache empty AND registry unreachable --
#       proves the blocking path never touches the network.
#   3b. structural: the opt-in diagnostic's exception handling is inspected
#       in source -- TimeoutExpired and general Exception are both caught,
#       and neither branch can reach fail()/ok(), by construction.
# ---------------------------------------------------------------------------
def test_network_failure_no_false_fail():
    # 3a — default path (no --network-diagnostic opt-in): must stay fast and
    # PASS even with an empty cache and an unreachable registry configured,
    # because test_package_available_offline() never touches the network.
    with tempfile.TemporaryDirectory() as empty_cache:
        r = run_suite(
            "bloque-F15-playwright.py",
            {"NPM_CONFIG_CACHE": empty_cache, "NPM_CONFIG_REGISTRY": "http://127.0.0.1:1/"},
            timeout=20,
        )
        overall_pass = "RESULTADO: PASS" in r.stdout
        if overall_pass and r.returncode == 0:
            ok("P3a default path ignores broken registry", f"exit 0, PASS, under 20s (elapsed timeout budget)")
        else:
            fail("P3a default path ignores broken registry",
                 f"overall_pass={overall_pass} exit={r.returncode}: {r.stdout[-300:]}")

    # 3b — structural guarantee: the opt-in diagnostic's exception handling
    # covers TimeoutExpired + general Exception, and neither path can call
    # fail() -- inspected directly in source, not exercised live.
    for script in ("bloque-F15-playwright.py", "bloque-F15-context7.py"):
        src = (PROJECT_ROOT / "_qa" / script).read_text(encoding="utf-8")
        fn_start = src.index("def test_live_reachable_diagnostic")
        fn_end = src.index("\ndef ", fn_start + 1) if "\ndef " in src[fn_start + 1:] else len(src)
        fn_body = src[fn_start:fn_end]
        # Strip the docstring before checking for real calls -- it discusses
        # ok()/fail() in prose ("never calls ok()/fail()"), which would
        # otherwise false-positive a naive substring search.
        parts = fn_body.split('"""')
        fn_body_code_only = parts[0] + ("".join(parts[2:]) if len(parts) > 2 else "")
        has_timeout_catch = "except subprocess.TimeoutExpired" in fn_body
        has_broad_catch = "except Exception" in fn_body
        calls_fail = "fail(" in fn_body_code_only
        calls_ok = "ok(" in fn_body_code_only
        if has_timeout_catch and has_broad_catch and not calls_fail and not calls_ok:
            ok(f"P3b diagnostic exception handling ({script})",
               "TimeoutExpired + Exception both caught, never calls fail()/ok()")
        else:
            fail(f"P3b diagnostic exception handling ({script})",
                 f"timeout_catch={has_timeout_catch} broad_catch={has_broad_catch} "
                 f"calls_fail={calls_fail} calls_ok={calls_ok}")


# ---------------------------------------------------------------------------
# Property 4: registry broken -> FAIL real (detection not neutered)
# ---------------------------------------------------------------------------
def test_broken_registry_still_fails():
    r = run_suite("bloque-F15-playwright.py", {"ATLAS_MCP_REGISTRY_DISABLED": "1"})
    if "[FAIL] T1 Playwright in registry -- not found" in r.stdout and "RESULTADO: FAIL" in r.stdout:
        ok("P4 broken registry -> FAIL real", "T1 correctly fails when registry disabled")
    else:
        fail("P4 broken registry -> FAIL real", r.stdout[-300:])


# ---------------------------------------------------------------------------
# Property 5: provider mapping broken -> FAIL real (detection not neutered)
# ---------------------------------------------------------------------------
def test_broken_provider_mapping_still_fails():
    r = run_suite("bloque-F15-playwright.py", {"ATLAS_CAPABILITIES_DISABLED": "1"})
    if "[FAIL] T9 Capability layer: browser" in r.stdout and "RESULTADO: FAIL" in r.stdout:
        ok("P5 broken provider mapping -> FAIL real", "T9 correctly fails when capability router disabled")
    else:
        fail("P5 broken provider mapping -> FAIL real", r.stdout[-300:])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Bloque F15 CI Determinism -- regression guard")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_clean_runner_skips_not_fails()
    test_package_installed_passes()
    test_network_failure_no_false_fail()
    test_broken_registry_still_fails()
    test_broken_provider_mapping_still_fails()

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()

    if FAIL_COUNT > 0:
        print("RESULTADO: FAIL")
        sys.exit(1)
    else:
        print("RESULTADO: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
