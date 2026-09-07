#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Smoke tests for scripts/list_skills.py and scripts/assert_skills.py.

Not a pytest suite: run with `uv run tests/test_list_skills.py`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIST_SKILLS = REPO / "scripts" / "list_skills.py"
ASSERT_SKILLS = REPO / "scripts" / "assert_skills.py"


def load_list_skills():
    spec = importlib.util.spec_from_file_location("list_skills", LIST_SKILLS)
    if spec is None or spec.loader is None:
        fail(f"cannot import {LIST_SKILLS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def try_dir_symlink(target: Path, dest: Path) -> bool:
    """Create a directory symlink. Return False (skip) if the OS refuses."""
    try:
        dest.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError) as exc:
        print(f"SKIP (cannot create directory symlink: {exc})")
        return False


def run(script: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=check,
    )


def fail(message: str) -> None:
    raise SystemExit(message)


def expect(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def write_skill(root: Path, directory: str, frontmatter: str | None) -> None:
    skill_dir = root / "skills" / directory
    skill_dir.mkdir(parents=True)
    body = "---\n" + (frontmatter or "") + "---\n\n# skill\n"
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")


def test_repo_enumerates_init() -> None:
    proc = run(LIST_SKILLS)
    expect(proc.returncode == 0, f"list_skills failed: {proc.stderr}")
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    expect("init" in names, f"expected 'init' in {names}")
    expect(names == sorted(names), f"names not sorted: {names}")

    proc_json = run(LIST_SKILLS, "--json")
    expect(proc_json.returncode == 0, f"list_skills --json failed: {proc_json.stderr}")
    payload = json.loads(proc_json.stdout)
    expect(isinstance(payload, list) and payload, f"bad json: {proc_json.stdout!r}")
    expect(payload[0]["name"] == "init", f"json name: {payload}")
    expect(payload[0]["dir"] == "init", f"json dir: {payload}")
    expect(payload[0]["path"] == "skills/init/SKILL.md", f"json path: {payload}")


def test_empty_root_is_nonzero() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        proc = run(LIST_SKILLS, "--root", tmp)
    expect(proc.returncode != 0, "empty root must exit non-zero")
    expect("no skills found" in proc.stderr, f"stderr: {proc.stderr!r}")
    expect(proc.stdout.strip() == "", f"stdout should be empty, got {proc.stdout!r}")


def test_frontmatter_name_and_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "alpha-dir", 'name: "renamed"\n')
        write_skill(root, "beta", "description: no name here\n")
        proc = run(LIST_SKILLS, "--root", str(root), "--json")
        expect(proc.returncode == 0, proc.stderr)
        payload = json.loads(proc.stdout)
        by_dir = {row["dir"]: row["name"] for row in payload}
        expect(by_dir == {"alpha-dir": "renamed", "beta": "beta"}, f"got {by_dir}")


def test_assert_listing_and_installed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "demo", "name: demo\n")
        listing = root / "listing.txt"
        listing.write_text("Available Skills\n  demo\n", encoding="utf-8")
        installed = root / "cache" / "mp" / "plugin" / "1.0.0"
        (installed / "skills" / "demo").mkdir(parents=True)
        (installed / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")

        ok = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--listing",
            str(listing),
            "--installed-root",
            str(root / "cache"),
        )
        expect(ok.returncode == 0, f"expected pass: {ok.stdout}\n{ok.stderr}")

        listing.write_text("Available Skills\n  other\n", encoding="utf-8")
        bad_list = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--listing",
            str(listing),
        )
        expect(bad_list.returncode != 0, "missing listing must fail")
        expect("MISSING" in bad_list.stderr, bad_list.stderr)

        empty_root = root / "empty"
        empty_root.mkdir()
        bad_disk = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--installed-root",
            str(empty_root),
        )
        expect(bad_disk.returncode != 0, "missing SKILL.md must fail")


def test_assert_plugin_registry_install_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "demo", "name: demo\n")
        install = root / "installed-copy"
        (install / "skills" / "demo").mkdir(parents=True)
        (install / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        registry = root / "installed_plugins.json"
        registry.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {
                        "speckit@claude-code-speckit-plugin": [
                            {"scope": "project", "installPath": str(install)}
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        proc = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--plugin-id",
            "speckit@claude-code-speckit-plugin",
            "--plugin-registry",
            str(registry),
        )
        expect(proc.returncode == 0, f"registry path should count: {proc.stdout}\n{proc.stderr}")


def test_assert_plugin_id_missing_registry_fails() -> None:
    """--plugin-id alone against a missing registry must not vacuous-pass."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "demo", "name: demo\n")
        missing_registry = root / "no-such-registry.json"
        proc = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--plugin-id",
            "speckit@claude-code-speckit-plugin",
            "--plugin-registry",
            str(missing_registry),
        )
        expect(
            proc.returncode != 0,
            f"missing registry must fail: {proc.stdout}\n{proc.stderr}",
        )
        expect("plugin registry not found" in proc.stderr, proc.stderr)
        expect("nothing to assert against" in proc.stderr, proc.stderr)
        expect("all 1 skill(s) present" not in proc.stdout, proc.stdout)


def test_assert_empty_expected_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "listing.txt"
        listing.write_text("nothing\n", encoding="utf-8")
        proc = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            tmp,
            "--listing",
            str(listing),
        )
    expect(proc.returncode != 0, "empty expected set must fail")


def test_discover_follows_skill_dir_symlink() -> None:
    """A skills/<name> directory that is a symlink to a real skill must be enumerated."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        real = root / "real" / "speckit-linked"
        real.mkdir(parents=True)
        (real / "SKILL.md").write_text(
            "---\nname: speckit-linked\n---\n\n# skill\n",
            encoding="utf-8",
        )
        skills = root / "skills"
        skills.mkdir()
        dest = skills / "speckit-linked"
        if not try_dir_symlink(real, dest):
            return
        found = load_list_skills().discover_skills(root)
        names = [skill["name"] for skill in found]
        expect("speckit-linked" in names, f"symlinked skill missing from {found}")
        linked = next(skill for skill in found if skill["name"] == "speckit-linked")
        expect(linked["dir"] == "speckit-linked", f"dir: {linked}")
        expect(linked["path"] == "skills/speckit-linked/SKILL.md", f"path: {linked}")


def test_discover_excludes_broken_symlink_without_raising() -> None:
    """A dangling skills/<name> symlink is skipped; siblings are still found."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "alive", "name: alive\n")
        dest = root / "skills" / "speckit-dead"
        missing = root / "missing-target"
        if not try_dir_symlink(missing, dest):
            return
        found = load_list_skills().discover_skills(root)
        names = [skill["name"] for skill in found]
        expect("alive" in names, f"sibling skill missing from {found}")
        expect("speckit-dead" not in names, f"broken symlink must be excluded: {found}")


def main() -> int:
    os.chdir(REPO)
    tests = [
        test_repo_enumerates_init,
        test_empty_root_is_nonzero,
        test_frontmatter_name_and_fallback,
        test_assert_listing_and_installed,
        test_assert_plugin_registry_install_path,
        test_assert_plugin_id_missing_registry_fails,
        test_assert_empty_expected_fails,
        test_discover_follows_skill_dir_symlink,
        test_discover_excludes_broken_symlink_without_raising,
    ]
    for test in tests:
        print(f"RUN {test.__name__}")
        test()
        print(f"OK  {test.__name__}")
    print(f"all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
