# 0100: A malformed ancillary figure is *not reported*, never a malformed response (retrieval-provider)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-12
- **Targets:** spec/retrieval-provider/spec.md **§7** (the carve-out: a malformed *ancillary* figure MUST
  NOT raise `provider_invalid_response`), **§4** / **§6** (the `usage` / `response_id` rows — a
  returned-but-malformed record is not a returned record), and **§8** *Batch chunking* step 4 (the stitched
  figure when a chunk is malformed). spec/graph-engine/spec.md **§6** (the typed `EmbeddingEvent` /
  `RerankEvent` carry the same figures — the rule must bind them, or an implementation can null the
  response yet emit the garbage figure on the event). Conformance (at Accept): embedding (single-figure
  collapse + `response_id`), rerank (partial record), and chunk-and-stitch fixtures, each also asserting
  the typed event mirrors the response.
- **Related:** 0093 (nullable provider usage records — established retrieval `usage = record | null`, the
  "a record is present when at least one figure is reported" rule this builds on, and the no-fabrication
  rule this extends to malformed input), 0096 (`raw` verbatim provider response — why not-reporting a
  figure loses nothing), 0097 (rerank `document` echo — the *payload* side of this boundary, whose
  raise-on-corruption rule this supplies the principle for)
- **Supersedes:**

## Summary

The spec pins what a malformed **payload** does on a retrieval call: `provider_invalid_response`. It is
silent on a reported **figure** that is present but garbage — a token count of `"abc"`, a negative, a
boolean where an integer belongs.

So two conforming implementations diverge on the same wire: one raises and discards a sound set of vectors
over an accounting figure; the other reports the count as unknown and returns the result. That is the
divergence conformance exists to eliminate.

This pins one rule, stated at the level of the **figure** rather than the field:

> **A malformed figure is not a reported figure.**

Everything else follows from rules retrieval-provider already has. The usage record shape is unchanged
(0093); the observability surfaces already emit conditionally on a figure being reported; and
`provider_invalid_response` stays where §7 already put it — on the payload.

