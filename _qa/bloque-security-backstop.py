#!/usr/bin/env python3
"""
Bloque Security Backstop — Deterministic Security Backstop (Autonomy
Improvement V2, Improvement A)
=============================================================================

Gap demostrado: Autonomy Benchmark V1 Security = 18.8%. 6/8 fixtures reales
(eval, SQL injection, insecure CORS, missing-auth, IDOR, unsafe upload) sin
deteccion — confirmado ejecutando .claude/hooks/quality-gate.js con stdin
real, no simulado. security-engineer (unico agente con juicio semantico
para estas categorias) solo se invoca en Fase 2 del pipeline completo.

Este suite valida las 7 reglas nuevas agregadas a quality-gate.js:
  - True positives: cada regla dispara con su fixture representativo.
  - False positives: casos plausibles que NO deben disparar (RegExp.exec,
    page.evaluate, query parametrizada, HTML estatico, CORS sin wildcard,
    filename sanitizado, TLS habilitado).
  - Regression test para el bug real encontrado durante el desarrollo de
    este mismo suite: el lookahead negativo de innerHTML era vulnerable a
    backtracking de \\s* (\\s* podia retroceder a cero espacios consumidos,
    dejando el lookahead frente al espacio en vez de la comilla, que
    trivialmente no es una comilla y dejaba pasar el string literal).
  - missing-authorization / IDOR genericos NO se prueban aqui porque
    DELIBERADAMENTE no se implementaron -- son problemas de ausencia
    (negative-space) que un regex no puede detectar sin ruido masivo.
  - Verifica que el hook sigue siendo exit-0/fail-open (WARN-only, nunca
    bloquea) y que el log estructurado security-signals.jsonl se escribe
    con el schema documentado.

Total (base): 17 tests (7 true-positive rule checks + 8 false-positive-
avoidance checks + 1 JSONL log schema check + 1 pre-existing-behavior
regression check; each true-positive case also asserts exit code 0,
silently, as part of the same check rather than a separate visible line).

Stability Repair 05 (SH-P1-2) additions — comment-induced false positives:
root cause was that the 7 SECURITY_PATTERNS regexes ran against raw file
content with no comment-awareness, so a `// TODO: never call eval(x)`
comment fired identically to a real eval() call. Fixed via maskComments()
in quality-gate.js, a single-pass lexical scanner that blanks // and /* */
comment interiors while leaving strings/template literals/regex literals
untouched (several rules — CMDI, SQLI, UPLOAD — are designed to match a
payload embedded *inside* a string argument, so blanking strings would
create new false negatives; see the function's own comment for detail).
Adds 15 comment-lookalike checks (// and /* */ forms, all 7 rules, plus one
JSX {/* */} case) and 6 structural edge-case checks (escaped quotes,
template literals with nested braces, regex literals, URL strings, a
multiline comment with line-number-preservation assertion, and same-line
comment+real-vulnerability disambiguation). New total: 38 tests.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
HOOK_PATH = PROJECT_ROOT / ".claude" / "hooks" / "quality-gate.js"
LOG_PATH = PROJECT_ROOT / ".claude" / "logs" / "security-signals.jsonl"

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


def run_hook(file_path: str, content: str) -> subprocess.CompletedProcess:
    payload = json.dumps({
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    })
    return subprocess.run(
        ["node", str(HOOK_PATH)],
        input=payload, capture_output=True, text=True, timeout=10,
    )


# ---------------------------------------------------------------------------
# True positives — one per rule, matching the exact benchmark gap categories
# ---------------------------------------------------------------------------
TRUE_POSITIVES = [
    ("SEC-EVAL-001", "src/utils.js", "function run(x) { return eval(x); }"),
    ("SEC-CMDI-001", "src/run.js",
     'const child_process = require("child_process");\n'
     'function run(userFile) {\n  child_process.exec("cat " + userFile);\n}'),
    ("SEC-SQLI-001", "src/db.js",
     'function getUser(id) {\n  return db.query("SELECT * FROM users WHERE id = " + id);\n}'),
    ("SEC-XSS-001", "src/render.js",
     'function show(userInput) {\n  el.innerHTML = userInput;\n}'),
    ("SEC-CORS-001", "src/server.js",
     'app.use(cors({ origin: "*", credentials: true }));'),
    ("SEC-TLS-001", "src/client.js",
     'const agent = new https.Agent({ rejectUnauthorized: false });'),
    ("SEC-UPLOAD-001", "src/routes/upload.js",
     'router.post("/upload", upload.single("file"), (req, res) => {\n'
     '  fs.writeFileSync(`./public/uploads/${req.file.originalname}`, req.file.buffer);\n});'),
]


def test_true_positives():
    for rule_id, path, content in TRUE_POSITIVES:
        r = run_hook(path, content)
        combined = r.stdout + r.stderr
        if f"security:{rule_id}" in combined:
            ok(f"TP {rule_id}", f"detected in {path}")
        else:
            fail(f"TP {rule_id}", f"NOT detected -- stdout/stderr: {combined[:150]}")
        if r.returncode != 0:
            fail(f"TP {rule_id} exit code", f"expected 0 (fail-open/WARN-only), got {r.returncode}")


# ---------------------------------------------------------------------------
# False positives — plausible safe code that must NOT trigger any rule
# ---------------------------------------------------------------------------
FALSE_POSITIVES = [
    ("regexp.exec (not child_process)", "src/parse.js",
     "const re = /foo(\\d+)/;\nconst match = re.exec(inputString + suffix);"),
    ("page.evaluate (Playwright, not eval)", "src/page.js",
     "async function check(page) {\n  await page.evaluate(() => document.title);\n}"),
    ("parameterized SQL query", "src/safe_db.js",
     'function getUser(id) {\n  return db.query("SELECT * FROM users WHERE id = ?", [id]);\n}'),
    ("static innerHTML string literal", "src/static.js",
     'el.innerHTML = "<b>Hello world</b>";'),
    ("static innerHTML, multiple spaces (backtracking regression)", "src/static2.js",
     'el.innerHTML    =    "<b>Safe</b>";'),
    ("CORS credentials:true WITHOUT wildcard origin", "src/cors_ok.js",
     'app.use(cors({ origin: "https://example.com", credentials: true }));'),
    ("upload with sanitized/generated filename", "src/safe_upload.js",
     "const safeName = crypto.randomUUID() + path.extname(req.file.originalname);\n"
     "fs.writeFileSync(`./uploads/${safeName}`, req.file.buffer);"),
    ("TLS verification explicitly enabled", "src/safe_tls.js",
     "const agent = new https.Agent({ rejectUnauthorized: true });"),
]


def test_false_positives():
    for name, path, content in FALSE_POSITIVES:
        r = run_hook(path, content)
        combined = r.stdout + r.stderr
        has_security_finding = "security:SEC-" in combined
        if not has_security_finding:
            ok(f"FP: {name}", "correctly silent")
        else:
            fail(f"FP: {name}", f"false positive fired: {combined[:150]}")


# ---------------------------------------------------------------------------
# Structured log schema
# ---------------------------------------------------------------------------
def test_jsonl_log_schema():
    if not LOG_PATH.exists():
        fail("JSONL log schema", f"log file not created at {LOG_PATH}")
        return
    lines = [l for l in LOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        fail("JSONL log schema", "log file exists but is empty")
        return
    required_fields = {"id", "category", "severity", "path", "line", "evidence", "confidence", "msg", "timestamp"}
    entry = json.loads(lines[-1])
    missing = required_fields - set(entry.keys())
    if not missing:
        ok("JSONL log schema", f"{len(lines)} entries, all required fields present")
    else:
        fail("JSONL log schema", f"missing fields: {missing}")


# ---------------------------------------------------------------------------
# Existing patterns (secrets, dangerous cmd via block-no-verify) unaffected
# ---------------------------------------------------------------------------
def test_existing_secret_detection_unaffected():
    r = run_hook(
        "src/config.js",
        'const apiKey = "sk_live_51H8x7ZKq9vN3mP2rTyUw4X6aB9cDeFgHiJkLmNoPqRs";',
    )
    combined = r.stdout + r.stderr
    if "hardcoded secret" in combined.lower() and r.returncode == 0:
        ok("Existing secret detection unaffected", "still WARN, still exit 0")
    else:
        fail("Existing secret detection unaffected", combined[:150])


# ---------------------------------------------------------------------------
# Stability Repair 05 (SH-P1-2) — comment-induced false positives.
# Adversarial corpus: for every one of the 7 rules, both // and /* */
# comment forms mentioning the exact dangerous pattern must be silent.
# ---------------------------------------------------------------------------
COMMENT_LOOKALIKES = [
    ("SEC-EVAL-001", "src/cl_eval_line.js", "// TODO: never call eval(userInput) directly, it is dangerous"),
    ("SEC-EVAL-001", "src/cl_eval_block.js", "/* never call eval(userInput) directly, it is dangerous */"),
    ("SEC-CMDI-001", "src/cl_cmdi_line.js", '// avoid: child_process.exec("cat " + userFile) -- injection risk'),
    ("SEC-CMDI-001", "src/cl_cmdi_block.js", '/* avoid: child_process.exec("cat " + userFile) -- injection risk */'),
    ("SEC-SQLI-001", "src/cl_sqli_line.js", '// bad practice: db.query("SELECT * FROM users WHERE id = " + id)'),
    ("SEC-SQLI-001", "src/cl_sqli_block.js", '/* bad practice: db.query("SELECT * FROM users WHERE id = " + id) */'),
    ("SEC-XSS-001", "src/cl_xss_line.js", "// don't do: el.innerHTML = userInput; -- XSS risk, sanitize first"),
    ("SEC-XSS-001", "src/cl_xss_block.js", "/* don't do: el.innerHTML = userInput; -- XSS risk, sanitize first */"),
    ("SEC-XSS-001", "src/cl_xss_jsx.jsx", "function C() {\n  return <div>{/* never use dangerouslySetInnerHTML here */}</div>;\n}"),
    ("SEC-CORS-001", "src/cl_cors_line.js", '// insecure: cors({ origin: "*", credentials: true }) must never ship'),
    ("SEC-CORS-001", "src/cl_cors_block.js", '/* insecure: cors({ origin: "*", credentials: true }) must never ship */'),
    ("SEC-TLS-001", "src/cl_tls_line.js", "// never set rejectUnauthorized: false in production code"),
    ("SEC-TLS-001", "src/cl_tls_block.js", "/* never set rejectUnauthorized: false in production code */"),
    ("SEC-UPLOAD-001", "src/cl_upload_line.js", '// insecure pattern: fs.writeFileSync(dest, req.file.originalname)'),
    ("SEC-UPLOAD-001", "src/cl_upload_block.js", '/* insecure pattern: fs.writeFileSync(dest, req.file.originalname) */'),
]


def test_comment_lookalikes():
    for rule_id, path, content in COMMENT_LOOKALIKES:
        r = run_hook(path, content)
        combined = r.stdout + r.stderr
        if f"security:{rule_id}" not in combined:
            ok(f"Comment lookalike silent: {rule_id}", path)
        else:
            fail(f"Comment lookalike silent: {rule_id}", f"FIRED from comment-only text: {combined[:150]}")


# ---------------------------------------------------------------------------
# Structural edge cases for the comment-masking lexer itself (Stability
# Repair 05, mission section 4/10/11): escaped quotes, template literals
# with nested braces, regex literals, multiline block comments, and
# trailing inline comments must not desync the masker and must not create
# new false negatives on real vulnerable code sharing the same file.
# ---------------------------------------------------------------------------
def test_edge_escaped_quotes_do_not_desync():
    content = 'const s = "she said \\"hello\\""; eval(userInput);'
    r = run_hook("src/edge_escaped_quotes.js", content)
    combined = r.stdout + r.stderr
    if "security:SEC-EVAL-001" in combined:
        ok("Edge: escaped quotes don't desync parser", "real eval() after escaped-quote string still detected")
    else:
        fail("Edge: escaped quotes don't desync parser", f"real eval() NOT detected: {combined[:150]}")


def test_edge_template_literal_nested_braces():
    content = 'const msg = `value: ${ {a: 1} }`;\neval(userInput);'
    r = run_hook("src/edge_template_nested.js", content)
    combined = r.stdout + r.stderr
    if "security:SEC-EVAL-001" in combined:
        ok("Edge: template literal nested braces don't desync parser", "real eval() after ${...} still detected")
    else:
        fail("Edge: template literal nested braces don't desync parser", f"real eval() NOT detected: {combined[:150]}")


def test_edge_regex_literal_does_not_swallow_code():
    content = 'const re = /eval\\(/;\nfunction run(x) { return eval(x); }'
    r = run_hook("src/edge_regex_literal.js", content)
    combined = r.stdout + r.stderr
    if "security:SEC-EVAL-001" in combined:
        ok("Edge: regex literal doesn't swallow following code", "real eval() after /eval\\(/ regex still detected")
    else:
        fail("Edge: regex literal doesn't swallow following code", f"real eval() NOT detected: {combined[:150]}")


def test_edge_url_in_string_not_treated_as_comment():
    content = 'const docs = "see https://example.com//path for details";\nfunction run(x) { return eval(x); }'
    r = run_hook("src/edge_url_string.js", content)
    combined = r.stdout + r.stderr
    if "security:SEC-EVAL-001" in combined:
        ok("Edge: URL // inside string not treated as comment start", "real eval() after URL string still detected")
    else:
        fail("Edge: URL // inside string not treated as comment start", f"real eval() NOT detected: {combined[:150]}")


def test_edge_multiline_block_comment_line_number_preserved():
    content = (
        "/*\n"
        " * TODO: remove this before shipping\n"
        " * never call eval(userInput) in production\n"
        " */\n"
        "function real() { return eval(x); }\n"
    )
    r = run_hook("src/edge_multiline_comment.js", content)
    combined = r.stdout + r.stderr
    if "security:SEC-EVAL-001" not in combined or "(1x)" not in combined:
        fail("Edge: multiline block comment silent + real vuln still detected",
             f"expected exactly 1 finding (the real call, not the comment text): {combined[:200]}")
        return
    lines = [l for l in LOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    last = json.loads(lines[-1])
    if last["id"] == "SEC-EVAL-001" and last["line"] == 5:
        ok("Edge: multiline block comment silent + real vuln still detected", "exactly 1 finding, reported line 5")
    else:
        fail("Edge: multiline block comment silent + real vuln still detected",
             f"expected line 5, got {last.get('line')}")


def test_edge_comment_and_real_vuln_same_line():
    content = "/* eval(bad) in comment */ function run(x) { return eval(x); }"
    r = run_hook("src/edge_same_line.js", content)
    combined = r.stdout + r.stderr
    count = combined.count("security:SEC-EVAL-001")
    # dedup terminal summary is one line per rule with a count suffix "(Nx)"
    if "security:SEC-EVAL-001" in combined and "(1x)" in combined:
        ok("Edge: comment + real vuln same line -- fires exactly once", "for the real call only")
    else:
        fail("Edge: comment + real vuln same line -- fires exactly once", combined[:200])


def main():
    print("=" * 60)
    print("Bloque Security Backstop -- Deterministic Security Backstop")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    print()

    if LOG_PATH.exists():
        LOG_PATH.unlink()  # clean slate so the schema test reads only this run's entries

    test_true_positives()
    test_false_positives()
    test_jsonl_log_schema()
    test_existing_secret_detection_unaffected()
    test_comment_lookalikes()
    test_edge_escaped_quotes_do_not_desync()
    test_edge_template_literal_nested_braces()
    test_edge_regex_literal_does_not_swallow_code()
    test_edge_url_in_string_not_treated_as_comment()
    test_edge_multiline_block_comment_line_number_preserved()
    test_edge_comment_and_real_vuln_same_line()

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
