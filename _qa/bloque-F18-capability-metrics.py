#!/usr/bin/env python3
"""
Bloque F18 — Capability Runtime Metrics Tests
=============================================

Verifica que el sistema de observabilidad de capability resolution funciona:
events.py, router emit integration, metrics reader, JSONL correctness.

Tests:
  T1  events.py importa sin error (make_event, emit, read_events)
  T2  make_event produce CapabilityEvent con campos correctos
  T3  emit() escribe evento al archivo JSONL (temp file)
  T4  ATLAS_CAPABILITY_EVENTS_DISABLED=1 → emit devuelve False, no escribe
  T5  read_events() lee CapabilityEvents del JSONL
  T6  read_events() tolera líneas malformadas sin lanzar excepción
  T7  resolve_capability emite evento por defecto (emit=True)
  T8  resolve_capability NO emite si emit=False
  T9  capability_metrics.py importa sin error
  T10 load_events() retorna [] si el archivo no existe
  T11 compute_metrics() con eventos calcula correctamente total + critical_status
  T12 compute_metrics() con lista vacía retorna estructura válida (no crash)
  T13 fallback_count se incrementa cuando fallback_used=True en eventos
  T14 unresolved incluye capabilities con UNAVAILABLE

Salida:
  [PASS] / [FAIL] por test
  Resumen al final

Exit code: 0 = todo PASS | 1 = al menos un FAIL
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_results: list[tuple[str, bool, str]] = []


def PASS(name: str, detail: str = "") -> None:
    _results.append((name, True, detail))
    print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))


def FAIL(name: str, detail: str = "") -> None:
    _results.append((name, False, detail))
    print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t1_events_imports() -> None:
    try:
        from core.capabilities.events import make_event, emit, read_events, CapabilityEvent
        PASS("T1 events.py importa", "make_event, emit, read_events OK")
    except Exception as e:
        FAIL("T1 events.py importa", str(e))


def t2_make_event_fields() -> None:
    try:
        from core.capabilities.events import make_event
        evt = make_event(
            capability="browser",
            provider_selected="playwright",
            provider_status="LIVE",
            fallback_used=False,
            action="use",
            requested_by="test-runner",
        )
        assert evt.capability == "browser", f"capability={evt.capability}"
        assert evt.provider_selected == "playwright", f"provider={evt.provider_selected}"
        assert evt.provider_status == "LIVE", f"status={evt.provider_status}"
        assert evt.resolution_ok is True, f"resolution_ok={evt.resolution_ok}"
        assert evt.requested_by == "test-runner"
        assert evt.timestamp.endswith("+00:00") or "Z" in evt.timestamp or "T" in evt.timestamp
        PASS("T2 make_event campos", f"timestamp={evt.timestamp[:19]}")
    except Exception as e:
        FAIL("T2 make_event campos", str(e))


def t3_emit_writes_jsonl() -> None:
    try:
        from core.capabilities.events import make_event, emit
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            evt = make_event(
                capability="memory",
                provider_selected="engram",
                provider_status="LIVE",
                fallback_used=False,
                action="use",
                requested_by="t3",
            )
            result = emit(evt, events_file=events_file)
            assert result is True, f"emit returned {result}"
            assert events_file.exists(), "JSONL file not created"
            lines = events_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1, f"expected 1 line, got {len(lines)}"
            d = json.loads(lines[0])
            assert d["capability"] == "memory"
            assert d["provider_selected"] == "engram"
            PASS("T3 emit() escribe JSONL", "1 línea válida escrita")
    except Exception as e:
        FAIL("T3 emit() escribe JSONL", str(e))


def t4_disabled_env_var() -> None:
    original = os.environ.get("ATLAS_CAPABILITY_EVENTS_DISABLED")
    try:
        os.environ["ATLAS_CAPABILITY_EVENTS_DISABLED"] = "1"
        from core.capabilities.events import make_event, emit
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            evt = make_event(
                capability="browser",
                provider_selected="playwright",
                provider_status="LIVE",
                fallback_used=False,
                action="use",
                requested_by="t4",
            )
            result = emit(evt, events_file=events_file)
            assert result is False, f"emit should return False when disabled, got {result}"
            assert not events_file.exists(), "File should not be created when disabled"
        PASS("T4 DISABLED env var", "emit() retorna False, no crea archivo")
    except Exception as e:
        FAIL("T4 DISABLED env var", str(e))
    finally:
        if original is None:
            os.environ.pop("ATLAS_CAPABILITY_EVENTS_DISABLED", None)
        else:
            os.environ["ATLAS_CAPABILITY_EVENTS_DISABLED"] = original


def t5_read_events_roundtrip() -> None:
    try:
        from core.capabilities.events import make_event, emit, read_events
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            for cap, prov, status in [
                ("memory", "engram", "LIVE"),
                ("browser", "playwright", "LIVE"),
                ("documentation", "context7", "CONFIG_ONLY"),
            ]:
                evt = make_event(
                    capability=cap,
                    provider_selected=prov,
                    provider_status=status,
                    fallback_used=False,
                    action="use",
                    requested_by="t5",
                )
                emit(evt, events_file=events_file)

            events = read_events(events_file=events_file)
            assert len(events) == 3, f"expected 3, got {len(events)}"
            assert events[0].capability == "memory"
            assert events[2].capability == "documentation"
            PASS("T5 read_events roundtrip", f"{len(events)} eventos leídos OK")
    except Exception as e:
        FAIL("T5 read_events roundtrip", str(e))


def t6_read_events_tolerates_bad_lines() -> None:
    try:
        from core.capabilities.events import read_events
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            events_file.write_text(
                '{"capability":"memory","requested_by":"t6","provider_selected":"engram",'
                '"provider_status":"LIVE","fallback_used":false,"resolution_ok":true,'
                '"action":"use","reason":"","metadata":{},"timestamp":"2026-01-01T00:00:00+00:00"}\n'
                'NOT VALID JSON\n'
                '{"capability":"browser","requested_by":"t6","provider_selected":"playwright",'
                '"provider_status":"LIVE","fallback_used":false,"resolution_ok":true,'
                '"action":"use","reason":"","metadata":{},"timestamp":"2026-01-01T00:01:00+00:00"}\n',
                encoding="utf-8",
            )
            events = read_events(events_file=events_file)
            assert len(events) == 2, f"expected 2 valid events, got {len(events)}"
            PASS("T6 tolerates bad JSONL", "2 válidas de 3 líneas (1 malformada ignorada)")
    except Exception as e:
        FAIL("T6 tolerates bad JSONL", str(e))


def t7_resolve_emits_event() -> None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            from core.capabilities.router import resolve_capability
            resolve_capability(
                "memory",
                requested_by="t7",
                emit=True,
                _events_file=events_file,
            )
            assert events_file.exists(), "No event file created"
            lines = events_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) >= 1, f"expected >=1 event, got {len(lines)}"
            d = json.loads(lines[0])
            assert d.get("capability") == "memory"
            PASS("T7 resolve emite evento", f"capability=memory OK")
    except Exception as e:
        FAIL("T7 resolve emite evento", str(e))


def t8_resolve_no_emit() -> None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "capability-events.jsonl"
            from core.capabilities.router import resolve_capability
            resolve_capability(
                "browser",
                requested_by="t8",
                emit=False,
                _events_file=events_file,
            )
            assert not events_file.exists(), "File should NOT be created when emit=False"
            PASS("T8 emit=False no escribe", "archivo no creado")
    except Exception as e:
        FAIL("T8 emit=False no escribe", str(e))


def t9_metrics_imports() -> None:
    metrics_path = PROJECT_ROOT / "tools" / "capability_metrics.py"
    if not metrics_path.exists():
        FAIL("T9 capability_metrics.py importa", "archivo no encontrado")
        return
    try:
        spec = importlib.util.spec_from_file_location("capability_metrics", metrics_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "load_events")
        assert hasattr(mod, "compute_metrics")
        assert hasattr(mod, "print_summary")
        PASS("T9 capability_metrics.py importa", "load_events, compute_metrics, print_summary OK")
    except Exception as e:
        FAIL("T9 capability_metrics.py importa", str(e))


def t10_load_events_no_file() -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "capability_metrics", PROJECT_ROOT / "tools" / "capability_metrics.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        result = mod.load_events(Path("/nonexistent/path/capability-events.jsonl"))
        assert result == [], f"expected [], got {result}"
        PASS("T10 load_events no file → []", "retorna lista vacía sin crash")
    except Exception as e:
        FAIL("T10 load_events no file → []", str(e))


def t11_compute_metrics_correct() -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "capability_metrics", PROJECT_ROOT / "tools" / "capability_metrics.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        events = [
            {"capability": "memory", "provider_selected": "engram", "provider_status": "LIVE",
             "fallback_used": False, "resolution_ok": True, "action": "use"},
            {"capability": "browser", "provider_selected": "playwright", "provider_status": "LIVE",
             "fallback_used": False, "resolution_ok": True, "action": "use"},
            {"capability": "memory", "provider_selected": "engram", "provider_status": "LIVE",
             "fallback_used": False, "resolution_ok": True, "action": "use"},
            {"capability": "documentation", "provider_selected": "context7", "provider_status": "CONFIG_ONLY",
             "fallback_used": False, "resolution_ok": True, "action": "restart_session"},
        ]
        m = mod.compute_metrics(events)
        assert m["total_resolutions"] == 4, f"total={m['total_resolutions']}"
        assert m["by_capability"]["memory"] == 2, f"memory count={m['by_capability']['memory']}"
        assert m["critical_status"]["memory"] == "LIVE"
        assert m["critical_status"]["browser"] == "LIVE"
        assert m["resolution_ok_rate"] == 1.0, f"rate={m['resolution_ok_rate']}"
        PASS("T11 compute_metrics correcto", f"total=4, memory=2, ok_rate=100%")
    except Exception as e:
        FAIL("T11 compute_metrics correcto", str(e))


def t12_compute_metrics_empty() -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "capability_metrics", PROJECT_ROOT / "tools" / "capability_metrics.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        m = mod.compute_metrics([])
        assert m["total_resolutions"] == 0
        assert isinstance(m["critical_status"], dict)
        assert m["resolution_ok_rate"] is None
        assert m["unresolved"] == []
        PASS("T12 compute_metrics vacío", "estructura válida sin crash")
    except Exception as e:
        FAIL("T12 compute_metrics vacío", str(e))


def t13_fallback_count() -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "capability_metrics", PROJECT_ROOT / "tools" / "capability_metrics.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        events = [
            {"capability": "browser", "provider_selected": "claude_in_chrome",
             "provider_status": "CONFIG_ONLY", "fallback_used": True,
             "resolution_ok": True, "action": "restart_session"},
            {"capability": "browser", "provider_selected": "playwright",
             "provider_status": "LIVE", "fallback_used": False,
             "resolution_ok": True, "action": "use"},
        ]
        m = mod.compute_metrics(events)
        assert m["fallback_count"] == 1, f"fallback_count={m['fallback_count']}"
        PASS("T13 fallback_count", "1 evento con fallback_used=True contado OK")
    except Exception as e:
        FAIL("T13 fallback_count", str(e))


def t14_unresolved_list() -> None:
    try:
        spec = importlib.util.spec_from_file_location(
            "capability_metrics", PROJECT_ROOT / "tools" / "capability_metrics.py"
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        events = [
            {"capability": "memory", "provider_selected": "engram",
             "provider_status": "LIVE", "fallback_used": False,
             "resolution_ok": True, "action": "use"},
            {"capability": "deploy_target", "provider_selected": None,
             "provider_status": "UNAVAILABLE", "fallback_used": False,
             "resolution_ok": False, "action": "register_provider"},
            {"capability": "unknown_cap", "provider_selected": None,
             "provider_status": "UNAVAILABLE", "fallback_used": False,
             "resolution_ok": False, "action": "register_provider"},
        ]
        m = mod.compute_metrics(events)
        assert "deploy_target" in m["unresolved"], f"unresolved={m['unresolved']}"
        assert "unknown_cap" in m["unresolved"], f"unresolved={m['unresolved']}"
        assert "memory" not in m["unresolved"]
        PASS("T14 unresolved list", f"unresolved={m['unresolved']}")
    except Exception as e:
        FAIL("T14 unresolved list", str(e))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("Bloque F18 — Capability Runtime Metrics Tests")
    print("=" * 60)
    print()

    t1_events_imports()
    t2_make_event_fields()
    t3_emit_writes_jsonl()
    t4_disabled_env_var()
    t5_read_events_roundtrip()
    t6_read_events_tolerates_bad_lines()
    t7_resolve_emits_event()
    t8_resolve_no_emit()
    t9_metrics_imports()
    t10_load_events_no_file()
    t11_compute_metrics_correct()
    t12_compute_metrics_empty()
    t13_fallback_count()
    t14_unresolved_list()

    print()
    n_pass = sum(1 for _, ok, _ in _results if ok)
    n_fail = sum(1 for _, ok, _ in _results if not ok)
    total  = len(_results)
    print(f"Resultado: {n_pass}/{total} PASS", end="")
    if n_fail:
        failed = [name for name, ok, _ in _results if not ok]
        print(f"  |  {n_fail} FAIL: {', '.join(failed)}")
    else:
        print()
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
