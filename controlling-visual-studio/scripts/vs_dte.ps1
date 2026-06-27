<#
.SYNOPSIS
Interact with running Visual Studio instances through EnvDTE/DTE COM automation.

.DESCRIPTION
Connects to Visual Studio DTE objects from the Running Object Table and exposes
common IDE operations without screen scraping: status, projects, build, debugger,
breakpoints, Output Window, Error List, commands, and documents.
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
        "error-list",
        "task-list",
        "list-commands",
        "attach-process",
        "execute-command",
        "open-document",
        "save-all"
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

    [switch]$Wait
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Ensure-RotType {
    if ("VisualStudioRot" -as [type]) {
        return
    }

    $source = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

public static class VisualStudioRot
{
    [DllImport("ole32.dll")]
    private static extern int GetRunningObjectTable(int reserved, out IRunningObjectTable prot);

    [DllImport("ole32.dll")]
    private static extern int CreateBindCtx(int reserved, out IBindCtx ppbc);

    public static Dictionary<string, object> GetObjects(string prefix)
    {
        var result = new Dictionary<string, object>();
        IRunningObjectTable rot;
        if (GetRunningObjectTable(0, out rot) != 0 || rot == null)
        {
            return result;
        }

        IEnumMoniker enumMoniker;
        rot.EnumRunning(out enumMoniker);
        enumMoniker.Reset();

        var monikers = new IMoniker[1];
        while (enumMoniker.Next(1, monikers, IntPtr.Zero) == 0)
        {
            IBindCtx bindCtx;
            if (CreateBindCtx(0, out bindCtx) != 0 || bindCtx == null)
            {
                continue;
            }

            string displayName = null;
            try
            {
                monikers[0].GetDisplayName(bindCtx, null, out displayName);
            }
            catch
            {
                displayName = null;
            }

            if (displayName == null)
            {
                continue;
            }

            if (prefix == null || displayName.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                object runningObject;
                try
                {
                    rot.GetObject(monikers[0], out runningObject);
                    result[displayName] = runningObject;
                }
                catch
                {
                }
            }
        }

        return result;
    }
}
'@

    Add-Type -TypeDefinition $source -Language CSharp
}

function Get-Value {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    try {
        return $Object.$Name
    } catch {
        return $null
    }
}

function Get-DebugModeName {
    param($Mode)

    switch ([int]$Mode) {
        1 { "design" }
        2 { "break" }
        3 { "run" }
        default { [string]$Mode }
    }
}

function Get-CurrentDebugMode {
    param($Dte)

    $debugger = Get-Value -Object $Dte -Name "Debugger"
    return Get-DebugModeName -Mode (Get-Value -Object $debugger -Name "CurrentMode")
}

function Get-RotPid {
    param([string]$RotName)

    $match = [regex]::Match($RotName, ":(?<pid>\d+)$")
    if ($match.Success) {
        return [int]$match.Groups["pid"].Value
    }
    return $null
}

function Convert-DteInstance {
    param(
        [Parameter(Mandatory = $true)][string]$RotName,
        [Parameter(Mandatory = $true)]$Dte
    )

    $solutionFullName = $null
    $solutionIsOpen = $false
    try {
        $solutionFullName = [string]$Dte.Solution.FullName
        $solutionIsOpen = [bool]$Dte.Solution.IsOpen
    } catch {
    }

    $prog = $null
    $match = [regex]::Match($RotName, "!(?<prog>VisualStudio\.DTE\.\d+\.\d+)")
    if ($match.Success) {
        $prog = $match.Groups["prog"].Value
    }

    [pscustomobject]@{
        rotName          = $RotName
        progId           = $prog
        processId        = Get-RotPid -RotName $RotName
        version          = [string](Get-Value -Object $Dte -Name "Version")
        edition          = [string](Get-Value -Object $Dte -Name "Edition")
        fullName         = [string](Get-Value -Object $Dte -Name "FullName")
        mode             = [string](Get-Value -Object $Dte -Name "Mode")
        solutionIsOpen   = $solutionIsOpen
        solutionFullName = $solutionFullName
    }
}

