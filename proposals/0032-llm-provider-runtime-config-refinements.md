# 0032: llm-provider — RuntimeConfig Surface Refinements

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-26
- **Accepted:** 2026-05-26
- **Targets:** spec/llm-provider/spec.md (modifies §6 *Response and configuration*; extends §8.1 *OpenAI-compatible wire mapping* with the three new declared-field mappings); spec/observability/spec.md (extends §5.5.2 *Request parameters*)
- **Related:** 0006 (llm-provider core), 0024 (LLM span payload + GenAI semconv)
- **Supersedes:**

## Summary

Refine the `RuntimeConfig` surface in llm-provider §6 with three changes
and one observability follow-on:

1. **Promote three cross-vendor sampling fields to declared
   `RuntimeConfig` fields:** `frequency_penalty`, `presence_penalty`,
   and `stop_sequences`. These are cross-vendor standard parameters
   (every major provider — OpenAI, Anthropic, Gemini, Mistral, Cohere
   — supports equivalents) currently handled via the
   implementation-allowed extras path. Promoting them to declared
   fields makes them discoverable, typed, and part of the versioned
   API contract. Field naming follows the cross-vendor OpenTelemetry
   GenAI semconv (`stop_sequences`, not OpenAI's shorter `stop`); the
   §8.1 OpenAI-compatible wire mapping translates `stop_sequences` to
   OpenAI's request-body key `stop` at the wire layer.

2. **Replace the current vague "implementations MAY accept additional
   provider-specific fields" clause with an explicit normative
   pass-through contract:** the spec defines the declared-fields shape;
   undeclared fields supplied by callers MUST be forwarded to the wire
   request body untouched, subject to the wire-format mapping (§8).
   This codifies the behavior every existing adopter already relies on
   to pass vendor-specific knobs (e.g., `repetition_penalty`, `top_k`,
   `min_p` to vLLM-fronting endpoints).

3. **Specify null-skip semantics on declared fields:** a declared
   `RuntimeConfig` field with a value of `None` (or the language's
   equivalent — Python `None`, TypeScript `undefined`) MUST be omitted
   from the wire request body. `None` denotes "field not supplied,"
   distinct from "field supplied with the null value." Callers can
   build partial configs by leaving unset fields as the language's
   default-null and rely on the framework to omit them at the wire
   layer.

4. **Extend observability §5.5.2** with the three new GenAI semconv
   attributes corresponding to the new declared `RuntimeConfig`
   fields: `gen_ai.request.frequency_penalty`,
   `gen_ai.request.presence_penalty`, and
   `gen_ai.request.stop_sequences`. The §5.5.2 emission rule
   ("MUST emit when the corresponding `RuntimeConfig` field is set,
   unless the GenAI semconv opt-out is enabled") applies uniformly
   to the new attributes. The §8.4.3 Langfuse-mapping reference to
   §5.5.2 (which already maps each `gen_ai.request.*` to
   `generation.modelParameters.<suffix>`) picks up the three new
   attributes by inclusion, no §8 edit required.

No breaking changes to existing behavior. Existing callers passing
`frequency_penalty` / `presence_penalty` / `stop` via the extras path
continue to work via the pass-through contract — the extras
pass-through forwards undeclared keys untouched to the wire body, and
OpenAI's `stop` body field continues to accept the value the same way
it does today. Callers who want to use the new declared field switch
their kwarg to `stop_sequences=[...]`; the §8.1 wire mapping handles
the translation to OpenAI's `stop` body field.

## Motivation

The v0.6.0 `RuntimeConfig` declared four fields: `temperature`,
`max_tokens`, `top_p`, `seed`. The closing line of §6 reads:

> Implementations MAY accept additional provider-specific fields. The
> four above are the minimum.

This produced three recurring frictions in production deployments:

1. **Asymmetry across OpenAI-standard sampling parameters.** The
   OpenAI Chat Completions reference treats `temperature`, `top_p`,
   `frequency_penalty`, `presence_penalty`, `max_tokens`, `seed`,
   `stop` as core parameters at the same tier. OA elevates four;
   the other three sit in the implementation-defined extras path.
   Discoverability suffers — IDE autocomplete doesn't surface them,
   type-checking doesn't catch typos (`presnce_penalty=0.1` is a
   runtime extras lookup, not a compile-time error), and the
   versioned API contract doesn't promise them. Each user reading
   the spec re-derives the gap.

2. **Implicit pass-through contract.** The "MAY accept additional
   provider-specific fields" clause says implementations are permitted
   to accept extras, but doesn't normatively say they MUST forward
   them. The behavior every implementation actually ships — vendor-
   specific kwargs ride through to the wire body untouched (e.g.,
   OpenAI-compatible providers fronting vLLM forward
   `repetition_penalty`, `top_k`, `min_p` via the SDK's `extra_body`)
   — is correct, but a new implementation reading the spec has to
   either follow undocumented precedent or invent its own
   approximation. Codifying the pass-through contract removes the
   guesswork.

3. **Null-skip semantics.** When a caller builds a partial config
   (only some fields set), they expect the framework to omit the
   unset fields from the wire request rather than send
   `{"temperature": null}` and risk vendor-specific interpretation
   (some servers treat null as "use default value zero"). Existing
   adopters implement this defensively with dict-comprehension-then-
   splat shims like
   `RuntimeConfig(**{k: v for k, v in maybe_none.items() if v is not None})`.
   The spec is silent on whether the framework should filter Nones
   at the wire layer; mandating omission makes the partial-config
   pattern safe by default without per-caller defensive code.

### Why now

Production deployments adopting the v0.17.0 LLM-payload + GenAI
semconv work (proposal 0024) and the v0.23.0 Langfuse mapping
(proposal 0031) have surfaced this surface as a follow-on adoption
gate. The three frictions above are independent of any specific
wire format (each applies equally to OpenAI, Anthropic, Gemini, and
future mappings), so landing the refinements before the
upcoming §8.2 (Anthropic) and §8.3 (Gemini) wire-format proposals
keeps the request-shape contract uniform across mappings — the
Anthropic and Gemini mappings inherit the full declared set rather
than re-deriving which OpenAI-standard parameters to elevate.

The observability §5.5.2 follow-on is the natural companion. The
§8.4.3 Langfuse mapping (just landed) was refactored to reference
§5.5.2 by inclusion, so adding three new `gen_ai.request.*`
attributes to §5.5.2 expands the Langfuse `generation.modelParameters`
set automatically with no §8 edit. Any future observability
backend-mapping section that references §5.5.2 by inclusion gets the
same automatic expansion.

## Design

The complete text of the §6 and §5.5.2 modifications is reproduced
below.

The spec version under which this lands is determined at acceptance
time and recorded in `CHANGELOG.md`. Anticipated bump: MINOR
(v0.24.0) — new declared fields and new normative clauses, no
breaking changes.

### llm-provider §6 — declared fields (replaces the existing
`RuntimeConfig` table)

A `RuntimeConfig` record:

| Field | Description |
|---|---|
| `temperature` | Float, optional. Provider-specific range; commonly `[0.0, 2.0]`. |
| `max_tokens` | Int, optional. Maximum completion tokens. |
| `top_p` | Float, optional. Nucleus sampling probability. |
| `seed` | Int, optional. Best-effort determinism for providers that support it. Setting `seed` does NOT guarantee determinism; see §9. |
| `frequency_penalty` | Float, optional. Penalty on token frequency; commonly `[-2.0, 2.0]` per the OpenAI reference. Cross-vendor: OpenAI, Mistral, Cohere, and most OpenAI-compatible servers accept this name directly; Anthropic and Gemini map to vendor-specific equivalents at the wire layer (per §8.2 / §8.3 when those land). |
| `presence_penalty` | Float, optional. Penalty on token presence; commonly `[-2.0, 2.0]`. Same cross-vendor framing as `frequency_penalty`. |
| `stop_sequences` | List of strings, optional. Stop sequences. When any string in the list appears in the generated text, generation halts. The OA declared name matches the OpenTelemetry GenAI semconv (`gen_ai.request.stop_sequences`) and the wire-key convention used by most cross-vendor providers (Anthropic uses `stop_sequences`, Gemini uses `stopSequences`). The OpenAI-compatible wire mapping (§8.1) translates this field to OpenAI's request-body key `stop`. Per-provider limits MAY differ (OpenAI accepts up to four; others vary) and are enforced at the wire layer by the provider, not by the framework. |

### llm-provider §6 — extras-pass-through contract (new normative
clause, replaces the existing "Implementations MAY accept additional
provider-specific fields. The four above are the minimum." line)

`RuntimeConfig` is extensible. Implementations MUST accept fields
beyond the declared set above without erroring at the API boundary;
undeclared fields MUST be preserved on the config record and
forwarded to the wire request body untouched, subject to the
wire-format mapping (§8). The wire-format mapping defines how
declared and undeclared fields appear in the provider's request
body; the §6 contract is that undeclared fields reach the wire
intact rather than being silently dropped.

The pass-through MUST NOT translate, rename, or otherwise transform
undeclared fields. A caller passing `repetition_penalty=1.05` MUST
see `repetition_penalty: 1.05` in the wire body (under whatever
sub-object the wire-format mapping defines for vendor-specific
extensions — e.g., OpenAI-compatible §8.1 uses the request body root
for unrecognized keys; Anthropic §8.2 will define its own
convention). The §8 wire-format mapping is the authoritative source
on where undeclared fields land in the body; this clause's
contribution is that they MUST land **somewhere** rather than being
discarded.

Undeclared fields are NOT validated by the spec. The provider's
backend (vLLM, the model server, etc.) is the source of truth on
what extra parameters it recognizes; the framework's job is to make
them reach the backend untouched.

### llm-provider §6 — null-skip semantics (new normative clause,
follows the extras-pass-through clause)

