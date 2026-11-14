# 0128: Streaming Wire Mappings for Anthropic and Gemini

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-11-14
- **Targets:**
  - spec/llm-provider/spec.md: modifies §3 (an assistant message's content MAY be empty when its response's
    `finish_reason` is `"content_filter"`); modifies §5 (*Provider streaming support*: the §8.2 and §8.3
    mappings implement streaming); modifies §8.2.2 and §8.3.2 (a content block or part type the mapping does
    not model is left out of the message and kept in `raw`); modifies §8.2.1 (the Anthropic body `stream`
    field becomes the wire realization of the declared `stream` argument, managed as §8.1.6 manages its
    own); adds §8.2.6 *Streaming*; modifies §8.3.1 (the paragraph on `stream` says the mapping selects the
    streaming endpoint); modifies §8.3.2 (a prompt Gemini blocks before any candidate maps to a
    `"content_filter"` response); adds §8.3.6 *Streaming*
  - docs/compatibility.md: the Anthropic and Gemini rows record the streaming facts checked at accept
  - spec/llm-provider/conformance/001-basic-completion.yaml (harness note: `stream_body` gains the named-event
    form and the Gemini chunk form)
  - spec/llm-provider/conformance/084 to 097 (new)
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
shape and then applies its existing response mapping unchanged, so §6's structural identity holds by
construction, and every rule the atomic mapping already states (finish reasons, usage, thinking blocks,
signatures, tool calls, structured output) carries over without being restated.

One contract change rides along. A filtered response can have no text at all, as when Gemini blocks a
prompt before producing any candidate, and §3 requires an assistant message without tool calls to have
content. §3 gains an exception for a `"content_filter"` response, and §8.3.2 maps the blocked prompt. No new
event, field or error category.

## Motivation

With 0037 and 0038 accepted, one `complete()` call runs against OpenAI-compatible servers, Anthropic and
Gemini, and a caller switches providers by binding a different one. Streaming is the exception. A node that
streams tokens to an observer, for a chat surface or for progress on a long generation, works on an
OpenAI-compatible server and raises `provider_invalid_request` on the other two. The caller has to know
which provider is bound, which is what the provider abstraction exists to hide.

Both vendors stream natively, so nothing stands in the way except the mapping text. 0062's *Out of scope*
named this follow-on.

## Detailed design

### llm-provider §3: an empty filtered response

§3's rule for an `assistant` message without tool calls, that its content MUST be a non-empty string or a
non-empty block sequence, gains one exception:

> When the response's `finish_reason` is `"content_filter"` (§6), the message's content MAY be the empty
> string. A provider's filter can block a response before any text is produced, and the response still
> reports what happened.

A filtered response is a `Response`, not an error, in every mapping: OpenAI's `content_filter` and refusal
(§8.1.2), Anthropic's `refusal` (§8.2.2) and Gemini's safety reasons (§8.3.2). Where the provider supplies
text, such as a refusal's, that text is the content, as today. The exception covers a filtered response that
carries none. A call that supplied a `response_schema` and receives one fails as `structured_output_invalid`
(§7) with an empty `output_content`, through the existing path, since empty content is not a conforming
object.

### llm-provider §8.3.2: a blocked prompt

When Gemini blocks the prompt itself, it returns a successful response with `promptFeedback.blockReason`
set and no candidates. §8.3.2 gains a rule for it: the mapping returns a `Response` whose `message.content`
is the empty string, with no tool calls, and whose `finish_reason` is `"content_filter"`. `usage` follows
§8.3.2's usage rule from `usageMetadata`, and `raw` keeps the response verbatim, `promptFeedback` included,
so the block reason stays visible. A candidate that carries a filtering `finishReason`, such as `SAFETY`, and
no parts maps the same way, through the §3 exception.

### llm-provider §8.2.2 and §8.3.2: a block type the mapping does not model

Neither response mapping says what happens to a content block, or a Gemini part, of a type it does not
model. Vendors add such types: Anthropic's versioning policy allows new content block types, and both
vendors return blocks for server-side tools a caller declares. Without a rule, one implementation raises,
another drops the block and a third passes it through. Each mapping gains the same sentence:

> A content block (§8.2) or part (§8.3) of a type this mapping does not model is left out of
> `message.content` and `message.tool_calls`. It stays in `raw`, verbatim, and is not an error.

The modeled types are those §8.2.1.1 and §8.3.1.1 map. A streamed block of an unmodeled type emits no token
events (§8.2.6, §8.3.6). A response whose only content was unmodeled blocks has empty content, which §3
allows only for a `"content_filter"` response, so for any other finish reason it is
`provider_invalid_response` (§7), as an unparseable response is today.

### llm-provider §5: provider streaming support

The last sentence of *Provider streaming support* becomes:

> The §8.1 OpenAI-compatible, §8.2 Anthropic and §8.3 Gemini mappings implement streaming (§8.1.6, §8.2.6,
> §8.3.6).

The rule above it, that a mapping without streaming rejects a `stream`-set call before sending, stays for
any future mapping.

### llm-provider §8.2.1: the Anthropic `stream` field

§8.2.1 today manages Anthropic's body `stream` field only to keep an extras `stream: true` off the wire,
since the mapping parsed an atomic body. With streaming implemented, the field is the wire realization of
the declared `stream` argument, managed as §8.1.6 manages its own: the mapping sends `stream: true` for a
`stream`-set call and sends no `stream` key otherwise. Because every call fixes a stream mode, the field is
managed on every call. A matching extras `stream` is a redundant no-op, and a conflicting one, such as an
extras `stream: false` on a `stream`-set call or an extras `stream: true` on a call without it, is rejected
before sending with `provider_invalid_request` (§7). The mapping MUST NOT drop it silently or let it override
the mode the call fixed.

### llm-provider §8.2.6: Anthropic streaming (new)

When `complete()` is called with `stream` set (§5), the Anthropic mapping sends `"stream": true` and
consumes the server-sent event stream.

**Assembly.** The mapping rebuilds Anthropic's atomic `Message` from the events and maps it to the §6
`Response` by §8.2.2, unchanged:

- `message_start` carries the `Message` with empty `content`. Its `id`, `model` and `usage` seed the
  assembled message.
- Each content block arrives as `content_block_start`, any number of `content_block_delta` events and
  `content_block_stop`, keyed by `index`, the block's position in the final `content` array. The block in
  `content_block_start` is the block's initial value, and each delta extends it:
  - `text_delta` appends `text` to a `text` block;
  - `thinking_delta` appends `thinking` to a `thinking` block;
  - `signature_delta` sets the `thinking` block's `signature`;
  - `input_json_delta` appends `partial_json` to a `tool_use` block's input string, which the mapping parses
    as JSON at `content_block_stop`. An input that does not parse follows §3's rule for unparseable
    arguments, as it would atomically.
  - A block that arrives whole, with no deltas, such as `redacted_thinking`, takes its value from
    `content_block_start`.
  - A block of a type the mapping does not model is assembled from its events like any other and then left
    out of the message by §8.2.2's rule, staying in `raw`. A delta type the mapping does not recognize is
    kept on its block in `raw` and changes nothing else.
- Each `message_delta` merges its `delta` (`stop_reason`, `stop_sequence`) into the message. Its `usage`
  counts are cumulative, so each key it carries replaces the same key from earlier events.
- `message_stop` ends the stream.
- `ping` events are ignored. An event type the mapping does not recognize is ignored too, which Anthropic's
  versioning policy asks of clients, since it may add event types.

The assembled message's `stop_reason` maps by §8.2.2's table and its `usage` by §8.2.2's usage rule. `raw`
is the assembled `Message`, whose `usage` is the merged usage above, so the terminal counts stay inspectable
verbatim, as §6 requires.

**Token events.** Each `text_delta` is emitted as it arrives as `LlmTokenEvent(delta_kind: "content")`, and
each `thinking_delta` as `LlmTokenEvent(delta_kind: "reasoning")` (§5, §6 *Streaming assembly*). An empty
`thinking` string, which Anthropic sends when thinking display is omitted, emits no event. `signature_delta`,
`input_json_delta` and a block that arrives whole emit none. Tool-call input is reassembled into
`message.tool_calls`, as §6 already says for every mapping.

