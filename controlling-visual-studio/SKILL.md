---
name: controlling-visual-studio
description: Use when Codex needs to inspect, configure, debug, build, or explain Microsoft Visual Studio projects, solutions, CMake workspaces, IDE settings, project properties, build errors, debugger state, EnvDTE/DTE automation, toolchain issues, or Visual Studio GUI-only behavior, especially when deciding between shell/CLI, EnvDTE, and Computer Use control.
---

# Controlling Visual Studio

## Overview

Use the least fragile control surface that can answer the Visual Studio request:

```text
Tier 1: CLI/file tools -> Tier 2: EnvDTE/DTE API -> Tier 3: Computer Use
```

Try shell, file, and build tools first. If the task depends on a running Visual Studio IDE state that CLI cannot observe or change reliably, use the EnvDTE automation scripts. Use Computer Use only when the task depends on pixels, modal dialogs, designer surfaces, or other transient GUI state that DTE cannot expose.

If the user restricts the control surface, obey that restriction even when another tier would be faster.

## Tiered Escalation

```text
Start
  |
  |-- Can this be answered by files, CLI build/test tools, logs, or config?
  |     Use Tier 1.
  |
  |-- Does it require the running Visual Studio IDE but not visual inspection?
  |     Use Tier 2 with EnvDTE/DTE.
  |
  |-- Does it require modal UI, designers, extension-specific panes, installer UI,
        screenshots, or inaccessible transient state?
        Use Tier 3 with Computer Use.
```

| Need | Tier 1: CLI/file tools | Tier 2: EnvDTE/DTE API | Tier 3: Computer Use gate |
|---|---|---|---|
| Locate VS, MSBuild, devenv | `scripts/find_vs.ps1`, `vswhere`, known tool paths | Not needed | Only if installer UI must be inspected |
| Build/test from source | `scripts/vs_build.ps1`, `msbuild`, `dotnet`, `cmake`, `ctest` | Build active IDE solution/configuration when CLI cannot match VS state | Only if build failure is visible only in IDE UI |
| Inspect solution/project files | Read `.sln`, project, props, targets, presets, package files | Enumerate loaded projects/references in the active IDE when load state matters | Only for Solution Explorer visual state |
| Active VS configuration, startup project, commands | Infer from files when reliable | Query or change active solution state, run `dte.ExecuteCommand(...)` | Only for UI-only selectors or blocked commands |
| Output Window, Error List, Task List | Prefer saved logs and CLI output | Read IDE panes through DTE; enumerate pane names with `output-panes`; clear panes with `clear-output` | Only if DTE cannot read the pane or a custom tool window is involved |
| Debugger state, breakpoints, stepping | Use logs/tests for deterministic repro | Query mode, list/set/remove breakpoints, start/stop/step through DTE | Only for visual debugger UI, data tips, or expression windows DTE cannot access |
| Debugger threads and modules | N/A | List/switch threads with `list-threads`/`set-active-thread`; inspect loaded modules with `list-modules` | Only for visual thread or module windows |
| Documents and editor state | Edit files directly with normal tools | Open/save documents, read dirty document text with `get-text`, find/replace with `replace-text` | Only for unsaved editor state or prompts |
| Solution build configurations | Read `.sln` and project files | Query/change active config with `get-active-config`/`set-active-config`; manage startup project with `get-startup-projects`/`set-startup-project` | Only for UI-only selectors |
| Extension management | `scripts/vs_extensions.ps1` to list, install, uninstall | N/A | Only for installer UI or Marketplace browsing |
| Modal dialogs, property pages, designers, trust/sign-in/install prompts | Avoid unless represented in files | Try DTE command/state first if non-visual | Computer Use, with confirmation for mutating prompts |

## Bundled Resources

- `scripts/find_vs.ps1`: Locate installed Visual Studio instances, `devenv.exe`, and `MSBuild.exe` with `vswhere` and Setup Configuration API fallback.
- `scripts/vs_build.ps1`: Run headless MSBuild builds and emit parsed diagnostics.
- `scripts/vs_dte.ps1`: Connect to running Visual Studio DTE instances and perform common IDE operations.
- `scripts/vs_extensions.ps1`: List installed extensions, install from `.vsix`, or uninstall by extension ID.
- `references/envdte-api.md`: Read when using DTE automation or adding a DTE operation.
- `references/vs-cli-tools.md`: Read when locating tools, choosing `msbuild` vs `devenv` vs `dotnet`, or debugging CLI build parity.

These PowerShell scripts are intended for Windows hosts with Visual Studio installed. On non-Windows hosts, treat them as reference implementations and use file/CLI inspection available in the current environment.

## Tier 1: CLI/File Workflow

Use shell/CLI when the request benefits from complete, repeatable output:

1. Locate tooling with `scripts/find_vs.ps1`, `vswhere`, Developer PowerShell environment commands, or known install paths.
2. Build `.sln`, `.csproj`, or `.vcxproj` with `scripts/vs_build.ps1` or `msbuild`.
3. Build .NET SDK projects with `dotnet build` and test with `dotnet test` when that matches the project.
4. Build CMake projects with `cmake -S`, `cmake --build`, `ctest`, and `CMakePresets.json` when present.
5. Inspect C++ toolchain issues with compiler/linker output, Windows SDK paths, include/library paths, NuGet, and package managers such as `vcpkg`.
6. Use `rg`/`git grep` and structured file inspection for `.sln`, project files, `.props`, `.targets`, `CMakeLists.txt`, `CMakePresets.json`, and launch/config files.

