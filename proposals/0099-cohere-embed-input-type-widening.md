# 0099: Cohere `/v2/embed` — widen `input_type`, and pin the extras-vs-managed-field claims

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-12
- **Targets:** spec/retrieval-provider/spec.md **§8.4 Cohere** — three edits: (1) widen the `/v2/embed`
  mapping's recognized `input_type` set from the closed `{query, document}` to also accept
  **`classification`** and **`clustering`** (identity-mapped onto Cohere's wire values), removing §8.4's
  claim that Cohere's other `input_type` values "are reached via the extras-pass-through bag" — a mechanism
  that cannot work and that contradicts §8.4's own reject-unrecognized rule; (2) sever the
  "per §8.2's treatment" anchor on that set, which this change makes false; (3) pin the **`embedding_types`
  extras semantics**, a second extras claim in the same paragraph whose collision with the mapping's
  mandatory `["float"]` is undefined today. And **§8.2 Jina** — reconcile the deferral rationale this makes
  stale (Jina keeps its closed set for a *different*, verified reason: model-dependent `task` support).
  Conformance (at Accept): fixture 033 gains `classification` / `clustering` cases, a new fixture pins the
  `embedding_types` merge, and both fixtures' prose companions move off the retired claim.
  **docs/open-questions.md**: the 0078 open question, which asserts the framing this proposal overturns, is
  reconciled.
- **Related:** 0091 (Cohere embeddings wire mapping — introduced §8.4's `input_type` and `embedding_types`
  paragraphs), 0077 (asymmetric query/document embedding — introduced the §2 `input_type` knob and its
  extensible value space), 0078 (Jina wire mapping — §8.2's `task` realization, the section §8.4's broken
  sentence was copied from)
- **Supersedes:**

## Summary

§8.4 says Cohere's other `input_type` values (`classification` / `clustering` / `image`) "are reached via
the extras-pass-through bag, not OA's `input_type`." **That mechanism cannot work**, and the sentence
contradicts the rule two sentences above it.

The fix is not merely to delete the false claim. §2 already provides the real mechanism — *"Additional
well-known values (`classification`, `clustering`, …) **MAY be recognized by mappings whose backend
supports them**"* — and Cohere's backend supports both. So the §8.4 mapping recognizes them, delivering the
capability the broken sentence promised instead of documenting its absence.

Auditing that sentence surfaced a **second** extras claim in the same paragraph: the mapping always sends a
managed `embedding_types: ["float"]`, yet says other precisions "ride the extras-pass-through bag" — and
the spec never says what happens when they meet. That one is *reachable* but *undefined*, and one of its
two readings is self-destructive. This proposal pins it.

## Motivation

### The `input_type` escape hatch cannot work

Two decisive reasons, both at the spec level:

1. **OA's `input_type` is a declared field.** llm-provider §6 defines the extras bag as carrying fields
   "beyond the declared set" — *undeclared* fields are what get forwarded to the wire untouched. §2 declares
   `input_type` on the embedding runtime config, so its name cannot also be an extra: the field owns it.
2. **§8.4 rejects an unrecognized `input_type` pre-send** (`provider_invalid_request`, §7). So
   `input_type: "classification"` never reaches the wire at all. The paragraph rejects the value in one
   sentence and claims you can reach it in the next.

There is also no *room* for such a value: the mapping is required to always send a managed `input_type`
(the wire mandates the field). What would happen if an extras key met that managed field, the spec does not
say — and that silence is itself evidence the escape hatch was never worked through. It is the same silence
the `embedding_types` half exposes, below.

### Why the sentence is wrong *here* but right in §8.2

The claim was copied from §8.2 (Jina), where it holds — and it holds there because of two properties Cohere
lacks:

| | Jina (§8.2) | Cohere (§8.4) |
|---|---|---|
| Wire field name | **`task`** — distinct from OA's field name | **`input_type`** — *the same name* as OA's declared field |
| Always sent? | **No** — an absent `input_type` omits `task` | **Yes** — the wire requires it |

For Jina a caller leaves `input_type` absent and puts `task: "classification"` in extras: it is an
undeclared key, the mapping omits `task`, and the extra rides through cleanly. **Neither precondition holds
for Cohere.** The escape hatch is a Jina property, not a general one, and copying the sentence across
vendors carried it into a mapping where both halves fail.

### The values are already in §2's vocabulary

§2 types `input_type` as an *extensible string* and already names `classification` and `clustering` as
well-known values a mapping MAY recognize when its backend supports them. Cohere's `/v2/embed` accepts
`search_document`, `search_query`, `classification`, `clustering`, and `image` (verified against Cohere's
live `/v2/embed` reference, 2026-07-12; only `image` carries a model-version restriction), and the first
four are purposes for *embedded text*. So no protocol-level widening is required: the mapping opts in,
which is exactly the mechanism §2 designed.

### The `embedding_types` claim is reachable but undefined

Unlike `input_type`, `embedding_types` is **not** a declared OA field, so it genuinely can ride the extras
bag. But the mapping also **always sends a managed `embedding_types: ["float"]`** (so the type-keyed
response is guaranteed to carry the `embeddings.float` key the mapping reads). What happens when a
caller's extras-supplied `embedding_types` meets that managed value is unspecified — and the two readings
diverge sharply:

- **Override** — the caller's `["int8"]` replaces `["float"]`. The response then carries no
  `embeddings.float`, so the mapping's own consumer breaks and the call fails `provider_invalid_response`.
  The documented escape hatch would destroy itself.
- **Merge** — the caller's precisions are added to the mandatory `float`. The response carries both; the
  mapping consumes `embeddings.float` as specified, and the caller reads their precision off
  `RerankResponse.raw` / `EmbeddingResponse.raw` (the verbatim response, per 0096).

Only the merge is coherent, and it is the reading that makes the escape hatch work as §8.4 advertises. The
spec should say so rather than leaving a mapping to pick the self-destructive branch.

## Proposed change

### retrieval-provider §8.4 — recognize `classification` / `clustering`

The `/v2/embed` mapping **MUST** recognize the `input_type` set `{query, document, classification,
clustering}` and map it onto the wire as:

- `query` → `search_query`
- `document` → `search_document`
- **`classification`** → `classification`
- **`clustering`** → `clustering`
- **absent** ⇒ `search_document` — unchanged (the wire requires a value; bulk-indexing is the dominant case)
- **unrecognized** ⇒ `provider_invalid_request` (§7) — unchanged for values outside the set

The mapping **MUST NOT** reject `classification` or `clustering` pre-send. The "reached via the
extras-pass-through bag" sentence is **removed**: the values are now reached through `input_type` itself,
which is where a caller would look for them.

**The "per §8.2's treatment" anchor is severed.** §8.4 currently justifies its closed set as being
"per §8.2's treatment." The two sets now differ deliberately, so the cross-reference is dropped — §8.4
states its own recognized set. (That copy-anchor is precisely what carried the broken sentence across
vendors in the first place.)

**`image` is not included.** It names an input *modality*, not a purpose for embedded text, and OA's
`embed()` consumes a list of strings (§3); §11 scopes v1 to text-only. Image embedding belongs to the
deferred multimodal capability, not to `input_type`'s value space.

### retrieval-provider §8.4 — pin the `embedding_types` extras semantics

An extras-supplied `embedding_types` **MUST** be **merged** with the mapping's mandatory `"float"`, not
replace it: the mapping always requests `float` (so `embeddings.float` is present for its own consumer) and
requests the caller's additional precisions alongside it. The caller reads the extra precisions off the
verbatim response on `raw` (0096). A mapping **MUST NOT** let an extras-supplied `embedding_types` drop
`"float"` from the request.

### retrieval-provider §8.2 — reconcile the stale deferral

§8.2 currently defers on the grounds that "widening `input_type`'s normative value space is a
protocol-level change, deferred until a consumer needs it." That reasoning does not survive this proposal —
and was never quite right, since §2's value space is already extensible and recognition is already
delegated per-mapping.

Jina's mapping still keeps the closed `{query, document}` set, but for the **real** reason: Jina's `task`
support is **model-dependent**. Verified against Jina's live OpenAPI (2026-07-12): `jina-embeddings-v3`
accepts `classification` but not `clustering`; `jina-embeddings-v4` accepts neither; `jina-embeddings-v5`
accepts both. A provider is bound to a model *identifier* and OA has no model-capability registry, so the
mapping cannot promise these values across Jina models — sending `task: "clustering"` to a v4 model would
produce exactly the wire rejection recognition is meant to prevent. §8.2's `task` extras path is unaffected
and continues to work (it is how a caller reaches `text-matching` and the rest — and it works precisely
because `task` is undeclared and omitted when `input_type` is absent).

### retrieval-provider §2 — no change

The value space is already extensible and already names these two values as recognizable-per-mapping. This
proposal exercises that mechanism rather than altering it.

### docs/open-questions.md — reconcile the 0078 open question

The 0078 OQ records widening `input_type` as "a §2 protocol change, not a per-mapping one" — the framing
this proposal overturns. It is updated: the §2-protocol-change premise is retired (recognition is
per-mapping, and §2 already delegates it); what survives, and is now recorded there, is the reason a
mapping may still decline — a backend whose support is model-dependent, as Jina's is.

## Conformance test impact

**At Accept** — the spec edits and fixture updates land with the accept PR:

- **033** (`embed-cohere-input-type`) gains two cases: `classification` → wire `classification`, and
  `clustering` → wire `clustering`. Its prose companion, which describes the recognized set as closed
  `query` / `document`, moves with it.
- **034** (`embed-cohere-input-type-rejected`) is **behaviorally unchanged** — its unrecognized value is
  `"summarization"`, which stays outside the widened set — but both halves of the pair repeat the
  unachievable extras claim (the YAML header comment *and* the markdown companion) and are corrected with
  the spec text.
- **New fixture** pinning the `embedding_types` merge: an extras-supplied `embedding_types` is sent
  *alongside* the mandatory `"float"` (not in place of it), and the mapping still consumes
  `embeddings.float`.

The absent-⇒-`search_document` default and the reject-unrecognized rule are already covered and unchanged.

## Versioning

**MINOR bump** (pre-1.0), and **not additive** — this reverses a normative requirement.

Today a conforming implementation **MUST raise** `provider_invalid_request` for
`input_type: "classification"` (§8.4's reject-unrecognized rule, with the value outside its closed set);
after this it **MUST send** `classification` on the wire. An implementation that hard-codes the old closed
set becomes non-conforming for the two new values, and a caller that relied on the rejection as a guard
(e.g. catching it to fall back to `document`) silently changes behavior. Pre-1.0, a breaking change of this
kind may land in a MINOR bump.

The `embedding_types` merge **pins previously-undefined behavior**: the collision had no specified
resolution, so no implementation could have conformed to a rule that did not exist — but one that chose the
override reading becomes non-conforming.

No change to §2 (its value space already admitted these values) and **no behavioral change** to
§8.1 / §8.2 / §8.3 — §8.2's *prose rationale* is corrected, but its mapping is untouched. Tentative spec
version target deferred to Accept.

## Alternatives considered

1. **Just delete the false sentence and document the gap.** Reject — it makes the spec truthful but
   strictly *less useful*: a caller would be told the values are unreachable on a backend that supports
   them, while §2 already supplies the mechanism to reach them. Deleting the claim fixes the contradiction;
   recognizing the values fixes the contradiction *and* delivers what the sentence promised.
2. **Widen §8.2 Jina as well, for a uniformly portable value space.** Reject — Jina's `task` support is
   model-dependent (v4 accepts neither value; v3 lacks `clustering`), and OA binds a provider to a model
   identifier with no capability registry. A mapping that sent `task: "clustering"` to a v4 model would
   produce the wire rejection recognition exists to prevent. §2's per-mapping opt-in is precisely the
   escape valve for a vendor that cannot promise a value uniformly.
3. **Widen §2's normative value space so `classification` / `clustering` are universal.** Reject — that
   obliges *every* embedding mapping to support them, which no vendor guarantees (see #2). The
   extensible-string + recognized-per-mapping model already accommodates this without a protocol-level
   promise OA cannot keep.
4. **Include `image` in the widening.** Reject — it names an input modality, not a purpose for embedded
   text, and `embed()` consumes strings. Admitting it would put a modality selector inside a field that
   otherwise describes intent, and would promise an image path the protocol has no input shape for.
5. **Let an extras `embedding_types` override the mapping's mandatory `"float"`.** Reject — the mapping's
   response consumer is specified to read `embeddings.float`; an override that dropped `float` from the
   request would strip that key from the response and fail the call `provider_invalid_response`. The
   escape hatch would destroy itself. Merge preserves both the mapping's read path and the caller's
   precision.

## Out of scope

- **`image` / multimodal embedding.** A separate capability concern, deferred.
- **§8.2 Jina's recognized set.** Stays closed; its extras path for `task` is unaffected.
- **§2's normative value space.** Unchanged — already extensible, already names these values.
- **The general extras-vs-managed-field collision rule.** This proposal pins §8.4's two instances. The
  cross-cutting question — what happens when *any* extras key collides with *any* mapping-managed wire
  field, in *any* mapping — is undefined spec-wide (llm-provider §6 says undeclared fields are forwarded
  untouched, but says nothing about a name a mapping also manages). That deserves a general rule rather
  than a per-vendor patch, and needs its own proposal.
- **Portability of the knob.** After this, `input_type: "classification"` succeeds on Cohere and is rejected
  on Jina. That asymmetry is what §2's per-mapping recognition model prescribes, and it is honest: Jina
  cannot promise the value across its models. A uniform cross-vendor purpose vocabulary would need its own
  proposal and a per-model capability story.
