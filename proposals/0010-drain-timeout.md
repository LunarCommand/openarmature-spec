# 0010: Bounded Drain — Configurable Timeout for Observer Delivery

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-05
- **Targets:** spec/graph-engine/spec.md §6 Observer hooks (the "Drain" subsection)
- **Related:** 0003 (introduced drain), 0005 (extended observer model to pair events)
- **Supersedes:**

## Summary

Allow callers of `drain` to bound the wait with a timeout. Today drain MUST return only after every
queued observer event has been delivered to every registered observer; with a slow, hung, or
misbehaving observer, drain can block indefinitely and stall the host process. This proposal adds
an optional timeout parameter that lets callers cap the wait, and specifies what happens to events
not yet delivered when the timeout is reached.

## Motivation

The current §6 Drain contract gives callers exactly one knob: "wait until done." That contract is
correct for the happy path but unsafe in the presence of:

1. **Buggy observers** — an observer that deadlocks on a lock or hangs on a network call with no
   timeout will block drain forever. The graph ran in milliseconds; the process now hangs
   indefinitely.
2. **Slow observers under unexpected load** — an observer that normally takes 10ms but is queued
   behind 10,000 events from a long-running invocation can still hold drain for tens of seconds
   during shutdown.
3. **Mixed-criticality observers** — a metrics observer's failure to flush should not prevent a
   CLI from exiting. Today there's no way to say "wait briefly, but don't let observer health gate
   process exit."

Callers can today wrap drain in their host language's timeout primitive (e.g., Python's
`asyncio.wait_for`). That works but cancels the worker mid-event, leaves the queue in an undefined
state for the next invocation on the same compiled graph (if any), and gives the caller no
visibility into how many events were dropped. A first-class timeout parameter lets the engine
handle teardown cleanly and report what was lost.

## Detailed design

Amend §6 Observer hooks → Drain subsection. The current text reads:

> **Drain.** The compiled graph MUST expose a `drain` operation that, when awaited, returns once
> all observer events produced by prior invocations of this graph have been delivered to every
> registered observer.

Replace with:

