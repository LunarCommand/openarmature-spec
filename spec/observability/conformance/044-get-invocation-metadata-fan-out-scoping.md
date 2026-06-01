# 044 — `get_invocation_metadata()` per-async-context scoping under fan-out

Verifies §3.4's *Read access* sibling-instance isolation rule. A fan-out's per-instance writes
are isolated to each instance's contextvar copy; sibling instances' writes are invisible to each
other's reads, and the outermost serial context after the fan-out joins sees neither instance's
write (the per-instance contexts do NOT propagate back across the join).

**Spec sections exercised:**

- §3.4 *Read access* — per-async-context scoping; sibling-instance writes invisible across the
  fan-out boundary.
- §3.4 *Per-async-context scoping* — copy-on-write at dispatch; the read surface mirrors the
  write surface.

**Cases:**

1. `fan_out_per_instance_read_isolation_and_outermost_serial_view` — Fan-out over two items.
   Each instance writes `item_id` with the per-item value, then reads
   `get_invocation_metadata()` into a per-instance result. After the fan-out joins, an
   outermost-serial node reads `get_invocation_metadata()` into a separate state field.

   Asserts: instance #0's captured metadata contains `item_id: "A"` and NOT `"B"`; instance
   #1's captured metadata contains `item_id: "B"` and NOT `"A"`; the outermost-serial node's
   captured metadata contains neither `item_id` value (the outermost view is the
   pre-fan-out baseline).

**What passes:**

- Each instance reads only its own `item_id` (per-instance contextvar copy isolated).
- The outermost-serial node sees neither instance's `item_id` (per-instance copies do not flow
  back across the join).
- The caller baseline (`tenantId`) is visible everywhere.

**What fails:**

- Instance #0's read sees instance #1's `item_id` (sibling-instance writes leaked — copy-on-
  write boundary breached).
- The outermost-serial read sees either instance's `item_id` (per-instance contexts propagated
  back, breaking the §3.4 scoping rule).
- The implementation layered a separate global aggregator structure to make sibling writes
  visible across the join — explicitly forbidden by §3.4's *Read access* paragraph.
