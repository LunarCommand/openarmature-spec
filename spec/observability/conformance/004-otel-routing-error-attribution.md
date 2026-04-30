# 004 — OTel Routing Error Attribution

Verifies §4.2 routing-error status mapping: a conditional edge returning an undeclared node name
produces a `routing_error` per graph-engine §4. The OTel mapping attributes this to the
**preceding node's span** (not a separate edge span).

**Spec sections exercised:**

- §4.2 Status mapping — `routing_error` row (status applied to the preceding node span).
- §4 — declined edge evaluation spans (no span for the edge function itself).

**What passes:**

- `pick`'s span is ERROR with description `"routing_error"`.
- The exception is recorded on `pick`'s span.
- `openarmature.error.category` on `pick` is `"routing_error"`.
- No spans for `unreachable_a` or `unreachable_b` (those nodes never executed).
- No span for the edge function itself — only the preceding node carries the routing error.

**What fails:**

- A separate "edge" span exists between `pick` and END (the spec does not emit edge spans).
- The routing error attaches to a nonexistent / phantom span instead of the preceding node.
