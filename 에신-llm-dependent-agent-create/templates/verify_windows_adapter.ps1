# verify_windows_adapter.ps1 - Aesin V3.9 standard static verifier
# Statically checks Windows .bat adapter files against rules 1-7.
# Usage:  powershell -ExecutionPolicy Bypass -File tools\verify_windows_adapter.ps1 -ProjectDir . -HumanFacing
param(
    [string]$ProjectDir = ".",
    [switch]$HumanFacing
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path $ProjectDir
$batFiles = Get-ChildItem -Path $root -Filter *.bat -File
if (-not $batFiles) {
    Write-Host "[FAIL] No .bat adapter found in $root"
    exit 1
}

$anyFail = $false

foreach ($bat in $batFiles) {
    Write-Host ""
    Write-Host "=== Checking: $($bat.Name) ==="
    $bytes = [System.IO.File]::ReadAllBytes($bat.FullName)
    $text  = [System.Text.Encoding]::UTF8.GetString($bytes)
    $results = @()

    # Rule 1: zero non-ASCII characters (no Korean in .bat - cp949 console safety)
    $nonAscii = @($text.ToCharArray() | Where-Object { [int]$_ -gt 127 })
    $results += [pscustomobject]@{
        No = 1; Rule = "No non-ASCII characters (Korean count must be 0)"
        Pass = ($nonAscii.Count -eq 0)
        Note = if ($nonAscii.Count -gt 0) { "$($nonAscii.Count) non-ASCII chars found" } else { "" }
    }

    # Rule 2: @echo off present
    $results += [pscustomobject]@{
        No = 2; Rule = "@echo off present"
        Pass = ($text -match "(?im)^\s*@echo off"); Note = ""
    }

    # Rule 3: pushd "%~dp0" (run from script's own folder)
    $results += [pscustomobject]@{
        No = 3; Rule = 'pushd "%~dp0" present'
        Pass = ($text -match '(?i)pushd\s+"%~dp0"'); Note = ""
    }

    # Rule 4: chcp 65001 (UTF-8 code page)
    $results += [pscustomobject]@{
        No = 4; Rule = "chcp 65001 present"
        Pass = ($text -match "(?i)chcp\s+65001"); Note = ""
    }

    # Rule 5: PYTHONUTF8=1 (and PYTHONIOENCODING recommended)
    $utf8Set = ($text -match "(?i)set\s+PYTHONUTF8=1")
    $ioSet   = ($text -match "(?i)set\s+PYTHONIOENCODING=utf-8")
    $results += [pscustomobject]@{
        No = 5; Rule = "set PYTHONUTF8=1 present"
        Pass = $utf8Set
        Note = if (-not $ioSet) { "PYTHONIOENCODING=utf-8 also recommended" } else { "" }
    }

    # Rule 6: no 'timeout' command (blocked with redirected stdin; use ping -n N 127.0.0.1)
    $usesTimeout = ($text -match "(?im)^\s*timeout\b")
    $results += [pscustomobject]@{
        No = 6; Rule = "No 'timeout' command (use ping -n N 127.0.0.1 > nul)"
        Pass = (-not $usesTimeout); Note = ""
    }

    # Rule 7: UTF-8 without BOM
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    $results += [pscustomobject]@{
        No = 7; Rule = "Saved as UTF-8 without BOM"
        Pass = (-not $hasBom); Note = if ($hasBom) { "BOM detected" } else { "" }
    }

    # HumanFacing: a double-clicked adapter must keep the window open long enough
    # to read messages on error paths (ping-based wait present).
    if ($HumanFacing) {
        $results += [pscustomobject]@{
            No = 8; Rule = "[HumanFacing] ping-based wait present (readable exit)"
            Pass = ($text -match "(?i)ping\s+-n\s+\d+\s+127\.0\.0\.1"); Note = ""
        }
    }

    foreach ($r in $results) {
        $mark = if ($r.Pass) { "[PASS]" } else { "[FAIL]"; $anyFail = $true }
        $line = "{0} Rule {1}: {2}" -f $mark, $r.No, $r.Rule
        if ($r.Note) { $line += "  ({0})" -f $r.Note }
        Write-Host $line
    }
}

Write-Host ""
if ($anyFail) {
    Write-Host "RESULT: FAIL - fix the rules above and re-run."
    exit 1
} else {
    Write-Host "RESULT: PASS - all adapter rules satisfied."
    exit 0
}
