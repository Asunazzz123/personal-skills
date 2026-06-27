<#
.SYNOPSIS
Solution, project, build, and configuration management functions.
#>

function Get-Status {
    param($Selected)

    $dte = $Selected.dte
    $solution = $dte.Solution
    $build = $solution.SolutionBuild
    $activeConfig = $null
    try { $activeConfig = $build.ActiveConfiguration } catch { }

    $activeDocument = $null
    try {
        if ($dte.ActiveDocument) {
            $activeDocument = [pscustomobject]@{
                name     = [string]$dte.ActiveDocument.Name
                fullName = [string]$dte.ActiveDocument.FullName
                saved    = [bool]$dte.ActiveDocument.Saved
            }
        }
    } catch {
    }

    [pscustomobject]@{
        instance = $Selected.meta
        solution = [pscustomobject]@{
            isOpen   = [bool]$solution.IsOpen
            fullName = [string]$solution.FullName
            count    = [int]$solution.Count
        }
        build = [pscustomobject]@{
            activeConfiguration = if ($activeConfig) { [string]$activeConfig.Name } else { $null }
            activePlatform      = if ($activeConfig) { [string](Get-Value -Object $activeConfig -Name "PlatformName") } else { $null }
            buildState          = [string](Get-Value -Object $build -Name "BuildState")
            lastBuildInfo       = Get-Value -Object $build -Name "LastBuildInfo"
            startupProjects     = @(Get-Value -Object $build -Name "StartupProjects")
        }
        debugger = [pscustomobject]@{
            currentMode = Get-CurrentDebugMode -Dte $dte
            lastBreakReason = [string](Get-Value -Object $dte.Debugger -Name "LastBreakReason")
        }
        activeDocument = $activeDocument
    }
}

function Get-ProjectList {
    param($Projects)

    $result = New-Object System.Collections.Generic.List[object]

    foreach ($project in $Projects) {
        if (-not $project) {
            continue
        }

        $result.Add([pscustomobject]@{
            name       = [string](Get-Value -Object $project -Name "Name")
            kind       = [string](Get-Value -Object $project -Name "Kind")
            fileName   = [string](Get-Value -Object $project -Name "FileName")
            fullName   = [string](Get-Value -Object $project -Name "FullName")
            uniqueName = [string](Get-Value -Object $project -Name "UniqueName")
        }) | Out-Null

        try {
            foreach ($item in $project.ProjectItems) {
                $subProject = Get-Value -Object $item -Name "SubProject"
                if ($subProject) {
                    foreach ($nested in @(Get-ProjectList -Projects @($subProject))) {
                        $result.Add($nested) | Out-Null
                    }
                }
            }
        } catch {
        }
    }

    return $result.ToArray()
}

function Get-ConfigurationList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    try {
        foreach ($config in $Dte.Solution.SolutionBuild.SolutionConfigurations) {
            $platforms = New-Object System.Collections.Generic.List[object]
            try {
                foreach ($ctx in $config.SolutionContexts) {
                    $platforms.Add([pscustomobject]@{
                        projectName  = [string](Get-Value -Object $ctx -Name "ProjectName")
                        platformName = [string](Get-Value -Object $ctx -Name "PlatformName")
                        shouldBuild  = [bool](Get-Value -Object $ctx -Name "ShouldBuild")
                        outputPath   = [string](Get-Value -Object $ctx -Name "OutputPath")
                    }) | Out-Null
                }
            } catch {
            }
            $items.Add([pscustomobject]@{
                name         = [string](Get-Value -Object $config -Name "Name")
                platformName = [string](Get-Value -Object $config -Name "PlatformName")
                contexts     = $platforms.ToArray()
            }) | Out-Null
        }
    } catch {
        throw "Configuration listing requires an open solution."
    }

    return $items.ToArray()
}

