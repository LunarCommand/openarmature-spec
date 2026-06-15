# Middleware

Middleware is OpenArmature's primitive for cross-cutting concerns around node execution —
retry, timing, failure isolation, custom telemetry, anything that wraps the node body without
being part of the node body itself. The normative spec for middleware lives in
[pipeline-utilities §2 *Concepts*](pipeline-utilities.md#2-concepts) (shape, chain semantics,
pre/post phases) and the canonical middleware primitives in
[pipeline-utilities §6 *Canonical middleware*](pipeline-utilities.md#6-canonical-middleware).
This page frames middleware from the spec point of view: the composition model, the
cross-cutting concepts that compose multiple middleware primitives, and the risks that emerge
when composition stacks.

## What middleware is

A middleware is an async callable with the shape:

```
async def middleware(state, next) -> partial_update
```

- `state` — the input state the wrapped node would have received.
- `next` — an async callable that invokes the rest of the chain (subsequent middleware, or
  the wrapped node at the inner end).
- Returns a partial update — the same shape a node returns.

The middleware MAY transform inputs before calling `next`, inspect or replace the returned
partial update, catch exceptions from `next`, call `next` multiple times (retry), or
short-circuit by NOT calling `next` and returning its own partial update. The middleware MUST
NOT mutate `state` or side-effect on engine internals. See
[pipeline-utilities §2](pipeline-utilities.md#2-concepts) for the normative MAY / MUST NOT
lists.

## The composition model

A middleware **chain** is an ordered list of middleware wrapping a single node. The chain
composes outermost-to-innermost: the first entry in the list runs first on the way in, calls
`next(state)` to invoke the second, and so on, with the wrapped node at the innermost end.
Each middleware has a **pre-node phase** (code before `await next(...)`) and a **post-node
phase** (code after `next` returns); a single middleware's pre-phase runs on the way *in* and
its post-phase runs on the way *out*. See [pipeline-utilities
§2](pipeline-utilities.md#2-concepts) for the diagram and full pre/post-phase semantics.

The outermost-to-innermost convention is the design choice behind every composition rule
described below — middleware order in a chain determines what each layer sees, in what state,
and how exceptions propagate.

## Cross-cutting composition concepts

The three canonical middleware primitives — retry (§6.1), timing (§6.2), failure isolation
(§6.3) — and the per-call retry on `LlmProvider.complete()` (llm-provider §7.1) compose in
ways that aren't obvious from any single section alone. The concepts below frame the
composition design at the spec level.

### Two-level retry lanes

Retry primitives operate at two semantic levels in OpenArmature:

- **Per-call retry** ([llm-provider §7.1](llm-provider.md#71-call-level-retry)) — the retry
  unit is a single `complete()` call. Used when a node loops over multiple LLM calls and you
  want to avoid re-running successful calls when a later call's transient fails.
- **Per-node retry** ([pipeline-utilities §6.1
  `RetryMiddleware`](pipeline-utilities.md#61-retry)) — the retry unit is a whole node
  invocation. Used when a node mixes LLM + non-LLM work (DB writes, parses, side effects)
  and you want to re-run the entire body on failure.

The lanes are independent design surfaces, not different implementations of the same idea.
Per-call retry exists because chunked-loop nodes pay a real cost when the whole body re-runs
on a transient failure of call N — calls 1..N-1 are re-executed unnecessarily, and any
non-idempotent side effects between them get duplicated. Per-node retry exists because LLM
calls aren't the only operations that fail transiently; a node that pulls from a database,
prompts an LLM, and writes back the result wants the whole body retryable as a unit.

The two lanes compose: per-call exhausts → propagates → per-node retry catches → re-runs whole
node → per-call budgets reset for each fresh per-node attempt. This is by design, and the
two-level lane separation guidance in [llm-provider
§7.1](llm-provider.md#71-call-level-retry) records the rule explicitly so callers can choose
intentional budgets per layer.

### Outer-to-inner ordering is load-bearing

When composing retry with failure isolation, the order matters. The
[three-piece pattern](pipeline-utilities.md#63-failure-isolation) — outer
`FailureIsolationMiddleware` wrapping inner `RetryMiddleware` wrapping a transient-aware node
body — handles "retry transients, give up gracefully on exhaustion or non-transient errors."
The outer-to-inner order is **not interchangeable**:

- **Retry MUST be inner.** It sees raw transients from the node body and retries them per its
  policy. On exhaustion, it propagates the exception.
- **Failure isolation MUST be outer.** It sees what escapes retry (exhaustion-propagated
  exceptions or any non-transient that re-raised through the node body's `except`) and
  returns the degraded update.

Reversing the order would let the inner isolation catch transients before retry sees them,
defeating retry's purpose entirely. This is why §6.3's composition framing names outer-to-inner
ordering as a load-bearing rule, not a preference.

### Failure isolation beyond the node

The three-piece pattern above places `FailureIsolationMiddleware` at the node level, but the
primitive also composes at two **non-node placements** that wrap a whole subgraph invocation as a
unit:

- **Fan-out instance middleware** ([pipeline-utilities
  §9.7](pipeline-utilities.md#97-instance-middleware)) — wraps each instance's subgraph invocation.
- **Parallel-branch middleware** ([pipeline-utilities
  §11.7](pipeline-utilities.md#117-branch-middleware)) — wraps each branch's subgraph invocation.

At both, the middleware operates in **subgraph space**: the `degraded_update` it returns is a
subgraph-space partial, and the engine projects it to the parent *after* the chain (fan-in for
fan-out; buffer-then-merge for branches). Two behaviors specific to these placements follow.

**Cause fidelity.** At a non-node placement the engine has already wrapped the originating error as
a graph-engine `node_exception` carrier before the isolation middleware catches it. The
framework-emitted failure-isolation event's `caught_exception.category` MUST resolve *through* that
wrapper to the originating cause rather than report the masking `node_exception` — the same
carrier-wrapper unwrap the default retry classifier performs ([pipeline-utilities
§6.3](pipeline-utilities.md#63-failure-isolation), [§6.1](pipeline-utilities.md#61-retry)). At
node-level placement no wrapper is present, so the category is already faithful.

**Degrade contribution.** A degraded instance or branch is a *success* whose contribution **is**
its `degraded_update` — the parent reads projected fields from it by subgraph field name
([§9.3](pipeline-utilities.md#93-per-instance-fan-in) for fan-out,
[§11.7](pipeline-utilities.md#117-branch-middleware) for branches), not from a merge onto the
pre-failure state. What an *incomplete* `degraded_update` does then depends on the collection's
shape:

- **Fan-out is homogeneous** — N instances fill N positional slots in one collection. A degraded
  instance still occupies its slot (it is never dropped), so a `degraded_update` omitting
  `collect_field` would leave a null in the collection. A **static** `degraded_update` that omits it
  is therefore a **compile-time error**
  ([§9.8](pipeline-utilities.md#98-fan-out-degrade-slot-coverage)); a **callable** one (not
  checkable at compile time) yields a graceful null slot at runtime and never raises.
- **Parallel branches are heterogeneous** — each branch contributes its own distinct parent fields,
  with no per-branch slot. A `degraded_update` omitting a projected `outputs` field simply **skips**
  it; the parent keeps its prior / sibling value
  ([§11.7](pipeline-utilities.md#117-branch-middleware)).

The asymmetry is deliberate: a missing contribution is first-class for heterogeneous branches but a
footgun for a homogeneous collection, so the homogeneous slot is the one the spec guards — at
compile time where it can.

### Timing's measurement scope

Timing middleware ([pipeline-utilities §6.2](pipeline-utilities.md#62-timing)) raises a
question composition decides: what time interval do you want to measure?

- **`[timing, retry, node]` — timing wraps retry.** The recorded duration covers all retry
  attempts and backoff sleeps. One `on_complete` call per node, measuring total elapsed time
  the caller waited.
- **`[retry, timing, node]` — retry wraps timing.** `on_complete` fires once per retry
  attempt, each measuring one attempt's duration. The retry layer doesn't see the timing
  layer's invocations.

Both compositions are valid; they answer different questions. End-to-end latency wants the
first; per-attempt latency wants the second. The user's intent dictates the order; the spec
doesn't pin one as canonical.

## Risks of composition

### Multiplicative retry budgets

Stacking per-node retry over a chunked-loop node that itself uses per-call retry multiplies
the worst-case attempt budget. A node configured with `RetryMiddleware(max_attempts=3)` over
a body that issues 5 LLM calls, each with a per-call `retry` record of `max_attempts=3`,
can issue up to **3 × 5 × 3 = 45 LLM calls** in the worst case. The budget multiplies because
each per-node attempt resets the per-call budgets for every call in the loop.

The two-level lane separation is by design (per-call retry is meaningful even when per-node
retry is configured — it avoids re-running successful calls), but stacking both with naive
budgets is a real production pitfall. Authors choosing both lanes pick intentional budgets
per layer; one layer often dominates, and the other can be narrower or absent.

### Order-dependent semantics

Beyond the load-bearing outer-to-inner ordering for failure isolation + retry, several
composition orders change observable behavior:

- Timing's measurement scope (above).
- Inserting custom telemetry middleware inside vs outside the retry layer determines whether
  it observes individual attempts or the final outcome.
- Custom failure-classification middleware placed inside retry sees individual attempt
  exceptions; placed outside, it sees the final exhaustion exception.

The pre/post-phase model from [pipeline-utilities §2](pipeline-utilities.md#2-concepts) makes
the ordering observable — each middleware's position in the chain determines what state and
which exceptions it sees. Ordering is a design decision the user makes per chain, not a
framework default.

### Classifier widening masks bugs

The default transient classifier from [pipeline-utilities
§6.1](pipeline-utilities.md#61-retry) excludes non-transient categories (`provider_invalid_request`,
`structured_output_invalid`, etc.) for a reason — retrying them doesn't help, and it masks
the real fault. Custom classifiers SHOULD widen the default only for categories that are
genuinely transient but not yet enumerated. Aggressive widening is one of the more common
ways a retry stack stops doing what its authors expected.

## See also

- [pipeline-utilities §2 *Concepts*](pipeline-utilities.md#2-concepts) — normative middleware
  shape, chain semantics, pre/post phases.
- [pipeline-utilities §6.1 *Retry*](pipeline-utilities.md#61-retry) — retry middleware,
  default transient classifier, backoff with full jitter.
- [pipeline-utilities §6.2 *Timing*](pipeline-utilities.md#62-timing) — timing middleware,
  measurement scope under composition.
- [pipeline-utilities §6.3 *Failure isolation*](pipeline-utilities.md#63-failure-isolation) —
  failure-isolation middleware, framework-emitted observer event, three-piece composition.
- [llm-provider §7.1 *Call-level retry*](llm-provider.md#71-call-level-retry) — per-call retry
  on `complete()`, two-level lane separation table, common-mistakes list.
