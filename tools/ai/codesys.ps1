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
      device   Report the configured target, or with -AddModule plug a module
               into the device tree. Writing requires -Force.
      rename   Rename objects and identifiers from a -Map file, rewriting every
               reference to them. -DryRun reports what it would touch and writes
               nothing; writing requires -Force.

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
    [ValidateSet('doctor', 'tree', 'device', 'scan', 'export', 'verify', 'simulate', 'download', 'apply', 'probe',
        'info', 'compare', 'libs', 'scaffold', 'rename')]
    [string]$Task,

    # Operate on a project other than src/HomeAutomation.project. This is what
    # lets the sync-implementation-project skill drive an installation project
    # that lives in a different repository entirely.
    #
    # `download` REFUSES a -Project override: shipping a foreign project to a PLC
    # from this repo's tooling is never what was meant, and the mistake is not
    # undoable.
    [string]$Project,

    # info/compare/export: where the report artefact goes. `export` needs it
    # whenever -Project is given, because the default output path is this
    # repository's committed src/Exports/PLCopen.xml.
    [string]$Output,

    # compare only: the project to compare -Project against. Defaults to this
    # repository's src/HomeAutomation.project, i.e. the reference.
    [string]$Against,

    # info only: include the full declaration and implementation text of every
    # object, not just a hash of it. Large, but it is what lets an agent read an
    # external project without exporting it.
    [switch]$Full,

    # verify/apply: take candidates from somewhere other than .ai/candidates.
    # The sync skill keeps its own set so a half-finished sync and a half-finished
    # block edit cannot get imported into each other's project.
    [string]$Candidates,

    # export only: export just these objects, by name, instead of all IEC content.
    [string[]]$Only,

    # verify/apply: honour the folder structure recorded in the candidate XML.
    # Right for a candidate exported from another project, wrong for a
    # hand-written one (which has no folders and would land at the root).
    [switch]$ImportFolders,

    # verify/apply: what to do when a candidate names an object that already
    # exists. Without this the importer has no say and quietly adds a SECOND
    # object of the same name, leaving the original in place and compiled.
    # An edits spec can also carry it as "import_conflict"; this parameter is
    # for a sync, which has no edits spec.
    [ValidateSet('replace', 'copy', 'skip')]
    [string]$ImportConflict,

    # download only: retarget for one run instead of using the stored address.
    # -Address takes a gateway node address as listed by `scan` (e.g. 003E);
    # -Ip takes an IP. The project is never saved, so committed settings stand.
    [string]$Address,
    [string]$Ip,

    # libs only: change the project's library references. Without any of these
    # `libs` is read-only and just reports what is referenced against what is
    # installed.
    #
    # -RemoveLib takes the name exactly as the Library Manager shows it,
    # placeholders included. -AddLib adds a fixed reference. -UpdateLib takes a
    # PLACEHOLDER name and repoints its default resolution at the newest version
    # installed on this machine - which is not the same as the newest that
    # exists, because a library nobody has downloaded is invisible to it.
    #
    # All three build before saving and refuse to save a project that does not
    # build, exactly as `apply` does.
    [string[]]$RemoveLib,
    [string[]]$AddLib,
    [string[]]$UpdateLib,

    # libs only: also report installed versions of libraries whose name contains
    # this, whether or not the project references them. How to answer "is there
    # a newer Modbus library?" without knowing what it would be called.
    [string]$LibFilter,

    # device only: plug something into the device tree.
    #
    # -AddModule takes the ModuleId from the PARENT's device description (e.g.
    # 0287_75x_647 for the 753-647 DALI multi-master) and reads the rest of the
    # identification off the parent, because a module has none of its own.
    #
    # -AddDevice takes a device's full identification as "type:id:version",
    # optionally with a ":moduleid" tail. Read it out of the device description:
    # C:\ProgramData\CODESYS\Devices\<type>\<id>\<version>\device.xml. With no
    # -Under it lands at the project root, which is how a second controller gets
    # added - a project can hold several, and one that is never downloaded still
    # gets compiled.
    #
    # -Under names the node to plug into (an exact node name wins over a path
    # substring), and -NodeName is the instance name. It is required for
    # -AddDevice and optional for -AddModule, which otherwise follows the
    # _75x_nnn convention the existing modules use.
    #
    # Writing to the real project needs -Force, and the change is only saved if
    # the project still builds - exactly as `apply` and `libs` behave.
    # -RemoveNode unplugs a device or module by node name, and -RenameNode
    # renames one (to the name given by -NodeName). Same guard as adding one: the
    # project is only saved if it still builds.
    #
    # A device's name is in the object path of every compiler message, so a
    # rename makes the recorded baseline stale - re-record it afterwards or every
    # unchanged warning under that device reads as NEW.
    [string]$AddModule,
    [string]$AddDevice,
    [string]$RemoveNode,
    [string]$RenameNode,
    [string]$Under,
    [string]$NodeName,

    # device -AddModule only: where in the parent's child list to plug it,
    # 0-based. Omit to append. On a K-bus the tree order IS the physical order of
    # terminals on the rail, so a module added anywhere but the far right end has
    # to go in at its real position or it reads its neighbour's process image.
    [int]$Index = -1,

    # device only: JSON file naming the I/O channels to map, as
    # { "map_io": [ { "node": "_75x_463_1",
    #                 "channel": "Analog Input Channel 0",
    #                 "variable": "RTD_005" } ] }
    # An unqualified variable name is created, which is what typing one into the
    # IDE's mapping editor does. A freshly added terminal is unusable until its
    # channels are named, and this is the alternative to a double-click each.
    [string]$MapIo,

    # scaffold only: JSON spec of objects to create inside an application - a
    # GVL, a program, or a task calling one. Adding a device gives you an
    # application with a Library Manager and nothing else, so this is what makes
    # that application able to compile anything. Idempotent by name, so re-running
    # a spec updates the text instead of creating a second object.
    [string]$Scaffold,

    # rename only: JSON map of what to rename. The driver reads and parses the
    # file itself rather than being handed a converted object, because a rename
    # map nests deeper than ConvertTo-Json's default depth and a silently
    # truncated map would rename half a project.
    #
    #   {
    #     "objects":     { "MqttVariables": "GVL_MQTT" },
    #     "identifiers": [ { "object": "MqttVariables", "mode": "qualified",
    #                        "map": { "fbMqttPublishQueue": "fbPublishQueue" } } ],
    #     "protect":      [ "name", "pl_on" ],
    #     "skip_objects": [ "MQTT_DISCOVERY_LIGHT" ],
    #     "allow_shadow": [ ]
    #   }
    #
    # mode is local (inside the declaring object only), qualified (also rewrites
    # Owner.name project-wide - right for GVL members and enum values), or loose
    # (also rewrites .name and name := project-wide - the only handle on a
    # function block's pins). protect is never renamed anywhere; skip_objects are
    # left alone by identifier passes.
    #
    # Identifier groups run before the object renames and name their object as the
    # project spells it TODAY, so one map can rename a variable out of the way of
    # an object about to take its name. An object whose old name is also a variable
    # somewhere is refused for that reason - allow_shadow accepts it deliberately.
    [string]$Map,

    # rename only: report what would be touched, write nothing, build nothing.
    [switch]$DryRun,

    # verify/apply: JSON list of surgical edits to POUs already in the project.
    # Defaults to .ai/edits/edits.json when that exists. Use -Edits none to skip.
    [string]$Edits,

    # simulate/download: JSON test spec to run against the running PLC.
    [string]$Spec,

    # simulate/download: milliseconds to let the PLC run before reading state.
    [int]$SettleMs = 1000,

    # export only: write a scratch export with lossless ST declaration text to
    # .ai/reports/PLCopen.plaintext.xml instead of updating the committed export.
    [switch]$Plaintext,

    # download only: leave the application loaded but stopped.
    [switch]$NoStart,

    # download only: also write a boot application, so the PLC comes back up
    # running this project after a power cycle.
    [switch]$BootApplication,

    # download only: skip the cold reset that normally runs between login and
    # start. The reset is what guarantees FB_init re-runs, so without it a changed
    # FB_init argument can still read as its OLD value on the PLC while the source,
    # the export and the build all agree on the new one. Only pass this if you are
    # deliberately preserving RETAIN state across a download.
    [switch]$NoColdReset,

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
$referenceProject = Join-Path $repo 'src\HomeAutomation.project'
# NOT $project: PowerShell variable names are case-insensitive, so $project and
# the -Project parameter are the same variable, and assigning to it silently
# discarded the override. Every task then ran against the reference project
# while the banner cheerfully said "override".
$targetProject = $referenceProject
if ($Project) {
    if (-not (Test-Path $Project)) { throw "Project not found: $Project" }
    $targetProject = (Resolve-Path $Project).Path
}
$aiDir = Join-Path $repo '.ai'
$candidates = if ($Candidates) { $Candidates } else { Join-Path $aiDir 'candidates' }
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

    Report 'project file' (Test-Path $targetProject) $targetProject

    # mosquitto clients: the only way to verify runtime behaviour on this project,
    # since CODESYS simulation cannot run it. Not needed to compile, so optional.
    $mos = $null
    $mosCmd = Get-Command mosquitto_sub -ErrorAction SilentlyContinue
    if ($mosCmd) { $mos = $mosCmd.Source }
    else {
        foreach ($p in @("$env:ProgramFiles\mosquitto\mosquitto_sub.exe",
                "${env:ProgramFiles(x86)}\mosquitto\mosquitto_sub.exe")) {
            if (Test-Path $p) { $mos = $p; break }
        }
    }
    if ($mos) { Report 'mosquitto_sub' $true $mos }
    else {
        Report 'mosquitto_sub' $false 'not found - winget install --id EclipseFoundation.Mosquitto' -Optional
    }

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

