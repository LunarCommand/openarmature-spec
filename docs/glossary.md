# Glossary

This glossary collects the named concepts defined across OpenArmature's capability
specifications — each with a one-line gloss and a link to the section where it is
normatively defined. Terms are grouped by capability; the index links to every term
for alphabetical lookup. The gloss orients — the linked spec section is authoritative.

## Index

- **A** — [Adapter](#adapter) · [Assertion shape](#assertion-shape) · [Attribute namespace](#attribute-namespace)
- **B** — [Branch middleware](#branch-middleware) · [Branch spec](#branch-spec)
- **C** — [Call-level retry](#call-level-retry) · [Case](#case) · [Cause chain](#cause-chain) · [ChatMessage](#chat-message) · [ChatSegment](#chat-segment) · [ChatTurnOutcome](#chat-turn-outcome) · [Checkpointer](#checkpointer) · [Checkpointing](#checkpointing) · [CheckpointRecord](#checkpoint-record) · [Compiled graph](#compiled-graph) · [Content block](#content-block) · [ContentBlockTemplate](#content-block-template) · [ConversationHistory](#conversation-history) · [Correlation ID](#correlation-id)
- **D** — [Degraded instance](#degraded-instance) · [Detached trace mode](#detached-trace-mode) · [Directive](#directive) · [Directive vocabulary](#directive-vocabulary) · [Drain](#drain) · [Driving span](#driving-span)
- **E** — [Edge](#edge) · [Embedding runtime config](#embedding-runtime-config) · [EmbeddingProvider](#embedding-provider) · [EmbeddingResponse](#embedding-response) · [EmbeddingUsage](#embedding-usage) · [END](#end) · [Error category](#error-category) · [`error_policy`](#error-policy) · [Extras pass-through](#extras-pass-through)
- **F** — [Failure isolation](#failure-isolation) · [Fan-in / collect](#fan-in-collect) · [Fan-out node](#fan-out-node) · [Fetch vs. render](#fetch-vs-render) · [Fixture](#fixture) · [Framework-emitted augmentation event](#framework-augmentation-event)
- **G** — [GenAI semconv](#genai-semconv)
- **H** — [Harness](#harness) · [Harness mode](#harness-mode) · [Harness primitive](#harness-primitive)
- **I** — [Idempotency contract](#idempotency-contract) · [Inbound dispatch path](#inbound-dispatch-path) · [Instance middleware](#instance-middleware) · [Invariant](#invariant) · [Invocation](#invocation) · [Invocation outcome](#invocation-outcome) · [`invocation_id`](#invocation-id)
- **L** — [Langfuse mapping](#langfuse-mapping) · [Log correlation](#log-correlation)
- **M** — [Message](#message) · [Middleware](#middleware) · [Middleware chain](#middleware-chain)
- **N** — [Node](#node) · [Node event](#node-event)
- **O** — [Observer](#observer) · [Outbound surface](#outbound-surface)
- **P** — [Parallel branches](#parallel-branches) · [Paused-invocation record](#paused-invocation-record) · [Pending message](#pending-message) · [Per-instance projection](#per-instance-projection) · [Pre-/post-node phase](#pre-post-node-phase) · [Prompt](#prompt) · [PromptBackend](#prompt-backend) · [PromptGroup](#prompt-group) · [PromptManager](#prompt-manager) · [PromptResult](#prompt-result) · [Provider](#provider) · [Provider interface](#provider-interface)
- **Q** — [Queryable observer](#queryable-observer)
- **R** — [Reasoning-continuity signature](#reasoning-continuity-signature) · [Reducer](#reducer) · [RerankProvider](#rerank-provider) · [Response](#response) · [Resume](#resume) · [RetrievalProvider](#retrievalprovider) · [Retry](#retry) · [RuntimeConfig](#runtime-config)
- **S** — [`send()` callable](#send-callable) · [Session](#session) · [`session_id`](#session-id) · [Session resolver](#session-resolver) · [SessionRecord](#session-record) · [SessionState](#session-state) · [SessionStore](#session-store) · [Signal coordinator](#signal-coordinator) · [Signal descriptor](#signal-descriptor) · [Signal payload](#signal-payload) · [`signal_id`](#signal-id) · [Span](#span) · [Span attributes](#span-attributes) · [Span hierarchy](#span-hierarchy) · [Span status](#span-status) · [State](#state) · [State migration](#state-migration) · [Structured output](#structured-output) · [Subgraph](#subgraph) · [Subscribed listener](#subscribed-listener) · [Suspended outcome](#suspended-outcome) · [Suspension](#suspension)
- **T** — [Timing](#timing) · [Tool](#tool) · [Tool call](#tool-call) · [Tool definition](#tool-definition) · [Trace](#trace) · [Turn](#turn) · [Turn-level wrapper span](#turn-level-wrapper-span)
- **W** — [Wire-format mapping](#wire-format-mapping)

## Graph engine

- **Compiled graph**{#compiled-graph} — The immutable, executable result of compiling a graph definition; compilation fails on no declared entry, unreachable nodes, dangling edges, multiple outgoing edges, or conflicting reducers. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **Drain**{#drain} — The engine's flush of all queued observer events before an invocation returns, so delivery completes within the invocation boundary. [graph-engine §6](capabilities/graph-engine.md#6-observer-hooks)
- **Edge**{#edge} — A directed connection between nodes: a *static edge* (fixed destination) or a *conditional edge* (destination computed from state, or the `END` sentinel). Each node has exactly one outgoing edge. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **END**{#end} — The engine-provided sentinel routing target that halts execution; a distinct constant, not a reserved node name. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **Error category**{#error-category} — A canonical identifier classifying a failure (e.g. `node_exception`, `no_declared_entry`, `dangling_edge`, `fan_out_empty`), surfaced per the language's idiom for cross-impl consistency. [graph-engine §4](capabilities/graph-engine.md#4-error-semantics)
- **Framework-emitted augmentation event**{#framework-augmentation-event} — A typed event the engine emits beyond raw node events — typed LLM completion / failure, embedding, rerank, and tool-call events — carrying provider- or tool-specific structured detail to observers. [graph-engine §6](capabilities/graph-engine.md#6-observer-hooks)
- **Invocation**{#invocation} — A single execution of a compiled graph via the entry surface (`invoke()`), returning one of three outcomes. (In conformance fixtures, one `invoke()` call within an `invocations:` list — conformance-adapter §2.) [graph-engine §3](capabilities/graph-engine.md#3-execution-model)
- **Invocation outcome**{#invocation-outcome} — The result shape of an invocation: `completed` (reached `END`), `errored` (a node raised), or `suspended` (a node paused; see [Suspension](#suspension)). [graph-engine §3](capabilities/graph-engine.md#3-execution-model)
- **Node**{#node} — A named, asynchronous unit of work that receives the current state and returns a partial update; it must not mutate the state it received. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **Node event**{#node-event} — The started/completed event pair the engine dispatches per node execution (and per retry attempt) to observers. [graph-engine §6](capabilities/graph-engine.md#6-observer-hooks)
- **Observer**{#observer} — An async callable receiving node lifecycle events from a strictly-serial delivery queue; the read-only telemetry surface over an invocation. [graph-engine §6](capabilities/graph-engine.md#6-observer-hooks)
- **Reducer**{#reducer} — A function merging a node's partial update into prior state for one field; each field has exactly one. Eight canonical reducers ship — `last_write_wins` (default), `append`, `merge`, `concat_flatten`, `merge_all`, `bounded_append`, `dedupe_append`, `merge_by_key` — and custom reducers may be registered per field. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **State**{#state} — The typed schema (a record of named, typed fields) describing data flowing through a graph; validated at graph boundaries. [graph-engine §2](capabilities/graph-engine.md#2-concepts)
- **Subgraph**{#subgraph} — A compiled graph used as a node inside another graph; runs against its own state schema and projects results back into the parent via `inputs`/`outputs` mappings or field-name matching. [graph-engine §2](capabilities/graph-engine.md#2-concepts)

## Pipeline utilities

- **Branch middleware**{#branch-middleware} — Middleware wrapping a single parallel branch's invocation, analogous to fan-out instance middleware. [pipeline-utilities §11.7](capabilities/pipeline-utilities.md#117-branch-middleware)
- **Branch spec**{#branch-spec} — The per-branch definition inside a parallel-branches node: the branch's subgraph plus its `inputs`/`outputs` projections. [pipeline-utilities §11.1.1](capabilities/pipeline-utilities.md#1111-branch-spec)
- **Cause chain**{#cause-chain} — The structured `caught_exception` on a failure-isolation event: an ordered list of `{category, message, carrier}` links (outermost→innermost) plus a derived top-level category and message. [pipeline-utilities §6.3](capabilities/pipeline-utilities.md#63-failure-isolation)
- **Checkpointer**{#checkpointer} — The `save` / `load` / `list` / `delete` protocol backends implement to persist checkpoint records, keyed by `invocation_id`. [pipeline-utilities §10.1](capabilities/pipeline-utilities.md#101-checkpointer-protocol)
- **Checkpointing**{#checkpointing} — Opt-in durable persistence of invocation progress so an interrupted run can resume; provided by a registered Checkpointer. [pipeline-utilities §10](capabilities/pipeline-utilities.md#10-checkpointing)
- **CheckpointRecord**{#checkpoint-record} — The in-memory typed object the engine hands to `save`: serialized state plus the completed-node positions needed to resume. [pipeline-utilities §10.2](capabilities/pipeline-utilities.md#102-checkpoint-record-shape)
- **Degraded instance**{#degraded-instance} — A fan-out instance that returns a configured `degraded_update` instead of raising; it counts as a §9.3 success whose contribution is the degraded value. [pipeline-utilities §9.8](capabilities/pipeline-utilities.md#98-fan-out-degrade-slot-coverage)
- **`error_policy`**{#error-policy} — A fan-out / parallel-branches failure mode: `fail_fast` (default — the first failure aborts) or `collect` (gather per-instance / per-branch errors and continue). [pipeline-utilities §9.5](capabilities/pipeline-utilities.md#95-error-policy)
- **Failure isolation**{#failure-isolation} — The canonical middleware that catches exceptions escaping the inner chain and returns a configured degraded partial update, emitting a named failure-isolation event. [pipeline-utilities §6.3](capabilities/pipeline-utilities.md#63-failure-isolation)
- **Fan-in / collect**{#fan-in-collect} — The merge of each fan-out instance's `collect_field` value back into the parent's `target_field` via that field's reducer. [pipeline-utilities §9.3](capabilities/pipeline-utilities.md#93-per-instance-fan-in)
- **Fan-out node**{#fan-out-node} — A node that runs a subgraph (or async callable) once per item in a parent field — or `count` times — with bounded concurrency, collecting per-instance results into a parent field. The one place subgraph executions overlap in time. [pipeline-utilities §9](capabilities/pipeline-utilities.md#9-parallel-fan-out)
- **Idempotency contract**{#idempotency-contract} — The requirement that resumed nodes tolerate re-execution, since resume may re-run a node whose effects partially applied before the interruption. [pipeline-utilities §10.5](capabilities/pipeline-utilities.md#105-idempotency-contract)
- **Instance middleware**{#instance-middleware} — Middleware wrapping each fan-out instance's invocation as a unit, sitting between the fan-out node's outer middleware and the instance subgraph's own middleware. [pipeline-utilities §9.7](capabilities/pipeline-utilities.md#97-instance-middleware)
- **Middleware**{#middleware} — An async callable wrapping a node with the shape `(state, next) -> partial_update`; it may inspect or transform input, short-circuit, catch exceptions, or retry by calling `next` again. [pipeline-utilities §2](capabilities/pipeline-utilities.md#2-concepts)
- **Middleware chain**{#middleware-chain} — An ordered sequence of middleware around one node, composing outer-to-inner; each layer's return flows back through the previous layer's `next` call. [pipeline-utilities §2](capabilities/pipeline-utilities.md#2-concepts)
- **Parallel branches**{#parallel-branches} — A node holding a static map of named, heterogeneous subgraphs that run concurrently within one invocation; topology-driven, complementing data-driven fan-out. [pipeline-utilities §11](capabilities/pipeline-utilities.md#11-parallel-branches)
- **Per-instance projection**{#per-instance-projection} — How each fan-out instance receives its slice of parent state: the per-item value via `item_field`, plus any `inputs`-mapped parent fields. [pipeline-utilities §9.1](capabilities/pipeline-utilities.md#91-per-instance-projection)
- **Pre-/post-node phase**{#pre-post-node-phase} — The two halves of a middleware split by `await next(...)`: the pre-phase runs on the way in (outer-to-inner), the post-phase on the way out (inner-to-outer). [pipeline-utilities §2](capabilities/pipeline-utilities.md#2-concepts)
- **Resume**{#resume} — Continuation of a checkpointed (or suspended) invocation via `invoke(resume_invocation=...)`, replaying from the last completed position. (Suspension's resume: [suspension §7](capabilities/suspension.md#7-resume-api).) [pipeline-utilities §10.4](capabilities/pipeline-utilities.md#104-resume-model-invokeresume_invocationinvocation_id)
- **Retry**{#retry} — The canonical middleware that re-invokes the wrapped chain on classifier-matched exceptions, up to `max_attempts`, with configurable backoff (default exponential with full jitter). [pipeline-utilities §6.1](capabilities/pipeline-utilities.md#61-retry)
- **State migration**{#state-migration} — Versioned transformation of a persisted checkpoint's state shape (`schema_version` chain resolution) so older records load into a newer schema. [pipeline-utilities §10.12](capabilities/pipeline-utilities.md#1012-state-migrations)
- **Timing**{#timing} — The canonical middleware that measures wrapped-node wall-clock duration on a monotonic clock and reports it via callback. [pipeline-utilities §6.2](capabilities/pipeline-utilities.md#62-timing)

## LLM provider

- **Call-level retry**{#call-level-retry} — The provider's own retry lane for transient API failures, distinct from (and nested inside) graph-engine retry middleware. [llm-provider §7.1](capabilities/llm-provider.md#71-call-level-retry)
- **Content block**{#content-block} — A typed segment of message content: `text`, `image`, `thinking`, or `redacted_thinking`; imported unchanged by harness-chat. [llm-provider §3.1](capabilities/llm-provider.md#31-content-blocks)
- **Extras pass-through**{#extras-pass-through} — The convention by which vendor-specific request parameters not in the typed config are forwarded to the provider via an extras bag, with null-skip semantics. [llm-provider §6](capabilities/llm-provider.md#6-response-and-configuration)
- **Message**{#message} — A typed conversation entry of kind `system`, `user`, `assistant`, or `tool`, each carrying kind-specific content. [llm-provider §2](capabilities/llm-provider.md#2-concepts)
- **Provider**{#provider} — An object bound to a model identifier that, given messages and optional tools, returns one assistant message wrapped in a Response. [llm-provider §2](capabilities/llm-provider.md#2-concepts)
- **Provider interface**{#provider-interface} — The `ready()` / `complete(...)` contract every provider satisfies. [llm-provider §5](capabilities/llm-provider.md#5-provider-interface)
- **Reasoning-continuity signature**{#reasoning-continuity-signature} — An opaque token attached to a thinking block that lets a provider verify reasoning continuity across turns. [llm-provider §3.1.7](capabilities/llm-provider.md#317-reasoning-continuity-signatures)
- **Response**{#response} — A provider call's result: the assistant message, a finish reason, and usage information. [llm-provider §2](capabilities/llm-provider.md#2-concepts)
- **RuntimeConfig**{#runtime-config} — The caller-supplied per-request parameter record (temperature, max tokens, etc.) plus an extras pass-through bag for vendor-specific knobs. [llm-provider §6](capabilities/llm-provider.md#6-response-and-configuration)
- **Structured output**{#structured-output} — Provider support for constraining a completion to a caller-supplied response schema, with a documented fallback for models lacking native support. [llm-provider §8](capabilities/llm-provider.md#8-wire-format-mappings)
- **Tool**{#tool} — A function the model may request the caller execute, defined by `name`, `description`, and a JSON-Schema `parameters` shape. [llm-provider §2](capabilities/llm-provider.md#2-concepts)
- **Tool call**{#tool-call} — An assistant message's request to invoke a named tool with structured arguments; answered by a `tool` message bearing the matching `tool_call_id`. [llm-provider §2](capabilities/llm-provider.md#2-concepts)
- **Tool definition**{#tool-definition} — The record (`name`, `description`, `parameters`) describing a tool to the provider. [llm-provider §4](capabilities/llm-provider.md#4-tool-definition)
- **Wire-format mapping**{#wire-format-mapping} — The normative translation between the spec's message / tool / config shapes and a vendor API's wire bytes; defined for OpenAI-compatible, Anthropic Messages, and Google Gemini. [llm-provider §8](capabilities/llm-provider.md#8-wire-format-mappings)

## Retrieval provider

- **Embedding runtime config**{#embedding-runtime-config} — A RuntimeConfig-shaped record for embedding requests; minimally an optional `dimensions` plus an extras pass-through bag. [retrieval-provider §2](capabilities/retrieval-provider.md#2-concepts)
- **EmbeddingProvider**{#embedding-provider} — An object bound to an embedding model that turns input strings into vectors wrapped in an EmbeddingResponse. [retrieval-provider §2](capabilities/retrieval-provider.md#2-concepts)
- **EmbeddingResponse**{#embedding-response} — An `embed()` result: the vectors, model identifier, usage, and optional request id / verbatim provider `raw` response. [retrieval-provider §2](capabilities/retrieval-provider.md#2-concepts)
- **EmbeddingUsage**{#embedding-usage} — An embedding usage record carrying `input_tokens` only (vectors have no output tokens). [retrieval-provider §2](capabilities/retrieval-provider.md#2-concepts)
- **RerankProvider**{#rerank-provider} — The retrieval protocol for relevance reranking — re-scores candidate documents against a query, returning relevance-sorted `ScoredDocument` entries — named as part of the RetrievalProvider umbrella. [retrieval-provider §5](capabilities/retrieval-provider.md#5-rerankprovider-protocol)
- **RetrievalProvider**{#retrievalprovider} — The umbrella capability covering EmbeddingProvider and RerankProvider; a capability-level descriptor for cross-protocol concerns, not a concrete protocol itself. [retrieval-provider §2](capabilities/retrieval-provider.md#2-concepts)

## Observability

- **Attribute namespace**{#attribute-namespace} — The `openarmature.*` dotted-key namespace for OA span attributes; upstream GenAI semconv names are adopted only once they reach upstream Stable. [observability §5](capabilities/observability.md#5-attribute-namespace)
- **Correlation ID**{#correlation-id} — A per-invocation, application-supplied identifier that flows across every observability backend as a join key; distinct from the backend-local `invocation_id`. [observability §2](capabilities/observability.md#2-concepts)
- **Detached trace mode**{#detached-trace-mode} — An opt-in mode where a specific subgraph or fan-out gets its own trace, with the parent's dispatch span carrying an OTel Link to it. [observability §4.4](capabilities/observability.md#44-detached-trace-mode-opt-in)
- **Driving span**{#driving-span} — The currently-open span an implementation drives as work executes; its lifecycle (open / attribute / close) is specified for deterministic emission. [observability §6](capabilities/observability.md#6-driving-span-lifecycle)
- **GenAI semconv**{#genai-semconv} — The OpenTelemetry Generative-AI semantic-convention attribute subset OA emits on LLM spans (the Stable subset). [observability §5.5.3](capabilities/observability.md#553-genai-semconv-response-attributes)
- **`invocation_id`**{#invocation-id} — The per-invocation identifier (caller-supplied or framework-generated) that correlates spans within a single backend; the checkpoint / resume key, distinct from the cross-backend `correlation_id`. [observability §3.2](capabilities/observability.md#32-distinction-from-invocation_id)
- **Langfuse mapping**{#langfuse-mapping} — The normative projection of OA spans onto Langfuse's trace / observation / generation data model and attributes. [observability §8](capabilities/observability.md#8-langfuse-mapping)
- **Log correlation**{#log-correlation} — The contract that log records emitted during an invocation carry the correlating ids (`correlation_id`, `invocation_id`) so logs join to traces. [observability §7](capabilities/observability.md#7-log-correlation)
- **Queryable observer**{#queryable-observer} — The pattern where a concrete observer exposes extra read methods that pipeline nodes consume at runtime, without expanding the abstract Observer protocol. [observability §9](capabilities/observability.md#9-queryable-observer-pattern)
- **Span**{#span} — An OTel unit of work — a named interval with timestamps, status, attributes, and parent/child links; each meaningful unit of a graph invocation maps to one. [observability §2](capabilities/observability.md#2-concepts)
- **Span attributes**{#span-attributes} — Scalar (or scalar-array) key/value pairs on a span, namespaced under `openarmature.`. [observability §2](capabilities/observability.md#2-concepts)
- **Span hierarchy**{#span-hierarchy} — The span tree of an invocation: invocation span (root) → node / subgraph / fan-out spans, with one node span per retry attempt. [observability §4](capabilities/observability.md#4-span-hierarchy)
- **Span status**{#span-status} — A span's `OK` / `ERROR` / `UNSET` status; engine error categories map to `ERROR` with a category-bearing description. [observability §2](capabilities/observability.md#2-concepts)
- **Trace**{#trace} — An OTel tree of spans under one trace id; by default one outermost invocation is one trace, with subgraphs / fan-outs nested (unless detached). [observability §2](capabilities/observability.md#2-concepts)
- **Turn-level wrapper span**{#turn-level-wrapper-span} — An optional harness-emitted span wrapping a whole turn, parenting the invocation span(s) within it. [observability §4.6](capabilities/observability.md#46-turn-level-wrapper-span-harness-capability)

## Prompt management

- **ChatSegment**{#chat-segment} — A unit of a chat-prompt template (role + content) in the chat-prompt variant of Prompt. [prompt-management §3.1](capabilities/prompt-management.md#31-chat-prompt-variant)
- **ContentBlockTemplate**{#content-block-template} — A templated content block within a ChatSegment, mirroring llm-provider content blocks at the template layer. [prompt-management §3.1](capabilities/prompt-management.md#31-chat-prompt-variant)
- **Fetch vs. render**{#fetch-vs-render} — The deliberate split between retrieving a template (the I/O-bound step) and applying variables to it (local), enabling separate caching and inspection. [prompt-management §2](capabilities/prompt-management.md#2-concepts)
- **Prompt**{#prompt} — An unrendered template plus identity metadata; what a backend returns from a fetch, renderable and content-addressable without another round-trip. [prompt-management §2](capabilities/prompt-management.md#2-concepts)
- **PromptBackend**{#prompt-backend} — The fetch-by-name-and-label protocol backends implement; backends fetch, they do not render. [prompt-management §2](capabilities/prompt-management.md#2-concepts)
- **PromptGroup**{#prompt-group} — A tracing convention grouping related PromptResults (e.g. classifier + follow-up) under one logical span grouping; not a fetch or render primitive. [prompt-management §10](capabilities/prompt-management.md#10-promptgroup)
- **PromptManager**{#prompt-manager} — The user-facing API composing one or more PromptBackends and exposing fetch + render. [prompt-management §2](capabilities/prompt-management.md#2-concepts)
- **PromptResult**{#prompt-result} — The rendered output of applying variables to a Prompt: the rendered Message sequence, identity metadata, and a `rendered_hash`. [prompt-management §2](capabilities/prompt-management.md#2-concepts)

## Sessions

- **Session**{#session} — The typed state record persisted under a `session_id`, carrying cross-invocation state plus identity metadata; distinct from per-invoke state. [sessions §2](capabilities/sessions.md#2-concepts)
- **`session_id`**{#session-id} — The caller-supplied, application-stable identifier scoping a session across many invocations; never engine-generated. [sessions §2](capabilities/sessions.md#2-concepts)
- **SessionRecord**{#session-record} — The stored representation of a session: `session_id`, serialized state, `schema_version`, and opaque backend metadata. [sessions §2](capabilities/sessions.md#2-concepts)
- **SessionState**{#session-state} — The optional typed projection of cross-invoke state — a narrower view than full invoke State, excluding per-invoke scratch fields. [sessions §2](capabilities/sessions.md#2-concepts)
- **SessionStore**{#session-store} — The `load` / `save` / `delete` / `list` protocol for session persistence; mirrors Checkpointer but session-keyed. [sessions §2](capabilities/sessions.md#2-concepts)

## Suspension {#group-suspension}

- **Paused-invocation record**{#paused-invocation-record} — The persisted state of a suspended invocation (state, signal descriptor, ids, completed positions), stored via the same machinery as checkpoints. [suspension §2](capabilities/suspension.md#2-concepts)
- **Signal descriptor**{#signal-descriptor} — The typed record attached at suspension: a caller-supplied `signal_id` correlation token plus optional application metadata. [suspension §2](capabilities/suspension.md#2-concepts)
- **Signal payload**{#signal-payload} — The application-defined data delivered at resume time and merged into invocation state before execution continues. [suspension §2](capabilities/suspension.md#2-concepts)
- **`signal_id`**{#signal-id} — The caller-supplied correlation token on a signal descriptor, used to route an inbound signal back to its paused invocation. [suspension §2](capabilities/suspension.md#2-concepts)
- **Suspended outcome**{#suspended-outcome} — The `invoke()` return shape when a graph suspends — carrying invocation / correlation ids, the signal descriptor, the state at the pause, and the suspending node. [suspension §2](capabilities/suspension.md#2-concepts)
- **Suspension**{#suspension} — The intentional pause of an in-progress invocation at a node via `suspend()`; the engine persists state and returns a `suspended` outcome, resumed later with a signal payload. [suspension §2](capabilities/suspension.md#2-concepts)

## Harness {#group-harness}

- **Harness**{#harness} — The integration layer wrapping the engine for a deployment runtime; owns inbound dispatch, the outbound surface, session lookup, and signal coordination. [harness §2](capabilities/harness.md#2-concepts)
- **Harness mode**{#harness-mode} — Whether a harness is *sessioned* (every transmission tied to a `session_id`, state loaded / saved per turn) or *stateless* (independent turns, no session); fixed at construction. [harness §2](capabilities/harness.md#2-concepts)
- **Inbound dispatch path**{#inbound-dispatch-path} — One of the classification paths the harness routes inbound traffic into (stateless, new-session, existing-session, signal-resume). [harness §2](capabilities/harness.md#2-concepts)
- **Outbound surface**{#outbound-surface} — The mechanisms a harness uses to expose in-invocation effects: sync returns, async dispatches from node bodies, and signal subscriptions. [harness §2](capabilities/harness.md#2-concepts)
- **Session resolver**{#session-resolver} — The (sessioned-mode) mechanism mapping inbound traffic to a `session_id`; the contract specifies that resolution happens, not how. [harness §2](capabilities/harness.md#2-concepts)
- **Signal coordinator**{#signal-coordinator} — The mechanism routing inbound signal callbacks to the correct paused invocation. [harness §2](capabilities/harness.md#2-concepts)
- **Turn**{#turn} — One bounded engine execution serving an inbound request or event — exactly one `invoke()` (or resume) call, beginning at invoke entry and ending at its outcome. [harness §2](capabilities/harness.md#2-concepts)

## Harness — chat

- **ChatMessage**{#chat-message} — The canonical typed message at the chat-harness boundary, mirroring llm-provider's message shape. [harness-chat §2](capabilities/harness-chat.md#2-concepts)
- **ChatTurnOutcome**{#chat-turn-outcome} — The discriminated return of the chat harness's `send()`: completed reply, errored turn, or suspended turn. [harness-chat §2](capabilities/harness-chat.md#2-concepts)
- **ConversationHistory**{#conversation-history} — The per-session field holding the ordered chat message list. [harness-chat §2](capabilities/harness-chat.md#2-concepts)
- **Pending message**{#pending-message} — A synthetic assistant message a node may append before `suspend()` to tell the user the turn is awaiting a signal. [harness-chat §2](capabilities/harness-chat.md#2-concepts)
- **`send()` callable**{#send-callable} — The convenience surface above raw `invoke()`: takes a session id and an inbound user message, returns a ChatTurnOutcome. [harness-chat §2](capabilities/harness-chat.md#2-concepts)
- **Subscribed listener**{#subscribed-listener} — The default mechanism by which a chat harness surfaces the post-resume assistant reply after a suspend → signal → resume cycle. [harness-chat §2](capabilities/harness-chat.md#2-concepts)

## Conformance adapter

- **Adapter**{#adapter} — A language-specific runtime that discovers fixtures, parses their YAML into native graph calls, executes them, and asserts against the `expected:` block. Implementation-private; the fixtures are spec-public. [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Assertion shape**{#assertion-shape} — A field under `expected:` specifying what to verify — exact-equality (`final_state`, `execution_order`) or invariant (`invariants`, `observer_event_invariants`). [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Case**{#case} — One scenario within a fixture; a fixture may hold a single top-level case or multiple under `cases:`. [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Directive**{#directive} — A named YAML field declaring something the adapter translates into a runtime construct or assertion (e.g. `update`, `fan_out`, `observers[]`, `final_state`). [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Directive vocabulary**{#directive-vocabulary} — The full catalog of fixture directives the adapter supports, organized by kind (node-behavior, state / schema, edge, composition, observer, persistence, invocation-shape, expected-outcome, invariant). [conformance-adapter §5](capabilities/conformance-adapter.md#5-directive-vocabulary)
- **Fixture**{#fixture} — A declarative test case: a YAML file (graph, initial state, expected outcome) plus a sibling Markdown describing intent and spec coverage. [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Harness primitive**{#harness-primitive} — A runtime construct the adapter must provide to satisfy directives needing infrastructure beyond the bare engine — in-memory observers, persistence backends, OTel capture, etc. [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
- **Invariant**{#invariant} — A name-keyed boolean predicate checked when ordering is observable but not uniquely determined (fan-out scheduling, parallel branches, observer dispatch). [conformance-adapter §2](capabilities/conformance-adapter.md#2-concepts)
