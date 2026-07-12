# 0097: Rerank `document` echo — object-shape contract (general §6 rule; Jina §8.2 realization)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-11
- **Targets:** spec/retrieval-provider/spec.md **§6 ScoredDocument** — generalize the `document`-echo
  contract to object-shaped echoes (echoed *text* or `null`, verbatim object on `raw`), amending the
  "surface verbatim" MUST (§6 `document` row) and the per-result null-dichotomy invariant (§6 "some results
  but not others"); and **§8.2 Jina** — realize that rule for Jina's `document: anyOf[string, TextDoc,
  ImageDoc, null]`, with a value **outside** the union mapped to `provider_invalid_response` (§7).
  Conformance: fixture 019 gains TextDoc, ImageDoc→`null`, and mixed-shape cases (+ a `raw` assertion).
- **Related:** 0078 (Jina wire mapping — introduced the §8.2 `document → document` mapping this refines),
  0060 (rerank protocol — §6 `ScoredDocument.document` contract), 0096 (`raw` verbatim JSON — the echo
  object is preserved nested in the verbatim response there)
- **Supersedes:**

## Summary

`ScoredDocument.document` (§6) is the echoed document **text** (`string | null`). But some providers echo it
as an **object**, not a bare string. Jina's rerank result `document` is `anyOf[string, TextDoc, ImageDoc,
null]` — verified against the live Jina OpenAPI (`https://api.jina.ai/openapi.json`, 2026-07-11: `TextDoc` is
`{"text": str}`, `ImageDoc` is `{"image": str}`) — and the text reranker typically returns the `TextDoc`
object (a bare string is also legal). §6's "surface the provider's echo verbatim" MUST and §8.2's
`document → document` direct mapping only fit the bare-string case: on the real wire an implementation either
type-violates `ScoredDocument.document` with an object, or (the common impl) reads `document` only when it is
a string and **silently drops the echo to `null`** — which fixture 019 (mocking only a bare string) cannot
catch.

This generalizes the §6 echo contract to object shapes — an object echo surfaces its **text content** (a
string-valued `text` key) or `null`, with the verbatim object preserved on `RerankResponse.raw` — and pins
the §8.2 Jina realization (`TextDoc → text`, `ImageDoc`/text-less → `null`, off-union → `provider_invalid_response`).

## Motivation

§6 types `document` as the echoed *text* (`string | null`) and requires implementations to "surface the
provider's echo verbatim when present." For a `TextDoc {"text": "berlin"}` the echoed text is `"berlin"`, so
the intent is already text — but the current MUST wording ("verbatim") and §8.2's `document → document`
mapping assume the echo *is* a string, so neither says how to handle the object shape.

The defect is silent: a mapping that reads `document` only when it is a string passes fixture 019 (which
mocks a bare string) but returns `null` against the live Jina text reranker, which echoes a `TextDoc`. Because
conformance can't distinguish a correct mapping from a bare-string-only one, the gap is a fixture-fidelity +
contract-specification problem, not a §6 / §2 disagreement — surfaced by a Jina rerank implementation against
the live endpoint. The object-echo case is not Jina-specific: any rerank vendor may echo a richer shape, so
the contract belongs in §6, with §8.2 the vendor realization.

## Proposed change

### retrieval-provider §6 — generalize the `document`-echo contract

Amend the `ScoredDocument.document` row and the §6 per-result echo invariant. `document` remains the echoed
document **text** (`string | null`); the echo rule generalizes to object shapes:

- a **string** echo → surfaced verbatim. An empty string `""` is *present* and MUST be surfaced as `""`
  (not folded to `null`).
- an **object** echo → its text content: an object with a **string-valued `text` key** → that string; any
  other object (no string `text`, or a non-text media shape such as an image wrapper) → `null`.
- an **absent** / `null` echo → `null`.
- the **verbatim echo** — whatever its shape — is preserved on `RerankResponse.raw` (0096), nested at
  `results[].document` within the verbatim provider response, so no echo information is lost. A caller that
  needs a non-text echo (e.g. an image) reads it there.

This **amends the "surface verbatim" MUST** to the text-or-null rule above (extracting the text from an
object echo is how "surface the echo" applies to a non-string shape). It **reconciles the per-result
invariant** ("when the provider returns `document` for some results but not others"): `document = null` now
covers both an **omitted** echo and an echo whose shape carries **no text** (e.g. an image), per result,
while a string / text-bearing echo populates. The "MUST NOT fabricate the echo from the input `documents`
list" rule is unchanged.

### retrieval-provider §8.2 — Jina realization

