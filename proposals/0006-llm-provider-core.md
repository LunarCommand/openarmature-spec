# 0006: LLM Provider — Core Abstraction (OpenAI-Compatible)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-28
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (creates)
- **Related:** 0001
- **Supersedes:**

## Summary

Establish the foundational behavioral specification for the OpenArmature LLM provider abstraction:
typed message and tool-call shapes, a stateless `complete()` operation, a pre-flight `ready()` check,
canonical error categories, and a normative mapping onto the OpenAI Chat Completions wire format.
This is the first capability spec to address the LLM half of the charter's thesis ("LLM pipelines and
tool-calling agents") and is a prerequisite for tool-system, prompt-management, and evaluation
capabilities.

## Motivation

Three releases of the graph-engine (v0.1, v0.2, v0.3) have shipped without a single LLM-shaped
primitive. Graph-engine is content-agnostic by design — it knows about state, nodes, and edges, not
about models — but the charter's defining claim is "one framework for both deterministic LLM
pipelines and tool-calling agents." Until LLM calls have a defined shape, that claim is unbacked: any
two implementations could each ship a working graph-engine and then disagree completely on what an
LLM call looks like, leaving users to write provider-specific code in their nodes.

A provider abstraction is also the prerequisite for every later LLM-shaped capability:

- **Tool system / MCP** (charter §4.4) needs a `ToolCall` shape to translate tool definitions into
  whatever the provider expects, and to surface tool-call requests back as routable graph state.
- **Prompt management** (charter §4.5) produces `Message` sequences; the provider abstraction is what
  consumes them.
- **Evaluation** (charter §4.7) needs a stable provider call surface to record inputs and outputs
  against.
- **Pipeline-utilities retry middleware** (proposal 0004, in flight) needs canonical error categories
  to classify which errors are retryable.

Picking OpenAI-compatible as the v1 wire format is a pragmatic shortcut. The OpenAI Chat Completions
API (`/v1/chat/completions`) is the de facto standard for local LLM servers — vLLM, LM Studio,
llama.cpp, Bifrost, and Ollama-with-the-OpenAI-shim all implement it. A single OpenAI-compatible
provider implementation therefore covers most of the local development surface. Provider-native
shapes (Anthropic Messages API, Google Vertex, Bedrock) are deferred to follow-on proposals; each
adds a new wire-format mapping section to this same capability spec rather than a new abstraction.

Streaming, multi-modal content (images / audio), structured output / JSON mode, and pre-call token
counting are deferred. The minimum viable surface is stateless text-and-tools completion: enough to
build a working agent loop above.

## Detailed design

The full proposed text of `spec/llm-provider/spec.md` is reproduced below. It is written in
language-agnostic terms — Python and TypeScript map their own idioms (Pydantic vs. Zod, dataclasses
vs. interfaces) onto the behavioral contract described here.

The spec version under which this capability lands is determined at acceptance time and recorded in
`CHANGELOG.md`.

---

### 1. Purpose

The LLM provider capability defines a uniform request/response surface for sending messages to a
Large Language Model and receiving its response. It is the substrate every higher-level LLM
capability composes against — tool systems, prompt management, evaluation harnesses, agent loops.

The substrate is intentionally narrow:

- A provider is **stateless**. It does not maintain conversation history; the caller passes the full
  message list on every call.
- A provider does **not** loop on tool calls. If the assistant returns tool calls, the caller is
  responsible for executing the tools and making a follow-on `complete()` with the results.
- A provider does **not** handle retry, rate limiting, fallback, or routing. Those are pipeline-
  utilities concerns and compose above the provider via middleware (proposal 0004).
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

### 2. Concepts

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

### 3. Message shape

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

### 4. Tool definition

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

### 5. Provider interface

A provider MUST expose the following operations:

#### `ready()`

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

#### `complete(messages, tools=None, config=None)`

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

### 6. Response and configuration

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

### 7. Error semantics

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

These six categories are the minimum required surface. Implementations MAY raise additional
provider-specific categories for cases not covered above; users MAY catch by category to implement
retry policy.

**Retry classification.** The categories `provider_unavailable`, `provider_rate_limit`,
`provider_model_not_loaded`, and `finish_reason: "error"` are *transient* — a retry MAY succeed.
The categories `provider_authentication`, `provider_invalid_model`, `provider_invalid_request`,
and `provider_invalid_response` are *non-transient* — retrying without changing the request will
not succeed. Pipeline-utilities retry middleware (proposal 0004) consumes these categories.

### 8. OpenAI-compatible wire format

The OpenAI Chat Completions API (`POST /v1/chat/completions`) is the de facto standard for local
LLM servers (vLLM, LM Studio, llama.cpp, Bifrost) as well as the OpenAI hosted API itself. A
provider implementation MAY opt into an "OpenAI-compatible" label only if it implements the wire
mapping below.

#### 8.1 Request mapping

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

