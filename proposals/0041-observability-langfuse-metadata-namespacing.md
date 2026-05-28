# 0041: Observability — Namespace OA-Emitted Langfuse Metadata Under `metadata.openarmature`

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-28
- **Targets:** spec/observability/spec.md (§8.4.1 / §8.4.2 / §8.4.3 / §8.4.4 — relocate every OA-emitted Langfuse `metadata.<key>` to a reserved `metadata.openarmature.<key>` sub-object; §8.5 and any §8.4.x payload/truncation prose — sweep the same relocation; §3.4 — extend the reserved-namespace rule to cover the bare `openarmature` / `gen_ai` tokens, not only the dotted prefixes)
- **Related:** 0031 (Langfuse backend mapping — introduced §8.4), 0034 (caller-supplied invocation metadata — placed caller keys top-level in `trace.metadata` / `observation.metadata`), 0007 (OTel span mapping — establishes the `openarmature.*` attribute namespace this mirrors)
- **Supersedes:**

## Summary

Today the Langfuse mapping (§8.4) writes OA-emitted observability fields as
**bare top-level keys** in `trace.metadata` / `observation.metadata` /
`generation.metadata` (`correlation_id`, `step`, `namespace`, `fan_out_index`,
`finish_reason`, `system`, `prompt`, …). Proposal 0034 then placed
**caller-supplied** metadata keys at the **same top level** so Langfuse UI
filtering on `metadata.<key>` matches what callers supplied. The two share one
flat namespace, so a caller key that happens to match an OA-emitted name
(`{"step": "…"}`, `{"correlation_id": "…"}`, `{"system": "…"}`) lands on the
same `metadata` key and **silently overwrites** the OA-emitted value — last
writer wins. The §3.4 API-boundary validation does not catch it (it reserves
only the `openarmature.*` / `gen_ai.*` prefixes), and the collision corrupts the
very correlation / attribution the observability layer exists to provide. The
problem is specific to Langfuse's flat-`metadata` placement; OTel-attribute
backends are unaffected because OA's keys live under `openarmature.*` there and
caller keys under `openarmature.user.*`.

This proposal moves the **OA-emitted** Langfuse metadata fields under a reserved
**`metadata.openarmature` sub-object**, leaving caller-supplied keys at the top
level (0034's filtering intent preserved). The collision becomes impossible:
caller keys can never reach `metadata.openarmature.*`, and the existing §3.4
`openarmature` reservation already forbids callers from supplying that key — the
one addition is to reserve the **bare** `openarmature` / `gen_ai` tokens (not
just the dotted prefixes) so a caller cannot supply `{"openarmature": …}` and
shadow the sub-object.

Net effect:

- **Collision eliminated permanently**, with **no reserved-key list to
  maintain** — the single `openarmature` namespace covers every current and
  future OA-emitted Langfuse metadata field.
- **Callers may use any business key**, including `step`, `system`, `prompt`,
  even `correlation_id` — they land top-level, disjoint from
  `metadata.openarmature.*`.
- **Langfuse metadata paths now mirror the OTel attribute names**
  (`metadata.openarmature.correlation_id` ↔ the `openarmature.correlation_id`
  span attribute), a consistency win across the two mappings.

## Motivation

The collision is a latent silent-corruption bug. A production caller attaches,
say, `{"step": "checkout"}` as business metadata (a perfectly ordinary domain
key). The Langfuse observer writes the caller's `"checkout"` to
`observation.metadata.step` — the exact field §8.4.2 uses for the OA node step
index. Whichever writer runs last wins; the node's step attribution is either
clobbered by `"checkout"` or the caller's value is lost, with no error at any
layer. The same hazard exists for every OA-emitted top-level metadata name.

There are three ways to resolve a flat-namespace collision: reserve the OA names
and reject caller use of them; define a precedence rule (one side wins, the
other is silently dropped); or separate the two into distinct namespaces. The
first imposes an ever-growing reserved-key blocklist that callers must avoid and
maintainers must extend with every new OA metadata field, and it forbids common
business keys (`system`, `prompt`, `step`) across all backends — even
OTel-only deployments that have no collision. The second trades silent
corruption for silent data loss. The third — separating the namespaces —
removes the collision at its root and is permanent.

Separating the namespaces can be done on either side. Nesting the **caller's**
keys under a sub-object would reverse 0034's deliberate decision (caller keys
top-level so `metadata.tenantId` filtering works) and break that ergonomic.
Nesting **OA's own** keys under `metadata.openarmature` does not: caller keys
stay exactly where 0034 put them, and only OA's internal observability fields
move — into a namespace OA already owns on the OTel side. This is the cleanest
permanent fix and the one this proposal adopts.

