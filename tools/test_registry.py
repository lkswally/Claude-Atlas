#!/usr/bin/env python3
"""
ATLAS Test Registry — F24
=========================

Authoritative loader for config/test.registry.yaml.

API:
    registry = TestRegistry()
    registry.list_suites()
    registry.get_suite("bloque-F10-sot-drift")
    registry.suites_for_mode("quick")   # quick | full | release
    registry.suites_by_layer("unit")
    registry.detect_orphaned_suites()   # on disk but not in registry

Fail-open: if YAML is missing or PyYAML is not installed, falls back to
returning an empty registry (callers should check registry.loaded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / "config" / "test.registry.yaml"
QA_DIR = PROJECT_ROOT / "_qa"

VALID_LAYERS = {"unit", "integration", "system", "evidence", "release", "legacy"}
VALID_STATUSES = {"active", "skipped", "legacy"}


@dataclass
class Suite:
    id: str
    path: Path
    layer: str
    status: str
    timeout: int
    can_run_in_quick: bool
    can_run_in_release: bool
    notes: str = ""

    @property
    def can_run_in_full(self) -> bool:
        return self.status == "active"

    def is_active(self) -> bool:
        return self.status == "active"


class TestRegistry:
    def __init__(self, registry_path: Path = REGISTRY_PATH) -> None:
        self._suites: list[Suite] = []
        self.loaded: bool = False
        self.load_error: Optional[str] = None
        self._load(registry_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            self.load_error = f"Registry not found: {path}"
            return
        try:
            import yaml
        except ImportError:
            self.load_error = "PyYAML not installed — run: pip install pyyaml"
            return
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            self.load_error = f"YAML parse error: {e}"
            return

        raw_suites = data.get("suites", [])
        for entry in raw_suites:
            try:
                suite = Suite(
                    id=entry["id"],
                    path=PROJECT_ROOT / entry["path"],
                    layer=entry.get("layer", "unit"),
                    status=entry.get("status", "active"),
                    timeout=int(entry.get("timeout", 60)),
                    can_run_in_quick=bool(entry.get("can_run_in_quick", True)),
                    can_run_in_release=bool(entry.get("can_run_in_release", True)),
                    notes=entry.get("notes", ""),
                )
                self._suites.append(suite)
            except (KeyError, TypeError, ValueError) as e:
                # Fail-open: skip malformed entries
                pass
        self.loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_suites(self) -> list[Suite]:
        """All suites in the registry (all statuses, all layers)."""
        return list(self._suites)

    def get_suite(self, id: str) -> Optional[Suite]:
        """Return a Suite by id, or None."""
        for s in self._suites:
            if s.id == id:
                return s
        return None

    def suites_for_mode(self, mode: str) -> list[Suite]:
        """
        Return active suites appropriate for the given run mode.

        quick   — active suites with can_run_in_quick=true
        full    — all active suites (quick + evidence-only)
        release — active suites with can_run_in_release=true
        """
        if mode == "quick":
            return [s for s in self._suites if s.is_active() and s.can_run_in_quick]
        if mode == "release":
            return [s for s in self._suites if s.is_active() and s.can_run_in_release]
        if mode == "full":
            return [s for s in self._suites if s.is_active()]
        return []

    def suites_by_layer(self, layer: str) -> list[Suite]:
        """Return all suites for a given layer (any status)."""
        return [s for s in self._suites if s.layer == layer]

    def active_suites_by_layer(self, layer: str) -> list[Suite]:
        """Return active suites for a given layer."""
        return [s for s in self._suites if s.layer == layer and s.is_active()]

    def detect_orphaned_suites(self) -> list[Path]:
        """Return .py files in _qa/ that are NOT registered."""
        registered_paths = {s.path for s in self._suites}
        on_disk = set(QA_DIR.glob("bloque-*.py")) | set(QA_DIR.glob("qa-*.py"))
        return sorted(on_disk - registered_paths)

    def detect_missing_files(self) -> list[Suite]:
        """Return registered active suites whose file doesn't exist on disk."""
        return [s for s in self._suites if s.is_active() and not s.path.exists()]

    def summary(self) -> dict:
        """Return a summary dict for reporting."""
        by_layer: dict[str, int] = {}
        for s in self._suites:
            by_layer[s.layer] = by_layer.get(s.layer, 0) + 1
        return {
            "total": len(self._suites),
            "active": sum(1 for s in self._suites if s.is_active()),
            "legacy": sum(1 for s in self._suites if s.status == "legacy"),
            "by_layer": by_layer,
            "quick_count": len(self.suites_for_mode("quick")),
            "release_count": len(self.suites_for_mode("release")),
            "full_count": len(self.suites_for_mode("full")),
            "loaded": self.loaded,
            "load_error": self.load_error,
        }


def main() -> None:
    import json
    reg = TestRegistry()
    if not reg.loaded:
        print(f"ERROR: {reg.load_error}", file=__import__("sys").stderr)
        raise SystemExit(1)

    import sys
    args = sys.argv[1:]

    if "--summary" in args or not args:
        print(json.dumps(reg.summary(), indent=2))

    elif "--list" in args:
        mode = None
        layer = None
        for i, a in enumerate(args):
            if a == "--mode" and i + 1 < len(args):
                mode = args[i + 1]
            if a == "--layer" and i + 1 < len(args):
                layer = args[i + 1]
        suites = reg.suites_for_mode(mode) if mode else (reg.suites_by_layer(layer) if layer else reg.list_suites())
        for s in suites:
            print(f"{s.id}  [{s.layer}]  timeout={s.timeout}s  quick={s.can_run_in_quick}")

    elif "--orphaned" in args:
        orphans = reg.detect_orphaned_suites()
        if orphans:
            print(f"Orphaned ({len(orphans)}):")
            for p in orphans:
                print(f"  {p.name}")
        else:
            print("No orphaned suites.")

    elif "--missing" in args:
        missing = reg.detect_missing_files()
        if missing:
            print(f"Missing files ({len(missing)}):")
            for s in missing:
                print(f"  {s.id}: {s.path}")
        else:
            print("All active suite files exist.")


if __name__ == "__main__":
    main()
