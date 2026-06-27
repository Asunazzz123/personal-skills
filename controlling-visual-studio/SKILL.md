---
name: controlling-visual-studio
description: Use when Codex needs to inspect, configure, debug, build, or explain Microsoft Visual Studio projects, solutions, CMake workspaces, IDE settings, project properties, build errors, debugger state, toolchain issues, or Visual Studio GUI-only behavior, especially when deciding between Computer Use and shell/CLI control.
---

# Controlling Visual Studio

## Overview

Use the least fragile control surface that can answer the Visual Studio request. Prefer CLI and file analysis for repeatable build/code work; use Computer Use for IDE state, GUI settings, project property pages, debugger windows, popups, and anything visible only inside Visual Studio.

## First Decision

Before acting, classify the request:

| Request | Preferred control |
|---|---|
| Inspect current VS screen, open tabs, Error List, Output, debugger panes, popups | Computer Use |
| Change Visual Studio options, project properties, startup item, CMake configuration UI, Python environment selector | Computer Use |
| Build/test from source, parse long logs, inspect symbols/references, edit code or config files | Shell/CLI plus file tools |
| Reproduce an IDE-only failure, then fix code/config | Computer Use for observation, shell/CLI for diagnosis and fix |
| User explicitly says only Computer Use or only GUI | Computer Use only; do not read project files or use shell to inspect them |
| User explicitly says only shell/CLI | Shell/CLI only; do not automate Visual Studio GUI |

If the user restricts the control surface, obey that restriction even when another route would be faster.

## Computer Use Workflow

When using Computer Use with Visual Studio:

1. Use the `computer-use` skill first and bootstrap the Windows connection exactly as it says.
2. Run `list_apps`, select the Visual Studio app/window returned by the tool, then `get_window` and optionally `activate_window`.
3. Capture the window with `get_window_state`; request accessibility text only when it helps choose the next action.
4. Prefer passive inspection before clicking. Use screenshots and bounded accessibility excerpts to understand current state.
5. For Explorer tree items, tabs, menus, and modal dialogs, refresh accessibility after any action that changes focus or layout before using element indexes again.
6. If Visual Studio shows a prompt that can modify files, settings, packages, credentials, workloads, or projects, pause and decide whether confirmation is required.
7. If a popup asks to normalize line endings, reload, save, trust, install, update, sign in, or repair, do not accept by default. Explain the prompt and choose the non-mutating option unless the user requested the change.
8. Do not use Computer Use to automate terminals, Windows Run, Start menu search, or shell commands.

## Shell/CLI Workflow

Use shell/CLI when the request benefits from complete, repeatable output:

- Locate Visual Studio tooling with `vswhere` or known Developer PowerShell environment commands.
- Build `.sln` or `.vcxproj` with `msbuild` or `devenv /Build` when appropriate.
- Build CMake projects with `cmake -S`, `cmake --build`, `ctest`, and `CMakePresets.json` when present.
- Build .NET projects with `dotnet build` and test with `dotnet test`.
- Inspect C++ toolchain issues with `cl`, linker output, Windows SDK paths, include/library paths, and package managers such as `vcpkg` or NuGet.
- Use `rg`/`git grep` for code search and structured file inspection for `.sln`, `.vcxproj`, `.props`, `.targets`, `CMakeLists.txt`, and `CMakePresets.json`.

When shell/CLI output disagrees with Visual Studio, inspect the active VS configuration: solution configuration, platform, startup item, CMake preset/configuration, environment, working directory, and project property inheritance.

## Build And Debug Triage

For build or compile problems:

1. Get the full error text. Use Visual Studio Output/Error List if the issue is IDE-only; otherwise use CLI build logs.
2. Identify active configuration and platform (`Debug/Release`, `x64/Win32`, CMake preset, startup target).
3. Separate code errors from environment/configuration errors: missing include/lib, SDK/toolset, package restore, wrong working directory, stale generated files, linker inputs, runtime DLL path.
4. Prefer a reproducible CLI command before editing code. If the user forbids shell access, use Visual Studio Output/Error List and visible project properties instead.
5. After a fix, verify through the same surface where the failure appeared. If the failure was in VS, verify in VS; if it was CLI/CI, verify by command.

For debugger or runtime problems:

- Use Computer Use for breakpoints, Call Stack, Locals, Watch, Output, Exception Settings, and visual debugger state.
- Use shell/CLI for logs, tests, deterministic repro commands, and source edits.
- Avoid changing breakpoints, run state, or exception settings unless the user asked for debugging actions.

## Settings And Project Properties

Use Computer Use for settings that are difficult to infer from files or depend on Visual Studio UI state:

- Project Properties pages, C/C++ include paths, linker paths, debug command arguments, working directory, environment fields.
- Visual Studio Options, extension settings, Python environments, CMake Settings UI, startup item selection.
- Installer/workload/component inspection.

When a setting is stored in version-controlled files (`.vcxproj`, `.props`, `.targets`, `CMakePresets.json`, `launch.vs.json`), prefer editing the file directly unless the user specifically wants GUI interaction or the location is unclear.

## Safety Rules

- Do not claim Visual Studio state from file inspection alone. If the user asks what VS currently shows, use Computer Use.
- Do not claim complete code understanding from a screenshot alone. Say when conclusions are based only on visible files/tabs.
- Do not save, normalize, reload, install, update, trust, sign in, or change settings through Visual Studio without user intent or required confirmation.
- Do not bypass security prompts, automate credentials, or accept permission prompts unless the user explicitly approved the exact action.
- Do not mix direct Windows UI automation scripts with Computer Use in the same turn.

## Response Pattern

When reporting back, state:

- Which control surface was used: Computer Use, shell/CLI, or both.
- What was observed or changed.
- What remains uncertain because it was not visible or not inspected.
- How verification was performed, or why it could not be performed.
