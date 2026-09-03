# Conformance Adapter

Canonical behavioral specification for the OpenArmature conformance-adapter capability.

- **Capability:** conformance-adapter
- **Introduced:** spec version 0.48.0

This specification is language-agnostic. Each implementation (Python, TypeScript, …) ships a thin **adapter**
that ingests the language-agnostic YAML fixtures under `spec/<capability>/conformance/` and executes them
against the host implementation's runtime, asserting on outcomes via the host language's idiomatic test
framework.

Normative keywords follow BCP 14 ([RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119), [RFC 8174](https://datatracker.ietf.org/doc/html/rfc8174)): MUST, SHOULD, MAY and the rest are normative **only when in all capitals** — a lowercase use is prose, not a requirement.

---

## 1. Purpose

The `conformance-adapter` capability defines the language-agnostic conformance fixture system that every
OpenArmature implementation builds against: the YAML schema fixtures use, the directive vocabulary they
draw from, the harness primitives implementations MUST provide to execute them, the assertion shapes
adapters MUST honor, and the responsibility model for language-specific adapters that translate fixtures
into host-runtime tests.

The capability is **descriptive of the system that already exists** as of spec v0.47.0. The fixture
format, directive vocabulary, and adapter pattern have accreted across more than two dozen prior
proposals since proposal 0001 introduced the first fixtures; this capability gives that vocabulary its
authoritative home. A future proposal that introduces a **general** directive extends §5 *Directive
vocabulary*, the same way new pipeline-utilities §6 middleware extend pipeline-utilities or new
observability §5 attribute sets extend observability; a directive whose contract does not generalize
beyond one capability's fixtures is defined in that directory's harness note instead, per §5
*Definition homes*.

The capability composes with:

- **Every other capability.** Each existing capability's `conformance/` directory contains fixtures
  written in the schema defined here, drawing directives from the recognized vocabulary (§5
  *Definition homes*).
- **Cross-language consistency rules** (`docs/governance.md` §"Multi-language consistency"). The
  fixtures are the behavioral floor cross-language implementations promise — "APIs MAY differ in
  syntactic shape; behavior MUST match conformance tests." This capability spec is the contract
  adapters target so that the cross-impl promise is enforceable end-to-end.

This capability does NOT define:

- **Specific language adapter implementations.** Concrete Python / TypeScript / future-language adapters
  ship in their respective implementation repositories. The spec defines the contract; implementations
  satisfy it.
- **Specific test-runner integration** (pytest, vitest, JUnit, etc.). The adapter MAY use any
  language-idiomatic runner; the spec mandates fixture discovery, parsing, execution, and assertion
  behavior, not the host runner's surface.
- **Fixture-authoring tooling** — linters that check fixture YAML against the schema, generators that
  scaffold fixture stubs from spec sections, visualization tools rendering the directive vocabulary as
  documentation. All useful, all out of scope.
- **Schema-validation tooling for the YAML itself.** Adapters MAY implement schema validation; the
  spec mandates behavior on schema violation (raise per §9 errors), not the validator surface.
- **Performance benchmarking or comparative-conformance reporting** between implementations.
  Performance is implementation-specific; conformance is behavioral.

## 2. Concepts

**Fixture.** A test case described declaratively in a YAML file plus a sibling Markdown description
file. The YAML defines what graph to construct, what initial state to use, and what to expect when the
graph runs; the Markdown describes intent, spec-section coverage, and pass / fail conditions in prose.

**Adapter.** A language-specific runtime that discovers fixture files under `spec/<capability>/conformance/`,
parses each fixture's YAML into native graph-construction calls in its host language, executes the
graph against the implementation's runtime, and asserts the result matches the YAML's `expected:` block.
The adapter is implementation-private; the fixtures are spec-public.

**Directive.** A named field that may appear in a fixture's YAML, declaring something the adapter must
translate into a runtime construct or assertion. Examples: `update` (a node behavior directive),
`fan_out` (a composition directive), `observers[]` (an observer registration directive),
`final_state` (an expected-outcome directive).

**Harness primitive.** A runtime construct the adapter MUST provide to satisfy directives that need
infrastructure beyond the bare graph engine — in-memory observer implementations, in-memory persistence
backends, slow-observer simulation, OTel collector capture, etc. The directive names the primitive; the
adapter provides it.

**Assertion shape.** A field under a fixture's `expected:` block specifying what the adapter MUST
verify about the executed graph's outcome. Exact-equality shapes (`final_state`, `execution_order`) check
literal equality; invariant shapes (`observer_event_invariants`, `invariants`) check named boolean
predicates suitable for nondeterministic-ordering cases.

**Invariant.** A name-keyed boolean predicate the adapter checks beyond the exact-equality assertions,
used when ordering is observable but not uniquely determined (fan-out instance scheduling, parallel-
branches branch scheduling, observer event dispatch within one phase).

**Case.** One scenario within a fixture. A fixture MAY contain a single case at top level or multiple
cases under a `cases:` list. Each case has its own graph definition, initial state, and expected
outcome.

**Invocation.** A single `invoke()` call within a fixture. A fixture MAY exercise multiple sequential
invocations (`invocations:` list) under shared graph + state configuration to test cross-invocation
behavior (sessions, resume from checkpoint, suspension-resume, etc.).

## 3. Fixture file format

### 3.1 Directory layout

Conformance fixtures live alongside each capability's spec at `spec/<capability>/conformance/`. Each
fixture is a numbered pair:

- `NNN-name.yaml` — declarative test data (the executable form)
- `NNN-name.md` — prose description of intent, spec-section coverage, and pass / fail conditions
  (the human-readable form)

The numbering (`001`, `002`, …) is per-capability-directory; numbers are zero-padded to three digits
and assigned at fixture-creation time. Numbers MUST NOT be reused after a fixture is removed (a removed
fixture's number is retired). Numbers MAY be non-contiguous if a fixture is removed.

The `name` portion is a kebab-case slug describing what the fixture tests. Implementations MUST
discover fixtures by walking `spec/<capability>/conformance/` directories for `*.yaml` files; the
numbering is presentational, not structural.

### 3.2 Per-directory harness notes via fixture-header comments

The capability spec is the home for **general** directives that span capabilities. Fixture-header
comments MAY supplement with **per-directory-specific** harness notes when a capability's fixtures share
a specialized contract that doesn't generalize.

**Worked example.** `spec/observability/conformance/001-otel-basic-trace.yaml` opens with a multi-line
comment block documenting the observability fixture suite's per-capability harness contract:

- The harness instantiates an in-memory OTel `SpanExporter` and a private `TracerProvider`
  (per observability §6 isolation).
- Optional config blocks the fixtures accept: `caller_correlation_id`, `detached_subgraphs`,
  `detached_fan_outs`, `disable_llm_spans`, `mock_llm`, `caller_global_otel_active`.
- Expected-outcome shapes specific to observability: `expected.span_tree`, `expected.log_records`,
  `expected.no_openarmature_spans_on_global`.
- Attribute placeholder syntax: `<uuid>` matches any canonical UUIDv4, `<any-string>` matches any
  non-empty string, `<trace_id_X>` matches an opaque trace_id with first-occurrence binding for
  cross-reference. (These inline value-tokens are normatively enumerated in §5.10 *Value matchers*,
  alongside the assertion sub-keys and the exact-value+derivation idiom; this list is the
  observability-suite example of them.)

That comment block is normative for the observability fixture suite even though it isn't part of this
capability spec. Implementations MUST honor per-directory harness notes when the fixture's YAML
references them; the directives this capability spec defines are the general surface, but per-directory
specialization is a permitted extension. A per-directory harness note is the second of the two
**definition homes** enumerated in §5's preamble, and a definition it carries is part of the recognized
vocabulary §8.2 parses against.

### 3.3 No required README per directory

Conformance directories MAY ship a `README.md` describing the directory's scope, but a README is NOT
required. The capability spec is the authoritative schema reference. A per-directory README that
documents no directive is a navigational aid; where a README carries the harness-note content §3.2
describes, it is normative for the directives it defines, per §5's *Definition homes* rule.

## 4. Fixture YAML schema

A fixture YAML document takes one of three top-level shapes.

### 4.1 Single-case form

The simplest shape — a single scenario at top level:

```yaml
state:
  fields:
    <field_name>:
      type: <type>
      default: <value>
      reducer: <reducer_name>

entry: <node_name>

nodes:
  <node_name>:
    <node-behavior directive>

edges:
  - {from: <node_name>, to: <node_name> | END}
  - {from: <node_name>, condition: { ... }}

initial_state: {<field>: <value>, ...}

observers:
  - {name: <name>, attach: <scope>, target: <target>, behavior: <behavior>, ...}

session_store: <store_name>
checkpointer: <checkpointer_name>

invoke:
  drain: { ... }
  # OR (for fixtures that exercise per-invoke directives at top level)

expected:
  final_state: { ... }
  execution_order: [ ... ]
  observer_events: { ... }
  invariants: { ... }
```

Directives appearing at the top level apply to a single implicit invocation; the adapter constructs the
graph, invokes it once, and asserts on the outcome.

### 4.2 Multi-case form (`cases:`)

A fixture MAY contain multiple independent cases sharing nothing but a file:

```yaml
cases:
  - name: <case_name_1>
    description: |
      <prose>
    state: { ... }
    entry: <node_name>
    nodes: { ... }
    edges: [ ... ]
    initial_state: { ... }
    expected: { ... }

  - name: <case_name_2>
    description: |
      <prose>
    state: { ... }
    ...
```

Each case is a fully-formed test in its own right. The adapter MUST run each case independently — no
state, observers, or backend instances are shared across cases within one fixture file.

**The `graph:` container.** A case MAY nest its graph specification under a `graph:` key instead of
carrying it directly:

```yaml
cases:
  - name: <case_name>
    graph:
      state: { ... }
      entry: <node_name>
      nodes: { ... }
      edges: [ ... ]
    initial_state: { ... }
    expected: { ... }
```

The container holds the graph specification and nothing else: `state:`, `entry:`, `nodes:`, `edges:`,
and any subgraph declaration the specification carries (§5.4 *Subgraph declaration placement*). Every
other case key stays a **sibling** of `graph:`, including `name:`, `description:`, `initial_state:`,
`expected:`, the compile-outcome assertions, and a case-level subgraph declaration.

The two forms are equivalent in what they specify, and an adapter **MUST** treat a case carrying a
`graph:` container exactly as it treats one carrying the specification directly: it compiles the same
way, and it **MUST** be executed when the case asserts a runtime outcome rather than only a
compile-time one. The container exists because a table fixture reads better when each case's graph is
one nested block, and it is the innermost of §5.4's three declaration sites.

An adapter **MUST NOT** require the container: a case carrying `state:`, `entry:`, `nodes:` and
`edges:` directly is the equally valid form shown above, and most shipped fixtures use it.

### 4.3 Multi-invocation form (`invocations:`)

A fixture MAY exercise multiple sequential invocations against the same compiled graph + shared
backend state (used for sessions, resume, suspension cycles):

```yaml
state:
  fields:
    ...
entry: <node_name>
nodes: { ... }
edges: [ ... ]
session_store: in_memory  # OR checkpointer: in_memory, etc.

invocations:
  - name: first_invoke
    session_id: <id>
    initial_state: { ... }
    expected:
      final_state: { ... }
      ...

  - name: second_invoke
    session_id: <same_id_or_different>
    initial_state: { ... }
    expected:
      ...

  - name: resume_invoke
    resume_invocation: <placeholder>
    signal_payload: { ... }
    expected:
      ...
```

The adapter constructs the graph and backend once, then runs each invocation against the shared state.
Invocations execute in declaration order. Per-invocation assertions verify outcomes; cross-invocation
state (e.g., a `<placeholder>` in `resume_invocation` that resolves to a prior invocation's id) is
resolved by the adapter from prior-invocation outcomes.

Multi-case and multi-invocation forms MAY be combined: a `cases:` list whose entries individually use
the `invocations:` shape is permitted.

### 4.4 Fixture version pinning

A fixture MAY declare which conformance-adapter version it targets via a top-level
`conformance_version:` key:

```yaml
conformance_version: "0.48.0"
state:
  ...
```

When `conformance_version:` is absent, the fixture targets the spec version at the time the fixture was
authored (recoverable from git history). When present, the adapter MUST verify its own
conformance-adapter version is compatible. The version-mismatch rule per §9 *Errors*:

- An adapter targeting `vX.Y.Z` MUST accept fixtures declaring `conformance_version` ≤ `vX.Y.Z` (the
  vocabulary is additive; later adapter versions know strictly more directives than earlier fixtures
  use).
- An adapter targeting `vX.Y.Z` MUST raise `fixture_version_unsupported` (§9) when a fixture declares
  `conformance_version > vX.Y.Z`. The adapter does NOT have the directive vocabulary the fixture
  requires; silent fallback would mask conformance gaps.

## 5. Directive vocabulary

This section is the authoritative home for the **general** directive surface, and is authoritative for
the *Definition homes* rule below, which governs where the definition of a directive introduced or
redefined after spec version 0.113.0 must live. Each directive entry specifies its YAML location,
parameters, runtime behavior the adapter MUST honor, and the spec section(s) the directive exists to
exercise. General directives in use that this section does not yet enumerate are a documentation gap, not
a licence to define them elsewhere.

**Definition homes.** A proposal that introduces or redefines a directive after spec version 0.113.0
**MUST** place that directive's definition in one of exactly two places:

1. **§5 of this capability spec**, for a directive used by more than one capability's fixtures, or whose
   contract is general even if only one capability currently exercises it.
2. **A per-directory harness note**, for a directive whose contract is specific to one capability's
   fixtures and does not generalize. A per-directory harness note is the fixture-header comment block
   described in §3.2 or the per-directory README described in §3.3, belonging to the `conformance/`
   directory whose fixtures use the directive.

Together these are the **recognized vocabulary**. A definition in either home is normative and an adapter
**MUST** honor it. §5 remains authoritative for the general surface and for this rule.

An adapter **MUST** treat a definition carried by a per-directory note as recognized **only for
fixtures under that note's own `conformance/` directory**. A fixture in another directory that uses
the same directive is outside the recognized vocabulary, because no note in its own directory defines
it, and §8.2's unknown-directive rule applies to it there.

Where §5 and a per-directory note both address the same directive, an adapter **MUST** follow §5 on any
point where they conflict. The note **MAY** supply detail §5 leaves to it, and an adapter **MUST NOT**
treat §5 naming a directive as voiding a note that specifies its shape.

A body of directives currently in use has a definition in neither home. Such a directive sits outside the
recognized vocabulary, and this rule is stated prospectively rather than retroactively invalidating it.
§5.9's fixture-specific invariant predicates are deliberately outside this rule: where the corpus
documents such a predicate at all it does so in the prose of the fixture that uses it, which is neither
home, and most are documented nowhere. Settling that surface is left to a proposal that can measure it.
Until then such a predicate remains outside the recognized vocabulary, so §8.2's unknown-name rule and
§5.9's obligation to implement it remain in conflict.

### 5.1 Node behavior directives

These directives appear under `nodes.<node_name>:` and define what the node does at runtime.

- **`update: {<field>: <value>, ...}`** — node returns a partial-update mapping when invoked. Per
  graph-engine §2's reducer contract, each field in the mapping merges into the prior state via that
  field's declared reducer. Exercises graph-engine §3 (execution model).
- **`update_pure: {<field>: <value>, ...}`** — same as `update` semantically; reserved for fixtures
  where the partial-update value is a constant literal that the adapter SHOULD inline verbatim
  without any post-processing (no formatter, no template expansion). Used in fixtures testing
  reducer behavior precisely. Exercises graph-engine §2.
- **`update_from_field: {<target>: <source_field>, multiplier: <int>}`** — node reads `<source_field>`
  from its current state, multiplies by `<multiplier>` (default 1), and returns
  `{<target>: <product>}`. Used in fan-out fixtures where each instance applies a deterministic
  transformation. Exercises pipeline-utilities §9 (fan-out item-projection rules).
- **`update_pure_from_state: {<output_field>: <harness_operation_name>}`** — per-directory harness
  extension (per §3.2). Used by observability fan-out / detached-trace fixtures (006, 008, 032,
  033) to derive a value from state via a named harness operation (e.g., `input_times_two`
  produces `output = input * 2`); operation names and semantics are documented inline in the
  fixture's YAML header comment. The adapter MUST implement each operation as specified in the
  fixture's prose.
- **`raises: "<error_message>"`** — node raises an exception with the given message instead of
  returning. Exercises graph-engine §4 (error semantics).
- **`suspend_with_descriptor: {signal_id: <id>, metadata: { ... }}`** — node calls
  `suspend(descriptor)` per suspension §3 with the given descriptor. Default `mark_node_completed=True`.
  The adapter MUST construct a real synthetic node body that calls the implementation's real
  `suspend()` operation; the directive does not simulate. Exercises suspension §3.
- **`conditional_suspend: {suspend_on_item_index: <int>, descriptor: { ... }, on_other_indices: { ... }}`**
  — node executing inside a fan-out instance: when `state.<item_idx_field>` equals the configured
  index, calls `suspend(descriptor)`; on other instance indices, applies the `on_other_indices`
  directive (typically `update_from_field`). Exercises suspension §8.2 fan-out propagation.
- **`invoke_drain_events_for: {timeout_seconds: <float>, snapshot_observer: <observer_name>}`** —
  before this node returns, the adapter MUST invoke
  `graph.drain_events_for(state.invocation_id, timeout=<timeout_seconds>)` then snapshot the named
  observer's accumulator bucket for that `invocation_id`. Both the drain summary and the snapshot
  are recorded for per-node assertion. Exercises graph-engine §6 *Per-invocation drain*.
- **`wrap_with_middleware: [{name: <name>, <middleware_config>}, ...]`** — the node body executes
  inside the named middleware(s), pre / post markers recorded as state-log entries for assertion.
  Standard middleware configs the adapter MUST support:
  - `{name: <name>, pre_log: <marker>, post_log: <marker>}` — middleware logs `pre_log` before
    `next()` and `post_log` after; verifies pre / post execution patterns.
  - `{name: <name>, pre_next_calls_suspend_with_descriptor: {...}}` — middleware itself calls
    `suspend()` from pre-`next()` (rejected per suspension §8.4).
  Exercises pipeline-utilities §6 (middleware) + suspension §8.4 composition.
- **`calls_llm: {messages: [...], stores_response_in: <state_field>}`** — per-directory observability
  harness extension (per §3.2). The node body issues one real `complete()` call against the mock
  provider (configured by the case-level `mock_llm`, §5.5) with the given messages and stores the
  response content in `<state_field>`. Used by the observability LLM-span fixtures. Exercises
  observability §5.5 (LLM provider span).

  Two **synthesis primitives** may stand in for literal content inside a `messages:` entry, so a fixture can
  induce an oversized or shaped payload without carrying one inline:

  - **`content_repeat: {char: <str>, bytes: <int>}`** in place of a message's text content, synthesizing it
    by repeating `char` until adding another repetition would exceed `bytes`. The result is the **largest
    whole number of repetitions whose UTF-8 encoding is at most `bytes`**: never longer than `bytes`,
    possibly shorter when `char` is multi-byte, and always valid UTF-8. A fixture needing an exact byte
    count uses a single-byte `char`. Used by the payload-truncation fixtures, whose whole subject is a value
    larger than the §5.5.5 cap, which is why the multi-byte case is specified rather than left to the
    adapter. `content` and `content_repeat` are mutually exclusive on one message; an adapter **MUST**
    reject a message carrying both with **`fixture_schema_invalid`** (§9).
  - **`base64_data_synthetic: {bytes: <int>}`** in place of an inline image's `source.base64_data` (llm-provider §3.1.3 *Image source*), synthesizing a
    base64 blob of the given byte length. The redaction rule it exercises (observability §5.5.5) is about
    the payload's shape, so no valid image bytes are needed.

  Both are test-only input shaping and assert nothing themselves. `message_repeat` (§5.15) is the same
  primitive applied to an exception message.
- **`calls_llm_from_wrapper: {phase: pre|post, messages: [...], yield_after_call: <bool>}`** — the adapter wraps the node in a
  middleware that issues exactly one real `complete()` call against the configured mock provider in
  the named phase: `pre` (before `next()`, so the calling node's span is not yet open) or `post`
  (after `next()` returns, so the node's span is already closed) — default `pre`. Either way the
  calling node's span is NOT open when the provider span / `LlmCompletionEvent` is emitted, so the
  call is orphaned from its calling-node span. The response is NOT written to state (it models a
  guardrail / classifier side call); the node's own body still runs inside `next()` (the node span
  still opens, making the orphan provider span a sibling of — not a child of — the node span).
  Exercises observability §5.5 *Lineage-resolved parent* (the orphan fallback to the nearest
  enclosing wrapper per §4.3).

  **`yield_after_call: <bool>`** (default `false`). When `true`, the adapter **MUST** ensure that
  observer delivery **through this call's provider event** has completed before the wrapper returns.
  The obligation is on what is achieved, not on the host language's mechanism for achieving it.
  When `false` the wrapper returns immediately after the call, which is the behavior every fixture
  carrying `calls_llm_from_wrapper` had before proposal 0124.

  The obligation is stated as a barrier on **this call's** event rather than as a yield, because
  graph-engine §6 makes the delivery queue strictly serial across the whole invocation: conceding a
  single turn hands the queue one event, and nothing binds that event to this call. An older event
  consumes the turn, the wrapper resumes, the node body runs, and its `started` event synthesizes
  the dispatch span before the provider event is ever drained, which is the favorable interleaving
  the directive exists to eliminate.

  Without it no fixture can distinguish an implementation that resolves the parent **structurally**
  (observability §5.5) from one that happens to pass because the wrapper span was already
  materialized when the orphan resolved. An observer that does its work on the delivery queue and one
  that registers spans in the engine's execution path disagree about exactly that interleaving, and
  the directive is what makes the difference observable rather than architecture-dependent.
- **`augment_metadata: {<key>: <value>, ...}`** — node calls `set_invocation_metadata(**kwargs)` per
  observability §3.4 with the given key/value pairs. Used in observability fixtures testing
  per-async-context metadata propagation. Exercises observability §3.4.
- **`augment_metadata_from_field: {<key>: <state_field_name>}`** — node reads `<state_field_name>`
  from state, then calls `set_invocation_metadata(<key>=<value>)` with the field's value. Used in
  fan-out per-instance metadata fixtures. Exercises observability §3.4 per-async-context scoping.
- **`capture_invocation_metadata_into: <state_field_name>`** — node calls
  `get_invocation_metadata()` per observability §3.4 and writes the returned (immutable) mapping
  snapshot into the named state field for downstream assertion. Exercises observability §3.4 read
  API.
- **`cause: {category: <category|null>, message: <str>, cause: {...}}`** — an optional field on the
  error a failure mock raises (e.g. a `failure_sequence` entry, or one of the `flaky*` failure
  mocks). When present, the raised error is chained to an originating cause via the host language's
  exception-cause linkage; `cause` nests recursively for multi-link chains. The adapter MUST
  construct the chain so a consumer walking it (e.g. the pipeline-utilities §6.3 failure-isolation
  event's cause chain) observes each link's `category` / `message`. Carriers the engine adds
  (graph-engine §4 `node_exception`) are independent of this mock-authored chain. Exercises
  pipeline-utilities §6.3 (failure-isolation cause chain).

**Failure-mock directives.** Beyond `raises:`, the retry (pipeline-utilities §6.1), failure-isolation
(§6.3), checkpoint-resume (§10), and collect-mode (§9.5) fixtures inject failure through a family of
node mocks (each under `nodes.<node_name>:`), keyed on the failure axis each models:

- **`failure_sequence` entry** — each entry is `{transient: <bool>, category: <category|null>,
  message: <str|null>}`; a `null` entry denotes a non-failing attempt at that position.
  `transient: true` + a `category` raises a transient (retry-classifier-friendly) error;
  `transient: false` raises a non-transient one.
- **`flaky`** — a node mock with two sub-forms:
  - **Sequence form:** `{failure_sequence: [<entry|null>, ...], success_update: {<field>: <value>}}`
    — raises once per entry across successive **attempts**; on an exhausted sequence (or a `null`
    entry) returns `success_update`.
  - **Compact form:** `{fail_first_invocation_only: <bool>, on_success: {<field>: <value>}}` — fails
    the **first whole invocation** only (raised as `node_exception`), succeeding (returning
    `on_success`) on any resume.
- **`flaky_by_index`** — fan-out mock with `success_compute` and an **optional** `category` (defaults
  to `provider_unavailable`; meaningful only for the retrying form, where it drives retry
  classification), in one of two forms: `{fail_when_idx: <int>}` — the instance whose **item value**
  equals `<int>` fails **deterministically** (no retry; a collect-mode seam, `category` typically
  omitted) — or `{fail_count_per_idx: <int>}` — every instance fails its first `<int>` **attempts**,
  then succeeds (retry).
- **`flaky_per_index`** — fan-out mock, **invocation**-keyed, with `success_compute`, in one of two
  forms: `{fail_first_run_indices: [<int>, ...]}` (those indices fail the **first invocation** only,
  then succeed on resume) or `{always_fail_indices: [<int>, ...]}` (those indices fail **every**
  invocation — a deterministic failure, e.g. for collect-mode error-contribution resume).
- **`flaky_instance_only`** — `{fail_count_per_instance: <int>, category: <category>,
  success_compute: {...}}` — each fan-out instance fails its first `fail_count_per_instance`
  **whole-instance invocations** (the subgraph re-runs from scratch on retry), then succeeds.
- **`flaky_resume_aware`** — `{fail_first_invocation_count: <int>, fail_resumed_invocation_count:
  <int>, category: <category>, on_success: {...}}` — fails N attempts on the first invocation, then
  M attempts on any resumed invocation before succeeding; used to verify `attempt_index` resets on
  resume.

Any failure these mocks raise MAY carry a `cause` (the `cause` directive above, proposal 0070) to
chain an originating cause. In any of the success-state mappings (`success_update` / `on_success` /
`success_compute`), a `<value>` that is a string naming a declared state field is read from that
field; any other value is taken as a literal.

**`flaky_per_index` vs `flaky_by_index`.** Both select fan-out instances by index, but for different
purposes — the shared `_index` suffix invites confusion:

- **`flaky_by_index`** has no checkpoint/resume semantics: `fail_count_per_idx` fails the first N
  *attempts* of each instance (retry); `fail_when_idx` fails the instance with that *item value*
  deterministically (a collect-mode seam). Use it for fan-out + retry / collect-mode fixtures.
- **`flaky_per_index`** is **invocation**-keyed (checkpoint/resume): `fail_first_run_indices` fail the
  *first invocation* then succeed on resume; `always_fail_indices` fail *every* invocation. Use it
  for fan-out + checkpoint fixtures.

**Success-state field naming (flagged, not changed).** The family names the success-path state
update three ways — `success_update` (`flaky` sequence form), `on_success` (`flaky` compact form,
`flaky_resume_aware`), and `success_compute` (`flaky_by_index`, `flaky_per_index`,
`flaky_instance_only`). This is organic drift, not a semantic distinction — all three are the partial
update the mock returns on the success path. They are documented as-is (renaming would churn the
accepted fixtures and adapters for no behavioral gain); unifying the name is a candidate future
cleanup.

### 5.2 State / schema directives

These directives appear under `state:` and define the typed-state schema.

- **`state.fields.<field_name>.type`** — string. Declares the field's type. The type system supports
  three category classes, which compose recursively:
  - **Primitives.** `string`, `int`, `float`, `bool`, `any`.
  - **Parameterized containers.** `list` (no element constraint) OR `list<T>` where T is recursively
    any accepted type string; `dict` (no constraints) OR `dict<K,V>` where K and V are recursively
    any accepted type strings.
  - **User-defined record types.** A bareword (e.g., `error_entry`) refers to a record type the
    fixture defines elsewhere (typically as a nested `state.fields` schema with its own fields). The
    adapter MUST support user-defined record types as element types of `list<T>` and as value types
    of `dict<K,V>`.

  Adapters MUST translate the type string into a host-language typed-state field with equivalent
  shape semantics. List-element-type-omitted (`list`) is permitted; the adapter MUST NOT impose
  element-type constraints in that case.
- **`state.fields.<field_name>.default`** — the field's initial value if `initial_state` does not
  supply one. MUST match the declared type.
- **`state.fields.<field_name>.reducer`** — string OR single-key mapping. The string form names a
  parameter-less canonical reducer: one of `last_write_wins` (default), `append`, `merge`,
  `concat_flatten`, `merge_all` (per graph-engine §2). The single-key mapping form names a
  canonical factory reducer with its construction kwargs: `{<factory_name>: <kwargs_mapping>}` —
  e.g., `{bounded_append: {max_len: 3}}`, `{dedupe_append: {key: id}}`, `{merge_by_key: {key: id}}`
  (per graph-engine §2's factory reducers from proposal 0023). The adapter instantiates the named
  factory with the kwargs at field-registration time and translates each reducer name into the
  corresponding implementation-side reducer. For factory reducers taking a `key` callable, the
  YAML expresses the key as a field-name string (e.g., `key: id`); the adapter constructs the
  callable as the language-idiomatic accessor for that field.
- **`initial_state: {<field>: <value>, ...}`** — top-level (or per-invocation) initial state. Fields
  omitted from `initial_state` default to the schema's declared default. Adapters MUST validate the
  resulting initial state against the schema before invocation.

### 5.3 Edge directives

These directives appear under `edges:` as a list of edge specifications.

- **Static edge**: `{from: <node_name>, to: <node_name> | END}` — always routes from source to
  destination. Exercises graph-engine §2 (static edge semantics).
- **Conditional edge**: `{from: <node_name>, condition: { ... }}` — destination depends on
  post-update state. The `condition:` mapping uses:
  - `if_field: <field_name>` — the field to evaluate
  - `equals: <value>` — the comparison value
  - `then: <node_name> | END` — destination when the equality holds
  - `else: <node_name> | END` — destination when it doesn't
  Exercises graph-engine §2 (conditional edge semantics).

### 5.4 Composition directives

The **node-attached** directives in this section (`subgraph:` as a node's behavior, `fan_out:`,
`parallel_branches:`) appear under `nodes.<node_name>:` and configure compound node shapes: `subgraph:`
per graph-engine §2, `fan_out:` and `parallel_branches:` per pipeline-utilities §9 / §11. The **declaration forms** below appear at none of those positions; where
they may sit is stated in *Subgraph declaration placement*.

- **`subgraph: <subgraph_name>`** — the node executes a named subgraph (declared via `subgraph:` or a
  `subgraphs:` mapping, at any of the positions *Subgraph declaration placement* below permits).
  Exercises graph-engine §2 (subgraph composition).
- **Subgraph declaration via `subgraph:`** — single inline subgraph (used when only one
  subgraph is needed):
  ```yaml
  subgraph:
    name: <name>
    state: { fields: ... }
    entry: <node_name>
    nodes: { ... }
    edges: [ ... ]
  ```
- **Subgraph declaration via `subgraphs:`** — named mapping (used when multiple subgraphs
  are needed, typically with parallel-branches):
  ```yaml
  subgraphs:
    <name_1>: { state: ..., entry: ..., nodes: ..., edges: ... }
    <name_2>: { ... }
  ```

**Subgraph declaration placement.** A subgraph declaration (`subgraph:` for a single inline subgraph,
`subgraphs:` for a named mapping) is scoped to the graph specification it accompanies, and an adapter
**MUST** accept it wherever that specification appears:

- at the fixture document's **top level**, where it is in scope for every case in the file;
- inside an individual **case**, where it is visible to that case alone;
- inside a case's **`graph:` block**, for a table fixture whose cases each carry a complete graph
  specification.

A subgraph body is itself a graph specification, so a declaration nested inside one is scoped to that
body by the same principle. This rule governs the three sites above, which are the ones a case resolves
against; it neither sanctions nor forbids the nested site.

One document-root declaration cannot express more than one body for a name, so a top-level declaration
alone reaches every case only where every case binds that name to the same body. Where cases bind a name
to different bodies, the differing bodies appear at the narrower sites. A top-level declaration **MAY**
still stand alongside them; the resolution rule below decides which applies.

The three sites rank from outermost to innermost in the order listed above: document top level, then
case, then the case's `graph:` block. Where a fixture declares the same subgraph name at more than one of
them, an adapter **MUST** resolve that name using the innermost declaration in scope for the case being
run.

Where both declaration forms appear at the **same** site and bind the same name, the site ranking cannot
decide between them. An adapter **MUST** then resolve the name using the `subgraphs:` mapping entry, since
it names the binding explicitly.

- **`fan_out:`** — fan-out node configuration:
  ```yaml
  fan_out:
    subgraph: <subgraph_name>
    items_field: <state_field>  # OR count: <int>
    item_field: <field_inside_subgraph_state>
    collect_field: <field_inside_subgraph_state>
    target_field: <field_in_outer_state>
    error_policy: fail_fast | collect
    concurrency: <int>  # optional
    concurrent_mode: serial | concurrent  # optional harness knob — forces serial vs concurrent instance dispatch (distinct from `concurrency`, the parallelism bound; interaction below)
  ```
  Exercises pipeline-utilities §9 (parallel fan-out). `concurrent_mode` and `concurrency` are
  normally set separately; if both appear, `serial` dispatches one instance at a time (equivalent to
  `concurrency: 1`, overriding any larger `concurrency`) and `concurrent` dispatches up to
  `concurrency` at once (or the §9 default when `concurrency` is absent).
- **`parallel_branches:`** — parallel-branches dispatcher configuration:
  ```yaml
  parallel_branches:
    branches:
      <branch_name>:
        subgraph: <subgraph_name>
        outputs:
          <outer_state_field>: <subgraph_state_field>
      ...
    error_policy: fail_fast | collect
  ```
  Exercises pipeline-utilities §11 (parallel branches).

### 5.5 Observer / observability directives

These directives appear at top level as `observers:` and configure observer attachment for the
fixture.

- **`observers[]`** — list of observer registrations. Each entry:
  - **`name: <observer_name>`** — identifier for cross-reference from assertions.
  - **`attach: graph | invocation`** — `graph` registers on the compiled graph (fires on every
    invocation); `invocation` passes through `invoke(observers=...)` for one invocation only.
  - **`target: outer | inner | <subgraph_or_node_name>`** — `outer` attaches to the outermost
    graph; `inner` attaches to the innermost subgraph; specific names attach to a named subgraph
    or node.
  - **`behavior: record | accumulate | raise`** — what the observer does on each event:
    - `record` — records the event into a per-observer event log for assertion via
      `observer_events` / `observer_event_invariants`.
    - `accumulate` — accumulates events into per-`invocation_id` buckets exposed via a read API
      the adapter MUST provide (consumed by `invoke_drain_events_for`'s `snapshot_observer` and
      by `node_accumulator_snapshots` assertions).
    - `raise` — observer raises on every event it receives. Used to test observer-error isolation
      (graph-engine §6: observer errors MUST NOT interrupt the graph or affect other observers).
  - **`sleep_ms_per_event: <int>`** OR **`sleep_ms_per_event: {first_invocation: <int>, subsequent_invocations: <int>}`**
    — observer sleeps the configured milliseconds before processing each event. Used in fixtures
    testing the drain primitive's timeout discipline. The two-key form lets the first invocation
    use one pace and subsequent invocations another (graph-engine §6 *Drain* fixture 024).

  - **`phases: [<phase>, ...]`** — phase subscription filter. Defaults to `[started, completed]`
    when omitted; explicit list restricts the observer to the named phases per graph-engine §6
    *Per-observer phase subscription*.

- **Case-level observability harness keys** — per-directory extensions (per §3.2) appearing at the case
  top level (siblings of `nodes:` / `expected:`, not under `observers:`): `mock_llm: [{status: <int>,
  body: {...}}, ...]` supplies the canned OpenAI-compatible chat-completion responses (llm-provider §8
  wire shape) the mock provider returns to successive `complete()` calls (paired with `calls_llm` /
  `calls_llm_from_wrapper`). A **non-2xx** `mock_llm` entry MAY carry a
  **`raises: {error_type, message | message_repeat}`** sub-directive, the LLM-side counterpart of §5.15's
  retrieval form and of the tool path's `mock_tool: {raises: ...}` (fixtures 093 / 098): it overrides
  only the exception's literal `error_type` / `error_message` while the `status` still fixes the
  deterministic llm-provider §7 `error_category`. `message_repeat` carries §5.15's shape and the same
  mutual exclusion with `message`.
  Without it a fixture cannot induce a Generation failure with a caller-controlled message, since
  `mock_llm` otherwise accepts only `{status, body}`. A non-2xx entry carrying `raises` MAY omit
  `body`, the same optionality §5.15 gives the retrieval mocks; fixture 160's Generation case does. `disable_llm_spans: true` constructs the OTel observer with the §5.5
  LLM-span opt-out; `caller_global_otel_active: true` installs a second exporter on the OTel global
  TracerProvider to exercise the §6 isolation rule.

- **`langfuse_client` construction + Langfuse-leak assertions** (observability provider isolation, §6 /
  §8.9). `langfuse_client: {mode: credentials | supplied, provider?: global | isolated}` configures how
  the Langfuse observer's client is constructed for the case: `mode: credentials` drives the
  implementation's own construct-from-credentials path (§8.9 mode (b)); `mode: supplied` hands it a
  harness-constructed client (mode (a)). `provider` applies only to `mode: supplied` (default `global`).
  The observers' payload settings use the existing per-observer convention — `langfuse_observer:
  {disable_provider_payload: <bool>}` for the Langfuse side and `otel_observer:
  {disable_provider_payload: <bool>}` for the OTel side (below). Omitted, each observer keeps its
  §5.5.4 default (`True`). openarmature's mode-(b) payload-leak invariant (§6) applies whenever openarmature
  would emit any **harvested payload** — the provider payload (`disable_provider_payload: false`), the
  Trace-level state payload (`disable_state_payload: false` or a `trace_*_from_state` hook), or a failed
  observation's error message — that would reach a shared provider (broadened by proposal 0117); the
  provider-payload case is one such configuration, and a composed OTel observer is neither required nor the
  trigger. The client is the provider-faithful fake of §6.4 (its spans carry the
  `langfuse.observation.*` attribute namespace, §6.4), so with `caller_global_otel_active: true` a leak is
  observable. A *Langfuse observation
  span* is one carrying that attribute namespace. `expected.no_langfuse_observations_on_global: true`
  asserts **none** reached the global exporter (the Langfuse analog of `no_openarmature_spans_on_global`);
  `expected.no_langfuse_observations_on_private: true` asserts none reached openarmature's **own private
  OTel** provider's exporter either — together they gate mode-(b) isolation against
  **both** provider spellings §6 forbids (not the global provider, and not openarmature's own OTel
  provider); and `expected.langfuse_observations_on_global: true` asserts at least one **did** reach the
  global exporter (the mode-(a) non-mutation effect, and the mode-(b) opt-out / acknowledged-leak effect).

- **`langfuse_client` isolation-outcome directives + assertions** (observability §6, [proposal 0116](../../proposals/0116-langfuse-isolation-fail-loud.md)). Extend the `langfuse_client` directive and add the assertions that gate the mode-(b) payload-leak invariant's arms:
  - `langfuse_client: {preexisting_same_key_client: <bool>}` (default `false`) — when `true`, the harness constructs a Langfuse client for the **same credential** *before* the implementation constructs its own, priming the SDK's per-credential singleton so the implementation is not first; the primed client binds the global provider (the provider-faithful default, §6.4), reproducing the discarded-isolation path deterministically. Meaningful only with `mode: credentials`.
  - `langfuse_client: {accept_shared_provider: <bool>}` (default `false`) — sets the single shared-provider caller opt-out on the implementation's Langfuse observer construction. Default `false` exercises the fail-closed path.
  - `adapter_capabilities: {langfuse_bound_provider_detection: <bool>}` — declared **by the adapter**, not per-case: whether the implementation's Langfuse SDK surface lets it establish the client's bound provider. Because that introspection is non-portable (§6; observability §6 makes the mode-(a) warn a MAY for the same reason), it is a per-adapter property, not a universal capability, so fixture 158 gates its arms on it — a **detection-capable** adapter MUST satisfy the *raise* cases, a **non-capable** adapter the *suppress* case; both satisfy the opt-out case. This prevents an adapter from passing raise-behavior (verified only against the §6.4 fake's accessor) that its real SDK cannot portably perform. An **undeclared** `langfuse_bound_provider_detection` defaults to `false` (a minimal adapter is treated as non-capable). A case selects its audience with `requires_capability: {langfuse_bound_provider_detection: <bool>}` — asserted only against adapters whose declaration (defaulted as above) matches; a case with no `requires_capability` applies to all. A case gated out by `requires_capability` is a **recognized skip**, not a silently-omitted case (§8.1 / §8.2 / §9): the raise floor and the suppress floor are each covered by whichever adapter class its gate selects.
  - `expected_construction_error: {category: <token>}` — a **top-level case-level** raised-error assertion (the observer/client-construction analogue of `expected_compile_error`, and catalogued alongside it in §5.8), placed as a sibling of `nodes` / `edges` / `expected`, **not** nested under `expected:`: asserts that standing up and running the case raises the categorized error at construction or first use. Fixture 158's raise cases use `{category: langfuse_provider_isolation_unavailable}`, the observability-native category observability §6 defines; like other raised-error categories it is referenced by `{category}` per §5.8's per-capability rule (a category is not a `carries` field key, so §5.13 does not govern it).
  - `expected.no_payload_bearing_langfuse_observations_on_global` / `expected.payload_bearing_langfuse_observations_on_global` — payload-scoped variants of the 0115 leak assertions (the §6.4 fake distinguishes a payload-bearing observation from a payload-free one). The raise cases assert **no payload-bearing** observation reached the global exporter (a metadata-only span reaching it before a first-use raise does not violate the payload invariant); the suppress case asserts an observation reached it but **payload-free**; the opt-out case asserts a **payload-bearing** one did (the acknowledged leak). Proposal 0117 broadens **payload-bearing** to any harvested payload — provider `input` / `output`, a Trace-level state `input` / `output` (raw state or a `trace_input_from_state` / `trace_output_from_state` hook value), **or** a failed observation's `error_type` / `error_message` — with the §8.4.1 minimal stub and a category-only failed observation as **payload-free**; the state channel uses the existing `langfuse_observer.disable_state_payload` / `trace_*_from_state` directives (proposal 0043 / fixture 037) and a failure is induced with the existing mock-failure directives (proposal 0107), so no new directive is added. Proposal 0118 **narrows** the error half of that classification to the `error_message` alone: a failed observation's `error_type` is a classification token rather than harvested text, so it does not make an observation payload-bearing (and is ungated by `disable_provider_payload`, observability §5.5.4).
  - `expected.log_records` entries gain a `level` key (e.g. `level: WARNING`) alongside `body` / `attributes`. OTel severity is a first-class `LogRecord` field, not an attribute, so without it a mandated `WARNING` cannot be asserted (an implementation emitting at `INFO` would pass). An entry matches by the **subset** of fields it specifies: an entry with only `level` asserts that a log record of that severity **exists** (body / attributes unconstrained), non-exhaustively (other records may be present). Fixture 158's opt-out and suppress cases assert `level: WARNING` this way.

- **Observer payload control + diagnostic assertion** (observability §5.5.4 / §7, [proposal 0121](../../proposals/0121-diagnostic-event-names-and-otel-observer-directive.md)). These are general observer-configuration and log-assertion directives, not part of the `langfuse_client` isolation family above:
  - `expected.log_records` entries **MAY** carry **`event_name: <string>`** alongside `level`, `body` and `attributes`, asserting the record's OTel `LogRecord` `EventName` field equals the given value (observability §7 *Diagnostic event names*). Severity alone cannot distinguish one mandated diagnostic from another, or from an unrelated `WARNING`; the event name can. Matching remains a subset over the fields an entry specifies and the list remains non-exhaustive.
  - **`otel_observer: {disable_provider_payload: <bool>, disable_genai_semconv: <bool>}`** configures the composed OTel observer's flags for the case, the OTel-side counterpart of `langfuse_observer`. Both keys are optional; omitted, the observer keeps that flag's observability §5.5.4 default. An adapter **MUST** honor the directive when present: a case that sets a flag and an adapter that ignores it produce the same observable result as a case that does not set it, so silently dropping it makes the case vacuous rather than failing it.

  - **`langfuse_observer: {payload_byte_cap: <int>}`** / **`otel_observer: {payload_byte_cap: <int>}`** configure that observer's truncation cap, the byte bound observability §5.5.5 applies to each payload-classified value the observer writes. Omitted, the observer keeps §5.5.5's default of **65,536 bytes**. The cap is **per observer**, so a case MAY set it on one observer and leave the other at the default; that asymmetry is the only way a fixture can separate an implementation applying the correct observer's cap from one reading its sibling's, which observability §8.7 makes a **MUST NOT**. Setting neither leaves both at the same default and no such fixture can discriminate. An adapter **MUST** honor the directive when present. Fixture 023 sets the Langfuse cap alone; fixture 160 does the same to gate §8.7's direct-application arm.

- **`metadata_absent` on a Langfuse observation entry** (observability §5.5.4 / §8.4, [proposal 0118](../../proposals/0118-llm-error-message-channel.md)). An observation entry inside `expected.langfuse_trace.observations` MAY carry **`metadata_absent: [<key>, ...]`**, asserting none of the listed keys are present in that observation's `metadata`. The existing `metadata:` assertion is a **subset** match (an observation carries cross-cutting keys such as `correlation_id` and the §8.4.2 node dimensions that a fixture does not enumerate), so it can assert a key's value but never its absence. This is the Langfuse-observation analogue of the OTel-span `attributes_absent` directive (§5.11, proposal 0095), added for the same reason and with the same semantics. Fixture 159 uses it to gate `disable_provider_payload`'s suppression of a failed observation's `error_message`, which cannot be expressed by asserting values. `error_type` is not gated and stays present, so it is asserted by value in the same case rather than through this directive.
- **`metadata_truncation` on a Langfuse observation entry** (observability §5.5.5 / §8.7, [proposal 0119](../../proposals/0119-error-message-cap-and-reserved-keys.md)). **`metadata_truncation: {<key>: {max_bytes: <int>, marker_pattern: <str>, utf8_valid: <bool>, prefix_of_full_serialization: <bool>}}`** asserts that the named `metadata` field was truncated per observability §5.5.5. It is the metadata-field analogue of the span-side `attribute_truncation` (§5.11) and carries the same four independent sub-keys with the same meanings; an entry MAY carry any subset. It exists because a value written directly by the Langfuse mapping, such as a failed observation's `error_message`, has no span attribute for `attribute_truncation` to assert against. It carries `attribute_truncation`'s honor rule unchanged: an adapter **MUST** honor the directive when present, an entry naming a key asserts that key is **present** as well as truncated, and an entry **MUST** carry at least one sub-key.

OTel and Langfuse emission are NOT observer behaviors. Observability fixtures that exercise OTel
span emission OR Langfuse trace/observation emission rely on **harness primitives** the adapter
provides at the capability-directory level — an in-memory OTel `SpanExporter` instantiated for
the observability fixture suite, an in-memory Langfuse client wrapper, etc. The per-directory
harness contract (per §3.2) documents this; see also §6 *Harness primitives*.

**Typed-event collector directives.** Beyond the raw `observers[]` registration above, fixtures assert the
graph-engine §6 **typed event families** via a dedicated collector:

- **`typed_observers: [{name: <collector>, kind: typed_event_collector, filter_event_type?: <EventType>}]`** —
  a top-level list registering one or more typed-event collectors. A `typed_event_collector` retains every typed
  event it receives in **observer-internal storage** (observers MUST NOT mutate state per graph-engine §6; the
  harness reads the events back via introspection, with no state-field round-trip). The optional
  `filter_event_type` narrows a collector to a single family. The captured families are the graph-engine §6
  typed events: `LlmCompletionEvent`, `LlmFailedEvent`, `LlmTokenEvent`, `LlmTokenFailedEvent`, `EmbeddingEvent`,
  `EmbeddingFailedEvent`, `RerankEvent`, `RerankFailedEvent`, `ToolCallEvent`, `ToolCallFailedEvent`, and
  `NodeEvent`.
- **`contains_event: {event_type: <EventType>, fields: {<field>: <expected>, ...}}`** — appears under
  `expected.observers.<collector>` and asserts the collector's storage holds an event of `event_type` whose
  `fields` match by value (each per the §5.10 *Value matchers* vocabulary — format tokens, first-occurrence
  bindings, assertion sub-keys, or a literal scalar / nested mapping). Sibling assertion forms on the same slot:
  **`contains_event_of_type: <EventType>`** and **`contains_exactly_one_event_of_type: <EventType>`** (presence
  / exactly-one, no field match), and per-family counts as either a single **`event_count: {event_type: <T>,
  count: <N>}`** (one mapping) or a list **`event_counts: [{event_type: <T>, count: <N>}, ...]`** — `count: 0`
  asserts a family is **absent**, the mutual-exclusion form.

  **Present-but-null vs absent in `contains_event.fields`.** The distinction is expressed **structurally**, not
  via a suffix: a `fields:` entry written as a literal `null` matches only a field that is **present and null**
  (distinct from a field the event omits); a `fields:` entry written as a **nested mapping** (e.g.
  `usage: {prompt_tokens: null, ...}`) requires the field to be a **present record** — a null-valued or omitted
  field cannot satisfy a nested-mapping expectation; and **omitting** a key from `fields:` asserts **nothing**
  about that field. This three-way distinction (present-and-null / present-record / no-assertion) is
  load-bearing — it is what lets a fixture assert an event mirrors a present-record-of-null-counters rather than
  a null record, or a nulled figure rather than a verbatim wire value.

### 5.6 Persistence directives

These directives appear at top level and configure persistence backends.

- **`session_store: <store_name>`** — names the SessionStore backend the adapter MUST instantiate
  for this fixture. The adapter MUST provide at minimum `in_memory` (per sessions §5.5). Exercises
  sessions §3 (identity scoping) + §5 (SessionStore protocol) + §6 (lifecycle hooks).
- **`checkpointer: <checkpointer_name>`** — names the Checkpointer backend the adapter MUST
  instantiate for this fixture. The adapter MUST provide at minimum `in_memory` (per
  pipeline-utilities §10.13). Exercises pipeline-utilities §10 (checkpointing).
- **`loaded_session_state: <mapping_or_null>`** — appears under per-invocation expected blocks.
  Asserts the session state the engine loaded at invoke entry (`null` if no record existed).
  Exercises sessions §6.1 (auto-save / auto-load lifecycle).
- **`saved_session_assertions: {state: { ... }, ...}`** — appears under per-invocation expected
  blocks. Asserts the session state written to the SessionStore at invoke exit. Exercises sessions
  §6.1.
- **`checkpointer_assertions: { ... }`** — appears under per-invocation expected blocks. Asserts
  the checkpointer backend's state at invocation completion (e.g., `paused_invocation_record_exists`,
  `record_type`). Exercises pipeline-utilities §10 + suspension §8.5.
- **`populate_checkpointer_via_runs: <int>`** — appears at the per-invocation level. Tells the
  adapter to run the graph the specified number of times BEFORE the test invocation, seeding the
  checkpointer with N completed invocation records. Used by fixtures that need to verify
  checkpoint resume behavior against a populated backend (e.g., "resume with a fake id when other
  records DO exist" — fixture 030). Exercises pipeline-utilities §10.
- **`first_run_expected_error: {category: <category>, raised_from: <node_name>}`** — at the invocation level. The
  error expected to end the **first** run before a resume: a failure mock fails, propagates under
  `fail_fast`, and the engine surfaces this category from the named node. Pairs with `resume:`.
  Exercises pipeline-utilities §10 (resume).
- **`resume: {from_first_run: <bool>, expected: { ... }, invariants: { ... }}`** — at the invocation level. After
  the first run ends (via `first_run_expected_error` or `crash_injection`), the adapter resumes the
  invocation from the saved checkpoint (`from_first_run: true` resumes the same invocation id) and
  asserts the resumed run's `expected` block plus any resume-specific `invariants`. Exercises
  pipeline-utilities §10.4 (resume model).
- **`crash_injection: {<boundary>}`** — at the invocation level; an alternative to `first_run_expected_error` for
  triggering a resume **without** an instance failure. The adapter runs the graph until the named
  checkpoint boundary's save has fired, then abandons the in-flight run, retaining only the
  persisted checkpoint; the first run has **no** asserted outcome (it "crashed"), and `resume:`
  loads from that checkpoint. `<boundary>` is one of:
  - **`after_node: <node_name>`** — crash immediately after the node's checkpoint save on its
    `completed` event (per pipeline-utilities §10.3).
  - **`after_fan_out_instance: {node: <fan_out_node>, index: <int>}`** — crash immediately after the
    given fan-out instance's `completed` save fires (per §10.11); the saved record reflects sibling
    instance states as of that moment.

  Lets a fixture checkpoint a fan-out where some instances **completed** (including
  `FailureIsolation`-degraded instances, which complete rather than propagate) and assert, on
  resume, that those slots roll forward unchanged while not-yet-run instances dispatch. Exercises
  pipeline-utilities §10.11 (per-instance fan-out resume).

### 5.7 Invocation-shape directives

These directives configure how the adapter invokes the compiled graph. Two forms:

**Single-invocation (top-level):**

```yaml
initial_state: { ... }
caller_metadata: { ... }      # observability §3.4
caller_correlation_id: <id>   # observability §3.1
caller_invocation_id: <id>    # observability §5.1
invoke:                       # OR invoke_with: — equivalent
  drain: { timeout_seconds: <float> }  # graph-engine §6 (process-wide drain at end)
  # OR drain: {} for explicit no-timeout
  resume_invocation: <id>             # when resuming from a checkpoint or suspended record
expected: { ... }
```

The container key MAY be spelled `invoke:` OR `invoke_with:` — adapters MUST treat them as
equivalent. Different fixtures use different spellings historically; the spec ratifies both. Both
forms accept the same set of sub-keys (`drain:`, `resume_invocation:`, etc.).

**Multi-invocation (`invocations:` list):**

```yaml
invocations:
  - name: <invocation_name>
    session_id: <id>                # sessions §3
    correlation_id: <id>            # observability §3.1
    caller_invocation_id: <id>      # observability §5.1
    caller_metadata: { ... }        # observability §3.4
    initial_state: { ... }
    resume_invocation: <id_or_placeholder>  # for checkpoint or suspension resume
    signal_payload: { ... }         # suspension §7
    drain: { timeout_seconds: <float> }
    expected: { ... }
```

The `<placeholder>` form for `resume_invocation` allows referring to prior invocations' outcomes —
the adapter MUST resolve `"<from previous suspended outcome>"` or `"<invocation_id from initial completed invoke>"`-style
placeholders by inspecting prior invocations' returned outcomes. The exact placeholder syntax is
implementation-defined; the spec requires only that the adapter support some such resolution.

### 5.8 Expected-outcome directives

These directives appear under per-invocation or per-case `expected:` blocks and configure assertions.

- **`final_state: { ... }`** — exact-equality assertion on the invocation's final state.
- **`execution_order: [<node_name>, ...]`** — ordered list of node names that ran (used for
  deterministic-flow fixtures).
- **`outcome: completed | errored | suspended`** — discriminator on the invoke return type. The
  three values correspond to graph-engine §3 *Invocation outcomes*.
- **`error.category: <category_name>`** — when `outcome: errored`, the error category that surfaced.
  Categories enumerated by graph-engine §4 (`node_exception`, `reducer_error`, `routing_error`,
  `state_validation_error`, `edge_exception`), pipeline-utilities §10.10 (`checkpoint_record_invalid`,
  etc.), sessions §10 (`session_load_failed`, etc.), suspension §9
  (`suspension_persistence_failed`, etc.), and others per-capability.
- **`expected_error: {category: <name>, raised_from: <node_name>}`** — alternative shape used in
  fixtures that expect the entire invocation to fail at construction or first-node entry. Equivalent
  to `outcome: errored` + `error.category:` but more compact.
- **`expected_compile_error: <category>`** — a scalar asserting that **compilation** (not invocation)
  fails with the named graph-engine §2 compile-error category (e.g. `no_declared_entry`,
  `mapping_references_undeclared_field`, `conflicting_projection_forms`, `reducer_configuration_invalid`).
  The adapter compiles the graph definition and asserts a compile-time error of that category is raised
  before any node body runs. (Established by the graph-engine compile-error fixtures; documented here for
  completeness.)
- **`expected_construction_error: {category: <category>}`** — the observer/client-**construction** analogue
  of `expected_compile_error`: a top-level case-level assertion (sibling of `nodes` / `edges` / `expected`)
  that standing up the case's observers/client and running it raises a categorized error of the named
  category at construction or first use. Defined by proposal 0116 for observability §6's mode-(b) payload-leak
  invariant; fixture 158's raise cases use `{category: langfuse_provider_isolation_unavailable}` (an
  observability-native category, observability §6). The per-case audience gate `requires_capability`
  (§5.5) selects which adapter class a case applies to.
- **`expected_compile_warning: <category> | [<category>, ...]`** — asserts that **compilation succeeds**
  while emitting compile-time **warnings** — non-fatal diagnostics, distinct from the `expected_compile_error`
  compile-*failure* assertion. The adapter captures the warnings raised during compilation. Two forms:
  a bare **scalar** asserts the named warning is **among** those emitted (presence only); a **list** asserts
  the **exhaustive** set of warnings emitted (order-insensitive) — so `expected_compile_warning: []` asserts
  **no** compile-time warnings, and `[projection_reducer_round_trip]` asserts exactly that one and no other.
  The list form is what lets a fixture assert a warning MUST **not** fire (catching an over-warning
  implementation). Used for graph-engine §2's `projection_reducer_round_trip` (the reducer round-trip
  warning): a round-trip into a non-round-trip-idempotent **canonical** reducer is MUST-level (asserted with
  the warning present); a SHOULD-level warning an implementation may omit (custom reducers) is not asserted
  by absence, so those cases stay out of the exhaustive-list fixtures.
- **`suspended_state: { ... }`** — when `outcome: suspended`, the state at suspension point per
  suspension §5.
- **`descriptor: {signal_id: <id>, metadata: { ... }} OR {signal_id: <id>, metadata_includes: { ... }}`**
  — when `outcome: suspended`, the signal descriptor on the suspended outcome. The `metadata:`
  variant asserts exact equality; the `metadata_includes:` variant asserts the descriptor's metadata
  contains at least the listed keys (used for fan-out / parallel-branches cases where the engine
  annotates `fan_out_index` / `branch_name` into the bubbled descriptor's metadata).
- **`suspending_node: <node_name>`** — when `outcome: suspended`, the bare node-name field on the
  suspended outcome per suspension §5.
- **`final_state_at_error: { ... }`** — when `outcome: errored`, the state at the point of error.
- **`drain_summary: {timeout_reached: <bool>, undelivered_count: <int> OR undelivered_count_min: <int>}`**
  — assertion on the process-wide drain's return shape (graph-engine §6).
- **`observer_events: {<observer_name>: [<event>, ...]}`** — exact ordered list of events the named
  observer received. Each event is a mapping with at least `phase`, `node_name`, `namespace`, plus
  any optional fields the fixture cares about.
- **`observer_event_invariants: {<predicate_name>: <value>, ...}`** — name-keyed invariant predicates
  the adapter MUST verify against the observer's recorded events. Used for nondeterministic-ordering
  cases (see §7). §5.9 documents common predicate names; the full set is per-fixture and grows per
  proposal. Adapter authors implement predicates as fixtures demand — the originating fixture's
  prose names the predicates and describes their semantics.
- **`otel_spans: {<observer_name>: {name: <span_name>, status: <status>, attributes: { ... }, children: [ ... ]}}`**
  — hierarchical span-tree assertion for OTel observers (observability fixtures only).
- **`langfuse_*: { ... }`** — Langfuse-specific assertion shapes (observability fixtures only).
  Per-shape definitions live in observability fixture headers (per §3.2).
- **`node_drain_summaries: {<node_name>: {timeout_reached: <bool>, undelivered_count: <int>}}`** —
  assertion on the drain summary returned by a node's `invoke_drain_events_for` directive
  (graph-engine §6 *Per-invocation drain*).
- **`node_accumulator_snapshots: {<node_name>: {<observer_name>: [<event>, ...]}}`** — exact
  accumulator snapshot taken at the node's drain-return moment.
- **`node_accumulator_snapshot_invariants: {<node_name>: {<observer_name>: {<predicate_name>: <value>, ...}}}`**
  — invariant predicates against the accumulator snapshot (for nondeterministic-ordering cases).
- **`final_accumulator_state: {<observer_name>: [<event>, ...]}`** — exact accumulator state after
  the invocation completes (post-drain delivery).
- **`saved_record_assertions: { ... }`** — a block of named assertions against the saved checkpoint
  record at first-run end (e.g. before a `resume:`); the adapter checks each listed sub-assertion
  against the persisted record. This proposal formalizes the `fan_out_progress` sub-assertion;
  existing checkpoint-resume fixtures also carry `fan_out_node_in_completed_positions` (bool),
  `completed_positions`, and `parent_states_present` / `parent_states_outermost_first` (subgraph /
  parent-state resume), documented per those fixtures.
  - **`fan_out_progress: {<node_name>: {instance_count: <int>, instances: [<instance_assertion>, ...]}}`**
    — the saved per-instance fan-out progress. Each `<instance_assertion>` is
    `{state: <not_started|in_flight|completed> | state_one_of: [<state>, ...], result: <value>,
    result_is_error: <bool>, completed_inner_positions: [{node_name, attempt_index}, ...]}` (fields
    optional; assert what the fixture cares about). `state_one_of` accommodates dispatch-timing
    nondeterminism (e.g. a sibling `in_flight` vs `not_started` under concurrent execution). Exercises
    pipeline-utilities §10.11.
- **`instances_executed_during_resume: [<int>, ...]`** / **`instances_skipped_during_resume: [<int>, ...]`**
  — appear under a `resume:` block. Assert which fan-out instances re-ran on resume (failed /
  cancelled / not-yet-started) vs. were skipped (completed-and-rolled-forward, including degraded
  instances). Exercises pipeline-utilities §10.11.
- **`metrics: [{instrument: <name>, dimensions: { ... }, value: <number>}, ...]`** — assertion on the
  measurements captured by the §6.9 in-memory metric-capture primitive (observability §11.5). Each
  entry asserts a recorded observation on the named instrument
  (`openarmature.gen_ai.client.token.usage` / `.operation.duration`) carrying the given dimensions;
  `value` asserts the recorded value (used for the fixed-usage mock's token counts) and is omitted for
  duration observations (value not asserted, per observability §11.4). Per proposal 0083 the directive
  also covers the token-budget instruments — `.token_budget.exceeded` (counter; the §11.3 dimensions plus
  the `openarmature.gen_ai.token_budget.kind` dimension, with `value` asserting the per-breach increment
  count per observability §11.2) and `.token_budget.utilization` (histogram; `value` asserts the
  deterministic ratio, plus `kind`, per §11.4). With the observer's
  `enable_metrics` off, no measurements are recorded — a `metrics: []` assertion confirms the opt-in
  gate. See §6.9 for the primitive and the `enable_metrics` configuration.
- **`caught_exception: {category: <category|null>, message: <str>, chain: [{category, message?, carrier}, ...]}`**
  — the failure-isolation event **cause-chain assertion** (pipeline-utilities §6.3). Asserts the structured
  `caught_exception` on a failure-isolation outcome: an ordered `chain` of `{category, message?, carrier}` links
  (outermost→innermost), plus the **derived** top-level `category` / `message` — the `category` is the outermost non-carrier
  link with a non-empty category (else `null`); the `message` is that link's message, or (when no non-carrier
  link has a category) the outermost non-carrier link's message. A **carrier** link is a graph-engine §4
  `node_exception` wrapper (`carrier: true`) whose engine-internal `message` is not pinned (subset match on
  `{carrier, category}` only). Distinct from the §5.1 mock-**input** `cause:` directive (which *constructs* the
  chained error a failure mock raises); this asserts the *resulting* chain.

### 5.9 Invariant assertions

The top-level `invariants:` block (and the per-section `observer_event_invariants`,
`node_accumulator_snapshot_invariants` blocks) name boolean predicates the adapter MUST verify as
additional checks beyond exact-equality assertions. Predicate names are declarative; the adapter MUST
ship logic that interprets each predicate name and runs the corresponding check against the executed
outcome.

Canonical / cross-cutting predicates that span multiple fixtures or capabilities. Adapters MUST
ship logic that interprets each canonical predicate name in this section. Fixture-specific
predicates not listed here are documented in the originating fixture's prose per §3.2
per-directory harness notes; adapters MUST also implement those, but the spec scopes its normative
enumeration to the canonical set below to keep this list maintainable.

- `inner_event_count: <int>` — total events from inner-instance / inner-branch nodes.
- `inner_fan_out_indices_seen: [<int>, ...]` — set of `fan_out_index` values observed.
- `inner_branch_names_seen: [<name>, ...]` — set of `branch_name` values observed.
- `<node_name>_node_events_count: <int>` — events from a specific node.
- `<node_name>_node_fan_out_index_absent: <bool>` — assertion that events from a non-fan-out node
  don't carry `fan_out_index`.
- `inner_event_identities_unique: <bool>` — `(namespace, fan_out_index, branch_name, attempt_index, phase)`
  tuple uniqueness across all inner events.
- `started_followed_by_suspended_in_order: <bool>` — ordering invariant for suspension fixtures.
- `no_completed_event_for_suspending_node: <bool>` — verifies the mutually-exclusive-terminal-phases
  rule per graph-engine §6.
- `drain_returned_within_timeout: <bool>` — verifies the drain timeout discipline.
- `workers_not_cancelled_on_per_invocation_drain_timeout: <bool>` — verifies the per-invocation
  drain's no-worker-cancellation rule per graph-engine §6 *Per-invocation drain*.

New proposals that add canonical predicates extend this section. Fixture-specific predicates added
in the course of a per-fixture exercise stay in the fixture's prose; the canonical promotion
happens when a predicate recurs across multiple fixtures or capabilities.

### 5.10 Value matchers

Several assertion shapes check a field's value by rule rather than against a hard-coded literal —
either matching it against a pattern, or deriving / injecting the expected value. The vocabulary
spans three idioms; adapters MUST interpret each uniformly so a fixture means the same thing across
implementations.

**Inline value-tokens** — a token written in an `expected:` mapping where a literal scalar value
would go; the adapter matches the runtime field value against the token rather than comparing it to a
literal. They are of two kinds — **format matchers** (match any value of a given shape) and
**first-occurrence-binding tokens** (cross-reference an opaque id within a case):

- **`<uuid>`** — (format) matches any canonical UUIDv4.
- **`<uuid-hex>`** — (format) matches a 32-character lowercase hex string — a UUID's dashes-stripped
  hex form (e.g. a derived Langfuse `trace.id`). A disambiguating suffix MAY be appended
  (`<uuid-hex-1>`, `<uuid-hex-5-a>`) to label distinct expected ids within a case for readability;
  each labeled form independently matches any value of the format (the suffix does not assert
  cross-equality).
- **`<any-string>`** — (format) matches any **non-empty** string. The empty string `""` does NOT match.
- **`<name_X>` first-occurrence-binding tokens** — an **opaque** id (no fixed format) whose `<name>`
  identifies the id being cross-referenced and whose suffix distinguishes independent bindings. It
  binds to the value at its first occurrence within a case; every later occurrence of the **exact
  same token string** MUST equal that bound value, and distinct token strings bind independently.
  Used for id consistency within one case. The concrete `<name>` set is **suite-defined**, documented
  in the suite's fixture-header notes (the §3.2 per-directory mechanism): the observability suite uses
  `<trace_id_X>` (`<trace_id_parent>`, `<trace_id_instance_0>`, …), `<corr_id_N>`, `<span_id_X>`, and
  `<invocation_id_X>`.

**Assertion sub-keys** — appear as *keys inside a field's assertion mapping*, not as a bare value
(used where a field's expected value is a mapping of assertions rather than a scalar):

- **`non_empty_string: true`** — the field is a non-empty string. Semantically identical to
  `<any-string>`; it is the sub-key spelling for assertion-mapping contexts.
- **`harness_parameterized: <name>`** — the field equals the harness-injected parameter named
  `<name>` (e.g. the implementation's own `implementation_name`). This is an **equality check against
  an injected value**, not a wildcard.

**Exact-value + named derivation invariant** — not a matcher: an exact expected value derived from
inputs by a documented rule (e.g. a Langfuse `trace.id` equal to a caller UUID's 32-character
dashes-stripped hex), paired with a named invariant predicate (per §5.9, e.g.
`langfuse_trace_id_is_uuid_hex_dashes_stripped`). Recorded here as the distinct third idiom so it is
not conflated with the wildcard matchers above.

This enumeration is the current authoritative set, not a frozen one — future proposals extend §5.10
the same way they extend the rest of §5. The observability fixture suite's per-directory header
comment (per §3.2) is a navigational example of the inline tokens; §5.10 is their normative home.

### 5.11 Provider call-retry directives (llm-provider §7.1)

llm-provider call fixtures configure a `complete()` call under `call:` and mock the provider's
per-attempt responses under `mock_provider.responses:` (an ordered list consumed one per attempt, in the
order attempts are issued; a fixture MAY supply more entries than the loop consumes — e.g. to prove it stops
early). This section documents the directives supporting llm-provider §7.1's adaptive call-level retry —
the two `call.retry` adaptive fields (`per_attempt_override`, `reask`) plus the `expected.wire_requests` and
`attributes_absent` assertion surfaces. It also carries **`attribute_truncation`**, which asserts
observability §5.5.5's per-value byte cap on a span attribute. That directive is not a retry directive; it
sits here because it is a span-entry assertion and belongs beside `attributes_absent`, its nearest
structural sibling.

**Call configuration.** Beyond the pipeline-utilities §6.1 four-field record, the `call.retry`
mapping accepts the two llm-provider adaptive fields (llm-provider §7.1):

- **`per_attempt_override: [<RuntimeConfig partial>, ...]`** — the retry override schedule. Entry
  *i* applies to retry *i* (attempt *i+1*); attempt 0 uses the base `config` unchanged. Each entry is
  a `RuntimeConfig` (llm-provider §6) partial merged onto the base for that attempt.
- **`reask: {template: <str>}`** — a declarative stand-in for the caller's reask builder (a real
  builder is a callable, which a data fixture cannot hold). The template is a string with
  `{output_content}` / `{error_message}` placeholders; on a `structured_output_invalid` attempt the
  adapter renders it with that error's 0082 surface (llm-provider §7) and wires the result as the
  message the builder returns. The adapter MUST NOT contribute any text beyond the rendered template
  — the fixture's purpose is to prove OA authors no prompt of its own (llm-provider §7.1).

**Per-attempt outbound-request assertion.** Under `expected:`, **`wire_requests: [<entry>, ...]`** is
an ordered list — one entry per attempt the retry loop issued — asserting that attempt's outbound
provider request. Each entry asserts only the fields it names (`{}` asserts nothing for that
attempt):

- **`sampling: { ... }`** — the effective sampling fields on the attempt's wire request (e.g.
  `{temperature: 0.3}`), for verifying `per_attempt_override`.
- **`appended_messages: [<msg>, ...]`** — the messages the loop appended to the working transcript
  **after** the caller's original messages, in order — for verifying reask (llm-provider §7.1). A
  reask retry appends the pair `{role: assistant, content: <the model's raw output>}` then
  `{role: user, content: <the builder's rendered correction>}`, accumulating across retries. Each
  `<msg>` asserts either `{role: <user|assistant>, content: <str>}` (exact — proving the appended
  text is exactly the model's output / the builder's rendering and nothing OA-authored) or
  `{role: <role>, content_contains: [<str>, ...]}` (substring set — used when the reask template
  interpolates the implementation-defined `{error_message}`, where exact equality is not portable;
  assert the literal template text and the verbatim `{output_content}` this way). An empty list `[]`
  asserts **no** appended messages (attempt 0, and reask-off cases).

Every reachable retry-loop attempt is **append-only** (a reask retry appends an `assistant`/`user`
pair; a transient retry appends nothing), so `appended_messages` expresses every case. This generalizes
the single-request `expected_wire_request` convention (provider wire-mapping fixtures) to the per-attempt
retry-loop case.

**Span attribute assertions.** The per-attempt `openarmature.llm.retry_reason` span attribute
(llm-provider §7.1) is asserted via the existing `expected.llm_spans[*].attributes` shape on retry
attempts. Because those attribute assertions are a subset match, asserting an attribute is **absent**
— e.g. that attempt 0 carries no `retry_reason` — needs its own directive: a span entry MAY carry
**`attributes_absent: [<key>, ...]`**, asserting none of the listed attribute keys are present on
that span.

A span entry MAY also carry **`attribute_truncation: {<attribute_key>: {max_bytes: <int>, marker_pattern:
<str>, utf8_valid: <bool>, prefix_of_full_serialization: <bool>}}`**, asserting that the named attribute was
truncated per observability §5.5.5. All four sub-keys are independent assertions and an entry MAY carry any
subset:

- `max_bytes` — the attribute's UTF-8 byte length is at most this value.
- `marker_pattern` — the value ends with a string matching this pattern, the §5.5.5 truncation marker.
- `utf8_valid` — the value is valid UTF-8, gating §5.5.5's code-point-boundary backtracking. A
  fixture asserting this MUST synthesize the value from a **multi-byte** character, since every byte
  offset in an all-ASCII value is already a code-point boundary and the assertion cannot fail.
- `prefix_of_full_serialization` — the value up to the marker is a byte-exact prefix of what the untruncated
  serialization would have been, gating that truncation cut rather than re-encoded.

Together they distinguish a correctly truncated value from one that is merely short: an implementation that
emitted a shortened value without the marker, or that split a multi-byte sequence, or that re-serialized
rather than cut, fails a different sub-key in each case.

An adapter **MUST** honor the directive when present, and an entry naming an attribute asserts that the
attribute is **present** as well as truncated: an absent attribute fails the entry rather than vacuously
satisfying it. An entry **MUST** carry at least one sub-key, since `{<key>: {}}` would assert nothing. As
with `otel_observer` (§5.5), an adapter that silently skips the directive produces the same observable
result as a case that never carried it, which makes the case vacuous rather than failing it.

### 5.12 Provider structured-output error assertion (llm-provider §7)

llm-provider call fixtures assert a raised `structured_output_invalid` error (llm-provider §7, its
diagnostics surface per 0082) via an `expected.raises` block with `category: structured_output_invalid`
and a `carries` mapping. The `carries` block asserts the error's exposed fields. The 0016 structured-output
fixtures (022 / 023) and the 0095 reask fixtures (063 / 064) use them — the other 0095 fixtures are
success-path and raise nothing.

**Key naming.** These keys follow the general raised-error `carries` convention (§5.13); this block is the
llm-provider `structured_output_invalid` **instance** of it. Each key names an llm-provider §7 error field,
with the flavor suffixes (`_present` / `_mentions`) and the mapping-valued subset match defined generally in
§5.13. The llm-provider keys:

- **`response_schema_present: <bool>`** — the error exposes the requested `response_schema` (llm-provider §5 / §7).
- **`output_content: <str>`** — exact-equality on the error's `output_content` (llm-provider §7): the
  verbatim content the model produced that failed to parse or validate.
- **`error_message_present: <bool>`** — the error's `error_message` (llm-provider §7) is present. Used when
  the wording is not asserted (e.g. a parse failure with no specific field to name).
- **`error_message_mentions: <str>`** — a substring the error's `error_message` MUST contain (e.g. the
  failing field name). A contains-check, since the exact wording is implementation-defined
  (llm-provider §7).
- **`finish_reason: <str>`** — the error's normalized `finish_reason` (llm-provider §6), mandated on
  `structured_output_invalid` by 0082.
- **`usage: { ... }`** — the error's token `usage`: the llm-provider §6 usage record (the baseline counters
  `prompt_tokens` / `completion_tokens` / `total_tokens`, plus any optional §6 fields such as the cache
  counters `cached_tokens` / `cache_creation_tokens`), mandated on `structured_output_invalid` by 0082.
  Asserted as a **subset match** per §5.13 — a fixture naming only the baseline counters
  does not fail an implementation that also reports the optional ones.

### 5.13 Raised-error field assertion (`carries`)

A `carries` block appears under a raised-error assertion (`expected.raises` / `expected_error`) and asserts
the fields the raised error exposes. It is used across capabilities — the llm-provider `structured_output_invalid`
block (§5.12), and the state-migration (pipeline-utilities §10.10 / sessions) and prompt render
(prompt-management §11) error fixtures, among others. This section defines the convention for all of them;
§5.12 is the llm-provider instance.

**Key naming.** A `carries` key **MUST** name a field the raised error's own capability spec defines the error
exposes, plus an optional suffix naming the assertion flavor:

- a **bare field name** — **exact-equality** on that field. When the field is a **mapping**, the assertion is a
  **subset match**: every key the fixture names MUST match, and keys it does not name are ignored (an
  implementation MAY expose additional optional fields without failing the assertion) — the same convention
  §5.11 applies to span `attributes`.
- the **`_present`** suffix — asserts the field's **presence**, not its value: `true` asserts the field is
  present (non-null); `false` asserts it is absent (null).
- the **`_mentions`** suffix — the field's value **contains** the given substring (used where the exact wording
  is implementation-defined).

The suffix, when present, **MUST** be one of `_present` / `_mentions` — the flavor set is **closed**, and a new
flavor requires a proposal.

A key **MUST NOT** coin a stem that names no field the error exposes: the vocabulary is derivable from the
error's capability spec, not invented at the fixture. And an error field name **MUST NOT** end in a recognized
flavor suffix, so a key parses unambiguously to exactly one (field, flavor) pair. A field name **MAY** end in
other tokens — `registered_migrations_count` (pipeline-utilities §10.10) is a **bare field name** (`_count` is
not a flavor), asserted by exact-equality, not a count-flavor on `registered_migrations`.

The sibling `cause` directive (`cause: { exception_type: … }`, used by the migration-failed fixtures) is a
**separate** directive, not a `carries` flavor; it is out of scope here.

### 5.14 Provider batch-chunking cap (`chunk_size`)

An embedding- or rerank-provider construction block (`tei_embedding_provider`, `openai_embedding_provider`,
`cohere_embedding_provider`, `tei_rerank_provider`, …) **MAY** carry a `chunk_size: <int>` field. It sets the
**per-call cap** the mapping uses for chunk-and-stitch in that fixture — retrieval-provider §8 *Batch chunking*
for embedding **inputs**, or the §8.1 mandatory rerank chunk-and-stitch for rerank **documents**: the largest
number of items the mapping sends in a single provider request, above which it chunks-and-stitches. An adapter
**MUST** honor `chunk_size` as that cap for the constructed provider, whatever the mapping.

The field has two roles, depending on whether the mapping's real per-call cap is configurable:

- **A real construction cap** for a mapping whose per-call limit is genuinely configurable — TEI's
  `max-client-batch-size` (§8.1), which governs both TEI `/embed` (fixture 038, `chunk_size: 2`) and TEI
  `/rerank` (the rerank chunk-and-stitch fixture 015, `chunk_size: 4`; fixtures 014 / 016 set a larger
  `chunk_size: 32` their document counts do not exceed). Here `chunk_size` *is* that config.
- **A test-only cap override** for a mapping whose per-call limit is a **fixed vendor constant** — OpenAI's
  2048 inputs (§8.3), Cohere's 96 (§8.4). These caps are not construction-configurable in the real mapping;
  `chunk_size` overrides the fixed cap **for the conformance run only**, so a fixture can drive the chunking
  path with a small, reviewable input body instead of an impractical over-cap one (fixture 043 uses
  `chunk_size: 2` in place of §8.3's fixed 2048 — a faithful over-cap body would need 2049 inputs). The real
  mapping's fixed cap is unchanged: when `chunk_size` is **absent**, the mapping applies its own documented cap
  (a fixed-cap mapping small enough to exercise with a real over-cap body needs no override — fixture 037
  drives Cohere's 96 with a real 100-input body).

An adapter that ignores `chunk_size` on a fixed-cap mapping sends the fixture's small input list in one
under-cap request and fails the fixture's expected chunk count — so honoring the field is required to pass, not
optional. This directive is what lets a small fixture exercise a large fixed cap; without it, cross-impl
coverage of a fixed-cap mapping's chunking path would be unreachable.

### 5.15 Retrieval-provider directives

The retrieval-provider fixtures (embedding + rerank) use a construction / call / mock / wire-assertion
vocabulary that parallels the llm-provider fixture directives; this subsection gives it a normative home. Some
retrieval assertions reuse directives documented elsewhere — `expected_error: {category, raised_from}` (§5.8),
the `chunk_size` provider cap (§5.14), and the `typed_observers` / `contains_event` typed-event assertions
(§5.5); those are cross-referenced, not redefined here.

**Provider construction blocks** — suite-level, one per bound provider; the block name selects the vendor and
its fields are the §8.x *Construction* parameters:

- **`tei_embedding_provider: {base_url, model, input_type_prompt_map, query_prefix?, document_prefix?}`** — a
  bound TEI `EmbeddingProvider` (retrieval-provider §8.1). `input_type_prompt_map` maps OA `input_type` → TEI
  `prompt_name` (e.g. `{query: "query", document: "passage"}`); the optional prefixes are the client-side
  fallback. TEI is a per-deployment host, so there is no `api_key`.
- **`tei_rerank_provider: {base_url, model, chunk_size}`** — a bound TEI `RerankProvider` (§8.1). `chunk_size`
  is the rerank client-batch chunk size (default 32; see §5.14).
- **`jina_embedding_provider` / `jina_rerank_provider: {base_url, model, api_key}`** — a bound Jina provider
  (§8.2). `api_key` is sent as `Authorization: Bearer <key>`; `base_url` is origin-only (the mapping appends the
  path, e.g. `/v1/rerank`).
- **`openai_embedding_provider: {base_url, model, api_key, query_prefix?, document_prefix?}`** — a bound
  OpenAI-compatible `EmbeddingProvider` (§8.3). `api_key` as `Authorization: Bearer <key>`; `base_url` defaults
  to the OpenAI origin and is overridable for any compatible backend; the optional prefixes are off by default
  (asymmetric-model client-side prefixing). MAY carry the §5.14 `chunk_size` test-only cap override.
- **`cohere_embedding_provider` / `cohere_rerank_provider: {base_url, model, api_key}`** — a bound Cohere
  provider (§8.4), one instance per endpoint sharing the hosted endpoint.

**`mapping: <name>`** — a suite-level scalar selecting the §8.x vendor wire mapping under test: `tei` (§8.1),
`jina` (§8.2), `openai` (§8.3), `cohere` (§8.4). Under a `mapping:`, the fixture's mocks and wire assertions use
that vendor's **real** wire shapes (the request the mapping MUST send, the response it MUST consume). **Absent**,
the harness-internal stand-in shape used by the pre-wire-mapping fixtures applies.

**Call directives** (node-level):

- **`calls_embed: {input: [str], config?: {...}, stores_response_in: <field>}`** — the node calls the bound
  `EmbeddingProvider.embed()` with `input` (and optional `config` — `dimensions`, `input_type`, and the §6
  `extras` bag) and stores the returned `EmbeddingResponse` in the named state field.
- **`calls_rerank: {query: str, documents: [str], top_k?: int, config?: {...}, model?: <id>,
  stores_response_in: <field>}`** — the node calls `RerankProvider.rerank()` and stores the `RerankResponse`;
  `top_k`, `config` (`return_documents`, and the `extras` bag), and `model` are optional.

**Response mocks** (suite-level lists; one `{status, body?}` entry dispatched per call in arrival order):

- **`mock_embedding: [{status, body?}, ...]`** / **`mock_rerank: [{status, body?}, ...]`** — the mock provider's
  responses; `status` is required and `body` is optional. When present, `body` is the vendor's real wire shape
  under a `mapping:` (e.g. OpenAI `{object, data, model, usage}`, TEI's bare vector array), or the
  harness-internal stand-in absent a `mapping:`. A non-2xx `status` drives the wire-error path (mapped to a §7
  `error_category`); such an entry MAY omit `body` and supply literal error detail via `raises` instead (as in
  fixtures 150 / 151). A **non-2xx** mock entry MAY carry a
  **`raises: {error_type, message}`** sub-directive — the retrieval analogue of the tool path's
  `mock_tool: {raises: {error_type, message}}` — that overrides only the exception's **literal** `error_type` /
  `error_message` (the mock `message` maps to the event's `error_message`) **while the `status` still fixes the
  deterministic §7 `error_category`**, so a fixture can assert those two fields literally rather than by format.
  `raises` is not used without a `status` (retrieval has no other category source).

  In place of a literal `message`, a `raises` entry MAY carry **`message_repeat: {char: <str>, bytes: <int>}`**,
  which synthesizes an exception message by repeating `char` until adding another repetition would exceed
  `bytes`. The result is the **largest whole number of repetitions whose UTF-8 encoding is at most `bytes`**:
  never longer than `bytes`, possibly shorter when `char` is multi-byte, and always valid UTF-8. A fixture
  needing an exact byte count uses a single-byte `char`. The rule is normative rather than incidental,
  because these directives feed the §5.5.5 truncation contract and an off-by-one at a sequence boundary is
  the precise defect `utf8_valid` exists to catch. It exists so a
  fixture can induce an **oversized** message without carrying one inline, the same reason `content_repeat`
  (§5.1) exists for message content. `message` and `message_repeat` are mutually exclusive on one entry; an
  adapter **MUST** reject an entry carrying both with **`fixture_schema_invalid`** (§9), since the intended
  message would be ambiguous.

**Wire-request assertions** (case-level):

- **`expected_wire_request: {...}`** — the request body the mapping MUST produce. The harness captures the
  outbound body and compares **key-by-key** (key order not significant); a field **absent** from
  `expected_wire_request` MUST be absent on the wire. For a chunk-and-stitch call it is a **list** of bodies,
  one per request in arrival order.
- **`expected_wire_request_count: <int>`** — the number of outbound requests the call MUST issue (pins the
  chunk count).
- **`expected_wire_request_absent_keys: [<key>, ...]`** — each named key MUST be **absent** from the outbound
  body (an explicit, positive absence assertion, complementing the absent-field rule above).
- **`expected_wire_headers: {<name>: <value>, ...}`** — a **subset** match: each listed HTTP request header MUST
  be present with the given value (other headers MAY be present; header names case-insensitive). Primary use:
  `Authorization: "Bearer <api_key>"` from the provider block's `api_key`.

**Pre-send-reject invariants** (under `expected.invariants`):

- **`no_embed_request_issued: true`** / **`no_rerank_request_issued: true`** — assert that **no** `/embed`
  (resp. `/rerank`) wire request was issued: the §7 error category was raised client-side at the pre-send
  validation layer. These pair with the pre-send-reject fixture convention — **no** `mock_embedding` /
  `mock_rerank` entry and **no** `expected_wire_request` (nothing leaves, so nothing to mock), while
  `expected_error` (§5.8) still asserts the category and `raised_from` node.

## 6. Harness primitives

Adapters MUST provide the following runtime primitives to satisfy directives in §5.

### 6.1 In-memory observers

- **`record` observer.** Maintains a per-observer FIFO list of every event received; exposes a read
  API the adapter uses to fulfill `observer_events` / `observer_event_invariants` assertions.
- **`accumulate` observer.** Maintains per-`invocation_id` buckets keyed by the event's
  `invocation_id`; exposes a read API consumed by `invoke_drain_events_for`'s `snapshot_observer`
  parameter and by `node_accumulator_snapshots` / `final_accumulator_state` assertions.
- **`raise` observer.** Raises on every event received. Validates the graph-engine §6 observer-error
  isolation contract (raises do not interrupt the graph or affect other observers).
- **Slow / paced behavior.** Any observer behavior MAY be configured with `sleep_ms_per_event` to
  simulate slow downstream observers (used in drain-timeout fixtures); the adapter's implementation
  sleeps in the observer's dispatch path before processing each event.

### 6.2 In-memory persistence backends

- **In-memory SessionStore.** Single-process, ephemeral, satisfying the sessions §5.1–§5.4
  protocol. The adapter MUST ship this at minimum; production SessionStore backends are
  out-of-scope sibling packages.
- **In-memory Checkpointer.** Single-process, ephemeral, satisfying the pipeline-utilities
  §10.1 protocol. The adapter MUST ship this at minimum.
- **Shared persistence per pipeline-utilities §10.15.** The adapter MAY use one backend store for
  both checkpoint records and paused-invocation records with a discriminator field, or two separate
  stores. Implementation choice; the spec requires only that the discrimination is correct (resume
  via `invoke(resume_invocation=...)` per §10.4 loads a checkpoint record; resume via
  `invoke(resume_invocation=..., signal_payload=...)` per suspension §7 loads a paused-invocation
  record).

### 6.3 OTel collector capture

Observability fixtures exercise OTel span emission. The adapter MUST provide an in-memory OTel
`SpanExporter` + private `TracerProvider` (per observability §6 isolation) for the observability
fixture suite. The exporter records every emitted span for structured assertion via the `otel_spans`
expected-outcome shape.

The OTel-collector-capture primitive is invoked automatically for fixtures under
`spec/observability/conformance/` per the per-directory harness contract in those fixtures' header
comments. The adapter MUST honor that contract when running observability fixtures.

### 6.4 Langfuse mock

Observability fixtures that exercise Langfuse mapping rely on an in-memory Langfuse client wrapper
that records emitted traces and observations for structured assertion. Same per-directory harness
contract pattern as the OTel collector.

Fixtures exercising **provider isolation** (proposal 0115, the `langfuse_client` directive) use a
**provider-faithful** variant of this fake: it records observation content as above **and** emits those
observations as OTel spans through its bound `TracerProvider` (as a Langfuse v4 client does), so an OTel
exporter on that provider observes any that reach it. Its emitted spans carry the `langfuse.observation.*`
attribute namespace (as a Langfuse v4 client does) — the identity §5.5's `no_langfuse_observations_on_global`
/ `no_langfuse_observations_on_private` / `langfuse_observations_on_global` assertions filter on. One object
serves both — the content / non-vacuity assertions read the recorded side, those leak assertions read the
provider side. It carries no network dependency and stays deterministic; for `mode: credentials` the adapter injects
it into the implementation's construct-from-credentials path, and for `mode: supplied` the harness
constructs it on the configured provider and passes it in.

Proposal 0116 extends this fake for the payload-leak invariant's arms. It **MUST** honor the SDK's
**per-credential singleton**: the first construction for a credential binds and records the supplied
`TracerProvider`; a later construction for the same credential returns the first client and ignores a newly
supplied provider (a plain priming construction with no provider supplied binds the global provider). The
`preexisting_same_key_client` directive drives this by constructing a same-credential client before the
implementation does, so the implementation's construction is handed the primed client on the global
provider — the discarded-isolation path. The fake **MUST** also **expose its bound provider**, so an adapter
that declares `langfuse_bound_provider_detection` can establish the binding deterministically in-harness (an
adapter that does not declare it exercises the suppress arm instead — the fake exposing the accessor does not
itself make detection portable; the adapter's declared capability selects the arm). Finally, the fake **MUST**
distinguish a **payload-bearing** observation from a **payload-free** one. Per proposal 0117 a
**payload-bearing** observation carries any harvested payload — provider `input` / `output`
(prompt/completion, embedding / tool / rerank I/O), a Trace-level state `input` / `output` (raw state or a
`trace_input_from_state` / `trace_output_from_state` hook value), **or** a failed observation's
`error_message`; a **payload-free** observation is the §8.4.1 minimal stub or a failed observation carrying
only its classifications. Proposal 0118 narrowed this to the **message**: a failed observation's `error_type`
is a classification token, not harvested text, so it does **not** make an observation payload-bearing (it is
also ungated by `disable_provider_payload`, observability §5.5.4). So the raise / suppress / omission cases can
assert that no *payload-bearing* observation reached the global provider while a stub, or an observation
carrying only `error_type` and its category, still did.

### 6.5 Suspend / resume wiring

The `suspend_with_descriptor` directive on a node MUST compile (at adapter parse time) to a real
synthetic node body that calls the implementation's real `suspend()` operation per suspension §3 —
not a simulation or mock. Likewise, an `invocations[]` entry with `resume_invocation` +
`signal_payload` MUST translate to a real `invoke(resume_invocation=..., signal_payload=...)` call
per suspension §7.

The adapter MUST handle suspension-resume's reused-`invocation_id` semantic (per suspension §7 + the
graph-engine §3 *Invocation entry surface* rule) — the resumed invocation carries the same
`invocation_id` as the suspended one. Placeholder resolution (`<from previous suspended outcome>`)
uses the suspended outcome's `invocation_id` field, not the caller's input.

### 6.6 Drain wiring

The `drain` directive in an `invoke:` block translates to a real call to the implementation's
`drain()` operation per graph-engine §6 (process-wide drain). The
`invoke_drain_events_for` directive on a node translates to a real call to the implementation's
`drain_events_for()` operation per graph-engine §6 *Per-invocation drain*. Neither is simulated; the
adapter exercises the real primitive and asserts on the returned summary.

### 6.7 Middleware wiring

The `wrap_with_middleware` directive on a node MUST compile to a real middleware that the
implementation's middleware system runs around the wrapped node. The standard pre / post logging
behavior (`pre_log` / `post_log` markers) is recorded into a per-fixture middleware-log accumulator
the adapter exposes for assertion.

The `pre_next_calls_suspend_with_descriptor` middleware-config variant MUST cause the middleware's
pre-`next()` block to call `suspend()` from within itself (rather than the wrapped node doing so).
This intentionally triggers `suspension_in_unsupported_context` per suspension §8.4; the fixture
asserts on the error category, not on any successful suspension.

### 6.8 Caching prompt backend

Prompt-management fixtures that exercise the per-fetch `cache_ttl_seconds` control (prompt-management
§5 / §6) rely on a **caching prompt-backend** primitive: an in-memory `PromptBackend` that caches
fetched templates by `(name, label)`, counts **source reads** (fetches that reach its backing store
rather than the cache), and honors `cache_ttl_seconds` per the prompt-management §5 contract:

- **`None` (default)** — serve a cached entry when present; read the source only on a miss.
- **`0`** — bypass the cache: every fetch is a source read.
- **`N > 0`** — serve a cached entry younger than `N` seconds; otherwise read the source. Age is
  measured against a **controllable clock** the adapter exposes, so a fixture can advance time
  deterministically (no wall-clock dependence).

The primitive exposes the per-`(name, label)` source-read count for assertion (the
`source_read_count` expected-outcome shape) and an `advance_clock` operation (advance the
controllable clock by a fixed number of seconds between `calls`). The adapter MUST ship this caching
backend in addition to the non-caching (preloaded in-memory mock) prompt backend the existing
prompt-management fixtures use — which reads its source on every fetch and therefore treats
`cache_ttl_seconds` as a no-op, as do the filesystem / in-memory backends prompt-management §5 describes.

**Fixture shapes.** The caching backend and its assertions are spelled in the prompt-management
fixture schema as:

- `backends[].caching: true` — marks a backend as the caching prompt backend (vs. the default
  preloaded mock backend that reads its source on every fetch).
- `cache_ttl_seconds: <int>` on a `fetch` `call` — passed to that backend's `fetch` per the prompt-management §5
  contract.
- a `calls` entry `{target: {backend: <name>}, operation: advance_clock, seconds: <int>}` —
  advances the named caching backend's controllable clock by `<int>` seconds; it is a `calls` entry
  like any other and carries a `target`.
- fixture-level `expected_backend_state: {<backend>: {source_read_count: <int>}}` — asserts the
  named backend's cumulative source-read count after all `calls` have run.
- a fixture-level `manager: {default_cache_ttl_seconds: <int>}` block (proposal 0086) — constructs a
  `PromptManager` over the declared `backends` (in order) with the given construction-time default
  (prompt-management §6); absent means no manager default.
- a `calls` entry `target: {manager: true}` — routes the fetch through that manager, exercising the
  §6 cache-TTL precedence chain (explicit per-call value > manager default > backend) rather than
  targeting a backend directly; a per-call `cache_ttl_seconds` on the call overrides the manager
  default, and omitting it selects the default.

### 6.9 Metric capture

observability §11 *Metrics* fixtures assert the measurements an observer records when `enable_metrics`
is on. The adapter MUST provide an in-memory **metric-capture** primitive — an in-memory OTel
`MetricReader` attached to the `MeterProvider` the metrics-emitting observer uses, sibling to the §6.3
OTel collector capture for spans — that records every observation (instrument name, value, dimensions)
for assertion.

- A case enables metrics via an observer-level `enable_metrics: <bool>` flag (observability §11.1,
  default off), configured on the in-memory observer (§6.1) the same way the span opt-out flags are.
- After the case runs, the captured observations are asserted via the §5.8 `metrics:` expected-outcome
  directive — instrument name + dimensions for every observation, plus the recorded value for the
  token-usage instrument (the mock returns fixed usage); duration observations assert presence +
  dimensions only, not the value (observability §11.4); and (proposal 0083) the token-budget instruments
  — the `token_budget.exceeded` counter (dimensions + `kind` + the per-breach increment-count `value`)
  and the `token_budget.utilization` histogram (deterministic ratio value + `kind`).
- A case with `enable_metrics: false` (or absent) records no measurements; a `metrics: []` assertion
  confirms the opt-in gate.

## 7. Nondeterminism handling

Several execution-ordering aspects are observable but not uniquely determined by the spec.
Fixtures MUST assert on invariants (counts, identity-tuple uniqueness, attribute presence) rather than
exact event sequences in these cases.

**Cases where exact ordering is not determined:**

- **Fan-out instance scheduling.** Per graph-engine §3's concurrency exception, multiple fan-out
  instances MAY execute concurrently. Their per-instance event sequences interleave; the order of
  events across sibling instances is observable but not deterministic.
- **Parallel-branches branch scheduling.** Same rule applies: branches MAY execute concurrently;
  events from different branches interleave nondeterministically.
- **Observer event dispatch within one phase.** Per graph-engine §6, observer event delivery is
  async with respect to graph execution. Events for the SAME `(node_name, phase, namespace,
  fan_out_index, branch_name, attempt_index)` tuple are dispatched in deterministic order (FIFO from
  the deliver queue), but interleaving between different sources within one phase is observable but
  not deterministic.

**The assertion pattern.** Fixtures touching these surfaces use `observer_event_invariants:` (rather
than `observer_events:`) with predicates like:

```yaml
observer_event_invariants:
  inner_event_count: 6                    # 3 instances × 2 phases
  inner_fan_out_indices_seen: [0, 1, 2]   # set, not list
  inner_event_identities_unique: true     # tuple-uniqueness invariant
```

The adapter MUST honor invariant predicates by name (per §5.9). Adapters MUST NOT impose an exact
ordering on events that the spec doesn't determine.

Within-node directive order is, by contrast, **deterministic**: a node's sibling directives execute
in fixture-document order (§8.3). The nondeterminism above is across *sources* (sibling fan-out
instances, parallel branches, distinct event sources within a phase), not within a single node's
directive list.

## 8. Adapter responsibility

A language adapter ships in its implementation's repository (e.g., openarmature-python,
openarmature-typescript) as test infrastructure. To satisfy this capability spec, the adapter MUST:

### 8.1 Discovery

Walk `spec/<capability>/conformance/` directories for `*.yaml` files. Each file is one fixture.
Adapters MAY filter by capability or fixture name; the default MUST be "discover and run all
fixtures."

### 8.2 Parsing

Translate each fixture's YAML into native graph-construction calls in the host language. Parsing
MUST be lossless against the **recognized vocabulary** (§5 *Definition homes*); unknown directives
MUST raise `fixture_directive_unknown` (per §9) rather than being silently skipped or treated as
defaults.
Lossless parsing preserves the document order of a node's directives (an order-preserving load), so
§8.3's execution-order rule has a well-defined order to honor.

### 8.3 Execution

Construct the graph, instantiate harness primitives per §6, run each invocation against the
implementation's real runtime. The adapter MUST NOT simulate any spec-defined behavior — every
construct the fixture exercises (suspend, drain, middleware, fan-out, parallel-branches, sessions,
checkpointing, observability emission) MUST be the real implementation primitive.

**Directive execution order.** When a node carries more than one directive (sibling keys under
`nodes.<node_name>:`), the adapter MUST execute them in **document order** — the order the directive
keys appear under `nodes.<node_name>:` (mapping insertion order, **not** sorted-by-key). Directives
whose effects compose order-dependently — e.g. `augment_metadata` / `augment_metadata_from_field`
(writes) and `capture_invocation_metadata_into` (a point-in-time read), per observability §3.4 —
therefore produce a deterministic result fixed by their document order. (`update` /
`update_from_field` partial-update merges are likewise applied in document order.)

### 8.4 Assertion

Verify each `expected:` block via the host language's idiomatic test framework. The adapter's
assertion layer translates spec-defined assertion shapes (per §5.8) into host-language test
assertions. Failures surface through the test runner.

### 8.5 Version pinning

The adapter declares which conformance-adapter version it targets via the implementation's package
metadata (per the convention each implementation already uses for `openarmature_spec_version` —
e.g., `openarmature-python` declares it in `pyproject.toml`'s
`[tool.openarmature]` section). When a fixture declares a `conformance_version:` higher than the
adapter targets, the adapter MUST raise `fixture_version_unsupported` per §4.4 + §9.

The conformance-adapter version is NOT pinned independently of the spec version — implementations
MAY target a spec version `vX.Y.Z` which implicitly fixes the conformance-adapter version to
whatever this capability shipped at as of `vX.Y.Z`.

## 9. Errors

Canonical error categories introduced by this capability. Adapters MUST raise these (not silently
recover or default) when the corresponding condition fires:

- **`fixture_directive_unknown`** — an adapter encountered a directive in fixture YAML that it
  does not recognize. Silent skipping would mask conformance gaps; the adapter MUST raise and
  surface the unknown directive name + the fixture location.
- **`fixture_schema_invalid`** — a fixture's YAML is structurally broken (required directive
  missing, malformed type for a known directive, invalid YAML syntax), **or** a co-occurrence
  constraint between known directives is violated (two mutually exclusive directives supplied on
  one entry, such as `message` with `message_repeat` or `content` with `content_repeat`). The
  adapter MUST raise rather than infer defaults or pick one of the two.
- **`fixture_version_unsupported`** — a fixture declares `conformance_version > adapter_version`.
  The adapter MUST raise per §4.4 + §8.5.
- **`harness_primitive_missing`** — a fixture references a harness primitive (named SessionStore
  backend, named Checkpointer backend, etc.) the adapter doesn't provide. The adapter MUST raise
  rather than silently skip the fixture.

Adapters MAY define additional adapter-layer error categories for their own internal use; the spec
defines the minimum set that MUST surface uniformly across implementations.

## 10. Determinism

The adapter itself is a control-flow layer; it does NOT perturb the determinism of the implementation
it exercises. Two adapter runs over the same fixture against the same implementation MUST produce the
same outcome (modulo nondeterminism that the implementation itself permits per §7, e.g., fan-out
instance scheduling).

This mirrors the same control-flow-layer-doesn't-perturb-determinism rule the harness contract
establishes per proposal 0022 when its capability spec lands.

## 11. Cross-spec touchpoints

Every other capability with a `conformance/` directory contributes fixtures using the schema defined
here and the **recognized vocabulary** (§5 *Definition homes*). §5 is the authoritative home for the
general surface and states where the definition of a directive introduced or redefined after spec
version 0.113.0 must live; this section is a navigational cross-reference.

- **graph-engine** — fixtures under `spec/graph-engine/conformance/`. Originated the v0 informal
  schema (proposal 0001's `spec/graph-engine/conformance/README.md`, now slimmed to a breadcrumb
  pointer to this capability spec).
- **sessions** — fixtures under `spec/sessions/conformance/`. Originated the `invocations:`
  multi-invocation form and the `session_store` directive.
- **pipeline-utilities** — fixtures under `spec/pipeline-utilities/conformance/`. Originated the
  `fan_out` / `parallel_branches` composition directives, `checkpointer` registration, retry /
  timing / failure-isolation middleware shapes.
- **llm-provider** — fixtures under `spec/llm-provider/conformance/`. Per-directory harness
  contract (mock LLM provider, wire-format-mapping assertion shapes).
- **observability** — fixtures under `spec/observability/conformance/`. Per-directory harness
  contract for OTel + Langfuse mocks; introduced `augment_metadata` / `capture_invocation_metadata_into`
  directives.
- **prompt-management** — fixtures under `spec/prompt-management/conformance/`. Per-directory
  harness contract for prompt-fetch + render exercise shapes.
- **suspension** — fixtures under `spec/suspension/conformance/`. Introduced `suspend_with_descriptor`
  / `wrap_with_middleware` / `resume_invocation` / `signal_payload` directives + assertion shapes for
  the suspended outcome.

Each capability's `conformance/` directory MAY contain a per-directory README documenting
specialized harness contracts (per §3.2). The general directive vocabulary lives here; the
per-directory specialization lives there. That division is an instance of §5's *Definition homes*
rule rather than an independent sanction: both are homes in the recognized vocabulary.

## 12. Out of scope

- **Per-language adapter implementations.** This proposal specifies the contract; concrete
  Python / TypeScript / future-language adapters ship in their respective implementation
  repositories. The implementation work for each adapter is sibling-package effort, not part
  of this spec.
- **Fixture-authoring tooling.** Linters that check fixture YAML against the schema; scaffolders
  that generate fixture stubs from spec sections; visualization tools that render the directive
  vocabulary as documentation — all useful, all out of scope.
- **Schema-validation tooling for the YAML itself.** A JSON Schema or equivalent for the fixture
  YAML would help adapter authors catch schema violations at parse time; ships as separate
  tooling work if it lands at all.
- **Performance benchmarking or comparative-conformance reporting** between implementations.
  Whether implementation A passes fixture N in 50ms and implementation B passes it in 200ms is
  not a conformance concern; performance is implementation-specific.
- **Redesigning the directive vocabulary.** v1 ratifies what exists. A follow-on cleanup proposal
  MAY consolidate overlapping directives (e.g., `update` / `update_pure` / `update_from_field`)
  once the v0.X.0 surface stabilizes; this proposal does not bundle that work.
- **Cross-capability test orchestration.** Whether the adapter runs fixtures in a specific order,
  parallelizes across capabilities, or applies tagging / filtering — all implementation choices
  that adapters MAY surface via their host test runner (pytest markers, vitest tags, etc.). Not
  normative.
- **Per-language test-runner integration** — pytest plugin shape, vitest reporter format, etc.
  Adapter-implementation concern.

## History

- created by [proposal 0055](../../proposals/0055-conformance-adapter-capability.md)
- §6 *Harness primitives* gains §6.8 *Caching prompt backend* — an in-memory `PromptBackend` that caches by `(name, label)`, counts source reads, and honors prompt-management `cache_ttl_seconds` (`0` bypasses the cache; `None` serves cached; `N > 0` serves within a controllable-clock max-age) — plus the `source_read_count` and `advance_clock` fixture shapes it exposes, supporting the prompt-management per-fetch cache-TTL fixtures by [proposal 0072](../../proposals/0072-prompt-management-fetch-cache-ttl.md)
- §5.8 *Expected-outcome directives* gains a `metrics:` assertion (recorded measurements — instrument + dimensions for every observation, recorded value for token-usage, presence-only for duration); §6 *Harness primitives* gains §6.9 *Metric capture* — an in-memory OTel `MetricReader` (sibling to §6.3 collector capture) recording every observation, gated by an `enable_metrics` observer flag — supporting the observability §11 metrics fixtures by [proposal 0067](../../proposals/0067-observability-genai-metrics.md)
- §6.8 *Caching prompt backend* gains a fixture-level `manager: {default_cache_ttl_seconds: <int>}` construction slot and a `target: {manager: true}` fetch, so a fixture can exercise the §6 cache-TTL precedence chain (per-call value > manager default > backend) rather than only a backend-direct call — supporting the prompt-management service-wide-default fixture by [proposal 0086](../../proposals/0086-prompt-default-cache-ttl.md)
- §5.1 *Node behavior directives* gained `calls_llm_from_wrapper` — issues a real `complete()` call from a pre- / post-phase middleware so the calling node's span is not open when the provider span / `LlmCompletionEvent` is emitted, exercising the observability §5.5 *Lineage-resolved parent* orphan fallback — alongside the existing `calls_llm` node directive it complements; §5.5 documents the case-level observability harness keys (`mock_llm`, `disable_llm_spans`, `caller_global_otel_active`); §5.4 *Composition directives* documents the existing `fan_out.concurrent_mode` (serial vs concurrent instance dispatch, distinct from `concurrency`), first surfaced in observability fixtures by the nested-fan-out span-keying tests. Supports proposal 0084's nested-fan-out span-lineage fixtures by [proposal 0084](../../proposals/0084-nested-fan-out-span-lineage.md)
- §8.3 *Execution* gained a **Directive execution order** rule — a node's sibling directives (the keys under `nodes.<node_name>:`) execute in fixture-document order (mapping insertion order, not sorted-by-key), so order-sensitive compositions like `augment_metadata` → `capture_invocation_metadata_into` (observability §3.4) are deterministic; §7 *Nondeterminism handling* gains a counterpoint note (within-node order is deterministic, unlike the cross-source interleaving cases); §8.2 *Parsing* notes lossless parsing preserves directive order. New fixture `135` pins it; ratifies behavior fixtures 043/045 already depended on by [proposal 0087](../../proposals/0087-conformance-adapter-directive-execution-order.md)
- §5.8 *Expected-outcome directives* gained `expected_compile_warning` — asserts compilation succeeds while emitting non-fatal compile-time **warnings** (the adapter captures compile-time warnings, distinct from the `expected_compile_error` compile-*failure* assertion), for diagnostics such as graph-engine §2's `projection_reducer_round_trip`; takes a **scalar** (the named warning is among those emitted) or a **list** (the exhaustive set — `[]` asserts *no* warnings, so a fixture can assert a warning MUST NOT fire). The established `expected_compile_error` scalar is formally documented in §5.8 alongside it for parity by [proposal 0094](../../proposals/0094-subgraph-projection-declared-boundary.md)
- New §5.11 *Provider call-retry directives* documents the fixture surface for llm-provider §7.1's adaptive call-level retry: the `call.retry` adaptive fields `per_attempt_override` (the retry override schedule) and `reask: {template}` (a declarative stand-in for the caller's reask builder — the adapter renders the template with the `structured_output_invalid` error's `output_content` / `error_message` and wires it, contributing no text of its own), plus the `expected.wire_requests` per-attempt outbound-request assertion (`sampling`; `appended_messages` — the ordered `assistant`-output + `user`-correction pairs a reask retry appends, accumulating across retries; `messages` — the full outbound list, for the assistant-prefill continuation where a retry modifies the caller's trailing message; each asserted exactly or via `content_contains`), generalizing the single-request `expected_wire_request` provider-fixture convention to the retry-loop case; and an `attributes_absent` span-attribute directive for asserting a span carries no `retry_reason` (attempt 0) by [proposal 0095](../../proposals/0095-adaptive-call-level-retry.md)
- §5.12 *Provider structured-output error assertion* — the three `carries` assertion keys that did not track the llm-provider §7 error field names are renamed (`raw_response_content` → `output_content`, `failure_description_present` → `error_message_present`, `failure_description_mentions` → `error_message_mentions`), and the section states the key-naming convention **normatively**, scoped to the `structured_output_invalid` block: a key MUST be named for the §7 error field it asserts plus an optional flavor suffix (bare field name = exact-equality, and a **subset match** when the field is a mapping such as `usage`; `_present` = presence not value, `true` present / `false` absent; `_mentions` = the value contains a given substring), the suffix set is **closed** (a new flavor requires a proposal), and a new key MUST derive its name from the field it asserts — so the vocabulary is derivable from §7 rather than enumerated. `carries` blocks asserting other raised errors (state-migration, prompt-management, sessions) are explicitly outside the rule. The remaining keys (`response_schema_present` / `finish_reason` / `usage`) already followed it. Breaking for an adapter reading the old names; the fixture corpus (022 / 023, 063 / 064) moves in the same version. §5.12's fixture-provenance citation is corrected in the same edit (the 0095 reask fixtures are `063 / 064`, not `062–067` — the others raise nothing) by [proposal 0098](../../proposals/0098-conformance-adapter-carries-key-alignment.md)
- §5.13 *Raised-error field assertion* (`carries`) added — the capability-neutral general rule the `carries` directive lacked (a key MUST name a field the raised error's own capability spec defines it exposes; bare field = exact-equality, subset match for a mapping-valued field; `_present` / `_mentions` the closed flavor set; a key MUST NOT coin a stem with no backing field; an error field name MUST NOT end in a recognized flavor suffix so a key parses to one (field, flavor) pair). §5.12 retrofitted to reference it as the llm-provider `structured_output_invalid` instance, dropping its "governs the `structured_output_invalid` block only" scoping by [proposal 0102](../../proposals/0102-general-carries-error-field-assertion.md)
- §5.14 *Provider batch-chunking cap* (`chunk_size`) added — documents the `chunk_size` construction directive an adapter MUST honor as an embedding- or rerank-provider's per-call cap for chunk-and-stitch (retrieval-provider §8 batch chunking for embedding inputs, §8.1 rerank chunk-and-stitch for rerank documents): a real construction cap for a configurable-cap mapping (TEI `max-client-batch-size`, governing TEI `/embed` and `/rerank`), a test-only override of a fixed vendor cap (OpenAI 2048, Cohere 96) so a fixture can drive the chunking path with a small body rather than an impractical over-cap one. Moves the affordance from fixture-header prose into the adapter contract, making a fixed-cap chunking fixture reachable cross-impl by [proposal 0103](../../proposals/0103-retrieval-conformance-coverage.md)
- §5.11 *Provider call-retry directives* — the full-list `wire_requests[*].messages` sub-form is removed. It existed only to assert the llm-provider §7.1 assistant-prefill continuation (its sole fixture, 067), which 0110 removes as unreachable. With no retry that *modifies* (rather than only appends to) the caller's messages, every reachable attempt is append-only and `appended_messages` expresses every case; `sampling` and `attributes_absent` are unchanged by [proposal 0110](../../proposals/0110-remove-reask-assistant-prefill-continuation.md)
- §5.5 *Observer / observability directives* gained the `langfuse_client` construction directive (`mode: credentials | supplied`, `provider`; payload flags reuse the existing per-observer `langfuse_observer` convention) and the `no_langfuse_observations_on_global` / `no_langfuse_observations_on_private` / `langfuse_observations_on_global` expected-outcome assertions; §6.4 *Langfuse mock* gained a **provider-faithful** variant that records observation content and also emits it as OTel spans through its bound `TracerProvider` — the machinery gating observability §6's Langfuse provider-isolation MUSTs (proposal 0114), mirroring the OTel `caller_global_otel_active` / `no_openarmature_spans_on_global` isolation pattern; observability fixture 157 exercises the mode-(b) MUST-isolate carve-out and the mode-(a) MUST-NOT-mutate by [proposal 0115](../../proposals/0115-langfuse-provider-isolation-conformance.md)
- §5.5 *Observer / observability directives* extended the `langfuse_client` directive with `preexisting_same_key_client` (primes the SDK's per-credential singleton so openarmature is not the first constructor) and `accept_shared_provider` (the single shared-provider caller opt-out), added the `adapter_capabilities.langfuse_bound_provider_detection` declaration that gates fixture 158's raise vs. suppress arms, a setup-scope `expected_construction_error: {category}` assertion (the observer/client-construction analogue of `expected_compile_error`), and a `level` key on `expected.log_records` so a mandated `WARNING` severity is assertable; §6.4 *Langfuse mock* extended the provider-faithful fake with per-credential-singleton semantics, a bound-provider accessor, and a payload-bearing vs. payload-free distinction — the machinery gating observability §6's payload-leak invariant (new observability fixture 158) by [proposal 0116](../../proposals/0116-langfuse-isolation-fail-loud.md)
- §5.5 *Observer / observability directives* and §6.4 *Langfuse mock* broadened the **payload-bearing** classification to any harvested payload — provider `input` / `output`, the Trace-level state `input` / `output` (raw state or a `trace_*_from_state` hook value), and a failed Tool / Embedding / Retriever observation's `error_type` / `error_message` — with the §8.4.1 minimal stub and a category-only failed observation as payload-free; no new directive (the state-channel controls and mock-failure directives exist since proposals 0043 / 0107). Observability fixture 158 gains six cases exercising the state channel, a supplied hook, and the error-message omission (rerank and tool) across detection-capable and non-detection-capable adapters by [proposal 0117](../../proposals/0117-payload-leak-invariant-channels.md)
- §5.5 *Observer / observability directives* gained **`metadata_absent: [<key>, ...]`** on a Langfuse observation entry, asserting none of the listed keys are present in that observation's `metadata`. The existing `metadata:` assertion is a subset match, so it can pin a key's value but never its absence; this is the Langfuse-observation analogue of the OTel-span `attributes_absent` directive (§5.11, proposal 0095), added for the same reason. It gates observability's move of a failed provider observation's `error_message` under the `disable_provider_payload` flag (new fixture 159), which is an absence assertion by nature. §6.4's payload-bearing classification is **narrowed** in the same change: a failed observation's `error_type` is a classification token rather than harvested text, so it no longer makes an observation payload-bearing by [proposal 0118](../../proposals/0118-llm-error-message-channel.md)
- §5's preamble gained a **Definition homes** rule naming exactly two places a directive's definition may live: §5 itself for the general surface, and a per-directory harness note for a contract specific to one capability's fixtures. Together they are the **recognized vocabulary**; §8.2's lossless-parsing rule is re-anchored to that phrase from "the §5 directive vocabulary", and §1, §3.2, §3.3 and §11 are reconciled to it. Prospective, binding on a proposal that introduces or redefines a directive after spec version 0.113.0. §5.9's fixture-specific invariant predicates are deliberately outside the rule and the §8.2-versus-§5.9 conflict survives for them, by [proposal 0120](../../proposals/0120-fixture-directive-definition-rule.md)
- §4.2 *Multi-case form* gained **The `graph:` container**, specifying a case form 17 shipped cases already used and no section defined: what the container holds, that every other case key stays its sibling, that the two case forms are equivalent, and that a container case asserting a runtime outcome MUST be executed. §5.4 *Composition directives* gained a **Subgraph declaration placement** rule: a declaration (`subgraph:` or `subgraphs:`) is scoped to the graph specification it accompanies, so an adapter MUST accept it at the document top level, inside a case, or inside a case's `graph:` block, and MUST resolve a name declared at more than one site using the innermost declaration in scope, with the `subgraphs:` mapping entry governing where both forms appear at one site. The section's three top-level claims and its `nodes.<node_name>:` preamble are reworded to match. Its own `conformance/` directory opens with fixture 001 by [proposal 0123](../../proposals/0123-case-level-subgraph-declaration.md)
- §5.5 *Observer / observability directives* gained **`event_name`** on an `expected.log_records` entry, asserting the record's OTel `EventName` field so a fixture can pin which mandated diagnostic fired rather than only a severity, and **`otel_observer: {disable_provider_payload: <bool>}`**, the OTel-side counterpart of `langfuse_observer` which an adapter MUST honor. The `langfuse_client` paragraph is reconciled to the new directive, and twelve cases across eleven fixtures migrated off the undocumented bare case-level form, covering both `disable_provider_payload` and `disable_genai_semconv`, by [proposal 0121](../../proposals/0121-diagnostic-event-names-and-otel-observer-directive.md)
- §5.11 documented the existing **`attribute_truncation`** directive and all four of its sub-keys beside `attributes_absent`; §5.5 gained **`metadata_truncation`** on a Langfuse observation entry and a **`raises: {error_type, message | message_repeat}`** form on `mock_llm`; §5.15 gained **`message_repeat`** on the retrieval mocks' `raises`; and §5.1 documented the existing **`content_repeat`** and **`base64_data_synthetic`** synthesis primitives beside `calls_llm`. §5.5 also documented the existing **`payload_byte_cap`** on both observer directives, the per-observer cap a fixture must set asymmetrically to gate observability §8.7's MUST NOT. Both truncation assertions gained an adapter **MUST**-honor rule, a key-presence requirement and an at-least-one-sub-key requirement, so a silently-skipping adapter fails rather than passing vacuously; `utf8_valid` gained the multi-byte-filler requirement without which it cannot fail. §5.11's scope sentence and §5.1's `base64_data_synthetic` field name (`source.base64_data`, not `source.data`) were corrected in the same pass by [proposal 0119](../../proposals/0119-error-message-cap-and-reserved-keys.md)
- §5.1 *Node behavior directives* gained **`yield_after_call`** on `calls_llm_from_wrapper`: when `true` the adapter MUST ensure observer delivery **through this call's provider event** has completed before the wrapper returns, with the obligation on what is achieved rather than on the host language's mechanism. Stated as a barrier rather than as the yield 0124 prescribed, because graph-engine §6's strictly serial delivery queue means conceding one turn hands the queue one event with nothing binding it to this call. Without it no fixture can distinguish an implementation that resolves an orphan's parent structurally (observability §5.5) from one that passes because the wrapper span happened to be materialized already, which is a difference of observer architecture rather than of conformance. Set on all five directive blocks across observability fixtures 133, 134, 152 and 153, every fixture carrying the primitive; no assertion changed by [proposal 0124](../../proposals/0124-orphan-provider-span-parent-resolution.md)
