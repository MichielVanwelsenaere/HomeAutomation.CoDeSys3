<#
.SYNOPSIS
    Make, list and promote working copies of an installation project.

.DESCRIPTION
    An installation project is a building's running control program and may not
    be under source control, so a sync is never performed on it directly. This
    script owns the three file operations that surround a sync:

      new      copy the installation project into .ai/sync/<name>/, which is
               gitignored scratch space in this repository. The sync runs there.
      list     show the working copies and backups that exist.
      promote  replace the installation project with the verified working copy,
               after taking a timestamped backup of the original. Requires
               -Force, and the user's explicit go-ahead before that.

    A project's sibling files (.opt user settings, .compileinfo, .bootinfo) are
    NOT copied: they are per-machine and per-download state, they are large, and
    CODESYS regenerates them. Only the .project itself, plus a sibling
    Libraries\ folder if the project has one, travel with the copy.

.EXAMPLE
    ./Working-Copy.ps1 new -Target 'C:\...\SiteA.project'
.EXAMPLE
    ./Working-Copy.ps1 list
.EXAMPLE
    ./Working-Copy.ps1 promote -Target 'C:\...\SiteA.project' -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('new', 'list', 'promote')]
    [string]$Stage,

    # The real installation project. For `promote` this is the file that gets
    # replaced; for `new` it is the file that gets copied.
    [string]$Target,

    # promote only. Overwriting a building's control project is not something to
    # do on inference.
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$syncRoot = Join-Path $repo '.ai\sync'

function Get-Slot {
    param([string]$Path)
    $stem = [IO.Path]::GetFileNameWithoutExtension($Path)
    $dir = Join-Path $syncRoot $stem
    return [pscustomobject]@{
        Stem    = $stem
        Dir     = $dir
        Project = Join-Path $dir ([IO.Path]::GetFileName($Path))
        Backups = Join-Path $dir 'backups'
    }
}

if ($Stage -eq 'list') {
    if (-not (Test-Path $syncRoot)) { Write-Host 'no working copies'; exit 0 }
    foreach ($d in Get-ChildItem $syncRoot -Directory) {
        Write-Host "$($d.Name)"
        foreach ($f in Get-ChildItem $d.FullName -Recurse -Filter '*.project' -ErrorAction SilentlyContinue) {
            $rel = $f.FullName.Substring($d.FullName.Length + 1)
            Write-Host ("  {0,-52} {1,10:n0} bytes  {2}" -f $rel, $f.Length, $f.LastWriteTime)
        }
    }
    exit 0
}

if (-not $Target) { throw "-Target is required for '$Stage'." }
if (-not (Test-Path $Target)) { throw "Project not found: $Target" }
$Target = (Resolve-Path $Target).Path
$slot = Get-Slot -Path $Target

if ($Stage -eq 'new') {
    if (Test-Path $slot.Project) {
        Write-Host "A working copy already exists at $($slot.Project)" -ForegroundColor Yellow
        Write-Host 'Delete it first if you want to start over - re-syncing on top of a' -ForegroundColor Yellow
        Write-Host 'half-synced copy makes the before/after check meaningless.' -ForegroundColor Yellow
        exit 1
    }
    New-Item -ItemType Directory -Path $slot.Dir -Force | Out-Null
    Copy-Item $Target $slot.Project
    $libs = Join-Path (Split-Path $Target -Parent) 'Libraries'
    if (Test-Path $libs) {
        Copy-Item $libs (Join-Path $slot.Dir 'Libraries') -Recurse -Force
        Write-Host "copied sibling Libraries\ as well"
    }
    Write-Host "working copy: $($slot.Project)"
    Write-Host "original    : $Target  (untouched)"
    exit 0
}

# ---------------------------------------------------------------- promote

if (-not (Test-Path $slot.Project)) {
    throw "No working copy at $($slot.Project). Run 'new' and sync it first."
}
if (-not $Force) {
    Write-Host @"
promote replaces

    $Target

with the working copy

    $($slot.Project)

That file is a building's control program. Before re-running with -Force:

  * the working copy must have built cleanly (codesys.ps1 verify -Project <copy>)
  * check_logic_unchanged.py must have passed on it
  * the user must have said, in this conversation, to replace the original

A backup of the original is taken either way, but a backup is not a substitute
for the user having agreed.
"@ -ForegroundColor Yellow
    exit 1
}

New-Item -ItemType Directory -Path $slot.Backups -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $slot.Backups "$($slot.Stem).$stamp.project"
Copy-Item $Target $backup
Write-Host "backup      : $backup"

Copy-Item $slot.Project $Target -Force
Write-Host "promoted    : $Target" -ForegroundColor Green
Write-Host ''
Write-Host 'CODESYS caches compile output beside the project. The stale .compileinfo/' -ForegroundColor Yellow
Write-Host '.bootinfo files next to the original now describe the OLD project; CODESYS' -ForegroundColor Yellow
Write-Host 'rebuilds them on the next build, but do not read them as current.' -ForegroundColor Yellow
Write-Host ''
Write-Host 'This changed a file only. Nothing was downloaded to any PLC.'
