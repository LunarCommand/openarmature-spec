# Prompt Management

Canonical behavioral specification for the OpenArmature prompt-management capability.

- **Capability:** prompt-management
- **Introduced:** spec version 0.15.0
- **History:**
  - created by [proposal 0017](../../proposals/0017-prompt-management-core.md)
  - §3 *Prompt shape* extended with two new optional typed fields (`sampling` — sub-record mirroring llm-provider §6 `RuntimeConfig`'s declared-fields-plus-extras shape for per-prompt sampling configuration; `observability_entities` — backend-keyed mapping for first-class entity references, with spec-normative key `langfuse_prompt` for the Langfuse Prompt entity). §4 *PromptResult shape* propagates both new fields. §5 *PromptBackend protocol* gains an informative filesystem sidecar convention (per-prompt `<root>/<name>.config.json` and unified `<root>/prompt_configs.json` shapes) for sourcing `sampling`. §6 *PromptManager interface* gains optional `LabelResolver` integration on `fetch()`; the default label parameter shifts from `"production"` to `None`/sentinel with a fallback chain (explicit > resolver > spec-fallback `"production"`). New §7 *LabelResolver* primitive added (renumbers existing §7-§13 → §8-§14). §12 (was §11) *Cross-spec touchpoints* gains two new touchpoints: `Prompt.sampling` → llm-provider §6 `RuntimeConfig` wiring at the LLM call site, and `Prompt.observability_entities['langfuse_prompt']` → observability §8.4.4 Langfuse Generation linkage lookup by [proposal 0033](../../proposals/0033-prompt-management-surface-refinements.md)
  - §3 *Prompt shape* gains a new §3.1 *Chat-prompt variant* subsection introducing a Chat-prompt variant alongside the existing Text-prompt variant (Chat-prompt carries `chat_template: list[ChatSegment]` in place of `template`; ChatSegments are either content segments — text-template or content-blocks-template `content`, with content-blocks mirroring llm-provider §3.1 text + image-URL + image-inline block shapes for multimodal user-message authoring, image blocks user-only per §3.1.2 — or placeholder segments naming a slot filled at render time with a `list[Message]`; Chat-prompt `template_hash` covers the canonical chat_template serialization). §6.render gains a `placeholders` parameter, a per-segment / per-block render rule for Chat prompts (text-template segments render to a text Message; content-blocks segments render to a Message with a rendered block sequence; placeholder segments inject the caller-supplied message list, empty injected lists valid), and a narrowing of the Text-prompt render clause to "exactly one Message with text content; multi-message and multimodal MUST use chat_template" (replaces the prior vague "MAY produce multiple messages" line). §8 *Variable injection* gains a per-segment / per-block strict-undefined paragraph. §11 *Errors* extends `prompt_render_error` with five new Chat-prompt triggers (empty content segment, empty content-blocks list, unfilled placeholder, duplicate placeholder name, role-block compatibility violation). §5 *PromptBackend protocol* gains a paragraph noting returned Prompts MAY be either variant. §12 cross-spec touchpoints confirms the §8.4.4 Langfuse Prompt-entity linkage is unaffected by Prompt variant or message count by [proposal 0046](../../proposals/0046-prompt-management-multi-message-rendering.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The prompt-management capability defines the contract by which named, versioned templates
are fetched from one or more backends, rendered with caller-supplied variables, and turned
into LLM-ready message sequences. The spec establishes the contracts; implementations and
sibling-package backends ship the concrete forms.

The capability composes with the llm-provider capability (a `PromptResult` carries
`Message` records per llm-provider §3) and with the observability capability (rendered
prompts carry stable identity that observer events MAY surface).

This capability does NOT define:

- The templating language or syntax (Jinja2 in Python, handlebars / template literals in
  TypeScript — per implementation).
- Specific backend implementations beyond a minimum local-filesystem reference.
- Prompt versioning workflows (the spec defines a `version` field on `Prompt`; how
  versions are assigned, incremented, or pinned is per-project discipline).
- Cache invalidation policies (the spec defines hashes that user code MAY use as cache
  keys; the cache itself is out of scope).

## 2. Concepts

**Prompt.** An unrendered template plus its identity metadata. A prompt is what a backend
returns from a fetch; it carries enough information to be rendered, traced, and
content-addressed without a backend round-trip.

**PromptResult.** The rendered output of applying variables to a prompt. Carries the
rendered `Message` sequence (per llm-provider §3) plus the prompt's identity metadata
(propagated from the source `Prompt`) plus a `rendered_hash` that captures the rendered
content.

**PromptManager.** The user-facing API. Composes one or more `PromptBackend`s and exposes
fetch + render operations. Users interact with the manager; backends are an
implementation detail of the manager's construction.

**PromptBackend.** The protocol implementations and sibling packages plug into. Defines a
single operation: fetch a prompt by name and label. Backends do not render; rendering is
the manager's concern.

**PromptGroup.** A composition pattern for tracing related prompts together: an ordered
sequence of `PromptResult` instances that should appear under one logical grouping in
observability. The canonical N=2 case is "classifier + follow-up"; longer chains
(multi-stage classification, RAG with reranking, self-correction loops, map-reduce over
chunks) work under the same primitive. The group is a thin wrapper over its members and
a span-grouping convention; it is not a fetch or render primitive and performs no
orchestration.

**Fetch vs. render distinction.** Fetching retrieves the template; rendering applies
variables. Splitting the two operations lets users:

- Inspect a template without binding variables (useful for tooling, schema validation,
  prompt-version diffs).
- Cache templates separately from rendered output (template fetch is the I/O-bound step;
  rendering is local).
- Render the same template with different variables in tight loops without re-fetching.

A convenience operation that combines fetch + render is permitted (see §6) but the spec
treats fetch and render as separable.

## 3. Prompt shape

A prompt is one of two variants (see §3.1 below): a **Text prompt** (the existing single-
template shape) or a **Chat prompt** (a list of role-tagged segments, optionally with
placeholder slots for variable-length message-list injection at render time). The table
below describes the fields common to both variants; the `template` row applies to the
Text-prompt variant and is replaced with `chat_template` on the Chat-prompt variant per
§3.1.

A `Prompt` record:

| Field | Description |
|---|---|
| `name` | String. The prompt's stable identifier within its backend. Matches the `name` argument the caller passed to fetch. |
| `version` | String. The prompt's version identifier within its backend. Implementation-defined: a backend MAY use semver, monotonic integers, content hashes, git short-SHAs, date stamps, or any stable identifier. Two distinct version strings MUST denote distinct prompt contents. |
| `label` | String. The label under which the prompt was fetched (e.g., `"production"`, `"latest"`, `"variant-a"`). Backends MAY support multiple labels per prompt; the label is part of the fetch query. |
| `template` | The unrendered template, in the implementation's chosen template representation (a Jinja2 `Template` instance, a string, an AST, etc.). The spec does not constrain the in-memory representation; it constrains the render contract (§8). |
| `template_hash` | String. A stable content-derived hash of the unrendered template. Implementations SHOULD use a cryptographic hash (e.g., SHA-256 hex) over the canonical serialization of the template. The hash MUST be deterministic for identical template content. |
| `fetched_at` | Timestamp of when this Prompt was fetched from its backend. Implementation-defined precision. When the backend serves a cached result, `fetched_at` MUST reflect the original fetch time, not the cache hit time (matching §5's "caching MUST NOT break content-addressing" intent). |
| `sampling` | Optional. A `SamplingConfig` sub-record carrying per-prompt sampling configuration. Field shape mirrors llm-provider §6 `RuntimeConfig`: the seven declared fields (`temperature`, `max_tokens`, `top_p`, `seed`, `frequency_penalty`, `presence_penalty`, `stop_sequences`), all optional, plus an extras mapping for vendor-specific fields per `RuntimeConfig`'s extras-pass-through contract. Per-language implementations SHOULD use the SAME type as `RuntimeConfig` (or a structurally-compatible subtype) so callers can splat `prompt.sampling` directly into `provider.complete(config=...)` without per-field translation. The model identifier is NOT part of `SamplingConfig`; per-prompt model selection is out of scope (the bound provider determines the model). Absent (`None` / `null` / `undefined`, per the language idiom) when the backend doesn't supply sampling config for this prompt. |
| `observability_entities` | Optional mapping (`dict[str, Any] \| None`) carrying backend-keyed references to first-class entities the prompt has been registered as in observability backends. Keys follow `<backend>_<entity>` naming. Spec-normative keys: `langfuse_prompt` — the Langfuse SDK Prompt-entity reference, used by observability §8.4.4 to establish the Langfuse Generation → Prompt link. Future observability backend mappings define their own keys. Values are opaque to the spec; per-language implementations determine the concrete type (e.g., the Langfuse Python SDK's `Prompt` class instance, the Langfuse TypeScript SDK's equivalent). Absent / `None` when the backend doesn't expose any such references; absent keys within a populated mapping signal "this backend's reference is not available." |
| `metadata` | Optional implementation-defined mapping of additional backend-supplied metadata (e.g., Langfuse tags, file path of origin, other backend-attribution metadata). The spec does not constrain shape. Note that the Langfuse Prompt-entity reference moved out of this field as of v0.26.0 (proposal 0033) — it now lives on `observability_entities['langfuse_prompt']` so the observability §8.4.4 lookup has a spec-defined location. |

The `name + version + label` triple identifies a prompt; the `template_hash` lets two
prompts with the same name be distinguished by content (e.g., a Langfuse-backed prompt
fetched at two different times with the same `latest` label may have different content).

**Opt-in per backend.** A backend that doesn't supply sampling config or observability
entities returns prompts with those fields as `None`. Callers consume the fields defensively
(checking for absence) or rely on the language's idiom for unset optional fields. The spec
does NOT mandate a default sampling config in the absence of a supplied one — callers fall
back to `RuntimeConfig()` defaults at the provider layer.

### 3.1 Chat-prompt variant

A `Prompt` is one of two variants:

- **Text prompt** — the shape described by the §3 table above; carries `template` (a single
  template per the implementation's chosen representation) and renders to a single text
  Message per §6.render. The simple lane for single-message prompts; remains text-only.
- **Chat prompt** — carries `chat_template: list[ChatSegment]` IN PLACE OF `template`. All
  other §3 fields (`name`, `version`, `label`, `template_hash`, `fetched_at`, `sampling`,
  `observability_entities`, `metadata`) apply identically. Renders to a multi-message
  `PromptResult` per §6.render. The lane for any prompt with structure: multiple roles,
  multimodal content (text + image), and / or variable-length chat-history injection.

A given Prompt is exactly one variant — `template` and `chat_template` are mutually
exclusive on the same Prompt record. The variant MUST be implementation-discriminable
(presence of `chat_template` versus `template`; an explicit type tag; a discriminated-union
shape — per the language idiom).

**ChatSegment.** Each segment in a `chat_template` is one of:

- **Content segment** — `{role: "system" | "user" | "assistant", content: <text-template OR
  content-blocks-template>}`. The `role` matches the canonical message roles from
  llm-provider §3 (Message shape). The `content` is one of:
  - **Text template** — the per-segment unrendered text in the implementation's chosen
    template representation (analogous to the Text-prompt `template` field). Renders to a
    Message with text content. The common case; valid for any role.
  - **Content-blocks template** — a non-empty ordered list of `ContentBlockTemplate` records
    (see *ContentBlockTemplate shapes* below) mirroring llm-provider §3.1 ContentBlock
    shapes. Renders to a Message with a content-blocks `content` per llm-provider §3. Image
    blocks are user-only per llm-provider §3.1.2 — a content-blocks segment containing any
    image block MUST have `role: "user"`; a non-user role with an image-block-containing
    template is a `prompt_render_error` (§11).
- **Placeholder segment** — `{placeholder: str}`. The `placeholder` is a name identifying a
  slot that the caller fills at render time with a `list[Message]` (per llm-provider §3).
  Placeholder names MUST match the regex `[A-Za-z_][A-Za-z0-9_]*` (ASCII-identifier shape:
  non-empty; starts with a letter or underscore; remaining characters are letters, digits,
  or underscores). The constraint is pinned for cross-impl portability and to avoid
  collision with backend-specific placeholder syntax (e.g., Langfuse's `{{name}}`
  delimiters). Placeholder names MUST be unique within a single `chat_template`; a
  duplicate name is a `prompt_render_error` (§11). A placeholder name that does not match
  the identifier regex is also a `prompt_render_error`.

**ContentBlockTemplate shapes.** A `ContentBlockTemplate` mirrors an llm-provider §3.1
ContentBlock with variable-substitutable text fields. The v1 set covers the user-message-
authoring blocks (text + image); thinking and redacted-thinking blocks per llm-provider
§3.1.4 / §3.1.5 are assistant-side round-trip content with provider-bound signatures, not
author-template content, and are not in the v1 ContentBlockTemplate set.

- **Text block template** — `{type: "text", text: <template representation>}`. The `text`
  is a per-block template. Variable substitution (per §6 / §8) produces an llm-provider
  §3.1.1 text block with the rendered text.
- **Image block template (URL source)** — `{type: "image", source: {type: "url", url:
  <template representation>}, media_type?, detail?}`. The `url` field is a per-block
  template; variable substitution produces the final URL. `media_type` and `detail` are
  literal values per llm-provider §3.1.2 / §3.1.3 (not templates) — they're fixed at
  authoring time and don't typically vary per render. Renders to an llm-provider §3.1.2
  image block with `url`-source per §3.1.3.
- **Image block template (inline source)** — `{type: "image", source: {type: "inline",
  base64_data: <template representation>}, media_type: <template representation>,
  detail?}`. The `base64_data` and `media_type` fields are per-block templates (variable
  substitution lets a caller supply pre-encoded bytes and the media type at render time).
  `detail` is literal. Renders to an llm-provider §3.1.2 image block with `inline`-source
  per §3.1.3.

A ContentBlockTemplate's `type` discriminator matches the corresponding llm-provider §3.1
ContentBlock `type`; the rendered ContentBlock shape matches the llm-provider §3.1 shape
exactly. Implementations MAY accept any image `media_type` llm-provider §3.1.2 declares
supported, with the same minimum-set guarantee (`image/png`, `image/jpeg`, `image/webp`).

**Chat-prompt `template_hash`.** For a Chat prompt, `template_hash` is computed over a
canonical serialization of `chat_template` that includes segment order, segment kind, role
+ content for content segments (and for content-blocks segments, the full block sequence
including each block's type, source variant, and template fields), and name for placeholder
segments. Two distinct chat_templates MUST hash to distinct values; two structurally-
identical chat_templates (same segments in the same order with the same roles + content /
blocks + placeholder names) MUST hash to identical values. Implementations SHOULD use the
same hash function as for Text-prompt `template_hash` (e.g., SHA-256 over a canonical
serialization).

## 4. PromptResult shape

A `PromptResult` record:

| Field | Description |
|---|---|
| `name` | String. Propagated from the source `Prompt.name`. |
| `version` | String. Propagated from the source `Prompt.version`. |
| `label` | String. Propagated from the source `Prompt.label`. |
| `template_hash` | String. Propagated from the source `Prompt.template_hash`. |
| `rendered_hash` | String. A stable content-derived hash of the rendered output, computed over a canonical serialization of the full `messages` sequence that includes message boundaries, roles, content (preserving content-block structure per llm-provider §3.1 when present), and `tool_calls` (when present). The canonical serialization is implementation-defined but MUST be deterministic — two renders of the same `Prompt` with the same variables MUST produce identical canonical bytes and thus identical `rendered_hash`. Implementations SHOULD use the same hash function as `template_hash`. |
| `messages` | An ordered, non-empty sequence of `Message` records, per llm-provider §3. Ready to pass to `Provider.complete()`. |
| `variables` | The variable mapping that was used to render. Implementations MAY redact or omit values that contain sensitive content; the keys MUST be present so audit trails can identify what variables were applied. |
| `fetched_at` | Timestamp of when the source `Prompt` was fetched. Implementation-defined precision. When the `Prompt` came from a cache (§6), `fetched_at` MUST reflect the original fetch time, not the cache hit time. |
| `rendered_at` | Timestamp of when this `PromptResult` was rendered. Distinct from `fetched_at`: a single fetched prompt MAY render multiple times. |
| `sampling` | Propagated from the source `Prompt.sampling`. Same shape as §3's `sampling` field; absent when the source Prompt had no sampling config. |
| `observability_entities` | Propagated from the source `Prompt.observability_entities`. Same shape as §3's field; carries the same backend-keyed reference mapping the source Prompt had. Rendering does NOT modify the contents. |

The `rendered_hash` is the cache-key value most useful to downstream consumers — two
calls with the same template AND the same variables produce the same `rendered_hash`,
which is exactly the equivalence relation a memoization layer wants.

## 5. PromptBackend protocol

A `PromptBackend` exposes one operation:

### `fetch(name, label="production")`

Async. Retrieves a `Prompt` by name and label. Returns a `Prompt` record (§3) on success.

- `name` — string. The prompt identifier within this backend. Required.
- `label` — string. The label under which to fetch. Default `"production"`. Backends MAY
  support backend-specific label conventions (e.g., Langfuse's labels are user-defined;
  filesystem backends MAY interpret label as a subdirectory or filename suffix).

Operation semantics:

- `fetch()` MUST be reentrant: multiple concurrent calls on the same backend are
  permitted.
- `fetch()` does NOT render or otherwise mutate the template.
- `fetch()` MUST raise `prompt_not_found` (§11) when no prompt matches `(name, label)`.
- `fetch()` MUST raise `prompt_store_unavailable` (§11) when the backend is unreachable
  (network failure, filesystem I/O error, vendor API timeout).

Backends MAY cache their own results internally (e.g., a Langfuse backend caching by
`(name, label)` for some TTL); cache invalidation is implementation-defined. When a
backend serves a cached result, the returned `Prompt`'s `template_hash` MUST still be
correct for the served template (caching MUST NOT break content-addressing).

The protocol is deliberately small — backends are fetchers, nothing more. Composition,
fallback, and rendering are the manager's concern.

**Returned `Prompt` variant.** The returned `Prompt` MAY be either variant per §3.1 (Text-
prompt or Chat-prompt). The protocol does not constrain which variant a backend produces;
backends SHOULD document which variants they emit (e.g., a Langfuse-backed `PromptBackend`
returns a Text-prompt for Langfuse TEXT prompts and a Chat-prompt for Langfuse
`ChatPromptClient` prompts, mapped one-to-one). Callers that need a specific variant
should validate the returned Prompt at the call site.

**Backends MAY populate `Prompt.sampling` and `Prompt.observability_entities`** from any
source the backend has access to. Common sources:

- A Langfuse-backed `PromptBackend` sources `sampling` from Langfuse's `prompt.config`
  field, and populates `observability_entities['langfuse_prompt']` with the Langfuse SDK's
  Prompt entity reference for use by observability §8.4.4's Generation linkage.
- A filesystem `PromptBackend` MAY adopt the convention of loading a sidecar file (see
  *Filesystem sidecar conventions* below).
- A database-backed backend loads from a per-prompt config column.
- A test / mock backend leaves both fields as `None` for prompts that don't need them.

When a backend supplies `Prompt.sampling`, it MUST construct the sub-record per §3's shape
(the seven declared fields plus extras mapping; declared-field types match `RuntimeConfig`).
A backend that sources from a vendor system with a richer config shape MUST project to the
declared `SamplingConfig` shape, placing vendor-specific fields under the extras mapping per
§3's extras-pass-through analog of llm-provider §6.

**Filesystem sidecar conventions (informative).** Filesystem backends MAY adopt either of
two conventions for sourcing `sampling`:

- **Per-prompt sidecar:** for a template at `<root>/<name>.j2`, also read
  `<root>/<name>.config.json` (or equivalent extension) and populate `Prompt.sampling`
  from its contents. The file's top-level JSON is a single `SamplingConfig`; the prompt
  name comes from the file path, so the file itself does NOT include a `name` field.
- **Unified config file:** read a single `<root>/prompt_configs.json` at backend
  construction time, keyed by prompt name; populate `Prompt.sampling` from the entry
  matching the fetched name. The file's top-level JSON is a mapping from prompt name to
  `SamplingConfig`.

The conventions are informative; the spec does NOT mandate a specific filesystem layout.
Implementations are free to use either convention, both, or neither (e.g., loading from a
separate config service). The normative contract is the `Prompt.sampling` field itself, not
the file convention that produces it.

## 6. PromptManager interface

A `PromptManager` is constructed with one or more `PromptBackend`s and (optionally) a
`LabelResolver` (per §7). It exposes:

### `fetch(name, label=None)`

Async. Fetches a `Prompt` by name and label, consulting backends in order per §9
fallback semantics. Label resolution:

1. If `label` is explicitly supplied (non-`None`), use it verbatim. Manager passes it
   through to backend `fetch(name, label)` calls.
2. If `label` is `None` (or absent) AND the manager has a `LabelResolver` configured,
   consult the resolver per §7: `label = resolver.resolve(name)`. Manager passes the
   resolved label to backends.
3. If `label` is `None` (or absent) AND no `LabelResolver` is configured, use the default
   `"production"` (backwards-compatible with the v0.15.0 default).

The default value for the `label` parameter is `None` (or the language's idiomatic "unset"
sentinel) rather than the string `"production"`. This makes the resolver / default chain
explicit: callers who want to force-pass `"production"` continue to do so; callers who
want the resolver to decide simply omit the argument.

Returns a `Prompt`. Raises `prompt_not_found` if no backend produces the prompt; raises
`prompt_store_unavailable` only when ALL backends are unavailable.

### `render(prompt, variables=None, placeholders=None)`

Synchronous (rendering is local — no I/O). Applies `variables` (and, for Chat prompts,
`placeholders`) to `prompt.template` or `prompt.chat_template` and returns a `PromptResult`
(§4).

- `prompt` — a `Prompt` record (§3), Text-prompt or Chat-prompt variant. Required.
- `variables` — mapping of template variable names to values. Default empty.
- `placeholders` — optional mapping of placeholder name → `list[Message]` (each `Message`
  per llm-provider §3). Default empty. Meaningful only when `prompt` is a Chat-prompt
  variant containing placeholder segments.

Render semantics common to both variants:

- The result's `name`, `version`, `label`, `template_hash` are propagated from the input
  `prompt`.
- `variables` (the input) are recorded on the result. The `placeholders` mapping is NOT
  recorded on `variables`; implementations MAY surface it on a separate field on
  `PromptResult` for audit symmetry but the spec does not require it.
- `rendered_at` is set to the call time; `fetched_at` is propagated from `Prompt.fetched_at`
  (per §3).
- `rendered_hash` is computed from the rendered messages (over the canonical serialization
  of the full `messages` sequence per §4 — including the content-block sequence for
  messages whose `content` is a block sequence).
- Variable handling follows §8.

**Text-prompt render contract.** When `prompt` is a Text-prompt variant, `render` produces
exactly one `Message` with `role: "user"` and `content` equal to the rendered template
text. The `placeholders` parameter MUST be ignored when rendering a Text prompt;
implementations MUST NOT raise on a non-empty `placeholders` mapping passed alongside a
Text prompt. (Pinned for cross-impl portability — callers wrapping `render()` generically
across both variants can pass `placeholders` unconditionally without per-variant
discrimination.) Multi-message and multimodal prompts MUST use the Chat-prompt variant
(`chat_template`).

**Chat-prompt render contract.** When `prompt` is a Chat-prompt variant, render produces
`PromptResult.messages` by walking `chat_template` in order:

- **Content segment, text-template `content`.** Apply per-segment variable substitution to
  `content` using `variables` (§8 strict-undefined rule applies per segment, per §8). The
  rendered text becomes a single `Message` whose `role` matches the segment's `role` and
  whose `content` is the rendered text. The resulting Message appends to
  `PromptResult.messages`.
- **Content segment, content-blocks-template `content`.** For each block in the segment's
  content-blocks list, in order:
  - **Text block template.** Apply variable substitution to the block's `text` field;
    produce an llm-provider §3.1.1 text block with the rendered text.
  - **Image block template.** Apply variable substitution to the block's template fields
    per the *ContentBlockTemplate shapes* enumeration in §3.1 (URL form: substitute into
    `url`; inline form: substitute into `base64_data` and `media_type`); produce an
    llm-provider §3.1.2 image block with the resolved source. The literal `detail` field
    passes through unchanged.

  The rendered block list becomes the `content` of a single Message whose `role` matches
  the segment's `role`. The resulting Message appends to `PromptResult.messages`. §8
  strict-undefined applies per text-template substitution within each block. Role-block
  compatibility (image blocks user-only) is enforced per §11.
- **Placeholder segment.** Look up `placeholders[<placeholder name>]`. If present, the
  resolved `list[Message]` appends to `PromptResult.messages` in order — each injected
  Message MUST appear as a standalone Message in the output (no merging across adjacent
  placeholder slots and no merging with surrounding content segments). If the placeholder
  name is absent from `placeholders` (including the case where `placeholders` itself is
  `None` / omitted), raise `prompt_render_error` (§11).

An injected `list[Message]` MAY be empty; an empty list contributes zero messages to the
output and is NOT an error. This natively handles the chat-history "first turn / no prior
messages" case without weakening the §8 / §11 empty-segment rule below.

The FINAL rendered `messages` sequence MUST be non-empty per §4. A Chat-prompt render
that produces zero messages — e.g., a `chat_template` consisting only of placeholder
segments that all inject empty lists, or any other combination that yields no rendered
Message — raises `prompt_render_error` (§11). The per-placeholder empty-list-valid rule
above remains: empty per-placeholder injections are valid when other segments contribute;
only the all-empty global result fails the non-empty invariant.

Render is synchronous because it is purely a transformation step over the in-memory
template; no backend I/O is involved. Async render would surface no benefits and would
needlessly couple the operation to the host's event loop.

### `get(name, label=None, variables=None)`

Async. Convenience equivalent to `render(await fetch(name, label), variables)`. Same
label-resolution rule as `fetch()` (per the three-step chain above): explicit label →
resolver → spec-fallback `"production"`. Implementations SHOULD provide this as a
convenience for the common single-shot path; users wanting fetch/render separation use
`fetch` and `render` directly.

## 7. LabelResolver

A `LabelResolver` is an optional helper that maps prompt names to labels for
deployment-time A/B testing — flip one prompt to `staging` or `variant-a` without code
changes by updating the resolver's data.

Operation:

### `resolve(name) -> str`

Synchronous. Returns the label to use when fetching the prompt named `name`. Pure
function; deterministic for given resolver state.

**Fallback chain.** Implementations MUST resolve in this order:

1. **Per-name override.** If the resolver has a specific label mapped for `name`, return
   it. (Highest precedence.)
2. **Default override.** If the resolver has a default label configured (e.g., a
   `"default"` key in a mapping source), return that.
3. **Spec fallback.** Return `"production"`. (Lowest precedence, backwards-compatible
   with v0.15.0's default.)

The contract is on the precedence order and on the spec-fallback value, not on how the
resolver stores its data. Implementations MAY back resolvers with:

- A static mapping (in-memory dict / record).
- A JSON file (e.g., `prompt_labels.json` keyed by prompt name).
- An environment-variable lookup.
- A remote config service (resolution result MAY be cached).

**Configuration shape (informative).** A common pattern is a JSON file structured as:

```json
{
  "default": "production",
  "segment_semantic": "staging",
  "extract_claims": "variant-a"
}
```

Under this shape, the resolver returns `"staging"` for `segment_semantic`, `"variant-a"`
for `extract_claims`, and `"production"` (the file's `"default"` value, which equals the
spec-fallback in this case) for every other prompt name.

**No resolver, no problem.** A `PromptManager` constructed without a `LabelResolver`
follows the §6 rule's step 3 directly: when no label is supplied at fetch time, use
`"production"`. Existing v0.15.0 callers continue to work without modification.

## 8. Variable injection

Render MUST treat undefined variables as errors by default. When a template references a
variable that is not present in the `variables` mapping passed to `render()`, render MUST
raise `prompt_render_error` (§11). Silently substituting empty strings or `null` is
forbidden by default.

Implementations MAY offer an explicit opt-out (e.g., a `strict=False` flag on `render`,
a per-template directive) for callers who need lenient behavior. When opted out, the
spec does not constrain the substitution semantics; implementations SHOULD document
their choice.

The strict default is a safety property: silent substitution masks bugs (a typo'd
variable name produces a working-but-wrong prompt, often invisibly), and the cost of
opting out per-call is small for the rare cases where leniency is wanted.

This requirement maps to Jinja2's `StrictUndefined` (Python) and to per-language
equivalents (TypeScript template engines vary; implementations document their concrete
choice). The spec mandates the behavior; the configuration knob is per-implementation.

**Per-segment and per-block scope (Chat-prompt variant).** When rendering a Chat prompt,
strict-undefined applies INDEPENDENTLY per segment, and within a content-blocks segment
also INDEPENDENTLY per block. A variable referenced inside one segment but absent from
`variables` raises `prompt_render_error` for that segment and aborts the render; a variable
referenced in segment N but not in segment M (where both appear in the same
`chat_template`) is checked only against segment N's references when segment N is rendered.
Within a content-blocks segment, a variable referenced inside a text-block template's
`text` field, an image-block template's `url` field, or an image-block template's
`base64_data` / `media_type` fields raises `prompt_render_error` when missing —
independently per block. The implementation-specific opt-out (when offered per the
paragraph above) applies per segment and per block.

## 9. Composite backends and fallback

A `PromptManager` constructed with multiple backends MUST consult them in order. The
fallback contract:

- For each backend in order, call `fetch(name, label)`.
- If the backend returns a `Prompt`, that prompt is the result; further backends are not
  consulted. (First-match semantics.)
- If the backend raises `prompt_not_found`, **the fallback chain stops**. The error
  propagates to the caller. A `prompt_not_found` is a logical "this prompt does not exist
  under this name + label" — falling back to a secondary backend would silently resurface
  an old version under a name the operator may have intentionally retired.
- If the backend raises `prompt_store_unavailable`, the manager tries the next backend.
  After exhausting all backends with `prompt_store_unavailable`, the manager raises
  `prompt_store_unavailable` to the caller.

This contract distinguishes infrastructure failure (transient; fall back) from logical
absence (terminal; do not silently substitute). The two cases have different operational
meanings — one is "the network is down; please use the local copy"; the other is "this
prompt was deleted; please don't quietly serve a stale version" — and conflating them
masks bugs in production.

The chartered example of "Langfuse primary, local fallback" composes correctly under
this contract: Langfuse outages route to the local copy; an operator who deleted a
prompt from Langfuse to retire it gets a `prompt_not_found` (not a silently-served local
copy) so the calling pipeline can surface the misconfiguration.

Implementations SHOULD log fallbacks (a `prompt_store_unavailable` from one backend
followed by a successful fetch from the next) at WARN level so operators see when
their primary backend is degraded.

## 10. PromptGroup

A `PromptGroup` composes two or more `PromptResult` instances under a single tracing
grouping. The group itself does not execute the calls or pass output between them — it
is a structural grouping that lets observability surface related prompts as one logical
unit under a shared name.

A `PromptGroup` record:

| Field | Description |
|---|---|
| `group_name` | String. A stable identifier for this group pattern. Used by observability §5.5 cross-reference (per §12) so all spans under the group share an `openarmature.prompt.group_name` attribute. |
| `members` | An ordered sequence of at least two `PromptResult` instances. Order matches the application's intended call sequence (first member runs first); the spec does not require sequential execution, but observability tools MAY use member order to lay out the group visually. |

The group is a hint to observability, not a control-flow primitive. User code is
responsible for executing each member's LLM call in whatever sequence the application
needs (sequential, parallel, conditional), parsing intermediate outputs, and rendering
later members with variables derived from earlier members' outputs. The group's
contribution is the `group_name` that observability propagates onto every member call's
span so trace UIs can group them as one unit.

The two-member case (a classifier followed by a specialized follow-up) is the most
common shape and works under this primitive without any specialization. Larger groups
handle real workloads:

- **Multi-stage classification** — `members = [coarse_classify, fine_classify, answer]`.
- **RAG with reranking** — `members = [query_rewrite, retrieve, rerank, answer]`.
- **Self-correction loops** — `members = [generate, critique, revise]`.
- **Map-reduce over chunks** — `members = [chunk_classify_1, ..., chunk_classify_N, synthesize]`.

Implementations MAY ship higher-level helpers that automate specific group shapes (a
two-step classifier+follow-up helper, a self-correction loop helper, etc.), but those
helpers are ergonomics on top of this spec, not part of the spec.

Empty groups and single-member groups are both spec-invalid; `members` MUST contain at
least two elements. (Single-prompt tagging is already served by the per-prompt
observability attributes in §12 — `openarmature.prompt.name`,
`openarmature.prompt.version`, `openarmature.prompt.label` —
without needing a degenerate group-of-one.)

## 11. Errors

Three canonical error categories:

- `prompt_not_found` — no prompt matches `(name, label)`. Raised by
  `PromptBackend.fetch()` and propagated by `PromptManager.fetch()` per §9 fallback
  semantics. Non-transient (retrying the same name + label will not succeed without
  changing the backends or the prompt store contents).

- `prompt_render_error` — render failed. Raised by `PromptManager.render()` when:
  - the template references an undefined variable under strict-by-default §8 handling, OR
  - the template fails to parse (syntax error in the template language), OR
  - a variable's value is not coercible to the template's expected type.

  *Additional Chat-prompt-specific triggers* (raised under the same `prompt_render_error`
  category):

  - a text-template content segment renders to the literally-empty string (zero
    characters), OR a content-blocks segment contains a `{type: "text"}` block whose
    rendered `text` is the literally-empty string. **Pinned: "empty" means literally
    zero characters after variable substitution; no leading / trailing whitespace
    stripping is applied.** A content segment whose template is empty before substitution
    OR whose template resolves any variable to `""` such that the rendered text is `""`
    raises. Cross-impl portability requires the same trigger condition.
  - a content-blocks segment has an empty block list (zero blocks).
  - a `{placeholder: <name>}` segment's `<name>` is absent from the `placeholders` mapping
    passed to `render` (distinct from `placeholders[<name>] = []` — present-with-empty-
    value is valid and contributes zero messages per §6.render).
  - a `chat_template` contains duplicate placeholder names (§3.1 placeholder uniqueness
    rule), OR a placeholder name that does not match the §3.1 identifier regex
    (`[A-Za-z_][A-Za-z0-9_]*`).
  - a content-blocks segment contains an image block with `role` other than `"user"` (per
    llm-provider §3.1.2's user-only constraint on image blocks; this is enforced at
    render time as the earliest point at which both the segment's role and its block list
    are known; implementations MAY also detect at prompt-construction time for faster
    feedback, but the spec-normative point of enforcement is render).
  - the final rendered `messages` sequence is empty (e.g., a `chat_template` consisting
    only of placeholder segments that all inject empty lists). The non-empty
    `PromptResult.messages` invariant (§4) MUST hold for every successful render.

  The error MUST expose the prompt's `name`, `version`, `label`, the variable mapping
  (with sensitive values redacted per implementation policy), and a description of the
  render failure (which segment / block / placeholder triggered, where applicable).
  Non-transient.

- `prompt_store_unavailable` — backend infrastructure failure (network unreachable,
  filesystem I/O error, vendor API 5xx, vendor API timeout). Raised by
  `PromptBackend.fetch()`. Transient — the same fetch may succeed when the backend
  recovers. `PromptManager.fetch()` raises this only after ALL composed backends raise
  it (per §9).

Each error MUST expose a `category` identifier (matching the strings above, per the
language's idiom — error class, error code, tagged discriminant). Provider-originated
errors (e.g., a Langfuse SDK exception) SHOULD preserve the underlying exception as
cause.

## 12. Cross-spec touchpoints

### Llm-provider §3 (Message shape)

`PromptResult.messages` is a sequence of `Message` records per llm-provider §3. The
prompt-management capability does not redefine the message shape; it produces messages
that conform to llm-provider's contract and are directly consumable by
`Provider.complete()`.

### Observability §5.5 (LLM provider span attributes)

When an LLM call is made with messages produced by a managed prompt (i.e., messages
sourced from a `PromptResult`), implementations MAY surface the prompt's identity on
the LLM call's observability span by adding the following attributes to the LLM-call
span (sibling to existing `openarmature.llm.model`, `openarmature.llm.finish_reason`,
etc., per observability §5.5):

- `openarmature.prompt.name` — `PromptResult.name`
- `openarmature.prompt.version` — `PromptResult.version`
- `openarmature.prompt.label` — `PromptResult.label`
- `openarmature.prompt.template_hash` — `PromptResult.template_hash`
- `openarmature.prompt.rendered_hash` — `PromptResult.rendered_hash`
- `openarmature.prompt.group_name` — when the call was part of a `PromptGroup`, the
  group's `group_name` propagates to every member span so trace UIs can render them as
  a single grouping.

The propagation mechanism (e.g., a context variable holding the `PromptResult`, an
explicit observer event the manager fires on render) is implementation-defined. The
attribute names are normative.

A follow-on proposal MAY tighten these from `MAY` to `SHOULD` once the propagation
mechanism is settled across implementations; v1 of this capability leaves the
mechanism flexible.

### Llm-provider §6 (RuntimeConfig wiring)

When a managed prompt has `Prompt.sampling` set (per §3), the LLM call site MAY thread
the sub-record through to `provider.complete(config=...)`'s `RuntimeConfig` argument. The
declared-fields-plus-extras shape mirrors `RuntimeConfig` exactly, so the wiring is a
direct splat in the implementation's idiom.

The §6 of llm-provider null-skip semantics applies once the values reach `RuntimeConfig`:
declared fields with value `None` / `undefined` in `Prompt.sampling` MUST be omitted from
the wire body per llm-provider §6. The PromptManager itself does NOT enforce null-skip —
it merely propagates `sampling` to the PromptResult; the wire-layer skip happens at the
RuntimeConfig construction site.

Per-language ergonomics may further provide a convenience method that combines `render()`
+ `complete()` (e.g., a `render_and_call()` or `invoke_with_prompt()` helper that
internally splats `PromptResult.sampling` into the LLM call). Convenience helpers are
out of spec scope; the contract this section establishes is the shape-compatibility
between `Prompt.sampling` and `RuntimeConfig`.

### Observability §8.4.4 (Langfuse Prompt-entity reference lookup)

Observability §8.4.4 specifies when a Langfuse Generation observation MUST be linked to
a Langfuse Prompt entity: "when the prompt's source exposes a Langfuse Prompt reference."
The reference lives at a spec-defined location on Prompt:
`Prompt.observability_entities['langfuse_prompt']`.

When that key is present (value is the opaque Langfuse SDK Prompt reference for the
rendered prompt), the Langfuse observer MUST establish the native link per §8.4.4 case 1.
When the key is absent or `observability_entities` itself is `None`, §8.4.4 case 2
applies (metadata-only, no Prompt-entity link). The trigger semantic is unchanged from
v0.23.0; only the lookup location is now spec-defined rather than
implementation-defined.

The §8.4.4 linkage is keyed on prompt identity (`name + version + label`) and is
**unaffected by Prompt variant** (Text-prompt vs Chat-prompt per §3.1) and by rendered
message count. A Chat-prompt that links to a Langfuse Prompt entity via
`observability_entities` flows through §8.4.4's lookup exactly as a Text-prompt does;
multi-message and multimodal rendering introduces no §8.4.4 changes.

## 13. Determinism

Render is deterministic: the same `Prompt` rendered with the same `variables` MUST
produce a `PromptResult` whose `messages` and `rendered_hash` are bytewise identical
across calls. Implementations MUST NOT introduce wall-clock-derived, random, or
process-state-derived content into render output (e.g., no implicit timestamps, no
process IDs, no random nonces).

User templates MAY include variables that capture nondeterministic values (e.g., the
caller passes `now=datetime.utcnow()` as a variable); the determinism contract applies
to the rendering operation given fixed inputs, not to user-supplied variable values.

Fetch is NOT required to be deterministic across time — a backend MAY return different
`Prompt` records for the same `(name, label)` query at different times (e.g., when an
operator updates the prompt in the source backend). The `version` and `template_hash`
fields on `Prompt` exist precisely to make this observable.

## 14. Out of scope

- **Templating language** — Jinja2, handlebars, simple format strings, etc. Per
  implementation. The spec mandates the render contract (strict undefined, deterministic
  output) but not the syntax.
- **Specific backends** — Langfuse, PromptLayer, file system, in-memory, etc. The spec
  defines the protocol; backends ship as core (a minimum filesystem reference) or
  sibling packages (`openarmature-langfuse` for Langfuse, etc.).
- **Prompt versioning workflows** — how versions are assigned, incremented, pinned,
  promoted. Per project. The spec defines the `version` field; the discipline is the
  user's.
- **Cache invalidation policies** — the spec defines `template_hash` and `rendered_hash`
  that user code MAY use as cache keys; the cache itself is a separate capability
  (potentially a future memoization proposal per pipeline-utilities).
- **Prompt linting / static analysis** — quality checks on prompt content, variable
  coverage analysis, etc. Out of scope; implementations MAY ship as separate tools.
- **Prompt evaluation** — running prompts against test cases and scoring outputs.
  Belongs to the eval capability (charter §4.7).
- **Group execution / orchestration** — `PromptGroup` is a tracing-grouping primitive
  only. Patterns that automate group execution (running members in sequence, parsing
  intermediate outputs, dispatching follow-ups conditionally based on prior results)
  are out of scope; users compose `PromptGroup` with their own application code.
  Higher-level orchestration helpers MAY ship as sibling packages or be specified by
  follow-on proposals once concrete patterns settle.
