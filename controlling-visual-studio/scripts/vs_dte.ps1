<#
.SYNOPSIS
Interact with running Visual Studio instances through EnvDTE/DTE COM automation.

.DESCRIPTION
Connects to Visual Studio DTE objects from the Running Object Table and exposes
common IDE operations without screen scraping: status, projects, build, debugger,
breakpoints, Output Window, Error List, commands, and documents.

Functional modules live in scripts/modules/ and are dot-sourced at startup.
#>

[CmdletBinding()]
param(
    [ValidateSet(
        "list-instances",
        "status",
        "list-projects",
        "build",
        "clean",
        "debug-state",
        "call-stack",
        "locals",
        "eval",
        "start-debugging",
        "stop-debugging",
        "break",
        "continue",
        "step-into",
        "step-over",
        "step-out",
        "list-breakpoints",
        "add-breakpoint",
        "remove-breakpoints",
        "output",
        "output-panes",
        "clear-output",
        "error-list",
        "task-list",
        "list-commands",
        "attach-process",
        "execute-command",
        "open-document",
        "save-all",
        "list-threads",
        "set-active-thread",
        "list-modules",
        "get-active-config",
        "set-active-config",
        "get-startup-projects",
        "set-startup-project",
        "get-text",
        "replace-text"
    )]
    [string]$Action = "status",

    [string]$ProgId,
    [string]$Solution,
    [int]$InstancePid,

    [string]$File,
    [int]$Line,
    [string]$Condition,
    [switch]$All,

    [string]$Pane = "Build",
    [int]$Tail = 200,

    [string]$Command,
    [string]$CommandArgs = "",
    [string]$CommandFilter,
    [int]$TargetPid,
    [string]$Engine,
    [string]$Expression,

    [int]$ThreadId,
    [string]$ConfigName,
    [string]$ConfigPlatform,
    [string]$Project,
    [string]$Find,
    [string]$Replace,
    [switch]$Regex,

    [switch]$Wait
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

# Load functional modules
. "$PSScriptRoot/modules/DteCore.ps1"
. "$PSScriptRoot/modules/DteSolution.ps1"
. "$PSScriptRoot/modules/DteOutput.ps1"
. "$PSScriptRoot/modules/DteDebugger.ps1"
. "$PSScriptRoot/modules/DteText.ps1"

# Early exit: list-instances does not require a selected instance
if ($Action -eq "list-instances") {
    Write-Json -Value @((Get-DteInstances) | ForEach-Object { $_.meta })
    exit 0
}

# Select a running DTE instance (ROT gives us metadata with PID/progId/solution)
$selected = Select-DteInstance

# Load EnvDTE type assemblies so we can cast to EnvDTE80.DTE2.
# Without this, ToolWindows/OutputWindow/ErrorList are unreachable via late binding.
Ensure-EnvDteTypes

# Get a DTE object cast to EnvDTE80.DTE2 (not raw IDispatch).
# This is required for ToolWindows, ErrorList, OutputWindow access.
$dte = Get-MarshalDte -ProgId $selected.meta.progId

# Build parameter hashtable for domain dispatch
$dispatchParams = @{
    Action    = $Action
    Selected  = $selected
    Dte       = $dte
}

# Dispatch to domain modules in priority order.
# Each Invoke-Dte* function writes JSON directly to stdout.
# It sets $script:ActionHandled = $true if it matched, so we don't need return values.

$script:ActionHandled = $false

Invoke-DteSolution @dispatchParams -Wait:$Wait -ConfigName $ConfigName -ConfigPlatform $ConfigPlatform -Project $Project
if ($script:ActionHandled) { exit 0 }

Invoke-DteOutput @dispatchParams -Pane $Pane -Tail $Tail
if ($script:ActionHandled) { exit 0 }

Invoke-DteDebugger @dispatchParams -File $File -Line $Line -Condition $Condition -All:$All -TargetPid $TargetPid -Engine $Engine -Expression $Expression -ThreadId $ThreadId -Wait:$Wait
if ($script:ActionHandled) { exit 0 }

Invoke-DteText @dispatchParams -File $File -Tail $Tail -Find $Find -Replace $Replace -Regex:$Regex
if ($script:ActionHandled) { exit 0 }

# Generic DTE commands (not domain-specific)
switch ($Action) {
    "list-commands" {
        $commands = New-Object System.Collections.Generic.List[object]
        foreach ($item in $dte.Commands) {
            $name = [string](Get-Value -Object $item -Name "Name")
            if ([string]::IsNullOrWhiteSpace($CommandFilter) -or $name -like "*$CommandFilter*") {
                $commands.Add([pscustomobject]@{
                    name = $name
                    guid = [string](Get-Value -Object $item -Name "Guid")
                    id   = Get-Value -Object $item -Name "ID"
                }) | Out-Null
            }
        }
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            filter   = $CommandFilter
            commands = $commands.ToArray()
        })
    }
    "execute-command" {
        if ([string]::IsNullOrWhiteSpace($Command)) {
            throw "-Command is required for execute-command."
        }
        $dte.ExecuteCommand($Command, $CommandArgs)
        Write-Json -Value ([pscustomobject]@{
            instance    = $selected.meta
            action      = "execute-command"
            command     = $Command
            commandArgs = $CommandArgs
        })
    }
    "open-document" {
        if ([string]::IsNullOrWhiteSpace($File)) {
            throw "-File is required for open-document."
        }
        $resolvedFile = (Resolve-Path -LiteralPath $File).Path
        $window = $dte.ItemOperations.OpenFile($resolvedFile)
        Write-Json -Value ([pscustomobject]@{
            instance      = $selected.meta
            action        = "open-document"
            file          = $resolvedFile
            windowCaption = [string](Get-Value -Object $window -Name "Caption")
        })
    }
    "save-all" {
        $dte.ExecuteCommand("File.SaveAll", "")
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action   = "save-all"
        })
    }
    default {
        throw "Unknown action: $Action"
    }
}
