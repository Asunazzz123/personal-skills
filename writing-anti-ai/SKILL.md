---
name: writing-anti-ai
description: Use when removing AI writing patterns, humanizing text, making prose sound natural, fixing robotic writing, or handling prompts such as anti-ai, humanize, AI-generated traces, 去除 AI 写作痕迹, 人性化处理, 让文字更自然, or 机器味. Supports English and Chinese prose.
---

# Writing Anti-AI

Remove detectable AI writing patterns while preserving the user's meaning, tone, and factual claims. Support both English and Chinese text.

## Required Reads

Choose references by language and task size:

- For English rewrites, read `references/patterns-english.md`.
- For Chinese rewrites, read `references/patterns-chinese.md`.
- For quick cleanup, read `references/phrases-to-cut.md`.
- For before/after calibration, read `examples/english.md` or `examples/chinese.md`.
- For source context, read `references/wikipedia-source.md`.

## Workflow

1. Identify the target language, audience, and desired tone from the user's text.
2. Scan for AI patterns: inflated significance, promotional adjectives, vague attributions, superficial analysis phrases, formulaic contrasts, rule-of-three phrasing, overused conjunctive openers, excessive bold text, and generic upbeat conclusions.
3. Replace vague claims with concrete facts when the source text provides them. Do not invent dates, numbers, citations, or named sources.
4. Cut filler before polishing. Prefer direct sentences over announcements about what the text is doing.
5. Break formulaic structure. Avoid "not just X, but Y", forced three-item lists, pull-quote endings, and dramatic dash reveals.
6. Vary rhythm. Mix short and longer sentences, but keep professional text clear and controlled.
7. Add human voice only when appropriate for the genre. Academic, legal, and technical prose should become clearer and more specific, not casual.
8. Preserve meaning. If the original contains uncertainty, keep the uncertainty without stacking hedges.
9. Return the revised text first unless the user asks for analysis. Add a short change note only when useful.

## Editing Rules

- Keep facts, terminology, and citations intact.
- Do not make the text more emotional unless the target voice calls for it.
- Do not over-correct into choppy sentence fragments.
- Replace vague attribution such as "experts believe" with a specific cited source only if one is present in the input.
- When evidence is missing, remove the claim or mark it as unsupported instead of fabricating support.
- For academic writing, prefer direct methods/results language over personality.

## Quick Checks

| Dimension | Ask |
| --- | --- |
| Directness | Does the sentence state the point, or announce that it will? |
| Specificity | Are there concrete facts where the original supports them? |
| Rhythm | Do adjacent sentences use different lengths and openings? |
| Trust | Does it avoid hand-holding, throat clearing, and generic reassurance? |
| Voice | Does it match the user's genre rather than generic assistant prose? |

## Common Rewrites

| Before | After |
| --- | --- |
| "serves as a testament to" | "shows" or a concrete fact |
| "It is important to note that" | Delete |
| "Moreover / Additionally" | Delete or use a plain transition |
| "It's not just X, it's Y" | State the relationship directly |
| "作为……的证明" | "表明" or a concrete fact |
| "值得注意的是" | Delete |
| "此外" | Delete or use a plain transition |
| "这不仅仅是……而是……" | Direct statement |

## Output Shape

For rewrite requests:

```text
[rewritten text]
```

For review requests:

```text
Score: X/50

Main issues:
- ...

Suggested rewrite:
...
```
