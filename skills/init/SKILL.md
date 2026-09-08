---
name: "init"
description: "Initialize a project with the real Spec Kit CLI via uv. Installs specify-cli from PyPI, runs specify init, then enables default extensions. Arguments: [<project-name>|--here] [--force]. User-invocable only — run /speckit:init; do not auto-invoke."
argument-hint: "[<project-name>|--here] [--force]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Bootstrap a project by installing and running the real upstream `specify` CLI (PyPI package `specify-cli`) through `uv`. This is not a bundled substitute: `uv` is required, the CLI is required, and a system `python3` is not (uv provisions the interpreter). `git` is optional and only needed for Spec Kit's own git features.

Do not implement init by copying files by hand. Install the CLI, run `specify init`, enable extensions, then report the CLI output and the workflow below.

## When to run

Only when the user invokes `/speckit:init` (optionally with a project name, `--here`, and/or `--force`). Do not run this skill because a project "looks uninitialized".

## Execution

Working directory **must** be the user's project root, not this skill directory.

Resolve `<skill-dir>`: use `${CLAUDE_SKILL_DIR}` when it is an existing directory, otherwise the directory that contains this `SKILL.md`.

### 1. Ensure `uv` is installed

Run `uv --version`. If `uv` is missing, tell the user how to install it, then **stop** (do not proceed without `uv`):

- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`

Ask them to restart the shell so `uv` is on `PATH`, then rerun `/speckit:init`.

### 2. Install or refresh the CLI

```bash
uv tool install specify-cli
```

This installs the latest stable `specify-cli` from PyPI (unpinned). To refresh an existing install, use `uv tool install specify-cli --force`.

Invoke the CLI as `specify`. If the shell cannot find it after install, use `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

### 3. Run `specify init`

Parse `$ARGUMENTS` for a project name, `--here`, and `--force`. Ignore an empty argument list (treat as init in the current directory). Other user wording may still inform flags below; do not require a rigid flag-only argv.

Choose flags:

| Flag | When |
| --- | --- |
| `--integration claude` | Always (this is a Claude Code skill). |
| `--script sh` | macOS, Linux, WSL, Git Bash. |
| `--script ps` | Native Windows (PowerShell). No bash required. |
| `<project-name>` | User asked for a new directory of that name. |
| `--here` (or `.`) | Init the current directory. Default when no project name is given. |
| `--non-interactive --ignore-agent-tools` | Always in this agent/CI harness (no picker, no hang). |
| `--force` | User passed `--force`, **or** the target already contains `.specify/`, **or** the target directory is not empty. |

Example, current directory on a Unix-like shell:

```bash
specify init --here --integration claude --script sh --non-interactive --ignore-agent-tools
```

Example, new project on native Windows:

```bash
specify init my-project --integration claude --script ps --non-interactive --ignore-agent-tools
```

Add `--force` when required (see below). Show the CLI's stdout/stderr. If it fails, **stop**.

### Existing directory / `.specify/`

There is no wrapper script and no custom exit-code table. `specify init` itself:

- With a `<project-name>`, creates that directory (and fails if it cannot).
- With `--here` or `.`, initializes the current directory.
- If the current directory is **not empty** and `--non-interactive` is set, the CLI exits with an error telling you to re-run with `--force` to merge into it. A directory that already contains `.specify/` is not empty, so this applies.
- `--force` skips that confirmation and merges/overwrites into the existing directory.

Pass `--force` on the first `specify init` when the target already contains `.specify/` or is otherwise non-empty. Do not wait for that error, and do not ask the user to rerun.

### 4. Enable default extensions

After a successful init, enable the default Spec Kit extensions unless the user opts out.

Source of truth for the default list: `<skill-dir>/extensions.txt` (sibling of this file; one name/path/URL per line; blank lines and `#` comments ignored). Read it from `<skill-dir>/extensions.txt`; it is the only source. If that file is somehow missing, proceed with no extensions and warn the user. Do not hardcode extension names.

**Optionally prompt** the user to add or remove entries before applying. If they reply with a modified list, use that. If they decline extensions entirely, skip this step. If they do not answer and you should not block, apply the defaults.

From the initialized project directory (the new `<project-name>` dir if one was created, otherwise the current dir), run once per name:

```bash
specify extension add <name>
```

(`specify extension add` takes a single `{extension}` argument; do not pass several names in one invocation.)

### 5. Report

Show the CLI output. Then give the post-init guidance below.

## After a successful init

`specify init --integration claude` writes **project** skills under `.claude/skills/` in the initialized project (for example `.claude/skills/speckit-specify`). They are invoked as `/speckit-<name>` (for example `/speckit-specify`). They are **not** plugin-namespaced `/speckit:speckit-<name>` commands.

Restart the session (or start a new one in the initialized project) so those project skills load. Do **not** run `/reload-plugins` for this — these are project skills, not plugin components.

Then follow the Spec Kit workflow, in order:

1. **Constitution** — `/speckit-constitution` — project principles and development guidelines. One-time per project.
2. **Specify** — `/speckit-specify <what to build>` — the *what* and *why*, not the tech stack.
3. **Clarify** — `/speckit-clarify` — recommended before planning; tightens underspecified areas of the spec.
4. **Plan** — `/speckit-plan` — technical implementation plan and stack choices.
5. **Tasks** — `/speckit-tasks` — dependency-ordered task list from the plan.
6. **Analyze** — `/speckit-analyze` — cross-artifact consistency and coverage, after tasks and before implement.
7. **Implement** — `/speckit-implement` — execute the tasks.
8. **Checklist** (optional) — `/speckit-checklist` — quality checklists for the spec ("unit tests for English").
9. **Converge** — `/speckit-converge` — assess the codebase against spec, plan, and tasks; append remaining work. Repeat implement → converge until it reports **Converged**.

Related: `/speckit-taskstoissues` converts the task list into GitHub issues.

If you initialized a new directory `<project-name>`, run those commands from that project (its `.claude/skills/`).

## Requirements

- **Required:** `uv`, then `specify-cli` from PyPI via `uv tool install specify-cli`.
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** use `--script ps`; bash/Git Bash/WSL is not required.
