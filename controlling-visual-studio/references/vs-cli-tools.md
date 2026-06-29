# Visual Studio CLI Tools Reference

Use this reference for Tier 1 work: locating Visual Studio, building from the command line, reproducing IDE builds without screen scraping, and comparing CLI output to active Visual Studio state.

## Official References

- Detecting and managing Visual Studio instances: https://learn.microsoft.com/en-us/visualstudio/install/tools-for-managing-visual-studio-instances?view=vs-2022
- vswhere repository: https://github.com/microsoft/vswhere
- MSBuild command-line reference: https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild-command-line-reference?view=vs-2022
- `devenv /Build`: https://learn.microsoft.com/en-us/visualstudio/ide/reference/build-devenv-exe?view=vs-2022
- Visual Studio command-line parameter index: https://learn.microsoft.com/en-us/visualstudio/ide/reference/visual-studio-command-line-switches?view=vs-2022

## Locate Visual Studio

Prefer `scripts/find_vs.ps1`:

```powershell
.\scripts\find_vs.ps1
.\scripts\find_vs.ps1 -Latest -RequireMsBuild -Format table
.\scripts\find_vs.ps1 -Latest -RequireMsBuild -Format path
```

Direct `vswhere` examples:

```powershell
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -all -products * -format json
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.Component.MSBuild -find "MSBuild\**\Bin\MSBuild.exe"
```

Use Setup Configuration COM fallback when `vswhere.exe` is unavailable. The helper script does this automatically.

## Choose The Build Tool

| Project shape | Prefer | Notes |
|---|---|---|
| `.sln`, legacy `.csproj`, `.vcxproj`, mixed native/managed solution | `MSBuild.exe` | Best default for Visual Studio parity and CI-style diagnostics. |
| SDK-style .NET solution/project | `dotnet build`, `dotnet test` | Use when the repo already uses .NET CLI and does not depend on VS-only targets. |
| CMake workspace | `cmake --build`, `ctest` | Use `CMakePresets.json` when present. |
| IDE command parity required | `devenv /Build` or DTE | Use sparingly; `devenv` is heavier and less parseable than MSBuild. |
| Current running IDE state required | `scripts/vs_dte.ps1` | Tier 2, not headless CLI. |

## MSBuild

Prefer `scripts/vs_build.ps1` for agent work because it finds MSBuild and emits parsed diagnostics:

```powershell
.\scripts\vs_build.ps1 C:\src\App\App.sln -Configuration Debug -Platform x64
.\scripts\vs_build.ps1 C:\src\App\App.sln -Target Rebuild -Configuration Release -Platform "Any CPU" -LogPath .\build.log
.\scripts\vs_build.ps1 C:\src\App\App.vcxproj -Configuration Debug -Platform Win32 -Verbosity normal
```

Direct MSBuild pattern:

```powershell
& $msbuild C:\src\App\App.sln /t:Build /p:Configuration=Debug /p:Platform=x64 /m /nologo /v:minimal /clp:Summary
```

Useful switches:

- `/t:<target>`: `Build`, `Rebuild`, `Clean`, `Restore`, or project-specific targets.
- `/p:Configuration=<name>` and `/p:Platform=<name>`: match Visual Studio active configuration/platform.
- `/m`: parallel build.
- `/restore`: restore before build for supported project types.
- `/bl[:path]`: binary log for deeper diagnosis.
- `/v:<level>`: `quiet`, `minimal`, `normal`, `detailed`, or `diagnostic`.
- `/clp:Summary`: include error/warning summary.

MSBuild diagnostic lines are usually parseable as:

```text
path\file.cpp(10,5): error C2065: message
path\file.cs(12,18): warning CS8602: message
error MSB1009: message
```

## dotnet CLI

Use for SDK-style .NET projects when it matches the repo workflow:

```powershell
dotnet restore C:\src\App\App.sln
dotnet build C:\src\App\App.sln -c Debug
dotnet test C:\src\App\App.Tests\App.Tests.csproj -c Debug --no-build
```

If `dotnet build` succeeds but Visual Studio fails, compare:

