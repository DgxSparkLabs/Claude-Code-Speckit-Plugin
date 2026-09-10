---
name: "workflow-authoring"
description: "Install, customize, and author Spec Kit automation workflows via specify workflow. Add a workflow from a catalog id, URL, or local path; manage overlays (add, list, set-priority, enable, disable, remove); inspect the composed layer stack with resolve; and write workflow.yml / overlay YAML. Overlays can override or remove human gates and inject shell steps — review before enabling. Arguments: [add|overlay|resolve] [args]. User-invocable only — run /speckit:workflow-authoring; do not auto-invoke."
argument-hint: "[add|overlay|resolve] [args]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Install, customize, and author Spec Kit **automation workflows** by running `specify workflow …`. This skill covers:

- **Install** a workflow (`add`) from a catalog id, HTTPS URL, local YAML, a directory containing `workflow.yml`, or a `.zip` / `.tar.gz` / `.tgz`.
- **Customize** an installed workflow with **overlays** (`overlay add` / `list` / `set-priority` / `enable` / `disable` / `remove`).
- **Inspect** the composed result (`resolve`) so the user sees which layer owns each step.
- **Author** `workflow.yml` and overlay YAML. Full step-type schema lives in the Reference; this skill documents the overlay fields, edit operations, and one small example.

**Running** a workflow (`run` / `resume` / `status` / `list`) belongs to `/speckit:workflows`. Do not start a run from this skill.

Do not drop overlay YAML into `.specify/workflows/overlays/` by hand. Run the CLI and report its output.

## When to run

Only when the user invokes `/speckit:workflow-authoring` (optionally with a subcommand and operands). Do not run this skill because a project "looks like it needs a custom workflow".

## Execution

Working directory **must** be the user's project root (the directory containing `.specify/`), not this skill directory. **Every command in this skill requires an initialized project.**

Parse `$ARGUMENTS` for a subcommand and its operands. An empty argument list means `specify workflow list` so the user can see what is already installed. Other user wording may still inform the subcommand; do not require a rigid flag-only argv.

### 1. Preflight

Run `uv --version` and `specify --version`.

