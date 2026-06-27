# EnvDTE/DTE API Reference

Use this reference when Tier 2 is needed: the request depends on a running Visual Studio IDE instance, but does not require visual inspection or screen scraping.

## Official References

- DTE2 top-level object: https://learn.microsoft.com/en-us/dotnet/api/envdte80.dte2?view=visualstudiosdk-2022
- Solution object: https://learn.microsoft.com/en-us/dotnet/api/envdte.solution?view=visualstudiosdk-2022
- SolutionBuild object: https://learn.microsoft.com/en-us/dotnet/api/envdte.solutionbuild?view=visualstudiosdk-2022
- Debugger object: https://learn.microsoft.com/en-us/dotnet/api/envdte.debugger?view=visualstudiosdk-2022
- Breakpoints collection: https://learn.microsoft.com/en-us/dotnet/api/envdte.breakpoints?view=visualstudiosdk-2022
- Output Window: https://learn.microsoft.com/en-us/dotnet/api/envdte.outputwindow?view=visualstudiosdk-2022
- Output Window Pane: https://learn.microsoft.com/en-us/dotnet/api/envdte.outputwindowpane?view=visualstudiosdk-2022
- Task List: https://learn.microsoft.com/en-us/dotnet/api/envdte.tasklist?view=visualstudiosdk-2022
- Task Item: https://learn.microsoft.com/en-us/dotnet/api/envdte.taskitem?view=visualstudiosdk-2022

## ProgIDs

Common Visual Studio automation ProgIDs:

| Visual Studio version | ProgID |
|---|---|
| 2026, when installed | `VisualStudio.DTE.18.0` |
| 2022 | `VisualStudio.DTE.17.0` |
| 2019 | `VisualStudio.DTE.16.0` |
| 2017 | `VisualStudio.DTE.15.0` |
| 2015 | `VisualStudio.DTE.14.0` |

Running instances are usually registered in the Running Object Table with names like `!VisualStudio.DTE.17.0:<process-id>`. Prefer ROT enumeration over `Marshal.GetActiveObject(...)` when multiple Visual Studio instances may be open.

## Connection Pattern

Use `scripts/vs_dte.ps1 -Action list-instances` first. Then select an instance by solution path, process id, or ProgID:

```powershell
.\scripts\vs_dte.ps1 -Action list-instances
.\scripts\vs_dte.ps1 -Action status -Solution C:\src\App\App.sln
.\scripts\vs_dte.ps1 -Action output -Pane Build -Tail 200
```

PowerShell and Visual Studio must run in the same Windows user desktop session. DTE automation can be blocked by modal dialogs or unavailable if Visual Studio is elevated and the PowerShell host is not elevated.

## Core Object Model

### DTE2

`EnvDTE80.DTE2` is the top-level automation object. Useful members:

- `Solution`: access loaded solution, projects, and `SolutionBuild`.
- `Debugger`: debugger mode, breakpoints, stack frame, stepping, expression evaluation.
- `ToolWindows`: Output Window, Error List, and other tool windows when exposed.
- `Documents` and `ActiveDocument`: open editor documents and save state.
- `ItemOperations.OpenFile(path)`: open a file in the editor.
- `ExecuteCommand(name, args)`: run a Visual Studio command by command name.
- `SuppressUI`: can reduce UI prompts, but do not set it blindly for operations that might need user confirmation.

### Solution And Projects

Common members:

- `DTE.Solution.FullName`: current solution path.
- `DTE.Solution.IsOpen`: whether a solution is loaded.
- `DTE.Solution.Projects`: top-level project collection.
- `Project.Name`, `Project.FullName`, `Project.FileName`, `Project.UniqueName`, `Project.Kind`: project identity.
- Solution folders may contain nested projects via `Project.ProjectItems[*].SubProject`; recurse when enumerating.
- `Solution.Open(path)`, `Solution.Create(path, name)`, `Solution.AddFromFile(path)`, and `Solution.Close(saveFirst)` mutate solution state and need clear intent.

### SolutionBuild

Common members:

