#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Sync `skills/init` from `assets/skills/init`.

`skills/` is a pure build artifact: it is deleted wholesale and recreated on
every run, so any dangling directory left behind by an earlier layout is
destroyed rather than preserved.

Canonical source:
  * `assets/skills/init` -- the hand-authored init skill

The rebuilt copy is what Claude Code discovers as the plugin's init skill and
what the vercel-labs `skills` CLI installs, so `skills/` stays git-committed.
"Build artifact" means deterministically regeneratable, not untracked.

Usage:
    uv run scripts/build_skills.py
    uv run scripts/build_skills.py --root /path/to/checkout

Exits non-zero when `assets/skills/init` is missing or empty, or when the
rebuilt tree would not contain `skills/init`, so a CI step can never silently
produce an empty `skills/`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

INIT_SOURCE_REL = Path("assets") / "skills" / "init"
BUNDLE_REL = Path("skills")
INIT_NAME = "init"


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

    init_source = root / INIT_SOURCE_REL
    bundle = root / BUNDLE_REL

    if not init_source.is_dir():
        print(
            f"error: cannot rebuild skills/: missing authored init source: "
            f"{INIT_SOURCE_REL.as_posix()}",
            file=sys.stderr,
        )
        return 1
    if not rel_files(init_source):
        print(
            f"error: {INIT_SOURCE_REL.as_posix()} is empty; "
            "refusing to rebuild skills/ into an empty tree",
            file=sys.stderr,
        )
        return 1

    init_bundle = bundle / INIT_NAME
    if init_bundle.is_dir() and not trees_byte_identical(init_source, init_bundle):
        print(
            "warning: skills/init has local edits that will be discarded; "
            "edit the source assets/skills/init/ and rerun scripts/build_skills.py",
            file=sys.stderr,
        )

    # Wholesale wipe: this is what destroys dangling entries.
    shutil.rmtree(bundle, ignore_errors=True)
    bundle.mkdir(parents=True)

    shutil.copytree(init_source, bundle / INIT_NAME)

    rebuilt = bundle / INIT_NAME
    if not rebuilt.is_dir():
        print("error: rebuilt skills/init is absent", file=sys.stderr)
        return 1
    if not rel_files(rebuilt):
        print("error: rebuilt skills/init is empty", file=sys.stderr)
        return 1

    scripts = make_scripts_executable(bundle)

    print(
        f"Synced {BUNDLE_REL.as_posix()}/{INIT_NAME} from {INIT_SOURCE_REL.as_posix()}; "
        f"{scripts} *.sh marked executable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
