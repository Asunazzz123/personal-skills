<#
.SYNOPSIS
Output Window, Error List, and Task List functions.
#>

function Get-OutputWindow {
    param($Dte)

    try {
        $tw = Get-ToolWindows -Dte $Dte
        if ($tw) {
            $window = $tw.OutputWindow
            if ($window) { return $window }
        }
    } catch {
    }

    try {
        $win = $Dte.Windows.Item("{34E76E81-EE4A-11D0-AE2E-00A0C90FFFC3}")
        if ($win) {
            $obj = Get-Value -Object $win -Name "Object"
            if ($obj) { return $obj }
        }
    } catch {
    }

    throw "Output Window is not available through DTE. Try Computer Use."
}

function Get-OutputText {
    param(
        [Parameter(Mandatory = $true)]$Dte,
        [Parameter(Mandatory = $true)][string]$PaneName,
        [int]$LineTail
    )

    $outputWindow = Get-OutputWindow -Dte $Dte

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
            name      = $name
            lineCount = $lines.Count
            text      = if ($LineTail -gt 0) { (($lines | Select-Object -Last $LineTail) -join "`n") } else { $text }
        }) | Out-Null
    }

    return $panes.ToArray()
}

function Get-OutputPaneList {
    param($Dte)

    $outputWindow = Get-OutputWindow -Dte $Dte
    $panes = New-Object System.Collections.Generic.List[object]
    $index = 0
    foreach ($paneItem in $outputWindow.OutputWindowPanes) {
        $panes.Add([pscustomobject]@{
            index = $index
            name  = [string]$paneItem.Name
            guid  = [string](Get-Value -Object $paneItem -Name "Guid")
        }) | Out-Null
        $index++
    }
    return $panes.ToArray()
}

function Clear-OutputPane {
    param(
        $Dte,
        [string]$PaneName
    )

    $outputWindow = Get-OutputWindow -Dte $Dte
    foreach ($paneItem in $outputWindow.OutputWindowPanes) {
        if ([string]::Equals([string]$paneItem.Name, $PaneName, [StringComparison]::OrdinalIgnoreCase)) {
            $paneItem.Clear()
            return $true
        }
    }
    return $false
}

function Get-ErrorList {
    param($Dte)

    $items = New-Object System.Collections.Generic.List[object]
    $errorItems = $null
    try {
        $tw = Get-ToolWindows -Dte $Dte
        if (-not $tw) {
            throw "ToolWindows is null"
        }
        $el = $tw.ErrorList
        if (-not $el) {
            throw "ErrorList is null"
        }
        # ErrorItems may not be reachable via IDispatch late binding.
        # Use reflection if the typed interface is available.
        if ("EnvDTE80.ErrorList" -as [type]) {
            $prop = [EnvDTE80.ErrorList].GetProperty("ErrorItems")
            if ($prop) {
                $errorItems = $prop.GetValue($el)
            }
        }
        if (-not $errorItems) {
            $errorItems = $el.ErrorItems
        }
    } catch {
        throw "DTE Error List was not available: $($_.Exception.Message)"
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
        $tw = Get-ToolWindows -Dte $Dte
        if (-not $tw) {
            throw "ToolWindows is null"
        }
        $tl = $tw.TaskList
        if (-not $tl) {
            throw "TaskList is null"
        }
        if ("EnvDTE.TaskList" -as [type]) {
            $prop = [EnvDTE.TaskList].GetProperty("TaskItems")
            if ($prop) {
                $taskItems = $prop.GetValue($tl)
            }
        }
        if (-not $taskItems) {
            $taskItems = $tl.TaskItems
        }
    } catch {
        throw "DTE Task List was not available: $($_.Exception.Message)"
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

function Invoke-DteOutput {
    param(
        [string]$Action,
        $Selected,
        $Dte,
        [string]$Pane = "Build",
        [int]$Tail = 200
    )

    switch ($Action) {
        "output" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                panes    = @(Get-OutputText -Dte $Dte -PaneName $Pane -LineTail $Tail)
            })
            $script:ActionHandled = $true
            return
        }
        "output-panes" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                panes    = @(Get-OutputPaneList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "clear-output" {
            $cleared = Clear-OutputPane -Dte $Dte -PaneName $Pane
            if (-not $cleared) {
                throw "Output pane '$Pane' was not found. Use -Action output-panes to list available panes."
            }
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                action   = "clear-output"
                pane     = $Pane
            })
            $script:ActionHandled = $true
            return
        }
        "error-list" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                items    = @(Get-ErrorList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
        "task-list" {
            Write-Json -Value ([pscustomobject]@{
                instance = $Selected.meta
                items    = @(Get-TaskList -Dte $Dte)
            })
            $script:ActionHandled = $true
            return
        }
    }
}
