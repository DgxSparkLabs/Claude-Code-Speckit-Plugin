# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Generate README.md for the Claude-Code-Speckit-Plugin.

The README is a build artifact. The plugin skill catalog is derived from
``skills/`` (the installable set of authored plugin skills). The post-init project-skill
catalog is derived from ``assets/bash/.claude/skills/``. The CLI reference
is derived from live ``specify --help`` output.

    uv run scripts/generate_readme.py

The daily asset-update workflow runs it automatically so the README tracks
the installed PyPI ``specify-cli`` version recorded in plugin.json.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = "DgxSparkLabs/Claude-Code-Speckit-Plugin"
ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_SKILLS_DIR = ROOT / "skills"
SNAPSHOT_SKILLS_DIR = ROOT / "assets" / "bash" / ".claude" / "skills"
EXTENSIONS_TXT = ROOT / "assets" / "skills" / "init" / "extensions.txt"
README = ROOT / "README.md"

ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")

# Project-skill grouping after init. Names match snapshot SKILL.md `name:`.
ANALYSIS_SKILLS = {"speckit-analyze", "speckit-checklist", "speckit-taskstoissues"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> dict:
    """Return the YAML frontmatter of a SKILL.md file as a dict."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} has no YAML frontmatter")
    end = text.index("\n---", 3)
    return yaml.safe_load(text[3:end]) or {}


def collect_skills(skills_dir: Path) -> list[dict]:
    """Collect ``*/SKILL.md`` as {name, description, group}."""
    skills: list[dict] = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = parse_frontmatter(skill_md)
        name = fm["name"]
        if name.startswith("speckit-git-"):
            group = "Git Integration"
        elif name in ANALYSIS_SKILLS:
            group = "Analysis & Quality"
        else:
            group = "Core Workflow"
        skills.append(
            {
                "name": name,
                "description": fm.get("description", "").strip(),
                "group": group,
            }
        )
    return skills


def default_extensions() -> list[str]:
    """Names from ``assets/skills/init/extensions.txt`` (comments/blanks skipped)."""
    if not EXTENSIONS_TXT.is_file():
        sys.exit(f"error: missing {EXTENSIONS_TXT.relative_to(ROOT)}")
    entries: list[str] = []
    for raw in EXTENSIONS_TXT.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    if not entries:
        sys.exit(f"error: {EXTENSIONS_TXT.relative_to(ROOT)} has no extension entries")
    return entries


def specify_commands() -> tuple[str, list[tuple[str, str]]]:
    """Return (tagline, [(command, description)]) parsed from ``specify --help``."""
    try:
        proc = subprocess.run(
            ["specify", "--help"],
            capture_output=True,
            text=True,
            env={**_clean_env(), "COLUMNS": "100"},
        )
    except FileNotFoundError:
        sys.exit(
            "error: 'specify' CLI not found. Install it first:\n"
            "  uv tool install specify-cli"
        )

    if proc.returncode != 0:
        sys.exit(
            f"error: 'specify --help' exited {proc.returncode}:\n{proc.stderr.strip()}"
        )

    lines = [ANSI.sub("", ln).rstrip() for ln in proc.stdout.splitlines()]

    tagline = ""
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Usage:"):
            for nxt in lines[i + 1 :]:
                if nxt.strip():
                    tagline = nxt.strip()
                    break
            break

    commands: list[tuple[str, str]] = []
    in_commands = False
    for ln in lines:
        if "─ Commands" in ln:
            in_commands = True
            continue
        if in_commands:
            if ln.startswith("└") or ln.startswith("┌"):
                break
            body = ln.strip().strip("│").strip()
            if not body:
                continue
            # Continuation line (wrapped description): no new command token, so
            # the row begins with lowercased description text under the previous
            # command. Detect by checking the raw indentation inside the border.
            inner = re.sub(r"^│\s?", "", ln)
            inner = re.sub(r"\s?│$", "", inner)
            if inner[:2] == "  " and commands:
                cmd, desc = commands[-1]
                commands[-1] = (cmd, f"{desc} {body}")
                continue
            parts = body.split(None, 1)
            cmd = parts[0]
            desc = parts[1].strip() if len(parts) > 1 else ""
            commands.append((cmd, desc))

    if not commands:
        sys.exit(
            "error: parsed no commands from 'specify --help'; the CLI output "
            "format may have changed"
        )
    return tagline, commands


def _clean_env() -> dict:
    import os

    env = dict(os.environ)
    env.pop("NO_COLOR", None)
    return env


def md_table(rows: list[tuple[str, ...]], header: tuple[str, ...]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def format_skill_names(names: list[str]) -> str:
    """Join skill names as `` `a` ``, `` `a` and `b` ``, or Oxford-comma."""
    ticks = [f"`{n}`" for n in names]
    if not ticks:
        return ""
    if len(ticks) == 1:
        return ticks[0]
    if len(ticks) == 2:
        return f"{ticks[0]} and {ticks[1]}"
    return ", ".join(ticks[:-1]) + f", and {ticks[-1]}"


def ships_noun_phrase(plugin_skills: list[dict]) -> str:
    """e.g. 'one skill, `init`' or '2 skills: `init` and `upgrade`'."""
    names = [s["name"] for s in plugin_skills]
    listed = format_skill_names(names)
    n = len(names)
    if n == 1:
        return f"one skill, {listed}"
    return f"{n} skills: {listed}"


def grouped_skill_tables(
    skills: list[dict], command_fmt
) -> str:
    """Render Core / Analysis / Git tables. ``command_fmt(name) -> cell``."""
    groups = ["Core Workflow", "Analysis & Quality", "Git Integration"]
    parts: list[str] = []
    for group in groups:
        rows = [
            (s["name"], f"`{command_fmt(s['name'])}`", s["description"])
            for s in skills
            if s["group"] == group
        ]
        if not rows:
            continue
        parts.append(f"### {group}\n")
        parts.append(md_table(rows, ("Skill", "Command", "Description")))
        parts.append("")
    return "\n".join(parts).rstrip()


def render() -> str:
    plugin = read_json(PLUGIN_JSON)
    marketplace = read_json(MARKETPLACE_JSON)
    plugin_name = plugin["name"]
    version = plugin["version"]
    marketplace_name = marketplace["name"]

    plugin_skills = collect_skills(PLUGIN_SKILLS_DIR)
    if not plugin_skills:
        sys.exit("error: found no skills under skills/*/SKILL.md")

    project_skills = collect_skills(SNAPSHOT_SKILLS_DIR)
    if not project_skills:
        sys.exit(
            "error: found no project skills under "
            "assets/bash/.claude/skills/*/SKILL.md"
        )

    plugin_rows = [
        (s["name"], f"`/{plugin_name}:{s['name']}`", s["description"])
        for s in plugin_skills
    ]
    plugin_table = md_table(plugin_rows, ("Skill", "Command", "Description"))

    project_section = grouped_skill_tables(
        project_skills, lambda name: f"/{name}"
    )

    ships_noun = ships_noun_phrase(plugin_skills)
    skill_names = format_skill_names([s["name"] for s in plugin_skills])
    if len(plugin_skills) == 1:
        ships = (
            f"The plugin ships {ships_noun}. It is a thin wrapper "
            "around the real `specify` CLI."
        )
    else:
        ships = f"The plugin ships {ships_noun}."

    npx_skill_flags = "\n".join(
        f"npx skills add {REPO} --skill {s['name']}" for s in plugin_skills
    )
    npx_direct_paths = "\n".join(
        f"npx skills add https://github.com/{REPO}/tree/main/skills/{s['name']}"
        for s in plugin_skills
    )
    npx_remove_args = " ".join(s["name"] for s in plugin_skills)

    extensions = default_extensions()
    ext_list = ", ".join(f"`{e}`" for e in extensions)

    tagline, commands = specify_commands()
    cli_rows = [(f"`{c}`", d) for c, d in commands]
    cli_table = md_table(cli_rows, ("Command", "Description"))

    badges = " ".join(
        [
            f"[![Compat Tests](https://github.com/{REPO}/actions/workflows/compat-test.yml/badge.svg)]"
            f"(https://github.com/{REPO}/actions/workflows/compat-test.yml)",
            f"[![Update Spec Kit Assets](https://github.com/{REPO}/actions/workflows/update-speckit-assets.yml/badge.svg)]"
            f"(https://github.com/{REPO}/actions/workflows/update-speckit-assets.yml)",
            f"![specify-cli](https://img.shields.io/badge/specify--cli-v{version}-blue)",
            "![License](https://img.shields.io/badge/license-MIT-green)",
        ]
    )

    return f"""<!--
  This file is generated by scripts/generate_readme.py.
  Do not edit by hand: run `uv run scripts/generate_readme.py` instead.
  Plugin skills come from skills/; project-skill catalog from
  assets/bash/.claude/skills/; CLI reference from live `specify --help`
  for specify-cli v{version} (PyPI, recorded in plugin.json).
-->
# Claude-Code-Speckit-Plugin

{badges}

A [DgxSparkLabs](https://github.com/DgxSparkLabs) Claude Code plugin that ships {skill_names} for [Spec Kit](https://github.com/github/spec-kit). `/speckit:init` requires [`uv`](https://docs.astral.sh/uv/) and installs `specify-cli` from PyPI (`uv tool install specify-cli`), then runs `specify init` and enables the default extensions. `/speckit:upgrade` updates the CLI and refreshes an initialized project's Spec Kit files.

This plugin is an independent port of the upstream Spec Kit project and is not affiliated with or endorsed by GitHub.

## Why a Plugin

- Native package management: install, update, and remove it like any other plugin from Claude Code.
- The plugin skills wrap the real `specify` CLI: they install or upgrade `specify-cli` from PyPI (the same channel as this repository's snapshot) and run it in the user's project. There is no bundled no-Python substitute.

## Requirements

Installing the plugin needs either the Claude Code CLI or the `skills` CLI from Vercel, which runs through Node.js with `npx`.

Running `/speckit:init` needs **`uv`** (hard requirement). The skill then installs `specify-cli` from PyPI. A system `python3` is not required — uv provisions the interpreter. `git` is optional and only needed for Spec Kit's own git features.

The skill always uses `--script sh` on all platforms, including native Windows. Native Windows needs Git Bash or WSL to run the generated `.sh` scripts.

## Installation

### Claude Code

Install at project scope so the plugin is shared with the team via `.claude/settings.json`:

```bash
claude plugin marketplace add {REPO} --scope project
claude plugin install {plugin_name}@{marketplace_name} --scope project
```

After installing, list the skills the plugin contributes:

```bash
claude plugin details {plugin_name}@{marketplace_name}
```

The command prints the plugin's component inventory. This plugin ships {ships_noun}.

### Agent Skills (`npx skills add`)

This repository follows the [Agent Skills](https://agentskills.io) layout (`skills/<name>/SKILL.md`) used by the [`skills` CLI](https://github.com/vercel-labs/skills). It ships {ships_noun}. These commands install at project scope by default (`./<agent>/skills/`); pass `-g` only if you want a global install:

```bash
npx skills add {REPO}
npx skills add {REPO} --list
{npx_skill_flags}
```

Direct skill path:

```bash
{npx_direct_paths}
```

## Updating

### Claude Code

```bash
claude plugin update {plugin_name}@{marketplace_name} --scope project
```

After updating the plugin, run `/{plugin_name}:upgrade` so the project picks up the latest CLI, integration files, and extensions:

```
/{plugin_name}:upgrade
```

For a broader re-init of project files, `/{plugin_name}:init --force` remains available.

## Removing

### Claude Code

Uninstall the plugin from the scope it was installed into, then drop the marketplace entry if nothing else is installed from it:

```bash
claude plugin uninstall {plugin_name}@{marketplace_name} --scope project
claude plugin marketplace remove {marketplace_name} --scope project
```

### Agent Skills (`npx skills remove`)

Remove the skills the `skills` CLI installed. Running `npx skills list` shows what is installed and `npx skills remove` opens an interactive selection; pass names to remove them without prompting, add `-g` for a global install, or use `--all` to remove every skill the CLI manages in that scope:

```bash
npx skills list
npx skills remove {npx_remove_args}
```

Neither route touches the `.specify/` tree or the specs already generated in your project, so delete those yourself if you no longer want them.

## Quick Start

1. Initialize the project. The `init` skill checks for `uv`, installs `specify-cli` from PyPI, runs `specify init --integration claude` (with `--script sh`, plus `--non-interactive --ignore-agent-tools`), then `specify extension add` for each default extension ({ext_list}):
   ```
   /{plugin_name}:init
   ```
   Optional arguments: a new directory `<project-name>`, `--here` for the current directory, and `--force` when the target is non-empty or already has `.specify/`.
2. Restart the session (or open the initialized project) so the **project** skills under `.claude/skills/` load. They are `/speckit-<name>`, not plugin-namespaced `/speckit:speckit-<name>`. Do not run `/reload-plugins` for these.
3. Establish your project constitution:
   ```
   /speckit-constitution
   ```
4. Specify a new feature:
   ```
   /speckit-specify <feature description>
   ```
5. Plan the implementation:
   ```
   /speckit-plan
   ```
6. Generate dependency-ordered tasks:
   ```
   /speckit-tasks
   ```
7. Implement:
   ```
   /speckit-implement
   ```

Recommended in between: `/speckit-clarify` before plan, `/speckit-analyze` after tasks, `/speckit-checklist` as needed, then `/speckit-converge` until it reports Converged. `/speckit-taskstoissues` turns the task list into GitHub issues.

## Available Skills

{ships}

{plugin_table}

### Project skills (after `/{plugin_name}:init`)

`specify init --integration claude` writes these under the project's `.claude/skills/`. Invoke them as `/speckit-<name>`. They are not plugin components.

{project_section}

## Spec Kit CLI Reference

`/speckit:init` installs and runs this CLI (PyPI `specify-cli`). {tagline}

{cli_table}

## How This Plugin Is Generated

A snapshot of `specify init` output is kept under `assets/bash/` so reviews can diff upstream changes. The installable plugin ships {ships_noun}; users get workflow skills from the live CLI at init time.

### Generation Process

1. `uv tool install specify-cli` installs the latest stable CLI from PyPI (the same channel `/speckit:init` uses).
2. `specify init` runs with `--script sh` and `--extension` for each entry in `assets/skills/init/extensions.txt`.
3. The resulting `.claude/` and `.specify/` directories are copied into `assets/bash/`.
4. `scripts/build_skills.py` syncs every authored skill from `assets/skills/*` into `skills/`.
5. `scripts/generate_readme.py` regenerates this README from `skills/`, the snapshot project skills, and the current `specify --help` output.

### How `init` Bootstraps a Project

When a user runs `/{plugin_name}:init`, the skill:

1. Ensures `uv` is installed (and tells the user how to install it if not).
2. Runs `uv tool install specify-cli` (PyPI, latest stable, unpinned).
3. Runs `specify init` with `--integration claude`, `--script sh`, `--non-interactive --ignore-agent-tools`, a project name or `--here`, and `--force` when the target is non-empty or already contains `.specify/`.
4. Optionally prompts to add or remove default extensions, then runs `specify extension add <name>` for each (defaults: {ext_list}, from `assets/skills/init/extensions.txt`).

After init, Spec Kit workflow commands live in the project as `/speckit-<name>` under `.claude/skills/`.

### Staying Aligned With Upstream

A [GitHub Actions workflow](/.github/workflows/update-speckit-assets.yml) runs daily to keep the snapshot in sync with PyPI:

1. Install: `uv tool install specify-cli` (latest stable from PyPI). The version written to plugin.json is parsed from `specify --version`, not a GitHub release tag.
2. Compare: if that CLI version differs from `.claude-plugin/plugin.json`, regenerate. A push to `assets/skills/init/extensions.txt` (or `workflow_dispatch` with `force_regenerate`) regenerates even when the version is unchanged.
3. Regenerate: `assets/bash/` is rebuilt from `specify init`, and `skills/` is synced from `assets/skills/*`.
4. Bump: `.claude-plugin/plugin.json` is updated when the installed CLI version differed.
5. README: `scripts/generate_readme.py` refreshes this file.
6. PR: the workflow opens a pull request (for example, `auto/update-speckit-<version>`) and enables auto-merge, so a clean update with no conflicts merges once checks pass.

## Troubleshooting

`Current directory is not empty and --non-interactive was set` (from `specify init`) means the target already has files — including an existing `.specify/` directory. Re-run `/{plugin_name}:init --force` to merge into it.

If `uv` is missing, install it from [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) and rerun `/speckit:init`. If `specify` is not on `PATH` after `uv tool install specify-cli`, invoke it as `uv tool run specify`.

Skills that do not appear, or a `Skills (0)` inventory, mean the agent loaded none of the plugin's components. This plugin should list {ships_noun}. Confirm with `claude plugin details {plugin_name}@{marketplace_name}` for the plugin route, or with `npx skills add {REPO} --list` for the Agent Skills route. After init, workflow commands are project skills (`/speckit-specify`, …) in that project's `.claude/skills/`; restart the session rather than `/reload-plugins`.

On native Windows the skill uses `--script sh`; Git Bash or WSL is needed to run the generated `.sh` scripts.

## License

MIT
"""


def main() -> None:
    README.write_text(render(), encoding="utf-8")
    print(f"Wrote {README.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
