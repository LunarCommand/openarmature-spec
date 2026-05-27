# 0033: prompt-management — Surface Refinements

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-26
- **Accepted:**
- **Targets:** spec/prompt-management/spec.md (extends §3 *Prompt shape* and §4 *PromptResult shape* with `sampling` and `observability_entities` sub-record fields; extends §5 *PromptBackend protocol* with an informative sidecar convention; extends §6 *PromptManager interface* with optional `LabelResolver` integration; adds new §7 *LabelResolver* primitive — renumbers existing §7-§13 by +1; extends §12 (was §11) *Cross-spec touchpoints* with sampling-to-RuntimeConfig wiring and Langfuse-Prompt-entity-lookup touchpoints); spec/observability/spec.md (clarifies §8.4.4 to name `Prompt.observability_entities['langfuse_prompt']` as the spec-defined location for the Langfuse Prompt reference, replacing the implementation-defined `metadata`-mapping phrasing inherited from proposal 0031)
- **Related:** 0017 (prompt management core), 0024 (LLM span payload + GenAI semconv), 0031 (observability Langfuse mapping), 0032 (llm-provider RuntimeConfig surface refinements)
- **Supersedes:**

## Summary

Four additions to the prompt-management capability, all driven by
production-deployment patterns surfaced during adoption of
proposals 0031 (Langfuse mapping) and 0032 (RuntimeConfig surface):

1. **Typed `sampling` sub-record on `Prompt` (§3) and `PromptResult`
   (§4).** A new optional field carrying per-prompt sampling
   configuration. The sub-record mirrors the declared-fields-plus-extras
   shape of llm-provider §6 `RuntimeConfig` (the seven declared fields
   landed by 0032 — `temperature`, `max_tokens`, `top_p`, `seed`,
   `frequency_penalty`, `presence_penalty`, `stop_sequences` — plus an
   extras mapping for vendor-specific knobs). Callers can splat it
   directly into a `RuntimeConfig` constructor at the LLM call site
   without per-field translation. The model identifier is NOT part of
   this sub-record; per-prompt model selection is out of scope (the
   bound provider determines the model).

2. **Optional `LabelResolver` integration on `PromptManager` (§6) plus
   a new §7 specifying the resolver primitive.** A `LabelResolver`
   maps prompt names to labels for deployment-time A/B testing —
   flip one prompt to `staging` or `variant-a` without code changes by
   updating the resolver's data. The manager MAY be constructed with a
   resolver; `fetch(name)` without an explicit label argument consults
   the resolver. Fallback chain: per-name override → resolver default
   → `"production"`. Existing §13 (was §12) Out-of-scope-mentions
   "where the label comes from" is now addressed.

3. **Informative filesystem sidecar convention on the PromptBackend
   protocol (§5).** A normative addition to the protocol that backends
   MAY populate `Prompt.sampling` from any source — Langfuse's
   `prompt.config`, a database row, a sidecar JSON file. Specifically
   for filesystem backends, the spec recommends (informatively) the
   conventions `<root>/<name>.config.json` (per-prompt sidecar) or a
   unified `<root>/prompt_configs.json` keyed by name. The file shape
   itself is informative; the normative contract is on the field
   appearing on Prompt.

4. **Typed `observability_entities` field on `Prompt` (§3) and
   `PromptResult` (§4).** A normative `dict[str, Any] | None` mapping
   where backends populate backend-keyed references to first-class
   entities the prompt has been registered as in observability
   backends. Keys follow a `<backend>_<entity>` naming convention.
   This proposal defines one spec-normative key: `langfuse_prompt` —
   the Langfuse SDK Prompt-entity reference (the value type is
   opaque to the spec; per-language SDKs determine the concrete type).
   Future observability backend mappings (e.g., a Phoenix mapping)
   define their own keys when they land. This replaces proposal
   0031's "implementation-defined under `Prompt.metadata`" placeholder
   for the Langfuse Prompt reference — observability §8.4.4 gets a
   small clarifying touch to read the reference from the new
   normative location.

Plus two cross-spec touchpoint updates: §12 (was §11) gains a paragraph
on `Prompt.sampling` → `RuntimeConfig` wiring at the LLM call site, and
a paragraph on the `observability_entities['langfuse_prompt']` lookup
that the §8.4.4 Langfuse Generation linkage rule reads.