### Why a sub-object, not dotted-flat keys

OA's OTel attributes are dotted flat names (`openarmature.correlation_id`). The
Langfuse analogue could be a flat metadata key literally named
`"openarmature.correlation_id"`. Two reasons not to: (1) §8.4 already documents
that Langfuse constrains propagated metadata **keys** (the alphanumeric-key
note), and a key containing a `.` is the most likely thing to trip such a
constraint; (2) Langfuse's UI and filter expressions treat `.` as a path
separator, so a dotted key is ambiguous with a nested path. A nested
`metadata.openarmature` object whose members are the existing underscore-style
field names (`correlation_id`, `fan_out_index`, …) avoids both: the only new key
introduced is the alphanumeric token `openarmature`, and filtering on
`metadata.openarmature.correlation_id` is an unambiguous path.

## Design

The proposed normative changes are below. Anticipated bump: **MINOR** (pre-1.0;
breaking change to the Langfuse metadata shape — see Versioning). The concrete
spec version is assigned at acceptance.

### observability §8.4 — OA-emitted metadata moves under `metadata.openarmature`

A new paragraph in the §8.4 preamble establishes the rule, and the §8.4.1 /
§8.4.2 / §8.4.3 / §8.4.4 mapping tables relocate every OA-emitted metadata
target accordingly.

**Rule (new §8.4 preamble paragraph).**

> All OA-emitted observability fields that the Langfuse mapping writes into
> `trace.metadata`, `observation.metadata`, or `generation.metadata` MUST be
> placed under a single reserved top-level key, `openarmature`, whose value is
> an object holding those fields. This applies to every field enumerated in
> §8.4.1–§8.4.4, regardless of whether its source OTel attribute is in the
> `openarmature.*` or the `gen_ai.*` family. Caller-supplied invocation metadata
> (§3.4) remains at the **top level** of the metadata object, disjoint from the
> `openarmature` sub-object. Because the two never share a key path, a
> caller-supplied key can never collide with an OA-emitted field, and the
> Langfuse metadata layout mirrors the `openarmature.*` OTel attribute namespace
> (§5) one-to-one.

**Relocation, by table:**

- **§8.4.1 (Trace-level).** `trace.metadata.correlation_id` →
  `trace.metadata.openarmature.correlation_id`; `…entry_node` →
  `…openarmature.entry_node`; `…spec_version` → `…openarmature.spec_version`.
  The caller-metadata row is unchanged: each caller `(key, value)` →
  `trace.metadata.<key>` at the top level. `trace.id` and `trace.name` are Trace
  fields (not metadata) and are unchanged.
- **§8.4.2 (Observation-level).** Every OA target relocates under
  `observation.metadata.openarmature.<field>`: `namespace`, `step`,
  `attempt_index`, `fan_out_index`, `subgraph_name`, `fan_out_item_count`,
  `fan_out_concurrency`, `fan_out_error_policy`, `fan_out_parent_node_name`,
  `correlation_id`, and `prompt_group_name`. The caller-metadata row is
  unchanged: each caller key → `observation.metadata.<key>` at the top level of
  every Observation.
- **§8.4.3 (Generation-specific).** `generation.metadata.{request_extras,
  finish_reason, system, response_model, response_id}` →
  `generation.metadata.openarmature.{…}`. `generation.model`,
  `generation.modelParameters.*`, `generation.usage.*`, `generation.input`, and
  `generation.output` are Generation fields outside `metadata` and are
  unchanged.
