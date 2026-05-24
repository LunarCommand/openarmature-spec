# 0026: LLM Provider — `§8.X` Wire-Format Mapping Subsection Template

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-24
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (adds a *Per-mapping subsection structure* paragraph under §8 framing)
- **Related:** 0019 (multi-provider wire-format extension — resolves its open-question #2), 0025 (tool_choice — the first §8.X follow-on to use the template)
- **Supersedes:**

## Summary

Lock in a recommended subsection template for §8.X wire-format mappings.
Each §8.X subsection SHOULD follow the structure §8.1 already uses:
*Request mapping* / *Response mapping* / *Error mapping* / *Concurrency* /
*Structured output*, in that order. Providers MAY add sub-subsections
for structural divergence (e.g., Anthropic's `tool_use` / `tool_result`
content-block model warrants its own organization under Request mapping
similar to §8.1.1.1's image-content-block sub-subsection). The
recommendation is SHOULD-level — bindings tighten cross-mapping
consistency without preventing genuinely-different providers from
diverging where they must. Resolves 0019's open question #2.

## Motivation

0019's *Open questions* section flagged the per-mapping subsection
structure as a decision that "the first §8.X follow-on" would settle.
With §8.2 Anthropic Messages and §8.3 Google Gemini both anticipated
as near-term follow-ons, deciding the template once — before two
parallel drafts diverge — is cheaper than reconciling structurally
inconsistent §8.X subsections later.

The case for locking now:

- **Cross-mapping readability.** A reader who already knows §8.1's
  organization can navigate §8.2 / §8.3 / §8.4 etc. by reflex. The
  subsection numbering carries semantic weight: §8.X.3 always means
  "this provider's error mapping," whether X is OpenAI, Anthropic,
  Gemini, or Mistral.
- **Cross-language consistency.** OA's value proposition is that an
  agent ported between Python and TypeScript behaves identically (per
  0019's framing). If `openarmature-anthropic` ships with §8.2.1
  Request mapping in Python and §8.2.5 Request mapping in TypeScript
  because the impls' authors chose different orderings, the spec
  text's cross-impl utility erodes.
- **Conformance fixture sidecar consistency.** Fixture sidecars
  reference spec sections by number (e.g., the §8.1.5.1 references in
  `027-structured-output-openai-wire-mapping-fallback.md`). A stable
  cross-mapping numbering convention means readers landing on a
  fixture sidecar can predict where in the spec text to look.

The case against — for which this proposal makes an explicit allowance —
is that some providers' shapes genuinely don't fit the template
(Anthropic's content-block tool model is the canonical example). The
SHOULD-level recommendation accommodates this by permitting additional
sub-subsections; only the top-level five are template-aligned.

## Detailed design

### §8 framing: add *Per-mapping subsection structure* paragraph

Insert a new paragraph under §8 (Wire-format mappings), after the
existing *Compliance label* paragraph and before §8.1:

> **Per-mapping subsection structure.** Each §8.X subsection SHOULD
> follow the canonical structure used by §8.1:
>
> | Subsection | Topic |
> |---|---|
> | §8.X.1 | Request mapping |
> | §8.X.2 | Response mapping |
> | §8.X.3 | Error mapping |
> | §8.X.4 | Concurrency |
> | §8.X.5 | Structured output |
>
> Provider-specific sub-subsections (e.g., §8.X.1.1 for content-block
> wire mapping per §8.1.1.1, §8.X.5.1 for prompt-augmentation fallback
> per §8.1.5.1) are permitted and expected. Providers whose wire
> shapes have features without §8.1 analogues MAY add additional
> top-level subsections at the end of the recommended five (e.g.,
> §8.X.6 *Caching* if the provider exposes a caching primitive worth
> spec'ing); the recommended five SHOULD precede any provider-specific
> additions, in the order shown.
>
> The recommendation is SHOULD-level rather than MUST-level because
> some providers' shapes diverge from §8.1's organization in ways the
> template can't accommodate by sub-subsection alone. When a §8.X
> proposal diverges from this template, the proposal text SHOULD
> explain the divergence in its *Detailed design* section so reviewers
> can confirm the divergence is structural rather than ergonomic.

### Cross-spec touchpoints

- **§8.1 OpenAI-compatible mapping** — already follows the recommended
  template by definition (the template is derived from §8.1's
  structure). No text changes.
- **§8.X subsections added by future proposals** (§8.2 Anthropic,
  §8.3 Gemini, §8.4 Mistral, …) — each SHOULD follow the template;
  divergences require explanation in the proposal text.
- **Conformance fixture sidecars** — no changes needed. The §8.X
  references in fixture sidecars (per the existing convention) become
  more predictable once the template is locked; future fixture
  sidecars added alongside new §8.X subsections SHOULD reference the
  canonical subsection numbering.
- **No other capability spec is touched.**

### No behavioral change

This proposal is a purely structural recommendation. No new types, no
new error categories, no changes to §3 / §4 / §5 / §6 / §7. All
existing conformance fixtures pass unchanged. §8.1 already follows
the template by construction — it IS the template source.

## Conformance test impact

None. Purely textual structural recommendation. No fixture additions,
no fixture changes.

## Alternatives considered

### Leave the template implicit; let §8.1 set the example

Rejected per 0019's open-question framing. Implicit precedent works if
follow-ons reliably mirror earlier examples, but when two follow-ons
(§8.2 Anthropic, §8.3 Gemini) draft in parallel — as anticipated —
the precedent has no enforcement and the two drafts can diverge
silently. Explicit template-with-allowance is cheap insurance.

### MUST-level template (no divergence permitted)

Rejected. Anthropic's `tool_use` / `tool_result` content-block model
is structurally different enough from OpenAI's top-level `tool_calls`
that forcing the template would either (a) require an awkward fit, or
(b) require the §8.X proposal to deviate from the template anyway, at
which point the MUST is paper. SHOULD with explicit
divergence-explanation requirement preserves both the cross-mapping
consistency benefit AND the room for genuinely-different providers to
shape their text appropriately.

### Add a sixth canonical subsection (e.g., *Tool-call mapping*)

Rejected as part of this proposal but flagged for follow-up. §8.1's
tool-call mapping lives inside §8.1.1 Request mapping (as a table row
mapping spec `ToolCall` to OpenAI's `tool_calls` shape).
That works for OpenAI because the tool-call shape is request-side
serialization of an existing data structure. For Anthropic, where
tool calls are content blocks rather than a top-level field, the
mapping warrants more text. If §8.2 Anthropic surfaces enough
text to warrant its own subsection (e.g., §8.2.1.1 or §8.2.6), that
can be the precedent for adding *Tool-call mapping* to the canonical
template — but only after we have two examples to compare. Premature
to add it now.

### Reorganize §8.1 to match a future canonical template

Rejected. §8.1's current organization IS the canonical template per
this proposal. Reorganizing §8.1 to match itself is a no-op; any
"canonical template" that doesn't match §8.1 would force a §8.1
renumber that breaks every external reference to existing §8.1.X
subsections. The simpler move is recognizing §8.1 as the template
source and recommending §8.X follow it.

## Open questions

None. The proposal's surface is small enough that the SHOULD-vs-MUST
question and the divergence-explanation requirement settle most of
the design space; the *Add a sixth canonical subsection* alternative
captures the one near-term extension point and explicitly defers it
to a future proposal once §8.2 lands.
