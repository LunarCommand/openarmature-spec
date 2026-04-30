# 003 — OTel Error Status

Verifies §4.2 status mapping for `node_exception`: the failing node's span has status `ERROR`
with the §4 category as description; the exception is recorded on the span; the invocation span
inherits ERROR via standard OTel parent-status-from-failed-children propagation.

**Spec sections exercised:**

- §4.2 Status mapping — `node_exception` row.
- §5.2 Node span attributes — `openarmature.error.category` populated when the node fails.

**What passes:**

- `ok_node`'s span is OK.
- `fail_node`'s span is ERROR with description `"node_exception"`.
- An OTel exception event is recorded on `fail_node`'s span (the exception's class and message).
- `fail_node`'s `openarmature.error.category` attribute is `"node_exception"`.
- The invocation span has status ERROR (parent inheritance from the failed child).

**What fails:**

- `fail_node`'s span is OK despite the raise.
- The exception event is missing from the span.
- `openarmature.error.category` is missing or wrong.
- The invocation span ends OK despite a failed child (broken OTel propagation).
