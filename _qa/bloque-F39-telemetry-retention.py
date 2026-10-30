#!/usr/bin/env python3
"""
Bloque F39 -- Telemetry retention (tools/bounded_jsonl.py + its adopters)
=============================================================================

Gap demostrado (roadmap P2): .pipeline/invocation-log.jsonl llego a 34.65 MB /
186,111 lineas sin cota y cada audit lo leia completo (en el HDD: 1.5 s en frio
con el disco libre, ~23 s durante un full scan de Defender). Ademas los logs
sin lock tenian 165 (invocation) y 472 (skills usage) lineas truncadas, y el
log con lock (capability-events) 0.

Este suite usa SOLO directorios temporales. Nunca toca los logs reales.
Los workers de concurrencia son procesos OS reales (no hilos).
"""

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TOOLS = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import bounded_jsonl as bj  # noqa: E402
from bounded_jsonl import BoundedJsonl  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, cond, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")
    else:
        FAIL_COUNT += 1
        print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


class _Crash(BaseException):
    """Simulated process death (not an Exception: nothing in the helper may swallow it)."""


def tmp():
    return Path(tempfile.mkdtemp(prefix="f39_"))


def iso(dt):
    return dt.isoformat()


def fill(store, n, start=0, pad=40, ts=None):
    for i in range(start, start + n):
        e = {"seq": i, "pad": "x" * pad}
        if ts is not None:
            e["timestamp"] = iso(ts(i))
        r = store.append(e)
        assert r.ok, r
    return start + n


def seqs(entries):
    return [e["seq"] for e in entries]


def total_bytes(store):
    return sum(p.stat().st_size for p in (store.path, store.segment_path) if p.exists())


def cur_size(store):
    """Current segment size; 0 right after a rotation (the file was moved away, next append recreates it)."""
    return store.path.stat().st_size if store.path.exists() else 0


@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


# --------------------------------------------------------------------------- A. bound + rotation
def test_bound_and_rotation():
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=4096)
    r = s.append({"seq": 0})
    check("01 append returns ok and the entry is readable", r.ok and seqs(s.tail_entries(10)) == [0])

    rotated = 0
    for i in range(1, 3000):
        r = s.append({"seq": i, "pad": "x" * 60})
        rotated += r.rotated
        assert r.ok
    check("02 rotation happens when the threshold is crossed", rotated > 10 and s.segment_path.exists(), f"{rotated} rotations")
    check("03 current segment stays under the bound after rotation", cur_size(s) < s.max_bytes)
    bound = 2 * s.max_bytes + 200
    check("04 total retained bytes stay bounded across 3000 appends", total_bytes(s) <= bound, f"{total_bytes(s)} <= {bound}")
    got = seqs(s.tail_entries(100000))
    contiguous = got == list(range(got[0], 3000))
    check("05 retained entries are a contiguous newest suffix (no gap, no duplicate)", contiguous and got[-1] == 2999,
          f"{len(got)} kept, oldest {got[0]}")
    check("06 the oldest entries were discarded by design (retention is bounded)", got[0] > 0)
    st = s.status()
    check("07 status reports the archive size and no rotation error", st["segment_bytes"] is not None
          and st["last_rotation_error"] is None and not st["over_bound"])


