# 0065: Pipeline Utilities — Failure-Isolation Event Cause-Fidelity at Non-Node Wrapping Sites

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-11
- **Accepted:** 2026-06-11
- **Targets:** spec/pipeline-utilities/spec.md (§6.3 — the `caught_exception` field definition gains a carrier-wrapper unwrap clause: at any non-node placement where the engine has wrapped the originating error as a graph-engine §4 `node_exception` before the isolation middleware catches it — §9.7 instance middleware, §11.7 branch middleware, or parent-node middleware on a fan-out / parallel-branches node (§9.6 / §11.6) — `caught_exception.category` MUST reflect the originating `__cause__` category, mirroring §6.1's existing classifier unwrap; plus message-coherence and wrapped-instance/branch lineage SHOULD-clauses)
- **Related:** 0050 (introduced §6.3 `FailureIsolationMiddleware` + the failure-isolation event whose fidelity this tightens, and §6.1's default classifier whose carrier-wrapper unwrap this mirrors), 0009 / 0036 (fan-out — the §9.7 instance-middleware site), 0011 (parallel branches — the §11.7 branch-middleware site), graph-engine §4 (`node_exception` carrier wrapper + `__cause__`)
- **Supersedes:**

## Summary

Proposal 0050's §6.3 defines the failure-isolation event's `caught_exception`
as "the caught exception's category (per its carrying spec)," and frames the
whole section around the node-level three-piece composition (node body → inner
Retry → outer FailureIsolation). At node level that is faithful: graph-engine
wraps a raw error as a §4 `node_exception` *outside* a node's middleware chain,
so a node-level isolation middleware catches the **raw** error (e.g.
`ProviderUnavailable`, category `provider_unavailable`) and the reported
category is correct.

But §6.3 also blesses non-node placements — **§9.7 instance middleware** and
**§11.7 branch middleware** (and parent-node middleware on a fan-out /
parallel-branches node, §9.6 / §11.6). At those sites the engine has
**already** wrapped the originating error as a §4 `node_exception` *before* the
isolation middleware catches it, so `caught_exception.category` is literally
`node_exception` and the originating cause (`provider_unavailable`, etc.) is
masked. §9.7 and §11.7 are where this was reported; the rule below covers them
all uniformly.

This proposal tightens §6.3: `caught_exception.category` MUST reflect the
**originating** failure — unwrapping a graph-engine §4 `node_exception` carrier
wrapper to its `__cause__` — at every wrapping site, exactly the unwrap §6.1's
default retry classifier already mandates. Node-level placement is unchanged
(no wrapper is present, so nothing to unwrap). A companion SHOULD-clause
addresses the related lineage symptom.

## Motivation

The failure-isolation event exists to tell a consumer **why** an instance or
branch was isolated. At a wrapping site `node_exception` is un-actionable — a
consumer cannot tell "isolated because the provider was down" (retry-worthy
signal, capacity alarm) from "isolated because of a logic bug" — whereas
`provider_unavailable` is exactly the actionable detail. The
"retry-transients-then-degrade-on-exhaustion" pairing that §6.3's own
composition example describes is a natural **instance-middleware** use
(`instance_middleware = (FailureIsolation, Retry)`, isolation outer), which is
precisely the §9.7 site where the masking occurs.

The fix is a **consistency** one, not a new behavior. §6.1's default classifier
*already* looks through the `node_exception` carrier wrapper to find the real
category — its normative text reads: "All graph-engine §4 errors except as
carrier wrappers (a `node_exception` whose `__cause__` is a transient category
MUST be classified as transient)." So within the same §6 bundled middleware
set, retry decisions unwrap the carrier wrapper while the isolation event does
not. Mandating the same unwrap on §6.3 closes that internal inconsistency.

This is an **underspecified interaction, not a conformance bug**: §6.3 was
written around the node-level model, and the category semantics at the blessed
non-node sites were never pinned. A literal reading ("the middleware genuinely
caught a §4 `node_exception`") is defensible — which is exactly why the
resolution is a spec ruling rather than a quiet implementation patch.

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0). The concrete spec version is assigned at acceptance.

### pipeline-utilities §6.3 — `caught_exception` carrier-wrapper unwrap

The §6.3 `caught_exception` field definition currently reads (in essence): "a
structured record carrying the caught exception's category (per its carrying
spec, e.g., llm-provider §7 / graph-engine §4) and the exception message; when
the caught exception does not carry a category, the category field is `null`."

It gains a **cause-fidelity clause**:

> **Cause fidelity at wrapping sites.** `caught_exception.category` MUST reflect
> the **originating** failure. When the caught exception is a graph-engine §4
> `node_exception` carrier wrapper — as it is at any non-node placement where
> the engine has wrapped the originating error before the isolation middleware
> catches it (**§9.7 instance middleware**, **§11.7 branch middleware**, or
> **parent-node middleware on a fan-out / parallel-branches node** per §9.6 /
> §11.6) — the middleware MUST resolve through the carrier wrapper to the
> originating cause (`__cause__`) and report *that* category. This is the same
> carrier-wrapper resolution §6.1's default classifier mandates ("a
> `node_exception` whose `__cause__` is a transient category MUST be classified
> as transient"). Resolution walks nested carrier wrappers to the originating
> cause — e.g. a parent-node middleware on a parallel-branches node catches the
> engine's `parallel_branches_branch_failed` wrapper (a §4 `node_exception`
> subtype, §11.9), whose `__cause__` chain leads to the branch's originating
> failure. When the originating cause itself
> carries no category (e.g., a bare `ValueError`), the category field is `null`
> per the existing rule. At **node-level** placement no carrier wrapper is
> present (the middleware catches the raw error), so no unwrap applies and
> behavior is unchanged.

