# 012 — Session Observability Propagation

Verifies §11.1: when an invocation is bound to a session, `openarmature.session_id` appears as
a §5.6 cross-cutting span attribute on every span and as a §7 log-record field on every log
record. The attribute is absent when the invocation is not session-bound, and `session_id` is
NOT a field on the §6 NodeEvent — it propagates through the ambient invocation context (like
`correlation_id` and `invocation_id`).

**Spec sections exercised:**

- sessions §3 — `session_id` propagates via the ambient invocation context, readable from
  anywhere within the invocation's async call tree (mirrors observability §3.1's correlation_id
  propagation contract).
- observability §5.6 — `openarmature.session_id` is a cross-cutting span attribute (every span)
  when the invocation is session-bound.
- observability §7 — `session_id` is a log-record field on every log record emitted during a
  session-bound invocation.
- graph-engine §6 — NodeEvent does NOT carry `session_id`; observers that need it read the
  ambient context.

**Cases:**

1. `session_id_on_every_span_and_log_record` — session-bound invoke; every span and every log
   record carries the session id.
2. `no_session_id_attribute_when_invocation_not_session_bound` — non-session invoke; the
   `openarmature.session_id` attribute and `session_id` log field are absent.

**What passes:**

- Every span across the trace tree carries `openarmature.session_id="s12"` (case 1).
- Every log record carries `session_id="s12"` (case 1).
- `openarmature.session_id` is absent from spans and log records when no `session_id` is
  supplied (case 2).
- The NodeEvent delivered to observers does NOT contain a `session_id` field.

**What fails:**

- A span (root, node, or otherwise) is missing `openarmature.session_id` despite session
  binding.
- A log record is missing `session_id`.
- The non-session invoke emits the attribute anyway.
- The implementation adds `session_id` as a field on NodeEvent (contradicts the §3 / §11.1
  propagation model).
