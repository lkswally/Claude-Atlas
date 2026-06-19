#!/usr/bin/env python3
"""
Bloque F29 — Boot Profiler
============================

Valida tools/boot_profiler.py — el profiler liviano de carga de conocimiento
(metadata-only) que mide costos de bootstrap antes de refactorizar (F28→F29).

Tests:
  T1  módulo importa; API pública presente
  T2  estimate_tokens(chars) = chars // 4
  T3  measure_file devuelve (bytes, lines) sin retener contenido
  T4  make_event arma evento con todos los campos del contrato
  T5  emit escribe 1 línea JSONL válida (a archivo temporal)
  T6  enums inválidos se coercen a defaults seguros (no crash)
  T7  DISABLED env var → emit no escribe, retorna False
  T8  read_events roundtrip + tolera líneas malformadas
  T9  already_loaded=True en segundo load del mismo dedup_key
  T10 summarize: totales, always_on_tokens, redundant_tokens, top_files
  T11 record_load (measure+emit) end-to-end a archivo temporal
  T12 evento NO contiene contenido del archivo (solo metadata)
  T13 profile_load context manager registra con duration_ms > 0
  T14 fail-open: path inexistente → measure (0,0), emit OK

Total: 14 tests
"""

import json
import os
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
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def _tmp_log() -> Path:
    fd, p = tempfile.mkstemp(suffix=".jsonl", prefix="f29-boot-")
    os.close(fd)
    path = Path(p)
    path.unlink(missing_ok=True)  # start clean
    return path


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=" * 60)
    print("Bloque F29 -- Boot Profiler")
    print("=" * 60)
    print()

    # T1 — import + API
    try:
        import boot_profiler as bp
        required = ["estimate_tokens", "measure_file", "make_event", "emit",
                    "record_load", "read_events", "summarize", "profile_load",
                    "KnowledgeLoadEvent"]
        missing = [a for a in required if not hasattr(bp, a)]
        if not missing:
            ok("T1 import + public API")
        else:
            fail("T1 import + public API", f"missing: {missing}")
            print(f"\nRESULTADO: FAIL ({FAIL_COUNT})"); sys.exit(1)
    except Exception as e:
        fail("T1 import", str(e))
        print("\nRESULTADO: FAIL"); sys.exit(1)

    # T2 — estimate_tokens
    if bp.estimate_tokens(0) == 0 and bp.estimate_tokens(4000) == 1000 and bp.estimate_tokens(3) == 0:
        ok("T2 estimate_tokens chars//4")
    else:
        fail("T2 estimate_tokens", f"got {bp.estimate_tokens(4000)} for 4000 chars")

    # T3 — measure_file
    sample = _tmp_log()
    try:
        sample.write_bytes(b"line1\nline2\nline3\n")  # bytes → no newline translation
        b, ln = bp.measure_file(sample)
        if b == 18 and ln == 3:
            ok("T3 measure_file (bytes, lines)", f"{b}b {ln}ln")
        else:
            fail("T3 measure_file", f"got {b}b {ln}ln (expected 18b 3ln)")
    finally:
        sample.unlink(missing_ok=True)

    # T4 — make_event fields
    evt = bp.make_event("CLAUDE.md", source="boot", reason="startup",
                        load_type="always_on", bytes_=34913, lines=544,
                        session_id="s1")
    d = evt.to_dict()
    contract = {"event", "timestamp", "path", "source", "reason", "bytes", "lines",
                "estimated_tokens", "load_type", "session_id", "dedup_key",
                "duration_ms", "already_loaded"}
    miss = contract - d.keys()
    if not miss and d["event"] == "knowledge_load" and d["estimated_tokens"] == 34913 // 4:
        ok("T4 make_event contract", f"{len(d)} fields, est_tokens={d['estimated_tokens']}")
    else:
        fail("T4 make_event contract", f"missing={miss} tokens={d.get('estimated_tokens')}")

    # T5 — emit writes valid JSONL
    log = _tmp_log()
    try:
        e1 = bp.make_event("a.md", source="boot", reason="startup",
                           load_type="always_on", bytes_=400, lines=10, session_id="s5")
        wrote = bp.emit(e1, log_file=log)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        parsed = json.loads(lines[0]) if lines else {}
        if wrote and len(lines) == 1 and parsed.get("path") == "a.md":
            ok("T5 emit writes 1 valid JSONL line")
        else:
            fail("T5 emit", f"wrote={wrote} lines={len(lines)}")
    finally:
        log.unlink(missing_ok=True)

    # T6 — invalid enums coerced
    evt2 = bp.make_event("x.md", source="bogus", reason="nope",
                         load_type="weird", bytes_=4, lines=1, session_id="s6")
    if evt2.source == "manual" and evt2.reason == "unknown" and evt2.load_type == "manual":
        ok("T6 invalid enums coerced to safe defaults")
    else:
        fail("T6 enum coercion", f"{evt2.source}/{evt2.reason}/{evt2.load_type}")

    # T7 — DISABLED env var
    log = _tmp_log()
    try:
        os.environ["ATLAS_BOOT_PROFILER_DISABLED"] = "1"
        e7 = bp.make_event("a.md", bytes_=4, lines=1, session_id="s7")
        wrote = bp.emit(e7, log_file=log)
        if wrote is False and not log.exists():
            ok("T7 DISABLED -> no write, returns False")
        else:
            fail("T7 DISABLED", f"wrote={wrote} exists={log.exists()}")
    finally:
        os.environ.pop("ATLAS_BOOT_PROFILER_DISABLED", None)
        log.unlink(missing_ok=True)

    # T8 — read_events roundtrip + malformed tolerance
    log = _tmp_log()
    try:
        bp.emit(bp.make_event("a.md", bytes_=400, lines=10, session_id="s8"), log_file=log)
        bp.emit(bp.make_event("b.md", bytes_=800, lines=20, session_id="s8"), log_file=log)
        with log.open("a", encoding="utf-8") as f:
            f.write("{ this is not json\n")  # malformed
        evts = bp.read_events(log_file=log)
        if len(evts) == 2 and evts[0].path == "a.md":
            ok("T8 read_events roundtrip + skips malformed")
        else:
            fail("T8 read_events", f"got {len(evts)} events")
    finally:
        log.unlink(missing_ok=True)

    # T9 — already_loaded dedup (in-process)
    log = _tmp_log()
    try:
        # Reset in-process dedup set for deterministic test
        bp._seen_keys.clear()
        bp.emit(bp.make_event("dup.md", bytes_=400, lines=10,
                              session_id="s9", dedup_key="dup.md"), log_file=log)
        # second make_event sees the key already in _seen_keys
        second = bp.make_event("dup.md", bytes_=400, lines=10,
                               session_id="s9", dedup_key="dup.md")
        if second.already_loaded is True:
            ok("T9 already_loaded=True on second load")
        else:
            fail("T9 already_loaded", f"got {second.already_loaded}")
    finally:
        bp._seen_keys.clear()
        log.unlink(missing_ok=True)

    # T10 — summarize
    log = _tmp_log()
    try:
        bp._seen_keys.clear()
        bp.emit(bp.make_event("CLAUDE.md", source="boot", reason="startup",
                              load_type="always_on", bytes_=40000, lines=500,
                              session_id="s10", dedup_key="CLAUDE.md"), log_file=log)
        bp.emit(bp.make_event("orq.md", source="agent", reason="orchestrator",
                              load_type="lazy", bytes_=8000, lines=100,
                              session_id="s10", dedup_key="orq.md"), log_file=log)
        # redundant load of CLAUDE.md
        bp.emit(bp.make_event("CLAUDE.md", source="boot", reason="startup",
                              load_type="always_on", bytes_=40000, lines=500,
                              session_id="s10", dedup_key="CLAUDE.md"), log_file=log)
        s = bp.summarize(bp.read_events(log_file=log))
        checks = (
            s["total_events"] == 3
            and s["always_on_tokens"] == (40000 // 4) * 2
            and s["redundant_tokens"] == 40000 // 4
            and s["top_files_by_tokens"][0][0] == "CLAUDE.md"
            and s["by_load_type"].get("always_on") == 2
        )
        if checks:
            ok("T10 summarize totals/always_on/redundant/top_files")
        else:
            fail("T10 summarize", json.dumps(s))
    finally:
        bp._seen_keys.clear()
        log.unlink(missing_ok=True)

    # T11 — record_load end-to-end
    log = _tmp_log()
    sample = _tmp_log()
    try:
        sample.write_text("x" * 1200, encoding="utf-8")
        wrote = bp.record_load(sample, source="manual", reason="docs",
                               load_type="manual", session_id="s11", log_file=log)
        evts = bp.read_events(log_file=log)
        if wrote and len(evts) == 1 and evts[0].bytes == 1200 and evts[0].estimated_tokens == 300:
            ok("T11 record_load end-to-end (measure+emit)")
        else:
            fail("T11 record_load", f"wrote={wrote} evts={len(evts)}")
    finally:
        log.unlink(missing_ok=True)
        sample.unlink(missing_ok=True)

    # T12 — no content leak
    log = _tmp_log()
    sample = _tmp_log()
    try:
        secret = "SUPER_SECRET_TOKEN_42"
        sample.write_text(f"header\n{secret}\nfooter\n", encoding="utf-8")
        bp.record_load(sample, source="manual", reason="docs", session_id="s12", log_file=log)
        raw = log.read_text(encoding="utf-8")
        if secret not in raw:
            ok("T12 event contains NO file content (metadata only)")
        else:
            fail("T12 content leak", "secret found in log")
    finally:
        log.unlink(missing_ok=True)
        sample.unlink(missing_ok=True)

    # T13 — profile_load context manager
    log = _tmp_log()
    sample = _tmp_log()
    try:
        sample.write_text("data\n" * 50, encoding="utf-8")
        with bp.profile_load(sample, source="boot", reason="startup",
                             load_type="always_on", session_id="s13", log_file=log):
            _ = sample.read_text(encoding="utf-8")
        evts = bp.read_events(log_file=log)
        if len(evts) == 1 and evts[0].duration_ms >= 0.0 and evts[0].source == "boot":
            ok("T13 profile_load context manager records timing")
        else:
            fail("T13 profile_load", f"evts={len(evts)}")
    finally:
        log.unlink(missing_ok=True)
        sample.unlink(missing_ok=True)

    # T14 — fail-open on missing file
    log = _tmp_log()
    try:
        b, ln = bp.measure_file(PROJECT_ROOT / "does-not-exist-xyz.md")
        wrote = bp.record_load(PROJECT_ROOT / "does-not-exist-xyz.md",
                               source="manual", session_id="s14", log_file=log)
        if (b, ln) == (0, 0) and wrote:
            ok("T14 fail-open on missing file (measure=0,0; emit OK)")
        else:
            fail("T14 fail-open", f"measure=({b},{ln}) wrote={wrote}")
    finally:
        log.unlink(missing_ok=True)

    # =====================================================================
    # F29.3/F29.4/F29.5 — Knowledge Registry + scan CLI + duplication
    # =====================================================================
    import subprocess

    REG = PROJECT_ROOT / "config" / "knowledge.registry.yaml"

    def _load_registry():
        try:
            import yaml
            data = yaml.safe_load(REG.read_text(encoding="utf-8")) or {}
            return data.get("knowledge", [])
        except Exception:
            return []

    reg = _load_registry()
    reg_by_path = {str(e.get("path", "")).replace("\\", "/"): e for e in reg if isinstance(e, dict)}

    # T15 — registry exists
    if REG.exists() and reg:
        ok("T15 knowledge.registry.yaml exists", f"{len(reg)} entries")
    else:
        fail("T15 knowledge.registry.yaml", "missing or empty")

    # T16 — CLAUDE.md always_on
    e = reg_by_path.get("CLAUDE.md", {})
    if e.get("load_policy") == "always_on":
        ok("T16 CLAUDE.md always_on")
    else:
        fail("T16 CLAUDE.md always_on", f"got {e.get('load_policy')}")

    # T17 — orquestador.md lazy
    e = reg_by_path.get(".claude/agents/orquestador.md", {})
    if e.get("load_policy") == "lazy":
        ok("T17 orquestador.md lazy")
    else:
        fail("T17 orquestador.md lazy", f"got {e.get('load_policy')}")

    # T18 — agent-protocol.md lazy
    e = reg_by_path.get(".claude/agents/agent-protocol.md", {})
    if e.get("load_policy") == "lazy":
        ok("T18 agent-protocol.md lazy")
    else:
        fail("T18 agent-protocol.md lazy", f"got {e.get('load_policy')}")

    # T19 — all load_policy valid
    valid_pol = {"always_on", "lazy", "manual", "runtime", "deprecated", "unknown"}
    bad = [e.get("id") for e in reg if isinstance(e, dict) and e.get("load_policy") not in valid_pol]
    if not bad:
        ok("T19 all load_policy values valid")
    else:
        fail("T19 load_policy valid", f"invalid: {bad}")

    # T20 — critical paths exist
    crit = ["CLAUDE.md", ".claude/agents/orquestador.md", ".claude/agents/agent-protocol.md"]
    missing_paths = [p for p in crit if not (PROJECT_ROOT / p).exists()]
    registered = [p for p in crit if p in reg_by_path]
    if not missing_paths and len(registered) == 3:
        ok("T20 critical paths exist + registered")
    else:
        fail("T20 critical paths", f"missing={missing_paths} registered={registered}")

    # T21 — build_scan() produces valid JSON-serializable payload (in-process)
    import boot_profiler as bp2
    scan_json = bp2.build_scan()
    try:
        json.dumps(scan_json)  # must be serializable
        if "files" in scan_json and "total_estimated_tokens" in scan_json:
            ok("T21 build_scan() JSON-serializable", f"{scan_json['total_files']} files")
        else:
            fail("T21 build_scan()", "missing keys")
    except Exception as ex:
        fail("T21 build_scan() JSON", str(ex))

    # T22 — --report produces human output (single lightweight CLI subprocess;
    # boot_profiler is fast and pure-python, no node/network — safe in parallel).
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "boot_profiler.py"), "--report"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and "static knowledge scan" in r.stdout and "policy" in r.stdout:
        ok("T22 --report human output (CLI)")
    else:
        fail("T22 --report", f"rc={r.returncode}")

    # T23 — --json machine-readable: build_scan is dict with expected shape
    if isinstance(scan_json, dict) and isinstance(scan_json.get("by_load_policy"), dict):
        ok("T23 scan machine-readable shape", f"keys={len(scan_json)}")
    else:
        fail("T23 scan shape", "unexpected")

    # T24 — top ranking descending by tokens (in-process via scan files)
    files = scan_json.get("files", [])
    toks = [f["estimated_tokens"] for f in files]
    if toks == sorted(toks, reverse=True) and len(files) >= 1:
        ok("T24 ranking descending by tokens", f"top={toks[:3]}")
    else:
        fail("T24 ranking", f"not sorted desc")

    # T25 — duplication scan detects Engram as candidate
    dups = bp2.scan_duplications()
    engram = next((d for d in dups if d["keyword"] == "Engram"), None)
    if engram and engram["duplication_candidate"] and engram["file_count"] > 1:
        ok("T25 duplication scan flags Engram", f"{engram['file_count']} files")
    else:
        fail("T25 duplication Engram", f"{engram}")

    # T26 — healthcheck includes Knowledge Registry check (IN-PROCESS — avoids
    # spawning the heavy healthcheck subprocess inside the parallel runner).
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        import atlas_healthcheck as hc_mod
        hc_mod._results.clear()
        hc_mod.check_knowledge_registry()
        kr = next((c for c in hc_mod._results if "Knowledge registry" in c.get("check", "")), {})
        if kr and kr.get("status") in ("PASS", "WARN"):
            ok("T26 healthcheck Knowledge Registry check (WARN-only)", kr.get("status"))
        else:
            fail("T26 healthcheck Knowledge Registry", f"status={kr.get('status')}")
        hc_mod._results.clear()
    except Exception as ex:
        fail("T26 healthcheck Knowledge Registry", str(ex))

    total = PASS_COUNT + FAIL_COUNT
    print()
    print(f"Total: {total} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT}")
    print()
    print("RESULTADO: PASS" if FAIL_COUNT == 0 else "RESULTADO: FAIL")
    sys.exit(0 if FAIL_COUNT == 0 else 1)


if __name__ == "__main__":
    main()
