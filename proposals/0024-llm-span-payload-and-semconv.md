# 0024: Observability — LLM Span Payload, Request Parameters, and GenAI Semconv

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-22
- **Accepted:**
- **Targets:** spec/observability/spec.md (modifies §5.5 *LLM provider attributes*)
- **Related:** 0007 (observability OTel span mapping), 0006 (LLM provider core), 0016 (structured output), 0017 (prompt management), 0019 (multi-provider wire-format extension)
- **Supersedes:**

## Summary

Extend observability §5.5 LLM-provider span attributes with three groups of additions:
(1) **input/output payload** on the LLM span (the §3 messages sent and the assistant
content received), default-off, governed by a per-attribute byte cap with a
truncation marker; (2) **request parameters** from `RuntimeConfig` (temperature,
max_tokens, top_p, seed) emitted under the OpenTelemetry **GenAI semantic
conventions** (`gen_ai.request.*`) rather than under the OpenArmature namespace, on
the principle that cross-vendor LLM parameters are not OA-specific state; and (3) a
minimum set of **GenAI semconv response attributes** (`gen_ai.system`,
`gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`,
`gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`,
`gen_ai.response.id`) that LLM-aware OTel backends (Langfuse, Phoenix, Honeycomb
LLM lens, etc.) key off of, so users get correct backend rendering without writing
custom attribute-mapping shims. Add two opt-out flags (`disable_llm_payload`,
`disable_genai_semconv`) paralleling the existing `disable_llm_spans` opt-out.
Specify a truncation contract (64 KiB default per-attribute byte cap, suffix
marker, inline-image redaction rule). No existing attribute is renamed; all
additions sit alongside the v0.7.0 attribute set.

## Motivation

The v0.7.0 §5.5 LLM-provider span carries `model`, `finish_reason`, and the
three usage-token counts. That set is sufficient to confirm a call happened and
to compute usage aggregates. It is **not** sufficient to drive any of the
following workflows that production deployments routinely need:

1. **Inspecting what the model saw and produced.** Trace UIs render an LLM span
   as a row labeled with `finish_reason` and token counts. Without the input
   messages and the assistant's response content, users cannot answer "what did
   the model see for this request" or "what did it actually say" without
   joining the trace against an external log of the request payload. The
   downstream log doesn't exist by default; users either build it themselves
   or accept that LLM calls are opaque in the trace.

2. **Rendering correctly in LLM-aware backends.** Langfuse, Phoenix, Honeycomb
   LLM lens, and similar tools key off the OpenTelemetry GenAI semantic
   conventions (`gen_ai.system`, `gen_ai.request.model`,
   `gen_ai.usage.input_tokens`, `gen_ai.response.finish_reasons`, etc.) to
   recognize a span as a generation, group generations by provider and model,
   render messages and responses as a chat view, and compute aggregates. With
   only OA-namespaced attributes, every user has to write an attribute-mapping
   shim (typically a span processor or an exporter wrapper that copies
   `openarmature.llm.usage.prompt_tokens` to `gen_ai.usage.input_tokens` and so
   on). Production deployments wiring OA with LLM-aware OTel backends have
   surfaced this gap repeatedly; the canonical fix is for OA to emit the
   semconv attributes directly.

3. **Filtering by sampling parameters.** `temperature`, `max_tokens`, `top_p`,
   and `seed` are part of `RuntimeConfig` and reach the wire (§8.1 of
   llm-provider) but are not emitted on the span. Comparing a slow run's
   parameters against a fast run's, or filtering for "all calls at
   temperature=0" in a trace UI, is impossible without lifting these onto the
   span.

The §5.5 design intent — production observability has no gaps by default — is
upheld for the trace-shape concerns it addresses (every call gets a span;
external auto-instrumentation is isolated via the private TracerProvider).
This proposal extends that intent to **content** — the span carries enough of
the call's request/response shape to make LLM-aware backends useful out of
the box, while keeping privacy-sensitive payload emission opt-in.

### Why now

