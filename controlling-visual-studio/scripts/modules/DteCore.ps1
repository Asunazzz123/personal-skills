<#
.SYNOPSIS
Core DTE utilities: ROT connection, instance discovery, safe property access, JSON output.
#>

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

function Ensure-EnvDteTypes {
    if ("EnvDTE80.DTE2" -as [type]) {
        return
    }

    $candidates = @()

    # Try from running VS instances
    $progIds = @("VisualStudio.DTE.17.0", "VisualStudio.DTE.16.0")
    foreach ($id in $progIds) {
        try {
            $dte = [Runtime.InteropServices.Marshal]::GetActiveObject($id)
            if ($dte) {
                $ideDir = Split-Path -Parent ([string]$dte.FullName)
                $candidates += (Join-Path $ideDir "PublicAssemblies")
                break
            }
        } catch {
        }
    }

    # Fallback to known VS 2022 install paths
    $pf = [Environment]::GetFolderPath("ProgramFiles")
    foreach ($edition in @("Enterprise", "Professional", "Community", "BuildTools")) {
        $candidates += (Join-Path $pf "Microsoft Visual Studio\2022\$edition\Common7\IDE\PublicAssemblies")
    }

    foreach ($dir in $candidates) {
        $envdte = Join-Path $dir "envdte.dll"
        $envdte80 = Join-Path $dir "envdte80.dll"
        if ((Test-Path -LiteralPath $envdte) -and (Test-Path -LiteralPath $envdte80)) {
            try {
                Add-Type -Path $envdte
                Add-Type -Path $envdte80
                return
            } catch {
            }
        }
    }
}

function Get-MarshalDte {
    param([string]$ProgId)

    # Marshal.GetActiveObject returns a raw COM proxy (IDispatch late binding).
    # This works for top-level properties (Solution, Debugger, Commands) which
    # live on the EnvDTE._DTE default dispatch interface.
    #
    # However, ToolWindows, ErrorList, OutputWindow etc. are defined on the
    # EnvDTE80.DTE2 interface (GUID 19AC6F68-3019-4D65-8D98-404DFB96B8E2),
    # NOT on the default dispatch interface. PowerShell's property accessor
    # uses IDispatch even for typed RCWs, so ToolWindows returns null.
    #
    # The fix: use GetTypedObjectForIUnknown for the DTE cast, then access
    # ToolWindows via .NET reflection (GetProperty.GetValue) which calls the
    # interface getter directly, bypassing IDispatch.
    # Ref: https://github.com/Edge-JB/TwinCAT-XAE-MCP/pull/6

    $rawDte = [Runtime.InteropServices.Marshal]::GetActiveObject($ProgId)

    if ("EnvDTE80.DTE2" -as [type]) {
        $pUnk = [Runtime.InteropServices.Marshal]::GetIUnknownForObject($rawDte)
        try {
            $typedDte = [Runtime.InteropServices.Marshal]::GetTypedObjectForIUnknown($pUnk, [EnvDTE80.DTE2])
            return $typedDte
        } finally {
            [void][Runtime.InteropServices.Marshal]::Release($pUnk)
        }
    }

    return $rawDte
}

function Get-ToolWindows {
    param($Dte)

    # PowerShell's COM property accessor uses IDispatch late binding, which
    # cannot reach EnvDTE80.DTE2.ToolWindows (returns null). Use .NET
    # reflection to call the interface property getter directly.
    if ("EnvDTE80.DTE2" -as [type]) {
        $prop = [EnvDTE80.DTE2].GetProperty("ToolWindows")
        if ($prop) {
            return $prop.GetValue($Dte)
        }
    }

    # Fallback: try late binding (works when type library is properly registered)
    return $Dte.ToolWindows
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
