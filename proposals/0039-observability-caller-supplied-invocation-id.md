# 0039: Observability — Caller-Supplied `invocation_id`

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-28
- **Accepted:** 2026-05-28
- **Targets:** spec/observability/spec.md (§5.1 *Invocation span attributes* — reframe `openarmature.invocation_id` from "framework-generated UUIDv4" to "caller-supplied or framework-generated," mirroring §3.1's `correlation_id` pattern; §3.2 distinction table touch; §8.4.1 *Trace-level mapping* — define the Langfuse `trace.id` derivation for caller-supplied non-UUID ids); spec/graph-engine/spec.md (§3 clarifying touch — `invoke()` MAY accept a caller-supplied invocation id, mechanism per-language idiomatic, mirroring 0034's `metadata` touch); conformance fixtures under spec/observability/conformance/ and spec/pipeline-utilities/conformance/.
- **Related:** 0007 (observability OTel span mapping — defined `openarmature.invocation_id`), 0031 (observability Langfuse mapping — defined §8.4.1 `trace.id` = invocation_id), 0034 (caller-supplied invocation metadata — established the per-language `invoke()` caller-surface pattern this proposal mirrors), 0008/0009 (checkpointing / per-instance fan-out resume — the resume-mints-fresh-id interaction this proposal preserves)
- **Supersedes:**

## Summary

Let a caller pass its own `invocation_id` into `invoke()`, instead
of always taking OA's framework-minted UUIDv4. Additive and opt-in:
absent → mint a UUIDv4 as today; supplied → use the caller's value
for the invocation context, checkpoint keys, observer events, and
span attributes.

This mirrors the existing caller-supplied `correlation_id` (§3.1):
a caller-supplied id MAY be any non-empty URL-safe string, while the
UUIDv4 format mandate applies only to the framework-generated
(absent) case. Because `invocation_id` is structurally load-bearing
in the Langfuse mapping (§8.4.1 uses it as the Langfuse `trace.id`,
which must be a valid OTel-style 128-bit id), this proposal also
defines how the Langfuse mapping derives a valid `trace.id` from a
non-UUID caller value — preserving caller flexibility without
producing broken traces.

The motivating problem is a real ordering race: `Checkpointer.save`
is synchronous (awaited inside `invoke()`), while observer dispatch
is queue-mediated and `invoke()` returns without draining. A
consumer that registers a parent run row via an observer (an async
insert) races the first node's checkpoint write (a synchronous
child insert with a foreign key to that parent's `invocation_id`).
Child-before-parent is not just possible — it dominates under load.
Letting the caller supply the `invocation_id` lets it insert the
parent row synchronously *before* `invoke()`, eliminating the race.

## Motivation

`invocation_id` (observability §5.1) is the framework-generated
UUIDv4 that ties together all spans, checkpoint records, and (in the
Langfuse mapping) the trace of a single invocation. Today the
framework always mints it internally with no hook between minting
and the first node running.

A consumer that wants its own identity space to join on OA's
`invocation_id` has only bad options:

1. **Capture it after the fact** from inside an observer or node
   body — but this loses the race described below.
2. **Run a parallel id space** and never join to OA's — losing the
   ability to correlate the consumer's records with OA's spans /
   checkpoints / Langfuse traces.

The race (code-verified in the reference implementation):

- `Checkpointer.save` is synchronous by contract — the engine awaits
  each save before advancing, *inside* `invoke()`.
- Observer dispatch is queue-mediated on a separate delivery task;
  `invoke()` returns without draining the queue.
- So a consumer that registers the invocation's parent row via an
  observer (async insert) races the first node's checkpoint write
  (a synchronous child insert carrying a foreign key to the parent
  row keyed by `invocation_id`). The child insert can — and under
  load usually does — land before the observer's parent insert.

The first production OA consumer hit exactly this against a
`checkpoints.invocation_id → runs.invocation_id` foreign key,
observing a child-before-parent rate high enough that they dropped
the constraint to ship. The fix: let the consumer mint the id, write
the parent row synchronously before `invoke()`, and pass the same id
in — the observer-based registration (and its race) goes away.

