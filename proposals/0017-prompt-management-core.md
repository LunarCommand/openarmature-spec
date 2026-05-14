# 0017: Prompt Management — Core

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-13
- **Targets:** spec/prompt-management/spec.md (creates)
- **Related:** 0006 (LLM provider core — `Message` shape produced by render), 0007 (observability — prompt metadata cross-reference)
- **Supersedes:**

## Summary

Create the `prompt-management` capability spec. Defines `PromptBackend` (the fetch-only
backend protocol), `PromptManager` (the user-facing API that composes backends and renders),
`Prompt` (the unrendered template), and `PromptResult` (the rendered output, ready to pass
to an LLM provider). Specifies strict-by-default variable handling, composite-backend
fallback semantics, the `PromptGroup` tracing pattern (an N≥2 ordered grouping of related
prompts), three canonical error categories, and the cross-references to llm-provider
(rendered messages) and observability (prompt identity in observer events).

## Motivation

Charter §4.5 has flagged prompt management as a v2 capability since charter v0.1.0:

> **Scope.** Dual-source prompt loading (Langfuse for production, local Jinja2 for
> development), variable injection with `StrictUndefined`, prompt-pair pattern for
> dual-observation tracing.
>
> **Core abstractions.** `PromptManager`, `Prompt`, `PromptResult`, `PromptPair`. Backends
> implement `PromptBackend` interface.

No spec has been written. Today, every LLM-using project re-implements the same pattern
from scratch:

- A loader that finds prompts by name (and optionally label) across some combination of
  filesystem, vendor APIs (Langfuse, PromptLayer, etc.), and inline literals.
- A renderer that injects per-call variables into a template, using a templating engine
  the project picks (Jinja2, Mustache, simple `str.format`, etc.).
- Some convention for what "prompt identity" means (name? name + version? hash?) so the
  prompt can flow through to observability tags, cache keys, and audit trails.
- Some convention for how rendered output becomes an LLM message list (single user message
  with the rendered text? structured system + user split? multi-message?).

These conventions converge across projects in shape but diverge in detail. A spec that
mandates the contract (without dictating the templating engine or backend) lets
implementations and sibling packages compose cleanly: `openarmature-langfuse` ships a
`PromptBackend` that fetches from Langfuse; the core ships a filesystem `PromptBackend` and
the orchestrating `PromptManager`; downstream projects consume one composed object instead
of building their own loader.

The primary cross-spec value is **prompt identity flowing through to other layers**:

- Observability §5.5 (per proposal 0007) defines LLM-call attributes; observer events MAY
  carry `prompt_name`, `prompt_version`, `prompt_label` when the call originated from a
  managed prompt, letting trace UIs and dashboards filter by prompt identity.
- A future memoization or caching capability (charter §4.2 mentions this in passing) can
  use `template_hash` and `rendered_hash` as cache keys, getting automatic invalidation on
  prompt edits.
- Production audit trails ("which exact prompt produced this output?") get a stable answer
  without per-project bookkeeping.

The spec scope deliberately stays narrow: this proposal defines fetch + render + backend
composition. It does NOT define the templating language (per-implementation), specific
vendor backends (sibling packages), or prompt versioning workflows (per-project discipline).

## Detailed design

### 1. Purpose

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

### 2. Concepts

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

### 3. Prompt shape

A `Prompt` record:

| Field | Description |
|---|---|
| `name` | String. The prompt's stable identifier within its backend. Matches the `name` argument the caller passed to fetch. |
| `version` | String. The prompt's version identifier within its backend. Implementation-defined: a backend MAY use semver, monotonic integers, content hashes, git short-SHAs, date stamps, or any stable identifier. Two distinct version strings MUST denote distinct prompt contents. |
| `label` | String. The label under which the prompt was fetched (e.g., `"production"`, `"latest"`, `"variant-a"`). Backends MAY support multiple labels per prompt; the label is part of the fetch query. |
| `template` | The unrendered template, in the implementation's chosen template representation (a Jinja2 `Template` instance, a string, an AST, etc.). The spec does not constrain the in-memory representation; it constrains the render contract (§7). |
| `template_hash` | String. A stable content-derived hash of the unrendered template. Implementations SHOULD use a cryptographic hash (e.g., SHA-256 hex) over the canonical serialization of the template. The hash MUST be deterministic for identical template content. |
| `metadata` | Optional implementation-defined mapping of additional backend-supplied metadata (e.g., Langfuse tags, file path of origin). The spec does not constrain shape. |

