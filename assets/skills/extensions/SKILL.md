---
name: "extensions"
description: "Manage Spec Kit extensions in a project via specify extension. List, search, inspect, add, update, remove, enable, disable, or set priority. The community catalog is discovery-only: never auto-install from an unvetted URL. Arguments: [list|search|add|remove|update|info|enable|disable] [name]. User-invocable only — run /speckit:extensions; do not auto-invoke."
argument-hint: "[list|search|add|remove|update|info|enable|disable] [name]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Manage Spec Kit extensions in an already-initialized project by running `specify extension …`. Extensions add workflows, templates, and integrations on top of the core CLI.

Do not add or remove extension files by hand. Run the CLI and report its output.

This plugin's `/speckit:init` enables `git` and `assess` by default (see `assets/skills/init/extensions.txt`).

## When to run

Only when the user invokes `/speckit:extensions` (optionally with a subcommand and name). Do not run this skill because a project "looks like it needs an extension".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory.

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `list` (installed extensions). Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to manage: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/`, tell the user to run `/speckit:init` first, then **stop**.

### 2. Dispatch

Use only these commands (never invent flags; `specify extension <cmd> --help` is the source of truth):

**List**

```bash
specify extension list                 # installed
specify extension list --available     # catalog
specify extension list --all           # both
```

**Search** (catalog discovery)

```bash
specify extension search [query] [--tag <str>] [--author <str>] [--verified]
```

**Info**

```bash
specify extension info <extension>
```

**Add**

```bash
specify extension add <extension> [--force] [--priority N] [--from <url>] [--dev]
```

`--dev` is a flag (install from a local directory). `--from` installs from a custom URL. `--force` overwrites if already installed. `--priority` is an integer (lower = higher precedence, default 10). `specify extension add` takes a single `{extension}` argument; do not pass several names in one invocation.

**Update**

```bash
specify extension update               # all installed
specify extension update <extension>   # one
```

**Remove**

```bash
specify extension remove <extension> [--keep-config] [--force]
```

`--keep-config` leaves config files in place. `--force` skips the CLI confirmation.

**Enable / disable** (disable does not uninstall)

```bash
specify extension enable <extension>
specify extension disable <extension>
```

**Priority**

```bash
specify extension set-priority <extension> <n>
```

Lower `n` = higher precedence.

There is also `specify extension catalog` for catalog sources; only use it if the user asked to manage catalogs.

### 3. Vetting boundary (CRITICAL)

The built-in **`community` catalog is discovery-only**. You may search it (`search`, `list --available`, `info`) so the user can inspect names, authors, and tags. You must **never auto-install** something found there.

To install an extension discovered in the community catalog:

1. Show the user the catalog entry (`specify extension info <name>`).
2. Wait for them to **vet** the source (they pick a URL they trust).
3. Only then run `specify extension add <name> --from <url>` with **that** URL.

Never invent a URL. Never pass `--from` with a catalog hit unless the user supplied the URL. Never treat "it showed up in `search`" as permission to `add`.

### 4. Confirm before destructive or forcing actions

For `remove`, `--force` on `add`/`remove`, or anything that overwrites an installed extension: **show what will change** (current `list`/`info`, whether it is already installed, whether `--keep-config` applies) and **confirm with the user** before proceeding.

Manifest-tracked local edits block non-forced operations. `--force` overwrites customizations. Do not pass `--force` unless the user asked for it after seeing that warning.

### 5. Report

Show the CLI output from each command you ran. State which extensions are now installed, enabled/disabled, and at what priority.

## Safety and notes

- **Never auto-install from an unvetted URL.** Community catalog = searchable, not installable, until the user vets a `--from` URL.
- **`--force` overwrites** an already-installed extension (on `add`) or skips confirmation (on `remove`). Confirm first.
- **`disable` is not `remove`.** Disable leaves the extension on disk; remove uninstalls it (`--keep-config` keeps its config).
- Your `specs/`, source code, git history, and constitution at `.specify/memory/constitution.md` are not the target of these commands. Back up customized extension files before a forced add/remove.
- `specify extension catalog` exists for managing catalog sources; do not add untrusted catalogs without the user asking.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit extensions: <https://github.github.io/spec-kit/reference/extensions.html>
