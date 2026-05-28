# 0041: Observability — Reserve OA-Emitted Metadata Key Names Against Caller-Key Collision

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-28
- **Targets:** spec/observability/spec.md (§3.4 — extend the reserved-namespace rule so caller-supplied invocation-metadata keys may not collide with the OA-emitted top-level metadata key names that backend mappings write; §8.4 — add a note documenting the shared-namespace collision and the §3.4 reservation that prevents it)
- **Related:** 0031 (Langfuse backend mapping — introduced §8.4), 0034 (caller-supplied invocation metadata — placed caller keys top-level in `trace.metadata` / `observation.metadata`), 0007 (OTel span mapping — `openarmature.*` attribute namespace)
- **Supersedes:**

## Summary

The Langfuse mapping (§8.4) writes OA-emitted observability fields as **bare
top-level keys** in `trace.metadata` / `observation.metadata` /
`generation.metadata` (`correlation_id`, `step`, `namespace`, `fan_out_index`,
`finish_reason`, `system`, `prompt`, …). Proposal 0034 then placed
**caller-supplied** metadata keys at the **same top level** so Langfuse UI
filtering on `metadata.<key>` matches what callers supplied. The two share one
flat namespace, so a caller key that happens to match an OA-emitted name
(`{"step": "…"}`, `{"correlation_id": "…"}`, `{"system": "…"}`) lands on the
same `metadata` key and **silently overwrites** the OA-emitted value — last
writer wins. The §3.4 API-boundary validation does not catch it (it reserves
only the `openarmature.*` / `gen_ai.*` prefixes), and the collision corrupts the
correlation / attribution the observability layer exists to provide. The
problem is specific to Langfuse's flat-`metadata` placement; OTel-attribute
backends are unaffected because OA's keys live under `openarmature.*` there and
caller keys under `openarmature.user.*`.

This proposal closes the gap by **reserving the OA-emitted top-level metadata
key names** at the §3.4 caller-metadata boundary: a caller key that exactly
matches one of those names is rejected at `invoke()`, the same loud / early /
deterministic mechanism §3.4 already applies to the `openarmature.*` /
`gen_ai.*` prefixes. **Both OA-emitted keys and caller keys remain at the top
level of the Langfuse metadata object** — nothing is relocated or nested — so
both stay filterable in the Langfuse UI.

Keeping the layout flat is deliberate and grounded in how Langfuse behaves
(verified against current Langfuse documentation and behavior): filtering works
reliably only on **top-level** metadata keys — nested metadata is poorly
filterable, and Langfuse's own remediation for nested / OpenTelemetry metadata
is to **flatten it to the top-level metadata object**. An earlier draft of this
proposal moved OA's keys under a `metadata.openarmature` sub-object; that would
have made `correlation_id` (the cross-backend lookup key, §8.5) and the other
OA keys unfilterable, so it is rejected here in favor of reservation. (The
OA-emitted key names keep their existing underscore form — `correlation_id`,
`fan_out_index`, etc.; Langfuse's alphanumeric-key guidance, per §8.4, applies
to its metadata-*propagation* feature, not to metadata the OA observer sets
directly on traces / observations.)

## Motivation

The collision is a latent silent-corruption bug. A production caller attaches,
say, `{"step": "checkout"}` as business metadata — an ordinary domain key. The
Langfuse observer writes the caller's `"checkout"` to
`observation.metadata.step` — the exact field §8.4.2 uses for the OA node step
index. Whichever writer runs last wins; the node's step attribution is either
clobbered by `"checkout"` or the caller's value is lost, with no error at any
layer. The same hazard exists for every OA-emitted top-level metadata name.

Three ways to resolve a flat-namespace collision: reserve the OA names and
reject caller use; define a precedence rule (one side wins, the other silently
dropped); or separate the two into distinct namespaces (nest one side under a
sub-object). The precedence rule trades silent corruption for silent data loss.
Namespacing OA's keys removes the collision but, as established above, breaks
Langfuse filtering on those keys — and namespacing the *caller's* keys would
reverse 0034's deliberate top-level placement (and break filtering on the keys
callers most want to filter by). Reservation is the only option that prevents
the collision **and** keeps both key sets top-level and filterable; its cost is
a set of reserved names callers may not use, which is acceptable because those
names are OA's own observability vocabulary.

## Design

The proposed normative changes are below. Anticipated bump: **MINOR** (pre-1.0).
The concrete spec version is assigned at acceptance.

### observability §3.4 — reserve OA-emitted metadata key names (extended)

§3.4's **Key/value constraints** currently reserve two prefixes:

> Keys MUST NOT collide with reserved namespaces: `openarmature.*` and
> `gen_ai.*`. Implementations MUST reject (raise an error at the `invoke()` API
> boundary, before any work begins) a metadata mapping that contains a colliding
> key.

This proposal extends the reservation with the OA-emitted **bare key names** a
backend mapping writes at the top level of its metadata object:

