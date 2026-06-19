# Conformance Adapter

Canonical behavioral specification for the OpenArmature conformance-adapter capability.

- **Capability:** conformance-adapter
- **Introduced:** spec version 0.48.0
- **History:**
  - created by [proposal 0055](../../proposals/0055-conformance-adapter-capability.md)
  - §6 *Harness primitives* gains §6.8 *Caching prompt backend* — an in-memory `PromptBackend` that caches by `(name, label)`, counts source reads, and honors prompt-management `cache_ttl_seconds` (`0` bypasses the cache; `None` serves cached; `N > 0` serves within a controllable-clock max-age) — plus the `source_read_count` and `advance_clock` fixture shapes it exposes, supporting the prompt-management per-fetch cache-TTL fixtures by [proposal 0072](../../proposals/0072-prompt-management-fetch-cache-ttl.md)
  - §5.8 *Expected-outcome directives* gains a `metrics:` assertion (recorded measurements — instrument + dimensions for every observation, recorded value for token-usage, presence-only for duration); §6 *Harness primitives* gains §6.9 *Metric capture* — an in-memory OTel `MetricReader` (sibling to §6.3 collector capture) recording every observation, gated by an `enable_metrics` observer flag — supporting the observability §11 metrics fixtures by [proposal 0067](../../proposals/0067-observability-genai-metrics.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) ships a thin **adapter**
that ingests the language-agnostic YAML fixtures under `spec/<capability>/conformance/` and executes them
against the host implementation's runtime, asserting on outcomes via the host language's idiomatic test
framework.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The `conformance-adapter` capability defines the language-agnostic conformance fixture system that every
OpenArmature implementation builds against: the YAML schema fixtures use, the directive vocabulary they
draw from, the harness primitives implementations MUST provide to execute them, the assertion shapes
adapters MUST honor, and the responsibility model for language-specific adapters that translate fixtures
into host-runtime tests.

The capability is **descriptive of the system that already exists** as of spec v0.47.0. The fixture
format, directive vocabulary, and adapter pattern have accreted across more than two dozen prior
proposals since proposal 0001 introduced the first fixtures; this capability gives that vocabulary a
single normative home. Future proposals that introduce new directives extend §5 *Directive vocabulary*
the same way new pipeline-utilities §6 middleware extend pipeline-utilities or new observability §5
attribute sets extend observability.

The capability composes with:

- **Every other capability.** Each existing capability's `conformance/` directory contains fixtures
  written in the schema defined here, drawing directives from the vocabulary enumerated in §5.
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
  `expected.no_global_provider_spans`.
- Attribute placeholder syntax: `<uuid>` matches any canonical UUIDv4, `<any-string>` matches any
  non-empty string, `<trace_id_X>` matches an opaque trace_id with first-occurrence binding for
  cross-reference.

That comment block is normative for the observability fixture suite even though it isn't part of this
capability spec. Implementations MUST honor per-directory harness notes when the fixture's YAML
references them; the directives this capability spec defines are the general surface, but per-directory
specialization is a permitted extension.

### 3.3 No required README per directory

Conformance directories MAY ship a `README.md` describing the directory's scope, but a README is NOT
required. The capability spec is the authoritative schema reference; per-directory READMEs are
navigational aids at most.

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

This section is the authoritative enumeration of directives currently in use. Each directive entry
specifies its YAML location, parameters, runtime behavior the adapter MUST honor, and the spec
section(s) the directive exists to exercise.

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

These directives appear under `nodes.<node_name>:` and configure compound node shapes per
pipeline-utilities §9 / §11.

- **`subgraph: <subgraph_name>`** — the node executes a named subgraph (declared at fixture top
  level via `subgraph:` or `subgraphs:` mapping). Exercises graph-engine §2 (subgraph composition).
- **Subgraph declaration via top-level `subgraph:`** — single inline subgraph (used when only one
  subgraph is needed):
  ```yaml
  subgraph:
    name: <name>
    state: { fields: ... }
    entry: <node_name>
    nodes: { ... }
    edges: [ ... ]
  ```
- **Subgraph declaration via top-level `subgraphs:`** — named mapping (used when multiple subgraphs
  are needed, typically with parallel-branches):
  ```yaml
  subgraphs:
    <name_1>: { state: ..., entry: ..., nodes: ..., edges: ... }
    <name_2>: { ... }
  ```
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
  ```
  Exercises pipeline-utilities §9 (parallel fan-out).
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

OTel and Langfuse emission are NOT observer behaviors. Observability fixtures that exercise OTel
span emission OR Langfuse trace/observation emission rely on **harness primitives** the adapter
provides at the capability-directory level — an in-memory OTel `SpanExporter` instantiated for
the observability fixture suite, an in-memory Langfuse client wrapper, etc. The per-directory
harness contract (per §3.2) documents this; see also §6 *Harness primitives*.

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
  duration observations (value not asserted, per observability §11.4). With the observer's
  `enable_metrics` off, no measurements are recorded — a `metrics: []` assertion confirms the opt-in
  gate. See §6.9 for the primitive and the `enable_metrics` configuration.

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
  dimensions only, not the value (observability §11.4).
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

## 8. Adapter responsibility

A language adapter ships in its implementation's repository (e.g., openarmature-python,
openarmature-typescript) as test infrastructure. To satisfy this capability spec, the adapter MUST:

### 8.1 Discovery

Walk `spec/<capability>/conformance/` directories for `*.yaml` files. Each file is one fixture.
Adapters MAY filter by capability or fixture name; the default MUST be "discover and run all
fixtures."

### 8.2 Parsing

Translate each fixture's YAML into native graph-construction calls in the host language. Parsing
MUST be lossless against the §5 directive vocabulary; unknown directives MUST raise
`fixture_directive_unknown` (per §9) rather than being silently skipped or treated as defaults.

### 8.3 Execution

Construct the graph, instantiate harness primitives per §6, run each invocation against the
implementation's real runtime. The adapter MUST NOT simulate any spec-defined behavior — every
construct the fixture exercises (suspend, drain, middleware, fan-out, parallel-branches, sessions,
checkpointing, observability emission) MUST be the real implementation primitive.

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
  missing, malformed type for a known directive, invalid YAML syntax). The adapter MUST raise
  rather than infer defaults.
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

Every other capability with a `conformance/` directory contributes fixtures using the schema and
directive vocabulary defined here. The directive vocabulary §5 is the authoritative enumeration;
this section is a navigational cross-reference.

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
per-directory specialization lives there.

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
