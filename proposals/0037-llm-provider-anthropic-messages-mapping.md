# 0037: llm-provider — Anthropic Messages Wire-Format Mapping (§8.2)

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-27
- **Accepted:** 2026-05-27
- **Targets:** spec/llm-provider/spec.md (new §8.2 *Anthropic Messages mapping* subsection following the §8.X template locked in by [proposal 0026](0026-llm-provider-wire-format-mapping-template.md); §3.1 *Content blocks* expanded with two new assistant-message block types — `ThinkingBlock` and `RedactedThinkingBlock` — surfacing provider-emitted reasoning content as first-class spec records; §8.1 *OpenAI-compatible mapping* extended with a strip-on-send rule for the new block types since OpenAI Chat Completions does not surface reasoning tokens); spec/llm-provider/conformance/ (eleven new fixtures `033-043` covering the Anthropic mapping rows, the cross-§-section `ThinkingBlock` semantics, and the §8.1 strip behavior).
- **Related:** 0006 (llm-provider core + §8.1 OpenAI mapping — established the wire-format-mapping pattern this proposal extends to a second provider), 0015 (multimodal images — defined the §3.1 content-block shape this proposal expands), 0016 (structured output — defined the §6 `response_schema` surface this proposal maps to Anthropic's native `output_config.format` field), 0019 (multi-provider wire-format extension — established the §8 catalog framing), 0025 (tool_choice — defined the §5 `tool_choice` parameter this proposal maps to Anthropic's distinct shape), 0026 (§8.X subsection template — defined the canonical five-subsection structure §8.2 follows), 0032 (RuntimeConfig surface refinements — declared field set this proposal maps to Anthropic's wire body)
- **Supersedes:**

## Summary

Add a normative wire-format mapping for the Anthropic Messages API
(`POST /v1/messages`) as §8.2 of llm-provider, following the §8.X
subsection template (Request / Response / Error / Concurrency /
Structured output) locked in by proposal 0026.

Anthropic's wire shape diverges from OpenAI Chat Completions enough
that §8.1's mapping cannot be reused: `system` is a top-level
request field rather than a message role, tool calls and tool
results are content blocks inside assistant and user messages
respectively (rather than a separate `tool_calls` field and `tool`
role), `tool_choice` has a different shape, `max_tokens` is
required, the tool definition uses `input_schema` rather than
`function.parameters`, and provider-emitted reasoning content
(`thinking` blocks) is round-trip-load-bearing for multi-turn
correctness on Anthropic's extended-thinking models.

The mapping spec'd here covers the conversational request/response
surface with parity to §8.1 plus three Anthropic-specific
sub-subsections:

- **§8.2.1.1** — Content-block wire mapping. Maps spec
  `TextBlock` / `ImageBlock` / `ToolCall` to Anthropic content
  blocks; introduces wire-level handling for the spec
  `ThinkingBlock` and `RedactedThinkingBlock` types this proposal
  adds to §3.1.
- **§8.2.1.2** — `tool` role bidirectional translation. Spec's §3
  `tool` role messages have no Anthropic-side counterpart;
  this sub-subsection specifies the bidirectional translation
  between spec `tool` messages and Anthropic user messages
  carrying `tool_result` content blocks.
- **§8.2.5** — Structured output. Anthropic provides native
  schema-constrained decoding via the top-level
  `output_config.format` field (GA on current models); this
  sub-subsection specifies the native path (mirroring §8.1.5)
  plus fallbacks (tool-call coercion, then prompt-augmentation)
  for models predating native support.

Two §3.1 ContentBlock additions, one §8.1 strip-on-send rule, no
changes to §3 role set, §4 Tool definition, §5 Provider interface,
§6 Response shape, §7 error categories, §9 Determinism, §10
*Out of scope*, or any other §-section beyond the touchpoints
listed above.

## Motivation

The Anthropic Messages API is the second major provider protocol
adopted across the OA implementation surface (after OpenAI Chat
Completions, which §8.1 already covers). The spec's §8 catalog
framing (per proposal 0019) intentionally placed the OpenAI mapping
as the first concrete entry and reserved §8.2, §8.3, etc. for
provider-native shapes that diverge enough to require their own
mappings.

Anthropic diverges from OpenAI Chat Completions across the
request, response, and structured-output surfaces in ways that make
§8.1's mapping rules incorrect to apply:

- **System extraction.** OpenAI puts `system` as a `messages`
  array entry with `role: "system"`; Anthropic puts it as a
  top-level request field. Reusing §8.1's mapping would put
  spec `system` messages into Anthropic's `messages` array as
  regular entries — Anthropic rejects this with HTTP 400.
- **Tool call placement.** OpenAI puts tool calls in
  `assistant.tool_calls` (sibling to `content`); Anthropic puts
  them as `tool_use` content blocks inside `assistant.content`.
  Reusing §8.1's mapping would emit tool calls in a field
  Anthropic doesn't recognize.
- **Tool result placement.** OpenAI uses a `tool` role for tool
  results; Anthropic has no `tool` role — tool results go as
  `tool_result` content blocks inside user messages, paired with
  the `tool_use_id` that generated them.
- **Tool definition shape.** OpenAI wraps in `{type: "function",
  function: {name, description, parameters}}`; Anthropic uses
  `{name, description, input_schema}` directly. Field names
  differ; nesting differs.
- **`tool_choice` shape.** OpenAI's specific-tool form is
  `{type: "function", function: {name}}`; Anthropic's is
  `{type: "tool", name}` (flatter; different `type` discriminator
  values: `"auto" | "any" | "tool" | "none"` rather than
  `"auto" | "required" | "none" | {function: {name}}`).
- **`max_tokens` requirement.** OpenAI permits `max_tokens` to
  be omitted (with provider default); Anthropic requires it on
  every request.
- **Structured output.** Both have native schema-constrained
  decoding, but via different fields: OpenAI's `response_format`
  (§8.1.5) vs Anthropic's top-level `output_config.format`. The
  §8.2 mapping targets Anthropic's native field; older Claude
  models without it fall back to tool-call coercion or
  prompt-augmentation.
- **Provider-emitted reasoning content.** Anthropic's
  extended-thinking models (Claude 3.7+ on the line; Claude 4
  family) emit `thinking` and `redacted_thinking` content blocks
  alongside text in assistant responses. The blocks carry a
  cryptographic `signature` that Anthropic verifies on
  round-trip; preserving thinking blocks across multi-turn
  conversation flows (especially tool-use-with-thinking) is
  load-bearing for the model to maintain reasoning continuity.
  Without first-class spec representation, callers wanting
  multi-turn flows would have to dig into `Response.raw`, extract
  thinking blocks, and manually reconstruct the next request —
  bypassing the §3/§6 abstraction entirely for the
  reasoning-model use case.

Codifying these mappings in spec is required for the same
cross-language behavioral consistency that §8.1 provides for the
OpenAI-compatible case: sibling language implementations
targeting Anthropic must agree on the wire shape, the
bidirectional `tool` role translation, the structured-output
strategy, and the thinking-block round-trip semantics. Without
the §8.2 spec, language sibs would drift in subtle wire details
and break the cross-language promise.

## Detailed design

### §3.1 — Content-block expansion

§3.1's intro (currently *"v1 defines two block types: text and
image"*) updates to enumerate four block types: text, image,
thinking, and redacted_thinking.

Two new sub-subsections added to §3.1 between the existing §3.1.3
*Image source* and the Mixing blocks section, which renumbers from
§3.1.4 to §3.1.6:

#### §3.1.4 Thinking block

A thinking block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"thinking"`. |
| `text` | yes | The reasoning content the provider emitted. A non-empty string. |
| `signature` | yes | An opaque provider-issued token used by the provider to verify the block on round-trip. Implementations MUST pass the value through unchanged; spec callers MUST NOT construct, modify, or fabricate the field. |

Thinking blocks represent provider-emitted reasoning content.
They MAY appear in assistant message content sequences (alongside
`TextBlock` and `ToolCall` entries — see §3 message shape — and
content-block sequences mixing them are valid). They MUST NOT
appear in user, system, or tool message content. Implementations
MUST surface thinking blocks emitted by a provider on the
`Response.message.content` block list (per §6) and MUST preserve
them verbatim when the same assistant message is sent back to
that provider in a subsequent `complete()` call.

Provider mappings that do not surface reasoning content (e.g.,
the §8.1 OpenAI mapping) MUST strip thinking blocks from
outbound assistant messages per §8.1's strip-on-send rule (see
*§8.1 extension* below), but MUST NOT emit thinking blocks on
inbound responses. Wire-level behavior for each provider is
specified in its §8.X mapping.

#### §3.1.5 Redacted thinking block

A redacted thinking block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"redacted_thinking"`. |
| `data` | yes | An opaque provider-issued blob preserving the structural slot for reasoning content that the provider has redacted from caller view. Implementations MUST pass the value through unchanged. |

The redacted variant covers cases where a provider's policy
withholds the reasoning text from the caller while preserving the
structural slot — necessary so that subsequent turns of the
conversation can be round-tripped without breaking the provider's
reasoning continuity. Same scope rules as `ThinkingBlock`:
assistant-message-content-only, round-trip-load-bearing.

#### §3.1.6 Mixing blocks — clarifying update (renumbered from §3.1.4)

The existing prose covers text and image blocks. Update adds one
sentence: "Assistant messages MAY also contain thinking and
redacted-thinking blocks (per §3.1.4 and §3.1.5) when the provider
mapping surfaces them; thinking blocks SHOULD precede text blocks
in an assistant message's content sequence, matching the order
providers emit them. Implementations MUST preserve the emitted
order on round-trip."

### §6 — Response.message.content clarifying note

§6's `Response.message.content` already accepts a content-block
list (per §3's content-block model). No structural change is
needed; this proposal adds a one-sentence clarifying note that
the content list MAY include `ThinkingBlock` and
`RedactedThinkingBlock` entries for provider mappings that surface
reasoning content.

### §8.1 — Strip-on-send rule for non-reasoning mappings

§8.1.1 *Request mapping* extends with one new paragraph specifying
the strip-on-send rule for `ThinkingBlock` and
`RedactedThinkingBlock` entries: when an assistant message in the
spec request contains thinking blocks (e.g., because the caller
is passing back conversation history that originated from a
different §8.X-mapped provider), the §8.1 mapping MUST strip
those blocks before emitting the OpenAI wire request. OpenAI Chat
Completions does not surface reasoning tokens, has no wire-level
representation for thinking blocks, and rejects requests
containing block types it does not recognize. Stripping preserves
the spec's content-block superset across cross-provider
conversation round-trips: callers MAY route a conversation that
originated from Anthropic (and therefore carries thinking blocks
in its assistant history) through an OpenAI-compatible provider
without manual block filtering. Implementations MUST document
this strip-on-send behavior. Strip is deterministic; no error is
raised. The §8.1 mapping MUST NOT emit thinking blocks on inbound
responses (OpenAI Chat Completions doesn't produce them).

### §8.2 — Anthropic Messages mapping (new)

The Anthropic Messages API (`POST /v1/messages`) is the
provider-native protocol for Anthropic's Claude model family.

#### §8.2.1 Request mapping

The §3 message list maps onto Anthropic's request body as
follows:

**System extraction.** Any §3 messages with `role: "system"` are
removed from the spec message list and their content is
concatenated (text-only) into Anthropic's top-level `system`
request-body field. Concatenation joins the per-message contents
with `\n\n` (two newlines) when more than one system message is
present, preserving the order they appeared in the spec list.
The `messages` array sent to Anthropic contains only
`role: "user"` and `role: "assistant"` entries.

Image content blocks MUST NOT appear in system-role messages
(per §3.1 — image blocks are user-message-only). Implementations
MUST reject at pre-send validation (`provider_invalid_request`)
any system message containing non-text content.

**Message body shape.** Each remaining spec message maps to one
Anthropic message:

| Spec role | Anthropic role | Notes |
|---|---|---|
| `user` | `user` | When `content` is a string, maps directly. When `content` is a content-block sequence (§3.1), maps to Anthropic's content-array form per §8.2.1.1. |
| `assistant` (no tool calls, no thinking) | `assistant` | `content` becomes Anthropic's `content` (string or block array). |
| `assistant` (with tool calls and/or thinking) | `assistant` | Tool calls become `tool_use` content blocks in Anthropic's `content` array; thinking blocks pass through unchanged. See §8.2.1.1. |
| `tool` | (no direct Anthropic role) | Maps via §8.2.1.2 bidirectional translation to an Anthropic `user` message containing one `tool_result` content block. |

**Tool definitions.** A §4 `Tool` `{name, description, parameters}`
maps to an Anthropic `tools` entry as:

```
{
  "name": <name>,
  "description": <description>,
  "input_schema": <parameters>
}
```

Note Anthropic uses `input_schema`, not `parameters`; the spec
`parameters` field's JSON Schema content passes through verbatim
under the renamed key.

**`tool_choice` mapping.** The §5 `tool_choice` parameter maps to
Anthropic's `tool_choice` request-body field per the table:

| Spec `tool_choice` | Anthropic wire body |
|---|---|
| `None` / absent | (field omitted from request body) |
| `"auto"` | `{"type": "auto"}` |
| `"required"` | `{"type": "any"}` (Anthropic's name for "require some tool") |
| `"none"` | `{"type": "none"}` |
| `{type: "tool", name: X}` | `{"type": "tool", "name": X}` |

The `"required"` → `"any"` rename is the load-bearing translation:
the spec's name is the cross-vendor stable form (matches OpenAI's
wire name), and Anthropic uses `"any"` for the same semantic.
Implementations of the Anthropic mapping MUST perform this
rename.

**RuntimeConfig field mapping.** The §6 `RuntimeConfig` declared
fields map to the Anthropic request body as follows:

- `temperature`, `top_p`, `seed`, `stop_sequences` — map directly
  (same name on the Anthropic request body; `stop_sequences`
  matches Anthropic's wire-key convention exactly, no rename
  needed).
- `max_tokens` — maps directly. Anthropic requires this field on
  every request; if `RuntimeConfig.max_tokens` is `None` or
  absent at the call site, implementations MUST reject at
  pre-send validation (`provider_invalid_request`) with a
  message identifying `max_tokens` as required by the Anthropic
  mapping. The spec MUST NOT default to a magic value; the
  caller decides.
- `frequency_penalty`, `presence_penalty` — Anthropic does NOT
  support these fields. If supplied (non-`None`), implementations
  MUST raise `provider_invalid_request` at pre-send validation
  with a message identifying the unsupported field. Quiet drop
  is forbidden; the caller's intent is preserved by surfacing
  the mismatch.

The bound model identifier becomes Anthropic's `model` field.

**Undeclared `RuntimeConfig` fields** appear at the Anthropic
request-body root, as siblings to `temperature`, `model`, etc.,
per §6's extras-pass-through contract. The §8.2 mapping does NOT
validate, rename, or transform undeclared keys.

##### §8.2.1.1 Content-block wire mapping

This sub-subsection covers two wire-encoding paths:

- Spec **content blocks** (per §3.1 — `TextBlock`, `ImageBlock`,
  `ThinkingBlock`, `RedactedThinkingBlock`) appearing in spec
  message `content` fields map directly to Anthropic wire content
  entries per the table below.
- Spec **ToolCall** records appearing in the assistant message's
  top-level `tool_calls` field (per §3) are NOT §3 content blocks
  — the wire mapping extracts them and serializes them as
  Anthropic `tool_use` wire entries in the assistant's content
  array. Reverse on receive: Anthropic `tool_use` wire entries
  in the assistant's content array are parsed back into spec
  `ToolCall` records on the response's `Response.message.tool_calls`
  field (per §6).

| Spec source | Anthropic wire entry |
|---|---|
| `TextBlock { text }` (content block) | `{ "type": "text", "text": <text> }` |
| `ImageBlock` with `source: url { url }` (content block; user-only per §3.1) | `{ "type": "image", "source": { "type": "url", "url": <url> } }`. The `detail` hint, when set on the spec block, is dropped — Anthropic does not honor detail. |
| `ImageBlock { media_type, source: inline { base64_data } }` (content block; user-only per §3.1) | `{ "type": "image", "source": { "type": "base64", "media_type": <media_type>, "data": <base64_data> } }`. The `detail` hint, when set, is dropped. |
| `ToolCall { id, name, arguments }` from assistant `tool_calls` field (NOT a content block; extracted at wire) | `{ "type": "tool_use", "id": <id>, "name": <name>, "input": <arguments> }`. The spec stores `arguments` as a deserialized mapping; Anthropic's wire format accepts an object directly under `input`. No JSON-string serialization step needed (unlike §8.1.1). |
| `ThinkingBlock { text, signature }` (content block; assistant-only) | `{ "type": "thinking", "thinking": <text>, "signature": <signature> }`. The signature passes through verbatim in both directions. |
| `RedactedThinkingBlock { data }` (content block; assistant-only) | `{ "type": "redacted_thinking", "data": <data> }`. The data blob passes through verbatim in both directions. |

Empty content blocks (text with empty `text`, image with both
sources absent) are spec-invalid and MUST be rejected at
pre-send validation per §3 / `provider_invalid_request`.

Anthropic and OpenAI use different content-block wire shapes
across all block types; the spec's content-block model abstracts
over the divergence so application code does not need
per-provider conditionals.

##### §8.2.1.2 `tool` role bidirectional translation

Spec messages with `role: "tool"` (§3) do not map to any
Anthropic message role directly. Instead, the §8.2 mapping
translates bidirectionally:

**Spec → Anthropic (on send):** Each consecutive run of spec
`tool` messages between two non-`tool` messages collapses into a
single Anthropic `user` message whose content is an array of
`tool_result` blocks — one per original spec `tool` message,
preserving order:

```
{
  "role": "user",
  "content": [
    { "type": "tool_result", "tool_use_id": <tool_call_id_from_spec_tool_msg>,
      "content": <content_from_spec_tool_msg> }
    /* one per consecutive spec tool message */
  ]
}
```

This collapse is required because Anthropic forbids consecutive
messages of the same role in `messages`, and a user message
already follows the model's prior tool calls; sending each tool
result as its own user message would violate Anthropic's role
alternation rule.

**Anthropic → Spec (on receive):** When parsing Anthropic
conversation history (e.g., when a caller passes back
`Response.raw.content` or constructs a follow-up `complete()`
call from a prior response), each `tool_result` content block
inside a user message maps back to one spec `tool` message with
`tool_call_id` from `tool_use_id` and `content` from the block's
`content`. The user message's other content blocks (if any —
e.g., a user text block preceding the tool results) form a
separate spec `user` message. The reverse translation preserves
the original tool-call/tool-result pairing without information
loss.

The translation is lossless and bidirectional: a spec → Anthropic
→ spec round-trip preserves message-role and tool-call
relationships.

#### §8.2.2 Response mapping

A successful Anthropic response maps onto a §6 `Response` as
follows:

- `message` — built from the response's `role: "assistant"` plus
  the `content` array. Each content-array entry maps back to its
  spec content block per §8.2.1.1's table (text → TextBlock,
  tool_use → ToolCall, thinking → ThinkingBlock,
  redacted_thinking → RedactedThinkingBlock). The order of blocks
  in the response is preserved on the spec `Message.content`
  list.
- `tool_calls` — extracted from the assistant's content array
  (any `tool_use` block becomes a spec `ToolCall` on the message;
  the §6 `Response.message.tool_calls` mirrors this for
  compatibility with §8.1's flatter shape). `tool_use` blocks
  remain in the `content` array as well — they appear in both
  places so that callers using either access pattern see the
  same tool calls.
- `finish_reason` — derived from Anthropic's `stop_reason`:

  | Anthropic `stop_reason` | Spec `finish_reason` |
  |---|---|
  | `"end_turn"` | `"stop"` |
  | `"max_tokens"` | `"length"` |
  | `"stop_sequence"` | `"stop"` (the matched sequence is preserved in `Response.raw.stop_sequence`) |
  | `"tool_use"` | `"tool_calls"` |
  | `"pause_turn"` | `"stop"` (a long-running turn the provider paused; the caller MAY continue by passing the response back. The pause is preserved in `Response.raw.stop_reason` for callers implementing the continue protocol) |
  | `"refusal"` | `"content_filter"` (the refusal category, when present, is preserved in `Response.raw.stop_details`) |
  | (unknown) | `"error"` |

- `usage` — built from Anthropic's `usage` field:
  `usage.prompt_tokens` ← `input_tokens`,
  `usage.completion_tokens` ← `output_tokens`,
  `usage.total_tokens` ← sum of the prompt and completion token
  counts the mapping reports (computed when both are present,
  otherwise `None` per §6's usage rules).
  **Cache-token note:** Anthropic's `input_tokens` counts only the
  non-cached input; cached input is reported separately in
  `cache_creation_input_tokens` and `cache_read_input_tokens`.
  Anthropic's own total-input accounting is therefore
  `input_tokens + cache_creation_input_tokens +
  cache_read_input_tokens`. The spec `usage.prompt_tokens` maps
  from `input_tokens` alone (the non-cached portion); the
  cache-related subfields appear in `Response.raw.usage`
  unchanged and are NOT promoted to the spec `usage` record (cache
  primitives are out of scope per *Out of scope* below).
  Implementations whose cost accounting needs the full input
  total read the cache subfields from `Response.raw`.
- `raw` — the parsed JSON body of the Anthropic response,
  verbatim. Implementations MUST NOT redact, rewrite, or omit
  fields. Anthropic-specific extensions (e.g., the response
  `id`, the `model` actually used, cache token counts) surface
  here unchanged.

#### §8.2.3 Error mapping

| Anthropic condition | Spec category |
|---|---|
| HTTP 401 `authentication_error` | `provider_authentication` |
| HTTP 402 `billing_error` | `provider_authentication` (account-level access failure — the spec groups it with auth; the specific `billing_error` type appears in `Response.raw`) |
| HTTP 403 `permission_error` | `provider_authentication` (the spec category groups auth + permission failures; the specific Anthropic type appears in `Response.raw` if needed) |
| HTTP 404 `not_found_error` (model-not-found body) | `provider_invalid_model` |
| HTTP 413 `request_too_large` | `provider_invalid_request` (the request exceeds Anthropic's size limit) |
| HTTP 429 `rate_limit_error` | `provider_rate_limit` |
| HTTP 500 `api_error` | `provider_unavailable` |
| HTTP 504 `timeout_error` | `provider_unavailable` |
| HTTP 529 `overloaded_error` | `provider_unavailable` |
| HTTP 5xx (other), connection error, client timeout | `provider_unavailable` |
| HTTP 400 with body indicating the bound model rejected a content block (image/media-type/unsupported source variant rejection) | `provider_unsupported_content_block` |
| HTTP 400 `invalid_request_error` (other malformed-request causes) | `provider_invalid_request` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

The error envelope is `{"type": "error", "error": {"type":
<error_type>, "message": <string>}, "request_id": <string>}`.
Anthropic's per-error `error.type` field and the `request_id`
surface in `Response.raw` for callers needing finer-grained
handling.

#### §8.2.4 Concurrency

Matches §8.1.4. Anthropic's hosted API supports concurrent
requests; implementations MUST NOT add a serialization layer.
Concurrent `complete()` calls go to the wire concurrently. Client-side
rate-limit needs use the pipeline-utilities rate limiter or
middleware, not this layer.

#### §8.2.5 Structured output

The Anthropic Messages API provides native structured output
(generally available on current Claude models) via the top-level
`output_config.format` request field. The spec defines a native
path (mirroring §8.1.5) plus a fallback for models predating
native support.

**Native: `output_config.format`.** When `complete()` is called
with a `response_schema`, the §8.2 mapping sets:

```
{
  "output_config": {
    "format": {
      "type": "json_schema",
      "schema": <response_schema verbatim>
    }
  }
}
```

The `type: "json_schema"` discriminator is required; the supplied
`response_schema` JSON Schema passes through under `schema`. The
GA path requires no beta header. Anthropic's constrained decoding
guarantees the generated output conforms to the schema. The
structured JSON is returned as the assistant message's text
content; the §8.2 mapping parses it into `Response.parsed` and
validates against `response_schema` per §6. On validation failure
raise `structured_output_invalid` (§7).

**Two non-conformance cases** are inherent to the provider and
NOT validation bugs: a `stop_reason: "refusal"` (safety refusal —
the output may not match the schema because the refusal takes
precedence) and a `stop_reason: "max_tokens"` (truncation — the
output is incomplete). In both cases the §8.2 mapping surfaces the
non-conforming content and the `stop_reason`; whether to raise
`structured_output_invalid` or surface the degraded response
follows §6 / §7's existing rules for the corresponding
`finish_reason` (`content_filter` / `length`). Implementations
MUST NOT silently coerce these into a schema-conforming shape.

When `complete()` is called without a `response_schema`, the
request MUST NOT include `output_config`; the free-form wire
shape is preserved.

(Anthropic also offers a complementary strict-tool-use feature —
`strict: true` on individual tool definitions — that guarantees
*tool-call argument* conformance rather than *response* shape.
That is a tool-parameter feature, not the §6 `response_schema`
surface; it is reachable via the tool-definition extras path and
is not part of this structured-output mapping.)

##### §8.2.5.1 Fallback for models without native structured output

Claude models predating native `output_config.format` support
fall back to one of the pre-native patterns. Two are available;
implementations SHOULD prefer tool-call coercion (stronger
conformance) and MUST document which path a given call uses.

**Tool-call coercion** (preferred fallback). When the caller's
`tools` list is empty or absent, construct a synthetic tool whose
`input_schema` is the `response_schema`, add it to the `tools`
array, and set `tool_choice` to `{"type": "tool", "name":
<synthetic name>}`. The response's `tool_use.input` for the
synthetic tool becomes `Response.parsed`. This was Anthropic's
documented best practice before native structured output and
remains the strongest fallback. Unavailable when the caller
already supplies tools (the synthetic tool would override the
caller's tool intent).

**Prompt-augmentation** (last-resort fallback). Per §8.1.5.1:
append a schema directive to the system field (or message list),
issue the request unmodified otherwise, parse and validate the
text response against `response_schema`, raise
`structured_output_invalid` on failure. The caller's original
`messages` MUST be left unchanged.

Implementations MUST document which path is selected for a given
call and SHOULD expose a way for callers to inspect or override
the choice.

## Spec-text changes (summary)

Eight edits to `spec/llm-provider/spec.md`:

1. **§3 assistant per-role constraint** — relax `content` from
   "non-empty string" to "non-empty string OR a non-empty ordered
   sequence of content blocks per §3.1." The content-block
   sequence MAY contain `TextBlock` and
   `ThinkingBlock`/`RedactedThinkingBlock` entries; `ImageBlock`
   remains user-only (per §3.1's existing constraints). `ToolCall`
   stays in the existing top-level `tool_calls` field on assistant
   messages — it is NOT a §3 content-block type; §8.X mappings
   that wire-encode tool calls as content blocks (e.g., §8.2's
   `tool_use` wire blocks) extract from `tool_calls` at the wire
   boundary.
2. **§3.1 intro** — update "v1 defines two block types" to
   enumerate four block types.
3. **§3.1.4 *Thinking block*** — new sub-subsection (existing
   *Mixing blocks* §3.1.4 renumbers to §3.1.6).
4. **§3.1.5 *Redacted thinking block*** — new sub-subsection.
5. **§3.1.6 *Mixing blocks*** (renumbered from §3.1.4) —
   clarifying update for thinking block ordering.
6. **§6 *Response message*** — one-sentence clarifying note that
   `Response.message.content` MAY include `ThinkingBlock` and
   `RedactedThinkingBlock` entries.
7. **§8.1.1** — strip-on-send rule for `ThinkingBlock` /
   `RedactedThinkingBlock` in assistant messages (since OpenAI
   doesn't accept those wire shapes).
8. **§8.2 (new)** — full Anthropic Messages mapping per §8.X
   template.

No changes to §3 role set or to `ToolCall` placement (still a
top-level `tool_calls` field on assistant messages), §4 Tool
definition, §5 Provider interface, §6 Response (beyond the
clarifying note), §7 error categories, §9 Determinism, §10
*Out of scope*, or any other §-section.

## Conformance fixtures

Eleven new fixture pairs under `spec/llm-provider/conformance/`:

| Fixture | Asserts |
|---|---|
| `033-anthropic-basic-message-round-trip` | Simple user→assistant text round-trip; system extraction; `messages` array contains only user/assistant entries; top-level `system` carries the concatenated system content; response parses into spec `Response` with text-only `message.content`. |
| `034-anthropic-tool-call-flow` | Multi-turn flow: user → assistant with `tool_use` blocks → spec `tool` messages → Anthropic user message with `tool_result` blocks (per §8.2.1.2 bidirectional translation) → assistant final response. Verifies tool-call wire shape, `tool` role collapse on send, `tool_result` parsing on receive. |
| `035-anthropic-image-content-blocks` | Both URL and base64 inline image variants; verifies `detail` hint is stripped (Anthropic doesn't honor it). |
| `036-anthropic-tool-choice-modes` | All five `tool_choice` shapes (`None`/absent, `"auto"`, `"required"` → `"any"` rename, `"none"`, specific tool by name). |
| `037-anthropic-runtime-config-mapping` | RuntimeConfig declared fields map to the Anthropic body. `temperature`, `top_p`, `seed`, `stop_sequences` pass through verbatim; `max_tokens` passes through; `frequency_penalty` and `presence_penalty` raise `provider_invalid_request` if supplied. |
| `038-anthropic-max-tokens-required` | Pre-send validation rejects calls without `max_tokens` (raises `provider_invalid_request`); calls with `max_tokens` set proceed. |
| `039-anthropic-error-mapping` | HTTP status + Anthropic `error.type` → spec §7 category table per §8.2.3. |
| `040-anthropic-structured-output-native` | Native path: caller supplies `response_schema`; the wire request carries `output_config.format = {type: "json_schema", schema}` with the schema verbatim; the response's text content is parsed into `Response.parsed`. |
| `041-anthropic-structured-output-fallback` | Tool-call-coercion fallback (for models without native support): the wire request introduces the synthetic tool with `tool_choice` set to it; the response's `tool_use.input` becomes `Response.parsed`. |
| `042-anthropic-thinking-block-round-trip` | Multi-turn flow with extended-thinking response: first call returns assistant content containing thinking + text blocks; second call passes the assistant message back verbatim; the wire request preserves thinking blocks unchanged with signatures intact; the second response also parses correctly. |
| `043-openai-strips-thinking-blocks` | Cross-mapping interop: a spec assistant message containing thinking blocks is routed through the §8.1 OpenAI mapping; the wire request to OpenAI strips the thinking blocks and contains only text; no error is raised; the response parses normally. |

Eleven fixtures total. The eleventh covers the §8.1 strip-on-send
rule from the §3.1 expansion.

## Versioning

**MINOR bump v0.28.0.** Additive normative changes:

- New §8.2 wire-format mapping (additive — does not change §8.1
  or any other §-section's behavior).
- Two new content-block types in §3.1 (additive — existing
  content-block consumers continue to work since the new types
  appear only in assistant messages from §8.2-mapped providers,
  and §8.1 strips them on send).
- One new strip-on-send rule in §8.1 (additive — affects
  outbound wire requests only when an assistant message
  contains thinking blocks, which prior to this proposal could
  not occur).

No breaking changes. Existing callers using only §3 text/image
blocks and §8.1 routing continue to work unchanged.
Implementations of §8.1 that don't handle the new strip rule
would still work for prior callers (no thinking blocks ever
appeared) but would fail conformance fixture 043 once it lands.

## Backwards compatibility

- **For callers using §8.1 with text/image only:** no change.
  No thinking blocks appear; no strip step runs.
- **For callers using §8.1 with cross-provider conversation
  history:** new strip-on-send rule activates when an assistant
  message containing thinking blocks (from a prior Anthropic
  call) is routed through OpenAI. Wire stays valid; thinking
  context is lost on the OpenAI side (as it would be regardless,
  since OpenAI doesn't surface reasoning).
- **For callers using §8.2 (new):** full mapping behavior per
  this proposal; no prior contract to preserve.
- **For §3.1 ContentBlock consumers:** the spec's content-block
  list extends with two new types. Implementations that switch
  exhaustively on `type` will need to add cases or fall through
  to default-handling; the spec recommends pass-through-or-strip
  patterns for non-reasoning-aware code paths.

## Out of scope

- **Streaming.** Anthropic's SSE streaming surface has different
  event types from OpenAI's; spec-level streaming awaits a
  cross-mapping streaming proposal.
- **Message Batches API** (`POST /v1/messages/batches`). Anthropic's
  asynchronous batch surface is operationally different from the
  synchronous `complete()` shape this mapping covers: callers
  submit N requests, the provider processes asynchronously, and
  callers fetch results when ready. Spec-level batch support is a
  future capability — likely a new set of `Provider` operations
  (`submit_batch`, `get_batch_status`, `get_batch_results`) with
  per-vendor wire mappings at §8.X.6 (or equivalent), composing
  with the graph-engine suspension primitive (currently Draft per
  proposal 0021) for the wait-for-result flow. OpenAI's Batch API
  and Gemini's equivalent surfaces fall under the same future
  capability.
- **Token Counting API** (`POST /v1/messages/count_tokens`).
  Anthropic's pre-flight token-counting endpoint computes the
  input token count for a message payload without sending the
  payload to a model. Useful for cost estimation, pre-send
  rejection when payloads exceed context limits, and client-side
  rate-limit budgeting. Spec-level support is a future capability —
  likely a new `Provider.count_tokens(messages, tools=None) -> int`
  operation with per-vendor wire mappings (Anthropic native
  endpoint, Gemini native `models.countTokens` method, OpenAI
  client-side tokenizer fallback since OpenAI has no native
  endpoint).
- **Models API** (`GET /v1/models`). Anthropic's model-listing
  endpoint enumerates available models with metadata
  (context limits, capabilities, pricing tier). Spec-level
  support is a future capability — likely a new
  `Provider.list_models() -> list[ModelInfo]` operation with
  per-vendor wire mappings, or a static `ModelInfo` registry the
  spec defines and implementations populate from vendor APIs.
  Lower priority than the batch and token-counting capabilities
  since most callers know their bound model.
- **Prompt caching.** Anthropic's `cache_control: {type:
  "ephemeral"}` content-block primitive is omitted from spec
  normative coverage; it remains user-extensible via §6's
  extras-pass-through (callers may attach `cache_control` to
  wire-level content blocks via implementation-specific
  extension paths). Cross-vendor caching is a future spec topic
  once patterns settle.
- **Document blocks.** Anthropic's `document` content blocks
  (PDF inputs) would require a §3.1 ContentBlock expansion
  beyond text/image/thinking/redacted_thinking; deferred to a
  future proposal. The Files API upload lifecycle (upload →
  `file_id` → reference in a message) rides with document-block
  support.
- **Server-side tools.** Anthropic-executed tools (`web_search`,
  `code_execution`, `web_fetch`, `tool_search`) declared in the
  request (e.g., `{"type": "web_search_20260209", "name": ...}`)
  and producing distinct response content blocks
  (`server_tool_use`, `web_search_tool_result`,
  `web_fetch_tool_result`, `code_execution_tool_result`). This is
  a different request/response shape from §8.2's client-tool
  `tool_use` / `tool_result` (where the caller executes) and is
  not covered here. A future proposal would add server-tool
  declaration and result-block mapping — cross-vendor, since
  OpenAI built-in tools and Gemini grounding are analogous.
- **Request-side reasoning controls.** §8.2 maps thinking blocks
  on the *response*; it does not define a first-class surface for
  *requesting* / budgeting extended thinking (Anthropic's
  `thinking` request param). Callers reach it today via §6's
  extras-pass-through (an undeclared `thinking` body field). A
  first-class cross-vendor reasoning-control surface (pairing
  with Gemini's `thinkingConfig`) is a future topic; this
  proposal covers reasoning *content*, not reasoning *control*.
- **Request-header passthrough (incl. beta features).** §6's
  extras-pass-through covers request-*body* fields; it does not
  cover request *headers*. Anthropic pre-GA features gated behind
  the `anthropic-beta` header are therefore not reachable through
  the declared surface. A general request-header passthrough
  mechanism (cross-vendor — any versioned/beta-header API) is a
  future topic.
- **Agentic tool-execution loop.** The Anthropic SDK's
  tool-runner (auto-execute a tool call, feed the result back,
  iterate) is intentionally NOT a provider concern: per
  llm-provider §1 the provider is stateless and does not loop on
  tool calls. An agent is a *graph* whose conditional edge loops
  back to the LLM node — the loop lives at the graph layer, not
  in §8.2. This is a design boundary, not an omission.
- **Cross-vendor reasoning abstraction.** This proposal
  introduces `ThinkingBlock` and `RedactedThinkingBlock` at the
  spec level but only maps them in §8.2 (Anthropic). If a
  future provider's reasoning content fits the same block shape,
  its §8.X mapping can adopt the existing blocks; if not, that
  proposal introduces sibling block types or expands the spec
  abstraction. This proposal does NOT pre-commit to a
  cross-vendor reasoning shape beyond Anthropic.

## Open questions

None at draft time. The six design decisions surfaced during
scoping (structured-output approach, `max_tokens` requirement,
multiple `system` messages, extended thinking treatment, prompt
caching scope, `tool` role round-trip) are resolved above. The
§3.1 expansion is scoped to two new block types (thinking +
redacted thinking) with explicit message-role and round-trip
constraints. The §8.1 strip-on-send rule provides cross-mapping
interop without requiring caller changes.
