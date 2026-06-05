# Conformance Fixtures

How the OpenArmature conformance fixture system works, end-to-end.

This page is the readable explainer. The normative source — the YAML schema, the full directive
vocabulary, the harness primitive requirements, the assertion shapes — lives in
[`spec/conformance-adapter/spec.md`](capabilities/conformance-adapter.md). This page is for
implementers who want a mental model first.

## The shape of the system

A conformance fixture is a YAML file that describes a test case **declaratively** — what graph to
build, what state to start with, what to expect when you run it. The spec ships hundreds of these
files under `spec/<capability>/conformance/`. Every language implementation has to read them, build
the equivalent graph in its own language, run it, and check the result matches the expectation. If
it matches, that implementation passes. If it doesn't, it's not conformant.

The point: the YAML doesn't know about Python or TypeScript. The behaviors it describes — state
types, reducers, node returns, edges, expected outcomes — exist in the abstract spec, not in any
language. So one fixture file works for every implementation. If the Python adapter and the
TypeScript adapter both pass the same fixture, they're behaviorally equivalent on whatever that
fixture tests.

**Most fixtures test behaviors WITHIN `invoke()`** — they describe a graph, run it, and assert on
the outcome. A small but important class of fixtures test behaviors **ABOVE** `invoke()` — for
example, the harness fixture suite (`spec/harness/conformance/`) describes a harness configuration
that WRAPS `invoke()`, with synthetic inbound transmissions and assertions on the harness's
dispatch-path classification, outcome handling, signal-coordinator behavior, and error
categorization. The schema is the same (declarative YAML; adapter translates to host language); the
layer being tested is different. The capability spec's §3.2 *per-directory harness notes via
fixture-header comments* rule lets each suite document its specialized fixture conventions inline
in the fixture headers.

## A concrete example

Here's a real fixture (`spec/graph-engine/conformance/001-linear-static-flow.yaml`, abbreviated):

```yaml
state:
  fields:
    count:
      type: int
      default: 0

entry: increment

nodes:
  increment:
    update: {count: 5}

edges:
  - {from: increment, to: END}

initial_state: {}

expected:
  final_state: {count: 5}
  execution_order: [increment]
```

Plain English: there's one state field called `count` (an int, default 0). The graph has one node
called `increment` that returns `{count: 5}`. There's an edge from `increment` to END. Start with
empty state. Expected outcome: final state has `count = 5` and the node `increment` ran. That's
the whole test.

