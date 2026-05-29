# 0038: llm-provider — Google Gemini Wire-Format Mapping (§8.3)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-27
- **Targets:** spec/llm-provider/spec.md (new §8.3 *Google Gemini mapping* subsection following the §8.X template; §3 *Message shape* extended so `TextBlock` and `ToolCall` carry an optional opaque `signature` field — a provider round-trip token mirroring `ThinkingBlock.signature`, for providers whose reasoning-continuity signatures attach to non-thinking parts; §3 reasoning-block round-trip rule generalized to single-provider scope; `ThinkingBlock.signature` relaxed from required to optional); spec/llm-provider/conformance/ (new fixtures `044-053` covering the Gemini mapping rows, the thought-summary / thought-signature round-trip, and the cross-provider signature-strip rule).
- **Related:** 0037 (Anthropic Messages mapping — introduced `ThinkingBlock`/`RedactedThinkingBlock`, the `tool` role bidirectional-translation pattern, and the §8.1 strip-on-send rule this proposal builds on and generalizes; **0038 depends on 0037 being accepted first**), 0006 (llm-provider core + §8.1 OpenAI mapping), 0015 (multimodal images — §3.1 content-block shape), 0016 (structured output — §6 `response_schema`), 0025 (tool_choice — §5 parameter), 0026 (§8.X subsection template), 0032 (RuntimeConfig declared fields)
- **Supersedes:**

## Summary

Add a normative wire-format mapping for the Google Gemini
`generateContent` API (`POST /v1beta/models/{model}:generateContent`)
as §8.3 of llm-provider, following the §8.X subsection template.

Gemini's wire shape diverges from both OpenAI (§8.1) and Anthropic
(§8.2): the request is a `contents` array of `Content` objects each
holding a `parts` array; the assistant role is named `model`;
`systemInstruction` is a top-level field; tool results are
`functionResponse` parts inside user-role contents (no `tool`
role); tools nest under `functionDeclarations`; tool-choice is
`toolConfig.functionCallingConfig` with a four-mode enum; sampling
parameters nest under `generationConfig`; and structured output is
natively supported via `generationConfig.responseMimeType` +
`generationConfig.responseJsonSchema`.

Gemini's extended-thinking surface (Gemini 2.5+) differs
structurally from Anthropic's: the thought summary is a `parts`
entry flagged `thought: true`, while the reasoning-continuity
`thoughtSignature` attaches to *sibling* parts (function-call and
text parts), not to the thought summary. To map this onto the
spec's uniform reasoning concept without losing multi-turn
correctness, this proposal extends §3 so `TextBlock` and `ToolCall`
may carry an optional opaque `signature` field (mirroring
`ThinkingBlock.signature` from 0037), and generalizes the
reasoning-block round-trip rule to **single-provider scope**:
signatures are provider-bound, and cross-provider routing strips
them. OA-level pipeline code interacts with reasoning content
uniformly (read `ThinkingBlock.text`, branch, log) regardless of
provider; the wire-level capture and round-trip of signatures is
provider-specific and handled entirely within each §8.X mapping.

