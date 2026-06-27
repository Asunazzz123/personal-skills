# Rename Project Code Visualization Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the generalized visualization skill and its reusable HTML template from AI-infrastructure-specific identifiers to project-code identifiers.

**Architecture:** Perform a hard Git rename so the directory name, skill frontmatter, invocation token, and template filename remain consistent. Preserve the reusable HTML structure while requiring generated pages to replace sample data with inspected repository evidence.

**Tech Stack:** Markdown, YAML, HTML/CSS/JavaScript, Git, Codex skill creator validator, Node.js, Python

---

### Task 1: Rename The Skill And Template

**Files:**
- Rename: `visualizing-ai-infra-code/` to `visualizing-project-code/`
- Rename: `visualizing-project-code/assets/ai-infra-code-map-template.html` to `visualizing-project-code/assets/project-code-map-template.html`
- Modify: `visualizing-project-code/SKILL.md`
- Modify: `visualizing-project-code/agents/openai.yaml`
- Modify: `visualizing-project-code/references/html-output-spec.md`

- [x] **Step 1: Run the stale-identifier check and verify it fails**

Run:

```bash
rg -n "visualizing-ai-infra-code|ai-infra-code-map-template\\.html" visualizing-ai-infra-code
```

Expected: matches in `SKILL.md`, `agents/openai.yaml`, and
`references/html-output-spec.md`.

- [x] **Step 2: Rename the skill directory and HTML template**

Run:

```bash
git mv visualizing-ai-infra-code visualizing-project-code
git mv visualizing-project-code/assets/ai-infra-code-map-template.html visualizing-project-code/assets/project-code-map-template.html
```

Expected: Git records the directory and template renames.

- [x] **Step 3: Update the skill identity and internal references**

Apply these exact substitutions:

```text
SKILL.md:
name: visualizing-project-code
assets/project-code-map-template.html

agents/openai.yaml:
Use $visualizing-project-code to map this repository...

references/html-output-spec.md:
Use `assets/project-code-map-template.html` as the structural starting point.
```

Require generated pages to replace sample template data with inspected
repository evidence. Do not remove AI/ML or AI infrastructure domain-profile
guidance.

- [x] **Step 4: Run the stale-identifier check and verify it passes**

Run:

```bash
rg -n "visualizing-ai-infra-code|ai-infra-code-map-template\\.html" visualizing-project-code
```

Expected: exit status 1 with no matches.

### Task 2: Validate, Commit, And Publish

**Files:**
- Verify: `visualizing-project-code/SKILL.md`
- Verify: `visualizing-project-code/agents/openai.yaml`
- Verify: `visualizing-project-code/assets/project-code-map-template.html`
- Verify: `visualizing-project-code/references/html-output-spec.md`

- [x] **Step 1: Validate the renamed skill package**

Run:

```bash
conda run -n agent python /Users/asuna/.codex/skills/.system/skill-creator/scripts/quick_validate.py visualizing-project-code
```

Expected: `Skill is valid!`

- [x] **Step 2: Validate the HTML template and rename contract**

Run:

```bash
node -e '<parse inline scripts and assert bilingual three-panel markers>'
conda run -n agent python -c '<rename contract check>'
```

Expected: one valid inline script block; the renamed template is the only HTML
file; and all skill metadata and references use `visualizing-project-code` and
`project-code-map-template.html`.

- [x] **Step 3: Review the complete Git scope**

Run:

```bash
git diff --check
git status --short
git diff --stat HEAD
```

Expected: only the skill/template renames, identifier/reference edits, design
update, and this plan document are present; no whitespace errors.

- [ ] **Step 4: Commit with the required co-author trailer**

Run:

```bash
git add visualizing-project-code visualizing-ai-infra-code docs/superpowers/plans/2026-06-27-rename-project-code-visualization-skill.md
git commit -m "Rename project code visualization skill" -m "Co-authored-by: Codex <codex@openai.com>"
```

Expected: one implementation commit containing the hard rename and updated
identifiers.

- [ ] **Step 5: Rebase safely if the remote advanced, then push**

Run:

```bash
git fetch origin main
git rebase origin/main
git push origin main
```

Expected: `main` pushes without force and local `HEAD` equals `origin/main`.