**Message coherence.** When the category is resolved from a carrier wrapper
(above), `caught_exception.message` SHOULD describe the **same** originating
cause — i.e., source the message from the resolved `__cause__`, not the
`node_exception` wrapper — so the event's `category` and `message` refer to one
exception rather than pairing a `provider_unavailable` category with a generic
wrapper message. Implementations MAY append wrapper context, but the originating
cause is the primary message; the exact composition is left to per-language
ergonomics.

### pipeline-utilities §6.3 — wrapped-instance/branch lineage (SHOULD)

The event's lineage tuple (`namespace` / `fan_out_index` / `branch_name`,
sourced from the graph-engine §6 event-source identity) shares the same root
cause: at the §9.7 / §11.7 sites the isolation middleware runs *outside* the
engine's per-instance / per-branch scope, so the lineage can resolve to the
**wrapping** node's identity rather than the isolated instance's / branch's
(the symptom: `fan_out_index = null`, `namespace` = the fan-out node's).

§6.3 gains a SHOULD-clause:

> Where the per-instance / per-branch identity is recoverable, the failure-
> isolation event's lineage (`fan_out_index`, `branch_name`, `namespace`) SHOULD
> resolve to the **wrapped** instance / branch rather than the wrapping node.

This is a **SHOULD**, not a MUST, because recovering the per-instance identity
may require the engine to surface it to the outer (wrapping-site) middleware —
a graph-engine change beyond this proposal's scope. The **category** fidelity
above is the MUST: it is the actionable contract and needs only exception
inspection (the `__cause__` chain is already on the caught exception). A
follow-on MAY tighten lineage to MUST if the engine grows a way to surface the
wrapped identity to wrapping-site middleware.

## Conformance test impact

### New / extended fixture

A fixture under `pipeline-utilities/conformance/` (number assigned at
acceptance), exercising `FailureIsolationMiddleware` at the wrapping sites:

- **Case 1 — §9.7 instance site, transient cause.** A fan-out whose instances
  each raise `ProviderUnavailable` (category `provider_unavailable`), with
  `instance_middleware = (FailureIsolation, Retry)` (isolation outer, retry
  inner). Assert one failure-isolation event per instance with
  `caught_exception.category == "provider_unavailable"` (**not**
  `node_exception`), and that the degrade behavior is unchanged (the batch
  completes with the degraded placeholder).
- **Case 2 — §11.7 branch site.** `FailureIsolationMiddleware` as branch
  middleware over a branch whose inner node raises a categorized error; assert
  the event's `caught_exception.category` resolves through the branch's
  `node_exception` to the originating category. (Verified at acceptance against
  §11: branch middleware wraps the branch's subgraph invocation and catches the
  inner node's `node_exception` — a single carrier wrapper whose `__cause__` is
  the originating failure. The engine's `parallel_branches_branch_failed`
  wrapper is raised at the parallel-branches *node* level per §11.9, so it is
  caught by parent-node middleware (§11.6), not branch middleware.)
- **Case 3 — node-level placement unchanged.** A node-level isolation
  middleware catching a raw `ProviderUnavailable`; assert
  `caught_exception.category == "provider_unavailable"` with no behavioral
  change from 0050 (guards against a double-unwrap regression).
- **Case 4 — uncategorized cause.** Originating cause is a bare `ValueError`;
  assert `caught_exception.category == null` at a wrapping site (the unwrap
  finds no category, per the existing rule).

The lineage SHOULD-clause is asserted as best-effort (or annotated as
non-normative in the fixture) consistent with its SHOULD status.

### Unaffected

0050's existing §6.3 fixtures (node-level placement, catch/degrade behavior)
continue to pass unchanged — this proposal tightens the wrapping-site category
contract, not the node-level path or the catch/degrade semantics.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments
(concrete version assigned at acceptance):

- §6.3's `caught_exception` definition gains the cause-fidelity (carrier-wrapper
  unwrap) clause — a MUST — and the wrapped-lineage SHOULD-clause.
