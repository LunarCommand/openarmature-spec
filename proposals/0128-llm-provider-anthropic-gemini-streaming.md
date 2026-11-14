# 0128: Streaming Wire Mappings for Anthropic and Gemini

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-11-14
- **Targets:**
  - spec/llm-provider/spec.md: modifies §3 (an assistant message in a `Response` MAY have empty content when
    its `finish_reason` is `"content_filter"`, `"length"` or `"error"`; a request may not send one); modifies
    §3.1.1 and §3.1.4 (a text or thinking block MAY have empty text when it carries a signature); modifies §5
    (*Provider streaming support*: the §8.2 and §8.3 mappings implement streaming); modifies §6 (*Streaming
    assembly*: each mapping defines its terminal usage, and an empty delta emits no token event; the
    `finish_reason: "error"` bullet is distinguished from a vendor error event, which raises); modifies §8.2.1
    (the Anthropic body `stream` field becomes the wire realization of the declared `stream` argument, managed
    as §8.1.6 manages its own; an empty signed thinking block is sent back); modifies §8.2.2 and §8.3.2 (a
    content block or part type the mapping does not model is left out of the message and kept in `raw`);
    adds §8.2.6 *Streaming*; modifies §8.3.1 (the paragraph on `stream` says the mapping selects the
    streaming endpoint; an empty signed text part is sent back); modifies §8.3.2 (a prompt Gemini blocks
    before any candidate maps to a `"content_filter"` response); adds §8.3.6 *Streaming*; modifies §10
    (removes the *Out of scope* item that says these two mappings reject streaming)
  - spec/conformance-adapter/spec.md: modifies §5.16 (under `mapping: gemini`, `expected_wire_url` compares
    the URL's path and query, without its scheme, host or a `key` parameter)
  - docs/compatibility.md: the Anthropic and Gemini rows record the streaming facts checked at accept
  - spec/llm-provider/conformance/001-basic-completion.yaml (harness note: `stream_body` gains the named-event
    form and the Gemini chunk form; new `expected.token_events`; `raw_check` gains a streamed form)
  - spec/llm-provider/conformance/060-stream-unsupported-mapping-rejects.{yaml,md} (header and sidecar: the
    stub stands for a future mapping, no longer for §8.2 and §8.3)
  - spec/llm-provider/conformance/078-managed-anthropic-stream-reject.{yaml,md} (rewritten for the managed
    field in both modes)
  - spec/llm-provider/conformance/084 to 101 (new)
- **Related:** 0062 (the streaming contract this maps), 0037 (the §8.2 Anthropic mapping), 0038 (the §8.3
  Gemini mapping), 0126 (the streamed refusal rule in §8.1.6, which this mirrors where a vendor has one)
- **Supersedes:**

## Summary

0062 defined streaming once for every provider: `complete(stream: ...)` emits a `LlmTokenEvent` per
streamed delta and still returns the atomic `Response`, assembled so it cannot be told apart from a
non-streamed one. It mapped the contract onto one wire, the OpenAI-compatible SSE stream (§8.1.6), and
left the other mappings rejecting a `stream`-set call until their own wire handling was written.

This proposal writes it for the other two. §8.2.6 maps Anthropic's typed server-sent events, and §8.3.6 maps
Gemini's `streamGenerateContent`. Each mapping assembles the stream into its vendor's own atomic response
shape and then applies its existing response mapping unchanged, so every rule the atomic mapping states
(finish reasons, usage, thinking blocks, signatures, tool calls, structured output) carries over without
being restated, and §6's structural identity follows from the assembly rules below.

Four rules ride along, each a case the streamed and atomic paths both reach and neither spec text settles:

- a response with no content, such as a prompt Gemini blocks before answering, has a defined shape (§3);
- a thinking or text block that is empty but carries a signature is kept and sent back (§3.1.1, §3.1.4);
- a content block or part of a type the mapping does not model is left out of the message (§8.2.2, §8.3.2);
- an empty delta emits no token event (§6).

No new event, field or error category.

## Motivation

With 0037 and 0038 accepted, one `complete()` call runs against OpenAI-compatible servers, Anthropic and
Gemini, and a caller switches providers by binding a different one. Streaming is the exception. A node that
streams tokens to an observer, for a chat surface or for progress on a long generation, works on an
OpenAI-compatible server and raises `provider_invalid_request` on the other two. The caller has to know
which provider is bound, which is what the provider abstraction exists to hide.

Both vendors stream natively, so nothing stands in the way except the mapping text. 0062's *Out of scope*
named this follow-on.

## Detailed design

### llm-provider §3: an empty response

§3's rule for an `assistant` message without tool calls, that its content MUST be a non-empty string or a
non-empty block sequence, gains one exception:

> In a `Response` (§6) whose `finish_reason` is `"content_filter"`, `"length"` or `"error"`, the message's
> content MAY be the empty string, and a mapping that produces no content for such a response MUST use the
> empty string, not an empty block sequence. An `assistant` message with empty content and no tool calls in a
> request remains invalid and is rejected before sending with `provider_invalid_request` (§7).

The three finish reasons are the ones that report a response cut short: a filter blocked it, the token budget
ran out (Gemini's thinking models can spend a whole budget before any text), or the provider failed while
producing it, which §6 already calls "a degraded but parseable response". Reporting the finish reason and
usage serves the caller better than raising. A `"stop"` or `"tool_calls"` response with no content is still
invalid, so a provider sending only content the mapping cannot read surfaces as an error rather than as an
empty answer.

Where the provider supplies text, such as a refusal's, that text is the content, as today. A call that
supplied a `response_schema` and receives an empty response fails as `structured_output_invalid` (§7) with an
empty `output_content`, through the existing path, since empty content is not a conforming object.

The request-side rule keeps one behavior across vendors, which reject an empty assistant turn. A caller that
keeps such a response in a conversation's history decides what that turn says.

### llm-provider §3.1.1 and §3.1.4: an empty signed block

A text block's `text` and a thinking block's `text` are required to be non-empty. Both gain one exception:

> The text MAY be the empty string when the block carries a `signature`. Implementations MUST keep such a block
> on `Response.message.content` and MUST send it back unchanged with the message, as for any signed block
> (§3.1.7).

Both vendors produce one. Anthropic sends an empty thinking block with its signature when the request asks
for thinking display to be omitted, and the signature is what lets the next turn continue the reasoning.
Gemini, when streaming a response without a function call, may send its thought signature on a part with empty
text, and Google's guidance is to return every signature in its part, unmerged. Dropping either block breaks
the vendor's reasoning continuity. §8.2.1.1 and §8.3.1.1, which reject empty blocks before sending, exempt a
signed one. An empty block without a signature is still invalid.

### llm-provider §8.3.2: a blocked prompt

When Gemini blocks the prompt itself, it returns a successful response with `promptFeedback.blockReason`
set and no candidates. §8.3.2 gains a rule for it: the mapping returns a `Response` whose `message.content`
is the empty string, with no tool calls, and whose `finish_reason` is `"content_filter"`. `usage` follows
§8.3.2's usage rule, so `prompt_tokens` and `total_tokens` come from `usageMetadata` and `completion_tokens`
is `null` when `candidatesTokenCount` is absent, as for any counter the provider does not report. `raw`
keeps the response verbatim, `promptFeedback` included, so the block reason stays visible.

A candidate whose `finishReason` maps to `"content_filter"`, `"length"` or `"error"` and which has no parts
maps to empty content the same way, through the §3 exception.

### llm-provider §8.2.2 and §8.3.2: a block type the mapping does not model

Neither response mapping says what happens to a content block, or a Gemini part, of a type it does not
model. Vendors add such types: Anthropic's versioning policy allows new content block types, and both
vendors return blocks for server-side tools a caller declares. Without a rule, one implementation raises,
another drops the block and a third passes it through. Each mapping gains the same sentence:

> A content block (§8.2) or part (§8.3) of a type this mapping does not model is left out of
> `message.content` and `message.tool_calls`. It stays in `raw`, verbatim, and is not an error.

The modeled types are those §8.2.1.1 and §8.3.1.1 map. A streamed block of an unmodeled type emits no token
events (§8.2.6, §8.3.6). A response whose only content was unmodeled blocks has empty content, which §3
allows only for the three finish reasons above, so for any other finish reason it is
`provider_invalid_response` (§7), as an unparseable response is today. That includes an Anthropic
`pause_turn` response made only of unmodeled blocks, so §8.2.2's note that a caller MAY continue a paused
turn holds only for a turn the mapping can represent; the §8.2.2 transcription says so.

### llm-provider §5: provider streaming support

The last sentence of *Provider streaming support* becomes:

> The §8.1 OpenAI-compatible, §8.2 Anthropic and §8.3 Gemini mappings implement streaming (§8.1.6, §8.2.6,
> §8.3.6).

The rule above it, that a mapping without streaming rejects a `stream`-set call before sending, stays for
any future mapping. §10's *Out of scope* item saying these two mappings reject streaming is removed.

### llm-provider §6: streaming assembly

Three changes to *Streaming assembly* and the `finish_reason` list:

- **Usage.** The *Usage / finish_reason* bullet says usage is sourced from the terminal chunk, and the `raw`
  bullet says `raw` keeps the terminal chunk's usage block verbatim. Not every wire puts the totals in one
  chunk: Anthropic spreads usage across `message_start` and `message_delta`. Both bullets become: each
  §8.X mapping defines its stream's terminal usage, and `raw` keeps that usage verbatim. §8.1.6's terminal
  usage chunk, §8.2.6's merged usage and §8.3.6's last `usageMetadata` are the three definitions.
- **Empty deltas.** A delta whose text is the empty string emits no `LlmTokenEvent`, in every mapping.
  Vendors send empty deltas as carriers for other fields: a Gemini part that carries only a signature, an
  Anthropic thinking block with display omitted. An event for them would carry nothing and would make the
  event count differ between implementations.
- **`finish_reason: "error"`.** The bullet describes a provider that reports an internal error inside a
  response it still completes. It gains a sentence: a mapping whose wire delivers an error as a stream event
  (§8.2.6, §8.3.6) raises the §7 category that event maps to, rather than returning a `"error"` response.

### llm-provider §8.2.1: the Anthropic `stream` field

§8.2.1 today manages Anthropic's body `stream` field only to keep an extras `stream: true` off the wire,
since the mapping parsed an atomic body. With streaming implemented, the field is the wire realization of
the declared `stream` argument, managed as §8.1.6 manages its own: the mapping sends `stream: true` for a
`stream`-set call and sends no `stream` key otherwise. Because every call fixes a stream mode, the field is
managed on every call:

- an extras `stream` matching the call's mode, `true` on a `stream`-set call or `false` on a call without
  it, is a redundant no-op;
- a conflicting one, `false` on a `stream`-set call or `true` on a call without it, is rejected before
  sending with `provider_invalid_request` (§7).

The mapping MUST NOT drop a conflicting value silently or let it override the mode the call fixed.

### llm-provider §8.2.6: Anthropic streaming (new)

When `complete()` is called with `stream` set (§5), the Anthropic mapping sends `"stream": true` and
consumes the server-sent event stream.

**Assembly.** The mapping rebuilds Anthropic's atomic `Message` from the events and maps it to the §6
`Response` by §8.2.2, unchanged:

- `message_start` carries the `Message` with empty `content`. It is the assembled message's initial value,
  with every field it carries.
- Each content block arrives as `content_block_start`, any number of `content_block_delta` events and
  `content_block_stop`, keyed by `index`, the block's position in the final `content` array. Events for
  different indexes MAY interleave, and each applies to its own block. The block in `content_block_start` is
  the block's initial value, and each delta extends it:
  - `text_delta` appends `text` to a `text` block;
  - `citations_delta` appends its `citation` to the `text` block's `citations` list;
  - `thinking_delta` appends `thinking` to a `thinking` block;
  - `signature_delta` sets the `thinking` block's `signature`;
  - `input_json_delta` appends `partial_json` to a `tool_use` block's input buffer. The buffer starts empty,
    whatever `input` the start event carries, and the mapping parses it as JSON at `content_block_stop`,
    where the parsed value replaces the block's `input`. An empty buffer, which a tool with no arguments
    produces, keeps the start event's `input`. A buffer that does not parse follows §3's rule for
    unparseable arguments, as it would atomically.
  - A block that arrives whole, with no deltas, such as `redacted_thinking`, takes its value from
    `content_block_start`.
  - A block of a type the mapping does not model is assembled from its events like any other and then left
    out of the message by §8.2.2's rule, staying in `raw`. A delta type the mapping does not recognize is
    recorded on its block in `raw` under a `deltas` list, in arrival order, and changes nothing else.
- Each `message_delta` replaces the message's value for every key in its `delta`, among them `stop_reason`,
  `stop_sequence` and `stop_details`. Its `usage` counts are cumulative, so each key it carries replaces the
  same key in the message's `usage`.
- `message_stop` ends the stream.
- `ping` events are ignored. An event type the mapping does not recognize is ignored too, which Anthropic's
  versioning policy asks of clients, since it may add event types.

The assembled message's `stop_reason` maps by §8.2.2's table and its `usage` by §8.2.2's usage rule. The
merged `usage` is this mapping's terminal usage (§6). `raw` is the assembled `Message`.

**Token events.** Each `text_delta` is emitted as it arrives as `LlmTokenEvent(delta_kind: "content")`, and
each `thinking_delta` as `LlmTokenEvent(delta_kind: "reasoning")` (§5, §6 *Streaming assembly*), except an
empty one (§6). `citations_delta`, `signature_delta`, `input_json_delta` and a block that arrives whole emit
none. Tool-call input is reassembled into `message.tool_calls`, as §6 already says for every mapping. With
thinking display omitted, the thinking block assembles to an empty signed `ThinkingBlock` (§3.1.4) and emits
no reasoning events.

**Errors.** An HTTP error before the stream starts maps by §8.2.3. An `error` event inside the stream maps
its `error.type` through §8.2.3's table as the HTTP response with that type would map (`rate_limit_error` to
`provider_rate_limit`, `overloaded_error` to `provider_unavailable`, `invalid_request_error` to
`provider_invalid_request`, and so on); a type the table does not list maps to `provider_unavailable`. A
stream that ends before `message_stop`, for a dropped connection or a client timeout, is a connection error,
`provider_unavailable`. Either way the call raises, even when events follow the error, and the token events
already emitted stand, followed by the terminal `LlmFailedEvent` (graph-engine §6, 0062).

**Structured output.** §8.2.5's paths apply to the assembled message, and `parsed` is validated at the end,
as §6 says for every mapping. On the tool-coercion path the structured content arrives as `input_json_delta`
on the synthetic tool's block, so it emits no content token events.

### llm-provider §8.3.1: the Gemini `stream` paragraph

§8.3.1's paragraph on `stream` keeps its substance, since Gemini selects streaming by endpoint rather than a
body field: an extras `stream` is a stray body key and rides untouched. Its first sentences, which say §8.3
does not implement streaming, become a pointer to §8.3.6.

### llm-provider §8.3.6: Gemini streaming (new)

When `complete()` is called with `stream` set (§5), the Gemini mapping sends the same request body to
`POST /v1beta/models/{model}:streamGenerateContent?alt=sse` in place of `:generateContent`, and consumes the
server-sent event stream. Each `data:` line is a JSON `GenerateContentResponse` carrying the parts produced
since the previous one.

**Assembly.** The mapping merges the chunks into one `GenerateContentResponse` and maps it to the §6
`Response` by §8.3.2, unchanged:

- The `parts` of `candidates[0].content` across all chunks are concatenated in arrival order.
- Adjacent text parts join into one part when both have the same `thought` value and neither carries a
  `thoughtSignature`, since a stream splits one atomic text part across chunks. An absent `thought` is
  `false`. A part of any other type between two text parts separates them.
- A part that carries a `thoughtSignature` is never joined with another part, which Google's guidance
  forbids, and keeps its signature. One with empty text, which Gemini sends to deliver a signature when the
  response has no function call, becomes an empty signed `TextBlock` (§3.1.1). §8.3.2's signature capture
  then applies as it does atomically.
- A part of a type the mapping does not model is kept in arrival order and left out of the message by
  §8.3.2's rule, staying in `raw`.
- Each `functionCall` part is one complete call. On the Gemini API a call is never split across chunks:
  partial-argument streaming (`partialArgs` and `willContinue`, enabled by `streamFunctionCallArguments`) is a
  Vertex AI feature the Gemini API does not support.
- `finishReason` is the last value any chunk carried for `candidates[0]`.
- `usageMetadata` is the last one any chunk carried, taken whole. Gemini sends counts already accumulated with
  each chunk, so the mapping MUST NOT sum them across chunks and MUST NOT combine counters from different
  chunks: the last `usageMetadata` holds the totals, even where one of its counts is lower than an earlier
  chunk's. It is this mapping's terminal usage (§6).
- The other top-level fields (`modelVersion`, `responseId`, `promptFeedback`) take the last value any chunk
  carried.

`raw` is the merged response.

**Token events.** Each text part is emitted as it arrives, except an empty one (§6): a part with
`thought: true` as `LlmTokenEvent(delta_kind: "reasoning")`, any other text part as
`LlmTokenEvent(delta_kind: "content")`. A `functionCall` part, and a part of an unmodeled type, emit none.

**Blocked prompt.** A prompt Gemini blocks arrives as a chunk with `promptFeedback.blockReason` and no
candidates. It emits no token events, and the merged response maps by §8.3.2's blocked-prompt rule.

**Errors.** An HTTP error before the stream starts maps by §8.3.3. A chunk that carries a top-level `error`
object, which Gemini can send inside a stream that began with HTTP 200, maps by §8.3.3 on its `code` and
`status`, as the HTTP response with that error would, and ends the call. A stream that ends with no chunk
carrying either a `finishReason` or a `promptFeedback.blockReason`, for a dropped connection or a client
timeout, is a connection error, `provider_unavailable`. The call raises, and the token events already
emitted stand, followed by the terminal `LlmFailedEvent`.

**Structured output.** §8.3.5's paths apply to the merged response, and `parsed` is validated at the end.

### Vendor facts

The Anthropic facts above were checked on 2026-11-14 against Anthropic's streaming and citations
documentation: the event names and order, the five delta types (`text_delta`, `input_json_delta`,
`thinking_delta`, `signature_delta`, `citations_delta`), cumulative `message_delta` usage, `ping`, the
`error` event with `overloaded_error` as its example, whole `redacted_thinking` blocks, the empty
`thinking_delta` sent with thinking display omitted, and the instruction to ignore unknown event types.

Google's API reference documents `streamGenerateContent` without describing its chunks, so four Gemini facts
were checked on 2026-11-14 against Google's own SDKs and documentation and one widely used client:

1. **`?alt=sse`.** Google's Python SDK (`google-genai`) requests `{model}:streamGenerateContent?alt=sse` for
   both the Gemini API and Vertex AI.
2. **Function calls arrive whole.** Google's Go SDK documents `FunctionCall.partialArgs` and `willContinue`,
   the fields that carry a call split across chunks, as "not supported in Gemini API". Google Cloud's
   function-calling guide describes them as an opt-in Vertex AI feature for Gemini 3 and later, enabled by
   `streamFunctionCallArguments`.
3. **Usage is cumulative.** Google's SDKs pass each chunk's `usageMetadata` through without summing it.
   LangChain's Gemini integration subtracts the previous chunk's counts because "gemini api returns
   already-accumulated token counts with each chunk", and treats the last chunk's counts as ground truth,
   noting that Gemini 2.0 reports a lower prompt count in the final chunk. That observation is third-party,
   and the rule above, the last `usageMetadata` taken whole, holds whether or not it recurs.
4. **Signatures.** Google's thinking guide says not to concatenate parts with signatures or merge a signed
   part with an unsigned one, and that when streaming a response without a function call "the model may
   return the thought signature in a part with an empty text content part".

## Conformance test impact

### Harness note

llm-provider's harness note (fixture 001's header) gains:

