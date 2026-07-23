# LLM Provider

Canonical behavioral specification for the OpenArmature LLM provider abstraction.

- **Capability:** llm-provider
- **Introduced:** spec version 0.4.0

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
| `signature` | Optional. An opaque provider-issued reasoning-continuity token, present only when a provider attaches reasoning-continuity signatures to tool calls (e.g. Gemini's `thoughtSignature`). Implementations MUST preserve it verbatim and pass it back to the same provider on round-trip; spec callers MUST NOT construct, modify, or interpret it. Provider-bound (§3.1.7); absent for providers that do not attach signatures to tool calls. |

**Validation timing.** Implementations MUST validate message-shape constraints (per-role required
fields, `tool_call_id` matching, etc.) no later than the `complete()` boundary — before sending to the
provider, and on the response before returning. A constraint over a single message (e.g. a per-role
*required field's presence*) MAY be enforced earlier, at message construction, in implementations
whose message types make it a required field; what MUST hold is that no message-shape-invalid request
reaches the provider. Constraints that span the message list (e.g. a `tool` message's `tool_call_id`
matching the `id` of an earlier assistant `ToolCall`) are enforced at the `complete()` boundary and
raise `provider_invalid_request` (§7). Tool argument validation against the parameters schema happens
at the same boundaries; under non-error responses, a malformed assistant `ToolCall` from the provider
raises `provider_invalid_response` (§7).

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
| `signature` | optional | An opaque provider-issued reasoning-continuity token, present only when the provider attaches one to a text block (e.g. Gemini's `thoughtSignature` on a text part). Same semantics as `ToolCall.signature`: preserved verbatim, passed back to the same provider, never constructed / modified / interpreted by callers; provider-bound (§3.1.7). |

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
| `signature` | optional | An opaque provider-issued token used by the provider to verify the block on round-trip. Present when the provider attaches the signature to the thinking block itself (e.g. Anthropic). Absent when the provider carries reasoning-continuity signatures on sibling parts instead (e.g. Gemini, where the thought summary maps to a thinking block with no own signature — the signature rides on the adjacent `TextBlock` / `ToolCall`). Implementations MUST pass the value through unchanged when present; spec callers MUST NOT construct, modify, or fabricate the field. |

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

#### 3.1.7 Reasoning-continuity signatures

Reasoning-continuity signatures — `ThinkingBlock.signature`,
`RedactedThinkingBlock.data`, and the optional `ToolCall.signature` /
`TextBlock.signature` fields — are **provider-bound**. A signature
produced by one provider is meaningful only to that provider's wire
mapping; it is NOT portable across providers. When a message list
carrying reasoning-continuity signatures is routed through a §8.X
mapping for a different provider than the one that produced them, that
mapping MUST strip the signatures (and any `ThinkingBlock` /
`RedactedThinkingBlock` entries) before emitting the wire request —
the same strip-on-send behavior the §8.1 OpenAI mapping applies to
thinking blocks. Thinking-bearing conversations are thus
single-provider for round-trip purposes.

The OA-level use of reasoning content — reading `ThinkingBlock.text`,
branching on it, logging it — is uniform across providers; only the
wire-level capture and round-trip of signatures is provider-specific.

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

### `complete(messages, tools=None, config=None, response_schema=None, tool_choice=None, retry=None, stream=False)`

Async. Performs a single completion call. When `response_schema` is supplied, the call
additionally constrains the model's output to conform to the schema. When `tool_choice` is
supplied, the call additionally constrains the model's tool-calling behavior. When `retry` is
supplied, the call additionally performs an in-call retry loop on transient failures per §7.1. When
`stream` is set, the provider additionally consumes the model's streaming wire response and emits a
per-chunk `LlmTokenEvent` (graph-engine §6) as each chunk arrives — the return type is unchanged
(still a `Response`); see *Streaming* below.

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
- `retry` — optional. Accepts an instance of the pipeline-utilities §6.1 retry middleware
  configuration record (four-field `max_attempts` / `classifier` / `backoff` / `on_retry` shape),
  an **llm-provider retry-config** that extends that record with two optional adaptive fields
  (`per_attempt_override`, `reask` — §7.1), or `None` / absent. Default is `None` / absent — the
  v0.4.0 behavior is preserved verbatim (no in-call retry; transient errors raise to the caller).
  When supplied, the call performs an in-call retry loop per §7.1 *Call-level retry*; the same
  configuration-record instance a caller would pass to pipeline-utilities §6.1's retry middleware
  is accepted here (cross-spec re-use of the framework-agnostic shape), and the adaptive fields add
  the §7.1 opt-in behaviors below.
- `stream` — optional boolean (keyword-only, or per-language idiomatic equivalent). Default `False`
  / absent — the v0.4.0 atomic behavior is preserved exactly. When set, the provider consumes the
  model's streaming wire response and emits per-chunk `LlmTokenEvent`s (graph-engine §6) as chunks
  arrive; the call STILL returns the atomic `Response` (the flag controls per-chunk event emission,
  not the return shape). See *Streaming* below.

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
- `complete()` does NOT retry on transient errors by default. Errors propagate; retry policy
  belongs above this layer — either at the node level via pipeline-utilities §6.1
  `RetryMiddleware`, or at the call level via the optional `retry` parameter (above) per §7.1.
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

**Streaming.** When `stream` is set:

- The provider MUST consume the model's **streaming wire response** (SSE / chunked transfer per the
  provider's API) rather than awaiting a single atomic response body, and MUST emit a `LlmTokenEvent`
  (graph-engine §6) on the observer delivery queue **per chunk, as it arrives** — genuinely
  incremental. Implementations MUST NOT satisfy the contract by awaiting the full response and then
  emitting synthesized chunks; the first-token-latency benefit is the contract's purpose. (This MUST
  states behavioral intent. Conformance verifies the testable proxy — that the assembled `Response`
  equals the ordered concatenation of the streamed deltas, per §6 *Streaming assembly* — not that
  chunks crossed the wire incrementally; a faked implementation passes conformance while violating
  the contract's purpose.)
- The call STILL returns the atomic `Response` (§6) at completion. **The return type is unchanged** —
  `complete()` returns `Response` whether or not `stream` is set. The flag governs per-chunk event
  emission, not the return shape; node bodies, reducers, retry middleware, and the terminal
  `LlmCompletionEvent` all see the same atomic `Response` either way.
- With no observer attached (direct provider use outside an invocation), `stream` set is **observably
  identical** to `stream` unset — the same atomic `Response` returns and there is no consumer for the
  token events. Implementations MAY still consume the wire incrementally for latency.

**Provider streaming support.** Streaming is a per-§8.X-mapping capability, not a guaranteed property
of every provider. A wire-format mapping that does NOT implement streaming MUST reject a `stream`-set
call at pre-send validation, raising `provider_invalid_request` (§7) with a message identifying that
the mapping does not support streaming. It MUST NOT silently fall back to an atomic call (which would
hide that the requested mode was unavailable) and MUST NOT fail opaquely mid-call. This is the same
mold as `tool_choice` validation — a request shape a mapping cannot satisfy is a pre-send
`provider_invalid_request`. The §8.1 OpenAI-compatible mapping implements streaming (below); the §8.2
Anthropic and §8.3 Gemini mappings do NOT in this version and therefore reject `stream`-set calls
until their streaming wire handling lands in follow-ons.

## 6. Response and configuration

A `Response` record:

| Field | Description |
|---|---|
| `message` | The assistant message returned by the model. Always `role: "assistant"`. May carry `tool_calls`. When the bound provider's §8.X mapping surfaces provider-emitted reasoning content, `message.content` is a content-block sequence that MAY include `ThinkingBlock` / `RedactedThinkingBlock` entries (per §3.1.4 / §3.1.5); mappings that do not surface reasoning content return text-only content. |
| `finish_reason` | One of `"stop"`, `"length"`, `"tool_calls"`, `"content_filter"`, `"error"`. See below. |
| `usage` | A record `{prompt_tokens, completion_tokens, total_tokens, cached_tokens?, cache_creation_tokens?}`. Each declared field is a non-negative integer or `null`. The first three (`prompt_tokens`, `completion_tokens`, `total_tokens`) MUST be `null` together when the provider does not report usage. The two optional fields surface prefix-cache statistics when the provider returns them: `cached_tokens` is the count of input tokens that hit a prefix cache ("reported miss" is `0`, distinct from absent — see below); `cache_creation_tokens` is the count of input tokens written to the cache during the call (typically populated by providers with explicit cache-control surfaces; absent or `0` otherwise). Each §8.X wire-format mapping documents the provider response field these values are sourced from. Absent (`null` / `None` / `undefined`, per the language's idiom) when the provider does not report the corresponding cache statistic. A counter **present on the wire but malformed** (a non-integer, a negative, a boolean) is treated as *not reported* — that counter is `null`, the others stand, never raised or repaired (§7 *Malformed usage counter*). |
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

**Managed-field collision.** The untouched pass-through above governs an undeclared key the wire-format
mapping (§8) does **not** touch. A mapping MAY additionally **manage** a wire-body field — set it for the
mapping's own correctness, because its response consumer reads a value keyed to that field, or because it
enforces a mapping-level contract. A §8.x mapping that manages a field **MUST** enumerate the keys it manages.
When an undeclared extras key **names a managed field**, the untouched pass-through does **not** apply; the
mapping resolves the collision by the managed field's shape:

- **Additive / list-shaped** managed field — the mapping's mandatory value(s) and the caller's value(s) are
  **merged** in a deterministic order (the mapping's value(s) first), de-duplicated with first occurrence
  winning, so a matching entry collapses to one.
- **Non-additive** managed field whose override would break the mapping's contract or its response consumer —
  a scalar mode-switch, or an object the mapping constructs wholesale (e.g. a structured-output `response_format`).
  The caller's value and the mapping's are mutually exclusive, so there is nothing to merge: an extras value
  **equal** to the managed value is a redundant no-op; a **conflicting** value is **rejected pre-send** with
  `provider_invalid_request` (§7). A field the mapping constructs **only conditionally** (e.g. `response_format`
  only when a `response_schema` is supplied, `stream_options` only when streaming) is managed **only when the
  mapping is producing it**; when it is not, the field is unmanaged and keeps untouched pass-through.
  "Equal" and "conflicting" are judged by **decoded-value deep equality**: the caller's and the managed
  value are compared as parsed values, structurally — **objects** member-wise (member/key order
  irrelevant), **arrays** element-wise in order (array order IS significant), and **scalars** by value
  (numbers compared numerically, so `1` and `1.0` are equal). Insignificant serialization differences do
  not matter; comparison is not by byte-level JSON or language-level object identity.

A mapping **MUST NOT** silently drop a conflicting extras value, and **MUST NOT** silently let it override the
managed value. A key the mapping does **not** manage is unaffected — it keeps the untouched pass-through above
verbatim. The managed set is **opt-in per mapping**; the default for every other undeclared key is unchanged.

**Null-skip semantics.** A declared `RuntimeConfig` field with a value of `None` (Python `None`,
TypeScript `undefined`, the language's equivalent "unset" sentinel) MUST be omitted from the wire
request body. Such a value denotes "field not supplied for this call," distinct from "field
supplied with an explicit null value." Implementations MUST NOT serialize `None`-valued declared
fields as JSON `null` in the wire body. The null-skip rule applies to declared fields only;
undeclared fields supplied to `RuntimeConfig` are forwarded per the extras-pass-through contract
above (the implementation's wire-format mapping determines whether an undeclared-field `None`
appears as `null` in the request body or is omitted — implementation-defined, since the spec does
not constrain undeclared-field types).

**Streaming assembly.** When `complete()` is called with `stream` set (§5), the atomic `Response` is
assembled from the streamed chunks so the streamed and non-streamed paths produce structurally
identical `Response` records:

- **Content** — `message.content` is the ordered concatenation of the streamed content deltas. Each
  content delta is also emitted live as `LlmTokenEvent(delta_kind="content")` (graph-engine §6).
- **Reasoning** — when the provider streams reasoning / thinking content (§3.1.4 / §3.1.5), the
  reasoning deltas assemble into their `ThinkingBlock` / `RedactedThinkingBlock` entries on the
  terminal `Response` AND are emitted live as `LlmTokenEvent(delta_kind="reasoning")`. Whether a
  provider streams reasoning is a per-§8.X-mapping capability (see §8.1); a mapping that does not
  surface streamed reasoning simply emits no `reasoning`-kind token events.
- **Tool calls** — streamed tool-call argument deltas are reassembled into complete `ToolCall`
  records (`id`, `name`, `arguments`) on `message.tool_calls`, in the order the provider streamed
  them; the reassembled `arguments` MUST parse identically to the non-streamed case (a mapping when
  valid JSON; `null` when unparseable, per §3). This reassembly is provider-internal — tool-call
  argument deltas are NOT emitted as `LlmTokenEvent`s in this version (only the complete `tool_calls`
  on the terminal `LlmCompletionEvent` is surfaced).
- **Usage / finish_reason** — sourced from the terminal chunk (providers emit usage and the finish
  reason on the final streamed event; §8.1 documents the OpenAI-compatible specifics).
- **`raw`** — the parsed provider response; for a streamed call, the assembled representation of the
  streamed events (implementation-defined assembly; MUST be populated per the `raw` contract above). The
  assembly MUST preserve the terminal chunk's usage block **verbatim**, so a malformed counter nulled on
  the normalized `Response.usage` remains inspectable on `raw` (§7 *Malformed usage counter*).
  Within-implementation wire-byte stability (§8) applies to the assembled form.
- **Structural identity** — a `Response` assembled from a stream MUST be indistinguishable in shape
  from a `Response` returned atomically for the equivalent non-streamed call. This is the contract
  that lets every downstream consumer (node bodies, reducers, the terminal typed events, the OTel /
  Langfuse mappings) ignore whether streaming was used.

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
  the §6 shape (missing required fields, invalid `tool_calls` structure, invalid JSON). This is a
  **payload** category: a malformed **usage counter** — an accounting figure beside the message — is
  *not* one; it is treated as not reported (see *Malformed usage counter* below).
- `provider_invalid_request` — the request was malformed before sending (per-role message
  constraints violated, `tool_call_id` does not match an earlier `assistant` tool call, duplicate
  tool names, etc.). This category is raised by the implementation's pre-send validation — except
  that a per-role *required field's presence* MAY instead be enforced at message construction (a
  construction-time error, not this category) in implementations whose message types make it
  required, per §3 *Validation timing*; the cross-message, value, and structural malformations that
  reach the `complete()` boundary are the `provider_invalid_request` cases. The
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
  content as **`output_content`** (the verbatim content the model produced), a description of the validation
  or parse failure as **`error_message`** (the wrapped exception's message, the failing JSON
  Pointer, or the language's idiomatic equivalent) — these two matching the graph-engine §6
  failure-event field names (0082), which the call-level `reask` builder (§7.1) consumes — **and
  the response's normalized `finish_reason` (§6) and token `usage`** — both
  available from the received response, since the failure is a downstream parse/validation step on an
  intact wire response, not a transport failure. The `finish_reason` lets callers distinguish a
  truncation (`"length"` — the model hit `max_tokens`) from a model that finished (`"stop"`) but
  emitted invalid or schema-violating content, and choose retry policy accordingly (this also
  reconciles §8.2.5's statement that the mapping surfaces the mapped `finish_reason`). Non-transient by default — a model that fails to produce schema-compliant output
  on a given prompt usually fails the same way on a byte-identical retry. Users wanting
  retry-on-validation-failure semantics SHOULD use the call-level `reask` extension (§7.1), which
  retries with a caller-authored correction built from this error's `output_content` + failure
  description rather than replaying the identical request; a pipeline-utilities `RetryMiddleware`
  classifier MAY also include `structured_output_invalid` in its transient set, but the category is
  NOT transient by default at the spec level.
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

### Malformed usage counter

A usage counter (§6 `Response.usage`) that is **present on the wire but malformed** — a non-integer, a
negative, a boolean where a non-negative integer is required — is treated as **not reported**, exactly as
an *absent* counter is. It is the per-field `null` §6 already permits: that counter is `null`, the others
stand. §6's "the first three MUST be `null` together" is conditioned on the provider reporting **no** usage
at all, which a partially-malformed record does not satisfy — a response reporting two sound counters and
one garbage one has reported usage, so `{null, 5, 15}` is the outcome, not `{null, null, null}`.

An implementation:

- **MUST NOT** raise `provider_invalid_response` (or any category) *because of the counter* — the
  completion succeeded and the message is intact; a genuine parse failure of the §6 shape (a missing
  required field, invalid `tool_calls`, invalid JSON) still raises on its own grounds;
- **MUST NOT** fabricate, coerce, clamp, or repair it — a repaired counter is indistinguishable from a
  reported one (fabrication under another name);
- **MUST** leave the verbatim value on `Response.raw`.

Where a mapping **derives** `total_tokens` (§8.2 — the providers that do not return a total on the wire),
a derived total whose addend is not reported (malformed or absent) is **itself not reported** (`null`); a
mapping **MUST NOT** substitute the surviving addend as the total, which would report a figure the
provider never sent.

The rule binds every surface that renders a counter, not only `Response.usage`: the typed
`LlmCompletionEvent.usage` (graph-engine §6) **mirrors the response** — a partially-malformed record
surfaces as a present record with the malformed counter(s) `null`, an all-malformed record as a present
record of null counters (§6 null-together), **not** as a null `usage` — and the observability usage
attributes, token-usage histogram, and token-budget instruments (observability §5.5.3 / §11.2 / §5.5.15)
**omit** — rather than emit, sum, compare, or divide over — a counter that is not reported.

### 7.1 Call-level retry

When `complete()` is called with a non-`None` `retry` parameter (per §5), the provider
implementation performs an in-call retry loop:

- On each attempt, dispatch the underlying request as it would for a non-retried call.
- If the response is successful, return immediately.
- If the response raises an exception classified as transient by the `retry` record's
  `classifier` field (default behavior matches pipeline-utilities §6.1's default transient
  classifier — `provider_unavailable`, `provider_rate_limit`, `provider_model_not_loaded`, plus
  any category marked transient by its carrying spec), wait per `backoff(attempt_index)` and
  re-attempt.
- If `max_attempts` is exhausted, propagate the final error per the normal `complete()`
  exception path.
- Exceptions classified as non-transient propagate immediately on first occurrence (no retry).

**Configuration record reuse.** The `retry` parameter accepts the same configuration record
pipeline-utilities §6.1 defines — the four-field shape (`max_attempts`, `classifier`,
`backoff`, `on_retry`) is framework-agnostic and reusable across the per-node and per-call
retry contexts. Implementations MUST accept the same configuration record instance a caller
would pass to the §6.1 retry middleware. (Cross-spec reference direction: this section
references pipeline-utilities §6.1, which is the inverse of pipeline-utilities §6.1's existing
dependency on this §7 for transient category names. The two-way dependency is acceptable
because the shared retry config record is framework-agnostic and the per-section content
remains independently coherent.)

**Adaptive extensions (opt-in).** The `retry` parameter (§5) MAY instead be an **llm-provider
retry-config** that extends the §6.1 four-field record with two optional fields; both default to
absent, and a plain §6.1 record (or `None`) behaves exactly as above. These extensions are
LLM-completion-specific — they concern sampling and messages — and so live here at the call level,
not on the framework-agnostic §6.1 middleware.

- **`per_attempt_override` — per-attempt request override.** A declarative *retry* schedule of
  `RuntimeConfig` (§6) partial-overrides; when supplied, the loop **MUST** apply it. **Attempt 0
  always uses the caller's base `config` unmodified.** The schedule applies to retries: retry *i*
  (attempt *i+1*) uses the base config with the *i*-th override shallow-merged on top per key — a field set
  to a non-`None` value in the override replaces the base's value for that key; a field left `None` or absent
  inherits the base (per §6's null-skip semantics, `None` means "unset", so an override cannot clear a base
  field to `None`). Undeclared extras (§6) merge by the same per-key rule. (A general `RuntimeConfig` partial;
  the canonical case overrides only sampling, e.g. an escalating temperature schedule). When the schedule is shorter than the retry count, the last
  entry carries forward. The override is applied to an internal per-attempt copy; `complete()` MUST
  NOT mutate the caller's `config` (§5). `on_retry` stays observe-only — the schedule is the
  declarative mutation surface (an implementation MUST NOT substitute a mutating retry callback).

- **`reask` — structured-output reask (caller-supplied corrective-message builder).** When `reask`
  is supplied, the loop treats `structured_output_invalid` (§7) as retryable **for this call**,
  without the caller supplying a custom `classifier` (the §6.1 default classifier is unchanged; this
  is a call-level convenience). Reask attempts consume the same `max_attempts` budget — there is no
  separate reask budget. On a `structured_output_invalid` attempt, before the next attempt the loop
  invokes the caller's `reask` builder with the raised error's structured-output-failure surface (§7
  / 0082 — the verbatim invalid `output_content` and the failure description on `error_message`) and
  appends **two** messages to a working transcript: the model's own raw output for that attempt as an
  `assistant` message, then the content the builder returns as a `user` message. The working
  transcript starts as a copy of the caller's `messages` and **accumulates** these pairs across reask
  retries — so attempt *k*'s request is the caller's messages followed by, for each prior reask
  attempt in order, that attempt's `assistant` output and its `user` correction. Appending the
  `assistant` output keeps the sequence role-alternating (Anthropic forbids consecutive same-role
  messages — §8.2) and gives the model its full self-heal history. The `assistant` message carries the
  attempt's output as the text the error surfaces on `output_content` (§7 / 0082); when the working
  transcript's last message is already an `assistant` message (e.g. a caller prefill), the output
  **continues** that message — concatenated onto its content verbatim, with no OA-added separator —
  rather than starting a new one, so alternation still holds. The builder is
  invoked only when a further attempt remains — not on the terminal attempt once `max_attempts` is
  exhausted. A **transient** retry interleaved in a reask-enabled loop appends no reask pair but re-sends
  the working transcript accumulated so far (its span's `retry_reason` is `transient`). `complete()` MUST
  NOT mutate the caller's `messages` (§5) — the working transcript is an internal copy. The implementation MUST NOT
  author or inject corrective prompt text of its own: the `assistant` message is the model's verbatim
  output and the `user` message is exactly what the caller's builder returns (charter §3.1 principle
  7, *No built-in prompts* — the caller owns every word OA adds beyond the model's own output; the
  framework provides only the retry loop and the typed error surface). Absent a `reask` builder,
  `structured_output_invalid` is non-transient and raises
  on first occurrence (§7), unchanged.

The two extensions compose: with both set, a `structured_output_invalid` retry both applies the next
override (e.g. a higher temperature) and appends the caller's corrective message.

**Transient classification.** The default `classifier` field's behavior matches the §6.1
*Default transient classifier* text — the same categories §6.1 enumerates as transient trigger
the per-call retry loop. Callers MAY supply a user-defined `classifier` if their application
has additional retriable categories or context-dependent retry policies. The classifier's
two-argument `(exception, state) -> bool` signature carries over from §6.1; the shape of the
`state` argument when the classifier is invoked at the call level is implementation-defined
(the §6.1 default classifier ignores `state` and matches purely on exception category, so the
default behaves correctly without depending on the `state` shape; custom classifiers that
inspect `state` at the call level consult the implementation's documentation for the carried
value's shape).

**Backoff behavior.** The `backoff` field's `(attempt_index) -> seconds` contract from §6.1
applies unchanged at the call-level retry. The §6.1 default (exponential with full jitter,
base 1s, cap 30s) applies when the caller doesn't override; implementations MAY ship additional
named backoff strategies per §6.1's MAY clause.

**Cancellation signals MUST propagate.** Per the §6.1 cancellation-propagation rule,
cancellation signals raised by the language runtime (Python's `CancelledError`, TypeScript's
`AbortError`, equivalents) MUST NOT be classified as transient — call-level retry
implementations MUST detect cancellation and re-raise it before consulting the classifier.

**Per-attempt span emission.** Each retry attempt produces its own `openarmature.llm.complete`
span per observability §5.5 — N retry attempts emit N LLM spans, all parented under the
calling node's span. The per-attempt span carries the `openarmature.llm.attempt_index`
attribute (per observability §5.5), and on retry attempts (attempt index ≥ 1) an
`openarmature.llm.retry_reason` attribute recording why **this attempt was scheduled** — the class of
the *immediately prior* attempt's failure, `transient` (a transient-classified failure) or `reask` (a
`structured_output_invalid` reask), not this attempt's own outcome; attempt 0 carries
no `retry_reason`. (§7.1 introduces the attribute; its detailed observability §5.5 / Langfuse
rendering is a follow-on.) The final-error category lands on the LAST attempt's span;
earlier failed-then-retried attempts carry their own per-span error categories.

**Two-level retry lane separation.** Retry primitives operate at two semantic levels in OA:

| Layer | Spec section | Semantic unit | Use when |
|---|---|---|---|
| Per-call retry | llm-provider §7.1 (this section) | A single `complete()` call | A node issues multiple LLM calls in a loop; you want to avoid re-running successful calls when a later call's transient fails |
| Per-node retry | pipeline-utilities §6.1 `RetryMiddleware` | A whole node invocation | A node does LLM + non-LLM work (DB writes, parses, side effects); you want to re-run the entire body on failure |

The layers compose: per-call exhausts → propagates → per-node retry catches → re-runs whole
node → per-call budgets reset for each fresh per-node attempt.

**Common mistakes to avoid:**

- **Multiplicative budget on chunked nodes.** Stacking the §6.1 retry middleware (configured
  with `max_attempts=3`) over a node that issues 5 LLM calls, each with a per-call `retry`
  record configured for `max_attempts=3`, can issue up to `3 × 5 × 3 = 45` LLM calls in the
  worst case. The budget multiplies. Authors stacking both layers SHOULD pick intentional
  budgets per layer (e.g., per-call retries narrower than per-node retries, or one layer only).
- **Inline retry via try/except inside the node body.** Implementing retry as a try/except
  inside the node body loses the per-attempt span attribution and the backoff-utility
  integration. Use the `retry` kwarg instead.
- **Widening the transient classifier to mask real errors.** The §6.1 default classifier
  excludes non-transient categories for a reason. Supplying a custom `classifier` that retries
  on `provider_invalid_request` or `structured_output_invalid` (for example) masks bugs rather
  than working around transient infrastructure issues. Custom classifiers SHOULD widen the
  default only for categories that are genuinely transient but not yet enumerated by §6.1. For
  `structured_output_invalid` specifically, prefer the opt-in `reask` extension above (which
  retries with a caller-authored correction) over a classifier that blindly replays the
  identical request.

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

**Intra-impl wire-byte stability.** Any §8.X mapping implementation MUST produce byte-identical
wire output for OA-input pairs that are structurally equivalent. Two `complete()` calls passing
the same `messages` sequence, the same `tools` list, the same `config`, the same `tool_choice`,
and (when present) the same `response_schema` MUST emit identical wire-format request bytes from
the same implementation. Sources of nondeterminism implementations MUST control for:

- **JSON object key ordering** within wire-format objects implementations construct (tool
  definitions, message records, content blocks, request-body roots) MUST be sorted
  lexicographically OR follow a stable implementation-defined key order. Construction-time
  dict-insertion order that varies across calls (e.g., a tool schema built from a mapping whose
  key order reflects build-time iteration) MUST be canonicalized before serialization.
- **Array ordering** for spec-canonical lists (the messages list, the tools list, the
  content-block sequence, the `stop_sequences` list) MUST preserve caller-supplied order. This
  is already implicit in the §3 / §4 shapes; the stability rule makes it explicit at the wire
  boundary.
- **JSON Schema in `Tool.parameters`** is user-supplied content with no spec-imposed key
  ordering. The wire-format mapping MUST canonicalize the schema's key order (sorted
  recursively) before emission — without this step, two semantically-equivalent schemas built
  differently produce different wire bytes. The same rule applies to JSON Schema in
  `response_schema` (§5).
- **`RuntimeConfig` extras** (the pass-through fields permitted by §6's extras-pass-through
  contract) MUST be emitted at their wire placement per the mapping's existing rule (§8.1 places
  them at the request-body root) with sorted key order, regardless of insertion order in the
  construction-time mapping.
- **Content-block source dicts** (an image block's `source: {type: "url", url: ...}` or
  `source: {type: "inline", base64_data: ...}`) are spec-structured records; key ordering within
  them follows the sorted-keys rule above.

The rule applies **intra-implementation only** — the existing observability §5.5.1 caveat
("cross-implementation bytewise stability NOT required — JSON encoding rules vary across
language standard libraries") applies identically here. Cross-language byte equality (Python and
TypeScript producing identical wire bytes for the same OA input) is NOT required and is out of
scope; Automatic Prefix Caching's hit rate is computed on a per-deployment basis (one language
port at a time), so intra-impl stability is sufficient for the use case.

Implementations SHOULD document the canonicalization mechanism (e.g., "object keys serialized
via `json.dumps(..., sort_keys=True)`") so users can reason about which inputs collide on the
cache. The §8.X.4 *Concurrency* subsection MAY note any concurrency interaction (none expected
— the rule is pure transformation, not state).

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
```json
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
```json
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

**Managed structural fields (§6 *Managed-field collision*).** The mapping sets several request-body-root
fields for its own correctness that a caller does **not** supply as declared `RuntimeConfig` fields, so an
undeclared extras key of the same name would collide with them at the root: **`model`** (the bound model
identifier — §3 / §5 per-instance binding), **`messages`** and **`tools`** (the `complete()` arguments), and
**`tool_choice`** (the §5 parameter). Each is a **managed non-additive field**: an extras-supplied value that
**conflicts** with the mapping's value is **rejected pre-send** with `provider_invalid_request` (§7) —
honoring it would silently replace the caller's conversation, tool set, or bound model (a caller who wants a
different model binds a different provider instance); the mapping **MUST NOT** silently drop it or silently
let it override. (A value equal to the managed value is a redundant no-op.) The wire key `stop` is **not**
enumerated here: it is the realization of the **declared** `stop_sequences` field, a declared-field-vs-extras
question deferred with the residual per-mapping audit (see `docs/open-questions.md`), not the managed-internal
field rule.

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

**Wire-byte stability** (per §8 framing). The §8.1 mapping implementation applies the intra-impl
wire-byte stability rule to its outputs. Specifically: tool definitions, `tool_choice` records,
the messages list, and the `response_format.json_schema.schema` (per §8.1.5) all canonicalize
with sorted JSON object keys; the undeclared-field pass-through at the request-body root (per
§6's extras-pass-through contract) emits with sorted keys; inline-image data URIs (§8.1.1.1)
produce byte-stable encodings — the `data:<media_type>;base64,<base64_data>` format has only one
canonical form given the source block's fields.

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
- `usage` — built from the response's `usage` field. If `usage` is absent, the three baseline
  subfields (`prompt_tokens`, `completion_tokens`, `total_tokens`) MUST be `null`.
- `usage.cached_tokens` — sourced from the response's `usage.prompt_tokens_details.cached_tokens`
  field when present (the OpenAI Chat Completions wire shape; vLLM and other OpenAI-compatible
  servers that surface prompt-cache stats follow the same nesting). Set to `0` when the provider
  reports zero cache-hit tokens; absent when the provider does not report cache statistics. The
  newer OpenAI Responses API surfaces the same value at `usage.input_tokens_details.cached_tokens`;
  implementations targeting that endpoint source from the `input_tokens_details` path with the
  same semantics. **vLLM caveat**: vLLM servers require both `--enable-prefix-caching` (enables
  the cache) and `--enable-prompt-tokens-details` (surfaces the stats in the response) for this
  value to populate; servers configured without one or both report the cache field as absent or
  unpopulated.
- `usage.cache_creation_tokens` — OpenAI's prompt-cache surface does not report a discrete
  cache-creation count under the OpenAI-compatible wire shape; the field is left absent. (Mappings
  that target providers exposing a cache-creation metric set the field per their §8.X mapping.)
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

```json
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
mapping **MUST NOT construct** a `response_format` of its own; the v0.4.0 wire shape is preserved
unchanged for free-form calls (absent an extras-supplied `response_format`, which rides the §6
extras pass-through untouched — see the managed-field clause below).

`response_format` is a **conditionally-managed** non-additive wire field (§6 *Managed-field collision*): it is
managed **while the mapping is producing it** — the native path (§8.1.5) when a `response_schema` is supplied,
where the mapping constructs `response_format` wholesale from the schema and its response consumer (§6 `parsed`,
§7 `structured_output_invalid` validation) depends on the model being constrained to that schema. On that path,
an extras-supplied `response_format` that **conflicts** with the mapping's schema-derived value is **rejected
pre-send** with `provider_invalid_request` (§7) — honoring it would constrain the model to the caller's format
while the mapping validates against `response_schema`, breaking structured output; the mapping **MUST NOT**
silently drop it or silently let it override. (A value equal to the managed value is a redundant no-op.) When
the mapping does **not** produce `response_format` — a free-form call (no schema), **or the §8.1.5.1
prompt-augmentation fallback path** (a schema is supplied but the request is issued *without* `response_format`)
— the field is unmanaged and an extras `response_format` rides the extras bag untouched.

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

#### 8.1.6 Streaming

When `complete()` is called with `stream` set (§5), the OpenAI-compatible mapping consumes the
Server-Sent Events streaming response and emits per-chunk `LlmTokenEvent`s (graph-engine §6),
assembling the atomic `Response` per §6 *Streaming assembly*.

- **Request** — `stream: true` in the request body, plus `stream_options: {include_usage: true}` so
  the terminal chunk carries usage (OpenAI omits usage from streamed responses otherwise). `stream_options` is
  a **conditionally-managed** wire field (§6 *Managed-field collision*): while streaming, the mapping sets it for
  the usage collection its §6 *Streaming assembly* consumer depends on. An extras-supplied `stream_options` that
  **conflicts** with `{include_usage: true}` — e.g. `{include_usage: false}`, which would drop the terminal-chunk
  usage the mapping reads — is **rejected pre-send** with `provider_invalid_request` (§7); the mapping
  **MUST NOT** silently drop it or silently let it override (a matching value is a no-op). For a non-streaming
  call the mapping sends no `stream_options`, so an extras `stream_options` is unmanaged and rides untouched.
  The `stream` flag itself is **not** enumerated here — it is the realization of the **declared**
  `complete(stream=…)` argument, a declared-field-vs-extras question deferred with the residual per-mapping audit
  (see `docs/open-questions.md`), not the managed-internal field rule.
- **Wire** — Server-Sent Events: each `data:` line is a chunk whose `choices[].delta` carries a
  `content` delta, `tool_calls` deltas (each with an `index` and partial `id` / `function.name` /
  `function.arguments` fields), and/or a reasoning delta (see below). The `data: [DONE]` sentinel
  terminates the stream.
- **Content deltas** → `LlmTokenEvent(delta_kind="content")` (§5), concatenated into
  `message.content` per §6.
- **Tool-call deltas** → reassembled into `message.tool_calls` per §6; NOT emitted as token events.
- **finish_reason / usage** — `finish_reason` is set on the last content-bearing chunk's
  `choices[].finish_reason` (one of `stop`, `length`, `tool_calls`, `content_filter`). With
  `stream_options.include_usage` set, a final chunk with empty `choices` carries `usage`, followed by
  the `[DONE]` sentinel.

**Reasoning deltas (OpenAI-compatible extension).** Base OpenAI Chat Completions does **not** stream
raw reasoning — its reasoning models do not expose chain-of-thought over this API. Streamed reasoning
is an OpenAI-compatible *extension* offered by reasoning-model servers, and the delta field name
**varies by backend**: `choices[].delta.reasoning_content` (DeepSeek, and earlier vLLM) and
`choices[].delta.reasoning` (current vLLM). The mapping MUST recognize **either** as a reasoning delta
→ `LlmTokenEvent(delta_kind="reasoning")`, assembling into the terminal `Response`'s reasoning blocks
per §6. On these backends a reasoning delta and a content delta are mutually exclusive within a single
chunk, and reasoning tokens stream first, then content. A backend that emits neither extension field
streams no reasoning token events (the vanilla-OpenAI case). The streamed-chunk shapes above (the
`stream_options` flag, `finish_reason` / `usage` chunk positioning, the `[DONE]` sentinel, tool-call
delta fields, and the two reasoning-delta field names) are **verified against current OpenAI, vLLM,
and DeepSeek streaming docs** (2026-06-20; tracked in `docs/compatibility.md`).

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

**Wire-byte stability** (per §8 framing). The §8.2 mapping implementation applies the intra-impl
wire-byte stability rule to its outputs. Specifically: `system` extraction concatenates with a
stable separator (`\n\n` per §8.2.1) and preserves source order, so the result is byte-stable;
`tools[].input_schema` canonicalizes with sorted JSON object keys; `tool_use` and `tool_result`
content blocks (per §8.2.1.1 / §8.2.1.2) serialize with sorted keys; the `tool_use.input` field
(deserialized mapping per the §8.2.1.1 row) canonicalizes recursively.

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
  `usage.total_tokens` ← the sum of those two (or `null` per §6's rules; a derived total whose addend is not reported — malformed or absent — is itself `null` per §7 *Malformed usage counter*, never the surviving addend). **Cache-token note:**
  Anthropic does NOT support implicit prefix caching — `cache_creation_input_tokens` and
  `cache_read_input_tokens` only fire when the caller explicitly annotates content with
  Anthropic `cache_control` blocks, which is an explicit-cache surface out of scope for the §6
  `usage.cached_tokens` / `usage.cache_creation_tokens` implicit-cache fields. The §8.2 mapping
  leaves both implicit-cache fields absent. (The Anthropic explicit-cache reporting surface
  remains visible to callers via `Response.raw.usage.cache_creation_input_tokens` /
  `cache_read_input_tokens`; a future proposal that adds spec-level explicit-cache primitives
  would map those values onto a dedicated explicit-cache surface, not onto the §6
  implicit-cache fields.) Anthropic's own total-input accounting is
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`; the spec
  `usage.prompt_tokens` maps from `input_tokens` alone, matching the implicit-only semantics.
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

```json
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

### 8.3 Google Gemini mapping

The Gemini `generateContent` API
(`POST /v1beta/models/{model}:generateContent`) is the
provider-native protocol for Google's Gemini model family.

#### 8.3.1 Request mapping

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

```json
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
in natural language), has no §5 `tool_choice` analogue; it is
reachable via the extras-pass-through path (`toolConfig` supplied
as an undeclared field) and is documented here so implementations
recognize it rather than treating it as invalid.

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

**Wire-byte stability** (per §8 framing). The §8.3 mapping implementation applies the intra-impl
wire-byte stability rule to its outputs. Specifically: Gemini's `system_instruction.parts` is built
from the spec system message and preserves source-order parts; `function_declarations[].parameters`
canonicalizes with sorted JSON object keys; `functionCall.args` (a structured-arguments mapping per
§8.3.1.2) serializes with sorted keys; `functionResponse.response` and inline data parts (per
§8.3.1.1) serialize with sorted keys. Undeclared `RuntimeConfig` extras nested under
`generationConfig` (per the preceding paragraph) emit with sorted keys at every nesting level.

##### 8.3.1.1 Parts wire mapping

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
| `ThinkingBlock { text }` | A `Part` flagged `{ "text": <text>, "thought": true }`. Gemini's thought summary is a text part with `thought: true` and carries no `thoughtSignature` of its own — for Gemini-origin reasoning the signature rides on the sibling `functionCall` / text part (captured to `ToolCall.signature` / `TextBlock.signature` per §8.3.2), not on the summary. |
| `TextBlock { text, signature }` (assistant, signature present) | `{ "text": <text>, "thoughtSignature": <signature> }`. A text part carrying a captured Gemini thought signature. |

`thoughtSignature` is emitted on a part only when the corresponding
spec block carries a non-empty `signature`. When the block has no
signature (the common case), the key MUST be omitted entirely — not
set to `null` — so the wire request matches Gemini's contract.

Empty content blocks are rejected at pre-send validation per §3 /
`provider_invalid_request`.

##### 8.3.1.2 `tool` role bidirectional translation

As with §8.2.1.2, spec `tool` messages have no Gemini role.

**Spec → Gemini (on send):** each consecutive run of spec `tool`
messages collapses into a single Gemini `user`-role `Content`
whose `parts` are `functionResponse` entries — one per spec `tool`
message, preserving order:

```json
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

#### 8.3.2 Response mapping

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
  `usage.total_tokens` ← `totalTokenCount`. The §6 implicit-cache
  fields map from Gemini's `usageMetadata`:
  `usage.cached_tokens` ← `cachedContentTokenCount` when present
  (Gemini 2.5+ surfaces this for implicit cache hits and for
  explicit-cache reads alike); `usage.cache_creation_tokens` is
  left absent because Gemini does not report a discrete
  cache-creation count under its implicit-cache surface (explicit
  caches are created out-of-band via the `cachedContents` API,
  out of scope for the §6 implicit-cache fields). Other
  Gemini-specific subfields (`toolUsePromptTokenCount`,
  `thoughtsTokenCount`, the `*TokensDetails` modality breakdowns)
  surface in `Response.raw.usageMetadata` unchanged and are NOT
  promoted to the spec `usage` record.
- `raw` — the parsed JSON response body, verbatim. Gemini-specific
  fields (`promptFeedback`, `safetyRatings`, `modelVersion`,
  `responseId`) surface here unchanged.

#### 8.3.3 Error mapping

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

#### 8.3.4 Concurrency

Matches §8.1.4. Gemini's hosted API supports concurrent requests;
implementations MUST NOT add a serialization layer. Client-side
rate-limit needs use the pipeline-utilities rate limiter or
middleware.

#### 8.3.5 Structured output

Gemini natively supports schema-constrained decoding. When
`complete()` is called with a `response_schema`, the §8.3 mapping
sets:

```json
{
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseJsonSchema": <response_schema>
  }
}
```

Gemini exposes two schema fields: `responseSchema` (an OpenAPI 3.0
Schema subset) and `responseJsonSchema` (a full JSON Schema). Because
the §6 `response_schema` is a full JSON Schema, the §8.3 mapping
targets `responseJsonSchema`, so the schema round-trips faithfully —
`responseSchema` would silently drop JSON Schema constructs outside
the OpenAPI subset. The `response_schema` passes through under
`responseJsonSchema` unchanged. The response's text content is the
JSON string conforming to the schema; the §8.3 mapping parses it into
`Response.parsed` and validates against `response_schema` per §6. On
validation failure, raise `structured_output_invalid` per §7. The
behavioral contract matches §8.1.5's native path.

When `complete()` is called without `response_schema`, the request
MUST NOT include `responseMimeType` / `responseJsonSchema`; the
free-form wire shape is preserved.

This is the native path: Gemini, like OpenAI (§8.1.5) and Anthropic
(§8.2.5), provides native schema-constrained decoding. The
prompt-augmentation fallback (§8.3.5.1) applies only to models
lacking native support, mirroring how §8.2.5.1 handles older
Anthropic models.

##### 8.3.5.1 Fallback for older models

Gemini model versions predating native JSON-Schema-constrained
decoding fall back to prompt-augmentation per §8.1.5.1's pattern
(append a schema directive to `systemInstruction` or the message
list, parse the text response, validate, raise
`structured_output_invalid` on failure). Implementations MUST
document which path a given call uses.

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

- **Node-body direct stream consumption** — streaming is observer-only in this version (token events
  via the observer union, §5); a node body consuming the stream directly (an async-iterator return for
  incremental parsing / early-stop) is deferred, additive if a consumer surfaces.
- **Tool-call-delta token events** — `LlmTokenEvent` carries `content` and `reasoning` deltas (§5);
  tool-call argument deltas are reassembled into the atomic `Response` but NOT emitted as token events.
  A `delta_kind="tool_call"` variant is additive if a consumer needs live tool-argument streaming.
- **Per-vendor streaming wire mappings beyond OpenAI-compatible** — Anthropic §8.2 and Gemini §8.3
  streaming handling land as follow-ons; until then those mappings reject `stream`-set calls (§5
  *Provider streaming support*).
- **Streaming for non-completion provider operations** — embedding / rerank streaming is a separate
  concern; not in this version.
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

## History

- created by [proposal 0006](../../proposals/0006-llm-provider-core.md)
- §3 Message shape extended (user content MAY be a sequence of content blocks); §3.1 Content blocks added (text and image blocks; image input only on user messages); §7 gained `provider_unsupported_content_block` error category; §8.1 user-row updated and §8.1.1 content-block wire mapping added; §10 multi-modal entry split (image input now covered; audio/video and image outputs remain deferred) by [proposal 0015](../../proposals/0015-llm-provider-multimodal-images.md)
- §5 `complete()` extended with optional `response_schema` parameter; §6 Response gained `parsed` field; §7 gained `structured_output_invalid` error category (non-transient by default); §8.5 structured output wire mapping added (with §8.5.1 prompt-augmentation fallback and §8.5.2 response mapping); §10 structured output deferral removed by [proposal 0016](../../proposals/0016-llm-provider-structured-output.md)
- §8 renamed from "OpenAI-compatible wire format" to "Wire-format mappings" and reorganized as a catalog of provider mappings; existing OpenAI-compatible body nested under new §8.1 "OpenAI-compatible mapping" (subsections §8.1 through §8.5 → §8.1.1 through §8.1.5); §8 framing paragraph added establishing the default placement rule (in-spec for any mapping with multi-language ambition; out-of-tree allowed only for single-language / opt-out / experimental cases) by [proposal 0019](../../proposals/0019-llm-provider-multi-provider-extension.md)
- §5 `complete()` extended with optional `tool_choice` parameter (four modes: `"auto"` / `"required"` / `"none"` / `{type: "tool", name: X}`) with pre-send validation routing through `provider_invalid_request`; §7 clarified to enumerate the three new validation failure modes; §8.1.1 gained a `tool_choice` mapping row by [proposal 0025](../../proposals/0025-llm-provider-tool-choice.md)
- §8 framing gained a *Per-mapping subsection structure* paragraph recommending the canonical §8.X template (Request mapping / Response mapping / Error mapping / Concurrency / Structured output) with allowance for sub-subsections, provider-specific top-level additions, and SHOULD-level divergence-explanation requirement; resolves 0019's open-question #2 by [proposal 0026](../../proposals/0026-llm-provider-wire-format-mapping-template.md)
- §6 `RuntimeConfig` extended with three new declared fields (`frequency_penalty`, `presence_penalty`, `stop_sequences`) matching the cross-vendor OpenTelemetry GenAI semconv naming; existing "MAY accept additional provider-specific fields" line replaced with an explicit extras-pass-through contract (undeclared fields MUST reach the wire untouched) and a null-skip contract (declared fields with `None` MUST be omitted from the wire body); §8.1 OpenAI-compatible mapping extended to cover the three new declared-field mappings (with `stop_sequences` → OpenAI body `stop` rename) and formally specify undeclared-field placement at the OpenAI request-body root by [proposal 0032](../../proposals/0032-llm-provider-runtime-config-refinements.md)
- §8.2 Anthropic Messages wire-format mapping added (sibling to §8.1) with §8.2.1 request mapping / §8.2.1.1 content-block mapping (including spec `ThinkingBlock` round-trip and §3 opaque `signature` field) / §8.2.1.2 tool-result content blocks / §8.2.2 response mapping / §8.2.3 error mapping; §3 Message gained opaque `signature` fields on `TextBlock` / `ThinkingBlock` / `ToolCall` for round-trip preservation of provider-side reasoning signatures by [proposal 0037](../../proposals/0037-llm-provider-anthropic-messages-mapping.md)
- §8.3 Google Gemini wire-format mapping added (sibling to §8.1 / §8.2) with §8.3.1 request mapping / §8.3.1.1 parts wire mapping (including thought-summary capture into `ThinkingBlock.text` and `thoughtSignature` round-trip into the §3 opaque `signature` field) / §8.3.1.2 `tool` role bidirectional translation / §8.3.2 response mapping / §8.3.3 error mapping; undeclared `RuntimeConfig` fields nest under Gemini's `generationConfig` (not the request root) to match Gemini's parameter location by [proposal 0038](../../proposals/0038-llm-provider-google-gemini-mapping.md)
- §6 `Response.usage` extended with two optional fields (`cached_tokens?` for prefix-cache hit input tokens, `cache_creation_tokens?` for input tokens written to the cache during the call); §8 framing gained an *Intra-impl wire-byte stability* paragraph (canonical sorted-key serialization of JSON-schema, content-block, and RuntimeConfig-extras payloads — within a single implementation; cross-impl byte equality is non-normative); per-mapping *Wire-byte stability* sub-paragraphs added to §8.1.1 / §8.2.1 / §8.3.1 anchoring the rule to that mapping's payloads; §8.1.2 gained cache-stat source rows (`usage.cached_tokens` ← `usage.prompt_tokens_details.cached_tokens` with the OpenAI Responses API alternate path and a vLLM dual-flag caveat; `cache_creation_tokens` left absent for OpenAI); §8.2.2 gained the Anthropic-implicit-not-supported caveat (Anthropic implicit-cache fields left absent because Anthropic only supports explicit `cache_control`-driven caching, out of scope for §6's implicit-cache surface); §8.3.2 maps `usage.cached_tokens` ← Gemini's `usageMetadata.cachedContentTokenCount` (Gemini 2.5+ implicit caching) by [proposal 0047](../../proposals/0047-implicit-prefix-cache-wire-stability.md)
- §5 `complete()` signature extended with an optional `retry` kwarg accepting an instance of pipeline-utilities §6.1's retry middleware configuration record (or `None` / absent default preserving the v0.4.0 no-retry behavior); the "does NOT retry" operation-semantics bullet amended to note retry policy lives at the per-node layer (pipeline-utilities §6.1) OR the per-call layer (this kwarg per §7.1); new §7.1 *Call-level retry* sub-section defining the in-call retry loop semantics (transient classification reuses §6.1's default categories, backoff reuses §6.1's exponential-with-jitter default, cancellation propagation rule preserved, per-attempt span emission produces N spans for N attempts), reuses the §6.1 framework-agnostic four-field configuration record (cross-spec reference direction is the inverse of §6.1's existing dependency on §7 transient categories — bidirectional acceptable because the shared record is framework-agnostic), plus a *Two-level retry lane separation* table comparing per-call vs per-node layers and a *Common mistakes* list (multiplicative budget pitfall `3 × 5 × 3 = 45` worst-case, inline try/except defeating per-attempt attribution, classifier widening to mask real errors) by [proposal 0050](../../proposals/0050-retry-and-degradation-primitives.md)
- §5 `complete()` gained an optional `stream` flag (default off; return type unchanged — still `Response`), a *Streaming* rule (consume the wire incrementally + emit per-chunk `LlmTokenEvent`s; observably identical to the atomic path when no observer is attached), and a *Provider streaming support* rule (a mapping without streaming rejects `stream`-set calls with `provider_invalid_request`); §6 gained a *Streaming assembly* contract (content concatenation, reasoning-block assembly, tool-call-delta reassembly, terminal usage / finish_reason, structural identity with the atomic path); §8.1 gained §8.1.6 *Streaming* (OpenAI-compatible SSE: `stream_options.include_usage`, `[DONE]`, content / tool-call deltas, and the OpenAI-compatible reasoning-delta extension recognizing both `reasoning_content` and `reasoning`); §10 *Out of scope* lifted the blanket streaming deferral, replaced by narrower deferrals (node-body iterator consumption, tool-call-delta token events, Anthropic / Gemini streaming wire, non-completion streaming) by [proposal 0062](../../proposals/0062-llm-completion-streaming.md)
- §5 `complete()`'s `retry` parameter extended to also accept an llm-provider retry-config (a superset of the pipeline-utilities §6.1 four-field record adding two optional fields); new §7.1 *Adaptive extensions (opt-in)* defining `per_attempt_override` — a declarative retry override schedule (attempt 0 uses the base `config`; the *i*-th override applies to retry *i*; a general `RuntimeConfig` partial merged onto base; last entry carries forward) — and `reask` — a caller-supplied corrective-message builder that makes `structured_output_invalid` retryable-for-this-call and, on each such failure, appends the model's raw output as an `assistant` message plus the builder's returned content as a `user` message to a working transcript that accumulates across reask retries (keeping the sequence role-alternating; the builder receives 0082's `output_content` + `error_message`; the implementation authors no prompt of its own, per charter §3.1 principle 7 *No built-in prompts*; reask reuses the `max_attempts` budget); the §7.1 per-attempt span gains an `openarmature.llm.retry_reason` (`transient` | `reask`) attribute on retry attempts; the *Common mistakes* classifier-widening bullet points `structured_output_invalid` at `reask` by [proposal 0095](../../proposals/0095-adaptive-call-level-retry.md)
- §7 gains **Malformed usage counter** — a `Response.usage` counter that is present on the wire but malformed (a non-integer, a negative, a boolean) is treated as **not reported**, the per-field `null` §6 already permits: that counter is `null` and the others stand (§6's "the first three MUST be `null` together" is conditioned on *no* usage being reported, which a partially-malformed record does not satisfy). It MUST NOT raise `provider_invalid_response` (or any category) because of the counter — a genuine §6-shape parse failure still raises — and MUST NOT be fabricated, coerced, clamped, or repaired; the verbatim value stays on `Response.raw`. A **derived** `total_tokens` (§8.2) whose addend is not reported is itself `null`, never the surviving addend. §6's streaming `raw` assembly MUST preserve the terminal chunk's usage verbatim. This is a **reversal**: composing §6's "non-negative integer or `null`" counter type with §7's "cannot be parsed into the §6 shape" reservation, a strict implementation today raises on `"abc"`; from this version it MUST NOT. Reconciled across the surfaces a null counter renders through (graph-engine §6 `LlmCompletionEvent.usage` mirrors the response; observability §5.5.3 / §11.2 / §5.5.15 / §8.4.3 omit rather than emit / sum / compare / divide over a not-reported counter) by [proposal 0101](../../proposals/0101-malformed-usage-counter-llm-observability.md)
- §6 *Extras pass-through* gains a **Managed-field collision** clause (inherited by retrieval-provider §10) — a bounded carve-out to untouched pass-through when an undeclared extras key names a wire field the mapping **manages** (sets for its own correctness / response consumer / a mapping-level contract; each §8.x mapping MUST enumerate its managed keys). An additive / list-shaped managed field **merges** the caller's value(s) with the mapping's (deterministic order, mapping-first, de-duplicated); a **non-additive** managed field — a scalar mode-switch **or an object the mapping constructs wholesale**, whose value is mutually exclusive with the caller's — takes a matching extras value as a redundant no-op and **rejects a conflicting one pre-send** `provider_invalid_request`, never silently dropping or overriding. A field the mapping produces only **conditionally** is managed only while it is producing it. Every unmanaged undeclared key keeps untouched pass-through. Generalizes 0099's mapping-local `embedding_types` exception. The OpenAI mapping (§8.1) enumerates its managed keys: the **structural** wire-root fields `model` / `messages` / `tools` / `tool_choice` (set for the mapping's own correctness — an override would silently replace the caller's conversation / tool set / bound model), and two **conditionally-managed non-additive** object fields — §8.1.5 `response_format` (managed while the mapping is producing it, i.e. the native structured-output path; unmanaged on a free-form call or the §8.1.5.1 fallback) and §8.1.6 `stream_options` (managed while streaming) — each a *reject*-arm key. The `stop` / `stream` wire fields (realizations of the declared `stop_sequences` / `complete(stream=…)`) and §8.2 `task` / §8.3 `encoding_format` are the *declared-field-vs-extras* residual, deferred to a follow-on by [proposal 0105](../../proposals/0105-extras-managed-field-collision-rule.md)