- A conformance fixture exercises the §9.7 / §11.7 wrapping sites + the
  unchanged node-level path + the uncategorized-cause case.

**Behavior-change note.** An implementation that today reports
`caught_exception.category = node_exception` at the §9.7 / §11.7 sites will,
after this lands, report the originating category. This is the intended
fidelity improvement; the catch/degrade behavior (correct everywhere today) is
untouched, so no graph execution outcome changes — only the event's reported
cause. The node-level path is unchanged.

**MINOR vs PATCH.** Classified MINOR because the emitted
`caught_exception.category` (and `message`) values change at the wrapping sites
— a change to conformance expectations. Because the change also reads as a
*clarification* of an interaction §6.3 left underspecified, a PATCH
classification is defensible; the concrete bump is the maintainer's call at
acceptance.

## Out of scope

- **Node-level placement.** Already faithful (no carrier wrapper present);
  unchanged by this proposal.
- **The middleware's catch / degrade behavior.** Correct at every wrapping site
  today (the batch completes with the degraded update); this proposal touches
  only the event's reported cause / lineage, not the recovery behavior.
- **Mandating lineage fidelity (MUST).** Kept SHOULD — recovering the
  per-instance / per-branch identity at a wrapping site may require the engine
  to surface it to the outer middleware (a graph-engine change). Left as a
  follow-on tightening; the actionable contract (category) is the MUST here.
- **§6.1 classifier nested-wrapper wording.** §6.1's carrier-wrapper rule is
  written single-level ("a `node_exception` whose `__cause__` is …"); whether it
  should also be stated to walk nested wrappers is a separate §6.1 clarification,
  not opened here. §6.3's unwrap is specified to resolve to the originating cause
  regardless of nesting so the event is faithful at the branch site.
- **Promoting the failure-isolation event to a typed observer-union variant.**
  Independent of cause fidelity; remains the deferred carve-out 0050 noted.

## Alternatives considered

- **Node-level-only / coarse-by-design** (the rejected resolution (b)). Declare
  §6.3's cause + lineage fidelity contracted only for node-level placement; at
  §9.7 / §11.7 the category is the boundary `node_exception` and per-cause
  detail is expected on the inner node's own events (the subgraph's
  `LlmFailedEvent` / `NodeEvent`). Rejected: it gives a consumer reading the
  isolation event an un-actionable `node_exception` exactly where isolation
  fired, and it is internally inconsistent with §6.1's classifier, which
  already unwraps the same carrier wrapper for retry decisions. Pushing the
  consumer to cross-correlate inner node events to recover the cause defeats the
  event's purpose.
- **Mandate lineage fidelity as a MUST** alongside the category MUST. Rejected
  for this proposal: it likely requires a graph-engine change to surface the
  per-instance / per-branch identity to wrapping-site middleware, widening scope
  beyond the cheap, exception-inspection-only category fix. Left as a documented
  SHOULD with a follow-on path.
- **Patch the implementation without a spec change.** Rejected: §6.3's
  wrapping-site category semantics are genuinely underspecified, so a silent
  implementation change would diverge from the (defensible) literal reading
  other implementations might adopt. The contract belongs in spec text so every
  implementation converges.
- **Do nothing.** Rejected: the event masks the cause at two of the three sites
  §6.3 blesses, and it does so in the natural retry-then-degrade
  instance-middleware posture, not a hypothetical edge case.
