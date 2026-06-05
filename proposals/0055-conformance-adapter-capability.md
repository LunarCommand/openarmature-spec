# 0055: Conformance Adapter Capability

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-03
- **Accepted:** 2026-06-04
- **Targets:** spec/conformance-adapter/spec.md (creates — new capability spec ratifying the existing fixture YAML schema, directive vocabulary, harness primitives, and adapter responsibility model); docs/conformance.md (creates — readable explainer / tutorial alongside governance.md); spec/graph-engine/conformance/README.md (slim down — its v0 informal schema content moves into the new capability spec; the README becomes a one-line breadcrumb pointing at the capability spec); docs/governance.md §"Conformance tests" (extends to cross-reference the new capability spec as the normative source).
- **Related:** 0001 (graph-engine — first capability with fixtures; source of the v0 informal YAML schema embedded in `spec/graph-engine/conformance/README.md`), 0020 (sessions — introduced the multi-invocation `invocations:` list directive for cross-invoke fixtures), 0048 (introduced `augment_metadata` / `augment_metadata_from_field` / `capture_invocation_metadata_into` for the read-symmetric invocation metadata read API), 0054 (introduced `behavior: accumulate`, `invoke_drain_events_for`, `node_drain_summaries`, `node_accumulator_snapshots`, `final_accumulator_state` for the per-invocation drain primitive), 0021 (introduced `suspend_with_descriptor`, `conditional_suspend`, `wrap_with_middleware`, `resume_invocation`, `signal_payload`, `descriptor` / `suspending_node` / `metadata_includes` assertion shapes for the suspension primitive)
- **Supersedes:**

## Summary

Create the `conformance-adapter` capability spec. Documents the language-agnostic fixture
system that every OA implementation builds against: the YAML fixture schema, the directive
vocabulary that has accreted across proposals 0001-0054, the harness primitives implementations
MUST provide, the assertion shapes adapters MUST honor, and the responsibility model for
language adapters that ingest fixtures and exercise them against a native implementation. Adds
a docs-side explainer (`docs/conformance.md`) parallel to `docs/governance.md` and
`docs/openarmature.md`.

The capability v1 is **ratifying** — it documents the directive vocabulary as it currently
exists across the conformance directories. No directive shapes change. Future proposals that
introduce new directives continue the established pattern (each proposal's *Conformance test
impact* section lists the new directives the proposal adds), but the new directives now have a
named home — implementations look up directive semantics in
`spec/conformance-adapter/spec.md` rather than reverse-engineering them from each proposal's
fixture additions.

The capability is **spec'd as a versioned capability** (not a top-level doc). Implementations
declare conformance-adapter version alongside spec_version in their package metadata; the
SemVer-pinned vocabulary is the contract a language adapter targets.

## Motivation

**The fixture system has outgrown its v0 documentation.** The original conformance README at
`spec/graph-engine/conformance/README.md` ships an "informal v0" YAML schema covering the
basic graph-engine shape (`state` / `entry` / `nodes` / `edges` / `expected`). That schema
was sufficient when graph-engine was the only capability with fixtures. Since then, every
proposal that introduced a new behavioral surface has extended the YAML format with new
directives:

- **Proposal 0005 (parallel fan-out):** `fan_out` node directive, `fan_out_index` event field,
  `subgraph` declaration form.
- **Proposal 0011 (parallel branches):** `parallel_branches` node directive, `branch_name`
  event field, `subgraphs` multi-declaration form, `branches` mapping.
- **Proposal 0020 (sessions):** `session_store` registration, `session_id` per-invocation,
  `invocations:` list for multi-invoke fixtures, `loaded_session_state` /
  `saved_session_assertions` assertion shapes.
- **Proposal 0008 / 0010 / 0030 (checkpointing + drain):** `checkpointer` registration,
  `drain: {timeout_seconds}` invoke directive, `drain_summary` assertion shape,
  `sleep_ms_per_event` observer-pacing directive, `behavior: record` observer behavior.
- **Proposal 0048 (read-symmetric invocation metadata + queryable observer pattern):**
  `augment_metadata` / `augment_metadata_from_field` / `capture_invocation_metadata_into`
  node directives, `caller_metadata` per-invocation, `caller_invocation_id`.
