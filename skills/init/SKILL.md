---
name: "init"
description: "Initialize a new project with the Spec Kit workflow infrastructure. Copies .specify/ and .claude/ directories with scripts, templates, skills, and extensions. User-invocable only — run /speckit:init; do not auto-invoke."
argument-hint: "[--force]"
disable-model-invocation: true
---

## User Input

```text
$ARGUMENTS
```

## Goal

Bootstrap the current project with Spec Kit — the no-Python equivalent of `specify init`. Detect the platform, copy the plugin's bundled `.specify/` and `.claude/skills/speckit-*/` from the matching `assets/` variant into the project root, and leave any user-authored files under `.claude/` untouched.

Do not implement this by hand. Run the bundled bootstrap script, then report its output and the next-step workflow below.

## When to run

Only when the user invokes `/speckit:init` (or `/speckit:init --force`). Do not run this skill because a project "looks uninitialized".

## Execution

Working directory **must** be the user's project root, not this skill directory.

1. Parse `$ARGUMENTS`. The only supported flag is `--force`. Ignore an empty argument list. Reject any other argument and stop.
2. Resolve `<skill-dir>`: use `${CLAUDE_SKILL_DIR}` when it is an existing directory, otherwise the directory that contains this `SKILL.md`.
3. Run **exactly one** of the following, forwarding `--force` when the user passed it:

**macOS / Linux (and Git Bash):**

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/init-speckit.sh" $ARGUMENTS
```

**Windows (PowerShell):**

```powershell
pwsh -File "${CLAUDE_SKILL_DIR}/scripts/init-speckit.ps1" $ARGUMENTS
```

If `${CLAUDE_SKILL_DIR}` was not substituted, replace it with `<skill-dir>`.

### What the script does

- **Refuse** if `.specify/` already exists in the project root, unless `--force` was passed (exit `2`). Tell the user to rerun `/speckit:init --force`. **Stop. Do not copy anything.**
- **Platform:** `ps` asset variant on Windows (including MINGW / MSYS / CYGWIN); `bash` asset variant on macOS and Linux.
- **Asset root**, first match:
  1. Plugin / repo layout: `<skill-dir>/../../assets/<variant>`
  2. `$CLAUDE_PLUGIN_ROOT/assets/<variant>` when that environment variable is set
  3. Standalone install (for example via `npx skills add`): shallow-clone this plugin repository and use its `assets/<variant>`
- **Copy:** replace `.specify/` entirely (plugin-owned). Under `.claude/`, remove only `.claude/skills/speckit-*/`, then copy the bundled `speckit-*` skills. Preserve every other file the user already has in `.claude/`.
- **bash variant only:** `chmod +x` on `.specify/**/*.sh`.

### Exit codes

| Code | Meaning | What you do |
| --- | --- | --- |
| `0` | Initialized | Show the script stdout, then the workflow below |
| `2` | `.specify/` exists and `--force` was not passed | Show the script message; **stop** |
| `1` | Error | Show stderr; **stop** |

Do not invent extra copy steps, do not delete `.claude/` wholesale, and do not skip the script.

## After a successful init

Restart the session so the newly copied project skills load (`/reload-plugins`, or exit and re-enter).

Then follow the Spec Kit workflow. Most agents expose these as `/speckit-*` skills once they are in `.claude/skills/`:

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

This plugin also copies the bundled Spec Kit extensions into `.specify/`. They are optional; the core workflow above does not require enabling extra extensions.

## Compatibility

Projects initialized this way stay compatible with the upstream `specify` CLI if you later install it. This skill does not require Python or `specify`.