The Python implementation has an **adapter** that reads this YAML, then translates it into actual
Python code: it builds a Pydantic model for the state schema, defines a Python async function for
the `increment` node, registers the edge, compiles the graph, calls `invoke()` with the initial
state, and finally compares the result against what's in `expected:`. If it doesn't match, pytest
reports a failure. If TypeScript eventually ships, its adapter does the analogous thing in
TypeScript (zod schema, async function, the TS graph engine's API).

## Directive vocabulary

The **directive vocabulary** is the set of keys you can put in the YAML. The fixture above used a
handful: `update`, `state.fields.*`, `entry`, `nodes`, `edges`, `initial_state`,
`expected.final_state`, `expected.execution_order`. The spec ships many more — directives for
fan-out, parallel-branches, observers, sessions, suspension, drain, middleware, and dozens of
assertion shapes.

The full enumeration lives in
[`spec/conformance-adapter/spec.md` §5](capabilities/conformance-adapter.md#5-directive-vocabulary).
That section is organized by category:

| Category | What it covers |
|---|---|
| §5.1 Node behavior | What a node does at runtime (`update`, `suspend_with_descriptor`, `invoke_drain_events_for`, …) |
| §5.2 State / schema | Field types, defaults, reducers |
| §5.3 Edges | Static + conditional edges |
| §5.4 Composition | `fan_out`, `parallel_branches`, `subgraph` |
| §5.5 Observers | `observers[]` with behavior enum (`record`, `accumulate`, `raise`), pacing, phase filters |
| §5.6 Persistence | `session_store`, `checkpointer`, per-invocation backend assertions |
| §5.7 Invocation shape | Single-invocation vs `invocations[]` multi-invoke (sessions, resume, suspension cycles) |
| §5.8 Expected outcomes | `final_state`, `execution_order`, `outcome`, `error.category`, `drain_summary`, `observer_events`, OTel + Langfuse assertion shapes |
| §5.9 Invariants | Name-keyed boolean predicates for nondeterministic-ordering cases |

Each directive entry in §5 specifies its YAML location, parameters, the runtime behavior the
adapter MUST honor, and the spec section(s) the directive exists to exercise.

## Harness primitives

For things that can't be expressed declaratively in YAML — like "make an in-memory observer that
records every event for later inspection," or "give me an in-memory session store that doesn't
actually hit disk," or "wire up a real `suspend()` call from inside this synthetic node body so I
can test the suspension primitive" — the adapter provides **harness primitives**. These are real
Python (or TS, or whatever) code that the adapter ships, configured by the directives in the
fixture.

The `behavior: accumulate` directive tells the adapter "instantiate your in-memory accumulating
observer and attach it to the graph"; the `session_store: in_memory` directive tells it
"instantiate your in-memory session store." None of that is in the YAML; the YAML just says "use
this primitive" and the adapter ships the primitive.

The required harness primitives are enumerated in
[§6](capabilities/conformance-adapter.md#6-harness-primitives):

- **In-memory observers** (`record`, `accumulate`, `raise`, paced)
- **In-memory persistence backends** (SessionStore, Checkpointer, shared per pipeline-utilities §10.15)
- **OTel collector capture** for observability fixtures
- **Langfuse mock** for observability fixtures
- **Suspend / resume wiring** — the spec mandates these are **real** primitive calls, not simulations
- **Drain wiring** — same, real `drain()` / `drain_events_for()` calls
- **Middleware wiring** — real middleware execution, markers recorded into a state log

The "real, not simulated" rule is load-bearing. The adapter constructs a real compiled graph and
calls real `invoke()`. The fixture describes what shape that graph takes and what outcome to
expect. The engine doesn't know it's being tested.

**Per-directory harness contracts.** Beyond the general harness primitives, some fixture suites
need specialized scaffolding that only applies inside that capability's directory. Per the
[capability spec's §3.2](capabilities/conformance-adapter.md#3-fixture-file-format), these
specializations live in **fixture-header comments** rather than the general directive vocabulary.
Two worked examples:

- **Observability fixtures** (`spec/observability/conformance/`) document an in-memory OTel
  `SpanExporter` + private `TracerProvider` (per observability §6 isolation), `caller_*` config
  blocks, and `<uuid>` / `<any-string>` placeholder syntax in the header of fixture
  `001-otel-basic-trace.yaml`. Those conventions are normative for the observability suite even
  though they aren't in the capability spec.
- **Harness fixtures** (`spec/harness/conformance/`) document a synthetic in-process transport
  with a `transmissions:` list (each entry is a simulated inbound request / event with
  `dispatch_intent`, optional `session_id`, optional `signal_payload`), a `harness:` block
  configuring mode (sessioned / stateless) and signal coordinator, and per-transmission assertion
  shapes (`dispatch_path`, `invoke_args`, `invoke_outcome`, `outbound_shape`, `error_bucket`,
  etc.). The fixture-header in `001-inbound-new-session.yaml` is the suite's documentation.

The pattern keeps the capability spec maintainable (it documents the general surface) while
letting specialized suites grow the scaffolding they need without bloating the general
vocabulary.

## Nondeterminism

Some execution orderings are observable but not uniquely determined by the spec — fan-out instance
scheduling, parallel-branches branch scheduling, observer event dispatch within one phase. The
spec defines these as nondeterministic per graph-engine §3, §5, and §6.

Fixtures touching these surfaces use `observer_event_invariants:` instead of `observer_events:`,
with named boolean predicates that the adapter resolves to runtime checks:

```yaml
observer_event_invariants:
  inner_event_count: 6                    # 3 instances × 2 phases
  inner_fan_out_indices_seen: [0, 1, 2]   # set, not list
  inner_event_identities_unique: true     # tuple-uniqueness invariant
```

Counts and identity-tuple uniqueness, not exact event sequences. The adapter MUST NOT impose
ordering the spec doesn't determine. Full rule per
[§7](capabilities/conformance-adapter.md#7-nondeterminism-handling).

## How a fixture run flows end-to-end

Picture the Python adapter at work on a single fixture:

1. **Discover.** Walk `spec/*/conformance/` for `*.yaml` files. The current fixture is
   `spec/graph-engine/conformance/032-drain-events-for-fan-out-coverage.yaml`.
2. **Parse.** Read the YAML. Recognize every directive — `state.fields`, `entry`, `nodes` with
   `fan_out` + `invoke_drain_events_for`, `edges`, `observers[]` with `behavior: accumulate`,
   `expected.outcome: completed`, `expected.node_drain_summaries`,
   `expected.node_accumulator_snapshot_invariants`. If any directive isn't recognized, raise
   `fixture_directive_unknown` rather than silently skip it (per
   [§9](capabilities/conformance-adapter.md#9-errors)).
3. **Construct.** Build a Pydantic model for the state schema. Register the fan-out node. Wire up
   the in-memory accumulating observer. Set up the implementation's real `drain_events_for()`
   primitive for the `invoke_drain_events_for` directive.
4. **Execute.** Call `invoke()` against the real compiled graph. The fan-out fires, instances run
   concurrently, the persist node calls the real `drain_events_for()` operation, the accumulator
   snapshot is captured.
5. **Assert.** Compare the returned outcome against `expected:`. Verify `final_state`
   exact-equality. Verify the drain summary on `persist`. Verify the accumulator snapshot
   invariants (counts, `fan_out_index` set). Surface failures through pytest.

Step 4 is the real engine doing real work — no mocking, no simulation. Step 5 is where the
fixture's declarative description meets the implementation's actual behavior.

## How a new language implementation ships a conformance-passing adapter

If a future OpenArmature implementation lands (TypeScript port, Rust port, etc.), the adapter is
implementation-private test infrastructure that satisfies the contract in
[`spec/conformance-adapter/spec.md`](capabilities/conformance-adapter.md). The work decomposes:

1. **Fixture discovery.** Walk the OA spec repository's `spec/<capability>/conformance/`
   directories for `*.yaml` files. Reuse a YAML parser appropriate to the host language.
2. **Directive translation.** For each directive in
   [§5](capabilities/conformance-adapter.md#5-directive-vocabulary), implement a host-language
   translator. Most are mechanical (a YAML `update:` block becomes the host language's equivalent
   "return this partial state from the node body"); a few require harness primitive infrastructure
   (`session_store: in_memory` needs an in-memory SessionStore implementation in the host
   language).
3. **Harness primitive implementations.** Per
   [§6](capabilities/conformance-adapter.md#6-harness-primitives), ship in-memory observers,
   in-memory backends, OTel + Langfuse mocks, suspend / drain / middleware wiring. These are
   typically substantially smaller than the production implementations of the same primitives —
   they exist for tests, not for production load.
4. **Assertion translation.** For each assertion shape in
   [§5.8 / §5.9](capabilities/conformance-adapter.md#58-expected-outcome-directives), implement a
   host-language assertion. Exact-equality shapes map directly to the host language's
   `assertEqual`-style operations; invariant shapes (per §5.9) require named-predicate logic that
   each adapter MUST implement.
5. **Test-runner integration.** Wire the adapter into the host language's idiomatic test framework
   (pytest for Python, vitest for TypeScript, etc.). Each fixture becomes a test case; failures
   surface through the host runner.

Adapters are typically a few thousand lines of code — small relative to the implementation itself
because the directive vocabulary is finite and the assertion shapes are well-defined.

## Future-proofing: how the vocabulary grows

The directive vocabulary will grow over time. Every proposal that adds new fixture shapes
extends the vocabulary — the proposal's *Conformance test impact* section enumerates the new
directives, and the conformance-adapter capability spec's
[§5](capabilities/conformance-adapter.md#5-directive-vocabulary) gains corresponding entries.

This is the same pattern other capabilities follow: new pipeline-utilities §6 middleware lands in
pipeline-utilities, new observability §5 attributes land in observability, new conformance
directives land in conformance-adapter. The spec's
[`docs/governance.md`](governance.md#conformance-tests) §"Conformance tests" makes this rule
normative: new conformance tests that any implementation could fail require a proposal.

Adapter authors track changes by following the
[`CHANGELOG.md`](changelog.md) for capability updates that touch conformance-adapter. The
implementation's spec-version pin (e.g., the openarmature-python `pyproject.toml`
`openarmature_spec_version` field) determines which directive vocabulary the adapter targets.

## Where to look next

- **Normative spec** — [`capabilities/conformance-adapter.md`](capabilities/conformance-adapter.md)
- **Governance overview** — [`governance.md`](governance.md#conformance-tests) (Conformance tests section)
- **A real fixture suite to study (graph-level)** — `spec/graph-engine/conformance/` in the
  repository; lower-level fixtures that describe a graph, run it, and assert on the outcome
- **A real fixture suite to study (above-invoke level)** — `spec/harness/conformance/` in the
  repository; higher-level fixtures that describe a harness configuration wrapping `invoke()`,
  with synthetic inbound transmissions and assertions on dispatch-path classification, outcome
  handling, signal coordination, and error categorization. A useful contrast to the graph-engine
  suite — same YAML schema, different layer being tested
- **The reference Python adapter** — `openarmature-python/tests/conformance/` (sibling repository)
