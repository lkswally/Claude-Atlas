#!/usr/bin/env python3
"""
Bloque F46 -- Test isolation (roadmap P21)
=============================================================================

Gap: 18 of 50 Quick suites wrote to REAL state: the repo's .pipeline (the invocation log that audit_invocations reads as
evidence of what ran), .claude/logs, the user's ~/.claude/snapshots (cost-log.jsonl, session-log.jsonl) and, through the
real Engram binary, ~/.engram. tools/test_sandbox.py runs every suite in a disposable copy of the working tree with a
disposable HOME; tools/run_all.py uses it by default.

This suite proves the property three ways:
  A. the sandbox is what it claims to be (a copy, its own git repo, an empty .pipeline, a HOME that Python and Node both
     resolve inside it, read-only inputs mirrored, nothing of the real state);
  B. a self-contained experiment with a CONTROL: the same writer, run unisolated, pollutes the "real" state; run in the
     sandbox it does not -- so the check can fail;
  C. the runner's own run_suite()/run_healthcheck() use the sandbox, and two real polluting suites (one writes the
     repo state, one runs the JS hooks that write ~/.claude/snapshots) leave the real state byte-for-byte unchanged.
"""
import ast
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import test_sandbox as ts  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
WORK = Path(tempfile.mkdtemp(prefix="atlas_f46_"))


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    detail = str(detail) if detail != "" else ""
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def child(code, env, *args, cwd=None):
    return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, env=env, cwd=cwd, timeout=60)


# --------------------------------------------------------------------------- A. what the sandbox is
def test_sandbox_shape():
    print("\n-- A. the sandbox is a disposable copy with its own HOME --")
    sb = ts.Sandbox(PROJECT_ROOT)
    try:
        check("A1 the working tree was copied", sb.copied > 500 and (sb.repo / "tools" / "test_sandbox.py").is_file(), f"{sb.copied} files")
        check("A2 a tracked file is byte-identical to the working tree",
              (sb.repo / "tools" / "run_all.py").read_bytes() == (PROJECT_ROOT / "tools" / "run_all.py").read_bytes())
        check("A3 the sandbox lives outside the real tree", PROJECT_ROOT.resolve() not in sb.repo.resolve().parents)
        pipeline = sb.repo / ".pipeline"
        check("A4 the sandbox .pipeline starts EMPTY, whatever the real one holds",
              pipeline.is_dir() and not any(p.is_file() for p in pipeline.rglob("*")))
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(sb.repo), capture_output=True, text=True)
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(sb.repo), capture_output=True, text=True)
        check("A5 the sandbox is its own git repository with a clean HEAD (suites that call git keep working)",
              git.returncode == 0 and len(git.stdout.strip()) == 40 and st.stdout.strip() == "", st.stdout[:80])
        check("A6 unrelated projects are not copied", not (sb.repo / "lucas-rojo-web").exists() and not (sb.repo / "conexo-web").exists())
        env = sb.env()
        py = child("from pathlib import Path; print(Path.home())", env)
        check("A7 Python resolves HOME inside the sandbox", py.stdout.strip() == str(sb.home), py.stdout.strip())
        if shutil.which("node"):
            nd = subprocess.run(["node", "-e", "console.log(require('os').homedir())"], capture_output=True, text=True, env=env, timeout=60)
            check("A8 Node (the hooks) resolves HOME inside the sandbox", nd.stdout.strip() == str(sb.home), nd.stdout.strip())
        else:
            print("  [SKIP] A8 node not installed")
        check("A9 the real state directories do not exist in the sandbox HOME",
              not (sb.home / ".claude" / "snapshots").exists() and not (sb.home / ".engram").exists())
        real_settings = Path.home() / ".claude" / "settings.json"
        if real_settings.is_file() and Path(env["HOME"]) != Path.home():
            check("A10 the user's settings.json is mirrored read-only (a COPY)",
                  (sb.home / ".claude" / "settings.json").read_bytes() == real_settings.read_bytes())
        else:
            print("  [SKIP] A10 no real ~/.claude/settings.json here")
        check("A11 path_for maps a real path into the sandbox",
              sb.path_for(PROJECT_ROOT / "_qa" / "bloque-F46-test-isolation.py") == sb.repo / "_qa" / "bloque-F46-test-isolation.py")
    finally:
        sb.cleanup()
    check("A12 cleanup removes the whole sandbox", not sb._tmp.exists())
    real_bin = Path.home() / "go" / "bin"
    if real_bin.is_dir():
        check("A13 cleanup leaves the REAL executables directory alone", any(real_bin.iterdir()))


