# 0124: Resolve an Orphan Provider Span's Parent Structurally

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:**
- **Targets:**
  - spec/observability/spec.md **§5.5 *Lineage-resolved parent***: state that the fallback parent is resolved
    **structurally**, from the call's position in the graph, not from which spans the observer has
    materialized at the moment it resolves. The rule already names the correct parents; what it does not say
    is that an observer-side materialization detail cannot change the answer.
  - spec/observability/spec.md **§6**: replace the sentence pinning the per-branch dispatch span's start time
    to the inner `started` event. Synthesis is triggered by the first event that needs the span, whichever
    arrives first, and the start time is the moment of that event. State the same for the fan-out instance
    dispatch span, which §6 currently leaves silent while pinning the branch one.
  - spec/observability/conformance/152 and 153: un-defer once an implementation resolves structurally. No
    fixture change; both assert the parent §5.5 already mandates.
- **Related:** 0084 (introduced the *Lineage-resolved parent* clause and the lineage-aware span keying),
  0044 (introduced per-branch dispatch spans)

## Summary

A provider call issued from a wrapper resolves its parent when the observer drains the event, while a
dispatch span is synthesized when its first inner node starts. Those two are unordered, so the parent of an
orphan provider span currently depends on whether user middleware happens to yield between the call and the
next node start. §5.5 already names the correct parent; this states that the answer is structural, and
removes the one sentence in §6 that makes the correct answer unreachable.

## Motivation

### The parent depends on scheduling

Measured downstream on a two-branch graph whose branch middleware issues one orphan call in the `pre` phase:

```
-- no yield in the wrapper
  [A] dispatch llm event
  [B] register branch dispatch span
  [C] resolve llm parent          -> parents under the branch dispatch span

-- one scheduler yield after the call
  [A] dispatch llm event
  [C] resolve llm parent          -> span does not exist yet
  [B] register branch dispatch span
```

In the second ordering the orphan parents under the invocation root. A single yield is enough, and yielding
is ordinary for real middleware: any network call, any lock, any sleep.

**This is already non-conforming.** §10 scopes determinism to the §6 event stream and excludes only
implementation-specific data, naming timestamps, span IDs and trace IDs. Parentage is structure derived from
the event stream, so it falls inside the portion §10 covers and the conformance suite asserts. A parent that
varies with a scheduling accident is a determinism violation today, independently of anything this proposal
changes.

### §5.5 already names the parent

