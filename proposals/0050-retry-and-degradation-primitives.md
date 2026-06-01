# 0050: Retry & Degradation Primitives — Failure-Isolation Middleware + Call-Level Retry

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:** 2026-06-01
- **Targets:** spec/pipeline-utilities/spec.md (new §6.3 *Failure isolation middleware* — third bundled middleware primitive in the §6 set, alongside §6.1 retry middleware and §6.2 timing middleware; covers the catch-and-recover pattern from §2's third MAY bullet with a named shape, lifecycle, and composition pattern); spec/llm-provider/spec.md (§5 `complete()` extended with an optional retry kwarg accepting the same retry configuration record pipeline-utilities §6.1 defines; new §7 *Call-level retry* subsection defining the per-call retry contract — reuses the §6.1 retry configuration record and the §6.1 default transient classifier's category set, with a two-level lane-separation framing distinguishing per-call from per-node retry); spec/observability/spec.md (§5.5 — adds `openarmature.llm.attempt_index` per-attempt span attribute paralleling `openarmature.node.attempt_index`); plus new conformance fixtures covering the failure-isolation middleware contract, call-level retry contract, attempt-index span emission, and the body+retry+isolation three-piece composition pattern.
- **Related:** 0004 (pipeline-utilities middleware — established the §6 middleware framework + the §2 catch-and-recover MAY bullet this proposal packages), 0006 (llm-provider core — established `LlmProvider.complete()` surface this proposal extends), 0024 (LLM span payload + GenAI semconv — established the §5.5 attribute surface this proposal extends with `openarmature.llm.attempt_index`)
- **Supersedes:**

## Summary

Two retry-and-degradation primitives, bundled because their normative
text shares a load-bearing lane-separation framing:

1. **`FailureIsolationMiddleware`** added to the pipeline-utilities §6
   bundled-middleware set as §6.3, paralleling §6.1 `RetryMiddleware`
   and §6.2 `TimingMiddleware`. Catches exceptions escaping the inner
   chain, returns a configured degraded partial update, and surfaces
   the catch via an observer event. Composes with `RetryMiddleware`
   via the three-piece pattern (transient-aware node body + inner
   retry + outer isolation) for "retry transients, degrade
   gracefully on exhaustion" workflows.

2. **Call-level retry on `LlmProvider.complete()`** via a new
   optional retry kwarg accepting the same retry configuration
   record pipeline-utilities §6.1 defines (`max_attempts` /
   `classifier` / `backoff` / `on_retry`). Handles transient LLM
   failures at the call boundary so a node issuing N LLM calls in
   a loop doesn't re-run already-successful calls when call N hits
   a transient failure. Reuses the §6.1 default transient
   classifier (categories explicitly enumerated as transient by
   their carrying spec). Adds an `openarmature.llm.attempt_index`
   per-attempt span attribute for observer disambiguation.

The two primitives ship together because the spec text needs
**two-level retry lane-separation guidance** as the connective
tissue — retry now lives at both the node level (pipeline-utilities
§6.1) and the call level (llm-provider §7), and the spec must
explicitly demarcate the lanes so callers don't stack overlapping
retry budgets they didn't reason about. The lane-separation table
+ a "common mistakes to avoid" list (multiplicative-budget pitfall:
3-attempt outer × 3-attempt call-level on a 5-call chunked node =
up to 45 calls) lives in llm-provider §7 alongside the per-call
retry framing, with `RetryMiddleware`'s §6.1 text cross-referencing
it.

Both primitives are additive at the spec level. Existing pipelines
see no behavioral change; pipelines opting into either primitive
get the named contract + the lane-separation discipline.

## Motivation

Three concrete pressures converge:

**The catch-and-recover middleware pattern is recurring.** Pipeline-
utilities §2's third MAY bullet under the middleware contract
("middleware MAY catch exceptions raised by `next(state)` and either
re-raise, transform, or recover, returning a partial update instead
of raising") describes the pattern; without a named primitive in the
§6 set, each implementation re-derives it independently. The two
existing bundled middlewares (§6.1 retry, §6.2 timing) set the
precedent for shipping small, focused primitives in the §6 set. The
catch-and-recover pattern deserves the same treatment — it's the
canonical companion to the §6.1 retry middleware for "retry then
give up gracefully" flows.

**Per-call retry granularity matters for chunked-loop nodes.** Node-
level `RetryMiddleware` (§6.1) is the right scope when a node's
entire body is the retry unit. But nodes that issue N LLM calls in
a loop (chunked processing, sequential multi-step, retrieve-then-
reason patterns) face a real cost when `RetryMiddleware` re-runs the
whole node body on a transient failure of call N: calls 1..N-1 are
re-executed unnecessarily. That's wasted spend, wasted latency,
and (for non-idempotent side effects in hybrid nodes) potentially
incorrect. Call-level retry on `LlmProvider.complete()` gives
surgical retry granularity exactly where it's needed.

**Lane separation prevents budget compounding.** With retry living
at two levels (per-call in llm-provider §7, per-node in
pipeline-utilities §6.1), the multiplicative-budget concern is
real: a 3-attempt outer `RetryMiddleware` wrapping a 5-call chunked
node with 3-attempt per-call retry can issue up to 45 LLM calls in
the worst case. The spec must demarcate the lanes explicitly so
callers don't stack overlapping retries without realizing the
combinatorial cost. The lane-separation table + "common mistakes"
list is the load-bearing connective tissue that makes the two-level
retry surface sane.

The bundle is justified by the lane-separation framing — splitting
the two primitives into separate proposals would force the
lane-separation text to live in only one (leaving the other
incomplete) or duplicate it (drift risk). The two primitives'
code surfaces are independent at the implementation layer; they
can land as separate implementation changes. The spec text wants
them together because of the shared connective text.

## Proposed change

### pipeline-utilities §6.3 — *Failure isolation middleware* (new)

Add a new §6.3 subsection between §6.2 (timing middleware) and any
subsequent §6 content, following the §6.1 / §6.2 template.

> **6.3 Failure isolation middleware**
>
> `FailureIsolationMiddleware` catches exceptions escaping the
> inner chain and returns a configured degraded partial update.
> The named primitive packages the §2 third-MAY-bullet pattern
> ("middleware MAY catch ... and either re-raise, transform, or
> recover") with a stable contract and observer-event surface,
> avoiding per-downstream re-derivation.
>
> **Configuration:**
>
> - `degraded_update` (required) — the partial state update returned
>   on caught exceptions. MAY be a static mapping OR a callable
>   `state -> partial_update` for cases where the degraded shape
>   depends on input state. Resolved at catch time.
> - `event_name` (required, no default) — a stable identifier for
>   this catch site. Surfaces on the observer event AND any default
>   logging. Required with no default because useful values are
>   node-specific (e.g., `"segment_extraction_failure_isolated"`)
>   and a generic `"failure_isolated"` default would make
>   downstream telemetry strictly worse — a single dashboard tile
>   labeled `failure_isolated` hides which specific path degraded.
>   Forcing the name at the construction site puts the decision
>   where the right context is available.
> - `predicate` (optional) — a callable `Exception -> bool`. When
>   supplied, only exceptions where `predicate(exc) is True` are
>   caught; others propagate. Defaults to "always True" (catch all
>   `Exception`). Mirrors the §6.1 retry-middleware classifier
>   shape in returning bool, with a single-argument signature
>   (`Exception -> bool`) rather than retry's two-argument
>   `(exception, state) -> bool` form. State-dependent predicates
>   aren't a documented use case for failure isolation today; the
>   simpler signature is sufficient for v1.
> - `on_caught` (optional) — an async callable `Exception ->
>   Awaitable[void]`. Optional hook fired when the middleware
>   catches an exception. Lets consumers pump caught exceptions to
>   caller-specific telemetry (custom logger, metric counter, etc.)
>   beyond the default observer event.
>
> **Catch semantics:**
>
> - Catches `Exception` by default; `BaseException` (cancellation,
>   keyboard interrupt) propagates. Same rule as `RetryMiddleware`
>   per §6.1.
> - On a caught exception:
>   1. Emit an observer event (see *Observability* below).
>   2. Call `on_caught(exc)` if supplied.
>   3. Resolve `degraded_update` (static OR callable) and return
>      the partial update as the node's normal return value.
> - The graph engine continues edge resolution from the
>   `FailureIsolationMiddleware`-wrapped node's degraded return per
>   the normal §3 / §4 contract. The engine does NOT see the
>   exception; from its perspective, the node returned normally.
>
> **Observability.** When the middleware catches an exception, it
> dispatches a **framework-emitted failure-isolation event** onto
> the same observer delivery queue as `NodeEvent` per graph-engine
> §6. The event is a distinct kind from `NodeEvent` — it does NOT
> reuse `NodeEvent.node_name` / `namespace` (which graph-engine §6
> reserves for registered-node identity) and does NOT reuse
> `NodeEvent.error` (a graph-engine §4 category). It is a separate
> framework-emitted observer event variant carrying its own field
> set:
>
> - `event_name` — the caller-supplied event name from the
>   middleware's configuration (a stable identifier for this
>   catch site).
> - The wrapped node's identity per graph-engine §6 (`namespace`,
>   `attempt_index`, `fan_out_index`, `branch_name` — the same
>   lineage tuple `NodeEvent` carries, surfaced here for
>   correlation with the wrapped node's other events).
> - `pre_state` / `post_state` reflecting the wrapped node's
>   input and degraded return.
> - `caught_exception` — a structured record carrying the caught
>   exception's category (per its carrying spec, e.g.,
>   llm-provider §7 / graph-engine §4) and the exception message.
>
> This pattern parallels graph-engine §6's RECOMMENDED metadata-
> augmentation event mechanism from proposal 0040 — a distinct
> framework-emitted event kind on the observer delivery queue,
> with the typed shape per-language idiom. Spec mandates the event
> mechanism + field set; per-language implementations choose the
> concrete typed shape (e.g., a Python dataclass, a TypeScript
> interface) following the language's naming idioms.
>
> A future proposal MAY promote the failure-isolation event to a
> spec-mandated typed variant on the observer event union
> (paralleling proposal 0049's `LlmCompletionEvent` carve-out) if
> the pattern accumulates across multiple middleware primitives.
> For v1, the event-mechanism framing (per 0040's pattern) is
> sufficient.
>
> **Default emission is observer-event-only.** The middleware MUST
> NOT pin a logging library (stdlib `logging`, structlog, etc.) —
> the default emission path is the observer event. Consumers
> wanting additional logging attach their own observer or use
> `on_caught`.
>
> **Composition with `RetryMiddleware` — the three-piece pattern.**
> Pipelines that want "retry transients, give up gracefully on
> exhaustion or non-transient errors" compose three pieces:
>
> 1. **Node body** keeps a transient-aware `except` block —
>    re-raise on exceptions whose category §6.1's default
>    classifier treats as transient (`provider_unavailable`,
>    `provider_rate_limit`, etc.), degrade in-place on
>    non-transient categories.
> 2. **Inner middleware**: `RetryMiddleware` (§6.1) — sees raw
>    transients and retries them per its policy; on exhaustion,
>    propagates the exception.
> 3. **Outer middleware**: `FailureIsolationMiddleware` — catches
>    the exhaustion-propagated exception (or any non-transient that
>    re-raised through the node body's `except`) and returns the
>    configured degraded update.
>
> Outer-to-inner ordering is load-bearing: retry MUST be inner
> (it sees raw transients first); failure isolation MUST be outer
> (it only sees what escapes retry). Reversing the order would let
> the inner isolation catch transients before retry sees them,
> defeating retry's purpose entirely. Implementations SHOULD
> document this composition explicitly in the middleware API
> documentation.

### llm-provider §5 — `complete()` retry parameter

Extend the §5 `complete()` interface with an optional retry
parameter:

> The signature extends with an additional optional keyword
> parameter, `retry`, accepting an instance of pipeline-utilities
> §6.1's retry middleware configuration record (or null/absent).
> Default is null/absent — no retry; the v0.4.0 behavior is
> preserved verbatim.
>
> When `retry` is absent/null, `complete()` behaves exactly as
> today — transient errors per §7 raise to the caller without
> retry. When `retry` is supplied, the provider implementation
> performs an in-call retry loop per the new §7 *Call-level
> retry* subsection (loops on transient errors matching the §6.1
> default classifier's category set, applies the configured
> backoff between attempts, propagates the final error when
> `max_attempts` is exhausted).

### llm-provider §7 — *Call-level retry* (new subsection)

Add a new §7 subsection after the existing retry-classification
text:

> **Call-level retry.** When `complete()` is called with a non-
> null `retry` parameter (per §5), the provider implementation
> performs an in-call retry loop:
>
> - On each attempt, dispatch the underlying request as it would
>   for a non-retried call.
> - If the response is successful, return immediately.
> - If the response raises an exception classified as transient
>   by the retry record's `classifier` field (default behavior
>   matches the §6.1 default transient classifier), wait per
>   `backoff(attempt_index)` and re-attempt.
> - If `max_attempts` is exhausted, propagate the final error
>   per the normal `complete()` exception path.
> - Exceptions classified as non-transient propagate immediately
>   on first occurrence (no retry).
>
> **Configuration record reuse.** The retry parameter accepts the
> same configuration record pipeline-utilities §6.1 defines — the
> four-field shape (`max_attempts` / `classifier` / `backoff` /
> `on_retry`) is framework-agnostic and reusable across the per-
> node and per-call retry contexts. Implementations MUST accept the
> same configuration record instance a caller would pass to the
> §6.1 retry middleware. (Cross-spec reference direction: llm-
> provider §7 here references pipeline-utilities §6.1, which is the
> inverse of pipeline-utilities §6.1's existing dependency on
> llm-provider §7 for transient category names. The two-way
> dependency is acceptable because the shared retry config record is
> framework-agnostic and the per-section content remains
> independently coherent.)
>
> **Transient classification.** The default `classifier` field's
> behavior matches the §6.1 *Default transient classifier* text —
> the same categories §6.1 enumerates as transient (`provider_
> unavailable`, `provider_rate_limit`, `provider_model_not_loaded`,
> plus categories marked transient by their carrying spec)
> trigger the per-call retry loop. Callers MAY supply a
> user-defined `classifier` if their application has additional
> retriable categories or context-dependent retry policies.
>
> **Backoff behavior.** The `backoff` field's `(attempt_index) ->
> delay_seconds` contract from §6.1 applies unchanged at the
> call-level retry. The §6.1 default (exponential with full
> jitter, base 1s, cap 30s) applies when the caller doesn't
> override; implementations MAY ship additional named backoff
> strategies per §6.1's MAY clause.
>
> **Per-attempt span emission.** Each retry attempt produces its
> own `openarmature.llm.complete` span per observability §5.5 —
> N retry attempts emit N LLM spans, all parented under the
> calling node's span. The per-attempt span carries the new
> `openarmature.llm.attempt_index` attribute (per observability
> §5.5 below). The final-error category lands on the LAST
> attempt's span; earlier failed-then-retried attempts carry
> their own per-span error categories.
>
> **Two-level retry lane separation.** Retry primitives operate
> at two semantic levels in OA:
>
> | Layer | Spec section | Semantic unit | Use when |
> |---|---|---|---|
> | Per-call retry | llm-provider §7 (this section) | A single `complete()` call | A node issues multiple LLM calls in a loop; you want to avoid re-running successful calls when a later call's transient fails |
> | Per-node retry | pipeline-utilities §6.1 `RetryMiddleware` | A whole node invocation | A node does LLM + non-LLM work (DB writes, parses, side effects); you want to re-run the entire body on failure |
>
> The layers compose: per-call exhausts → propagates → per-node
> retry catches → re-runs whole node → per-call budgets reset for
> each fresh per-node attempt.
>
> **Common mistakes to avoid:**
>
> - **Multiplicative budget on chunked nodes.** Stacking the
>   §6.1 retry middleware (configured with `max_attempts=3`) over
>   a node that issues 5 LLM calls, each with a per-call retry
>   record configured for `max_attempts=3`, can issue up to
>   3 × 5 × 3 = 45 LLM calls in the worst case. The budget
>   multiplies. Authors stacking both layers should pick
>   intentional budgets per layer.
> - **Inline retry via try/except inside the node body.**
>   Implementing retry as a try/except inside the node loses the
>   per-attempt span attribution and the backoff-utility
>   integration. Use the `retry` kwarg instead.
> - **Widening the transient classifier to mask real errors.**
>   The §6.1 default classifier excludes non-transient categories
>   for a reason. Supplying a custom `classifier` that retries on
>   `provider_invalid_request` or `structured_output_invalid`
>   (for example) masks bugs rather than working around transient
>   infrastructure issues. Custom classifiers SHOULD widen the
>   default only for categories that are genuinely transient
>   but not yet enumerated by §6.1.

### observability §5.5 — `openarmature.llm.attempt_index` attribute + per-attempt span amendment

§5.5 today frames LLM provider span emission as "a span around each
`complete()` call" (one span per call). This proposal amends that
framing to **"one span per attempt under call-level retry; one
span per `complete()` call when retry is absent (the default —
§5.5's existing one-span-per-call framing preserved verbatim)"**.
The amendment is required because call-level retry per
llm-provider §7 produces N attempts inside a single `complete()`
call; emitting one span per attempt is the observability shape
backends expect for retry attribution. The new
`openarmature.llm.attempt_index` attribute discriminates the N
spans.

Add a new attribute to the §5.5 LLM provider span attribute set:

> - `openarmature.llm.attempt_index` — int. The retry-attempt
>   index for the LLM call, where `0` is the first attempt and
>   `0..N-1` covers the N spans produced by an N-attempt
>   call-level retry per llm-provider §7. Emitted on every LLM
>   provider span; defaults to `0` when call-level retry is not
>   configured on the `complete()` call (a single attempt).
>   Paralleled with `openarmature.node.attempt_index` per §5.2
>   for node-level retry; the two attributes are independent
>   (a per-call retry attempt 0 may be nested under a node-level
>   attempt 1, etc.).
>
> The attribute lives in the `openarmature.llm.*` namespace per
> the §5.5.2 framing precedent for OA-specific attributes; if the
> OpenTelemetry GenAI semconv adds a stable `gen_ai.*` equivalent
> in a future release, a follow-on proposal MAY mirror this
> attribute to both namespaces per the existing §5.5.3 mirror
> pattern (`openarmature.llm.model` + `gen_ai.request.model`).

## Conformance test impact

### New fixtures

Ten new fixtures (numbers assigned at acceptance):

**Failure-isolation middleware (pipeline-utilities/conformance/):**

1. **Static degraded update.** A node wrapped with
   `FailureIsolationMiddleware(degraded_update={"result": []},
   event_name="extraction_failed")` that raises an exception.
   Asserts the wrapped node returns `{"result": []}` to the
   engine; the engine continues edge resolution from the
   degraded return; the observer receives a framework-emitted
   failure-isolation event with `event_name = "extraction_failed"`,
   the wrapped node's lineage identity (`namespace`,
   `attempt_index`, etc.) matching the wrapped node, and a
   `caught_exception` record carrying the raised exception's
   category and message.

2. **Callable degraded update.** Same shape as fixture 1 but
   `degraded_update = lambda state: {"result": []}` for input-
   state-dependent degraded shapes. Asserts the callable receives
   the pre-call state and its return becomes the partial update.

3. **Predicate filtering.** A node wrapped with
   `FailureIsolationMiddleware(predicate=lambda exc: isinstance(exc,
   ValueError), ...)`. Raises a `KeyError` (not caught — propagates)
   and separately raises a `ValueError` (caught — degraded
   returned). Asserts predicate filtering works per the §6.3
   semantics.

4. **Three-piece composition pattern.** A node wrapped with both
   `RetryMiddleware(max_attempts=2)` (inner) and
   `FailureIsolationMiddleware(degraded_update={"result": []},
   event_name="x_failed")` (outer). The node body raises a
   transient error twice (retry exhausts) then propagates;
   `FailureIsolationMiddleware` catches the propagated error.
   Asserts the three-piece pattern works end-to-end: retry's
   `openarmature.node.attempt_index` attribute shows attempts
   0 and 1; the middleware emits its observer event; the
   degraded return reaches the engine.

**Call-level retry (llm-provider/conformance/):**

5. **Per-call retry on transient.** A graph with one LLM-calling
   node, a mocked provider returning a `provider_unavailable`
   error on attempt 0 and a successful response on attempt 1, and
   `complete()` called with a retry parameter configured for
   `max_attempts=2`. Asserts the call returns the successful
   response; two LLM spans emit with
   `openarmature.llm.attempt_index = 0` and `1` respectively;
   the first attempt's span carries the `provider_unavailable`
   error category.

6. **Per-call retry exhaustion.** Same shape as fixture 5 but
   the mocked provider returns `provider_unavailable` on both
   attempts. Asserts the call raises the final
   `provider_unavailable` error (propagates per the §7 exception
   path); two LLM spans emit with attempt indices 0 and 1, both
   carrying the error category.

7. **Non-transient propagates without retry.** A graph with one
   LLM-calling node, a mocked provider returning HTTP 400 (→
   `provider_invalid_request` per §7), and `complete()` called with
   a retry parameter configured for `max_attempts=3`. Asserts the
   call raises `provider_invalid_request` on attempt 0 (the retry
   loop does NOT iterate on non-transient categories); exactly one
   LLM span emits with `attempt_index = 0` carrying the error
   category. Locks down §7.1's non-transient-immediate-propagation
   rule.

8. **`on_caught` callback fires.** A node wrapped with
   `FailureIsolationMiddleware` whose `on_caught` is a recording
   callback. The node raises a transient exception; the middleware
   catches. Asserts the callback fires exactly once with the
   original exception, the framework-emitted observer event still
   emits (the callback is additive, not replacing), and the
   degraded return reaches the engine. Locks down §6.3's
   `on_caught` optional-hook contract.

9. **Default predicate catches bare exception.** A node wrapped
   with `FailureIsolationMiddleware` (no `predicate` supplied —
   default always-true) raises a bare `ValueError` carrying no
   category. Asserts the middleware catches; the framework-emitted
   event's `caught_exception.category` is `null` and `message`
   captures `str(exc)`. Locks down §6.3's
   default-predicate-catches-all + null-category-on-non-categorized
   rules.

**Observability single-attempt default (observability/conformance/):**

10. **`openarmature.llm.attempt_index` single-attempt default.** A
    graph with one LLM-calling node, no `retry` kwarg on
    `complete()`. Asserts exactly one LLM provider span emits
    carrying `openarmature.llm.attempt_index = 0` alongside the
    baseline §5.5 attributes (`model`, `finish_reason`, `usage.*`).
    Locks down the §5.5 single-span backwards-compat contract (the
    existing single-span framing preserved verbatim when retry is
    absent) AND the new attribute's default-value contract
    (`attempt_index = 0` when call-level retry is not configured).

### Unaffected fixtures

All existing fixtures continue to pass unchanged. The middleware
primitive and call-level retry kwarg are additive — existing
pipelines that don't use them see no behavioral change.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New `FailureIsolationMiddleware` as pipeline-utilities §6.3
  (additive — existing §6.1 / §6.2 unchanged).
- New `retry` kwarg on `LlmProvider.complete()` per §5
  (additive — default `None` preserves current behavior verbatim).
- New §7 *Call-level retry* subsection in llm-provider
  (additive — current §7 retry-classification text unchanged).
- New `openarmature.llm.attempt_index` attribute on the §5.5 LLM
  provider span surface (additive — existing attributes unchanged;
  emitted with default value `0` for non-retried calls per the
  attribute definition).
- New conformance fixtures (ten required). Existing fixtures
  unchanged.

The change is backwards-compatible across all three capabilities.

## Alternatives considered

1. **Split into two proposals (failure-isolation only +
   call-level retry only).** Land them as independent proposals
   without the bundle. Rejected: the two-level retry lane-
   separation framing is load-bearing for both primitives and
   would need to live in one of them (leaving the other
   incomplete) or be duplicated (drift risk between the two
   proposals' lane tables). Bundling consolidates the connective
   text in one canonical home. The proposals' code surfaces are
   independent at the impl level — they can ship as separate PRs
   downstream — but the spec text wants them together.

2. **Make `event_name` optional on `FailureIsolationMiddleware`
   with a default of `"failure_isolated"`.** Easier to use; one
   less required argument. Rejected: a generic
   `"failure_isolated"` default makes downstream logs and
   dashboards strictly worse — a single dashboard tile labeled
   `failure_isolated` hides which specific path degraded across
   N different middleware-wrapped nodes. Requiring the name
   forces the naming decision once, at the middleware
   construction site, where the right context is available.

3. **Typed `MiddlewareEvent` variant on the observer event union
   (instead of the framework-emitted event mechanism).** Promote
   the failure-isolation event to a spec-mandated typed variant
   on the observer event union, paralleling proposal 0049's
   `LlmCompletionEvent` carve-out. Rejected for v1: middleware
   events are low-frequency (only fire when a middleware catches;
   not on every node execution) and have a narrower consumer
   audience than LLM completions. The Observer event union
   shouldn't grow a typed variant for a one-off middleware
   emission. The framework-emitted event mechanism (paralleling
   proposal 0040's metadata-augmentation event pattern) is the
   right ceremony level for v1 — spec mandates the event
   mechanism + field set; the typed shape is per-language idiom.
   If/when other middleware events accumulate (rate-limit,
   circuit-breaker, etc.), a follow-on proposal can promote them
   as a family.

4. **Sibling `complete_with_retry()` method instead of `retry`
   kwarg.** Have llm-provider expose a separate method for
   retried calls. Rejected: kwarg is cleaner — `retry=None`
   default preserves the existing call surface verbatim, composes
   with other call params (`response_schema`, `config`,
   `tool_choice`), and avoids surface-area duplication
   (`complete()` + `complete_with_retry()`).

5. **Spec-defined LLM-specific retry config record instead of
   reusing pipeline-utilities §6.1's record.** Define a sibling
   retry configuration record in llm-provider rather than cross-
   referencing pipeline-utilities §6.1's shape. Rejected: the
   fields are framework-agnostic (`max_attempts`, backoff
   function, classifier, on_retry); duplicating them across two
   specs is busywork without value. Cross-spec reference is the
   cleaner shape. The cross-spec dependency direction is
   acceptable — llm-provider §7 referencing pipeline-utilities
   §6.1 here inverts the existing pipeline-utilities §6.1 →
   llm-provider §7 reference (for transient category names), but
   the two-way dependency stays clean because the shared
   configuration record is itself framework-agnostic.

6. **Use `gen_ai.attempt_index` instead of
   `openarmature.llm.attempt_index`.** Mirror the GenAI semconv
   attribute namespace directly. Rejected per the
   docs/compatibility.md *Stable-only adoption* policy: the OTel
   GenAI semconv doesn't currently have a stable
   `gen_ai.attempt_index` attribute (and at the time of writing,
   no Development-status equivalent either). Per the policy, OA
   uses `openarmature.llm.attempt_index` as the OA-namespace
   shape; a follow-on proposal mirrors to `gen_ai.*` when an
   upstream stable name emerges. The verification check belongs
   at Accept time per the docs/compatibility.md verification
   discipline.

7. **Cap call-level retry budgets at the framework level
   (multiplicative-budget prevention).** Have the framework
   enforce a maximum total LLM-call budget per node, preventing
   the worst-case 3 × 5 × 3 = 45-call scenario. Rejected for v1:
   the worst case requires deliberate stacking (the caller
   configures both layers); a framework cap would surprise
   callers who intentionally wanted the budget. The "common
   mistakes to avoid" list in §7 documents the pitfall; spec
   doesn't impose a cap. A follow-on MAY add an opt-in budget
   ceiling if the pitfall surfaces frequently in practice.

## Open questions

None at draft time. The design choices are settled in the
proposal text above:

- **Bundle vs split** (alternative 1) — bundled; lane-separation
  framing is the connective tissue.
- **`event_name` required vs default** (alternative 2) — required
  with no default; the naming decision is per-catch-site.
- **Typed middleware event vs framework-emitted event mechanism**
  (alternative 3) — framework-emitted event mechanism for v1
  (parallels proposal 0040's metadata-augmentation event pattern);
  spec mandates the event mechanism + field set, typed shape is
  per-language idiom; future proposal MAY promote to a typed
  variant family if accumulation warrants.
- **`retry` kwarg vs sibling `complete_with_retry()`**
  (alternative 4) — kwarg per the precedent of
  `response_schema` / `config` / `tool_choice` parameters.
- **Shared retry configuration record vs sibling shape**
  (alternative 5) — reuse the pipeline-utilities §6.1 record;
  framework-agnostic fields, cross-spec reference is cleaner.
  Two-way cross-spec dependency direction (pipeline-utilities §6.1
  → llm-provider §7 for category names; llm-provider §7 →
  pipeline-utilities §6.1 for the retry record) is acceptable
  because the shared config record is framework-agnostic.
- **`openarmature.llm.attempt_index` vs `gen_ai.attempt_index`**
  (alternative 6) — OA namespace for v1 per the stable-only
  adoption policy; verify at Accept that no upstream stable
  `gen_ai.*` attribute has emerged.
- **Multiplicative-budget cap** (alternative 7) — out of scope
  for v1; documented in the "common mistakes" list.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Sub-node retry for non-LLM call sites.** Call-level retry on
  DB writes, HTTP calls to non-LLM services, etc. — out of scope.
  Those call sites have their own retry abstractions (DB
  connection pools, HTTP client libraries) and adding a
  framework-level retry surface for them would duplicate that
  infrastructure. This proposal scopes to LLM provider calls
  only.
- **Framework-level multiplicative-budget cap** (alternative 7).
  Documented as a pitfall in §7's "common mistakes" list; spec
  does not impose a cap.
- **Typed middleware event variant family** (alternative 3).
  Framework-emitted event mechanism for v1 (per 0040's pattern);
  future promotion to spec-mandated typed variant via follow-on
  if accumulation warrants.
- **Streaming-retry semantics.** Per-call retry on a streaming
  `complete()` call (where the LLM returns chunks rather than a
  single response) raises questions the spec doesn't address
  (partial-content handling, resumption from mid-stream, etc.).
  Out of scope for v1; streaming completion patterns are a
  separate concern.
- **Retry budget aggregation across nodes.** A pipeline-level
  budget that aggregates retry attempts across all nodes in an
  invocation — out of scope; per-call and per-node budgets are
  independent.
- **Rate-limit middleware.** A separate retry-adjacent primitive
  (token-bucket / leaky-bucket rate limiting) is a logical
  follow-on to §6.3 but warrants its own design discussion;
  bundling here would expand scope. Out of scope for this
  proposal.
- **Circuit-breaker middleware.** Same framing as rate-limit — a
  natural follow-on primitive, scoped out of v1 to keep the
  bundle focused on the retry + degradation pair specifically.
