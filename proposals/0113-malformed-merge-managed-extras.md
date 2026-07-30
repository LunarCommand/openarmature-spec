# 0113: Malformed Extras on a Merge-Managed Wire Field

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-29
- **Targets:** spec/llm-provider/spec.md **§6 Managed-field collision** (the *merge* arm — the
  **Additive / list-shaped** bullet, ~L543–545): add the malformed-value case the merge arm leaves
  undefined. When a caller's undeclared extras value for a merge-managed field is **malformed** — not the
  field's expected list shape, or a list containing an element that is not of the field's expected element
  type/shape — the mapping treats the whole extras value as **absent** and sends only the value(s) it would
  send with no such extra present (all-or-nothing, no partial salvage), and does not raise or emit a
  diagnostic. Inherited by retrieval-provider §10 / §8.4
  (`embedding_types`, whose mandatory value is `["float"]`). The **reject** arm is unaffected (a malformed
  value is already unequal to the managed value, so it is a *conflict* and rejected pre-send today).
- **Related:** 0105 (established the general §6 *Managed-field collision* rule and its merge / reject arms),
  0099 (pinned the `embedding_types` merge but only for a well-formed extras value), 0108 (extended the rule
  to declared-field-realizing wire keys); §7 *Malformed ancillary figures* (the response-side principle this
  applies to the request side)
- **Supersedes:**

## Summary

§6's merge arm defines only the **well-formed** case: an extras value that is a valid list of the field's
members is merged with the mapping's mandatory value(s), ordered and de-duplicated. It says nothing about a
**malformed** extras value — one that is not a list at all, or a list carrying an element that is not a valid
member. With the behavior unspecified, an implementation may currently fall back to the mandatory value(s),
salvage the well-formed elements, or reject the call — three conforming readings that produce three different
wire requests. This proposal pins the reading: a malformed merge-extra is treated as **absent** (the mapping
sends only the value(s) it would send with no such extra, all-or-nothing, no diagnostic), grounded in §7's
established treatment of malformed *ancillary* data as not-reported. It is behaviorally-normative — two implementations otherwise
diverge on the same request.

## Motivation

**The merge arm is silent on malformed input.** §6's *Additive / list-shaped* bullet reads: "the mapping's
mandatory value(s) and the caller's value(s) are **merged** in a deterministic order … de-duplicated with
first occurrence winning." That prose assumes the caller's value is a well-formed list of valid members. It
does not say what a mapping does with `embedding_types: ["int8", {"x": 1}]` (a list with a malformed element)
or `embedding_types: 5` (not a list). Nothing elsewhere in §6, §7, or the §8.x mappings fills the gap — the
only "malformed" rules in the spec are §7's *response-side* ancillary figures.

**Three conforming readings exist today, so the choice is behavioral, not editorial.** Because the spec is
silent, a conforming implementation may:

1. **fall back** — treat the malformed value as absent and send only the mandatory value(s) (`["float"]`);
2. **salvage** — merge the well-formed elements and drop the malformed ones (`["int8", {"x": 1}]` →
   `["float", "int8"]`); or
3. **reject** — fail the call pre-send with `provider_invalid_request`.

They produce different outbound requests, so this is exactly the kind of gap a numbered proposal closes rather
than a clarification: pinning one reading makes the other two non-conforming (a change to conformance-test
expectations, not a restatement of an implied rule). The gap surfaced from a downstream adversarial review of
the `embedding_types` merge — a caller reads their requested precisions off the verbatim response (`raw`), so a
silently-partial request (reading 2) is worse than a clean fallback, and 0099 pinned the merge itself without
defining the malformed edge.

**The response-side already answers the request-side.** §7 *Malformed ancillary figures* establishes OA's
disposition toward malformed **ancillary** data: it is "treated as not reported" — nulled, never raised, never
repaired or fabricated. `embedding_types` (and `stop`) extras are ancillary caller decoration on top of a
valid core request. Applying the same principle to the request side, a malformed ancillary **extra** is
treated as **not supplied** — the mapping proceeds with the value(s) it would send anyway, exactly as §7
proceeds with a nulled figure. This weights the choice toward reading 1: the malformed value is optional
decoration on an otherwise-valid core request, so treating it as not-supplied mirrors §7's handling of a
malformed figure as not-reported. Reading 3 (fail-loud reject) is a coherent alternative — a caller-supplied
malformed value is a request error, and `provider_invalid_request` is the category for one — but it elevates a
malformed *optional* extra to a call-fatal error on a valid core request, the heavier choice; §7's disposition
toward ancillary data favors proceeding.

## Proposed change

### llm-provider §6 — the merge arm's malformed case

Extend the *Additive / list-shaped* merge bullet with the malformed-value rule:

- A caller's extras value is **malformed for the merge** when it is not the field's expected list shape, or is
  a list containing **any** element that is not of the field's expected element **type/shape** (e.g. a
  non-string element where the field's members are precision strings). Malformation is judged
  **structurally**: the mapping does **not** semantically validate element *values* against a provider
  vocabulary (the spec enumerates none), so a well-typed but provider-unrecognized member is **not**
  malformed — it is merged, and the provider rejects it if unsupported.
- A malformed merge-extra is treated as **absent**: the mapping sends **only the value(s) it would send with
  no extra for that key present** — its mandatory value(s) for a field like `embedding_types` (`["float"]`),
  or the declared field's value(s) for a clause-(b) realization like `stop` (the declared `stop_sequences`).
  The mapping **MUST NOT** salvage the well-formed elements of a partially-malformed list (it is
  **all-or-nothing**) — salvaging would send a value the caller never wrote, and the caller reads the
  effective set off the verbatim response (`raw`).
