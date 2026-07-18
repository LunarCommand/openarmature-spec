# 0101: A malformed usage counter is *not reported* — llm-provider + observability

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-15
- **Targets:** spec/llm-provider/spec.md **§6** (`Response.usage` — a malformed counter is not a reported
  counter; and the *Streaming assembly* clause — the verbatim usage must survive on `raw`), **§7** (its
  reservation clause, which today mandates the raise this forbids), **§8.2** (the *derived*
  `total_tokens`). spec/graph-engine/spec.md **§6** (`LlmCompletionEvent.usage` mirrors the response —
  present record, null counter, not a null record). spec/observability/spec.md **§5.5.3** (the
  `gen_ai.usage.*` / `openarmature.llm.usage.*` omit-guards, which key on the *record* being null),
  **§11.2** (the token-usage histogram, which records an observation per counter but skips only on an
  absent record), and the **§11.2** token-budget instruments (which compare and divide over the
  counters — the *exceeded* span signal is §5.5.15), plus the Langfuse `Generation` `usage`. Conformance (at Accept): the llm-provider counter
  cases, a derived-`total_tokens` case, a streamed-call case, and observability fixtures asserting the
  span, histogram, and budget surfaces omit rather than emit from a null counter.
- **Related:** 0100 (the figure-level principle this applies to the LLM surface — *"a malformed figure is
  not a reported figure"*), 0093 (nullable provider usage records — and the premise, that no completion
  mapping reaches the "no usage" state, that this updates), 0083 (per-prompt token-budget observability —
  the instruments reconciled here), 0067 (OTel GenAI metrics — the histogram reconciled here), 0062 (LLM
  completion streaming — the `raw` assembly this constrains)
- **Supersedes:**

## Summary

0100 pinned the figure-level rule — **a malformed figure is not a reported figure** — for retrieval-provider,
and deliberately left llm-provider out, because llm-provider is not the same shape. retrieval's usage
figures are already individually nullable (0093), so a null counter is an existing state its observability
guards already handle. llm-provider's `Response.usage` is an **always-present record** whose counters
0093 explicitly declined to null, and the entire LLM observability layer was built on that: the OTel usage
attributes, the token-usage histogram, and the token-budget instruments all assume that a present record
carries real integers.

This proposal applies the figure-level rule to llm-provider and reconciles the guard chain a null counter
runs through:

1. a malformed llm-provider usage counter is **not reported** — that counter is `null`, the others stand;
2. a **derived** figure (`total_tokens`, where a mapping computes it as `prompt + completion`) whose addend
   is not reported is **itself not reported**;
3. the typed event and every observability surface that renders a counter **omit** it when it is not
   reported, rather than emitting, comparing, or dividing over a null;
4. and the verbatim figure survives on `raw` even for a **streamed** call, so nothing is lost.

## Motivation

### The rule is the same; the exposure is not

The case for *not reporting* rather than raising is 0100's, unchanged: the completion succeeded, the message
is intact, `raw` preserves the corrupt value verbatim, and llm-provider §7's `provider_invalid_response` is
about a response that cannot be parsed into the §6 shape — not an accounting figure beside it. What differs
is what a null counter *touches*.

### llm-provider §6 admits the per-counter null — narrowly

llm-provider §6 types `Response.usage` as a record where "each declared field is a non-negative integer or
`null`," and adds: "the first three (`prompt_tokens`, `completion_tokens`, `total_tokens`) MUST be `null`
together **when the provider does not report usage**." That obligation is *conditioned* — it fires when the
provider reports no usage at all. A provider that reports two sound counters and one garbage one **has**
reported usage, so null-together does not fire, and the per-field `null` the first sentence already permits
is the correct outcome: `{null, 5, 15}`, not `{null, null, null}`.

So the response side needs no new nullability — only a statement that a malformed counter is treated as the
`null` §6 already allows, rather than raised.