# ---------------------------------------------------------------- edits

function Resolve-Edits {
    # Returns the edit list to hand to the driver, with every *_file path made
    # absolute (the driver reads them itself, so no escaping games).
    if ($Edits -eq 'none') { return @() }
    $path = $Edits
    if (-not $path) {
        $default = Join-Path $repo '.ai\edits\edits.json'
        if (-not (Test-Path $default)) { return @() }
        $path = $default
    }
    if (-not (Test-Path $path)) { throw "Edit spec not found: $path" }
    $spec = Get-Content $path -Raw | ConvertFrom-Json
    # Not an edit, but it travels in the same spec file because it belongs to the
    # same operation: what the driver should do when a candidate XML names an
    # object that already exists. Without it the import quietly adds a duplicate.
    if ($spec.PSObject.Properties.Name -contains 'import_conflict') {
        $script:importConflict = $spec.import_conflict
    }
    $list = @($spec.edits)
    $base = Split-Path (Resolve-Path $path) -Parent
    $out = @()
    foreach ($e in $list) {
        if (-not $e) { continue }
        $h = [ordered]@{}
        foreach ($p in $e.PSObject.Properties) {
            $v = $p.Value
            if ($p.Name -like '*_file' -and $v) {
                # Relative to the spec file, then to the repo root.
                $cand = Join-Path $base $v
                if (-not (Test-Path $cand)) { $cand = Join-Path $repo $v }
                if (-not (Test-Path $cand)) { throw "Edit fragment not found: $v (for $($e.pou))" }
                $v = (Resolve-Path $cand).Path
            }
            $h[$p.Name] = $v
        }
        $out += $h
    }
    Write-Host "edits     : $($out.Count) from $path"
    return $out
}

