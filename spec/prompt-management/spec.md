# Prompt Management

Canonical behavioral specification for the OpenArmature prompt-management capability.

- **Capability:** prompt-management
- **Introduced:** spec version 0.15.0
- **History:**
  - created by [proposal 0017](../../proposals/0017-prompt-management-core.md)

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

A `Prompt` record:

| Field | Description |
|---|---|
| `name` | String. The prompt's stable identifier within its backend. Matches the `name` argument the caller passed to fetch. |
| `version` | String. The prompt's version identifier within its backend. Implementation-defined: a backend MAY use semver, monotonic integers, content hashes, git short-SHAs, date stamps, or any stable identifier. Two distinct version strings MUST denote distinct prompt contents. |
| `label` | String. The label under which the prompt was fetched (e.g., `"production"`, `"latest"`, `"variant-a"`). Backends MAY support multiple labels per prompt; the label is part of the fetch query. |
| `template` | The unrendered template, in the implementation's chosen template representation (a Jinja2 `Template` instance, a string, an AST, etc.). The spec does not constrain the in-memory representation; it constrains the render contract (§7). |
| `template_hash` | String. A stable content-derived hash of the unrendered template. Implementations SHOULD use a cryptographic hash (e.g., SHA-256 hex) over the canonical serialization of the template. The hash MUST be deterministic for identical template content. |
| `fetched_at` | Timestamp of when this Prompt was fetched from its backend. Implementation-defined precision. When the backend serves a cached result, `fetched_at` MUST reflect the original fetch time, not the cache hit time (matching §5's "caching MUST NOT break content-addressing" intent). |
| `metadata` | Optional implementation-defined mapping of additional backend-supplied metadata (e.g., Langfuse tags, file path of origin). The spec does not constrain shape. |

The `name + version + label` triple identifies a prompt; the `template_hash` lets two
prompts with the same name be distinguished by content (e.g., a Langfuse-backed prompt
fetched at two different times with the same `latest` label may have different content).

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
- `fetch()` MUST raise `prompt_not_found` (§10) when no prompt matches `(name, label)`.
- `fetch()` MUST raise `prompt_store_unavailable` (§10) when the backend is unreachable
  (network failure, filesystem I/O error, vendor API timeout).

Backends MAY cache their own results internally (e.g., a Langfuse backend caching by
`(name, label)` for some TTL); cache invalidation is implementation-defined. When a
backend serves a cached result, the returned `Prompt`'s `template_hash` MUST still be
correct for the served template (caching MUST NOT break content-addressing).

The protocol is deliberately small — backends are fetchers, nothing more. Composition,
fallback, and rendering are the manager's concern.

## 6. PromptManager interface

A `PromptManager` is constructed with one or more `PromptBackend`s and exposes:

### `fetch(name, label="production")`

Async. Fetches a `Prompt` by name and label, consulting backends in order per §8
fallback semantics. Returns a `Prompt`. Raises `prompt_not_found` if no backend produces
the prompt; raises `prompt_store_unavailable` only when ALL backends are unavailable.

### `render(prompt, variables=None)`

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
- `rendered_at` is set to the call time; `fetched_at` is propagated from `Prompt.fetched_at`
  (per §3).
- `rendered_hash` is computed from the rendered messages.
- Variable handling follows §7.

Render is synchronous because it is purely a string-transformation step over the
in-memory template; no backend I/O is involved. Async render would surface no
benefits and would needlessly couple the operation to the host's event loop.

### `get(name, label="production", variables=None)`

Convenience. Equivalent to `render(await fetch(name, label), variables)`. Implementations
SHOULD provide this as a convenience for the common single-shot path; users wanting
fetch/render separation use `fetch` and `render` directly.

## 7. Variable injection

Render MUST treat undefined variables as errors by default. When a template references a
variable that is not present in the `variables` mapping passed to `render()`, render MUST
raise `prompt_render_error` (§10). Silently substituting empty strings or `null` is
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

## 8. Composite backends and fallback

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

## 9. PromptGroup

A `PromptGroup` composes two or more `PromptResult` instances under a single tracing
grouping. The group itself does not execute the calls or pass output between them — it
is a structural grouping that lets observability surface related prompts as one logical
unit under a shared name.

A `PromptGroup` record:

| Field | Description |
|---|---|
| `group_name` | String. A stable identifier for this group pattern. Used by observability §5.5 cross-reference (per §11) so all spans under the group share an `openarmature.prompt.group_name` attribute. |
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

Empty groups and single-member groups are both spec-invalid; `members` MUST contain at
least two elements. (Single-prompt tagging is already served by the per-prompt
observability attributes in §11 — `openarmature.prompt.name`,
`openarmature.prompt.version`, `openarmature.prompt.label` —
without needing a degenerate group-of-one.)

## 10. Errors

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

## 11. Cross-spec touchpoints

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

## 12. Determinism

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

## 13. Out of scope

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
