<#
.SYNOPSIS
Locate Visual Studio installations and common command-line tools.

.DESCRIPTION
Uses vswhere when available and falls back to the Visual Studio Setup
Configuration COM API. Emits JSON by default for agent-friendly parsing.
#>

[CmdletBinding()]
param(
    [switch]$Latest,
    [switch]$Prerelease,
    [switch]$Legacy,
    [switch]$RequireMsBuild,
    [ValidateSet("json", "table", "path")]
    [string]$Format = "json"
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

    $pf = [Environment]::GetFolderPath("ProgramFiles")
    if (-not [string]::IsNullOrWhiteSpace($pf)) {
        $candidates += (Join-Path $pf "Microsoft Visual Studio\Installer\vswhere.exe")
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

function Find-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$RelativePaths
    )

    foreach ($relative in $RelativePaths) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Convert-ToInstanceObject {
    param(
        [Parameter(Mandatory = $true)]$Instance,
        [Parameter(Mandatory = $true)][string]$Source
    )

    $path = [string]$Instance.installationPath
    $devenvPath = $null
    $msbuildPath = $null

    if (-not [string]::IsNullOrWhiteSpace($path)) {
        $devenvPath = Find-ChildPath -Root $path -RelativePaths @(
            "Common7\IDE\devenv.exe"
        )

        $msbuildPath = Find-ChildPath -Root $path -RelativePaths @(
            "MSBuild\Current\Bin\MSBuild.exe",
            "MSBuild\Current\Bin\amd64\MSBuild.exe",
            "MSBuild\15.0\Bin\MSBuild.exe",
            "MSBuild\15.0\Bin\amd64\MSBuild.exe"
        )
    }

    [pscustomobject]@{
        source              = $Source
        instanceId          = [string]$Instance.instanceId
        displayName         = [string]$Instance.displayName
        installationVersion = [string]$Instance.installationVersion
        installationPath    = $path
        productId           = [string]$Instance.productId
        channelId           = [string]$Instance.channelId
        isPrerelease        = [bool]($Instance.isPrerelease)
        productPath         = [string]$Instance.productPath
        devenvPath          = $devenvPath
        msbuildPath         = $msbuildPath
    }
}

function Get-VsInstancesFromVsWhere {
    $vswhere = Find-VsWhere
    if (-not $vswhere) {
        return @()
    }

    $args = @("-products", "*", "-format", "json", "-utf8")
    if ($Latest) {
        $args += "-latest"
    } else {
        $args += "-all"
    }
    if ($Prerelease) {
        $args += "-prerelease"
    }
    if ($Legacy) {
        $args += "-legacy"
    }
    if ($RequireMsBuild) {
        $args += @("-requires", "Microsoft.Component.MSBuild")
    }

    $json = & $vswhere @args
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($json -join ""))) {
        return @()
    }

    $instances = $json | ConvertFrom-Json
    if ($null -eq $instances) {
        return @()
    }
    if ($instances -isnot [System.Array]) {
        $instances = @($instances)
    }

    return @($instances | ForEach-Object { Convert-ToInstanceObject -Instance $_ -Source "vswhere" })
}

function New-SetupConfiguration {
    $clsid = [Guid]"177F0C4A-1CD3-4DE7-A32C-71DBBB9FA36D"
    $type = [Type]::GetTypeFromCLSID($clsid)
    if (-not $type) {
        return $null
    }
    return [Activator]::CreateInstance($type)
}

function Get-VsInstancesFromSetupConfiguration {
    try {
        $setup = New-SetupConfiguration
        if (-not $setup) {
            return @()
        }

        $enum = $setup.EnumInstances()
        $items = New-Object System.Collections.Generic.List[object]

        while ($true) {
            $fetched = 0
            $instance = $null
            $enum.Next(1, [ref]$instance, [ref]$fetched) | Out-Null
            if ($fetched -lt 1 -or -not $instance) {
                break
            }

            $displayName = $null
            try { $displayName = $instance.GetDisplayName(1033) } catch { }

            $path = $null
            try { $path = $instance.GetInstallationPath() } catch { }

            $version = $null
            try { $version = $instance.GetInstallationVersion() } catch { }

            $id = $null
            try { $id = $instance.GetInstanceId() } catch { }

            $items.Add([pscustomobject]@{
                instanceId          = $id
                displayName         = $displayName
                installationVersion = $version
                installationPath    = $path
                productId           = $null
                channelId           = $null
                isPrerelease        = $false
                productPath         = if ($path) { Join-Path $path "Common7\IDE\devenv.exe" } else { $null }
            }) | Out-Null
        }

        $objects = @($items | ForEach-Object { Convert-ToInstanceObject -Instance $_ -Source "setup-configuration" })
        if ($RequireMsBuild) {
            $objects = @($objects | Where-Object { -not [string]::IsNullOrWhiteSpace($_.msbuildPath) })
        }
        if ($Latest) {
            $objects = @($objects | Sort-Object installationVersion -Descending | Select-Object -First 1)
        }

        return $objects
    } catch {
        return @()
    }
}

$instances = @(Get-VsInstancesFromVsWhere)
if ($instances.Count -eq 0) {
    $instances = @(Get-VsInstancesFromSetupConfiguration)
}

if ($instances.Count -eq 0) {
    Write-Error "No Visual Studio instances were found by vswhere or Setup Configuration COM."
    exit 1
}

switch ($Format) {
    "json" {
        $instances | ConvertTo-Json -Depth 6
    }
    "table" {
        $instances | Sort-Object installationVersion -Descending | Format-Table displayName, installationVersion, installationPath, msbuildPath, devenvPath -AutoSize
    }
    "path" {
        $selected = $instances | Sort-Object installationVersion -Descending | Select-Object -First 1
        if ($RequireMsBuild -and $selected.msbuildPath) {
            $selected.msbuildPath
        } elseif ($selected.devenvPath) {
            $selected.devenvPath
        } else {
            $selected.installationPath
        }
    }
}
