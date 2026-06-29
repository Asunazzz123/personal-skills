<#
.SYNOPSIS
Audit Visual Studio .NET project files without modifying them.

.DESCRIPTION
Reads a .sln or .csproj file and emits JSON with project style, target
frameworks, platform settings, package references, project references,
assembly references, HintPath resolution, packages.config entries, and
conditional PropertyGroup metadata. The script is read-only and intended for
early build/configuration triage.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-XmlChildText {
    param(
        [Parameter(Mandatory = $true)]$Node,
        [Parameter(Mandatory = $true)][string]$Name
    )

    foreach ($child in @($Node.ChildNodes)) {
        if ($child.NodeType -eq [System.Xml.XmlNodeType]::Element -and $child.LocalName -eq $Name) {
            return [string]$child.InnerText
        }
    }

    return $null
}

function Get-XmlElements {
    param(
        [Parameter(Mandatory = $true)][xml]$Xml,
        [Parameter(Mandatory = $true)][string]$Name
    )

    return @($Xml.GetElementsByTagName($Name))
}

function Convert-ToAbsolutePath {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDirectory,
        [Parameter(Mandatory = $true)][string]$Value,
        [string]$SolutionDirectory
    )

    $expanded = $Value.Trim()
    $expanded = $expanded.Replace('$(MSBuildProjectDirectory)', $BaseDirectory)
    $expanded = $expanded.Replace('$(ProjectDir)', ($BaseDirectory.TrimEnd('\') + '\'))
    $expanded = $expanded.Replace('$(MSBuildThisFileDirectory)', ($BaseDirectory.TrimEnd('\') + '\'))

    if (-not [string]::IsNullOrWhiteSpace($SolutionDirectory)) {
        $expanded = $expanded.Replace('$(SolutionDir)', ($SolutionDirectory.TrimEnd('\') + '\'))
    }

    if ($expanded -match '\$\([^)]+\)') {
        return [pscustomobject]@{
            raw          = $Value
            resolvedPath = $null
            exists       = $null
            unresolved   = $true
        }
    }

    if ([System.IO.Path]::IsPathRooted($expanded)) {
        $candidate = $expanded
    } else {
        $candidate = Join-Path $BaseDirectory $expanded
    }

    $full = [System.IO.Path]::GetFullPath($candidate)
    return [pscustomobject]@{
        raw          = $Value
        resolvedPath = $full
        exists       = (Test-Path -LiteralPath $full)
        unresolved   = $false
    }
}

function Split-FrameworkList {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return @()
    }

    return @($Value -split ';' | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Read-PackagesConfig {
    param([Parameter(Mandatory = $true)][string]$ProjectDirectory)

    $path = Join-Path $ProjectDirectory "packages.config"
    if (-not (Test-Path -LiteralPath $path)) {
        return [pscustomobject]@{
            path     = $path
            exists   = $false
            packages = @()
        }
    }

    [xml]$xml = Get-Content -LiteralPath $path -Raw
    $packages = @($xml.GetElementsByTagName("package") | ForEach-Object {
        [pscustomobject]@{
            id              = $_.GetAttribute("id")
            version         = $_.GetAttribute("version")
            targetFramework = $_.GetAttribute("targetFramework")
        }
    })

    return [pscustomobject]@{
        path     = (Resolve-Path -LiteralPath $path).Path
        exists   = $true
        packages = $packages
    }
}

function Read-CSharpProjectsFromSolution {
    param([Parameter(Mandatory = $true)][string]$SolutionPath)

    $solutionDirectory = Split-Path -Parent $SolutionPath
    $projectPattern = '^Project\("\{(?<typeGuid>[^}]+)\}"\)\s*=\s*"(?<name>[^"]+)",\s*"(?<relativePath>[^"]+\.csproj)",\s*"\{(?<projectGuid>[^}]+)\}"'

    return @(Get-Content -LiteralPath $SolutionPath | ForEach-Object {
        $match = [regex]::Match([string]$_, $projectPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if (-not $match.Success) {
            return
        }

        $relativePath = $match.Groups["relativePath"].Value
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $solutionDirectory $relativePath))

        [pscustomobject]@{
            name         = $match.Groups["name"].Value
            relativePath = $relativePath
            path         = $fullPath
            exists       = (Test-Path -LiteralPath $fullPath)
            projectGuid  = $match.Groups["projectGuid"].Value
        }
    })
}

function Audit-CSharpProject {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectPath,
        [string]$SolutionDirectory
    )

    $resolvedProjectPath = (Resolve-Path -LiteralPath $ProjectPath).Path
    $projectDirectory = Split-Path -Parent $resolvedProjectPath

    [xml]$xml = Get-Content -LiteralPath $resolvedProjectPath -Raw
    $projectNode = $xml.Project
    $sdkAttribute = if ($projectNode) { $projectNode.GetAttribute("Sdk") } else { $null }
    $style = if (-not [string]::IsNullOrWhiteSpace($sdkAttribute)) { "sdk-style" } else { "legacy-or-non-sdk" }

    $propertyGroups = @(Get-XmlElements -Xml $xml -Name "PropertyGroup" | ForEach-Object {
        $condition = $_.GetAttribute("Condition")
        [pscustomobject]@{
            condition              = if ([string]::IsNullOrWhiteSpace($condition)) { $null } else { $condition }
            targetFramework        = Get-XmlChildText -Node $_ -Name "TargetFramework"
            targetFrameworks       = @(Split-FrameworkList (Get-XmlChildText -Node $_ -Name "TargetFrameworks"))
            targetFrameworkVersion = Get-XmlChildText -Node $_ -Name "TargetFrameworkVersion"
            outputType             = Get-XmlChildText -Node $_ -Name "OutputType"
            useWindowsForms        = Get-XmlChildText -Node $_ -Name "UseWindowsForms"
            useWpf                 = Get-XmlChildText -Node $_ -Name "UseWPF"
            platformTarget         = Get-XmlChildText -Node $_ -Name "PlatformTarget"
            prefer32Bit            = Get-XmlChildText -Node $_ -Name "Prefer32Bit"
            runtimeIdentifier      = Get-XmlChildText -Node $_ -Name "RuntimeIdentifier"
            runtimeIdentifiers     = @(Split-FrameworkList (Get-XmlChildText -Node $_ -Name "RuntimeIdentifiers"))
        }
    })

    $packageReferences = @(Get-XmlElements -Xml $xml -Name "PackageReference" | ForEach-Object {
        $version = $_.GetAttribute("Version")
        if ([string]::IsNullOrWhiteSpace($version)) {
            $version = Get-XmlChildText -Node $_ -Name "Version"
        }

        [pscustomobject]@{
            include   = $_.GetAttribute("Include")
            update    = if ([string]::IsNullOrWhiteSpace($_.GetAttribute("Update"))) { $null } else { $_.GetAttribute("Update") }
            version   = if ([string]::IsNullOrWhiteSpace($version)) { $null } else { $version }
            condition = if ([string]::IsNullOrWhiteSpace($_.GetAttribute("Condition"))) { $null } else { $_.GetAttribute("Condition") }
        }
    })

    $projectReferences = @(Get-XmlElements -Xml $xml -Name "ProjectReference" | ForEach-Object {
        $include = $_.GetAttribute("Include")
        $resolved = Convert-ToAbsolutePath -BaseDirectory $projectDirectory -Value $include -SolutionDirectory $SolutionDirectory
        [pscustomobject]@{
            include      = $include
            project      = Get-XmlChildText -Node $_ -Name "Project"
            name         = Get-XmlChildText -Node $_ -Name "Name"
            resolvedPath = $resolved.resolvedPath
            exists       = $resolved.exists
            unresolved   = $resolved.unresolved
        }
    })

    $references = @(Get-XmlElements -Xml $xml -Name "Reference" | ForEach-Object {
        $include = $_.GetAttribute("Include")
        $hintPath = Get-XmlChildText -Node $_ -Name "HintPath"
        $hint = if ([string]::IsNullOrWhiteSpace($hintPath)) {
            $null
        } else {
            Convert-ToAbsolutePath -BaseDirectory $projectDirectory -Value $hintPath -SolutionDirectory $SolutionDirectory
        }

        [pscustomobject]@{
            include             = $include
            hintPath            = if ([string]::IsNullOrWhiteSpace($hintPath)) { $null } else { $hintPath }
            resolvedHintPath    = if ($hint) { $hint.resolvedPath } else { $null }
            hintPathExists      = if ($hint) { $hint.exists } else { $null }
            hintPathUnresolved  = if ($hint) { $hint.unresolved } else { $false }
            specificVersion     = Get-XmlChildText -Node $_ -Name "SpecificVersion"
            private             = Get-XmlChildText -Node $_ -Name "Private"
            embedInteropTypes   = Get-XmlChildText -Node $_ -Name "EmbedInteropTypes"
        }
    })

    $missingHintPaths = @($references | Where-Object { $_.hintPath -and $_.hintPathExists -eq $false })
    $unresolvedHintPaths = @($references | Where-Object { $_.hintPath -and $_.hintPathUnresolved -eq $true })
    $missingProjectReferences = @($projectReferences | Where-Object { $_.exists -eq $false })

    return [pscustomobject]@{
        path                     = $resolvedProjectPath
        directory                = $projectDirectory
        projectStyle             = $style
        sdk                      = if ([string]::IsNullOrWhiteSpace($sdkAttribute)) { $null } else { $sdkAttribute }
        propertyGroups           = $propertyGroups
        targetFrameworks         = @($propertyGroups | ForEach-Object {
            if ($_.targetFramework) { $_.targetFramework }
            $_.targetFrameworks
            if ($_.targetFrameworkVersion) { $_.targetFrameworkVersion }
        } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
        packageReferences        = $packageReferences
        packagesConfig           = Read-PackagesConfig -ProjectDirectory $projectDirectory
        projectReferences        = $projectReferences
        assemblyReferences       = $references
        missingHintPaths         = $missingHintPaths
        unresolvedHintPaths      = $unresolvedHintPaths
        missingProjectReferences = $missingProjectReferences
    }
}

$resolvedInput = (Resolve-Path -LiteralPath $Path).Path
$extension = [System.IO.Path]::GetExtension($resolvedInput)

switch -Regex ($extension) {
    '^\.csproj$' {
        $projectAudit = Audit-CSharpProject -ProjectPath $resolvedInput
        [pscustomobject]@{
            inputType = "csproj"
            path      = $resolvedInput
            projects  = @($projectAudit)
        } | ConvertTo-Json -Depth 12
    }
    '^\.slnx?$' {
        $solutionDirectory = Split-Path -Parent $resolvedInput
        $solutionProjects = @(Read-CSharpProjectsFromSolution -SolutionPath $resolvedInput)
        $audits = @($solutionProjects | ForEach-Object {
            if ($_.exists) {
                Audit-CSharpProject -ProjectPath $_.path -SolutionDirectory $solutionDirectory
            }
        })

        [pscustomobject]@{
            inputType        = "solution"
            path             = $resolvedInput
            solutionProjects = $solutionProjects
            projects         = $audits
        } | ConvertTo-Json -Depth 12
    }
    default {
        throw "Unsupported input type '$extension'. Pass a .sln, .slnx, or .csproj file."
    }
}