#### 8.2 Response mapping

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

#### 8.3 Error mapping

| OpenAI condition | Spec category |
|---|---|
| HTTP 401, 403 | `provider_authentication` |
| HTTP 404 with model-not-found body | `provider_invalid_model` |
| HTTP 429 | `provider_rate_limit` |
| HTTP 5xx, connection error, timeout | `provider_unavailable` |
| HTTP 400 (malformed request, schema violation) | `provider_invalid_request` |
| Successful HTTP response that fails to parse into §6 shape | `provider_invalid_response` |

#### 8.4 Concurrency

OpenAI-compatible servers vary in concurrency support — local servers may serialize internally,
hosted APIs do not. Implementations MUST NOT add a serialization layer; concurrent `complete()` calls
go to the wire concurrently. Providers that benefit from client-side concurrency limits use the
pipeline-utilities rate limiter or middleware, not this layer.

### 9. Determinism

LLM completions are not deterministic by default. Even with `temperature=0` and a fixed `seed`,
identical inputs MAY produce different outputs across calls or across deployments of the same
provider (different model weight versions, different infrastructure, different sampling
implementations).

The spec therefore makes no determinism guarantees for `complete()`. The conformance suite uses
**mock providers** that return canned responses; live-provider tests are out of scope.

For `ready()`: implementations MUST return successfully when the provider is reachable and the
model exists, and raise the appropriate §7 category otherwise. This is testable deterministically
against a mock or stub HTTP server.

### 10. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Streaming responses** — incremental delivery of assistant content and tool calls.
- **Multi-modal content** — image, audio, and video inputs and outputs.
- **Structured output** — JSON mode, schema-constrained decoding, response_format.
- **Token counting before the call** — tokenizer access for budget-aware prompt assembly.
- **Provider-native wire formats** — Anthropic Messages, Google Vertex, AWS Bedrock. Each adds a new
  §8-style mapping section to this spec via a follow-on proposal.
- **Agent loop** — tool-call-then-respond loops live in graph-engine nodes or a future agent-runner
  capability.
- **Retry and rate-limit policy** — pipeline-utilities concern (proposal 0004).
- **Prompt template rendering** — prompt-management capability (charter §4.5).
- **Embeddings** — separate API surface; separate capability if/when needed.

## Conformance test impact

Add a new conformance directory `spec/llm-provider/conformance/` with the following fixtures. The
shape mirrors graph-engine conformance: a YAML pair (input + expected) plus a markdown description.
All fixtures use a **mock provider** the implementation supplies for testing — the conformance suite
does not call live APIs.

1. **`001-basic-completion`** — `[system, user]` → mock provider returns assistant text → `Response`
   has `message.role == "assistant"`, `content` populated, `finish_reason == "stop"`, no
   `tool_calls`. Verifies the minimal happy path.

2. **`002-tool-call-roundtrip`** — `[user]` with one `Tool` defined → mock provider returns
   assistant `tool_calls` (with a non-trivial id, e.g., `call_abc123_with_underscores`) → caller
   appends `tool` message → second `complete()` with full history → mock returns final assistant
   text with `finish_reason == "stop"`. Verifies the call / tool-result / call shape, the
   `tool_call_id` matching, and that the tool-call `id` is preserved verbatim through the second
   `complete()` (no rewriting, normalization, or stripping).

3. **`003-message-validation`** — table of malformed inputs (system message in middle of list, tool
   message without preceding assistant tool_call, duplicate tool names, empty content where required)
   → each MUST raise `provider_invalid_request` before any wire call.

4. **`004-error-categories`** — table of mock provider failures → each maps to the documented §7
   category. Cases: 401 → `provider_authentication`; 404+model-not-found →
   `provider_invalid_model`; 503 with model-loading body (or vLLM-style `model_not_loaded` payload)
   → `provider_model_not_loaded`; 429 → `provider_rate_limit`; 5xx → `provider_unavailable`;
   malformed-but-200 → `provider_invalid_response`.

5. **`005-openai-wire-mapping`** — table of round-trip cases: spec `Message` / `Tool` /
   `RuntimeConfig` → OpenAI request JSON → spec `Response`. Verifies the §8 mapping
   bidirectionally. Includes a case where the OpenAI response carries a provider-specific extension
   (e.g., `choices[0].logprobs`); verifies `Response.raw` carries it verbatim while normalized
   fields are unchanged. Implementations MAY use a stub HTTP server or a translation function
   exposed for testing.

6. **`006-usage-accounting`** — mock provider returns a response with `usage` populated; another
   mock returns `usage: null`. Verifies `Response.usage` carries integers in the first case and
   `null` in all three subfields in the second.

7. **`007-ready-check`** — table of `ready()` outcomes against a stub server: 200 with model
   listed AND loaded → success; 200 with model listed but not yet loaded →
   `provider_model_not_loaded`; 401 → `provider_authentication`; 404 with no matching model →
   `provider_invalid_model`; network failure → `provider_unavailable`. Verifies the stronger
   `ready()` contract: a successful return implies the next `complete()` is expected to succeed.