function Get-DteInstances {
    Ensure-RotType
    $instances = New-Object System.Collections.Generic.List[object]

    $running = [VisualStudioRot]::GetObjects("!VisualStudio.DTE.")
    foreach ($entry in $running.GetEnumerator()) {
        $instances.Add([pscustomobject]@{
            meta = Convert-DteInstance -RotName $entry.Key -Dte $entry.Value
            dte  = $entry.Value
        }) | Out-Null
    }

    if ($instances.Count -eq 0) {
        $progIds = @("VisualStudio.DTE.18.0", "VisualStudio.DTE.17.0", "VisualStudio.DTE.16.0", "VisualStudio.DTE.15.0")
        foreach ($id in $progIds) {
            try {
                $dte = [Runtime.InteropServices.Marshal]::GetActiveObject($id)
                if ($dte) {
                    $instances.Add([pscustomobject]@{
                        meta = Convert-DteInstance -RotName "legacy:$id" -Dte $dte
                        dte  = $dte
                    }) | Out-Null
                }
            } catch {
            }
        }
    }

    return @($instances.ToArray() | Sort-Object { $_.meta.version } -Descending)
}

function Select-DteInstance {
    $instances = @(Get-DteInstances)
    if ($instances.Count -eq 0) {
        throw "No running Visual Studio DTE instances were found."
    }

    if (-not [string]::IsNullOrWhiteSpace($ProgId)) {
        $instances = @($instances | Where-Object { $_.meta.progId -eq $ProgId -or $_.meta.rotName -like "*$ProgId*" })
    }

    if ($InstancePid -gt 0) {
        $instances = @($instances | Where-Object { $_.meta.processId -eq $InstancePid })
    }

    if (-not [string]::IsNullOrWhiteSpace($Solution)) {
        $solutionPath = $Solution
        try {
            $solutionPath = (Resolve-Path -LiteralPath $Solution).Path
        } catch {
        }
        $instances = @($instances | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_.meta.solutionFullName) -and
            [string]::Equals($_.meta.solutionFullName, $solutionPath, [StringComparison]::OrdinalIgnoreCase)
        })
    }

    if ($instances.Count -eq 0) {
        throw "No running Visual Studio DTE instance matched the supplied filters."
    }

    return ($instances | Select-Object -First 1)
}

function Write-Json {
    param([Parameter(Mandatory = $true)]$Value)
    ConvertTo-Json -InputObject $Value -Depth 12
}

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
            name     = [string](Get-Value -Object $project -Name "Name")
            kind     = [string](Get-Value -Object $project -Name "Kind")
            fileName = [string](Get-Value -Object $project -Name "FileName")
            fullName = [string](Get-Value -Object $project -Name "FullName")
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

function Get-BreakpointList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    foreach ($breakpoint in $Dte.Debugger.Breakpoints) {
        $items.Add([pscustomobject]@{
            name         = [string](Get-Value -Object $breakpoint -Name "Name")
            enabled      = [bool](Get-Value -Object $breakpoint -Name "Enabled")
            file         = [string](Get-Value -Object $breakpoint -Name "File")
            fileLine     = Get-Value -Object $breakpoint -Name "FileLine"
            fileColumn   = Get-Value -Object $breakpoint -Name "FileColumn"
            functionName = [string](Get-Value -Object $breakpoint -Name "FunctionName")
            condition    = [string](Get-Value -Object $breakpoint -Name "Condition")
            hitCount     = Get-Value -Object $breakpoint -Name "HitCount"
        }) | Out-Null
    }

    return $items.ToArray()
}

