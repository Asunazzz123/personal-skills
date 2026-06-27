<#
.SYNOPSIS
Build a Visual Studio solution or project with MSBuild and parse diagnostics.

.DESCRIPTION
Finds MSBuild from Visual Studio installations, runs a headless build, captures
output, and emits JSON containing exit code, diagnostics, and useful log lines.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path,

    [ValidateSet("Build", "Rebuild", "Clean", "Restore")]
    [string]$Target = "Build",

    [string]$Configuration = "Debug",
    [string]$Platform,

    [switch]$Prerelease,
    [switch]$Restore,
    [switch]$BinaryLog,
    [string]$LogPath,
    [string]$MSBuildPath,

    [ValidateSet("quiet", "minimal", "normal", "detailed", "diagnostic")]
    [string]$Verbosity = "minimal",

    [switch]$NoExitCode
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-ProgramFilesX86 {
    $value = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetFolderPath("ProgramFiles")
    }
    return $value
}

function Find-VsWhere {
    $candidates = @()
    $envPath = [Environment]::GetEnvironmentVariable("VSWHERE_EXE")
    if (-not [string]::IsNullOrWhiteSpace($envPath)) {
        $candidates += $envPath
    }

    $pf86 = Get-ProgramFilesX86
    if (-not [string]::IsNullOrWhiteSpace($pf86)) {
        $candidates += (Join-Path $pf86 "Microsoft Visual Studio\Installer\vswhere.exe")
    }

    $command = Get-Command "vswhere.exe" -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += $command.Source
    }

    foreach ($candidate in $candidates | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Find-MSBuild {
    param([switch]$AllowPrerelease)

    if (-not [string]::IsNullOrWhiteSpace($MSBuildPath)) {
        if (-not (Test-Path -LiteralPath $MSBuildPath)) {
            throw "MSBuildPath does not exist: $MSBuildPath"
        }
        return (Resolve-Path -LiteralPath $MSBuildPath).Path
    }

    $vswhere = Find-VsWhere
    if ($vswhere) {
        $args = @("-latest", "-products", "*", "-requires", "Microsoft.Component.MSBuild", "-find", "MSBuild\**\Bin\MSBuild.exe")
        if ($AllowPrerelease) {
            $args += "-prerelease"
        }

        $found = @(& $vswhere @args) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_) }
        if ($found.Count -gt 0) {
            return (Resolve-Path -LiteralPath ($found | Select-Object -First 1)).Path
        }
    }

    $pf = [Environment]::GetFolderPath("ProgramFiles")
    $pf86 = Get-ProgramFilesX86
    $candidates = @(
        (Join-Path $pf "Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf "Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf "Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf "Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf86 "Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf86 "Microsoft Visual Studio\2019\Professional\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf86 "Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe"),
        (Join-Path $pf86 "Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command "msbuild.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "MSBuild was not found. Install Visual Studio Build Tools or pass -MSBuildPath."
}

function Parse-MSBuildDiagnostics {
    param([Parameter(Mandatory = $true)][string[]]$Lines)

    $diagnostics = New-Object System.Collections.Generic.List[object]
    $filePattern = "^(?<file>.+?)\((?<line>\d+)(,(?<column>\d+))?\)\s*:\s*(?<level>error|warning)\s+(?<code>[A-Za-z]+\d+[A-Za-z0-9]*):\s*(?<message>.*)$"
    $plainPattern = "^\s*(?<level>error|warning)\s+(?<code>[A-Za-z]+\d+[A-Za-z0-9]*):\s*(?<message>.*)$"

    foreach ($line in $Lines) {
        $text = [string]$line
        $match = [regex]::Match($text, $filePattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success) {
            $diagnostics.Add([pscustomobject]@{
                level   = $match.Groups["level"].Value.ToLowerInvariant()
                code    = $match.Groups["code"].Value
                file    = $match.Groups["file"].Value.Trim()
                line    = [int]$match.Groups["line"].Value
                column  = if ($match.Groups["column"].Success) { [int]$match.Groups["column"].Value } else { $null }
                message = $match.Groups["message"].Value.Trim()
                raw     = $text
            }) | Out-Null
            continue
        }

        $match = [regex]::Match($text, $plainPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if ($match.Success) {
            $diagnostics.Add([pscustomobject]@{
                level   = $match.Groups["level"].Value.ToLowerInvariant()
                code    = $match.Groups["code"].Value
                file    = $null
                line    = $null
                column  = $null
                message = $match.Groups["message"].Value.Trim()
                raw     = $text
            }) | Out-Null
        }
    }

    return @($diagnostics)
}

$resolvedPath = (Resolve-Path -LiteralPath $Path).Path
$msbuild = Find-MSBuild -AllowPrerelease:$Prerelease

$targets = New-Object System.Collections.Generic.List[string]
if ($Restore -and $Target -ne "Restore") {
    $targets.Add("Restore") | Out-Null
}
$targets.Add($Target) | Out-Null

$arguments = New-Object System.Collections.Generic.List[string]
$arguments.Add($resolvedPath) | Out-Null
$arguments.Add("/t:$($targets -join ';')") | Out-Null
$arguments.Add("/p:Configuration=$Configuration") | Out-Null
if (-not [string]::IsNullOrWhiteSpace($Platform)) {
    $arguments.Add("/p:Platform=$Platform") | Out-Null
}
$arguments.Add("/m") | Out-Null
$arguments.Add("/nologo") | Out-Null
$arguments.Add("/v:$Verbosity") | Out-Null
$arguments.Add("/clp:Summary;Verbosity=$Verbosity") | Out-Null
if ($BinaryLog) {
    $arguments.Add("/bl") | Out-Null
}

$started = Get-Date
$rawOutput = @(& $msbuild @arguments 2>&1)
$exitCode = $LASTEXITCODE
$finished = Get-Date
$lines = @($rawOutput | ForEach-Object { $_.ToString() })

if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
    $logDirectory = Split-Path -Parent $LogPath
    if (-not [string]::IsNullOrWhiteSpace($logDirectory) -and -not (Test-Path -LiteralPath $logDirectory)) {
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    }
    $lines | Set-Content -LiteralPath $LogPath -Encoding UTF8
}

$diagnostics = @(Parse-MSBuildDiagnostics -Lines $lines)
$errors = @($diagnostics | Where-Object { $_.level -eq "error" })
$warnings = @($diagnostics | Where-Object { $_.level -eq "warning" })

$result = [pscustomobject]@{
    tool        = "MSBuild"
    msbuildPath = $msbuild
    path        = $resolvedPath
    arguments   = @($arguments)
    exitCode    = $exitCode
    succeeded   = ($exitCode -eq 0)
    started     = $started.ToString("o")
    finished    = $finished.ToString("o")
    durationMs  = [int](($finished - $started).TotalMilliseconds)
    errorCount  = $errors.Count
    warningCount = $warnings.Count
    diagnostics = $diagnostics
    logPath     = if ([string]::IsNullOrWhiteSpace($LogPath)) { $null } else { $LogPath }
    tail        = @($lines | Select-Object -Last 80)
}

$result | ConvertTo-Json -Depth 8

if (-not $NoExitCode) {
    exit $exitCode
}
