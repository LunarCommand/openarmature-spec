# 0106: §8.3 base64 embedding output-encoding — decode support

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-23
- **Ships as:** _assigned at acceptance (MINOR)_
- **Targets:** spec/retrieval-provider/spec.md **§8.3** (*OpenAI-compatible embeddings* — replace the deferred
  `encoding_format` note with a **shape-driven decode** contract for `data[].embedding`, so a base64 response is
  decoded to float vectors rather than breaking the consumer). Conformance: new §8.3 fixtures for the base64
  round-trip and the malformed-base64 boundary.
- **Related:** 0079 (introduced the §8.3 OpenAI-compatible embedding mapping), 0099 (purged the same
  advertised-but-broken knob shape from §8.4 Cohere and surfaced this one as an open question), 0105 (deferred
  `encoding_format` as the "output-encoding scalar"; this resolves that slice), and §6 *Extras pass-through*
  (`encoding_format` stays an ordinary unmanaged extras key under this design)
- **Supersedes:**

## Summary

§8.3 says the mapping "does not send `encoding_format` by default (OpenAI's wire default is `"float"`);
`"base64"` rides the extras-pass-through bag." But the mapping's response consumer reads `data[].embedding` as
float vectors, so when a caller actually sets `encoding_format: "base64"` the provider returns each embedding as
a **base64 string**, which the consumer cannot read as a vector — it blows §4's dimensionality invariants and
fails the call `provider_invalid_response`. The advertised knob cannot work. This is the same false-promise
shape 0099 removed from §8.4, left unpinned in §8.3 and explicitly deferred by 0105.

This proposal makes the knob real by decoding the base64 response:

> **The §8.3 consumer decodes `data[].embedding` by wire shape.** A JSON array of numbers is the float vector
> verbatim (today's behavior). A **base64 string** is decoded as a base64-encoded array of **little-endian
> IEEE-754 single-precision (float32)** values, yielding the same float vector. Both encodings are supported and
> produce identical vectors; §4's invariants apply to the decoded vectors. A base64 value that is not valid
> base64, or whose decoded byte length is not a whole multiple of 4, is a malformed response
> (`provider_invalid_response`, §7), with the verbatim provider response preserved on `raw`. Because the consumer
> keys on the **response shape**, not the request parameter, `encoding_format` stays an **unmanaged** extras key
> and the wire default stays `"float"`.

## Motivation

### The gap

`encoding_format: "base64"` is a real OpenAI `/v1/embeddings` option: instead of returning each embedding as a
JSON array of numbers, the provider returns it as a base64 string that encodes the vector's float32 values as
raw little-endian bytes. It is a **wire-transport** choice only — the decoded vector is identical to the float
encoding — and it is meaningfully more compact on the wire (the OpenAI SDKs request it and decode it for exactly
this reason). §8.3 advertises that a caller may reach it through the extras bag, which is true at the request
layer: `encoding_format` is undeclared, so it forwards untouched per §6.

The problem is the **response** layer. The §8.3 consumer assumes `data[].embedding` is a JSON number array. A
base64 string is not, so the consumer either fails to read it or reads garbage, and the call dies
`provider_invalid_response` (§4 vector invariants). The knob is advertised but structurally cannot work — the
caller who takes §8.3 at its word gets a broken call. 0105 deferred this as the "output-encoding scalar"; this
proposal is that work.

### Why decode rather than reject

The alternatives 0105's open question named were: **reject** a base64 request pre-send, **stop advertising** the
knob, or **decode** the response. Decoding is the only one that keeps the advertised capability. Because base64
is a pure transport encoding of the same vector, decoding it is well-defined and language-agnostic (base64 →
bytes → little-endian float32 array), and it costs nothing on the float path — the consumer branches on the
response shape. Rejecting or un-advertising would remove a working, useful efficiency knob for no benefit.

### Why the wire default stays `"float"`

§8.3 is the **OpenAI-compatible** mapping — it targets vLLM, LocalAI, Together, TEI's OpenAI endpoint, and other
compatible servers, not only OpenAI. base64 `encoding_format` support across that ecosystem is uneven, so
requesting base64 by default would bet every caller's happy path on a parameter some backends do not implement.
Keeping `"float"` as the default (the mapping continues to send no `encoding_format`) is the ecosystem-safe
choice: base64 is a working **opt-in** for callers whose backend supports it, and existing callers see no change
to the wire or to `raw`. (Adopting base64 by default for efficiency is a separate decision that should follow a
survey of compatible-backend support — see *Open questions*.)

## Proposal

### 1. §8.3 — shape-driven decode of `data[].embedding`

Replace §8.3's parenthetical deferral note (the one declaring `encoding_format` a "deferred question" and an
unmanaged extras key that would break the consumer) with the decode contract:

- The mapping still does **not** send `encoding_format` by default; the wire default is OpenAI's `"float"`. A
  caller **MAY** set `encoding_format: "base64"` through the extras-pass-through bag (§6) to request the compact
  base64 encoding; it forwards to the wire untouched.
