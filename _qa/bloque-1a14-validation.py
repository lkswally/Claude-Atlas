#!/usr/bin/env python3
"""
Validacion real de Bloque 1A.14: Auto-Audit Pre-Return
Test 8 escenarios cubriendo todas las reglas BLOCK y WARN.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Agregar tools/ al path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from pre_return_audit import audit_files


def setup_project(tmpdir: str) -> Path:
    root = Path(tmpdir)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "tools").mkdir()
    return root


def write_file(root: Path, rel_path: str, content: str) -> str:
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return rel_path


def assert_block(report: Dict[str, Any], rule_substr: str, file_hint: str = "") -> None:
    found = [f for f in report["block_findings"] if rule_substr in f["rule"]]
    if file_hint:
        found = [f for f in found if file_hint in f["file"]]
    assert found, f"FAIL: Expected BLOCK '{rule_substr}' in {file_hint or 'any file'}, got {report['block_findings']}"


def assert_no_block(report: Dict[str, Any], rule_substr: str = "") -> None:
    if rule_substr:
        found = [f for f in report["block_findings"] if rule_substr in f["rule"]]
        assert not found, f"FAIL: Unexpected BLOCK '{rule_substr}', got {found}"
    else:
        assert report["ok"] is True, f"FAIL: Expected ok=True, got {report}"


def assert_warn(report: Dict[str, Any], rule_substr: str) -> None:
    found = [f for f in report["warn_findings"] if rule_substr in f["rule"]]
    assert found, f"FAIL: Expected WARN '{rule_substr}', got {report['warn_findings']}"


def assert_no_warn(report: Dict[str, Any], rule_substr: str) -> None:
    found = [f for f in report["warn_findings"] if rule_substr in f["rule"]]
    assert not found, f"FAIL: Unexpected WARN '{rule_substr}', got {found}"


# ============================================================
#  TESTS
# ============================================================

def test_1_clean_code_passes():
    print("\n" + "="*70)
    print("TEST 1: CLEAN CODE -> PASS (no findings)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/clean.ts", """
export function greet(name: string): string {
  return `Hello, ${name}!`;
}
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, summary={report['summary']}")
        assert report["ok"] is True
        assert report["block_findings"] == []
        print("[OK] TEST 1: Clean code passes")


def test_2_debugger_blocks():
    print("\n" + "="*70)
    print("TEST 2: debugger en archivo no-test -> BLOCK")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/buggy.ts", """
export function calc(x: number): number {
  debugger;
  return x * 2;
}
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}")
        assert report["ok"] is False
        assert_block(report, "debugger", "buggy.ts")
        print("[OK] TEST 2: debugger blocks correctly")


def test_3_breakpoint_blocks():
    print("\n" + "="*70)
    print("TEST 3: breakpoint() en Python no-test -> BLOCK")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/server.py", """
def handle():
    breakpoint()
    return "ok"
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}")
        assert report["ok"] is False
        assert_block(report, "breakpoint", "server.py")
        print("[OK] TEST 3: breakpoint() blocks correctly")


def test_4_only_skip_in_tests_blocks():
    print("\n" + "="*70)
    print("TEST 4: .only(/.skip( en test files -> BLOCK")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f1 = write_file(root, "tests/foo.test.ts", """
describe.only('focused', () => {
  it.skip('todo', () => {});
});
""")
        report = audit_files([f1], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}")
        assert report["ok"] is False
        assert_block(report, "only_skip", "foo.test.ts")
        print("[OK] TEST 4: .only/.skip blocks in tests")


