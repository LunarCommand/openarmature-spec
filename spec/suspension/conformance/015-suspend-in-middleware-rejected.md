# 015 — Suspend inside middleware is rejected

Middleware itself MUST NOT call `suspend()`. Attempting to suspend
from middleware (before, around, or after the inner `next()` call)
MUST raise `suspension_in_unsupported_context`. The rationale (§8.4):
attribution ambiguity, pathological composition, gnarly re-entrancy
under `mark_node_completed=False`.

**Spec sections exercised:**

- §8.4 — middleware MUST NOT call `suspend()`.
- §9 — `suspension_in_unsupported_context` error category (case c in
  the enumeration).

**What passes:**

- Invoke errors with `suspension_in_unsupported_context`.
- The wrapped node's update did NOT apply (the
  middleware-suspend attempt intercepted execution before the node
  body ran; the failure surfaces as an error outcome).

**What fails:**

- Invoke returns suspended — would mean the middleware-suspend
  prohibition was not enforced; the engine would attribute the
  suspension to the wrapped node that never ran (the attribution-
  ambiguity case §8.4 calls out).
- A different error category surfaces — would mean the
  middleware-suspend case is miscategorized.
- The wrapped node's update applied — would mean the middleware's
  suspend attempt did not actually intercept execution (the
  middleware ran and the wrapped node ran; spec says middleware MUST
  NOT call suspend at all).