- The mapping **MUST NOT** raise on a malformed merge-extra, and **MUST NOT** emit a diagnostic for the
  discard. This mirrors §7 *Malformed ancillary figures*, which treats a malformed ancillary figure as
  not-reported rather than raising; a malformed ancillary **extra** is likewise not-supplied. The caller's
  original extras remain visible verbatim on the typed event (e.g. `EmbeddingEvent`) and, where a mapping
  exposes it, the request surface — so the discard is inspectable without a bespoke diagnostic no §8 section
  defines.

This is a merge-arm addition only. The **reject** arm is unchanged: a malformed value is not **equal** to the
managed value under §6's decoded-value deep-equality test, so it is a **conflict** and already rejected
pre-send with `provider_invalid_request` (§7) — the reject arm is fail-loud by construction, and a malformed
value inherits that disposition. The asymmetry is deliberate and follows each arm's existing logic: the merge
arm accepts valid caller additions and therefore ignores a non-addition; the reject arm admits only an exact
match and therefore rejects everything else.

### retrieval-provider §8.4 — inherited, one-line pointer

`embedding_types` (mandatory `["float"]`) is the concrete merge-managed instance. §8.4 gains a one-line
pointer that the general §6 malformed-merge rule applies: a malformed or partially-malformed extras
`embedding_types` falls back to `["float"]`. No retrieval-specific behavior — the rule is the general one.

## Conformance test impact

The rule is general (§6), with two current merge-managed instances — llm-provider `stop` (← `stop_sequences`)
and retrieval `embedding_types` — so it is pinned at both, numbers assigned at Accept:

- **retrieval / Cohere `/v2/embed` — partially-malformed `embedding_types`.** Extras
  `embedding_types: ["int8", {"x": 1}]` → the wire request carries `embedding_types: ["float"]` (the malformed
  list treated as absent; the well-formed `"int8"` is **not** salvaged). Compilation/send succeeds; no error.
- **retrieval / Cohere `/v2/embed` — fully-malformed `embedding_types`.** Extras `embedding_types: 5` (not a
  list) → wire `embedding_types: ["float"]`.
- **llm-provider `stop` — malformed extras (general-rule instance).** A malformed extras `stop` (e.g. a
  non-list, or a list with a non-string element) alongside a declared `stop_sequences` → the wire carries only
  the declared value(s), the malformed extra treated as absent — demonstrating the rule at its §6 home, not
  only on the retrieval instance.

A well-formed merge (0099 / 0105 fixtures) is unchanged, and the reject-arm fixtures (0105 046–048, 072–074)
are unaffected — this adds the malformed-input case to the merge arm; it changes none of their behavior.

## Versioning

**MINOR bump** (pre-1.0), additive. It adds a behavioral clause to §6's merge arm covering input the arm
previously left undefined, plus fixtures; no existing well-formed behavior changes, and the reject arm is
untouched. An implementation that already fell back to the mandatory value(s) is unaffected; one that salvaged
or rejected gains the pinned behavior. Ships as spec **v0.107.0** (llm-provider §6 text + retrieval §8.4
pointer + the new fixtures).

## Alternatives considered

1. **Salvage the well-formed elements.** Reject — it sends a precision set the caller never wrote, and because
   the caller reads the effective set off the verbatim response (`raw`), a silently-partial request is a
   valid-but-wrong result that is harder to diagnose than a clean fallback. A partially-malformed list is
   itself ambiguous to "repair," and all-or-nothing is the deterministic, testable rule.
2. **Fail loud — reject the call with `provider_invalid_request`.** Reject — it elevates a malformed
   **optional** decoration to a call-fatal error on an otherwise-valid core request, contrary to §7's
   established treatment of malformed ancillary data as not-reported rather than raised. Fail-loud is the
   reject arm's disposition (for mutually-exclusive managed fields), not the merge arm's (for additive caller
   decoration).
3. **Emit a diagnostic / warning for the discard.** Reject — no §8 section defines such a surface, and the
   caller's original extras are already visible verbatim on the typed event; inventing an observability
   surface for this one case would be inconsistent with §7 (which nulls a malformed figure without a
   diagnostic) and out of scope.
4. **A §8.4-local rule for `embedding_types` only.** Reject — the hazard is general to every merge-managed
   field (today `embedding_types` and `stop`), and per-vendor patching is what produced the copied-sentence
   drift 0099 had to correct. The rule belongs on §6's merge arm, inherited, consistent with 0105 / 0108.

## Open questions

- None. The disposition (treat-as-absent, all-or-nothing, no diagnostic) is the request-side application of
  §7's malformed-ancillary principle; the reject arm's malformed handling already falls out of its
  deep-equality conflict rule.

## Out of scope

- **The reject arm** — a malformed value there is already a conflict (unequal to the managed value) and
  rejected pre-send; unchanged.
- **A well-formed merge** — unchanged (0099 / 0105): valid caller precisions merge with the mandatory value(s),
  ordered and de-duplicated.
- **§7 response-side malformed figures** — unchanged; this proposal borrows the principle, it does not touch
  the response side.
- **Undeclared, unmanaged extras** — a malformed value for a key the mapping does **not** manage keeps the §6
  untouched pass-through (the mapping does not inspect or validate unmanaged extras).
