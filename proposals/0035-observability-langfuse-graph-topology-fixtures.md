# 0035: Observability — Langfuse §8.3 Graph-Topology Conformance Coverage

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-27
- **Targets:** spec/observability/conformance/ (three new fixture pairs); no normative spec-text changes
- **Related:** 0031 (observability Langfuse mapping — defined the §8 mapping including §8.3 observation-type rows and §8.5 detached-trace mode); 0034 (observability caller-supplied invocation metadata — extended §8.4.1/§8.4.2 with metadata propagation)
- **Supersedes:**

## Summary

Add three new conformance fixtures to `spec/observability/conformance/`
exercising the §8.3 *Observation-type mapping* rows and §8.5 *Detached
trace mode* Langfuse-specific rules that v0.23.0 (proposal 0031)
shipped normatively but only partially fixtured. Specifically:

- **Subgraph Span observation hierarchy** — §8.3 row 3 (Subgraph span
  → Span observation, child of the surrounding parent Span, containing
  the subgraph's nested node Span observations).
- **Fan-out node dispatch + per-instance Span observations
  (non-detached)** — §8.3 rows 4-5 (Fan-out node span → Span
  observation as dispatch container; Fan-out instance span → child
  Span observation of the dispatch).
- **Detached trace mode** — §8.5 Langfuse-specific rules for detached
  subgraph and detached fan-out: each detached child mints its own
  Langfuse Trace; the parent's dispatch observation carries
  `metadata.detached_child_trace_ids` (string array, one entry per
  detached child); `correlation_id` is invocation-scoped and shared
  across all detached Traces and the parent Trace.

This proposal is pure conformance-coverage extension. **No normative
spec-text changes.** The v0.23.0 prose for these mapping rows already
specifies the expected behavior; the fixtures harden cross-impl
parity by making the contract testable rather than re-derivable from
prose.

## Motivation

When proposal 0031 shipped the Langfuse mapping (v0.23.0), the
accompanying conformance fixtures (`022-langfuse-basic-trace`,
`023-langfuse-generation-rendering`,
`024-langfuse-prompt-linkage`) exercised the linear-graph subset of
the §8.3 mapping table:

- Invocation → Trace (row 1)
- Node → Span observation (row 2)
- LLM provider → Generation observation (row 6)
- Retry attempts (row 7, implicit in 023)

Three rows of the §8.3 table were specified normatively but not
fixtured: Subgraph (row 3), Fan-out node (row 4), and Fan-out instance
(row 5). The §8.5 detached-trace-mode Langfuse rules were specified
in prose but had no fixture asserting the `detached_child_trace_ids`
metadata-array shape or the cross-trace `correlation_id` consistency
for the Langfuse mapping.

Each row has a matching OTel-side fixture asserting the equivalent
OTel mapping:

| §8.3 / §8.5 row              | OTel fixture                              |
|------------------------------|-------------------------------------------|
| Subgraph                     | `002-otel-subgraph-hierarchy`             |
| Fan-out node + instance      | `006-otel-fan-out-instance-attribution`   |
| Detached subgraph + fan-out  | `008-otel-detached-trace-mode`            |

The OTel side has cross-impl test coverage for these graph
topologies; the Langfuse side has not. The asymmetry creates two
risks:

1. **Cross-impl drift for future implementations.** When a second
   implementation (e.g., openarmature-typescript) adds a Langfuse
   observer, its subgraph / fan-out / detached behavior has no
   fixtures to validate against — it would re-derive the parenting
   rules and metadata-array shape from §8.3 / §8.5 prose. Drift from
   the reference implementation is likely.
2. **Implementation-side regression risk.** Future changes to any
   implementation's dispatch-synthesis logic for Langfuse observations
   pass local unit tests but could drift from the spec contract
   without any cross-impl signal.

Adding fixture coverage for the three missing topologies closes both
risks. The cost is small — three new fixture pairs (YAML + MD
sidecar) — and the work is mechanical: the harness primitives for
subgraph dispatch, fan-out dispatch, and detached-trace mode all
exist in the conformance test framework (used by fixtures 002, 006,
and 008 respectively). The Langfuse-specific assertions layer onto
those primitives the way 022-024 already layer Langfuse assertions
onto the linear-graph harness primitives used by 001 / 003 / 004 /
007.

## Detailed design

### Fixture 1 — `031-langfuse-subgraph-span-hierarchy`

**Mirrors:** `002-otel-subgraph-hierarchy`

**Graph topology:** outer graph with three nodes (`outer_in`,
`outer_sub`, `outer_out`); `outer_sub` is a subgraph dispatch to an
`inner` subgraph containing two nodes (`inner_x`, `inner_y`).

**Asserts the §8.3 row 3 mapping:**

- The invocation maps to one Langfuse Trace.
- `outer_in` and `outer_out` map to Span observations directly under
  the Trace.
- `outer_sub` maps to a Span observation directly under the Trace
  (the subgraph dispatch container).
- `inner_x` and `inner_y` map to Span observations under
  `outer_sub` (subgraph wrapper contains the inner nodes).

**Langfuse-specific assertions in addition to the OTel parenting
shape:**

- `trace.id` matches the `openarmature.invocation_id` per §8.4.1.
- `observation.name` of each Span observation matches the OA span
  name per §8.4.2.
- `observation.metadata.namespace` reflects the subgraph nesting per
  §8.4.2 (e.g., `["outer_sub", "inner_x"]`).
- `observation.metadata.subgraph_name` is set on `inner_x` and
  `inner_y` per §8.4.2.

### Fixture 2 — `032-langfuse-fan-out-per-instance-spans`

**Mirrors:** `006-otel-fan-out-instance-attribution`

**Graph topology:** single fan-out node (`process`) dispatching three
instances over a one-node `worker` subgraph (the `compute` node),
non-detached, `concurrency: 2`, `error_policy: collect`.

**Asserts the §8.3 rows 4-5 mappings:**

- The fan-out node `process` maps to a Span observation under the
  Trace (the dispatch container).
- Each of the three instances maps to a Span observation child of
  the dispatch container (one per instance).
- Each instance's nested `compute` node maps to a Span observation
  child of its instance Span.

**Langfuse-specific assertions:**

- `process` observation's `metadata.fan_out_item_count` = 3,
  `metadata.fan_out_concurrency` = 2, `metadata.fan_out_error_policy`
  = `"collect"` per §8.4.2 fan-out-node-specific keys.
- Each instance observation's `metadata.fan_out_index` is unique in
  `0..2` and `metadata.fan_out_parent_node_name` = `"process"` per
  §8.4.2 fan-out-instance-specific keys.

### Fixture 3 — `033-langfuse-detached-trace-mode`

**Mirrors:** `008-otel-detached-trace-mode`

Two cases, one per detachment level:

**Case A — `detached_subgraph_two_traces_one_link`:**

Outer graph with a `dispatch` node configured as a detached subgraph
dispatch to a `long_running_workflow` subgraph (single `step` node),
followed by an `after` node back in the parent graph.

Asserts the §8.5 Langfuse-specific rules for detached subgraph:

- The invocation produces two distinct Langfuse Traces (parent + one
  detached).
- The parent Trace's `dispatch` Span observation carries
  `metadata.detached_child_trace_ids` = `[<detached_trace_id>]` (a
  string array of length 1) per §8.5.
- The detached Trace contains the subgraph's spans (`long_running_workflow`
  and `step`), NOT the parent Trace.
