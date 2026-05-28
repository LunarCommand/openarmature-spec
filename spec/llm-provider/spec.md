# LLM Provider

Canonical behavioral specification for the OpenArmature LLM provider abstraction.

- **Capability:** llm-provider
- **Introduced:** spec version 0.4.0
- **History:**
  - created by [proposal 0006](../../proposals/0006-llm-provider-core.md)
  - §3 Message shape extended (user content MAY be a sequence of content blocks); §3.1 Content blocks added (text and image blocks; image input only on user messages); §7 gained `provider_unsupported_content_block` error category; §8.1 user-row updated and §8.1.1 content-block wire mapping added; §10 multi-modal entry split (image input now covered; audio/video and image outputs remain deferred) by [proposal 0015](../../proposals/0015-llm-provider-multimodal-images.md)
  - §5 `complete()` extended with optional `response_schema` parameter; §6 Response gained `parsed` field; §7 gained `structured_output_invalid` error category (non-transient by default); §8.5 structured output wire mapping added (with §8.5.1 prompt-augmentation fallback and §8.5.2 response mapping); §10 structured output deferral removed by [proposal 0016](../../proposals/0016-llm-provider-structured-output.md)
  - §8 renamed from "OpenAI-compatible wire format" to "Wire-format mappings" and reorganized as a catalog of provider mappings; existing OpenAI-compatible body nested under new §8.1 "OpenAI-compatible mapping" (subsections §8.1 through §8.5 → §8.1.1 through §8.1.5); §8 framing paragraph added establishing the default placement rule (in-spec for any mapping with multi-language ambition; out-of-tree allowed only for single-language / opt-out / experimental cases) by [proposal 0019](../../proposals/0019-llm-provider-multi-provider-extension.md)
  - §5 `complete()` extended with optional `tool_choice` parameter (four modes: `"auto"` / `"required"` / `"none"` / `{type: "tool", name: X}`) with pre-send validation routing through `provider_invalid_request`; §7 clarified to enumerate the three new validation failure modes; §8.1.1 gained a `tool_choice` mapping row by [proposal 0025](../../proposals/0025-llm-provider-tool-choice.md)
  - §8 framing gained a *Per-mapping subsection structure* paragraph recommending the canonical §8.X template (Request mapping / Response mapping / Error mapping / Concurrency / Structured output) with allowance for sub-subsections, provider-specific top-level additions, and SHOULD-level divergence-explanation requirement; resolves 0019's open-question #2 by [proposal 0026](../../proposals/0026-llm-provider-wire-format-mapping-template.md)
  - §6 `RuntimeConfig` extended with three new declared fields (`frequency_penalty`, `presence_penalty`, `stop_sequences`) matching the cross-vendor OpenTelemetry GenAI semconv naming; existing "MAY accept additional provider-specific fields" line replaced with an explicit extras-pass-through contract (undeclared fields MUST reach the wire untouched) and a null-skip contract (declared fields with `None` MUST be omitted from the wire body); §8.1 OpenAI-compatible mapping extended to cover the three new declared-field mappings (with `stop_sequences` → OpenAI body `stop` rename) and formally specify undeclared-field placement at the OpenAI request-body root by [proposal 0032](../../proposals/0032-llm-provider-runtime-config-refinements.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The LLM provider capability defines a uniform request/response surface for sending messages to a
Large Language Model and receiving its response. It is the substrate every higher-level LLM
capability composes against — tool systems, prompt management, evaluation harnesses, agent loops.

The substrate is intentionally narrow:

- A provider is **stateless**. It does not maintain conversation history; the caller passes the full
  message list on every call.
- A provider does **not** loop on tool calls. If the assistant returns tool calls, the caller is
  responsible for executing the tools and making a follow-on `complete()` with the results.
- A provider does **not** handle retry, rate limiting, fallback, or routing. Those are pipeline-
  utilities concerns and compose above the provider via middleware.
- A provider is **bound to a single model identifier**. Switching models means constructing a new
  provider, not passing a different argument per call. (Implementations MAY offer convenience
  factories that produce per-model providers from shared credentials; that is a constructor concern,
  not a behavioral one.)

Every constraint above is a deliberate scope cut. The narrower the provider surface, the easier it is
to swap implementations, mock for tests, and stack pipeline utilities on top.

**Transparency.** Per charter §3.1 principle 8 ("Transparency over abstraction"), the provider
abstraction surfaces a normalized shape — `Message`, `Tool`, `Response` — without hiding what the
underlying provider returned. The `Response` record carries the parsed provider response verbatim
alongside the normalized fields (§6 `raw`), and the §7 error categories preserve the underlying
provider exception as cause. Users who need provider-specific fields (logprobs, content-filter
details, vendor-specific extensions) reach through the abstraction directly; structure is added,
never removed.

## 2. Concepts

**Message.** A typed entry in a conversation. The four message kinds are `system`, `user`,
`assistant`, and `tool`. Each kind carries kind-specific content as defined in §3.

**Tool.** A function the model may request the user execute. A tool definition is a record of `name`,
`description`, and `parameters` (a JSON Schema describing the argument shape).

**Tool call.** A request from an assistant message to invoke a named tool with structured arguments.
The user is responsible for executing the tool and returning the result via a `tool` message bearing
the corresponding `tool_call_id`.

**Provider.** An object that, given a sequence of messages and an optional set of tools, returns a
single assistant message wrapped in a `Response`. A provider is bound to a specific model identifier.

**Response.** The result of a provider call: the assistant message, a finish reason, and usage
information.

## 3. Message shape

A message is a record with the following fields:

| Field | Required | Description |
|---|---|---|
| `role` | yes | One of `"system"`, `"user"`, `"assistant"`, `"tool"`. Discriminator. |
| `content` | conditional (see below) | Text content of the message, OR a non-empty ordered sequence of content blocks per §3.1. `user` messages MAY carry text or image blocks; `assistant` messages MAY carry text, thinking, and redacted-thinking blocks (per the per-role constraints below). |
| `tool_calls` | only on `assistant` | Ordered list of `ToolCall` records the model is requesting. |
| `tool_call_id` | required on `tool` | The `id` of the matching `assistant` tool call. |

Per-role constraints:

- `system`: `content` MUST be a non-empty string. `tool_calls` MUST be absent. `tool_call_id` MUST be
  absent.
- `user`: `content` MUST be one of:
  - a non-empty string (text-only message), OR
  - a non-empty ordered sequence of content blocks (per §3.1).

  `tool_calls` MUST be absent. `tool_call_id` MUST be absent.
- `assistant`: `tool_calls` MAY be present. If `tool_calls` is present and non-empty, `content` MAY
  be empty (the assistant is purely calling tools); if `tool_calls` is absent or empty, `content`
  MUST be one of:
  - a non-empty string (text-only message), OR
  - a non-empty ordered sequence of content blocks containing `TextBlock` and/or
    `ThinkingBlock` / `RedactedThinkingBlock` entries (per §3.1). `ImageBlock` MUST NOT appear in
    an `assistant` message (image blocks are user-only). Thinking and redacted-thinking blocks
    appear only when a provider mapping surfaces provider-emitted reasoning content (per §3.1.4 /
    §3.1.5).

  `tool_call_id` MUST be absent.
- `tool`: `content` MUST be a string (the tool's textual result; serialize structured results to a
  string at the call boundary). `tool_call_id` MUST be present and MUST match the `id` of an
  `assistant` `ToolCall` earlier in the message list. `tool_calls` MUST be absent.

A `ToolCall` record:

| Field | Description |
|---|---|
| `id` | String identifier, unique within the message. The matching `tool` message bears this `id` as `tool_call_id`. For provider-returned tool calls, implementations MUST preserve the provider's `id` verbatim — neither rewriting nor normalizing it. Ids are opaque correlators within a single message list; preserving the original lets users correlate with provider-side logs/billing and persists naturally as conversations are stored, replayed, or routed. |
| `name` | The tool name. MUST match a `Tool.name` declared in the call's `tools` argument under non-error responses; on `finish_reason: "error"`, an unmatched `name` MAY appear (see below). |
| `arguments` | A JSON-serializable mapping of argument names to values. Under non-error responses, MUST be a parsed mapping conforming to the tool's `parameters` schema. Under `finish_reason: "error"`, MAY be `null` (the implementation could not parse the provider's bytes as JSON) or a parsed mapping that does not conform to the schema. |

