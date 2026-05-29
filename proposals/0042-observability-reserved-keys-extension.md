# 0042: Observability — Reserve `branch_name`, `detached`, `detached_from_invocation_id` Metadata Keys

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-29
- **Accepted:** 2026-05-29
- **Targets:** spec/observability/spec.md (§3.4 — extend the reserved-key enumeration with three keys the §8.4 Langfuse mapping writes to top-level metadata; §8.4.1 — add the `detached_from_invocation_id` Trace-metadata row; §8.4.2 — add `branch_name` and `detached` Observation-metadata rows)
- **Related:** 0041 (the predecessor reservation — extended), 0034 (caller-supplied invocation metadata — established the top-level placement), 0031 (Langfuse backend mapping — introduced §8.4), 0011 (parallel branches — defined `branch_name` on the §6 NodeEvent)
- **Supersedes:**

## Summary

Closes a coverage gap in proposal 0041's reserved-key set. 0041 reserved 21
OA-emitted top-level metadata key names against caller-key collision at the
§3.4 boundary, drawn from an enumeration of §8.4 Langfuse mapping at acceptance
time. Three additional keys the §8.4 Langfuse mapping writes to
`trace.metadata` / `observation.metadata` at the top level were not enumerated
in the §8.4 mapping tables (and so not in 0041's reservation): `branch_name`
(per-branch observation metadata), `detached` (dispatching observation when
its child is detached per §4.4), and `detached_from_invocation_id` (detached
child trace's pointer back to the parent invocation). A caller key matching
any of the three would silently shadow the OA-emitted field — the same
silent-corruption hazard 0041 fixed for the original 21.

This proposal closes the gap with the same reserve-at-boundary mechanism,
extends §3.4's reserved enumeration to 24 names, and documents the three
keys' emission sites in §8.4.1 / §8.4.2 so cross-implementation emission is
normatively specified rather than left as a per-implementation convention.

## Motivation

The collision shape and the remediation rationale are unchanged from 0041
(see its Motivation). The narrower questions 0042 answers are: why the three
keys were missed, and why fixing the gap matters now.

**Why missed.** 0041's 20-key list (plus `invocation_id` for 21) was drawn
from the keys §8.4's mapping tables explicitly enumerate. The three keys 0042
covers are emitted by the same Langfuse mapping but were not in §8.4.1 /
§8.4.2's tables at the time:

- `branch_name` is a graph-engine §6 NodeEvent field (parallel branches,
  proposal 0011) but §8.4.2 had no row mapping it to
  `observation.metadata.branch_name`. The Langfuse observer's per-branch
  Span observation needs the field for the same reason the per-instance
  Span observation needs `fan_out_index` — to disambiguate identically-named
  inner nodes across siblings — but the §8.4.2 table only listed
  `fan_out_index`.
- `detached` and `detached_from_invocation_id` are Langfuse-mapping-internal
  metadata fields that surface §4.4 detached-trace mode to the Langfuse data
  model. §4.4 specifies the detached-mode lifecycle; §8.4 documents the
  Langfuse mappings — neither side enumerated these specific keys, even
  though detached mode is unrepresentable in Langfuse without them.

**Why now.** Same dynamic as 0041: a downstream-implementation pass caught
the gap. The §3.4 reserved set is a cross-implementation contract (§3.4's
maintenance rule requires new emitted keys to be added to it in the
introducing proposal), and the gap predates the reservation mechanism — it
was not introduced by 0041. A caller using one of the three names as caller
metadata (an unlikely but legitimate domain key choice) sees the same
silent corruption 0041 was built to prevent.

## Design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0). The concrete spec version is assigned at acceptance.

### observability §3.4 — extend the reserved-key enumeration

§3.4's reserved-name enumeration (21 entries as of v0.31.0) extends with three
names: `branch_name`, `detached`, `detached_from_invocation_id`. The full
reserved set becomes:

> `correlation_id`, `entry_node`, `spec_version`,
> `detached_child_trace_ids`, `namespace`, `step`, `attempt_index`,
> `fan_out_index`, `subgraph_name`, `fan_out_item_count`,
> `fan_out_concurrency`, `fan_out_error_policy`, `fan_out_parent_node_name`,
> `prompt_group_name`, `request_extras`, `finish_reason`, `system`,
> `response_model`, `response_id`, `prompt`, `invocation_id`, `branch_name`,
> `detached`, `detached_from_invocation_id`.

The reservation mechanism, error idioms (`invoke()` boundary plus the
mid-invocation `set_invocation_metadata` helper, both raising at the API
boundary with the same per-language error shape), and the maintenance rule
are unchanged from 0041.

### observability §8.4.1 — add a `detached_from_invocation_id` Trace-level row

A new row is added to the §8.4.1 Trace-level mapping table:

| OA source | Langfuse Trace field |
|---|---|
| §4.4 detached-mode dispatch context: the parent invocation's `invocation_id` | `trace.metadata.detached_from_invocation_id` — emitted on the detached child trace (a trace produced by detached-mode dispatch per §4.4). Points back to the parent invocation for inverse lookup. Sibling to `trace.metadata.correlation_id` (which is preserved across detached and parent traces per §3.1, providing the forward direction). Absent on non-detached traces. |

The "OA source" cell deviates from the existing rows' `openarmature.*`
attribute pattern because §5 currently has no
`openarmature.detached_from_invocation_id` attribute — the value is derived
from §4.4 detached-mode dispatch context, not from a span attribute. This is
a Langfuse-mapping-internal emission tied to §4.4 lifecycle behavior, called
out explicitly to keep the §8.4 mapping coverage complete.

### observability §8.4.2 — add `branch_name` and `detached` Observation-level rows

Two new rows are added to the §8.4.2 Observation-level mapping table:

| OA source | Langfuse Observation field |
|---|---|
| graph-engine §6 NodeEvent `branch_name` (per parallel branches, proposal 0011) | `observation.metadata.branch_name` (when present, per-branch Span observation). Sibling to `observation.metadata.fan_out_index` — same disambiguation role for parallel branches that `fan_out_index` plays for fan-out instances, distinguishing identically-named inner nodes across sibling branches. Absent on observations from nodes outside any parallel-branches subgraph. |
| §4.4 detached-mode: the dispatching observation marks itself when it fires a detached child | `observation.metadata.detached` — boolean `true` on the parent-side dispatching observation that dispatches a detached subgraph or fan-out instance. Absent (or `false`) on non-dispatch observations and on observations that dispatch non-detached children. |

The same source-side deviation note as §8.4.1 applies to `detached`: it is
not derived from an `openarmature.*` attribute; it is a Langfuse-mapping-
internal flag tied to §4.4 detached-mode behavior. `branch_name`, by
contrast, has a graph-engine §6 NodeEvent source; adding a corresponding §5.x
parallel-branches attribute (paralleling `openarmature.node.fan_out_index`)
would be a natural future tightening but is out of scope here.

## Conformance test impact

### Extended

- **`observability/conformance/028-caller-metadata-namespace-rejection`** —
  three new rejection cases asserting that caller-supplied metadata exactly
  matching `branch_name`, `detached`, or `detached_from_invocation_id` is
  rejected at the `invoke()` boundary (and at the §3.4 mid-invocation
  `set_invocation_metadata` helper), with no spans / observations produced.
  Same rejection-at-boundary mechanism as the existing fixture cases — the
  fixture's name still fits its scope.

### Unaffected

The existing Langfuse-mapping fixtures (detached-mode and parallel-branches
Langfuse fixtures) are unaffected by this proposal. The three keys'
Langfuse emissions are already exercised by those fixtures; this proposal
documents the emissions in §8.4 normative text but does not change the
emissions themselves, so the expected `metadata` payloads in those fixtures
remain correct.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments
(concrete version assigned at acceptance):

- Extends §3.4's reserved-name enumeration from 21 to 24 names.
- Adds one row to §8.4.1's Trace-level mapping table.
- Adds two rows to §8.4.2's Observation-level mapping table.
- Extends fixture 028 with three rejection cases.

A caller that previously supplied one of the three now-reserved names
(e.g. `metadata={"branch_name": …}`) is rejected at `invoke()` after this
lands — a breaking change for that caller, taken deliberately to stop the
silent-corruption hazard (the same disposition 0041 took for its 20 names).
Pre-1.0 it lands in a MINOR. Callers using non-reserved keys are unaffected;
no Langfuse-metadata-layout change, so existing dashboards and saved filters
keep working. The §8.4.1 / §8.4.2 table additions document emissions the
§8.4 Langfuse mapping was already producing — no observer behavior changes.

CHANGELOG entry references this proposal.

## Out of scope

- **New `openarmature.*` span attributes for the three keys.** Two of the
  three (`detached`, `detached_from_invocation_id`) are Langfuse-mapping-
  internal metadata that surface §4.4 detached-mode lifecycle — they have
  no OTel-attribute counterpart and are introduced as §8.4 emission
  conventions only. `branch_name` has a graph-engine §6 NodeEvent source
  but no §5.x observability span attribute; adding such an attribute
  (paralleling `openarmature.node.fan_out_index` in §5.4) would be a
  natural future tightening but is out of scope here. The present proposal
  scopes to closing the reserved-key coverage gap.
- **Other OA-emitted top-level metadata keys that may have similar coverage
  gaps.** This proposal addresses the three keys identified by a downstream
  implementation pass; if a future review surfaces additional keys, they
  follow §3.4's maintenance rule (a follow-up proposal extends the set in
  the same proposal that introduces the emission).
- **Relocating or nesting any metadata keys.** Both OA-emitted and caller-
  supplied keys remain at the top level of `trace.metadata` /
  `observation.metadata` per 0041's design — Langfuse filters reliably
  only on top-level metadata keys.
- **OTel-attribute backends.** Unchanged. No flat-namespace collision
  exists for OTel-attribute backends, the same as 0041; the reservation is
  enforced at the backend-agnostic §3.4 boundary for cross-backend
  consistency.

## Alternatives considered

- **Document-only (no reservation).** Add §8.4.1 / §8.4.2 rows for the three
  keys, but leave §3.4's reserved enumeration at 21 names. Rejected: the
  shared-namespace collision shape is identical to 0041's, so a caller key
  matching any of the three would silently shadow the OA-emitted field —
  exactly the hazard 0041 was designed to prevent. Reservation is the only
  mechanism that prevents silent corruption while keeping both key sets at
  the top level (the design 0041 settled, which this proposal extends).
- **Reserve-only (tight scope, §3.4 only).** Extend §3.4's enumeration with
  the three names but leave §8.4.1 / §8.4.2 silent. Rejected: reserving names
  whose emission is not formally specified in §8.4 would leave the emission
  as a per-implementation convention rather than a normative requirement,
  risking cross-implementation divergence on the underlying observability
  data. Documenting the emission in §8.4.1 / §8.4.2 grounds the reservation
  in normative spec text and obligates conforming implementations to emit
  the keys.
- **Add an `openarmature.node.branch_name` §5.x span attribute.** Source the
  Langfuse `branch_name` row in §8.4.2 from a new `openarmature.*` attribute
  paralleling `openarmature.node.fan_out_index` in §5.4. Rejected for scope:
  it would require touching graph-engine §6 and observability §5, expanding
  this proposal beyond closing the reserved-key coverage gap. Left as a
  natural future tightening (flagged under Out of scope above); 0042 sources
  `branch_name` directly from the graph-engine §6 NodeEvent field.
- **Do nothing.** Leave the three keys unreserved and undocumented in §8.4.
  Rejected: same disposition 0041 took for its 20 names — the silent-
  corruption hazard is real, and these three are known emissions that
  should not remain a per-implementation convention.