# --------------------------------------------------------------------------- B. reads
def test_reads():
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=5000)          # ~120 B/entry => ~40 lines per segment
    now = datetime.now(timezone.utc)
    n = fill(s, 400, ts=lambda i: now - timedelta(seconds=400 - i))
    n = fill(s, 1, start=n, ts=lambda i: now - timedelta(seconds=400 - i))       # guarantees a current file exists
    assert s.segment_path.exists() and s.path.exists()
    cur_lines = len([l for l in s.path.read_bytes().splitlines() if l.strip()])
    seg_lines = len([l for l in s.segment_path.read_bytes().splitlines() if l.strip()])
    assert seg_lines >= 30, seg_lines
    last30 = seqs(s.tail_entries(30))
    check("08 tail_entries(n) is the newest n, oldest -> newest", last30 == list(range(n - 30, n)))
    span = seqs(s.tail_entries(cur_lines + 25))
    check("09 tail_entries spans the segment boundary without gaps",
          span == list(range(n - cur_lines - 25, n)) and len(span) == cur_lines + 25,
          f"current holds {cur_lines}, archive holds {seg_lines}, asked {cur_lines + 25}")
    every = seqs(s.tail_entries(10**6))
    check("10 asking for more than retained returns exactly the retained set (current + archive)",
          len(every) == cur_lines + seg_lines and every == list(range(n - len(every), n)))

    window = cur_lines + 10                                   # reaches 10 entries into the archive
    win = s.recent_entries(now - timedelta(seconds=window))
    expected = [i for i in range(n) if (400 - i) <= window]     # entry i has ts = now - (400 - i); cutoff is inclusive
    check("11 time-window query returns exactly the in-window entries across the boundary",
          seqs(win) == expected and len(expected) > cur_lines, f"{len(win)} entries, window crosses into the archive")

    # out-of-order tolerance: an entry 60 s "older" sits among new ones but is still inside the window
    d2 = tmp()
    s2 = BoundedJsonl(d2 / "t.jsonl", max_bytes=10**6)
    base = datetime.now(timezone.utc)
    for i in range(30):
        s2.append({"seq": i, "timestamp": iso(base - timedelta(seconds=10) + timedelta(milliseconds=i))})
    s2.append({"seq": 100, "timestamp": iso(base - timedelta(seconds=60))})                 # skewed, inside a 120 s window
    for i in range(31, 60):
        s2.append({"seq": i, "timestamp": iso(base - timedelta(seconds=10) + timedelta(milliseconds=i))})
    s2.append({"seq": 200, "timestamp": iso(base - timedelta(seconds=3000))})               # genuinely old
    got = set(seqs(s2.recent_entries(base - timedelta(seconds=120))))
    check("12 skewed entry inside the window is kept and a genuinely old one is excluded",
          100 in got and 200 not in got and set(range(60)) - {30} <= got)

    # slack: a burst (>= the consecutive-old limit) stamped just BEFORE the cutoff but inside the slack must not
    # hide the in-window entries that sit behind it in file order
    d2b = tmp()
    s2b = BoundedJsonl(d2b / "t.jsonl", max_bytes=10**6)
    base = datetime.now(timezone.utc)
    cutoff = base - timedelta(seconds=100)
    for i in range(10):                                                  # in-window, older in file order
        s2b.append({"seq": i, "timestamp": iso(base - timedelta(seconds=50))})
    for i in range(10, 10 + bj.READ_CONSECUTIVE_OLD_STOP + 50):          # burst 30 s before the cutoff (inside the 120 s slack)
        s2b.append({"seq": i, "timestamp": iso(cutoff - timedelta(seconds=30))})
    got = seqs(s2b.recent_entries(cutoff))
    check("12b a burst just before the cutoff (inside the slack) does not truncate the window",
          got == list(range(10)), f"{len(got)} found, expected the 10 in-window entries")

    # bounded read: a tiny window over a big store must not read the whole store
    d3 = tmp()
    s3 = BoundedJsonl(d3 / "t.jsonl", max_bytes=50 * 10**6)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    for i in range(6000):
        s3.append({"seq": i, "timestamp": iso(old + timedelta(seconds=i)), "pad": "y" * 80})
    recent_ts = datetime.now(timezone.utc)
    for i in range(6000, 6020):
        s3.append({"seq": i, "timestamp": iso(recent_ts), "pad": "y" * 80})
    size = s3.path.stat().st_size
    counter = {"bytes": 0}

    class Counting:
        def __init__(self, fh):
            self.fh = fh

        def read(self, n=-1):
            b = self.fh.read(n)
            counter["bytes"] += len(b)
            return b

        def __getattr__(self, a):
            return getattr(self.fh, a)

    orig_open_pair = s3._open_pair
    s3._open_pair = lambda: [Counting(h) if h else None for h in orig_open_pair()]
    win = s3.recent_entries(recent_ts - timedelta(seconds=30))
    s3._open_pair = orig_open_pair
    check("13 recent-window read touches a tiny fraction of the store (bounded, newest-first)",
          len(win) == 20 and counter["bytes"] <= 4 * bj._BLOCK and size > 8 * bj._BLOCK,
          f"read {counter['bytes']} of {size} bytes")
    counter["bytes"] = 0
    s3._open_pair = lambda: [Counting(h) if h else None for h in orig_open_pair()]
    last = s3.tail_entries(100)
    s3._open_pair = orig_open_pair
    check("14 latest-100 read touches a tiny fraction of the store",
          seqs(last) == list(range(5920, 6020)) and counter["bytes"] <= 4 * bj._BLOCK, f"read {counter['bytes']} of {size} bytes")


