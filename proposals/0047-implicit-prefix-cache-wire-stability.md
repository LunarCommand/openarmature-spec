# 0047: Implicit Prefix-Cache Wire-Byte Stability

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-31
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (§8 framing — new wire-byte stability paragraph requiring intra-impl byte equality across calls with equivalent OA inputs; per-mapping clarifications under §8.1 / §8.2 / §8.3 calling out how the rule applies to that mapping's specifics); spec/prompt-management/spec.md (§13 *Determinism* — tighten with a static-substring cross-variable determinism clause covering renders that differ only in unrelated variable bindings; new §14 *APC-friendly authoring guidance* — informative subsection on placeholder placement, nondeterministic content in static segments, few-shot ordering); spec/observability/spec.md (§5.5.3 — extend GenAI semconv response attribute set with optional cache-usage attributes emitted when the provider response surfaces them); plus new conformance fixtures covering intra-impl wire-byte equality and cache-usage attribute emission.
- **Related:** 0019 (multi-provider extension — established §8 framing this proposal extends with byte-stability requirements), 0024 (LLM span payload + GenAI semconv — established §5.5 cross-vendor LLM attribute convention this proposal extends with cache-usage attributes), 0026 (§8.X wire-format mapping subsection template — the canonical structure each mapping follows; this proposal's wire-byte rule applies uniformly across all subsections), 0046 (multi-message / chat prompt rendering — established the chat_template + placeholder shape this proposal's authoring guidance references)
- **Supersedes:**

## Summary

Inference engines that implement **Automatic Prefix Caching** (APC) — vLLM
running locally, OpenAI's hosted prompt-caching path, llama.cpp's prefix-reuse
optimization, others — skip recomputing attention for token prefixes they have
already processed in a recent request. The cache hit is decided by **byte
equality** of the prefix: a single re-ordered JSON key, a shuffled tool
definition list, or a timestamp embedded in the system prompt invalidates the
cache and re-runs full attention from the first changed byte. On long
system-prompt + RAG-context + chat-history workloads, APC routinely halves
latency and cost; without prefix discipline, those gains do not materialize.

OpenArmature today says nothing about prefix-cache friendliness. Prompts
render deterministically (prompt-management §13 — same Prompt + same
variables → bytewise-identical `PromptResult.messages`), but nothing in
llm-provider's §8 wire-format mappings pins down whether two equivalent OA
requests turn into byte-identical wire output. And when caching IS working,
nothing surfaces that fact through observability — pipelines tune blind.

This proposal closes three gaps with one cross-capability change:

1. **llm-provider §8 — intra-impl wire-byte stability.** Any §8.X wire-format
   mapping MUST produce byte-identical wire output for equivalent OA inputs
   within a given implementation: sorted JSON object keys, deterministic
   array ordering for spec-canonical lists, defensive canonicalization at
   user-supplied-dict boundaries (tool parameter schemas, `RuntimeConfig`
   extras, content-block source dicts). The cross-implementation bytewise
   caveat from observability §5.5.1 (Python and TypeScript MAY differ on JSON
   encoding details) is preserved — the new rule is intra-impl only.

2. **prompt-management §13 / §14 — cross-variable determinism pin +
   APC-friendly authoring guidance.** §13 *Determinism* tightens with a
   normative clause: the static substring of a rendered output (the portion
   not derived from variable substitution) MUST be identical across renders
   that differ only in unrelated variable bindings. A new §14 (informative)
   *APC-friendly authoring guidance* documents the authoring discipline that
   makes APC hits reliable — place variables and chat history at the end of
   `chat_template`, avoid timestamps / UUIDs / nondeterministic values in
   static segments, maintain stable few-shot ordering.

3. **observability §5.5.3 — optional cache-usage GenAI semconv attributes.**
   When the LLM provider's response surfaces cache statistics (vLLM reports
   `cached_tokens` in its OpenAI-compatible usage details; OpenAI surfaces
   `prompt_tokens_details.cached_tokens`; future providers may follow), the
   OTel observer emits a GenAI semconv attribute carrying the value. Absent
   the field, the attribute is not emitted (matching the existing §5.5.2 /
   §5.5.3 conditional-emission convention).

Scope is **implicit caching only** — the kind decided by the inference engine
without API-level cache markers. Explicit-cache primitives (Anthropic's
`cache_control` blocks, OpenAI's request-cache keys when those exist, Gemini's
cached-content references) are a different mechanism and a separate proposal
if cross-vendor demand surfaces.

