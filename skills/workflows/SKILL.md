---
name: "workflows"
description: "Run Spec Kit automation workflows in a project via specify workflow. Run a workflow from an installed ID or local YAML, resume a paused or failed run, show run status, and list installed workflows. The built-in speckit workflow drives the full SDD cycle (specify to plan to tasks to implement, with gates). Running a workflow executes the shell and command steps it defines, so only run sources the user trusts. Arguments: [run|resume|status|list] [source|run_id]. User-invocable only — run /speckit:workflows; do not auto-invoke."
argument-hint: "[run|resume|status|list] [source|run_id]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Operate Spec Kit **automation workflows** by running `specify workflow …`: start a run, resume one that paused or failed, inspect run status, and list the workflows installed in the project.

A workflow is a declarative list of steps (shell commands, agent prompts, human gates) stored as YAML. The built-in **`speckit`** workflow drives the full spec-driven cycle — specify → plan → tasks → implement — with gates between phases.

This skill **operates** workflows only. Installing, customizing, and authoring them (`add`, the `overlay` group, `resolve`) belong to `/speckit:workflow-authoring`.

Do not hand-run a workflow's steps yourself and do not edit run state under `.specify/workflows/runs/`. Run the CLI and report its output.

## When to run

Only when the user invokes `/speckit:workflows` (optionally with a subcommand and a source or run id). Do not run this skill because a project "looks like it needs the SDD cycle", and never start a workflow run on your own initiative.

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory.

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `list` (installed workflows) plus `status` (existing runs). Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to run: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/`, tell the user to run `/speckit:init` first, then **stop**. The **one exception** is `specify workflow run <local-file.yml>`, which works outside an initialized project: it creates run state under `./.specify/workflows/runs/<run_id>/` in the current directory. `resume`, `status`, and `list` all require an initialized project.

### 2. Dispatch

Use only these commands (never invent flags; `specify workflow <cmd> --help` is the source of truth):

**Run**

```bash
specify workflow run <source> [-i key=value ...] [--json]
```

`<source>` is a workflow ID installed in the project **or** a path to a local `.yml`/`.yaml` file. `-i` / `--input` passes input values as `key=value` and is repeatable. `--json` emits the run outcome as a single JSON object instead of formatted text.

```bash
specify workflow run speckit                       # full SDD cycle
specify workflow run ./my-workflow.yml -i name=api # local file, one input
```

**Resume**

```bash
specify workflow resume <run_id> [-i key=value ...] [--json]
```

Resumes a **paused or failed** run from the exact step it stopped at. `-i` values are merged over the stored inputs and re-validated.

**Status**

```bash
specify workflow status              # all runs
specify workflow status <run_id>     # one run
specify workflow status --json
```

Run states: `created`, `running`, `completed`, `paused`, `failed`, `aborted`.

**List**

```bash
specify workflow list
```

Lists the workflows installed in the project. It takes no options.

### 3. Run lifecycle

- A run gets a **run id** (shown when it starts and by `status`). Everything else is addressed by that id.
- A **`gate` step pauses the run** and hands control back to a human. The run goes to `paused`; nothing further executes until someone continues it with `specify workflow resume <run_id>`.
- A failed step leaves the run `failed`. Fix the cause, then `resume` the same run id rather than starting over — `resume` picks up at the failing step.
- Run state lives under `.specify/workflows/runs/<run_id>/`. Read it if you need detail; do not edit it.

### 4. Relationship to the project skills (not new capability)

After `/speckit:init`, the same spec-driven cycle is already available as **project** skills in the initialized project: `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement` (plus `/speckit-constitution`, `/speckit-clarify`, `/speckit-analyze`).

`specify workflow run speckit` is a **one-shot orchestrated driver over those same steps**, with gates between phases. It is not a different or more capable path. Say this plainly when the user is deciding: use the project skills to go phase by phase with full control, use `workflow run speckit` to drive the whole cycle in one command.

### 5. Report

Show the CLI output from each command you ran. State the run id, the resulting state, and — if the run is `paused` or `failed` — which step it stopped at and the exact `specify workflow resume <run_id>` command to continue.

## Safety and notes

- **Running a workflow executes arbitrary shell and command steps defined in that workflow.** A workflow YAML can run any command with your permissions. Only run catalog IDs or local files the user trusts. If the source is unvetted — a file you did not write, a workflow just installed from an untrusted origin — **show the user its steps and confirm before running it**.
- **Read a workflow before running it.** Open the YAML (a local file, or the installed copy under `.specify/`) and look at its steps. Your `specs/`, source code, git history, and constitution at `.specify/memory/constitution.md` are affected exactly as far as the workflow's steps touch them, which is not bounded by this skill.
- **Gates are human checkpoints.** A gate exists so a person reviews the output before the next phase. Do not blindly `resume` past one: surface what the gate is asking, let the user decide, then resume.
- **`resume`, not re-run.** Re-running a workflow starts a fresh run and repeats completed steps; `resume <run_id>` continues the existing one.
- **Installing and customizing workflows is out of scope here.** `specify workflow add`, the `overlay` group, and `resolve` belong to `/speckit:workflow-authoring`.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit workflows: <https://github.github.io/spec-kit/reference/workflows.html>