- Target framework and SDK selection.
- Solution configuration/platform.
- User-specific `.suo`/launch state.
- Visual Studio-only targets, workloads, analyzers, and design-time build settings.

## .NET Project File Audit

Use `scripts/audit_dotnet_project.ps1` before changing source when errors point to missing namespaces/types, unresolved references, package restore, target framework mismatch, or platform mismatch:

```powershell
.\scripts\audit_dotnet_project.ps1 C:\src\App\App.csproj
.\scripts\audit_dotnet_project.ps1 C:\src\App\App.sln
```

Treat `.csproj` as the Visual Studio/MSBuild project configuration file for C# and .NET projects, not as a domain-specific code file. The same audit pattern applies to desktop apps, Web APIs, internal tools, experiment or instrument data tools, and mixed managed/native projects.

Check these fields first:

- Project style: SDK-style uses `<Project Sdk="...">`; legacy projects usually rely on imported MSBuild targets.
- Targeting: `TargetFramework`, `TargetFrameworks`, `TargetFrameworkVersion`, `OutputType`, `UseWindowsForms`, and `UseWPF`.
- Dependencies: `PackageReference`, `packages.config`, `ProjectReference`, and assembly `Reference` entries.
- Reference paths: `HintPath` existence, unresolved MSBuild properties, duplicate references, and version conflicts.
- Interop/copy behavior: `SpecificVersion`, `Private`/Copy Local, and `EmbedInteropTypes`.
- Platform/runtime: `PlatformTarget`, `Prefer32Bit`, `RuntimeIdentifier`, `RuntimeIdentifiers`, and conditional `PropertyGroup` settings such as `Debug|x86` or `Release|x64`.
- External inputs: `Directory.Build.props`, `Directory.Build.targets`, `NuGet.Config`, imported `.props`/`.targets`, generated files, and design-time build artifacts.

Diagnostic mapping:

| Error family | First project-file checks |
|---|---|
| `CS0234`, `CS0246` | Missing assembly/package/project reference, wrong target framework, stale generated code, or missing using after reference validation |
| `MSB3245` | Unresolved assembly reference, broken `HintPath`, missing SDK/workload, or conditional reference not active |
| `MSB3270` | `PlatformTarget`, `Prefer32Bit`, native dependency architecture, or active solution platform mismatch |
| `NU110x` | Package source, version range, restore state, central package management, or `NuGet.Config` |
| `NETSDK*` | SDK selection, target framework support, runtime identifier, workload, or `global.json` |

## devenv

Use `devenv` only when MSBuild cannot reproduce the IDE behavior or a Visual Studio command-line switch is specifically required:

```powershell
& $devenv C:\src\App\App.sln /Build "Debug|x64"
& $devenv C:\src\App\App.sln /Rebuild "Release|Any CPU"
& $devenv C:\src\App\App.sln /Clean "Debug|Win32"
```

Notes:

- `devenv` may require a full Visual Studio install, not Build Tools only.
- Output is less structured than MSBuild output.
- Some operations may open UI or depend on user profile state.

## CMake

Use CMake presets when present:

```powershell
cmake --list-presets
cmake --preset windows-debug
cmake --build --preset windows-debug
ctest --preset windows-debug
```

Without presets:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Debug
ctest --test-dir build -C Debug
```

If Visual Studio CMake output differs from CLI output, inspect the active CMake preset/configuration, environment, kit/toolset, cache variables, and working directory.

## Compare CLI To Visual Studio

When command-line and IDE results disagree, check these in order:

1. Configuration and platform.
2. Startup project or startup item.
3. Target framework, Windows SDK, toolset, and workload availability.
4. NuGet/package restore state.
5. Project property inheritance from `.props`, `.targets`, `Directory.Build.props`, and `Directory.Build.targets`.
6. Environment variables and working directory.
7. Generated files, design-time build artifacts, and stale intermediates.
8. DTE-visible active IDE state if the mismatch remains.

Escalate from Tier 1 to Tier 2 when the active Visual Studio state is the likely difference. Escalate to Tier 3 only when a modal dialog, custom UI, or visual designer state blocks programmatic inspection.
