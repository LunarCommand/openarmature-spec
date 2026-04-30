# 023 — Fan-Out Empty Input Behavior

Verifies the §9.1 empty-fan-out semantics: default raises `fan_out_empty`; `on_empty: "noop"`
produces a clean no-op; `count_field` records the resolved instance count for programmatic
inspection.

This is the load-bearing test for the "loud by default, opt-in graceful" empty-handling design.

**Spec sections exercised:**

- §9 Configuration — `on_empty` (default `"raise"`) and `count_field` config fields.
- §9.1 Empty fan-out behavior — both `"raise"` and `"noop"` modes.
- New runtime error category `fan_out_empty` (non-transient).

**Cases:**

1. **`default_raises_on_empty_items_field`** — `items_field == []`, no `on_empty` config (default
   `"raise"`). Engine raises `node_exception` with `fan_out_category: fan_out_empty`.
   Recoverable state is the pre-fan-out parent state.
2. **`default_raises_on_count_zero`** — `count` callable returns 0, default `on_empty: raise`.
   Same outcome: `node_exception` with `fan_out_empty`.
3. **`noop_opt_out_with_count_field`** — empty `items_field`, `on_empty: "noop"`, `count_field:
   processed_count`. No raise; `count_field` is written with `0`; downstream node runs.
4. **`count_field_records_actual_count`** — non-empty `items_field` (3 items), `count_field:
   processed_count`. `count_field` is written with `3` after fan-in.

**What passes:**

- Cases 1-2: engine raises `node_exception`; the inner category surfaces as `fan_out_empty`.
- Case 3: no raise; `processed_count == 0`; `downstream_ran == true`; `results` empty.
- Case 4: `processed_count == 3` (matches the items count).

**What fails:**

- Default behavior is silent no-op instead of raising (regression of the new default).
- `on_empty: "noop"` raises anyway (opt-out not honored).
- `count_field` not written despite being configured.
- `count_field` written only when count > 0 (it should always be written when configured).
- `fan_out_empty` is classified as transient and retried by retry middleware (it MUST NOT be —
  empty doesn't auto-resolve via retry).

## Implementation note

The `recoverable_state` on cases 1-2 must reflect the pre-fan-out snapshot. `count_field` is NOT
written when raising — the raise occurs before fan-in, and `recoverable_state` preserves the
prior value (or default if not yet set).