**Validation timing.** Implementations MUST validate message-shape constraints (per-role required
fields, `tool_call_id` matching, etc.) at the boundary of `complete()` — before sending to the
provider, and on the response before returning. Tool argument validation against the parameters
schema happens at the same boundaries; under non-error responses, a malformed assistant `ToolCall`
from the provider raises `provider_invalid_response` (§7).

**Validation under `finish_reason: "error"`.** A degraded response MAY carry `tool_calls`, and
those tool calls MAY be partially constructed: malformed argument JSON (truncated, syntactically
invalid), `arguments` that don't match the parameters schema, or unmatched `name`. Implementations
MUST NOT raise `provider_invalid_response` in this case — the partial response is the response.
The implementation surfaces what it could parse:

- Tool calls with parseable JSON arguments populate `arguments` as a mapping (whether or not it
  matches the schema).
- Tool calls with unparseable arguments populate `arguments` as `null`. The original bytes are
  available verbatim via `Response.raw`.
- Tool calls with missing or unknown `name` are still surfaced.

Callers iterating `tool_calls` after a successful (non-error) `complete()` can rely on validated
arguments. Callers handling `finish_reason: "error"` SHOULD inspect each tool call before
executing — argument repair (parsing partial JSON, completing truncated braces) is an application
concern, performed against `Response.raw` for the original bytes. The spec deliberately surfaces
malformed data rather than dropping it, so applications can repair-and-continue.

**Cross-provider id round-tripping.** A conversation MAY traverse multiple providers within a
single application — for example, behind an LLM gateway / router that applies fallback strategies
across providers, or when an application explicitly switches providers between conversation rounds.
Tool-call ids are opaque correlators within the message list, not provider-side references;
providers accept arbitrary id strings on inbound requests and only verify that subsequent
`tool_call_id` values match earlier tool calls in the same conversation. Because implementations
preserve provider-supplied ids verbatim (per the `id` field rule above), message lists round-trip
across providers cleanly without id rewriting. Applications that need a unified internal id format
MAY rewrite ids at their own boundary; the spec keeps the abstraction transparent and leaves that
choice to the application.

### 3.1 Content blocks

A **content block** is a typed record with a discriminator field identifying the block type.
The spec defines four block types: text, image, thinking, and redacted-thinking. Text and image
blocks appear in `user` messages (and text blocks in `assistant` messages); thinking and
redacted-thinking blocks appear only in `assistant` messages when a provider mapping surfaces
provider-emitted reasoning content (per §3.1.4 / §3.1.5).

#### 3.1.1 Text block

