<#
.SYNOPSIS
Text document operations: read and replace text in the VS editor.
#>

function Get-TextDocument {
    param(
        $Dte,
        [string]$File
    )

    $targetDoc = $null
    if (-not [string]::IsNullOrWhiteSpace($File)) {
        $resolvedFile = (Resolve-Path -LiteralPath $File).Path
        $window = $Dte.ItemOperations.OpenFile($resolvedFile)
        $targetDoc = $window.Document
    } else {
        $targetDoc = $Dte.ActiveDocument
    }

    if (-not $targetDoc) {
        throw "No active document and no -File specified."
    }

    $textDoc = $null
    try {
        $textDoc = $targetDoc.Object("TextDocument")
    } catch {
        $textDoc = $targetDoc
    }

    return [pscustomobject]@{
        Document     = $targetDoc
        TextDocument = $textDoc
    }
}

function Invoke-DteText {
    param(
        [string]$Action,
        $Selected,
        $Dte,
        [string]$File,
        [int]$Tail,
        [string]$Find,
        [string]$Replace,
        [switch]$Regex
    )

    switch ($Action) {
        "get-text" {
            $doc = Get-TextDocument -Dte $Dte -File $File
            $fullText = ""
            $lineCount = 0
            try {
                $editPoint = $doc.TextDocument.StartPoint.CreateEditPoint()
                $fullText = [string]$editPoint.GetText($doc.TextDocument.EndPoint)
                $lineCount = [int]$doc.TextDocument.EndPoint.Line
            } catch {
                throw "Could not read text from document: $([string]$doc.Document.FullName)"
            }
            $lines = @($fullText -split "`r?`n")
            Write-Json -Value ([pscustomobject]@{
                instance  = $Selected.meta
                fullName  = [string]$doc.Document.FullName
                saved     = [bool]$doc.Document.Saved
                lineCount = $lineCount
                text      = if ($Tail -gt 0) { (($lines | Select-Object -Last $Tail) -join "`n") } else { $fullText }
            })
            $script:ActionHandled = $true
            return
        }
        "replace-text" {
            if ([string]::IsNullOrWhiteSpace($Find)) {
                throw "-Find is required for replace-text."
            }
            $doc = Get-TextDocument -Dte $Dte -File $File
            $replaceText = if ($null -ne $Replace) { $Replace } else { "" }
            $vsFindOptionsNone = 0
            if ($Regex.IsPresent) {
                $vsFindOptionsNone = 1
            }
            $count = 0
            try {
                $editPoint = $doc.TextDocument.StartPoint.CreateEditPoint()
                while ($editPoint.FindPattern($Find, $vsFindOptionsNone, $doc.TextDocument.EndPoint, $null)) {
                    $editPoint.ReplaceText($editPoint, $replaceText, 0)
                    $count++
                }
            } catch {
                throw "Replace operation failed. The document may not support FindPattern. Ensure the file is open in the VS editor."
            }
            Write-Json -Value ([pscustomobject]@{
                instance         = $Selected.meta
                action           = "replace-text"
                fullName         = [string]$doc.Document.FullName
                find             = $Find
                replace          = $replaceText
                replacementsMade = $count
            })
            $script:ActionHandled = $true
            return
        }
    }
}
