# 0093: Nullable Provider Usage Records (embedding + rerank)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-30
- **Targets:** spec/retrieval-provider/spec.md — **§4** (`EmbeddingResponse.usage` → **"an `EmbeddingUsage`
  record, or null when the provider reports no usage"**; `EmbeddingUsage.input_tokens` stays `Int`, the
  "always reported" phrasing dropped — its presence follows the record's); **§6** (`RerankResponse.usage`
  → **"a `RerankUsage` record, or null …"**; the record's `input_tokens` / `search_units` stay
  `Int or null` for partial usage — **and reconcile the RerankUsage note** that "a `RerankUsage` with both
  fields null is valid and represents the 'no billing surface' case": that case is now `usage = null`, not
  an all-null record); **§2** (the `EmbeddingResponse` / `RerankResponse` concept lines list "usage
  information" unconditionally — qualify it, matching how `response_id` is "(when present)"); **§8.1** (the
  TEI `/embed` + `/rerank` mapping text pins `usage = null` explicitly — TEI returns no usage object; the
  outcome is currently unstated in the mapping a reader implements from, unlike §8.4 Cohere). And
  spec/observability/spec.md — **§5.5.8** (embedding OTel `gen_ai.usage.input_tokens` → **conditionally
  emitted**, present only when a usage record is reported), **§8.4.5** (Langfuse
  `embedding.usageDetails.input` → when a usage record is reported), **§5.5.13** (fix the parenthetical
  asserting "the embedding span, where `input_tokens` is always present" **and** phrase the rerank guard
  record-aware) and **§8.4.7** (phrase the rerank `usageDetails` guard record-aware) — so the rerank
  observability guards read consistently with §8.4.5's record-aware wording. **No change to graph-engine §6
  or observability §11** — the typed events (`EmbeddingEvent.usage` / `RerankEvent.usage`) and the GenAI
  token metric already model no-usage as a null record; this proposal brings the *response* types and the
  observability *guards* into line. Plus conformance-fixture updates (embedding + rerank no-usage). No hard
  sequencing dependency on 0092 — the embedding no-usage case is already covered by the pre-existing TEI
  `/embed` fixture **017**; 0092 has shipped, so its TEI `/embed` fixture **038** is updated too.
- **Related:** 0059 (created `EmbeddingUsage` with "always reported" — the over-assumption this corrects),
  0060 (created `RerankUsage` with nullable fields **and** the record-null typed-event / conditional-
  emission posture this generalizes to responses), 0077 (TEI `/embed` + `/rerank` return no usage object —
  the mappings that break the assumption; fixture 017 already sidesteps usage), 0092 (its TEI `/embed`
  chunk-and-stitch fixture 038 also sidesteps usage; the contradiction was consciously noted at its
  accept), 0067 (GenAI metrics — the token-usage record, already null-usage-aware)
- **Supersedes:**

## Summary

A reconciliation that gives OA **one uniform model for "the provider reported no token usage"** across
both retrieval-provider response types, matching what the typed events and metrics already do.

The spec is inconsistent today about representing "no usage":

- **Typed events** (`EmbeddingEvent.usage`, `RerankEvent.usage`, graph-engine §6) and the **§11 GenAI
  metric** model it as a **null record** — `usage` may be null when the provider reports none.
- **`RerankResponse.usage`** (§6) is instead **always a record** with individually-nullable fields, and §6
  even blesses a *both-fields-null* record as the "no billing surface" case — so a provider that reports
  nothing (TEI `/rerank`) is forced into a *fabricated empty record* `{input_tokens: null, search_units: null}`.
- **`EmbeddingResponse.usage`** (§4) is worse: not only always a record, but `EmbeddingUsage.input_tokens`
  is declared "**Int. Always reported**" — which TEI `/embed` (a bare vector array, no usage object)
  **cannot satisfy at all**. The pre-existing TEI `/embed` fixture (017) already sidesteps this — it
  asserts no usage at all — and 0092's TEI `/embed` fixture (038) does the same; the contradiction was
  consciously noted when 0092 was accepted.

This proposal makes both **`EmbeddingResponse.usage`** and **`RerankResponse.usage`** nullable — a usage
record when the provider reports one, `null` when it doesn't — so all four surfaces (both responses, both
events) and the metric agree: **no usage ⇒ `usage = null`**. The events and metric need no change; they
were already right. Rerank additionally **keeps** its per-field nullability inside the record, because it
genuinely needs it (see below).

