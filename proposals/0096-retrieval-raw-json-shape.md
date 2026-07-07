# 0096: Retrieval `raw` — Verbatim Deserialized JSON of Any Top-Level Shape

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-04
- **Targets:** spec/retrieval-provider/spec.md **§4** (`EmbeddingResponse.raw`) + **§6** (`RerankResponse.raw`)
  — widen the `raw` type from `dict[str, Any]` (TypeScript `Record<string, unknown>`) to
  **`dict[str, Any] | list[Any]`** (TS `Record<string, unknown> | unknown[]`), so a bare-array provider
  response is carried **verbatim** as its deserialized list instead of being forced into a synthetic
  object. Restate the field's contract as "the verbatim deserialized JSON of the successful response — an
  object or an array." No behavioral change for object-shaped single-request mappings (§8.2 Jina, §8.3
  OpenAI-compatible, §8.4 Cohere); reconcile the "Parallel to llm-provider §6 `Response.raw`" note. Also
  **§8** *Batch chunking* + **§8.1** — add the `raw` stitch rule for a multi-request (chunk-and-stitch) call
  (the list of per-request responses, in order) alongside the existing vectors / usage / response_id rules,
  and pin the array-response single-vs-chunked disambiguation.
- **Related:** 0059 (created `EmbeddingResponse.raw`), 0060 (`RerankResponse.raw`), 0077 (TEI wire mapping —
  surfaced the conflict: TEI `/embed` returns `[[float, …], …]`, `/rerank` returns `[{index, score, text?}]`;
  also the mandatory rerank chunk-and-stitch), 0092 (the general §8 batch-chunking rule this extends with the
  `raw` stitch convention)
- **Supersedes:**

## Summary

`raw` (retrieval-provider §4 / §6) exists to give callers **verbatim** access to what the provider actually
returned — the *transparency over abstraction* the §6 row already cites (charter §3.1 principle 8).
Its type is pinned to `dict[str, Any]`, an object shape inherited from llm-provider's `Response.raw`
(`raw` predates any §8 wire mapping; chat/completion responses are always JSON objects). The TEI wire mapping (§8.1) returns **bare
JSON arrays** — `/embed` a list of vector lists, `/rerank` a list of result objects — whose verbatim
deserialized JSON is a **list**, not a dict. The two clauses ("verbatim deserialized JSON" and
"`dict[str, Any]`") conflict for any array-response mapping, forcing an implementation to either violate the
type or wrap the array under a synthetic key it invents — the exact abstraction `raw` exists to avoid.

This widens `raw` to `dict[str, Any] | list[Any]` so it is the verbatim deserialized JSON whether the
provider response is an **object or an array**. It also pins what `raw` is for a **chunked** call (§8): the
**list of the per-request verbatim responses**, so nothing the provider returned across the chunk requests
is lost — the normalized fields (`response_id`, `usage`, `vectors` / `results`) stay ergonomic summaries,
and `raw` carries the complete record. Object-shaped single-request mappings are unaffected.

## Motivation

§4 / §6 say `raw` is "the parsed provider response, as a language-idiomatic representation of deserialized
JSON (Python: `dict[str, Any]`) … populated on every successful return," and §6 grounds it in
*transparency over abstraction* — callers keep access to provider-specific fields the normalized shape
doesn't surface. That promise is **verbatim**: what `raw` holds should be exactly what the provider sent,
deserialized, with nothing added or reshaped.

The `dict[str, Any]` type was inherited from llm-provider's `Response.raw` — 0059 / 0060 created `raw`
before any §8 wire mapping existed, and chat/completion responses are always JSON objects. TEI (§8.1) is
the first mapping whose wire response is a **top-level array**. For such a response:

- Honoring `dict[str, Any]` means **inventing a wrapper key** — an OA-authored object such as
  `{"data": <the array>}` — which is precisely the abstraction `raw` promises to not impose. A caller
  reaching into `raw` gets OA's key, not the provider's shape.
- Honoring **verbatim** means `raw` is the deserialized list — which the current type forbids.

The two can't both hold. The fix is to let `raw`'s type follow the response's actual top-level shape.
Object-shaped mappings (Jina §8.2, OpenAI-compatible §8.3, Cohere §8.4) return objects, so their
single-request `raw` is unchanged (their chunked `raw` becomes a list of per-request objects, per §8 below).
The typed events (`EmbeddingEvent` / `RerankEvent`, graph-engine §6) do **not** carry `raw`, so there is no
event-surface ripple.

## Proposed change

### retrieval-provider §4 / §6 — widen `raw`