# --------------------------------------------------------------------------- B. control + isolation
WRITER = '''
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
(root / ".pipeline").mkdir(exist_ok=True)
with open(root / ".pipeline" / "log.jsonl", "a") as f:
    f.write("repo-write\\n")
snap = Path.home() / ".claude" / "snapshots"
snap.mkdir(parents=True, exist_ok=True)
with open(snap / "session-log.jsonl", "a") as f:
    f.write("home-write\\n")
'''


def make_fake_real():
    root = Path(tempfile.mkdtemp(prefix="fake_real_", dir=WORK))
    home = Path(tempfile.mkdtemp(prefix="fake_home_", dir=WORK))
    (root / "tools").mkdir()
    (root / "tools" / "writer.py").write_text(WRITER, encoding="utf-8")
    (root / "tools" / "version.py").write_text("V = 2  # an UNCOMMITTED edit: the sandbox copies the working tree, not HEAD\n", encoding="utf-8")
    (root / ".pipeline").mkdir()
    (root / ".pipeline" / "log.jsonl").write_text("seed\n", encoding="utf-8")
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    return root, home, env


def test_control_and_isolation():
    print("\n-- B. the same writer: unisolated it pollutes, in the sandbox it does not --")
    root, home, env = make_fake_real()
    r = subprocess.run([sys.executable, str(root / "tools" / "writer.py")], cwd=str(root), env=env, capture_output=True, text=True, timeout=60)
    polluted_repo = (root / ".pipeline" / "log.jsonl").read_text() == "seed\nrepo-write\n"
    polluted_home = (home / ".claude" / "snapshots" / "session-log.jsonl").is_file()
    check("B1 CONTROL: unisolated, the writer changes the real repo state and the real HOME (so a leak WOULD be detected)",
          r.returncode == 0 and polluted_repo and polluted_home, r.stderr[-120:])

    root, home, env = make_fake_real()
    before = ts.protected_snapshot(root)
    sb = ts.Sandbox(root)
    try:
        sbenv = sb.env(env)
        r = subprocess.run([sys.executable, str(sb.path_for(root / "tools" / "writer.py"))], cwd=str(sb.repo), env=sbenv,
                           capture_output=True, text=True, timeout=60)
        check("B2 isolated, the writer runs fine", r.returncode == 0, r.stderr[-120:])
        check("B3 the REAL repo state is untouched (the seed is not even copied)", (root / ".pipeline" / "log.jsonl").read_text() == "seed\n")
        check("B4 the REAL HOME is untouched", not (home / ".claude" / "snapshots").exists())
        check("B5 the leak guard sees no change in the real state", ts.changed(before, ts.protected_snapshot(root)) == [])
        check("B6 the writes landed in the sandbox instead",
              (sb.repo / ".pipeline" / "log.jsonl").read_text() == "repo-write\n" and (sb.home / ".claude" / "snapshots" / "session-log.jsonl").is_file())
        check("B7 the sandbox holds the CURRENT working tree (an uncommitted edit), not a commit",
              (sb.repo / "tools" / "version.py").read_text().startswith("V = 2"))
    finally:
        sb.cleanup()

    # git semantics: the WORKING TREE is copied (tracked + untracked-not-ignored), not a commit
    if shutil.which("git"):
        g = Path(tempfile.mkdtemp(prefix="fake_git_", dir=WORK))
        genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@invalid")

        def git(*a):
            return subprocess.run(["git", *a], cwd=str(g), env=genv, capture_output=True, text=True, timeout=60)
        (g / "a.txt").write_text("1", encoding="utf-8")
        (g / ".gitignore").write_text("*.log\n", encoding="utf-8")
        git("init", "-q")
        git("add", "-A")
        git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "x")
        (g / "a.txt").write_text("2", encoding="utf-8")          # an uncommitted edit
        (g / "b.txt").write_text("new", encoding="utf-8")        # untracked, not ignored
        (g / "c.log").write_text("ignored", encoding="utf-8")    # ignored
        sbg = ts.Sandbox(g)
        try:
            check("B12 git semantics: an uncommitted edit and an untracked file are copied, an ignored file is not",
                  (sbg.repo / "a.txt").read_text() == "2" and (sbg.repo / "b.txt").read_text() == "new" and not (sbg.repo / "c.log").exists())
        finally:
            sbg.cleanup()
    else:
        print("  [SKIP] B12 git not installed")

    # the leak guard itself
    root, home, env = make_fake_real()
    a = ts.protected_snapshot(root)
    check("B8 guard: nothing changed -> nothing reported", ts.changed(a, ts.protected_snapshot(root)) == [])
    (root / ".pipeline" / "log.jsonl").write_text("seed\nmore\n", encoding="utf-8")
    check("B9 guard: a modified file is reported", len(ts.changed(a, ts.protected_snapshot(root))) == 1)
    b = ts.protected_snapshot(root)
    (root / ".pipeline" / "new.json").write_text("{}", encoding="utf-8")
    check("B10 guard: a new file is reported", len(ts.changed(b, ts.protected_snapshot(root))) == 1)
    c = ts.protected_snapshot(root)
    (root / ".pipeline" / "new.json").unlink()
    check("B11 guard: a deleted file is reported", len(ts.changed(c, ts.protected_snapshot(root))) == 1)


