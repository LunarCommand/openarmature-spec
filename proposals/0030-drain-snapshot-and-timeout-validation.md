# 0030: Graph Engine — §6 Drain snapshot semantic and timeout-input validation

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-25
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (clarifies §6 Drain with two textual amendments: snapshot semantic for "prior invocations" + MUST-reject rule for negative / NaN timeout inputs)
- **Related:** 0010 (drain timeout — both clarifications surfaced during 0010's openarmature-python implementation pass)
- **Supersedes:**

## Summary

Tighten graph-engine §6 Drain with two clarifications surfaced
during the openarmature-python implementation of proposal 0010:

1. **Snapshot semantic.** Name the rule that the set of invocations
   covered by a `drain` call is the set whose worker(s) were active
   at the time `drain` is invoked. Invocations started after `drain`
   begins are NOT covered by that drain.

2. **Timeout-input validation.** Mandate that implementations MUST
   reject negative or `NaN` timeout inputs with an API-boundary
   error before any drain work begins. The error surface is
   per-language idiomatic; the spec mandates the rejection, not
   the error type.

Both are clarifications of implicit rules. Existing implementations
that already follow the natural reading need no behavior change;
the clarifications close cross-implementation drift before the
TypeScript implementation lands.

## Motivation

§6 Drain (amended by proposal 0010) currently reads:

> The compiled graph MUST expose a `drain` operation that, when
> awaited, returns once all observer events produced by **prior
> invocations** of this graph have been delivered to every
> registered observer, OR once an optional caller-supplied timeout
> elapses, whichever happens first.

The phrase "prior invocations" is ambiguous on two fronts:

- **Snapshot vs. continuous.** "Prior invocations" could mean
  "invocations that began before `drain` was called" (snapshot —
  drain waits on a fixed set captured at call time) or "invocations
  whose work hasn't fully delivered yet" (continuous — drain waits
  until the observer queue is fully empty for ALL invocations,
  including ones started during the drain). The two readings
  disagree silently when an invocation begins concurrently with a
  drain call.
- **Timeout interaction.** The continuous reading interacts
  awkwardly with the 0010 timeout: new invocations starting during
  the drain can extend the queue indefinitely, and the spec would
  have to define which work the timeout cancels (the
  originally-active workers? the new ones? all of them?). The
  snapshot reading composes cleanly: the deadline applies to a
  known finite worker set captured at call time.

The reference Python implementation lands on snapshot (its
`drain()` captures the active worker set at call entry). Future
implementations reading only the current spec text could land on
either reading. Naming the rule normatively prevents
cross-implementation drift.

Separately, §6's timeout-parameter paragraph says the parameter is
"a non-negative duration in seconds" but doesn't mandate what
implementations MUST do when callers pass invalid input (negative
values, `NaN`, non-numeric). The natural defensive read is "reject
at the API boundary"; without an explicit normative rule,
implementations could silently treat a negative value as "immediate
cancel" (since `asyncio.wait(timeout=-1)` and similar primitives
treat negative as "don't wait"). Silent fall-through to cancel-now
is a user-hostile failure mode for what's almost certainly a caller
mistake. The reference Python implementation rejects with
`ValueError`; mandating the rejection cross-language locks in the
right surface without forcing per-language error-type uniformity.

## Detailed design

### §6 amendment: snapshot semantic

Insert a new paragraph after the existing "**Drain.**" paragraph
(which currently ends "…MUST use drain to avoid losing observer
events that were dispatched but not yet delivered.") and before the
"The `drain` operation MUST accept an optional **timeout**
parameter…" paragraph:

> The set of invocations covered by a `drain` call is the set
> whose worker(s) were active at the time `drain` is invoked.
> Invocations started after `drain` is called are NOT covered by
> that drain; callers needing delivery guarantees for a later
> invocation MUST call `drain` again after the later invocation
> begins. The snapshot semantic composes cleanly with the optional
> `timeout`: the deadline applies to a known finite set of workers
> captured at call time, rather than an open-ended set that new
> invocations could extend past the deadline.

### §6 amendment: timeout-input validation

Append a new bullet to the existing bulleted list under the "If a
timeout is supplied:" introduction (the list currently has four
bullets covering deadline / undelivered events / cancellation /
observer cancellation-safety):