8. **`008-error-finish-reason-with-malformed-tool-calls`** — mock provider returns a 200 response
   with `finish_reason: "error"` and a `tool_calls` array containing: one valid tool call with
   parseable schema-conforming arguments, one with parseable JSON that does not conform to the
   tool's parameters schema, and one with truncated/invalid JSON in the arguments string.
   Verifies:
   - `complete()` does NOT raise (`finish_reason: "error"` is a degraded but parseable response,
     not a request-level failure).
   - `Response.message.tool_calls` has all three entries.
   - The valid call's `arguments` is a parsed mapping; the schema-violating call's `arguments` is
     a parsed mapping (no schema enforcement under `error`); the truncated-JSON call's
     `arguments` is `null`.
   - `Response.raw` carries the full original response, including the truncated-JSON arguments
     bytes verbatim — application code can repair from there.

The conformance harness in each implementation supplies a mock-provider adapter that loads a fixture,
runs the operation, and asserts against the YAML's expected block. The fixtures themselves contain
no live URLs and no API keys.

## Alternatives considered

**Do nothing — let each implementation define its own LLM call shape.** The path of least resistance,
and the path LangChain Python and LangChain TypeScript took (visible drift, separate "differences"
docs). Rejected: violates the charter's drift policy (`GOVERNANCE.md` §Multi-language consistency).
A user moving between Python and TypeScript implementations would face two unrelated provider APIs.

**Spec the OpenAI wire format directly as the abstraction.** Faster: the wire shape is already
defined and mature. Rejected because it bakes one provider's design choices into the spec — OpenAI's
content-array shape, OpenAI's `function_call` legacy field, OpenAI's specific `finish_reason` set.
Future Anthropic-native or Bedrock-native providers would have to either pretend to be OpenAI on the
wire (re-translation surface) or sit outside the abstraction. The two-layer approach (abstract shape
+ wire mapping) lets each provider's native form be a parallel mapping section, with the abstract
shape stable.

**Abstract over message *content* shape (text + parts) from day one.** OpenAI and Anthropic both
support a richer "content as list of parts" form for multi-modal messages. Rejected because the
spec scope here is text-and-tool-calls; baking a content-parts abstraction in v1 would be designing
for a feature (multi-modal) that's explicitly deferred. When multi-modal lands as a follow-on
proposal, it can extend `content` to accept either a string or a list of parts in a backwards-
compatible way (tagged-union semantics; the string form remains valid).

**Make the provider stateful — cache conversation history server-side.** Some provider APIs offer
this (OpenAI's Assistants API, Anthropic's prompt-caching opt-in). Rejected: stateful providers
complicate every higher-level capability (retry can't blindly resubmit, evaluation can't reproduce
inputs from logs alone, the agent loop has to know whether the provider remembers). A stateless
substrate composes; statefulness can be added by a higher capability that wraps a stateless
provider.

**Have `complete()` loop on tool calls internally (single call returns final assistant text).** The
"agent runner" shape — the caller passes tools and a starting message list, the provider loops
until it gets a non-tool-calling response. Rejected because it conflates two concerns: provider
calls and agent loops. Tool execution is application logic (tools may be local Python functions,
remote MCP servers, network calls); embedding it in the provider forces the provider to know about
async tool dispatch, error handling, and step budgets. The graph-engine + a tool-system capability
expresses the loop as a conditional edge — a much better fit for the framework's primitives.

**Retries inside the provider.** Rejected for the same reason: retry policy is a cross-cutting
concern that belongs in pipeline-utilities middleware (proposal 0004). The provider returns errors
classified by category; middleware decides what to do with them.

**Rate limiting inside the provider.** Same. The charter §4.2 (`RateLimiter` with per-model and
per-node scopes that compose) places rate limiting in pipeline-utilities. A per-provider limiter
inside this layer would conflict with the cross-cutting design.

**Tokenizer access (token counting before the call).** Useful for prompt-budget-aware assembly.
Rejected for v1: not every provider exposes a tokenizer (especially private models behind APIs),
and the bringing-your-own-tokenizer story (tiktoken for OpenAI, the equivalent for Anthropic, etc.)
is messy enough to deserve its own proposal. Without it, `max_tokens` and `usage.total_tokens` are
the budget tools available; that is enough for v1.

**Use a vendor-neutral framework like LiteLLM as the abstraction.** LiteLLM is excellent at what it
does (provider routing, fallback, cost tracking) but it solves a different problem — multi-provider
*runtime* dispatch. The spec needs a *static type contract* implementations can ship without a
runtime dependency on a third-party library. A provider built on top of LiteLLM is a perfectly good
implementation of this spec.

## Open questions

None at time of submission.