- **`stream_body`, two more forms**, selected by the fixture's `mapping`:
  - **`mapping: anthropic`**: a list of `{event: <name>, data: <object>}` entries, each yielded as an SSE
    `event:` line and a `data:` line, in order. There is no `[DONE]` sentinel; the stream ends after the last
    entry.
  - **`mapping: gemini`**: a list of objects, each yielded as one `data:` line. Each is a
    `GenerateContentResponse` or, for an in-stream failure, `{error: {code, message, status}}`.
- **`expected.token_events`**, in a call's `expected:`: the `LlmTokenEvent`s the call emitted, a complete
  ordered list of `{delta_kind, delta}` entries compared as values (conformance-adapter §8.4). `[]` asserts
  that none were emitted. Fixtures that used the `no_token_events_emitted` claim keep it until the named-claims
  proposal settles it.
- **`expected.response.raw_check`, a streamed form**: on a streamed call, `required_keys` compares each listed
  top-level key of `raw` with the value the mapping's assembly rule defines (§8.2.6, §8.3.6), by exact deep
  equality. The atomic form is unchanged.

conformance-adapter §5.16's `expected_wire_url` compares the full URL as an exact string. Under
`mapping: gemini` it compares the path and query instead, without the scheme and host, which the harness's
mock server sets, and without a `key` query parameter, since an implementation MAY authenticate either by
header or by that parameter. `expected_wire_request` asserts the Anthropic body's `stream: true`.

