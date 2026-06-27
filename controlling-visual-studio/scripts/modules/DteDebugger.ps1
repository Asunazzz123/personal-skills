<#
.SYNOPSIS
Debugger operations: state, stepping, breakpoints, threads, modules, process attachment.
#>

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

function Get-ThreadList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    $currentThread = $null
    try {
        $currentThread = $Dte.Debugger.CurrentThread
    } catch {
    }

    try {
        $process = $Dte.Debugger.CurrentProcess
        if (-not $process) {
            throw "No current process."
        }
        foreach ($thread in $process.Threads) {
            $threadId = Get-Value -Object $thread -Name "ID"
            $isCurrent = $false
            if ($currentThread) {
                try { $isCurrent = ([int](Get-Value -Object $currentThread -Name "ID") -eq [int]$threadId) } catch { }
            }
            $items.Add([pscustomobject]@{
                id           = $threadId
                name         = [string](Get-Value -Object $thread -Name "Name")
                suspendCount = Get-Value -Object $thread -Name "SuspendCount"
                isCurrent    = $isCurrent
            }) | Out-Null
        }
    } catch {
        throw "Thread listing requires the debugger to be in run or break mode with an active process."
    }

    return $items.ToArray()
}

function Get-ModuleList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    try {
        foreach ($module in $Dte.Debugger.Modules) {
            $items.Add([pscustomobject]@{
                name        = [string](Get-Value -Object $module -Name "Name")
                path        = [string](Get-Value -Object $module -Name "Path")
                isOptimized = [bool](Get-Value -Object $module -Name "IsOptimized")
                isUserCode  = [bool](Get-Value -Object $module -Name "IsUserCode")
                version     = [string](Get-Value -Object $module -Name "Version")
                loadOrder   = Get-Value -Object $module -Name "LoadOrder"
            }) | Out-Null
        }
    } catch {
        throw "Module listing is available only while the debugger is active."
    }

    return $items.ToArray()
}