> - implementations MUST reject negative or `NaN` timeout inputs by
>   raising an API-boundary error before any drain work begins. The
>   error surface is per-language idiomatic (e.g., a Python
>   `ValueError`, a TypeScript `RangeError`, a Go error return
>   value); the spec mandates the rejection, not the error type.
>   Non-numeric input is rejected per the language's type-error
>   idiom (e.g., a Python `TypeError` from the underlying
>   comparison or validation).

The bullet sits alongside the other timeout-parameter rules and
naturally reads as part of the "if a timeout is supplied" contract.
The "no validation when omitted" case is unchanged — omitted
timeout still means "wait indefinitely" per the existing v0.3.0
behavior.

### Cross-spec touchpoints

- **Graph-engine §6** — primary site (both clarifications).
- **Pipeline-utilities §10.8** — no changes. Checkpoint save event
  emission under drain timeout is unchanged.
- **Observability §6** — no changes.
- **LLM-provider** — no changes.

### No behavior change for existing implementations

The reference Python implementation already implements both
clarifications (snapshot in its `drain()` worker capture; the
API-boundary error on negative / NaN inputs added during the 0010
implementation pass). The clarifications make those implicit
choices normative for cross-implementation consistency; no Python
impl follow-on is needed beyond a documentation sweep (the
docstring already names both behaviors).

## Conformance test impact

None.

Both clarifications are textual sharpenings of implicit rules. A
fixture for either rule would have meaningful limitations:

- **Snapshot rule.** Testing "invoke A, start drain, invoke B;
  drain returns after A's events but not B's" is timing-sensitive
  — the fixture would assert scheduler behavior more than the
  contract. Implementations whose `drain()` naturally snapshots
  pass; the spec text catches up to that behavior.
- **Timeout-input validation rule.** The error surface is
  per-language (Python `ValueError`, TypeScript `RangeError`, Go
  error return value). A cross-language fixture asserting "drain
  with negative timeout raises something" is too generic to be
  useful; asserting language-specific error types per fixture isn't
  the right shape for a cross-impl conformance suite. The normative
  rule + per-language documentation suffices.

Matches the v0.16.1 / v0.17.1 / v0.21.1 textual-clarification
precedent (implicit rules made explicit; no new fixtures).

## Alternatives considered

### Continuous semantic instead of snapshot

Rejected. Continuous semantic interacts awkwardly with the 0010
timeout — new invocations starting during a drain can extend the
queue past the deadline, and the spec would have to define
unambiguously which work the timeout cancels. Snapshot has a clean
answer: the deadline applies to a known finite worker set captured
at call time. Existing implementations (reference Python) land on
snapshot naturally; changing the spec to continuous would force
implementation work in the wrong direction.

### Mandate `ValueError` specifically for the timeout-input error

Rejected. Each language has its own API-boundary error idiom:
Python `ValueError`, TypeScript `RangeError`, Go error return
value, Java `IllegalArgumentException`, etc. Specifying the Python
idiom would force the TypeScript / Go / future-language
implementations to invent matching surfaces — pure ceremony. The
MUST-reject rule with implementation-defined error type matches
the existing pattern for "cancellation mechanism is
implementation-defined per language idiom" in the same §6
contract.

### Add a fixture for the snapshot rule

Rejected. Timing-sensitive (assertion shape would be "drain
returns within X ms after A's events deliver, regardless of
whether B's events are pending"). Tests scheduler behavior more
than the contract. Implementations naturally land on snapshot;
the spec text suffices as documentation of the rule.

### Add a fixture for timeout-input validation

Rejected. Cross-language error-surface assertions are awkward.
Asserting language-specific types per fixture isn't the shape of a
cross-impl conformance suite; asserting "drain raises something"
is too generic to catch real implementation bugs. The normative
rule plus per-language documentation captures the contract.

### Split into two proposals (0030 snapshot + 0031 timeout-validation)

Rejected. Both clarifications target the same spec section, both
came from the same 0010 implementation pass, both ship together
naturally. Splitting would be cosmetic — each proposal would be
tiny on its own and would force two acceptance passes for what
amounts to two adjacent paragraph edits.

## Open questions

None. Both clarifications are settled in the proposal text above:
snapshot wins over continuous; per-language error idiom suffices
for the timeout-input rejection.
