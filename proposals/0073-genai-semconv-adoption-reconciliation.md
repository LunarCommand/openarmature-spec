# 0073: GenAI Semantic-Convention Adoption Reconciliation

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-17
- **Accepted:** 2026-06-18
- **Targets:** `GOVERNANCE.md` (*External-dependency adoption*) — adds two subsections: a **De-facto interoperability standard** carve-out (scoped to the OpenTelemetry GenAI semantic conventions) licensing direct adoption of universally-recognized upstream names even at upstream Development status, and a **Post-adoption upstream change** retention rule (an adopted name is retained through a later upstream rename / removal / restructure / status change; migration to a successor happens only via a deliberate follow-on proposal). `docs/compatibility.md` — corrects the OpenTelemetry-semconv row + *Per-dependency detail* section to record that the GenAI conventions moved to the dedicated `open-telemetry/semantic-conventions-genai` repository where the entire `gen_ai.*` surface is **Development** (verified 2026-06-17), that `gen_ai.system` has been replaced upstream by `gen_ai.provider.name`, and that OA adopts the core `gen_ai.*` names per the carve-out and retains `gen_ai.system` per the retention rule. `spec/observability/spec.md` — reconciling notes only (no emitted-attribute change): a new framing note in §5.5 distinguishing the *core de-facto-standard* `gen_ai.*` attributes (adopted directly) from *peripheral Development* attributes (mirrored to `openarmature.*`); a retention note that `gen_ai.system` is retained pending a future migration to `gen_ai.provider.name`; and a wording reconciliation of the §5.5.3.1 / §5.5.8 "until upstream Stable" rationale to match the core-vs-peripheral distinction. No spec text in `spec/` changes which attribute keys are emitted.
- **Related:** 0007 (observability OTel span mapping — established the `gen_ai.*` mapping surface), 0024 (GenAI semconv response attributes — where the direct `gen_ai.system` / `gen_ai.request.model` / `gen_ai.usage.*` adoption originated), 0047 (§5.5.3.1 OA-namespaced cache-attribute mirror — the *peripheral Development* mirror precedent this proposal generalizes), 0059 (embedding §5.5.8 — extended the direct `gen_ai.*` adoption to embedding spans and deferred `gen_ai.operation.name` as peripheral), 0067 (OTel GenAI metrics — **blocked on this proposal**; its §11.3 dimension table reuses these `gen_ai.*` keys and must cite a correct adoption basis). Policy: *Stable-only upstream adoption* (`GOVERNANCE.md`; tracked in `docs/compatibility.md`).
- **Supersedes:**

## Summary

OpenArmature's observability spec emits a set of `gen_ai.*` attributes directly (§5.5.2 request
parameters, §5.5.3 LLM response attributes, §5.5.8 embedding attributes), and `docs/compatibility.md`
records them as "Stable attributes adopted directly." A re-verification against the **current
authoritative source** — the dedicated `open-telemetry/semantic-conventions-genai` repository, into
which the GenAI conventions were carved out of the main `semantic-conventions` repo — shows that the
**entire GenAI semantic-convention surface is at Development status** (registry `model/gen-ai/registry.yaml`,
verified 2026-06-17: 96 attributes at `stability: development`, none Stable), and that
**`gen_ai.system` has been removed upstream in favor of `gen_ai.provider.name`**. OA's "Stable, adopted
directly" classification is therefore inaccurate.

This proposal reconciles the policy with reality without changing any emitted attribute. It adds two
rules to the *External-dependency adoption* governance section — a narrow **de-facto-standard carve-out**
(OA MAY adopt the universally-recognized core `gen_ai.*` names directly even at upstream Development,
because every GenAI-aware backend keys on them and an `openarmature.*` mirror would defeat the
interoperability the names exist to provide) and a **post-adoption retention rule** (an adopted name is
held through a later upstream rename / removal / status change; migration is a deliberate follow-on
decision) — and corrects `docs/compatibility.md` plus the §5.5 framing prose accordingly. The emitted
attribute keys are unchanged; existing conformance fixtures remain valid.

