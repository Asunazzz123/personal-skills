# Code Asset And Interface Analysis Framework

Use this reference to analyze repositories in any software domain: AI infra, compilers, databases, backend systems, SDKs, CLIs, libraries, frameworks, plugins, and operator/kernel projects.

## 1. Case-First Trace

Pick a case small enough to trace but rich enough to cross the main system boundary.

| Repository type | Good starting case |
| --- | --- |
| Backend service | one request from ingress to response and storage side effect |
| SDK/library | one public API call through adapter and implementation |
| CLI tool | one command from argument parse to output |
| Compiler/runtime | one source construct through IR, passes, lowering, runtime ABI |
| Database/storage | one query or write through planning, index/buffer/log, response |
| Scheduler/runtime | one task submission through placement, execution, completion |
| AI training framework | one training iteration from data batch to optimizer/checkpoint |
| AI inference serving | one request from API ingress to token/output stream |
| Kernel/operator library | one operator invocation through dispatch, launch, completion |

Record:

- Entry command, test, example, route, API, or hook.
- Main files and functions in order of first contact.
- Runtime phases: initialization, preparation, core execution, completion, cleanup, final state.
- Parallelism shape: threads, async tasks, worker pools, actors, event loops, queues, GPU streams, collectives, background jobs, or distributed services.
- What is directly observed versus inferred.

## 2. Asset-Interface Ledger

Build this ledger before drawing the graph.

### Code Assets

Assets are things the repository owns or materially defines:

| Asset type | Examples |
| --- | --- |
| module/package | package, namespace, crate, service folder |
| type | class, struct, dataclass, enum, trait, interface |
| function | method, handler, operator, kernel, compiler pass |
| state | cache, queue, registry, state machine, session, transaction |
| config/schema | config object, env var contract, JSON/YAML schema, DB schema |
| resource | file handle, socket, stream, worker, memory buffer, lock, device |
| artifact | checkpoint, index, compiled binary, generated file, log segment |

For each asset, capture:

- `name`, `assetType`, `layer`, `owner`.
- `source_refs`: file:line references.
- `inputs`, `outputs`, `sideEffects`.
- `lifecycle`: create/acquire, active use, mutation, share/transfer, release.
- `invariants`: shape, dtype, ordering, ownership, state constraints, schema.
- `dependencies`: local assets and external boundaries.
- `confidence`: high when directly confirmed; medium/low when inferred.

### Interfaces

Interfaces are how users, modules, or external systems touch assets:

| Interface type | Examples |
| --- | --- |
| public API | function export, SDK method, class constructor |
| CLI | command, flag, environment variable |
| config contract | config file, schema, feature flag |
| native binding | pybind, FFI, JNI, C ABI, plugin ABI |
| network contract | HTTP, RPC, websocket, queue message |
| storage contract | file format, database schema, object store path |
| hook/plugin | callback, lifecycle hook, registry extension point |
| memory/layout contract | tensor shape, buffer layout, binary format |

For each interface, capture:

- `interfaceType`, caller, callee, contract.
- Input/output shapes, schemas, ownership transfer, and error behavior.
- Version or compatibility constraints.
- Whether the repository owns the implementation or only adapts to an external system.

## 3. Runtime Overlay

Overlay the selected case on the asset ledger:

- Mark phase per node: `initialization`, `resource_preparation`, `core_execution`, `terminal_cleanup`, or domain-specific phase.
- Mark edge kind: `calls`, `creates`, `owns`, `reads`, `writes`, `dispatches`, `awaits`, `schedules`, `returns`, `external_call`, `error_path`, `case_path`.
- Distinguish synchronous control, asynchronous control, data movement, resource lifecycle, and ownership.
- Keep static structure and runtime path separable; the same asset can appear in multiple case overlays.

## 4. Boundary Lens

Mark boundaries because they define what the local repository does not own.

| Boundary | Record |
| --- | --- |
| OS/kernel | syscall intent, process/thread/file/socket/mmap behavior, cleanup |
| Network/protocol | transport, serialization, ordering, retry, delivery assumptions |
| Storage/database | consistency, atomicity, durability, indexes, transaction semantics |
| GPU/accelerator | stream/event/memcpy/kernel launch, driver/runtime API, async errors |
| Native binding | ABI, memory ownership, exception conversion, build artifact |
| Upper library | imported API, expected contract, data shape, ownership transfer |
| User/config | allowed values, defaults, validation, backward compatibility |

If the target repository only calls a library or service, summarize the interface contract and local adapter, not the external implementation.

## 5. Domain Profiles

Use profiles as overlays, not as the base model.

### AI/ML And High-Performance Profile

Separate:

- Data plane: samples, requests, tensors, batches, activations, tokens, KV cache, files.
- Model plane: weights, gradients, optimizer state, parameter shards, metadata, adapters, checkpoints.
- Control plane: schedulers, RPC, actors, futures, events, locks, barriers, streams, retries, cancellation.

Add resource classes: compute, memory, storage, network, model state, runtime state.

### Compiler Profile

Track:

- Source construct, parser, AST, IR, analysis, transform pass, lowering, codegen, runtime ABI.
- Invariants: dominance, type constraints, SSA, ownership, target feature, layout.
- Risks: pass ordering bugs, invalid IR, miscompile, ABI mismatch.

### Backend/Distributed Profile

Track:

- API ingress, auth, validation, service call, database/cache/queue, response.
- Control: retries, idempotency, timeouts, cancellation, worker ownership, backpressure.
- Risks: consistency, partial failure, silent retry, duplicated side effect.

### Database/Storage Profile

Track:

- Query/write path, planner, index, buffer/cache, log, transaction, compaction, durability.
- Risks: atomicity, isolation, corruption, stale read, write amplification.

## 6. Risk And Invariant Lens

Add risk nodes where code shape creates hazards:

- Deadlock/livelock: locks, barriers, queues, futures, callbacks, collectives, process joins.
- Precision/numerics: dtype casts, changed reduction order, fused kernels, quantization, stochastic sampling.
- Consistency: idempotency, transactions, schema migration, cache invalidation, retry semantics.
- Silent/deferred errors: background task exceptions, async GPU work, swallowed retries, best-effort cleanup, logging-only failures.
- Security/permissions: auth boundary, secret handling, path traversal, tenant isolation.
- Lifecycle leaks: unclosed files, unreleased memory, dangling pointer, stale registry, abandoned task.

## 7. Deep Dives

Create second-level pages or sections when a module has:

- Complex state machine or lifecycle.
- Scheduler, planner, optimizer, or admission-control logic.
- Algorithm API where formulas, docs, and code names diverge.
- Cross-language binding or memory ownership boundary.
- Protocol/schema compatibility surface.
- High coupling between config, resource layout, and runtime behavior.

Each deep dive should include:

- Local goal and public interface.
- Owned assets and external interfaces.
- State variables and invariants.
- Transition, partition, or algorithm diagram.
- Inputs, outputs, side effects, and resource lifecycle.
- Formula/pseudocode to code mapping if needed.
- Main risks and observability hooks.
