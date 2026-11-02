# 063 — Failure-isolation middleware: default predicate catches bare exceptions

Verifies that §6.3's default `predicate` (always true) catches exceptions that don't carry a
category, and the `caught_exception` field's null-category handling in §6.3's *Observability*
paragraph: for a caught exception that carries no category, the category field is `null` and the
message is the exception's message.

**Spec sections exercised:**

- §6.3: the default `predicate` behavior (always true; catches every exception).
- §6.3 *Observability*: `caught_exception.category = null` for an uncategorized exception, and
  the message is the exception's message.

**Cases:**

1. `default_predicate_catches_uncategorized_error`: a node wrapped with failure-isolation
   middleware that sets `degraded_update` and `event_name` and supplies no `predicate`, so the
   default applies. The node raises an uncategorized error with the message `"bad input"`, one
   that does NOT carry a §7 or §4 category. Asserts:
   - The middleware catches the exception (the default predicate accepts it).
   - The framework-emitted failure-isolation event's `caught_exception.category` is `null`.
   - The framework-emitted event's `caught_exception.message` is the exception's message
     (`"bad input"`).
   - The degraded return reaches the engine.

**What passes:**

- The default predicate catches the uncategorized error.
- `caught_exception.category = null` (no category to surface).
- `caught_exception.message = "bad input"`.
- Engine sees the degraded return.

**What fails:**

- The uncategorized error propagates uncaught: the default predicate was not always true (it
  rejects uncategorized exceptions incorrectly).
- `caught_exception.category` carries a fabricated value (e.g., `"unknown"`, `"value_error"`)
  rather than `null`. The spec mandates `null` for uncategorized exceptions.
- `caught_exception.message` is empty, null or a different value. The exception's message MUST be
  captured.
