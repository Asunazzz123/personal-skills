# Controlling Visual Studio

A Codex skill for inspecting, building, and debugging Visual Studio projects on Windows.

It uses the least fragile control surface available:

1. CLI and project files for repeatable builds and diagnostics.
2. EnvDTE automation for the active Visual Studio instance.
3. Computer Use (Codex plugin needed) only when a task depends on Visual Studio UI state.

## Included scripts

- `scripts/find_vs.ps1` — locate Visual Studio, MSBuild, and `devenv.exe`.
- `scripts/vs_build.ps1` — build solutions and projects and return structured diagnostics.
- `scripts/vs_dte.ps1` — inspect and control running Visual Studio instances through EnvDTE.

See `SKILL.md` for the complete workflow and safety rules.