A declared `RuntimeConfig` field with a value of `None` (Python
`None`, TypeScript `undefined`, the language's equivalent
"unset" sentinel) MUST be omitted from the wire request body. Such
a value denotes "field not supplied for this call," distinct from
"field supplied with an explicit null value." Implementations MUST
NOT serialize `None`-valued declared fields as JSON `null` in the
wire body.

The null-skip rule applies to declared fields only. Undeclared
fields supplied to `RuntimeConfig` are forwarded per the
extras-pass-through contract above; if a caller passes an undeclared
field with value `None`, the implementation's wire-format mapping
determines whether that field appears as `null` in the request body
or is omitted (implementation-defined, since the spec does not
constrain undeclared-field types).

This rule lets callers construct partial configs by leaving unset
fields as the language's default-null:

```
config = RuntimeConfig(temperature=0.0, max_tokens=32)
# top_p, seed, frequency_penalty, presence_penalty, stop_sequences
# are all unset (None / undefined). The wire body contains only the
# two declared fields the caller set.
```

Without this rule, callers would have to filter Nones defensively
before constructing a config, as in:

```
non_null = {k: v for k, v in maybe_none.items() if v is not None}
config = RuntimeConfig(**non_null)
```

Mandating the omission at the wire layer makes the partial-config
pattern safe without the defensive shim.

