---
name: "doctor"
description: "Read-only Spec Kit health check. Runs specify check (required tools), specify self check (is the installed CLI the latest release), and, inside an initialized project, specify integration status to report the default integration and any modified or missing managed files. Changes nothing. Arguments: [--json]. User-invocable only — run /speckit:doctor; do not auto-invoke."
argument-hint: "[--json]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Report the health of the Spec Kit installation and, when run inside an initialized project, the health of that project's Spec Kit files. Everything this skill runs is **read-only**: it inspects, it never installs, upgrades, or rewrites anything.

Do not diagnose by poking at files by hand. Run the CLI's own diagnostic commands and report their output, then recommend a next action.

## When to run

Only when the user invokes `/speckit:doctor` (optionally with `--json`). Do not run this skill because something "looks broken"; a failing Spec Kit command is not an invitation to auto-invoke it.

## Execution

Run from the user's project root (the directory containing `.specify/`) when there is one. Outside a project, steps 2 and 3 still work; step 4 is skipped.

Parse `$ARGUMENTS` for `--json`. An empty argument list means "human-readable report".

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to diagnose: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

### 2. Check the tool environment

```bash
specify check
```

Reports whether the required and optional tools Spec Kit relies on are installed and visible. It takes no options. Show the output.

### 3. Check the CLI version

```bash
specify self check
```

**Read-only.** It compares the installed `specify-cli` against the latest release and reports either that you are up to date or that a newer release exists. It does not modify the installation. Show the output.

### 4. Check the project (only inside an initialized project)

Only if the working directory contains `.specify/`:

```bash
specify integration status
```

Add `--json` when the user passed it:

```bash
specify integration status --json
```

This reports the current project's integration status **without changing files**: the default integration, the installed integrations, and any managed files that are modified or missing.

If the user asked for a fuller picture, these are also read-only and safe to add:

```bash
specify integration list
specify extension list
specify preset list
specify bundle list
```

If the directory has no `.specify/`, say so plainly — the project is not initialized, and `/speckit:init` is the fix. Do not run `specify init` from this skill.

### 5. Report

Summarize in one place:

- `uv` and `specify` versions.
- Missing required tools from `specify check`.
- Whether a newer CLI release is available.
- The default integration, installed integrations, and any modified or missing managed files.

Then recommend a next action:

- Newer CLI release available, or managed project files out of date → recommend `/speckit:upgrade`.
- No `.specify/` in the directory → recommend `/speckit:init`.
- Locally modified managed files → point them out by name and let the user decide; a forced refresh would overwrite those edits.
- Everything clean → say so and stop.

## Safety and notes

- **Nothing here writes.** `specify check`, `specify self check`, and `specify integration status` only inspect. If a fix is needed, hand it off to `/speckit:upgrade` or `/speckit:init` rather than running an upgrade from this skill.
- **Do not "fix while you're in there."** Report modified managed files; do not run `--force` anything. Forced refreshes overwrite local customizations.
- **`specify check` is about the environment**, not your specs. Your `specs/`, source code, git history, and `.specify/memory/constitution.md` are never touched by this skill.
- **Upgrading this plugin** is separate from upgrading Spec Kit: `claude plugin update speckit@claude-code-speckit-plugin`.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit CLI reference: <https://github.github.io/spec-kit/reference/overview.html>
