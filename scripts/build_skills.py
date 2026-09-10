#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Sync all authored skills from `assets/skills/*` into `skills/`.

`skills/` is a pure build artifact: it is deleted wholesale and recreated on
every run, so any dangling directory left behind by an earlier layout is
destroyed rather than preserved.

Canonical source:
  * `assets/skills/<name>` -- each hand-authored plugin skill

The rebuilt copies are what Claude Code discovers as the plugin's skills and
what the vercel-labs `skills` CLI installs, so `skills/` stays git-committed.
"Build artifact" means deterministically regeneratable, not untracked.

Usage:
    uv run scripts/build_skills.py
    uv run scripts/build_skills.py --root /path/to/checkout

Exits non-zero when `assets/skills/` has no skill directories, when any
authored skill is empty, or when the rebuilt `skills/` would be empty, so a
CI step can never silently produce an empty `skills/`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

SKILLS_SOURCE_REL = Path("assets") / "skills"
BUNDLE_REL = Path("skills")


def make_scripts_executable(root: Path) -> int:
    """Add the executable bits to every `*.sh` under `root`. Returns the count."""
    count = 0
    for script in sorted(root.rglob("*.sh")):
        if not script.is_file():
            continue
        mode = script.stat().st_mode
        os.chmod(script, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        count += 1
    return count


def rel_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    if not root.is_dir():
        return files
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            files[path.relative_to(root).as_posix()] = path
    return files


def trees_byte_identical(src: Path, dst: Path) -> bool:
    """True when `dst` has the same relative files and bytes as `src`."""
    src_files = rel_files(src)
    dst_files = rel_files(dst)
    if set(src_files) != set(dst_files):
        return False
    return all(
        src_files[rel].read_bytes() == dst_files[rel].read_bytes() for rel in src_files
    )


def authored_skill_dirs(root: Path) -> list[Path]:
    source = root / SKILLS_SOURCE_REL
    if not source.is_dir():
        return []
    return sorted(p for p in source.iterdir() if p.is_dir())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository checkout to rebuild (default: this script's repository)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    bundle = root / BUNDLE_REL
    authored = authored_skill_dirs(root)

    if not authored:
        print(
            f"error: cannot rebuild skills/: no authored skill directories under "
            f"{SKILLS_SOURCE_REL.as_posix()}/",
            file=sys.stderr,
        )
        return 1
    for src in authored:
        if not rel_files(src):
            print(
                f"error: {SKILLS_SOURCE_REL.as_posix()}/{src.name} is empty; "
                "refusing to rebuild skills/ into an empty tree",
                file=sys.stderr,
            )
            return 1

    if bundle.is_dir():
        for src in authored:
            dst = bundle / src.name
            if dst.is_dir() and not trees_byte_identical(src, dst):
                print(
                    f"warning: skills/{src.name} has local edits that will be discarded; "
                    f"edit the source assets/skills/{src.name}/ and rerun "
                    "scripts/build_skills.py",
                    file=sys.stderr,
                )

    # Wholesale wipe: this is what destroys dangling entries.
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)

    for src in authored:
        shutil.copytree(src, bundle / src.name)

    rebuilt = [p for p in sorted(bundle.iterdir()) if p.is_dir()]
    if not rebuilt:
        print("error: rebuilt skills/ is empty", file=sys.stderr)
        return 1
    for dst in rebuilt:
        if not rel_files(dst):
            print(f"error: rebuilt skills/{dst.name} is empty", file=sys.stderr)
            return 1

    scripts = make_scripts_executable(bundle)
    names = ", ".join(p.name for p in rebuilt)

    print(
        f"Synced all authored skills from {SKILLS_SOURCE_REL.as_posix()}/* "
        f"into {BUNDLE_REL.as_posix()}/ ({names}); "
        f"{scripts} *.sh marked executable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