# --------------------------------------------------------------------------- C. damaged data
def test_damaged_data():
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=10**6)
    now = datetime.now(timezone.utc)
    good_old = [json.dumps({"seq": i, "timestamp": iso(now)}).encode() for i in range(5)]
    s.segment_path.write_bytes(b"\n".join([good_old[0], b'{"seq": 9, "tim', b"\xff\xfe\x00garbage\x80", good_old[1], b"", b"[1,2]", good_old[2]]) + b"\n")
    s.path.write_bytes(json.dumps({"seq": 10, "timestamp": iso(now)}).encode() + b"\n" + b'{"seq": 11, "timestamp": "2026')   # torn last line
    try:
        got = seqs(s.tail_entries(100))
        rec = seqs(s.recent_entries(now - timedelta(seconds=60)))
        ok = True
    except Exception as e:  # noqa: BLE001
        ok, got, rec = False, [], []
    check("15 malformed archive segment + torn tail: readers skip bad lines, never raise", ok and got == [0, 1, 2, 10] and rec == [0, 1, 2, 10], f"{got}")
    e = BoundedJsonl(tmp() / "none.jsonl")
    check("16 missing files read as empty", e.tail_entries(10) == [] and e.recent_entries(datetime.now(timezone.utc)) == [] and not e.exists())
    garbage = BoundedJsonl(tmp() / "g.jsonl")
    garbage.path.write_bytes(os.urandom(5000))
    check("17 random binary content yields no entries and no exception", garbage.tail_entries(50) == [])


# --------------------------------------------------------------------------- D. failure handling
def test_failures():
    # permission failure on rotation
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=1500)
    calls = {"n": 0}
    real_replace = os.replace

    def denied(*a, **k):
        calls["n"] += 1
        raise PermissionError(13, "simulated: file in use")

    err = io.StringIO()
    bj._WARNED.clear()
    with patched(os, "replace", denied), contextlib.redirect_stderr(err):
        results = [s.append({"seq": i, "pad": "x" * 60}) for i in range(60)]
    first_fail = next((r for r in results if r.rotation_error), None)
    check("18 permission failure on rotation: entry still stored, failure reported in the result",
          all(r.ok for r in results) and first_fail is not None and "PermissionError" in first_fail.rotation_error)
    check("19 rotation failure is visible on stderr exactly once", err.getvalue().count("rotation failed") == 1, err.getvalue().strip()[:80])
    check("20 rotation retries are throttled after a failure", calls["n"] == 1, f"{calls['n']} attempts over 60 appends")
    st = s.status()
    check("21 status exposes the rotation error", st["last_rotation_error"] and "PermissionError" in st["last_rotation_error"])
    s._rotation_blocked_until = 0.0                       # time passes; the cause is fixed
    r = s.append({"seq": 999, "pad": "x"})
    check("22 once the cause is fixed rotation recovers and the bound is restored",
          r.ok and r.rotated and cur_size(s) < s.max_bytes and s.status()["last_rotation_error"] is None)

    # over_bound becomes visible when rotation keeps failing and the file keeps growing
    s2 = BoundedJsonl(tmp() / "t.jsonl", max_bytes=1000)
    with patched(os, "replace", denied), contextlib.redirect_stderr(io.StringIO()):
        for i in range(120):
            s2.append({"seq": i, "pad": "x" * 60})
    check("23 a log that cannot rotate is flagged over_bound", s2.status()["over_bound"] is True)

    # disk error on append
    s3 = BoundedJsonl(tmp() / "t.jsonl", max_bytes=10**6)
    fill(s3, 5)

    def enospc(path, mode="r", *a, **k):
        if "b" in mode and "a" in mode and str(path).endswith("t.jsonl"):
            raise OSError(28, "No space left on device")
        return open(path, mode, *a, **k)

    with patched(bj, "open", enospc, ) if hasattr(bj, "open") else _set_open(bj, enospc):
        r = s3.append({"seq": 99})
    check("24 disk error on append: no exception, ok=False with the error, existing data intact",
          r.ok is False and "OSError" in (r.error or "") and seqs(s3.tail_entries(10)) == [0, 1, 2, 3, 4])

    # lock timeout
    s4 = BoundedJsonl(tmp() / "t.jsonl", max_bytes=10**6)
    holder_ready, release = threading.Event(), threading.Event()

    def hold():
        with s4._exclusive(10):
            holder_ready.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    holder_ready.wait(5)
    out = {}
    with patched(bj, "LOCK_TIMEOUT_SECONDS", 0.3):
        t0 = time.monotonic()
        out["r"] = s4.append({"seq": 1})
        out["dt"] = time.monotonic() - t0
    release.set()
    t.join()
    check("25 lock timeout: append fails fast and writes nothing", out["r"].ok is False and "Timeout" in (out["r"].error or "")
          and out["dt"] < 3 and s4.tail_entries(10) == [], f"{out['dt']:.2f}s")
    check("26 after the lock is released appends work again", s4.append({"seq": 2}).ok and seqs(s4.tail_entries(5)) == [2])

    # unserializable payload
    check("27 unserializable entry is rejected without raising", BoundedJsonl(tmp() / "x.jsonl").append({"o": object()}).ok is False)


