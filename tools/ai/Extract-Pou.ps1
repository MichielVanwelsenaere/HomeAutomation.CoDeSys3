<#
.SYNOPSIS
    Print one POU from a PLCopen export as readable Structured Text.

.DESCRIPTION
    The export is 20k lines of XML; this pulls a single POU out of it and prints
    the declaration, the body, and every method and action as ST, which is what
    you actually want to read when changing a function block.

    Works best against a plaintext export, where declarations are already ST:

        ./tools/ai/codesys.ps1 export -Plaintext

    Falls back to the committed structured export, in which case declarations
    are reconstructed loosely from the XML and are for orientation only.

.EXAMPLE
    ./tools/ai/Extract-Pou.ps1 FB_MQTT_BASE
.EXAMPLE
    ./tools/ai/Extract-Pou.ps1 FB_OUTPUT_BINARY_MQTT -Members InitMqtt,PublishReceived
.EXAMPLE
    ./tools/ai/Extract-Pou.ps1 -List
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Name,

    # Only print these methods/actions (default: all of them).
    [string[]]$Members,

    # Print the declaration and member names only, no bodies.
    [switch]$Outline,

    # List every POU in the export and exit.
    [switch]$List,

    [string]$Export
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

if (-not $Export) {
    $plain = Join-Path $repo '.ai\reports\PLCopen.plaintext.xml'
    $Export = if (Test-Path $plain) { $plain } else { Join-Path $repo 'src\Exports\PLCopen.xml' }
}
if (-not (Test-Path $Export)) { throw "No export found at $Export" }

$xml = [xml](Get-Content $Export -Raw)
$nsm = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
$nsm.AddNamespace('p', 'http://www.plcopen.org/xml/tc6_0200')

function Get-PlainDeclaration {
    param($Node)
    # The lossless ST declaration, when the export carried one.
    $n = $Node.SelectSingleNode('.//*[local-name()="InterfaceAsPlainText"]//*[local-name()="xhtml"]')
    if ($n) { return $n.InnerText }
    return $null
}

function Get-BodyText {
    param($Node)
    # Only this node's own <body>, not a nested method's.
    foreach ($child in $Node.ChildNodes) {
        if ($child.LocalName -eq 'body') {
            $st = $child.SelectSingleNode('.//*[local-name()="xhtml"]')
            if ($st) { return $st.InnerText }
        }
    }
    return $null
}

if ($List) {
    foreach ($p in $xml.SelectNodes('//p:pou', $nsm)) {
        $kids = @($p.SelectNodes('.//*[local-name()="Method" or local-name()="Action"]'))
        Write-Host ("{0,-40} {1,-15} {2} member(s)" -f $p.name, $p.pouType, $kids.Count)
    }
    foreach ($d in $xml.SelectNodes('//p:dataType', $nsm)) {
        Write-Host ("{0,-40} {1}" -f $d.name, 'dataType')
    }
    exit 0
}

if (-not $Name) { throw 'Pass a POU name, or -List.' }

$pou = $xml.SelectNodes('//p:pou', $nsm) | Where-Object { $_.name -eq $Name } | Select-Object -First 1
if (-not $pou) {
    $dt = $xml.SelectNodes('//p:dataType', $nsm) | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($dt) {
        Write-Host "(* ==== DATA TYPE $Name ==== *)"
        $decl = Get-PlainDeclaration $dt
        if ($decl) { Write-Host $decl } else { Write-Host $dt.OuterXml }
        exit 0
    }
    throw "POU '$Name' not found in $Export. Try -List."
}

Write-Host "(* ==== $($pou.name)  [$($pou.pouType)]  from $(Split-Path $Export -Leaf) ==== *)"
Write-Host ''
$decl = Get-PlainDeclaration $pou
if ($decl) { Write-Host $decl }
else { Write-Host "(* no plaintext declaration in this export - run: ./tools/ai/codesys.ps1 export -Plaintext *)" }

if (-not $Outline) {
    $body = Get-BodyText $pou
    if ($body) {
        Write-Host ''
        Write-Host '(* ---- body ---- *)'
        Write-Host $body
    }
}

# Not $members: PowerShell variable names are case-insensitive, so that would
# overwrite the -Members parameter and filter every member out.
$memberNodes = $pou.SelectNodes('.//*[local-name()="Method" or local-name()="Action"]')
foreach ($m in $memberNodes) {
    if ($Members -and ($Members -notcontains $m.name)) { continue }
    Write-Host ''
    Write-Host "(* ---- $($m.LocalName): $($m.name) ---- *)"
    if ($Outline) { continue }
    $mdecl = Get-PlainDeclaration $m
    if ($mdecl) { Write-Host $mdecl }
    else {
        # Methods carry no plaintext interface, so show the structured one.
        $iface = $m.SelectSingleNode('./*[local-name()="interface"]')
        if ($iface) { Write-Host "(* interface (structured) *)"; Write-Host $iface.OuterXml }
    }
    $mbody = Get-BodyText $m
    if ($mbody) { Write-Host $mbody }
}