**Precedent.** `correlation_id` is already caller-supplyable (§3.1):
"Accept a caller-supplied ID at invoke time … When the caller
supplies an ID, the framework uses it verbatim. … Caller-supplied
correlation IDs MAY be any non-empty URL-safe string … the format
mandate applies only to the auto-generated case." This proposal
extends the identical opt-in pattern to `invocation_id`.

## Detailed design

### §5.1 — reframe `openarmature.invocation_id`

§5.1's current text mandates the attribute "MUST be a UUIDv4
(canonical 36-character form)" unconditionally. Reframe to parallel
§3.1's `correlation_id` treatment:

> `openarmature.invocation_id` — string. A unique identifier for
> this invocation. **Caller-supplied or framework-generated.** When
> the caller supplies an id at invoke time, the framework uses it
> verbatim; a caller-supplied id MAY be any non-empty URL-safe
> string. When the caller does not supply one, the framework MUST
> generate a UUIDv4 (canonical 36-character form). The UUIDv4 format
> mandate applies only to the framework-generated case, so "you
> don't supply an invocation id" produces consistent UUIDv4 output
> across implementations. Backends that derive a fixed-width
> identifier from `invocation_id` (e.g., the Langfuse `trace.id` per
> §8.4.1) define their own derivation for non-UUID values.

The §3.2 distinction table row for `invocation_id` updates its
"Source" cell from "Framework" to "Caller (or framework-generated
when absent)."

### graph-engine §3 — `invoke()` caller surface

Add a clarifying paragraph (the same kind of touch 0034 made for the
`metadata` mapping): `invoke()` MAY accept a caller-supplied
invocation id alongside the existing `correlation_id` and `metadata`
surfaces. The mechanism is per-language idiomatic (a keyword
argument, a field on an invocation-config record, equivalent). When
supplied, it becomes the invocation's `invocation_id` (§5.1);
when absent, the framework mints a UUIDv4.

### §8.4.1 — Langfuse `trace.id` derivation for non-UUID ids

This is the load-bearing addition. §8.4.1 currently maps
`openarmature.invocation_id` → Langfuse `trace.id` with "MUST use
the invocation_id verbatim as the Trace ID." Langfuse (OTel-based)
requires `trace.id` to be a 128-bit value rendered as 32 lowercase
hex characters. A UUIDv4 carries exactly 128 bits, so the verbatim
mapping works by stripping dashes. A non-UUID caller value does not,
and passing it through unchanged produces an invalid (silently
broken) Langfuse trace.

Updated §8.4.1 rule:

- **When `invocation_id` is a valid UUID:** `trace.id` = the
  UUID's 32-character lowercase hex form (dashes stripped). Direct
  lookup by `invocation_id` works (strip dashes to search), as today.
- **When `invocation_id` is not a UUID:** `trace.id` = a
  deterministic 128-bit derivation of the `invocation_id` —
  the first 16 bytes of `SHA-256(invocation_id)`, rendered as 32
  lowercase hex characters. The raw `invocation_id` is ALSO written
  to `trace.metadata.invocation_id` so lookup by the caller's
  original value works via Langfuse metadata filtering. The
  derivation MUST be deterministic and stable across
  implementations (SHA-256 of the UTF-8 bytes of `invocation_id`,
  first 16 bytes, lowercase hex) so a TypeScript and a Python
  implementation map the same caller id to the same Langfuse trace.

This replaces the v0.10.0 Langfuse adapter's current behavior of
passing non-UUID inputs through unchanged (which fails Langfuse's
trace-id parse). The OTel mapping is unaffected: there
`openarmature.invocation_id` is a span attribute carrying the raw
value, independent of the OTel span context's own trace id, so any
string value surfaces correctly.

**Why allow non-UUID rather than mandate hard-UUID.** A hard-UUID
requirement (the simpler alternative) was considered and rejected:
the whole point of caller-supplied `invocation_id` is to let a
consumer reuse an id from its own system (a run id, a job id), which
may not be a UUID. `correlation_id` already accepts any URL-safe
string for exactly this reason; constraining `invocation_id` to
UUIDs only would force consumers to maintain a UUID id-space solely
to satisfy OA, undermining the join-on-our-id use case the proposal
exists to serve. The deterministic Langfuse derivation closes the
one place a non-UUID value would otherwise break, so flexibility
costs only a small, well-defined mapping rule.

