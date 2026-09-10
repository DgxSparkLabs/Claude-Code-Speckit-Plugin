#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""End-to-end smoke test for the init wrapper sequence.

Runs the real `specify` CLI in a throwaway directory:

  1. `specify init . --integration claude --script sh ...`
  2. `specify extension add <name>` for every entry in
     `assets/skills/init/extensions.txt`

then asserts the generated tree looks like the committed snapshot: `.specify/`
exists, `.claude/skills/` holds at least one `speckit-*` skill, and every
snapshot skill name is present (missing ones are a GitHub warning, not a
failure, because the live CLI may legitimately ship a different set).
Finally delegates the extensions set comparison to `assert_extensions.py`.

Requires the `specify` CLI on PATH and network access.

Usage:
    uv run scripts/wrapper_smoke.py
    uv run scripts/wrapper_smoke.py --repo /path/to/checkout

Exits 1 when a required path is missing or the CLI fails, or with
`assert_extensions.py`'s exit code when the extensions sets disagree.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXT_TXT_REL = Path("assets") / "skills" / "init" / "extensions.txt"
SNAPSHOT_SKILLS_REL = Path("assets") / "bash" / ".claude" / "skills"

INIT_ARGS = [
    "init",
    ".",
    "--integration",
    "claude",
    "--script",
    "sh",
    "--non-interactive",
    "--ignore-agent-tools",
    "--force",
]


def parse_extensions_txt(path: Path) -> list[str]:
    entries: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def speckit_dirs(skills_dir: Path) -> list[str]:
    if not skills_dir.is_dir():
        return []
    return sorted(p.name for p in skills_dir.glob("speckit-*") if p.is_dir())


def dump_dir(skills_dir: Path) -> None:
    """Mirror the bash `ls -la` diagnostics, on stderr."""
    print(f"=== {skills_dir} ===", file=sys.stderr)
    if not skills_dir.is_dir():
        print("(directory does not exist)", file=sys.stderr)
        return
    for entry in sorted(skills_dir.iterdir()):
        kind = "d" if entry.is_dir() else "f"
        print(f"{kind} {entry.name}", file=sys.stderr)


def run_specify(work: Path, *args: str) -> None:
    """Run `specify <args>` in `work`, raising CalledProcessError on failure."""
    subprocess.run(["specify", *args], cwd=work, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(os.environ.get("GITHUB_WORKSPACE") or Path(__file__).resolve().parent.parent),
        help="repository checkout (default: $GITHUB_WORKSPACE or this script's repository)",
    )
    args = parser.parse_args(argv)
    root = args.repo.resolve()

    ext_txt = root / EXT_TXT_REL
    if not ext_txt.is_file():
        print(f"::error::Missing {EXT_TXT_REL.as_posix()}")
        return 1

    expected_names = speckit_dirs(root / SNAPSHOT_SKILLS_REL)
    if not expected_names:
        print(
            f"ERROR: no speckit-* skills under {SNAPSHOT_SKILLS_REL.as_posix()}/",
            file=sys.stderr,
        )
        return 1

    work = Path(tempfile.mkdtemp())
    try:
        run_specify(work, *INIT_ARGS)
        for name in parse_extensions_txt(ext_txt):
            run_specify(work, "extension", "add", name)
    except FileNotFoundError:
        print("ERROR: `specify` CLI not found on PATH", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: {' '.join(exc.cmd)} failed with exit {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1

    if not (work / ".specify").is_dir():
        print("ERROR: wrapper sequence did not create .specify/", file=sys.stderr)
        return 1

    live_skills = work / ".claude" / "skills"
    live_names = speckit_dirs(live_skills)
    if not live_names:
        print(
            "ERROR: .claude/skills/ is empty (expected at least one speckit-* skill)",
            file=sys.stderr,
        )
        dump_dir(live_skills)
        return 1

    missing = [n for n in expected_names if not (live_skills / n / "SKILL.md").is_file()]
    if missing:
        print(f"::warning::snapshot names absent from live specify init: {' '.join(missing)}")
        dump_dir(live_skills)

    print(f"ok: .specify/ present and {len(live_names)} speckit-* skills installed")

    return subprocess.run(
        [
            "uv",
            "run",
            str(root / "scripts" / "assert_extensions.py"),
            "--extensions-txt",
            str(ext_txt),
            "--extensions-yml",
            str(work / ".specify" / "extensions.yml"),
            "--skills-dir",
            str(live_skills),
        ],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