## Motivation

**Embedding is broken; rerank is inelegant.** TEI `/embed` returns no usage, so `input_tokens` "always
reported" is un-satisfiable — a live contradiction. TEI `/rerank` likewise returns no usage, forcing a
fabricated empty `RerankUsage` today. Both are the same underlying gap: the response types assume a usage
record always exists.

**The events already got it right.** graph-engine §6 defines every typed-event `usage` field
(`LlmCompletionEvent`, `EmbeddingEvent`, `RerankEvent`) as "record | null … may be null when the provider
does not report usage," and §11 records no token observation "when a call's usage record is absent." The
response types are the outliers. Aligning them is the minimal, most-consistent fix — and it requires **no
change** to the already-correct events / metric.

**Why record-null for the *presence* of usage, but field-null retained inside rerank.** The right model
follows the shape of each usage record:

- **Embedding usage has one field** (`input_tokens`). A provider either reports it or reports nothing —
  all-or-nothing. So "no usage" is genuinely "no record": **pure record-null**. Field-nullability would
  force fabricating an empty record the provider never sent (the same "don't invent data" principle OA
  applies to echoes).
- **Rerank usage has two fields** (`input_tokens`, `search_units`) that vary **independently**: Cohere
  reports `search_units` but not `input_tokens`; Voyage/Jina report `input_tokens` but not `search_units`.
  That *partial* case needs the **record present** with some fields null — so rerank keeps field-null.
  Rerank's *no-usage-at-all* case (TEI `/rerank`) is the one that becomes `usage = null`.

So both responses end at **`usage` is `record | null`**; rerank's record additionally has nullable fields
because it carries more than one. The models differ only where the data shapes differ.

## Proposed change

### retrieval-provider §4 — `EmbeddingResponse.usage`

`usage` becomes **"an `EmbeddingUsage` record, or `null` when the provider reports no usage"** (e.g. TEI
`/embed`, which returns a bare vector array with no usage object). `EmbeddingUsage.input_tokens` remains
`Int` but the "Always reported" phrasing is dropped — `input_tokens` is present exactly when the usage
record is. Implementations MUST populate `usage` when the provider returns a usage record and MUST NOT
fabricate one (an empty record, a zero, or a client-side token estimate) when it does not.

### retrieval-provider §6 — `RerankResponse.usage`