# --------------------------------------------------------------------------- C. the runner
def load_run_all():
    spec = importlib.util.spec_from_file_location("atlas_run_all_f46", str(PROJECT_ROOT / "tools" / "run_all.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner():
    print("\n-- C. the runner uses the sandbox, and real polluting suites leave real state alone --")
    ra = load_run_all()
    check("C1 isolation is ON by default and the env switch turns it off",
          ts.isolation_enabled() is True and ts.isolation_enabled(False) is False and ts.isolation_enabled(True) is True)
    old = os.environ.get("ATLAS_TEST_ISOLATION")
    os.environ["ATLAS_TEST_ISOLATION"] = "0"
    try:
        check("C2 ATLAS_TEST_ISOLATION=0 disables it", ts.isolation_enabled() is False)
    finally:
        if old is None:
            os.environ.pop("ATLAS_TEST_ISOLATION", None)
        else:
            os.environ["ATLAS_TEST_ISOLATION"] = old

    sb = ts.Sandbox(PROJECT_ROOT)
    try:
        calls = []
        real_run = ra.subprocess.run

        def spy(cmd, **kw):
            calls.append((list(cmd), kw))
            return subprocess.CompletedProcess(cmd, 0, stdout="RESULTADO: PASS\nFAIL=0 ", stderr="")
        ra.subprocess.run = spy
        try:
            ra._SANDBOX = sb
            ra.run_suite(PROJECT_ROOT / "_qa" / "bloque-F16-capability-router.py", timeout=5)
            ra.run_healthcheck(strict=False)
            suite_call, hc_call = calls[0], calls[1]
            ra._SANDBOX = None
            calls.clear()
            ra.run_suite(PROJECT_ROOT / "_qa" / "bloque-F16-capability-router.py", timeout=5)
            plain = calls[0]
        finally:
            ra.subprocess.run = real_run
            ra._SANDBOX = None
        check("C3 run_suite runs the SANDBOX copy of the suite with the sandbox as cwd",
              str(sb.repo) in suite_call[0][1] and suite_call[1]["cwd"] == str(sb.repo), suite_call[0][1][-60:])
        check("C4 run_suite hands the suite the sandbox HOME", suite_call[1]["env"]["HOME"] == str(sb.home) and suite_call[1]["env"]["USERPROFILE"] == str(sb.home))
        check("C5 run_healthcheck is sandboxed too (it writes capability events and snapshots)",
              str(sb.repo) in str(hc_call[0][1]) and hc_call[1]["cwd"] == str(sb.repo) and hc_call[1]["env"]["HOME"] == str(sb.home))
        check("C6 with isolation off the runner still uses the real tree (the switch really switches)",
              plain[1]["cwd"] == str(PROJECT_ROOT) and str(sb.repo) not in plain[0][1])

        # the real thing: two suites known to write state, run through the runner's own run_suite.
        # An idle control interval first: if the host itself is writing to the protected locations right now (its own
        # hooks), a before/after comparison would prove nothing either way, so say so instead of passing or failing.
        idle_a = ts.protected_snapshot(PROJECT_ROOT)
        time.sleep(2.0)
        host_noise = ts.changed(idle_a, ts.protected_snapshot(PROJECT_ROOT))
        before = ts.protected_snapshot(PROJECT_ROOT)
        ra._SANDBOX = sb
        try:
            r1 = ra.run_suite(PROJECT_ROOT / "_qa" / "bloque-F16-capability-router.py", timeout=120)
            hooks = PROJECT_ROOT / "_qa" / "bloque-F6-runtime-hooks-validation.py"
            r2 = ra.run_suite(hooks, timeout=180) if shutil.which("node") and hooks.is_file() else None
        finally:
            ra._SANDBOX = None
        after = ts.protected_snapshot(PROJECT_ROOT)
        check("C7 the repo-state writer (capability router) passes in the sandbox", r1["passed"], (r1.get("stderr") or "")[-120:])
        if r2 is not None:
            check("C8 the hooks suite (writes ~/.claude/snapshots) passes in the sandbox", r2["passed"], (r2.get("stderr") or "")[-120:])
        else:
            print("  [SKIP] C8 node or the hooks suite is unavailable")
        if host_noise:
            print(f"  [SKIP] C9 the host is writing to the protected state right now ({len(host_noise)} file(s) changed while idle)")
        else:
            check("C9 the REAL protected state (repo .pipeline, .claude/logs, ~/.claude/snapshots, ~/.engram) is byte-for-byte unchanged",
                  ts.changed(before, after) == [], str(ts.changed(before, after)[:3]))
        written = [p for p in (sb.repo / ".pipeline").rglob("*") if p.is_file()] + [p for p in (sb.home / ".claude").rglob("*") if p.is_file()]
        check("C10 the writes really happened, in the sandbox (the suites were not silently skipped)", len(written) > 0, f"{len(written)} files")
    finally:
        sb.cleanup()

    src = (PROJECT_ROOT / "tools" / "run_all.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mains = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in ("main", "_run")]
    names = {n.id for f in mains for n in ast.walk(f) if isinstance(n, ast.Name)}
    check("C11 the runner reports the isolation mode and leaks in its output and fails the run on a leak",
          '"isolation"' in src and '"isolation_leaks"' in src and "ISOLATION LEAK" in src and "leaks" in names)

    # behaviour of the runner's leak guard: a change in the REAL repo state during the run fails the run
    import argparse
    import contextlib
    import io

    def run_guard(leaky):
        args = argparse.Namespace(json_output=True, out=None, release=False, full=False, report="x.md", no_network=False,
                                  timeout=5, no_isolation=False)
        key = str(PROJECT_ROOT / ".pipeline" / "x.json")
        before = {key: (1, 1)}
        after = {key: (2, 2)} if leaky else dict(before)
        saved = ra.protected_snapshot
        ra.protected_snapshot = lambda root, extra=(): after
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = ra._run(args, [], [], "quick", time.monotonic(), [], None, "on (test)", before)
        finally:
            ra.protected_snapshot = saved
        return rc, buf.getvalue()
    rc0, out0 = run_guard(False)
    rc1, out1 = run_guard(True)
    check("C12 no change in the real state -> the runner exits 0 and reports no leaks", rc0 == 0 and '"isolation_leaks": []' in out0, f"rc={rc0}")
    check("C13 a change in the REAL repo state during the run FAILS the run and names the file in the JSON",
          rc1 == 1 and "x.json" in out1 and '"failed": 1' in out1, f"rc={rc1}")


# --------------------------------------------------------------------------- D. the runner end to end
SUITE_WRITER = '''
import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
(root / ".pipeline").mkdir(exist_ok=True)
with open(root / ".pipeline" / "log.jsonl", "a") as f:
    f.write("repo-write\\n")
snap = Path.home() / ".claude" / "snapshots"
snap.mkdir(parents=True, exist_ok=True)
with open(snap / "session-log.jsonl", "a") as f:
    f.write("home-write\\n")
print("RESULTADO: PASS")
'''


def fake_project():
    root = Path(tempfile.mkdtemp(prefix="fake_proj_", dir=WORK))
    home = Path(tempfile.mkdtemp(prefix="fake_proj_home_", dir=WORK))
    (root / "tools").mkdir()
    (root / "_qa").mkdir()
    shutil.copy2(PROJECT_ROOT / "tools" / "run_all.py", root / "tools" / "run_all.py")
    shutil.copy2(PROJECT_ROOT / "tools" / "test_sandbox.py", root / "tools" / "test_sandbox.py")
    (root / "_qa" / "bloque-F99-writer.py").write_text(SUITE_WRITER, encoding="utf-8")
    (root / ".pipeline").mkdir()
    (root / ".pipeline" / "log.jsonl").write_text("seed\n", encoding="utf-8")
    return root, home


def run_fake(root, home, *flags):
    import json
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    env.pop("ATLAS_TEST_ISOLATION", None)
    r = subprocess.run([sys.executable, str(root / "tools" / "run_all.py"), "--quick", "--json", *flags], cwd=str(root), env=env,
                       capture_output=True, text=True, timeout=120)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = {}
    return r, out


def test_runner_end_to_end():
    print("\n-- D. main() end to end on a fake project: isolation is the DEFAULT --")
    sandboxes_before = set(Path(tempfile.gettempdir()).glob("atlas_sbx_*"))
    root, home = fake_project()
    r, out = run_fake(root, home)
    leftovers = set(Path(tempfile.gettempdir()).glob("atlas_sbx_*")) - sandboxes_before
    check("D5 a finished run leaves no sandbox directory behind", not leftovers, str(sorted(p.name for p in leftovers))[:120])
    check("D1 default run: the suite passes and the runner reports isolation ON",
          r.returncode == 0 and out.get("passed") == 1 and str(out.get("isolation", "")).startswith("on"), (out.get("isolation"), r.stderr[-150:]))
    check("D2 default run: the fake project's real state and HOME are untouched",
          (root / ".pipeline" / "log.jsonl").read_text() == "seed\n" and not (home / ".claude").exists())
    check("D3 default run: no leak reported", out.get("isolation_leaks") == [])

    root, home = fake_project()
    r, out = run_fake(root, home, "--no-isolation")
    check("D4 CONTROL --no-isolation: the runner reports it OFF and the same suite DOES pollute the real state (so D2 can fail)",
          out.get("isolation") == "off" and (root / ".pipeline" / "log.jsonl").read_text() == "seed\nrepo-write\n"
          and (home / ".claude" / "snapshots" / "session-log.jsonl").is_file(), str(out.get("isolation")))


def main():
    print("=" * 60)
    print("Bloque F46 -- Test isolation (P21)")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    t0 = time.perf_counter()
    try:
        test_sandbox_shape()
        test_control_and_isolation()
        test_runner()
        test_runner_end_to_end()
    finally:
        shutil.rmtree(WORK, ignore_errors=True)
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nElapsed: {time.perf_counter() - t0:.1f}s")
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
