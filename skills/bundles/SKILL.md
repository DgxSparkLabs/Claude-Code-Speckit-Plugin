---
name: "bundles"
description: "Discover, install, and maintain Spec Kit bundles (role/team setups that compose extensions, presets, and workflows) via specify bundle. Search, inspect, list, install, update, remove, or validate. Authoring (build/init) is out of scope. Arguments: [search|info|list|install|update|remove] [id]. User-invocable only — run /speckit:bundles; do not auto-invoke."
argument-hint: "[search|info|list|install|update|remove] [id]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Manage Spec Kit **bundles** in an already-initialized project by running `specify bundle …`. A bundle is a role- or team-oriented composition of extensions, presets, and workflows. Installing one runs each primitive's own machinery; removing one uninstalls only the components **that bundle contributed** (no collateral removals).

This skill is for **discovering, installing, and maintaining** bundles. `specify bundle build` and `specify bundle init` exist for bundle **authors**; mention them only if the user asks to author a bundle, then point them at the docs rather than driving a full authoring flow.

Do not compose extensions and presets by hand to "simulate a bundle". Run the CLI and report its output.

## When to run

Only when the user invokes `/speckit:bundles` (optionally with a subcommand and id). Do not run this skill because a project "looks like it needs a team setup".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory. (`validate` can point `--path` at a bundle directory or `bundle.yml` elsewhere.)

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `list` (installed bundles). Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to manage: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/` and the user asked to install/list/update/remove (not just `search`/`info`/`validate --path`), tell the user to run `/speckit:init` first, then **stop**.

### 2. Dispatch

Use only these user-facing commands (never invent flags; `specify bundle <cmd> --help` is the source of truth):

**Search**

```bash
specify bundle search [query] [--offline] [--json]
```

**Info** — full metadata and the fully expanded component set (what `install` would add):

```bash
specify bundle info <bundle_id> [--offline] [--json]
```

**List** (installed in this project)

```bash
specify bundle list [--json]
```

**Install** — `bundle_id` may be a catalog id **or** a local path to a `.zip` artifact, a bundle directory, or a `bundle.yml`:

```bash
specify bundle install <bundle_id> [--integration <key>] [--offline]
```

`--integration` overrides the integration used while installing the bundle's components.

**Update**

```bash
specify bundle update <bundle_id> [--integration <key>] [--offline]
specify bundle update --all [--integration <key>] [--offline]
```

Pass either a `bundle_id` or `--all`. Do not invent `--all` as a positional.

**Remove** — uninstalls only components this bundle contributed:

```bash
specify bundle remove <bundle_id>
```

**Validate** — whether the manifest is well-formed and references resolve:

```bash
specify bundle validate [--path <dir-or-bundle.yml>] [--offline]
```

Default `--path` is the current working directory.

`--json` and `--offline` exist on the commands shown above; only pass them when the user asked. There is also `specify bundle catalog` for catalog sources; only use it if the user asked to manage catalogs.

### 3. Confirm before destructive or forcing actions

For `install`, `update`, and `remove`: **show what will change** first. For install/update, run `specify bundle info <id>` so the user sees the expanded component set. For remove, run `list`/`info` and remind them that only **this bundle's** contributions are uninstalled. Then **confirm with the user** before proceeding.

Do not auto-install a bundle from an unvetted catalog hit or local path. Show `info`, wait for a yes.

Manifest-tracked local edits in the underlying extensions/integrations can block non-forced primitive updates. If a nested command asks for `--force`, **stop**, show what would be overwritten, and confirm — this skill does not pass `--force` on `bundle install`/`update`/`remove` because those commands do not take it.

### 4. Report

Show the CLI output. State which bundles are installed and, after install/update/remove, which extensions/presets/workflows that changed.

## Safety and notes

- **Install composes primitives.** A bundle can add extensions, presets, and workflows in one step. Read `info` before you install so the user knows the blast radius.
- **Remove is scoped.** `bundle remove` only uninstalls what that bundle contributed; it will not strip unrelated extensions.
- **Authoring is out of scope.** `specify bundle build` produces a versioned `.zip`; `specify bundle init` is an idempotent project init that can optionally install a bundle. Point authors at the docs; do not drive those flows from this skill unless the user explicitly asks.
- **Never auto-install from an unvetted source.** Confirm catalog ids and local paths.
- Your `specs/`, source code, git history, and constitution at `.specify/memory/constitution.md` are not the target of these commands.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit bundles: <https://github.github.io/spec-kit/reference/bundles.html>