function Resolve-Scaffold {
    # Same treatment as an edits spec: every *_file path made absolute, because
    # the driver reads the fragments itself.
    if (-not $Scaffold) { throw 'scaffold needs -Scaffold <spec.json>.' }
    if (-not (Test-Path $Scaffold)) { throw "Scaffold spec not found: $Scaffold" }
    $spec = Get-Content $Scaffold -Raw | ConvertFrom-Json
    $base = Split-Path (Resolve-Path $Scaffold) -Parent
    $out = @()
    foreach ($o in @($spec.objects)) {
        if (-not $o) { continue }
        $h = [ordered]@{}
        foreach ($p in $o.PSObject.Properties) {
            $v = $p.Value
            if ($p.Name -like '*_file' -and $v) {
                $cand = Join-Path $base $v
                if (-not (Test-Path $cand)) { $cand = Join-Path $repo $v }
                if (-not (Test-Path $cand)) { throw "Scaffold fragment not found: $v" }
                $v = (Resolve-Path $cand).Path
            }
            elseif ($p.Name -eq 'calls' -and $v) { $v = @($v) }
            $h[$p.Name] = $v
        }
        $out += $h
    }
    Write-Host "scaffold  : $($out.Count) object(s) from $Scaffold"
    return $out
}

# ---------------------------------------------------------------- sandbox

