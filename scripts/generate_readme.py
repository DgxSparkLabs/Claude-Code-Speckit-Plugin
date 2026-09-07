# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Generate README.md for the Claude-Code-Speckit-Plugin.

The README is a build artifact: its skill catalog is derived from the skills this
repository ships under ``skills/`` and its CLI reference is derived from the live
``specify --help`` output. Run this whenever the assets or plugin manifest
change:

    uv run scripts/generate_readme.py

The daily asset-update workflow runs it automatically so the README never drifts
from the bundled spec-kit version.
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
README = ROOT / "README.md"

ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")

# Skill grouping. Names are matched exactly or by the ``speckit-git-`` prefix.
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


def collect_skills(plugin_name: str) -> list[dict]:
    """Collect the shipped ``skills/*`` as {name, command, description, group}.

    Top-level ``skills/`` is the installable set: ``init`` plus the bundled
    ``speckit-*`` copies of ``assets/bash/.claude/skills/``. Installed as a
    Claude Code plugin every skill is namespaced ``/<plugin>:<skill>``.
    """
    skills: list[dict] = []

    for skill_md in sorted(PLUGIN_SKILLS_DIR.glob("*/SKILL.md")):
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
                "command": f"/{plugin_name}:{name}",
                "description": fm.get("description", "").strip(),
                "group": group,
            }
        )

    if not skills:
        sys.exit("error: found no skills under skills/*/SKILL.md")
    return skills


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
            "  uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
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


