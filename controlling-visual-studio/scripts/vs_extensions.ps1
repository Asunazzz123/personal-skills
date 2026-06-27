<#
.SYNOPSIS
Manage Visual Studio extensions: list installed, install from .vsix, or uninstall.

.DESCRIPTION
Scans Visual Studio extension directories for installed extensions and provides
install/uninstall operations through VSIXInstaller.exe. Emits JSON by default
for agent-friendly parsing.
#>

[CmdletBinding()]
param(
    [ValidateSet("list-extensions", "install-extension", "uninstall-extension")]
    [string]$Action = "list-extensions",

    [string]$Path,
    [string]$VSIXId,
    [string]$Filter,
    [string]$VSIXInstallerPath,

    [ValidateSet("json", "table")]
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

function Find-VSIXInstaller {
    if (-not [string]::IsNullOrWhiteSpace($VSIXInstallerPath)) {
        if (-not (Test-Path -LiteralPath $VSIXInstallerPath)) {
            throw "VSIXInstallerPath does not exist: $VSIXInstallerPath"
        }
        return (Resolve-Path -LiteralPath $VSIXInstallerPath).Path
    }

    $vswhere = Find-VsWhere
    if ($vswhere) {
        $found = @(& $vswhere -latest -products * -property productPath 2>$null | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        if ($found.Count -gt 0) {
            $ideDir = Split-Path -Parent ($found | Select-Object -First 1)
            $installer = Join-Path $ideDir "VSIXInstaller.exe"
            if (Test-Path -LiteralPath $installer) {
                return (Resolve-Path -LiteralPath $installer).Path
            }
        }
    }

    $pf = [Environment]::GetFolderPath("ProgramFiles")
    $pf86 = Get-ProgramFilesX86
    $candidates = @(
        (Join-Path $pf "Microsoft Visual Studio\Installer\VSIXInstaller.exe"),
        (Join-Path $pf86 "Microsoft Visual Studio\Installer\VSIXInstaller.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command "VSIXInstaller.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "VSIXInstaller.exe was not found. Install Visual Studio or pass -VSIXInstallerPath."
}

function Find-ExtensionDirectories {
    $dirs = New-Object System.Collections.Generic.List[string]

    $pf = [Environment]::GetFolderPath("ProgramFiles")
    $pf86 = Get-ProgramFilesX86
    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")

    # VS 2022 per-user extensions
    if (-not [string]::IsNullOrWhiteSpace($localAppData)) {
        $userRoot = Join-Path $localAppData "Microsoft\VisualStudio"
        if (Test-Path -LiteralPath $userRoot) {
            foreach ($dir in (Get-ChildItem -LiteralPath $userRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "^17\.\d+" })) {
                $extDir = Join-Path $dir.FullName "Extensions"
                if (Test-Path -LiteralPath $extDir) {
                    $dirs.Add($extDir) | Out-Null
                }
            }
        }
    }

    # VS 2022 global extensions
    foreach ($edition in @("Enterprise", "Professional", "Community", "BuildTools")) {
        $globalExt = Join-Path $pf "Microsoft Visual Studio\2022\$edition\Common7\IDE\Extensions"
        if (Test-Path -LiteralPath $globalExt) {
            $dirs.Add($globalExt) | Out-Null
        }
    }

    # VS 2019 global extensions
    foreach ($edition in @("Enterprise", "Professional", "Community", "BuildTools")) {
        $globalExt = Join-Path $pf86 "Microsoft Visual Studio\2019\$edition\Common7\IDE\Extensions"
        if (Test-Path -LiteralPath $globalExt) {
            $dirs.Add($globalExt) | Out-Null
        }
    }

    return $dirs.ToArray()
}

function Parse-VsixManifest {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        return $null
    }

    try {
        [xml]$xml = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8

        $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
        $ns.AddNamespace("v", "http://schemas.microsoft.com/developer/vsx-schema/2011")

        $identifier = $xml.SelectSingleNode("//v:Identifier", $ns)
        $metadata = $xml.SelectSingleNode("//v:Metadata", $ns)

        $vsixId = if ($identifier) { $identifier.GetAttribute("Id") } else { $null }
        $version = if ($identifier) { $identifier.GetAttribute("Version") } else { $null }
        $displayName = if ($metadata) { $metadata.SelectSingleNode("//v:DisplayName", $ns).'#text' } else { $null }
        $description = if ($metadata) { $metadata.SelectSingleNode("//v:Description", $ns).'#text' } else { $null }
        $publisher = if ($identifier) { $identifier.SelectSingleNode("//v:Publisher", $ns).'#text' } else { $null }

        if ([string]::IsNullOrWhiteSpace($vsixId)) {
            return $null
        }

        return [pscustomobject]@{
            vsixId      = $vsixId
            version     = $version
            displayName = $displayName
            description = if ($description) { $description.Substring(0, [Math]::Min($description.Length, 200)) } else { $null }
            publisher   = $publisher
        }
    } catch {
        return $null
    }
}

function Get-InstalledExtensions {
    $extensions = New-Object System.Collections.Generic.List[object]
    $dirs = Find-ExtensionDirectories
    $seen = @{}

    foreach ($dir in $dirs) {
        foreach ($subDir in (Get-ChildItem -LiteralPath $dir -Directory -ErrorAction SilentlyContinue)) {
            $manifest = Join-Path $subDir.FullName "extension.vsixmanifest"
            if (-not (Test-Path -LiteralPath $manifest)) {
                continue
            }

            $parsed = Parse-VsixManifest -ManifestPath $manifest
            if (-not $parsed) {
                continue
            }

            if ($seen.ContainsKey($parsed.vsixId)) {
                continue
            }
            $seen[$parsed.vsixId] = $true

            if (-not [string]::IsNullOrWhiteSpace($Filter) -and
                $parsed.vsixId -notlike "*$Filter*" -and
                ($parsed.displayName -eq $null -or $parsed.displayName -notlike "*$Filter*")) {
                continue
            }

            $extensions.Add([pscustomobject]@{
                vsixId      = $parsed.vsixId
                version     = $parsed.version
                displayName = $parsed.displayName
                description = $parsed.description
                publisher   = $parsed.publisher
                installPath = $subDir.FullName
                source      = if ($dir -like "*LocalApplicationData*") { "per-user" } else { "global" }
            }) | Out-Null
        }
    }

    return $extensions.ToArray()
}

switch ($Action) {
    "list-extensions" {
        $extensions = @(Get-InstalledExtensions)
        $result = [pscustomobject]@{
            action     = "list-extensions"
            count      = $extensions.Count
            extensions = $extensions
        }
        if ($Format -eq "json") {
            $result | ConvertTo-Json -Depth 8
        } else {
            $extensions | Format-Table vsixId, version, displayName, publisher, source -AutoSize
        }
    }
    "install-extension" {
        if ([string]::IsNullOrWhiteSpace($Path)) {
            throw "-Path is required for install-extension (path to .vsix file)."
        }
        $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
        $installer = Find-VSIXInstaller
        $output = & $installer /quiet $resolvedPath 2>&1
        $exitCode = $LASTEXITCODE
        $result = [pscustomobject]@{
            action      = "install-extension"
            vsixPath    = $resolvedPath
            installer   = $installer
            exitCode    = $exitCode
            succeeded   = ($exitCode -eq 0)
            output      = @($output | ForEach-Object { $_.ToString() })
        }
        if ($Format -eq "json") {
            $result | ConvertTo-Json -Depth 6
        } else {
            $result
        }
        exit $exitCode
    }
    "uninstall-extension" {
        if ([string]::IsNullOrWhiteSpace($VSIXId)) {
            throw "-VSIXId is required for uninstall-extension."
        }
        $installer = Find-VSIXInstaller
        $output = & $installer /quiet "/uninstall:$VSIXId" 2>&1
        $exitCode = $LASTEXITCODE
        $result = [pscustomobject]@{
            action    = "uninstall-extension"
            vsixId    = $VSIXId
            installer = $installer
            exitCode  = $exitCode
            succeeded = ($exitCode -eq 0)
            output    = @($output | ForEach-Object { $_.ToString() })
        }
        if ($Format -eq "json") {
            $result | ConvertTo-Json -Depth 6
        } else {
            $result
        }
        exit $exitCode
    }
}