### But the guards downstream assume a non-null counter

Everything that reads a counter was written when "record present ⇒ counters are integers" always held.
0100's retrieval half was safe precisely because 0093 had already broken that assumption for retrieval; on
the LLM side it still holds, and this proposal is what breaks it. Left unreconciled, the rule is a paper
rule — a null counter would still reach the dashboard:

- **OTel span (§5.5.3).** `gen_ai.usage.input_tokens` says "Omit when the response's usage **record** is
  null." The record is not null, so an implementation must emit an int-typed attribute sourced from a null
  counter. Its declared mirror `openarmature.llm.usage.prompt_tokens` says "Omit when null" (the *field*),
  so it omits — the spec's own "both emit" pairing breaks, and one of the pair is undefined.
  (`gen_ai.usage.output_tokens` already reads "Omit when null" — the pair is *already* asymmetric; this is
  what makes it bite.)
- **Token-usage histogram (§11.2).** It records "two observations … sourced from the response usage record"
  and skips only "when a call's usage record is **absent**." A present record with a null counter records
  an observation from null.
- **Token-budget instruments (§11.2 metrics / §5.5.15 span).** `token_budget.exceeded` is `true` when
  `usage.prompt_tokens > input_max_tokens` (a null comparison) and its `total` bound sums
  `prompt_tokens + completion_tokens` when the provider omits `total_tokens` (a null addend);
  `token_budget.utilization` records `prompt_tokens / input_max_tokens` (a null division).
- **Langfuse `Generation` (§8.4.3).** It maps the counters to a fixed Langfuse `usage` record
  (`generation.usage.input` / `output` / `total`) — and, unlike the `Embedding` / `Retriever` observations'
  open `usageDetails` map, those rows carry **no** per-counter null guard today. A null counter must be
  omitted from `generation.usage`.

### The typed event, and a premise 0093 relied on

graph-engine §6 types `LlmCompletionEvent.usage` as `record | null`, "may be null when the provider does
not report usage." When **all three** counters are malformed, §6's null-together fires and the *response*
carries a `{null, null, null}` record (the response record is never null). The event must **mirror** that —
a present record of null counters — not a null record, or the response and its own observability event
disagree about the same call. 0093 could leave `LlmCompletionEvent.usage` record-null unreconciled because
"no completion mapping reports 'no usage,' so there is nothing to reconcile." A malformed all-counter
response now reaches that state; this pins the event to mirror the response so the dormant divergence does
not become live.

### Streaming

For a streamed completion, llm-provider §6 sources usage "from the terminal chunk" and defines `raw` as
"the assembled representation of the streamed events (implementation-defined assembly)." The whole case for
*not reporting* rests on the corrupt value surviving on `raw` — but under an implementation-defined
assembly it might not. §6's streaming clause is tightened so the terminal chunk's verbatim usage is
preserved on `raw`, so the transparency guarantee holds for streamed and non-streamed calls alike.

## Proposed change

### llm-provider §6 — the counter rule

A malformed usage counter (a value present on the wire but not a non-negative integer) **MUST** be treated
as **not reported**: that counter is `null`; the other counters stand. It **MUST NOT** raise
`provider_invalid_response` and **MUST NOT** be coerced, clamped, or repaired (a repaired counter is
indistinguishable from a reported one — fabrication, which §6 already forbids for absent figures). The
verbatim value **MUST** remain on `Response.raw`.

§6's "the first three MUST be `null` together when the provider does not report usage" is unchanged: it is
conditioned on no usage being reported, which a partially-malformed record does not satisfy. When **every**
counter is malformed, no usage is reported, and that condition applies as written — the record is
`{null, null, null}`.

### llm-provider §6 — derived `total_tokens`

