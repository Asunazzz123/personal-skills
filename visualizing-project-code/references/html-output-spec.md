# HTML Output Specification

The source-code explanation must include at least one zoomable HTML artifact. Use `assets/project-code-map-template.html` as the structural starting point and replace its sample data with inspected repository evidence.

## Output Directory Contract

Write all generated pages and supporting or intermediate artifacts beneath the target project root:

```text
<project>/.visualize_web/
├── index.html                 # default entry page
├── case-path.html             # optional focused views
├── interfaces.html
├── resources.html
├── deep-dive-<module>.html
├── assets/                    # optional generated CSS, JS, images, or fonts
└── data/                      # optional graph data, ledgers, manifests, or analysis JSON
```

- Create `.visualize_web/` when it does not exist and update it in place when it does.
- Keep all generated relative links inside `.visualize_web/` so the directory is portable as one unit.
- Put standalone CSS/JavaScript and analysis intermediates in `assets/` or `data/`; a single-file build may inline them into `index.html`.
- Do not copy generated output into the skill's own `assets/` directory; that directory contains reusable source templates.
- Preserve unrelated existing files and never delete or replace the whole `.visualize_web/` directory.
- Use another output location only when the user explicitly requests it.

## Layout Requirements

Match the stable three-column reading layout:

- Top header: title, subtitle, branch/commit/generated time/case metadata.
- Left sidebar: language switcher, view selector, search box, filters, fit/reset controls, artifact links.
- Center stage: graph card with title bar, legend, pan/zoom canvas, and stable dimensions.
- Right sidebar: selected node/interface details plus the currently hovered or pinned edge relation, tags, inputs/outputs, invariants, evidence.
- Background: light warm beige. Panels remain high-contrast white/off-white.
- Mobile: stack header, controls, graph, details without overlapping.

## Bilingual Requirements

- UI chrome must support `zh` and `en`.
- Put display strings under `i18n.zh` and `i18n.en`.
- Nodes may use `{ zh, en }` labels/details or language-neutral identifiers.
- The language selector must update title, sidebar labels, graph title, details labels, buttons, and placeholder text without reloading.
- Missing localized node text may fall back to English, then raw value.

## Minimum Page Set

Small repositories can use one HTML file with multiple graph views. Large repositories should create:

- `.visualize_web/index.html`: overview, asset inventory, navigation.
- `.visualize_web/case-path.html`: concrete runtime overlay.
- `.visualize_web/interfaces.html`: interface surface and boundary map.
- `.visualize_web/resources.html`: lifecycle/resource view.
- `.visualize_web/deep-dive-<module>.html`: one page per complex module.

## Node Schema

Every node should carry enough source information to jump back into code.

```js
{
  id: "public-api-handler",
  label: { en: "Public API handler", zh: "公开 API 处理器" },
  symbol: "handleRequest",
  kind: "interface",
  assetType: "function",
  interfaceType: "public-api",
  layer: "service",
  phase: "core_execution",
  planes: ["control", "data"],
  resourceTypes: ["network", "runtime_state"],
  ownership: "repo-owned",
  source_refs: ["src/server.ts:88"],
  summaryShort: { en: "Validates and dispatches the request.", zh: "校验并分发请求。" },
  summary: { en: "Validates request and dispatches service call.", zh: "校验请求并分发服务调用。" },
  inputs: ["HTTP request"],
  outputs: ["HTTP response"],
  invariants: ["validated auth context"],
  risks: ["retry may duplicate side effect"],
  confidence: "high"
}
```

Use these `kind` values consistently:

| Kind | Meaning |
| --- | --- |
| `asset` | repository-owned code/data/state asset |
| `interface` | public, internal, native, network, config, or storage contract |
| `resource` | compute, memory, storage, network, runtime, lock, stream, worker |
| `boundary` | external system handoff |
| `runtime` | concrete case-path execution node |
| `state` | state machine state or lifecycle stage |
| `risk` | invariant, failure mode, security, consistency, numeric, lifecycle risk |

Recommended asset types: `module`, `class`, `struct`, `function`, `config`, `schema`, `state`, `cache`, `queue`, `registry`, `kernel`, `pass`, `adapter`, `artifact`.

