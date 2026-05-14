# 0016: LLM Provider — Structured Output

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-13
- **Accepted:** 2026-05-14
- **Targets:** spec/llm-provider/spec.md (modifies §5 *Provider interface*; modifies §6 *Response and configuration*; modifies §7 *Error semantics*; adds §8.5 *Structured output wire mapping*; modifies §10 *Out of scope*)
- **Related:** 0006 (LLM provider core)
- **Supersedes:**

## Summary

Extend the existing `complete()` operation with an optional `response_schema` parameter that
constrains the model's output to a caller-supplied JSON Schema. Augment `Response` with a
`parsed` field that carries the validated structured value when `response_schema` was
supplied. Introduce a new error category `structured_output_invalid` (non-transient by default)
for the case where the model's output cannot be parsed or validated against the requested
schema. Specify the OpenAI wire mapping for structured output via `response_format`, with
prompt-augmentation-plus-post-parse as a fallback for providers that do not natively
support it.

## Motivation

§10 of v0.4.0 defers structured output: "JSON mode, schema-constrained decoding,
response_format." That deferral was correct at v1 scope — the v1 surface was tool calling,
canonical errors, and the OpenAI wire mapping. But every meaningfully-typed LLM pipeline ends
up needing structured output, and the absence of a framework primitive forces every node to
re-implement the same render/call/parse/validate/retry loop in user code.

The boilerplate today, replicated across every LLM-calling node that produces typed output:

1. Render the prompt with whatever JSON-shape directive the user has standardized on.
2. Call `complete()`.
3. Parse the response content as JSON.
4. Validate the parsed JSON against the user's schema declaration.
5. On parse or validation failure, retry with adjusted parameters (commonly `max_tokens` is
   doubled, sometimes the system message is augmented with a stricter directive).
6. On second failure, give up or split the input.

Steps 3–6 are identical across nodes; only the schema and prompt differ. Folding this into
the Provider interface lets users declare the expected shape once and rely on the framework
to either (a) use the provider's native structured-output path (OpenAI's `response_format`,
Anthropic's tool-as-schema convention, Gemini's `responseSchema`) where the model produces
schema-compliant output on the wire in one trip, or (b) fall back transparently to the
prompt-augmentation-plus-post-parse shape for providers that lack native support.

The Provider-level placement matters. A middleware-level structured-output wrapper can only
operate on the response after `complete()` has returned a string — it cannot reach the wire
to use native structured-output features, so it pays the round-trip cost of an unstructured
call and a post-parse retry even when the model could have produced schema-compliant output
on the first try. Provider-level placement opens the native path; userland middleware
patterns remain buildable on top for users who want them.

The single-method shape (parameter on `complete()` rather than a separate
`complete_structured()` method) matches the industry pattern across major LLM SDKs (OpenAI,
Anthropic, Gemini, Instructor) and keeps the Provider Protocol surface small. The shape
discussion is recorded in *Alternatives considered*.

## Detailed design

### §5 Provider interface: extend `complete()` with `response_schema`

Amend the existing `complete()` operation in §5 to accept an optional `response_schema`
parameter. The full updated signature (described abstractly; per-language ergonomics decide
positional-vs-keyword conventions):

#### `complete(messages, tools=None, config=None, response_schema=None)`

Async. Performs a single completion call. When `response_schema` is supplied, the call
additionally constrains the model's output to conform to the schema.

- `messages` — non-empty ordered sequence of messages. Constraints unchanged: the first
  message MAY be `system`; the last message MUST be `user` or `tool`. Violations raise
  `provider_invalid_request` (§7).
- `tools` — optional ordered sequence of `Tool` records. Constraints unchanged.
- `config` — optional `RuntimeConfig` (§6). Constraints unchanged.
- `response_schema` — optional JSON Schema describing the expected output shape. When
  `None` / absent, the call behaves as in v0.4.0: free-form text content; no parsed value.
  When present, MUST be a valid JSON Schema. The top-level schema MUST be an object schema
  (`type: "object"` at the root) — this matches §4 `Tool.parameters` and OpenAI's
  strict-mode wire format. Non-object top-level schemas are out of scope for this proposal;
  a follow-on MAY relax this if cross-provider demand warrants. Implementations SHOULD
  validate at call time. The JSON Schema convention matches §4 — see §4's note on
  language-native schema constructors compiling to JSON Schema.

