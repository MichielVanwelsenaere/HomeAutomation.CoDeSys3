<#
.SYNOPSIS
    Snapshot the retained MQTT state, and diff two snapshots.

.DESCRIPTION
    This is how runtime behaviour gets verified on this project. CODESYS
    simulation is unavailable (the vendored 32-bit SysSocket23/SysFile23 cannot
    load in the 64-bit simulation runtime), so the compiler is the only automated
    gate on the PLC side - but the broker sees everything the PLC publishes. A
    snapshot before a download and another after it turns "did I break the Home
    Assistant entities?" into a diff.

    Retained topics are the useful ones: discovery configs and last-known states
    survive a reconnect, so a snapshot is reproducible rather than a race.

.EXAMPLE
    ./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/before.txt
.EXAMPLE
    ./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/after.txt
    ./tools/ai/Mqtt-Snapshot.ps1 -Diff .ai/mqtt/before.txt,.ai/mqtt/after.txt
.EXAMPLE
    # Watch live traffic instead of snapshotting retained state
    ./tools/ai/Mqtt-Snapshot.ps1 -Watch -Seconds 30
#>
[CmdletBinding()]
param(
    [string]$Out,

    # Two snapshot files to compare: before,after
    [string[]]$Diff,

    # Print live messages instead of a retained snapshot.
    [switch]$Watch,

    [string]$Broker = '10.101.1.11',
    [int]$Port = 1883,

    # Defaults cover Home Assistant discovery plus this project's own tree.
    [string[]]$Topics = @('homeassistant/#', 'Devices/PLC/Lab/#'),

    # How long to collect before giving up. Retained messages arrive at once, so
    # a few seconds is plenty; raise it for -Watch.
    [int]$Seconds = 5,

    [string]$User,
    [string]$Password
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

# ---------------------------------------------------------------- diff mode

if ($Diff) {
    if ($Diff.Count -ne 2) { throw 'Pass -Diff before.txt,after.txt' }
    foreach ($f in $Diff) { if (-not (Test-Path $f)) { throw "Snapshot not found: $f" } }

    function Read-Snapshot([string]$path) {
        $map = @{}
        foreach ($line in Get-Content $path) {
            if ($line -match '^\s*#') { continue }
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            $i = $line.IndexOf(' ')
            if ($i -lt 1) { $map[$line] = ''; continue }
            $map[$line.Substring(0, $i)] = $line.Substring($i + 1)
        }
        return $map
    }
    $before = Read-Snapshot $Diff[0]
    $after = Read-Snapshot $Diff[1]

    $gone = @($before.Keys | Where-Object { -not $after.ContainsKey($_) } | Sort-Object)
    $new = @($after.Keys | Where-Object { -not $before.ContainsKey($_) } | Sort-Object)
    $changed = @($before.Keys | Where-Object { $after.ContainsKey($_) -and $after[$_] -ne $before[$_] } | Sort-Object)

    Write-Host "before: $($before.Count) retained topic(s)   after: $($after.Count)"
    Write-Host ''
    if ($gone.Count) {
        # The dangerous class: an orphaned discovery config means an entity that
        # Home Assistant still shows but nothing publishes to any more.
        Write-Host "GONE ($($gone.Count)) - was retained before, absent now:" -ForegroundColor Red
        $gone | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
        Write-Host ''
    }
    if ($new.Count) {
        Write-Host "NEW ($($new.Count)):" -ForegroundColor Yellow
        $new | ForEach-Object { Write-Host "  + $_" -ForegroundColor Yellow }
        Write-Host ''
    }
    if ($changed.Count) {
        Write-Host "CHANGED ($($changed.Count)):" -ForegroundColor Cyan
        foreach ($t in $changed) {
            Write-Host "  ~ $t" -ForegroundColor Cyan
            Write-Host "      before: $($before[$t])"
            Write-Host "      after : $($after[$t])"
        }
        Write-Host ''
    }
    if (-not ($gone.Count -or $new.Count -or $changed.Count)) {
        Write-Host 'IDENTICAL - no retained topic added, removed or changed.' -ForegroundColor Green
    }
    exit 0
}

# ---------------------------------------------------------------- locate client

function Resolve-MosquittoSub {
    $cmd = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # The Windows installer does not add itself to PATH.
    foreach ($p in @(
            "$env:ProgramFiles\mosquitto\mosquitto_sub.exe",
            "${env:ProgramFiles(x86)}\mosquitto\mosquitto_sub.exe")) {
        if (Test-Path $p) { return $p }
    }
    throw @'
mosquitto_sub not found. Install it with:
    winget install --id EclipseFoundation.Mosquitto --scope machine
The installer does not add itself to PATH; this script also looks in
C:\Program Files\mosquitto.
'@
}
$sub = Resolve-MosquittoSub

$args = @('-h', $Broker, '-p', $Port, '-v', '-W', $Seconds)
foreach ($t in $Topics) { $args += @('-t', $t) }
if (-not $Watch) {
    # Retained state only, so the snapshot is reproducible.
    $args += '--retained-only'
}
if ($User) { $args += @('-u', $User) }
if ($Password) { $args += @('-P', $Password) }

Write-Host "client : $sub"
Write-Host "broker : ${Broker}:${Port}"
Write-Host "topics : $($Topics -join ', ')"
Write-Host "mode   : $(if ($Watch) { "live for ${Seconds}s" } else { "retained snapshot (${Seconds}s collect)" })"
Write-Host ''

# -W makes mosquitto_sub exit non-zero on timeout, which is its normal end here.
$lines = & $sub @args 2>&1
$lines = @($lines | Where-Object { $_ -notmatch '^Timed out$' })

if ($Watch) {
    $lines | ForEach-Object { Write-Host $_ }
    Write-Host ''
    Write-Host "$($lines.Count) message(s)"
    exit 0
}

$sorted = @($lines | Sort-Object)
if (-not $Out) {
    $sorted | ForEach-Object { Write-Host $_ }
    Write-Host ''
    Write-Host "$($sorted.Count) retained topic(s). Pass -Out to save a snapshot."
    exit 0
}

$dir = Split-Path $Out -Parent
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$header = @(
    "# retained MQTT snapshot",
    "# broker : ${Broker}:${Port}",
    "# topics : $($Topics -join ', ')",
    "# git    : $(git -C $repo rev-parse --short HEAD 2>$null)",
    "# topics are sorted so two snapshots diff cleanly"
)
($header + $sorted) -join "`n" | Set-Content $Out -Encoding utf8
Write-Host "wrote $Out with $($sorted.Count) retained topic(s)"
