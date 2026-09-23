"""Worker process spawned by _qa/bloque-capability-events-integrity.py.

Emits N real CapabilityEvents via the real production writer
(core.capabilities.events.emit) against a disposable target file passed
on the command line. Never touches the real .pipeline/capability-events.jsonl.

Not a test file itself — a helper subprocess used only by the integrity
suite to reproduce genuine cross-process concurrency.
"""
import sys

sys.path.insert(0, sys.argv[1])  # project root
from pathlib import Path

from core.capabilities.events import emit, make_event

target = Path(sys.argv[2])
worker_id = sys.argv[3]
n_events = int(sys.argv[4])

for i in range(n_events):
    evt = make_event(
        capability="qa-integrity-test",
        provider_selected="dummy",
        provider_status="LIVE",
        fallback_used=False,
        action="use",
        requested_by=f"worker-{worker_id}",
        reason="capability-events integrity regression fixture",
        metadata={"worker": worker_id, "seq": i},
    )
    ok = emit(evt, events_file=target)
    if not ok:
        print(f"worker-{worker_id} seq={i} emit() returned False", file=sys.stderr)