function New-Sandbox {
    # A throwaway copy, so a broken candidate or a simulation flag can never
    # reach the real project. Returns the path of the copied project.
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    $sandbox = Join-Path $work (Split-Path $targetProject -Leaf)
    Copy-Item $targetProject $sandbox
    # Keep the project-relative Libraries layout intact in the sandbox. A
    # foreign project may resolve everything from the installed repository and
    # have no sibling folder at all, which is fine.
    $libs = Join-Path (Split-Path $targetProject -Parent) 'Libraries'
    if (Test-Path $libs) { Copy-Item $libs (Join-Path $work 'Libraries') -Recurse -Force }
    return $sandbox
}

# ---------------------------------------------------------------- build the task

$projectStem = [IO.Path]::GetFileNameWithoutExtension($targetProject)
# Reports for a foreign project are stem-qualified, so a `verify` on an
# installation project cannot overwrite this repository's own baseline.json and
# quietly retune what "NEW vs baseline" means for the next reference build.
$suffix = if ($Project) { ".$projectStem" } else { '' }
$reportName = switch ($Task) {
    'verify' { if ($Baseline) { "baseline$suffix.json" } else { "verify$suffix.json" } }
    # Always stem-qualified: the sync skill runs `info` against two projects in
    # a row, and an unqualified name would make the second clobber the first.
    'info'   { "info.$projectStem.json" }
    default  { "$Task$suffix.json" }
}
$baselineName = "baseline$suffix.json"
$reportPath = Join-Path $reports $reportName

$cfg = [ordered]@{
    task    = $Task
    report  = $reportPath
    project = $targetProject
}

