# 072 — Failure-isolation middleware: `catch` cause-chain category classification

Verifies §6.3's `catch` gate (proposal 0074) — a set of error categories matched
against the caught exception's **cause chain** via the §6.4 cause-chain
classification primitive (the same carrier-skipping walk §6.3 derives
`caught_exception.category` from). The point is the **wrapping placement**: at a
§9.7 instance placement the engine wraps the instance failure as a graph-engine
§4 `node_exception` carrier before FailureIsolation catches it, so the surface
exception is the carrier and a surface category check misses the originating
provider failure. `catch` classifies *through* the carrier and catches correctly.

## Spec coverage

- §6.3 — Failure isolation middleware; `catch` field; cause-chain category match
  (the derived category); composition with `predicate` (conjunction, permissive
  defaults).
- §6.4 — Cause-chain classification primitive (the carrier-skipping walk).
- §9.7 — instance middleware (the carrier-wrapping placement).

## Cases

1. `catch_matches_carrier_wrapped_category_and_degrades` — single-instance
   fan-out; the instance raises `provider_unavailable`, wrapped by the engine as
   a `node_exception` carrier at the instance placement. `catch=[provider_unavailable]`
   matches the originating category through the carrier, so the instance is
   caught and degraded (`results: ["(degraded)"]`), and the failure-isolation
   event reports `caught_exception.category = provider_unavailable`. A surface
   category check (the carrier is `node_exception`) would miss it.
2. `catch_non_matching_category_propagates` — same carrier-wrapped
   `provider_unavailable` failure, but `catch=[provider_rate_limit]` excludes the
   originating category, so the gate rejects and the exception propagates as
   `node_exception` from the fan-out node; no failure-isolation event fires.

## Anti-cases (would indicate a broken implementation)

- The carrier-wrapped category is not matched through the `node_exception`
  carrier (catch classified on the surface and missed the originating failure) —
  the degrade→crash footgun this gate closes.
- The non-matching case is caught — `catch` is not enforced as a filter.
- A failure-isolation event fires in case 2 — the gate let a non-matching
  exception through.
