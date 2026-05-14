# 0015: LLM Provider — Image Content Blocks for User Messages

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-13
- **Accepted:** 2026-05-14
- **Targets:** spec/llm-provider/spec.md (modifies §3 *Message shape*; adds §3.1 *Content blocks*; modifies §7 *Error semantics*; modifies §8.1 *Request mapping*; modifies §10 *Out of scope*)
- **Related:** 0006 (LLM provider core)
- **Supersedes:**

## Summary

Extend the §3 message shape so that `user` messages MAY carry a sequence of typed **content
blocks** instead of a single text string. v1 of this proposal defines two block types — text
and image — and the OpenAI wire mapping for both. Audio and video are explicitly deferred to
follow-on proposals (one per modality). A new error category
`provider_unsupported_content_block` covers the case where the bound model rejects a block
type used in the request.

## Motivation

§10 of the v0.4.0 spec defers all multimodal content. Section §8.1's request mapping carries the
explicit note "OpenAI's content-array form is not used in v1." That deferral was correct at the
time: tool calling, error categories, and the OpenAI wire mapping were the v1 surface; multimodal
needed its own proposal.

Real downstream use now requires it. A common multimodal pipeline shape — feeding video frames,
screenshots, or other images to a vision-language model for narration, OCR, or scene
understanding — cannot be expressed within the current §3 message shape. Without multimodal
support in the spec, a project hitting this requirement has two options:

- Build a project-side wrapper around an OpenAI-wire-compatible Provider that constructs the raw
  content-array payload and bypasses the typed `UserMessage` model. This is exactly the
  workaround OA's Provider interface exists to avoid: paying the cost of OA's abstractions
  without getting the benefits, because the message shape can't express what the wire needs.
- Sit on the floor of text-only content and lose access to whatever signal the non-text
  modality would have surfaced.

Every major LLM provider (OpenAI, Anthropic, Google, Bifrost as a multiplexer over all three)
uses a content-array shape for multimodal input. The wire format is settled industry-wide; only
the spec's message shape lags. Bringing it forward is a single proposal — small surface, big
unlock.

Scope is deliberately narrowed to **images** for v1 of this proposal. Audio and video are real
work to spec correctly (formats, codecs, size/bitrate constraints, base64-vs-URL semantics,
streaming vs. inline) and pulling them into this proposal widens the review surface
unnecessarily. They land as separate follow-on proposals when a downstream project actually
needs them.

## Detailed design

### §3 Message shape: add content-blocks form for user messages

Amend §3's `content` field description and per-role constraints so that `user` messages MAY
carry either:

- a text string (the current v0.4.0 shape), OR
- an ordered sequence of typed content blocks (the new shape this proposal defines, §3.1).

Other roles (`system`, `assistant`, `tool`) remain text-string-only in v1 of this proposal. The
v1 vision-language pattern is "model receives images in a user turn, produces text in an
assistant turn"; image-bearing assistant outputs are not specified here and would need their own
proposal if a workload requires them.

Replace the `user` row of the per-role constraints in §3 with:

> - `user`: `content` MUST be one of:
>   - a non-empty string (text-only message), OR
>   - a non-empty ordered sequence of content blocks (per §3.1).
>   `tool_calls` MUST be absent. `tool_call_id` MUST be absent.

Leave `system`, `assistant`, and `tool` rows unchanged.

**Implementation latitude.** The two forms are normatively equivalent — a text-only user message
and a single-text-block user message have the same wire semantics. Implementations choose their
own representation: a tagged union (TypeScript discriminated union; Python `str |
list[ContentBlock]`), a single list with a text-string convenience constructor (always
internally a list, accept-string-on-construction), or any equivalent shape. The behavioral
contract is what the spec mandates; the in-memory class layout is per-language.

**Validation timing.** The existing §3 rule applies: implementations MUST validate the
message-shape constraints (including content-block well-formedness, per §3.1 below) at the
boundary of `complete()` — before sending to the provider, and on the response before
returning.

### §3.1 Content blocks (new subsection)