No breaking changes. Existing callers see the new fields as optional
(absent on Prompts that don't supply sampling config or observability
entities); existing PromptManagers continue to work without a
`LabelResolver`. Existing backends are not required to populate
`sampling` or `observability_entities`; both fields are opt-in
per-backend. The observability §8.4.4 touch is a clarification of the
already-Accepted v0.23.0 contract (the Langfuse mapping's trigger rule
unchanged — "the prompt's source exposes a Langfuse Prompt reference"
— with the lookup location now spec-defined rather than
implementation-defined); no observability behavior changes for
existing implementations.

## Motivation

The prompt-management capability shipped at v0.15.0 (proposal 0017)
with a minimal `Prompt` shape — name, version, label, template,
template_hash, fetched_at, metadata. Three frictions have surfaced
across production adoption since:

1. **Per-prompt sampling parameters end up in a parallel structure.**
   When a prompt has prompt-specific tuning (e.g., `temperature=0.0`
   for a structured-extraction prompt, `temperature=0.7` for a
   creative-writing prompt), there's nowhere on `Prompt` to put it.
   Adopters maintain a parallel JSON file mapping prompt names to
   sampling configs and a service-side loader that reads it, then
   manually splat the configs into `RuntimeConfig` at every LLM call
   site. Two patterns recur:
   - A `prompt_configs.json` sidecar file structured as
     `{name: {temperature, max_tokens, top_p, ...}}`.
   - A typed `ModelConfig` / `PromptConfig` dataclass per service that
     parses the JSON and exposes typed accessors.
   The §3 `metadata` field nominally accommodates this (it's
   implementation-defined), but its lack of typing means every
   adopter writes the same parsing scaffolding. Folding sampling
   config into a typed `Prompt.sampling` sub-record (mirroring
   `RuntimeConfig`) replaces ~50-100 lines of per-service
   scaffolding with one normative field.

2. **The `label` argument has no deployment-time override path.**
   `PromptManager.fetch(name, label)` requires the caller to pass
   the label at every call site. Production deployments wanting to
   A/B test or canary one specific prompt (`segment_semantic` should
   be on `staging`; everything else stays on `production`) have to
   either hard-code per-prompt label arguments (rebuilds the service
   for every A/B switch) or maintain a per-service "label resolver"
   shim that maps prompt names to labels via a config file. Every
   adopter ends up re-implementing the same shim. A `LabelResolver`
   primitive surfaces the pattern in spec and lets the manager
   consult it transparently.