- **Proposal 0054 (per-invocation event drain):** `behavior: accumulate` observer behavior,
  `invoke_drain_events_for` node directive, `node_drain_summaries` /
  `node_accumulator_snapshots` / `node_accumulator_snapshot_invariants` /
  `final_accumulator_state` assertion shapes.
- **Proposal 0021 (suspension):** `suspend_with_descriptor` /
  `conditional_suspend` / `pre_next_calls_suspend_with_descriptor` node directives,
  `wrap_with_middleware` directive, `resume_invocation` / `signal_payload`
  per-invocation, `descriptor` / `suspending_node` / `metadata_includes` /
  `node_drain_summaries` / `outcome` / `error.category` assertion shapes.

The vocabulary has roughly doubled in size since v0 and is split across the *Conformance test
impact* sections of more than two dozen subsequent proposals. No single document collects it;
no version is declared; no normative contract obligates implementations to honor each
directive's documented semantics.

The downstream consequence is that the **reference Python implementation has become the de
facto source of truth** for what each directive means at runtime. A future
`openarmature-typescript` adapter would have to reverse-engineer the directive semantics from
the Python implementation rather than from spec text — an inversion of the spec-repo-as-truth
model the rest of OA is built on.

**Cross-language consistency is the load-bearing payoff.** OA's whole rationale for shipping
as a spec repo separate from any language implementation is that future language ports build
against the spec, not against the Python implementation. The conformance fixtures are the
behavioral truth for cross-language consistency (per `docs/governance.md` §"Multi-language
consistency" — "APIs MAY differ in syntactic shape; behavior MUST match conformance tests").
For that promise to hold, the YAML schema + directive vocabulary + harness primitives + assertion
shapes MUST themselves be specified, not just the behaviors they exercise.

**This proposal does the documentation work that should have happened incrementally but was
deferred at every step.** Each new directive landed via a proposal that focused on the
behavior being tested; the directive itself was treated as test-infrastructure detail. The
accumulated state is now substantial enough to warrant its own capability spec — and the
ratification gives future proposals a clear home for new directives (each new proposal's
*Conformance test impact* section adds to the conformance-adapter capability's directive
vocabulary, the same way new pipeline-utilities §6.x middleware land in pipeline-utilities or
new observability §5.x attribute sets land in observability).

## Detailed design

### 1. Capability spec scope

The new `spec/conformance-adapter/spec.md` defines:

- **Fixture file format.** Per-capability `conformance/` directories under
  `spec/<capability>/`. Each fixture is a numbered `NNN-name.yaml` + `NNN-name.md` pair (the
  YAML carries the declarative test; the Markdown carries the prose description of what is
  being tested, which spec sections are exercised, and what passes vs fails).
- **YAML schema.** The full document shape, including the single-case form (`state:` /
  `entry:` / `nodes:` / `edges:` / `initial_state:` / `expected:` at top level), the
  multi-case form (`cases:` list), and the multi-invocation form (`invocations:` list with
  per-invocation `initial_state` / `resume_invocation` / `signal_payload` / `session_id` /
  `expected`).
- **Directive vocabulary.** Every directive currently in use across the seven capabilities'
  conformance directories, organized by category (node behavior, state / schema, edge,
  composition, observer, persistence, invocation-shape, expected-outcome, invariant).
  Each directive entry specifies: name, where it appears in the YAML structure, parameters
  and their types, the runtime behavior the adapter MUST honor, and the spec
  section(s) the directive exists to exercise.
- **Harness primitives.** What language adapters MUST provide to execute the fixtures —
  in-memory observer types (recording, accumulating, slow / paced, OTel-emitting, Langfuse-
  emitting, raising), in-memory persistence backends (session store, checkpointer), suspend /
  resume primitive wiring (so a fixture's `suspend_with_descriptor` directive translates to a
  real `suspend()` call from inside a synthetic node body), drain primitive wiring (so
  `drain: {timeout_seconds}` and `invoke_drain_events_for` translate to real drain calls).
- **Assertion shapes.** The expected-outcome surface — exact-equality assertions on final
  state and execution order; invariant assertions for nondeterministic-ordering cases (counts,
  identity-tuple uniqueness, attribute presence, ordering relations between events that are
  ordered even when individual event positions are not); structured assertions on observer
  events, OTel spans, Langfuse traces, drain summaries, accumulator snapshots, session
  records.
- **Nondeterminism handling.** Which orderings are observable but not uniquely determined
  (fan-out instance scheduling, parallel-branches branch scheduling, observer event dispatch
  within a phase) and how fixtures assert on those cases (`observer_event_invariants` rather
  than `observer_events`, count-based or identity-tuple-based assertions rather than
  enumerated event lists).
- **Adapter responsibility model.** What a language implementation does to ship a
  conformance-passing adapter — fixture discovery (walking `spec/*/conformance/` for `*.yaml`
  files), per-case parsing into the implementation's native graph-construction calls,
  per-case execution against the implementation's runtime, per-case assertion via the
  language's idiomatic test framework (pytest for Python, vitest for TypeScript, etc.). The
  adapter is implementation-private; the fixtures are spec-public.
- **Versioning.** The conformance-adapter capability follows whole-spec SemVer like every
  other capability. Each proposal that adds directives bumps the capability version. The
  capability ships at v0.X.0 (matching whatever the spec version is at acceptance time).
- **Errors at the adapter layer.** `fixture_directive_unknown` (an adapter that doesn't
  recognize a directive MUST raise rather than silently skip), `fixture_schema_invalid` (an
  adapter that finds a structurally-broken fixture MUST raise rather than infer a default),
  and a handful of other adapter-layer error categories.

### 2. Spec section structure (12 sections, matching the established capability-spec template)

- **§1 Purpose** — frames the conformance-adapter as the spec-side authority for the fixture
  system; cross-references `docs/governance.md` §"Conformance tests" (overview),
  `docs/conformance.md` (explainer), and the new `spec/conformance-adapter/spec.md`
  (normative).
- **§2 Concepts** — Fixture, Adapter, Directive, Harness primitive, Assertion shape,
  Invariant, Case, Invocation.
- **§3 Fixture file format** — directory layout, `NNN-name.{yaml,md}` pair convention,
  numbering rules, README discovery (no required README per directory; the capability spec
  is the schema reference). **Per-directory harness notes via fixture-header comments.**
  The capability spec is the home for *general* directives that span capabilities; fixture-
  header comments MAY supplement with per-directory-specific harness notes when a
  capability's fixtures share a specialized contract that doesn't generalize. Worked
  example: `spec/observability/conformance/001-otel-basic-trace.yaml` opens with a comment
  block documenting the per-capability harness contract (in-memory OTel `SpanExporter`,
  private `TracerProvider` per spec §6 isolation, `caller_correlation_id` /
  `detached_subgraphs` / `mock_llm` / etc. optional config blocks, the `<uuid>` /
  `<any-string>` / `<trace_id_X>` placeholder syntax). That header is normative for the
  observability fixture suite even though it isn't part of the capability spec. The
  conformance-adapter spec describes the general directive surface; per-directory
  fixture-header notes describe specialized harness wiring that only applies inside that
  directory.
- **§4 Fixture YAML schema** — top-level shape (single-case form), `cases:` multi-case form,
  `invocations:` multi-invocation form, version pinning (the conformance-adapter version a
  fixture targets MAY be declared in a `conformance_version:` top-level key; defaults to
  whatever the spec version is at the time the fixture was authored).
- **§5 Directive vocabulary** — enumerated by category (sub-sections §5.1-§5.9):
  - §5.1 Node behavior directives — `update`, `update_pure`, `update_from_field`, `raises`,
    `suspend_with_descriptor`, `conditional_suspend`,
    `pre_next_calls_suspend_with_descriptor`, `invoke_drain_events_for`,
    `wrap_with_middleware`, `augment_metadata`, `augment_metadata_from_field`,
    `capture_invocation_metadata_into`.
  - §5.2 State / schema directives — `state.fields` shape (type, default, reducer),
    `initial_state`.
  - §5.3 Edge directives — static form, conditional form, conditional with `if_field` /
    `equals` / `then` / `else`.
  - §5.4 Composition directives — `subgraph` (single inline), `subgraphs` (named mapping),
    `fan_out` (subgraph, items_field, item_field, collect_field, target_field,
    error_policy, concurrency), `parallel_branches` (branches mapping with subgraph /
    outputs, error_policy).
  - §5.5 Observer / observability directives — `observers[]` with `behavior` enum
    (`record`, `accumulate`, `raise`), `sleep_ms_per_event` (constant OR
    `{first_invocation, subsequent_invocations}` shape), `attach` (`graph` /
    `invocation`), `target` (`outer` / `inner` / specific subgraph or node name),
    `phases` filter, `caller_metadata`, `caller_invocation_id`. OTel and Langfuse
    emission are NOT observer behaviors — they're harness primitives provided by the
    capability's host directory; see §6.
  - §5.6 Persistence directives — `session_store` (e.g., `in_memory`), `checkpointer`
    (e.g., `in_memory`), `loaded_session_state`, `saved_session_assertions`,
    `checkpointer_assertions`.
  - §5.7 Invocation-shape directives — single-invocation top-level (`invoke:` / direct
    `initial_state:` + `expected:`); multi-invocation `invocations[]` with per-entry
    `name`, `session_id`, `correlation_id`, `caller_invocation_id`, `resume_invocation`,
    `signal_payload`, `caller_metadata`, `initial_state`, `drain`, `expected`.
  - §5.8 Expected-outcome directives — `final_state`, `execution_order`, `outcome`
    (completed / errored / suspended), `error.category`, `expected_error.category` /
    `expected_error.raised_from`, `drain_summary`, `observer_events`,
    `observer_event_invariants`, `otel_spans`, `langfuse_*`, `node_drain_summaries`,
    `node_accumulator_snapshots`, `node_accumulator_snapshot_invariants`,
    `final_accumulator_state`, `saved_session_assertions`, `descriptor`,
    `suspending_node`, `metadata_includes`, `suspended_state`,
    `final_state_at_error`.
  - §5.9 Invariant assertions — `invariants:` block (name-keyed boolean predicates the
    adapter verifies as additional checks beyond exact-equality assertions; used for
    nondeterministic-ordering cases and for stating load-bearing properties verbatim, e.g.,
    `drain_returned_within_timeout: true`).
- **§6 Harness primitives** — what implementations MUST provide to satisfy each directive
  class. Organized by primitive type:
  - In-memory observers (record, accumulate, raise, slow/paced via `sleep_ms_per_event`).
  - In-memory session store + checkpointer (single-process, ephemeral, mirroring the
    bundled-minimum pattern from sessions §5.5 and pipeline-utilities §10.13).
  - OTel collector capture (an in-memory OTel exporter that records emitted spans for
    structured assertion).
  - Langfuse mock (an in-memory Langfuse client wrapper that records emitted
    traces/observations for structured assertion).
  - Suspend / resume wiring (the `suspend_with_descriptor` directive on a node compiles to a
    real `suspend()` call from the synthetic node body; the resume invocation calls the
    real `invoke(resume_invocation=..., signal_payload=...)` API).
  - Drain wiring (the `drain` and `invoke_drain_events_for` directives invoke the real
    `drain()` / `drain_events_for()` operations on the compiled graph).
  - Middleware wiring (the `wrap_with_middleware` directive wraps the node with a real
    middleware that runs pre / post code recording markers into a state log field).
- **§7 Nondeterminism handling** — enumeration of which orderings are observable but not
  determined by the spec (fan-out instance scheduling, parallel-branches branch scheduling,
  observer event dispatch within one phase), and the rule that fixtures assert on
  invariants (counts, identity-tuple uniqueness, presence of branch_name / fan_out_index
  values) rather than exact event sequences in those cases. References graph-engine §3
  (concurrency exception) and §5 (determinism).
- **§8 Adapter responsibility** — discovery (walking `spec/*/conformance/` for `*.yaml`),
  parsing (per-case translation into native graph-construction calls), execution,
  assertion via the language's idiomatic test framework. Version pinning rule (the adapter
  declares which conformance-adapter version it targets via the implementation's
  package metadata).
