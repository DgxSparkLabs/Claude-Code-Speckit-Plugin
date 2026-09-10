"""Smoke tests for scripts/list_skills.py and scripts/assert_skills.py.

Run with `uv run pytest`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIST_SKILLS = REPO / "scripts" / "list_skills.py"
ASSERT_SKILLS = REPO / "scripts" / "assert_skills.py"


def run(script: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=check,
    )


def write_skill(root: Path, directory: str, frontmatter: str | None) -> None:
    skill_dir = root / "skills" / directory
    skill_dir.mkdir(parents=True)
    body = "---\n" + (frontmatter or "") + "---\n\n# skill\n"
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")


def test_repo_enumerates_authored_skills() -> None:
    authored = sorted(
        p.name
        for p in (REPO / "assets" / "skills").iterdir()
        if p.is_dir()
    )
    assert set(authored) >= {"init", "upgrade"}, (
        f"expected authored skills to include init and upgrade, got {authored}"
    )

    proc = run(LIST_SKILLS)
    assert proc.returncode == 0, f"list_skills failed: {proc.stderr}"
    names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert names == authored, f"list names {names} != authored {authored}"
    assert names == sorted(names), f"names not sorted: {names}"

    proc_json = run(LIST_SKILLS, "--json")
    assert proc_json.returncode == 0, f"list_skills --json failed: {proc_json.stderr}"
    payload = json.loads(proc_json.stdout)
    assert isinstance(payload, list) and payload, f"bad json: {proc_json.stdout!r}"
    by_name = {row["name"]: row for row in payload}
    assert set(by_name) == set(authored), f"json names: {payload}"
    for name in authored:
        assert by_name[name]["dir"] == name, f"json dir for {name}: {payload}"
        assert (
            by_name[name]["path"] == f"skills/{name}/SKILL.md"
        ), f"json path for {name}: {payload}"


def test_empty_root_is_nonzero() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        proc = run(LIST_SKILLS, "--root", tmp)
    assert proc.returncode != 0, "empty root must exit non-zero"
    assert "no skills found" in proc.stderr, f"stderr: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"stdout should be empty, got {proc.stdout!r}"


def test_frontmatter_name_and_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_skill(root, "alpha-dir", 'name: "renamed"\n')
        write_skill(root, "beta", "description: no name here\n")
        proc = run(LIST_SKILLS, "--root", str(root), "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        by_dir = {row["dir"]: row["name"] for row in payload}
        assert by_dir == {"alpha-dir": "renamed", "beta": "beta"}, f"got {by_dir}"


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
        assert ok.returncode == 0, f"expected pass: {ok.stdout}\n{ok.stderr}"

        listing.write_text("Available Skills\n  other\n", encoding="utf-8")
        bad_list = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--listing",
            str(listing),
        )
        assert bad_list.returncode != 0, "missing listing must fail"
        assert "MISSING" in bad_list.stderr, bad_list.stderr

        empty_root = root / "empty"
        empty_root.mkdir()
        bad_disk = run(
            ASSERT_SKILLS,
            "--expected-from-repo",
            str(root),
            "--installed-root",
            str(empty_root),
        )
        assert bad_disk.returncode != 0, "missing SKILL.md must fail"


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
        assert proc.returncode == 0, f"registry path should count: {proc.stdout}\n{proc.stderr}"


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
        assert (
            proc.returncode != 0
        ), f"missing registry must fail: {proc.stdout}\n{proc.stderr}"
        assert "plugin registry not found" in proc.stderr, proc.stderr
        assert "nothing to assert against" in proc.stderr, proc.stderr
        assert "all 1 skill(s) present" not in proc.stdout, proc.stdout


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
    assert proc.returncode != 0, "empty expected set must fail"
