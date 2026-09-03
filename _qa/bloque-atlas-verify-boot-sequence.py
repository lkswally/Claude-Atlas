#!/usr/bin/env python3
"""
Bloque atlas-verify — orquestador_boot_sequence regression guard
===================================================================

Regression test for the tools/atlas_verify.py::check_orquestador_documentation
STALE_TEST bug (2026-08-24 diagnostic).

Root cause: F32 (commit aec6752, 2026-06-19) moved "Paso 4a-4d" boot-mode
documentation VERBATIM from agents/orquestador.md to agents/refs/
orchestrator-routing.md as part of a deliberate, documented boot-loader
slimming (orquestador.md -96% tokens). The check's target path was never
updated to follow that move, so it silently failed against the (correctly)
slimmed facade for 2+ months -- atlas_verify.py is a standalone script, not
wired into run_all.py/CI, so nothing caught the drift.

This suite guards against BOTH failure directions:
  1. The fix regressing back to the pre-F32 path (or any other stale path).
  2. The check itself becoming a silent no-op false-PASS (i.e. it must still
     be able to fail when the required content is genuinely absent).

Total: 3 tests
"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(name: str, detail: str = "") -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    suffix = f" -- {detail}" if detail else ""
    print(f"  [PASS] {name}{suffix}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    suffix = f" -- {detail}" if detail else ""
    print(f"  [FAIL] {name}{suffix}")


# ---------------------------------------------------------------------------
# T1: check_orquestador_documentation() returns PASS against the real repo
# ---------------------------------------------------------------------------
def test_check_passes_against_real_repo():
    import os
    cwd_before = os.getcwd()
    try:
        os.chdir(PROJECT_ROOT)
        import atlas_verify
        result = atlas_verify.check_orquestador_documentation()
        status = result.get("orquestador_boot_sequence", "")
        if status == "[PASS]":
            ok("T1 check_orquestador_documentation() PASS", status)
        else:
            fail("T1 check_orquestador_documentation() PASS", status)
    except Exception as e:
        fail("T1 check_orquestador_documentation() PASS", str(e))
    finally:
        os.chdir(cwd_before)


# ---------------------------------------------------------------------------
# T2: the canonical target file exists and is the registered lazy-ref
# ---------------------------------------------------------------------------
def test_target_file_is_registered_ref():
    target = PROJECT_ROOT / "agents" / "refs" / "orchestrator-routing.md"
    if not target.exists():
        fail("T2 Target file exists", f"missing: {target}")
        return
    try:
        import yaml
        registry = yaml.safe_load(
            (PROJECT_ROOT / "config" / "knowledge.registry.yaml").read_text(encoding="utf-8")
        )
        ids = {k.get("id") for k in registry.get("knowledge", [])}
        if "orchestrator-routing" in ids:
            ok("T2 Target file is a registered lazy-ref", "orchestrator-routing in knowledge.registry.yaml")
        else:
            fail("T2 Target file is a registered lazy-ref", f"'orchestrator-routing' not in registry ids: {sorted(ids)[:5]}...")
    except ImportError:
        # PyYAML absent: file-existence check above already gives partial coverage.
        ok("T2 Target file exists (registry check skipped, PyYAML absent)")
    except Exception as e:
        fail("T2 Target file is a registered lazy-ref", str(e))


# ---------------------------------------------------------------------------
# T3: the check still has teeth -- it FAILs when required content is absent
# ---------------------------------------------------------------------------
def test_check_still_fails_on_missing_content():
    import os
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        (tmp_root / "agents" / "refs").mkdir(parents=True)
        # A file that does NOT contain the required steps
        (tmp_root / "agents" / "refs" / "orchestrator-routing.md").write_text(
            "# Orchestrator routing\n\nNo boot-mode steps here.\n", encoding="utf-8"
        )
        cwd_before = os.getcwd()
        try:
            os.chdir(tmp_root)
            import atlas_verify
            result = atlas_verify.check_orquestador_documentation()
            status = result.get("orquestador_boot_sequence", "")
            if status.startswith("[FAIL]") and "Paso 4a" in status:
                ok("T3 Check still fails on missing content", status)
            else:
                fail("T3 Check still fails on missing content",
                     f"expected FAIL mentioning missing steps, got: {status}")
        except Exception as e:
            fail("T3 Check still fails on missing content", str(e))
        finally:
            os.chdir(cwd_before)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Bloque atlas-verify -- orquestador_boot_sequence regression guard")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    test_check_passes_against_real_repo()
    test_target_file_is_registered_ref()
    test_check_still_fails_on_missing_content()

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
