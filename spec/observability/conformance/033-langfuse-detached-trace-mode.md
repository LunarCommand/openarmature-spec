# 033 — Langfuse Detached Trace Mode

Verifies §8.5 *Detached trace mode* (Langfuse-specific rules) for both detachment levels:
per-subgraph and per-fan-out. Each detached child mints its own Langfuse Trace (new
`trace.id`); the parent's dispatch Span observation carries
`metadata.detached_child_trace_ids` — a string array, one entry per detached child — as
the Langfuse-native cross-trace reference. `correlation_id` is invocation-scoped per
§3 / §8.5 and shared across all detached Traces and the parent Trace, so callers can
filter all observations in the invocation by a single `correlation_id` query in the
Langfuse UI without first finding the related Traces.

Mirrors the OTel-side fixture `008-otel-detached-trace-mode` one-to-one in graph
topology; the assertion surface differs because Langfuse expresses cross-trace linkage
as a `metadata.detached_child_trace_ids` array on the parent's dispatch observation
rather than as OTel-native Links between span contexts.

**Spec sections exercised:**

- §4.4 — Detached trace mode (opt-in per subgraph or per fan-out node).
- §8.5 — Langfuse-specific detached-mode rules: separate Trace per detached child;
  parent's dispatch observation carries `metadata.detached_child_trace_ids` (string
  array, one entry per detached child); `correlation_id` is invocation-scoped and
  shared across all Traces in the invocation.
- §3 — Cross-backend correlation ID flows through detached subgraphs and fan-outs
  unchanged.

**Cases:**

1. `detached_subgraph_two_traces_one_child_id` — `detached_subgraphs:
   ["long_running_workflow"]`. The parent invocation produces one Langfuse Trace; the
   subgraph dispatch produces a second Trace. The parent's `dispatch` Span observation
   carries `metadata.detached_child_trace_ids` with exactly one entry — the detached
   Trace's id. The `correlation_id` is identical on both Traces.
2. `detached_fan_out_one_trace_per_instance` — `detached_fan_outs:
   ["per_document_scoring"]` with three items. The parent Trace contains only the
   fan-out node's dispatch Span observation; the dispatch observation carries
   `metadata.detached_child_trace_ids` with three entries (one per per-instance Trace).
   Three additional Traces are minted (one per instance), all four Traces share the
   same `correlation_id`.

**What passes:**

- Distinct Trace ids between parent and detached Traces.
- Correct `metadata.detached_child_trace_ids` count on the parent's dispatch
  observation (1 for case 1, 3 for case 2).
- No detached-side observations appear inside the parent Trace.
- `correlation_id` is identical across all Traces in the invocation (both on Trace
  metadata and on every Observation metadata).

**What fails:**

- Detached Trace shares the parent's `trace.id` — detachment didn't actually create a
  new Langfuse Trace.
- Parent's dispatch observation has no `metadata.detached_child_trace_ids` — the
  trace-pivot reference is broken in the Langfuse UI.
- Detached subgraph's observations appear as children of the parent's invocation /
  dispatch observation — the detachment was config-only, not behavioral.
- Case 2: only one detached Trace produced for the whole fan-out (instances share a
  Trace) — detached fan-out semantics demand one Trace per instance.
- `correlation_id` differs across Traces — caller can no longer pivot between
  observations via the cross-cutting correlation key.
- `metadata.detached_child_trace_ids` is a single string rather than an array, or its
  entries don't match the minted detached Trace ids — the array shape is the
  spec-normative form.