When CLI output disagrees with Visual Studio, compare the active VS solution configuration, platform, startup project, CMake preset/configuration, environment, working directory, and property inheritance.

## Tier 2: EnvDTE/DTE Workflow

Use EnvDTE when the active Visual Studio instance matters and the task can be expressed through the automation object model:

1. Confirm the task is not solvable by Tier 1 alone.
2. Confirm Visual Studio is running in the same Windows desktop session.
3. Use `scripts/vs_dte.ps1 -Action list-instances` to identify running DTE instances.
4. Select an instance by solution path, process id, or ProgID when more than one instance is running.
5. Run the smallest DTE operation that answers the request: `status`, `list-projects`, `output`, `error-list`, `task-list`, `debug-state`, `list-breakpoints`, `attach-process`, `build`, `list-commands`, or `execute-command`.
6. For mutating actions such as adding/removing breakpoints, running commands, saving documents, or starting/stopping debugging, require clear user intent.
7. If DTE is blocked by a modal dialog, custom designer, extension pane, or unavailable COM object, escalate to Tier 3.

Common ProgIDs:

- Visual Studio 2022: `VisualStudio.DTE.17.0`
- Visual Studio 2019: `VisualStudio.DTE.16.0`
- Visual Studio 2017: `VisualStudio.DTE.15.0`

Read `references/envdte-api.md` before extending DTE behavior.

## Tier 3: Computer Use Workflow

Use Computer Use only for Visual Studio state that cannot be obtained safely through Tier 1 or Tier 2:

1. Use the `computer-use` skill first and bootstrap the Windows connection exactly as it says.
2. Run `list_apps`, select the Visual Studio app/window returned by the tool, then inspect the window state.
3. Prefer passive inspection before clicking. Use screenshots and bounded accessibility excerpts to understand current state.
4. Refresh accessibility after any action that changes focus, layout, tabs, tree expansion, or modal state.
5. If Visual Studio shows a prompt that can modify files, settings, packages, credentials, workloads, or projects, pause and decide whether confirmation is required.
6. If a popup asks to normalize line endings, reload, save, trust, install, update, sign in, or repair, do not accept by default. Explain the prompt and choose the non-mutating option unless the user requested the change.
7. Do not use Computer Use to automate terminals, Windows Run, Start menu search, or shell commands.

## Build And Debug Triage

For build or compile problems:

1. Get the full error text. Prefer Tier 1 logs; use DTE Output/Error List if the issue is IDE-only.
2. Identify active configuration and platform (`Debug`/`Release`, `x64`/`Win32`, CMake preset, startup target).
3. Separate code errors from environment/configuration errors: missing include/lib, SDK/toolset, package restore, wrong working directory, stale generated files, linker inputs, runtime DLL path.
4. Prefer a reproducible CLI command before editing code. If the user forbids shell access, use DTE or Computer Use based on the allowed surface.
5. After a fix, verify through the same surface where the failure appeared. If the failure was in VS, verify through DTE or VS; if it was CLI/CI, verify by command.

For debugger or runtime problems:

- Use DTE for debugger mode, breakpoints, stepping, call stack, current frame, and expression evaluation when possible.
- Use `attach-process -TargetPid <pid> -Engine native` for an already-running native process; the script maps `native` to the stable Visual Studio native-engine GUID so localized engine names do not matter.
- Use `continue` with `-Wait` when the next breakpoint or process exit must be observed synchronously.
- Use shell/CLI for logs, tests, deterministic repro commands, and source edits.
- Use Computer Use only for visual debugger affordances that DTE cannot expose.
- Avoid changing breakpoints, run state, or exception settings unless the user asked for debugging actions.

## Safety Rules

- Do not claim current Visual Studio state from file inspection alone. Use DTE or Computer Use when the user asks what VS currently shows or has loaded.
- Do not claim complete code understanding from a screenshot alone. Say when conclusions are based only on visible files/tabs.
- Do not save, normalize, reload, install, update, trust, sign in, or change settings through Visual Studio without user intent or required confirmation.
- Do not bypass security prompts, automate credentials, or accept permission prompts unless the user explicitly approved the exact action.
- Do not mix direct Windows UI automation scripts with Computer Use in the same turn.
- Prefer DTE over screen scraping for repeatable IDE operations, but stop and escalate when DTE is blocked by UI or extension-specific behavior.

## Code Editing Policy

Edit source files directly with file tools. Do not use DTE text manipulation for routine code changes. DTE text operations (`get-text`, `replace-text`) are reserved for:

- Files that have unsaved changes in the VS editor where a disk edit would conflict with the editor state.
- Operations that depend on VS editor state such as the current selection or active document.

When a file is open in VS and has unsaved changes, prefer asking the user to save or discard before editing on disk, rather than switching to DTE text APIs.

## CLI-First Operations

These operations should always use CLI, never DTE:

- `dotnet build`, `dotnet restore`, `dotnet test`, `dotnet add package` for .NET SDK projects.
- `tasklist`, `taskkill` for process management.
- `scripts/vs_extensions.ps1` or `VSIXInstaller.exe` for extension installation from a `.vsix` file.

DTE equivalents exist but are slower and require VS to be running. Use DTE only when the task depends on the live IDE state that CLI cannot observe.

## Response Pattern

When reporting back, state:

- Which tier was used: CLI/file tools, EnvDTE/DTE, Computer Use, or a combination.
- What was observed or changed.
- What remains uncertain because it was not visible or not inspected.
- How verification was performed, or why it could not be performed.
