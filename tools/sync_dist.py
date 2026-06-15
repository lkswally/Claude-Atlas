"""
sync_dist.py — Sincroniza carpetas de distribucion desde source of truth.

Source of truth: .claude/hooks/ y .claude/agents/
Destino:         hooks/         y agents/

Uso:
  python tools/sync_dist.py           # sync hooks + agents
  python tools/sync_dist.py --dry-run # mostrar que cambiaria sin tocar nada
  python tools/sync_dist.py --check   # exit 1 si hay drift (para CI / tests)
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PAIRS = [
    (PROJECT_ROOT / ".claude" / "hooks",  PROJECT_ROOT / "hooks",  ".js"),
    (PROJECT_ROOT / ".claude" / "agents", PROJECT_ROOT / "agents", ".md"),
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sync(dry_run: bool = False, check_only: bool = False) -> int:
    drift_found = False

    for src_dir, dst_dir, ext in PAIRS:
        if not src_dir.exists():
            print(f"[WARN] source no encontrado: {src_dir}")
            continue
        if not dst_dir.exists():
            print(f"[WARN] destino no encontrado: {dst_dir}")
            continue

        src_files = {f.name: f for f in src_dir.iterdir() if f.suffix == ext}
        dst_files = {f.name: f for f in dst_dir.iterdir() if f.suffix == ext}

        for name, src in sorted(src_files.items()):
            dst = dst_dir / name
            if not dst.exists():
                drift_found = True
                print(f"  [NEW]  {dst_dir.name}/{name}")
                if not dry_run and not check_only:
                    shutil.copy2(str(src), str(dst))
            elif sha256(src) != sha256(dst):
                drift_found = True
                print(f"  [UPD]  {dst_dir.name}/{name}")
                if not dry_run and not check_only:
                    shutil.copy2(str(src), str(dst))

        extra = set(dst_files) - set(src_files)
        if extra:
            for name in sorted(extra):
                print(f"  [XTRA] {dst_dir.name}/{name}  (solo en dist, no en runtime — ignorado)")

    if not drift_found:
        print("  Sin drift — distribucion en sync con source of truth.")

    if check_only and drift_found:
        print("\n[FAIL] Drift detectado. Ejecutar: python tools/sync_dist.py")
        return 1
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run    = "--dry-run" in args
    check_only = "--check" in args

    print("=" * 60)
    if check_only:
        print("sync_dist.py — Check mode (sin cambios)")
    elif dry_run:
        print("sync_dist.py — Dry run (sin cambios)")
    else:
        print("sync_dist.py — Sync: .claude/* -> dist")
    print("=" * 60)

    sys.exit(sync(dry_run=dry_run, check_only=check_only))
