# 0124: Resolve an Orphan Provider Span's Parent Structurally

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:** 2026-09-03
- **Targets:**
  - spec/observability/spec.md **§5.5 *Lineage-resolved parent***: state that the fallback parent is resolved
    **structurally**, from the call's position in the graph, not from which spans the observer has
    materialized at the moment it resolves. The rule already names the correct parents; what it does not say
    is that an observer-side materialization detail cannot change the answer.
  - spec/observability/spec.md **§6**: replace both the synthesis **trigger** ("On the first inner `started`
    event received ...") and the sentence pinning the per-branch dispatch span's **start time** to that event.
    Synthesis is triggered by the first event that needs the span, whichever arrives first. State the same for
    the **fan-out instance span**, which §6 leaves without a synthesis paragraph while giving the branch one.
    A fifth statement of the trigger sits three paragraphs below at **:1808** ("the dispatch span is created
    on the first inner event for each branch"). On the reading §6 uses at :1777, an "inner event" is an event
    from a node inside the branch, which an orphan issued from the branch's middleware is not, so :1808 can be
    read as still confining synthesis. It is widened to match rather than left to be read either way.
  - spec/observability/spec.md **§5.7**: the sentence reads "The branch's `branch_name` is sourced from the
    first inner event of that branch (`event.branch_name`)." Under the amended trigger the sourcing event may
    be a provider event instead of an inner-node one, so the sentence is re-anchored to the triggering event.
    Both event kinds carry `branch_name`.
  - spec/observability/spec.md **§5.4**: give the fan-out instance span the synthesis statement the
    per-branch dispatch span has, so the two are stated symmetrically rather than one pinned and one silent.
  - spec/observability/spec.md **§8.4.8**: the Langfuse observer synthesizes its dispatch Span "lazily, on the
    first inner observation of each branch", the same trigger with the same defect. Re-anchor it, or make it
    defer to §6 so the two cannot drift.
  - spec/observability/spec.md **§8.4.3, §8.4.5, §8.4.6, §8.4.7**: four Langfuse counterparts restate the
    parent resolution in the temporal terms being replaced: **:2485** (§8.4.3) promises that "the Langfuse
    observation tree and the OTel span tree produce the same parent for the nested and orphan cases" while
    routing to "the nearest open ancestor observation", and **:2630**, **:2712** and **:2725** each say "or
    the nearest open ancestor when it is closed". Left alone, §5.5 would make the parent structural while
    these four keep walking to the nearest **open** ancestor, so the two trees disagree on exactly the
    interleaving this proposal exists to fix and §8.4.3's parity promise becomes false in shipped text. They
    take the same structural-enclosure rewording, or defer to §5.5.
  - spec/observability/spec.md **§5.5, §5.5.8, §5.5.11, §5.5.13**: six cross-references condition the
    fallback on the calling node's span being "not open" or on a more-specific wrapper being "open". They are
    enumerated by line rather than counted, since a count is what an accept author would work from and stop
    short on: **:838**, **:862** and **:870** in §5.5 itself, plus **:1341** (§5.5.8), **:1461** (§5.5.11) and
    **:1520** (§5.5.13). Those conditionals are what the structural rule below replaces, so they are reworded
    to key on structural enclosure rather than span openness.
  - spec/conformance-adapter/spec.md **§5.1**: add a `yield_after_call` sub-key to
    `calls_llm_from_wrapper`, without which no fixture can distinguish an implementation that resolves
    structurally from one that passes on a favourable interleaving. The entry's proposed text:

    > **`yield_after_call: <bool>`** (default `false`) - when `true`, the adapter **MUST** yield control
    > between the provider call returning and the wrapper returning, in a way that lets observer delivery
    > queued before that point make progress. The obligation is on what the yield achieves, not on the
    > host language's mechanism for achieving it. When `false` the wrapper returns immediately after the
    > call, which is the behavior every fixture carrying `calls_llm_from_wrapper` has today.
  - spec/observability/conformance/133, 134, 152 and 153: set `yield_after_call: true` on all four. These
    are every fixture that already carries `calls_llm_from_wrapper`, and 133 and 134 exercise the same orphan
    resolution against the same not-yet-synthesized wrapper span, so leaving them without the control leaves
    them passing on the favourable interleaving. 134 case 2
    (`orphan_generation_parents_under_inner_fan_out_instance_observation`) is the only Langfuse orphan case in
    the corpus, so without it the amended §8.4.8 trigger ships with nothing on the Langfuse surface able to
    fail it. No assertion changes; all four already assert the parent §5.5 mandates.
- **Related:** 0084 (introduced the *Lineage-resolved parent* clause and the lineage-aware span keying),
  0044 (introduced per-branch dispatch spans)

## Summary

A provider call issued from a wrapper resolves its parent when the observer drains the event, while §6
synthesizes a dispatch span on its first inner node's `started`. Under the pre-phase wrapper the provider
event is queued first, so the span an orphan needs does not yet exist when the orphan resolves. The wrong
parent that follows is **either intermittent or constant depending on the observer's architecture**, and the
spec constrains neither architecture today. §5.5 already names the correct parent; this states that the answer
is structural, removes the sentences in §6 that make the correct answer unreachable, and reconciles the four
further texts that restate the trigger or the temporal resolution it replaces.

## Motivation

### The parent is wrong in two different ways

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

In the second ordering the orphan parents under the invocation root. A single yield is enough, and yielding is
ordinary for real middleware: any network call, any lock, any sleep.

That trace comes from an observer that publishes span state **synchronously, in the engine's execution path,
before the engine queues the event**, so that a span is in context before the node body runs. Registration and
resolution then sit on two different timelines, and graph-engine §6's serial-delivery guarantee does not order
them against each other: it orders queued events, and one of these two operations is not a queued event.
Unqualified `§6` elsewhere in this proposal means observability §6, the section being amended.

**An observer that does all its work on the delivery queue has the same defect in a different shape.** There
the ordering is fixed, not raced. Graph-engine §6 dispatches the provider event before `complete()` returns,
and a pre-phase wrapper calls `complete()` before the node runs, so the provider event precedes the inner
`started`. The dispatch span therefore does not exist when the orphan resolves, and the orphan parents under
the invocation root on every run. Consistently wrong rather than intermittently wrong. This holds for a
`pre`-phase wrapper, which is what all four affected fixtures declare; a `post`-phase orphan arrives after the
branch's inner node has started, so the span is already there and only the two-timeline shape can miss it.

Both shapes conform to the spec as written, because nothing requires an observer to do its work in one place
or the other. So this is not one implementation's bug: the spec admits two architectures and gives the wrong
answer under both.

**The racy shape is additionally non-conforming.** §10 scopes determinism to the §6 event stream and excludes
only implementation-specific data, naming timestamps, span IDs and trace IDs. Parentage is structure derived
from the event stream, so it falls inside the portion §10 covers and the conformance suite asserts. A parent
that varies with a scheduling accident is a determinism violation today, independently of anything this
proposal changes. The queue-only shape is deterministic and so does not violate §10; it is simply wrong
against §5.5's enumeration. That difference is why the fix has to be structural rather than a determinism
patch.

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
synthesizing from it preserves exactly what laziness protects.

**Five texts conflict, not one.** §6 states the trigger ("On the first inner `started` event received ...")
and separately pins the start time ("The dispatch span's start time is the moment the inner `started` event
fires"), and restates the trigger a third time at :1808 ("the dispatch span is created on the first inner
event for each branch"). §5.7 sources the branch's `branch_name` "from the first inner event of that branch".
And §8.4.8 gives the Langfuse observer the same trigger, synthesizing "lazily, on the first inner observation
of each branch". A change that touched only the start-time sentence would leave four statements asserting the
trigger it replaces.

The Langfuse surface carries the defect twice over. Beyond §8.4.8's trigger, §8.4.3, §8.4.5, §8.4.6 and §8.4.7
route a provider observation to "the nearest open ancestor" when its own is closed, which is the temporal
resolution §5.5 is being moved away from. §8.4.3 additionally promises that the Langfuse and OTel trees
"produce the same parent for the nested and orphan cases", so leaving those four alone would make that promise
false in shipped text the moment §5.5 becomes structural. They take the same rewording.

Note also an asymmetry in the text: §6 gives the **per-branch dispatch span** a synthesis paragraph and a
pinned start time, and gives the **fan-out instance span** neither, although downstream measurement confirms
both are synthesized by the same path with the same trigger, so both carry the defect in the same shape. The
text is asymmetric where the behaviour is not.

## Detailed design

### §5.5: resolve structurally

Append to *Lineage-resolved parent*:

> **Resolution is structural.** The enclosing wrapper is determined by the call's position in the graph, not
> by which spans an observer has materialized at the moment it resolves the parent. A call issued from
> middleware or a wrapper anywhere inside a parallel branch, whether the branch's own middleware
> (pipeline-utilities §11.7) or middleware around a node within it, is inside that branch, and its enclosing
> wrapper is that branch's per-branch dispatch span. A call issued from middleware or a wrapper anywhere
> inside a fan-out instance, whether the instance's own middleware (pipeline-utilities §9.7) or middleware
> around a node within it, is inside that instance, and its enclosing wrapper is that fan-out instance span.
>
> This rule binds **where the event's lineage identifies the enclosing instance or branch**. Where it does not,
> because the middleware ran outside the engine's per-instance or per-branch scope and pipeline-utilities
> leaves resolving to the wrapped instance or branch a SHOULD rather than a MUST, the observer **MUST** parent
> the span under the nearest enclosing wrapper its lineage does identify, and §5.5's MUST NOT against the
> shared node span and the invocation span does not apply to that case.
>
> An implementation **MUST NOT** select a different parent because a wrapper span has not yet been created,
> and **MUST NOT** let the selected parent depend on the ordering between the triggering event and any other
> event.

**The existing conditionals are reworded, not left standing.** §5.5's fallback fires "when the calling node's
span is **not open**", and its MUST NOT applies "when a more-specific enclosing wrapper (per §4.3) is **open**".
Both phrases are temporal, and leaving them beside a rule that says resolution is structural would put the
ambiguity inside one clause instead of removing it. They key on structural enclosure instead: the fallback
fires when the calling node's span is not the call's immediate enclosure, and the MUST NOT applies when a
more-specific wrapper per §4.3 encloses the call. The same rewording is owed to the three cross-references in
§5.5.8, §5.5.11 and §5.5.13 (:1341, :1461, :1520), which repeat "when that span is not open" verbatim, and to
the two further openness clauses inside §5.5 itself (:838, :870). The Targets enumerate all six by line
rather than by count.

### §6: synthesis is triggered by the first event that needs the span

Replace the start-time sentence, and state the same rule for both dispatch-span kinds:

> An observer **MUST** synthesize a per-branch dispatch span, or a fan-out instance span, on the **first event
> that needs it**, whichever arrives first: an inner node's `started` event, or any event whose span resolves
> under §5.5's *Lineage-resolved parent* to that branch or instance. A later event that would also have
> triggered synthesis **MUST** reuse the existing span rather than create a second one.
>
> The span's start time is the moment of the triggering event, which under this rule may be a provider event
> rather than an inner node's `started`.
>
> The synthesis remains **lazy** in the sense §6 intends: it is driven by events the engine already emits, and
> requires no per-branch or per-instance lifecycle event.

The trigger is stated over "any event whose span resolves under §5.5's *Lineage-resolved parent*" rather than
over provider events, because §5.5's rule is already shared by the LLM, embedding, tool-execution and rerank
spans. Enumerating one kind would leave the other three to inference.

**The rule converges the two architectures, which is the strongest argument for it.** The orphan provider event
is the first event that needs the span under *both* readings above. An observer that registers spans in the
engine's execution path and one that does everything on the delivery queue therefore synthesize at the same
point in the event stream and produce the same parent, even though the two disagree about when registration
happens relative to delivery. The alternative fixes do not have this property: resolving at emit time gives the
two architectures different answers, and buffering leaves the queue-only shape waiting for an event that has
already passed. A rule that makes observer architecture unobservable in the span tree is what portability
requires here, and it is why this proposal takes the on-demand synthesis rather than either neighbour.

**Why the start-time sentence changes at all.** §6 currently pins the start to "the moment the inner `started`
event fires". Under the amended trigger the synthesizing event may be a provider event instead, so leaving the
sentence would pin the start to an event that no longer necessarily triggers synthesis. Re-anchoring it to the
triggering event is the minimum the trigger change forces.

Moving the start earlier is a fidelity improvement rather than a concession: a dispatch span that starts at the
first inner node understates the branch's extent whenever branch middleware does work first, which is precisely
the case under discussion.

**What this proposal deliberately does not state.** A provider call is made before its event is drained, so a
span synthesized at drain time can still start *after* a span it then adopts as a child, producing a parent
that starts later than its own child. That is malformed in every trace viewer. An earlier revision of this
proposal added a start-ordering **MUST NOT** to forbid it. That is withdrawn: no assertion shape on either
observer surface can express relative span start order, and observability §10 puts timing outside what the
suite asserts, so the rule could not be tested and `GOVERNANCE.md` requires new behavior to have tests. The
hazard is recorded in *Open questions* with the vocabulary it would need.

### Fixtures

Four fixtures carry `calls_llm_from_wrapper` today: **133, 134, 152 and 153**. All four assert the parents
§5.5 already mandates, so no assertion changes. But against an observer that registers spans in the engine's
execution path, none can currently fail: each passes on a favourable interleaving, and nothing in the fixture
vocabulary makes a wrapper yield, so an implementation that resolves at drain time and one that resolves
structurally are indistinguishable to the suite.

That is why `calls_llm_from_wrapper` gains a **`yield_after_call` sub-key** in conformance-adapter §5.1,
boolean and defaulting to `false`. **All four set it to `true`**, which forces the interleaving that
currently makes the defect invisible. Restricting the control to 152 and 153 would leave 133 and 134 exercising
the same orphan resolution against the same not-yet-synthesized wrapper span while still passing for the wrong
reason, and 134 case 2 (`orphan_generation_parents_under_inner_fan_out_instance_observation`) is the only
Langfuse orphan case in the corpus, so omitting it would leave the amended §8.4.8 trigger with nothing on the
Langfuse surface able to fail it.

**The control is inert for a queue-only observer, and the fixtures still discriminate there.** With one
timeline there is nothing to reorder, so the yield changes no ordering. It does not need to: that architecture
produces the wrong parent on every run, so a non-conforming adapter fails these fixtures without any help, and
a conforming one synthesizes on the orphan and passes. The control is necessary for the two-timeline shape and
harmless for the other, rather than being the thing the assertion depends on. This is worth stating because the
opposite arrangement, where a directive an adapter treats as a no-op is what makes a fixture meaningful, is the
silent-pass shape the surrounding proposals exist to close, and a reader is right to check for it here.

No new fixture file is added. The four between them cover both wrapper kinds on both observer surfaces; what
they lacked was the ability to provoke the unfavourable ordering where one exists to provoke.
`yield_after_call` earns the structural MUST NOTs, which are the only new normative rules this proposal
ships.

### Terminology

The spec names these two spans differently: a **per-branch dispatch span** (§5.7, §6) and a **fan-out instance
span** (§5.4, §4.3). This proposal uses both terms as the spec does rather than coining a collective
"dispatch span" for the pair, since §8.4.8 and §4.3 already use "dispatch span" for the parallel-branches one
specifically and a widened sense would make those references ambiguous. Where a statement covers both, it
names both.

## Conformance test impact

**Four fixtures gain the control.** 133, 134, 152 and 153 each add `yield_after_call: true` to their
`calls_llm_from_wrapper` block. No assertion changes in any of them: their expected parents are the ones §5.5 already
mandates, and the control exists to force the interleaving that currently lets a non-conforming implementation
pass.

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
   require amending §5.5's enumeration and retiring fixture 152. It also gives the two observer architectures
   different answers, since which wrapper span is open at emit time depends on whether the observer registers
   spans in the engine's execution path.
2. **Buffer the orphan** until its enclosing wrapper appears. Rejected: it holds a parent decision open for an
   unbounded period with no principled rule for when to give up, trading a determinable answer for an
   indeterminable wait. It is not equally bad in both architectures, which is itself a reason to reject it: a
   queue-only observer would resolve the buffered orphan correctly once the inner `started` drains, while the
   two-timeline shape may already have registered the span, so the two differ in how long the decision hangs
   open rather than in the answer.
3. **Emit per-branch and per-instance lifecycle events from the engine**, so dispatch spans can be opened
   eagerly. Rejected: that is precisely the cost §6's laziness exists to avoid, and it changes the engine's
   event surface to fix an observer-side materialization detail.
4. **Fix only the branch dispatch span**, since that is what the downstream report raised. Rejected:
   downstream measurement shows both kinds are synthesized by the same path with the same trigger, so both
   carry the defect in whichever shape the observer's architecture produces. A branch-only fix would leave the
   defect standing on the other kind, and would preserve
   an asymmetry that exists in §6's text (which pins the branch span's start time and is silent on the
   instance span's) but not in the behaviour.

## Open questions

1. **Whether the structural-resolution rule should be stated once in §4.3** rather than appended to §5.5.
   §4.3 owns the parent-child rules §5.5 defers to, so the principle arguably belongs there and would then
   cover any future span kind. §5.5 is where the fallback is defined and where an implementer looks, which is
   why this proposal puts it there; the two placements are not exclusive.
2. **How a relative span start-ordering constraint could be asserted at all.** Moving the synthesis trigger
   earlier does not remove the case where a span synthesized at drain time starts after a span it adopts as a
   child. An earlier revision of this proposal forbade it with a **MUST NOT**, withdrawn because nothing can
   test it: `expected.span_tree` carries a name, subset attribute assertions, status, optional links and
   children, the Langfuse observation shape is equally start-time-free, and observability §10 excludes
   timing-derived attributes and exact timestamps from what the suite asserts. Closing it needs a relative
   start-ordering assertion shape on both observer surfaces plus a §10 carve-out narrow enough not to
   reintroduce timestamp comparison generally. That is a conformance-vocabulary change that should be measured
   across capabilities rather than attached to this proposal.
