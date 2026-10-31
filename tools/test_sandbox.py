#!/usr/bin/env python3
"""
Test sandbox (roadmap P21): run QA suites in a DISPOSABLE copy of the working tree with a DISPOSABLE home directory, so a
suite can never write to the real repo state (.pipeline, .claude/logs) or to the real HOME (~/.claude/snapshots,
~/.engram, ...).

Why a copy and not per-module path overrides: the writers are spread over Python modules (which compute their paths from
their own location or from the project root a test hands them) and JS hooks (which use os.homedir()). A copy of the code
makes every one of them relative to the copy, and a different HOME moves every home-relative writer, with no change to
any production module. The audit that motivated this (18 of 50 Quick suites wrote to real state, including the user's
cost-log.jsonl, session-log.jsonl, the invocation log that audit_invocations reads as evidence, and the Engram WAL) is
reproducible with state_audit-style before/after snapshots; F46 asserts the property.

What a suite still sees of the real world (read-only inputs): the working tree as it is NOW (tracked files and untracked
non-ignored ones, uncommitted edits included), the user's ~/.claude/settings.json, and a link to the executables under
~/go/bin. It does NOT see the real .pipeline/, .claude/logs/, ~/.claude/snapshots or ~/.engram: those start empty.

Disable with ATLAS_TEST_ISOLATION=0 (or `run_all.py --no-isolation`) when a suite needs the real environment.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

# Never copied into the sandbox, even if tracked or untracked-not-ignored.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".pipeline"}
_SKIP_TOP = {"lucas-rojo-web", "conexo-web", "Proyectos internos"}     # unrelated projects, not part of ATLAS's QA surface

# Read-only inputs mirrored from the real home (path relative to home). Executables are hard-linked, not copied.
HOME_FILES = (".claude/settings.json",)
HOME_LINK_DIRS = ("go/bin",)


def isolation_enabled(flag: Optional[bool] = None) -> bool:
    if flag is not None:
        return flag
    return os.environ.get("ATLAS_TEST_ISOLATION", "1").strip().lower() not in ("0", "false", "no", "off")


def _git_files(root: Path) -> Optional[List[str]]:
    try:
        r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=str(root), capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def _walk_files(root: Path) -> List[str]:
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for f in filenames:
            out.append(str((Path(dirpath) / f).relative_to(root)).replace("\\", "/"))
    return out


def files_to_copy(root: Path) -> List[str]:
    files = _git_files(root)
    if files is None:
        files = _walk_files(root)
    keep = []
    for rel in files:
        parts = rel.replace("\\", "/").split("/")
        if parts[0] in _SKIP_TOP or any(p in _SKIP_DIRS for p in parts[:-1]):
            continue
        if (root / rel).is_file():
            keep.append(rel)
    return keep


class Sandbox:
    def __init__(self, real_root: Path, base_dir: Optional[Path] = None):
        self.real_root = Path(real_root).resolve()
        self._tmp = Path(tempfile.mkdtemp(prefix="atlas_sbx_", dir=str(base_dir) if base_dir else None))
        self.repo = self._tmp / "repo"
        self.home = self._tmp / "home"
        self.copied = 0
        self._links: List[Path] = []
        self._build()

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        self.repo.mkdir()
        for rel in files_to_copy(self.real_root):
            dst = self.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.real_root / rel, dst)
            self.copied += 1
        (self.repo / ".pipeline").mkdir(exist_ok=True)
        self.home.mkdir()
        real_home = Path.home()
        for rel in HOME_FILES:
            src = real_home / rel
            if src.is_file():
                dst = self.home / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        for rel in HOME_LINK_DIRS:
            src_dir = real_home / rel
            if src_dir.is_dir():
                dst_dir = self.home / rel
                dst_dir.parent.mkdir(parents=True, exist_ok=True)
                self._link_dir(src_dir, dst_dir)
        self._git_init()

    def _link_dir(self, src: Path, dst: Path) -> None:
        """Expose a real directory (executables) read-only-by-convention without copying it. A link, never a hard link:
        a hard link to a RUNNING executable cannot be deleted on Windows, a junction/symlink can."""
        try:
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], capture_output=True, timeout=30, check=True)
            else:
                os.symlink(src, dst, target_is_directory=True)
            self._links.append(dst)
        except (OSError, subprocess.SubprocessError):
            pass                                    # the suites that need the binary fall back to PATH or skip

    def _git_init(self) -> None:
        """Suites that call git expect a repository with a clean HEAD."""
        env = dict(os.environ, GIT_AUTHOR_NAME="atlas-sandbox", GIT_AUTHOR_EMAIL="sandbox@invalid",
                   GIT_COMMITTER_NAME="atlas-sandbox", GIT_COMMITTER_EMAIL="sandbox@invalid")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "sandbox snapshot"]):
            try:
                subprocess.run(["git", *args], cwd=str(self.repo), env=env, capture_output=True, timeout=120)
            except (OSError, subprocess.SubprocessError):
                return

    # ---------------------------------------------------------------- use
    def env(self, base: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        e = dict(base if base is not None else os.environ)
        home = str(self.home)
        e.update({"HOME": home, "USERPROFILE": home, "ATLAS_TEST_SANDBOX": str(self._tmp)})
        if os.name == "nt":
            e["HOMEDRIVE"], e["HOMEPATH"] = os.path.splitdrive(home)[0], os.path.splitdrive(home)[1]
        return e

    def path_for(self, real_path: Path) -> Path:
        """Where a path of the real tree lives inside the sandbox."""
        return self.repo / Path(real_path).resolve().relative_to(self.real_root)

    def cleanup(self) -> None:
        # Links to real directories are removed FIRST, as links: rmtree must never walk into the real directory.
        for link in self._links:
            try:
                os.unlink(link)                      # POSIX symlink
            except OSError:
                try:
                    os.rmdir(link)                   # Windows junction: removes the link only
                except OSError:
                    pass
        git_dir = str(self.repo / ".git")

        def _force(func, path, _exc):
            if str(path).startswith(git_dir):            # git object files are read-only on Windows
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except OSError:
                    pass

        for _ in range(3):
            if sys.version_info >= (3, 12):
                shutil.rmtree(self._tmp, onexc=_force)
            else:
                shutil.rmtree(self._tmp, onerror=_force)
            if not self._tmp.exists():
                return

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()


def protected_snapshot(real_root: Path, extra: Iterable[Path] = ()) -> Dict[str, tuple]:
    """(size, mtime_ns) of the REAL state a suite must never change: the repo's .pipeline and .claude/logs, and the
    user's ~/.claude/snapshots and ~/.engram. Used by the runner's leak guard and by F46."""
    home = Path.home()
    bases = [real_root / ".pipeline", real_root / ".claude" / "logs", home / ".claude" / "snapshots", home / ".engram", *extra]
    out: Dict[str, tuple] = {}
    for base in bases:
        if not base.exists():
            continue
        for dirpath, _, filenames in os.walk(base):
            for f in filenames:
                p = Path(dirpath) / f
                try:
                    st = p.stat()
                except OSError:
                    continue
                out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


def changed(before: Mapping[str, tuple], after: Mapping[str, tuple]) -> List[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