- Both Traces share the same `metadata.correlation_id` per §8.5.

**Case B — `detached_fan_out_one_trace_per_instance`:**

Single fan-out node (`per_document_scoring`) dispatching three
instances over a `per_doc` subgraph, configured as detached fan-out.

Asserts the §8.5 Langfuse-specific rules for detached fan-out:

- The invocation produces four distinct Langfuse Traces (parent +
  three per-instance).
- The parent Trace's `per_document_scoring` Span observation carries
  `metadata.detached_child_trace_ids` as a three-element string array,
  one entry per instance Trace ID, per §8.5.
- The parent Trace does NOT contain any per-instance spans.
- All four Traces share the same `metadata.correlation_id` per §8.5.

## Spec-text changes

**None.** All four expected behaviors (subgraph parenting, fan-out
dispatch + instance parenting, detached `detached_child_trace_ids`
array, detached `correlation_id` consistency) are already specified
normatively in §8.3 / §8.4 / §8.5 by proposal 0031. This proposal
only adds fixture coverage.

The proposal's CHANGELOG entry will note this is a coverage extension
to be clear that no observable contract changes for existing
implementations of §8.3 / §8.5.

## Conformance fixtures

Three new pairs under `spec/observability/conformance/`:

- `031-langfuse-subgraph-span-hierarchy.yaml` + `.md`
- `032-langfuse-fan-out-per-instance-spans.yaml` + `.md`
- `033-langfuse-detached-trace-mode.yaml` + `.md`

The conformance harness primitives required (subgraph dispatch,
fan-out dispatch with concurrency/error-policy config, `detached_subgraphs`,
`detached_fan_outs`) are already exercised by the OTel-side fixtures
this set mirrors. No new harness DSL extensions are required.

## Versioning

**Patch bump: v0.26.1.** Pure conformance-coverage extension; no
normative spec-text changes, no public-type changes, no behavior
changes for any compliant implementation of the §8 Langfuse mapping
as already specified.

Implementations that pass the v0.23.0 (0031) Langfuse fixtures
without internally exercising the additional graph topologies covered
here MAY have latent bugs in their subgraph / fan-out / detached
Langfuse mappings — the new fixtures will surface those, and that
surfacing is intentional. The "no behavior change" framing applies
to *correct* implementations of the v0.23.0 spec; the fixtures harden
the contract that was always there.

## Backwards compatibility

No breaking changes. Existing fixtures (022-024) continue to apply
unchanged. The new fixtures are additive; an implementation passing
022-024 and the three new fixtures conforms to the full §8 Langfuse
mapping as specified by 0031.

## Open questions

None at draft time. The mapping rows and detached-trace rules being
fixtured are normatively specified in v0.23.0; the fixtures simply
exercise them. The fixture YAML shapes mirror their OTel siblings
(002 / 006 / 008) where applicable, so harness conventions are
already established.