def _set_open(module, fake):
    @contextlib.contextmanager
    def cm():
        module.open = fake
        try:
            yield
        finally:
            del module.open
    return cm()


# --------------------------------------------------------------------------- E. crash + rotation during IO
def test_crash_and_concurrent_read():
    # (a) crash right before the atomic replace of a normal rotation
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=2000)
    n = 0
    while not s.segment_path.exists() and n < 500:
        s.append({"seq": n, "pad": "x" * 50}); n += 1
    fill(s, 5, start=n); n += 5
    before = s.path.read_bytes()

    def die(*a, **k):
        raise _Crash()

    crashed = False
    s2 = BoundedJsonl(d / "t.jsonl", max_bytes=len(before) + 5)       # next append crosses the threshold
    with patched(os, "replace", die):
        try:
            s2.append({"seq": n, "pad": "x" * 50})
        except _Crash:
            crashed = True
    state_ok = s.path.exists() and s.path.read_bytes().startswith(before)
    tail = seqs(BoundedJsonl(d / "t.jsonl").tail_entries(10))
    check("28 crash before the atomic replace: lock released, data intact, readers fine",
          crashed and state_ok and tail[-1] == n, f"tail {tail[-3:]}")
    r = BoundedJsonl(d / "t.jsonl", max_bytes=len(before) + 5).append({"seq": n + 1, "pad": "x"})   # a fresh process, same threshold
    got = seqs(BoundedJsonl(d / "t.jsonl").tail_entries(10**6))
    check("29 the next writer (a new process) completes the rotation: no corruption, no duplicates",
          r.ok and r.rotated and len(got) == len(set(got)) and got[-1] == n + 1 and n in got)

    # (b) legacy migration crash between 'write archive' and 'rename original'
    d2 = tmp()
    s3 = BoundedJsonl(d2 / "t.jsonl", max_bytes=2000)
    s3.path.write_bytes(b"".join(json.dumps({"seq": i, "pad": "x" * 50}).encode() + b"\n" for i in range(600)))   # >> 4 x max
    n_calls = {"n": 0}
    real = os.replace

    def second_dies(a, b):
        n_calls["n"] += 1
        if n_calls["n"] == 2:                  # 1st = archive replace, 2nd = legacy rename
            raise _Crash()
        return real(a, b)

    crashed = False
    with patched(os, "replace", second_dies):
        try:
            s3.append({"seq": 600, "pad": "x" * 50})
        except _Crash:
            crashed = True
    readable = seqs(BoundedJsonl(d2 / "t.jsonl", max_bytes=2000).tail_entries(10**6))
    check("30 legacy-migration crash mid-way: every entry still readable and the newest is never hidden "
          "(a transient duplicate of the archive tail is accepted; hiding data is not)",
          crashed and readable[-1] == 600 and set(range(601)) <= set(readable))
    r = BoundedJsonl(d2 / "t.jsonl", max_bytes=2000).append({"seq": 601, "pad": "x" * 50})
    after = BoundedJsonl(d2 / "t.jsonl", max_bytes=2000)
    got = seqs(after.tail_entries(10**6))
    check("31 next append completes the migration: bounded, no duplicates, legacy file preserved",
          r.ok and len(got) == len(set(got)) and got[-1] == 601 and total_bytes(after) <= 2 * 2000 + 200
          and len(list(d2.glob("t.legacy-*.jsonl"))) == 1)

    # (c) rotation attempted while a reader holds a snapshot
    d3 = tmp()
    s4 = BoundedJsonl(d3 / "t.jsonl", max_bytes=2500)
    fill(s4, 40)
    it = s4.iter_entries_reverse()
    seen = [next(it)["seq"] for _ in range(5)]
    for i in range(40, 140):                                           # crosses the threshold while the iterator is open
        assert s4.append({"seq": i, "pad": "x" * 40}).ok
    rest = []
    try:
        rest = [e["seq"] for e in it]
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    got_all = seen + rest
    check("32 rotation attempted during a read: reader finishes with a consistent snapshot, no exception",
          ok and got_all == sorted(got_all, reverse=True) and len(got_all) == len(set(got_all)))
    it.close()
    s4._rotation_blocked_until = 0.0
    s4.append({"seq": 140, "pad": "x"})
    degraded_bound = (1 + bj.LEGACY_FACTOR) * 2500 + 300       # a delayed rotation may archive an overshot file
    check("33 after the reader closes, the next append rotates and the total is bounded again",
          s4.segment_path.exists() and cur_size(s4) < 2500 and total_bytes(s4) <= degraded_bound, f"{total_bytes(s4)} bytes")


