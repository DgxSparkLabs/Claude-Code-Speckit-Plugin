#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Snapshot-integrity gate for default Spec Kit extensions.

Asserts:

  * ``assets/bash/.specify/extensions.yml`` ``installed:`` is the same set as
    the entries in ``assets/skills/init/extensions.txt`` (comments and blank
    lines ignored)
  * ``assets/bash/.claude/skills/`` exists and is non-empty

Fails closed: missing files, an empty skills tree, or a set mismatch are
errors. Does not talk to the network.

Usage:
    uv run scripts/assert_extensions.py
    uv run scripts/assert_extensions.py --repo /path/to/checkout

Exits 2 on installed-set mismatch, 1 when a required path is missing or the
skills tree is empty.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

EXT_TXT_REL = Path("assets") / "skills" / "init" / "extensions.txt"
EXT_YML_REL = Path("assets") / "bash" / ".specify" / "extensions.yml"
SKILLS_REL = Path("assets") / "bash" / ".claude" / "skills"


def parse_extensions_txt(path: Path) -> list[str]:
    entries: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def parse_installed(path: Path) -> list[str] | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    installed = data.get("installed")
    if not isinstance(installed, list):
        print(
            f"error: {path} 'installed:' is missing or not a list",
            file=sys.stderr,
        )
        return None
    return [str(item) for item in installed]



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository checkout (default: this script's repository)",
    )
    parser.add_argument(
        "--extensions-txt",
        type=Path,
        default=None,
        help="override path to extensions.txt (default: <repo>/assets/skills/init/extensions.txt)",
    )
    parser.add_argument(
        "--extensions-yml",
        type=Path,
        default=None,
        help="override path to extensions.yml (default: <repo>/assets/bash/.specify/extensions.yml)",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=None,
        help="override skills directory (default: <repo>/assets/bash/.claude/skills)",
    )
    args = parser.parse_args(argv)
    root = args.repo.resolve()

    ext_txt = (args.extensions_txt or (root / EXT_TXT_REL)).resolve()
    ext_yml = (args.extensions_yml or (root / EXT_YML_REL)).resolve()
    skills_dir = (args.skills_dir or (root / SKILLS_REL)).resolve()

    def rel(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    if not ext_txt.is_file():
        print(f"error: missing {rel(ext_txt)}", file=sys.stderr)
        return 1
    if not ext_yml.is_file():
        print(f"error: missing {rel(ext_yml)}", file=sys.stderr)
        return 1
    if not skills_dir.is_dir():
        print(f"error: missing {rel(skills_dir)}/", file=sys.stderr)
        return 1

    children = list(skills_dir.iterdir())
    if not children:
        print(
            f"error: {rel(skills_dir)}/ is empty "
            "(must contain generated speckit-* skills)",
            file=sys.stderr,
        )
        return 1

    expected = parse_extensions_txt(ext_txt)
    if not expected:
        print(
            f"error: {rel(ext_txt)} has no extension entries",
            file=sys.stderr,
        )
        return 1

    actual = parse_installed(ext_yml)
    if actual is None:
        return 1

    exp_set, act_set = set(expected), set(actual)
    if exp_set != act_set:
        missing = sorted(exp_set - act_set)
        extra = sorted(act_set - exp_set)
        print(
            f"error: {rel(ext_yml)} installed: does not match {rel(ext_txt)}",
            file=sys.stderr,
        )
        if missing:
            print(f"  missing from yml: {', '.join(missing)}", file=sys.stderr)
        if extra:
            print(f"  extra in yml: {', '.join(extra)}", file=sys.stderr)
        print(f"  extensions.txt: {sorted(exp_set)}", file=sys.stderr)
        print(f"  extensions.yml: {sorted(act_set)}", file=sys.stderr)
        return 2

    print(
        f"ok: installed {sorted(act_set)} matches {rel(ext_txt)}; "
        f"{rel(skills_dir)}/ has {len(children)} entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