The `name + version + label` triple identifies a prompt; the `template_hash` lets two
prompts with the same name be distinguished by content (e.g., a Langfuse-backed prompt
fetched at two different times with the same `latest` label may have different content).

### 4. PromptResult shape

A `PromptResult` record:

| Field | Description |
|---|---|
| `name` | String. Propagated from the source `Prompt.name`. |
| `version` | String. Propagated from the source `Prompt.version`. |
| `label` | String. Propagated from the source `Prompt.label`. |
| `template_hash` | String. Propagated from the source `Prompt.template_hash`. |
| `rendered_hash` | String. A stable content-derived hash of the rendered output (the concatenation of all `messages` content). Implementations SHOULD use the same hash function as `template_hash`. |
| `messages` | An ordered, non-empty sequence of `Message` records, per llm-provider §3. Ready to pass to `Provider.complete()`. |
| `variables` | The variable mapping that was used to render. Implementations MAY redact or omit values that contain sensitive content; the keys MUST be present so audit trails can identify what variables were applied. |
| `fetched_at` | Timestamp of when the source `Prompt` was fetched. Implementation-defined precision. When the `Prompt` came from a cache (§6), `fetched_at` MUST reflect the original fetch time, not the cache hit time. |
| `rendered_at` | Timestamp of when this `PromptResult` was rendered. Distinct from `fetched_at`: a single fetched prompt MAY render multiple times. |

The `rendered_hash` is the cache-key value most useful to downstream consumers — two
calls with the same template AND the same variables produce the same `rendered_hash`,
which is exactly the equivalence relation a memoization layer wants.

### 5. PromptBackend protocol

A `PromptBackend` exposes one operation:

#### `fetch(name, label="production")`

Async. Retrieves a `Prompt` by name and label. Returns a `Prompt` record (§3) on success.

- `name` — string. The prompt identifier within this backend. Required.
- `label` — string. The label under which to fetch. Default `"production"`. Backends MAY
  support backend-specific label conventions (e.g., Langfuse's labels are user-defined;
  filesystem backends MAY interpret label as a subdirectory or filename suffix).

Operation semantics:

- `fetch()` MUST be reentrant: multiple concurrent calls on the same backend are
  permitted.
- `fetch()` does NOT render or otherwise mutate the template.
- `fetch()` MUST raise `PromptNotFound` (§10) when no prompt matches `(name, label)`.
- `fetch()` MUST raise `PromptStoreUnavailable` (§10) when the backend is unreachable
  (network failure, filesystem I/O error, vendor API timeout).

Backends MAY cache their own results internally (e.g., a Langfuse backend caching by
`(name, label)` for some TTL); cache invalidation is implementation-defined. When a
backend serves a cached result, the returned `Prompt`'s `template_hash` MUST still be
correct for the served template (caching MUST NOT break content-addressing).

The protocol is deliberately small — backends are fetchers, nothing more. Composition,
fallback, and rendering are the manager's concern.

### 6. PromptManager interface

A `PromptManager` is constructed with one or more `PromptBackend`s and exposes:

#### `fetch(name, label="production")`

Async. Fetches a `Prompt` by name and label, consulting backends in order per §8
fallback semantics. Returns a `Prompt`. Raises `PromptNotFound` if no backend produces
the prompt; raises `PromptStoreUnavailable` only when ALL backends are unavailable.

#### `render(prompt, variables=None)`

Synchronous (rendering is local — no I/O). Applies `variables` to `prompt.template` and
returns a `PromptResult` (§4).

- `prompt` — a `Prompt` record (§3). Required.
- `variables` — mapping of template variable names to values. Default empty.

Render semantics:

- The result's `name`, `version`, `label`, `template_hash` are propagated from the
  input `prompt`.
- `messages` is the rendered output, decomposed into LLM-provider messages per the
  template's structure (templates MAY produce multiple messages — e.g., a system +
  user split — when the template language supports it).
- `variables` (the input) are recorded on the result.
- `rendered_at` is set to the call time; `fetched_at` is propagated from the prompt's
  fetch time (the prompt MUST carry its fetch time per §3 implementation note — see
  the §3 `metadata` field where implementations MAY stash this, OR per-language
  ergonomics MAY add a `fetched_at` accessor on `Prompt`).
- `rendered_hash` is computed from the rendered messages.
- Variable handling follows §7.