A text block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"text"`. |
| `text` | yes | A non-empty string. |

A text block is the content-array equivalent of the text-string form. A user message containing
exactly one text block with text `T` is normatively equivalent to a user message with
`content: T`.

#### 3.1.2 Image block

An image block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"image"`. |
| `source` | yes | One of `url` or `inline` (per §3.1.3). |
| `media_type` | conditional | Required when `source` is `inline`; ignored when `source` is `url` (the provider infers the media type from the URL's payload). Implementations MUST accept the IANA media types `image/png`, `image/jpeg`, and `image/webp` at minimum, and MAY accept additional `image/*` media types they document support for. Portable users SHOULD restrict to the three guaranteed types. |
| `detail` | optional | A hint to the provider about the desired image-processing fidelity. One of `"auto"`, `"low"`, `"high"`. Default is `"auto"`. Providers that do not honor a detail hint MUST ignore it without error. |

#### 3.1.3 Image source

The `source` field on an image block carries one of two variants:

- **`url`** — the image is referenced by a URL: `{ type: "url", url: <string> }`. The URL MAY
  be `http(s)://`, `data:` (RFC 2397 inline data URI), or another scheme the provider
  documents support for. Implementations MUST pass the URL through to the wire unchanged; the
  spec does not mandate fetching, caching, or transforming URL-form images.
- **`inline`** — the image is provided as base64-encoded bytes:
  `{ type: "inline", base64_data: <string> }`. The `media_type` field on the image block
  (§3.1.2) MUST be present for inline images. Implementations MUST NOT inspect, transcode, or
  re-encode the bytes; they pass through to the wire encoded as the provider's wire format
  expects (§8.1.1.1).

A single image block carries exactly one source — `url` XOR `inline`. The discriminator is
the `type` field on the source itself.

#### 3.1.4 Thinking block

A thinking block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"thinking"`. |
| `text` | yes | The reasoning content the provider emitted. A non-empty string. |
| `signature` | yes | An opaque provider-issued token used by the provider to verify the block on round-trip. Implementations MUST pass the value through unchanged; spec callers MUST NOT construct, modify, or fabricate the field. |

Thinking blocks represent provider-emitted reasoning content. They MAY appear in `assistant`
message content sequences. They MUST NOT appear in `user`, `system`, or `tool` message content.
Implementations MUST surface thinking blocks a provider emits on the `Response.message.content`
block list (per §6) and MUST preserve them verbatim when the same `assistant` message is sent
back to that provider in a subsequent `complete()` call.

Provider mappings that do not surface reasoning content (e.g., the §8.1 OpenAI mapping) MUST
strip thinking blocks from outbound `assistant` messages (per §8.1.1's strip-on-send rule) and
MUST NOT emit thinking blocks on inbound responses. Each provider's §8.X mapping specifies its
wire-level handling. Thinking-block `signature` values are provider-bound — a signature issued
by one provider is not portable to another; routing thinking-bearing conversation history to a
different provider's mapping strips the blocks rather than forwarding signatures the target
provider cannot verify.

#### 3.1.5 Redacted thinking block

A redacted thinking block is a record:

| Field | Required | Description |
|---|---|---|
| `type` | yes | The literal string `"redacted_thinking"`. |
| `data` | yes | An opaque provider-issued blob preserving the structural slot for reasoning content the provider has redacted from caller view. Implementations MUST pass the value through unchanged. |

The redacted variant covers cases where a provider's policy withholds reasoning text from the
caller while preserving the structural slot so subsequent conversation turns can round-trip
without breaking the provider's reasoning continuity. Same scope and round-trip rules as
`ThinkingBlock` (§3.1.4): `assistant`-message-content only; preserved verbatim on round-trip;
provider-bound; stripped when routed to a non-surfacing provider mapping.

#### 3.1.6 Mixing blocks

A user message MAY mix text and image blocks freely. An assistant message MAY contain thinking
and redacted-thinking blocks (per §3.1.4 / §3.1.5) alongside text blocks when the provider
mapping surfaces them; thinking blocks SHOULD precede text blocks in an assistant message's
content sequence, matching the order providers emit them. Implementations MUST preserve the
emitted block order on round-trip. The wire format preserves block order; providers vary in
whether they treat block order as semantically meaningful (e.g., "image appearing before its
describing text" vs. "image after"), so application code SHOULD construct the block sequence in
the order it wants the model to perceive it.

A content-block sequence MUST NOT be empty (per the §3 per-role constraint). A content-block
sequence consisting entirely of text blocks is valid (and is the multi-text-block shape some
applications prefer for prompt-composition reasons).

## 4. Tool definition

A `Tool` record:

| Field | Description |
|---|---|
| `name` | String identifier. MUST be unique within a single `complete()` call's `tools` list. |
| `description` | String describing the tool's behavior. Sent to the model. |
| `parameters` | A JSON Schema (object schema) describing the argument record. MUST be a valid JSON Schema; implementations SHOULD validate at call time. |

The `parameters` field is JSON Schema, not a language-native schema type. This keeps the spec
provider-agnostic (every supported wire format expects JSON Schema) and language-agnostic
(implementations may offer ergonomic constructors that compile from native types into JSON Schema —
e.g., Pydantic's `model_json_schema()`, Zod's `zod-to-json-schema` — but the spec surface is JSON
Schema regardless).

## 5. Provider interface

A provider MUST expose the following operations:

### `ready()`

Async. Verifies that the bound model is reachable and serving — i.e., that the next `complete()`
call is expected to succeed. A successful return MUST imply that `complete()` would not raise any
of the §7 categories that surface mismatched configuration or unloaded state
(`provider_authentication`, `provider_invalid_model`, `provider_model_not_loaded`,
`provider_unavailable`). Raises one of the §7 categories on failure.

For hosted APIs this typically means credentials are valid, the base URL is reachable, and the
model is in the provider's catalog. For local servers (vLLM, LM Studio, llama.cpp),
this additionally means the model is loaded into memory and ready to serve — not just
configured. Implementations SHOULD distinguish these by raising `provider_invalid_model` when the
model is unknown to the provider versus `provider_model_not_loaded` when the model is known but
not yet serving (see §7).

Implementations SHOULD make this operation idempotent and inexpensive — a `GET /models`-style
probe is RECOMMENDED for hosted APIs; for local servers, a server-specific health endpoint that
distinguishes "model in registry" from "model loaded" SHOULD be preferred over a no-op
`complete()`.

`ready()` is a pre-flight check intended for fail-fast on startup or warmup polling. It MUST NOT
be called automatically by `complete()`; callers decide when (or whether) to invoke it.

### `complete(messages, tools=None, config=None, response_schema=None, tool_choice=None)`

Async. Performs a single completion call. When `response_schema` is supplied, the call
additionally constrains the model's output to conform to the schema. When `tool_choice` is
supplied, the call additionally constrains the model's tool-calling behavior.

- `messages` — non-empty ordered sequence of messages. The first message MAY be `system`; otherwise
  the message list begins with `user`. The last message before the call MUST be `user` or `tool` (the
  request to the model). Implementations MUST validate this ordering; violations raise
  `provider_invalid_request` (§7).
- `tools` — optional ordered sequence of `Tool` records. When present and non-empty, the model is
  permitted to return `tool_calls`. Tool names MUST be unique within the list.
- `config` — optional `RuntimeConfig` (§6). Per-call sampling parameters and budget hints.
- `response_schema` — optional JSON Schema describing the expected output shape. When `None` /
  absent, the call behaves as in v0.4.0: free-form text content; no parsed value. When present,
  MUST be a valid JSON Schema. The top-level schema MUST be an object schema (`type: "object"` at
  the root) — this matches §4 `Tool.parameters` and OpenAI's strict-mode wire format. Non-object
  top-level schemas are out of scope for this version; a follow-on MAY relax this if cross-provider
  demand warrants. Implementations SHOULD validate at call time. The JSON Schema convention matches
  §4 — see §4's note on language-native schema constructors compiling to JSON Schema.
- `tool_choice` — optional tool-choice constraint. One of:
  - `"auto"` — the model decides whether to call tools. Equivalent to the no-`tool_choice`
    default behavior when `tools` is non-empty; with `tools` empty / absent, the model has no
    tools to call regardless.
  - `"required"` — the model MUST return at least one tool call. `tools` MUST be non-empty when
    `tool_choice` is `"required"`; violations raise `provider_invalid_request` (§7) at pre-send
    validation.
  - `"none"` — the model MUST NOT call tools, even if `tools` is supplied. Useful for guarded
    LLM calls or for explicitly disabling tool-calling on a per-call basis without constructing
    a tools-less request.
  - `{type: "tool", name: <string>}` — the model MUST call the named tool (and no other). The
    named tool MUST appear in the supplied `tools` list; violations raise `provider_invalid_request`
    (§7) at pre-send validation. (`tools` MUST be non-empty in this case, by transitivity.)

  Default is `None` / absent. When `tool_choice` is `None` / absent, the engine MUST omit the
  wire-level `tool_choice` field — the provider's own default applies. This preserves the
  v0.4.0 behavior exactly (no wire-shape change for callers who don't supply `tool_choice`).

  The discriminated-union shape (three string literals plus one record form) is described
  abstractly; per-language ergonomics decide the type (e.g., Python could use
  `Literal["auto", "required", "none"] | ToolChoiceForce`; TypeScript could use a string union
  with the record form discriminated by `type`). Implementations MUST validate the shape at
  call time before sending.

Returns: a `Response` (§6).

When `response_schema` is set and the model returns content (not tool calls):

- `Response.parsed` is the parsed-and-validated structured value per `response_schema`.
- `Response.message.content` is the JSON-serialized string form of the structured output (preserved
  verbatim from the provider per §6).

When `response_schema` is set and `finish_reason` is `"tool_calls"`, `Response.parsed` MUST be
absent regardless of whether `message.content` is also populated (the §3 contract allows assistant
messages to carry both `tool_calls` and non-empty `content`, and this section does not change that).
`message.content` preserves the model's output verbatim per §6; the `parsed` slot only populates
when the model returned structured content (typically `finish_reason: "stop"`).

When `tools` and `response_schema` are both supplied, the model decides which path to take,
signaled by `finish_reason`. If `finish_reason` is `"tool_calls"`, the user handles tool execution
and may make a follow-on `complete()`; if `finish_reason` is `"stop"`, the user reads `parsed`
and/or `message.content`.

When `response_schema` is `None` / absent, `Response.parsed` is absent regardless of content. The
v0.4.0 behavior is preserved exactly.

Operation semantics:

- `complete()` MUST NOT mutate `messages`, `tools`, `config`, `response_schema`, or `tool_choice`.
- `complete()` MUST be reentrant: multiple concurrent calls on the same provider are permitted.
  Implementations MUST NOT serialize concurrent calls internally.
- `complete()` does NOT loop on tool calls. If the response's `finish_reason` is `"tool_calls"`,
  the caller is responsible for executing the tools, appending `tool` messages, and making a
  follow-on `complete()`.
- `complete()` does NOT retry on transient errors. Errors propagate; retry policy belongs above this
  layer.
- When `response_schema` is set and the model produces output that successfully parses as JSON but
  fails to validate against `response_schema`, OR fails to parse as JSON at all, `complete()`
  raises `structured_output_invalid` (§7).
- `complete()` MUST validate `tool_choice` against `tools` before sending. The validation rules:
  1. `tool_choice="required"` requires `tools` non-empty.
  2. `tool_choice={type: "tool", name: X}` requires `tools` non-empty AND X to be a `Tool.name`
     in the supplied list.
  3. `tool_choice="auto"` and `tool_choice="none"` have no `tools`-related preconditions.

  Violations of rules 1–2 raise `provider_invalid_request` (§7) at pre-send validation, before
  the implementation contacts the provider.

When `tool_choice="none"` is supplied AND the provider returns tool calls anyway, the
implementation MUST surface what the provider returned (per the §6 transparency principle)
without re-validating against the constraint post-hoc. The constraint is a request-side hint
the implementation passes to the wire; whether the model honored it is observable via the
returned `finish_reason` (`"tool_calls"` means the model called tools regardless of the
`"none"` hint) but is not enforced by the framework. Providers vary in whether they honor
`"none"` strictly; provider compliance is a provider-quality concern, not a framework-policed
contract.

## 6. Response and configuration

A `Response` record:

| Field | Description |
|---|---|
| `message` | The assistant message returned by the model. Always `role: "assistant"`. May carry `tool_calls`. When the bound provider's §8.X mapping surfaces provider-emitted reasoning content, `message.content` is a content-block sequence that MAY include `ThinkingBlock` / `RedactedThinkingBlock` entries (per §3.1.4 / §3.1.5); mappings that do not surface reasoning content return text-only content. |
| `finish_reason` | One of `"stop"`, `"length"`, `"tool_calls"`, `"content_filter"`, `"error"`. See below. |
| `usage` | A record `{prompt_tokens, completion_tokens, total_tokens}`. Each field is a non-negative integer or `null`. If the provider does not report usage, all three MUST be `null`. |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Carries everything the provider returned — including fields the spec does not normalize (logprobs, content-filter details, provider-specific extensions). The normalized fields above are derived from `raw`; the two views MUST be consistent (modifying one does not affect the other, since both are immutable from the caller's perspective). |
| `parsed` | The parsed and validated structured value when the call supplied a `response_schema` and the model returned structured content. The value conforms to the supplied `response_schema`. Absent (`null` / `None` / `undefined`, per the language's idiom) on calls that did not supply a `response_schema`, and on responses whose `finish_reason` is `"tool_calls"` (regardless of whether `message.content` is also populated, per the §3 assistant-message contract). |

`finish_reason` semantics:

- `stop` — the model produced a complete response and stopped naturally.
- `length` — the model hit `max_tokens` (or the equivalent provider budget).
- `tool_calls` — the model returned tool calls and is awaiting their results.
- `content_filter` — the provider's content filter blocked or truncated the response.
- `error` — the provider reported an internal error mid-stream and could not return a complete
  response. This is distinct from a `complete()` exception (which signals a request-level failure
  per §7); `finish_reason: "error"` signals a degraded but parseable response. The response MAY
  carry `tool_calls`, possibly with malformed `arguments`; see §3 "Validation under
  `finish_reason: \"error\"`" for handling.

`parsed` semantics. The `parsed` field is the language-idiomatic deserialized form of the
structured value (e.g., a Python `dict[str, Any]` populated per the JSON Schema, or a TypeScript
`unknown` typed at the call site via a generic). Implementations MAY offer ergonomic typed
accessors on top (e.g., Python users supplying a Pydantic model class instead of a raw JSON
Schema and receiving a validated model instance, surfaced via per-language overloads or generics
so that the static type of `parsed` reflects the supplied schema) — those are per-language
ergonomics, not normative spec.

`message.content` carries the provider's content string preserved verbatim — the bytes the model
returned, UTF-8 decoded. Implementations MUST NOT re-serialize `parsed` back into
`message.content`; doing so would mask formatting differences (whitespace, key ordering, number
representation) and break conformance assertions that rely on byte-level equivalence. `parsed`
and `message.content` MUST be consistent in the following sense: deserializing `message.content`
as JSON and validating against `response_schema` produces `parsed`. The reverse operation
(serializing `parsed` and comparing) is NOT required to round-trip bytewise, because the model's
serialization may differ from the framework's.

When `finish_reason: "tool_calls"`, `parsed` is absent regardless of whether `response_schema`
was supplied. The tool-call path and the structured-content path are mutually exclusive at the
response level.

A `RuntimeConfig` record:

| Field | Description |
|---|---|
| `temperature` | Float, optional. Provider-specific range; commonly `[0.0, 2.0]`. |
| `max_tokens` | Int, optional. Maximum completion tokens. |
| `top_p` | Float, optional. Nucleus sampling probability. |
| `seed` | Int, optional. Best-effort determinism for providers that support it. Setting `seed` does NOT guarantee determinism; see §9. |
| `frequency_penalty` | Float, optional. Penalty on token frequency; commonly `[-2.0, 2.0]` per the OpenAI reference. Cross-vendor: OpenAI, Mistral, Cohere, and most OpenAI-compatible servers accept this name directly; Anthropic and Gemini map to vendor-specific equivalents at the wire layer. |
| `presence_penalty` | Float, optional. Penalty on token presence; commonly `[-2.0, 2.0]`. Same cross-vendor framing as `frequency_penalty`. |
| `stop_sequences` | List of strings, optional. Stop sequences. When any string in the list appears in the generated text, generation halts. The OA declared name matches the OpenTelemetry GenAI semconv (`gen_ai.request.stop_sequences`) and the wire-key convention used by most cross-vendor providers (Anthropic uses `stop_sequences`, Gemini uses `stopSequences`). The OpenAI-compatible wire mapping (§8.1) translates this field to OpenAI's request-body key `stop`. Per-provider limits MAY differ (OpenAI accepts up to four; others vary) and are enforced at the wire layer by the provider, not by the framework. |

**Extras pass-through.** `RuntimeConfig` is extensible. Implementations MUST accept fields beyond
the declared set above without erroring at the API boundary; undeclared fields MUST be preserved
on the config record and forwarded to the wire request body untouched, subject to the wire-format
mapping (§8). The pass-through MUST NOT translate, rename, or otherwise transform undeclared
fields. A caller passing `repetition_penalty=1.05` MUST see `repetition_penalty: 1.05` in the wire
body under whatever placement the wire-format mapping defines (e.g., §8.1's OpenAI-compatible
mapping places undeclared keys at the request-body root). Undeclared fields are NOT validated by
the spec; the provider's backend is the source of truth on what extra parameters it recognizes.

**Null-skip semantics.** A declared `RuntimeConfig` field with a value of `None` (Python `None`,
TypeScript `undefined`, the language's equivalent "unset" sentinel) MUST be omitted from the wire
request body. Such a value denotes "field not supplied for this call," distinct from "field
supplied with an explicit null value." Implementations MUST NOT serialize `None`-valued declared
fields as JSON `null` in the wire body. The null-skip rule applies to declared fields only;
undeclared fields supplied to `RuntimeConfig` are forwarded per the extras-pass-through contract
above (the implementation's wire-format mapping determines whether an undeclared-field `None`
appears as `null` in the request body or is omitted — implementation-defined, since the spec does
not constrain undeclared-field types).

## 7. Error semantics

A provider call (`ready()` or `complete()`) may raise one of the following canonical category errors:

- `provider_authentication` — auth failed (invalid key, expired token, missing credentials).
- `provider_unavailable` — provider is unreachable (network failure, 5xx error, connection timeout,
  DNS failure).
- `provider_invalid_model` — the bound model does not exist on this provider (unknown to the
  provider's model catalog). Terminal: retry will not succeed without changing the bound model.
- `provider_model_not_loaded` — the bound model is known to the provider but is not currently
  serving requests (e.g., a local vLLM, LM Studio, or llama.cpp server has the model configured
  but has not yet loaded it into memory, or has unloaded it under memory pressure). Distinct from
  `provider_invalid_model` because retry MAY succeed once loading completes; warmup-polling
  callers SHOULD treat this as a transient signal.
- `provider_rate_limit` — provider returned a rate-limit response (e.g., HTTP 429). Implementations
  SHOULD expose a `retry_after` accessor when the provider supplies one (e.g., `Retry-After` header).
- `provider_invalid_response` — provider returned a malformed response that cannot be parsed into
  the §6 shape (missing required fields, invalid `tool_calls` structure, invalid JSON).
- `provider_invalid_request` — the request was malformed before sending (per-role message
  constraints violated, `tool_call_id` does not match an earlier `assistant` tool call, duplicate
  tool names, etc.). This category is raised by the implementation's pre-send validation. The
  `tool_choice` parameter (§5) adds three validation failure modes routed through this category:
  (1) `tool_choice="required"` supplied with empty / absent `tools`; (2) `tool_choice={type: "tool",
  name: X}` supplied with empty / absent `tools`; (3) `tool_choice={type: "tool", name: X}`
  supplied with X not in the supplied `tools` list. Each MUST raise `provider_invalid_request`
  at pre-send validation, before the implementation contacts the provider.
- `provider_unsupported_content_block` — the bound model does not support a content block type
  used in the request (e.g., a text-only model received an image block, or the model supports
  images but not the requested `media_type` (per §3.1.2) or `source` variant (per §3.1.3)).
  Raised by the implementation's pre-send validation when the unsupported case is statically
  known (per the provider's documented capabilities), or by the post-receive error mapping
  when the provider itself rejects the request.
- `structured_output_invalid` — `complete()` was called with a `response_schema` (§5), and the
  provider returned content that could not be parsed as JSON OR did not validate against the
  supplied schema. The error MUST expose the requested `response_schema`, the raw response
  content (the bytes the model produced), and a description of the validation or parse failure
  (the wrapped exception's message, the failing JSON Pointer, or the language's idiomatic
  equivalent). Non-transient by default — a model that fails to produce schema-compliant output
  on a given prompt usually fails the same way on retry. Users wanting retry-on-validation-failure
  semantics MAY include `structured_output_invalid` in a pipeline-utilities `RetryMiddleware`
  classifier's transient set, but the category is NOT transient by default at the spec level.
  Distinct from `provider_invalid_response` (which covers wire-shape malformation, not content
  validation against the caller's schema).

Each error MUST expose a `category` identifier (matching the strings above, as an error class, error
code, or tagged discriminant per the language's idiom). Provider-originated errors SHOULD preserve
the underlying provider exception as cause (`__cause__` in Python, `cause` in TypeScript).

These nine categories are the minimum required surface. Implementations MAY raise additional
provider-specific categories for cases not covered above; users MAY catch by category to implement
retry policy.

**Retry classification.** The categories `provider_unavailable`, `provider_rate_limit`,
`provider_model_not_loaded`, and `finish_reason: "error"` are *transient* — a retry MAY succeed.
The categories `provider_authentication`, `provider_invalid_model`, `provider_invalid_request`,
`provider_invalid_response`, `provider_unsupported_content_block`, and `structured_output_invalid`
are *non-transient* — retrying without changing the request will not succeed.

## 8. Wire-format mappings

The §5 Provider interface, §3 message shape, §4 Tool definition, §6 Response and configuration,
and §7 error semantics are the normative cross-provider contract. Any provider implementation
conforming to those sections satisfies the abstract spec, regardless of the underlying HTTP / RPC
/ SDK wire format used to reach the model.

This section catalogs concrete wire-format mappings for specific provider protocols. Each mapping
specifies how the abstract §3 / §4 / §6 records translate to that provider's wire shape and how
the provider's responses / errors map back to §3 / §6 / §7. §8.1 describes the OpenAI-compatible
Chat Completions mapping, which is the broadest-compatibility option (the OpenAI hosted API,
vLLM, LM Studio, llama.cpp server, and many other local servers all speak it). Future
subsections (§8.2, §8.3, …) are reserved for provider-native formats whose shape diverges from
the OpenAI mapping — Anthropic Messages API, Google Gemini, Mistral, etc. Each lands via its
own follow-on proposal.

**Default placement rule.** Any provider wire-format mapping intended for implementation across
multiple OA language implementations (Python, TypeScript, …) MUST be specified in this section.
The cross-language behavioral consistency that §3 / §5 / §7 provide for the abstract Provider
interface extends to wire-format mappings whenever the same provider is targeted from multiple
languages — without a shared spec, sibling packages like `openarmature-anthropic` (Python) and
`openarmature-anthropic` (TypeScript) would diverge in subtle wire shape and break the
cross-language promise.

**Out-of-tree mappings.** Wire-format mappings NOT specified here remain valid but make NO
cross-impl behavioral guarantee. Out-of-tree is appropriate for: (a) genuinely single-language
specialty providers (a vendor-specific mapping with no anticipated TypeScript sibling),
(b) vendor extensions that explicitly opt out of cross-impl consistency, or (c) experimental
mappings still finding their shape before promotion to in-spec status. In all other cases the
in-spec default applies.

**Compliance label.** Provider implementations MAY opt into a mapping's compliance label
(e.g., "OpenAI-compatible", "Anthropic Messages") only if they implement that mapping exactly
per the §8.X subsection. A provider MAY implement multiple mappings (e.g., one implementation
routing OpenAI-compatible requests through one path and Anthropic-native requests through
another) and claim the corresponding labels independently.

**Per-mapping subsection structure.** Each §8.X subsection SHOULD follow the canonical
structure used by §8.1:

| Subsection | Topic |
|---|---|
| §8.X.1 | Request mapping |
| §8.X.2 | Response mapping |
| §8.X.3 | Error mapping |
| §8.X.4 | Concurrency |
| §8.X.5 | Structured output |

Provider-specific sub-subsections (e.g., §8.X.1.1 for content-block wire mapping per §8.1.1.1,
§8.X.5.1 for prompt-augmentation fallback per §8.1.5.1) are permitted and expected. Providers
whose wire shapes have features without §8.1 analogues MAY add additional top-level subsections
at the end of the recommended five (e.g., §8.X.6 *Caching* if the provider exposes a caching
primitive worth spec'ing); the recommended five SHOULD precede any provider-specific additions,
in the order shown.

The recommendation is SHOULD-level rather than MUST-level because some providers' shapes
diverge from §8.1's organization in ways the template cannot accommodate by sub-subsection
alone. When a §8.X proposal diverges from this template, the proposal text SHOULD explain the
divergence in its *Detailed design* section so reviewers can confirm the divergence is
structural rather than ergonomic.

### 8.1 OpenAI-compatible mapping

The OpenAI Chat Completions API (`POST /v1/chat/completions`) is the de facto standard for local
LLM servers (vLLM, LM Studio, llama.cpp) as well as the OpenAI hosted API itself.

#### 8.1.1 Request mapping

The §3 message list maps onto the OpenAI `messages` field:

| Spec role | OpenAI role | Notes |
|---|---|---|
| `system` | `system` | Direct mapping. |
| `user` | `user` | When `content` is a string, maps directly. When `content` is a content-block sequence (§3.1), maps to OpenAI's content-array form per §8.1.1.1. |
| `assistant` (no tool calls) | `assistant` | `content` becomes OpenAI's `content`. |
| `assistant` (with tool calls) | `assistant` | `content` becomes OpenAI's `content` (may be `null` per OpenAI's schema if empty). `tool_calls` becomes OpenAI's `tool_calls` array. |
| `tool` | `tool` | `content` becomes OpenAI's `content`. `tool_call_id` becomes OpenAI's `tool_call_id`. |

A spec `ToolCall` `{id, name, arguments}` maps to an OpenAI tool call entry as:
```
{
  "id": <id>,
  "type": "function",
  "function": {
    "name": <name>,
    "arguments": <JSON-serialized arguments>
  }
}
```

The spec stores `arguments` as a deserialized mapping; the wire format requires a JSON-encoded
string. Implementations MUST serialize on send and deserialize on receive.

A §4 `Tool` `{name, description, parameters}` maps to an OpenAI `tools` entry as:
```
{
  "type": "function",
  "function": {
    "name": <name>,
    "description": <description>,
    "parameters": <parameters>
  }
}
```

The §6 `RuntimeConfig` declared fields map to the OpenAI request body as follows:

- `temperature`, `max_tokens`, `top_p`, `seed`, `frequency_penalty`, `presence_penalty` — map
  directly (same name on the OpenAI request body).
- `stop_sequences` — renamed to OpenAI body field `stop`. The OA declared name follows the
  cross-vendor OpenTelemetry GenAI semconv (`gen_ai.request.stop_sequences`) and matches the
  wire-key convention used by Anthropic / Gemini / Cohere; OpenAI is the outlier with the shorter
  `stop` name. The wire mapping translates `RuntimeConfig.stop_sequences` to OpenAI's `stop`
  field on emission. Implementations of the OpenAI-compatible mapping MUST perform this rename;
  emitting `stop_sequences` directly to the OpenAI request body would not be recognized by
  OpenAI's server.

The bound model identifier becomes OpenAI's `model` field.

**Undeclared `RuntimeConfig` fields** (those a caller supplies beyond the declared set, per §6's
extras-pass-through contract) appear at the OpenAI request-body root, as siblings to
`temperature`, `model`, etc. This codifies the behavior every existing OpenAI-compatible adopter
relies on (e.g., the OpenAI Python SDK's `extra_body=` parameter; LangChain's wrapper splatting
kwargs into the body; gateways like Bifrost passing straight through to vLLM). The pass-through
MUST preserve key names and value types verbatim per §6's extras-pass-through contract; the §8.1
mapping does NOT validate, rename, or transform undeclared keys.

The §5 `tool_choice` parameter maps to OpenAI's `tool_choice` request-body field:

| Spec `tool_choice` | OpenAI wire body |
|---|---|
| `None` / absent | (field omitted from request body) |
| `"auto"` | `tool_choice: "auto"` |
| `"required"` | `tool_choice: "required"` |
| `"none"` | `tool_choice: "none"` |
| `{type: "tool", name: X}` | `tool_choice: {type: "function", function: {name: X}}` |

The `None`-omitted-from-wire row is load-bearing for backward compatibility: existing callers
who never supply `tool_choice` see no wire-shape change, and the OpenAI provider's own default
(which itself depends on whether `tools` is non-empty) applies unchanged. The spec `type: "tool"`
discriminator renames OpenAI's `type: "function"` for spec-layer readability; the implementation
performs the rename when constructing the wire body.

**Thinking-block strip-on-send.** OpenAI Chat Completions does not surface reasoning tokens and
has no wire representation for `ThinkingBlock` / `RedactedThinkingBlock` (§3.1.4 / §3.1.5). When
an `assistant` message in the request carries thinking or redacted-thinking blocks — e.g.,
because the caller is replaying conversation history that originated from a different §8.X-mapped
provider — the §8.1 mapping MUST strip those blocks before emitting the OpenAI wire request.
Stripping is deterministic and raises no error; it preserves the spec's content-block superset
across cross-provider conversation round-trips (a conversation that accrued thinking blocks under
one provider can be routed through an OpenAI-compatible provider without manual filtering). The
remaining text-block content emits normally. The §8.1 mapping MUST NOT emit thinking blocks on
inbound responses (OpenAI does not produce them). This strip-on-send rule generalizes to any
provider mapping that does not surface reasoning content; reasoning-block signatures are
provider-bound (per §3.1.4) and are never forwarded to a provider that did not issue them.

##### 8.1.1.1 Content-block wire mapping

Each spec content block maps to one OpenAI content-array entry:

| Spec block | OpenAI entry |
|---|---|
| `TextBlock { text }` | `{ "type": "text", "text": <text> }` |
| `ImageBlock` with `source: url { url }` | `{ "type": "image_url", "image_url": { "url": <url> } }`. The `detail` hint, when set on the spec block, becomes `image_url.detail`. |
| `ImageBlock { media_type, source: inline { base64_data } }` | `{ "type": "image_url", "image_url": { "url": "data:<media_type>;base64,<base64_data>" } }`. OpenAI's inline-image path goes through the same `image_url` entry shape with a `data:` URL; implementations MUST construct the data URI per RFC 2397, reading `media_type` from the ImageBlock and `base64_data` from its inline source. The `detail` hint, when set, becomes `image_url.detail`. |

Empty content blocks (e.g., a text block with empty `text`, or an image block with both
sources absent) are spec-invalid and MUST be rejected at pre-send validation per §3 /
`provider_invalid_request`. The wire never sees them.

OpenAI uses the same `image_url` content-entry shape for both URL-referenced and base64-inline
images (with the inline case expressed as a `data:` URL). Anthropic and Google use different
wire shapes; their own §8-style mapping sections (§8.2 Anthropic; future proposals for others)
define their own block→wire mappings without disrupting this one.

#### 8.1.2 Response mapping

A successful OpenAI response maps onto a §6 `Response` as follows:

- `message` — built from `choices[0].message` (assuming a single-choice request, which is the only
  shape v1 supports).
- `finish_reason` — `choices[0].finish_reason`. OpenAI's values are `stop`, `length`, `tool_calls`,
  `content_filter`, and `function_call` (legacy). Map `function_call` to `tool_calls`. Map any
  unknown `finish_reason` to `error`.
- `usage` — built from the response's `usage` field. If `usage` is absent, all three usage subfields
  MUST be `null`.
- `raw` — the parsed JSON body of the OpenAI response, verbatim. Implementations MUST NOT redact,
  rewrite, or omit fields. Provider-specific extensions surface here unchanged (e.g.,
  `choices[0].logprobs`, vLLM's `prompt_logprobs`, LM Studio's runtime stats).

#### 8.1.3 Error mapping

| OpenAI condition | Spec category |
|---|---|
| HTTP 401, 403 | `provider_authentication` |
| HTTP 404 with model-not-found body | `provider_invalid_model` |
| HTTP 503 with model-loading body | `provider_model_not_loaded` |
| HTTP 429 | `provider_rate_limit` |
| HTTP 5xx (other), connection error, timeout | `provider_unavailable` |
| HTTP 400 with body indicating the bound model rejected a content block (e.g., image/audio/media-type rejection, unsupported `source` variant) | `provider_unsupported_content_block` |
| HTTP 400 (malformed request, schema violation) | `provider_invalid_request` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

#### 8.1.4 Concurrency

OpenAI-compatible servers vary in concurrency support — local servers may serialize internally,
hosted APIs do not. Implementations MUST NOT add a serialization layer; concurrent `complete()` calls
go to the wire concurrently. Providers that benefit from client-side concurrency limits use the
pipeline-utilities rate limiter or middleware, not this layer.

#### 8.1.5 Structured output

When `complete()` is called with a `response_schema`, the OpenAI-compatible request body includes
a `response_format` field:

```
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "<implementation-derived identifier>",
      "schema": <response_schema verbatim>,
      "strict": true
    }
  }
}
```

The `name` field is required by OpenAI but does not affect output semantics; implementations
SHOULD derive a stable identifier from the schema (e.g., a hash, or the schema's `title` field
when present). The `strict: true` flag enables OpenAI's schema-constrained decoding path;
implementations SHOULD pass `strict: true` when the supplied schema satisfies the strict-mode
constraints (no `additionalProperties: true`, all properties listed in `required`, etc.), and
SHOULD fall back to `strict: false` when the schema does not satisfy the constraints. The
behavioral contract at the spec layer is identical regardless of `strict`: validation happens
post-receive against `response_schema`; failures raise `structured_output_invalid` (§7).

When `complete()` is called without `response_schema` (or with `response_schema=None`), the
request body MUST NOT include `response_format`. The v0.4.0 wire shape is preserved unchanged
for free-form calls.

##### 8.1.5.1 Fallback for providers without native structured output

OpenAI-compatible servers that do not implement `response_format` (older vLLM versions, some
LM Studio releases, some local-server wrappers) raise an error or silently ignore the field.
Implementations SHOULD detect this — either statically (via provider capability metadata) or
dynamically (a first-call attempt that returns an error) — and fall back to a prompt-augmentation
strategy:

1. Construct a modified copy of the message list with a system directive appended (or with the
   existing system message's content extended) instructing the model to return only valid JSON
   matching the `response_schema`. The directive SHOULD include the schema serialized as part
   of the prompt. The caller's original `messages` list MUST be left unchanged — the §5
   mutation rule applies to fallback paths the same as native paths.
2. Issue the underlying request without `response_format`.
3. Parse and validate the response content against `response_schema` per §6 `parsed`.
4. On validation failure, raise `structured_output_invalid` per §7.

Fallback behavior is implementation-defined. Implementations MUST document whether `complete()`
with `response_schema` uses native `response_format` or prompt-augmentation, and SHOULD expose
a way for callers to inspect or override the path chosen.

##### 8.1.5.2 Response mapping

When the response carries structured content (not tool calls):

- `message.content` is the response body's content string, verbatim.
- `parsed` is the deserialization of `message.content` against `response_schema`.
- `finish_reason` is mapped per §8.1.2 (typically `"stop"`).

When the response carries tool calls instead, the mapping follows §8.1.2 unchanged: `parsed` is
absent, `tool_calls` is populated, `finish_reason` is `"tool_calls"`.

### 8.2 Anthropic Messages mapping

The Anthropic Messages API (`POST /v1/messages`) is the provider-native protocol for Anthropic's
Claude model family. Its wire shape diverges from §8.1's OpenAI-compatible mapping: `system` is a
top-level request field rather than a message role; tool calls and tool results are content
blocks (not a separate `tool_calls` field and `tool` role); `tool_choice` has a different shape;
`max_tokens` is required; the tool definition uses `input_schema`; and extended-thinking models
emit reasoning content blocks that are round-trip-load-bearing for multi-turn correctness.

#### 8.2.1 Request mapping

**System extraction.** Spec messages with `role: "system"` are removed from the message list and
their text content is concatenated into Anthropic's top-level `system` request field
(joined with `\n\n` when more than one system message is present, preserving order). The
`messages` array sent to Anthropic contains only `user` and `assistant` entries.
Implementations MUST reject (`provider_invalid_request`) any system message containing non-text
content.

**Message body shape.** Each remaining spec message maps to one Anthropic message:

| Spec role | Anthropic role | Notes |
|---|---|---|
| `user` | `user` | String `content` maps directly; a content-block sequence maps per §8.2.1.1. |
| `assistant` (no tool calls, no thinking) | `assistant` | `content` becomes Anthropic's `content`. |
| `assistant` (with tool calls and/or thinking) | `assistant` | Tool calls become `tool_use` content blocks; thinking / redacted-thinking blocks pass through. See §8.2.1.1. |
| `tool` | (no direct Anthropic role) | Maps via §8.2.1.2 to an Anthropic `user` message containing `tool_result` content blocks. |

**Tool definitions.** A §4 `Tool` `{name, description, parameters}` maps to an Anthropic `tools`
entry as `{name, description, input_schema}` — note `input_schema`, not `parameters`; the JSON
Schema passes through verbatim under the renamed key.

**`tool_choice` mapping.** The §5 `tool_choice` maps to Anthropic's `tool_choice` field:

| Spec `tool_choice` | Anthropic wire body |
|---|---|
| `None` / absent | (field omitted) |
| `"auto"` | `{"type": "auto"}` |
| `"required"` | `{"type": "any"}` |
| `"none"` | `{"type": "none"}` |
| `{type: "tool", name: X}` | `{"type": "tool", "name": X}` |

The `"required"` → `"any"` rename is the load-bearing translation (the spec's cross-vendor name
maps to Anthropic's wire name for the same semantic). Anthropic's optional
`disable_parallel_tool_use` field, when a caller needs it, is supplied via the extras-pass-through
path.

**RuntimeConfig field mapping.** The §6 `RuntimeConfig` declared fields map to the Anthropic
request body:

- `temperature`, `top_p`, `seed`, `stop_sequences` map directly (`stop_sequences` matches
  Anthropic's wire-key convention exactly — no rename).
- `max_tokens` maps directly. Anthropic requires this field on every request; if
  `RuntimeConfig.max_tokens` is `None` or absent, implementations MUST reject at pre-send
  validation (`provider_invalid_request`) identifying `max_tokens` as required by this mapping.
  The mapping MUST NOT default to a magic value.
- `frequency_penalty`, `presence_penalty` — Anthropic does NOT support these. If supplied
  (non-`None`), implementations MUST raise `provider_invalid_request` at pre-send validation
  identifying the unsupported field. Quiet drop is forbidden.

The bound model identifier becomes Anthropic's `model` field. Undeclared `RuntimeConfig` fields
appear at the request-body root per §6's extras-pass-through contract; the mapping does NOT
validate, rename, or transform them.

##### 8.2.1.1 Content-block wire mapping

This sub-subsection covers two wire-encoding paths. Spec content blocks (per §3.1) in message
`content` map to Anthropic content entries per the table. Spec `ToolCall` records in the
`assistant` message's top-level `tool_calls` field (per §3) are NOT §3 content blocks — the
mapping extracts them and serializes them as Anthropic `tool_use` wire entries (and parses
inbound `tool_use` entries back into `Response.message.tool_calls`).

| Spec source | Anthropic wire entry |
|---|---|
| `TextBlock { text }` (content block) | `{ "type": "text", "text": <text> }` |
| `ImageBlock` with `source: url { url }` (content block; user-only) | `{ "type": "image", "source": { "type": "url", "url": <url> } }`. The `detail` hint is dropped — Anthropic does not honor it. |
| `ImageBlock { media_type, source: inline { base64_data } }` (content block; user-only) | `{ "type": "image", "source": { "type": "base64", "media_type": <media_type>, "data": <base64_data> } }`. The `detail` hint is dropped. |
| `ToolCall { id, name, arguments }` from `tool_calls` field (extracted at wire) | `{ "type": "tool_use", "id": <id>, "name": <name>, "input": <arguments> }`. `arguments` is the deserialized mapping; Anthropic accepts an object directly under `input` (no JSON-string serialization, unlike §8.1.1). |
| `ThinkingBlock { text, signature }` (content block; assistant-only) | `{ "type": "thinking", "thinking": <text>, "signature": <signature> }`. The signature passes through verbatim in both directions. |
| `RedactedThinkingBlock { data }` (content block; assistant-only) | `{ "type": "redacted_thinking", "data": <data> }`. The data blob passes through verbatim in both directions. |

Empty content blocks are spec-invalid and MUST be rejected at pre-send validation per §3 /
`provider_invalid_request`.

##### 8.2.1.2 `tool` role bidirectional translation

Spec `tool` messages (§3) do not map to any Anthropic role. The mapping translates
bidirectionally.

**Spec → Anthropic (on send):** each consecutive run of spec `tool` messages collapses into a
single Anthropic `user` message whose content is an array of `tool_result` blocks — one per
spec `tool` message, preserving order: `{ "type": "tool_result", "tool_use_id":
<tool_call_id>, "content": <content> }`. The collapse is required because Anthropic forbids
consecutive messages of the same role; the user message carrying the tool results follows the
assistant's prior `tool_use` blocks. Anthropic's optional `is_error` field on a `tool_result`
is supplied via the extras path when a caller signals tool failure.

**Anthropic → Spec (on receive):** the user message's content blocks are walked in order. Each
`tool_result` block maps to one spec `tool` message (`tool_call_id` ← `tool_use_id`, content ←
the block's `content`); each maximal run of non-`tool_result` blocks maps to one spec `user`
message carrying those blocks. The walk preserves the original block order across the emitted
spec messages.

The send-side collapse (above) only ever produces `user` messages whose content is entirely
`tool_result` blocks, so a conversation OA itself produced round-trips exactly. For an
externally-authored Anthropic `user` message that interleaves `tool_result` blocks with other
content, the receive split preserves block order and the tool-call/tool-result pairing but
re-segments the interleaved message into multiple spec `user` / `tool` messages (one per
maximal run); a subsequent send re-collapses consecutive `tool` messages per the send rule.
Content and order are preserved; the exact message-boundary segmentation MAY differ from the
original wire shape.

#### 8.2.2 Response mapping

A successful Anthropic response maps onto a §6 `Response`:

- `message` — built from the response's `role: "assistant"` and `content` array. Anthropic
  `text` / `thinking` / `redacted_thinking` entries map to spec `TextBlock` / `ThinkingBlock` /
  `RedactedThinkingBlock` content blocks (per §8.2.1.1), preserving their relative order on
  `Message.content`. Anthropic `tool_use` entries are NOT content blocks — per §3, `ToolCall`
  is the top-level `message.tool_calls` field, not a §3.1 content-block type — so they are
  extracted to `Response.message.tool_calls` (next bullet) and do NOT appear on
  `Message.content`.
- `tool_calls` — the `tool_use` entries from the content array, extracted in wire order onto
  `Response.message.tool_calls` as spec `ToolCall` records (mirroring §8.1's flatter shape so
  callers see tool calls in the same place regardless of provider). Order within the
  `tool_calls` list follows the order the `tool_use` entries appeared in the Anthropic response.
- `finish_reason` — derived from Anthropic's `stop_reason`:

  | Anthropic `stop_reason` | Spec `finish_reason` |
  |---|---|
  | `end_turn` | `"stop"` |
  | `max_tokens` | `"length"` |
  | `stop_sequence` | `"stop"` (the matched sequence is preserved in `Response.raw.stop_sequence`) |
  | `tool_use` | `"tool_calls"` |
  | `pause_turn` | `"stop"` (a long-running turn the provider paused; the caller MAY continue by passing the response back — the pause is preserved in `Response.raw.stop_reason`) |
  | `refusal` | `"content_filter"` (the refusal category, when present, is preserved in `Response.raw.stop_details`) |
  | (unknown) | `"error"` |

- `usage` — `usage.prompt_tokens` ← `input_tokens`, `usage.completion_tokens` ← `output_tokens`,
  `usage.total_tokens` ← the sum of those two (or `null` per §6's rules). **Cache-token note:**
  Anthropic's `input_tokens` counts only non-cached input; `cache_creation_input_tokens` and
  `cache_read_input_tokens` report cached input separately, and Anthropic's own total-input
  accounting is `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. The spec
  `usage.prompt_tokens` maps from `input_tokens` alone; the cache subfields surface in
  `Response.raw.usage` and are NOT promoted to the spec `usage` record.
- `raw` — the parsed JSON response body, verbatim. Anthropic-specific fields (response `id`,
  the `model` used, cache token counts, `stop_details`) surface here unchanged.

#### 8.2.3 Error mapping

The error envelope is `{"type": "error", "error": {"type": <error_type>, "message": <string>},
"request_id": <string>}`.

| Anthropic condition | Spec category |
|---|---|
| HTTP 401 `authentication_error` | `provider_authentication` |
| HTTP 402 `billing_error` | `provider_authentication` (account-level access failure; the specific type appears in `Response.raw`) |
| HTTP 403 `permission_error` | `provider_authentication` |
| HTTP 404 `not_found_error` (model-not-found body) | `provider_invalid_model` |
| HTTP 413 `request_too_large` | `provider_invalid_request` |
| HTTP 429 `rate_limit_error` | `provider_rate_limit` |
| HTTP 500 `api_error` | `provider_unavailable` |
| HTTP 504 `timeout_error` | `provider_unavailable` |
| HTTP 529 `overloaded_error` | `provider_unavailable` |
| HTTP 5xx (other), connection error, client timeout | `provider_unavailable` |
| HTTP 400 with body indicating the model rejected a content block (image / media-type / unsupported source) | `provider_unsupported_content_block` |
| HTTP 400 `invalid_request_error` (other malformed-request causes) | `provider_invalid_request` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

Anthropic's `error.type` and `request_id` surface in `Response.raw` for finer-grained handling.

#### 8.2.4 Concurrency

Matches §8.1.4. Anthropic's hosted API supports concurrent requests; implementations MUST NOT
add a serialization layer. Client-side rate-limit needs use the pipeline-utilities rate limiter
or middleware, not this layer.

#### 8.2.5 Structured output

The Anthropic Messages API provides native structured output (generally available on current
Claude models) via the top-level `output_config.format` request field.

**Native: `output_config.format`.** When `complete()` is called with a `response_schema`, the
mapping sets:

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

The `type: "json_schema"` discriminator is required; the GA path requires no beta header.
Anthropic's constrained decoding guarantees the generated output conforms to the schema. The
structured JSON is returned as the assistant message's text content; the mapping parses it into
`Response.parsed` and validates against `response_schema` per §6. On validation failure raise
`structured_output_invalid` (§7).

Two non-conformance cases are inherent to the provider and are NOT validation bugs: a
`stop_reason: "refusal"` (the refusal takes precedence, so output may not match the schema) and
a `stop_reason: "max_tokens"` (truncation). In both cases the mapping surfaces the
non-conforming content and the mapped `finish_reason` (`content_filter` / `length`) per §6 / §7;
implementations MUST NOT silently coerce these into a schema-conforming shape.

When `complete()` is called without a `response_schema`, the request MUST NOT include
`output_config`; the free-form wire shape is preserved.

(Anthropic's complementary strict-tool-use feature — `strict: true` on a tool definition —
guarantees tool-call *argument* conformance, not *response* shape; it is a tool-parameter
feature reachable via the tool-definition extras path, not part of this structured-output
mapping.)

##### 8.2.5.1 Fallback for models without native structured output

Claude models predating native `output_config.format` support fall back to a pre-native pattern.
Implementations SHOULD prefer tool-call coercion (stronger conformance) and MUST document which
path a given call uses.

**Tool-call coercion** (preferred fallback). When the caller's `tools` list is empty or absent,
construct a synthetic tool whose `input_schema` is the `response_schema`, add it to `tools`, and
set `tool_choice` to `{"type": "tool", "name": <synthetic name>}`. The response's
`tool_use.input` for the synthetic tool becomes `Response.parsed`. Unavailable when the caller
already supplies tools (the synthetic tool would override the caller's tool intent).

**Prompt-augmentation** (last-resort fallback). Per §8.1.5.1: append a schema directive to the
`system` field (or message list), issue the request otherwise unmodified, parse and validate the
text response against `response_schema`, raise `structured_output_invalid` on failure. The
caller's original `messages` MUST be left unchanged.

## 9. Determinism

LLM completions are not deterministic by default. Even with `temperature=0` and a fixed `seed`,
identical inputs MAY produce different outputs across calls or across deployments of the same
provider (different model weight versions, different infrastructure, different sampling
implementations).

The spec therefore makes no determinism guarantees for `complete()`. The conformance suite uses
**mock providers** that return canned responses; live-provider tests are out of scope.

For `ready()`: implementations MUST return successfully when the provider is reachable and the
model exists, and raise the appropriate §7 category otherwise. This is testable deterministically
against a mock or stub HTTP server.

## 10. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Streaming responses** — incremental delivery of assistant content and tool calls.
- **Multi-modal audio and video** — audio and video inputs and outputs. Image inputs are
  covered by §3.1 (per proposal 0015). Audio and video each warrant their own proposal —
  formats, codecs, inline-vs-URL semantics, and provider wire mappings differ enough that
  one proposal per modality is the right scope.
- **Image outputs** — assistant-message-borne images (e.g., DALL-E-style image generation).
  v1 image support is user-input-only; assistant-output image content would need a separate
  proposal and is not common in tool-using agent workloads.
- **Token counting before the call** — tokenizer access for budget-aware prompt assembly.
- **Provider-native wire formats** — Anthropic Messages, Google Vertex, AWS Bedrock. Each adds a new
  §8-style mapping section to this spec via a follow-on proposal.
- **Agent loop** — tool-call-then-respond loops live in graph-engine nodes or a future agent-runner
  capability.
- **Retry and rate-limit policy** — pipeline-utilities concern.
- **Prompt template rendering** — prompt-management capability (charter §4.5).
- **Embeddings** — separate API surface; separate capability if/when needed.