- **§8.4.4 (Prompt linkage).** The structured prompt-identity map relocates from
  `generation.metadata.prompt.{name,version,label,template_hash,rendered_hash}`
  to `generation.metadata.openarmature.prompt.{…}`. The normative-shape
  requirement on the `prompt` map (cross-implementation parity) carries over to
  its new path. The native Langfuse Prompt-entity **link** (§8.4.4 case 1) is
  not a metadata field and is unchanged.

**§8.5 and payload/truncation prose sweep.** §8.5 (correlation ID realization)
references `metadata.correlation_id` at trace and observation level; the
detached-trace-mode rule references `metadata.detached_child_trace_ids`; the
§8.4.3 payload / truncation prose references `generation.metadata.request_extras`.
All such `metadata.<oa_field>` references throughout §8.4–§8.9 relocate under
`metadata.openarmature.<field>`. (`detached_child_trace_ids` →
`trace.metadata.openarmature.detached_child_trace_ids`.) The acceptance edit
sweeps §8.4–§8.9 exhaustively for `metadata.<oa_field>` references.

### observability §3.4 — reserve the bare `openarmature` / `gen_ai` tokens

The §3.4 reserved-namespace rule currently reads (paraphrased): caller keys MUST
NOT collide with `openarmature.*` and `gen_ai.*`, rejected at the `invoke()`
boundary. This proposal makes the reservation cover the **bare token** as well
as the dotted prefix:

> Caller keys MUST NOT use the reserved `openarmature` or `gen_ai` namespaces —
> neither the bare token (a key exactly equal to `openarmature` or `gen_ai`) nor
> any dotted descendant (`openarmature.<…>`, `gen_ai.<…>`). Implementations MUST
> reject a colliding key at the `invoke()` API boundary before any work begins,
> per the existing error idiom.

The load-bearing addition is the bare `openarmature` token: it prevents a caller
from supplying `{"openarmature": …}`, which would otherwise land at
`metadata.openarmature` (top level) and shadow the OA sub-object. The bare
`gen_ai` token is reserved symmetrically for consistency and future-proofing
(no §8.4 field uses a `gen_ai` sub-object today). This is the **only** key
constraint this proposal adds — there is no enumerated list of OA field names to
reserve, because OA's fields no longer share the caller's namespace.

## Conformance fixtures

### Rewritten (OA metadata relocates under `metadata.openarmature`)

Each of these asserts OA-emitted metadata fields and has its expected
trace/observation/generation `metadata` trees updated to nest the OA fields
under `openarmature`:

- **022-langfuse-basic-trace** — `correlation_id`, `entry_node`, `spec_version`,
  `namespace`, `step`, `attempt_index`.
- **023-langfuse-generation-rendering** — `generation.metadata.openarmature.{finish_reason,
  system, response_model, response_id, request_extras}`.
- **024-langfuse-prompt-linkage** — `generation.metadata.openarmature.prompt.*`
  and `observation.metadata.openarmature.prompt_group_name`.
- **027-langfuse-caller-supplied-metadata** — OA's `correlation_id` relocates
  under `openarmature`; the caller keys (`tenantId`, etc.) stay top-level. This
  fixture also **gains a coexistence case** (below).
- **031-langfuse-subgraph-span-hierarchy** — `namespace`, `step`,
  `subgraph_name`, `correlation_id`.
- **032-langfuse-fan-out-per-instance-spans** — `fan_out_item_count`,
  `fan_out_concurrency`, `fan_out_error_policy`, `fan_out_index`,
  `fan_out_parent_node_name`, `subgraph_name`, `correlation_id`.
- **033-langfuse-detached-trace-mode** — `correlation_id`,
  `detached_child_trace_ids`.

### Extended

- **028-caller-metadata-namespace-rejection** — add a case asserting a caller
  key exactly equal to the bare token `openarmature` (and `gen_ai`) is rejected
  at the `invoke()` boundary, alongside the existing dotted-prefix rejection
  cases.