### New fixtures

| Fixture | Mapping | Asserts |
|---|---|---|
| 084 | anthropic | A text stream: `stream: true` on the wire; `token_events` with one content entry per non-empty `text_delta`, in order, and none for an empty one; the assembled `Response`; usage merged from `message_start` (`input_tokens` 25, `output_tokens` 1) and `message_delta` (`output_tokens` 15 only), so `completion_tokens` is 15, which neither summing nor taking each event alone gives; `raw_check` on the assembled `usage` and `stop_reason`. |
| 085 | anthropic | Tool input: a call whose JSON is split mid-token across `input_json_delta` events, with `input: {}` on the start event, gives the parsed arguments; a tool with no arguments and no deltas gives `{}`; a buffer that does not parse gives `null`; no token events; `finish_reason: "tool_calls"`. |
| 086 | anthropic | Thinking: reasoning `token_events` per `thinking_delta`; the `ThinkingBlock` with its signature from `signature_delta`; a whole `redacted_thinking` block with no event; then text. A second case with display omitted: the empty signed `ThinkingBlock` is on the message and no reasoning event is emitted. |
| 087 | anthropic | `ping` events, an unknown event type, a block of an unmodeled type, an unknown delta type on a text block, and a `citations_delta`: the `Response` holds only the modeled blocks, the text block's `citations` list holds the citation, no token events come from any of them, and `raw_check` shows the unmodeled block and the unknown delta under `deltas`. |
| 088 | anthropic | An `error` event (`rate_limit_error`) after two text deltas: two content `token_events`, then `provider_rate_limit` raised. A second case: the same error followed by `message_stop` still raises. |
| 089 | gemini | A `{error: {code: 429, status: "RESOURCE_EXHAUSTED"}}` chunk after one text part: one content token event, then `provider_rate_limit` raised. |
| 090 | gemini | A text stream: `expected_wire_url` on the `:streamGenerateContent?alt=sse` path; `token_events` per non-empty text part; the merged `Response`; usage from the last `usageMetadata`, across chunks whose counts rise and whose last `promptTokenCount` is lower than an earlier one, and a final chunk with no `usageMetadata`; `raw_check` on the merged `usageMetadata`. |
| 091 | gemini | A `functionCall` part: no token event, `message.tool_calls`, `finish_reason: "tool_calls"`. |
| 092 | gemini | Thought parts: reasoning `token_events` for `thought: true` parts, joined into one `ThinkingBlock`, then content parts joined into one `TextBlock`. A signed text part is not joined with its neighbors and keeps its signature. A final chunk with an empty signed text part, its `finishReason` and its `usageMetadata` adds an empty signed `TextBlock` and no event. |
| 093 | gemini | A `finishReason` of `SAFETY` on the last chunk maps to `"content_filter"`, after the content token events already emitted. |
| 094 | gemini | Atomic: a blocked prompt (`promptFeedback.blockReason`, no candidates) returns a `Response` with empty content `""`, no tool calls and `finish_reason: "content_filter"`; `usage` with `prompt_tokens` and `total_tokens` set and `completion_tokens` `null`; `promptFeedback` on `raw`. |
| 095 | gemini | The same blocked prompt streamed: one chunk, `token_events: []`, the same `Response`, and no `provider_unavailable`. |
| 096 | anthropic | Atomic: a response with a text block and a block of an unmodeled type maps the text and leaves the other block on `raw` only. A second case: a response whose only block is unmodeled, with `stop_reason: "end_turn"`, raises `provider_invalid_response`. |
| 097 | gemini | An unmodeled part type between two text parts: streamed, it emits no event, keeps the text parts separate, is left out of the message and stays on `raw`; atomic, the same response maps the same way. |
| 098 | anthropic | Truncation: a stream that ends after two text deltas without `message_stop` emits the two content events, then raises `provider_unavailable`. |
| 099 | gemini | Truncation: a stream that ends after one text part without any `finishReason` emits the content event, then raises `provider_unavailable`. |
| 100 | gemini | Atomic empty responses: a candidate with `finishReason: "SAFETY"` and no parts returns `""` with `"content_filter"`; one with `finishReason: "MAX_TOKENS"` and no parts returns `""` with `"length"`. |
| 101 | gemini | An empty filtered response on a call with a `response_schema` raises `structured_output_invalid` with `output_content: ""`. |

