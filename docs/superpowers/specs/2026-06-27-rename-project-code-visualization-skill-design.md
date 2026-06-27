# Rename Project Code Visualization Skill

## Goal

Rename the generalized repository visualization skill from
`visualizing-ai-infra-code` to `visualizing-project-code` so its identity matches
its project-wide code asset, interface, boundary, resource, and runtime views.

## Scope

- Rename the skill directory to `visualizing-project-code`.
- Change the `SKILL.md` frontmatter name to `visualizing-project-code`.
- Change the invocation in `agents/openai.yaml` to
  `$visualizing-project-code`.
- Rename `assets/ai-infra-code-map-template.html` to
  `assets/project-code-map-template.html`.
- Update all internal references to the renamed template and require generated
  pages to replace its sample data with inspected repository evidence.
- Keep AI/ML and AI infrastructure guidance as an optional domain profile.

## Compatibility

This is a hard rename. The old `$visualizing-ai-infra-code` invocation and old
directory name will no longer exist. No compatibility alias will be added.

## Validation

- The skill creator validator passes for the renamed directory.
- The renamed HTML template's inline JavaScript parses successfully.
- The bilingual three-panel layout and light beige background markers remain.
- No stale `visualizing-ai-infra-code` or
  `ai-infra-code-map-template.html` identifiers remain in the renamed skill.
- Git records only the intended rename and metadata/reference updates.