> **Drain.** The compiled graph MUST expose a `drain` operation that, when awaited, returns once
> all observer events produced by prior invocations of this graph have been delivered to every
> registered observer, OR once an optional caller-supplied timeout elapses, whichever happens
> first.
>
> The `drain` operation MUST accept an optional **timeout** parameter (interpreted as a
> non-negative duration in seconds, mapped to the host language's idiomatic wait-bound type — for
> example, Python's `float` seconds). If the timeout is omitted or `None`, drain waits
> indefinitely (the existing v0.3.0 behavior). If a timeout is supplied:
>
> - drain MUST return no later than `timeout` seconds after the call begins;
> - any observer events still queued or in-flight when the timeout is reached are considered
>   **undelivered** for the purposes of this invocation's drain;
> - workers MUST be cancelled or otherwise terminated such that the compiled graph remains usable
>   for subsequent invocations — partial delivery state from one drain MUST NOT leak into the next
>   invocation;
>
> drain MUST return a summary of the drain's outcome, in a form appropriate to the host language.
> The summary MUST include at least: the count of undelivered events, and a boolean or equivalent
> flag indicating whether the timeout was reached. Implementations MAY provide richer detail
> (per-observer counts, sampled event metadata). When called without a timeout, drain MUST still
> return a summary; in that case the undelivered count is `0` and the timeout-reached flag is
> `false`. Callers receive a consistent shape regardless of whether they supplied a timeout.
>
> Implementations SHOULD document drain's worst-case duration in the presence of slow observers
> and SHOULD recommend setting a timeout in short-lived process contexts (CLIs, scripts,
> serverless functions).

The "callers running in short-lived processes ... MUST use drain" sentence remains unchanged.

## Cross-spec touchpoints

This proposal does not modify any other capability spec. Three downstream interactions worth
noting:

- **Observability §6 (TracerProvider isolation).** The OTel observer is a §6 observer; under a
  timeout, late observer events may be lost, causing some openarmature spans to never reach the
  exporter. Implementations SHOULD recommend that downstream OTel exporters (Jaeger, Tempo,
  OTLP-HTTP) configure their own buffer/retry settings so transient delivery loss at the
  openarmature boundary does not propagate to the trace backend.
- **Pipeline-utilities §10.8 (checkpoint save event emission).** Checkpoint save events SHOULD
  emit through the §6 observer stream so the OTel mapping can surface them as spans. Under a
  timeout, those late save events may not be delivered to observers — but the underlying
  checkpoint save itself was synchronous and durable per §10.3 / §10.1.1. Only the observer-
  stream surfacing is best-effort under timeout; resume correctness is unaffected.
- **Graph-engine §5 (determinism).** Event *production* remains deterministic — same input, same
  events, same order. Only event *delivery* is bounded by the timeout. Conformance fixtures
  asserting deterministic event content are unaffected; fixtures asserting deterministic delivery
  counts under timeout are not (delivery count depends on observer speed, which is not part of
  the determinism contract).

## Conformance test impact

Add fixtures under `spec/graph-engine/conformance/`:

- **`020-drain-timeout-elapses-with-undelivered.yaml`** — a graph with observers that
  intentionally sleep longer than the supplied timeout. Asserts drain returns within the timeout,
  the summary reports a non-zero undelivered count, and the timeout-reached flag is true.
- **`021-drain-timeout-not-reached-fast-observers.yaml`** — same setup with fast observers that
  finish well within the timeout. Asserts timeout-reached flag is false and undelivered count is
  zero.
- **`022-drain-timeout-clean-state-for-next-invocation.yaml`** — drain one invocation with a
  timeout that elapses, then run a second invocation and drain it without a timeout. Assert the
  second drain returns cleanly and its observer events are delivered as if the first drain's
  truncation never happened. Verifies the "MUST NOT leak" requirement.
- **`023-drain-no-timeout-waits-for-all.yaml`** — regression coverage: drain called with no
  timeout still blocks until every event lands, matching the v0.3.0 contract; the returned
  summary has `undelivered_count == 0` and `timeout_reached == false`.

## Alternatives considered

1. **No spec change; document `asyncio.wait_for` (Python) / `Promise.race` (TS) at the call
   site.** Cheap; works today. But it leaves the post-cancel state of the compiled graph
   implementation-defined and provides no undelivered-events visibility. Two well-meaning users
   would land in different places.
2. **Hard-coded default timeout.** E.g., drain always caps at 30 seconds. Simpler API but breaks
   long-running batch jobs where minutes-long drains are legitimate. The spec shouldn't pick a
   number on the user's behalf.
3. **CompiledGraph-level configuration instead of per-call.** Set the default timeout once at
   compile time. Saves typing in CLIs that always want the same bound, but loses the flexibility
   to use a short timeout at process shutdown and an unbounded drain during normal operation.
   Per-call timeout composes both: implementations MAY also expose a graph-level default that the
   per-call argument overrides.
4. **Cancel-and-discard vs. deliver-some-best-effort under a timeout.** This proposal mandates
   the former. The latter — "deliver as many events as you can, then stop" — is what the natural
   implementation already does, since the worker drains FIFO until cancelled. The normative
   wording makes both behaviors compatible: events the worker already finished are delivered;
   the rest are reported undelivered.

## Open questions

- **Cancellation semantics for an in-flight observer.** When the timeout elapses while an
  observer is mid-call, MUST the implementation cancel that observer (e.g., `task.cancel()` in
  Python) or wait for it to complete its current event before terminating? Cancellation is more
  responsive but exposes observers to interruption mid-side-effect; a "finish current, then stop"
  rule is gentler but means timeout is a soft floor, not a hard ceiling. Lean: implementation-
  defined, documented per-impl.
- **Summary shape across languages.** A Python `dict`/dataclass and a TypeScript object will
  diverge in detail. The spec should require the fields above as a minimum and let each language
  pick the shape.
