# Proposals

OpenArmature evolves through numbered RFC-style proposals. Each proposal targets a capability spec and
moves through a `Draft → Accepted` lifecycle. Once `Accepted`, a proposal's text is **immutable** — further
changes happen via new proposals that supersede the prior. See [Governance](governance.md) for the full
lifecycle and the proposal template.

| #    | Title                                       | Capability          | Status   |
|------|---------------------------------------------|---------------------|----------|
| [0001](proposals/0001-graph-engine-foundation.md) | Foundation                                  | graph-engine        | Accepted |
| [0002](proposals/0002-subgraph-explicit-mapping.md) | Subgraph explicit I/O mapping               | graph-engine        | Accepted |
| [0003](proposals/0003-node-boundary-observer-hooks.md) | Node-boundary observer hooks                | graph-engine        | Accepted |
| [0004](proposals/0004-pipeline-utilities-middleware.md) | Middleware                                  | pipeline-utilities  | Accepted |
| [0005](proposals/0005-pipeline-utilities-parallel-fan-out.md) | Parallel fan-out                            | pipeline-utilities  | Accepted |
| [0006](proposals/0006-llm-provider-core.md) | Core abstraction + OpenAI wire mapping      | llm-provider        | Accepted |
| [0007](proposals/0007-observability-otel-span-mapping.md) | OpenTelemetry span mapping                  | observability       | Accepted |
| [0008](proposals/0008-pipeline-utilities-checkpointing.md) | Checkpointing                               | pipeline-utilities  | Accepted |
| [0009](proposals/0009-pipeline-utilities-per-instance-fan-out-resume.md) | Per-instance fan-out resume                 | pipeline-utilities  | Accepted |
| [0010](proposals/0010-drain-timeout.md) | Bounded drain — configurable timeout        | graph-engine        | Accepted |
| [0011](proposals/0011-pipeline-utilities-parallel-branches.md) | Parallel branches                           | pipeline-utilities  | Accepted |
| [0012](proposals/0012-graph-engine-completed-event-after-edges.md) | Completed event fires after edge evaluation | graph-engine        | Accepted |
| [0013](proposals/0013-fan-out-config-on-node-event.md) | Fan-out config on node event                | graph-engine        | Accepted |
| [0014](proposals/0014-pipeline-utilities-state-migration.md) | State migration hooks for checkpoints       | pipeline-utilities  | Accepted |
| [0015](proposals/0015-llm-provider-multimodal-images.md) | Image content blocks for user messages      | llm-provider        | Accepted |
| [0016](proposals/0016-llm-provider-structured-output.md) | Structured output                           | llm-provider        | Accepted |
| [0017](proposals/0017-prompt-management-core.md) | Prompt management core                      | prompt-management   | Accepted |
| [0018](proposals/0018-state-migration-chain-ambiguity.md) | State migration chain ambiguity             | pipeline-utilities  | Accepted |
| [0019](proposals/0019-llm-provider-multi-provider-extension.md) | Multi-provider wire-format extension        | llm-provider        | Accepted |
| [0020](proposals/0020-sessions-capability.md) | Sessions capability                         | sessions            | Draft    |
| [0021](proposals/0021-graph-suspension.md) | Graph suspension and external-signal resume | suspension          | Draft    |
| [0022](proposals/0022-harness-contract.md) | Harness contract                            | harness             | Draft    |
| [0023](proposals/0023-canonical-state-reducers.md) | Canonical state reducers                    | graph-engine        | Draft    |
| [0024](proposals/0024-llm-span-payload-and-semconv.md) | LLM span payload + GenAI semconv            | observability       | Accepted |
| [0025](proposals/0025-llm-provider-tool-choice.md) | LLM provider `tool_choice` parameter        | llm-provider        | Accepted |
| [0026](proposals/0026-llm-provider-wire-format-mapping-template.md) | §8.X wire-format mapping subsection template | llm-provider        | Accepted |
| [0027](proposals/0027-fan-out-instance-progress-result-is-error.md) | Explicit `result_is_error` on `fan_out_progress` per-instance entries | pipeline-utilities  | Accepted |
| [0028](proposals/0028-schema-version-canonical-source.md) | Canonical source for `schema_version` on saved records | pipeline-utilities  | Accepted |
| [0029](proposals/0029-count-drift-strict.md) | Strict `checkpoint_record_invalid` on fan-out `instance_count` drift | pipeline-utilities  | Accepted |
| [0030](proposals/0030-drain-snapshot-and-timeout-validation.md) | §6 Drain snapshot semantic and timeout-input validation | graph-engine        | Accepted |
| [0031](proposals/0031-observability-langfuse-mapping.md) | Langfuse backend mapping (§8 sibling to OTel)             | observability       | Accepted |

Click any column header to sort.