Where a mapping **derives** `total_tokens` by summing `prompt_tokens + completion_tokens` — the case for a
provider that does not return a total on the wire (§8.2 Anthropic) — and either addend is not reported
(malformed or absent), the derived `total_tokens` is **itself not reported** (`null`). A mapping
**MUST NOT** substitute the surviving addend as the total: a total that omits an unreported half is a
fabricated figure that understates the true count. §8.2's total-derivation clause gains this pointer. A
provider that returns `total_tokens` **on the wire** (§8.1 OpenAI, §8.3 Gemini via `totalTokenCount`) is the
*direct* case instead — a malformed wire total is a malformed counter, nulled by the counter rule above.

### llm-provider §7 — the reservation carve-out

§7 reserves `provider_invalid_response` for "a malformed response that cannot be parsed into the §6 shape."
Since §6 declares a usage counter as "a non-negative integer or `null`," a counter of `"abc"` cannot be
parsed into that shape, so §7 **today mandates the raise this proposal forbids**. The clause is amended to
except a malformed usage counter (which §6 now dispositions as not-reported). Without this the accepted spec
would both require and forbid the raise.

### graph-engine §6 — the event mirrors the response

`LlmCompletionEvent.usage` **MUST** mirror `Response.usage`: a partially-malformed record surfaces as a
present record with the malformed counter(s) `null`; an all-malformed record surfaces as a present record
of null counters (§6 null-together), **not** as a null `usage`. The `record | null` type is unchanged — the
`null` case remains "the provider did not report usage" for mappings that genuinely report none — this only
pins which shape a malformed-counter response takes so the event and the response agree.

### observability — omit a not-reported counter, everywhere it renders

Every LLM usage surface **MUST** treat a null counter as not-emitted, not as a value:

- **§5.5.3** — `gen_ai.usage.input_tokens` / `output_tokens` and their `openarmature.llm.usage.*` mirrors
  are **omitted when their counter is `null`** (per-field), superseding the input-token attribute's current
  "omit when the record is null" (per-record) guard. This aligns the pair — both omit together on a
  not-reported counter — and matches the output-token attribute's existing per-field guard.
- **§11.2** — the token-usage histogram records the input / output observation **only when that counter is
  reported**, extending the LLM branch to the per-counter conditionality the rerank branch already has
  ("only when the rerank usage reports `input_tokens`"). A null counter records no observation for that
  token type.
- **§11.2 metrics / §5.5.15 span** — a token-budget bound whose input counter is not reported is **not evaluated**:
  `token_budget.exceeded` is not set and `token_budget.utilization` records no observation for that bound
  (a comparison or ratio against a null is undefined, not `false` / `0`). The `total` bound follows the
  derived-`total_tokens` rule — if the total is not reported, the total bound is not evaluated.
- **Langfuse `Generation` (§8.4.3)** — a null counter is omitted from the fixed `generation.usage` record
  (its `input` / `output` / `total` fields are individually optional); the §8.4.3 mapping rows gain the
  omit-on-not-reported guard they lack today (the `Embedding` / `Retriever` `usageDetails` omit-on-null is
  the precedent, on a different Langfuse field).

### llm-provider §6 — streaming `raw`

For a streamed call, the assembled `Response.raw` **MUST** preserve the terminal chunk's usage block
verbatim, so a malformed counter nulled on the normalized `Response.usage` remains inspectable on `raw` — the
same guarantee a non-streamed call already has.

## Conformance test impact

**At Accept** — the spec edits and fixtures land with the accept PR:

- **llm-provider** — a malformed `prompt_tokens` beside sound `completion_tokens` / `total_tokens` ⇒ that
  counter `null`, the others reported, the record still present, `message` and `finish_reason` intact, **no
  raise**, verbatim value on `raw`. A second case: **all three** counters malformed ⇒ `{null, null, null}`
  record (§6 null-together), the typed event carrying the same present-record-of-nulls, not a null record.
- **derived total** — an Anthropic-shape mapping (no wire `total_tokens`) with a malformed `input_tokens` ⇒
  `prompt_tokens = null` **and** the derived `total_tokens = null` (not the surviving `completion_tokens`).
