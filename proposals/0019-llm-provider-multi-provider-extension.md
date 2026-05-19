# 0019: LLM Provider — Multi-Provider Wire-Format Extension

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (modifies §8 framing)
- **Related:** 0006 (LLM provider core), 0015 (multimodal images), 0016 (structured output)
- **Supersedes:**

## Summary

Reframe llm-provider §8 from "the wire format" to "one wire-format mapping among
several." The §5 Provider interface, §3 message shape, and §7 error categories
are the normative cross-provider contract; §8 catalogs concrete wire-format
mappings, of which §8.1 (OpenAI-compatible) is the current entry. Establish the
**default rule** that any provider wire-format mapping intended for cross-language
implementation (i.e., a `openarmature-<provider>` sibling package shipping in both
Python and TypeScript) MUST land in §8.X — wire-format consistency across
language implementations is part of OA's cross-language promise. Out-of-tree
mappings remain valid for genuinely niche / single-language cases that make no
cross-impl behavioral guarantee. No behavioral change to existing implementations;
follow-on proposals (Anthropic Messages, Google Gemini, Mistral, …) each add a
§8.X subsection.

## Motivation

Today's §8 is structured as if OpenAI-compatible is the only wire format the spec
contemplates ("The OpenAI Chat Completions API … is the de facto standard. A
provider implementation MAY opt into an 'OpenAI-compatible' label only if it
implements the wire mapping below."). The §5 Provider interface, §3 message shape,
and §7 error categories are already abstract — they don't assume OpenAI's wire
format — but the framing of §8 leaves implementations to infer the spec's stance
on non-OpenAI providers.

The next wave of `openarmature-python` work will likely ship native providers for
Anthropic Messages API, Google Gemini, and Mistral. Each has its own wire shape:
Anthropic uses a different `content`-array discriminator for tool calls; Google's
tool calling routes through `FunctionCall` records with a different schema-encoding
convention; Mistral targets OpenAI compatibility but with provider-specific tool-
result conventions. These divergences fit within the §3 / §5 / §7 contract but
need a different §8 wire mapping.

**Cross-language consistency is the load-bearing motivation.** OA's value
proposition is that an agent written against the Python implementation behaves
identically when ported to TypeScript (or any future language) — same state
contract, same observer events, same error categorization, same provider
behavior. The §3 / §5 / §7 contract delivers most of this for the abstract
Provider interface. But when a user installs `openarmature-anthropic` in Python
AND its TypeScript sibling expects to deploy the same agent, **the wire-format
mapping must be the same** — same encoding for `tool_calls`, same translation
of multimodal blocks, same handling of Anthropic's structured-output workaround,
same error category mapping. Without a shared spec for the Anthropic mapping,
the two implementations drift in subtle wire shape and the cross-language
promise breaks.

This proposal establishes the rule: any provider mapping with multi-language
ambition lives in §8.X. The OpenAI-compatible mapping (currently §8) is the
first instance; Anthropic, Gemini, Mistral, and others each get follow-on
proposals adding their §8.X subsection. Out-of-tree mappings remain valid for
the genuinely niche case (a single-language specialty provider, a vendor
extension that explicitly doesn't claim cross-impl consistency), but the
default position is in-spec.

This proposal itself is **purely textual** — it establishes the framing and the
default rule, but does not add any new provider mappings. No behavioral change,
no new types, no conformance fixture changes. Implementations currently passing
v0.16.1 fixtures remain conformant under the renamed framing.

## Detailed design

### Renaming §8

Rename §8 from "OpenAI-compatible wire format" to "Wire-format mappings". The
existing §8 body becomes §8.1 "OpenAI-compatible mapping" with its current
subsections renumbered (§8.1 request mapping → §8.1.1, §8.2 response mapping →
§8.1.2, etc.).

### New §8.0 framing paragraph

Insert under the renamed §8 heading, before §8.1:

> ## 8. Wire-format mappings
>
> The §5 Provider interface, §3 message shape, §4 Tool definition, §6 Response
> and configuration, and §7 error semantics are the normative cross-provider
> contract. Any provider implementation conforming to those sections satisfies
> the abstract spec, regardless of the underlying HTTP / RPC / SDK wire format
> used to reach the model.
>
> This section catalogs concrete wire-format mappings for specific provider
> protocols. Each mapping specifies how the abstract §3 / §4 / §6 records
> translate to that provider's wire shape and how the provider's responses /
> errors map back to §3 / §6 / §7. §8.1 describes the OpenAI-compatible Chat
> Completions mapping, which is the broadest-compatibility option (the OpenAI
> hosted API, vLLM, LM Studio, llama.cpp server, and many other local servers
> all speak it). Subsequent subsections (§8.2, §8.3, …) cover provider-native
> formats whose shape diverges from the OpenAI mapping — Anthropic Messages
> API, Google Gemini, Mistral, etc.
>
> **Default placement rule.** Any provider wire-format mapping intended for
> implementation across multiple OA language implementations (Python,
> TypeScript, …) MUST be specified in this section. The cross-language
> behavioral consistency that §3 / §5 / §7 provide for the abstract Provider
> interface extends to wire-format mappings whenever the same provider is
> targeted from multiple languages — without a shared spec, sibling packages
> like `openarmature-anthropic` (Python) and `openarmature-anthropic`
> (TypeScript) would diverge in subtle wire shape and break the cross-language
> promise.
>
> **Out-of-tree mappings.** Wire-format mappings NOT specified here remain
> valid but make NO cross-impl behavioral guarantee. Out-of-tree is appropriate
> for: (a) genuinely single-language specialty providers (a vendor-specific
> mapping with no anticipated TypeScript sibling), (b) vendor extensions that
> explicitly opt out of cross-impl consistency, or (c) experimental mappings
> still finding their shape before promotion to in-spec status. In all other
> cases the in-spec default applies.
>
> **Compliance label.** Provider implementations MAY opt into a mapping's
> compliance label (e.g., "OpenAI-compatible", "Anthropic Messages") only if
> they implement that mapping exactly per the §8.X subsection. A provider MAY
> implement multiple mappings (e.g., one implementation routing OpenAI-
> compatible requests through one path and Anthropic-native requests through
> another) and claim the corresponding labels independently.

### §8.1 subsection updates

Existing §8.1 (Request mapping), §8.2 (Response mapping), §8.3 (Error mapping),
§8.4 (Concurrency), and §8.5 (Structured output) become §8.1.1 through §8.1.5
respectively. Internal cross-references within §8 update accordingly. No other
content changes.

### Anticipated follow-on proposals

This proposal establishes the framing but does NOT add any non-OpenAI mappings.
Each anticipated mapping is its own follow-on proposal with its own wire
specification, conformance fixtures, and acceptance review:

- **§8.2 Anthropic Messages API** — request/response mapping, tool-call
  translation (Anthropic's `tool_use` / `tool_result` content blocks vs OpenAI's
  `tool_calls` + `tool` role), multimodal mapping (Anthropic's
  `source.type: "base64" | "url"` discriminator), structured-output translation
  (Anthropic's `tool` workaround pre-native-structured-output, or its native
  schema support once stable), error categorization.
- **§8.3 Google Gemini** — `FunctionCall` / `FunctionResponse` mapping,
  Gemini's distinct schema-encoding conventions for tool parameters,
  multimodal `Part` / `inline_data` shape, Vertex AI vs Gemini API path
  differences.
- **§8.4 Mistral** — largely OpenAI-compatible at the wire surface but with
  provider-specific tool-result conventions and quirks worth pinning.

Order, exact numbering, and timing are per-proposal decisions. The spec
maintainer is free to accept these in any order; the proposal numbers
shouldn't be reserved here.

### No changes to other sections

§1 through §7, §9, §10 are unchanged. The §3 message shape, §4 Tool definition,
§5 Provider interface, §6 Response and configuration, and §7 error categories
remain the normative contract; this proposal does not add or modify any.

## Conformance test impact

None. This is a purely textual clarification. All existing llm-provider
conformance fixtures (under `spec/llm-provider/conformance/`) target the §3 / §5
/ §7 contract and the §8.1 OpenAI-compatible mapping. They continue to pass
without modification under the renumbered structure.

Future provider wire-format mappings (Anthropic Messages, Google Gemini, etc.)
that land as in-spec subsections (§8.2+) would each ship their own conformance
fixtures verifying the new wire shape. Those fixtures are out of scope for this
proposal.

## Alternatives considered

**Do nothing.** Leave §8 as-is and rely on implementation authors to infer that
non-OpenAI wire formats are first-class. Rejected: the current framing is
plausibly read as "OpenAI-compatible is the only spec-contemplated wire
format," and the next wave of provider work will surface that ambiguity in code
review. Better to clarify ahead of the work than to argue about it per-provider.

**Spec each non-OpenAI mapping inline now.** Pre-emptively write §8.2 Anthropic,
§8.3 Gemini, §8.4 Mistral, etc. in this proposal before any implementation has
shipped. Rejected: without concrete implementations to anchor the wire-format
text, the mappings risk drift between spec and reality. Better to ship each
mapping's spec alongside (or after) its first implementation as its own
follow-on proposal, so the spec text reflects what the wire actually does.

**Leave out-of-tree as a first-class option indefinitely.** Don't establish the
in-spec default; let implementations choose per-provider whether to land in
spec. Rejected: this is the framing the original draft used. Chris's pushback
was correct — if `openarmature-anthropic` exists in Python and TypeScript, the
wire-format mapping must be the same in both, which means it belongs in spec.
Treating out-of-tree as first-class would allow Python and TypeScript siblings
to diverge silently. The cross-language promise requires in-spec by default
for any multi-language mapping.

**Move §8 out of llm-provider into a separate `wire-formats` capability.**
Rejected: the §3 / §5 / §7 / §8 split is already coherent (abstract contract +
concrete mappings); splitting wire formats into their own capability adds a
cross-reference burden without clarifying anything.

**Reorganize §8 as a registry / discovery mechanism.** A spec section that
lists "known wire-format mappings" with metadata about each. Rejected: spec is
not a registry. Per-mapping discoverability is a docs / sibling-package
discoverability concern, not a normative spec one.

## Open questions

- **Numbering convention for §8 subsections.** This proposal uses §8.1 for
  OpenAI-compatible, leaving §8.2+ for additional mappings. An alternative
  numbers each mapping at the same level as the original §8.1-§8.5 set (§8
  becomes "Wire-format mappings: OpenAI-compatible" → "§8 OpenAI-compatible
  mappings" + new §8.6+ Anthropic). The proposed nesting (§8.1, §8.2, …) is
  cleaner for readers; the alternative preserves more existing cross-reference
  text. Maintainer call.
- **Per-mapping section structure.** Should this proposal establish a
  recommended structure for each §8.X subsection (e.g., §8.X.1 Request mapping,
  §8.X.2 Response mapping, §8.X.3 Error mapping, …) so the §8.2 Anthropic
  follow-on can adopt it without re-litigating organization? §8.1's current
  structure works as the template; future proposals could either mirror it or
  diverge per provider. Worth deciding here vs leaving to the first follow-on.
- **What "Cross-language ambition" means in practice.** The default rule says
  multi-language mappings land in spec. The first concrete test will be when
  someone proposes a new provider mapping — does the spec maintainer accept
  it on the grounds of "TypeScript port anticipated" or require a concrete
  TypeScript implementation in flight? Probably the former is fine (the spec
  is the contract; the implementation follows), but worth clarifying in the
  first follow-on if reviewers push.