Change the `raw` type on `EmbeddingResponse` (§4) and `RerankResponse` (§6) from `dict[str, Any]`
(TS `Record<string, unknown>`) to **`dict[str, Any] | list[Any]`** (TS `Record<string, unknown> | unknown[]`).
Restate the contract: for a call that issues a **single** provider request, `raw` MUST be the **verbatim
deserialized JSON of that response — an object (`dict`) or an array (`list`)**, matching its top-level shape
(an array for bare-array responses like TEI §8.1); an implementation MUST NOT wrap, rename, or reshape it to
fit a container type. When a call issues **multiple** requests (chunk-and-stitch), `raw` is the list of
those per-request responses — see the §8 rule below. `raw`'s purpose (transparency over abstraction)
requires the provider's own shape either way.

### Reconcile the llm-provider parallel

The §4 / §6 note "Parallel to llm-provider §6 `Response.raw`" is retained but qualified: the parallel is in
**intent** (verbatim provider response), not in type. llm-provider `Response.raw` stays `dict[str, Any]` —
chat/completion responses are always JSON objects, with no bare-array wire — so the widening is
**retrieval-provider-scoped**. (Add a one-line note to that effect at both §4 / §6 and leave llm-provider
untouched.)

### retrieval-provider §8 (Batch chunking) + §8.1 — `raw` for a multi-request call

The §8 *Batch chunking* rule (embedding) and §8.1's mandatory TEI rerank chunk-and-stitch already pin how
each stitched field is assembled from the per-chunk responses — §8 embedding: `vectors` concatenated,
`usage` summed when the provider reports it (else `null`, per 0093), `response_id` = the first chunk's id;
§8.1 rerank: results re-based to absolute indices, concatenated, and re-sorted by score (with `top_k`
honored). `raw` needs the same treatment, and — per its transparency purpose — it keeps **all** of the
per-chunk responses:

- A call that issues a **single request**: `raw` is that request's verbatim response (an object or an array,
  per §4 / §6 above).
- A call that issues **multiple requests** (chunk-and-stitch): `raw` is the **list of the per-request
  verbatim responses, in request order** (a `list`, admitted by the widened union). Every chunk's response is
  present verbatim — for providers whose responses carry ids / usage / extra fields (OpenAI-compatible,
  Cohere) that means every chunk's `response_id`, usage, and provider-specific field is retained; for a
  bare-array provider (TEI) each entry is that chunk's verbatim array. The normalized top-level fields
  (`response_id`, `usage`, `vectors` / `results`) remain the §8 ergonomic summaries, with `raw` the complete
  record. This is a **new stitch rule added to §8 alongside the existing ones; it changes none of them.** A
  chunked `raw` presupposes **every** request succeeded — a chunk failure fails the whole call (§7 / §9),
  yielding no `EmbeddingResponse` / `RerankResponse` and therefore no `raw`.

**`raw`'s shape depends on whether the call chunked; disambiguation.** Because a chunked `raw` is a list of
per-request responses, its container shape depends on whether the call chunk-and-stitched. For an
**object-response** mapping this is self-evident from the type (`dict` = single response, a `list` of objects
= chunked). For a **bare-array** mapping (TEI, §8.1) both a single response and a chunked `raw` are a `list`,
so the type alone does not disambiguate; the discriminator is whether the input exceeded the mapping's
per-call cap (the chunk trigger — caps recorded in `docs/compatibility.md`), which the caller controls.
Callers that index into `raw` structurally MUST account for this input-size dependence.

For TEI `/embed` the chunked `raw` is largely redundant — the bare array *is* the vectors, surfaced fully
stitched in `vectors`. For TEI `/rerank` it is **not** redundant: `raw` carries each chunk's verbatim
`[{index, score, text?}]` with **chunk-relative** indices in the provider's order, whereas `results`
re-bases indices to absolute positions and re-sorts by score — so `raw` preserves index / order information
`results` deliberately reshapes away.

## Conformance test impact