- The response consumer decodes each `data[].embedding` **by its wire shape**:
  - a **JSON array of numbers** is the float vector verbatim (unchanged);
  - a **base64 string** is decoded as a base64-encoded array of **little-endian IEEE-754 single-precision
    (float32)** values: base64-decode to bytes, then read the bytes as consecutive 4-byte little-endian float32
    values in order. The resulting floats, in order, are the vector; the float count is the vector's
    dimensionality.
  - any **other shape** — `null`, a number, a boolean, an object, or an array containing non-numbers — is a
    malformed response → `provider_invalid_response` (§7). The shape dispatch is **exhaustive**: the two arms
    above are the only accepted shapes (this mirrors 0097's exhaustive echo-shape dispatch, which the malformed
    boundary below cites as its parallel).
- **Both encodings yield the same vector** — the float32 values the provider computed (the float encoding
  serializes them as JSON numbers, base64 as raw little-endian float32 bytes). §4's cross-impl invariants (one
  vector per input, input order, uniform dimensionality, `dimensions` = inner length) apply to the **decoded**
  vectors, exactly as for the float path.
- `encoding_format` is therefore an **unmanaged** extras key (not a §6 *Managed-field collision* key): the
  consumer keys on the response shape, not on the request parameter, so a caller-supplied `encoding_format` never
  breaks the consumer and needs no merge/reject handling. This is the distinguishing line from 0105's
  managed-field keys — those are read-back dependencies the mapping must control; `encoding_format` is not,
  because the consumer is shape-robust.

### 2. Malformed base64 → `provider_invalid_response`

A base64 `data[].embedding` value that cannot be decoded to a whole float32 vector is a malformed response:

- the string is **not valid base64**, or
- its decoded **byte length is not a whole multiple of 4** (so it does not partition into float32 values).

In either case the mapping raises `provider_invalid_response` (§7), fail-loud — it MUST NOT return a truncated
or padded vector — and preserves the **verbatim (undecoded)** provider response on `raw` (the general §7
*malformed response* posture; consistent with §4 `raw`). This is a **payload** corruption boundary, parallel to
0097's non-object rerank echo raising rather than nulling.

### 3. `raw` is unchanged (verbatim)

`raw` carries the verbatim deserialized provider response per §4. When base64 is on the wire, `data[].embedding`
on `raw` is the **base64 string** as the provider sent it; the decoded floats live on `vectors`. The mapping
MUST NOT rewrite `raw`'s embeddings to the decoded form. (This mirrors 0097: the normalized surface is decoded /
re-shaped, `raw` stays byte-faithful.) Base64 also composes with §8 *Batch chunking*: an over-cap base64 call
decodes each per-chunk response's embeddings independently by shape, and `raw` is the list of the per-request
responses (§8) with their base64 strings preserved verbatim.

### 4. Conformance

New §8.3 fixtures (the OpenAI-compatible `mapping: openai` dialect, fixtures 023–027 / 043):

- **base64 round-trip** — `embed(config={extras: {encoding_format: "base64"}})`. The wire request carries
  `encoding_format: "base64"`; the mock response returns `data[].embedding` as base64 strings encoding
  exactly-representable float32 vectors. Asserts the decoded `vectors` equal the intended floats, §4 invariants
  hold on the decoded vectors, and `raw.data[].embedding` retains the **base64 strings** verbatim (decoded on
  `vectors`, not on `raw`).
- **malformed embedding** — a base64 `data[].embedding` string whose decoded byte length is not a multiple of 4,
  and a second case pinning the exhaustive-dispatch arm (a `data[].embedding` of a non-conforming shape, e.g. an
  object or `null`). Each asserts `provider_invalid_response` (§7), no vectors returned, verbatim value preserved
  on `raw`.

The existing float-path round-trip (fixture 023) already pins the JSON-array branch, unchanged.

## Versioning

**MINOR** (whole-spec SemVer). Behavioral for the base64 path only: a base64 `encoding_format` call that
previously failed `provider_invalid_response` now succeeds and returns decoded float vectors. That prior
behavior was a broken advertised knob (undefined-in-practice), so this is a correction that **adds** working
behavior, not a change to a working contract. The float path, the wire default, `raw`, and every other §8.3
surface are unchanged; no regression for existing callers.

## Open questions

- **Should the mapping request base64 by default for wire efficiency?** This proposal keeps `"float"` as the
  default because §8.3 spans the OpenAI-compatible ecosystem and base64 support is uneven there. Defaulting to
  base64 (as the OpenAI SDKs do) would shrink the wire ~2× for embeddings but change `raw` (base64 blobs) for
  every caller and risk compatible backends that do not implement it. A future proposal could adopt base64 by
  default after a `docs/compatibility.md` survey of compatible-backend support; the decode contract here is the
  prerequisite either way.
- **Output-encoding knobs on other §8.x mappings.** TEI (§8.1) and Jina (§8.2) expose no base64-style output
  encoding, and Cohere's `embedding_types` (§8.4) is a *managed list-shaped* field (0099/0105), not a transport
  encoding — so no other mapping needs this today. A future embedding mapping that adds a transport encoding
  should follow §8.3's shape-driven-decode precedent.
