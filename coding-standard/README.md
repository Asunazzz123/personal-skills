# coding-standard

Portable Codex Skill containing the global Python coding standard.

## Install

Copy or symlink this folder to:

```text
$HOME/.agents/skills/coding-standard
```

On Windows, `$HOME` is the user profile directory. Restart Codex if the Skill
does not appear automatically.

## `AGENTS.md` template fragment

Add this fragment to `~/.codex/AGENTS.md`:

```md
## Python Coding Standard

- When creating, modifying, refactoring, or reviewing Python code, always
  invoke and follow `$coding-standard`.
- Repository-specific `AGENTS.md` instructions may extend or override this
  standard.
```

This is intentionally a template fragment, not a complete `AGENTS.md`. Merge it
into the existing file; do not overwrite other global instructions.

## Portability

Version the entire `coding-standard` folder in Git. On another machine, clone
the repository, copy or symlink the folder into `$HOME/.agents/skills`, and
merge the template fragment into that machine's `~/.codex/AGENTS.md`.
