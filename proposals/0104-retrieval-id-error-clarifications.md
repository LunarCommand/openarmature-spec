# 0104: Retrieval id/error clarifications — empty-string `response_id`, Jina bare-400

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-18
- **Targets:** spec/retrieval-provider/spec.md **§4 / §6** (the `response_id` rows — an empty-string identifier
  is not a present one), and **§8.2** (the Jina error mapping — a bare `400` maps to `provider_invalid_request`,
  not `provider_unavailable`). Conformance: one empty-string-`response_id` fixture and one Jina-`400` fixture.
- **Related:** 0100 (malformed ancillary figures — the `response_id` "not a present one → null" rule this
  extends from *malformed* to *empty*), 0097 (the `document` echo, whose empty-string handling this deliberately
  diverges from and explains why)
- **Supersedes:**

## Summary

Two under-specified edges in retrieval-provider let conforming implementations diverge. Both surfaced as
cross-mapping inconsistencies:

1. **Empty-string `response_id`.** §4 / §6 say `response_id` is "the provider-returned response identifier when
   present; null otherwise," and 0100 added "a **malformed** identifier is not a present one — it is `null`."
   Neither pins the **empty string** `""`. Mappings diverge: one folds `""` → `null`, others surface a literal
   `""`.
2. **Jina bare-`400`.** §8.2's error enumeration lists only `422` → `provider_invalid_request`, so a bare `400`
   falls through to the catch-all `provider_unavailable` — diverging from every other mapping (§8.1 / §8.3 /
   §8.4 all map `400` → `provider_invalid_request`) and from the general §7 intent.

This proposal pins both:

- **An empty-string `response_id` is not a present one — it is `null`.**
- **§8.2 maps a bare `400` to `provider_invalid_request`.**

## Motivation

### Empty-string `response_id`

`response_id` is an **identifier**. An empty string is not a usable identifier — it correlates nothing, matches
no provider record, and is indistinguishable from "the provider returned no id." Treating `""` as *present*
propagates a meaningless value onto `EmbeddingResponse.response_id`, the typed `EmbeddingEvent.response_id`, and
the OTel `gen_ai.response.id` attribute, where a consumer cannot tell it apart from a real id. Treating it as
*absent* (`null`) is the useful contract and is already what the strictest mapping does.

**Why this diverges from 0097.** 0097 ruled that an empty-string `document` echo stays **present** (`""`). That
is correct *there* and correct to differ *here*: `document` is **content** — an empty echo is a real, faithful
reproduction of what the provider returned, and suppressing it would lose the distinction between "echoed empty"
and "not echoed." `response_id` is an **identifier** — an empty id carries no such signal; it is simply the
absence of an id. Content preserves the empty value; an identifier collapses it to absent. The rule is stated at
the level of *what the field is for*, not a blanket empty-string policy.

This extends the existing "not a present one → `null`" rule (0100) from *malformed* to *empty*: a `response_id`
that is malformed **or** empty is `null`. No record shape or nullability changes.

### Jina bare-`400`

§8.2's enumeration names `422` (Jina's over-length/validation status) but omits `400`, so the mapping's
catch-all routes a bare `400` to `provider_unavailable`. That is wrong on two counts: it diverges from §8.1 /
§8.3 / §8.4, which all map `400` → `provider_invalid_request`; and `provider_unavailable` is a **transient**
category (a caller may retry), while a `400` is a malformed request that will not succeed on retry. A request
error misclassified as transient invites a pointless retry loop.

## Proposal

### 1. §4 / §6 — empty-string `response_id`

Amend the `response_id` rows: an empty-string identifier, like a malformed one, is **not a present identifier**
— it is `null`. (The row already reads "the provider-returned response identifier when present; null otherwise.
A malformed identifier is not a present one — it is `null`"; this adds the empty string to that clause.) The
mapping MUST NOT surface `""` on `response_id`. This is scoped to `response_id`; the parallel `model` /
`response_model` empty-value question remains the separate cross-cutting open question already tracked.

### 2. §8.2 — Jina bare-`400`

Amend §8.2's error enumeration so a bare `400` (malformed / invalid request) maps to
`provider_invalid_request`, alongside the existing `422`: "malformed request (`400` / `422`) →
`provider_invalid_request`." This aligns §8.2 with §8.1 / §8.3 / §8.4 and with the general §7 category
semantics; the transient `provider_unavailable` catch-all no longer captures a `400`.

### 3. Conformance

- An empty-string-`response_id` fixture: a mapping whose mocked response carries `response_id: ""` asserts
  `EmbeddingResponse.response_id` (and the typed event) is `null`, not `""`.
- A Jina-`400` fixture: a mocked Jina `400` asserts the raised category is `provider_invalid_request`.

## Versioning

**MINOR** (whole-spec SemVer), expected as a batch accept. **Behavioral at two edges**: a mapping that surfaced
`""` on `response_id`, or routed a Jina `400` to `provider_unavailable`, changes outcome in exactly those two
cases. Both are corrections of under-specified edges toward cross-mapping consistency; neither affects a
well-formed response or a non-`400` error. Pre-1.0, folded into a MINOR.

## Open questions

- The `model` / `response_model` empty-value / malformed-value question is out of scope here and remains the
  separate cross-cutting open question (a provider returning an empty or malformed model identifier is handled
  inconsistently between a response and its typed event).