The OpenTelemetry GenAI semantic conventions for LLM operations have
stabilized for the attribute names this proposal mandates (the request/response/usage
attributes listed in §6 below; tool-call attributes remain experimental and
are deferred). Locking these names into the spec creates cross-implementation
compatibility (a Python OpenArmature span and a future TypeScript OpenArmature
span both register as the same generation in Langfuse / Phoenix), and pins
implementations to the same external standard as their out-of-tree
competitors so backend behavior is uniform.

The deferred items (tool-call attributes, Langfuse-native backend) get their
own follow-on proposals once concrete shape requirements settle. Bundling
them here would inflate the proposal beyond its core scope and risk locking
in a tool-call shape before the semconv settles.

## Detailed design

This proposal modifies §5.5 only. All other sections of `spec/observability/spec.md`
are unchanged.

### §5.5 — preserved attributes (no change)

The following attributes are emitted on the LLM provider span as in v0.7.0:

- `openarmature.llm.model` — string. The model identifier the provider is bound to.
- `openarmature.llm.finish_reason` — string. The llm-provider §6 `finish_reason`.
- `openarmature.llm.usage.prompt_tokens`, `openarmature.llm.usage.completion_tokens`,
  `openarmature.llm.usage.total_tokens` — int. From the response's usage record.
  Omit when null.

Cross-cutting attributes (§5.6 `openarmature.correlation_id`) and prompt-management
attributes (per proposal 0017 §11) are unaffected.

### §5.5.1 — Input/output payload attributes (new, default-off)

When the LLM payload-emission flag is enabled (per §5.5.4), implementations MUST
emit the following attributes on the LLM provider span:

- `openarmature.llm.input.messages` — string. The messages list sent to the
  provider, JSON-encoded per the llm-provider §3 message shape. Each message
  is serialized as `{role, content, tool_calls?, tool_call_id?}`. Content
  blocks (per llm-provider §3.1) are serialized with the discriminator
  (`{type, text}` for text blocks, `{type, source, media_type?, detail?}` for
  image blocks) — but inline image bytes are replaced with a placeholder per
  §5.5.5. The serialization MUST be deterministic for identical inputs (sorted
  object keys, no insignificant whitespace).

- `openarmature.llm.output.content` — string. The assistant's response content
  verbatim, as returned by the provider in the §6 `message.content` field.
  Emitted only when `message.content` is non-empty (assistant messages with
  only `tool_calls` and empty content MUST NOT emit this attribute). When
  `Response.parsed` is populated (per llm-provider §6, structured output),
  this attribute carries the unparsed `message.content` string, NOT a
  re-serialization of `parsed` — matching the llm-provider §6 rule that
  `message.content` is verbatim.