The *Lineage-resolved parent* clause enumerates the fallback parents for a call issued from middleware or a
wrapper: "the fan-out instance span ..., the per-branch dispatch span inside a parallel branch, the innermost
of the two when both are nested (§4.3's mixed-nesting rule), the subgraph span inside a subgraph, otherwise
the invocation span". It then forbids the alternatives: the span "MUST NOT parent under a shared fan-out node
span, a shared parallel-branches node span, or the invocation span when a more-specific enclosing wrapper
(per §4.3) is open".

So the correct parent for a branch-middleware orphan is the branch's dispatch span, and for a fan-out
instance orphan the instance's dispatch span. Neither is a new rule.

### What blocks the correct answer

§6 makes dispatch-span synthesis lazy, and gives its reason: the span "is created on the first inner event
for each branch, not eagerly at the parallel-branches NODE's `started`. This keeps the synthesis observable
from existing NodeEvents without requiring the engine to emit per-branch lifecycle events."

That rationale is about avoiding **new engine events**. An orphan provider event is an existing event, so
synthesizing from it preserves exactly what laziness protects. The only text that conflicts is one sentence:
"The dispatch span's start time is the moment the inner `started` event fires."

Note the asymmetry in the text: §6 pins the start time of the **branch** dispatch span and says nothing about
the **fan-out instance** dispatch span, although downstream measurement confirms both are synthesized by the
same path with the same trigger and both race identically. The text is asymmetric where the behaviour is not.

## Detailed design

### §5.5: resolve structurally

Append to *Lineage-resolved parent*:

> **Resolution is structural.** The enclosing wrapper is determined by the call's position in the graph, not
> by which spans an observer has materialized at the moment it resolves the parent. A call issued from a
> parallel branch's middleware is inside that branch and its enclosing wrapper is that branch's dispatch
> span; a call issued from a fan-out instance's middleware is inside that instance. An implementation **MUST
> NOT** select a different parent because a wrapper span has not yet been created, and **MUST NOT** let the
> selected parent depend on the ordering between the provider event and any other event.

### §6: synthesis is triggered by the first event that needs the span

Replace the start-time sentence, and state the same rule for both dispatch-span kinds:

> A dispatch span (per-branch or per-fan-out-instance) is synthesized on the **first event that needs it**,
> whichever arrives first: an inner node's `started` event, or a provider event whose lineage places it
> inside that branch or instance. Its start time is the moment of that triggering event. A later event that
> would also have triggered synthesis reuses the existing span rather than creating a second one.
>
> The synthesis remains **lazy** in the sense §6 intends: it is driven by events the engine already emits and
> requires no per-branch or per-instance lifecycle event.

The start time becoming earlier is a fidelity improvement rather than a concession. A dispatch span that
starts at the first inner node understates the branch's extent whenever branch middleware does work first,
which is precisely the case under discussion.

### Fixtures

Fixtures 152 and 153 assert the parents §5.5 already mandates and need no change. They are currently deferred
downstream because they pass only on a favourable interleaving. They un-defer when an implementation resolves
structurally, and they should be required to pass **with** a yielding wrapper, since passing only without one
demonstrates the defect rather than the fix.

No new fixture is added. 152 and 153 between them already assert both dispatch-span kinds as the fallback
parent, which is the whole of what this proposal makes reachable.

## Conformance test impact

**No fixture changes.** 152 and 153 are correct as written; this makes them satisfiable.

**One implementation obligation.** Structural resolution is new text, though it makes explicit what §5.5's
enumeration already required rather than adding a parent it did not name. §5.5's MUST NOT against the shared
fan-out node span, the shared parallel-branches node span and the invocation span is untouched and remains
binding as it stands.

**Determinism.** After this, an orphan's parent is a function of the event stream alone, which is what §10
already requires of it.

## Alternatives considered

1. **Resolve at emit time**, making the parent whatever wrapper span is open when the call is made.
   Rejected: for a `pre`-phase branch-middleware orphan that yields the parallel-branches NODE span or the
   invocation, which §5.5 forbids by name. It is deterministic, but deterministically wrong, and it would
   require amending §5.5's enumeration and retiring fixture 152.
2. **Buffer the orphan** until its enclosing wrapper appears. Rejected: it holds a parent decision open for an
   unbounded period with no principled rule for when to give up, trading a determinable answer for an
   indeterminable wait.
3. **Emit per-branch and per-instance lifecycle events from the engine**, so dispatch spans can be opened
   eagerly. Rejected: that is precisely the cost §6's laziness exists to avoid, and it changes the engine's
   event surface to fix an observer-side materialization detail.
4. **Fix only the branch dispatch span**, since that is what the downstream report raised. Rejected:
   downstream measurement shows both kinds are synthesized by the same path with the same trigger and both
   race identically. A branch-only fix would leave the defect standing on the other kind, and would preserve
   an asymmetry that exists in §6's text (which pins the branch span's start time and is silent on the
   instance span's) but not in the behaviour.

## Open questions

1. **Whether the structural-resolution rule should be stated once in §4.3** rather than appended to §5.5.
   §4.3 owns the parent-child rules §5.5 defers to, so the principle arguably belongs there and would then
   cover any future span kind. §5.5 is where the fallback is defined and where an implementer looks, which is
   why this proposal puts it there; the two placements are not exclusive.