## Motivation

**OA's stable-only policy cannot explain OA's own practice.** GOVERNANCE.md *External-dependency
adoption* says upstream attributes are adopted directly "ONLY when the upstream marks them Stable," and
Development attributes "MUST be mirrored to the `openarmature.*` namespace." But OA has emitted
`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, the
§5.5.2 request parameters, and the §5.5.8 embedding subset **directly** since proposals 0007 / 0024 /
0059 — and the authoritative GenAI semconv marks all of them Development. A literal reading of the
policy would require mirroring the *entire* `gen_ai.*` surface to `openarmature.*`, which would render
OA's spans unrecognizable to every GenAI-aware OTel backend — destroying the cross-vendor recognition
that is the whole reason to emit `gen_ai.*` at all. The policy has a gap: it never contemplated an
upstream convention that is *the* de-facto interoperability standard while remaining formally
pre-stable.

**The trigger.** Proposal 0067 (OTel GenAI metrics) adds metric *dimensions* that reuse these same
`gen_ai.*` keys, and its draft §11.3 justifies `gen_ai.system` / `gen_ai.request.model` as "Stable
upstream attributes, used directly." Accepting 0067 would freeze that inaccurate claim into immutable
spec text — and would build a brand-new normative surface (the §11 metrics signal) on an adoption
rationale that does not hold. The foundation must be corrected first; then 0067 (and the further
observability work in 0060 / 0063) builds on a coherent basis.

**Upstream moved twice.** Two distinct upstream events surfaced during verification (both against
`semantic-conventions-genai` `main`, 2026-06-17):

1. The GenAI conventions were **split into a dedicated repository**, where the whole `gen_ai.*` surface
   carries Development badges. Whether the core attributes were ever Stable in the old main-repo
   location is moot — the authoritative current source is unambiguously all-Development.
2. **`gen_ai.system` was removed and replaced by `gen_ai.provider.name`** (itself Development). OA
   currently emits `gen_ai.system` across §5.5.3 / §5.5.8 and the Langfuse §8.4.3 mapping, and many
   accepted fixtures assert it.

OA needs a rule for both — for adopting a pre-stable de-facto standard, and for what happens when an
adopted name is later renamed or removed.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0) — adds normative adoption rules to governance and reconciles the
spec's adoption framing. No emitted attribute key changes and no conformance expectation changes, so a
**PATCH / textual** classification is defensible; the concrete version and classification are the
maintainer's call at acceptance.

### The core distinction: de-facto-standard vs peripheral

The reconciliation rests on a distinction OA's existing practice already draws implicitly, which this
proposal makes explicit. Because the *entire* GenAI convention is Development, "Stable vs Development"
is not the line that separates OA's direct-adoption set from its mirrored set. The real line is:

- **Core de-facto-standard attributes** — the `gen_ai.*` names the broad installed base of GenAI-aware
  observability backends recognizes today: the operation identity (`gen_ai.system` / its successor),
  the request model (`gen_ai.request.model`), token usage (`gen_ai.usage.input_tokens` /
  `gen_ai.usage.output_tokens`), the response identity (`gen_ai.response.model`, `gen_ai.response.id`,
  `gen_ai.response.finish_reasons`), and the §5.5.2 request parameters. OA adopts these **directly**:
  mirroring them would make OA's spans unrecognizable to the exact tools the convention exists to serve.

- **Peripheral Development attributes** — newer or not-yet-ubiquitous `gen_ai.*` attributes that backends
  do not broadly key on: the cache-token attributes (`gen_ai.usage.cache_read.input_tokens` /
  `gen_ai.usage.cache_creation.input_tokens`, §5.5.3.1), `gen_ai.operation.name`, and `gen_ai.token.type`.
  OA **mirrors** these to `openarmature.*` until they are either Stable or demonstrably ubiquitous, per
  the §5.5.3.1 / 0047 precedent.

This is the coherent explanation for why §5.5.3 emits `gen_ai.usage.input_tokens` directly while
§5.5.3.1 mirrors `gen_ai.usage.cache_read.input_tokens` — both are upstream Development, but only the
former is part of the recognized core. No emitted attribute changes under this framing; it renames the
*justification*, not the keys.

### Governance: two new subsections under *External-dependency adoption*

The following are added after the existing **Stable-only adoption** / **Rationale** /
**Implementation constraint** / **Tracking** paragraphs.

> **De-facto interoperability standard (narrow carve-out).** Where an upstream attribute set is the
> de-facto cross-ecosystem interoperability standard for its domain — recognized by the broad installed
> base of tools that consume the signal — OA MAY adopt the recognized **core** names directly even while
> the upstream marks them Development, when mirroring those names to `openarmature.*` would defeat the
> interoperability the names exist to provide. This carve-out is currently scoped to the **OpenTelemetry
> GenAI semantic conventions** (`gen_ai.*`): every GenAI-aware observability backend keys on the
> `gen_ai.*` names, so an `openarmature.*` mirror of the core attributes would render OA's spans
> unrecognizable to precisely the tools the semconv targets. Newer or peripheral attributes within the
> same convention that the installed base does not broadly recognize are still mirrored to
> `openarmature.*` per the stable-only rule above, until they are Stable or demonstrably ubiquitous. Each
> use of this carve-out MUST be recorded in `docs/compatibility.md` with the adopted names, their
> upstream status, and the interoperability rationale. The carve-out does NOT extend to other
> dependencies without a proposal that makes the same de-facto-standard showing.

> **Post-adoption upstream change (retention).** Once OA has adopted an upstream name — whether at
> upstream Stable or under the de-facto-standard carve-out above — a later upstream **rename, removal,
> restructure, or status change** does NOT automatically change what OA emits. OA **retains** the adopted
> name, keeping its emitted surface stable for the consumers and conformance fixtures that depend on it,
> and migrates to a successor name only through a deliberate follow-on proposal, when the successor is
> itself worth adopting (it reaches Stable, or the ecosystem has demonstrably moved to it).
> `docs/compatibility.md` records the divergence — the adopted name, the upstream successor, and that
> migration is deferred. *Rationale:* spec text and conformance fixtures are durable; chasing upstream
> churn — especially within a pre-stable convention that renames freely — would thrash every
> implementation for no consumer benefit, which is the same volatility the stable-only rule guards
> against.

### `docs/compatibility.md` corrections

- The OpenTelemetry-semconv compatibility-matrix row: change the GenAI portion of the **Notes** from
  "Stable attributes adopted directly via `gen_ai.*`" to record that the GenAI conventions now live in
  the dedicated `semantic-conventions-genai` repository where the `gen_ai.*` surface is **Development**;
  OA adopts the **core** `gen_ai.*` names directly per the de-facto-standard carve-out and mirrors
  peripheral ones; `error.type` (core semconv, not GenAI) remains genuinely Stable. Update the
  **Last verified** date to 2026-06-17 and note the repository split.
- The *Per-dependency detail → OpenTelemetry semantic conventions* section: replace the "Stable
  attributes: adopted directly (e.g., `gen_ai.system`, `gen_ai.request.model`, …)" bullet with the
  core-vs-peripheral framing; add a bullet recording the **`gen_ai.system` → `gen_ai.provider.name`**
  upstream rename and that OA retains `gen_ai.system` per the retention rule (migration deferred,
  because `gen_ai.provider.name` is itself Development and the installed base still keys on
  `gen_ai.system`).

### `spec/observability/spec.md` reconciling notes

No attribute key emitted by the spec changes. The following prose is reconciled:

- A short framing note added to §5.5 (ahead of §5.5.1) stating that the `gen_ai.*` attributes OA emits
  are adopted under the GenAI de-facto-standard carve-out (`GOVERNANCE.md`), drawing the core-vs-peripheral
  distinction above; the core names are emitted directly and the peripheral ones are mirrored to
  `openarmature.*` (§5.5.3.1).
- §5.5.3's `gen_ai.system` entry gains a note that the attribute is **retained** even though upstream has
  replaced it with `gen_ai.provider.name`, per the governance retention rule; a future proposal MAY
  migrate to `gen_ai.provider.name` when warranted. The same note is referenced from §5.5.8.
- §5.5.3.1's *Stable-only namespace rationale* paragraph and §5.5.8's *Stable-only upstream adoption —
  operation-name attribute deferred* paragraph are reconciled to the core-vs-peripheral framing: the
  cache attributes and `gen_ai.operation.name` are mirrored because they are **peripheral**
  Development attributes, not merely because "they are Development" (the whole convention is). The
  migration trigger is restated as "Stable **or** demonstrably ubiquitous."

### Relationship to proposal 0067

Under this reconciliation, 0067's §11.3 metric dimensions are **correct exactly as drafted** and need no
key change: `gen_ai.request.model` and the operation-identity dimension are core de-facto-standard
attributes (direct), `openarmature.gen_ai.operation` and `openarmature.gen_ai.token.type` are mirrors of
peripheral Development attributes (correct), and `error.type` is genuinely Stable (direct). 0067's accept
work substitutes the de-facto-standard / retention justification for the inaccurate "Stable upstream
attributes" wording, and uses the operation-identity dimension consistently with whatever §5.5.3 emits
(`gen_ai.system`, retained). This proposal therefore unblocks 0067 without expanding its scope.

## Conformance test impact

**None.** No emitted attribute key changes, so no fixture changes. The existing observability fixtures
that assert `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`, and the §5.5.2 request parameters
(e.g., 019 / 020 / 082) remain valid as-is and serve as the retention regression coverage — they pin
that OA continues to emit `gen_ai.system` despite the upstream removal. This proposal is governance +
spec-framing reconciliation; it changes no behavior any implementation could newly fail.

## Alternatives considered

- **Do nothing.** Leave `compatibility.md` asserting "Stable, adopted directly" and let 0067 inherit the
  claim. Rejected: it freezes a verifiably false rationale into 0067's immutable §11 text and leaves the
  policy unable to explain OA's own emitted surface.
- **R2 — chase the rename: migrate `gen_ai.system` → `gen_ai.provider.name` now.** Rejected: the successor
  is itself Development, so adopting it directly violates stable-only (and the carve-out would then have
  to cover it anyway), while mirroring it to `openarmature.*` loses backend recognition. It also churns
  every fixture and the §8.4.3 Langfuse mapping that asserts `gen_ai.system`, for no consumer benefit
  while the installed base still keys on `gen_ai.system`. A deliberate migration remains available as a
  future proposal under the retention rule.
- **R3 — strict mirror: move the entire `gen_ai.*` surface to `openarmature.*`.** Rejected: this is the
  literal stable-only reading given the all-Development upstream, and it is self-defeating — it destroys
  the cross-vendor GenAI recognition that is the sole reason to emit `gen_ai.*`. It would also be a
  massive breaking change across the observability fixture corpus and the Langfuse mapping.
- **General (non-GenAI-scoped) de-facto-standard carve-out.** A broader carve-out applicable to any
  upstream dependency was considered. Rejected for v1: scoping the carve-out to the GenAI semconv keeps
  the stable-only posture conservative everywhere else; a future de-facto-standard case extends the
  carve-out via its own proposal making the same showing.

## Open questions

- **Timing of an eventual `gen_ai.system` → `gen_ai.provider.name` migration.** The retention rule defers
  it; a future proposal decides when (the successor stabilizing, or the ecosystem demonstrably moving).
  Tracked in `docs/compatibility.md`.
- **Whether the core-vs-peripheral classification should be enumerated normatively** (a fixed list of
  "core" `gen_ai.*` names) or left as the descriptive criterion ("recognized by the broad installed
  base") applied per attribute as proposals add them. This proposal uses the descriptive criterion;
  enumeration could follow if it proves ambiguous.
