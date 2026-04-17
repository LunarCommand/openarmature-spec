# 008 — Routing Error

Verifies that if a conditional edge returns a destination name that is neither a declared node nor `END`, the
engine raises a categorized routing error before invoking any further node.

**Spec sections exercised:**
- §4 Error semantics — "If a conditional edge returns a name that is not a declared node or `END`, the
  engine MUST raise a routing error before invoking any further node."

**What passes:**
- Node `a` runs and updates `v` to `"a"`.
- The conditional edge returns `"ghost"` (undeclared).
- The engine raises a routing error; node `b` never runs.
- Pre-failure state is recoverable from the error and equals `{v: "a"}`.

**What fails:**
- Node `b` runs (engine silently treated `ghost` as `END` or coerced the name).
- Error raised but state at point of failure is not exposed.
- Routing error is caught at compile time (it can't be — the undeclared name is returned by a function at
  runtime; this is a runtime check).
