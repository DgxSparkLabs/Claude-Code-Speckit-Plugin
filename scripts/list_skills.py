#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Enumerate the skills this repository ships as installable package content.

Installable skills are the top-level `skills/<dir>/SKILL.md` files. Those are the
files Claude Code discovers when the repo is installed as the `speckit` plugin
(https://code.claude.com/docs/en/plugins-reference -- "Plugin components
reference > Skills") and the files the vercel-labs `skills` CLI installs.

The `speckit-*` skills under `assets/**/.claude/skills/` are deliberately NOT
enumerated: they are project-scaffold content that `/speckit:init` copies into a
target project, not content either package manager installs from this repo.

Usage:
    uv run scripts/list_skills.py            # newline-delimited skill names
    uv run scripts/list_skills.py --json     # JSON array of {name, dir, path}

Exits non-zero when no skills are found, so a CI step can never silently pass
against an empty set.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILLS_DIRNAME = "skills"
SKILL_FILENAME = "SKILL.md"


def parse_frontmatter_name(skill_md: Path) -> str | None:
    """Return the `name` field from the YAML frontmatter, or None.

    Deliberately a hand-rolled scan of the top-level frontmatter block so this
    script keeps a `dependencies = []` PEP-723 header and needs no wheel
    downloads in CI. Skill frontmatter is flat `key: value` YAML.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        # Only top-level keys: an indented line belongs to a nested structure.
        if line[:1] in (" ", "\t") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        if key.strip() != "name":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value or None
    return None


def discover_skills(root: Path) -> list[dict[str, str]]:
    """Discover installable skills under `<root>/skills/*/SKILL.md`."""
    skills_dir = root / SKILLS_DIRNAME
    found: list[dict[str, str]] = []
    if not skills_dir.is_dir():
        return found

    for child in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        skill_md = child / SKILL_FILENAME
        # Require the manifest file itself: an empty directory is not a skill.
        if not skill_md.is_file():
            continue
        found.append(
            {
                "name": parse_frontmatter_name(skill_md) or child.name,
                "dir": child.name,
                "path": skill_md.relative_to(root).as_posix(),
            }
        )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to scan (default: this script's repository)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="emit a JSON array of {name, dir, path} instead of bare names",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    skills = discover_skills(root)

    if not skills:
        print(
            f"error: no skills found under {root / SKILLS_DIRNAME}/*/{SKILL_FILENAME}",
            file=sys.stderr,
        )
        return 1

    if args.as_json:
        print(json.dumps(skills, indent=2))
    else:
        for skill in skills:
            print(skill["name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