function Invoke-DteSolution {
    param(
        [string]$Action,
        $Selected,
        $Dte,
        [switch]$Wait,
        [string]$ConfigName,
        [string]$ConfigPlatform,
        [string]$Project
    )

    switch ($Action) {
        "status" {
            Write-Json -Value (Get-Status -Selected $Selected)
            $script:ActionHandled = $true
            return
        }
        "list-projects" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                projects = @(Get-ProjectList -Projects $Dte.Solution.Projects)
            })
            $script:ActionHandled = $true
            return
        }
        "build" {
            $build = $Dte.Solution.SolutionBuild
            $build.Build($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance       = $Selected.meta
                action         = "build"
                waited         = $Wait.IsPresent
                buildState     = [string](Get-Value -Object $build -Name "BuildState")
                lastBuildInfo  = Get-Value -Object $build -Name "LastBuildInfo"
            })
            $script:ActionHandled = $true
            return
        }
        "clean" {
            $build = $Dte.Solution.SolutionBuild
            $build.Clean($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance       = $Selected.meta
                action         = "clean"
                waited         = $Wait.IsPresent
                buildState     = [string](Get-Value -Object $build -Name "BuildState")
                lastBuildInfo  = Get-Value -Object $build -Name "LastBuildInfo"
            })
            $script:ActionHandled = $true
            return
        }
        "get-active-config" {
            $activeConfig = $null
            try { $activeConfig = $Dte.Solution.SolutionBuild.ActiveConfiguration } catch { }
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                active   = [pscustomobject]@{
                    name         = if ($activeConfig) { [string]$activeConfig.Name } else { $null }
                    platformName = if ($activeConfig) { [string](Get-Value -Object $activeConfig -Name "PlatformName") } else { $null }
                }
                available = @(Get-ConfigurationList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "set-active-config" {
            if ([string]::IsNullOrWhiteSpace($ConfigName)) {
                throw "-ConfigName is required for set-active-config (e.g. 'Debug', 'Release')."
            }
            $targetConfig = $null
            foreach ($config in $Dte.Solution.SolutionBuild.SolutionConfigurations) {
                $name = [string](Get-Value -Object $config -Name "Name")
                if ([string]::Equals($name, $ConfigName, [StringComparison]::OrdinalIgnoreCase)) {
                    if ([string]::IsNullOrWhiteSpace($ConfigPlatform)) {
                        $targetConfig = $config
                        break
                    }
                    $platform = [string](Get-Value -Object $config -Name "PlatformName")
                    if ([string]::Equals($platform, $ConfigPlatform, [StringComparison]::OrdinalIgnoreCase)) {
                        $targetConfig = $config
                        break
                    }
                }
            }
            if (-not $targetConfig) {
                throw "Configuration '$ConfigName'$(if ($ConfigPlatform) { " with platform '$ConfigPlatform'" }) was not found."
            }
            $targetConfig.Activate()
            $activeConfig = $Dte.Solution.SolutionBuild.ActiveConfiguration
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                action   = "set-active-config"
                active   = [pscustomobject]@{
                    name         = [string]$activeConfig.Name
                    platformName = [string](Get-Value -Object $activeConfig -Name "PlatformName")
                }
            })
            $script:ActionHandled = $true
            return
        }
        "get-startup-projects" {
            Write-Json -Value ([pscustomobject]@{
                instance         = $Selected.meta
                startupProjects  = @(Get-Value -Object $Dte.Solution.SolutionBuild -Name "StartupProjects")
            })
            $script:ActionHandled = $true
            return
        }
        "set-startup-project" {
            if ([string]::IsNullOrWhiteSpace($Project)) {
                throw "-Project is required for set-startup-project (use the project's UniqueName)."
            }
            $Dte.Solution.SolutionBuild.StartupProjects = @($Project)
            Write-Json -Value ([pscustomobject]@{
                instance         = $Selected.meta
                action           = "set-startup-project"
                startupProjects  = @(Get-Value -Object $Dte.Solution.SolutionBuild -Name "StartupProjects")
            })
            $script:ActionHandled = $true
            return
        }
    }
}
