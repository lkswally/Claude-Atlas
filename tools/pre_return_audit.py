#!/usr/bin/env python3
"""
Pre-Return Audit (Bloque 1A.14)
Audita archivos modificados ANTES de emitir Return Envelope.

Reglas BLOCK (exit code 1):
  1. debugger en archivos no-test
  2. breakpoint() en Python no-test
  3. .only( / .skip( en tests/specs
  4. Secrets hardcodeados

Reglas WARN (exit code 0, reportadas):
  5. console.log/warn/error en archivos modificados no-test/no-dev-util
  6. TODO/FIXME/HACK recien agregados (via git diff)

Uso:
  python tools/pre_return_audit.py <archivo1> [archivo2] ...
  python tools/pre_return_audit.py --files-from envelope.json

Salida: JSON a stdout.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
#  PATRONES
# ============================================================

# BLOCK rules — patrones compilados una sola vez
RE_DEBUGGER = re.compile(r"\bdebugger\b\s*;?")
RE_BREAKPOINT = re.compile(r"\bbreakpoint\s*\(")
RE_ONLY_SKIP = re.compile(r"\.(only|skip)\s*\(")

SECRET_PATTERNS = [
    ("api_key", re.compile(r"""api[_-]?key\s*=\s*["'][A-Za-z0-9]{16,}["']""", re.IGNORECASE)),
    ("password", re.compile(r"""password\s*=\s*["'][^"']{6,}["']""", re.IGNORECASE)),
    ("secret", re.compile(r"""secret\s*=\s*["'][A-Za-z0-9]{16,}["']""", re.IGNORECASE)),
    ("bearer_token", re.compile(r"""Bearer\s+[A-Za-z0-9._\-]{20,}""")),
    ("openai_key", re.compile(r"""\bsk-[A-Za-z0-9]{20,}\b""")),
    ("github_token", re.compile(r"""\bghp_[A-Za-z0-9]{20,}\b""")),
    ("aws_access_key", re.compile(r"""\bAKIA[0-9A-Z]{16}\b""")),
]

# WARN rules
RE_CONSOLE = re.compile(r"\bconsole\.(log|warn|error)\s*\(")
RE_TODO_TAGS = re.compile(r"\b(TODO|FIXME|HACK)\b")

# Comment detection (line starts with // or # ignoring whitespace)
RE_COMMENT_LINE = re.compile(r"^\s*(//|#)")

# Path classification
RE_TEST_PATH = re.compile(r"(^|/)(_)?(test|tests|spec|__tests__)(/|$)|\.spec\.|\.test\.")
DEV_UTIL_PREFIXES = ("tools/", "_qa/", "scripts/", ".claude/")


# ============================================================
#  PATH CLASSIFIERS
# ============================================================

def normalize_path(path: str) -> str:
    """Normalize path for matching (forward slashes, no leading ./)"""
    p = path.replace("\\", "/").lstrip("./")
    return p


def is_test_file(path: str) -> bool:
    """Check if path matches test/spec patterns"""
    return bool(RE_TEST_PATH.search(normalize_path(path)))


def is_dev_util(path: str) -> bool:
    """Check if path is in dev utilities (tools/, _qa/, scripts/, .claude/)"""
    p = normalize_path(path)
    return any(p.startswith(prefix) for prefix in DEV_UTIL_PREFIXES)


def is_comment_line(line: str) -> bool:
    """Check if line is a single-line comment (// or #)"""
    return bool(RE_COMMENT_LINE.match(line))


# ============================================================
#  GIT DIFF HELPERS (para regla 6 TODO/FIXME/HACK recien agregados)
# ============================================================