Recommended interface types: `public-api`, `cli`, `config`, `native-binding`, `rpc`, `http`, `queue`, `file-format`, `database`, `plugin-hook`, `memory-layout`, `external-library`.

`summaryShort` is an optional authored preview. Fall back to `summary` when it is absent. Render only the preview inside the graph; keep the complete `summary` and ledger fields in the right sidebar.

## Edge Schema

```js
{
  from: "public-api-handler",
  to: "service-core",
  kind: "calls",
  label: { en: "dispatches", zh: "分发" },
  dependency: "validated input",
  inferred: false
}
```

Recommended edge kinds: `calls`, `creates`, `owns`, `reads`, `writes`, `dispatches`, `awaits`, `schedules`, `returns`, `data-flow`, `model-flow`, `control-flow`, `resource-lifecycle`, `boundary-call`, `external_call`, `case_path`, `risk-edge`.

## Visual Requirements

- Include language, view, search, filters, fit, reset, zoom in, zoom out.
- Support drag-to-pan and wheel/button zoom.
- Keep graph card dimensions stable; node hover/selection must not resize the layout.
- Keep every node fixed-size. Fit the title to one line by measured pixel width, wrap `summaryShort` or `summary` to at most two measured lines, add an ellipsis when truncated, and enforce an SVG clip path as a final overflow guard.
- Never expand a node to fit prose. Display the complete summary, inputs, outputs, invariants, risks, and source references in the right sidebar after selection.
- On dense graphs, do not render persistent edge-label text on the canvas. Add a transparent 14–18 px hit path over each visible edge, highlight the hovered edge, and display `source → target` plus the localized relation label in a dedicated right-sidebar relation card.
- Allow clicking an edge to pin or unpin its right-sidebar relation card. Stop edge pointer events from starting canvas drag, and clear a pinned relation if filtering removes either endpoint.
- Preserve each relation label in an SVG `<title>` or equivalent accessible text even when it is not permanently visible.
- Use color or border style to distinguish repo-owned assets, interfaces, external boundaries, case path, and risks.
- Keep arrowheads consistent with their edge semantics: case-path, boundary, risk, resource, and default arrows must inherit or explicitly match the line color.
- Route each edge to the nearest sensible node side (left/right/top/bottom) instead of assuming every target is to the right; arrowheads must stop at the node boundary.
- Keep nodes aligned to stable columns. For each adjacent column pair, derive one shared gap from node geometry and the widest localized relation crossing that boundary; recompute after language changes without collapsing the layout during filtering.
- Mark inferred edges with dashed lines.
- Give edges a larger transparent hit target, accessible relation text, and hover/selection feedback without changing graph layout.
- Display selected-node details in the right sidebar.
- Display controls in the left sidebar.
- Prefer multiple focused views over one unreadable mega-graph.

## Writing Requirements

The HTML should answer:

- What case is being traced?
- What code assets does this repository own?
- What interfaces does it expose or consume?
- Which assets are crossed by the selected runtime case?
- Which resources and lifecycles does it manage?
- Where are external boundaries and contracts?
- What invariants and failure modes matter?
- Which modules need second-level explanation?

## Verification Checklist

Before finishing:

- Confirm every generated page, visual asset, graph-data file, ledger, and manifest is contained under `<project>/.visualize_web/` and that `index.html` is the default entry.
- Inspect the HTML and confirm it contains non-placeholder repository data.
- Confirm language switching changes UI labels and localized node fields.
- Confirm left controls, center graph, and right details are present.
- Confirm zoom, pan, fit, reset, search, and filters are wired.
- Confirm all major nodes have `source_refs`.
- Confirm external systems are represented as boundaries or interfaces.
- Confirm complex modules have deep-dive sections or linked pages.
- Test a long mixed Chinese/English node summary: the node must remain fixed-size, show no more than two preview lines, and expose the full text in the right sidebar.
- Test multiple converging and crossing edges: no persistent relation text may overlap the graph; hover and click-to-pin must show exactly one relation in the right sidebar.
- Confirm the graph is readable at default zoom and useful when zoomed in.
- Confirm typed arrowheads have the same color as their lines, reverse/vertical edges attach to the correct node side, and wheel zoom stays centered on the pointer.
- Confirm adjacent columns retain clearance for the longest localized relation in Chinese and English while persistent relation text remains off the canvas.
