# 0063: Tool-Execution Observability

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-09
- **Accepted:** 2026-06-19
- **Targets:** spec/graph-engine/spec.md (§6 — two new typed event variants on the observer event union, `ToolCallEvent` (success) and `ToolCallFailedEvent` (failure), paired per the 0049 / 0058 / 0059 success+failure precedent; plus a node-body **tool-call instrumentation scope** primitive the caller wraps tool execution in — OA observes the execution and emits the events; the caller runs the tool, OA does NOT select tools, loop, or feed results back); spec/observability/spec.md (§5.5 — new sub-subsection for the OTel tool span, span name `openarmature.tool.call`, OA-namespace `openarmature.tool.*` attributes; the upstream GenAI `execute_tool` span + `gen_ai.tool.*` attributes are at Development status (verified at draft time) and deferred per the stable-only adoption policy; §8.4 — Langfuse mapping onto the dedicated `Tool` observation type (`asType="tool"`); §5.5.4 — the `disable_provider_payload` flag's framing extends to cover tool-call payload (arguments / result), no new flag); plus new conformance fixtures under `spec/observability/conformance/`.
- **Related:** 0006 (llm-provider — §3 `ToolCall` / `tool` message shape and §4 `Tool` definition this references; the `ToolCall.id` that `tool_call_id` links to), 0049 (typed `LlmCompletionEvent` — the model *requesting* tools, carrying `tool_calls`; `ToolCallEvent` is the downstream *execution* of one of those requests, linked by `tool_call_id`), 0058 (typed `LlmFailedEvent` — the success+failure pairing precedent), 0059 (retrieval-provider — the `disable_provider_payload` cross-spec flag this reuses for tool payload, and the dedicated-Langfuse-observation-type pattern this applies to `Tool`)
- **Supersedes:**

## Summary

Makes a caller's **tool execution** observable as a first-class typed event, closing the
last RAG/agent-pipeline observability gap after LLM completion (0049/0058) and embedding (0059)
— rerank (0060) is the remaining sibling. The model requests a tool via `LlmCompletionEvent.output_tool_calls`; the caller
executes the tool (in node-body code — OA does not loop on tools per llm-provider §1); today
that execution is invisible to OA's observer stream. This proposal adds:

1. An opt-in **tool-call instrumentation scope** (graph-engine node-body primitive). The caller
   wraps its tool execution in the scope; OA emits a `ToolCallEvent` (success) or
   `ToolCallFailedEvent` (failure) around it. OA *observes* the execution — it does NOT run the
   tool, choose which tool to call, loop, or feed results back to the model. Those are
   orchestration concerns that stay in the user's graph (see *Out of scope*).
2. Two paired typed events on the graph-engine §6 observer union — `ToolCallEvent` +
   `ToolCallFailedEvent` — carrying the identity / scoping baseline plus tool-specific fields
   (`tool_name`, `tool_call_id` linking back to the requesting `LlmCompletionEvent`, the
   arguments, and the result or the error).
3. OTel mapping (a tool span, OA-namespace attributes — the upstream `gen_ai.tool.*` / `execute_tool`
   span is Development, assessed peripheral under the GenAI de-facto-standard carve-out and mirrored)
   and Langfuse mapping (the dedicated `Tool` observation type).

Because tool execution is arbitrary user-code, the failure variant departs from the other
typed failure events: tool failures are **not** llm-provider §7 error categories, so
`ToolCallFailedEvent` carries an impl-level `error_type` + `error_message` with **no
`error_category` enum**.

This is strictly the *observability* primitive. It composes with — but does not provide — the
agent tool-loop, which remains a user-authored graph.

## Motivation

**The execution half of tool calling is invisible.** llm-provider §3/§4 + proposal 0025
(`tool_choice`) cover the model *requesting* a tool, and `LlmCompletionEvent.output_tool_calls`
(0049/0057) surfaces the request. But llm-provider §1 is explicit that "the caller is
responsible for executing the tools" — OA does not loop. So the tool *execution* happens in
user node-body code, outside any OA abstraction, and is invisible to the observer stream: no
span, no observer event, no Langfuse observation, no per-invocation tool-cost / latency rollup
via the queryable-observer pattern (0048). observability §5.5.5 already flags "first-class
tool-call observability is a separate forthcoming proposal" — this is it.

**Spans alone can't see user code.** Unlike LLM / embedding / rerank calls — which flow through
OA provider abstractions that emit their events internally — tool execution has no abstraction
for OA to instrument. So OA must offer an explicit, opt-in instrumentation point the caller
routes its execution through. That's the minimal hook required; it is an observability surface,
not an orchestration one (it does not run or sequence tools).

**It completes the agent observability picture without owning the loop.** With `LlmCompletionEvent`
(the model's reasoning + tool requests) and `ToolCallEvent` (the tool executions), a
user-authored agent graph — `call_llm → execute_tools → call_llm` — is fully observable on OA's
vendor-neutral terms (OTel + Langfuse), which is the differentiation. The loop itself stays a
graph; OA supplies the observable primitives it composes from.

## Proposed change

### graph-engine §6 — tool-call instrumentation scope

A node-body primitive: a **tool-call instrumentation scope** the caller enters around a tool
execution. Behaviorally (language-agnostic; Python: an async context manager or a helper
wrapping the call; TypeScript: equivalent):

- The caller provides the `tool_name`, the `arguments` the tool is being invoked with, and
  OPTIONALLY a `tool_call_id` (the `ToolCall.id` from the `LlmCompletionEvent.output_tool_calls` entry
  this execution satisfies, per llm-provider §3).
- The caller executes the tool **within** the scope. OA does not execute it.
- On the execution returning a result, OA emits a `ToolCallEvent` carrying the result.
- On the execution raising, OA emits a `ToolCallFailedEvent` carrying the exception's type +
  message, and **re-raises** — the scope observes, it does not swallow. The caller's node body
  decides what to do with the exception (feed it back to the model as a tool message, abort,
  etc. — orchestration, out of scope here).

**OA observes; the caller runs.** The scope MUST NOT select which tool to call (it has no tool
registry), retry it, loop, or feed the result back to the model — those are orchestration. It
instruments a single caller-initiated execution and obtains the outcome as the value the execution
**yields to the scope**: in the inline-wrapping form, the return value of the caller-supplied call the
scope wraps (the wrapping invocation is instrumentation — capturing timing and the return value — not
tool ownership); in the start/complete form, a result the caller reports at completion. The result is
**opaque** to OA — the pre-serialization, language-idiomatic value as the tool produced it; OA has no
tool schema and does not parse, validate, or transform it. Tool selection / looping / result-feedback
live in the user's graph.

**Event-driven composition.** The scope MUST NOT assume synchronous inline execution. In an
event-driven runtime a tool call may dispatch as a separate step and return in a later
invocation / turn. The event contract is **emitted when the tool's outcome (result or failure)
is known**, not necessarily synchronously within a single function call. Implementations MAY
offer an inline-wrapping form (the common case) and a start/complete split (for deferred
execution where the result lands later), correlating the completion to its start via the
`call_id` / `tool_call_id`. The spec defines the event contract (one terminal `ToolCallEvent`
XOR `ToolCallFailedEvent` per execution, emitted at outcome time); the surface shape is
per-language / per-runtime.

**Identity under deferred execution.** When the start and the outcome fall in different
invocations / turns, the emitted event carries the **scope-entry identity** — the `node_name`,
`namespace`, `invocation_id`, `correlation_id`, `attempt_index`, `fan_out_index`, and
`branch_name` captured when the scope was *entered* (the node that initiated the tool
execution), NOT the ambient identity of the later turn where the outcome happened to land. The
tool execution belongs to the node that requested it; attributing it to a downstream turn's
context would mislocate it in the trace. This mirrors suspension §7's `invocation_id`-reuse
correlation across the suspend/resume boundary. Implementations capture the scope-entry
identity at start and carry it through to outcome-time emission. (The inline case is the
trivial instance — start and outcome share one context.)

**"Tool" is any instrumented function.** The scope is general — it observes any function the
caller wants recorded as a tool call, not only functions the model requested. `tool_call_id`
is populated when the execution satisfies an LLM `tool_calls` entry, and null otherwise (a
node-body utility the caller chooses to instrument as a tool).

### graph-engine §6 — `ToolCallEvent` (success)

Mirrors the identity / scoping baseline of `LlmCompletionEvent`, plus tool-specific fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that executed the tool. |
| `namespace` | sequence of strings | The calling node's namespace. |
| `attempt_index` | int | The node-level retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | Per pipeline-utilities §9. Null otherwise. |
| `branch_name` | string \| null | Per pipeline-utilities §11. Null otherwise. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `LlmCompletionEvent`. |
| `call_id` | string | A per-execution disambiguator minted by the implementation when the scope is entered. **Always present**; freshly minted per tool execution. (Distinct from `tool_call_id` — `call_id` is OA's own correlation token for this execution; `tool_call_id` is the provider's id from the model's request.) |
| `tool_name` | string | The name of the tool / function executed. Matches the `Tool.name` (llm-provider §4) when the execution satisfies a model request. |
| `tool_call_id` | string \| null | The `ToolCall.id` (llm-provider §3) of the `LlmCompletionEvent.output_tool_calls` entry this execution satisfies — the linkage back to the requesting LLM call. Null when the instrumented function did not originate from an LLM tool request. |
| `arguments` | mapping \| null | The arguments the tool was invoked with. For an LLM-originated call this is the parsed `ToolCall.arguments` mapping (llm-provider §3/§4 — an object schema); for a standalone instrumented function it is the caller-supplied argument shape. Null when the tool takes no arguments. Payload-bearing — observer-side privacy gating per the privacy paragraph below. |
| `result` | (language-idiomatic value) | The tool's return value, **as the tool produced it** (pre-serialization — a mapping, string, or any language-idiomatic value). The caller serializes it into the `tool` message content (a string per llm-provider §3); the §8.X observability mappings JSON-encode it for rendering. OA does not build the `tool` message — it observes the return value. Payload-bearing. |
| `latency_ms` | float \| null | Wall-clock latency of the tool execution measured at the scope boundary, in milliseconds. May be null when not measured. |

### graph-engine §6 — `ToolCallFailedEvent` (failure)

Mirrors `ToolCallEvent`'s identity / scoping / request-side fields (`tool_name`, `tool_call_id`,
`arguments`, `latency_ms`, `call_id`), with the success-only `result` absent and **two**
failure-specific fields:

| Field | Type | Description |
|---|---|---|
| (identity / scoping / `tool_name` / `tool_call_id` / `arguments` / `latency_ms` / `call_id`) | | Same definitions as on `ToolCallEvent`. |
| `error_type` | string \| null | The impl-level / language-level exception type — the exception class name (e.g., `"TimeoutError"`, `"ValueError"`) or a tool-defined error code. Null when no type is available. |
| `error_message` | string | The human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

**No `error_category`.** This is the deliberate departure from `LlmFailedEvent` /
`EmbeddingFailedEvent` / `RerankFailedEvent`. Those carry an `error_category` from the
llm-provider §7 normative enumeration because provider calls have a closed, spec-defined failure
taxonomy. Tool execution is arbitrary user / third-party code that can raise anything — there is
no normative category enumeration to assign, and inventing one would be a fiction. `error_type`
(the actual exception class) + `error_message` carry the failure faithfully.

### graph-engine §6 — mutual exclusion + exception flow + dispatch

- `ToolCallEvent` and `ToolCallFailedEvent` are **mutually exclusive** per tool execution.
  Implementations MUST NOT emit both for the same execution.
- The exception still propagates out of the instrumentation scope per the *re-raise* rule above;
  the typed event is dispatched alongside the exception, not in place of it. Caller code
  handling the exception sees the exception path unchanged; observers see the failure event.
- Both events MUST be dispatched on the observer delivery queue at the point the execution's
  outcome is known (after the result is in hand / after the exception is raised; before the
  result or exception flows back to the caller). Delivery follows graph-engine §6 — strict-serial
  across the invocation, async-delivered. Like the other typed variants, these carry no `phase`
  discriminator and are not subject to the `phases` filter; observers filter via type
  discrimination.

**Privacy posture.** `arguments` and `result` carry potentially sensitive payload data (the
tool's inputs and outputs — often user content or external-API data). The posture matches
`LlmCompletionEvent`'s — implementations populate the fields unconditionally; observer-side
gating applies at the rendering boundary per observability §5.5.4. The `disable_provider_payload`
flag (renamed from `disable_llm_payload` by proposal 0059) gates tool payload: its framing
extends to cover payload from any instrumented external operation, and a tool call is exactly
that (the canonical example being a tool that calls an external API). No new flag — reusing it
avoids the per-operation flag proliferation rejected in proposal 0059's alternatives. Custom
queryable observers consuming the tool events own their own redaction posture, identical to the
`LlmCompletionEvent` posture.

The flag gates **observability rendering only** — the span attributes and Langfuse fields below.
It does NOT affect the `result` the caller serializes into the `tool` message (the model needs
the tool's output to continue), nor the event-field population (fields are populated
unconditionally; gating is at the observer's rendering boundary). Setting
`disable_provider_payload=True` keeps tool inputs/outputs out of traces without changing what
the tool returns to the graph.

### observability §5.5 — OTel tool span

A new sub-subsection (numbered at Accept). A tool span emits per instrumented tool execution,
parented under the calling node's span.

**Span name** — `openarmature.tool.call`. This deliberately uses `.call` rather than the
sibling spans' `.complete` suffix (`openarmature.llm.complete` / `.embedding.complete` /
`.rerank.complete`): a tool execution is not a "completion," and `.call` matches the
terminology used everywhere else for this concept — the `ToolCallEvent` name, llm-provider §3's
"tool call," and Langfuse's `Tool` ("a tool call"). It is also deliberately distinct from the
upstream GenAI `execute_tool {gen_ai.tool.name}` span-name convention, which OA does not adopt
in v1 (Development — see below); when that subset reaches Stable and OA adopts it, the
span-name convention migrates per the §5.5.3.1 / 0047 mirror pattern.

**OA-namespace attributes**:

| Attribute | Type | Description |
|---|---|---|
| `openarmature.tool.name` | string | The tool name. Mirrors `gen_ai.tool.name`. |
| `openarmature.tool.call.id` | string | The `tool_call_id` (model-request linkage) when present; omitted otherwise. Mirrors `gen_ai.tool.call.id`. |
| `openarmature.tool.call.arguments` | string (JSON-encoded) | The tool arguments. Mirrors `gen_ai.tool.call.arguments`. Subject to `disable_provider_payload` (§5.5.4) and the §5.5.5 truncation contract. |
| `openarmature.tool.call.result` | string (JSON-encoded) | The tool result. Mirrors `gen_ai.tool.call.result`. Subject to `disable_provider_payload` (§5.5.4) and the §5.5.5 truncation contract. |
| `error.type` | string | On failure only — the exception type. Uses the **standard OTel `error.type`** attribute (not an OA-namespace name) since OTel models span errors with `error.type` generally, not via a `gen_ai.tool.*` attribute. Span status is `ERROR` (§4.2) with an OTel exception event carrying the `error_message`. |

**GenAI semconv adoption — peripheral, mirrored (per the carve-out).** The upstream OTel GenAI
semconv defines an `execute_tool` span (`gen_ai.operation.name = "execute_tool"`, span name
`execute_tool {gen_ai.tool.name}`) and tool attributes (`gen_ai.tool.name`, `gen_ai.tool.call.id`,
`gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, `gen_ai.tool.type`,
`gen_ai.tool.description`) — **all at Development status** (verified 2026-06-19 against the
`semantic-conventions-genai` registry; tracked in `docs/compatibility.md`). Under the GenAI
**de-facto-standard carve-out** (`GOVERNANCE.md` *External-dependency adoption*; observability §5.5),
the deciding line is installed-base recognition, not the maturity label — and `gen_ai.tool.*` is
assessed **peripheral**, not recognized-core: the tool-*execution* surface is an emerging convention
(the upstream span guidance directs application developers to *manually* instrument tool calls) without
the installed-base recognition of the core completion attributes (`gen_ai.system` /
`gen_ai.request.model` / `gen_ai.usage.*`). So OA does NOT emit the `gen_ai.tool.*` names in v1 — it
**mirrors** them: the OA-namespace attributes above are deliberately structured to mirror the upstream
shape (`openarmature.tool.name` ↔ `gen_ai.tool.name`; `openarmature.tool.call.{id,arguments,result}` ↔
`gen_ai.tool.call.{id,arguments,result}`), so adoption when the surface becomes recognized-core (or
Stable) is a clean **prefix swap** (`openarmature.tool.*` → `gen_ai.tool.*`), not a re-modeling. This
is the same mirror-then-adopt pattern proposal 0047 used for the cache-token attributes
(`openarmature.llm.cache_read.input_tokens` ↔ `gen_ai.usage.cache_read.input_tokens`). A follow-on
performs the adoption (the `gen_ai.tool.*` names + the `execute_tool` span-name convention, and
`gen_ai.tool.type` / `gen_ai.tool.description` if useful) when the surface reaches recognized-core /
Stable, per the §5.5.3.1 / 0047 pattern. The failure attribute uses the standard OTel `error.type`
(not a `gen_ai.tool.*` name), which is already Stable and needs no migration.

**Opt-out flags.** `disable_provider_payload` gates the payload attributes
(`openarmature.tool.call.arguments`, `openarmature.tool.call.result`); `disable_genai_semconv` is
not applicable in v1 (no GenAI semconv tool attributes are emitted — only the OA-namespace mirror
and the Stable `error.type`). `disable_llm_spans` is scoped to LLM completion spans and does not
gate tool spans (a future `disable_provider_spans` umbrella could cover both).

A *Typed tool events* note frames the `ToolCallEvent` / `ToolCallFailedEvent` surface as the
structured form of the tool-span attribute surface, paralleling the typed-event notes for LLM
completion / embedding.

### observability §8.4 — Langfuse Tool observation

A new sub-subsection. Tool executions map onto Langfuse's dedicated **`Tool`** observation type
(verified against current Langfuse docs at draft time — Langfuse defines `Tool` as "a tool call,
for example to a weather API," created via the SDK's `asType="tool"`). NOT a `Generation` with a
metadata discriminator.

Field mappings:

| Tool observation field | Source |
|---|---|
| `tool.input` | The tool `arguments`. Privacy-gated per `disable_provider_payload`; when the flag is `True` (default), NOT populated. |
| `tool.output` | The tool `result`. Privacy-gated per `disable_provider_payload`. |
| `tool.metadata.openarmature_tool_name` | The tool name. |
| `tool.metadata.openarmature_tool_call_id` | The `tool_call_id` when present. |
| `tool.level` / status | `DEFAULT` on success; `ERROR` (with `error_type` / `error_message` in metadata + statusMessage) on `ToolCallFailedEvent`. |

Tool observations nest under the calling node's Span observation, and trace-level cost / latency
rollup includes them alongside Generation / Embedding / Retriever observations.

## Conformance test impact

New fixtures under `spec/observability/conformance/` (numbered at Accept):

- **tool-call-event-dispatch** — an instrumented tool execution returning a result dispatches a
  `ToolCallEvent` with the full field set populated (`tool_name`, `arguments`, `result`,
  `latency_ms`, identity / scoping).
- **tool-call-failed-event-dispatch** — an instrumented tool execution that raises dispatches a
  `ToolCallFailedEvent` with `error_type` + `error_message` (and **no** `error_category` field),
  and the exception re-raises out of the scope.
- **tool-call-event-mutual-exclusion** — success emits exactly one `ToolCallEvent` / zero
  `ToolCallFailedEvent`; failure the reverse.
- **tool-call-id-links-to-llm-request** — a tool execution satisfying an
  `LlmCompletionEvent.output_tool_calls` entry carries the matching `tool_call_id`; a standalone
  instrumented function carries `tool_call_id = null`.
- **tool-call-payload-gating** — `disable_provider_payload=True` (default) suppresses
  `arguments` / `result` at the bundled OTel + Langfuse observers; `False` populates them.
- **otel-tool-span-attributes** — span name `openarmature.tool.call`, OA-namespace
  `openarmature.tool.*` attributes; asserts the Development `gen_ai.tool.*` attributes and the
  `execute_tool` span name are NOT emitted in v1.
- **langfuse-tool-observation** — dedicated `Tool` observation (`asType="tool"`), with
  `input` / `output` payload-gated and `tool_name` / `tool_call_id` in metadata; asserts the
  observation type is `Tool` (not `Generation`).

## Versioning

**MINOR bump** (pre-1.0). Additive: two new observer-union typed variants + a new node-body
instrumentation primitive + new OTel / Langfuse mapping sub-subsections; the
`disable_provider_payload` framing extends to tool payload with no rename and no new flag.
Observers that don't consume the tool events are unaffected (opt-in via type discrimination, and
events fire only when the caller instruments a tool execution).

Not a textual-only proposal — the reference implementation needs the instrumentation-scope
primitive + the observer-union variants + the OTel / Langfuse handlers. Tentative spec version
target deferred to Accept.

## Alternatives considered

1. **No instrumentation surface — infer tool execution from state / messages.** Reject — OA
   cannot observe user node-body code without an explicit hook. Inferring "a tool ran" from a
   `tool` message appearing in state is lossy (no timing, no failure, no arguments) and fragile.

2. **An `error_category` enum for tool failures (mirroring §7).** Reject — tool execution is
   arbitrary user / third-party code with no closed failure taxonomy. A normative category enum
   would be a fiction; `error_type` (the exception class) + `error_message` carry the failure
   honestly.

3. **A tool-specific `disable_tool_payload` flag.** Reject — flag proliferation, the exact
   anti-pattern proposal 0059 rejected when it consolidated to `disable_provider_payload`. A tool
   call is an instrumented external operation in the same payload-threat class; it rides the
   existing flag. (If independent tool-vs-provider payload gating ever becomes a real need, a
   follow-on can split it — see *Out of scope*.)

4. **OA runs the tool (a registry / executor primitive).** Reject *for 0063* — running and
   dispatching tools is the charter §4.4 **Tool System** (a core module: `ToolSet`, registry, MCP
   dispatch), deferred to its own proposal. 0063 is the **observability** layer and observes tool
   execution whoever runs it — a user node today, the §4.4 Tool System when it lands. The loop
   *topology* stays user-composed (charter §5.2's conditional edge); 0063 supplies the observability
   primitive both compose with.

5. **Reuse `LlmCompletionEvent.output_tool_calls` instead of a separate event.** Reject — that event is
   the model *requesting* tools; `ToolCallEvent` is the caller *executing* one of them. Different
   timing (request vs execution), different outcome (a tool can fail independently of the LLM
   call that requested it), and a request may be executed much later (event-driven). They are
   distinct events linked by `tool_call_id`.

6. **Langfuse `Generation` with `metadata.operation = "tool"`.** Reject — Langfuse defines a
   dedicated `Tool` observation type (verified at draft time) that carries the tool semantics
   (`input` / `output` / metadata) directly and integrates with trace rollup; the
   `Generation`-with-discriminator shape is the wrong fit, mirroring the embedding (0059) and
   rerank (0060) dedicated-type decisions.

7. **Adopt the GenAI `gen_ai.tool.*` / `execute_tool` attributes now.** Reject — the entire GenAI
   tool-execution surface is Development (verified 2026-06-19), and under the GenAI de-facto-standard
   carve-out it is assessed **peripheral** (not recognized-core), so OA mirrors it to the OA-namespace
   until the surface becomes recognized-core / Stable.

## Open questions

None at draft time. The two design points that could be open are settled in the text above:

- **GenAI tool semconv adoption** — assessed **peripheral** under the GenAI de-facto-standard
  carve-out (verified Development 2026-06-19); OA-namespace mirror in v1, follow-on adopts when the
  surface becomes recognized-core / Stable. Recorded in `docs/compatibility.md` at Accept.
- **Independent tool-payload privacy gating** — resolved by reusing `disable_provider_payload`;
  a future proposal can introduce per-operation gating if a consumer demonstrates the need.

## Out of scope

- **The agent tool-loop and tool dispatch.** The loop *topology* stays user-composed (charter §5.2's
  conditional edge); tool *dispatch / execution* (registry, `ToolSet`, MCP) is the charter §4.4 **Tool
  System** — a core module, deferred to its own proposal. This proposal supplies the observability
  primitive both compose with; it does not itself dispatch tools or own the loop.
- **Tool registry / discovery.** Mapping tool names to executables (local + MCP) is the charter §4.4
  **Tool System**'s concern — a core module, deferred to its own proposal, not 0063's.
- **Parallel tool execution.** When a model requests several tool calls, executing them
  concurrently is the existing fan-out / parallel-branches primitives over the `tool_calls`
  list — a documented pattern, not a new primitive. Each execution is instrumented with its own
  scope and emits its own event.
- **GenAI `gen_ai.tool.*` / `execute_tool` adoption** — mirrored as peripheral under the carve-out, deferred pending recognized-core / Stable.
- **Independent tool-payload privacy gating** — reuses `disable_provider_payload`; a follow-on
  may split it if needed.
- **Tool result caching / memoization** — an application concern, not a protocol primitive.
- **Streaming tool-call argument deltas** — the model *generating* a tool request's arguments
  incrementally is the streaming proposal's concern (and deferred there); this proposal observes
  the *execution* of an already-requested tool.