def get_added_lines(file_path: str) -> Optional[List[int]]:
    """
    Retorna lista de numeros de linea agregados/modificados en file_path
    segun git diff vs HEAD. Si git falla o archivo no esta en repo, retorna None
    (signaling 'no se puede determinar — tratar todas las lineas como nuevas').
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", "HEAD", "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        added_lines: List[int] = []
        current_new_start = 0
        current_offset = 0

        for diff_line in result.stdout.splitlines():
            if diff_line.startswith("@@"):
                # Parse hunk header: @@ -old,count +new,count @@
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff_line)
                if m:
                    current_new_start = int(m.group(1))
                    current_offset = 0
            elif diff_line.startswith("+") and not diff_line.startswith("+++"):
                added_lines.append(current_new_start + current_offset)
                current_offset += 1
            elif diff_line.startswith(" "):
                current_offset += 1
            # lines starting with "-" don't increment new file offset

        return added_lines
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


# ============================================================
#  RULE CHECKS
# ============================================================

def check_block_rules(path: str, lines: List[str]) -> List[Dict[str, Any]]:
    """Aplica reglas BLOCK: debugger, breakpoint, .only/.skip, secrets"""
    findings: List[Dict[str, Any]] = []
    is_test = is_test_file(path)

    for idx, line in enumerate(lines, start=1):
        # Skip pure comment lines for non-secret rules
        comment = is_comment_line(line)

        # Rule 1: debugger (no-test, no-comment)
        if not is_test and not comment:
            if RE_DEBUGGER.search(line):
                findings.append({
                    "rule": "debugger",
                    "severity": "BLOCK",
                    "file": path,
                    "line": idx,
                    "match": line.strip()[:120],
                })

        # Rule 2: breakpoint() Python (no-test, no-comment)
        if not is_test and not comment:
            if path.endswith(".py") and RE_BREAKPOINT.search(line):
                findings.append({
                    "rule": "breakpoint",
                    "severity": "BLOCK",
                    "file": path,
                    "line": idx,
                    "match": line.strip()[:120],
                })

        # Rule 3: .only( / .skip( in tests only
        if is_test:
            if RE_ONLY_SKIP.search(line):
                findings.append({
                    "rule": "only_skip",
                    "severity": "BLOCK",
                    "file": path,
                    "line": idx,
                    "match": line.strip()[:120],
                })

        # Rule 4: secrets (all files, all lines incl. comments — secrets in comments are still secrets)
        for secret_name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "rule": f"secret:{secret_name}",
                    "severity": "BLOCK",
                    "file": path,
                    "line": idx,
                    "match": "<redacted>",
                })
                break  # one secret per line is enough

    return findings


def check_warn_rules(path: str, lines: List[str], added_lines: Optional[List[int]]) -> List[Dict[str, Any]]:
    """Aplica reglas WARN: console.* y TODO/FIXME/HACK"""
    findings: List[Dict[str, Any]] = []
    is_test = is_test_file(path)
    is_dev = is_dev_util(path)

    # Rule 5: console.log/warn/error — solo si NO es test Y NO es dev util
    apply_console_rule = not is_test and not is_dev

    # Rule 6: TODO/FIXME/HACK — solo si NO es test
    apply_tags_rule = not is_test

    for idx, line in enumerate(lines, start=1):
        comment = is_comment_line(line)

        # Console
        if apply_console_rule and not comment:
            if RE_CONSOLE.search(line):
                findings.append({
                    "rule": "console_log",
                    "severity": "WARN",
                    "file": path,
                    "line": idx,
                    "match": line.strip()[:120],
                })

        # TODO/FIXME/HACK — solo si la linea fue agregada/modificada (segun git diff)
        if apply_tags_rule:
            if RE_TODO_TAGS.search(line):
                # added_lines=None means "git diff failed" -> treat all as new (conservative)
                if added_lines is None or idx in added_lines:
                    m = RE_TODO_TAGS.search(line)
                    findings.append({
                        "rule": f"tag:{m.group(1)}",
                        "severity": "WARN",
                        "file": path,
                        "line": idx,
                        "match": line.strip()[:120],
                    })

    return findings


# ============================================================
#  AUDIT ENGINE
# ============================================================

def audit_file(path: str, project_root: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Audita un archivo. Retorna (block_findings, warn_findings)."""
    full_path = project_root / path
    if not full_path.exists():
        return ([{
            "rule": "missing_file",
            "severity": "BLOCK",
            "file": path,
            "line": 0,
            "match": "Archivo declarado en envelope no existe en disco",
        }], [])

    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, IOError) as e:
        return ([{
            "rule": "read_error",
            "severity": "BLOCK",
            "file": path,
            "line": 0,
            "match": f"Error leyendo archivo: {e}",
        }], [])

    lines = content.splitlines()
    block_findings = check_block_rules(path, lines)
    added_lines = get_added_lines(path)
    warn_findings = check_warn_rules(path, lines, added_lines)

    return (block_findings, warn_findings)


def audit_files(file_paths: List[str], project_root: Path) -> Dict[str, Any]:
    """Audita lista de archivos y arma reporte agregado."""
    all_blocks: List[Dict[str, Any]] = []
    all_warns: List[Dict[str, Any]] = []
    audited: List[str] = []

    for raw_path in file_paths:
        path = normalize_path(raw_path)
        blocks, warns = audit_file(path, project_root)
        all_blocks.extend(blocks)
        all_warns.extend(warns)
        audited.append(path)

    ok = len(all_blocks) == 0
    summary = f"{'PASS' if ok else 'FAIL'} ({len(all_blocks)} blocks, {len(all_warns)} warns)"

    return {
        "ok": ok,
        "block_findings": all_blocks,
        "warn_findings": all_warns,
        "files_audited": audited,
        "summary": summary,
    }


# ============================================================
#  CLI
# ============================================================

def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python tools/pre_return_audit.py <archivo1> [archivo2] ...", file=sys.stderr)
        print("     python tools/pre_return_audit.py --files-from <envelope.json>", file=sys.stderr)
        return 2

    project_root = Path.cwd()

    # Opcion: --files-from <envelope.json>
    if sys.argv[1] == "--files-from":
        if len(sys.argv) < 3:
            print("Error: --files-from requiere ruta a envelope.json", file=sys.stderr)
            return 2
        envelope_path = Path(sys.argv[2])
        try:
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            file_paths = envelope.get("archivos", [])
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error leyendo envelope: {e}", file=sys.stderr)
            return 2
    else:
        file_paths = sys.argv[1:]

    if not file_paths:
        # Empty file list = trivially PASS
        report = {
            "ok": True,
            "block_findings": [],
            "warn_findings": [],
            "files_audited": [],
            "summary": "PASS (0 blocks, 0 warns) — no files to audit",
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    report = audit_files(file_paths, project_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
