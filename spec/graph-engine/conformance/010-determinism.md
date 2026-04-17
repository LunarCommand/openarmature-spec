# 010 — Determinism

Verifies the engine's determinism guarantee: same initial state, same node implementations, same edge
functions → same final state and same observed node-execution order across runs.

**Spec sections exercised:**
- §5 Determinism — "Given the same initial state, the same node implementations, and the same edge
  functions, a graph run MUST produce the same final state and the same observed node-execution order."

**Test protocol:**
Adapters MUST execute this fixture `run_count` times (currently 2) and assert that every run's
`final_state` and `execution_order` are deeply equal — both to the expected reference values and to every
other run's results.

**What passes:**
- Both runs produce `final_state == {counter: 3, log: ["a", "b", "c"]}`.
- Both runs observe execution order `[a, b, c]`.

**What fails:**
- Any variance in `final_state` across runs.
- Any variance in `execution_order` across runs.
- Order-sensitive structures (lists) differing between runs.

**Scope note:**
This fixture verifies *engine* determinism only. Nondeterminism in node implementations (wall-clock time,
randomness, I/O) is explicitly out of scope per §5; the nodes here are deliberately pure.
