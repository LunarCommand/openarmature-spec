# 006 — Suspended outcome handling (§5.3)

The harness reads the signal descriptor from the suspended outcome,
registers a signal subscription with the signal coordinator, returns
a suspended-acknowledgment outbound shape, and EXITS without blocking.

**Spec sections exercised:**

- harness §5.3 — suspended outcome handling (four-step requirement)
- harness §6 — signal coordinator (suspend-time subscription
  registration)
- harness §5.3 step 4 (load-bearing) — harness MUST NOT block on
  suspended turns

**What passes:**

- Invoke returns suspended with the expected descriptor.
- Harness reads the descriptor.
- Harness registers a signal subscription with the in-memory signal
  coordinator.
- Outbound shape is "suspended_acknowledgment" (distinct from
  completion / error).
- Harness does NOT block — the next transmission could arrive and be
  handled.

**What fails:**

- Harness blocks on the suspended turn — violates the load-bearing
  §5.3 step 4 rule.
- No subscription registered — would mean the signal coordinator
  can't route the eventual signal back.
- Outbound shape matches completion or error — violates §5.1's
  observability requirement applied to suspended.
