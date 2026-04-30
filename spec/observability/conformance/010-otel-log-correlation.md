# 010 — Log Correlation via OTel Logs Bridge

Verifies §7 log correlation: log records emitted during an invocation carry the active span's
`trace_id`/`span_id` (via the OTel Logs Bridge) and the invocation-scoped
`openarmature.correlation_id`. Detached trace mode (§4.4) changes the trace context for logs
emitted inside the detached span tree — but the correlation_id is invocation-scoped and
flows unchanged.

**Spec sections exercised:**

- §7 Log correlation — required fields on every log record; OTel-native trace-log linkage.
- §7 Detached trace mode interaction — log records inside a detached subgraph carry the
  detached trace's `trace_id`, not the parent's. `correlation_id` is unchanged.

**Cases:**

1. `log_records_carry_trace_span_correlation_ids` — two nodes each emit a log. Both records
   share the same `trace_id` (single trace) but have different `span_id` values (each emitted
   under its own node's active span). Both carry the caller-supplied correlation_id verbatim.
2. `detached_subgraph_log_uses_detached_trace_id_keeps_correlation_id` — outer node emits
   a log; outer dispatches a detached subgraph; inner node emits a log. The two log records
   have DIFFERENT `trace_id` values (parent trace vs. detached trace) but the SAME
   `correlation_id`.

**What passes:**

- Each log record has populated `trace_id` and `span_id` matching the active span at emission
  time.
- Each log record has `openarmature.correlation_id` matching the invocation's correlation_id.
- Case 2: the detached-subgraph-internal log's `trace_id` matches the detached trace, NOT the
  parent.

**What fails:**

- Log records missing `trace_id`/`span_id` — the OTel Logs Bridge wasn't wired up; users
  cannot pivot from a log line to the surrounding trace.
- Log records missing `openarmature.correlation_id` — the cross-backend pivot is broken; a
  user reading logs in HyperDX cannot find the matching Langfuse trace.
- Case 2: detached-subgraph log carries the parent's trace_id — the trace context wasn't
  switched to the detached trace inside the detached span tree.
- Case 2: detached-subgraph log carries a different correlation_id — the correlation_id was
  treated as trace-scoped instead of invocation-scoped.