### observability §5.5.2 — request parameters (extended attribute list)

Implementations MUST emit the following attributes on the LLM
provider span when the corresponding `RuntimeConfig` (§6 of
llm-provider) field is set on the request, unless the GenAI semconv
opt-out is enabled (per §5.5.4):

- `gen_ai.request.temperature` — double. Mapped from
  `RuntimeConfig.temperature`.
- `gen_ai.request.max_tokens` — int. Mapped from
  `RuntimeConfig.max_tokens`.
- `gen_ai.request.top_p` — double. Mapped from `RuntimeConfig.top_p`.
- `gen_ai.request.seed` — int. Mapped from `RuntimeConfig.seed`.
- `gen_ai.request.frequency_penalty` — double. Mapped from
  `RuntimeConfig.frequency_penalty`.
- `gen_ai.request.presence_penalty` — double. Mapped from
  `RuntimeConfig.presence_penalty`.
- `gen_ai.request.stop_sequences` — string array. Mapped from
  `RuntimeConfig.stop_sequences`. Both the OA declared field and the
  GenAI semconv attribute use the same name (`stop_sequences`); the
  cross-vendor naming convention is uniform across the OA layer and
  the observability layer. The OpenAI-compatible wire body field
  (`stop`) is the outlier and is handled by §8.1's translation.
  Implementations MUST emit the list verbatim, preserving order.

