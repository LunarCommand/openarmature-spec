# 0062: LLM Completion Streaming

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-09
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (§5 `complete()` gains an optional `stream` flag — when set, the provider consumes the LLM's streaming wire response and emits per-chunk token events, while the call STILL returns the atomic `Response` (return type unchanged); §6 gains a *Streaming assembly* contract specifying how the atomic `Response` is assembled from the stream (content concatenated, tool-call argument deltas reassembled into complete `tool_calls`, usage / finish_reason from the terminal chunk) so node bodies are agnostic to whether streaming was used; §8.1 OpenAI-compatible mapping gains a streaming sub-section (SSE wire handling); §5 also gains a *Provider streaming support* rule — a wire mapping that does not implement streaming MUST reject a `stream`-set call with `provider_invalid_request`, so the §8.2 Anthropic / §8.3 Gemini mappings reject streaming (defined behavior) until their streaming follow-ons land; §10 *Out of scope* — the "Streaming responses" item is lifted into scope, replaced by narrower deferrals); spec/graph-engine/spec.md (§6 — new `LlmTokenEvent` typed event variant on the observer event union, a within-call sub-event carrying per-chunk assistant **content** deltas (tool-call argument deltas are reassembled into the atomic `Response` but not emitted as token events in v1), correlated to the terminal `LlmCompletionEvent` by shared `call_id`); spec/observability/spec.md (§5.5 + §8 — note that the bundled OTel and Langfuse observers do NOT render `LlmTokenEvent` (no per-token spans / observations); trace recording stays atomic at the terminal `LlmCompletionEvent`, token events are for custom forwarding observers); plus new conformance fixtures under `spec/observability/conformance/` and `spec/llm-provider/conformance/`.
- **Related:** 0006 (llm-provider core — the `complete()` shape this extends), 0049 (typed `LlmCompletionEvent` — the terminal event the token stream precedes; the observer-union typed-event pattern this extends), 0058 (typed `LlmFailedEvent` — the terminal event for a mid-stream failure), 0057 (LlmCompletionEvent field-set extension — the identity / scoping baseline `LlmTokenEvent` mirrors), 0037 / 0038 (Anthropic / Gemini wire mappings — streaming wire handling for these is deferred to follow-ons, same as §8.1 is the first concrete streaming mapping here)
- **Supersedes:**

## Summary

Lifts LLM response streaming from llm-provider §10 *Out of scope* into a normative
capability. Today `complete()` is atomic — it sends the request, awaits the full response,
and returns a `Response`. For user-facing surfaces (a chat UI rendering the answer
token-by-token over WebSocket / SSE) the atomic shape means the client waits the full call
duration (commonly ~800ms–2s) before seeing anything; streaming surfaces the first token in
~150–300ms, which is a structural UX requirement for chat.

This proposal lands two layers:

1. **Provider streaming capability (llm-provider).** `complete()` gains an optional `stream`
   flag. When set, the provider MUST consume the LLM's streaming wire response and emit a
   `LlmTokenEvent` per chunk as it arrives — genuinely incremental, not a post-hoc chunking
   of the final response. Crucially, **the return type is unchanged**: `complete()` still
   returns the atomic `Response` at the end. The `stream` flag controls per-chunk event
   emission, NOT the return shape. A new §6 *Streaming assembly* contract specifies how the
   atomic `Response` is reassembled from the stream (content concatenated, tool-call argument
   deltas reassembled into complete `tool_calls`, usage / finish_reason from the terminal
   chunk) so node bodies, reducers, and the terminal `LlmCompletionEvent` are all agnostic to
   whether streaming was used.

2. **Token-event observability (graph-engine §6 + observability).** A new `LlmTokenEvent`
   typed event on the observer event union, carrying per-chunk deltas. A route handler
   attaches an invocation-scoped observer that filters by node and forwards `event.delta` to
   the WebSocket. The bundled OTel and Langfuse observers do NOT render token events —
   trace-level recording stays atomic at the terminal `LlmCompletionEvent` (the Generation /
   span collapse the stream back to one input/output). Token-level emission is for the UI,
   not for traces.

The §10 item's own wording — "incremental delivery of assistant content **and tool calls**"
— is honored: a streamed response can carry tool-call argument deltas, and the provider MUST
reassemble them into the complete `tool_calls` on the atomic `Response`. This is distinct
from tool-*execution* observability (the caller running a tool after the model requested it),
which is a separate forthcoming proposal.

## Motivation

**The gap is foundational, not cosmetic.** llm-provider §10 explicitly defers "Streaming
responses — incremental delivery of assistant content and tool calls." So there is no
streaming surface at any layer today. A downstream chat-agent consumer needs to stream the
final answer to a user-facing client; with an atomic `complete()` the client stares at a
spinner for the full call duration. First-token latency is the structural UX lever for chat,
and it is unreachable without provider-side streaming.

**Observability alone is insufficient.** A token-event on the observer union (the obvious
"streaming" surface) presupposes the provider is genuinely streaming from the wire. Define
only the event and an implementation could satisfy it by awaiting the full response and
emitting fake chunks — which surfaces nothing earlier and defeats the entire point. So the
load-bearing piece is the provider-side capability (the wire consumption + the genuine-
incremental contract); the event is the surface on top of it.

**Atomic recording must be preserved.** Streaming is a delivery concern for the consumer, not
a trace-shape change. A 500-token response must not fan out into 500 child spans, and the
Langfuse Generation must still show one input/output payload. So the trace-level mapping
(proposal 0024 / §8.4) is untouched — token events are consumed by the consumer's own
forwarding observer, ignored by the bundled OTel / Langfuse observers.

**Within-call, not cross-turn.** Token streaming happens entirely within a single
`complete()` call (the model streams its response over the call's duration). It does NOT
cross invocation / turn boundaries the way a deferred tool execution might in an event-driven
runtime — a streamed `complete()` is one held-open wire connection within one step. This
keeps the contract simple: no suspend/resume composition is required for streaming.

## Proposed change

### llm-provider §5 — `complete()` gains an optional `stream` flag

`complete()`'s signature extends with an optional `stream` parameter (keyword-only, or
per-language idiomatic equivalent), default `False` / absent — preserving the v0.4.0 atomic
behavior exactly for callers that don't opt in.

When `stream` is set:

- The provider MUST consume the LLM's **streaming wire response** (SSE / chunked transfer per
  the provider's API) rather than awaiting a single atomic response body.
- The provider MUST emit a `LlmTokenEvent` (graph-engine §6) on the observer delivery queue
  **per chunk, as the chunk arrives** — genuinely incremental. Implementations MUST NOT
  satisfy the contract by awaiting the full response and then emitting synthesized chunks;
  the first-token-latency benefit is the contract's purpose, and post-hoc chunking violates
  it. (This MUST states behavioral intent. Conformance can only verify the testable proxy —
  that the assembled `Response` equals the ordered concatenation of the streamed deltas
  (below) — not that chunks crossed the wire incrementally; a faked implementation passes
  conformance while violating the contract's purpose. Implementations are nonetheless
  expected to drive emission from the live wire stream.)
- The call STILL returns the atomic `Response` (§6) at completion. **The return type is
  unchanged** — `complete()` returns `Response` whether or not `stream` is set. The flag
  governs per-chunk event emission, not the return shape. This is the load-bearing
  distinction from the rejected "return an async iterator when streaming" alternative (see
  *Alternatives*): node bodies, reducers, retry middleware, and the terminal
  `LlmCompletionEvent` all see the same atomic `Response` either way.
- When no observer is attached (direct provider use outside an invocation), `stream` set is
  **observably identical** to `stream` unset — `complete()` returns the same atomic `Response`
  and there is no consumer for the token events. Implementations MAY still consume the wire
  incrementally for latency, but with no observer attached the behavior is indistinguishable
  from the atomic path.

**Provider streaming support.** Streaming is a per-§8.X-mapping capability, not a guaranteed
property of every provider. A provider whose wire-format mapping does NOT implement streaming
MUST reject a `stream`-set call at pre-send validation, raising `provider_invalid_request` (§7)
with a message identifying that the mapping does not support streaming. It MUST NOT silently
fall back to an atomic call (which would hide that the requested mode was unavailable) and MUST
NOT fail opaquely mid-call. This is the same mold as `tool_choice` validation — a request shape
a mapping cannot satisfy is a pre-send `provider_invalid_request`. The §8.1 OpenAI-compatible
mapping implements streaming (below) and so accepts `stream`-set calls; the §8.2 Anthropic and
§8.3 Gemini mappings do NOT implement streaming in this proposal and therefore reject
`stream`-set calls until their streaming wire handling lands in a follow-on. So this proposal
defines `stream`'s behavior across all three mappings: OpenAI streams, Anthropic / Gemini reject
(pending their follow-ons).

Interaction with existing parameters:

- **`tools` / `tool_choice`** — a streamed response MAY contain tool calls. The provider
  reassembles streamed tool-call argument deltas into complete `tool_calls` on the atomic
  `Response` per the §6 assembly contract below.
- **`response_schema`** — when supplied with `stream` set, the structured `parsed` value is
  assembled and validated at the **terminal** (partial JSON cannot be validated mid-stream);
  token deltas carry the partial unparsed content. `parsed` on the atomic `Response` is
  identical to the non-streamed case.
- **`retry` (§7.1, call-level)** — the §7.1 retry loop runs *inside* a single `complete()`
  call (it produces N per-attempt OTel spans within one call). So a streamed call with `retry`
  set is **one** `complete()` call with **one** `call_id`: each internal wire attempt streams
  its token events under that one `call_id`; a transient is caught and retried **internally** —
  it does NOT raise out of `complete()`, re-enter it, or emit a per-attempt typed event; only
  retry exhaustion raises the §7 category exception. The terminal `LlmCompletionEvent`
  (success) or `LlmFailedEvent` (exhausted) fires **once** at the end (per graph-engine §6's
  one-typed-event-per-`complete()`-call mutual exclusion). The token event's `attempt_index` is
  the **node-level** retry index (see the field table below) — it does NOT advance across §7.1
  wire attempts (the node attempted the call once; the retry was internal). The per-wire-attempt
  index lives on the §7.1 OTel span (`openarmature.llm.attempt_index`), not on the token event.
- **Per-node retry (pipeline-utilities §6.1)** — `RetryMiddleware` re-runs the whole node,
  re-calling `complete()` once per attempt. Each re-call is a **fresh** `complete()` with its
  own `call_id`; the streams are distinct calls, not wire attempts within one call. A consumer
  sees a new `call_id` per node-run, and the node-level `attempt_index` advances per run.
- **Multi-attempt streams (consumer guidance).** A streamed call that restarts (either retry
  layer) makes a forwarding observer see a prior attempt's partial tokens followed by the next
  attempt's — restarted output from the end consumer's view. Under **per-node** retry this is
  decidable: a fresh `call_id` (and an advanced node-level `attempt_index`) signals a new
  attempt, so a forwarding observer SHOULD reset its forwarded buffer when the `call_id`
  changes. Under **call-level (§7.1)** retry there is **no token-event-level restart signal in
  v1** — the wire attempts share one `call_id` and the node-level `attempt_index` does not
  advance; a forwarder that needs §7.1-restart detection consults the per-wire-attempt index on
  the §7.1 OTel span, or simply uses per-node retry for streamed UI calls. Token-event-level
  signaling of call-level-retry restarts is deferred (see *Out of scope*) — adding a
  per-wire-attempt field to `LlmTokenEvent` is additive if a real consumer needs it.

### llm-provider §6 — *Streaming assembly* contract

A new sub-section specifying how the atomic `Response` is assembled from the stream, so the
streamed and non-streamed paths produce structurally identical `Response` records:

- **Content** — the `message.content` is the ordered concatenation of the streamed content
  deltas. Reasoning-content blocks (§3.1.4 / §3.1.5) assemble into their respective blocks on
  the terminal `Response` when the provider streams them, but are NOT surfaced as
  `LlmTokenEvent` deltas in v1 (see *Out of scope*). So the terminal `Response` is
  shape-identical to the non-streamed case (content + reasoning blocks present), while the
  live `LlmTokenEvent` stream carries **answer content only** — the right default for
  forwarding (you stream the answer to a user, not raw reasoning or partial tool-call args).
- **Tool calls** — streamed tool-call argument deltas are reassembled into complete `ToolCall`
  records (`id`, `name`, `arguments`) on `message.tool_calls`, in the order the provider
  streamed them. The reassembled `arguments` MUST parse identically to the non-streamed case
  (a mapping when valid JSON; `null` when unparseable, per §3's existing tool-call validation).
  This reassembly is provider-internal — the tool-call deltas are NOT emitted as `LlmTokenEvent`s
  in v1 (only the complete `tool_calls` on the terminal `LlmCompletionEvent` is surfaced; see
  *Out of scope*).
- **Usage / finish_reason** — sourced from the terminal chunk (providers emit usage and the
  finish reason on the final streamed event; OpenAI requires `stream_options` to include usage
  — see §8.1 below).
- **`raw`** — the parsed provider response. For a streamed call, `raw` is the assembled
  representation of the streamed events (implementation-defined assembly; MUST be populated per
  §6's existing `raw` contract). Within-implementation wire-byte stability (§8) applies to the
  assembled form.
- **Structural identity** — a `Response` assembled from a stream MUST be indistinguishable in
  shape from a `Response` returned atomically for the equivalent non-streamed call. This is
  the contract that lets every downstream consumer (node bodies, reducers, the terminal typed
  events, the OTel / Langfuse mappings) ignore whether streaming was used.

### llm-provider §8.1 — OpenAI-compatible streaming wire handling

A streaming sub-section under the OpenAI-compatible mapping (the first concrete streaming wire
mapping; Anthropic §8.2 and Gemini §8.3 streaming deferred to follow-ons — until then those
mappings reject `stream`-set calls per the §5 *Provider streaming support* rule):

- Request: `stream: true` in the request body; `stream_options: {include_usage: true}` so the
  terminal chunk carries usage (OpenAI omits usage from streamed responses otherwise).
- Wire: Server-Sent Events; each `data:` line is a chunk with `choices[].delta` carrying either
  a `content` delta or `tool_calls` deltas (each with an `index`, and partial `id` / `name` /
  `arguments` fields); the `[DONE]` sentinel terminates the stream.
- Content deltas map to `LlmTokenEvent` (content-only). Tool-call deltas are reassembled into
  `message.tool_calls` per the §6 assembly contract but are NOT emitted as token events in v1.
- `finish_reason` is set on the last content-bearing chunk's `choices[].finish_reason`; when
  `stream_options.include_usage` is set, a final chunk with empty `choices` carries `usage`,
  followed by the `[DONE]` sentinel.

The exact streamed-chunk shapes above (the `finish_reason` / `usage` chunk positioning, the
`stream_options` flag, the `[DONE]` sentinel, tool-call delta fields) are asserted from the
OpenAI streaming format and **MUST be verified against current OpenAI streaming docs at Accept**
before this §8.1 text becomes normative, per the external-dependency verification discipline
(`docs/compatibility.md`).

### llm-provider §10 — lift the streaming deferral

Remove the "Streaming responses — incremental delivery of assistant content and tool calls"
item (now in scope). Replace with the narrower deferrals this proposal does NOT cover (see
*Out of scope* below): node-body stream consumption (async-iterator return), per-vendor
streaming wire mappings beyond OpenAI-compatible, and streaming for non-completion provider
operations.

### graph-engine §6 — `LlmTokenEvent` typed event

A new typed event variant on the observer event union. Unlike `LlmCompletionEvent` /
`LlmFailedEvent` (and the embedding / rerank pairs), `LlmTokenEvent` is a **within-call
sub-event**, not a call-outcome event — it carries one delta of an in-progress call. It is
therefore **unpaired**: there is no `LlmTokenFailedEvent`. A streamed call that fails mid-
stream emits the partial token events it produced, then the terminal `LlmFailedEvent`
(proposal 0058) fires when the §7 category exception raises; the call's outcome is carried by
the terminal `LlmCompletionEvent` / `LlmFailedEvent`, not by the token events.

Field set — mirrors `LlmCompletionEvent`'s identity / scoping baseline, plus the per-chunk
content delta. Request-side and response-side payload fields are deliberately absent (they are
invariant across the stream and live on the terminal `LlmCompletionEvent`; consumers correlate
via `call_id`):

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace. |
| `attempt_index` | int | The **node-level** retry-attempt index (0 on the first attempt), sourced from the same per-node retry context as `LlmCompletionEvent.attempt_index`. It does NOT vary across §7.1 *call-level* wire attempts (those share one `call_id` and one node-level index — see the `retry` interaction note above); the per-wire-attempt index lives on the §7.1 OTel span, not here. |
| `fan_out_index` | int \| null | Per pipeline-utilities §9. Null otherwise. |
| `branch_name` | string \| null | Per pipeline-utilities §11. Null otherwise. |
| `provider` | string | The LLM provider identifier. |
| `model` | string | The model identifier the request was made against. |
| `call_id` | string | The per-call disambiguator minted by the implementation for this `complete()` call. **Matches the `call_id` on the terminal `LlmCompletionEvent` / `LlmFailedEvent` for the same call** — this is the linkage observers use to associate a token stream with its eventual completion. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `LlmCompletionEvent`. |
| `chunk_index` | int | Monotonic per call, starting at 0. Establishes delta ordering within the call's token stream. |
| `delta` | string | The assistant **content** text delta for this chunk. `LlmTokenEvent` carries answer content only — tool-call argument deltas are reassembled into the atomic `Response.message.tool_calls` (§6) for correctness but are NOT emitted as token events in v1 (see *Out of scope*), and reasoning-content deltas are likewise not emitted. So `delta` is always a content fragment; no payload discriminator is needed. |

Dispatch + ordering: `LlmTokenEvent`s are dispatched on the observer delivery queue in
`chunk_index` order, all **before** the terminal `LlmCompletionEvent` for the same call.
Delivery follows the standard graph-engine §6 *Event delivery* rules — strict-serial across
the invocation, async-delivered. Token events fire ONLY when the call was made with `stream`
set; a non-streamed call emits no token events (backward-compatible). Like the other typed
variants, `LlmTokenEvent` carries no `phase` discriminator and is NOT subject to the `phases`
subscription filter; observers filter via type discrimination.

**Privacy posture.** The `delta` field carries model output (payload-bearing). The bundled OTel and Langfuse observers do NOT render token events (see below), so
there is no bundled-observer rendering surface to gate. Custom observers consuming token
events (the UI-forwarding case) are responsible for their own redaction posture, identical to
the custom-observer posture for `LlmCompletionEvent` (observability §9). The terminal
`LlmCompletionEvent`'s payload remains gated by `disable_provider_payload` at the bundled
observers as today; streaming changes nothing there.

### observability §5.5 + §8 — bundled observers ignore token events

A note in §5.5 (OTel) and §8 (Langfuse): the bundled observers do NOT render `LlmTokenEvent`
— no per-token spans, no per-token observations. Trace-level recording stays atomic at the
terminal `LlmCompletionEvent`: the OTel `openarmature.llm.complete` span and the Langfuse
Generation collapse the streamed deltas back into one input/output payload at end-of-call,
exactly as for a non-streamed call. A 500-token response produces one span / one Generation,
not 500 children. `LlmTokenEvent` exists for custom forwarding observers (per §9); the
backend mappings consume the terminal events only.

## Conformance test impact

### New fixtures under `spec/observability/conformance/`

- **`0XX-llm-token-event-dispatch-on-stream`** — A `complete(stream=...)` call with a mocked
  streaming provider returning N content chunks. Asserts N `LlmTokenEvent`s observed with
  monotonic `chunk_index`, the ordered concatenation of `delta`s equals the terminal
  `LlmCompletionEvent`'s assembled content, and all token events share the terminal event's
  `call_id`.
- **`0XX-llm-token-event-absent-without-stream`** — The same graph with `stream` unset emits
  zero `LlmTokenEvent`s and one `LlmCompletionEvent` (backward-compat / opt-in lockdown).
- **`0XX-streamed-tool-call-reassembles-no-token-events`** — A streamed response carrying
  tool-call argument deltas: asserts **no** tool-call `LlmTokenEvent`s are emitted (token events
  carry content only), and the terminal `LlmCompletionEvent`'s assembled
  `Response.message.tool_calls` is complete and parses identically to the non-streamed
  equivalent (reassembly is provider-internal). Locks the "reassemble into the atomic Response,
  don't emit as token events" contract.
- **`0XX-llm-token-event-then-failure-mid-stream`** — A stream that errors partway: asserts
  the partial token events fire, then the terminal `LlmFailedEvent` (no `LlmTokenFailedEvent`),
  and the §7 exception raises out of `complete()`.
- **`0XX-llm-token-event-call-id-links-to-completion`** — Two streamed calls in one invocation:
  asserts each call's token events carry that call's `call_id`, distinct across calls, each
  matching its terminal `LlmCompletionEvent`.
- **`0XX-llm-token-event-call-level-retry-one-call-id`** — A streamed `complete(retry=...)`
  call whose first wire attempt fails transiently and second succeeds: asserts all token events
  (across both wire attempts) share **one** `call_id` and **one** node-level `attempt_index`
  (the call-level wire attempt does NOT advance it — per the §7.1 interaction note), exactly
  **one** terminal `LlmCompletionEvent` fires (no per-attempt typed event for the caught
  transient, per the §6 one-event-per-call mutual exclusion), and the assembled `Response`
  reflects the successful attempt only. Locks the §7.1-vs-per-node distinction and the
  one-typed-event-per-`complete()`-call contract under streaming.
- **`0XX-otel-langfuse-atomic-under-stream`** — A streamed call with bundled OTel + Langfuse
  observers attached: asserts exactly one `openarmature.llm.complete` span and one Generation
  observation (no per-token children), with the full assembled input/output — i.e., token
  events are not rendered by the bundled observers.

### New fixtures under `spec/llm-provider/conformance/`

- **`0XX-openai-streaming-wire`** — The §8.1 streaming wire path: mocked SSE response
  (`data:` chunks with `choices[].delta`, `stream_options` usage on the terminal chunk,
  `[DONE]` sentinel). Asserts the assembled `Response` (content, tool_calls, usage,
  finish_reason) equals the equivalent non-streamed response.
- **`0XX-stream-unsupported-mapping-rejects`** — A provider mapping configured as
  streaming-unsupported (a synthetic mock standing in for a not-yet-streaming §8.X mapping
  such as Anthropic / Gemini): a `stream`-set call raises `provider_invalid_request` at
  pre-send validation, with no token events and no atomic fallback. Locks the §5 *Provider
  streaming support* rejection contract.

Final fixture numbers assigned at Accept.

## Versioning

**MINOR bump** (pre-1.0). Additive at every surface that matters:

- `complete()`'s new `stream` parameter is optional, default-off — existing callers are
  unaffected; the atomic path is byte-for-byte the v0.4.0 behavior.
- The §6 *Streaming assembly* contract describes how the streamed path produces a `Response`
  structurally identical to the atomic path — no change to the `Response` shape.
- `LlmTokenEvent` is a new observer-union variant; observers that don't consume it are
  unaffected (it's opt-in via type discrimination, and only fires when `stream` is set).
- Lifting the §10 *Out of scope* item is the one "removal," replaced by narrower deferrals.

Not a textual-only proposal: the reference implementation's OpenAI provider needs real
streaming-wire consumption + reassembly, and the observer union grows a variant. Tentative
spec version target deferred to Accept.

## Alternatives considered

1. **Invocation-level streaming API (`graph.stream_invocation(stream_node=...)`).** Reject —
   the `stream_node` hint is invoke-time static, but in a multi-turn tool-use shape whether a
   given LLM call is the terminal user-facing one is decided at runtime by the model's
   tool-call output. A static node name can't express "stream whichever turn ends up
   terminal." It also forces single-consumer-per-invocation and new framework plumbing to
   route a node's tokens out.

2. **`complete()` returns an async iterator when `stream` is set.** Reject — overloads the
   return type (`Response` vs `AsyncIterator[Chunk]` depending on a flag), hostile to static
   typing in both Python and TypeScript, and forces every node body to disambiguate at the
   call site. It also pushes "publish each chunk to a side-channel" plumbing into node bodies.
   The chosen design keeps the return type `Response` unconditionally and surfaces deltas via
   the observer union — the orchestration-free, type-stable shape. (The `stream` flag here
   controls event emission, not the return type; that is the whole distinction from this
   alternative.)

3. **Define `LlmTokenEvent` only; leave provider streaming impl-defined.** Reject — without a
   normative provider-side genuine-streaming contract, an implementation could await the full
   response and emit synthesized chunks, surfacing nothing earlier and defeating the first-
   token-latency purpose. The provider capability is the load-bearing half.

4. **A paired `LlmTokenFailedEvent`.** Reject — token events are within-call sub-events, not
   call outcomes. A call's failure is already carried by the terminal `LlmFailedEvent`
   (proposal 0058). Pairing a failure variant onto a sub-event would duplicate the outcome
   surface and create ambiguity about which event is authoritative for the call's result.

5. **Per-token OTel spans / Langfuse observations.** Reject — a 500-token response would fan
   out into 500 child spans / observations, blowing up trace storage and UI rendering for no
   diagnostic gain. Trace recording stays atomic at the terminal event; token events are for
   the consumer's forwarding observer, not for the backend mappings.

6. **Streaming via a `RuntimeConfig` field instead of a `complete()` parameter.** Reject —
   streaming is a per-call control-flow decision (this call streams to a UI; that internal
   call doesn't), more discoverable as an explicit `complete()` parameter than buried in the
   sampling-config record. `RuntimeConfig` carries sampling parameters; `stream` is an
   operation mode.

## Open questions

None remaining at draft time. The two questions surfaced during drafting are resolved in the
proposal text above (collected here for retrieval).

**Resolved at Draft:**

- **Node-body stream consumption** — decided: **v1 is observer-only.** The actual demand (the
  downstream agent streaming its answer to a UI) is the observer-forwarding case; the node body
  gets the atomic `Response` at the end and doesn't need the stream. Direct node-body
  consumption (incremental parsing, early-stop) has no current consumer, and an async-iterator
  return mode is purely additive later. Deferred per *Out of scope*.
- **Tool-call-delta emission** — decided: **content-only token events.** `LlmTokenEvent` carries
  answer content only; tool-call argument deltas are reassembled into the atomic `Response`
  (correctness, unchanged) but are not emitted as token events. Rationale: the demand is content
  streaming; the "show tool progress live" UI case is better served by the tool-execution
  observability proposal's `ToolCallEvent` (the tool *running*) or the complete `tool_calls` on
  the terminal `LlmCompletionEvent`, not by streaming the model *generating* the request's args.
  This also keeps `LlmTokenEvent` lean (no `delta_kind` discriminator, no tool-call-delta fields)
  and cleanly separates 0062 (streams the answer) from the tool-exec proposal (observes
  execution). Deferred per *Out of scope*.

## Out of scope

- **Node-body direct stream consumption** (async-iterator return) — v1 is observer-only; a
  node body consuming the stream directly (incremental parsing, early-stop) is deferred, with an
  opt-in iterator return offered alongside the atomic return if a consumer surfaces.
- **Tool-call-delta streaming as token events** — `LlmTokenEvent` carries content only; tool-call
  argument deltas are reassembled into the atomic `Response` but not emitted as token events in
  v1. The "show tool progress live" UI case is served by the tool-execution observability
  proposal's `ToolCallEvent` (the tool *running*), not by streaming the model generating the
  request's arguments. A follow-on MAY add tool-call-delta emission (a `delta_kind` discriminator
  + tool-call fields on `LlmTokenEvent`) if a concrete consumer needs it — additive.
- **Per-vendor streaming wire mappings beyond OpenAI-compatible** — Anthropic §8.2 and Gemini
  §8.3 streaming handling land as follow-ons, same per-vendor deferral pattern as the
  embedding / rerank wire mappings. Until then those mappings reject `stream`-set calls
  (§5 *Provider streaming support*) — so the behavior is defined, not undefined, for the
  not-yet-streaming mappings.
- **Streaming for non-completion provider operations** — embedding / rerank streaming (some
  providers stream large result sets) is a separate concern; not v1.
- **Per-node streaming of partial state updates** — the graph-engine §7 *Out of scope*
  "Streaming outputs" item (per-node partial state deltas) is a different concern and stays
  out of scope; this proposal streams an LLM call's response, not a node's state.
- **Tool-execution observability** — observing the caller *running* a tool after the model
  requested it (`ToolCallEvent`) is a separate forthcoming proposal at a different layer;
  this proposal covers the model *requesting* tools in a streamed response (the tool-call
  argument deltas), not their execution.
- **First-token / inter-token latency telemetry** — surfacing first-token-ms / inter-token-ms
  as span attributes is a possible follow-on; not load-bearing for v1.
- **Token-event-level signaling of call-level-retry restarts** — under §7.1 call-level retry,
  the wire attempts share one `call_id` and node-level `attempt_index`, so a forwarding
  observer cannot detect a §7.1 restart from token events alone (the per-wire-attempt index is
  on the §7.1 OTel span). A follow-on MAY add a per-wire-attempt field to `LlmTokenEvent` if a
  consumer needs token-event-level §7.1-restart detection; per-node retry restarts are already
  detectable via the `call_id` change.
- **Streaming reasoning / thinking content as token deltas** — reasoning-content blocks
  (§3.1.4 / §3.1.5) assemble into the terminal `Response` when the provider streams them, but
  are NOT emitted as `LlmTokenEvent` deltas in v1 (`LlmTokenEvent` carries content only).
  Forwarding raw partial reasoning to an end user is rarely wanted; a follow-on MAY add
  reasoning-delta emission if a concrete consumer needs partial-reasoning streaming.
