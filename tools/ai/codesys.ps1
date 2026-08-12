<#
.SYNOPSIS
    Drives CODESYS headlessly so an AI agent (or CI) gets real compiler feedback
    on this PLC project.

.DESCRIPTION
    Launches CODESYS.exe with --noUI and tools/ai/codesys_task.py, then prints
    the JSON report that script leaves behind. A --noUI CODESYS process has no
    usable stdout, so all results travel through .ai/reports/*.json.

    Tasks:

      doctor   Check the toolchain without launching CODESYS.
      tree     Dump the project object tree.
      export   Re-export src/Exports/PLCopen.xml from src/HomeAutomation.project.
      verify   Copy the project to .ai/work, import every .ai/candidates/*.xml
               into the copy, build it, report all compiler messages.
               The real project is never touched.
      apply    Import .ai/candidates/*.xml into the real project and save it,
               but only if it still builds. Requires -Force.

.EXAMPLE
    ./tools/ai/codesys.ps1 verify
.EXAMPLE
    ./tools/ai/codesys.ps1 verify -Baseline      # record today's clean-tree messages
.EXAMPLE
    ./tools/ai/codesys.ps1 export
.EXAMPLE
    ./tools/ai/codesys.ps1 apply -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('doctor', 'tree', 'device', 'scan', 'export', 'verify', 'simulate', 'download', 'apply', 'probe')]
    [string]$Task,

    # download only: retarget for one run instead of using the stored address.
    # -Address takes a gateway node address as listed by `scan` (e.g. 003E);
    # -Ip takes an IP. The project is never saved, so committed settings stand.
    [string]$Address,
    [string]$Ip,

    # simulate/download: JSON test spec to run against the running PLC.
    [string]$Spec,

    # simulate/download: milliseconds to let the PLC run before reading state.
    [int]$SettleMs = 1000,

    # download only: leave the application loaded but stopped.
    [switch]$NoStart,

    # download only: also write a boot application, so the PLC comes back up
    # running this project after a power cycle.
    [switch]$BootApplication,

    # verify only: build the project as-is and store the result as the baseline
    # that every later verify run is diffed against.
    [switch]$Baseline,

    # apply only: required, because this writes to src/HomeAutomation.project.
    [switch]$Force,

    # Override the CODESYS executable / profile if you run a different install.
    [string]$Exe,
    [string]$CodesysProfile,

    [int]$TimeoutMinutes = 20
)

$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project = Join-Path $repo 'src\HomeAutomation.project'
$aiDir = Join-Path $repo '.ai'
$candidates = Join-Path $aiDir 'candidates'
$reports = Join-Path $aiDir 'reports'
$work = Join-Path $aiDir 'work'

foreach ($d in @($aiDir, $candidates, $reports)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# ---------------------------------------------------------------- locate CODESYS

function Resolve-Codesys {
    param([string]$Explicit)
    if ($Explicit) {
        if (-not (Test-Path $Explicit)) { throw "CODESYS not found at $Explicit" }
        return (Get-Item $Explicit)
    }
    if ($env:CODESYS_EXE -and (Test-Path $env:CODESYS_EXE)) { return (Get-Item $env:CODESYS_EXE) }
    $found = Get-ChildItem -Path 'C:\Program Files', 'C:\Program Files (x86)' -Filter 'CODESYS.exe' `
        -Recurse -Depth 4 -ErrorAction SilentlyContinue |
        Sort-Object { $_.VersionInfo.ProductVersion } -Descending |
        Select-Object -First 1
    if (-not $found) {
        throw 'CODESYS.exe not found. Pass -Exe <path> or set $env:CODESYS_EXE.'
    }
    return $found
}

# ---------------------------------------------------------------- doctor

if ($Task -eq 'doctor') {
    $problems = 0
    function Report {
        param([string]$Name, [bool]$Ok, [string]$Detail, [switch]$Optional)
        $mark = if ($Ok) { 'OK  ' } elseif ($Optional) { 'WARN' } else { 'FAIL' }
        $colour = if ($Ok) { 'Green' } elseif ($Optional) { 'Yellow' } else { 'Red' }
        Write-Host ("[{0}] {1,-22} {2}" -f $mark, $Name, $Detail) -ForegroundColor $colour
        if (-not $Ok -and -not $Optional) { $script:problems++ }
    }

    $psOk = $PSVersionTable.PSVersion.Major -ge 5
    Report 'PowerShell' $psOk "$($PSVersionTable.PSVersion) (5.1+ required)"

    $exeItem = $null
    try { $exeItem = Resolve-Codesys -Explicit $Exe } catch { }
    Report 'CODESYS.exe' ($null -ne $exeItem) $(
        if ($exeItem) { "$($exeItem.FullName) ($($exeItem.VersionInfo.ProductVersion))" }
        else { 'not found - install CODESYS 3.5 SP21, or set $env:CODESYS_EXE' })

    if ($exeItem) {
        $common = Split-Path $exeItem.FullName -Parent
        $root = Split-Path $common -Parent
        $engine = Join-Path $common 'ScriptEngine.dll'
        Report 'ScriptEngine' (Test-Path $engine) $(
            if (Test-Path $engine) { 'present (headless scripting available)' }
            else { 'MISSING - the whole harness depends on it' })

        $profiles = @(Get-ChildItem (Join-Path $root 'Profiles') -Filter '*.profile.xml' -ErrorAction SilentlyContinue)
        Report 'CODESYS profile' ($profiles.Count -gt 0) $(
            if ($profiles.Count -gt 0) { ($profiles | ForEach-Object { $_.Name -replace '\.profile\.xml$', '' }) -join ', ' }
            else { 'no profile found' })

        $pfc = Test-Path (Join-Path $root 'CODESYS Control for PFC200 SL')
        Report 'PFC200 SL package' $pfc $(
            if ($pfc) { 'installed' } else { 'missing - the project device will not resolve' }) -Optional:(-not $pfc)
    }

    Report 'project file' (Test-Path $project) $project

    # Python is not needed by this harness, only by the update-fb-docs skill.
    $py = $null
    foreach ($c in @('py', 'python', 'python3')) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        # The Windows "App Execution Alias" stub is a 0-byte reparse point that
        # opens the Microsoft Store instead of running Python.
        if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $py = $cmd; break }
    }
    if ($py) {
        $ver = (& $py.Source --version 2>&1) -join ' '
        Report 'Python (docs only)' $true "$ver at $($py.Source)"
    }
    else {
        Report 'Python (docs only)' $false 'not installed - see the codesys-loop skill for the winget command' -Optional
    }

    Write-Host ''
    if ($problems -gt 0) {
        Write-Host "RESULT: $problems required item(s) missing" -ForegroundColor Red
        exit 1
    }
    Write-Host 'RESULT: toolchain OK' -ForegroundColor Green
    exit 0
}

$codesys = Resolve-Codesys -Explicit $Exe

if (-not $CodesysProfile) {
    $profileDir = Join-Path (Split-Path (Split-Path $codesys.FullName -Parent) -Parent) 'Profiles'
    $profileFile = Get-ChildItem -Path $profileDir -Filter '*.profile.xml' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $profileFile) { throw "No CODESYS profile found in $profileDir. Pass -CodesysProfile." }
    $CodesysProfile = $profileFile.Name -replace '\.profile\.xml$', ''
}

# ---------------------------------------------------------------- sandbox

function New-Sandbox {
    # A throwaway copy, so a broken candidate or a simulation flag can never
    # reach src/. Returns the path of the copied project.
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    $sandbox = Join-Path $work 'HomeAutomation.project'
    Copy-Item $project $sandbox
    # Keep the project-relative Libraries layout intact in the sandbox.
    Copy-Item (Join-Path $repo 'src\Libraries') (Join-Path $work 'Libraries') -Recurse -Force
    return $sandbox
}

# ---------------------------------------------------------------- build the task

$reportName = switch ($Task) {
    'verify' { if ($Baseline) { 'baseline.json' } else { 'verify.json' } }
    default  { "$Task.json" }
}
$reportPath = Join-Path $reports $reportName

$cfg = [ordered]@{
    task    = $Task
    report  = $reportPath
    project = $project
}

switch ($Task) {
    'export' {
        $cfg.output = Join-Path $repo 'src\Exports\PLCopen.xml'
    }
    'verify' {
        $cfg.project = New-Sandbox
        $cfg.candidates = if ($Baseline) { '' } else { $candidates }
    }
    'simulate' {
        # Always a sandbox: `simulate` switches the device into simulation mode,
        # and leaving that flag set in the real project would silently retarget
        # the next GUI download away from the PLC.
        $cfg.project = New-Sandbox
        $cfg.candidates = $candidates
        $cfg.settle_ms = $SettleMs
        if ($Spec) {
            if (-not (Test-Path $Spec)) { throw "Spec file not found: $Spec" }
            $parsed = Get-Content $Spec -Raw | ConvertFrom-Json
            # ConvertTo-Json in the task file re-serialises these verbatim.
            $cfg.steps = @($parsed.steps)
            Write-Host "spec      : $Spec ($(@($parsed.steps).Count) step(s))"
        }
    }
    'download' {
        if (-not $Force) {
            throw @'
download transfers the application to the real PLC and starts it. This stops the
running application and re-initialises non-persistent variables. Re-run with
-Force once you are sure the target is the intended device.
'@
        }
        # Downloads the real project deliberately: the point is to ship what
        # src/HomeAutomation.project actually contains.
        $cfg.start = (-not $NoStart)
        $cfg.boot_application = [bool]$BootApplication
        $cfg.settle_ms = $SettleMs
        if ($Address -and $Ip) { throw 'Pass -Address or -Ip, not both.' }
        if ($Address) { $cfg.address = $Address; Write-Host "target    : node $Address (this run only)" }
        if ($Ip) { $cfg.ip = $Ip; Write-Host "target    : $Ip (this run only)" }
        # Credentials from the environment only. They are passed through the task
        # file, which lives in gitignored .ai/ and is deleted after the run.
        if ($env:PLC_USER) {
            $cfg.plc_user = $env:PLC_USER
            $cfg.plc_password = $env:PLC_PASS
            Write-Host "credentials: using `$env:PLC_USER ($($env:PLC_USER))"
        }
        else {
            Write-Host 'credentials: none set; relying on CODESYS''s cached device login'
            Write-Host '             set $env:PLC_USER / $env:PLC_PASS if login fails'
        }
        if ($Spec) {
            if (-not (Test-Path $Spec)) { throw "Spec file not found: $Spec" }
            $cfg.steps = @((Get-Content $Spec -Raw | ConvertFrom-Json).steps)
        }
    }
    'apply' {
        if (-not $Force) {
            throw 'apply writes to src/HomeAutomation.project. Re-run with -Force.'
        }
        $cfg.candidates = $candidates
    }
}

$taskFile = Join-Path $reports 'task.json'
# UTF-8 *without* BOM: the IronPython side json.loads() the raw text.
[System.IO.File]::WriteAllText($taskFile, ($cfg | ConvertTo-Json -Depth 5),
    (New-Object System.Text.UTF8Encoding($false)))
if (Test-Path $reportPath) { Remove-Item $reportPath -Force }

# ---------------------------------------------------------------- run

$driver = Join-Path $PSScriptRoot 'codesys_task.py'
Write-Host "CODESYS   : $($codesys.FullName) ($($codesys.VersionInfo.ProductVersion))"
Write-Host "profile   : $CodesysProfile"
Write-Host "task      : $Task -> $reportPath"
if ($Task -in @('verify', 'apply')) {
    $n = @(Get-ChildItem $candidates -Filter '*.xml' -ErrorAction SilentlyContinue).Count
    if ($Baseline) { Write-Host 'candidates: none (baseline run)' }
    else { Write-Host "candidates: $n file(s)" }
}

if ($Task -eq 'verify' -and -not $Baseline -and -not (Test-Path (Join-Path $reports 'baseline.json'))) {
    Write-Host 'note      : no baseline recorded; pre-existing library warnings will be listed too.' -ForegroundColor Yellow
    Write-Host '            run "./tools/ai/codesys.ps1 verify -Baseline" once to silence them.' -ForegroundColor Yellow
}

$cliArgs = @(
    "--profile=`"$CodesysProfile`""
    '--noUI'
    "--runscript=`"$driver`""
    "--scriptargs:`"$taskFile`""
)
$sw = [Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $codesys.FullName -ArgumentList $cliArgs -PassThru
$null = $proc.Handle   # cache the handle so ExitCode is readable after exit
if (-not $proc.WaitForExit($TimeoutMinutes * 60 * 1000)) {
    try { $proc.Kill() } catch { }
    throw "CODESYS did not finish within $TimeoutMinutes minutes (killed)."
}
$sw.Stop()
Write-Host ("elapsed   : {0:n1}s (CODESYS exit {1})" -f $sw.Elapsed.TotalSeconds, $proc.ExitCode)

# The task file carries the device password when one was supplied. Shred it as
# soon as CODESYS is done with it rather than leaving it on disk.
if ($cfg.Contains('plc_password')) {
    [System.IO.File]::WriteAllText($taskFile, '{}')
    Remove-Item $taskFile -Force -ErrorAction SilentlyContinue
}

$logPath = "$reportPath.log"
function Show-DriverLog {
    if (Test-Path $logPath) {
        Write-Host ''
        Write-Host "--- driver log ($logPath) ---"
        Get-Content $logPath | ForEach-Object { Write-Host "  $_" }
    }
}

if (-not (Test-Path $reportPath)) {
    Show-DriverLog
    throw "No report at $reportPath - the driver script did not run. Check the profile name."
}
$raw = Get-Content $reportPath -Raw
if ([string]::IsNullOrWhiteSpace($raw)) {
    Show-DriverLog
    throw "Report at $reportPath is empty - the driver died before writing it."
}
try { $report = $raw | ConvertFrom-Json }
catch {
    Show-DriverLog
    throw "Report at $reportPath is not valid JSON: $($_.Exception.Message)"
}

# ---------------------------------------------------------------- summarise

function Get-Where {
    param($Message)
    $bits = @($Message.object, $Message.position) | Where-Object { $_ }
    if ($bits.Count -eq 0) { return '' }
    return ($bits -join ' ')
}

function Show-Messages {
    param($Messages, [string]$Title)
    if (-not $Messages -or @($Messages).Count -eq 0) { return }
    Write-Host ''
    Write-Host $Title
    foreach ($m in $Messages) {
        $where = Get-Where -Message $m
        if ($where) { Write-Host ("  [{0}] {1}  <{2}>" -f $m.severity, $m.text, $where) }
        else { Write-Host ("  [{0}] {1}" -f $m.severity, $m.text) }
    }
}

Write-Host ''
foreach ($e in $report.errors) { Write-Host "TOOL ERROR: $e" -ForegroundColor Red }

$errors = @($report.messages | Where-Object { $_.severity -eq 'Error' -or $_.severity -eq 'FatalError' })
$warnings = @($report.messages | Where-Object { $_.severity -eq 'Warning' })

switch ($Task) {
    'export' {
        Write-Host "exported roots: $($report.exported_roots -join ', ')"
        Write-Host "written to    : $($report.output)"
    }
    'tree' {
        foreach ($node in $report.tree) {
            Write-Host ("{0}{1}" -f (' ' * (2 * $node.depth)), $node.name)
        }
    }
    'scan' {
        foreach ($gw in @($report.scan | Where-Object { $null -ne $_ })) {
            $suffix = if ($gw.cached) { ' (cached result - live scan returned nothing)' } else { '' }
            Write-Host "gateway $($gw.gateway)$suffix"
            $devs = @($gw.devices | Where-Object { $null -ne $_ })
            if ($devs.Count -eq 0) {
                Write-Host '  no PLC answered' -ForegroundColor Yellow
            }
            foreach ($d in $devs) {
                Write-Host ("  {0,-24} address {1,-14} {2} {3}" -f $d.name, $d.address, $d.vendor, $d.type)
            }
        }
    }
    default {
        foreach ($imp in $report.imports) {
            Write-Host ("import {0}: +{1} replaced {2} skipped {3}" -f (Split-Path $imp.file -Leaf),
                @($imp.added).Count, @($imp.replaced).Count, @($imp.skipped).Count)
        }
        Write-Host "built: $($report.built -join ', ')"
        if ($Task -eq 'apply') { Write-Host "saved: $($report.saved)" }
        if ($report.harness) {
            $inst = @($report.harness.instantiated)
            if ($inst.Count -gt 0) {
                Write-Host "harness: instantiated $($inst -join ', ') in $($report.harness.host)"
            }
            # A clean build proves nothing about a block that was never
            # instantiated, so never let this pass by unremarked.
            foreach ($s in @($report.harness.not_instantiated)) {
                Write-Host "NOT COMPILE-CHECKED: $($s.name) - $($s.reason)" -ForegroundColor Yellow
            }
        }
    }
}

if ($report.online) {
    Write-Host ''
    $kind = if ($Task -eq 'download') { 'ONLINE (real PLC)' } else { 'ONLINE (simulation)' }
    Write-Host "${kind}:"
    if ($report.online.simulated_devices) {
        Write-Host "  devices    : $($report.online.simulated_devices -join ', ')"
    }
    if ($report.online.device) {
        Write-Host "  target     : $($report.online.device)  gateway $($report.online.gateway)  address $($report.online.address)"
        Write-Host "  simulation : $($report.online.simulation)"
        Write-Host "  credentials: $($report.online.credentials)"
    }
    Write-Host "  logged in  : $($report.online.logged_in)"
    if ($null -ne $report.online.started) { Write-Host "  started    : $($report.online.started)" }
    if ($report.online.boot_application) { Write-Host "  boot app   : written" }
    Write-Host "  app state  : $($report.online.application_state)"
    Write-Host "  operating  : $($report.online.operation_state)"
    # Filter nulls: @($null) has Count 1 in PowerShell, which previously printed
    # a phantom failing step for runs that never got as far as executing one.
    foreach ($step in @($report.online.steps | Where-Object { $null -ne $_ })) {
        $label = if ($step.label) { $step.label } else { "step $($step.index)" }
        $vals = @()
        if ($step.values) {
            foreach ($p in $step.values.PSObject.Properties) { $vals += "$($p.Name)=$($p.Value)" }
        }
        $failures = @($step.failures | Where-Object { $null -ne $_ })
        $status = if ($failures.Count -gt 0) { 'FAIL' } else { 'ok  ' }
        $colour = if ($failures.Count -gt 0) { 'Red' } else { 'Gray' }
        Write-Host ("  [$status] {0}  {1}" -f $label, ($vals -join '  ')) -ForegroundColor $colour
        foreach ($f in $failures) { Write-Host "         $f" -ForegroundColor Red }
    }
}

$testFailures = @($report.test_failures | Where-Object { $null -ne $_ })
if ($testFailures.Count -gt 0) {
    Write-Host ''
    Write-Host "TEST FAILURES ($($testFailures.Count)):" -ForegroundColor Red
    foreach ($f in $testFailures) { Write-Host "  $f" -ForegroundColor Red }
}

Show-Messages -Messages $errors -Title "ERRORS ($($errors.Count)):"
Show-Messages -Messages $warnings -Title "WARNINGS ($($warnings.Count)):"

# Diff against the recorded baseline so pre-existing warnings stay quiet.
$baselinePath = Join-Path $reports 'baseline.json'
if ($Task -eq 'verify' -and -not $Baseline -and (Test-Path $baselinePath)) {
    $base = Get-Content $baselinePath -Raw | ConvertFrom-Json
    $known = @{}
    foreach ($m in $base.messages) { $known["$($m.severity)|$($m.text)|$($m.object)"] = $true }
    $new = @($report.messages | Where-Object { -not $known.ContainsKey("$($_.severity)|$($_.text)|$($_.object)") })
    Write-Host ''
    Write-Host "NEW vs baseline: $($new.Count)"
    Show-Messages -Messages $new -Title 'NEW MESSAGES:'
}

Write-Host ''
if ($report.ok) {
    # Guard the null: @($null).Count is 1 in PowerShell, which would report
    # phantom unchecked blocks for tasks that have no harness at all.
    $unchecked = 0
    if ($report.harness -and $report.harness.not_instantiated) {
        $unchecked = @($report.harness.not_instantiated).Count
    }
    if ($unchecked -gt 0) {
        Write-Host "RESULT: BUILD OK, but $unchecked candidate block(s) were not compile-checked" -ForegroundColor Yellow
        exit 0
    }
    Write-Host 'RESULT: OK' -ForegroundColor Green
    exit 0
}
Write-Host "RESULT: FAILED ($($errors.Count) error(s), $(@($report.errors).Count) tool error(s))" -ForegroundColor Red
exit 1