### Resume interaction

Resume (per checkpointing / per-instance fan-out resume) mints a
fresh `invocation_id` regardless: each attempt is its own
invocation in the §5.1 sense. A caller-supplied `invocation_id`
applies ONLY to the fresh-invocation path; on a resume call the
framework mints a fresh id and ignores any caller-supplied
`invocation_id` (a caller wanting to correlate resume attempts uses
`correlation_id`, which is stable across attempts by design). This
preserves the existing resume semantics unchanged.

## Spec-text changes (summary)

1. **observability §5.1** — reframe `openarmature.invocation_id`
   (caller-supplied or framework-generated; UUIDv4 mandate applies
   to the framework-generated case only).
2. **observability §3.2** — distinction table "Source" cell for
   `invocation_id`.
3. **observability §8.4.1** — Langfuse `trace.id` derivation: UUID →
   hex (verbatim, as today); non-UUID → deterministic SHA-256-based
   128-bit hex + raw id preserved in `trace.metadata.invocation_id`.
4. **graph-engine §3** — clarifying paragraph: `invoke()` MAY accept
   a caller-supplied invocation id (per-language idiomatic).

No changes to §5.2-§5.6, the OTel mapping (§4 / §7 — `invocation_id`
is an attribute there, format-agnostic), §6, or other §-sections.

## Conformance fixtures

- **`observability/conformance/NNN-caller-invocation-id-uuid`** —
  caller supplies a valid UUID `invocation_id`; it surfaces verbatim
  on `openarmature.invocation_id`; the Langfuse mapping sets
  `trace.id` to its 32-hex form; round-trips on the invocation span.
- **`observability/conformance/NNN-caller-invocation-id-non-uuid`** —
  caller supplies a non-UUID string (e.g., `"run_abc123"`); it
  surfaces verbatim on `openarmature.invocation_id`; the Langfuse
  mapping sets `trace.id` to the deterministic SHA-256-derived
  32-hex value and writes the raw id to
  `trace.metadata.invocation_id`.
- **`pipeline-utilities/conformance/NNN-resume-mints-fresh-invocation-id`** —
  a resume call supplying a caller `invocation_id` mints a fresh id
  for the resumed attempt and does NOT adopt the caller-supplied
  value (caller-supplied applies to the fresh-invocation path only).

(Exact fixture numbers assigned at accept time against the then-current
conformance sequences.)

## Versioning

**MINOR bump.** Additive: a new opt-in caller surface, a §5.1
reframe that relaxes (does not tighten) the format constraint, a new
§8.4.1 derivation branch for a value shape that could not previously
occur, and a graph-engine §3 clarifying touch. No breaking changes
for callers that don't supply an `invocation_id` (unchanged
UUIDv4-minting behavior).

## Backwards compatibility

- **Callers not supplying `invocation_id`:** no change — framework
  mints a UUIDv4; Langfuse `trace.id` derivation is the
  UUID-to-hex path, identical to today.
- **The v0.10.0 Langfuse adapter** currently passes non-UUID inputs
  through unchanged (producing a broken trace). Implementing this
  proposal changes that path to the SHA-256 derivation — a behavior
  change only for the non-UUID case, which is newly reachable by
  this proposal. No existing (UUID-only) behavior changes.

## Out of scope

- **Caller-supplied ids for nested constructs** (subgraph / fan-out
  instance / detached trace ids). This proposal covers the
  outermost invocation id only; nested ids remain framework-derived.
- **Changing the OTel span-context trace id.** The OTel mapping's
  trace id is managed by the OTel SDK; `openarmature.invocation_id`
  remains a span attribute. This proposal does not make the OTel
  trace id caller-settable.
- **Resume adopting a caller-supplied id.** Explicitly preserved as
  fresh-mint (see Resume interaction).

## Open questions

None blocking at draft time. The validation strictness (any
URL-safe string, not hard-UUID) and the Langfuse non-UUID derivation
(SHA-256 → 128-bit hex + raw-id-in-metadata) are resolved above. The
deterministic-derivation algorithm is pinned (SHA-256, first 16
bytes, lowercase hex) so cross-implementation Langfuse trace ids
agree for a given non-UUID caller id.
