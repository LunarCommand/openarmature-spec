# 046 — `get_invocation_metadata()` outside an active invocation

Verifies §3.4's *Read access* outside-invocation behavior — calling `get_invocation_metadata()`
when there is no active invocation context returns an empty immutable mapping, with no
exception raised. Mirrors `set_invocation_metadata`'s silent-no-op-outside-scope rule for
consumer code that may run inside or outside a graph.

**Spec sections exercised:**

- §3.4 *Read access* — *Outside invocation* paragraph; silent no-op returning an empty mapping.

**Cases:**

1. `get_invocation_metadata_outside_active_invocation_returns_empty` — The harness invokes
   `openarmature.observability.get_invocation_metadata()` from code that is NOT executing
   inside a graph node (e.g., a test driver, a top-level setup script, a separate utility
   function). Asserts the call returns an immutable empty mapping and no exception is raised.

**Harness extensions:** the harness MUST support invoking `get_invocation_metadata()` outside
the graph-execution context as a top-level operation. This case is unique among the §3.4
fixtures in that it does not run a graph; the fixture's "test" is a single direct call to the
spec-public read primitive.

**What passes:**

- The call returns an empty immutable mapping.
- No exception is raised.
- The returned mapping is the same immutable shape as in-invocation reads (the type contract
  is consistent across in-scope / out-of-scope calls).

**What fails:**

- The call raises (e.g., a `RuntimeError("no active invocation")` or similar) — the spec
  requires silent no-op.
- The call returns `None` instead of an empty mapping — the return type contract MUST be the
  immutable-mapping shape on every call path.
- The call returns a mutable mapping — the immutability contract applies uniformly.