`usage` becomes **"a `RerankUsage` record, or `null` when the provider reports no usage"** (e.g. TEI
`/rerank`). The record's `input_tokens` / `search_units` stay `Int or null` — a provider that reports
*some* usage (e.g. Cohere's `search_units` without `input_tokens`) yields a record with the reported
field(s) set and the rest null; a provider that reports *no* usage yields `usage = null`. The existing §6
note that **"a `RerankUsage` with both fields null is valid and represents the 'provider reports no
billing surface' case"** is reconciled: the no-usage case is now `usage = null`; a `RerankUsage` record is
present only when the provider surfaces at least one figure. Same populate/don't-fabricate rule as §4.

### retrieval-provider §2 — concept lines

The `EmbeddingResponse` and `RerankResponse` concept definitions currently list "usage information" as an
unconditional field while qualifying the request identifier as "(when present)". Qualify usage the same
way — it is present only when the provider reports it — so §2 matches the now-nullable §4 / §6 field
tables.

### retrieval-provider §8.1 — TEI usage is `null`

The TEI `/embed` and `/rerank` mappings pin their usage outcome explicitly: TEI returns no usage object on
either endpoint, so the mapping produces **`usage = null`** (it MUST NOT fabricate a usage record or a
zero — the §4 / §6 rule). Today §8.1 is silent on usage, leaving the behavior pinned only in fixtures;
this states it in the mapping text a reader implements from, as §8.4 Cohere already documents its usage
sourcing.

### observability — conditional / record-aware emission

- **§5.5.8 (OTel embedding span).** `gen_ai.usage.input_tokens` becomes **conditionally emitted** —
  present only when a usage record is reported, omitted otherwise (the §5.5.3.1 / 0047 convention the
  rerank span §5.5.13 already uses).
- **§8.4.5 (Langfuse embedding observation).** `embedding.usageDetails.input` is populated only when a
  usage record is reported.
- **§5.5.13 (OTel rerank span).** Correct the parenthetical contrasting rerank with "the embedding span
  (where `input_tokens` is always present)" — after this change both spans emit usage conditionally — and
  phrase the guard record-aware ("when a usage record is reported and its `input_tokens` is non-null"),
  so `usage = null` is covered explicitly rather than by implicit field-through-null-record reasoning.
- **§8.4.7 (Langfuse rerank observation).** Phrase the `retriever.usageDetails.*` guards record-aware, the
  same way, for consistency with §8.4.5.
- **No change to §11 or graph-engine §6** — already null-usage-aware.

## Conformance test impact

- **Embedding no-usage.** The pre-existing TEI `/embed` fixture **017** (which already asserts no usage) is
  updated to assert `usage: null`; 0092's TEI `/embed` fixture **038** gets the same update. A new OTel
  embedding fixture pins the conditional omission (a no-usage embed call emits **no**
  `gen_ai.usage.input_tokens` attribute), and a Langfuse embedding fixture pins `usageDetails.input`
  omitted.
- **Rerank no-usage.** A TEI `/rerank` fixture asserts `usage: null` (exercising the record-null path
  through the §5.5.13 / §8.4.7 rerank guards). The existing rerank fixtures that report *partial* usage
  (e.g. Cohere `search_units`-only, Jina `input_tokens`-only) stay valid — a record-present-with-null-fields
  result is still well-formed under "record | null."
- **Positive fixtures unaffected.** The OpenAI / Jina / Cohere embedding fixtures and the observability
  embedding-usage fixtures that assert an integer `input_tokens` continue to pass (those providers report
  usage). Numbers assigned at Accept.

## Versioning

**MINOR bump** (pre-1.0). Both response `usage` fields widen to nullable and the embedding observability
emission becomes conditional — a public-type + conformance change, hence its own proposal. Additive for
the hosted mappings (they report usage and are unchanged); it **unblocks** the TEI `/embed` mapping (the
prior contract made it non-conformant on usage) and removes the fabricated-empty-record for TEI
`/rerank`. Tentative spec version target deferred to Accept. No hard sequencing dependency — fixture 017
(pre-existing) covers the embedding no-usage case independently of 0092.

## Alternatives considered

1. **Field-null for embedding (make `input_tokens` nullable, keep the record always present).** Reject —
   embedding usage is single-field all-or-nothing, so "no usage" is genuinely "no record"; a
   record-with-null-`input_tokens` is a fabricated object the provider never sent, and it would clash with
   the record-null model the events (graph-engine §6) and metric (§11) already use (forcing changes there
   and two competing encodings of "no usage").
2. **Fix embedding only; leave rerank's fabricated empty record.** Reject — it's the same one-concept
   change ("provider reported no usage ⇒ `usage = null`"), the rerank half is tiny (one field → nullable
   plus the both-null-record note reconciliation; everything downstream already handles it), and doing both
   delivers the cross-OA uniformity in one proposal instead of a near-identical follow-on.
3. **Pure record-null for rerank too (drop the record's field-nullability).** Reject — Cohere `/v2/rerank`
   reports `search_units` without `input_tokens`, so the record must exist to carry `search_units` with
   `input_tokens` null; collapsing that to `usage = null` would lose the reported `search_units`. Rerank
   needs both record-null (nothing) and field-null (partial).
4. **Require TEI to synthesize `input_tokens` (client-side tokenization) or report `0`.** Reject —
   fabricating a count the provider never returned (and `0` asserts "zero billed," a false claim). `null`
   is the truthful "unknown."
5. **Do nothing.** Reject — embedding is a live contradiction; rerank silently fabricates an empty record.

## Open questions

None blocking — surfaced and resolved during drafting:

- **Record-null vs. field-null.** RESOLVED: record-null for whether a usage record exists (both
  responses), field-null retained *inside* the rerank record for its independently-varying fields. The
  model follows each type's shape (Motivation).
- **LLM completion usage.** Out of scope — LLM completions always carry a usage record; `LlmCompletionEvent.usage`
  is already record-null but no completion mapping reports "no usage," so there is nothing to reconcile.

## Out of scope

- **LLM completion `Response.usage`** — always present in practice; not touched.
- **The rerank record's field-level nullability** — unchanged (`input_tokens` / `search_units` stay
  `Int or null`); this proposal only makes the *record* itself nullable (and reconciles the both-null-record
  note).
- **`output_tokens` for embedding** — there are none.
- **A separate "usage absent" flag** — the `null` record is sufficient; no extra signal.
