#!/usr/bin/env bash
# Bootstrap the current directory with Spec Kit (no-Python equivalent of `specify init`).
#
# Always copies `.specify/` (the runtime every skill needs). Copies
# `.claude/skills/speckit-*/` only when CLAUDE_PLUGIN_ROOT is unset
# (standalone). When CLAUDE_PLUGIN_ROOT is set (installed-plugin route), the
# plugin already provides those skills, so they are not copied.
#
# Exit codes: 0 = initialized, 2 = already initialized (pass --force), 1 = error.
set -euo pipefail

REPO_URL="https://github.com/DgxSparkLabs/Claude-Code-Speckit-Plugin.git"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    "") ;;
    *) printf 'init-speckit: unknown argument: %s\n' "$arg" >&2; exit 1 ;;
  esac
done

cleanup() { if [ -n "${clone_dir:-}" ]; then rm -rf "$clone_dir"; fi; }
trap cleanup EXIT

# Asset root resolution, in order:
#   1. plugin/repo layout    -> <skill dir>/../../assets/bash
#   2. explicit plugin root  -> $CLAUDE_PLUGIN_ROOT/assets/bash
#   3. standalone install    -> shallow clone of the plugin repo
resolve_assets() {
  local candidate
  for candidate in \
    "$SKILL_DIR/../../assets/bash" \
    "${CLAUDE_PLUGIN_ROOT:-}/assets/bash"; do
    case "$candidate" in /assets/*) continue ;; esac
    if [ -d "$candidate/.specify" ]; then
      (cd "$candidate" && pwd)
      return 0
    fi
  done

  command -v git >/dev/null 2>&1 || {
    printf 'init-speckit: bundled assets not found and git is unavailable to fetch them.\n' >&2
    return 1
  }
  clone_dir="$(mktemp -d)"
  printf 'Bundled assets not found locally; fetching them from %s ...\n' "$REPO_URL" >&2
  git clone --depth 1 --quiet "$REPO_URL" "$clone_dir/plugin" >&2 || {
    printf 'init-speckit: failed to fetch plugin assets from %s\n' "$REPO_URL" >&2
    return 1
  }
  if [ -d "$clone_dir/plugin/assets/bash/.specify" ]; then
    printf '%s\n' "$clone_dir/plugin/assets/bash"
    return 0
  fi
  printf 'init-speckit: fetched repository has no assets/bash.\n' >&2
  return 1
}

if [ -d .specify ] && [ "$force" -eq 0 ]; then
  cat >&2 <<'MSG'
A .specify/ directory already exists in this project.
To reinitialize and overwrite the plugin-owned files, run: /speckit:init --force
MSG
  exit 2
fi

assets="$(resolve_assets)"

[ "$force" -eq 1 ] && printf 'Reinitializing Spec Kit (--force specified)...\n'

# `.specify/` is entirely plugin-owned.
rm -rf .specify
cp -R "$assets/.specify" .specify
find .specify -name '*.sh' -exec chmod +x {} +

if [ -z "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  # Standalone: inside `.claude/`, only `skills/speckit-*/` is plugin-owned;
  # every other user file there is left untouched.
  rm -rf .claude/skills/speckit-*
  mkdir -p .claude/skills
  cp -R "$assets/.claude/skills/"speckit-* .claude/skills/
  skill_count="$(find .claude/skills -maxdepth 1 -name 'speckit-*' | wc -l | tr -d '[:space:]')"
  cat <<MSG
Spec Kit initialized successfully (standalone).

Copied .specify/ and $skill_count Spec Kit workflow skills into .claude/skills/.

Installed:
  .claude/skills/         $skill_count Spec Kit workflow skills
  .specify/templates/     spec, plan, tasks, and constitution templates
  .specify/scripts/       workflow automation scripts
  .specify/memory/        constitution and project memory
  .specify/extensions/    bundled Spec Kit extensions
  .specify/integrations/  integration configuration
MSG
else
  cat <<'MSG'
Spec Kit initialized successfully (plugin mode).

Copied .specify/. Skills were not copied: the installed plugin already provides them.

Installed:
  .specify/templates/     spec, plan, tasks, and constitution templates
  .specify/scripts/       workflow automation scripts
  .specify/memory/        constitution and project memory
  .specify/extensions/    bundled Spec Kit extensions
  .specify/integrations/  integration configuration
MSG
fi
exit 0