# --------------------------------------------------------------------------- F. legacy migration
def test_legacy_migration():
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=4000)
    original = b"".join(json.dumps({"seq": i, "pad": "z" * 70}).encode() + b"\n" for i in range(2000))     # ~190 KB >> 16 KB
    s.path.write_bytes(original)
    digest = hashlib.sha256(original).hexdigest()
    r = s.append({"seq": 2000, "pad": "z"})
    legacy = list(d.glob("t.legacy-*.jsonl"))
    check("34 oversized legacy log is migrated on the first append", r.ok and r.rotated and len(legacy) == 1)
    lb = legacy[0].read_bytes() if legacy else b""
    check("35 the full original is preserved byte-for-byte in the legacy file",
          lb.startswith(original) and hashlib.sha256(lb[:len(original)]).hexdigest() == digest)
    seg = seqs([json.loads(l) for l in s.segment_path.read_bytes().splitlines() if l.strip()])
    check("36 the archive holds the newest max_bytes as complete lines", seg and seg[-1] == 2000 and seg == list(range(seg[0], 2001))
          and s.segment_path.stat().st_size <= s.max_bytes + 200, f"{len(seg)} entries")
    check("37 active set is bounded after migration", total_bytes(s) <= 2 * 4000 + 200, f"{total_bytes(s)} bytes")
    s.clear()
    check("38 clear() removes current + archive but never the legacy file",
          not s.path.exists() and not s.segment_path.exists() and legacy[0].exists())


# --------------------------------------------------------------------------- G. multi-process concurrency
WORKER = (
    "import sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from bounded_jsonl import BoundedJsonl\n"
    "path, wid, n, maxb, pad = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])\n"
    "s = BoundedJsonl(path, max_bytes=maxb)\n"
    "bad = 0\n"
    "for i in range(n):\n"
    "    if not s.append({'w': wid, 'i': i, 'pad': 'p' * pad}).ok: bad += 1\n"
    "print(bad)\n"
)


