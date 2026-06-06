# 011 — Stateless mode skips session machinery (§3.0 + §8.1)

A stateless-mode harness invokes a graph without resolving any
session_id and without invoking the SessionStore — even when a
SessionStore is registered on the compiled graph. The §3.0 dispatch
path is the only path stateless-mode harnesses use; the §8.1
composition rule applies (engine MUST NOT invoke SessionStore when
session_id is absent).

**Spec sections exercised:**

- harness §2 — stateless-mode definition
- harness §3.0 — stateless transmission path
- harness §3.4 — path classification (stateless mode uses §3.0
  exclusively)
- harness §8.1 — stateless-mode sessions composition rule
- sessions §3 — engine's `session_id` omit-and-skip rule

**What passes:**

- Harness classifies the transmission via §3.0 (not §3.1 / §3.2 /
  §3.3).
- Harness does NOT resolve any session_id.
- The engine's call site receives no session_id argument.
- The registered SessionStore receives ZERO load AND ZERO save calls
  (verified via the synthetic in-memory store's call counter).
- Final state matches the simple `v: 42` outcome.

**What fails:**

- Harness assigns or generates a session_id — would mean stateless-
  mode is leaking sessioned-mode behavior.
- SessionStore.load() is called even though no session_id was passed
  — would mean the sessions §3 omit-and-skip rule is broken in the
  engine.
- SessionStore.save() is called at invoke exit — same issue.

**Notes:**

- This fixture validates the load-bearing claim of Q6 in proposal
  0022: stateless mode is first-class, not a degenerate sessioned
  case. The SessionStore is registered (so the same compiled graph
  could be reused by a sessioned-mode harness) but the stateless
  harness keeps it inert across the entire turn.