The change is backwards-compatible: existing applications that don't care
about caching keep working as today; the proposal makes the wire-shape
predictable for any application that does want APC hits, and surfaces the
cache-effectiveness signal for any application that wants to measure it.

## Motivation

Three concrete pressures converge:

**APC is real and load-bearing.** Local vLLM deployments routinely see 40-60%
prompt-token cache hit rates on long-context LLM workflows (RAG with stable
retrieval context, multi-turn chat with growing history, few-shot prompts with
fixed example banks). Hit rate translates directly to latency and cost
reduction. Hit rate also is brittle: a single byte mismatch in the prefix
re-runs full attention from that position. Application-side discipline is the
gating factor — the inference engine can only cache what the app sends
stably.

**OA owns the prefix shape.** OpenArmature is between the user and the wire.
Every byte that reaches the inference engine flows through one of OA's §8
wire-format mappings. The decisions OA makes — how it serializes tool
definitions, what order it places content blocks, whether it sorts JSON keys
or relies on dict iteration order — directly determine whether two equivalent
OA requests produce cache-friendly bytes. Today those decisions are
implementation-defined; in practice they vary at the points where user input
shapes flow through (user-supplied JSON Schema for tool parameters,
`RuntimeConfig` extras, content-block construction).

**Observability is the feedback loop.** Tuning prefix-cache hit rate requires
seeing the hit rate. The provider's response carries the signal (vLLM's usage
details, OpenAI's `prompt_tokens_details`); the OTel observer is the natural
place to surface it. Without the signal, every prompt change is a blind
A/B test on production latency.

The proposal is forward-looking but not speculative: the three changes are
each individually small, individually have clear acceptance criteria, and
individually have backwards-compatible defaults. Their bundling reflects a
single cross-cutting concern — implicit caching as a first-class spec
concern — rather than three unrelated pieces of work.

## Proposed change

### §8 *Wire-format mappings* — intra-impl byte stability (llm-provider)

Add a new top-level paragraph to §8's framing section (after the
*Per-mapping subsection structure* paragraph established by proposal 0026 and
before §8.1):