- `openarmature.llm.request.extras` — string. The `RuntimeConfig` extras
  mapping (the `extra="allow"` pass-through fields permitted by llm-provider
  §6), JSON-encoded as an object. Emitted only when the mapping is non-empty.
  This attribute is OA-shape (the extras bag is the spec's structure, not the
  GenAI semconv's); it is grouped with payload because it MAY contain provider-
  specific parameters that warrant the same default-off treatment as
  messages. Implementations MAY choose to gate `request.extras` separately from
  `input.messages` / `output.content`; the default is to gate all three under
  the same flag.

All three attributes are subject to the §5.5.5 truncation contract.

### §5.5.2 — Request parameters (new, default-on, GenAI semconv)

Implementations MUST emit the following attributes on the LLM provider span
when the corresponding `RuntimeConfig` (§6 of llm-provider) field is set on
the request:

- `gen_ai.request.temperature` — double. Mapped from `RuntimeConfig.temperature`.
- `gen_ai.request.max_tokens` — int. Mapped from `RuntimeConfig.max_tokens`.
- `gen_ai.request.top_p` — double. Mapped from `RuntimeConfig.top_p`.
- `gen_ai.request.seed` — int. Mapped from `RuntimeConfig.seed`.

When the corresponding `RuntimeConfig` field is not set (or `RuntimeConfig`
is absent on the call), the implementation MUST NOT emit the attribute. The
absence of an attribute means "the field was not supplied for this call,"
distinct from "the field was supplied with a zero value."

These attributes use the GenAI semconv namespace directly (no
`openarmature.llm.request.*` parallel). Rationale: `temperature`, `max_tokens`,
`top_p`, and `seed` are cross-vendor LLM parameters with no OpenArmature-specific
semantics. The GenAI semconv names for these are settled in the upstream
specification and are the names every LLM-aware OTel backend reads. Adding
OA-prefixed parallels would be pure duplication.

This establishes a precedent that future cross-spec touchpoints follow: **the
OpenArmature attribute namespace is normative for attributes encoding
OA-specific state (correlation_id, prompt identity, error category, fan-out
index, etc.); the GenAI semconv namespace is used directly for cross-vendor
LLM parameters and response metadata when the semconv name is stable.**

### §5.5.3 — GenAI semconv response attributes (new, default-on)

Implementations MUST emit the following attributes on the LLM provider span
unless the GenAI semconv opt-out is enabled (per §5.5.4):

- `gen_ai.system` — string. The LLM system identifier, per the GenAI semconv
  enum (`"openai"`, `"anthropic"`, `"vllm"`, `"lm_studio"`, etc.).
  Implementations MUST allow this value to be configurable per provider
  instance. The OpenAI-compatible provider (§8.1 of llm-provider) MUST default
  this value to `"openai"`; callers using the OpenAI-compatible provider with
  a non-OpenAI endpoint (vLLM, LM Studio, llama.cpp server, etc.) MUST be able
  to override this default to the appropriate system identifier. Specific
  override mechanism (constructor argument, factory method, environment
  variable) is implementation-defined; the behavioral contract is that an
  override is available and effective.

- `gen_ai.request.model` — string. The model the request was made against —
  the model identifier bound to the provider. Mirrors
  `openarmature.llm.model`; both emit. Rationale: the GenAI semconv requires
  this name for backend recognition; the OA-namespaced version is preserved
  for backwards compatibility with v0.7.0 fixtures.

- `gen_ai.response.model` — string. The model identifier the provider returned
  in the response (the `model` field on the response body, when the provider
  populates it). Distinct from `gen_ai.request.model` because providers MAY
  return a more specific model identifier than the one requested (e.g.,
  requested `gpt-4o`, response carries `gpt-4o-2024-08-06`). Emitted only
  when the provider returns a non-null response model.

- `gen_ai.usage.input_tokens` — int. The prompt token count from the response's
  usage record. Mirrors `openarmature.llm.usage.prompt_tokens`; both emit.
  Omit when the response's usage record is null.

- `gen_ai.usage.output_tokens` — int. The completion token count from the
  response's usage record. Mirrors `openarmature.llm.usage.completion_tokens`;
  both emit. Omit when null.

- `gen_ai.response.finish_reasons` — string array. The `finish_reason` values
  from the response, as a single-element array (the llm-provider §6
  `Response.finish_reason` is a single string; the GenAI semconv defines this
  as an array to accommodate providers returning multiple choices, which OA's
  §6 shape collapses to one). Mirrors `openarmature.llm.finish_reason` as
  string-scalar; both emit, with the GenAI version always wrapped in a
  one-element array.

- `gen_ai.response.id` — string. The response identifier the provider
  returned (the `id` field on the response body), when present. Useful for
  cross-referencing OA spans with provider-side billing or audit logs.
  Emitted only when the provider returns a non-null id.

### §5.5.4 — Opt-out flags

Implementations MUST support the following observer-level configuration flags
(specific ergonomics — constructor argument, builder method, etc. — are
implementation-defined; flag names below are normative for cross-implementation
consistency):

- `disable_llm_payload: bool` — default `True`. When `True`, the §5.5.1
  payload attributes (`input.messages`, `output.content`, `request.extras`)
  are NOT emitted. When `False`, payload attributes emit per §5.5.1, subject
  to the §5.5.5 truncation contract.

- `disable_genai_semconv: bool` — default `False`. When `True`, the §5.5.2
  request-parameter attributes and the §5.5.3 response-attribute set are NOT
  emitted. When `False` (the default), GenAI semconv attributes emit per
  §5.5.2 and §5.5.3.

The existing `disable_llm_spans` flag (per v0.7.0 §5.5) MUST continue to
behave as specified: when `True`, the LLM provider span is not emitted at all,
and none of the attributes specified in this proposal are emitted (they have
no span to attach to).

The three flags are independent. The matrix of typical configurations:

| Configuration | `disable_llm_spans` | `disable_llm_payload` | `disable_genai_semconv` | Outcome |
|---|---|---|---|---|
| Default (out of the box) | `False` | `True` | `False` | LLM span emits with OA + GenAI semconv attributes; no payload. |
| Maximum visibility | `False` | `False` | `False` | LLM span emits with full payload and all attributes. |
| External auto-instrumentation is canonical | `True` | (irrelevant) | (irrelevant) | OA emits no LLM span; external library handles it. |
| OA span without GenAI semconv | `False` | `True` | `True` | OA-namespaced attributes only; useful when an external library is the canonical GenAI emitter and OA's role is internal-only attribution. |

### §5.5.5 — Truncation contract

The §5.5.1 payload attributes (`openarmature.llm.input.messages`,
`openarmature.llm.output.content`, `openarmature.llm.request.extras`) MAY be
arbitrarily large in principle (a long conversation, a verbose model response,
a multi-image user message). Emission without bounds would produce spans
larger than typical OTLP exporters accept and inflate observability storage
unbounded. The following contract applies:

**Per-attribute byte cap.** Implementations MUST enforce a maximum byte length
on each of the three payload attributes individually. The default cap is **65,536
bytes (64 KiB)** per attribute. Implementations MUST allow the cap to be
configured per observer (specific mechanism — constructor argument, environment
variable, etc. — is implementation-defined). The byte length is measured on the
UTF-8 encoding of the final attribute string, after JSON serialization and
after inline-image redaction (below).

**Truncation marker.** When an attribute's serialized value exceeds the
configured cap, the implementation MUST emit the first N bytes of the value
(N = configured cap minus marker length) followed by the literal suffix:

```
…[truncated, M bytes total]
```

where M is the pre-truncation byte length (decimal integer). The marker is
appended **outside** any JSON encoding — the result of truncating a
JSON-encoded attribute is not itself parseable JSON, which is the signal to
backend code that the value was truncated. Backends performing custom parsing
get a clean affordance to detect truncation without needing a separate flag
attribute.

The marker bytes count toward the cap: an attribute capped at 64 KiB and
truncated will have at most 64 KiB total, including the marker.

**Inline-image redaction.** Image content blocks (per llm-provider §3.1.2)
carry either a URL source or inline base64 bytes (per §3.1.3). The URL form is
a short string and passes through unchanged. The inline form is potentially
very large (base64-encoded image bytes). When serializing messages for
`openarmature.llm.input.messages`, implementations MUST replace inline-image
source records with a redacted placeholder before JSON encoding:

```
{"type": "image", "source": {"type": "inline_redacted", "media_type": <mt>, "byte_count": <N>}}
```

where `<mt>` is the original `media_type` and `<N>` is the byte length of the
original base64-encoded data. The placeholder preserves enough metadata for a
reader to understand "an inline image of this type and approximate size was
present" without inlining the bytes themselves. Implementations MUST NOT emit
inline image bytes on the span under any configuration; this is a hard rule,
not gated by `disable_llm_payload` or by the per-attribute cap.

URL-form images are NOT redacted — the URL is a short string and is
informative for trace readers (it points to the actual image asset). The
redaction rule applies only to `source.type == "inline"`.

**Tool-call serialization.** Assistant `tool_calls` (per llm-provider §3) in
`openarmature.llm.input.messages` are JSON-encoded as
`[{"id", "name", "arguments"}, ...]` with `arguments` serialized verbatim from
the parsed mapping. Tool-call argument content is subject only to the overall
per-attribute byte cap; this proposal does not specify a separate per-tool-call
cap. (Tool-call observability has its own follow-on; the placeholder rule here
is the minimum needed to keep the assistant-message round-trip well-formed.)

### §5.5.6 — Cross-implementation consistency

Implementations of this proposal across languages (Python, TypeScript) MUST
agree on:

- Attribute names (exactly as specified above; case- and prefix-sensitive).
- Attribute value types (string, int, double, string-array as specified).
- JSON serialization shape for `input.messages` and `request.extras` (sorted
  object keys, UTF-8 encoding, deterministic for identical inputs).
- The truncation marker string (`…[truncated, M bytes total]`, including the
  Unicode ellipsis character `…` U+2026, the brackets, the comma, the literal
  word "truncated", and the integer M).
- The inline-image placeholder shape (the `{type: "image", source: {type: "inline_redacted", media_type, byte_count}}` record).
- The default `disable_llm_payload: bool = True`, `disable_genai_semconv: bool = False`,
  `disable_llm_spans: bool = False` defaults.

Per-language ergonomics (constructor argument naming, builder patterns,
environment-variable lookup) MAY differ. The above are the cross-impl
behavioral surface.

## Conformance test impact

Add the following fixtures under `spec/observability/conformance/` (numbered
sequentially after the existing v0.7.0 fixture set, which currently tops out
at `011-otel-determinism`):

- **`012-otel-llm-payload-default-off.yaml`** — single LLM call; default
  observer configuration (no `disable_llm_payload` override). Assert the LLM
  span carries the v0.7.0 attribute set plus the §5.5.2 / §5.5.3 GenAI
  semconv attributes; assert `openarmature.llm.input.messages`,
  `openarmature.llm.output.content`, and `openarmature.llm.request.extras`
  are NOT present.

- **`013-otel-llm-payload-enabled.yaml`** — single LLM call with messages
  including a multi-turn conversation; observer constructed with
  `disable_llm_payload=False`. Assert `openarmature.llm.input.messages` is
  present and parses (when un-truncated) as the §3 message list; assert
  `openarmature.llm.output.content` is present and equals the response's
  `message.content` verbatim.

- **`014-otel-llm-payload-truncation.yaml`** — single LLM call with messages
  whose JSON encoding exceeds 64 KiB (the default cap); observer with
  `disable_llm_payload=False` and default cap. Assert the attribute's byte
  length is ≤ 64 KiB; assert the suffix matches `…[truncated, M bytes total]`
  with M being the pre-truncation byte length; assert the bytes preceding the
  marker are a prefix of the full serialization.

- **`015-otel-llm-payload-image-redaction.yaml`** — single LLM call with a
  user message containing one inline image block (per llm-provider §3.1.3)
  and surrounding text blocks; observer with `disable_llm_payload=False`.
  Assert the inline image's `source` is replaced with the
  `inline_redacted` placeholder structure carrying the original `media_type`
  and a `byte_count` matching the original base64 length; assert no base64
  bytes appear in the attribute value.

- **`016-otel-llm-request-params.yaml`** — single LLM call with a
  `RuntimeConfig` carrying `temperature`, `max_tokens`, `top_p`, and `seed`.
  Assert `gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
  `gen_ai.request.top_p`, `gen_ai.request.seed` are emitted with the
  corresponding values; assert no `openarmature.llm.request.*` parallel
  attributes are emitted for these fields.

- **`017-otel-llm-request-params-partial.yaml`** — single LLM call with a
  `RuntimeConfig` carrying only `temperature` (other fields absent). Assert
  `gen_ai.request.temperature` is emitted; assert `gen_ai.request.max_tokens`,
  `gen_ai.request.top_p`, `gen_ai.request.seed` are NOT emitted (absence
  semantics per §5.5.2).

- **`018-otel-llm-request-extras.yaml`** — single LLM call with a
  `RuntimeConfig` carrying provider-specific extras (e.g., `frequency_penalty:
  0.5`); observer with `disable_llm_payload=False`. Assert
  `openarmature.llm.request.extras` is emitted as a JSON-encoded object
  carrying the extras mapping.

- **`019-otel-llm-genai-semconv.yaml`** — single LLM call against an
  OpenAI-compatible provider. Assert `gen_ai.system: "openai"`,
  `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons` (as a
  one-element array), and `gen_ai.response.id` are all emitted; assert the
  v0.7.0 `openarmature.llm.*` attributes are also emitted (additions, not
  renames).

- **`020-otel-llm-genai-system-override.yaml`** — single LLM call against an
  OpenAI-compatible provider configured to point at a non-OpenAI endpoint
  with `gen_ai.system` overridden to `"vllm"`. Assert `gen_ai.system: "vllm"`
  on the LLM span.

- **`021-otel-llm-disable-genai-semconv.yaml`** — single LLM call with
  observer constructed with `disable_genai_semconv=True`. Assert no
  `gen_ai.*` attributes are emitted; assert the v0.7.0 `openarmature.llm.*`
  attributes are still emitted (the GenAI opt-out does NOT suppress the
  legacy OA attributes).

The existing fixture `005-otel-llm-provider-span-nested` (covering the default
and `disable_llm_spans` cases) is unchanged — its assertions verify only the
v0.7.0 attribute set, which this proposal preserves.

## Alternatives considered

### Default-on payload emission

Considered: emit `openarmature.llm.input.messages` and
`openarmature.llm.output.content` by default. Industry convention (OpenInference,
LangSmith, Phoenix) is default-on; the immediate user experience of "wiring up
the observer and immediately seeing message content in the trace UI" is
better.

Rejected. Two reasons dominate:

1. **PII risk is asymmetric and recurring.** A user running OA against
   regulated data (HIPAA, GDPR, financial) who didn't audit observability
   configuration discovers prompt content in their trace backend storage
   months later. Default-on means every new OA deployment is one careless
   integration away from a regulated-data leak. Default-off means the user
   makes a deliberate choice to enable payload emission; the friction is
   one-time at integration, the privacy outcome is the safe default.

2. **Storage cost is asymmetric and recurring.** Trace storage is priced by
   span volume and attribute byte volume. Default-on emission of full message
   payloads inflates storage cost on every request; the cost is hidden until
   the bill arrives.

The friction default-off creates is one-time per integration (the integrator
sets `disable_llm_payload=False` once when wiring the observer). The friction
default-on creates is recurring per user and per request. The asymmetry
favors default-off.

A "warn but default-on" middle ground (emit a noisy warning the first time the
observer runs without an explicit setting) was also considered and rejected:
the warning becomes either ignorable (users disable it) or noisy in normal
operation. A clean opt-in is cleaner than a default-on with a warning.

### `openarmature.llm.request.*` namespace for request parameters

Considered: emit `openarmature.llm.request.temperature`,
`openarmature.llm.request.max_tokens`, etc., paralleling the existing
`openarmature.llm.usage.*` pattern. Either replacing the GenAI semconv
attributes entirely or emitting both.

Rejected. The §5.5.2 design notes already cover this; the short form is:
request parameters have no OA-specific semantics. They are cross-vendor LLM
parameters; the GenAI semconv name is the canonical one. OA-prefixed parallels
would be pure duplication and increase span size without adding diagnostic
value. The principle established here — OA-prefix for OA-specific state,
semconv for cross-vendor parameters — extends cleanly to future capability
proposals.

The `openarmature.llm.usage.*` attributes are kept (with `gen_ai.usage.*`
parallels emitted) because they predate this proposal and removing them would
be a breaking change for users who already query OTLP backends by the OA
names. Future-greenfield attributes (like `request.*`) go directly to
`gen_ai.*` without an OA parallel.

### Inferring `gen_ai.system` from `base_url`

Considered: for the OpenAI-compatible provider, infer the `gen_ai.system`
value from the provider's `base_url` configuration (e.g., `localhost:8000` →
`"vllm"`, `api.openai.com` → `"openai"`).

Rejected. Base-URL inference is unreliable in practice. `http://localhost:8000`
could be vLLM, LM Studio, llama.cpp, sglang, a custom proxy, or somebody's
forward proxy in front of the real OpenAI hosted API. No correct inference
exists. Caller-set override is explicit, one-time per provider instance, and
honest — the user knows which system they're hitting better than any
heuristic.

Future provider implementations whose wire-format mapping is provider-specific
(e.g., the Anthropic Messages mapping under proposal 0019's §8.X catalog) MAY
hard-code their `gen_ai.system` value non-overridably, because the mapping is
specific to the wire shape and identifying it as another system would be
incorrect.

### Bundling tool-call attributes into this proposal

Considered: extend §5.5 with `gen_ai.tool.call.*` attributes covering the
assistant's `tool_calls` and (separately) the `tool` role response messages.

Rejected for this round. Tool-call observability has its own design surface
(span-per-tool-call vs attributes-on-LLM-span; malformed-tool-calls under
`finish_reason: "error"` per llm-provider §3; parallel tool-call handling;
tool definition emission). The GenAI semconv tool-call attributes are still
experimental in upstream. Bundling here would either bake in a tool-call
shape prematurely or leave the proposal vague where it should be normative.
A follow-on proposal handles tool-call observability once a concrete forcing
function (a downstream integration with explicit tool-call requirements, or
the TypeScript impl coming online) makes the shape decisions concrete.

With this proposal landed, tool calls are still observable in the trace —
they appear inside the JSON-encoded `openarmature.llm.input.messages`
attribute as `tool_calls` arrays on assistant messages, and inside `tool`
role messages on subsequent turns. The friction is that they are not
first-class for backend filtering / rendering; that gap is what the follow-on
proposal closes.

### Single combined opt-out flag

Considered: one flag (e.g., `disable_llm_extensions`) that covers payload,
request parameters, and GenAI semconv as a single on/off toggle.

Rejected. The three concerns have different default-correctness profiles:

- Payload is privacy- and cost-sensitive; the right default is off.
- Request parameters are not privacy-sensitive (sampling parameters are not
  PII) and not large; the right default is on.
- GenAI semconv emission is the canonical way LLM-aware backends recognize
  the span; the right default is on. The opt-out exists for the case where
  external auto-instrumentation (OpenInference, opentelemetry-instrumentation-openai)
  is the canonical GenAI emitter and OA's role is internal-only attribution.

Collapsing them under a single flag forces users into one of two corner
configurations. Three independent flags cost three lines of constructor
documentation and let each concern have its right default.

### Emitting payload as OTel events instead of attributes

Considered: emit the messages and response content as OTel `span.add_event`
events (e.g., `gen_ai.user.message`, `gen_ai.assistant.message`) per a
recent direction in the GenAI semconv working group, rather than as span
attributes.

Rejected for this version. The event-based shape has merits (smaller
individual records, natural ordering) but is still in flux in the upstream
spec, and OTLP backend support for content events is uneven. The
attribute-based shape is implementable today against any OTLP-compatible
backend without backend-side changes. A future proposal MAY add an
event-based emission mode as an opt-in alternative once upstream and
backends settle.

### Truncating in the OTel exporter rather than in the observer

Considered: emit unbounded attribute values from the observer and rely on
the OTLP exporter to truncate to its configured max attribute length.

Rejected. Exporter-side truncation produces silent data loss with no marker —
the backend receives a value that ends mid-string with no signal that
truncation occurred. The contract in §5.5.5 specifies an explicit suffix
marker carrying the original byte count, which gives backends a clean way to
distinguish "this is the full value" from "this is a truncated value" and
exposes how much was lost. Observer-side truncation is the only way to
preserve that distinction.

Exporter-side truncation also varies by exporter implementation; the spec
contract cannot rely on it being consistent.

## Open questions

None at this time. The four questions raised during scope discussion (payload
default, request-parameter namespacing, tool-call bundling, `gen_ai.system`
override mechanism) are answered in *Detailed design*.