Fixture 078 is rewritten for §8.2.1's managed field in both modes: an extras `stream: true` on a call without
`stream` and an extras `stream: false` on a `stream`-set call are each rejected before sending, and `true` on a
`stream`-set call and `false` on a call without it are each a no-op. Fixture 060's header and sidecar change
to say its stub stands for any future mapping that does not stream, not for §8.2 and §8.3. The other
streaming fixtures (llm-provider 059, 071, 073, 077 and observability 111 to 118) are unchanged.

## Versioning

MINOR. Two mappings gain a behavior: a `stream`-set call that each rejected now streams. A caller that relied
on the rejection is the only one affected, and the rejection was documented as temporary. The §3 and §3.1
exceptions relax constraints on what a mapping returns, the blocked-prompt and unmodeled-type rules define
cases that had no mapping, and the empty-delta rule removes events that carried no text. llm-provider's
`Latest` moves, and so does conformance-adapter's.

## Alternatives considered

1. **A separate per-chunk mapping for each vendor, without rebuilding the atomic response.** Rejected. It
   would restate every rule of §8.2.2 and §8.3.2 for chunks, and each restatement is a place the streamed and
   atomic paths could drift apart, which §6's structural identity forbids. Rebuilding the vendor's own atomic
   shape keeps one response mapping per vendor.