- If `uv` is missing, tell the user how to install it, then **stop**:
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`
- If `specify` is missing, there is nothing to manage: tell the user to run `/speckit:init` first (or install the CLI directly with `uv tool install specify-cli`), then **stop**.

If the shell cannot find `specify`, invoke it as `uv tool run specify` with the same arguments (uv's tool bin may not be on `PATH` yet).

If the directory has no `.specify/`, tell the user to run `/speckit:init` first, then **stop**.

### 2. Dispatch

Use only these commands (never invent flags; `specify workflow <cmd> --help` is the source of truth):

**Add** (install)

```bash
specify workflow add <source> [--dev] [--from <url>]
```

`<source>` is a catalog id, an HTTPS URL, a local `.yml` / `.yaml` file, a directory containing `workflow.yml`, or a `.zip` / `.tar.gz` / `.tgz`. `--dev` installs from a local file, directory, or archive. `--from <url>` installs from a custom URL; when it is used, `<source>` is the expected workflow id.

**Overlay**

```bash
specify workflow overlay add <path-to-overlay.yml> [--priority N]   # default 10
specify workflow overlay list <workflow-id>
specify workflow overlay set-priority <workflow-id> <overlay-id> <n>
specify workflow overlay enable <workflow-id> <overlay-id>
specify workflow overlay disable <workflow-id> <overlay-id>
specify workflow overlay remove <workflow-id> <overlay-id>
```

Overlays live at `.specify/workflows/overlays/<extends>/<id>.yml`. Lower priority number wins (applied later, overrides earlier edits on the same anchors). `--priority` on `overlay add` defaults to 10.

**Resolve**

```bash
specify workflow resolve <workflow-id>
```

Prints the composed layer stack (base + overlays) with per-step source attribution. Run this after any overlay add / enable / disable / set-priority / remove so the user sees the result.

There is also `specify workflow catalog` for managing catalog sources; only use it if the user asked to manage catalogs. `specify workflow search` / `info` / `update` / `remove` / `enable` / `disable` (the workflow, not the overlay) and `specify workflow step` exist as well; only use those if the user asked.

### 3. Vetting boundary (CRITICAL)

You must **never auto-install** a workflow from an unvetted URL.

To install a workflow from a URL (`--from`, or `<source>` that is itself an HTTPS URL):

1. Show the user the source (the URL, and `specify workflow info <id>` if the workflow is already catalogued).
2. Wait for them to **vet** the source (they pick a URL they trust, or they confirm this one).
3. Only then run `specify workflow add`.

Never invent a URL. Never pass `--from` unless the user supplied the URL. Never treat "it showed up in `search`" as permission to `add`.

### 4. Confirm before destructive or gate-removing actions

Overlays can `replace` a gate with a non-interactive command (skipping human review) or inject arbitrary `shell` steps.

Before `overlay add` or `overlay enable`:

1. **Read the overlay YAML** and show the user every edit: which anchor, which operation, and the incoming `step` (if any).
2. Call out any edit that **removes or replaces a gate**, or that injects a `shell` / command step.
3. **Confirm with the user**, then proceed.

For `overlay remove` or `workflow remove`: show what will be removed (`overlay list` / `workflow list`) and confirm first.

After any overlay mutation, run `specify workflow resolve <workflow-id>` and show the composed stack.

### 5. Report

Show the CLI output. State which workflows are installed, which overlays are enabled and at what priority, and the `resolve` attribution after any change.

## Authoring

Point at the Reference for the full `workflow.yml` step-type schema. What follows is the **overlay** schema this skill needs to write correctly.

An overlay is one YAML file. Fields:

| Field | Required | Notes |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits, hyphens (must match `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$`). |
| `extends` | yes | Base workflow id (same id rules). |
| `priority` | no | Integer, default 10. **Lower number wins.** |
| `enabled` | no | Boolean, default `true`. |
| `edits` | yes | Non-empty list of edit operations. |

Each edit is one of:

- Shorthand: `{insert_after|insert_before|replace|remove}: <anchor>` plus `step:` (except `remove`).
- Explicit: `operation:` + `anchor:` plus `step:` (except `remove`).

Do not mix shorthand and `operation` on the same edit.

| Operation | `step:` | Effect |
| --- | --- | --- |
| `insert_after` | required | Insert `step` immediately after the anchor. |
| `insert_before` | required | Insert `step` immediately before the anchor. |
| `replace` | required | Replace the anchored step with `step`. |
| `remove` | forbidden | Delete the anchored step. |

`anchor` is a **base** step's `id`. It is resolved recursively inside `then` / `else` / `steps` / `cases.*` / `default`. Fan-out templates are **not** valid anchors (they are runtime-multiplied stamps, not uniquely addressable). Step ids must not contain `:`.

Overlays always apply against the original base tree — they cannot target a step another overlay just inserted.

Example — insert a lint `shell` step after `implement` on the built-in `speckit` workflow:

```yaml
id: add-lint
extends: speckit
priority: 10
edits:
  - insert_after: implement
    step:
      id: lint
      type: shell
      run: npm run lint
```

Write the file, then:

```bash
specify workflow overlay add ./add-lint.yml --priority 10
specify workflow resolve speckit
```

## Safety and notes

- **Never auto-install from an unvetted URL.** Same rule as `/speckit:extensions`.
- **Overlays can skip human review.** A `replace` or `remove` of a `gate` step, or a `shell` step injected around one, changes who is in the loop. Review overlay YAML before `overlay add` / `enable`, and **confirm with the user** before enabling an overlay that removes or replaces a gate.
- **Lower priority number wins.** After any overlay change, `specify workflow resolve <id>` is how the user sees the composed result.
- **`disable` is not `remove`.** Disable leaves the overlay on disk; remove deletes it.
- Your `specs/`, source code, git history, and constitution at `.specify/memory/constitution.md` are not the target of these commands, but any `shell` step an overlay injects *will* touch whatever that command touches. Read the YAML.

## Requirements

- **Required:** `uv`, and an existing `specify-cli` install (from `/speckit:init` or `uv tool install specify-cli`).
- **Not required:** a system `python3` (uv provisions it); `git` (only Spec Kit's git features need it).
- **Windows:** the generated project scripts are `.sh`; native Windows needs Git Bash or WSL to run them.

## Reference

Spec Kit workflows: <https://github.github.io/spec-kit/reference/workflows.html>
