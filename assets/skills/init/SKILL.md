---
name: "init"
description: "Initialize a new project with the Spec Kit workflow infrastructure. Always copies .specify/. Copies speckit-* skills into .claude/skills/ only in standalone mode, detected by absence of .claude-plugin/plugin.json two levels above this skill; --skills/--no-skills override. User-invocable only — run /speckit:init; do not auto-invoke."
argument-hint: "[--force] [--skills|--no-skills]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Bootstrap the current project with Spec Kit — the no-Python equivalent of `specify init`. Copy the plugin's bundled `.specify/` into the project root. Copy `.claude/skills/speckit-*/` only when running standalone. Leave any user-authored files under `.claude/` untouched.

Do not implement this by hand. Run the bundled bootstrap script, then report its output and the next-step workflow below.

Native Windows uses Git Bash or WSL for the bundled `.sh` scripts.

## When to run

Only when the user invokes `/speckit:init` (or `/speckit:init` with `--force`, `--skills`, and/or `--no-skills`). Do not run this skill because a project "looks uninitialized".

## Execution

Working directory **must** be the user's project root, not this skill directory.

1. Parse `$ARGUMENTS`. Supported flags are `--force`, `--skills`, and `--no-skills`. Ignore an empty argument list. Reject any other argument and stop.
2. Resolve `<skill-dir>`: use `${CLAUDE_SKILL_DIR}` when it is an existing directory, otherwise the directory that contains this `SKILL.md`.
3. Run the bootstrap script, forwarding those flags as the user passed them:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/init-speckit.sh" $ARGUMENTS
```

If `${CLAUDE_SKILL_DIR}` was not substituted, replace it with `<skill-dir>`.

### What the script does

- **Refuse** if `.specify/` already exists in the project root, unless `--force` was passed (exit `2`). Tell the user to rerun `/speckit:init --force`. **Stop. Do not copy anything.**
- **Asset root**, first match:
  1. Plugin / repo layout: `<skill-dir>/../../assets/bash`
  2. `$CLAUDE_PLUGIN_ROOT/assets/bash` when that environment variable is set
  3. Standalone install (for example via `npx skills add`): shallow-clone this plugin repository and use its `assets/bash`
- **Always copy** `.specify/` (plugin-owned; replaced entirely).
- **Skills copy is dual-mode:**
  - Default: plugin mode if `<skill-dir>/../../.claude-plugin/plugin.json` exists (skip the skill copy; the installed plugin already provides them); otherwise standalone (under `.claude/`, remove only `.claude/skills/speckit-*/`, then copy the bundled `speckit-*` skills). Preserve every other file the user already has in `.claude/`.
  - `--skills` forces the skill copy; `--no-skills` forces skipping it. These override the detected mode.
  - Do not use `$CLAUDE_PLUGIN_ROOT` to decide the mode; that variable is only an asset-root candidate.
- `chmod +x` on `.specify/**/*.sh`.

### Exit codes

| Code | Meaning | What you do |
| --- | --- | --- |
| `0` | Initialized | Show the script stdout, then the workflow below |
| `2` | `.specify/` exists and `--force` was not passed | Show the script message; **stop** |
| `1` | Error | Show stderr; **stop** |

Do not invent extra copy steps, do not delete `.claude/` wholesale, and do not skip the script.

## After a successful init

Restart the session so newly available skills load (`/reload-plugins`, or exit and re-enter).

Then follow the Spec Kit workflow.

When this plugin is installed, skills are namespaced `/speckit:speckit-<name>` (for example `/speckit:speckit-specify`). In standalone mode (project skills under `.claude/skills/`), the form is `/speckit-<name>`.

1. **Constitution** — `/speckit:speckit-constitution` / `/speckit-constitution` — project principles and development guidelines. One-time per project.
2. **Specify** — `/speckit:speckit-specify <what to build>` / `/speckit-specify <what to build>` — the *what* and *why*, not the tech stack.
3. **Clarify** — `/speckit:speckit-clarify` / `/speckit-clarify` — recommended before planning; tightens underspecified areas of the spec.
4. **Plan** — `/speckit:speckit-plan` / `/speckit-plan` — technical implementation plan and stack choices.
5. **Tasks** — `/speckit:speckit-tasks` / `/speckit-tasks` — dependency-ordered task list from the plan.
6. **Analyze** — `/speckit:speckit-analyze` / `/speckit-analyze` — cross-artifact consistency and coverage, after tasks and before implement.
7. **Implement** — `/speckit:speckit-implement` / `/speckit-implement` — execute the tasks.
8. **Checklist** (optional) — `/speckit:speckit-checklist` / `/speckit-checklist` — quality checklists for the spec ("unit tests for English").
9. **Converge** — `/speckit:speckit-converge` / `/speckit-converge` — assess the codebase against spec, plan, and tasks; append remaining work. Repeat implement → converge until it reports **Converged**.

Related: `/speckit:speckit-taskstoissues` / `/speckit-taskstoissues` converts the task list into GitHub issues.

This plugin also copies the bundled Spec Kit extensions into `.specify/`. They are optional; the core workflow above does not require enabling extra extensions.

## Compatibility

Projects initialized this way stay compatible with the upstream `specify` CLI if you later install it. This skill does not require Python or `specify`.
