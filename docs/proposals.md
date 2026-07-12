# Proposals

OpenArmature evolves through numbered RFC-style proposals. Each proposal targets a capability spec and
moves through a `Draft → Accepted` lifecycle. Once `Accepted`, a proposal's text is **immutable** — further
changes happen via new proposals that supersede the prior. See [Governance](governance.md) for the full
lifecycle and the proposal template.

| #    | Title                                       | Capability          | Status   | Python          | TypeScript |
|------|---------------------------------------------|---------------------|----------|-----------------|------------|
| [0098](proposals/0098-conformance-adapter-carries-key-alignment.md) | Align structured-output `carries` assertion keys with §7 error field names | conformance-adapter | Draft | —               | —          |
| [0097](proposals/0097-retrieval-provider-jina-document-echo-shape.md) | Rerank `document` object-shape echo — general §6 rule + Jina TextDoc / ImageDoc | retrieval-provider | Accepted | Pending         | —          |
| [0096](proposals/0096-retrieval-raw-json-shape.md) | Retrieval `raw` verbatim JSON of any top-level shape | retrieval-provider | Accepted | Pending         | —          |
| [0095](proposals/0095-adaptive-call-level-retry.md) | Adaptive call-level retry (per-attempt override + reask) | llm-provider | Accepted | Pending         | —          |
| [0094](proposals/0094-subgraph-projection-declared-boundary.md) | Subgraph projection declared same-name boundary | graph-engine | Accepted | Pending         | —          |
| [0093](proposals/0093-nullable-provider-usage-records.md) | Nullable provider usage records | retrieval-provider | Accepted | Partial (0.16.0)| —          |
| [0092](proposals/0092-retrieval-provider-embedding-batch-chunking.md) | Embedding-mapping batch chunking | retrieval-provider | Accepted | Pending         | —          |
| [0091](proposals/0091-retrieval-provider-cohere-embeddings-wire.md) | Cohere embeddings wire mapping | retrieval-provider | Accepted | Pending         | —          |
| [0090](proposals/0090-retrieval-provider-cohere-rerank-wire.md) | Cohere rerank wire mapping | retrieval-provider | Accepted | Shipped (0.16.0)| —          |
| [0089](proposals/0089-embedding-rerank-typed-event-output.md) | Embedding / rerank typed-event output | graph-engine | Accepted | Shipped (0.16.0)| —          |
| [0088](proposals/0088-observability-langfuse-parallel-branches-parity.md) | Langfuse parallel-branches mapping parity | observability | Accepted | Pending         | —          |
| [0087](proposals/0087-conformance-adapter-directive-execution-order.md) | Within-node directive execution order | conformance-adapter | Accepted | Pending         | —          |
| [0086](proposals/0086-prompt-default-cache-ttl.md) | Service-wide default cache-TTL | prompt-management | Accepted | Pending         | —          |
| [0085](proposals/0085-nested-fan-out-checkpoint-lineage.md) | Nested fan-out checkpoint lineage | pipeline-utilities | Accepted | Partial (0.16.0)| —          |
| [0084](proposals/0084-nested-fan-out-span-lineage.md) | Nested-fan-out span lineage chain | observability | Accepted | Pending         | —          |
| [0083](proposals/0083-prompt-token-budget-observability.md) | Per-prompt token-budget observability | observability | Accepted | Pending         | —          |
| [0082](proposals/0082-structured-output-failure-diagnostics.md) | Structured-output failure diagnostics | graph-engine | Accepted | Pending         | —          |
| [0081](proposals/0081-conformance-adapter-value-matcher-vocabulary.md) | Value-matcher vocabulary | conformance-adapter | Accepted | Textual (0.16.0)| —          |
| [0080](proposals/0080-prompt-group-arity-enforcement.md) | PromptGroup arity enforcement | prompt-management | Accepted | Pending         | —          |
| [0079](proposals/0079-retrieval-provider-openai-compatible-embeddings.md) | OpenAI-compatible embeddings wire mapping | retrieval-provider | Accepted    | Shipped (0.16.0)| —          |
| [0078](proposals/0078-retrieval-provider-jina-wire-mapping.md) | Jina wire mapping (rerank + embedding) | retrieval-provider | Accepted    | Shipped (0.16.0)| —          |
| [0077](proposals/0077-retrieval-provider-tei-wire-mapping.md) | TEI wire mapping + asymmetric query/document embedding | retrieval-provider | Accepted    | Shipped (0.16.0)| —          |
| [0076](proposals/0076-tool-call-request-observability-llm-spans.md) | Tool-call request observability on LLM spans | observability | Accepted | Shipped (0.15.0)| —          |
| [0075](proposals/0075-parallel-branches-lightweight-branches.md) | Parallel-branches lightweight callable + conditional branches | pipeline-utilities | Accepted | Shipped (0.15.0)| —          |
| [0074](proposals/0074-failure-isolation-catch-classification.md) | Failure-isolation cause-chain catch classification | pipeline-utilities | Accepted | Shipped (0.15.0)| —          |
| [0073](proposals/0073-genai-semconv-adoption-reconciliation.md) | GenAI semconv adoption reconciliation | observability | Accepted | Textual (0.15.0)| —          |
| [0072](proposals/0072-prompt-management-fetch-cache-ttl.md) | Per-fetch cache-TTL control | prompt-management   | Accepted | Shipped (0.15.0)| —          |
| [0071](proposals/0071-conformance-adapter-failure-mock-catalog.md) | Failure-mock directive catalog | conformance-adapter | Accepted | Textual (0.14.0)| —          |
| [0070](proposals/0070-conformance-adapter-crash-injection-and-cause-chaining.md) | Crash-injection + cause-chaining adapter directives | conformance-adapter | Accepted | Shipped (0.14.0)| —          |
| [0069](proposals/0069-pipeline-utilities-fan-out-degrade-refinements.md) | Fan-out degrade contribution refinements | pipeline-utilities  | Accepted | Shipped (0.14.0)| —          |
| [0068](proposals/0068-pipeline-utilities-failure-isolation-cause-chain.md) | Failure-isolation event structured cause chain | pipeline-utilities  | Accepted | Shipped (0.14.0)| —          |
| [0067](proposals/0067-observability-genai-metrics.md) | OTel GenAI metrics | observability       | Accepted | Partial (0.15.0)| —          |
| [0066](proposals/0066-pipeline-utilities-fan-out-degrade-contribution.md) | Fan-out failure-isolation degrade contribution           | pipeline-utilities  | Accepted | Shipped (0.14.0)| —          |
| [0065](proposals/0065-pipeline-utilities-failure-isolation-cause-fidelity.md) | Failure-isolation cause-fidelity at wrapping sites        | pipeline-utilities  | Accepted | Shipped (0.14.0)| —          |
| [0064](proposals/0064-observability-langfuse-session-user-promotion.md) | Langfuse session / user trace-field population            | observability       | Accepted | Partial (0.15.0)| —          |
| [0063](proposals/0063-tool-execution-observability.md) | Tool-execution observability                              | graph-engine        | Accepted | Shipped (0.15.0)| —          |
| [0062](proposals/0062-llm-completion-streaming.md) | LLM completion streaming                                  | llm-provider        | Accepted | Pending         | —          |
| [0061](proposals/0061-detached-trace-invocation-span.md) | Detached-trace invocation span                            | observability       | Accepted | Shipped (0.15.0)| —          |
| [0060](proposals/0060-retrieval-provider-rerank.md) | Retrieval-provider rerank protocol                        | retrieval-provider  | Accepted | Shipped (0.16.0)| —          |
| [0059](proposals/0059-retrieval-provider-embedding.md) | Retrieval-provider capability (embedding protocol)        | retrieval-provider  | Accepted | Shipped (0.16.0)| —          |
| [0058](proposals/0058-typed-llm-failure-event.md) | Typed LLM failure event                                  | graph-engine        | Accepted | Shipped (0.13.0)| —          |
| [0057](proposals/0057-llm-completion-event-field-set-extension.md) | LlmCompletionEvent field-set extension | graph-engine | Accepted | Shipped (0.13.0)| —          |
| [0056](proposals/0056-harness-chat.md) | Chat harness sub-spec | harness-chat | Accepted | Pending         | —          |
| [0055](proposals/0055-conformance-adapter-capability.md) | Conformance adapter capability | conformance-adapter | Accepted | Textual (0.13.0)| —          |
| [0054](proposals/0054-per-invocation-event-drain.md) | Per-invocation observer event drain | graph-engine | Accepted | Shipped (0.12.0)| —          |
| [0053](proposals/0053-shared-parent-boundary-clarification.md) | Shared-parent boundary clarification (invocation span) | observability | Accepted | Textual (0.12.0)| —          |
| [0052](proposals/0052-implementation-attribution-rows.md) | Implementation attribution attributes | observability | Accepted | Shipped (0.12.0)| —          |
| [0051](proposals/0051-langfuse-trace-io-deprecation-caveat.md) | Langfuse trace input/output implementation-surface caveat | observability | Accepted | Textual (0.12.0)| —          |
| [0050](proposals/0050-retry-and-degradation-primitives.md) | Retry & degradation primitives (failure-isolation middleware + call-level retry) | pipeline-utilities | Accepted | Shipped (0.15.0)| —          |
| [0049](proposals/0049-typed-llm-completion-event.md) | Typed LLM completion event | observability | Accepted | Shipped (0.13.0)| —          |
| [0048](proposals/0048-read-symmetric-invocation-metadata-queryable-observer.md) | Read-symmetric invocation metadata + queryable observer pattern | observability | Accepted | Shipped (0.12.0)| —          |
| [0047](proposals/0047-implicit-prefix-cache-wire-stability.md) | Implicit prefix-cache wire-byte stability | llm-provider | Accepted | Shipped (0.13.0)| —          |
| [0046](proposals/0046-prompt-management-multi-message-rendering.md) | Multi-message / chat prompt rendering | prompt-management | Accepted | Shipped (0.11.0)| —          |
| [0045](proposals/0045-observability-nested-lineage-augmentation.md) | Nested-lineage augmentation containment scope | observability | Accepted | Shipped (0.11.0)| —          |
| [0044](proposals/0044-parallel-branches-dispatch-span.md) | Parallel-branches dispatch span synthesis | graph-engine  | Accepted | Shipped (0.11.0)| —          |
| [0043](proposals/0043-observability-langfuse-trace-input-output.md) | Langfuse `trace.input` / `trace.output` population | observability | Accepted | Shipped (0.11.0)| —          |
| [0042](proposals/0042-observability-reserved-keys-extension.md) | Reserve `branch_name`, `detached`, `detached_from_invocation_id` metadata keys | observability | Accepted | Shipped (0.11.0)| —          |
| [0041](proposals/0041-observability-langfuse-metadata-key-collision.md) | Reserve OA-emitted Langfuse metadata keys | observability | Accepted | Shipped (0.11.0)| —          |
| [0040](proposals/0040-observability-mid-invocation-metadata-open-span-update.md) | Mid-invocation metadata open-span update | observability | Accepted | Shipped (0.11.0)| —          |
| [0039](proposals/0039-observability-caller-supplied-invocation-id.md) | Caller-supplied `invocation_id` | observability | Accepted | Shipped (0.11.0)| —          |
| [0038](proposals/0038-llm-provider-google-gemini-mapping.md) | Google Gemini wire-format mapping | llm-provider  | Accepted | Pending         | —          |
| [0037](proposals/0037-llm-provider-anthropic-messages-mapping.md) | Anthropic Messages wire-format mapping | llm-provider  | Accepted | Pending         | —          |
| [0036](proposals/0036-graph-engine-fan-out-collection-reducers.md) | Fan-out collection reducers | graph-engine  | Accepted | Shipped (0.10.0)| —          |
| [0035](proposals/0035-observability-langfuse-graph-topology-fixtures.md) | Langfuse graph-topology fixtures | observability | Accepted | Shipped (0.10.0)| —          |
| [0034](proposals/0034-caller-supplied-invocation-metadata.md) | Caller-supplied invocation metadata | observability | Accepted | Shipped (0.10.0)| —          |
| [0033](proposals/0033-prompt-management-surface-refinements.md) | Prompt-management surface refinements | prompt-management | Accepted | Shipped (0.10.0)| —          |
| [0032](proposals/0032-llm-provider-runtime-config-refinements.md) | RuntimeConfig surface refinements | llm-provider | Accepted | Shipped (0.10.0)| —          |
| [0031](proposals/0031-observability-langfuse-mapping.md) | Langfuse backend mapping                                  | observability       | Accepted | Shipped (0.10.0)| —          |
| [0030](proposals/0030-drain-snapshot-and-timeout-validation.md) | Drain snapshot + timeout-input validation | graph-engine        | Accepted | Textual (0.9.0) | —          |
| [0029](proposals/0029-count-drift-strict.md) | Strict fan-out count-drift detection | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0028](proposals/0028-schema-version-canonical-source.md) | Canonical `schema_version` source | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0027](proposals/0027-fan-out-instance-progress-result-is-error.md) | `result_is_error` on fan-out progress entries | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0026](proposals/0026-llm-provider-wire-format-mapping-template.md) | Wire-format mapping subsection template | llm-provider        | Accepted | Textual (0.9.0) | —          |
| [0025](proposals/0025-llm-provider-tool-choice.md) | LLM provider `tool_choice` parameter        | llm-provider        | Accepted | Shipped (0.9.0) | —          |
| [0024](proposals/0024-llm-span-payload-and-semconv.md) | LLM span payload + GenAI semconv            | observability       | Accepted | Shipped (0.8.0) | —          |
| [0023](proposals/0023-canonical-state-reducers.md) | Canonical state reducers                    | graph-engine        | Accepted | Pending         | —          |
| [0022](proposals/0022-harness-contract.md) | Harness contract                            | harness             | Accepted | Pending         | —          |
| [0021](proposals/0021-graph-suspension.md) | Graph suspension and external-signal resume | suspension          | Accepted | Pending         | —          |
| [0020](proposals/0020-sessions-capability.md) | Sessions capability                         | sessions            | Accepted | Pending         | —          |
| [0019](proposals/0019-llm-provider-multi-provider-extension.md) | Multi-provider wire-format extension        | llm-provider        | Accepted | Textual (0.9.0) | —          |
| [0018](proposals/0018-state-migration-chain-ambiguity.md) | State migration chain ambiguity             | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0017](proposals/0017-prompt-management-core.md) | Prompt management core                      | prompt-management   | Accepted | Shipped (0.6.0) | —          |
| [0016](proposals/0016-llm-provider-structured-output.md) | Structured output                           | llm-provider        | Accepted | Shipped (0.6.0) | —          |
| [0015](proposals/0015-llm-provider-multimodal-images.md) | Image content blocks for user messages      | llm-provider        | Accepted | Shipped (0.6.0) | —          |
| [0014](proposals/0014-pipeline-utilities-state-migration.md) | State migration hooks for checkpoints       | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0013](proposals/0013-fan-out-config-on-node-event.md) | Fan-out config on node event                | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0012](proposals/0012-graph-engine-completed-event-after-edges.md) | Completed event fires after edge evaluation | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0011](proposals/0011-pipeline-utilities-parallel-branches.md) | Parallel branches                           | pipeline-utilities  | Accepted | Shipped (0.6.0) | —          |
| [0010](proposals/0010-drain-timeout.md) | Bounded drain — configurable timeout        | graph-engine        | Accepted | Shipped (0.9.0) | —          |
| [0009](proposals/0009-pipeline-utilities-per-instance-fan-out-resume.md) | Per-instance fan-out resume                 | pipeline-utilities  | Accepted | Shipped (0.9.0) | —          |
| [0008](proposals/0008-pipeline-utilities-checkpointing.md) | Checkpointing                               | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0007](proposals/0007-observability-otel-span-mapping.md) | OpenTelemetry span mapping                  | observability       | Accepted | Shipped (0.5.0) | —          |
| [0006](proposals/0006-llm-provider-core.md) | Core abstraction + OpenAI wire mapping      | llm-provider        | Accepted | Shipped (0.5.0) | —          |
| [0005](proposals/0005-pipeline-utilities-parallel-fan-out.md) | Parallel fan-out                            | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0004](proposals/0004-pipeline-utilities-middleware.md) | Middleware                                  | pipeline-utilities  | Accepted | Shipped (0.5.0) | —          |
| [0003](proposals/0003-node-boundary-observer-hooks.md) | Node-boundary observer hooks                | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0002](proposals/0002-subgraph-explicit-mapping.md) | Subgraph explicit I/O mapping               | graph-engine        | Accepted | Shipped (0.5.0) | —          |
| [0001](proposals/0001-graph-engine-foundation.md) | Foundation                                  | graph-engine        | Accepted | Shipped (0.5.0) | —          |

Click any column header to sort.

The **Python** column reflects [`openarmature-python/conformance.toml`](https://github.com/LunarCommand/openarmature-python/blob/main/conformance.toml). Status values: `Shipped (X.Y.Z)` — proposal's behavior shipped in this implementation version; `Textual (X.Y.Z)` — accepted proposal was purely textual (reframe, clarification, template) and required no module-level change; `Pending` — Accepted in spec, not yet pinned in this implementation; `—` — proposal is Draft and impl status does not apply.

The **TypeScript** column shows `—` for every row pending the start of a TypeScript implementation.
