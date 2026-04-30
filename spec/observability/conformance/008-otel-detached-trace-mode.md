# 008 — Detached Trace Mode

Verifies §4.4 detached trace mode for both detachment levels: per-subgraph and per-fan-out.
A detached subgraph or fan-out gets its OWN OTel `trace_id`; the parent's dispatch span is
opened in the parent trace as usual but carries an OTel `Link` whose target is the new
detached trace's root. Status crosses the boundary via standard link semantics; the §3
correlation_id flows across the boundary unchanged so callers can pivot between the two
traces in any backend that indexes by correlation_id.

**Spec sections exercised:**

- §4.4 Detached trace mode — opt-in per subgraph or per fan-out node.
- §4.4 Composition rules — detached fan-out produces one trace per instance.
- §3 Cross-backend correlation ID — flows through detached subgraphs and fan-outs unchanged.

**Cases:**

1. `detached_subgraph_two_traces_one_link` — `detached_subgraphs: ["long_running_workflow"]`.
   The parent invocation produces one trace; the subgraph produces a second trace. The
   parent's `dispatch` span has exactly one Link targeting the detached trace's root. The
   `correlation_id` is identical on both traces.
2. `detached_fan_out_one_trace_per_instance` — `detached_fan_outs: ["per_document_scoring"]`
   with three items. The parent trace contains only the invocation and fan-out node span; the
   fan-out node span carries three Links, one per instance trace. Three detached traces are
   produced (one per instance), all four traces share the same `correlation_id`.

**What passes:**

- Distinct `trace_id` between parent and detached traces.
- Correct Link count on the parent's dispatch span (1 for case 1, 3 for case 2).
- No detached-side spans appear in the parent trace.
- `correlation_id` is identical across all traces in the invocation.

**What fails:**

- Detached trace shares the parent's `trace_id` — detachment didn't actually create a new
  trace context.
- Dispatch span has no Link to the detached trace — the trace pivot is broken in the UI.
- Detached subgraph's nodes appear as children of the parent's invocation span — the
  detachment was config-only, not behavioral.
- Case 2: only one detached trace produced for the whole fan-out (instances share a trace) —
  detached fan-out semantics demand one trace per instance.
- `correlation_id` differs across the two traces — caller can no longer pivot between them
  via the cross-cutting correlation key.
