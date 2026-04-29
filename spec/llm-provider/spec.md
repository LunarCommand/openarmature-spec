# LLM Provider

Canonical behavioral specification for the OpenArmature LLM provider abstraction.

- **Capability:** llm-provider
- **Introduced:** spec version 0.4.0
- **History:**
  - created by [proposal 0006](../../proposals/0006-llm-provider-core.md)

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
| `content` | conditional (see below) | Text content of the message. |
| `tool_calls` | only on `assistant` | Ordered list of `ToolCall` records the model is requesting. |
| `tool_call_id` | required on `tool` | The `id` of the matching `assistant` tool call. |

Per-role constraints:

- `system`: `content` MUST be a non-empty string. `tool_calls` MUST be absent. `tool_call_id` MUST be
  absent.
- `user`: `content` MUST be a non-empty string. `tool_calls` MUST be absent. `tool_call_id` MUST be
  absent.
- `assistant`: `tool_calls` MAY be present. If `tool_calls` is present and non-empty, `content` MAY
  be empty (the assistant is purely calling tools); if `tool_calls` is absent or empty, `content`
  MUST be a non-empty string. `tool_call_id` MUST be absent.
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

### `complete(messages, tools=None, config=None)`

Async. Performs a single completion call.

- `messages` — non-empty ordered sequence of messages. The first message MAY be `system`; otherwise
  the message list begins with `user`. The last message before the call MUST be `user` or `tool` (the
  request to the model). Implementations MUST validate this ordering; violations raise
  `provider_invalid_request` (§7).
- `tools` — optional ordered sequence of `Tool` records. When present and non-empty, the model is
  permitted to return `tool_calls`. Tool names MUST be unique within the list.
- `config` — optional `RuntimeConfig` (§6). Per-call sampling parameters and budget hints.

Returns: a `Response` (§6).

Operation semantics:

- `complete()` MUST NOT mutate `messages`, `tools`, or `config`.
- `complete()` MUST be reentrant: multiple concurrent calls on the same provider are permitted.
  Implementations MUST NOT serialize concurrent calls internally.
- `complete()` does NOT loop on tool calls. If the response's `finish_reason` is `"tool_calls"`,
  the caller is responsible for executing the tools, appending `tool` messages, and making a
  follow-on `complete()`.
- `complete()` does NOT retry on transient errors. Errors propagate; retry policy belongs above this
  layer.

## 6. Response and configuration

A `Response` record:

| Field | Description |
|---|---|
| `message` | The assistant message returned by the model. Always `role: "assistant"`. May carry `tool_calls`. |
| `finish_reason` | One of `"stop"`, `"length"`, `"tool_calls"`, `"content_filter"`, `"error"`. See below. |
| `usage` | A record `{prompt_tokens, completion_tokens, total_tokens}`. Each field is a non-negative integer or `null`. If the provider does not report usage, all three MUST be `null`. |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Carries everything the provider returned — including fields the spec does not normalize (logprobs, content-filter details, provider-specific extensions). The normalized fields above are derived from `raw`; the two views MUST be consistent (modifying one does not affect the other, since both are immutable from the caller's perspective). |

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

A `RuntimeConfig` record:

| Field | Description |
|---|---|
| `temperature` | Float, optional. Provider-specific range; commonly `[0.0, 2.0]`. |
| `max_tokens` | Int, optional. Maximum completion tokens. |
| `top_p` | Float, optional. Nucleus sampling probability. |
| `seed` | Int, optional. Best-effort determinism for providers that support it. Setting `seed` does NOT guarantee determinism; see §9. |

Implementations MAY accept additional provider-specific fields. The four above are the minimum.

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
  tool names, etc.). This category is raised by the implementation's pre-send validation.

Each error MUST expose a `category` identifier (matching the strings above, as an error class, error
code, or tagged discriminant per the language's idiom). Provider-originated errors SHOULD preserve
the underlying provider exception as cause (`__cause__` in Python, `cause` in TypeScript).

These seven categories are the minimum required surface. Implementations MAY raise additional
provider-specific categories for cases not covered above; users MAY catch by category to implement
retry policy.

**Retry classification.** The categories `provider_unavailable`, `provider_rate_limit`,
`provider_model_not_loaded`, and `finish_reason: "error"` are *transient* — a retry MAY succeed.
The categories `provider_authentication`, `provider_invalid_model`, `provider_invalid_request`,
and `provider_invalid_response` are *non-transient* — retrying without changing the request will
not succeed.

## 8. OpenAI-compatible wire format

The OpenAI Chat Completions API (`POST /v1/chat/completions`) is the de facto standard for local
LLM servers (vLLM, LM Studio, llama.cpp) as well as the OpenAI hosted API itself. A provider
implementation MAY opt into an "OpenAI-compatible" label only if it implements the wire mapping
below.

### 8.1 Request mapping

The §3 message list maps onto the OpenAI `messages` field:

| Spec role | OpenAI role | Notes |
|---|---|---|
| `system` | `system` | Direct mapping. |
| `user` | `user` | Direct mapping. `content` is a string; OpenAI's content-array form is not used in v1. |
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

The §6 `RuntimeConfig` fields map directly: `temperature`, `max_tokens`, `top_p`, `seed`. The bound
model identifier becomes OpenAI's `model` field.

### 8.2 Response mapping

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

### 8.3 Error mapping

| OpenAI condition | Spec category |
|---|---|
| HTTP 401, 403 | `provider_authentication` |
| HTTP 404 with model-not-found body | `provider_invalid_model` |
| HTTP 503 with model-loading body | `provider_model_not_loaded` |
| HTTP 429 | `provider_rate_limit` |
| HTTP 5xx (other), connection error, timeout | `provider_unavailable` |
| HTTP 400 (malformed request, schema violation) | `provider_invalid_request` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

### 8.4 Concurrency

OpenAI-compatible servers vary in concurrency support — local servers may serialize internally,
hosted APIs do not. Implementations MUST NOT add a serialization layer; concurrent `complete()` calls
go to the wire concurrently. Providers that benefit from client-side concurrency limits use the
pipeline-utilities rate limiter or middleware, not this layer.

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
- **Multi-modal content** — image, audio, and video inputs and outputs.
- **Structured output** — JSON mode, schema-constrained decoding, response_format.
- **Token counting before the call** — tokenizer access for budget-aware prompt assembly.
- **Provider-native wire formats** — Anthropic Messages, Google Vertex, AWS Bedrock. Each adds a new
  §8-style mapping section to this spec via a follow-on proposal.
- **Agent loop** — tool-call-then-respond loops live in graph-engine nodes or a future agent-runner
  capability.
- **Retry and rate-limit policy** — pipeline-utilities concern.
- **Prompt template rendering** — prompt-management capability (charter §4.5).
- **Embeddings** — separate API surface; separate capability if/when needed.