Jina's rerank result `document` is `anyOf[string, TextDoc, ImageDoc, null]` (Jina OpenAPI: `TextDoc =
{"text": str}`, `ImageDoc = {"image": str}`). Apply the §6 rule; this replaces §8.2's prior
`document → document` direct mapping:

- a **`string`** → itself;
- a **`TextDoc`** (object with a string-valued `text` key) → its `text`;
- an **`ImageDoc`** (`{"image": str}`), or any object without a string `text` → `null`;
- **absent** / `null` → `null`.

A `TextDoc` / `ImageDoc` echo is a **documented Jina shape**, so the mapping MUST NOT treat it as malformed.
A `document` value **outside** the `anyOf` — a number, array, boolean, etc. — is a malformed response and maps
to `provider_invalid_response` (§7); the null fallback is scoped to the documented member shapes, not a
catch-all that would swallow wire corruption.

## Conformance test impact

Fixture **019** (`019-rerank-jina-return-documents`) gains three cases alongside the existing bare-string
case B, and — since 019 currently asserts no `raw` — an added `raw` assertion (the harness supports asserting
`raw`, per 0096's retrieval-`raw` fixtures):

- **TextDoc echo** — `return_documents: true`; mocked response echoes `document: {"text": "doc about
  berlin"}` per result. Assert `ScoredDocument.document` is the extracted string (`"doc about berlin"`,
  **not** the object), and `RerankResponse.raw` carries the verbatim `{"text": …}` object nested in
  `results[]`.
- **ImageDoc echo → `null`** — mocked response echoes `document: {"image": "https://…"}`. Assert
  `ScoredDocument.document` is `null` (no text), with the verbatim `{"image": …}` object on `raw` (proving a
  non-text echo maps to `null` rather than raising, and stays recoverable on `raw`).
- **Mixed-shape (per-result variance)** — one response echoing a string, a `TextDoc`, an `ImageDoc`, and an
  absent `document` across four results → `["…", "…", null, null]` per result, exercising the §6 per-result
  invariant so a "read the first result's shape, apply to all" implementation fails.

An off-union `document` (e.g. a number) → `provider_invalid_response` rides the existing §7 error-mapping
coverage; a dedicated malformed-echo case MAY be added at Accept. Numbers / case-names assigned at Accept.

## Versioning

**MINOR bump** (pre-1.0). A behavioral change to the §6 `document`-echo contract (generalized to object
shapes) and the §8.2 Jina mapping. §6's `string | null` type is unchanged and the bare-string case is
unchanged; an implementation that only handled bare-string echoes becomes non-conforming for object echoes
(it was already silently dropping the echo on the live Jina wire). Depends on 0096 for the "verbatim echo on
`raw`" clause (`RerankResponse.raw` carries the verbatim response). Tentative spec version target deferred to
Accept.

## Alternatives considered

1. **Reject non-string echoes as `provider_invalid_response`.** Reject — a `TextDoc` / `ImageDoc` is a
   *documented, expected* Jina response shape (per the OpenAPI `anyOf`), not malformed; §6 types `document`
   as text with a `null` fallback, so a non-text echo maps cleanly to `null` (object on `raw`), not an error.
   (A value *outside* the `anyOf` — number, array — DOES raise; that is the documented-shape-vs-corruption
   line.)
2. **Widen `ScoredDocument.document` to carry the echo object.** Reject — §6 deliberately types the field as
   the echoed *text* (`string | null`) for cross-vendor uniformity; the verbatim object already has a home on
   `RerankResponse.raw` (0096). Widening the field would fork its type per vendor and duplicate `raw`.
3. **Keep the rule Jina-specific in §8.2 (no §6 change).** Reject — the object-echo case recurs for any
   rerank vendor with a rich `document` field; §6 is the reusable home (amend once), §8.2 the vendor
   realization. A §8.2-only special case would leave the §6 MUST contradicting the mapping and force every
   future vendor to re-derive it.
4. **Leave §8.2 as `document → document`.** Reject — it under-models the real Jina wire; a conforming impl
   either type-violates `ScoredDocument.document` with an object or silently drops the echo, and conformance
   can't catch either. This is the exact defect the proposal fixes.

## Out of scope

- **Image documents as rerank *input*** — this proposal covers `ImageDoc` only as an *echo* shape (→ `null`
  document); reranking image documents is a separate future concern.
- **Other vendors' current mappings** — Cohere `/v2/rerank` has no `return_documents` (§8.4, silent no-op)
  and TEI uses `text` (§8.1); their mappings are unaffected, though the generalized §6 rule now governs them
  if they ever echo an object shape.