Returns: a `Response` (§6).

When `response_schema` is set and the model returns content (not tool calls):

- `Response.parsed` is the parsed-and-validated structured value per `response_schema`.
- `Response.message.content` is the JSON-serialized string form of the structured output.

When `response_schema` is set and `finish_reason` is `"tool_calls"`, `Response.parsed`
MUST be absent regardless of whether `message.content` is also populated (the existing §3
contract allows assistant messages to carry both `tool_calls` and non-empty `content`, and
this proposal does not change that). `message.content` preserves the model's output
verbatim per §6; the parsed slot only populates when the model returned structured content
(typically `finish_reason: "stop"`).

When `tools` and `response_schema` are both supplied, the model decides which path to
take, signaled by `finish_reason`. If `finish_reason` is `"tool_calls"`, the user handles
tool execution and may make a follow-on `complete()` (per §5); if `finish_reason` is
`"stop"`, the user reads `parsed` and/or `message.content`.

When `response_schema` is `None` / absent, `Response.parsed` is absent regardless of
content. The v0.4.0 behavior is preserved exactly.

Operation semantics (unchanged from v0.4.0 except where structured output augments them):

- `complete()` MUST NOT mutate `messages`, `tools`, `config`, or `response_schema`.
- `complete()` MUST be reentrant.
- `complete()` does NOT loop on tool calls.
- `complete()` does NOT retry on transient errors.
- When `response_schema` is set and the model produces output that successfully parses as
  JSON but fails to validate against `response_schema`, OR fails to parse as JSON at all,
  `complete()` raises `structured_output_invalid` (§7).

### §6 Response: add `parsed` field

Amend the §6 `Response` record by adding one field:

| Field | Description |
|---|---|
| `parsed` | The parsed and validated structured value when the call supplied a `response_schema` and the model returned structured content. The value conforms to the supplied `response_schema`. Absent (`null` / `None` / `undefined`, per the language's idiom) on calls that did not supply a `response_schema`, and on responses whose `finish_reason` is `"tool_calls"` (regardless of whether `message.content` is also populated, per the §3 assistant-message contract). |

The `parsed` field is the language-idiomatic deserialized form of the structured value
(e.g., a Python `dict[str, Any]` populated per the JSON Schema, or a TypeScript `unknown`
typed at the call site via a generic). Implementations MAY offer ergonomic typed accessors
on top (e.g., Python users supplying a Pydantic model class instead of a raw JSON Schema and
receiving a validated model instance, surfaced via per-language overloads or generics so
that the static type of `parsed` reflects the supplied schema) — those are per-language
ergonomics, not normative spec.

`message.content` carries the provider's content string preserved verbatim — the bytes the
model returned, UTF-8 decoded. Implementations MUST NOT re-serialize `parsed` back into
`message.content`; doing so would mask formatting differences (whitespace, key ordering,
number representation) and break conformance assertions that rely on byte-level
equivalence. `parsed` and `message.content` MUST be consistent in the following sense:
deserializing `message.content` as JSON and validating against `response_schema` produces
`parsed`. The reverse operation (serializing `parsed` and comparing) is NOT required to
round-trip bytewise, because the model's serialization may differ from the framework's.

When `finish_reason: "tool_calls"`, `parsed` is absent regardless of whether
`response_schema` was supplied. The tool-call path and the structured-content path are
mutually exclusive at the response level.

### §7 Error semantics: add `structured_output_invalid`

Add to the §7 canonical error list:

- `structured_output_invalid` — `complete()` was called with a `response_schema`, and the
  provider returned content that could not be parsed as JSON OR did not validate against
  the supplied schema. The error MUST expose:
  - the `response_schema` that was requested,
  - the raw response content (the bytes the model produced),
  - a description of the validation or parse failure (the wrapped exception's message, the
    failing JSON Pointer, or the language's idiomatic equivalent).

  **Non-transient by default.** A model that fails to produce schema-compliant output on a
  given prompt usually fails the same way on retry; retrying without changing the prompt,
  model, or schema is unlikely to succeed. Users who want retry-on-validation-failure
  semantics MAY include `structured_output_invalid` in a pipeline-utilities
  `RetryMiddleware` classifier's transient set, but the category is NOT transient by
  default at the spec level.

Update the retry classification paragraph at the end of §7 to add
`structured_output_invalid` to the *non-transient* list alongside `provider_authentication`,
`provider_invalid_model`, `provider_invalid_request`, and `provider_invalid_response`.

The category is distinct from `provider_invalid_response`. `provider_invalid_response`
covers "the provider's wire response is malformed per §6 shape" (the wire envelope is
broken). `structured_output_invalid` covers "the wire envelope is fine; the content the
provider returned does not validate against the caller's `response_schema`." Both are
non-transient, but they have different remediation paths (one is a provider bug; the other
is a model output that needs prompt or schema adjustment).

### §8.5 Structured output wire mapping (new subsection)

Add a new subsection §8.5 to the OpenAI-compatible wire format chapter:

#### 8.5 Structured output

When `complete()` is called with a `response_schema`, the OpenAI-compatible request body
includes a `response_format` field:

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
SHOULD derive a stable identifier from the schema (e.g., a hash, or the schema's `title`
field when present). The `strict: true` flag enables OpenAI's schema-constrained decoding
path; implementations SHOULD pass `strict: true` when the supplied schema satisfies the
strict-mode constraints (no `additionalProperties: true`, all properties listed in
`required`, etc.), and SHOULD fall back to `strict: false` when the schema does not satisfy
the constraints. The behavioral contract at the spec layer is identical regardless of
`strict`: validation happens post-receive against `response_schema`; failures raise
`structured_output_invalid`.

When `complete()` is called without `response_schema` (or with `response_schema=None`), the
request body MUST NOT include `response_format`. The v0.4.0 wire shape is preserved
unchanged for free-form calls.

#### 8.5.1 Fallback for providers without native structured output

OpenAI-compatible servers that do not implement `response_format` (older vLLM versions, some
LM Studio releases, some local-server wrappers) raise an error or silently ignore the field.
Implementations SHOULD detect this — either statically (via provider capability metadata) or
dynamically (a first-call attempt that returns an error) — and fall back to a
prompt-augmentation strategy:

1. Construct a modified copy of the message list with a system directive appended (or
   with the existing system message's content extended) instructing the model to return
   only valid JSON matching the `response_schema`. The directive SHOULD include the
   schema serialized as part of the prompt. The caller's original `messages` list MUST
   be left unchanged — the §5 mutation rule applies to fallback paths the same as
   native paths.
2. Issue the underlying request without `response_format`.
3. Parse and validate the response content against `response_schema` per §6 `parsed`.
4. On validation failure, raise `structured_output_invalid` per §7.

Fallback behavior is implementation-defined. Implementations MUST document whether
`complete()` with `response_schema` uses native `response_format` or prompt-augmentation,
and SHOULD expose a way for callers to inspect or override the path chosen.

#### 8.5.2 Response mapping

When the response carries structured content (not tool calls):

- `message.content` is the response body's content string, verbatim.
- `parsed` is the deserialization of `message.content` against `response_schema`.
- `finish_reason` is mapped per §8.2 (typically `"stop"`).

When the response carries tool calls instead, the mapping follows §8.2 unchanged: `parsed`
is absent, `tool_calls` is populated, `finish_reason` is `"tool_calls"`.

### §10 Out of scope: structured output removed

Remove the existing §10 entry:

> - **Structured output** — JSON mode, schema-constrained decoding, response_format.

This proposal's §5 / §6 / §7 / §8.5 amendments collectively cover the deferred capability.
The remaining §10 entries (streaming, audio/video, token counting, provider-native wire
formats, agent loop, retry/rate-limit, prompt template rendering, embeddings) are unchanged.

### Cross-spec touchpoints

This proposal does not modify graph-engine, pipeline-utilities, or observability.

Observability §5.5 (`llm.model`, `llm.finish_reason`, `llm.usage.*`) is unchanged. A
follow-on observability proposal MAY surface `structured_output_invalid` failures with
additional attributes (the failing JSON Pointer, the schema name, etc.), but the existing
span attributes already capture the call's basic identity.

A userland `StructuredOutputMiddleware` (an earlier alternative — see *Alternatives
considered*) remains buildable on top of the existing pipeline-utilities §6 middleware seam
for callers who want it. The single-method extension does NOT preclude that pattern; it
just makes it unnecessary in the common case.

## Conformance test impact

Add fixtures under `spec/llm-provider/conformance/`. Each fixture is a pair
(`NNN-name.yaml` + `NNN-name.md`) per the conformance README:

- **`018-structured-output-success.yaml`** — `complete()` with a simple object schema
  passed as `response_schema`; provider returns valid JSON matching the schema. Assert:
  - returned `Response.parsed` is the parsed value (deep-equal to the expected
    deserialization);
  - `Response.message.content` is the JSON-serialized form;
  - `Response.parsed` and `Response.message.content` are consistent under
    `response_schema`;
  - `finish_reason` is `"stop"`.
- **`019-structured-output-parse-failure.yaml`** — provider returns content that is not
  valid JSON (truncated, syntactically invalid). Assert `complete()` raises
  `structured_output_invalid`; the error exposes the schema, raw content, and a
  parse-failure description.
- **`020-structured-output-validation-failure.yaml`** — provider returns valid JSON that
  fails to validate against `response_schema` (missing required field, type mismatch).
  Assert `complete()` raises `structured_output_invalid`; the error description
  identifies the failing field.
- **`021-structured-output-non-transient.yaml`** — verify retry classification: an
  unwrapped `RetryMiddleware` (per pipeline-utilities §6.1) with the default classifier
  does NOT retry `structured_output_invalid` (the category is non-transient by default).
- **`022-structured-output-with-tool-calls.yaml`** — `complete()` called with both
  `tools` and `response_schema` populated; provider returns `tool_calls` instead of
  structured content. Assert `Response.parsed` is absent,
  `Response.message.tool_calls` is populated, `finish_reason` is `"tool_calls"`.
- **`023-structured-output-openai-wire-mapping-native.yaml`** — assert the outbound HTTP
  request to an OpenAI-compatible endpoint carries the
  `response_format: { type: "json_schema", json_schema: { name, schema, strict } }` shape
  with the spec's `response_schema` passed verbatim under `json_schema.schema`.
- **`024-structured-output-openai-wire-mapping-fallback.yaml`** — provider configured to
  reject native `response_format`; assert the implementation falls back to
  prompt-augmentation + post-parse, the response is still validated against
  `response_schema`, and the final `Response.parsed` is populated identically to the
  native path.
- **`025-structured-output-no-schema-regression.yaml`** — regression: a `complete()`
  call without `response_schema` produces a `Response` with `parsed` absent, even when
  the model would have produced JSON-looking content. The wire shape MUST NOT include
  `response_format`. The v0.4.0 behavior is preserved exactly when `response_schema` is
  not supplied.

## Alternatives considered

### Option A — Middleware-level (`StructuredOutputMiddleware`)

An earlier alternative recommended a canonical middleware that ships alongside
`RetryMiddleware` and `TimingMiddleware`. The middleware would read the inner node's raw
response from a designated state field, attempt JSON parse + validation against a declared
schema, and either pass the validated value through or raise a transient
`structured_output_invalid` so RetryMiddleware retries automatically.

Rejected because:

1. **Middleware can't reach the wire.** Native structured-output support (OpenAI strict
   mode, Anthropic tool-as-schema, Gemini responseSchema) lives at the provider boundary.
   A middleware operating on the post-`complete()` partial update has already paid the
   round-trip cost of an unstructured call; it can't engage the native one-trip path. For
   the major providers in 2026, this is a meaningful cost.
2. **State-field coupling.** The middleware would need to know which state field carries
   the raw response (`llm_response_raw`, `claim_draft_raw`, etc.) and which receives the
   parsed value. That's per-node naming convention being lifted into a canonical
   middleware's configuration, which couples the middleware to per-graph state-schema
   choices.
3. **Pipeline-utilities cross-cutting concerns.** RetryMiddleware and TimingMiddleware are
   genuinely cross-cutting (anything can fail; anything has duration). Structured output
   is a per-call concern about the provider's wire path, not a cross-cutting concern about
   node execution.

Userland middleware around `complete()` remains buildable for users who want
middleware-style composition. This proposal does not preclude that pattern — it just
doesn't make it the canonical shape.

### Option B alternative — Separate `complete_structured()` method

An earlier draft of this proposal split structured output into a distinct
`complete_structured()` method on the Provider Protocol, parallel to `complete()` and
`ready()`. The argument was that the return shape differs (presence of `parsed`) enough to
justify a distinct surface.

Rejected because:

1. **Industry pattern is single-method.** Every major LLM SDK in 2026 (OpenAI, Anthropic,
   Gemini, Instructor, LiteLLM) exposes structured output as a parameter on the existing
   completion method (`response_format`, `response_schema`, `response_model`), not as a
   separate method. A two-method Provider interface would be unusual and would surprise
   anyone porting from another SDK.
2. **Wrapper composition.** Wrappers around `Provider` (logging, mocking, observability,
   caching) write one wrapper, not two. Splitting structured output into a second method
   doubles the wrapper surface for no payoff.
3. **Implementation duplication.** Most of the implementation is shared between
   "structured and free-form completions"; the two-method form would expose that as two
   thin variants over a shared core.
4. **Surface growth.** If future modes appear (audio output, multi-response, etc.), the
   single-method form scales by adding parameters; the two-method form would push toward
   N methods.

The weak counter-argument for two methods is static typing: a separate
`complete_structured()` returning `StructuredResponse[T]` could be statically distinct
from `complete()` returning `Response`. Single-method recovers most of this via
per-language overloads (Python `@overload`, TypeScript conditional types on the schema
parameter) without splitting the Protocol. The spec doesn't mandate the per-language
typing approach; it mandates the behavioral contract.

### Bundle `response_schema` semantics as required (no opt-out)

Considered briefly: make `response_schema` a required parameter of `complete()` and
always validate output. Rejected — free-form text is the dominant call shape (chat
assistants, narrative responses, summaries). Requiring a schema would force
`{"type": "string"}` boilerplate at every free-form call site and would push the model
into schema-fitting output style even for prose.

### Schema-language flexibility (Pydantic / Zod / attrs as alternative inputs)

Considered: spec accepts a "schema declaration" abstractly and lets implementations decide
how to interpret it (Pydantic class, Zod schema, raw JSON Schema). Rejected because the
wire format is JSON Schema regardless — accepting other forms just pushes the
JSON-Schema-derivation step inside the implementation. The spec mandates JSON Schema
(matching §4 `Tool.parameters`); implementations are free to offer ergonomic constructors
that compile from native types to JSON Schema. This is the same shape §4 took for tools
and has held up well.

### Transient-by-default error classification

An earlier draft of this proposal classified `structured_output_invalid` as transient by
default, so `RetryMiddleware` would retry without user configuration. Rejected because:

- A model that produces non-schema-compliant output on a given prompt usually produces
  the same non-compliant output on the next attempt (the model is sampling from
  approximately the same distribution given the same context). The retry burns tokens
  without improving outcomes.
- Genuinely useful retry-on-validation-failure logic typically involves modifying the
  prompt (adding a more emphatic directive, including the validation error as feedback,
  doubling `max_tokens` to recover from truncation). That's not "retry the same call" —
  it's "retry a different call." Spec-level transient-by-default would make the
  no-op-retry case the default, which is the worst of both worlds.
- Users who want naive retry can configure their RetryMiddleware classifier to include
  `structured_output_invalid` in its transient set. The classifier-driven model already
  exists per pipeline-utilities §6.1; the new category just isn't transient by default.

### Add a `parsed` accessor on `Message` instead of `Response`

Considered: put `parsed` on `Message` (alongside `content`, `tool_calls`,
`tool_call_id`) rather than on `Response`. Rejected because the parsed value is a
per-call artifact derived from a specific schema — it's not an intrinsic property of the
message that would persist if the message were later re-sent or stored. Keeping `parsed`
on `Response` ties it to the specific call boundary where the schema was supplied.

## Open questions

None at time of submission.
