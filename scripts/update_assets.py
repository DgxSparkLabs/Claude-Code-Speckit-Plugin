#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Helpers for the "Update Spec Kit Assets" workflow.

Each subcommand replaces one long inline bash block:

  * ``parse-version``  -- read the installed CLI version from `specify
    --version` and publish it as the ``version`` step output
  * ``decide``         -- compare the installed CLI version against
    plugin.json and publish ``needs_update`` / ``regen``
  * ``regenerate``     -- run `specify init` with the default extension set in
    a temp dir and rebuild ``assets/bash/`` from the result
  * ``bump-version``   -- rewrite ``.claude-plugin/plugin.json``'s ``version``

Step outputs are appended to the file named by ``$GITHUB_OUTPUT``; when that
variable is unset (local runs) they are printed instead.

Usage:
    uv run scripts/update_assets.py parse-version
    uv run scripts/update_assets.py decide --cli 1.2.3 --current 1.2.2 \\
        --force false --event schedule
    uv run scripts/update_assets.py regenerate
    uv run scripts/update_assets.py bump-version --version 1.2.3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXT_TXT_REL = Path("assets") / "skills" / "init" / "extensions.txt"
TARGET_REL = Path("assets") / "bash"
PLUGIN_JSON_REL = Path(".claude-plugin") / "plugin.json"

PRERELEASE_RE = re.compile(r"(dev|alpha|beta|rc)")

INIT_FLAGS = [
    "--integration",
    "claude",
    "--here",
    "--force",
    "--ignore-agent-tools",
    "--non-interactive",
]


def emit(**outputs: str) -> None:
    """Append `key=value` lines to $GITHUB_OUTPUT (or print them locally)."""
    lines = "".join(f"{key}={value}\n" for key, value in outputs.items())
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        sys.stdout.write(lines)
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(lines)


def parse_extensions_txt(path: Path) -> list[str]:
    entries: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def cmd_parse_version(args: argparse.Namespace) -> int:
    raw = subprocess.run(
        ["specify", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    version = raw.rsplit(" ", 1)[-1].strip()
    if not version:
        print(f"::error::Could not parse version from: {raw}")
        return 1
    emit(version=version)
    print(f"Installed CLI version: {version}")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    needs_update = False
    regen = False

    if PRERELEASE_RE.search(args.cli):
        print(f"Skipping pre-release CLI version: {args.cli}")
    elif args.cli == args.current:
        print(f"Version {args.current} is already up to date.")
    else:
        print(f"Update available: {args.current} \u2192 {args.cli}")
        needs_update = True
        regen = True

    if args.force == "true":
        print("force_regenerate=true; will regenerate.")
        regen = True

    if args.event == "push":
        print("extensions.txt changed on main; will regenerate.")
        regen = True

    emit(
        needs_update="true" if needs_update else "false",
        regen="true" if regen else "false",
    )
    return 0


def cmd_regenerate(args: argparse.Namespace) -> int:
    root = args.repo.resolve()
    ext_txt = root / EXT_TXT_REL
    if not ext_txt.is_file():
        print(
            f"::error::Missing {EXT_TXT_REL.as_posix()} "
            "(default extension list for specify init --extension)."
        )
        return 1

    ext_flags: list[str] = []
    for name in parse_extensions_txt(ext_txt):
        ext_flags += ["--extension", name]

    target = root / TARGET_REL
    print("\u2550\u2550\u2550 Generating bash assets (--script sh) \u2550\u2550\u2550")

    work = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            ["specify", "init", ".", *INIT_FLAGS, *ext_flags, "--script", "sh"],
            cwd=work,
            check=True,
        )
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        for name in (".claude", ".specify"):
            shutil.copytree(work / name, target / name)
        for script in (target / ".specify").rglob("*.sh"):
            script.chmod(script.stat().st_mode | 0o111)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"\u2705  {TARGET_REL.as_posix()} updated")
    return 0


def cmd_bump_version(args: argparse.Namespace) -> int:
    plugin_json = args.plugin_json or (args.repo.resolve() / PLUGIN_JSON_REL)
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    data["version"] = args.version
    plugin_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated plugin.json version to {args.version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository checkout (default: this script's repository)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("parse-version", help="publish the installed specify-cli version").set_defaults(
        func=cmd_parse_version
    )

    decide = sub.add_parser("decide", help="decide whether to update and/or regenerate")
    decide.add_argument("--cli", required=True, help="installed specify-cli version")
    decide.add_argument("--current", required=True, help="version currently in plugin.json")
    decide.add_argument("--force", default="", help="force_regenerate workflow input")
    decide.add_argument("--event", default="", help="triggering GitHub event name")
    decide.set_defaults(func=cmd_decide)

    sub.add_parser("regenerate", help="rebuild assets/bash from a fresh specify init").set_defaults(
        func=cmd_regenerate
    )

    bump = sub.add_parser("bump-version", help="set plugin.json's version")
    bump.add_argument("--version", required=True, help="new version string")
    bump.add_argument(
        "--plugin-json",
        type=Path,
        default=None,
        help="override plugin.json path (default: <repo>/.claude-plugin/plugin.json)",
    )
    bump.set_defaults(func=cmd_bump_version)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: {' '.join(exc.cmd)} failed with exit {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
