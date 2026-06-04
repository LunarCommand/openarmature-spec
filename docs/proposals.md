# Proposals

OpenArmature evolves through numbered RFC-style proposals. Each proposal targets a capability spec and
moves through a `Draft → Accepted` lifecycle. Once `Accepted`, a proposal's text is **immutable** — further
changes happen via new proposals that supersede the prior. See [Governance](governance.md) for the full
lifecycle and the proposal template.

| #    | Title                                       | Capability          | Status   | Python          | TypeScript |
|------|---------------------------------------------|---------------------|----------|-----------------|------------|
| [0001](proposals/0001-graph-engine-foundation.md) | Foundation                                  | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0002](proposals/0002-subgraph-explicit-mapping.md) | Subgraph explicit I/O mapping               | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0003](proposals/0003-node-boundary-observer-hooks.md) | Node-boundary observer hooks                | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0004](proposals/0004-pipeline-utilities-middleware.md) | Middleware                                  | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0005](proposals/0005-pipeline-utilities-parallel-fan-out.md) | Parallel fan-out                            | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0006](proposals/0006-llm-provider-core.md) | Core abstraction + OpenAI wire mapping      | llm-provider        | Accepted | Shipped (0.5.0) | —          |
| [0007](proposals/0007-observability-otel-span-mapping.md) | OpenTelemetry span mapping                  | observability       | Accepted | Shipped (0.5.0) | —          |
| [0008](proposals/0008-pipeline-utilities-checkpointing.md) | Checkpointing                               | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0009](proposals/0009-pipeline-utilities-per-instance-fan-out-resume.md) | Per-instance fan-out resume                 | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0010](proposals/0010-drain-timeout.md) | Bounded drain — configurable timeout        | graph-engine        | Accepted | Shipped (0.9.0) | —          |
| [0011](proposals/0011-pipeline-utilities-parallel-branches.md) | Parallel branches                           | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0012](proposals/0012-graph-engine-completed-event-after-edges.md) | Completed event fires after edge evaluation | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0013](proposals/0013-fan-out-config-on-node-event.md) | Fan-out config on node event                | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0014](proposals/0014-pipeline-utilities-state-migration.md) | State migration hooks for checkpoints       | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0015](proposals/0015-llm-provider-multimodal-images.md) | Image content blocks for user messages      | llm-provider        | Accepted | Shipped (0.6.0) | —          |
| [0016](proposals/0016-llm-provider-structured-output.md) | Structured output                           | llm-provider        | Accepted | Shipped (0.6.0) | —          |
| [0017](proposals/0017-prompt-management-core.md) | Prompt management core                      | prompt-management   | Accepted | Shipped (0.6.0) | —          |
| [0018](proposals/0018-state-migration-chain-ambiguity.md) | State migration chain ambiguity             | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0019](proposals/0019-llm-provider-multi-provider-extension.md) | Multi-provider wire-format extension        | llm-provider        | Accepted | Textual (0.9.0) | —          |
| [0020](proposals/0020-sessions-capability.md) | Sessions capability                         | sessions            | Accepted | Pending         | —          |
| [0021](proposals/0021-graph-suspension.md) | Graph suspension and external-signal resume | suspension          | Accepted | Pending         | —          |
| [0022](proposals/0022-harness-contract.md) | Harness contract                            | harness             | Draft    | —               | —          |
| [0023](proposals/0023-canonical-state-reducers.md) | Canonical state reducers                    | graph-engine        | Draft    | —               | —          |
| [0024](proposals/0024-llm-span-payload-and-semconv.md) | LLM span payload + GenAI semconv            | observability       | Accepted | Shipped (0.8.0) | —          |
| [0025](proposals/0025-llm-provider-tool-choice.md) | LLM provider `tool_choice` parameter        | llm-provider        | Accepted | Shipped (0.9.0) | —          |
| [0026](proposals/0026-llm-provider-wire-format-mapping-template.md) | §8.X wire-format mapping subsection template | llm-provider        | Accepted | Textual (0.9.0) | —          |
| [0027](proposals/0027-fan-out-instance-progress-result-is-error.md) | `result_is_error` on fan-out progress entries | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0028](proposals/0028-schema-version-canonical-source.md) | Canonical `schema_version` source | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0029](proposals/0029-count-drift-strict.md) | Strict fan-out count-drift detection | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0030](proposals/0030-drain-snapshot-and-timeout-validation.md) | Drain snapshot + timeout-input validation | graph-engine        | Accepted | Textual (0.9.0) | —          |
| [0031](proposals/0031-observability-langfuse-mapping.md) | Langfuse backend mapping (§8 sibling to OTel)             | observability       | Accepted | Shipped (0.10.0)| —          |
| [0032](proposals/0032-llm-provider-runtime-config-refinements.md) | RuntimeConfig surface refinements | llm-provider | Accepted | Shipped (0.10.0)| —          |
| [0033](proposals/0033-prompt-management-surface-refinements.md) | Prompt-management surface refinements | prompt-management | Accepted | Shipped (0.10.0)| —          |
| [0034](proposals/0034-caller-supplied-invocation-metadata.md) | Caller-supplied invocation metadata | observability | Accepted | Shipped (0.10.0)| —          |
| [0035](proposals/0035-observability-langfuse-graph-topology-fixtures.md) | Langfuse graph-topology fixtures | observability | Accepted | Shipped (0.10.0)| —          |
| [0036](proposals/0036-graph-engine-fan-out-collection-reducers.md) | Fan-out collection reducers | graph-engine  | Accepted | Shipped (0.10.0)| —          |
| [0037](proposals/0037-llm-provider-anthropic-messages-mapping.md) | Anthropic Messages wire-format mapping (§8.2) | llm-provider  | Accepted | Pending         | —          |
| [0038](proposals/0038-llm-provider-google-gemini-mapping.md) | Google Gemini wire-format mapping (§8.3) | llm-provider  | Accepted | Pending         | —          |
| [0039](proposals/0039-observability-caller-supplied-invocation-id.md) | Caller-supplied `invocation_id` | observability | Accepted | Shipped (0.11.0)| —          |
| [0040](proposals/0040-observability-mid-invocation-metadata-open-span-update.md) | Mid-invocation metadata open-span update | observability | Accepted | Shipped (0.11.0)| —          |
| [0041](proposals/0041-observability-langfuse-metadata-key-collision.md) | Reserve OA-emitted Langfuse metadata keys | observability | Accepted | Shipped (0.11.0)| —          |
| [0042](proposals/0042-observability-reserved-keys-extension.md) | Reserve `branch_name`, `detached`, `detached_from_invocation_id` metadata keys | observability | Accepted | Shipped (0.11.0)| —          |
| [0043](proposals/0043-observability-langfuse-trace-input-output.md) | §8 Langfuse `trace.input` / `trace.output` population | observability | Accepted | Shipped (0.11.0)| —          |
| [0044](proposals/0044-parallel-branches-dispatch-span.md) | Parallel-branches dispatch span synthesis | graph-engine  | Accepted | Shipped (0.11.0)| —          |
| [0045](proposals/0045-observability-nested-lineage-augmentation.md) | Nested-lineage augmentation containment scope | observability | Accepted | Shipped (0.11.0)| —          |
| [0046](proposals/0046-prompt-management-multi-message-rendering.md) | Multi-message / chat prompt rendering | prompt-management | Accepted | Shipped (0.11.0)| —          |
| [0047](proposals/0047-implicit-prefix-cache-wire-stability.md) | Implicit prefix-cache wire-byte stability | llm-provider | Accepted | Pending         | —          |
| [0048](proposals/0048-read-symmetric-invocation-metadata-queryable-observer.md) | Read-symmetric invocation metadata + queryable observer pattern | observability | Accepted | Pending         | —          |
| [0049](proposals/0049-typed-llm-completion-event.md) | Typed LLM completion event | observability | Accepted | Pending         | —          |
| [0050](proposals/0050-retry-and-degradation-primitives.md) | Retry & degradation primitives (failure-isolation middleware + call-level retry) | pipeline-utilities | Accepted | Pending         | —          |
| [0051](proposals/0051-langfuse-trace-io-deprecation-caveat.md) | Langfuse trace input/output implementation-surface caveat | observability | Accepted | Textual (0.12.0)| —          |
| [0052](proposals/0052-implementation-attribution-rows.md) | Implementation attribution attributes (§5.1 invocation span + §8.4.1 Langfuse mapping) | observability | Accepted | Pending         | —          |
| [0053](proposals/0053-shared-parent-boundary-clarification.md) | §3.4 shared-parent boundary clarification (invocation span) | observability | Accepted | Textual (0.12.0)| —          |
| [0054](proposals/0054-per-invocation-event-drain.md) | Per-invocation observer event drain | graph-engine | Accepted | Pending         | —          |
| [0055](proposals/0055-conformance-adapter-capability.md) | Conformance adapter capability | conformance-adapter | Draft    | —               | —          |

Click any column header to sort.

The **Python** column reflects [`openarmature-python/conformance.toml`](https://github.com/LunarCommand/openarmature-python/blob/main/conformance.toml). Status values: `Shipped (X.Y.Z)` — proposal's behavior shipped in this implementation version; `Textual (X.Y.Z)` — accepted proposal was purely textual (reframe, clarification, template) and required no module-level change; `Pending` — Accepted in spec, not yet pinned in this implementation; `—` — proposal is Draft and impl status does not apply.

The **TypeScript** column shows `—` for every row pending the start of a TypeScript implementation.