function Get-OutputText {
    param(
        [Parameter(Mandatory = $true)]$Dte,
        [Parameter(Mandatory = $true)][string]$PaneName,
        [int]$LineTail
    )

    $outputWindow = $null
    try {
        $outputWindow = $Dte.ToolWindows.OutputWindow
    } catch {
        $outputWindow = $Dte.Windows.Item("{34E76E81-EE4A-11D0-AE2E-00A0C90FFFC3}").Object
    }

    $panes = New-Object System.Collections.Generic.List[object]
    foreach ($paneItem in $outputWindow.OutputWindowPanes) {
        $name = [string]$paneItem.Name
        if ($PaneName -ne "all" -and -not [string]::Equals($name, $PaneName, [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }

        $text = ""
        try {
            $document = $paneItem.TextDocument
            $editPoint = $document.StartPoint.CreateEditPoint()
            $text = [string]$editPoint.GetText($document.EndPoint)
        } catch {
            $text = ""
        }

        $lines = @($text -split "`r?`n")
        $panes.Add([pscustomobject]@{
            name = $name
            lineCount = $lines.Count
            text = if ($LineTail -gt 0) { (($lines | Select-Object -Last $LineTail) -join "`n") } else { $text }
        }) | Out-Null
    }

    return $panes.ToArray()
}

function Get-ErrorList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    $errorItems = $null
    try {
        $errorItems = $Dte.ToolWindows.ErrorList.ErrorItems
    } catch {
        throw "DTE Error List was not available. Try the Output Window or Computer Use."
    }

    foreach ($item in $errorItems) {
        $items.Add([pscustomobject]@{
            description = [string](Get-Value -Object $item -Name "Description")
            fileName    = [string](Get-Value -Object $item -Name "FileName")
            line        = Get-Value -Object $item -Name "Line"
            column      = Get-Value -Object $item -Name "Column"
            project     = [string](Get-Value -Object $item -Name "Project")
            errorLevel  = [string](Get-Value -Object $item -Name "ErrorLevel")
        }) | Out-Null
    }

    return $items.ToArray()
}

function Get-TaskList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    $taskItems = $null
    try {
        $taskItems = $Dte.ToolWindows.TaskList.TaskItems
    } catch {
        throw "DTE Task List was not available. Try the Output Window or Computer Use."
    }

    foreach ($item in $taskItems) {
        $items.Add([pscustomobject]@{
            description = [string](Get-Value -Object $item -Name "Description")
            fileName    = [string](Get-Value -Object $item -Name "FileName")
            line        = Get-Value -Object $item -Name "Line"
            category    = [string](Get-Value -Object $item -Name "Category")
            subCategory = [string](Get-Value -Object $item -Name "SubCategory")
            priority    = [string](Get-Value -Object $item -Name "Priority")
            checked     = Get-Value -Object $item -Name "Checked"
            displayed   = Get-Value -Object $item -Name "Displayed"
        }) | Out-Null
    }

    return $items.ToArray()
}

function Get-CallStack {
    param($Dte)

    $frames = New-Object System.Collections.Generic.List[object]
    try {
        foreach ($frame in $Dte.Debugger.CurrentThread.StackFrames) {
            $frames.Add([pscustomobject]@{
                functionName = [string](Get-Value -Object $frame -Name "FunctionName")
                fileName     = [string](Get-Value -Object $frame -Name "FileName")
                lineNumber   = Get-Value -Object $frame -Name "LineNumber"
                module       = [string](Get-Value -Object $frame -Name "Module")
                language     = [string](Get-Value -Object $frame -Name "Language")
            }) | Out-Null
        }
    } catch {
        throw "Call stack is available only while the debugger has an active current thread."
    }

    return $frames.ToArray()
}

function Get-Locals {
    param($Dte)

    $locals = New-Object System.Collections.Generic.List[object]
    try {
        foreach ($expr in $Dte.Debugger.CurrentStackFrame.Locals) {
            $locals.Add([pscustomobject]@{
                name         = [string](Get-Value -Object $expr -Name "Name")
                value        = [string](Get-Value -Object $expr -Name "Value")
                type         = [string](Get-Value -Object $expr -Name "Type")
                isValidValue = [bool](Get-Value -Object $expr -Name "IsValidValue")
            }) | Out-Null
        }
    } catch {
        throw "Locals are available only while the debugger is stopped at a stack frame."
    }

    return $locals.ToArray()
}

if ($Action -eq "list-instances") {
    Write-Json -Value @((Get-DteInstances) | ForEach-Object { $_.meta })
    exit 0
}

$selected = Select-DteInstance
$dte = $selected.dte

