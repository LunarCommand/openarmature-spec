# 063 — Failure-isolation middleware: default predicate catches bare exceptions

Verifies §6.3's default `predicate` (always-true) catches exceptions that don't carry a
category, AND verifies the `caught_exception` field's null-category handling per §6.3's
*Observability* paragraph: "When the caught exception does not carry a category (e.g., a bare
`ValueError`), the category field is `null` and the message captures the exception's
`str(exc)` form."

**Spec sections exercised:**

- §6.3 — Default `predicate` behavior (always-true; catches all `Exception`).
- §6.3 *Observability* — `caught_exception.category = null` for non-categorized exceptions;
  message captures the `str(exc)` form.

**Cases:**

1. `default_predicate_catches_bare_value_error` — A node wrapped with
   `FailureIsolationMiddleware(degraded_update={...}, event_name="...")` — `predicate` is not
   supplied (default always-true). The node raises a bare `ValueError("bad input")` — an
   exception that does NOT carry a §7 or §4 category. Asserts:
   - The middleware catches the exception (default predicate accepts it).
   - The framework-emitted failure-isolation event's `caught_exception.category` is `null`.
   - The framework-emitted event's `caught_exception.message` captures the exception's
     `str(exc)` form (`"bad input"`).
   - The degraded return reaches the engine.

**What passes:**

- Default predicate catches the bare `ValueError`.
- `caught_exception.category = null` (no category to surface).
- `caught_exception.message = "bad input"`.
- Engine sees the degraded return.

**What fails:**

- The bare `ValueError` propagates uncaught — default predicate was not always-true (rejects
  non-categorized exceptions incorrectly).
- `caught_exception.category` carries a fabricated value (e.g., `"unknown"`, `"value_error"`)
  rather than `null` — the spec mandates `null` for non-categorized exceptions.
- `caught_exception.message` is empty / null / a different value — the `str(exc)` form MUST
  be captured.