**Errors.** An HTTP error before the stream starts maps by §8.2.3. An `error` event inside the stream maps
its `error.type` by the same table, as the HTTP status that type corresponds to would: `overloaded_error` as
529, `api_error` as 500, `rate_limit_error` as 429, and any other type as `provider_unavailable`. A stream
that ends before `message_stop`, for a dropped connection or a client timeout, is a connection error,
`provider_unavailable`. Either way the call raises, and the token events already emitted stand, followed by
the terminal `LlmFailedEvent` (graph-engine §6, 0062).

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

- The `parts` of `candidates[0].content` across all chunks are concatenated in arrival order. Adjacent text
  parts with the same `thought` value are joined into one part, since a stream splits one atomic text part
  across chunks.
- A `thoughtSignature` stays on the part it arrived on, after joining, so §8.3.2's signature capture applies
  as it does atomically.
- A part of a type the mapping does not model is kept in arrival order and left out of the message by
  §8.3.2's rule, staying in `raw`.
- Each `functionCall` part is one complete call. On the Gemini API a call is never split across chunks:
  partial-argument streaming (`partialArgs` and `willContinue`, enabled by `streamFunctionCallArguments`) is a
  Vertex AI feature the Gemini API does not support.
- `finishReason` is the last value any chunk carried for `candidates[0]`.
- `usageMetadata` is the last chunk's, taken whole. Gemini sends counts already accumulated with each chunk,
  so the mapping MUST NOT sum them across chunks, and MUST NOT combine counters from different chunks: the
  last chunk's counts are the totals, even where one is lower than an earlier chunk's.
- The other top-level fields (`modelVersion`, `responseId`, `promptFeedback`) take the last value any chunk
  carried.

`raw` is the merged response, whose `usageMetadata` is the last chunk's verbatim, as §6 requires.

**Token events.** Each text part is emitted as it arrives: a part with `thought: true` as
`LlmTokenEvent(delta_kind: "reasoning")`, any other text part as `LlmTokenEvent(delta_kind: "content")`. A
`functionCall` part emits none.

**Blocked prompt.** A prompt Gemini blocks arrives as a chunk with `promptFeedback.blockReason` and no
candidates. It emits no token events, and the merged response maps by §8.3.2's blocked-prompt rule.

**Errors.** An HTTP error before the stream starts maps by §8.3.3. A stream that ends with no chunk carrying
either a `finishReason` or a `promptFeedback.blockReason`, for a dropped connection or a client timeout, is a
connection error, `provider_unavailable`. The call raises, and the token events already emitted stand,
followed by the terminal `LlmFailedEvent`.

**Structured output.** §8.3.5's paths apply to the merged response, and `parsed` is validated at the end.

### Vendor facts

The Anthropic facts above were checked on 2026-11-14 against Anthropic's streaming documentation: the event
names and order, the five delta types, cumulative `message_delta` usage, `ping`, the `error` event with
`overloaded_error` as its example, whole `redacted_thinking` blocks, and the instruction to ignore unknown
event types.

Google's API reference documents `streamGenerateContent` without describing its chunks, so three Gemini facts
were checked on 2026-11-14 against Google's own SDKs and one widely used client:

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
   and the rule above, the last chunk's counts taken whole, holds whether or not it recurs.

## Conformance test impact

### Harness note

llm-provider's `stream_body` (fixture 001's header) describes the OpenAI chunk shape. It gains two forms,
selected by the fixture's `mapping`:

- **`mapping: anthropic`**: a list of `{event: <name>, data: <object>}` entries, each yielded as an SSE
  `event:` line and a `data:` line, in order. There is no `[DONE]` sentinel; the stream ends after the last
  entry.
- **`mapping: gemini`**: a list of `GenerateContentResponse` objects, each yielded as one `data:` line.

`expected_wire_url` (conformance-adapter §5.16) asserts the Gemini streaming endpoint, and
`expected_wire_request` the Anthropic body's `stream: true`.

### New fixtures