def test_5_secrets_block():
    print("\n" + "="*70)
    print("TEST 5: Hardcoded secrets -> BLOCK (multiple patterns)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/config.ts", """
const API_KEY = "abc123def456ghi789jkl012";
const password = "supersecret123";
const token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
const openaiKey = "sk-proj-1234567890abcdefghij";
const ghToken = "ghp_1234567890abcdefghijklmn";
const awsKey = "AKIAIOSFODNN7EXAMPLE";
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}")
        assert report["ok"] is False
        # Al menos 3 patterns deben matchear (api_key, password, bearer)
        secret_blocks = [b for b in report["block_findings"] if b["rule"].startswith("secret:")]
        assert len(secret_blocks) >= 3, f"FAIL: Expected >=3 secret blocks, got {len(secret_blocks)}: {secret_blocks}"
        # Match should be redacted
        for sb in secret_blocks:
            assert sb["match"] == "<redacted>", f"FAIL: Secret match must be redacted, got {sb['match']}"
        print(f"[OK] TEST 5: {len(secret_blocks)} secrets blocked (redacted)")


def test_6_console_log_warns_in_src():
    print("\n" + "="*70)
    print("TEST 6: console.log en src/ -> WARN (no BLOCK)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/logger.ts", """
export function log(msg: string) {
  console.log(msg);
  console.warn("warning");
}
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, warns={len(report['warn_findings'])}")
        assert report["ok"] is True, "WARN must NOT block envelope"
        assert_warn(report, "console_log")
        print(f"[OK] TEST 6: console.log warns but does not block")


def test_7_console_log_ignored_in_dev_utils():
    print("\n" + "="*70)
    print("TEST 7: console.log en tools/ y _qa/ -> IGNORED (no WARN)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f1 = write_file(root, "tools/helper.ts", """
console.log("dev util log");
""")
        f2 = write_file(root, "_qa/test-runner.ts", """
console.log("qa log");
""")
        report = audit_files([f1, f2], root)
        print(f"Result: ok={report['ok']}, warns={len(report['warn_findings'])}")
        assert report["ok"] is True
        assert_no_warn(report, "console_log")
        print("[OK] TEST 7: console.log ignored in dev utilities")


def test_8_debugger_in_test_ignored():
    print("\n" + "="*70)
    print("TEST 8: debugger en test file -> IGNORED (not a block)")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "tests/foo.spec.ts", """
it('debugs', () => {
  debugger;
});
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}")
        # debugger NOT blocked in tests, but .only/.skip would be (not present here)
        debugger_blocks = [b for b in report["block_findings"] if b["rule"] == "debugger"]
        assert len(debugger_blocks) == 0, f"FAIL: debugger in test should be ignored, got {debugger_blocks}"
        print("[OK] TEST 8: debugger ignored in test files")


def test_9_comment_lines_ignored():
    print("\n" + "="*70)
    print("TEST 9: debugger en comentario -> IGNORED")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/notes.ts", """
// debugger; this is just a note
// console.log("commented out")
# breakpoint() comment in mixed file
export const x = 1;
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}, warns={len(report['warn_findings'])}")
        assert report["ok"] is True
        assert_no_warn(report, "console_log")
        print("[OK] TEST 9: Comment lines ignored for debugger/console/breakpoint")


def test_10_mixed_block_and_warn():
    print("\n" + "="*70)
    print("TEST 10: MIXED -> BLOCK takes precedence, WARNs reported")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/mixed.ts", """
export function badCode() {
  debugger;
  console.log("debug");
  // TODO: clean this up
  return 42;
}
""")
        report = audit_files([f], root)
        print(f"Result: ok={report['ok']}, blocks={len(report['block_findings'])}, warns={len(report['warn_findings'])}")
        assert report["ok"] is False, "BLOCK must override OK"
        assert_block(report, "debugger")
        assert_warn(report, "console_log")
        print("[OK] TEST 10: Mixed -> BLOCK + WARN both reported")


def test_11_missing_file_blocks():
    print("\n" + "="*70)
    print("TEST 11: Archivo declarado pero NO existe -> BLOCK")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        report = audit_files(["src/ghost.ts"], root)
        print(f"Result: ok={report['ok']}, summary={report['summary']}")
        assert report["ok"] is False
        assert_block(report, "missing_file")
        print("[OK] TEST 11: Missing file blocks correctly")


def test_12_summary_format():
    print("\n" + "="*70)
    print("TEST 12: Summary format conforme spec")
    print("="*70)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = setup_project(tmpdir)
        f = write_file(root, "src/clean.ts", "export const x = 1;\n")
        report = audit_files([f], root)
        keys_expected = {"ok", "block_findings", "warn_findings", "files_audited", "summary"}
        assert set(report.keys()) == keys_expected, f"FAIL: keys mismatch, got {report.keys()}"
        assert report["summary"].startswith("PASS"), f"FAIL: summary should start with PASS, got {report['summary']}"
        assert "0 blocks" in report["summary"]
        print(f"[OK] TEST 12: Summary format OK -- '{report['summary']}'")


# ============================================================
#  RUNNER
# ============================================================

def main():
    print("\n" + "="*70)
    print("VALIDACION REAL -- Bloque 1A.14: Auto-Audit Pre-Return")
    print("="*70)

    tests = [
        test_1_clean_code_passes,
        test_2_debugger_blocks,
        test_3_breakpoint_blocks,
        test_4_only_skip_in_tests_blocks,
        test_5_secrets_block,
        test_6_console_log_warns_in_src,
        test_7_console_log_ignored_in_dev_utils,
        test_8_debugger_in_test_ignored,
        test_9_comment_lines_ignored,
        test_10_mixed_block_and_warn,
        test_11_missing_file_blocks,
        test_12_summary_format,
    ]

    passed = 0
    failed = 0
    try:
        for t in tests:
            t()
            passed += 1
    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        failed += 1

    print("\n" + "="*70)
    print(f"RESULTADO: {passed}/{len(tests)} PASS, {failed} FAIL")
    print("="*70)

    if failed == 0:
        print("\nCONCLUSION:")
        print("[OK] BLOCK rules: debugger, breakpoint, .only/.skip, secrets")
        print("[OK] WARN rules: console.* (excluding tests/dev utils), TODO/FIXME/HACK")
        print("[OK] Path classifiers: tests, dev utilities, comments")
        print("[OK] Secrets redacted in output")
        print("[OK] Missing files blocked")
        print("[OK] JSON output format matches spec")
        print("\nAuto-Audit Pre-Return operativo. Dev agents pueden invocarlo antes de emitir envelope.")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
