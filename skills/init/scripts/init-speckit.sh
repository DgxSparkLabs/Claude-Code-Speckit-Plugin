#!/usr/bin/env bash
# Bootstrap the current directory with Spec Kit (no-Python equivalent of `specify init`).
#
# Resolves the bundled asset variant for this platform and copies `.specify/` and
# `.claude/skills/speckit-*/` into the current working directory.
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

case "$(uname -s 2>/dev/null || echo Windows)" in
  MINGW* | MSYS* | CYGWIN* | Windows*) variant=ps ;;
  *) variant=bash ;;
esac

cleanup() { if [ -n "${clone_dir:-}" ]; then rm -rf "$clone_dir"; fi; }
trap cleanup EXIT

# Asset root resolution, in order:
#   1. plugin/repo layout    -> <skill dir>/../../assets/<variant>
#   2. explicit plugin root  -> $CLAUDE_PLUGIN_ROOT/assets/<variant>
#   3. standalone install    -> shallow clone of the plugin repo
resolve_assets() {
  local candidate
  for candidate in \
    "$SKILL_DIR/../../assets/$variant" \
    "${CLAUDE_PLUGIN_ROOT:-}/assets/$variant"; do
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
  if [ -d "$clone_dir/plugin/assets/$variant/.specify" ]; then
    printf '%s\n' "$clone_dir/plugin/assets/$variant"
    return 0
  fi
  printf 'init-speckit: fetched repository has no assets/%s variant.\n' "$variant" >&2
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

# `.specify/` is entirely plugin-owned. Inside `.claude/`, only `skills/speckit-*/`
# is plugin-owned; every other user file there is left untouched.
rm -rf .specify
rm -rf .claude/skills/speckit-*
mkdir -p .claude/skills
cp -R "$assets/.specify" .specify
cp -R "$assets/.claude/skills/"speckit-* .claude/skills/

if [ "$variant" = bash ]; then
  find .specify -name '*.sh' -exec chmod +x {} +
fi

skill_count="$(find .claude/skills -maxdepth 1 -name 'speckit-*' | wc -l | tr -d '[:space:]')"

cat <<MSG
Spec Kit initialized successfully. (asset variant: $variant)

Installed:
  .claude/skills/         $skill_count Spec Kit workflow skills
  .specify/templates/     spec, plan, tasks, and constitution templates
  .specify/scripts/       workflow automation scripts
  .specify/memory/        constitution and project memory
  .specify/extensions/    bundled Spec Kit extensions
  .specify/integrations/  integration configuration
MSG
exit 0
