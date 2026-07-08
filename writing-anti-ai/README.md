# Writing Anti-AI

`writing-anti-ai` is a Codex skill for revising English and Chinese prose that sounds AI-generated. It focuses on removing formulaic phrasing, inflated significance, vague attribution, promotional language, repetitive rhythm, and common "humanize this text" artifacts while preserving meaning and factual claims.

## Contents

- `SKILL.md`: Codex skill instructions and trigger description.
- `agents/openai.yaml`: Codex UI metadata and implicit invocation policy.
- `references/`: English and Chinese pattern references plus phrase lists.
- `examples/`: Before/after rewrite examples.
- `.codex/`: Optional Codex hook package that suggests this skill from matching prompts.

## Install The Skill

Install the skill into your Codex skills directory:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
target="$CODEX_HOME/skills/writing-anti-ai"
rm -rf "$target"
cp -R writing-anti-ai "$target"
```

This replaces any older installed copy of the same skill.

After installation, invoke it explicitly with `$writing-anti-ai`, or let Codex choose it when the prompt matches the skill description.

## Migrate The Bundled `.codex` Hook To `~/.codex`

The bundled `.codex` directory is not active while it stays inside the skill folder. To enable the prompt hook globally, copy its script and merge its config into your user Codex config layer.

Copy the hook script:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/hooks"
cp writing-anti-ai/.codex/hooks/suggest_writing_anti_ai.py "$CODEX_HOME/hooks/suggest_writing_anti_ai.py"
chmod +x "$CODEX_HOME/hooks/suggest_writing_anti_ai.py"
```

Enable hooks in `~/.codex/config.toml`. If the file does not exist, copy the bundled one:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
cp writing-anti-ai/.codex/config.toml "$CODEX_HOME/config.toml"
```

If `~/.codex/config.toml` already exists, merge this setting manually instead of overwriting the file:

```toml
[features]
hooks = true
```

Install the hook config. If `~/.codex/hooks.json` does not exist, copy the bundled file:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
cp writing-anti-ai/.codex/hooks.json "$CODEX_HOME/hooks.json"
```

If `~/.codex/hooks.json` already exists, merge this entry into `hooks.UserPromptSubmit`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CODEX_HOME:-$HOME/.codex}/hooks/suggest_writing_anti_ai.py\"",
            "timeout": 5,
            "statusMessage": "Checking writing-anti-ai trigger"
          }
        ]
      }
    ]
  }
}
```

## Hook Behavior

The hook listens to `UserPromptSubmit`. When a prompt contains terms such as `anti-ai`, `humanize`, `AI 写作`, `去 AI 痕迹`, `人性化处理`, or `机器味`, it adds Codex-visible context recommending `$writing-anti-ai`.

It does not block prompts, rewrite user text, or enforce policy. It only nudges Codex to load the skill when the prompt appears relevant.