This proposal is **scoped to retrieval-provider**. The parallel llm-provider question is materially larger
— llm-provider's usage record is never null, so a null counter is a state its observability guards do not
currently anticipate — and is handled separately (see *Alternatives* #4).

## Motivation

### The gap

retrieval-provider §4 / §6 say `usage` is a record "when the provider reports one," `null` when it does
not, and MUST NOT be fabricated. `response_id` is "the provider-returned response identifier when present;
null otherwise." Neither says what happens when the figure **is** present and **is** garbage. The wire
produces this: a provider bug, a proxy that stringifies numbers, a gateway that rewrites a field. The
vectors come back sound and the accounting block does not.

### Why *not reported*, and not `provider_invalid_response`

**The call succeeded.** The vectors are intact, the ranking is valid, the invariants hold. Failing the
whole call over a secondary accounting figure discards a good result to report a bad number.

**Not-reporting loses nothing.** `raw` carries the verbatim provider response (0096), so the corrupt value
is still there for any caller who wants it. The normalized figure says "unknown"; the transparency surface
says exactly what the provider sent. Raising, by contrast, destroys the result *and* still sends the caller
to `raw` to find out why.

**§7's own enumeration already says so.** retrieval-provider §7 defines `provider_invalid_response` as
"missing required fields, or a violation of the capability's cross-impl invariants," and every invariant it
lists is payload-integrity — mismatched vector count, inconsistent dimensions, out-of-range or duplicate
`index`, more results than `top_k`. **`usage` and `response_id` appear nowhere in it.** The category was
already drawn around the payload; this states the boundary it was drawn around.

### Why this is not in tension with 0097

0097 ruled that a rerank `document` echo of a non-object scalar **is** a `provider_invalid_response`. That
looks like the opposite call until the line is drawn where it actually falls — and the line is
**structural**:

- `document` lives **inside a result entry**. A type violation there means the provider's result-object
  schema is violated, which impugns the `results` array itself. You cannot trust the ranking if you cannot
  trust the shape of a result.
- `usage` and `response_id` sit **beside** the payload. A garbage token count says nothing about whether
  the vectors are sound.

One principle, two outcomes: **corruption inside the payload raises; a corrupt figure beside it is treated
as absent.** 0097 was applying this without naming it.

### Why "figure", not "field"

`RerankUsage` already types its two counters (`search_units`, `input_tokens`) as individually nullable
(0093): "a record is present when at least one figure is reported." So "record present, one figure absent"
is a state retrieval-provider **already** admits. Phrasing the rule over the *figure* means a malformed
`input_tokens` beside a sound `search_units` lands in that existing state — a record carrying
`search_units` only — with no new nullability introduced and no observability guard disturbed (the retrieval
usage attributes already omit a figure that is not reported: observability §5.5.13 already varies on
"whether a *present* record carries a token count"). A field-level rule would have had to invent something;
the figure-level rule inherits what is already there.

## Proposed change

### Definition

A figure is **malformed** when it is present on the wire but does not conform to its declared type or
domain — a non-integer where an integer is required, a negative count, a boolean or string in a numeric
field. Distinct from a value the mapping does not *recognize*, which each §8 mapping handles on its own
terms.

The **ancillary** figures on a retrieval response are those the provider reports *about* the call rather
than *as* its result: the figures inside `usage` (`EmbeddingUsage.input_tokens`;
`RerankUsage.search_units` / `RerankUsage.input_tokens`), and `response_id`. They are enumerated, not
open-ended.

### The rule

**A malformed ancillary figure MUST be treated as not reported.** It:

- **MUST NOT** raise `provider_invalid_response` (or any §7 category);
- **MUST NOT** be fabricated, coerced, clamped, or repaired — not a negative clamped to `0`, not a `"12"`
  parsed to `12`. A repaired figure is indistinguishable from a reported one, which is fabrication under
  another name: the same thing §4 / §6 already forbid for *absent* figures;
- **MUST** remain verbatim on `raw` (§4 / §6), which is where a caller inspects what the provider sent.

Each figure is judged **independently**, and what that yields follows from §4 / §6's existing record rules:

- **`EmbeddingUsage`** — a single figure. Malformed `input_tokens` ⇒ no figure is reported ⇒ `usage = null`
  (§4's record is present only when its figure is).
- **`RerankUsage`** — two individually-nullable figures. A malformed `input_tokens` beside a sound
  `search_units` ⇒ a record carrying `search_units` only (§6's "a record is present when at least one
  figure is reported"). Both malformed ⇒ `usage = null`.
- **`response_id`** — malformed ⇒ `null` (§4 / §6: "when present; null otherwise").

No record shape changes. The rule adds no new nullability anywhere.

### The rule binds the typed events, not just the response

A figure that is not reported is not reported **anywhere it surfaces**. An implementation **MUST NOT**
surface a malformed provider figure on the typed events — graph-engine §6 `EmbeddingEvent.usage` /
`RerankEvent.usage` and the `response_id` on those events — any more than on the response.

**This clause is load-bearing.** Observability renders spans and Langfuse observations *from the typed
event*, not the response (0089). Without it an implementation could null the response and still emit the
garbage figure on the event — and the corrupt number would reach the span, the trace, and the billing
dashboard anyway, with the rule satisfied on paper. The observability attributes themselves
(observability §5.5.8 / §5.5.13 for OTel, §8.4.5 / §8.4.7 for Langfuse, and the §11.2 metrics histogram)
need **no change**: they already emit conditionally on a figure being reported (0093), so a not-reported
figure is already omitted once the event carries it as absent. (The rerank surfaces guard per-figure
directly; the embedding surfaces guard per-record, which is equivalent here because `EmbeddingUsage` is
single-figure — a malformed figure collapses the record to `null`.)

### Chunk-and-stitch (retrieval §8)

§8 *Batch chunking* step 4 currently reads: "combine the per-chunk usage … **sum the
`EmbeddingUsage.input_tokens` when the provider reports usage**, or produce `usage = null` when it reports
none," with "`EmbeddingResponse.response_id` is the **first** chunk's response id." A malformed chunk is
neither the report-usage nor the report-none case, so §8 is amended:

- If **any** chunk's `input_tokens` is malformed, that chunk has not reported usage, so the stitched figure
  is **not reported** ⇒ `usage = null`. A mapping **MUST NOT** sum only the well-formed chunks: that
  produces a total the provider never reported, which understates the true count and is indistinguishable
  from a truthful figure — the fabrication this proposal forbids.
- If the **first** chunk's `response_id` is malformed ⇒ `response_id = null`. A mapping **MUST NOT** fall
  through to a later chunk's id: the contract is "the first chunk's id," and substituting a different
  chunk's id reports an identifier the call does not have.

Nothing is lost either way: `raw` is the list of the per-chunk responses (0096), so every chunk's verbatim
figure remains available.

### Reconciling the sections that currently say otherwise

- **§4 / §6** — the `usage` rows say "Implementations MUST populate `usage` when the provider returns a
  usage record." Read literally that captures a returned-but-*malformed* record. They gain the carve-out: a
  malformed figure is not a reported one.
- **§7** — gains the carve-out clause (a malformed ancillary figure MUST NOT raise).
- **§8** — step 4's usage-combine and first-chunk-`response_id` clauses gain the malformed-chunk handling
  above.

### What is *not* changed

The payload side stands exactly as it is: §7's enumerated invariants and 0097's `document` rule are
untouched, and this proposal adds **no new payload obligation**. Whether §7's payload enumeration should
generalize — a `relevance_score` returned as `"0.9"` is not currently an enumerated invariant — is a
separate question, recorded in `docs/open-questions.md`.

`EmbeddingResponse.model` / `RerankResponse.model` and the events' `response_model` are **not** ancillary
figures under this rule. `model` is non-nullable with an established fallback to the bound model identifier
where the provider returns none (§8.4); reconciling a malformed provider model against that fallback, and
against the event's separately-nullable `response_model`, is a distinct question left to the dedicated
`model` / `response_model` open-questions entry, not folded in here.

## Conformance test impact

**At Accept** — the spec edits and fixtures land with the accept PR:

- **embedding** — sound vectors alongside a malformed `input_tokens`. Asserts `usage = null` (the
  single-figure collapse), vectors and dimensions intact, **no raise**, the corrupt value verbatim on
  `raw`, **and the typed `EmbeddingEvent.usage` null to match**. A second case: a malformed `response_id`
  → `null`, verbatim on `raw`.
- **rerank** — the **partial record**: a sound `search_units` beside a malformed `input_tokens` ⇒ a
  `RerankUsage` carrying `search_units` only, `input_tokens` null. `EmbeddingUsage` has a single figure and
  so cannot express a partial record; rerank is where this half of the rule is exercised.
- **chunk-and-stitch** — one chunk of several reports a malformed `input_tokens` ⇒ the stitched
  `usage = null` (not a partial sum), with every chunk's verbatim response on `raw`.

The payload side needs no new fixture: it is unchanged, and 0097's fixture 019 case G already covers the
raise.

## Versioning

**MINOR bump** (pre-1.0). **Previously-undefined behavior.** retrieval §4 / §6 addressed only
absent-vs-reported, and §7's invariant list is payload-only, so the spec said nothing about a malformed
ancillary figure; no fixture covered it. No implementation could have conformed to a rule that did not
exist — but one that raises `provider_invalid_response` on a malformed usage figure becomes non-conforming,
and one that nulls the response while emitting the malformed figure on the typed event becomes
non-conforming.

Nothing previously specified changes: no record shape, no nullability, the no-fabrication rule (0093), and
0097's `document` boundary all stand exactly as written. Tentative spec version target deferred to Accept.

## Alternatives considered

1. **Raise `provider_invalid_response` on a malformed ancillary figure.** Reject — it discards a sound
   result (intact vectors, valid ranking) to report a bad accounting number, and buys nothing: `raw`
   already preserves the corrupt value, so the caller loses information rather than gaining it. §7's own
   invariant list is payload-only, so raising here would widen the category past what it was drawn around.
2. **Coerce or repair the figure** (clamp a negative to `0`, parse `"12"` → `12`). Reject — fabrication
   under another name. §4 / §6 already forbid fabricating a figure the provider did not report; a
   *repaired* figure is worse, because it is indistinguishable from a reported one and the caller has no way
   to know the number is invented. The same argument kills the partial-sum reading of chunk-and-stitch.
3. **Phrase the rule over fields rather than figures.** Reject — `RerankUsage` already types its figures as
   individually nullable, so a figure-level rule inherits an existing state ("record present, one figure
   absent") while a field-level rule would have to invent whole-record collapse for a single bad counter,
   discarding the sound one beside it.
4. **Extend the rule to llm-provider in this proposal.** Reject — *for now*, and on the merits, not for
   convenience. llm-provider's `Response.usage` is an always-present record (0093 declined to make it
   nullable), so a null counter is a state its observability guards do not currently anticipate: the
   OTel §5.5.3 usage attributes and the §11.2 token-usage histogram omit on a **record** being null, the
   §11.2 token-budget instruments compute comparisons and ratios over the counters, and a mapping that
   derives `total_tokens` by summing (§8.2) has to decide what a summed-with-null total is. Reconciling that
   guard chain is a materially larger and riskier change than the retrieval gap that surfaced this one, and
   it earns its own proposal rather than riding along here. retrieval-provider has none of that exposure —
   its usage figures are already individually nullable and its usage attributes already omit conditionally
   — so the retrieval half is safe to land on its own.
5. **Leave it undefined.** Reject — two conforming implementations diverge on identical wire, and the cost
   of settling it rises once implementations have picked different answers.

## Out of scope

- **llm-provider.** A separate proposal, for the reasons in Alternative #4.
- **The payload side.** §7's enumerated invariants and 0097's `document` rule are unchanged; this proposal
  adds no payload obligation. Whether that enumeration should generalize to any type-malformed payload
  field is recorded in `docs/open-questions.md`.
- **`model` / `response_model`.** Non-nullable response field with a bound-id fallback vs a separately
  nullable event field; a distinct reconciliation, left to the dedicated `model` / `response_model`
  open-questions entry.
- **Record shapes and nullability.** Unchanged. `RerankUsage`'s individually-nullable figures are 0093's
  out-of-scope and stay as they are.
- **`raw`.** The verbatim response; not validated, not subject to this rule. Unparseable JSON is already
  `provider_invalid_response` (§7).
