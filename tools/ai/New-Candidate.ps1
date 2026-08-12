<#
.SYNOPSIS
    Build a candidate PLCopen file by copying an existing POU out of the export
    and applying surgical edits to it.

.DESCRIPTION
    Importing a candidate REPLACES the existing object, so a hand-written partial
    file silently deletes every method it forgot to include. This copies the POU
    node verbatim from the export - declaration, body, and every method and
    action - and edits only what you ask it to, so nothing can be lost.

    Source the PLAINTEXT export, so declarations come through as lossless ST:

        ./tools/ai/codesys.ps1 export -Plaintext

.PARAMETER DeclAppend
    Text appended to the POU's plaintext declaration, before the final END_VAR-less
    tail. Use a complete VAR ... END_VAR block.

.PARAMETER BodyPrepend
    Text inserted at the very top of the POU's own body.

.EXAMPLE
    ./tools/ai/New-Candidate.ps1 -Pou FB_MQTT_BASE -DeclAppendFile .ai/work/base.decl
.EXAMPLE
    ./tools/ai/New-Candidate.ps1 -Pou FB_OUTPUT_BINARY_MQTT -BodyPrependFile .ai/work/prologue.st
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Pou,
    [string]$DeclAppend,
    [string]$DeclAppendFile,
    [string]$BodyPrepend,
    [string]$BodyPrependFile,
    # Also copy these DUTs into the same candidate file.
    [string[]]$IncludeDataType,
    [string]$Export,
    [string]$OutFile
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Export) { $Export = Join-Path $repo '.ai\reports\PLCopen.plaintext.xml' }
if (-not (Test-Path $Export)) {
    throw "No plaintext export at $Export. Run: ./tools/ai/codesys.ps1 export -Plaintext"
}
if ($DeclAppendFile) { $DeclAppend = Get-Content $DeclAppendFile -Raw }
if ($BodyPrependFile) { $BodyPrepend = Get-Content $BodyPrependFile -Raw }
if (-not $OutFile) { $OutFile = Join-Path $repo ".ai\candidates\$Pou.xml" }

$NS = 'http://www.plcopen.org/xml/tc6_0200'
$src = [xml](Get-Content $Export -Raw)
$nsm = New-Object System.Xml.XmlNamespaceManager($src.NameTable)
$nsm.AddNamespace('p', $NS)

$node = $src.SelectNodes('//p:pou', $nsm) | Where-Object { $_.name -eq $Pou } | Select-Object -First 1
if (-not $node) { throw "POU '$Pou' not found in $Export" }

# --- build a minimal project envelope ------------------------------------------
$out = New-Object System.Xml.XmlDocument
$out.AppendChild($out.CreateXmlDeclaration('1.0', 'utf-8', $null)) | Out-Null
$proj = $out.CreateElement('project', $NS); $out.AppendChild($proj) | Out-Null

$fh = $out.CreateElement('fileHeader', $NS)
$fh.SetAttribute('companyName', ''); $fh.SetAttribute('productName', 'CODESYS')
$fh.SetAttribute('productVersion', 'CODESYS V3.5 SP21 Patch 3')
$fh.SetAttribute('creationDateTime', '2026-01-01T00:00:00')
$proj.AppendChild($fh) | Out-Null

$ch = $out.CreateElement('contentHeader', $NS)
$ch.SetAttribute('name', $Pou); $ch.SetAttribute('modificationDateTime', '2026-01-01T00:00:00')
$ci = $out.CreateElement('coordinateInfo', $NS)
foreach ($lang in 'fbd', 'ld', 'sfc') {
    $l = $out.CreateElement($lang, $NS); $s = $out.CreateElement('scaling', $NS)
    $s.SetAttribute('x', '1'); $s.SetAttribute('y', '1')
    $l.AppendChild($s) | Out-Null; $ci.AppendChild($l) | Out-Null
}
$ch.AppendChild($ci) | Out-Null; $proj.AppendChild($ch) | Out-Null

$types = $out.CreateElement('types', $NS); $proj.AppendChild($types) | Out-Null
$dts = $out.CreateElement('dataTypes', $NS); $types.AppendChild($dts) | Out-Null
foreach ($dtName in @($IncludeDataType)) {
    if (-not $dtName) { continue }
    $dt = $src.SelectNodes('//p:dataType', $nsm) | Where-Object { $_.name -eq $dtName } | Select-Object -First 1
    if (-not $dt) { throw "dataType '$dtName' not found in $Export" }
    $dts.AppendChild($out.ImportNode($dt, $true)) | Out-Null
}
$pous = $out.CreateElement('pous', $NS); $types.AppendChild($pous) | Out-Null
$copy = $out.ImportNode($node, $true)
$pous.AppendChild($copy) | Out-Null

$inst = $out.CreateElement('instances', $NS)
$inst.AppendChild($out.CreateElement('configurations', $NS)) | Out-Null
$proj.AppendChild($inst) | Out-Null

# --- apply the edits ------------------------------------------------------------
$changed = @()

if ($DeclAppend) {
    $plain = $copy.SelectSingleNode('.//*[local-name()="InterfaceAsPlainText"]/*[local-name()="xhtml"]')
    if (-not $plain) {
        throw "POU '$Pou' has no plaintext declaration - re-export with -Plaintext"
    }
    $plain.InnerText = ($plain.InnerText.TrimEnd() + "`n" + $DeclAppend.TrimEnd() + "`n")
    $changed += 'declaration'

    # The structured <interface> WINS over the plaintext one when both are
    # present and complete, so editing only the plaintext is silently ignored.
    # Emptying it makes the plaintext authoritative. (An empty <interface /> is
    # accepted - proven by compile probe.) Method interfaces are untouched: for
    # a METHOD the structured form is the only one the importer reads at all.
    $iface = $copy.SelectSingleNode('./*[local-name()="interface"]')
    if ($iface) {
        while ($iface.HasChildNodes) { $iface.RemoveChild($iface.FirstChild) | Out-Null }
        $changed += 'structured interface emptied so plaintext wins'
    }
}

if ($BodyPrepend) {
    # Only the POU's OWN body, never a method's.
    $body = $null
    foreach ($c in $copy.ChildNodes) { if ($c.LocalName -eq 'body') { $body = $c; break } }
    if (-not $body) { throw "POU '$Pou' has no body element" }
    $st = $body.SelectSingleNode('.//*[local-name()="xhtml"]')
    if (-not $st) { throw "POU '$Pou' body carries no ST - is it FBD/SFC?" }
    $st.InnerText = ($BodyPrepend.TrimEnd() + "`n`n" + $st.InnerText)
    $changed += 'body'
}

$dir = Split-Path $OutFile -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$sw = New-Object System.IO.StreamWriter($OutFile, $false, (New-Object System.Text.UTF8Encoding($false)))
try { $out.Save($sw) } finally { $sw.Close() }

$members = @($copy.SelectNodes('.//*[local-name()="Method" or local-name()="Action"]')).Count
Write-Host "wrote $OutFile"
Write-Host "  POU      : $Pou ($members method(s)/action(s) carried over intact)"
Write-Host "  edited   : $(if ($changed) { $changed -join ' + ' } else { 'nothing - verbatim copy' })"
if ($IncludeDataType) { Write-Host "  dataTypes: $($IncludeDataType -join ', ')" }
