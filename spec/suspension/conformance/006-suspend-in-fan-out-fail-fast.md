# 006 — Suspend inside fan-out (fail_fast)

Under `error_policy="fail_fast"` (the default), one fan-out instance
calling `suspend()` suspends the entire fan-out node at the
outer-graph level. Sibling instances are cancelled (consistent with
cancellation-on-error under `fail_fast`). The descriptor bubbles up
with `fan_out_index` annotated in `metadata` so the runtime has
attribution for which instance is awaited.

**Spec sections exercised:**

- §8.2 — fan-out composition under `fail_fast`: suspension propagates,
  siblings cancel, descriptor carries `fan_out_index` in metadata.

**What passes:**

- Initial invoke returns suspended with `suspending_node = fan_out`
  (the outer fan-out node, not an inner-instance node).
- The bubbled descriptor's metadata includes both the original
  caller-supplied keys (`kind: "approval"`) AND the engine-annotated
  `fan_out_index: 1`.
- Sibling instances (indices 0 and 2) did NOT produce results — they
  were cancelled, not completed.

**What fails:**

- The fan-out completes normally with only the suspending instance
  excluded — would mean the suspend did not propagate to the fan-out
  node.
- The descriptor's metadata is missing `fan_out_index` — would mean
  the engine did not annotate the bubbled descriptor; runtime cannot
  attribute the awaited instance.
- Sibling instances complete their work — would mean cancellation on
  suspend was not honored under `fail_fast`.