function Invoke-DteDebugger {
    param(
        [string]$Action,
        $Selected,
        $Dte,
        [string]$File,
        [int]$Line,
        [string]$Condition,
        [switch]$All,
        [int]$TargetPid,
        [string]$Engine,
        [string]$Expression,
        [int]$ThreadId,
        [switch]$Wait
    )

    switch ($Action) {
        "debug-state" {
            Write-Json -Value ([pscustomobject]@{
                instance          = $Selected.meta
                currentMode       = Get-CurrentDebugMode -Dte $Dte
                currentProcess    = [string](Get-Value -Object (Get-Value -Object $Dte.Debugger -Name "CurrentProcess") -Name "Name")
                currentThread     = [string](Get-Value -Object (Get-Value -Object $Dte.Debugger -Name "CurrentThread") -Name "Name")
                currentStackFrame = [string](Get-Value -Object (Get-Value -Object $Dte.Debugger -Name "CurrentStackFrame") -Name "FunctionName")
                breakpoints       = @(Get-BreakpointList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "call-stack" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                frames   = @(Get-CallStack -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "locals" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                locals   = @(Get-Locals -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "eval" {
            if ([string]::IsNullOrWhiteSpace($Expression)) {
                throw "-Expression is required for eval."
            }
            $expr = $Dte.Debugger.GetExpression($Expression, $true, 1000)
            Write-Json -Value ([pscustomobject]@{
                instance      = $Selected.meta
                expression    = $Expression
                name          = [string](Get-Value -Object $expr -Name "Name")
                value         = [string](Get-Value -Object $expr -Name "Value")
                type          = [string](Get-Value -Object $expr -Name "Type")
                isValidValue  = [bool](Get-Value -Object $expr -Name "IsValidValue")
            })
            $script:ActionHandled = $true
            return
        }
        "start-debugging" {
            $solutionPath = [string](Get-Value -Object $Dte.Solution -Name "FullName")
            $isFolderWorkspace = -not [string]::IsNullOrWhiteSpace($solutionPath) -and (Test-Path -LiteralPath $solutionPath -PathType Container)
            if ($isFolderWorkspace) {
                $Dte.ExecuteCommand("Debug.Start", "")
            } else {
                $Dte.Solution.SolutionBuild.Debug()
            }
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "start-debugging"
                mechanism   = if ($isFolderWorkspace) { "Debug.Start" } else { "SolutionBuild.Debug" }
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "stop-debugging" {
            $Dte.Debugger.Stop($true)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "stop-debugging"
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "break" {
            $Dte.Debugger.Break($true)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "break"
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "continue" {
            $Dte.Debugger.Go($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "continue"
                waited      = $Wait.IsPresent
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "step-into" {
            $Dte.Debugger.StepInto($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "step-into"
                waited      = $Wait.IsPresent
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "step-over" {
            $Dte.Debugger.StepOver($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "step-over"
                waited      = $Wait.IsPresent
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "step-out" {
            $Dte.Debugger.StepOut($Wait.IsPresent)
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "step-out"
                waited      = $Wait.IsPresent
                currentMode = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
        "list-breakpoints" {
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                breakpoints = @(Get-BreakpointList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "add-breakpoint" {
            if ([string]::IsNullOrWhiteSpace($File) -or $Line -le 0) {
                throw "-File and -Line are required for add-breakpoint."
            }
            $resolvedFile = (Resolve-Path -LiteralPath $File).Path
            $conditionText = if ([string]::IsNullOrWhiteSpace($Condition)) { "" } else { $Condition }
            $Dte.Debugger.Breakpoints.Add("", $resolvedFile, $Line, 1, $conditionText, 1, "", "", 0, "", 0, 1) | Out-Null
            Write-Json -Value ([pscustomobject]@{
                instance    = $Selected.meta
                action      = "add-breakpoint"
                file        = $resolvedFile
                line        = $Line
                breakpoints = @(Get-BreakpointList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
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
            $breakpoints = @($Dte.Debugger.Breakpoints)
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
                instance    = $Selected.meta
                action      = "remove-breakpoints"
                removed     = $removed
                breakpoints = @(Get-BreakpointList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "list-threads" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                threads  = @(Get-ThreadList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "set-active-thread" {
            if ($ThreadId -le 0) {
                throw "-ThreadId is required for set-active-thread."
            }
            $targetThread = $null
            try {
                $process = $Dte.Debugger.CurrentProcess
                foreach ($thread in $process.Threads) {
                    if ([int](Get-Value -Object $thread -Name "ID") -eq $ThreadId) {
                        $targetThread = $thread
                        break
                    }
                }
            } catch {
                throw "Thread listing requires the debugger to be in run or break mode with an active process."
            }
            if (-not $targetThread) {
                throw "Thread with ID $ThreadId was not found in the current process."
            }
            $Dte.Debugger.CurrentThread = $targetThread
            Write-Json -Value ([pscustomobject]@{
                instance      = $Selected.meta
                action        = "set-active-thread"
                threadId      = $ThreadId
                currentThread = [string](Get-Value -Object $Dte.Debugger.CurrentThread -Name "Name")
            })
            $script:ActionHandled = $true
            return
        }
        "list-modules" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                modules  = @(Get-ModuleList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "attach-process" {
            if ($TargetPid -le 0) {
                throw "-TargetPid is required for attach-process."
            }

            $targetProcess = $null
            foreach ($candidate in $Dte.Debugger.LocalProcesses) {
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
                    $ideDirectory = Split-Path -Parent ([string](Get-Value -Object $Dte -Name "FullName"))
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
                instance       = $Selected.meta
                action         = "attach-process"
                targetProcessId = $TargetPid
                targetName     = [string](Get-Value -Object $targetProcess -Name "Name")
                engine         = if ([string]::IsNullOrWhiteSpace($Engine)) { "automatic" } else { $engineSelector }
                currentMode    = Get-CurrentDebugMode -Dte $Dte
            })
            $script:ActionHandled = $true
            return
        }
    }
}
