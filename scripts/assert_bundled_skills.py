#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Byte-equality gate: top-level skills/speckit-* must match assets/bash/.claude/skills/.

The plugin exposes speckit-* skills as generated copies under skills/ so both
Claude Code and `npx skills` discover them. assets/bash/.claude/skills/ remains
the source of truth; this gate fails CI if the copies drift.

Usage:
    uv run scripts/assert_bundled_skills.py
    uv run scripts/assert_bundled_skills.py --repo /path/to/checkout

Exits non-zero when the name sets differ, any file differs in bytes, a file is
present on only one side, or the set is empty.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SOURCE_REL = Path("assets") / "bash" / ".claude" / "skills"
BUNDLE_REL = Path("skills")
PREFIX = "speckit-"


def skill_dirs(parent: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not parent.is_dir():
        return found
    for child in parent.iterdir():
        if child.is_dir() and child.name.startswith(PREFIX):
            found[child.name] = child
    return found


def rel_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            files[path.relative_to(root).as_posix()] = path
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository checkout to inspect (default: this script's repository)",
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()

    source = skill_dirs(repo / SOURCE_REL)
    bundle = skill_dirs(repo / BUNDLE_REL)

    errors: list[str] = []

    if not source:
        errors.append(f"no {PREFIX}* directories under {SOURCE_REL.as_posix()}")
    if not bundle:
        errors.append(f"no {PREFIX}* directories under {BUNDLE_REL.as_posix()}")

    only_source = sorted(set(source) - set(bundle))
    only_bundle = sorted(set(bundle) - set(source))
    for name in only_source:
        errors.append(f"missing copy: {BUNDLE_REL.as_posix()}/{name}")
    for name in only_bundle:
        errors.append(f"extra copy: {BUNDLE_REL.as_posix()}/{name} (not in {SOURCE_REL.as_posix()})")

    verified = 0
    for name in sorted(set(source) & set(bundle)):
        src_files = rel_files(source[name])
        dst_files = rel_files(bundle[name])
        only_src = sorted(set(src_files) - set(dst_files))
        only_dst = sorted(set(dst_files) - set(src_files))
        for rel in only_src:
            errors.append(f"{name}: missing file skills/{name}/{rel}")
        for rel in only_dst:
            errors.append(f"{name}: extra file skills/{name}/{rel}")
        for rel in sorted(set(src_files) & set(dst_files)):
            if src_files[rel].read_bytes() != dst_files[rel].read_bytes():
                errors.append(f"{name}: byte mismatch skills/{name}/{rel}")
        if not only_src and not only_dst:
            verified += 1

    if errors:
        print("error: bundled skills drifted from assets/bash/.claude/skills/:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 2

    if verified == 0:
        print(
            "error: no matching speckit-* skills to compare; "
            "the equality gate must never pass against an empty set",
            file=sys.stderr,
        )
        return 1

    print(
        f"ok: {verified} bundled skills byte-identical "
        f"({BUNDLE_REL.as_posix()}/speckit-* == {SOURCE_REL.as_posix()}/speckit-*)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
