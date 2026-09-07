#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Assert every enumerated repo skill is present in a listing and/or on disk.

Used by CI so the expected set is always driven by `scripts/list_skills.py`
rather than a hardcoded name like "init".

Checks (at least one required):

    --listing FILE             each skill *name* appears as a token in FILE
    --installed-root DIR       SKILL.md exists under DIR at
                               `skills/<dir>/SKILL.md` or `skills/<name>/SKILL.md`
                               (direct or nested, e.g. the Claude plugin cache)
    --plugin-id NAME[@MP]      also resolve `installPath` from Claude Code's
                               `installed_plugins.json` registry

Exit status is non-zero if the expected set is empty, nothing was resolved to
assert against, or any skill is missing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")
TOKEN_CHARS = r"A-Za-z0-9_-"


def load_list_skills():
    path = Path(__file__).resolve().parent / "list_skills.py"
    spec = importlib.util.spec_from_file_location("list_skills", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_skills(raw: object) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ValueError("expected JSON array of names or {name, dir, path} objects")
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                continue
            out.append({"name": name, "dir": name, "path": f"skills/{name}/SKILL.md"})
            continue
        if not isinstance(item, dict) or "name" not in item:
            raise ValueError(f"invalid skill entry: {item!r}")
        name = str(item["name"])
        directory = str(item.get("dir") or name)
        path = str(item.get("path") or f"skills/{directory}/SKILL.md")
        out.append({"name": name, "dir": directory, "path": path})
    return out


def load_expected(*, repo: Path | None, json_path: Path | None) -> list[dict[str, str]]:
    if json_path is not None:
        return normalize_skills(json.loads(json_path.read_text(encoding="utf-8")))
    if repo is None:
        raise ValueError("pass --expected-from-repo or --expected-json")
    return load_list_skills().discover_skills(repo.resolve())


def listing_contains(text: str, name: str) -> bool:
    """True when `name` appears as a token, including namespaced `plugin:name`."""
    cleaned = ANSI.sub("", text)
    pattern = rf"(?<![{TOKEN_CHARS}]){re.escape(name)}(?![{TOKEN_CHARS}])"
    return re.search(pattern, cleaned) is not None


def skill_md_under(root: Path, skill: dict[str, str]) -> Path | None:
    """Return the first SKILL.md that belongs to this skill under root."""
    if not root.exists():
        return None
    names = {skill["dir"], skill["name"]}
    for name in names:
        direct = root / "skills" / name / "SKILL.md"
        if direct.is_file():
            return direct
    # Nested layout used by Claude's versioned plugin cache:
    # ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/<dir>/SKILL.md
    try:
        iterator = root.rglob("SKILL.md")
    except OSError:
        return None
    for md in iterator:
        try:
            if md.parent.name in names and md.parent.parent.name == "skills" and md.is_file():
                return md
        except OSError:
            continue
    return None


def collect_registry_install_paths(registry: object, plugin_id: str) -> list[Path]:
    """Pull installPath values for plugin_id out of installed_plugins.json.

    The on-disk schema has shifted across Claude Code versions; walk both the
    keyed `plugins["name@marketplace"]` form and records with a `name` field.
    """
    name, _, marketplace = plugin_id.partition("@")
    keys = {plugin_id, name}
    if marketplace:
        keys.add(f"{name}@{marketplace}")
    paths: list[Path] = []
    seen: set[str] = set()

    def add_path(value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        path = Path(value).expanduser()
        key = str(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)

    def walk(obj: object, keyed: bool) -> None:
        if isinstance(obj, dict):
            record_name = obj.get("name") or obj.get("plugin") or obj.get("id")
            this_keyed = keyed
            if isinstance(record_name, str) and (
                record_name in keys or record_name == name or record_name.startswith(f"{name}@")
            ):
                this_keyed = True
            for key, value in obj.items():
                if key in keys:
                    walk(value, True)
                    continue
                if this_keyed and key in {
                    "installPath",
                    "install_path",
                    "installDir",
                    "install_dir",
                }:
                    add_path(value)
                walk(value, this_keyed)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, keyed)

    walk(registry, False)
    return paths


def default_plugin_registry() -> Path:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    root = Path(config_dir).expanduser() if config_dir else Path.home() / ".claude"
    return root / "plugins" / "installed_plugins.json"


def dump_tree(root: Path, *, depth: int = 5) -> None:
    if not root.exists():
        print(f"  (missing) {root}", file=sys.stderr)
        return
    print(f"  {root}", file=sys.stderr)
    prefix_len = len(root.parts)
    try:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            rel_depth = len(Path(dirpath).parts) - prefix_len
            if rel_depth >= depth:
                dirnames.clear()
                continue
            for name in sorted(dirnames + filenames):
                print(f"  {Path(dirpath) / name}", file=sys.stderr)
    except OSError as exc:
        print(f"  (walk failed) {root}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expected-from-repo", type=Path, help="repo root to enumerate")
    parser.add_argument("--expected-json", type=Path, help="JSON array from list_skills.py --json")
    parser.add_argument(
        "--listing",
        type=Path,
        action="append",
        default=[],
        help="CLI output that must mention every skill name (repeatable)",
    )
    parser.add_argument(
        "--installed-root",
        type=Path,
        action="append",
        default=[],
        help="directory to search for skills/<name>/SKILL.md (repeatable)",
    )
    parser.add_argument(
        "--plugin-id",
        help="Claude plugin id (plugin@marketplace) whose installPath is also searched",
    )
    parser.add_argument(
        "--plugin-registry",
        type=Path,
        help="path to installed_plugins.json (default: ~/.claude/plugins/installed_plugins.json)",
    )
    args = parser.parse_args(argv)

    if not args.listing and not args.installed_root and not args.plugin_id:
        parser.error("pass --listing, --installed-root, and/or --plugin-id")

    try:
        expected = load_expected(repo=args.expected_from_repo, json_path=args.expected_json)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not expected:
        print("error: expected skill set is empty", file=sys.stderr)
        return 1

    listing_texts: list[tuple[Path, str]] = []
    for path in args.listing:
        listing_texts.append((path, path.read_text(encoding="utf-8", errors="replace")))

    search_roots = [path.expanduser().resolve() for path in args.installed_root]
    registry_path = args.plugin_registry
    if args.plugin_id:
        if registry_path is None:
            registry_path = default_plugin_registry()
        if registry_path.is_file():
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"error: cannot parse plugin registry {registry_path}: {exc}", file=sys.stderr)
                return 1
            for install_path in collect_registry_install_paths(registry, args.plugin_id):
                search_roots.append(install_path)
            print(f"plugin registry: {registry_path}")
        else:
            print(f"plugin registry not found: {registry_path}", file=sys.stderr)

    # De-dupe roots while preserving order.
    deduped: list[Path] = []
    seen_roots: set[str] = set()
    for root in search_roots:
        key = str(root)
        if key not in seen_roots:
            seen_roots.add(key)
            deduped.append(root)
    search_roots = deduped

    # A run that resolves neither listings nor installed roots has nothing to
    # assert against; reporting success there would be a vacuous pass. This is
    # reachable via --plugin-id alone when the registry is missing or lists no
    # install paths for the plugin.
    if not listing_texts and not search_roots:
        print(
            "error: nothing to assert against: no --listing files and no installed roots resolved",
            file=sys.stderr,
        )
        return 1

    missing = False
    for skill in expected:
        name = skill["name"]
        print(f"skill {name} (dir={skill['dir']}, path={skill['path']})")
        for path, text in listing_texts:
            if listing_contains(text, name):
                print(f"  OK listing {path}")
            else:
                print(f"  MISSING from listing {path}", file=sys.stderr)
                missing = True
        if search_roots:
            found: Path | None = None
            for root in search_roots:
                found = skill_md_under(root, skill)
                if found is not None:
                    print(f"  OK installed {found}")
                    break
            if found is None:
                print("  MISSING SKILL.md under installed roots:", file=sys.stderr)
                for root in search_roots:
                    print(f"    - {root}", file=sys.stderr)
                missing = True

    if missing:
        if search_roots:
            print("installed-root trees:", file=sys.stderr)
            for root in search_roots:
                dump_tree(root)
        for path, text in listing_texts:
            print(f"--- listing {path} ---", file=sys.stderr)
            print(text, file=sys.stderr)
        return 1

    print(f"all {len(expected)} skill(s) present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