The remaining §5.5.2 paragraphs (attribute-omission rule for unset
fields, GenAI-semconv-not-OpenArmature rationale, the
cross-vendor-parameters precedent) apply unchanged to the expanded
list.

The §8.4.3 Langfuse mapping (introduced by proposal 0031) references
§5.5.2 by inclusion; the three new attributes flow into
`generation.modelParameters.{frequency_penalty, presence_penalty,
stop_sequences}` automatically, without any §8 edit.

### llm-provider §8.1 — OpenAI-compatible wire mapping (extension)

The existing §8.1 sentence "The §6 `RuntimeConfig` fields map directly:
`temperature`, `max_tokens`, `top_p`, `seed`. The bound model
identifier becomes OpenAI's `model` field." extends to cover the three
new declared fields:

- `frequency_penalty` → OpenAI request-body field `frequency_penalty`
  (same name; maps directly).
- `presence_penalty` → OpenAI request-body field `presence_penalty`
  (same name; maps directly).
- `stop_sequences` → OpenAI request-body field **`stop`** (rename).
  OpenAI's wire body uses the shorter `stop` key; the OA declared
  field is named `stop_sequences` to match the cross-vendor convention
  (the GenAI semconv attribute, Anthropic's `stop_sequences` field,
  Gemini's `stopSequences` field). The wire-mapping layer translates
  the OA declared name to OpenAI's body key on emission and back on
  ingress.

The rename is the only declared-field-to-wire-body translation in the
§8.1 mapping; every other declared field carries the same name on
both sides. Future §8.2 (Anthropic) and §8.3 (Gemini) mappings define
their own per-field translations.

Undeclared `RuntimeConfig` fields (those a caller supplies beyond the
declared set per §6's extras-pass-through contract) appear at the
OpenAI request-body root, as siblings to `temperature`, `model`, etc.
This codifies the behavior every existing OpenAI-compatible adopter
already relies on (e.g., the OpenAI Python SDK's `extra_body=`
parameter; LangChain's wrapper splatting kwargs into the body;
Bifrost's straight pass-through to vLLM). The pass-through MUST
preserve key names and value types verbatim per §6's
extras-pass-through contract.

A short normative note is added to §8.1 announcing the
`stop_sequences` → `stop` rename so that implementers of the
OpenAI-compatible wire mapping don't accidentally emit
`stop_sequences` to the OpenAI request body (where OpenAI's server
would not recognize the field).

## Conformance fixtures

Two new fixtures land at acceptance:

- **`spec/llm-provider/conformance/032-runtime-config-declared-fields-and-null-skip.{yaml,md}`** — exercises both behaviors in one fixture with two cases.
  - Case 1: All seven declared fields set on `RuntimeConfig`; verifies each reaches the OpenAI-compatible §8.1 wire body under the expected key (including the `stop_sequences` → OpenAI body `stop` rename). Includes one undeclared field (`repetition_penalty=1.05`) to verify the pass-through contract — the field MUST appear at the OpenAI request-body root per §8.1's normative convention for undeclared keys.
  - Case 2: Partial config with `temperature` and `max_tokens` set, all other declared fields left as the language's default-null sentinel. Verifies the wire body contains exactly two declared fields; verifies the unset declared fields are NOT present (no `null`-valued entries).

- **`spec/observability/conformance/025-otel-llm-request-params-extended.{yaml,md}`** — exercises §5.5.2's expanded attribute list against the OTel observer. One case: all seven declared `RuntimeConfig` fields set; mock provider returns a basic response; verifies the LLM provider span carries `gen_ai.request.{temperature, max_tokens, top_p, seed, frequency_penalty, presence_penalty, stop_sequences}` with the supplied values.

Existing-fixture update (lands with the accept PR):

- **`spec/observability/conformance/018-otel-llm-request-extras.{yaml,md}`** — currently uses `frequency_penalty` as its example extras key. With `frequency_penalty` promoted to a declared field by this proposal, the fixture's example would no longer demonstrate a true extras key (the value would be sourced from the declared field, not the extras bag). Switch the example to `repetition_penalty: 1.05` (a genuine vendor-specific extra used by vLLM / HuggingFace endpoints; not on any roadmap to become a declared field). Assertions update accordingly: `openarmature.llm.request.extras` carries `{repetition_penalty: 1.05}` instead of `{frequency_penalty: 0.5}`. No behavior contract change to §5.5.1 — only the example key changes.

## Versioning

MINOR bump. The spec's whole-spec SemVer increments to **v0.24.0** on
acceptance:

- Adds three declared fields to llm-provider §6 `RuntimeConfig`.
- Adds two new normative clauses to llm-provider §6 (extras-pass-
  through, null-skip).
- Extends observability §5.5.2 with three new GenAI semconv
  attributes.
- Adds two conformance fixtures.
- No breaking changes. Existing callers passing the three new fields
  as extras continue to work; the new declared fields take precedence
  over a same-named extras key when both are supplied (per Pydantic-
  style framework defaults and per the language idiom).

CHANGELOG entry references this proposal.

## Out of scope

For this proposal specifically:

- **Vendor-specific extras documentation** (`repetition_penalty`,
  `top_k`, `min_p`, vLLM-flavored knobs). Vendor-specific content
  does not belong in the language-agnostic spec; implementations
  document the conventions their reference providers support in
  their own docs. This proposal only formalizes that the framework
  MUST forward such extras untouched, not what specific extras to
  document.
- **Provider-side range validation** for the new declared fields.
  Range validation (e.g., `frequency_penalty ∈ [-2.0, 2.0]`) is the
  provider's responsibility, not the framework's. A caller passing
  `frequency_penalty=5.0` reaches the wire as `5.0`; the provider
  rejects it via the framework's existing `provider_invalid_request`
  error category (per §7).
- **The `min_p` sampling parameter.** Not yet widespread enough to
  warrant a declared field (the HuggingFace / vLLM ecosystem
  established it in mid-2024; broader provider support is still
  emerging). Works via the extras-pass-through contract today; a
  future proposal MAY promote it once cross-vendor adoption settles.
- **Per-language partial-config constructors.** Per-language
  ergonomic helpers (e.g., a `RuntimeConfig.from_partial(**kwargs)`
  constructor that filters language-null kwargs) are implementation
  ergonomics. The spec mandates the wire-layer null-skip; whether
  implementations expose a separate convenience constructor is per-
  language.

## Open questions

None. Three questions flagged at draft time are settled in the
proposal text above:

- **Null-skip rule location** — placed in §6 (general declared-field
  semantics), so future §8.2 / §8.3 wire mappings inherit uniform
  null-skip behavior without re-derivation. The rule expresses what
  `None`/`undefined` means semantically, not how a specific wire
  format serializes it.
- **Range validation timing** — deferred to the provider (rejected
  via the existing `provider_invalid_request` error category).
  Vendor ranges differ and the framework's job is to forward intent
  to the wire untouched.
- **Stop-field naming** — declared field is `stop_sequences`,
  matching the cross-vendor OpenTelemetry GenAI semconv (and
  Anthropic / Gemini wire-key conventions). The §8.1 OpenAI-
  compatible wire mapping translates `stop_sequences` to OpenAI's
  shorter request-body key `stop`. OpenAI is the outlier on the
  shorter name; the OA declared layer matches the cross-vendor
  norm.
