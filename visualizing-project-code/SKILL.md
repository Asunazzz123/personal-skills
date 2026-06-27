---
name: visualizing-project-code
description: Use when analyzing source code repositories for 源码理解, 源码可视化, code asset maps, interface visualization, architecture companion pages, API/boundary diagrams, runtime case overlays, resource lifecycle views, or complex module deep dives across AI infra, compilers, databases, backend systems, SDKs, libraries, and frameworks.
---

# Visualizing Code Assets And Interfaces

## Overview

Use this skill to turn a repository into a zoomable bilingual map of code assets, interfaces, boundaries, resources, and runtime case paths. Treat AI infrastructure as one domain profile, not the whole skill.

## Required Reads

Before analyzing a repository, read `references/analysis-framework.md`.

Before creating the visual artifact, read `references/html-output-spec.md` and use `assets/project-code-map-template.html` as the structural starting point. Replace its sample data with inspected repository evidence.

## Workflow

1. Start from one concrete case: CLI command, API request, test, example script, training step, inference request, compiler pass, DB query, scheduler tick, plugin hook, or operator invocation. If the user does not provide one, choose a representative case and state why.
2. Build an asset-interface ledger before drawing: modules, packages, classes, structs, functions, configs, schemas, state objects, caches, queues, registries, kernels, passes, adapters, protocols, and external dependencies.
3. For each important asset or interface, record owner, source references, inputs, outputs, invariants, lifecycle, mutability, dependencies, confidence, and failure modes.
4. Overlay the concrete case path on top of the ledger. Trace initialization, resource preparation, core execution, completion, teardown, and final externally visible state. Preserve async, background, multi-threaded, distributed, GPU, or event-driven behavior instead of flattening it into a sequential chain.
5. Mark boundaries explicitly: public API, CLI, config, schema, RPC/HTTP, queue, file format, database, OS/kernel, network, GPU/accelerator, native binding, plugin/hook, and upper-library calls. Summarize boundary contracts; do not deep dive into external systems unless the target repository owns them.
6. Add domain profiles only when useful:
   - AI/ML profile: data plane, model plane, control plane, resource lifecycle, numeric risk.
   - Compiler profile: source language, IR, pass pipeline, lowering, runtime ABI.
   - Backend/distributed profile: API, service, storage, queue, cache, consistency, retry.
   - Database/storage profile: query, plan, index, buffer, transaction, log, durability.
7. Add second-level deep dives for complex state machines, schedulers, partitioning, algorithms, protocol contracts, formula-to-code gaps, lifecycle-sensitive resources, or highly coupled modules.
8. Produce at least one direct visual HTML artifact with pan/zoom, stable three-column layout, left control sidebar, right node detail panel, light beige background, and Chinese/English display toggle.
9. Finish with a concise reading guide: selected case, generated HTML path, key assets, interfaces, resource abstractions, boundary handoffs, runtime risks, and unresolved uncertainties.

## Views To Produce

| View | Purpose | Required annotations |
| --- | --- | --- |
| Asset inventory | What the repo owns | owner, source, lifecycle, invariants, mutability |
| Interface surface | How users/systems touch it | contract, input, output, caller, boundary |
| Case path overlay | One executable path through assets | phases, sync/async edges, final state |
| Resource lifecycle | What is acquired and released | capacity, ownership, hidden lower layer |
| Boundary map | Where complexity is handed off | external system, API contract, error surface |
| Risk/invariant map | Where understanding can break | deadlock, precision, consistency, silent failure |
| Deep dive | Hard module explanation | state, transitions, algorithm mapping, side effects |

## Output Rules

- Make the HTML artifact useful before prose is read. The first screen should show controls, graph, and selected-node details.
- Use bilingual labels when possible. At minimum, UI chrome must support Chinese and English; node text may be bilingual or language-neutral identifiers.
- Use file/function references with line numbers after inspecting code.
- Use visual distinctions for owned assets, interfaces, external boundaries, runtime states, resources, risks, and selected case path.
- Support pan, zoom, reset, fit, search, and filters. Keep text readable and prevent node text from resizing the layout.
- Prefer multiple focused views over one unreadable mega-graph.
- Preserve uncertainty. Mark inferred edges and low-confidence nodes.

## Common Mistakes

- Drawing architecture first without building the asset-interface ledger.
- Treating public APIs, config contracts, and file formats as ordinary functions instead of interfaces.
- Hiding external boundaries, which conceals what this repository actually owns.
- Mixing static ownership, runtime flow, and risk annotations into one untyped arrow.
- Explaining external libraries instead of the local adapter/contract.
- Producing a static image only; the required deliverable includes zoomable HTML.