Render is synchronous because it is purely a string-transformation step over the
in-memory template; no backend I/O is involved. Async render would surface no
benefits and would needlessly couple the operation to the host's event loop.

#### `get(name, label="production", variables=None)`

Convenience. Equivalent to `render(await fetch(name, label), variables)`. Implementations
SHOULD provide this as a convenience for the common single-shot path; users wanting
fetch/render separation use `fetch` and `render` directly.

### 7. Variable injection

Render MUST treat undefined variables as errors by default. When a template references a
variable that is not present in the `variables` mapping passed to `render()`, render MUST
raise `PromptRenderError` (§10). Silently substituting empty strings or `null` is
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

### 8. Composite backends and fallback

A `PromptManager` constructed with multiple backends MUST consult them in order. The
fallback contract:

- For each backend in order, call `fetch(name, label)`.
- If the backend returns a `Prompt`, that prompt is the result; further backends are not
  consulted. (First-match semantics.)
- If the backend raises `PromptNotFound`, **the fallback chain stops**. The error
  propagates to the caller. A `PromptNotFound` is a logical "this prompt does not exist
  under this name + label" — falling back to a secondary backend would silently resurface
  an old version under a name the operator may have intentionally retired.
- If the backend raises `PromptStoreUnavailable`, the manager tries the next backend.
  After exhausting all backends with `PromptStoreUnavailable`, the manager raises
  `PromptStoreUnavailable` to the caller.

This contract distinguishes infrastructure failure (transient; fall back) from logical
absence (terminal; do not silently substitute). The two cases have different operational
meanings — one is "the network is down; please use the local copy"; the other is "this
prompt was deleted; please don't quietly serve a stale version" — and conflating them
masks bugs in production.

The chartered example of "Langfuse primary, local fallback" composes correctly under
this contract: Langfuse outages route to the local copy; an operator who deleted a
prompt from Langfuse to retire it gets a `PromptNotFound` (not a silently-served local
copy) so the calling pipeline can surface the misconfiguration.

Implementations SHOULD log fallbacks (a `PromptStoreUnavailable` from one backend
followed by a successful fetch from the next) at WARN level so operators see when
their primary backend is degraded.

### 9. PromptGroup

A `PromptGroup` composes two or more `PromptResult` instances under a single tracing
grouping. The group itself does not execute the calls or pass output between them — it
is a structural grouping that lets observability surface related prompts as one logical
unit under a shared name.

A `PromptGroup` record:

| Field | Description |
|---|---|
| `group_name` | String. A stable identifier for this group pattern. Used by observability §5.5 cross-reference (per §11) so all spans under the group share a `prompt.group_name` attribute. |
| `members` | An ordered, non-empty sequence of `PromptResult` instances. Order matches the application's intended call sequence (first member runs first); the spec does not require sequential execution, but observability tools MAY use member order to lay out the group visually. |

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

Empty groups (`members` of length zero) are spec-invalid. A single-member group is
permitted; in that case the `group_name` propagates to one span and the group is
equivalent to attaching a tag to one PromptResult, which is rarely useful but not
forbidden.

### 10. Errors

Three canonical error categories:

- `prompt_not_found` — no prompt matches `(name, label)`. Raised by
  `PromptBackend.fetch()` and propagated by `PromptManager.fetch()` per §8 fallback
  semantics. Non-transient (retrying the same name + label will not succeed without
  changing the backends or the prompt store contents).

- `prompt_render_error` — render failed. Raised by `PromptManager.render()` when:
  - the template references an undefined variable under strict-by-default §7 handling, OR
  - the template fails to parse (syntax error in the template language), OR
  - a variable's value is not coercible to the template's expected type.

  The error MUST expose the prompt's `name`, `version`, `label`, the variable mapping
  (with sensitive values redacted per implementation policy), and a description of the
  render failure. Non-transient.

- `prompt_store_unavailable` — backend infrastructure failure (network unreachable,
  filesystem I/O error, vendor API 5xx, vendor API timeout). Raised by
  `PromptBackend.fetch()`. Transient — the same fetch may succeed when the backend
  recovers. `PromptManager.fetch()` raises this only after ALL composed backends raise
  it (per §8).