| Fixture | Mapping | Asserts |
|---|---|---|
| 084 | anthropic | A text stream: `stream: true` on the wire, one content token event per `text_delta` in order, the assembled `Response` (content, `finish_reason` from `message_delta`'s `stop_reason`, usage merged from `message_start` and `message_delta`). |
| 085 | anthropic | A tool call whose input arrives in several `input_json_delta` events: no token events for it, `message.tool_calls` with the parsed arguments, `finish_reason: "tool_calls"`. |
| 086 | anthropic | Thinking: reasoning token events per `thinking_delta`, the `ThinkingBlock` with its signature from `signature_delta`, a whole `redacted_thinking` block assembled with no event, then text. |
| 087 | anthropic | `ping` events, an unknown event type, and a block of an unmodeled type mid-stream change nothing in the `Response` and emit no token events; the unmodeled block is on `raw`. |
| 088 | anthropic | An `error` event (`overloaded_error`) after two text deltas: the two content token events, then `provider_unavailable` raised. |
| 089 | anthropic | The managed `stream` field: an extras `stream: false` on a `stream`-set call and an extras `stream: true` on a call without it are each rejected before sending; a matching extras value is a no-op. |
| 090 | gemini | A text stream: the `:streamGenerateContent?alt=sse` URL, content token events per text part, the merged `Response`, usage from the last chunk's `usageMetadata`. |
| 091 | gemini | A `functionCall` part: no token event, `message.tool_calls`, `finish_reason: "tool_calls"`. |
| 092 | gemini | Thought parts: reasoning token events for `thought: true` parts, joined into one `ThinkingBlock`, then content. A `thoughtSignature` on a part survives to the assembled block. |
| 093 | gemini | A `finishReason` of `SAFETY` on the last chunk maps to `"content_filter"`, after the content token events already emitted. |
| 094 | gemini | Atomic, not streamed: a blocked prompt (`promptFeedback.blockReason`, no candidates) returns a `Response` with empty content, no tool calls and `finish_reason: "content_filter"`, with `promptFeedback` on `raw`. |
| 095 | gemini | The same blocked prompt streamed: one chunk, no token events, the same `Response`, and no `provider_unavailable`. |
| 096 | anthropic | Atomic: a response with a text block and a block of an unmodeled type maps the text and leaves the other block on `raw` only. |
| 097 | gemini | Streamed: an unmodeled part type between two text parts emits no event, is left out of the message and stays on `raw`. |

The existing streaming fixtures (llm-provider 059, 060, 071, 073, 077 and observability 111 to 118) are
unchanged. Fixture 060's stub mapping still covers the rejection rule in §5.

## Versioning

MINOR. Two mappings gain a behavior: a `stream`-set call that each rejected now streams. A caller that relied
on the rejection is the only one affected, and the rejection was documented as temporary. The §3 exception
relaxes a constraint on what a mapping returns, and the blocked-prompt rule defines a case that had no
mapping. llm-provider's
`Latest` moves.

## Alternatives considered

1. **A separate per-chunk mapping for each vendor, without rebuilding the atomic response.** Rejected. It
   would restate every rule of §8.2.2 and §8.3.2 for chunks, and each restatement is a place the streamed and
   atomic paths could drift apart, which §6's structural identity forbids. Rebuilding the vendor's own atomic
   shape keeps one response mapping per vendor.
2. **Gemini's Interactions API** (`/v1beta/interactions?alt=sse`), which Google's guides now lead with for
   streaming. Rejected for this proposal. §8.3 maps `generateContent`, and streaming the same API through
   `streamGenerateContent` keeps the request mapping shared. Whether §8.3 should move to the Interactions API
   is a separate question, tracked with the other Gemini guide drift.
3. **Emitting tool-call input deltas as token events.** Out of scope, as in 0062: `LlmTokenEvent` carries
   content and reasoning only.

## Open questions

None remain. Server-side tool blocks fall under the unmodeled-type rule until the server-side tools
proposal maps them.

## Out of scope

- Prompt caching, a separate proposal.
- Gemini's Interactions API (see *Alternatives considered*).
- The rest of 0062's *Out of scope*: a node body consuming the stream directly, tool-call deltas as token
  events, first-token latency telemetry, and signaling a call-level retry restart on the token stream.
