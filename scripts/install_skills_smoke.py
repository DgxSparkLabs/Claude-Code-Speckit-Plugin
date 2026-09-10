#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install every enumerated skill via `npx skills` and assert the result.

Reproduces the CI "Install every enumerated skill for Claude Code" step:

  1. Enumerate names with `uv run scripts/list_skills.py`
  2. `npx --yes skills@latest add . --skill <name> -a claude-code -y` for each
  3. Capture `npx --yes skills@latest list` to `$RUNNER_TEMP/skills-installed.txt`
  4. Delegate the installed-set check to `assert_skills.py`

Requires Node/`npx` on PATH and network access to the npm registry.

Usage:
    uv run scripts/install_skills_smoke.py
    uv run scripts/install_skills_smoke.py --repo /path/to/checkout

Exits with `assert_skills.py`'s exit code on success of the installs, or with
the failing `npx`/`list_skills.py` status otherwise.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def skill_names_from_listing(text: str) -> list[str]:
    """Split enumerator stdout the same way the bash `while read` loop did."""
    return [line for line in text.splitlines() if line]


def installed_listing_path() -> Path:
    """`$RUNNER_TEMP/skills-installed.txt`, or a throwaway file locally."""
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        return Path(runner_temp) / "skills-installed.txt"
    return Path(tempfile.mkdtemp()) / "skills-installed.txt"


def print_skills_tree(root: Path) -> None:
    """Mirror `find .claude/skills -print 2>/dev/null || true`."""
    print("=== .claude/skills tree ===")
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        print(dirpath)
        for name in filenames:
            print(os.path.join(dirpath, name))


def run_npx(*args: str, stdin_null: bool = False, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["npx", "--yes", "skills@latest", *args],
        check=True,
        text=True,
        cwd=cwd,
        stdin=subprocess.DEVNULL if stdin_null else None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository checkout (default: current working directory)",
    )
    args = parser.parse_args(argv)
    root = args.repo.resolve()

    try:
        listing = subprocess.run(
            ["uv", "run", str(root / "scripts" / "list_skills.py")],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        names = skill_names_from_listing(listing.stdout)

        for name in names:
            print(f"::group::npx skills add . --skill {name} -a claude-code -y")
            run_npx(
                "add",
                ".",
                "--skill",
                name,
                "-a",
                "claude-code",
                "-y",
                stdin_null=True,
                cwd=root,
            )
            print("::endgroup::")

        print("=== npx skills list ===")
        listed = subprocess.run(
            ["npx", "--yes", "skills@latest", "list"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        sys.stdout.write(listed.stdout)
        out_path = installed_listing_path()
        out_path.write_text(listed.stdout, encoding="utf-8")
        print_skills_tree(root / ".claude" / "skills")

        return subprocess.run(
            [
                "uv",
                "run",
                str(root / "scripts" / "assert_skills.py"),
                "--expected-from-repo",
                ".",
                "--listing",
                str(out_path),
                "--installed-root",
                ".claude",
            ],
            cwd=root,
            check=False,
        ).returncode
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: {' '.join(map(str, exc.cmd))} failed with exit {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