Each error MUST expose a `category` identifier (matching the strings above, per the
language's idiom — error class, error code, tagged discriminant). Provider-originated
errors (e.g., a Langfuse SDK exception) SHOULD preserve the underlying exception as
cause.

### 11. Cross-spec touchpoints

#### Llm-provider §3 (Message shape)

`PromptResult.messages` is a sequence of `Message` records per llm-provider §3. The
prompt-management capability does not redefine the message shape; it produces messages
that conform to llm-provider's contract and are directly consumable by
`Provider.complete()`.

#### Observability §5.5 (LLM provider span attributes)

When an LLM call is made with messages produced by a managed prompt (i.e., messages
sourced from a `PromptResult`), implementations MAY surface the prompt's identity on
the LLM call's observability span by adding the following attributes to the LLM-call
span (sibling to existing `llm.model`, `llm.finish_reason`, etc.):

- `prompt.name` — `PromptResult.name`
- `prompt.version` — `PromptResult.version`
- `prompt.label` — `PromptResult.label`
- `prompt.template_hash` — `PromptResult.template_hash`
- `prompt.rendered_hash` — `PromptResult.rendered_hash`
- `prompt.group_name` — when the call was part of a `PromptGroup`, the group's
  `group_name` propagates to every member span so trace UIs can render them as a
  single grouping.

The propagation mechanism (e.g., a context variable holding the `PromptResult`, an
explicit observer event the manager fires on render) is implementation-defined. The
attribute names are normative.

A follow-on proposal MAY tighten these from `MAY` to `SHOULD` once the propagation
mechanism is settled across implementations; v1 of this capability leaves the
mechanism flexible.

### 12. Determinism

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

### 13. Out of scope

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

## Conformance test impact

Add fixtures under `spec/prompt-management/conformance/`. Each fixture is a pair
(`NNN-name.yaml` + `NNN-name.md`) per the conformance README pattern in other
capabilities. v1 fixtures cover the protocol contracts:

- **`001-fetch-success.yaml`** — backend with a known prompt; `fetch("greeting",
  "production")` returns a `Prompt` with the expected name, version, label, template,
  and template_hash.
- **`002-fetch-not-found.yaml`** — backend without the named prompt; assert
  `prompt_not_found` is raised.
- **`003-fetch-store-unavailable.yaml`** — backend simulating infrastructure failure
  (e.g., I/O error); assert `prompt_store_unavailable` is raised.
- **`004-render-success.yaml`** — render a fetched prompt with valid variables; assert
  `PromptResult` carries propagated identity fields, deterministic `rendered_hash`,
  and well-formed `messages` per llm-provider §3.
- **`005-render-undefined-variable.yaml`** — render with a variable mapping missing a
  variable the template references; assert `prompt_render_error` is raised under the
  strict default; assert the error exposes name/version/label and a description of the
  failure.
- **`006-render-determinism.yaml`** — render the same prompt with the same variables
  twice; assert `messages` and `rendered_hash` are bytewise identical.
- **`007-manager-fetch-fallback-store-unavailable.yaml`** — composite manager with two
  backends; primary raises `prompt_store_unavailable`; secondary returns a prompt;
  assert manager returns the secondary's prompt without raising.
- **`008-manager-fetch-fallback-not-found-no-fallback.yaml`** — composite manager with
  two backends; primary raises `prompt_not_found`; secondary has the prompt; assert
  manager raises `prompt_not_found` (does NOT fall back to secondary). Verifies §8
  not-found-is-terminal contract.
- **`009-manager-fetch-all-backends-unavailable.yaml`** — composite manager with two
  backends; both raise `prompt_store_unavailable`; assert manager raises
  `prompt_store_unavailable` after consulting all.
- **`010-manager-get-fetch-and-render.yaml`** — `manager.get(name, label, variables)`
  is equivalent to `manager.render(await manager.fetch(name, label), variables)`;
  assert the resulting `PromptResult` is deep-equal modulo `rendered_at` (which may
  differ by call timing).
- **`011-prompt-group-shape.yaml`** — construct a `PromptGroup` with three
  `PromptResult` instances and a `group_name`; assert the group record exposes the
  ordered `members` sequence and the `group_name`. Test the N>2 case explicitly to
  validate that the primitive is not pair-only. Also assert that an empty `members`
  sequence is rejected per §9.
- **`012-prompt-result-rendered-hash-stability.yaml`** — render the same template with
  two different variable mappings; assert `rendered_hash` differs. Render the same
  template with the same variables in both Python and a mock TypeScript implementation
  (or two implementations of the same language); assert `rendered_hash` is identical
  across implementations (for the canonical test template). Verifies cross-language
  determinism for the cache-key use case.

## Alternatives considered

### Bundle fetch and render into a single operation

Considered: drop the separation between `fetch` and `render`; expose only a single
`get(name, label, variables)` that returns a `PromptResult`. Smaller surface, simpler
documentation.

Rejected because the separation enables real workflows: caching templates separately
from rendered output, inspecting templates without binding variables, rendering the
same template with different variables in tight loops without re-fetching. The
convenience `get()` operation (§6) gives users the single-call shape when they want it
without removing the separability.

### Fall back on `PromptNotFound` as well as `PromptStoreUnavailable`

The chartered phrasing ("if Langfuse fetch fails, fall back to local template with
warning") would naturally extend to "fall back on any error." Rejected — falling back on
`PromptNotFound` lets a stale local copy silently resurface for a name an operator
deliberately retired upstream. The two error categories have different operational
meanings; conflating them masks production bugs. The §8 contract is "fall back only on
infrastructure failure."

### Mandate a specific templating language

Rejected. Jinja2 is the obvious Python default; TypeScript implementations would pick
their own (handlebars, lit-html templating, native template literals, etc.). Mandating
one would force every implementation to ship a Python-flavored template parser even for
non-Python languages. The spec mandates the render *contract* (strict undefined,
deterministic output, message decomposition) and leaves the syntax to the
implementation.

### Make `render()` async

Considered: declare `render` async for symmetry with `fetch`. Rejected — render is
purely a local string transformation with no I/O. Forcing it async would require every
caller to await a sync operation, complicating sync code paths and adding event-loop
overhead for no benefit. The spec keeps render synchronous; if a future implementation
needs to do I/O during render (e.g., resolving included sub-templates from a remote
store), that's a structural change that warrants its own proposal.

### Make `PromptGroup` a control-flow primitive

Considered: have `PromptGroup` actually execute its members in sequence, parse
intermediate outputs, render later members with variables derived from earlier members'
outputs, and execute each call. Rejected for v1 — too much policy embedded in the
primitive (how is each member's output parsed? how is it mapped to subsequent members'
variables? what happens if a member fails? do later members execute conditionally on
prior outputs? does the group support parallel execution of independent members?). The
v1 group is a tracing-grouping primitive; higher-level orchestration ships as user code
or as a separate proposal once concrete patterns emerge.

### Keep `PromptPair` (charter alignment) instead of generalizing to `PromptGroup`

The charter §4.5 originally named `PromptPair`: "a classification prompt paired with a
follow-up prompt, traced together under one parent span." Rejected the pair-only form
because:

- Real workloads exist with N>2: multi-stage classification chains, RAG with reranking,
  self-correction loops, map-reduce over chunks. The pair-only form forces users to
  either stack pairs awkwardly (the same `PromptResult` appearing in two pairs as both
  follow-up and classifier) or skip the primitive entirely.
- The pair's specific field names (`classifier`, `follow_up`) were never structurally
  enforced — the spec just labels the two slots, and the producer-consumer relationship
  is application code's job. A generalized ordered list of members loses no semantic
  information.
- A future proposal could specialize `PromptGroup` into typed sub-primitives
  (`PromptPair`, `PromptFanOut`, `PromptChain`) if real patterns warrant it; starting
  general and specializing later is easier than the reverse.

The cost: the charter §4.5 mention of `PromptPair` becomes outdated. Charter edits are
not subject to the proposal lifecycle (the charter is freely editable per
`GOVERNANCE.md`), so a small follow-on charter edit can land alongside this proposal's
acceptance — not a blocker.

### Spec a vendor-specific backend (Langfuse) inline with the core

Rejected. The same precedent that keeps vendor-specific observability mappings out of
`spec/observability/spec.md` (only the open-standard OTel mapping lives there per
proposal 0007) applies here: vendor backends live in sibling packages, not in the core
spec. The spec defines `PromptBackend`; `openarmature-langfuse` ships the
Langfuse-specific concrete backend without the spec needing to mention it.

### Add prompt rendering hooks (pre-render / post-render)

Considered: middleware-style hooks on render that let observers transform the
template, the variables, or the rendered output. Rejected for v1 — adds significant
surface (hook protocol, ordering rules, error semantics) for unclear payoff. Users
wanting transformations build them at the application layer (preprocess variables
before calling `render`; post-process the `PromptResult` before passing to the
provider). If real patterns emerge that benefit from canonical hooks, a follow-on
proposal can add them.

## Open questions

None at time of submission.