> **Intra-impl wire-byte stability.** Any §8.X mapping implementation MUST
> produce byte-identical wire output for OA-input pairs that are
> structurally equivalent. Two `complete()` calls passing the same
> `messages` sequence, the same `tools` list, the same `config`, the same
> `tool_choice`, and (when present) the same `response_schema` MUST emit
> identical wire-format request bytes from the same implementation. Sources
> of nondeterminism implementations MUST control for:
>
> - **JSON object key ordering** within wire-format objects implementations
>   construct (tool definitions, message records, content blocks, request-body
>   roots) MUST be sorted lexicographically OR follow a stable
>   implementation-defined key order. Construction-time dict-insertion order
>   that varies across calls (e.g., a tool schema built from a mapping whose
>   key order reflects build-time iteration) MUST be canonicalized before
>   serialization.
> - **Array ordering** for spec-canonical lists (the messages list, the
>   tools list, the content-block sequence, the `stop_sequences` list) MUST
>   preserve caller-supplied order. This is already implicit in the §3 / §4
>   shapes; the stability rule makes it explicit at the wire boundary.
> - **JSON Schema in `Tool.parameters`** is user-supplied content with no
>   spec-imposed key ordering. The wire-format mapping MUST canonicalize the
>   schema's key order (sorted recursively) before emission — without this
>   step, two semantically-equivalent schemas built differently produce
>   different wire bytes. The same rule applies to JSON Schema in
>   `response_schema` (§5).
> - **`RuntimeConfig` extras** (the pass-through fields permitted by §6's
>   extras-pass-through contract) MUST be emitted at their wire placement
>   per the mapping's existing rule (§8.1 places them at the request-body
>   root) with sorted key order, regardless of insertion order in the
>   construction-time mapping.
> - **Content-block source dicts** (an image block's `source: {type: "url",
>   url: ...}` or `source: {type: "inline", base64_data: ...}`) are spec-
>   structured records; key ordering within them follows the sorted-keys
>   rule above.
>
> The rule applies **intra-implementation only** — the existing observability
> §5.5.1 caveat ("cross-implementation bytewise stability NOT required —
> JSON encoding rules vary across language standard libraries") applies
> identically here. Cross-language byte equality (Python and TypeScript
> producing identical wire bytes for the same OA input) is NOT required and
> is out of scope; APC's hit rate is computed on a per-deployment basis (one
> language port at a time), so intra-impl stability is sufficient for the
> use case.
>
> Implementations SHOULD document the canonicalization mechanism (e.g.,
> "object keys serialized via `json.dumps(..., sort_keys=True)`") so users can
> reason about which inputs collide on the cache. The §8.X.4 *Concurrency*
> subsection MAY note any concurrency interaction (none expected — the rule
> is pure transformation, not state).

Each existing §8.X subsection (§8.1 OpenAI-compatible, §8.2 Anthropic
Messages, §8.3 Google Gemini) extends with a *Wire-byte stability* note in
its Request mapping subsection (§8.1.1, §8.2.1, §8.3.1) calling out the
mapping's specifics:

- **§8.1.1 (OpenAI-compatible)** — tool definitions, `tool_choice` records,
  the messages list, and the `response_format.json_schema.schema` (per
  §8.1.5) all canonicalize per the §8 rule. The undeclared-field
  pass-through at the request-body root (§8.1.1's existing extras row)
  emits with sorted keys. Inline-image data URIs (§8.1.1.1) produce
  byte-stable encodings — the `data:<media_type>;base64,<base64_data>`
  format has only one canonical form given the source block's fields.
- **§8.2.1 (Anthropic Messages)** — `system` extraction concatenates with a
  stable separator (`\n\n` per §8.2.1) and preserves source order, so the
  result is byte-stable. `tools[].input_schema` canonicalizes per the §8
  rule. `tool_use` and `tool_result` content blocks (per §8.2.1.1 /
  §8.2.1.2) serialize with sorted keys; the `tool_use.input` field
  (deserialized mapping per the §8.2.1.1 row) canonicalizes recursively.
- **§8.3.1 (Google Gemini)** — applies the same rule across Gemini's
  request body shape; specifics follow Gemini's wire layout (function
  declarations, content parts, etc.) per 0038's mapping.

### §13 *Determinism* — cross-variable substring stability (prompt-management)

The existing §13 paragraph reads:

> Render is deterministic: the same `Prompt` rendered with the same
> `variables` MUST produce a `PromptResult` whose `messages` and
> `rendered_hash` are bytewise identical across calls.

Add a follow-up paragraph:

> **Cross-variable substring stability.** The static substring of a rendered
> output — the portion of `messages` content not derived from variable
> substitution — MUST be identical across renders with different variable
> bindings; changes to variable values affect only the variable-derived
> bytes. A render with `variables={"a": "x"}` and a subsequent render with
> `variables={"a": "y"}` MUST produce
> `PromptResult.messages` content whose non-variable-derived bytes (system
> prefix text, few-shot exchange text, segment role markers, etc.) are
> bytewise identical between the two renders. This rule is implementation-
> natural for template engines that perform pure substitution (Jinja2 with
> `StrictUndefined`, mustache-style engines, per-language equivalents) but
> is made explicit here because it is the substring stability that
> downstream prefix-caching (inference-engine APC) relies on. Implementations
> using template engines with side-effecting features (conditional sections
> that branch on variable values, loops that emit context, etc.) MUST ensure
> the static substring rule still holds — variable-dependent control flow
> is permitted, but its emitted bytes are then "variable-derived" and the
> stability requirement does not extend to them.

### §14 *APC-friendly authoring guidance* (prompt-management — new, informative)

Add a new §14 subsection (renumbering the existing §14 *Out of scope* to
§15):

> **§14. APC-friendly authoring guidance (informative)**
>
> Inference engines that implement Automatic Prefix Caching (APC) — vLLM,
> OpenAI's hosted prompt-caching, llama.cpp's prefix-reuse path, others —
> cache the computed attention state for token prefixes that have been
> processed in recent requests, skipping recomputation when a subsequent
> request shares the same prefix bytes. Cache hits translate directly to
> latency and cost reduction on long-context LLM workloads (RAG with stable
> retrieval context, multi-turn chat with growing history, few-shot prompts
> with fixed example banks).
>
> Cache hits require **prefix byte stability**. The spec's normative rules
> (§13 *Determinism* with the cross-variable substring clause above, plus
> llm-provider §8's intra-impl wire-byte stability) guarantee that two
> equivalent OA requests produce equivalent wire bytes. The following
> authoring patterns make those byte-stable prefixes long enough to be worth
> caching:
>
> 1. **Place variables and chat history at the end of `chat_template`.** A
>    `chat_template` of `[system, user]` where the system segment is static
>    and the user segment holds the variable portion has a long static
>    prefix (the system bytes). A `chat_template` that interleaves variables
>    into early segments (e.g., a system segment that references `{{user_id}}`)
>    breaks the prefix at the first variable substitution. Place static
>    content (system preambles, few-shot examples, tool definitions) first;
>    place variables (user input, RAG-retrieved context, chat history
>    placeholders) last.
> 2. **Avoid embedding nondeterministic content in static segments.**
>    Timestamps (`datetime.utcnow()`), UUIDs generated per-call, random
>    seeds, request-IDs, or any value that varies across calls invalidates
>    the cache when embedded in an otherwise-static segment. If a request-ID
>    or correlation-ID is genuinely needed in the prompt content, place it
>    in a variable-bound segment at the END of `chat_template` so the
>    earlier prefix stays stable.
> 3. **Maintain stable few-shot ordering.** Few-shot example banks shuffled
>    per-call (e.g., to mitigate ordering bias) break the cache. If
>    shuffling is needed for output quality, the resulting requests are
>    inherently uncacheable; consider whether a fixed canonical ordering
>    suffices.
> 4. **Stable `tools` list ordering.** When a `complete()` call supplies a
>    `tools` list (llm-provider §5), the list ordering is preserved on the
>    wire (per the llm-provider §8 wire-byte stability rule). Application
>    code that reorders the tools list per-call (e.g., based on retrieval
>    relevance) breaks the cache; if reordering is needed, the resulting
>    requests are inherently uncacheable.
> 5. **Long-enough static prefix.** Inference engines typically require a
>    minimum prefix length before caching activates (engine-specific;
>    consult your engine's documentation for current thresholds). Very
>    short system prompts may not benefit; longer static contexts (system
>    + few-shot + tool definitions, before user variables) cross the
>    threshold naturally.
>
> The guidance is informative — application code that follows none of these
> patterns is spec-conformant, but is unlikely to see APC benefits. Apps
> that want APC hits follow the patterns; apps with no caching concerns
> ignore them.
>
> Cache-effectiveness measurement is the feedback loop: observability
> §5.5.3 surfaces the provider's reported cache-token count when available
> (see the *§5.5.3 extension* below), making it possible to A/B test prompt
> changes against actual hit-rate impact.

### §5.5.3 — optional cache-usage GenAI semconv attributes (observability)

Extend the §5.5.3 attribute set with optional cache-usage attributes
emitted when the LLM provider's response surfaces them:

> - `gen_ai.usage.cached_tokens` — int. The count of input tokens that hit
>   a prefix cache, as reported by the provider's response (e.g., vLLM's
>   OpenAI-compatible `prompt_tokens_details.cached_tokens`; OpenAI's
>   `prompt_tokens_details.cached_tokens`; future providers reporting under
>   the same shape or a documented equivalent). Emitted only when the
>   provider's response carries the value; absent otherwise (matching the
>   conditional-emission convention of §5.5.2 / §5.5.3 for fields the
>   provider does not return).
>
> **Open question:** the exact source of this value is provider-dependent —
> vLLM's `prompt_tokens_details.cached_tokens` is the most-cited shape (it
> matches the OpenAI Chat Completions wire convention adopted by vLLM's
> OpenAI-compatible API), but the field name and nesting MUST be verified
> against current vendor docs before the Accept-phase normative text lands.
> The Accept-phase text SHOULD enumerate which providers populate the field
> and through what response path. If multiple providers report cache stats
> under divergent field names, the attribute name remains
> `gen_ai.usage.cached_tokens` (matching the OTel GenAI semconv naming
> direction) and the §8.X mappings each document their extraction path.

This raises a design fork: the value reaches the OTel observer either (a)
through an extension to llm-provider §6's `Response.usage` shape (a new
optional `cached_tokens: int | None` field, populated by each adapter from
its provider's response), or (b) via the existing `Response.raw` field with
the OTel observer extracting per-provider field paths. Path (a) is the
cleaner contract — `Response.usage` becomes the spec-defined home for usage
stats including cache, and adapters opt in by populating the field; path
(b) avoids changing llm-provider's typed surface but couples the observer
to vendor raw shapes.

This proposal selects **path (a)** — extend `Response.usage` with an
optional `cached_tokens: int | None` field — for the following reasons:
the typed surface is the spec-canonical home for usage data, multiple
providers will populate the field over time (one source of normalization
is better than per-observer extraction), and the Accept-phase normative
text in observability §5.5.3 can reference the typed field rather than
documenting per-provider raw extraction. Path (b) is captured in
*Alternatives considered*.

llm-provider §6 *Response and configuration* extends:

> The `usage` record extends with one optional field:
>
> - `cached_tokens` — int, optional. The count of input tokens that hit a
>   prefix cache, as reported by the provider's response. Absent (`null` /
>   `None` / `undefined`, per the language's idiom) when the provider
>   does not report cache statistics; set to `0` when the provider
>   reports zero cache-hit tokens (the "reported miss" case is distinct
>   from "not reported" and the two MUST be observable separately).
>   Each §8.X wire-format mapping documents the provider response field
>   this value is sourced from.

Each §8.X subsection's Response mapping (§8.1.2, §8.2.2, §8.3.2) extends
with a row mapping the provider's cache-stat field to `Response.usage.cached_tokens`:

- **§8.1.2 (OpenAI-compatible)** — sourced from
  `usage.prompt_tokens_details.cached_tokens` when the response carries the
  field. vLLM, OpenAI's hosted API, and other OpenAI-compatible servers
  that surface prompt-cache stats use this path. Absent on responses
  without the nested field.
- **§8.2.2 (Anthropic Messages)** — Anthropic's response carries
  `usage.cache_read_input_tokens` (plus `usage.cache_creation_input_tokens`
  for explicit-cache writes). The implicit-scope reading is
  `cache_read_input_tokens`; `cache_creation_input_tokens` is
  explicit-cache territory and out of scope. (**Verification needed**:
  field names against current Anthropic docs before Accept.)
- **§8.3.2 (Google Gemini)** — Gemini's usage shape is `usageMetadata` with
  `cachedContentTokenCount` for explicit-cache reads; implicit caching's
  reporting path is **verification needed**.

## Conformance test impact

### New fixtures

Five new fixtures across the three capabilities (numbers assigned at
acceptance):

**llm-provider:**

1. **Wire-byte stability (OpenAI-compatible).** Two `complete()` calls with
   structurally-equivalent inputs constructed differently (e.g., a tool
   parameter schema built from a dict whose keys were inserted in different
   orders, plus a `RuntimeConfig` with extras inserted in different orders).
   Asserts the implementation's emitted wire bytes are byte-identical. Run
   against the §8.1 OpenAI-compatible adapter.

2. **Wire-byte stability (Anthropic Messages).** Same shape as fixture 1
   but exercising §8.2 — Anthropic-specific tool `input_schema`
   canonicalization, `system` extraction byte-stability, `tool_use` block
   serialization. Asserts byte-identical wire output.

**prompt-management:**

3. **Cross-variable substring stability.** Render the same `chat_template`
   with two different variable bindings (`variables={"a": "x"}` vs
   `variables={"a": "y"}`). Asserts the non-variable-derived bytes of
   `PromptResult.messages` content are bytewise identical between the two
   renders. The variable-derived substrings differ as expected.

**observability:**

4. **Cache-usage attribute emission (cache hit).** A `complete()` call
   whose provider response carries `usage.prompt_tokens_details.cached_tokens
   = N` (N > 0; provider-mocked with a fixture response per the existing
   §5.5 fixture pattern). Asserts the emitted OTel LLM provider span carries
   `gen_ai.usage.cached_tokens = N`.

5. **Cache-usage attribute absence (no cache field).** A `complete()` call
   whose provider response does NOT carry the cache field (e.g., a vLLM
   server without prefix caching configured, or a provider that does not
   report the field). Asserts the OTel LLM provider span does NOT carry the
   `gen_ai.usage.cached_tokens` attribute (the conditional-emission
   convention).

### Unaffected fixtures

All existing fixtures across the three capabilities remain valid unchanged.
The proposal's normative changes are additive: §8's wire-byte stability
rule is implementation-natural for any adapter that already constructs wire
output deterministically (most do, by virtue of using stable serialization
paths); §13's cross-variable substring stability is implementation-natural
for any template engine performing pure substitution; §5.5.3's
cache-usage attribute is conditional on a field the provider response may
or may not carry, and adds a row to the existing attribute table.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments:

- New normative wire-byte stability paragraph in llm-provider §8 framing.
  Existing §8.X subsections gain a *Wire-byte stability* note in their
  Request mapping subsections; the rule applies uniformly across §8.1 /
  §8.2 / §8.3 and any future §8.X mapping.
- New `cached_tokens: int | None` optional field on llm-provider §6
  `Response.usage` — additive, default absent, no impact on existing
  callers.
- Cross-variable substring stability clause added to prompt-management §13.
  Implementation-natural for pure-substitution template engines.
- New informative §14 *APC-friendly authoring guidance* in prompt-management
  (renumbers existing §14 *Out of scope* to §15).
- New optional `gen_ai.usage.cached_tokens` attribute in observability
  §5.5.3 — additive, conditional emission.
- New conformance fixtures (wire-byte stability × 2; cross-variable
  substring stability × 1; cache-usage attribute × 2). Existing fixtures
  unchanged.

The change is backwards-compatible across all three capabilities. Existing
applications see no behavioral change; applications opting into APC
discipline get predictable wire bytes for free, and the cache-stat signal
appears in OTel automatically when the provider returns it.

## Alternatives considered

1. **Out-of-tree wire-byte stability (per-impl docs only).** Leave llm-
   provider §8 silent on byte stability and let each implementation
   document its own canonicalization rules. Rejected: byte stability is a
   cross-impl concern (every adapter in every language needs to produce
   stable bytes for its own deployment to benefit from APC), and
   per-impl docs would drift across the four §8 subsections (and across
   the Python and TypeScript ports of each subsection). The spec-normative
   approach gives every adapter the same rule to follow.

2. **Cross-impl byte equality.** Mandate that Python and TypeScript
   implementations of the same §8.X mapping produce byte-identical wire
   output for the same OA input. Rejected: JSON encoding rules vary across
   language standard libraries (number formatting, string escaping,
   key-ordering details), and mandating bytewise cross-impl equality would
   require a canonical JSON scheme (RFC 8785 JCS or equivalent) — heavy
   machinery for a use case (per-deployment APC) that is naturally
   single-impl at runtime. The observability §5.5.1 caveat already
   establishes the cross-impl byte-equality boundary for OTel attribute
   payloads; this proposal keeps the same boundary for wire-format output.

3. **Raw extraction for cache stats (no `Response.usage` extension).**
   Have the OTel observer extract cache-stat fields from `Response.raw`
   directly (e.g., `raw["usage"]["prompt_tokens_details"]["cached_tokens"]`
   for OpenAI-compatible) instead of adding a typed `cached_tokens` field
   to `Response.usage`. Rejected: couples the observer to per-provider raw
   shapes (the OpenAI nested path differs from Anthropic's flat
   `cache_read_input_tokens`); requires the observer to ship a per-provider
   extraction table; and asymmetrical to the existing `Response.usage`
   typed fields (`prompt_tokens`, `completion_tokens`, `total_tokens`)
   which ARE normalized through the §8.X mappings rather than raw-extracted.
   The typed-field approach is the consistent shape and the cleaner
   contract.

4. **Explicit-cache primitives in scope.** Specify a normative OA-side
   surface for explicit cache control (Anthropic's `cache_control` blocks,
   future OpenAI request-cache keys, Gemini's cached-content references).
   Out of scope for v1: explicit caching is a separate mechanism with
   different API ergonomics per vendor (block-level markers on Anthropic
   vs cache-config records on Gemini vs (currently) automatic-only on
   OpenAI), and bundling it with implicit-cache concerns conflates two
   distinct user-facing concepts. A follow-on proposal can add explicit-
   cache primitives if cross-vendor demand surfaces — the implicit-cache
   work in this proposal does not block or complicate that follow-on.

5. **Cache-effectiveness aggregate metrics.** Surface a per-invocation or
   per-pipeline cache-hit rate aggregate as an additional observability
   attribute (`openarmature.llm.cache.hit_rate = 0.62` summarizing N LLM
   calls within the invocation). Rejected for v1: aggregation belongs in
   the observability backend (Phoenix, Langfuse, Honeycomb, Grafana Tempo
   all compute per-span aggregates trivially from `gen_ai.usage.*`
   attributes). Adding a synthetic aggregate at OA's emission layer would
   duplicate work backends do better and pin OA to a specific
   aggregation choice. The per-span `gen_ai.usage.cached_tokens` value is
   the primitive every backend's aggregation infrastructure can consume
   without OA pre-computing.

6. **Sort-keys-on-by-default in `Response.raw`.** Apply the wire-byte
   stability sorted-key rule also to `Response.raw` (the parsed provider
   response — observability §6.5 / llm-provider §6). Rejected:
   `Response.raw` is the provider's response verbatim, parsed as a dict —
   the §6 transparency principle says implementations MUST NOT redact,
   rewrite, or omit fields. Sorting keys on receive would rewrite the dict
   shape (Python dict order is observable) and break the verbatim contract;
   downstream code relying on `raw` to inspect provider-specific extension
   fields (logprobs, vLLM `prompt_logprobs`, LM Studio runtime stats) would
   see different key ordering than the provider returned. The wire-byte
   rule is one-way (OA construction → wire, not wire → OA receive); the
   `Response.raw` shape stays verbatim.

## Out of scope

- **Explicit-cache primitives** — Anthropic `cache_control` blocks, OpenAI
  request-cache keys, Gemini cached-content references. Separate mechanism;
  follow-on proposal if cross-vendor demand surfaces. (Alternative 4.)
- **Cross-impl byte equality** — Python and TypeScript producing identical
  wire bytes for the same OA input. Out of scope; the §5.5.1
  observability caveat applies identically here. (Alternative 2.)
- **Cache-effectiveness aggregate metrics** — per-invocation hit-rate
  summaries computed by OA. Backends compute these from the per-span
  primitive. (Alternative 5.)
- **`Response.raw` key sorting** — `raw` stays verbatim per §6
  transparency. (Alternative 6.)
- **Cache control on `Prompt` or `PromptResult`** — the proposal does NOT
  add a cache-related field to the prompt-management data model. APC works
  on wire-byte equality; the prompt-management contribution is authoring
  guidance + the cross-variable substring stability clause. Adding a
  `cache_anchor`-style field (a hint that a segment should be a stable
  cache boundary) is in the explicit-cache territory and out of scope.
- **Inference-engine-side cache configuration** — APC block size, eviction
  policy, max-prefix-length, etc. Per-engine concern; not OA's surface to
  pin.
- **Best-effort cache-warming primitives** — a feature where OA pre-flights
  a prompt to populate the inference engine's cache before the real call
  fires. Out of scope; users can build this with two `complete()` calls if
  needed.

## Open questions and verification work

The following items require verification against current vendor docs
before the Accept-phase normative text lands. They are flagged here so the
Accept PR's verification step has a checklist:

1. **vLLM's exact response field name for cached prompt tokens.** This
   draft cites `usage.prompt_tokens_details.cached_tokens` (matching the
   OpenAI Chat Completions wire convention). vLLM's OpenAI-compatible API
   adopts the OpenAI shape, so this is likely accurate, but the Accept
   text MUST verify against current vLLM docs / source.

2. **OpenAI's hosted prompt-cache reporting shape.** OpenAI's prompt
   caching surfaces stats; the field path needs current-doc verification.

3. **Anthropic's implicit-cache reporting shape.** Anthropic's response
   carries `usage.cache_read_input_tokens` (explicit-cache reads); whether
   implicit prefix caching has a distinct reporting path or is reported
   under the same field needs verification.

4. **Google Gemini's implicit-cache reporting shape.** Gemini's
   `cachedContentTokenCount` is documented for explicit caching; the
   implicit-cache reporting path (if any) needs verification.

5. **OTel GenAI semconv attribute name for cache stats.** This draft uses
   `gen_ai.usage.cached_tokens`. The upstream OTel GenAI semconv may
   have settled on a different name (e.g.,
   `gen_ai.usage.input_tokens_cached`); the Accept-phase text MUST match
   the upstream convention to preserve the §5.5.3 "use the GenAI semconv
   directly for cross-vendor LLM parameters and response metadata when
   the semconv name is stable" rule.

The Accept PR's verification step (per the established protocol for
external-API-fact verification on proposals) addresses each item before
the normative text lands.
