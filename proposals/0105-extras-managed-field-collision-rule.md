# 0105: Extras-key vs mapping-managed wire-field collision rule

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-18
- **Targets:** spec/llm-provider/spec.md **§6** (a general rule for what happens when an undeclared extras key
  collides with a wire field the mapping *manages* — an explicit, bounded carve-out to the untouched
  pass-through), inherited by retrieval-provider §10. Applied to the known managed keys: **§8.4** `embedding_types`
  (the *merge* arm, ratifying 0099's mapping-local exception as the general rule) and the fail-loud truncation
  flag in **§8.1 / §8.2 / §8.4** (`truncate` / `truncation`, the *reject* arm). Conformance: a reject-arm fixture.
- **Related:** 0099 (pinned the §8.4 `embedding_types` collision as a mapping-local exception and explicitly
  left the general rule open — this closes it), and §6's *Extras pass-through* contract this carves out of
- **Supersedes:**

## Summary

llm-provider §6 says an undeclared extras field is forwarded to the wire body **untouched** and MUST NOT be
translated, renamed, or transformed. It says nothing about an extras key that collides with a wire field the
mapping itself **manages** — a field the mapping sets for its own correctness (e.g. Cohere's
`embedding_types: ["float"]`, which its response consumer reads; `truncate: "NONE"`, which enforces the
fail-loud posture). Under untouched pass-through, a caller's colliding extras value silently overrides the
managed field and **breaks the mapping** — the exact failure 0099 prevented for one key and explicitly declined
to generalize. Two conforming implementations can diverge: forward-untouched, let-the-mapping-win, or
silently-drop.

This proposal states the general rule, bounded to keys a mapping declares it manages:

> **A managed wire field governs a colliding extras key.** If the field is additive / list-shaped, the caller's
> value(s) are **merged** with the mapping's (de-duplicated, so a matching entry collapses). If it is a scalar
> whose override would break the mapping's contract, a value **equal** to the managed value is a redundant
> no-op and a **conflicting** value is **rejected pre-send** (`provider_invalid_request`). A mapping MUST NOT
> silently drop a conflicting value or silently let it override the managed one. Keys the mapping does **not**
> manage keep untouched pass-through unchanged.

## Motivation

### The gap 0099 left open

0099 pinned the §8.4 `embedding_types` collision as an explicit **mapping-local** exception: the mapping must
request `"float"` for its own response consumer, so an extras-supplied `embedding_types` is **merged** with
`"float"` rather than replacing it. 0099 closed with: "The general question — what happens when *any* extras key
collides with *any* mapping-managed wire field — is not specified." This is that specification.

The failure mode is concrete. A managed field is one the mapping sets because its own logic depends on it. If an
undeclared extras key of the same name reaches the wire untouched (as §6 currently requires), it overrides the
managed value and defeats the mapping: an extras `embedding_types: ["int8"]` strips the `embeddings.float` key
the response consumer reads (0099's case); an extras `truncate: "END"` overrides the mapping's `"NONE"` and
silently truncates an over-length input the mapping meant to fail loud on. Untouched pass-through is correct for
a field the mapping doesn't touch; it is wrong for a field the mapping owns.

### Why merge for some, reject for others

The resolution depends on the **shape** of the managed field:

- **Additive / list-shaped** (`embedding_types`): the managed value and the caller's can coexist — the wire
  accepts a set, and the response is keyed by member, so the mapping requests `"float"` **and** the caller's
  precisions. **Merge** (deterministic order, de-duplicated) preserves both without breaking the consumer.
- **Scalar mode-switch** (`truncate`, and — when it lands — an output `encoding_format`): the field selects one
  behavior; the managed value and the caller's are mutually exclusive. There is nothing to merge, and honoring
  the caller's value breaks the mapping's contract (its fail-loud posture, its response format). The only safe
  resolution is to **reject pre-send** with `provider_invalid_request` — fail-loud, not a silent drop (which
  would hide the caller's intent) and not a silent override (which would break the mapping).

Rejecting is not hostile to the extras mechanism: it applies only to a key the mapping **manages**, which the
mapping declares. Every other undeclared key still passes through untouched. The rule narrows, it does not close,
the extras bag.

## Proposal

### 1. §6 — the general rule (bounded carve-out)

Add to §6's *Extras pass-through* a **managed-field collision** clause:

- Define a **managed wire field**: a wire-body field the wire-format mapping (§8) sets for its own correctness —
  because its response consumer reads a value keyed to it, or because it enforces a mapping-level contract. Each
  §8.x mapping **MUST enumerate** the keys it manages.
- When an undeclared extras key **names a managed field**, untouched pass-through does **not** apply. Instead:
  - **Merge** if the managed field is additive / list-shaped: the mapping's mandatory value(s) and the caller's
    are combined, in a deterministic order (mapping value(s) first), de-duplicated first-occurrence-wins.
  - **Reject pre-send** with `provider_invalid_request` (§7) if the managed field is a scalar whose override
    would break the mapping's contract or its response consumer — **unless** the extras value **equals** the
    managed value, which is a redundant no-op (the scalar analogue of the merge arm's de-duplication).
  - A mapping **MUST NOT** silently drop a conflicting extras value, and **MUST NOT** silently let it override
    the managed value.
- A key the mapping does **not** manage is unaffected: it keeps the untouched pass-through of §6 verbatim. The
  managed set is opt-in per mapping; the default for any other key is unchanged.

### 2. §8.4 `embedding_types` — the merge arm (ratify 0099)

Re-anchor 0099's `embedding_types` exception as an **instance** of §6's merge arm rather than a standalone
mapping-local exception: `embedding_types` is a managed list-shaped field; an extras-supplied value merges with
`"float"` (float-first, de-duplicated), per §1. The behavior is unchanged; only its framing generalizes.

### 3. `truncate` — the reject arm (§8.2 / §8.4)

The TEI (§8.1), Jina (§8.2), and Cohere (§8.4) embed mappings each send a **managed fail-loud truncation flag**
so an over-length input errors rather than being silently truncated — `truncate: false` (TEI; Jina
`/v1/embeddings`), `truncation: false` (Jina `/v1/rerank`), `truncate: "NONE"` (Cohere). The value type differs
by vendor, but in each case the mapping sets the flag to enforce its fail-loud contract. Declare each mapping's
truncation flag a **managed scalar**: an extras-supplied value that **conflicts** with the managed flag is
**rejected pre-send** with `provider_invalid_request` (honoring it would defeat the fail-loud posture; the
mapping MUST NOT silently drop it either); a value **equal** to the managed flag is a redundant no-op.

### 4. Conformance

A reject-arm fixture: an extras `truncate` colliding with a mapping's managed value raises
`provider_invalid_request` pre-send (no wire request issued). The existing merge-arm fixture (039,
`embedding_types`) already exercises §1's merge arm.

## Versioning

**MINOR** (whole-spec SemVer), expected as a batch accept. **Behavioral for a managed-key collision only**: a
**conflicting** extras value on a managed scalar (`truncate`) that a mapping previously forwarded untouched now
rejects pre-send. That prior behavior was undefined and harmful (it silently defeated the mapping), so this is a
correction, not a removal of working behavior. A matching value is a no-op; every unmanaged extras key is
unaffected; the `embedding_types` merge is unchanged from 0099.

## Open questions

- **Full per-mapping managed-key audit.** §1 requires each §8.x mapping to enumerate its managed keys; this
  proposal enumerates the currently-known ones (`embedding_types`, `truncate`). A future §8.x mapping MUST
  declare its own; the enumeration is per-mapping, not a global list. An output `encoding_format` will be the
  first *new* reject-arm managed key when output-encoding support lands (a separate proposal).
