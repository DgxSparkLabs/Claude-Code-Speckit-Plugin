---
name: "upgrade"
description: "Upgrade Spec Kit: update the specify CLI and refresh an initialized project's Spec Kit files. Upgrades the CLI via specify self upgrade (uv tool install fallback), then runs specify integration upgrade and specify extension update. Arguments: [--dry-run] [--tag vX.Y.Z]. User-invocable only — run /speckit:upgrade; do not auto-invoke."
argument-hint: "[--dry-run] [--tag vX.Y.Z]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Move an existing Spec Kit installation to a newer version: first the real upstream `specify` CLI (PyPI package `specify-cli`, installed through `uv`), then the Spec Kit files inside the already-initialized project (integration skills, managed scripts/templates, extensions).

Do not upgrade by hand-copying files. Run the CLI's own upgrade commands and report their output.

This skill upgrades **Spec Kit**, not this plugin. To upgrade the plugin itself, the user runs:

```bash
claude plugin update speckit@claude-code-speckit-plugin
```

## When to run

Only when the user invokes `/speckit:upgrade` (optionally with `--dry-run` and/or `--tag vX.Y.Z`). Do not run this skill because a project "looks out of date".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory.

Parse `$ARGUMENTS` for `--dry-run` and `--tag vX.Y.Z`. An empty argument list means "upgrade to the latest stable release, for real". Other user wording may still inform these choices; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to upgrade: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify` right after an install, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

### 2. Check for a newer release

```bash
specify self check
```

This is **read-only**: it compares the installed version against the latest GitHub release and reports either `Up to date: X.Y.Z` or that a newer release is available. Show the output. If the CLI is already up to date and the user only asked for a CLI upgrade, say so and skip to step 4 or stop, as appropriate.

### 3. Upgrade the CLI

If `--dry-run` was given, preview first and **stop** after showing the plan (do not perform the upgrade):

```bash
specify self upgrade --dry-run
```

Otherwise upgrade in place:

```bash
# Latest stable release
specify self upgrade

# Or pin a specific release tag, when the user passed --tag
specify self upgrade --tag vX.Y.Z
```

`specify self upgrade` auto-detects the install method. `/speckit:init` installs the CLI with `uv tool install specify-cli`, so this path upgrades automatically (under the hood it runs `uv tool install specify-cli --force --from <git ref>`). Pinned tags must start with `vMAJOR.MINOR.PATCH`; suffixes are limited to dev, alpha/beta/rc, and/or build-metadata forms (for example `v1.0.0-rc1`, `v0.8.0.dev0`). Branch names, hashes, `latest`, and bare versions without `v` are rejected.

**Fallback** — for CLIs older than the release that introduced `self upgrade`, or when you want explicit control over the installer command:

```bash
# Latest stable from PyPI
uv tool install specify-cli --force

# Pin a release tag from the upstream repository
uv tool install specify-cli --force --from git+https://github.com/github/spec-kit.git@vX.Y.Z
```

Note: one-shot `uvx --from git+... specify ...` runs a temporary copy for that single command. It does **not** update a persistent `specify` installed with `uv tool install`. If a feature works through `uvx` but `specify --version` still reports an older version, upgrade the persistent CLI with one of the commands above.

### 4. Update the initialized project's Spec Kit files

Run these from the project root.

```bash
specify integration status
```

This reports the default integration, all installed integrations, and any modified or missing managed files. (`.specify/integration.json` lists them under `installed_integrations`.)

Then upgrade each installed integration key — this plugin's init uses `claude`:

```bash
specify integration upgrade claude
```

Run it once per installed integration key (for example also `specify integration upgrade codex` if that key is installed). If the command stops because manifest-tracked files were modified locally, **do not** force blindly: show the user which files changed, let them review or back them up, and only then re-run with `--force`.

Finally, update installed extensions:

```bash
specify extension update
```

With no argument this updates all installed extensions; pass `specify extension update <extension-id-or-name>` to update just one.

### 5. Verify

```bash
specify check
specify self check
```

`specify check` shows the surrounding tool environment; `specify self check` confirms the installed version against the latest release.

### 6. Report

Show the CLI output from each step, state the before/after version, and list which integrations and extensions were updated. Then give the notes below.

## Safety and notes

- **Never touched** by the manifest-aware upgrade path: your specifications and plans under `specs/` (`spec.md`, `plan.md`, `tasks.md`, …), your source code, your git history, and your constitution at `.specify/memory/constitution.md`.
- **Back up custom `.specify/scripts/` and `.specify/templates/`** before any forced refresh. Managed shared scripts and templates are refreshed only when they still match the previously recorded managed copy, but a force/refresh option overwrites local customizations:

  ```bash
  cp -r .specify/templates .specify/templates-backup
  cp -r .specify/scripts .specify/scripts-backup
  ```

  Merge your changes back manually afterwards.
- **Escape hatch, not the default:** if the project predates manifests or has missing integration metadata, a broader refresh is

  ```bash
  specify init --here --force --integration claude
  ```

  It preserves an existing `.specify/memory/constitution.md`, but it does not run the per-integration manifest checks before overwriting files. Commit first so the resulting diff is reviewable.
- **Restart the session** after project files are updated so the refreshed `/speckit-*` **project** skills under `.claude/skills/` load. Do not run `/reload-plugins` for these — they are project skills, not plugin components.
- **Upgrading this plugin** is a separate action: `claude plugin update speckit@claude-code-speckit-plugin`.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.