Structured output uses the native path. Gemini, like OpenAI (§8.1.5)
and Anthropic (§8.2.5), has a native schema-constrained-decoding
field (`generationConfig.responseJsonSchema`); the prompt-augmentation
fallback applies only to older models lacking native support
(§8.3.5.1, mirroring Anthropic's §8.2.5.1).

## Motivation

Gemini is the third major provider protocol adopted across the OA
implementation surface (after OpenAI Chat Completions in §8.1 and
Anthropic Messages in §8.2). Its wire shape diverges enough from
both that neither existing mapping applies:

- **`contents` / `parts` structure.** Where OpenAI uses
  `messages[].content` and Anthropic uses `messages[].content`
  (string or block array), Gemini uses `contents[].parts[]` —
  every message body is a list of typed `Part` objects.
- **`model` role.** Gemini names the assistant role `model`, not
  `assistant`. The wire mapping translates spec `assistant` ↔
  Gemini `model`.
- **`systemInstruction` top-level.** Like Anthropic, Gemini puts
  the system prompt at the request top level (as a `Content`
  object), not as a message-list entry. Spec `system` messages
  are extracted.
- **No `tool` role.** Tool results are `functionResponse` parts
  inside user-role contents (the same structural pattern as
  Anthropic's `tool_result`, requiring the same bidirectional
  `tool` role translation).
- **Tool definition nesting.** Tools nest as
  `tools[].functionDeclarations[]`, each
  `{name, description, parameters}`. The spec `Tool.parameters`
  JSON Schema passes through under `parameters`.
- **Tool-choice shape.** `toolConfig.functionCallingConfig` with
  `mode` ∈ {`AUTO`, `ANY`, `NONE`, `VALIDATED`} and an optional
  `allowedFunctionNames` list — a different shape and a different
  mode set from both OpenAI and Anthropic.
- **`generationConfig` nesting.** Sampling parameters
  (`temperature`, `topP`, `topK`, `maxOutputTokens`,
  `stopSequences`) nest under `generationConfig`, not at the
  request root.
- **Native structured output.** `generationConfig.responseMimeType:
  "application/json"` + `generationConfig.responseJsonSchema` —
  native schema-constrained decoding, as OpenAI (§8.1.5) and
  Anthropic (§8.2.5) also provide.
- **Thought-signature placement.** Gemini's reasoning-continuity
  signatures attach to sibling parts (function-call / text),
  not to the thought summary — structurally different from
  Anthropic's self-contained thinking-block signature.

Codifying these mappings in spec gives the same cross-language
behavioral consistency §8.1 and §8.2 provide: sibling language
implementations targeting Gemini must agree on the wire shape, the
`tool` role translation, the native structured-output path, and
the thought-signature round-trip mechanics.

## Detailed design

### §3 — reasoning-continuity signature generalization

0037 introduced `ThinkingBlock {text, signature}` and
`RedactedThinkingBlock {data}` with `signature` as an opaque,
provider-issued, round-trip-preserved token. That shape fits
Anthropic, where the signature is a property of the thinking
block itself. Gemini attaches its `thoughtSignature` to *sibling*
parts (function-call and text parts), so the spec needs a place to
carry a round-trip signature on those block types too — and,
because Gemini's thought summary itself carries no signature,
`ThinkingBlock.signature` is relaxed from required (0037) to
optional.

**§3 ToolCall record** — add an optional field:

| Field | Required | Description |
|---|---|---|
| `signature` | optional | An opaque, provider-issued reasoning-continuity token. Present only when a provider attaches reasoning-continuity signatures to tool calls (e.g., Gemini's `thoughtSignature`). Implementations MUST preserve it verbatim and pass it back to the SAME provider on round-trip; spec callers MUST NOT construct, modify, or interpret it. Absent for providers that do not attach signatures to tool calls. |

**§3.1.1 TextBlock** — add an optional field:

| Field | Required | Description |
|---|---|---|
| `signature` | optional | Same semantics as `ToolCall.signature` — an opaque provider reasoning-continuity token, present only when the provider attaches one to a text block. |

**§3.1.4 ThinkingBlock** — relax `signature` from required to
optional:

| Field | Required | Description |
|---|---|---|
| `signature` | optional | Opaque provider reasoning-continuity token. Present only when the provider attaches it to the thinking block itself (Anthropic). Absent when the provider carries the signature on sibling parts — e.g. Gemini's `thoughtSignature`, where the thought summary maps to a `ThinkingBlock` with no own signature. 0037 introduced this field as required; Gemini's sibling-part placement requires relaxing it. |

**Single-provider round-trip rule (new §3 normative paragraph).**
Reasoning-continuity signatures — `ThinkingBlock.signature`,
`RedactedThinkingBlock.data`, and the new `ToolCall.signature` /
`TextBlock.signature` — are **provider-bound**. A signature
produced by provider P is meaningful only to P's wire mapping;
it is NOT portable across providers. When a message list carrying
reasoning-continuity signatures is routed through a §8.X mapping
for a DIFFERENT provider than the one that produced them, that
mapping MUST strip the signatures (and any `ThinkingBlock` /
`RedactedThinkingBlock` entries) before emitting the wire request,
exactly as §8.1 strips thinking blocks for OpenAI. This generalizes
0037's §8.1 strip-on-send rule: thinking-bearing conversations are
single-provider for round-trip purposes. The OA-level use of
reasoning content (reading `ThinkingBlock.text`, branching on it,
logging it) is uniform across providers; only the wire-level
capture and round-trip of signatures is provider-specific.

This codifies the design principle that an application uses one
provider's reasoning surface at a time — cross-provider reasoning
round-trip is out of scope (and not a realistic single-conversation
pattern). The OA pipeline-level concept and usage patterns for
"thinking content" stay identical across providers; the wire
get/transmit is per-provider.

### §8.3 — Google Gemini mapping (new)

The Gemini `generateContent` API
(`POST /v1beta/models/{model}:generateContent`) is the
provider-native protocol for Google's Gemini model family.

#### §8.3.1 Request mapping

**System extraction.** Any §3 messages with `role: "system"` are
removed from the spec message list; their text content is
concatenated (joined with `\n\n` when more than one is present,
preserving order) into Gemini's top-level `systemInstruction`
field as a `Content` object: `{"parts": [{"text": <concatenated>}]}`.
The `contents` array sent to Gemini contains only `user` and
`model` role entries. Non-text content in system messages is
rejected at pre-send validation (`provider_invalid_request`).

**Role + body shape.** Each remaining spec message maps to one
Gemini `Content`:

| Spec role | Gemini `role` | Notes |
|---|---|---|
| `user` | `user` | `content` maps to `parts` per §8.3.1.1. |
| `assistant` | `model` | `content` blocks + `tool_calls` map to `parts` per §8.3.1.1. |
| `tool` | (no direct Gemini role) | Maps via §8.3.1.2 bidirectional translation to a `user`-role `Content` containing `functionResponse` parts. |

The spec `assistant` role name translates to Gemini's `model` on
send and back to `assistant` on receive.

**Tool definitions.** A §4 `Tool` `{name, description, parameters}`
maps into Gemini's `tools[].functionDeclarations[]`:

```
{
  "tools": [
    {
      "functionDeclarations": [
        { "name": <name>, "description": <description>, "parameters": <parameters> }
      ]
    }
  ]
}
```

The spec `parameters` JSON Schema passes through under
`parameters` verbatim.

**Tool-choice mapping.** The §5 `tool_choice` parameter maps to
Gemini's `toolConfig.functionCallingConfig`:

| Spec `tool_choice` | Gemini `functionCallingConfig` |
|---|---|
| `None` / absent | (field omitted) |
| `"auto"` | `{"mode": "AUTO"}` |
| `"required"` | `{"mode": "ANY"}` |
| `"none"` | `{"mode": "NONE"}` |
| `{type: "tool", name: X}` | `{"mode": "ANY", "allowedFunctionNames": [X]}` |

The `"required"` → `"ANY"` rename is the load-bearing translation
(spec's cross-vendor name → Gemini's wire name). A specific-tool
choice maps to `ANY` mode constrained to a single allowed function
name. Gemini's fourth mode, `VALIDATED` (the model may call only
declared functions, validated against their schemas, or respond
in natural language), has no §5 `tool_choice` analogue in v1; it
is reachable via the extras-pass-through path
(`toolConfig` supplied as an undeclared field) and is documented
here so implementations recognize it rather than treating it as
invalid.

**RuntimeConfig field mapping.** The §6 `RuntimeConfig` declared
fields map to `generationConfig`:

- `temperature` → `generationConfig.temperature`
- `top_p` → `generationConfig.topP`
- `max_tokens` → `generationConfig.maxOutputTokens`
- `stop_sequences` → `generationConfig.stopSequences`
- `seed` → `generationConfig.seed`
- `frequency_penalty` → `generationConfig.frequencyPenalty`
- `presence_penalty` → `generationConfig.presencePenalty`

`max_tokens` is optional for Gemini (server default applies when
absent) — unlike Anthropic, no required-field validation.

All seven §6 declared `RuntimeConfig` fields map to `generationConfig`:
Gemini's `GenerationConfig` carries `seed`, `frequencyPenalty`, and
`presencePenalty` alongside `temperature` / `topP` / `maxOutputTokens` /
`stopSequences`. So, like the §8.1 OpenAI mapping (and unlike §8.2
Anthropic, which lacks the penalties), the Gemini mapping has no
unsupported-sampling-field rejections — every declared field has a
direct `generationConfig` target. Out-of-range values (e.g.,
`frequencyPenalty` / `presencePenalty` outside Gemini's documented
bounds) are surfaced by Gemini per §8.3.3, not pre-validated by the
mapping.

Gemini's `topK` is not a §6 declared field; callers needing it
supply it via the extras-pass-through path, which the §8.3
mapping places under `generationConfig`.

The bound model identifier becomes the `{model}` path segment in
the request URL (not a body field).

**Undeclared `RuntimeConfig` fields** pass through per §6's
extras-pass-through contract. Because Gemini nests sampling
parameters under `generationConfig`, the §8.3 mapping places
undeclared keys under `generationConfig` (not the request root),
matching where Gemini expects generation parameters. The mapping
does NOT validate, rename, or transform undeclared keys.

##### §8.3.1.1 Parts wire mapping

This sub-subsection covers two wire-encoding paths, mirroring
§8.2.1.1:

- Spec **content blocks** (per §3.1) appearing in message
  `content` map to Gemini `Part` entries per the table below.
- Spec **ToolCall** records in the assistant message's
  `tool_calls` field are extracted and serialized as Gemini
  `functionCall` parts; reverse on receive.

| Spec source | Gemini `Part` entry |
|---|---|
| `TextBlock { text }` | `{ "text": <text> }` |
| `ImageBlock` with `source: inline { base64_data }` + `media_type` | `{ "inlineData": { "mimeType": <media_type>, "data": <base64_data> } }`. The `detail` hint, when set, is dropped — Gemini does not honor it. |
| `ImageBlock` with `source: url { url }` | `{ "fileData": { "mimeType": <inferred>, "fileUri": <url> } }`. Gemini references external media via `fileData.fileUri`; the `detail` hint is dropped. (Note: Gemini's `fileUri` typically expects a Gemini Files API URI or a supported storage URI; arbitrary `http(s)` image URLs may be rejected by the provider — surfaced as `provider_unsupported_content_block` per §8.3.3.) |
| `ToolCall { id, name, arguments, signature? }` from assistant `tool_calls` field | `{ "functionCall": { "name": <name>, "id": <id>, "args": <arguments> }, "thoughtSignature": <signature> }`. The `id` round-trips Gemini's per-call identifier. `args` is the deserialized mapping (Gemini accepts an object directly). When the spec `ToolCall` carries an opaque `signature` (a Gemini `thoughtSignature` captured on receive), it is reattached to this part on send. |
| `ThinkingBlock { text, signature? }` | A `Part` flagged `{ "text": <text>, "thought": true }`. Gemini's thought summary is a text part with `thought: true`; the `signature`, when present, is reattached per the thought-signature mapping in §8.3.2 below. |
| `TextBlock { text, signature }` (assistant, signature present) | `{ "text": <text>, "thoughtSignature": <signature> }`. A text part carrying a captured Gemini thought signature. |

`thoughtSignature` is emitted on a part only when the corresponding
spec block carries a non-empty `signature`. When the block has no
signature (the common case), the key MUST be omitted entirely — not
set to `null` — so the wire request matches Gemini's contract.

Empty content blocks are rejected at pre-send validation per §3 /
`provider_invalid_request`.

##### §8.3.1.2 `tool` role bidirectional translation

As with §8.2.1.2, spec `tool` messages have no Gemini role.

**Spec → Gemini (on send):** each consecutive run of spec `tool`
messages collapses into a single Gemini `user`-role `Content`
whose `parts` are `functionResponse` entries — one per spec `tool`
message, preserving order:

```
{
  "role": "user",
  "parts": [
    { "functionResponse": { "name": <name>, "id": <tool_call_id>, "response": <wrapped content> } }
    /* one per consecutive spec tool message */
  ]
}
```

The `name` is the tool name from the matching `functionCall`; the
`id` is the spec `tool_call_id` (matching the `functionCall.id`);
the `response` wraps the spec `tool` message's content. Gemini
expects a structured object under `response`, and §3 tool content is
a string, so the mapping always wraps it as `{"result": <content>}`
(it does not attempt to JSON-parse the string).

**Gemini → Spec (on receive):** each `functionResponse` part in a
user-role `Content` maps back to one spec `tool` message with
`tool_call_id` from the part's `id` and content from `response`.

The translation is lossless and bidirectional.

#### §8.3.2 Response mapping

A successful Gemini response maps onto a §6 `Response`:

- `message` — built from `candidates[0].content` (role `model` →
  spec `assistant`). Each `parts` entry maps back to its spec form
  per §8.3.1.1: `text` parts → `TextBlock` (or `ThinkingBlock`
  when flagged `thought: true`); `functionCall` parts → `ToolCall`
  entries. Block order is preserved.
- **Thought-signature capture.** When a `parts` entry carries a
  `thoughtSignature`, the §8.3 mapping captures it onto the
  corresponding spec block's opaque `signature` field:
  `functionCall` part → `ToolCall.signature`; text part →
  `TextBlock.signature`; a `thought: true` summary part's own
  text → `ThinkingBlock.text` (Gemini's summary part does not
  itself carry the signature). The mapping MUST preserve every
  `thoughtSignature` it receives so that, on the next
  `complete()` call passing the assistant message back, the
  signatures reattach to their parts in original position (per
  Gemini's "return all parts with signatures intact" rule). OA-level
  code never reads these signatures; they are opaque round-trip
  state.
- `tool_calls` — extracted from `functionCall` parts (mirrors
  §8.2.2's dual surfacing on `Response.message.tool_calls`).
- `finish_reason` — derived from `candidates[0].finishReason`:

  | Gemini `finishReason` | Spec `finish_reason` |
  |---|---|
  | `STOP` | `"stop"` |
  | `MAX_TOKENS` | `"length"` |
  | `SAFETY` / `RECITATION` / `BLOCKLIST` / `PROHIBITED_CONTENT` / `SPII` | `"content_filter"` |
  | `MALFORMED_FUNCTION_CALL` / `UNEXPECTED_TOOL_CALL` / `LANGUAGE` / `OTHER` | `"error"` |
  | (a `functionCall` part is present) | `"tool_calls"` |
  | (any other / unknown value) | `"error"` |

  Note: Gemini does not use a dedicated tool-call finish reason in
  all versions — when the response contains a `functionCall` part,
  the mapping reports `"tool_calls"` regardless of the raw
  `finishReason`. The table above covers the documented Gemini
  `finishReason` enum; image-generation-only variants (`IMAGE_SAFETY`,
  `IMAGE_PROHIBITED_CONTENT`, `IMAGE_RECITATION`, `IMAGE_OTHER`,
  `NO_IMAGE`) are out of scope for this text/tool mapping and fall to
  the `"error"` fallback, as does any value not listed. The raw value
  is preserved in `Response.raw`.

- `usage` — built from `usageMetadata`:
  `usage.prompt_tokens` ← `promptTokenCount`,
  `usage.completion_tokens` ← `candidatesTokenCount`,
  `usage.total_tokens` ← `totalTokenCount`. Gemini-specific
  subfields (`cachedContentTokenCount`, `toolUsePromptTokenCount`,
  `thoughtsTokenCount`, the `*TokensDetails` modality breakdowns)
  surface in `Response.raw.usageMetadata` unchanged and are NOT
  promoted to the spec `usage` record.
- `raw` — the parsed JSON response body, verbatim. Gemini-specific
  fields (`promptFeedback`, `safetyRatings`, `modelVersion`,
  `responseId`) surface here unchanged.

#### §8.3.3 Error mapping

Gemini returns errors with an HTTP status and a body
`{"error": {"code": <int>, "message": <string>, "status": <string>}}`.

| Gemini condition | Spec category |
|---|---|
| HTTP 400 `INVALID_ARGUMENT` (malformed request) | `provider_invalid_request` |
| HTTP 400 / 403 indicating the model rejected a content part (unsupported media type, unsupported `fileUri` scheme) | `provider_unsupported_content_block` |
| HTTP 401 / 403 `PERMISSION_DENIED` / `UNAUTHENTICATED` | `provider_authentication` |
| HTTP 404 `NOT_FOUND` (model not found) | `provider_invalid_model` |
| HTTP 429 `RESOURCE_EXHAUSTED` | `provider_rate_limit` |
| HTTP 500 `INTERNAL` | `provider_unavailable` |
| HTTP 503 `UNAVAILABLE` | `provider_unavailable` |
| HTTP 504 `DEADLINE_EXCEEDED` | `provider_unavailable` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

Gemini's `error.status` string surfaces in `Response.raw` for
finer-grained handling.

#### §8.3.4 Concurrency

Matches §8.1.4. Gemini's hosted API supports concurrent requests;
implementations MUST NOT add a serialization layer. Client-side
rate-limit needs use the pipeline-utilities rate limiter or
middleware.

#### §8.3.5 Structured output

Gemini natively supports schema-constrained decoding. When
`complete()` is called with a `response_schema`, the §8.3 mapping
sets:

```
{
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseJsonSchema": <response_schema>
  }
}
```

Gemini exposes two schema fields: `responseSchema` (an OpenAPI 3.0
Schema subset) and `responseJsonSchema` (a full JSON Schema). Because
OA's §6 `response_schema` is a full JSON Schema (per 0016), the §8.3
mapping targets `responseJsonSchema`, so the schema round-trips
faithfully — `responseSchema` would silently drop JSON Schema
constructs outside the OpenAPI subset. The `response_schema` passes
through under `responseJsonSchema` unchanged. The response's text
content is the JSON string conforming to the schema; the §8.3 mapping
parses it into `Response.parsed` and validates against
`response_schema` per §6. On validation failure, raise
`structured_output_invalid` per §7. The behavioral contract matches
§8.1.5's native path.

When `complete()` is called without `response_schema`, the request
MUST NOT include `responseMimeType` / `responseJsonSchema`; the
free-form wire shape is preserved.

This is the native path: Gemini, like OpenAI (§8.1.5) and Anthropic
(§8.2.5), provides native schema-constrained decoding. The
prompt-augmentation fallback (§8.3.5.1) applies only to models
lacking native support, mirroring how §8.2.5.1 handles older
Anthropic models.

##### §8.3.5.1 Fallback for older models

Gemini model versions predating native JSON-Schema-constrained decoding
fall back to prompt-augmentation per §8.1.5.1's pattern (append a
schema directive to `systemInstruction` or the message list,
parse the text response, validate, raise
`structured_output_invalid` on failure). Implementations MUST
document which path a given call uses.

## Spec-text changes (summary)

Edits to `spec/llm-provider/spec.md`:

1. **§3 ToolCall record** — add optional opaque `signature` field
   (provider reasoning-continuity round-trip token).
2. **§3.1.1 TextBlock** — add optional opaque `signature` field
   (same semantics).
3. **§3.1.4 ThinkingBlock** — relax `signature` from required to
   optional (a provider may emit a thought summary with no own
   signature, e.g. Gemini).
4. **§3 reasoning-continuity round-trip rule** — new normative
   paragraph: signatures are provider-bound; cross-provider
   routing strips them (generalizes 0037's §8.1 strip rule).
5. **§8.3 (new)** — full Google Gemini mapping per the §8.X
   template, with sub-subsections §8.3.1.1 (parts wire mapping),
   §8.3.1.2 (`tool` role translation), and §8.3.5.1 (structured-
   output fallback).

No changes to §3 role set, §4 Tool definition (beyond the
`ToolCall.signature` field), §5 Provider interface, §6 Response
shape, §7 error categories, §9 Determinism, or §10 *Out of scope*.

§8.1 and §8.2 gain no provider-specific text, but the generalized §3
strip rule applies to them uniformly: on a cross-provider hop they
strip the new `TextBlock.signature` / `ToolCall.signature` fields
(and any thinking blocks), exactly as §8.1 already strips thinking
blocks for OpenAI. Fixture 053 verifies this.

## Conformance fixtures

Ten new fixture pairs under `spec/llm-provider/conformance/`:

| Fixture | Asserts |
|---|---|
| `044-gemini-basic-message-round-trip` | user→model text round-trip; system extraction to `systemInstruction`; `contents` holds only user/model; `model` role ↔ spec `assistant`. |
| `045-gemini-function-call-flow` | model `functionCall` (with `id`) → spec `tool` messages → Gemini `functionResponse` parts in user content (§8.3.1.2) → final response. |
| `046-gemini-image-content-blocks` | inline (`inlineData`) and URL (`fileData.fileUri`) image variants; `detail` hint dropped. |
| `047-gemini-tool-choice-modes` | all mappings: `None`/absent, `auto`→AUTO, `required`→ANY, `none`→NONE, specific-tool→ANY+allowedFunctionNames. |
| `048-gemini-runtime-config-mapping` | all seven §6 declared fields map: `temperature`/`top_p`→topP/`max_tokens`→maxOutputTokens/`stop_sequences`→stopSequences/`seed`→seed/`frequency_penalty`→frequencyPenalty/`presence_penalty`→presencePenalty. |
| `049-gemini-error-mapping` | HTTP status + Gemini `error.status` → §7 category table per §8.3.3. |
| `050-gemini-structured-output-native` | native path: `response_schema` → `generationConfig.responseJsonSchema` + `responseMimeType`; response text parsed into `Response.parsed`. |
| `051-gemini-structured-output-fallback` | prompt-augmentation fallback for models without native support. |
| `052-gemini-thought-signature-round-trip` | thinking response: `thought: true` summary → `ThinkingBlock.text`; `thoughtSignature` on a `functionCall` part → `ToolCall.signature`; second call reattaches the signature to the reconstructed `functionCall` part in position. |
| `053-cross-provider-signature-strip` | a spec assistant message carrying Gemini-origin signatures (on `ToolCall`/`TextBlock`) routed through the §8.1 OpenAI mapping (or §8.2 Anthropic mapping) strips the signatures and any thinking blocks; no error raised; wire request is valid. |

## Versioning

**MINOR bump.** Targets the next MINOR after 0037 ships (v0.29.0
if 0037 is v0.28.0). Additive:

- New §8.3 wire-format mapping (does not change §8.1 / §8.2).
- New optional `signature` field on §3 `ToolCall` and §3.1.1
  `TextBlock` (additive — absent unless a provider attaches a
  signature; OA-level code treats as opaque).
- Generalized single-provider round-trip rule (additive — affects
  outbound wire only when signatures are present, which prior to
  0037/0038 could not occur).

No breaking changes. Existing callers and the §8.1 / §8.2 mappings
are unaffected.

## Backwards compatibility

- **Callers using §8.1 / §8.2 only:** no change.
- **§3 ContentBlock / ToolCall consumers:** the optional
  `signature` field is additive; exhaustive consumers ignore it
  (it is opaque and absent unless a Gemini-origin signature is
  present).
- **Cross-provider routing:** a conversation carrying
  Gemini-origin signatures routed to OpenAI / Anthropic strips
  them (single-provider round-trip rule). Reasoning continuity is
  lost on the cross-provider hop, as it would be regardless.

## Dependency on proposal 0037

0038 depends on 0037 being accepted first: it reuses
`ThinkingBlock` / `RedactedThinkingBlock` (added by 0037's §3.1
expansion) and the §8.2.1.2 `tool` role bidirectional-translation
pattern, and it generalizes 0037's §8.1 strip-on-send rule. While
0037 is in Draft/Accept-pending state, this Draft references those
as "introduced by 0037 (pending acceptance)." Both resolve cleanly
once accepted in sequence (0037 then 0038).

## Out of scope

- **Streaming** (`streamGenerateContent`) — future cross-mapping
  streaming proposal.
- **Batch mode** (Gemini's batch API) — future cross-vendor batch
  capability (see 0037 *Out of scope*).
- **`thinkingConfig` request knobs** (`thinkingBudget`,
  `includeThoughts`) — surfacing thinking on the request side
  (how much to think, whether to include summaries) is a
  reasoning-control surface broader than this wire mapping;
  reachable via extras-pass-through under `generationConfig` for
  now. A future cross-vendor reasoning-control proposal may add a
  first-class surface.
- **Safety settings** (`safetySettings` / `safetyRatings`) —
  Gemini-specific; user-extensible via extras; surfaces in
  `Response.raw`. Cross-vendor content-safety abstraction is a
  future topic.
- **Cached content** (`cachedContent`) — Gemini's explicit context
  caching; out of scope alongside Anthropic's cache_control.
- **`candidateCount` > 1** — multi-candidate responses; v1 of the
  Provider interface assumes a single response (per §8.1.2's
  single-choice assumption). Mapping reads `candidates[0]`.
- **Files API** (`fileData.fileUri` upload lifecycle) — the
  mapping passes a `fileUri` through but does not spec the upload
  / lifecycle; that is a provider-side concern.

## Open questions

None. Both items flagged at draft time were verified against the
current Gemini API during revision and are now reflected in
normative text:

1. **`seed` / `frequency_penalty` / `presence_penalty` Gemini
   support** — confirmed: `GenerationConfig` carries `seed`,
   `frequencyPenalty`, and `presencePenalty`. §8.3.1 direct-maps all
   seven §6 declared fields (no `provider_invalid_request` for
   sampling fields), matching the §8.1 OpenAI mapping.
2. **Full `finishReason` enum** — confirmed and finalized in §8.3.2:
   `BLOCKLIST` / `PROHIBITED_CONTENT` / `SPII` join the
   `content_filter` row; `MALFORMED_FUNCTION_CALL` /
   `UNEXPECTED_TOOL_CALL` / `LANGUAGE` / `OTHER` map to `"error"`;
   image-generation-only variants are out of scope and fall to the
   `"error"` fallback.
