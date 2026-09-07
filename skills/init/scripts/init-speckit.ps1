#!/usr/bin/env pwsh
# Bootstrap the current directory with Spec Kit (no-Python equivalent of `specify init`).
#
# Resolves the bundled asset variant for this platform and copies `.specify/` and
# `.claude/skills/speckit-*/` into the current working directory.
#
# Exit codes: 0 = initialized, 2 = already initialized (pass -Force/--force), 1 = error.
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/DgxSparkLabs/Claude-Code-Speckit-Plugin.git'
$SkillDir = Split-Path -Parent $PSScriptRoot

$force = $false
foreach ($arg in ($Arguments | Where-Object { $_ })) {
    if ($arg -in @('--force', '-Force', '-force')) { $force = $true }
    else { Write-Error "init-speckit: unknown argument: $arg"; exit 1 }
}

$variant = if ($IsLinux -or $IsMacOS) { 'bash' } else { 'ps' }
$cloneDir = $null

# Asset root resolution, in order:
#   1. plugin/repo layout    -> <skill dir>/../../assets/<variant>
#   2. explicit plugin root  -> $env:CLAUDE_PLUGIN_ROOT/assets/<variant>
#   3. standalone install    -> shallow clone of the plugin repo
function Resolve-Assets {
    $pluginRoot = Split-Path -Parent (Split-Path -Parent $SkillDir)
    $candidates = @(Join-Path $pluginRoot "assets/$variant")
    if ($env:CLAUDE_PLUGIN_ROOT) {
        $candidates += Join-Path $env:CLAUDE_PLUGIN_ROOT "assets/$variant"
    }
    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate '.specify') -PathType Container) {
            return (Resolve-Path $candidate).Path
        }
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Error 'init-speckit: bundled assets not found and git is unavailable to fetch them.'
        exit 1
    }
    $script:cloneDir = Join-Path ([System.IO.Path]::GetTempPath()) ("speckit-" + [guid]::NewGuid().ToString('N'))
    Write-Host "Bundled assets not found locally; fetching them from $RepoUrl ..."
    git clone --depth 1 --quiet $RepoUrl (Join-Path $script:cloneDir 'plugin')
    if ($LASTEXITCODE -ne 0) {
        Write-Error "init-speckit: failed to fetch plugin assets from $RepoUrl"
        exit 1
    }
    $fetched = Join-Path $script:cloneDir "plugin/assets/$variant"
    if (Test-Path (Join-Path $fetched '.specify') -PathType Container) {
        return (Resolve-Path $fetched).Path
    }
    Write-Error "init-speckit: fetched repository has no assets/$variant variant."
    exit 1
}

try {
    if ((Test-Path '.specify' -PathType Container) -and -not $force) {
        Write-Host 'A .specify/ directory already exists in this project.'
        Write-Host 'To reinitialize and overwrite the plugin-owned files, run: /speckit:init --force'
        exit 2
    }

    $assets = Resolve-Assets

    if ($force) { Write-Host 'Reinitializing Spec Kit (--force specified)...' }

    # `.specify/` is entirely plugin-owned. Inside `.claude/`, only `skills/speckit-*/`
    # is plugin-owned; every other user file there is left untouched.
    Remove-Item -Recurse -Force '.specify' -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force '.claude/skills/speckit-*' -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path '.claude/skills' | Out-Null
    Copy-Item -Recurse -Force (Join-Path $assets '.specify') '.specify'
    Copy-Item -Recurse -Force (Join-Path $assets '.claude/skills/speckit-*') '.claude/skills/'

    $skillCount = (Get-ChildItem '.claude/skills' -Directory -Filter 'speckit-*').Count

    Write-Host ""
    Write-Host "Spec Kit initialized successfully. (asset variant: $variant)"
    Write-Host ""
    Write-Host "Installed:"
    Write-Host "  .claude/skills/         $skillCount Spec Kit workflow skills"
    Write-Host "  .specify/templates/     spec, plan, tasks, and constitution templates"
    Write-Host "  .specify/scripts/       workflow automation scripts"
    Write-Host "  .specify/memory/        constitution and project memory"
    Write-Host "  .specify/extensions/    bundled Spec Kit extensions"
    Write-Host "  .specify/integrations/  integration configuration"
    exit 0
}
finally {
    if ($script:cloneDir -and (Test-Path $script:cloneDir)) {
        Remove-Item -Recurse -Force $script:cloneDir -ErrorAction SilentlyContinue
    }
}
