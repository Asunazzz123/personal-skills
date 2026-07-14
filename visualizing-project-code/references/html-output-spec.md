# HTML Output Specification

The source-code explanation must include at least one zoomable HTML artifact. Use `assets/project-code-map-template.html` as the structural starting point and replace its sample data with inspected repository evidence.

## Layout Requirements

Match the stable three-column reading layout:

- Top header: title, subtitle, branch/commit/generated time/case metadata.
- Left sidebar: language switcher, view selector, search box, filters, fit/reset controls, artifact links.
- Center stage: graph card with title bar, legend, pan/zoom canvas, and stable dimensions.
- Right sidebar: selected node/interface details, tags, inputs/outputs, invariants, evidence.
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

- `index.html`: overview, asset inventory, navigation.
- `case-path.html`: concrete runtime overlay.
- `interfaces.html`: interface surface and boundary map.
- `resources.html`: lifecycle/resource view.
- `deep-dive-<module>.html`: one page per complex module.

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
- Keep node labels readable and clipped/wrapped inside fixed-size nodes.
- Use color or border style to distinguish repo-owned assets, interfaces, external boundaries, case path, and risks.
- Keep arrowheads consistent with their edge semantics: case-path, boundary, risk, resource, and default arrows must inherit or explicitly match the line color.
- Route each edge to the nearest sensible node side (left/right/top/bottom) instead of assuming every target is to the right; arrowheads must stop at the node boundary.
- Keep nodes aligned to stable columns. For each adjacent column pair, derive one shared gap from the widest localized edge label crossing that boundary, plus label padding and at least 20px clearance on both sides; recompute after language changes without collapsing the layout during filtering.
- Mark inferred edges with dashed lines.
- Give edges a larger transparent hit target, a readable label background, and hover/selection feedback without changing graph layout.
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

- Inspect the HTML and confirm it contains non-placeholder repository data.
- Confirm language switching changes UI labels and localized node fields.
- Confirm left controls, center graph, and right details are present.
- Confirm zoom, pan, fit, reset, search, and filters are wired.
- Confirm all major nodes have `source_refs`.
- Confirm external systems are represented as boundaries or interfaces.
- Confirm complex modules have deep-dive sections or linked pages.
- Confirm the graph is readable at default zoom and useful when zoomed in.
- Confirm typed arrowheads have the same color as their lines, reverse/vertical edges attach to the correct node side, and wheel zoom stays centered on the pointer.
- Confirm adjacent columns use the longest crossing label as their spacing constraint, with every label background visibly separated from both nodes in Chinese and English.