A **content block** is a typed record with a discriminator field identifying the block type.
v1 defines two block types: text and image.

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
| `media_type` | conditional | Required when `source` is `inline`; ignored when `source` is `url` (the provider infers the media type from the URL's payload). MUST be one of the IANA media types `image/png`, `image/jpeg`, `image/webp`. Implementations MAY accept additional media types; portable users SHOULD restrict to these three. |
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
  expects (§8.1).

A single image block carries exactly one source — `url` XOR `inline`. The discriminator is
the `type` field on the source itself.

#### 3.1.4 Mixing blocks

A user message MAY mix text and image blocks freely. The wire format preserves block order;
providers vary in whether they treat block order as semantically meaningful (e.g., "image
appearing before its describing text" vs. "image after"), so application code SHOULD construct
the block sequence in the order it wants the model to perceive it.

A content-block sequence MUST NOT be empty (per the §3 per-role constraint). A content-block
sequence consisting entirely of text blocks is valid (and is the multi-text-block shape some
applications prefer for prompt-composition reasons).

### §7 Error semantics: add `provider_unsupported_content_block`

Add the following category to §7's canonical error list:

- `provider_unsupported_content_block` — the bound model does not support a content block
  type used in the request (e.g., a text-only model received an image block, or the model
  supports images but not the requested `media_type` or `source` variant). Raised by the
  implementation's pre-send validation when the unsupported case is statically known (per the
  provider's documented capabilities), or by the post-receive error mapping when the provider
  itself rejects the request. **Non-transient.** Retrying without changing the request will
  not succeed.

Update the retry classification paragraph at the end of §7 to include
`provider_unsupported_content_block` in the *non-transient* list alongside
`provider_authentication`, `provider_invalid_model`, `provider_invalid_request`, and
`provider_invalid_response`.

The category is distinct from `provider_invalid_request` because it surfaces a *capability*
mismatch (the request is well-formed; the bound model can't fulfill it) rather than a *shape*
violation (the request is malformed at the spec layer). Distinguishing the two lets users
route the unsupported-content case differently (e.g., fall back to a multimodal-capable
provider) without overloading the malformed-request category.

### §8.1 Request mapping: content arrays for user messages

Amend the §8.1 mapping table's `user` row, replacing:

> | `user` | `user` | Direct mapping. `content` is a string; OpenAI's content-array form is not used in v1. |

with:

> | `user` | `user` | When `content` is a string, maps directly. When `content` is a content-block sequence (§3.1), maps to OpenAI's content-array form per §8.1.1. |

#### 8.1.1 Content-block wire mapping (new subsection of §8.1)

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
wire shapes; their own §8-style mapping sections (added by future proposals per §10's
"Provider-native wire formats" deferral) will define their own block→wire mappings without
disrupting this one.

### §10 Out of scope: image removed, audio/video remain

Replace the existing §10 entry:

> - **Multi-modal content** — image, audio, and video inputs and outputs.

with:

> - **Multi-modal audio and video** — audio and video inputs and outputs. Image inputs are
>   covered by §3.1 (per proposal 0015). Audio and video each warrant their own proposal —
>   formats, codecs, inline-vs-URL semantics, and provider wire mappings differ enough that
>   one proposal per modality is the right scope.
> - **Image outputs** — assistant-message-borne images (e.g., DALL-E-style image generation).
>   v1 image support is user-input-only; assistant-output image content would need a
>   separate proposal and is not common in tool-using agent workloads.

The other §10 entries (streaming, structured output, token counting, provider-native wire
formats, agent loop, retry/rate-limit, prompt template rendering, embeddings) remain unchanged.

### Cross-spec touchpoints

This proposal does not modify graph-engine, pipeline-utilities, or observability. Image
content blocks flow through node state and into `Provider.complete()` calls; no other
capability spec needs to know about them.

Observability §5.5 (`llm.model`, `llm.finish_reason`, `llm.usage.*`) is unchanged. Per-image
attribution on spans (e.g., "this generation consumed N image tokens") is a usage-accounting
concern at the provider level and is not surfaced by this proposal; if a follow-on usage
proposal adds per-modality token breakdowns to `Usage`, observability §5.5 can mirror them then.

## Conformance test impact

Add fixtures under `spec/llm-provider/conformance/`. Each fixture is a pair
(`NNN-name.yaml` + `NNN-name.md`) per the conformance README:

- **`009-content-blocks-text-only-equivalence.yaml`** — construct a user message as
  `content: [TextBlock(text="hello")]` and an equivalent message as
  `content: "hello"`. Assert both serialize to identical OpenAI wire payloads (the
  string-content form is preferred when blocks contain only text, OR both forms are
  accepted on the wire — implementation choice; assert wire-shape equivalence regardless).
- **`010-content-blocks-image-url.yaml`** — user message with one `ImageBlock(source=url(url="https://example.com/a.png"))`
  and one `TextBlock(text="describe this")`. Assert the OpenAI wire payload contains an
  `image_url` entry followed by a `text` entry, in that block order.
- **`011-content-blocks-image-inline-base64.yaml`** — user message with one
  `ImageBlock(source=inline(base64_data="<bytes>"), media_type="image/jpeg")`. Assert the
  OpenAI wire payload's `image_url.url` is `"data:image/jpeg;base64,<bytes>"`.
- **`012-content-blocks-image-detail-hint.yaml`** — user message with an image block whose
  `detail="high"`. Assert the OpenAI wire payload's `image_url.detail` is `"high"`. Then
  assert that omitting the detail field on the spec block omits it from the wire payload
  (default-applied-by-provider, not by us).
- **`013-content-blocks-mixed-order-preserved.yaml`** — user message with blocks in the
  order `[image, text, image, text]`. Assert the OpenAI wire payload preserves the order.
- **`014-content-blocks-validation-empty-sequence.yaml`** — attempt to construct a user
  message with `content: []`. Assert the implementation raises
  `provider_invalid_request` at pre-send validation (per §3 the sequence MUST be non-empty).
- **`015-content-blocks-validation-empty-text-block.yaml`** — user message with a `TextBlock(text="")`
  block in an otherwise non-empty sequence. Assert pre-send validation raises
  `provider_invalid_request` (per §3.1.1, `text` MUST be non-empty).
- **`016-content-blocks-unsupported-by-model.yaml`** — provider configured to bind a
  text-only model (e.g., a mock provider declaring no image support); user message contains
  an image block. Assert pre-send validation (or post-receive mapping) raises
  `provider_unsupported_content_block`.
- **`017-content-blocks-system-message-text-only.yaml`** — attempt to construct a `system`
  message with a content-blocks sequence. Assert the implementation raises
  `provider_invalid_request` (only `user` messages support blocks in v1, per amended §3).

## Alternatives considered

### Replace `content: str` with `content_blocks: list[...]` everywhere (breaking)

Considered. Cleaner long-term: every message role uses the same content-array shape, and the
spec's content-string form goes away. Rejected for this proposal because (a) only `user`
messages need blocks in v1, (b) flattening every other role's text-string to a one-block
list adds ceremony for the common case, and (c) the proposal's surface stays narrow if it
only changes the role that actually needs the change. A future proposal MAY normalize all
roles onto blocks if a workload requires it.

### Strict union (`content` is either str or list, never both) vs. additive (`content` always str, optional `content_blocks` list)

Decided on the union form (one field, two shapes). The additive form (a separate
`content_blocks` field alongside the existing `content`) creates a per-message-construction
ambiguity ("if both are set, which wins?") and complicates wire mapping. A union keeps the
constraint explicit: a user message has *one* form of content, either string or blocks.

### Spec the image block's media_type as an open enum (any IANA `image/*`)

Considered. The constraint to `png`/`jpeg`/`webp` is the intersection of what major
providers actually accept across the OpenAI/Anthropic/Google ecosystem. Allowing any
`image/*` (e.g., `image/gif`, `image/heic`, `image/avif`) sounds more permissive but in
practice means providers reject the request anyway. The spec mandates the common subset and
lets implementations accept more if they document it. Users wanting portability stick to
the three.

### Bundle audio and video blocks in this proposal

Rejected. Audio and video each have their own wire-shape variation (audio's `input_audio`
shape on OpenAI is different from images; video is barely supported across providers and
has no settled wire shape). Bundling would either ship them in a half-specified state or
delay images. Single-modality scope keeps this proposal shippable.

### Add image-output (assistant message images) in this proposal

Rejected. Assistant-output images are a different workload (image generation, e.g.,
DALL-E-style) and use different wire conventions across providers. Tool-using agent
pipelines (the v1 OA target workload) overwhelmingly want image *input* only. Adding output
support would expand the surface without serving the actual demand.

### Keep image inputs out of spec and require project-side wrappers

Rejected. The current §3 message shape is already typed; users wanting images today must
construct provider-specific raw payloads outside the spec and bypass the abstraction. That
defeats the purpose of OA's Provider interface — users pay for the typing discipline without
getting the benefit when their workload needs images. Bringing images into the spec keeps
the abstraction intact for the workloads that need it.

## Open questions

None at time of submission.
