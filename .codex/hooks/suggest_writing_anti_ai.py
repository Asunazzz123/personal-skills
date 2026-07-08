#!/usr/bin/env python3
"""Suggest the writing-anti-ai Codex skill for matching prompts."""

from __future__ import annotations

import json
import re
import sys


TRIGGER_RE = re.compile(
    r"\b(anti[-\s]?ai|humanize|humanise)\b"
    r"|ai[-\s]?generated\s+traces?"
    r"|remove\s+ai\s+writing\s+patterns?"
    r"|robotic\s+writing"
    r"|make\s+(this|the\s+text|it)\s+sound\s+more\s+natural"
    r"|去\s*.*ai\s*.*痕迹"
    r"|ai\s*写作"
    r"|AI\s*写作"
    r"|人性化处理"
    r"|机器味"
    r"|像\s*AI",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or not TRIGGER_RE.search(prompt):
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": (
                    "The prompt appears to ask for removing AI writing patterns "
                    "or humanizing prose. Use $writing-anti-ai before editing; "
                    "load the language-specific reference file when needed."
                ),
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