- **§9 Errors** — adapter-layer error categories: `fixture_directive_unknown` (adapter
  MUST raise on unrecognized directive; MUST NOT silently skip), `fixture_schema_invalid`
  (structurally broken fixture), `harness_primitive_missing` (a fixture references a
  harness primitive the adapter doesn't provide).
- **§10 Determinism** — the adapter itself is a control-flow layer; it does not perturb
  the determinism of the implementation it exercises (mirrors the same
  control-flow-layer-doesn't-perturb-determinism rule the harness contract establishes per
  proposal 0022 when its capability spec lands).
- **§11 Cross-spec touchpoints** — references every capability whose fixtures contribute
  directives. The directive vocabulary §5 is the authoritative directive enumeration; this
  section is a navigational cross-reference.
- **§12 Out of scope** — explicit non-goals: specific language test-runner integration
  (pytest / vitest / etc. are implementation choices); fixture-authoring tooling (linters,
  generators, scaffolders); schema-validation tooling for the YAML itself; performance
  benchmarking or comparative-conformance reporting between implementations.

### 3. Docs side

A new `docs/conformance.md` ships alongside `docs/governance.md` and `docs/openarmature.md`
as a readable explainer / tutorial. Distinct from the normative `spec/conformance-adapter/spec.md`:

- **Spec text** (normative): exact directive shapes, error categories, MUST/SHOULD/MAY
  language, version pin.
- **Docs page** (informative): why the fixture system exists, end-to-end worked example
  (here's a real fixture, here's what the Python adapter does with it, here's the
  pytest output), how an implementer ships a conformance-passing adapter for a new
  language, the "every proposal that introduces new fixtures adds to the
  conformance-adapter capability" rule, cross-link to the formal capability spec for
  normative details.

The docs page lives in `docs/` (alongside governance.md), NOT in `docs/capabilities/`
(which is reserved for symlinks to spec capability files). Linked from the mkdocs nav at
top level, between "Governance" and "Releasing" (or equivalent slot).

### 4. Existing-content migration

- `spec/graph-engine/conformance/README.md` — its current v0 informal schema content moves
  into the new capability spec's §4. The README slims to a one-line breadcrumb pointing at
  `spec/conformance-adapter/spec.md`.
- `docs/governance.md` §"Conformance tests" — extends to cross-reference the new capability
  spec as the normative source. The §"Conformance tests" prose stays (overview is useful
  navigation); a paragraph appended pointing at the capability spec for directive details
  and adapter requirements.

### 5. Versioning

**MINOR bump (pre-1.0).** Documentary and additive only:

- New capability spec at `spec/conformance-adapter/spec.md` ratifying the existing
  directive vocabulary. No behavior change — every existing fixture continues to pass
  unchanged under any conforming adapter.
- New docs page at `docs/conformance.md`.
- One symlink under `docs/capabilities/conformance-adapter.md` → `../../spec/conformance-adapter/spec.md`
  per the established docs-side capability-page pattern.
- `spec/graph-engine/conformance/README.md` slimmed (content moves; lookup pointer remains).
- `docs/governance.md` §"Conformance tests" extended with a cross-ref paragraph.

The conformance-adapter capability ships at v0.X.0 (matching the spec version at acceptance
time). Future proposals that add new directives bump the capability's effective version in
the same way other capabilities track versions (the proposal's *Conformance test impact*
section enumerates the new directives; the spec's §5 sub-sections gain entries; the
History line records the addition).

## Conformance test impact

**No conformance fixtures for the conformance-adapter capability itself.** The capability
defines the YAML schema and directive vocabulary; its own correctness is validated by
every OTHER capability's fixtures passing. A meta-conformance suite that exercises the
directive vocabulary in isolation would be redundant — every per-capability fixture
already exercises the directive vocabulary; meta-coverage adds no orthogonal verification
beyond what the existing per-capability fixture suites already provide.

**Existing fixtures unchanged.** The ratification is descriptive — no fixture YAML files
are modified by this proposal. Implementations passing the conformance suite today continue
to pass it under the new capability spec.

## Alternatives considered

**1. Document the directive vocabulary in `docs/governance.md` (no separate capability).**
Extend the existing §"Conformance tests" section with the directive enumeration; skip
creating a new capability.

Rejected: governance.md is meta-content (process rules, versioning policy, multi-language
consistency rules); the directive vocabulary is normative behavioral content (each directive
specifies runtime behavior an adapter MUST honor). The two have different stability profiles
(governance changes are rare; directive vocabulary changes every proposal). Mixing them
makes it harder to version each appropriately and harder for adapter authors to find the
authoritative directive list.

**2. Ship as a top-level spec doc (`spec/CONFORMANCE.md`) rather than a capability.**
Treat the fixture system as repo-level infrastructure outside the capability framework.

Rejected: the directive vocabulary IS specifying behavior that adapters must implement; it
fits the capability model exactly. The other capabilities (graph-engine, sessions, etc.) define
behaviors of the framework; the conformance-adapter capability defines behaviors of the
language adapters that exercise the framework. Both are behavioral specifications targeting
implementations; both deserve the same versioning, history, and conformance-via-Accept
discipline.

**3. Redesign the directive shapes to a cleaner v1 schema before ratifying.** Take this
proposal as a chance to clean up the directives that accreted ad-hoc (e.g., consolidate
overlapping shapes like `update` vs `update_pure` vs `update_from_field` into a single
`update` directive with parameters; rationalize the assertion-shape naming conventions).

Rejected for v1, deferred to a possible v2: each existing directive landed via a proposal
that exercised concrete behavioral coverage; the directive shape was approved alongside the
fixture additions. Redesigning would invalidate that work and require re-approving every
existing fixture against the new shape — significant churn for marginal cleanliness gain.
The ratification approach freezes the current vocabulary as v0.X.0 and lets future proposals
either continue the established pattern OR open a cleanup proposal targeting specific
directive consolidations once the v0.X.0 surface stabilizes.

**4. Defer the proposal until cross-language demand surfaces (when openarmature-typescript
starts).** Argue that the Python adapter remains the de facto source of truth until a
second language adapter actually needs to be built.

Rejected: the documentation gap exists now; deferring it makes the eventual TS adapter
work harder (more accreted directives to reverse-engineer) and pushes the cross-impl
consistency burden onto the Python implementer (who would have to document the directives
ad-hoc for the TS implementer). Documenting now, while the vocabulary is fresh in mind, is
cheaper than documenting later.

## Open questions

- **Whether the conformance-adapter capability includes the OTel and Langfuse mock harness
  primitives in its v1 surface, or leaves them to a follow-on proposal.** The current
  conformance directories include observability fixtures that exercise OTel span emission
  and Langfuse trace/observation emission; the Python adapter ships in-memory mocks for
  both. Including them in v1 ratifies the existing pattern; deferring them shrinks the v1
  surface but leaves the existing mocks under-specified. Lean: include in v1 (the Python
  implementation already has them; documenting matches reality).
- **Whether the `conformance_version` per-fixture pin is enforced at parse time.** A fixture
  authored against conformance-adapter v0.5.0 declares
  `conformance_version: "0.5.0"`. An adapter targeting conformance-adapter v0.7.0 SHOULD
  accept the fixture (additive directive vocabulary is backwards-compatible). What
  happens when the adapter targets v0.5.0 and the fixture declares v0.7.0? The adapter
  MUST raise per the version-mismatch rule, OR the adapter SHOULD warn-and-attempt
  (lenient). Lean: MUST raise (strict version-pin matches OA's general "no silent
  fallback" disposition).
- **Whether the v1 ratification enumerates EVERY current directive or a subset.** Some
  directives appear in only one fixture (e.g., `update_from_field` with `multiplier` —
  appears in fan-out fixtures specifically). Enumerating every such directive bloats the
  spec. Lean: enumerate every directive currently in use; treat the comprehensive
  enumeration as the load-bearing value of the capability (the whole point is to make
  the directive vocabulary discoverable and pinned).
- **Naming alternatives for the capability.** "Conformance adapter" was selected over
  "conformance protocol", "fixture protocol", "conformance fixtures", and bare
  "conformance" for the reasons in the proposal's pre-PR design discussion. Re-opening
  if reviewers find a meaningfully better fit.

## Out of scope

- **Per-language adapter implementations.** This proposal specifies the contract; concrete
  Python / TypeScript / future-language adapters are sibling-implementation work and ship
  separately in their respective implementation repositories.
- **Fixture-authoring tooling.** Linters that check fixture YAML against the schema;
  scaffolders that generate fixture stubs from spec sections; visualization tools that
  render the directive vocabulary as documentation — all useful, all out of scope for v1.
- **Performance benchmarking or comparative-conformance reporting.** Whether implementation
  A passes fixture N in 50ms and implementation B passes it in 200ms is not a conformance
  concern (performance is implementation-specific and not specified at the behavioral
  layer).
- **Redesigning the directive vocabulary.** v1 ratifies what exists. A follow-on cleanup
  proposal MAY consolidate overlapping directives if real demand surfaces, but is not
  bundled here (per alternative 3).
- **Cross-capability test orchestration.** Whether the adapter runs fixtures in a specific
  order, parallelizes across capabilities, or applies tagging / filtering — all
  implementation choices that adapters MAY surface via their host test runner
  (pytest markers, vitest tags, etc.), not normative in the spec.
