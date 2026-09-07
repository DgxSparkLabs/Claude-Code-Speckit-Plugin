#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Structural gate: every `skills/speckit-*` entry must be a committed symlink.

The bundled `speckit-*` plugin skills are exposed at the plugin root as relative
symlinks into `assets/bash/.claude/skills/`, keeping `assets/` the single source
of truth. Detection tests (Claude `plugin details`, `npx skills add . --list`)
would pass just as happily against copied directories, so this gate reads the
git *index* -- not the working tree, which cannot represent symlinks on Windows
checkouts with `core.symlinks=false` -- and fails unless each entry is recorded
with git mode 120000 and resolves under `assets/bash/.claude/skills/`.

Usage:
    uv run scripts/assert_symlinked_skills.py
    uv run scripts/assert_symlinked_skills.py --repo /path/to/checkout

Exits non-zero when an entry is a regular file/directory (i.e. a copy), has a
non-symlink mode, points outside the assets tree, or dangles. Also exits
non-zero when no symlinked skill is found at all, so the gate can never
vacuously pass against an empty set.
"""

from __future__ import annotations

import argparse
import posixpath
import subprocess
import sys
from pathlib import Path

SKILLS_PREFIX = "skills/"
LINK_PREFIX = "skills/speckit-"
SYMLINK_MODE = "120000"
TARGET_PREFIX = "assets/bash/.claude/skills/"
SKILL_FILENAME = "SKILL.md"


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"error: git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def index_entries(repo: Path) -> list[tuple[str, str, str]]:
    """Return (mode, sha, path) for every index entry under `skills/`."""
    entries: list[tuple[str, str, str]] = []
    for line in git(repo, "ls-files", "-s", "--", SKILLS_PREFIX).splitlines():
        line = line.rstrip("\r")
        if not line:
            continue
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) < 3 or not path:
            raise SystemExit(f"error: cannot parse `git ls-files -s` line: {line!r}")
        entries.append((fields[0], fields[1], path))
    return entries


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

    entries = index_entries(repo)
    if not entries:
        print(f"error: no index entries under {SKILLS_PREFIX} in {repo}", file=sys.stderr)
        return 1

    errors: list[str] = []
    verified: list[str] = []
    seen_links: set[str] = set()

    for mode, sha, path in entries:
        if not path.startswith(LINK_PREFIX):
            continue

        # A copy shows up as blobs *beneath* the skill directory
        # (skills/speckit-x/SKILL.md), never as a single entry at
        # skills/speckit-x. Flag the containing directory once.
        head = path[len(SKILLS_PREFIX) :].split("/", 1)
        if len(head) > 1:
            offender = SKILLS_PREFIX + head[0]
            if offender not in seen_links:
                seen_links.add(offender)
                errors.append(
                    f"{offender}: is a real directory (copy) -- found tracked file {path} "
                    f"with mode {mode}; expected a single {SYMLINK_MODE} symlink entry"
                )
            continue

        seen_links.add(path)
        if mode != SYMLINK_MODE:
            errors.append(
                f"{path}: git mode is {mode}, expected {SYMLINK_MODE} (symlink); "
                "a regular file or copy is not acceptable"
            )
            continue

        target = git(repo, "cat-file", "blob", sha).strip()
        if not target:
            errors.append(f"{path}: symlink blob is empty")
            continue

        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        if not resolved.startswith(TARGET_PREFIX):
            errors.append(
                f"{path}: target {target!r} resolves to {resolved!r}, "
                f"which is outside {TARGET_PREFIX}"
            )
            continue

        skill_md = repo / resolved / SKILL_FILENAME
        if not skill_md.is_file():
            errors.append(f"{path}: dangling target -- {resolved}/{SKILL_FILENAME} does not exist")
            continue

        verified.append(f"{path} -> {target}")

    if errors:
        print("error: skills/ symlink structure gate failed:", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 2

    if not verified:
        print(
            f"error: no {LINK_PREFIX}* symlink entries found in the git index of {repo}; "
            "the structural gate must never pass against an empty set",
            file=sys.stderr,
        )
        return 1

    for line in verified:
        print(f"symlink ok: {line}")
    print(f"ok: {len(verified)} symlinked skills verified (mode {SYMLINK_MODE} -> {TARGET_PREFIX})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