2. **Gemini's Interactions API** (`/v1beta/interactions?alt=sse`), which Google's guides now lead with for
   streaming. Rejected for this proposal. §8.3 maps `generateContent`, and streaming the same API through
   `streamGenerateContent` keeps the request mapping shared. Whether §8.3 should move to the Interactions API
   is a separate question.
3. **Emitting tool-call input deltas as token events.** Out of scope, as in 0062: `LlmTokenEvent` carries
   content and reasoning only.
4. **Joining a signed Gemini part into its neighbors**, so a stream that splits one text part gives one block.
   Rejected: Google's guidance forbids merging a signed part with another, and the merged part might not
   validate when sent back.
5. **Raising for any empty response.** Rejected for the three finish reasons that report a response cut
   short, where the finish reason and usage are worth more to the caller than an error. Kept for `"stop"`,
   where empty content means the mapping could not read what the provider sent.

## Open questions

1. **A signed Gemini text part continued by unsigned parts.** If a stream sends the first piece of a text part
   with its signature and the rest without one, §8.3.6 keeps them as separate blocks while the atomic response
   has one signed part. The joined text is the same, but the block count differs, an exception to §6's
   structural identity. Google's documentation does not say whether this happens, and it should be confirmed
   against a live stream before accept.

## Out of scope

- Prompt caching, a separate proposal.
- Gemini's Interactions API (see *Alternatives considered*).
- The rest of 0062's *Out of scope*: a node body consuming the stream directly, tool-call deltas as token
  events, first-token latency telemetry, and signaling a call-level retry restart on the token stream.
