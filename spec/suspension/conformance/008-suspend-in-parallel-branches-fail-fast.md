# 008 — Suspend inside parallel-branches (fail_fast)

Peer to fixture 006 (fan-out fail_fast). Under
`error_policy="fail_fast"` (the default), one parallel-branches branch
calling `suspend()` suspends the entire parallel-branches node at the
outer-graph level. Sibling branches are cancelled. The descriptor
bubbles up with `branch_name` annotated in `metadata`.

**Spec sections exercised:**

- §8.3 — parallel-branches composition under `fail_fast`: suspension
  propagates, siblings cancel, descriptor carries `branch_name`.

**What passes:**

- Initial invoke returns suspended with `suspending_node = dispatcher`
  (the outer parallel-branches node).
- Descriptor's metadata includes both caller-supplied keys
  (`kind: "approval"`) AND the engine-annotated `branch_name: "alpha"`.
- The beta branch's update did NOT apply — it was cancelled.

**What fails:**

- Beta's update applied (`b_result == 99`) — would mean cancellation
  on suspend was not honored under `fail_fast`.
- The descriptor's metadata is missing `branch_name` — would mean the
  engine did not annotate the bubbled descriptor.