switch ($Action) {
    "status" {
        Write-Json -Value (Get-Status -Selected $selected)
    }
    "list-projects" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            projects = @(Get-ProjectList -Projects $dte.Solution.Projects)
        })
    }
    "build" {
        $build = $dte.Solution.SolutionBuild
        $build.Build($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "build"
            waited = $Wait.IsPresent
            buildState = [string](Get-Value -Object $build -Name "BuildState")
            lastBuildInfo = Get-Value -Object $build -Name "LastBuildInfo"
        })
    }
    "clean" {
        $build = $dte.Solution.SolutionBuild
        $build.Clean($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "clean"
            waited = $Wait.IsPresent
            buildState = [string](Get-Value -Object $build -Name "BuildState")
            lastBuildInfo = Get-Value -Object $build -Name "LastBuildInfo"
        })
    }
    "debug-state" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            currentMode = Get-CurrentDebugMode -Dte $dte
            currentProcess = [string](Get-Value -Object (Get-Value -Object $dte.Debugger -Name "CurrentProcess") -Name "Name")
            currentThread = [string](Get-Value -Object (Get-Value -Object $dte.Debugger -Name "CurrentThread") -Name "Name")
            currentStackFrame = [string](Get-Value -Object (Get-Value -Object $dte.Debugger -Name "CurrentStackFrame") -Name "FunctionName")
            breakpoints = @(Get-BreakpointList -Dte $dte)
        })
    }
    "call-stack" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            frames = @(Get-CallStack -Dte $dte)
        })
    }
    "locals" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            locals = @(Get-Locals -Dte $dte)
        })
    }
    "eval" {
        if ([string]::IsNullOrWhiteSpace($Expression)) {
            throw "-Expression is required for eval."
        }
        $expr = $dte.Debugger.GetExpression($Expression, $true, 1000)
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            expression = $Expression
            name = [string](Get-Value -Object $expr -Name "Name")
            value = [string](Get-Value -Object $expr -Name "Value")
            type = [string](Get-Value -Object $expr -Name "Type")
            isValidValue = [bool](Get-Value -Object $expr -Name "IsValidValue")
        })
    }
    "start-debugging" {
        $solutionPath = [string](Get-Value -Object $dte.Solution -Name "FullName")
        $isFolderWorkspace = -not [string]::IsNullOrWhiteSpace($solutionPath) -and (Test-Path -LiteralPath $solutionPath -PathType Container)
        if ($isFolderWorkspace) {
            $dte.ExecuteCommand("Debug.Start", "")
        } else {
            $dte.Solution.SolutionBuild.Debug()
        }
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "start-debugging"
            mechanism = if ($isFolderWorkspace) { "Debug.Start" } else { "SolutionBuild.Debug" }
            currentMode = Get-CurrentDebugMode -Dte $dte
        })
    }
    "stop-debugging" {
        $dte.Debugger.Stop($true)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "stop-debugging"; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "break" {
        $dte.Debugger.Break($true)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "break"; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "continue" {
        $dte.Debugger.Go($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "continue"; waited = $Wait.IsPresent; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "step-into" {
        $dte.Debugger.StepInto($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "step-into"; waited = $Wait.IsPresent; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "step-over" {
        $dte.Debugger.StepOver($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "step-over"; waited = $Wait.IsPresent; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "step-out" {
        $dte.Debugger.StepOut($Wait.IsPresent)
        Write-Json -Value ([pscustomobject]@{ instance = $selected.meta; action = "step-out"; waited = $Wait.IsPresent; currentMode = Get-CurrentDebugMode -Dte $dte })
    }
    "list-breakpoints" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            breakpoints = @(Get-BreakpointList -Dte $dte)
        })
    }
    "add-breakpoint" {
        if ([string]::IsNullOrWhiteSpace($File) -or $Line -le 0) {
            throw "-File and -Line are required for add-breakpoint."
        }
        $resolvedFile = (Resolve-Path -LiteralPath $File).Path
        $conditionText = if ([string]::IsNullOrWhiteSpace($Condition)) { "" } else { $Condition }
        $dte.Debugger.Breakpoints.Add("", $resolvedFile, $Line, 1, $conditionText, 1, "", "", 0, "", 0, 1) | Out-Null
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "add-breakpoint"
            file = $resolvedFile
            line = $Line
            breakpoints = @(Get-BreakpointList -Dte $dte)
        })
    }
    "remove-breakpoints" {
        $resolvedFile = $null
        if (-not [string]::IsNullOrWhiteSpace($File)) {
            $resolvedFile = (Resolve-Path -LiteralPath $File).Path
        }
        if (-not $All -and [string]::IsNullOrWhiteSpace($resolvedFile) -and $Line -le 0) {
            throw "Use -All or provide -File and/or -Line for remove-breakpoints."
        }

        $removed = 0
        $breakpoints = @($dte.Debugger.Breakpoints)
        foreach ($breakpoint in $breakpoints) {
            $matches = $All.IsPresent
            if (-not $matches -and -not [string]::IsNullOrWhiteSpace($resolvedFile)) {
                $bpFile = [string](Get-Value -Object $breakpoint -Name "File")
                $matches = [string]::Equals($bpFile, $resolvedFile, [StringComparison]::OrdinalIgnoreCase)
            }
            if ($matches -and $Line -gt 0) {
                $matches = ([int](Get-Value -Object $breakpoint -Name "FileLine") -eq $Line)
            }
            if ($matches) {
                $breakpoint.Delete()
                $removed++
            }
        }

        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "remove-breakpoints"
            removed = $removed
            breakpoints = @(Get-BreakpointList -Dte $dte)
        })
    }
    "output" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            panes = @(Get-OutputText -Dte $dte -PaneName $Pane -LineTail $Tail)
        })
    }
    "error-list" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            items = @(Get-ErrorList -Dte $dte)
        })
    }
    "task-list" {
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            items = @(Get-TaskList -Dte $dte)
        })
    }
    "list-commands" {
        $commands = New-Object System.Collections.Generic.List[object]
        foreach ($item in $dte.Commands) {
            $name = [string](Get-Value -Object $item -Name "Name")
            if ([string]::IsNullOrWhiteSpace($CommandFilter) -or $name -like "*$CommandFilter*") {
                $commands.Add([pscustomobject]@{
                    name = $name
                    guid = [string](Get-Value -Object $item -Name "Guid")
                    id = Get-Value -Object $item -Name "ID"
                }) | Out-Null
            }
        }
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            filter = $CommandFilter
            commands = $commands.ToArray()
        })
    }
    "attach-process" {
        if ($TargetPid -le 0) {
            throw "-TargetPid is required for attach-process."
        }

        $targetProcess = $null
        foreach ($candidate in $dte.Debugger.LocalProcesses) {
            if ([int](Get-Value -Object $candidate -Name "ProcessID") -eq $TargetPid) {
                $targetProcess = $candidate
                break
            }
        }
        if (-not $targetProcess) {
            throw "The target process was not found in DTE.Debugger.LocalProcesses: $TargetPid"
        }

        if ([string]::IsNullOrWhiteSpace($Engine)) {
            $targetProcess.Attach()
        } else {
            $engineSelector = if ([string]::Equals($Engine, "native", [StringComparison]::OrdinalIgnoreCase)) {
                "{3B476D35-A401-11D2-AAD4-00C04F990171}"
            } else {
                $Engine
            }

            if (-not ("EnvDTE80.Process2" -as [type])) {
                $ideDirectory = Split-Path -Parent ([string](Get-Value -Object $dte -Name "FullName"))
                $publicAssemblies = Join-Path $ideDirectory "PublicAssemblies"
                Add-Type -Path (Join-Path $publicAssemblies "envdte.dll")
                Add-Type -Path (Join-Path $publicAssemblies "envdte80.dll")
            }

            $unknown = [Runtime.InteropServices.Marshal]::GetIUnknownForObject($targetProcess)
            try {
                $process2 = [Runtime.InteropServices.Marshal]::GetTypedObjectForIUnknown($unknown, [EnvDTE80.Process2])
                $attachMethod = [EnvDTE80.Process2].GetMethod("Attach2")
                [void]$attachMethod.Invoke($process2, @([object]$engineSelector))
            } finally {
                [void][Runtime.InteropServices.Marshal]::Release($unknown)
            }
        }

        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "attach-process"
            targetProcessId = $TargetPid
            targetName = [string](Get-Value -Object $targetProcess -Name "Name")
            engine = if ([string]::IsNullOrWhiteSpace($Engine)) { "automatic" } else { $engineSelector }
            currentMode = Get-CurrentDebugMode -Dte $dte
        })
    }
    "execute-command" {
        if ([string]::IsNullOrWhiteSpace($Command)) {
            throw "-Command is required for execute-command."
        }
        $dte.ExecuteCommand($Command, $CommandArgs)
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "execute-command"
            command = $Command
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
            instance = $selected.meta
            action = "open-document"
            file = $resolvedFile
            windowCaption = [string](Get-Value -Object $window -Name "Caption")
        })
    }
    "save-all" {
        $dte.ExecuteCommand("File.SaveAll", "")
        Write-Json -Value ([pscustomobject]@{
            instance = $selected.meta
            action = "save-all"
        })
    }
}