- **027** coexistence case — supply caller metadata whose keys deliberately
  match OA field names (e.g., `{"step": "caller-step", "system": "caller-sys"}`)
  and assert both survive at distinct paths:
  `observation.metadata.step == "caller-step"` (caller, top level) **and**
  `observation.metadata.openarmature.step == <OA step index>` (OA, nested) — no
  overwrite in either direction. This is the direct regression test for the
  collision this proposal fixes.

### Unaffected

- **029 / 030** (caller-metadata fan-out / parallel-branches) assert only
  caller keys (`tenantId`, `productId`, `branchName`) at the top level, which
  this proposal leaves in place; their expected trees do not assert OA-emitted
  metadata fields, so they need no change here. (They are revised separately for
  the mid-invocation open-span update.)

The exact set is reconciled against the conformance directory at acceptance, in
case fixtures are added between this Draft and acceptance.

## Versioning

MINOR bump (pre-1.0). On acceptance the whole-spec SemVer increments (concrete
version assigned at acceptance):

- Relocates every OA-emitted Langfuse `metadata.<field>` to
  `metadata.openarmature.<field>` across §8.4.1–§8.4.4 and the §8.5 / payload
  prose.
- Extends §3.4's reserved-namespace rule to the bare `openarmature` / `gen_ai`
  tokens.
- Rewrites the Langfuse conformance fixtures listed above and extends fixture
  028 + the 027 coexistence case.

This is a **breaking change** to the Langfuse metadata layout: consumers that
read OA-emitted fields at `trace.metadata.correlation_id` /
`observation.metadata.step` / etc. must read them at
`metadata.openarmature.correlation_id` / `metadata.openarmature.step` after this
lands (Langfuse saved views, dashboards, and filters that target OA fields
move one path segment deeper). Caller-supplied metadata is unaffected — it stays
at the top level. The break is taken deliberately in favor of a permanently
collision-free layout that mirrors the OTel namespace; per the spec's pre-1.0
SemVer policy it lands in a MINOR.

CHANGELOG entry references this proposal.

## Out of scope

- **OTel-attribute backends.** No change. OA keys already live under
  `openarmature.*` and caller keys under `openarmature.user.*` (§5.6); there is
  no flat-namespace collision to fix. This proposal touches only the Langfuse
  mapping (§8.4) and the §3.4 boundary reservation that protects its sub-object.
- **Caller-key namespacing.** Caller-supplied metadata stays top-level
  (0034's UI-filtering decision is preserved); this proposal does not move or
  prefix caller keys.
- **Langfuse value constraints.** The existing §8.4 note on Langfuse's
  alphanumeric-key / 200-character-value constraints for caller keys is
  unchanged; this proposal addresses key *collision*, not value handling.
- **Other backends' data models.** Future observability backend mappings define
  their own metadata layout; if a future backend also uses a flat caller-shared
  namespace it follows this same pattern (OA fields under an `openarmature`
  sub-object), but no other backend mapping exists to amend today.

## Open questions

The design decisions are settled in the text above:

- **Which side to namespace** — OA's own keys, not the caller's (preserves
  0034's top-level caller-key filtering; moves only OA-internal fields into the
  namespace OA already owns on the OTel side).
- **Sub-object vs dotted-flat key** — a nested `metadata.openarmature` object,
  not a flat `"openarmature.<field>"` key, to avoid Langfuse's alphanumeric-key
  constraint and `.`-as-path-separator ambiguity.
- **Single namespace for all OA fields** — `gen_ai.*`-sourced fields
  (`system`, `response_model`, `response_id`) go under `metadata.openarmature`
  alongside `openarmature.*`-sourced fields rather than a separate
  `metadata.gen_ai` sub-object — one reserved sub-object is simplest and both
  bare tokens are reserved regardless.
- **Reserved-key surface** — only the bare `openarmature` / `gen_ai` tokens are
  added to §3.4 (the dotted prefixes were already reserved); no enumerated
  list of OA field names, because OA fields no longer share the caller
  namespace.