def run_workers(path, procs, n, maxb, pad):
    ps = [subprocess.Popen([sys.executable, "-I", "-c", WORKER, str(TOOLS), str(path), str(w), str(n), str(maxb), str(pad)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for w in range(procs)]
    fails = 0
    for p in ps:
        out, _err = p.communicate(timeout=180)
        fails += int(out.strip() or 999) if p.returncode == 0 else 999
    return fails


def load_all_lines(store):
    lines = []
    for p in (store.segment_path, store.path):
        if p.exists():
            lines += [l for l in p.read_bytes().split(b"\n") if l.strip()]
    return lines


def test_concurrency():
    procs, n = 6, 150
    d = tmp()
    s = BoundedJsonl(d / "t.jsonl", max_bytes=50 * 10**6)
    fails = run_workers(s.path, procs, n, 50 * 10**6, 200)
    lines = load_all_lines(s)
    bad = 0
    keys = []
    for l in lines:
        try:
            o = json.loads(l); keys.append((o["w"], o["i"]))
        except Exception:  # noqa: BLE001
            bad += 1
    check("39 6 real processes x 150 appends (no rotation): every entry stored, 0 torn lines, 0 duplicates",
          fails == 0 and bad == 0 and len(keys) == procs * n and len(set(keys)) == procs * n,
          f"stored {len(keys)}/{procs * n}, torn {bad}, failed appends {fails}")

    d2 = tmp()
    s2 = BoundedJsonl(d2 / "t.jsonl", max_bytes=30_000)
    fails = run_workers(s2.path, procs, 200, 30_000, 200)
    lines = load_all_lines(s2)
    bad, keys = 0, []
    for l in lines:
        try:
            o = json.loads(l); keys.append((o["w"], o["i"]))
        except Exception:  # noqa: BLE001
            bad += 1
    per = {}
    for w, i in keys:
        per.setdefault(w, []).append(i)
    # Retention keeps only the newest entries overall, so a worker that finished early may be rotated out
    # entirely. What must hold: every worker still present keeps a gap-free suffix ending at its last append.
    suffix_ok = bool(per) and all(sorted(v) == list(range(min(v), 200)) for v in per.values())
    check("40 6 real processes x 200 appends WITH rotation: every append ok, 0 torn lines, 0 duplicates",
          fails == 0 and bad == 0 and len(keys) == len(set(keys)), f"retained {len(keys)}, torn {bad}, failed {fails}")
    check("41 under concurrent rotation each surviving writer keeps a gap-free newest suffix (nothing lost mid-window)", suffix_ok,
          {w: (min(v), max(v)) for w, v in sorted(per.items())}.__repr__()[:90])
    check("42 concurrent rotation keeps the total bounded", total_bytes(s2) <= 2 * 30_000 + 400, f"{total_bytes(s2)} bytes")


# --------------------------------------------------------------------------- H. adopters
def test_adopters():
    from invocation_tracker import InvocationTracker
    root = tmp()
    t = InvocationTracker(project_root=root)
    t._store.max_bytes = 3000
    t.record("validate_return_envelope", {"task_id": "a"})
    i = 0
    while not t._store.segment_path.exists() and i < 200:       # fill until exactly the first rotation happened
        t.record("check_qa_retry_limit", {"i": i, "pad": "x" * 40}); i += 1
    for j in range(3):
        t.record("check_qa_retry_limit", {"i": i + j, "pad": "x"})
    first_in_archive = b"validate_return_envelope" in t._store.segment_path.read_bytes()
    check("43 tracker: the log rotated and the first record now lives only in the archive segment",
          first_in_archive and b"validate_return_envelope" not in t.log_path.read_bytes() and cur_size(t._store) < 3000)
    audit = t.audit_invocations(["validate_return_envelope", "check_qa_retry_limit"], since_seconds=300)
    check("44 audit_invocations finds a helper that is only in the archive segment (reader spans the boundary)",
          audit["verdict"] == "complete" and not audit["missing"], str(audit["invoked"]))
    miss = t.audit_invocations(["never_called_helper"], since_seconds=300)
    check("45 audit still reports a genuinely missing helper (negative control)", miss["verdict"] == "incomplete" and miss["missing"] == ["never_called_helper"])
    stats = t.stats()
    check("46 stats() keeps its keys and adds retention info", {"total_entries", "unique_helpers", "invocations_by_helper", "log_path", "exists", "retention"} <= set(stats)
          and stats["retention"]["segment_bytes"] is not None)
    with open(t.log_path, "a", encoding="utf-8") as f:                        # legacy-style direct write must stay visible
        f.write(json.dumps({"helper": "direct_write", "timestamp": datetime.now(timezone.utc).isoformat()}) + "\n")
    check("47 a direct append to log_path (old writers/tests) is still read", "direct_write" in [e["helper"] for e in t._read_log()])
    t.clear()
    check("48 clear() empties the tracker", t._read_log() == [] and not t._store.exists())

    # cutoff is fixed before the read: a slow (cold) read must not shift the window
    t2 = InvocationTracker(project_root=tmp())
    captured = {}
    real = t2._store.recent_entries

    def slow(cutoff, *a, **k):
        captured["cutoff"] = cutoff
        time.sleep(0.4)
        return real(cutoff, *a, **k)

    t2._store.recent_entries = slow
    start = datetime.now(timezone.utc)
    t2.get_recent(since_seconds=30)
    drift = (captured["cutoff"] - (start - timedelta(seconds=30))).total_seconds()
    check("49 get_recent computes its window BEFORE the (possibly slow) read", abs(drift) < 0.2, f"drift {drift:.3f}s")

    import skills_registry as sr
    p = tmp() / "usage.jsonl"
    old_env = os.environ.get("ATLAS_SKILLS_USAGE_LOG_PATH")
    os.environ["ATLAS_SKILLS_USAGE_LOG_PATH"] = str(p)
    try:
        sr._usage_store(p).max_bytes = 2500
        for i in range(80):
            sr._log_usage("get_skill", {"skill_id": f"s{i % 5}", "found": True})
        sr._log_usage("get_skill", {"bad": object()})                          # must not raise
        stats = sr.usage_stats(log_path=p)
        check("50 skills usage log is bounded and usage_stats reads current + archive",
              sr._usage_store(p).segment_path.exists() and total_bytes(sr._usage_store(p)) <= 2 * 2500 + 300
              and 0 < stats["total_invocations"] <= 80 and stats["by_event"].get("get_skill") == stats["total_invocations"],
              f"{stats['total_invocations']} retained of 80")
    finally:
        if old_env is None:
            os.environ.pop("ATLAS_SKILLS_USAGE_LOG_PATH", None)
        else:
            os.environ["ATLAS_SKILLS_USAGE_LOG_PATH"] = old_env


# --------------------------------------------------------------------------- I. source guards
def test_source_guards():
    src = (TOOLS / "bounded_jsonl.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    banned = ("subprocess", "socket", "urllib", "requests", "eval(", "exec(", "os.system", "shell=True", "expanduser", "pickle")
    hit = [b for b in banned if b in code]
    check("51 helper has no process/network/eval/pickle/home-dir access", not hit, str(hit))
    check("52 helper never deletes a legacy file", ".legacy-" in src and "unlink" in src and
          "legacy" not in "".join(l for l in src.splitlines() if "unlink" in l))


def main():
    print("=" * 60)
    print("Bloque F39 -- Telemetry retention")
    print(f"Project  : {PROJECT_ROOT}")
    print("=" * 60)
    for fn in (test_bound_and_rotation, test_reads, test_damaged_data, test_failures, test_crash_and_concurrent_read,
               test_legacy_migration, test_concurrency, test_adopters, test_source_guards):
        print(f"\n-- {fn.__name__} --")
        fn()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nTotal: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}\n")
    print("RESULTADO: FAIL" if FAIL_COUNT else "RESULTADO: PASS")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()
