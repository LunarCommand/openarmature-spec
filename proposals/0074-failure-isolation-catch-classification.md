# 0074: Failure-Isolation Cause-Chain Catch Classification

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-18
- **Accepted:** 2026-06-18
- **Targets:** spec/pipeline-utilities/spec.md (§6.3 *Failure isolation* — add an optional `catch` configuration field: a set of error categories matched against the caught exception's cause chain via the new §6.4 primitive, additive and composing with `predicate`; `predicate` documented as surface-only with the cause-aware alternatives; behavior block updated. New **§6.4 *Cause-chain classification*** — promotes §6.3's carrier-skipping cause-fidelity walk to a public, named classification primitive (cause chain + derived category) shared by §6.1 / §6.3 / consumers; appended after §6.3, no renumber. §6.1 *Retry* — document the default classifier's single-level depth as deliberate. Plus a new conformance fixture under `spec/pipeline-utilities/conformance/`.)
- **Related:** 0050 (failure-isolation + retry middleware — the §6.1 `classifier` + §6.3 `predicate` this extends), 0065 (cause-fidelity at wrapping sites — established that `caught_exception.category` resolves through the carrier), 0068 (structured `caught_exception.chain` + derived category — the full-chain carrier-skipping derivation this exposes), 0069 (fan-out degrade refinements). Depends on graph-engine §4 (`node_exception` carrier + cause preservation).
- **Supersedes:**

## Summary

The §6.3 failure-isolation `predicate` decides the catch on the **surface** exception, but the same
middleware's `caught_exception.category` (proposal 0068) is derived from the **full, carrier-skipped
cause chain**. At the §9.7 instance / §11.7 branch / §9.6 · §11.6 parent-node wrapping placements the
engine has already wrapped the failure in one or more graph-engine §4 `node_exception` carriers before
the isolation middleware catches it — so a surface category or exception-type check sees the carrier,
not the originating failure, returns "don't catch," and re-raises, **inverting an intended degrade into
a crash** on exactly the degrade-vs-crash boundary where a silent miss is most damaging.

This proposal (1) adds a first-class **`catch`** gate to §6.3 — a set of error categories matched
against the cause chain via the same carrier-skipping walk — so the common "degrade on these failure
categories" case is correct by construction; (2) promotes that walk to a public **§6.4 cause-chain
classification** primitive shared by retry (§6.1), isolation (§6.3), and consumers; and (3) documents
§6.1's default-classifier depth as deliberately single-level, distinct from §6.3's full-chain degrade
classification. `catch` is additive (default catch-all preserved); retry behavior is unchanged.

## Motivation

A downstream consumer composing inner `RetryMiddleware` + outer `FailureIsolationMiddleware` — "retry
the transients, degrade-don't-abort on exhaustion" — needed the isolation gate to express "catch this only if it is a provider
failure," degrading on provider faults while letting deploy-misconfiguration and
genuine node bugs crash loudly. The obvious gate, a surface type/category check, is **wrong precisely at
the placements where it matters**: at instance / branch / parent-node-middleware placements the graph
engine wraps the real error in a `node_exception` carrier (§6.3 *Cause fidelity*; graph-engine §4), so
the exception reaching the isolation layer carries the provider failure as a cause, not on the surface.
A surface check returns "no" on the carrier and re-raises — a wrapped failure that should have degraded
crashes the run. At a plain node-level placement the same gate sees the error raw, so the miss stays
invisible until failure isolation moves under a wrapping placement (which a fan-out-degrade migration
does).

The framework already classifies the exception correctly: §6.3 derives `caught_exception.category` by
walking the full cause chain and skipping carriers (0068). It just applies that knowledge **after** the
catch decision, for telemetry, and does not offer it to the `predicate` that makes the actual
control-flow decision. §6.1 retry does not have this problem for the common case — it ships a
category-based default classifier — but §6.3 isolation shipped with no category-based gate, so every
consumer hand-rolls a chain walk, and the natural hand-roll (a surface check) is subtly broken.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive new public surface (`catch`, §6.4); `catch` defaults
preserve the current catch-all behavior; retry behavior is unchanged (the §6.1 edit is documentation).
The concrete version is the maintainer's call at acceptance.

### §6.3 — the `catch` gate

`FailureIsolationMiddleware` gains an optional **`catch`** field: a set of error categories (the
llm-provider §7 / graph-engine §4 category enum). When supplied, an exception is caught only if the
**derived category** of its cause chain (the outermost non-carrier link's category, resolved **through**
carrier wrappers via the §6.4 cause-chain classification primitive — the same value §6.3 reports as
`caught_exception.category`) is in the set. So a carrier-wrapped provider failure at a wrapping placement
is classified correctly, where a surface check sees only the `node_exception` carrier and misses it; a
bare uncategorized error has a `null` derived category and does not match (it propagates).

`catch` matches when the **derived category** is in the set — the same value §6.3 reports as
`caught_exception.category`, so the catch decision and the catch report classify identically (and a
deliberate non-carrier re-categorization is respected, per 0068's outermost-wins derivation; a consumer
needing to match a category buried below it walks the full chain via the §6.4 primitive in a custom
`predicate`). It composes with `predicate` as a **conjunction**: an exception is caught exactly when
`(catch is unset OR the derived category is in catch) AND (predicate(surface_exc))`. Both default permissive — `catch` unset matches any category, `predicate`
defaults to always-true — so configuring one narrows on that axis and the both-unset default remains
catch-all. `catch` is the recommended gate for category-scoped degradation (mirroring §6.1's
category-based classifier and unifying the retry / isolation classification *vocabulary*); `predicate`
remains the escape hatch for genuinely custom gating. The behavior block becomes:

```
try:
    return await next(state)
except Exception as exc:
    if not (catch_gate(exc) and predicate(exc)):   # catch_gate: cause-chain category match per §6.4; both gates default permissive
        raise
    …                                               # resolve degraded_update, emit event, on_caught — unchanged
```

`predicate` is documented as evaluating the **surface** (caught) exception, with an explicit caveat that
a `predicate` inspecting the exception directly will misclassify a carrier-wrapped failure at the
wrapping placements — use `catch`, or walk the chain via the §6.4 primitive.

A per-language form of `catch` that accepts a **native exception type** MAY be offered as ergonomic
sugar that resolves to the categories that type represents. That is an implementation concern; the
normative contract is the **category set** (categories are the language-agnostic classification).

### §6.4 — Cause-chain classification (new)

§6.3's *Cause fidelity* walk — from the caught exception down its cause chain, one link per exception,
skipping graph-engine §4 `node_exception` carriers, terminating on a repeated reference — is the
canonical way OpenArmature classifies a failure through the carrier wrappers the engine adds at
subgraph / fan-out / branch boundaries. Because the catch *decision* (§6.3 `catch`), the catch *report*
(§6.3 `caught_exception`), and the retry decision (§6.1) all need the same classification,
implementations MUST expose it as a **public, named classification primitive** — not a private helper.
Given an exception it returns the ordered **cause chain** (links `{category, message, carrier}`,
outermost to innermost, per §6.3) and the **derived category** (the outermost non-carrier link's
category, or `null`). Names and shapes are implementation-defined; the contract is that the chain and
derived category are reachable by any consumer — a `catch` set, a retry classifier, a custom
`predicate`, a router, a metric — so all classify a wrapped failure identically instead of each
re-deriving the carrier-skipping walk subtly differently.

### §6.1 — classifier depth (documentation, no behavior change)

The default transient classifier inspects the surface category and its immediate cause **one level**
deep (a `node_exception` whose direct cause is transient — the existing §6.1 rule), NOT the full chain.
This is documented as **deliberate** and contrasted with §6.3's full-chain derivation: retry **re-runs**
the wrapped target, so it classifies at the granularity it re-attempts. A transient buried two or more
carriers deep (e.g., inside a subgraph's fan-out reached through a containing node) is the inner scope's
to retry — placing retry there re-attempts only the failing call, whereas an outer full-chain match
would coarsely re-run the whole subgraph / fan-out for one inner transient. A caller that genuinely
needs outer full-chain retry classification supplies a custom `classifier` that walks the chain via the
§6.4 primitive. §6.3's `catch`, by contrast, classifies full-chain because it **degrades** rather than
re-runs — where the failure originated does not change whether it is degradeable.

This is the principled resolution of the retry-vs-isolation classification question: the two share the
**vocabulary** (the category enum, the §6.4 primitive) but match at the **depth** their semantics
require — isolation full-chain (degrade is depth-independent), retry single-level by default
(re-run granularity), with the primitive available for opt-in full-chain retry.

## Conformance test impact

New fixture `pipeline-utilities/conformance/072-failure-isolation-catch-cause-chain` (two cases): at a
§9.7 instance placement where the engine wraps the instance failure in a `node_exception` carrier, (1)
`catch=[provider_unavailable]` matches the originating category through the carrier and degrades, where
a surface check would miss it; (2) a non-matching `catch=[provider_rate_limit]` rejects and the
exception propagates as `node_exception`. The existing `predicate` fixture (060) and cause-fidelity
fixtures (064 / 066) are unchanged. The §6.4 primitive is an API-exposure mandate (no standalone
fixture); it is exercised through `catch`. The §6.1 change is documentation (no fixture).

## Alternatives considered

- **Upgrade `predicate` to receive the cause chain.** Rejected: it would change `predicate`'s
  established surface-exception input (a breaking semantic change) and conflate the escape hatch with
  the common case. The §6.4 primitive lets a custom `predicate` go chain-aware without changing what
  `predicate` is handed.
- **Match any non-carrier link in the chain (vs the derived category).** Rejected: it would diverge from
  `caught_exception.category` (the same middleware reporting one category and matching on another), could
  over-match a buried cause when a deliberate non-carrier re-categorization escalated the proximate
  failure (degrading what the caller meant to crash on), and would contradict 0068's outermost-wins
  derivation. The derived category skips mechanical carriers (the footgun fix) while honoring a deliberate
  re-categorization; the full chain stays reachable via the §6.4 primitive for the rare buried-match case.
- **Make §6.1's default classifier full-chain too (unify depth).** Rejected: retry re-runs, so a
  full-chain default would trigger coarse outer re-runs of deeply-nested transients; single-level nudges
  toward retrying at the scope where the transient occurs. The §6.4 primitive enables opt-in full-chain
  retry for the genuine "can't place retry inner" case.
- **Normative exception-type `catch`.** Rejected for spec normativity: error categories are the
  language-agnostic classification; an exception-type form is per-language sugar resolving to categories.
- **OR / precedence composition for `catch` + `predicate`.** Rejected: conjunction (each configured
  gate narrows, both permissive by default) is the least-surprising filter semantics.
- **Do nothing / document only.** Rejected: the miss is on the degrade-vs-crash boundary and silent; the
  common case deserves a correct-by-construction gate, not a documented footgun.

## Open questions

- Whether a future proposal promotes the §6.4 primitive into a richer classification surface (e.g.,
  predicates over the chain, not just a category set) if usage accumulates. The category-set `catch` is
  sufficient for the motivating case; richer matching stays in the `predicate` escape hatch + the §6.4
  primitive for now.