- **streaming** — a streamed completion whose terminal chunk carries a malformed usage counter ⇒ counter
  `null` on `Response.usage`, verbatim on the assembled `raw`.
- **observability** — the span omits `gen_ai.usage.input_tokens` (and its mirror) on a null `prompt_tokens`;
  the histogram records no input observation; the token-budget instruments emit nothing for the unreported
  bound. At least one fixture asserts the null counter reaches **none** of the span, metric, or Langfuse
  surfaces — the bypass this proposal closes.

## Versioning

**MINOR bump** (pre-1.0), and it is a **reversal**, not previously-undefined behavior — the point the
retrieval half (0100) could make cleanly and this half cannot.

llm-provider §6 declares each usage counter "a non-negative integer or `null`," and §7 reserves
`provider_invalid_response` for a response "that cannot be parsed into the §6 shape." A strict
implementation composing the two **today MUST raise** on a counter of `"abc"`. From this version it **MUST
NOT**. That is a backwards-incompatible change to a derivable requirement; pre-1.0, a change of this kind may
land in a MINOR bump.

The observability changes are behavioral for observers: the §5.5.3 input-token omit-guard moves from
per-record to per-field, the §11.2 histogram gains per-counter conditionality, and the §11.2 budget
instruments gain a not-evaluated branch. An observer that emitted an attribute or recorded an observation
from a null counter becomes non-conforming. No record shape changes; the `record | null` event type,
0093's no-fabrication rule, and 0097's `document` boundary all stand. Tentative spec version target
deferred to Accept.

## Alternatives considered

1. **Raise `provider_invalid_response` on a malformed counter.** Reject — same grounds as 0100 Alternative
   #1: it discards a sound completion over an accounting figure, and `raw` already preserves the value.
   Here it also contradicts §7's own "cannot be parsed into the §6 shape" reservation once §6 dispositions
   the counter as `null`.
2. **Null the whole `Response.usage` record on any malformed counter.** Reject — it discards the sound
   counters beside the bad one, and it would require making the always-present record nullable, which 0093
   explicitly declined. The per-counter null §6 already permits is the smaller, truthful outcome.
3. **Fix the response but leave the observability guards alone.** Reject — this is the paper-rule failure
   the review of the combined draft exposed: observability renders from the event, and its guards key on the
   *record* being null, so a null counter would still be emitted to the span, summed into the histogram, and
   compared in the budget instruments. A rule an observer routes around is not a rule.
4. **Fold this into 0100.** Reject — 0100 is a clean, low-risk retrieval change (no new state, no guard
   touched); this is a four-section observability reconciliation with a behavioral reversal. Batching them
   would hold the safe change hostage to the risky one and hide the reversal inside a "previously-undefined"
   framing. Splitting keeps each proposal's versioning honest.

## Out of scope

- **retrieval-provider.** Handled by 0100; this proposal does not touch it.
- **The optional cache counters** (`cached_tokens` / `cache_creation_tokens`). §6 already types them as
  independently absent-or-present with their own semantics; a malformed cache counter follows the same
  not-reported rule as the core three (it is `null`, omitted from the observability surfaces that carry it),
  and no fixture beyond the core-counter cases is required.
- **`response_id` / `response_model`.** llm-provider §6 `Response` declares neither; they exist only on the
  typed event and the OTel span, sourced from `raw`. Their malformed-value handling is the same
  event-consistency question retrieval's `response_model` raises, tracked in `docs/open-questions.md`, not
  resolved here.
- **`parsed`.** Governed by `structured_output_invalid` (§7); a schema-violating value raises rather than
  nulling, which 0095's reask loop depends on. Not an ancillary figure.
- **Record shapes.** The `Response.usage` record stays always-present; the `LlmCompletionEvent.usage`
  `record | null` type is unchanged.