3. **Filesystem backends have no convention for prompt-adjacent
   metadata.** Adopters who use the filesystem reference backend
   typically maintain a side directory tree (`prompts/templates/<name>.j2`
   alongside `prompts/configs/<name>.json` or similar) — but the spec
   doesn't recommend any convention, so every adopter invents one.
   This is purely a discoverability friction (the spec doesn't
   prescribe filesystem layout, and shouldn't), but a brief
   informative recommendation in §5 saves the discovery loop.

### Why now

Proposal 0032 (just landed at v0.24.0) settled the seven declared
`RuntimeConfig` fields. With that surface stable, the
`Prompt.sampling` sub-record can mirror it cleanly without
chicken-and-egg ambiguity ("which fields should sampling carry?"
becomes "exactly the seven declared in `RuntimeConfig` plus extras").
The two follow-on Langfuse-related proposals (0031 Langfuse mapping +
0032 RuntimeConfig refinements) have closed the observability and
LLM-call surfaces; the prompt-management refinements complete the
adoption set for production deployments wiring OA to managed prompt
backends.

The three additions are independent surface refinements — each
addresses a distinct adoption gap. They bundle into one proposal
because they share a single driver (production adopters of
proposal 0031 + 0032), a single spec (prompt-management), and a
short PR-review cycle keeps the related changes coherent.

## Design

The complete text of the §3 / §4 / §5 / §6 / §7 (new) / §12 (was §11)
modifications is reproduced below. Section numbering shifts: current
§7 (Variable injection) → §8; §8 (Composite backends) → §9; §9
(PromptGroup) → §10; §10 (Errors) → §11; §11 (Cross-spec touchpoints)
→ §12; §12 (Determinism) → §13; §13 (Out of scope) → §14.

The spec version under which this lands is determined at acceptance
time and recorded in `CHANGELOG.md`. Anticipated bump: MINOR
(v0.25.0) — new optional fields, new primitive, no breaking changes.

### prompt-management §3 — Prompt shape (extended)

A `Prompt` record:

| Field | Description |
|---|---|
| `name` | String. The prompt's stable identifier within its backend. Matches the `name` argument the caller passed to fetch. |
| `version` | String. The prompt's version identifier within its backend. Implementation-defined: a backend MAY use semver, monotonic integers, content hashes, git short-SHAs, date stamps, or any stable identifier. Two distinct version strings MUST denote distinct prompt contents. |
| `label` | String. The label under which the prompt was fetched (e.g., `"production"`, `"latest"`, `"variant-a"`). Backends MAY support multiple labels per prompt; the label is part of the fetch query. |
| `template` | The unrendered template, in the implementation's chosen template representation (a Jinja2 `Template` instance, a string, an AST, etc.). The spec does not constrain the in-memory representation; it constrains the render contract (§8 (was §7)). |
| `template_hash` | String. A stable content-derived hash of the unrendered template. Implementations SHOULD use a cryptographic hash (e.g., SHA-256 hex) over the canonical serialization of the template. The hash MUST be deterministic for identical template content. |
| `fetched_at` | Timestamp of when this Prompt was fetched from its backend. Implementation-defined precision. When the backend serves a cached result, `fetched_at` MUST reflect the original fetch time, not the cache hit time. |
| `sampling` | Optional. A `SamplingConfig` sub-record carrying per-prompt sampling configuration. Field shape mirrors llm-provider §6 `RuntimeConfig`: the seven declared fields (`temperature`, `max_tokens`, `top_p`, `seed`, `frequency_penalty`, `presence_penalty`, `stop_sequences`), all optional, plus an extras mapping for vendor-specific fields per `RuntimeConfig`'s extras-pass-through contract. Per-language implementations SHOULD use the SAME type as `RuntimeConfig` (or a structurally-compatible subtype) so callers can splat `prompt.sampling` directly into `provider.complete(config=...)` without per-field translation. The model identifier is NOT part of `SamplingConfig`; per-prompt model selection is out of scope (the bound provider determines the model). Absent (`None` / `null` / `undefined`, per the language idiom) when the backend doesn't supply sampling config for this prompt. |
| `observability_entities` | Optional mapping (`dict[str, Any] \| None`) carrying backend-keyed references to first-class entities the prompt has been registered as in observability backends. Keys follow `<backend>_<entity>` naming. Spec-normative keys (this proposal): `langfuse_prompt` — the Langfuse SDK Prompt-entity reference, used by observability §8.4.4 to establish the Langfuse Generation → Prompt link. Future observability backend mappings define their own keys. Values are opaque to the spec; per-language implementations determine the concrete type (e.g., the Langfuse Python SDK's `Prompt` class instance, the Langfuse TypeScript SDK's equivalent). Absent / `None` when the backend doesn't expose any such references; absent keys within a populated mapping signal "this backend's reference is not available." |
| `metadata` | Optional implementation-defined mapping of additional backend-supplied metadata (e.g., Langfuse tags, file path of origin, other backend-attribution metadata). The spec does not constrain shape. Note that the Langfuse Prompt-entity reference has moved out of this field as of this proposal — it now lives on `observability_entities['langfuse_prompt']` so that the observability §8.4.4 lookup has a spec-defined location. |

The `name + version + label` triple identifies a prompt; the
`template_hash` lets two prompts with the same name be distinguished
by content (e.g., a Langfuse-backed prompt fetched at two different
times with the same `latest` label may have different content).

`sampling` is opt-in per backend. A backend that doesn't supply
sampling config (e.g., a minimal in-memory test backend) returns
prompts with `sampling = None`. Callers consume the field defensively
(checking for absence) or rely on the language's idiom for unset
optional fields. The spec does NOT mandate a default sampling config
in the absence of a supplied one — callers fall back to
`RuntimeConfig()` defaults at the provider layer.

### prompt-management §4 — PromptResult shape (extended)

A `PromptResult` record:

| Field | Description |
|---|---|
| `name` | String. Propagated from the source `Prompt.name`. |
| `version` | String. Propagated from the source `Prompt.version`. |
| `label` | String. Propagated from the source `Prompt.label`. |
| `template_hash` | String. Propagated from the source `Prompt.template_hash`. |
| `rendered_hash` | String. (Unchanged from v0.15.0.) |
| `messages` | An ordered, non-empty sequence of `Message` records, per llm-provider §3. Ready to pass to `Provider.complete()`. |
| `variables` | The variable mapping that was used to render. (Unchanged from v0.15.0.) |
| `fetched_at` | Timestamp. (Unchanged from v0.15.0.) |
| `rendered_at` | Timestamp. (Unchanged from v0.15.0.) |
| `sampling` | Propagated from the source `Prompt.sampling`. Same shape as §3's `sampling` field; absent when the source Prompt had no sampling config. |
| `observability_entities` | Propagated from the source `Prompt.observability_entities`. Same shape as §3's field; carries the same backend-keyed reference mapping the source Prompt had. Rendering does NOT modify the contents. |

The propagation rule for `sampling` matches the rule for
`name` / `version` / `label` / `template_hash`: the source `Prompt`'s
value is carried forward verbatim. Rendering does NOT modify or
reinterpret the sampling sub-record.

### prompt-management §5 — PromptBackend protocol (extended)

The PromptBackend protocol is unchanged at the operation level:
`fetch(name, label="production")` returns a `Prompt`. New normative
addition:

**Backends MAY populate `Prompt.sampling`** from any source the
backend has access to. Common sources:

- A Langfuse-backed `PromptBackend` sources `sampling` from Langfuse's
  `prompt.config` field (Langfuse's own per-prompt config storage).
- A filesystem `PromptBackend` MAY adopt the convention of loading a
  sidecar file (see *Filesystem sidecar conventions* below).
- A database-backed backend loads from a per-prompt config column.
- A test / mock backend hard-codes `sampling = None` for the prompts
  it returns.

When a backend supplies `Prompt.sampling`, it MUST construct the
sub-record per §3's shape (the seven declared fields plus extras
mapping; declared-field types match `RuntimeConfig`). A backend that
sources from a vendor system with a richer config shape MUST project
to the declared `SamplingConfig` shape, placing vendor-specific
fields under the extras mapping per §3's extras-pass-through analog
of llm-provider §6.

**Filesystem sidecar conventions (informative).** Filesystem backends
MAY adopt either of two conventions for sourcing `sampling`:

- **Per-prompt sidecar:** for a template at `<root>/<name>.j2`, also
  read `<root>/<name>.config.json` (or equivalent extension) and
  populate `Prompt.sampling` from its contents.
- **Unified config file:** read a single `<root>/prompt_configs.json`
  at backend construction time, keyed by prompt name; populate
  `Prompt.sampling` from the entry matching the fetched name.

Both conventions parse the file as JSON whose top-level shape
matches `SamplingConfig`. Example (informative):

```json
{
  "name": "classify",
  "temperature": 0.0,
  "max_tokens": 256,
  "stop_sequences": ["END"],
  "extras": {
    "repetition_penalty": 1.05
  }
}
```

The convention is informative; the spec does NOT mandate a specific
filesystem layout. Implementations are free to use either
convention, both, or neither (e.g., loading from a separate config
service). The normative contract is the `Prompt.sampling` field
itself, not the file convention that produces it.

### prompt-management §6 — PromptManager interface (extended)

A `PromptManager` is constructed with one or more `PromptBackend`s
and (per this proposal) an optional `LabelResolver`. The fetch
operation is extended to consult the resolver when no explicit label
is supplied:

#### `fetch(name, label=None)`

Async. Fetches a `Prompt` by name and label, consulting backends in
order per §9 (was §8) fallback semantics. Label resolution:

1. If `label` is explicitly supplied (non-`None`), use it verbatim.
   Manager passes it through to backend `fetch(name, label)` calls.
2. If `label` is `None` (or absent) AND the manager has a
   `LabelResolver` configured, consult the resolver per §7 (new):
   `label = resolver.resolve(name)`. Manager passes the resolved
   label to backends.
3. If `label` is `None` (or absent) AND no `LabelResolver` is
   configured, use the default `"production"`. (Backwards-compatible
   with the v0.15.0 default.)

The default value for the `label` parameter is `None` (or the
language's idiomatic "unset" sentinel) rather than the string
`"production"`. This makes the resolver / default chain explicit:
callers who want to force-pass `"production"` continue to do so;
callers who want the resolver to decide simply omit the argument.

The `render(prompt, variables)` operation is unchanged. The
`get(name, label, variables)` convenience continues to apply the
same label-resolution rule.

### prompt-management §7 — LabelResolver (new section)

A `LabelResolver` is an optional helper that maps prompt names to
labels for deployment-time A/B testing — flip one prompt to
`staging` or `variant-a` without code changes by updating the
resolver's data.

Operation:

#### `resolve(name) -> str`

Synchronous. Returns the label to use when fetching the prompt named
`name`. Pure function; deterministic for given resolver state.

**Fallback chain.** Implementations MUST resolve in this order:

1. **Per-name override.** If the resolver has a specific label
   mapped for `name`, return it. (Highest precedence.)
2. **Default override.** If the resolver has a default label
   configured (e.g., a `"default"` key in a mapping source), return
   that.
3. **Spec fallback.** Return `"production"`. (Lowest precedence,
   backwards-compatible with v0.15.0's default.)

The contract is on the precedence order and on the spec-fallback
value, not on how the resolver stores its data. Implementations MAY
back resolvers with:

- A static mapping (in-memory dict / record).
- A JSON file (e.g., `prompt_labels.json` keyed by prompt name).
- An environment-variable lookup.
- A remote config service (resolution result MAY be cached).

**Configuration shape (informative).** A common pattern is a JSON
file structured as:

```json
{
  "default": "production",
  "segment_semantic": "staging",
  "extract_claim_candidates": "variant-a"
}
```

Under this shape, the resolver returns `"staging"` for
`segment_semantic`, `"variant-a"` for `extract_claim_candidates`,
and `"production"` (the file's `"default"` value, which equals the
spec-fallback in this case) for every other prompt name.

**No resolver, no problem.** A `PromptManager` constructed without
a `LabelResolver` follows the §6 rule's step 3 directly: when no
label is supplied at fetch time, use `"production"`. Existing
v0.15.0 callers continue to work without modification.

### prompt-management §12 (was §11) — Cross-spec touchpoints (extended)

The existing §11 touchpoints (llm-provider §3 message shape;
observability §5.5 LLM-provider span attributes) continue to apply.
This proposal adds two more:

#### llm-provider §6 (RuntimeConfig wiring)

When a managed prompt has `Prompt.sampling` set (per §3), the LLM
call site MAY thread the sub-record through to
`provider.complete(config=...)`'s `RuntimeConfig` argument. The
declared-fields-plus-extras shape mirrors `RuntimeConfig` exactly,
so the wiring is a direct splat in the implementation's idiom (e.g.,
Python `RuntimeConfig(**prompt.sampling.fields)`,
TypeScript `{ ...prompt.sampling }`).

The §6 of llm-provider null-skip semantics applies once the values
reach `RuntimeConfig`: declared fields with value `None` /
`undefined` in `Prompt.sampling` MUST be omitted from the wire body
per llm-provider §6. The PromptManager itself does NOT enforce
null-skip — it merely propagates `sampling` to the PromptResult; the
wire-layer skip happens at the RuntimeConfig construction site.

Per-language ergonomics may further provide a convenience method
that combines `render()` + `complete()` (e.g., a `render_and_call()`
or `invoke_with_prompt()` helper that internally splats
`PromptResult.sampling` into the LLM call). Convenience helpers are
out of spec scope; the contract this section establishes is the
shape-compatibility between `Prompt.sampling` and `RuntimeConfig`.

#### observability §8.4.4 (Langfuse Prompt-entity reference lookup)

Proposal 0031's observability §8.4.4 specifies when a Langfuse
Generation observation MUST be linked to a Langfuse Prompt entity:
"when the prompt's source exposes a Langfuse Prompt reference."
The v0.23.0 phrasing leaves the lookup location
implementation-defined under `Prompt.metadata`. This proposal moves
the reference to a spec-defined location on Prompt:
`Prompt.observability_entities['langfuse_prompt']`.

When that key is present (value is the opaque Langfuse SDK Prompt
reference for the rendered prompt), the Langfuse observer MUST
establish the native link per §8.4.4 case 1. When the key is absent
or `observability_entities` itself is `None`, §8.4.4 case 2 applies
(metadata-only, no Prompt-entity link). The trigger semantic is
unchanged; only the lookup location is now spec-defined.

Observability §8.4.4 of the spec is updated in tandem with this
proposal's acceptance to read the reference from
`observability_entities['langfuse_prompt']` rather than from
`metadata`. Implementations of the Langfuse mapping that previously
read from impl-defined metadata keys update their lookup
accordingly.

## Conformance fixtures

Four new fixtures land at acceptance:

- **`spec/prompt-management/conformance/013-prompt-sampling-from-backend.{yaml,md}`** — verifies §3 `Prompt.sampling` propagation. A mock backend returns a `Prompt` with a populated `sampling` sub-record (covering all seven declared fields plus one extras key). The fixture asserts that `Prompt.sampling` carries the supplied values verbatim and that `PromptResult.sampling` (after render) is identical.

- **`spec/prompt-management/conformance/014-prompt-sampling-absent.{yaml,md}`** — verifies §3's "opt-in per backend" semantic. A mock backend returns a `Prompt` with `sampling = None`. The fixture asserts that the field is absent / null on both `Prompt` and the resulting `PromptResult`, and that no defaulting happens at the manager layer.

- **`spec/prompt-management/conformance/015-label-resolver-fallback-chain.{yaml,md}`** — verifies §7 LabelResolver fallback chain. One case exercises all three levels:
  - `fetch("segment_semantic", label=None)` → resolver returns `"staging"` (per-name override).
  - `fetch("extract_claims", label=None)` → resolver returns `"variant-a"` (per-name override).
  - `fetch("classify", label=None)` → resolver returns its `"default"` value (default override; in the fixture's resolver config, the default is `"production"`, matching the spec fallback).
  - `fetch("unknown_prompt", label=None)` with a resolver configured with NO `"default"` key → spec fallback returns `"production"`.
  - `fetch("any", label="explicit")` → resolver is NOT consulted; label is `"explicit"` verbatim.

- **`spec/prompt-management/conformance/016-prompt-observability-entities-propagation.{yaml,md}`** — verifies §3 `Prompt.observability_entities` propagation through fetch → render → PromptResult. A mock backend returns a `Prompt` with an `observability_entities` mapping containing a canned `langfuse_prompt` reference value. The fixture asserts that `Prompt.observability_entities['langfuse_prompt']` carries the supplied value verbatim, that `PromptResult.observability_entities` (after render) carries the same value, and that rendering does NOT modify the mapping. A second case exercises the absent semantic (`observability_entities = None`) and asserts the field is null on both sides.

The harness conventions extend with three new primitives:

- `prompt_backend.populates_sampling: {sampling-config block}` — when used by a mock backend, attaches a sampling sub-record to every prompt the backend returns.
- `prompt_backend.populates_observability_entities: {mapping}` — when used by a mock backend, attaches the supplied `observability_entities` mapping to every prompt the backend returns. Values are opaque sentinel strings the harness uses for equality assertions (no real Langfuse SDK objects are constructed at fixture time).
- `label_resolver: {mapping or null}` — configures the manager with a LabelResolver backed by the supplied mapping; when `null`, no resolver is configured (manager uses the spec-fallback).

## Versioning

MINOR bump. The spec's whole-spec SemVer increments to **v0.25.0** on
acceptance:

- Adds optional `sampling` field to prompt-management §3 `Prompt` and
  §4 `PromptResult`.
- Adds optional `observability_entities` field to prompt-management
  §3 `Prompt` and §4 `PromptResult`.
- Adds the informative filesystem sidecar convention to §5.
- Extends §6 `PromptManager.fetch()` with optional `LabelResolver`
  consultation; default `label` parameter shifts from `"production"`
  to `None`/sentinel.
- Adds new §7 `LabelResolver` primitive section; renumbers existing
  §7-§13 → §8-§14.
- Adds §12 (was §11) cross-spec touchpoints with llm-provider §6
  `RuntimeConfig` and observability §8.4.4 Langfuse-Prompt-entity
  lookup.
- Updates observability §8.4.4 to read the Langfuse Prompt reference
  from `Prompt.observability_entities['langfuse_prompt']` rather
  than from an implementation-defined `metadata` key. The §8.4.4
  trigger semantic is unchanged; only the lookup location is now
  spec-defined.
- Adds four conformance fixtures (013, 014, 015, 016).
- No breaking changes. Callers passing `label="production"`
  explicitly continue to work. Callers using `fetch(name)` without
  an explicit label continue to get `"production"` when no resolver
  is configured (spec-fallback path). Implementations of the
  observability §8.4.4 Langfuse mapping update their lookup from
  the v0.23.0 implementation-defined `metadata` key to the v0.25.0
  spec-defined `observability_entities['langfuse_prompt']`; the
  visible behavior is unchanged.

CHANGELOG entry references this proposal.

## Out of scope

For this proposal specifically:

- **Per-prompt model selection.** Adding a model identifier to
  `Prompt.sampling` would require either an llm-provider §5 change
  (per-call model override on `complete()`) or PromptManager
  dispatch logic that selects a Provider based on prompt-supplied
  model identity. Both are larger surfaces than this proposal
  warrants. Production adopters that need this today route through
  per-prompt Provider instances (one Provider per model); a future
  proposal MAY tackle per-call model override once the usage
  patterns settle.
- **Backend-level sampling-config caching / invalidation.** A Langfuse
  backend that fetches sampling config alongside the template might
  want TTL-based caching. The caching policy is per-backend
  implementation per prompt-management §5 (the v0.15.0 contract that
  backends MAY cache their own results); this proposal does not
  constrain it.
- **`SamplingConfig` validation.** The declared fields mirror
  `RuntimeConfig`; range validation is deferred to the provider
  (per 0032's resolution of that question). The `Prompt.sampling`
  shape is not subject to additional validation at the
  prompt-management layer.
- **Per-language partial-config constructors.** Per-language
  ergonomic helpers (e.g., a `SamplingConfig.from_partial(**kwargs)`
  constructor that filters language-null kwargs) are implementation
  ergonomics, paralleling llm-provider §6's same out-of-scope item.
- **Resolver hot-reload.** A `LabelResolver` backed by a file MAY
  reload on file change; the spec does not mandate it (and a hot
  reload during an active invocation would violate determinism for
  that invocation). Implementations decide.

## Open questions

None. Three questions flagged at draft time are settled in the
proposal text above:

- **`sampling` field name** — settled at `sampling`. Accurately bounds
  the field to its actual contents (sampling parameters mirroring
  `RuntimeConfig`); alternatives `prompt_config` / `runtime` /
  `params` either overpromise scope (`prompt_config` suggests broader
  per-prompt configuration the field doesn't carry) or are ambiguous
  / collision-prone (`runtime` ambiguous out of context, `params`
  collides with `parameters` for tool JSON Schema in llm-provider
  §4). Avoids Pydantic's reserved `model_config` attribute. Matches
  the OA spec's existing convention of precise, scoped field names
  (`template_hash`, `rendered_hash`, `fetched_at`).
- **`LabelResolver` section placement** — placed as new §7 with §7-§13
  renumbered to §8-§14. The resolver is a first-class primitive that
  PromptManager consumes; sibling placement matches the dependency
  graph and gives the primitive its own discoverable section.
- **Langfuse Prompt-entity reference location** — normalized to
  `Prompt.observability_entities['langfuse_prompt']` (new typed
  field). Replaces proposal 0031's implementation-defined
  `metadata`-key placeholder. The `observability_entities` mapping
  is generic enough to accommodate future observability backends
  (Phoenix, Honeycomb LLM lens) without per-vendor pollution on
  Prompt's primary surface, while giving §8.4.4 a spec-defined
  lookup target.