switch ($Task) {
    'info' {
        # Read-only. Opened with VersionUpdateFlags.NoUpdates on the driver side,
        # so looking at an older project never silently converts it.
        $cfg.full = [bool]$Full
        $cfg.ide_version = $codesys.VersionInfo.ProductVersion
        if ($Output) { $cfg.output = $Output }
    }
    'libs' {
        if ($RemoveLib) { $cfg.lib_remove = @($RemoveLib) }
        if ($AddLib)    { $cfg.lib_add    = @($AddLib) }
        if ($UpdateLib) { $cfg.lib_update = @($UpdateLib) }
        if ($LibFilter) { $cfg.lib_filter = $LibFilter }
        if ($RemoveLib -or $AddLib -or $UpdateLib) {
            Write-Host 'mode      : editing library references (builds before saving)'
        }
        else {
            Write-Host 'mode      : read-only report'
        }
    }
    'scaffold' {
        if (-not $Force) {
            throw "scaffold writes to $targetProject. Re-run with -Force."
        }
        $cfg.scaffold = Resolve-Scaffold
    }
    'device' {
        if ($AddModule -or $AddDevice -or $RemoveNode -or $RenameNode -or $MapIo) {
            if (-not $Force) {
                throw "device -AddModule/-AddDevice/-RemoveNode/-RenameNode/-MapIo writes to $targetProject. Re-run with -Force."
            }
            if ($RenameNode -and -not $NodeName) {
                throw 'device -RenameNode needs -NodeName <name>, the name to rename it to.'
            }
            if ($RemoveNode) { $cfg.node_remove = $RemoveNode }
            if ($RenameNode) { $cfg.node_rename = $RenameNode }
            if ($MapIo) {
                if (-not (Test-Path $MapIo)) { throw "I/O mapping spec not found: $MapIo" }
                $mapIoSpec = Get-Content $MapIo -Raw | ConvertFrom-Json
                $mapIoRules = @($mapIoSpec.map_io)
                if (-not $mapIoRules -or $mapIoRules.Count -eq 0) {
                    throw "$MapIo has no map_io array - nothing to map."
                }
                Write-Host "mappings  : $($mapIoRules.Count) channel(s) from $MapIo"
            }
            if ($AddModule -and -not $Under) {
                throw 'device -AddModule needs -Under <node>, the device tree node to plug it into.'
            }
            if ($AddDevice -and -not $NodeName) {
                throw 'device -AddDevice needs -NodeName <name>, what to call the new device.'
            }
            if ($Index -ge 0 -and -not $AddModule) {
                throw 'device -Index only means anything with -AddModule.'
            }
            if ($AddModule) { $cfg.module_add = $AddModule }
            if ($AddDevice) { $cfg.device_add = $AddDevice }
            if ($Under)     { $cfg.node_under = $Under }
            if ($NodeName)  { $cfg.node_name  = $NodeName }
            if ($Index -ge 0) {
                $cfg.node_index = $Index
                Write-Host "position  : index $Index under $Under"
            }
            if ($MapIo) { $cfg.map_io = $mapIoRules }
            Write-Host 'mode      : editing the device tree (builds before saving)'
        }
        else {
            Write-Host 'mode      : read-only report'
        }
    }
    'compare' {
        $right = if ($Against) { $Against } else { $referenceProject }
        if (-not (Test-Path $right)) { throw "Comparison project not found: $right" }
        $cfg.against = (Resolve-Path $right).Path
        if ($cfg.against -eq $targetProject) {
            throw 'compare needs two different projects. Pass -Project and -Against.'
        }
        if ($Output) { $cfg.output = $Output }
        Write-Host "left      : $targetProject"
        Write-Host "right     : $($cfg.against)"
    }
    'export' {
        if ($Project -and -not $Output -and -not $Plaintext) {
            throw @'
export writes src/Exports/PLCopen.xml by default, which belongs to THIS
repository and does not describe the project you passed with -Project.
Pass -Output <path> to say where the foreign export should go.
'@
        }
        if ($Output) {
            $cfg.output = $Output
            $cfg.plaintext = [bool]$Plaintext
        }
        elseif ($Plaintext) {
            # Scratch copy with lossless ST declarations: much easier to read
            # than the XML-encoded form, but not the committed artefact - the
            # docs generator parses the structured declarations.
            $cfg.output = Join-Path $reports 'PLCopen.plaintext.xml'
            $cfg.plaintext = $true
        }
        else {
            $cfg.output = Join-Path $repo 'src\Exports\PLCopen.xml'
        }
        if ($Only) { $cfg.only = @($Only); Write-Host "objects   : $($Only -join ', ')" }
    }
    'verify' {
        $cfg.project = New-Sandbox
        $cfg.candidates = if ($Baseline) { '' } else { $candidates }
        # A baseline must be the untouched project, so it takes no edits.
        if (-not $Baseline) {
            $cfg.edits = Resolve-Edits
            # Explicit parameter wins over whatever an edits spec happened to say.
            if ($ImportConflict) { $script:importConflict = $ImportConflict }
            if ($script:importConflict) { $cfg.import_conflict = $script:importConflict }
            $cfg.import_folders = [bool]$ImportFolders
        }
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
        if ($Project) {
            throw @'
download refuses a -Project override. This repository's tooling ships THIS
project to a PLC; pointing it at an installation project would put reference
code onto a building's controller from the wrong working copy, and there is no
undo. Open that project in the IDE and download it from there.
'@
        }
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
        # A cold reset between login and start, so what runs is the code just
        # downloaded, initialised from scratch. Off only if you are deliberately
        # keeping RETAIN state across the download and accept that an FB_init value
        # on the PLC may then be the previous one. See do_download.
        $cfg.cold_reset = (-not $NoColdReset)
        $cfg.boot_application = [bool]$BootApplication
        $cfg.settle_ms = $SettleMs
        if ($Address -and $Ip) { throw 'Pass -Address or -Ip, not both.' }
        if ($Address) { $cfg.address = $Address; Write-Host "target    : node $Address (this run only)" }
        if ($Ip) { $cfg.ip = $Ip; Write-Host "target    : $Ip (this run only)" }
        # Credentials from the environment only. They are passed through the task
        # file, which lives in gitignored .ai/ and is deleted after the run.
        # Process environment first, then the User-scope registry value. The
        # fallback matters for an agent: a tool call's shell inherits the host
        # process's environment block, which was captured at startup, so a
        # [Environment]::SetEnvironmentVariable(...,'User') made mid-session is
        # invisible to $env: until the host restarts - but it IS readable here.
        $plcUser = $env:PLC_USER
        $plcPass = $env:PLC_PASS
        $plcFrom = '$env:PLC_USER'
        if (-not $plcUser) {
            $plcUser = [Environment]::GetEnvironmentVariable('PLC_USER', 'User')
            $plcPass = [Environment]::GetEnvironmentVariable('PLC_PASS', 'User')
            $plcFrom = 'User-scope environment'
        }
        if ($plcUser) {
            $cfg.plc_user = $plcUser
            $cfg.plc_password = $plcPass
            Write-Host "credentials: using $plcFrom ($plcUser)"
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
    'rename' {
        if (-not $Map) { throw 'rename needs -Map <file>, the JSON rename map.' }
        if (-not (Test-Path $Map)) { throw "Rename map not found: $Map" }
        if (-not $DryRun -and -not $Force) {
            throw "rename writes to $targetProject. Re-run with -Force, or with -DryRun to see what it would touch."
        }
        $cfg.rename_map = (Resolve-Path $Map).Path
        $cfg.dry_run = [bool]$DryRun
        if ($DryRun) { Write-Host 'mode      : dry run, nothing is written' }
    }
    'apply' {
        if (-not $Force) {
            throw "apply writes to $targetProject. Re-run with -Force."
        }
        $cfg.candidates = $candidates
        $cfg.edits = Resolve-Edits
        if ($ImportConflict) { $script:importConflict = $ImportConflict }
        if ($script:importConflict) { $cfg.import_conflict = $script:importConflict }
        $cfg.import_folders = [bool]$ImportFolders
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
if ($Project) { Write-Host "project   : $targetProject (override)" -ForegroundColor Cyan }
if ($Task -in @('verify', 'apply')) {
    $n = @(Get-ChildItem $candidates -Filter '*.xml' -ErrorAction SilentlyContinue).Count
    if ($Baseline) { Write-Host 'candidates: none (baseline run)' }
    else { Write-Host "candidates: $n file(s)" }
}

if ($Task -eq 'verify' -and -not $Baseline -and -not (Test-Path (Join-Path $reports $baselineName))) {
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
    'info' {
        $i = $report.info
        if ($i) {
            Write-Host "project      : $($i.path)"
            Write-Host "IDE running  : $($i.ide_version)"
            Write-Host "devices      : $(@($i.devices | ForEach-Object { "$($_.name) [$($_.id) $($_.version)]" }) -join ', ')"
            Write-Host "objects      : $(@($report.objects).Count)"
            Write-Host ''
            Write-Host 'libraries:'
            foreach ($l in @($i.libraries)) {
                Write-Host ("  {0,-46} {1}" -f $l.name, $(if ($l.is_placeholder) { 'placeholder' } else { 'fixed' }))
            }
        }
        if ($report.output) { Write-Host ''; Write-Host "written to   : $($report.output)" }
    }
    'libs' {
        foreach ($c in @($report.library_changes | Where-Object { $_ })) {
            Write-Host "  $c" -ForegroundColor Green
        }
        if ($report.library_changes) { Write-Host '' }
        Write-Host 'references:'
        foreach ($r in @($report.library_references)) {
            $kind = if ($r.is_placeholder) { 'placeholder' } else { 'fixed' }
            $note = ''
            if ($r.outdated) { $note = "  <-- $($r.latest_installed) is installed" }
            elseif ($r.not_in_repository) { $note = '  <-- not in any local repository' }
            elseif ($r.unresolved) { $note = '  (not resolved in this project)' }
            $shown = if ($r.is_placeholder -and $r.effective_resolution) { "$($r.name)  ->  $($r.effective_resolution)" } else { $r.name }
            $line = "  {0,-64} {1,-12}{2}" -f $shown, $kind, $note
            if ($r.outdated) { Write-Host $line -ForegroundColor Yellow }
            elseif ($r.not_in_repository) { Write-Host $line -ForegroundColor Red }
            else { Write-Host $line }
        }
        if ($report.library_repository_error) {
            Write-Host ''
            Write-Host "library repository: $($report.library_repository_error)" -ForegroundColor Yellow
        }
        if ($report.installed_libraries) {
            Write-Host ''
            Write-Host 'installed versions (this machine only - the Store is not consulted):'
            foreach ($p in $report.installed_libraries.PSObject.Properties | Sort-Object Name) {
                Write-Host ("  {0,-46} {1}" -f $p.Name, ($p.Value.versions -join ', '))
            }
        }
        if ($null -ne $report.saved) {
            Write-Host ''
            Write-Host "saved     : $($report.saved)"
        }
    }
    'scaffold' {
        foreach ($c in @($report.scaffold | Where-Object { $_ })) {
            Write-Host "  $c" -ForegroundColor Green
        }
        Write-Host ''
        Write-Host "built: $($report.built -join ', ')"
        Write-Host "saved: $($report.saved)"
    }
    'rename' {
        $r = $report.renames
        if ($r) {
            if ($r.dry_run) { Write-Host 'DRY RUN - nothing was written' -ForegroundColor Yellow; Write-Host '' }
            if (@($r.objects).Count -gt 0) {
                Write-Host 'objects renamed:'
                # One name can reach several objects: two applications mean two
                # MqttVariables, and a program is renamed together with the task
                # configuration's call entry for it. Say which is which rather than
                # printing the same line twice.
                $dupes = @($r.objects | Group-Object old | Where-Object { $_.Count -gt 1 } |
                    ForEach-Object { $_.Name })
                foreach ($o in @($r.objects)) {
                    $note = ''
                    if ($o.task_call) { $note = '   (task call)' }
                    elseif ($dupes -contains $o.old) { $note = "   $($o.path)" }
                    Write-Host ("  {0,-40} -> {1}{2}" -f $o.old, $o.new, $note) -ForegroundColor Green
                }
                if ($r.object_references) {
                    Write-Host ''
                    Write-Host "references rewritten: $($r.object_references.total)"
                    foreach ($h in @($r.object_references.top)) {
                        Write-Host ("  {0,-64} {1}" -f $h.object, $h.hits)
                    }
                }
            }
            if (@($r.identifiers).Count -gt 0) {
                Write-Host ''
                Write-Host 'identifiers renamed:'
                foreach ($i in @($r.identifiers)) {
                    Write-Host ("  {0,-52} {1,4} name(s)  {2,5} local  {3,5} elsewhere  ({4})" -f `
                        $i.object, $i.names, $i.local_hits, $i.cross_hits, $i.mode)
                }
                # A cross-object rename that lands nowhere is the interesting case:
                # either nothing refers to it, or it is referred to in a shape this
                # pass does not recognise - and the second is a silent half-rename.
                foreach ($i in @($r.identifiers | Where-Object { $_.mode -ne 'local' -and $_.cross_hits -eq 0 })) {
                    Write-Host "  note: $($i.object) matched nothing outside itself" -ForegroundColor Yellow
                }
            }
            if ($r.protected) { Write-Host ''; Write-Host "protected names (never renamed): $($r.protected)" }
        }
        if ($null -ne $report.saved) {
            Write-Host ''
            Write-Host "built: $($report.built -join ', ')"
            Write-Host "saved: $($report.saved)"
        }
    }
    'device' {
        foreach ($c in @($report.device_changes | Where-Object { $_ })) {
            Write-Host "  $c" -ForegroundColor Green
        }
        if ($report.device_changes) { Write-Host '' }
        Write-Host 'device tree:'
        foreach ($d in @($report.devices)) {
            $note = ''
            if ($d.gateway) { $note = "  gateway $($d.gateway) address $($d.address) simulation $($d.simulation)" }
            Write-Host ("  {0,-52}{1}" -f $d.path, $note)
        }
        if (@($report.gateways).Count -gt 0) {
            Write-Host ''
            Write-Host 'gateways:'
            foreach ($g in @($report.gateways)) { Write-Host "  $($g.name)  $($g.id)" }
        }
        if ($null -ne $report.saved) {
            Write-Host ''
            Write-Host "saved     : $($report.saved)"
        }
    }
    'compare' {
        Write-Host "left  : $($report.compare.left)"
        Write-Host "right : $($report.compare.right)"
        Write-Host ''
        foreach ($d in @($report.compare.differences)) {
            Write-Host ("  {0,-14} {1}" -f $d.difference, $d.path)
        }
        Write-Host ''
        Write-Host "differences: $(@($report.compare.differences).Count)"
        if ($report.output) { Write-Host "written to : $($report.output)" }
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
        foreach ($e in @($report.edits | Where-Object { $null -ne $_ })) {
            if ($e.error) { Write-Host "edit $($e.target): FAILED - $($e.error)" -ForegroundColor Red }
            else { Write-Host "edit $($e.target): $(@($e.applied) -join ', ')" }
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
    if ($null -ne $report.online.cold_reset) {
        # Worth printing either way: if this says False after a download, any value
        # that arrives through FB_init may still be the previous one.
        Write-Host "  cold reset : $($report.online.cold_reset)"
    }
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

# Advisories are not compiler output: they are cases where the build is clean and the
# change still will not do what it looks like it does. Printed for every task, because
# the whole point is that nothing else would tell you.
if ($report.advisories) {
    Write-Host ''
    Write-Host "ADVISORIES ($(@($report.advisories).Count)):" -ForegroundColor Yellow
    foreach ($a in $report.advisories) { Write-Host "  $a" -ForegroundColor Yellow }
}

# Diff against the recorded baseline so pre-existing warnings stay quiet.
$baselinePath = Join-Path $reports $baselineName
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
