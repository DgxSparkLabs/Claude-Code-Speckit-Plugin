---
name: "integrations"
description: "Manage coding-agent integrations in a Spec Kit project via specify integration. List, status, install, upgrade, switch, use, uninstall, info, or search. There is no integration add (use install). This plugin's init uses claude. switch/uninstall/--force can remove or overwrite integration files. Arguments: [list|status|install|upgrade|switch|use|uninstall] [key]. User-invocable only — run /speckit:integrations; do not auto-invoke."
argument-hint: "[list|status|install|upgrade|switch|use|uninstall] [key]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Manage coding-agent **integrations** in an already-initialized project by running `specify integration …`. An integration is the agent-specific file set Spec Kit writes (skills, commands, helpers). This plugin's `/speckit:init` installs the **`claude`** integration.

There is **no** `specify integration add`. Install with `specify integration install`.

Do not copy integration files by hand. Run the CLI and report its output.

## When to run

Only when the user invokes `/speckit:integrations` (optionally with a subcommand and key). Do not run this skill because a project "looks like it is on the wrong agent".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory.

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `status` (current project) plus `list` if they asked what exists. Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to manage: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/` and the user asked to install/upgrade/switch/use/uninstall/status, tell the user to run `/speckit:init` first, then **stop**. `list`/`search`/`info` can still run without a project.

### 2. Dispatch

Use only these commands (never invent flags; `specify integration <cmd> --help` is the source of truth):

**List**

```bash
specify integration list              # available + installed status
specify integration list --catalog    # full catalog (built-in + community)
```

**Status** (read-only; does not change files)

```bash
specify integration status
specify integration status --json
```

**Install** — there is no `add`:

```bash
specify integration install <key> [--script sh|ps|py] [--force] [--integration-options="<opts>"]
```

`<key>` is required (for example `claude`, `copilot`). `--script` defaults from `init-options.json` or the platform. This plugin always inits with `--script sh`; prefer `sh` unless the user asked otherwise. `--force` allows multi-install when integrations are not declared safe.

**Upgrade** — reinstall with diff-aware file handling. Manifest hashes detect locally modified files and **block** the upgrade unless `--force`:

```bash
specify integration upgrade [key] [--force] [--script sh|ps|py] [--integration-options="<opts>"]
```

Omitting `key` upgrades the current (default) integration.

**Switch** — leave the current integration for a different one:

```bash
specify integration switch <target> [--force] [--script sh|ps|py] [--refresh-shared-infra] [--integration-options="<opts>"]
```

`--force` forces removal of modified files while uninstalling the previous integration. `--refresh-shared-infra` also overwrites shared infrastructure files even if customized (otherwise customizations are preserved).

**Use** — set the default integration **without** uninstalling others:

```bash
specify integration use <key> [--force]
```

`--force` overwrites existing shared infrastructure files, including customizations, while changing the default.

**Uninstall**

```bash
specify integration uninstall [key] [--force]
```

Omitting `key` uninstalls the current integration. Without `--force`, modified files are preserved. `--force` removes files even if modified.

**Info / search**

```bash
specify integration info <integration_id>
specify integration search [query] [--tag <str>] [--author <str>]
```

There is also `specify integration catalog` (catalog sources) and `specify integration scaffold` (author a minimal integration package). Only use those if the user asked.

### 3. Confirm before destructive or forcing actions

`switch`, `uninstall`, `upgrade --force`, `install --force`, `use --force`, and `--refresh-shared-infra` can **remove or overwrite integration files**.

Before any of those:

1. Run `specify integration status` and show the default, the installed keys, and any modified or missing managed files.
2. Explain what the chosen command will do (switch uninstalls the previous integration; uninstall deletes that key's files; `--force` overwrites local customizations; `use` does not uninstall others).
3. **Confirm with the user**, then proceed.

Manifest-tracked local edits block non-forced `upgrade`/`uninstall`. Do not pass `--force` unless the user asked for it after seeing that warning.

This plugin's init uses `claude`. Switching away from `claude` will remove or stop using the `.claude/` skills this plugin relies on — say that out loud before switching.

### 4. Report

Show the CLI output. State the default integration, every installed key, and any remaining modified/missing managed files (`specify integration status` after a mutating command).

## Safety and notes

- **No `integration add`.** Use `install`.
- **`switch` / `uninstall` / `--force` are destructive.** They can remove or overwrite integration files, including local customizations. Confirm first.
- **`use` is not `switch`.** `use` only changes the default; other integrations stay installed.
- **`--force` on upgrade/uninstall** overwrites or deletes modified managed files. Back them up if the user still wants the edits:

  ```bash
  cp -r .specify/templates .specify/templates-backup
  cp -r .specify/scripts .specify/scripts-backup
  ```

- **Never touched** by a careful (non-forced) integration change: your specifications and plans under `specs/`, your source code, your git history, and your constitution at `.specify/memory/constitution.md`.
- **Restart the session** after integration files change so `/speckit-*` **project** skills under `.claude/skills/` (or the other agent's directory) reload. Do not run `/reload-plugins` for these — they are project skills, not plugin components.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit integrations: <https://github.github.io/spec-kit/reference/integrations.html>