> Caller keys also MUST NOT exactly match any **OA-emitted metadata key name**
> that a backend mapping in §8 writes at the top level of a backend metadata
> object (alongside caller-supplied keys). These names are reserved so a caller
> key cannot shadow an OA-emitted field in a backend (e.g. Langfuse, §8.4) whose
> data model places both at the same top level. The current reserved set, drawn
> from the §8.4 Langfuse mapping, is:
>
> `correlation_id`, `entry_node`, `spec_version`, `detached_child_trace_ids`,
> `namespace`, `step`, `attempt_index`, `fan_out_index`, `subgraph_name`,
> `fan_out_item_count`, `fan_out_concurrency`, `fan_out_error_policy`,
> `fan_out_parent_node_name`, `prompt_group_name`, `request_extras`,
> `finish_reason`, `system`, `response_model`, `response_id`, `prompt`.
>
> Implementations MUST reject a caller key that exactly matches a reserved name
> at the `invoke()` API boundary, before any work begins, with the same
> per-language error idiom used for the `openarmature.*` / `gen_ai.*` reservation
> above. The match is exact (the names are reserved as whole keys, not as
> prefixes). The reservation applies regardless of which backends are wired:
> these are OA's observability vocabulary and stay reserved for cross-backend
> consistency, so the same caller code is valid against any backend set.

A maintenance rule accompanies the list: any future proposal that introduces a
new top-level OA-emitted metadata key in a §8 backend mapping MUST add the key
name to this reserved set in the same proposal.

### observability §8.4 — shared-namespace collision note (new)

A short note added to the §8.4 preamble (informative, pointing at §3.4):

> The Langfuse mapping writes OA-emitted observability fields as top-level keys
> of `trace.metadata` / `observation.metadata` / `generation.metadata`, the same
> top level where §3.4 caller-supplied metadata keys land. Both are placed at the
> top level on purpose: Langfuse filters reliably only on top-level metadata
> keys. To keep both sets filterable without collision, §3.4 reserves the
> OA-emitted key names (listed there) so a caller key cannot occupy the same
> metadata key as an OA-emitted field. OA-emitted keys are NOT nested under a
> sub-object — doing so would place them where Langfuse filtering does not reach.

No mapping-table rows change; OA-emitted keys and caller keys keep their current
top-level placement.

## Conformance fixtures

### Extended

- **028-caller-metadata-namespace-rejection** — add cases asserting that a
  caller key exactly matching a reserved OA-emitted name is rejected at the
  `invoke()` boundary (no spans / observations produced), alongside the existing
  `openarmature.*` / `gen_ai.*` prefix-rejection cases. Representative additions:
  `{"step": "x"}`, `{"correlation_id": "y"}`, `{"system": "z"}` each reject at
  boundary. The fixture's name still fits — it covers reserved-key rejection at
  the metadata boundary, now both reserved prefixes and reserved exact names.

### Unaffected

The Langfuse mapping fixtures (022, 023, 024, 027, 031, 032, 033) are unchanged:
this proposal relocates nothing, so their expected `metadata` trees — OA-emitted
keys and caller keys both top-level — remain correct.

## Versioning

MINOR bump (pre-1.0). On acceptance the whole-spec SemVer increments (concrete
version assigned at acceptance):

- Extends §3.4's reserved-key rule with the OA-emitted top-level metadata key
  names + the maintenance rule.
- Adds the §8.4 shared-namespace collision note.
- Extends fixture 028 with reserved-name rejection cases.

A caller that previously supplied one of the now-reserved names (e.g.
`metadata={"step": …}`) is rejected at `invoke()` after this lands — a breaking
change for that caller, taken deliberately to stop the silent corruption. Pre-1.0
it lands in a MINOR. Callers using non-reserved keys are unaffected; no
Langfuse-metadata-layout change, so existing dashboards / saved filters on OA
keys and caller keys keep working.

CHANGELOG entry references this proposal.

## Out of scope

- **OTel-attribute backends.** No change. OA keys live under `openarmature.*` and
  caller keys under `openarmature.user.*` (§5.6); there is no flat-namespace
  collision. The reservation is enforced at the backend-agnostic §3.4 boundary
  for cross-backend consistency, but it resolves a Langfuse-specific hazard.
- **Relocating / nesting metadata keys.** Considered and rejected (breaks
  Langfuse filtering on the nested side). Both key sets stay top-level.
- **Langfuse value constraints.** The existing §8.4 note on Langfuse's
  alphanumeric-key / 200-character-value constraints is unchanged; this proposal
  addresses key *collision*, not value handling.
- **Reserving caller-domain names beyond OA's vocabulary.** Only OA-emitted key
  names are reserved; the spec does not reserve arbitrary caller-domain names
  (`tenantId`, `userId`, etc.).

## Open questions

The design decisions are settled in the text above:

- **Reserve vs. nest vs. precedence** — reserve. Nesting breaks Langfuse
  filtering on the nested side (verified: Langfuse filters top-level metadata
  reliably and flattens nested metadata to top-level); precedence silently drops
  caller data. Reservation keeps both key sets top-level + filterable and fails
  loudly at the boundary.
- **Universal vs. Langfuse-conditional reservation** — universal (backend-set-
  independent), so the same caller code is valid against any wired backend and
  the reserved set is a single stable contract.
- **Exact-match vs. prefix** — exact whole-key match; the reserved names are
  specific keys, not namespaces.
- **List maintenance** — the reserved set is enumerated for the current §8.4
  mapping; the accompanying maintenance rule requires future top-level OA
  metadata keys to extend it in the introducing proposal.
