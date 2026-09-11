---
name: "presets"
description: "Manage Spec Kit presets (template/terminology/workflow overrides via the resolution stack) with specify preset. List, search, inspect, add, remove, enable, disable, set priority, or resolve which template wins. Presets outrank extensions; multiple can stack. Arguments: [list|search|add|remove|info|resolve] [id]. User-invocable only — run /speckit:presets; do not auto-invoke."
argument-hint: "[list|search|add|remove|info|resolve] [id]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Manage Spec Kit presets in an already-initialized project by running `specify preset …`. Presets customize templates, terminology, and workflow through the resolution stack. They are **higher-priority overrides than extensions**; several presets can be installed at once and they stack by priority (lower number = higher precedence).

Do not edit template files by hand to "apply a preset". Run the CLI and report its output.

## When to run

Only when the user invokes `/speckit:presets` (optionally with a subcommand and id). Do not run this skill because templates "look customizable".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory.

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `list` (installed presets). Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to manage: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/`, tell the user to run `/speckit:init` first, then **stop**.

### 2. Dispatch

Use only these commands (never invent flags; `specify preset <cmd> --help` is the source of truth):

**List**

```bash
specify preset list
```

**Search**

```bash
specify preset search [query] [--tag <str>] [--author <str>]
```

**Info**

```bash
specify preset info <preset_id>
```

**Add**

```bash
specify preset add <preset_id> [--from <url>] [--dev <dir>] [--priority N]
```

`--from` installs from a `.zip`, `.tar.gz`, or `.tgz` URL. `--dev` takes a **local directory path** (development mode) — it is not a boolean flag. `--priority` is an integer (lower = higher precedence, default 10). Catalog ids install without `--from` when they are in an installable catalog.

Do not auto-install a preset from an unvetted URL. If the user found it via `search`, show `info`, wait for them to vet a `--from` URL (or confirm a catalog id they trust), then add.

**Remove**

```bash
specify preset remove <preset_id>
```

There is no `--force` on `preset remove`. Show what will be removed and confirm with the user before proceeding.

**Enable / disable** (disable does not uninstall)

```bash
specify preset enable <preset_id>
specify preset disable <preset_id>
```

**Priority**

```bash
specify preset set-priority <preset_id> <n>
```

Lower `n` = higher precedence.

**Resolve** — show which template wins for a given name (for example `spec-template`):

```bash
specify preset resolve <template-name>
```

There is also `specify preset catalog` for catalog sources; only use it if the user asked to manage catalogs.

### 3. Confirm before destructive actions

For `remove` (and any add from `--from` / `--dev` that would replace what is already installed): **show what will change** (`list`/`info`, current priority, `resolve` of the templates they care about) and **confirm with the user** before proceeding.

### 4. Report

Show the CLI output. State which presets are installed, enabled/disabled, and at what priority. If the user asked about a template, include `specify preset resolve <template-name>` so they can see which layer wins.

## Safety and notes

- **Presets outrank extensions** on the resolution stack. Installing a preset can change which template a later `/speckit-*` command uses; `resolve` is how you check.
- **Multiple presets stack.** Priority is an integer; lower = higher precedence (default 10).
- **Do not invent flags.** `preset add --dev` requires a directory path. `preset remove` has no `--force`.
- **Never auto-install from an unvetted URL.** Confirm `--from` / `--dev` sources with the user.
- Your `specs/`, source code, git history, and constitution at `.specify/memory/constitution.md` are not the target of these commands.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit presets: <https://github.github.io/spec-kit/reference/presets.html>