def render() -> str:
    plugin = read_json(PLUGIN_JSON)
    marketplace = read_json(MARKETPLACE_JSON)
    plugin_name = plugin["name"]
    version = plugin["version"]
    marketplace_name = marketplace["name"]

    skills = collect_skills(plugin_name)
    groups = ["Core Workflow", "Analysis & Quality", "Git Integration"]

    skills_md = []
    for group in groups:
        rows = [
            (s["name"], f"`{s['command']}`", s["description"])
            for s in skills
            if s["group"] == group
        ]
        if not rows:
            continue
        skills_md.append(f"### {group}\n")
        skills_md.append(md_table(rows, ("Skill", "Command", "Description")))
        skills_md.append("")
    skills_section = "\n".join(skills_md).rstrip()

    tagline, commands = specify_commands()
    cli_rows = [(f"`{c}`", d) for c, d in commands]
    cli_table = md_table(cli_rows, ("Command", "Description"))

    badges = " ".join(
        [
            f"[![Compat Tests](https://github.com/{REPO}/actions/workflows/compat-test.yml/badge.svg)]"
            f"(https://github.com/{REPO}/actions/workflows/compat-test.yml)",
            f"[![Update Spec Kit Assets](https://github.com/{REPO}/actions/workflows/update-speckit-assets.yml/badge.svg)]"
            f"(https://github.com/{REPO}/actions/workflows/update-speckit-assets.yml)",
            f"![Spec Kit](https://img.shields.io/badge/spec--kit-v{version}-blue)",
            "![License](https://img.shields.io/badge/license-MIT-green)",
        ]
    )

    return f"""<!--
  This file is generated by scripts/generate_readme.py.
  Do not edit by hand: run `uv run scripts/generate_readme.py` instead.
  The skill catalog and CLI reference are derived from the bundled assets and
  the live `specify --help` output for spec-kit v{version}.
-->
# Claude-Code-Speckit-Plugin

{badges}

A [DgxSparkLabs](https://github.com/DgxSparkLabs) Claude Code plugin that installs [Spec Kit](https://github.com/github/spec-kit) into any project. It bundles the spec-kit templates, scripts, and workflow skills so you can run the full specification-driven workflow without installing Python or the `specify` CLI.

This plugin is an independent port of the upstream Spec Kit project and is not affiliated with or endorsed by GitHub.

## Why a Plugin

The upstream Spec Kit CLI requires Python. This plugin bundles the generated assets as a native agent plugin, which means:

- Native package management: install, update, and remove it like any other plugin from Claude Code.
- CLI compatible: projects initialized by the plugin remain fully compatible with the `specify` CLI if you later switch.

## Installation

### Claude Code

Install at project scope so the plugin is shared with the team via `.claude/settings.json`:

```bash
claude plugin marketplace add {REPO} --scope project
claude plugin install {plugin_name}@{marketplace_name} --scope project
```

### Agent Skills (`npx skills add`)

This repository follows the [Agent Skills](https://agentskills.io) layout (`skills/<name>/SKILL.md`) used by the [`skills` CLI](https://github.com/vercel-labs/skills). These commands install at project scope by default (`./<agent>/skills/`); pass `-g` only if you want a global install:

```bash
npx skills add {REPO}
```

List skills first, or install only `init`:

```bash
npx skills add {REPO} --list
npx skills add {REPO} --skill init
```

Direct skill path:

```bash
npx skills add https://github.com/{REPO}/tree/main/skills/init
```

## Updating

### Claude Code

```bash
claude plugin update {plugin_name}@{marketplace_name} --scope project
```

After updating the plugin, re-initialize your project to pick up the latest assets:

```
/{plugin_name}:init --force
```

## Quick Start

1. Initialize your project with Spec Kit infrastructure:
   ```
   /{plugin_name}:init
   ```
2. Establish your project constitution:
   ```
   /{plugin_name}:speckit-constitution
   ```
3. Specify a new feature:
   ```
   /{plugin_name}:speckit-specify <feature description>
   ```
4. Plan the implementation:
   ```
   /{plugin_name}:speckit-plan
   ```
5. Generate dependency-ordered tasks:
   ```
   /{plugin_name}:speckit-tasks
   ```
6. Implement:
   ```
   /{plugin_name}:speckit-implement
   ```

## Available Skills

{skills_section}

## Spec Kit CLI Reference

The bundled assets track the `specify` CLI. {tagline}

{cli_table}

## How This Plugin Is Generated

The plugin assets are generated from the upstream `specify` CLI and kept in sync automatically as upstream evolves.

### Generation Process

1. `specify init` runs with `--script sh` and the bundled Spec Kit extensions.
2. The resulting `.claude/` and `.specify/` directories are copied into `assets/bash/`.
3. `skills/speckit-*` is mirrored from `assets/bash/.claude/skills/` so the plugin and `npx skills` both discover the workflow skills.
4. `scripts/generate_readme.py` regenerates this README from the new assets and the current `specify --help` output.

### How `init` Bootstraps a Project

When a user runs `/{plugin_name}:init`, the plugin copies the pre-generated `.specify/` tree into the project root. Spec Kit workflow skills are copied into `.claude/skills/` only in standalone mode (`CLAUDE_PLUGIN_ROOT` unset); when the plugin is installed they are already provided. Native Windows uses Git Bash or WSL for the bundled `.sh` scripts. No Python or `specify` CLI is required. User content in `.claude/` is preserved: only plugin-owned paths are replaced.

### Staying Aligned With Upstream

A [GitHub Actions workflow](/.github/workflows/update-speckit-assets.yml) runs daily to keep the plugin in sync:

1. Detect: the workflow checks the [latest stable release](https://github.com/github/spec-kit/releases) of `github/spec-kit` and compares it to the version in `.claude-plugin/plugin.json`. Pre-release versions (dev, alpha, beta, rc) are skipped.
2. Regenerate: if a newer stable release exists, `assets/bash/` is regenerated from scratch and `skills/speckit-*` is re-synced from it.
3. Bump: `.claude-plugin/plugin.json` is updated to the new version.
4. README: `scripts/generate_readme.py` refreshes the skill catalog and CLI reference.
5. PR: the workflow opens a pull request (for example, `auto/update-speckit-<version>`) and enables auto-merge, so a clean update with no conflicts merges once checks pass.

## License

MIT
"""


def main() -> None:
    README.write_text(render(), encoding="utf-8")
    print(f"Wrote {README.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