- **TEI single-request `raw` is the verbatim array.** A TEI fixture asserts `EmbeddingResponse.raw` is the
  deserialized bare array (`[[…], […]]`) and `RerankResponse.raw` the deserialized result-list
  (`[{index, score, …}, …]`) — **not** an OA-wrapped object. (The single-request TEI wire fixtures — 017
  embed, 014 rerank within-batch — don't assert `raw`; this adds the assertion.)
- **Chunk-and-stitch `raw` is the list of per-request responses.** The two existing TEI chunk-and-stitch
  fixtures — **038** (`038-embed-tei-chunk-and-stitch`) and **015** (`015-rerank-tei-chunk-and-stitch`) —
  gain a `raw` assertion: `raw` is the list of per-chunk verbatim responses, one entry per request issued in
  order, **not** a single stitched array nor a first-chunk-only value. For embed, chunked `raw` is a list of
  the per-chunk arrays — two chunks of `[[…], …]` give `raw = [ [[…], …], [[…], …] ]`, one level deeper than a
  single-request `raw`, **not** a flattened single array. An object-response chunked case (OpenAI-compatible
  / Cohere over-cap embed) asserts `raw` is the list of per-chunk objects.
- **Object-shaped single-request mappings unaffected.** Fixtures for Jina / OpenAI-compatible / Cohere that
  assert a single-request `raw` as an object continue to pass — the widened union still admits `dict`.

Numbers assigned at Accept.

## Versioning

**MINOR bump** (pre-1.0). A public-type widening on two response fields, plus a new `raw` stitch rule added
to the §8 *Batch chunking* contract (0092) for multi-request calls — previously-undefined behavior, so
additive, and it changes none of §8's existing normalized-field stitch rules. Additive for object-shaped
single-request mappings (the union still admits `dict`, so existing callers and fixtures are unaffected); it
**unblocks** the array-response mappings, whose verbatim `raw` the prior `dict`-only type could not express,
and closes the previously-undefined chunked-`raw` case. Scoped to retrieval-provider (llm-provider
`Response.raw` unchanged). Tentative spec version target deferred to Accept.

## Alternatives considered

1. **Bless the wrap** — keep `raw: dict[str, Any]` and standardize an array-response wrapping key (e.g.
   `data` / `embeddings` / `results`) across mappings for cross-impl uniformity. Reject — the standardized
   synthetic key is exactly the OA-invented abstraction `raw` exists to avoid (charter §3.1 principle 8); a
   caller's `raw` access would return OA's wrapper, not the provider's shape. It keeps the type stable at
   the cost of the field's entire purpose.
2. **Widen to the fully-general JSON value** (`dict | list | str | int | float | bool | None`). Reject for
   now — provider responses for these endpoints are always an object or an array, so the two-container
   widening covers every specced mapping without diluting the type to "any". A top-level scalar response, if
   one ever arises, would be a further tiny widening at that point.
3. **First chunk's response only for a chunked `raw`** (parallel to the §8 `response_id` = first-chunk rule).
   Reject — it hides chunks 2..N's responses (and every id, usage figure, and provider-specific field they
   carry), violating `raw`'s transparency purpose. `raw` is the one field designed to hide nothing, so a
   chunked `raw` carries **all** per-request responses; the *normalized* fields (`response_id` = first,
   `usage` = summed, `vectors` / `results` = concatenated) remain the ergonomic summaries, with `raw` the
   complete record. (See §8 change above.)
4. **Stitch a chunked `raw` like `vectors` — one concatenated shape** (concatenate the per-chunk responses
   into a single value, so `raw` has the same shape whether or not the call chunked). Reject — it only works
   for array responses; concatenating *object* responses would have to pick or merge each chunk's `id` /
   `usage` / metadata (the reshape #1 rejects), and even for arrays it discards the per-request boundaries
   `raw` exists to preserve — including the chunk-relative indices and provider order TEI `/rerank`'s `raw`
   carries and `results` reshapes away (the §8.1 note above). Shape-stability isn't worth erasing the
   transparency `raw` is for.
5. **Leave `raw` an unspecified implementation detail** (no spec change, single- or multi-request). Reject —
   a caller's `raw` shape would then differ by mapping and by implementation, a cross-impl-visible contract
   divergence. The single-request shape and the chunked-list shape are both genuine §4 / §6 / §8 defects and
   must be pinned.

## Open questions

None blocking. Settled during drafting: two-container (`dict | list`) vs. fully-general JSON-value typing
(Alternatives #2 — two containers now); first-chunk vs. all-chunks for a chunked `raw` (Alternatives #3 —
all chunks, since `raw` hides nothing); and the array-response single-vs-chunked disambiguation (the §8.1
convention above — a chunked `raw` is the list of per-request responses).

## Out of scope

- **llm-provider `Response.raw`** — stays `dict[str, Any]`; chat/completion responses are always JSON
  objects, with no bare-array wire.
- **The typed events** (`EmbeddingEvent` / `RerankEvent`) — do not carry `raw`; no ripple.
- **A standardized wrapping key** (Alternative 1) — rejected, not deferred.