- `DTE.Solution.SolutionBuild.ActiveConfiguration`: active IDE solution configuration.
- `SolutionBuild.SolutionConfigurations`: available configurations.
- `SolutionBuild.StartupProjects`: startup project names.
- `SolutionBuild.Build(wait)`: build active solution configuration.
- `SolutionBuild.Clean(wait)`: clean active solution configuration.
- `SolutionBuild.BuildProject(configuration, projectUniqueName, wait)`: build one project in solution context.
- `SolutionBuild.Debug()`: start debugging.
- `SolutionBuild.Run()`: run without debugging.
- `SolutionBuild.LastBuildInfo`: number of projects that failed in the last build.
- `SolutionBuild.BuildState`: current or last build state.

Prefer `scripts/vs_build.ps1` for repeatable headless builds. Use DTE build only when the active IDE configuration or loaded solution state is the source of truth.

### Debugger

Common members:

- `Debugger.CurrentMode`: design, run, or break mode.
- `Debugger.Breakpoints`: pending breakpoints.
- `Debugger.CurrentProcess`, `CurrentThread`, `CurrentStackFrame`: active debug context.
- `Debugger.CurrentStackFrame.Locals`: local expressions when stopped.
- `Debugger.GetExpression(expression, useAutoExpandRules, timeout)`: evaluate in the current frame.
- `Debugger.Go(wait)`, `Break(wait)`, `Stop(wait)`, `StepInto(wait)`, `StepOver(wait)`, `StepOut(wait)`: control execution.

Only mutate debugger state when the user asked for debugging actions. If the target is running, some reads are unavailable until the debugger is stopped.

### Breakpoints

Use `Debugger.Breakpoints` to list and manipulate pending breakpoints:

- `Breakpoints.Add(function, file, line, column, condition, conditionType, language, data, dataCount, address, hitCount, hitCountType)`.
- `Breakpoint.Delete()` removes a breakpoint.
- Useful properties include `Name`, `Enabled`, `File`, `FileLine`, `FileColumn`, `FunctionName`, `Condition`, and `HitCount`.

For script use:

```powershell
.\scripts\vs_dte.ps1 -Action list-breakpoints
.\scripts\vs_dte.ps1 -Action add-breakpoint -File C:\src\App\Program.cs -Line 42
.\scripts\vs_dte.ps1 -Action remove-breakpoints -File C:\src\App\Program.cs -Line 42
```

### Output Window

Use `DTE.ToolWindows.OutputWindow.OutputWindowPanes` when available. Each pane can expose a `TextDocument`; read it with an edit point:

```powershell
$pane = $dte.ToolWindows.OutputWindow.OutputWindowPanes.Item("Build")
$doc = $pane.TextDocument
$point = $doc.StartPoint.CreateEditPoint()
$text = $point.GetText($doc.EndPoint)
```

If a custom pane is not exposed as text, escalate to Computer Use.

### Error List

Many Visual Studio versions expose Error List through `DTE.ToolWindows.ErrorList.ErrorItems`. Useful item properties include `Description`, `FileName`, `Line`, `Column`, `Project`, and `ErrorLevel`.

If Error List is unavailable or stale, prefer Output Window text or a headless MSBuild log.

### Task List

Use `DTE.ToolWindows.TaskList.TaskItems` when Visual Studio exposes the Task List through EnvDTE. Useful item properties include `Description`, `FileName`, `Line`, `Category`, `SubCategory`, `Priority`, `Checked`, and `Displayed`.

If Task List content is supplied by an extension and DTE cannot read it, escalate to Computer Use.

### Commands

`DTE.ExecuteCommand(commandName, commandArgs)` runs any registered Visual Studio command. Examples:

```powershell
$dte.ExecuteCommand("Build.BuildSolution", "")
$dte.ExecuteCommand("Debug.Start", "")
$dte.ExecuteCommand("File.SaveAll", "")
```

Command names can vary by installed workloads and extensions. If a command opens UI, treat the next step as Tier 3.

## When DTE Is Not Enough

Escalate to Computer Use for:

- Modal dialogs, trust prompts, sign-in prompts, installer/workload UI, or repair/update prompts.
- Designer surfaces and extension-specific panes not exposed through DTE.
- Visual state such as selected tree nodes, hover data tips, editor adornments, drag/drop operations, and transient popups.
- Any situation where DTE calls hang because the IDE is waiting on user input.
