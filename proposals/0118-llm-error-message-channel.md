# 0118: Bring the Harvested Error Message Under the Payload Flag

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-09
- **Accepted:** 2026-08-10
- **Targets:**
  - spec/observability/spec.md **§5.5.4 Opt-out flags** — extend `disable_provider_payload` to gate a failed
    provider call's harvested exception **text**: the `error_message` field the Langfuse mapping writes to
    `observation.metadata` on a failed Generation / Embedding / Tool / Retriever observation. At the flag's
    default (`True`) the message is not emitted. **`error_type` is deliberately NOT gated:** it is a
    classification token, a vendor code or an exception class name (§5.5.12, and the permissive contract fixture
    073 asserts), so suppressing it buys no privacy while removing the caller's only failure discriminator on an
    observation that has no error category. That case is real: a failed **Tool** observation has no category
    (§8.4.6 / §5.5.12), so gating the type would leave it carrying `level = "ERROR"` and nothing else. The gate
    is Langfuse-side only, because the OTel surface defines no `error_message` span attribute: there the
    exception reaches the backend through `record_exception` on openarmature's own span (§6), which this flag
    does not affect.
  - spec/observability/spec.md **§8.7 Generation rendering** — add the failed Generation's `error_message` to
    both the flag-`False` emission list and the flag-`True` suppression list, and state that `error_type` and
    the error category continue to emit regardless, so an implementer deriving Generation behaviour from §8.7
    alone gets the complete picture.
  - spec/observability/spec.md **§8.4.2 / §8.4.3** — add the failed **LLM Generation** to the mapped
    error-message surfaces. Proposal 0117 enumerated three (Tool / Embedding / Retriever) and **explicitly
    excluded** the Generation, on the rationale that a Generation's error *output* is the payload-gated
    `generation.output` (§8.4.3). That holds only for `structured_output_invalid`; every other failure category
    carries **no** output, leaving the raised exception's `error_message` (carried by `LlmFailedEvent`, §5.5.7)
    as the Generation's only harvested error content. Rewrite the §8.4.2 error row to cover all four provider
    observations and add a §8.4.3 *Failed Generation error message* paragraph, both gated by the flag above.
  - spec/observability/spec.md **§6 Driving span lifecycle** — **retire the per-emission error-message rule**
    that 0117 introduced. With the flag governing the error message, that rule can no longer be the operative
    gate in any configuration (see *Why the per-emission rule goes* below), so it is removed rather than left
    as dead text. What stays: the error message is named as a harvested channel riding
    `disable_provider_payload`, the **suppress-all** arm continues to cover it (load-bearing whenever the flag
    is off), and the **Tool anti-smuggling** MUST NOT is preserved, re-anchored to omission generally rather
    than to the retired rule. Reconcile the *No hard failure* and *isolation trade-off* paragraphs, and the
    now-false claim that the error message "applies regardless of the payload knobs."
  - spec/observability/spec.md **§8.4 (mapping intro)** — state the **exhaustive-mapping / over-emission rule**
    (elevating 0117 Open Question #2 to normative): the §8.4.x tables are the complete definition of the
    **harvested content** openarmature renders to Langfuse, so a harvested field is written only where a table
    maps it, and harvested content the tables do **not** map (a stacktrace, or the exception detail on a
    framework-emitted observer event the tables do not render, such as the failure-isolation event's
    `caught_exception`, pipeline-utilities §6.3) is non-conforming over-emission that **MUST NOT** be written to
    any Langfuse observation. Such detail reaches consumers through the surface that owns it: `record_exception`
    on openarmature's OTel span where the error propagates, and otherwise the typed observer event itself. The
    rule governs **harvested** content only; caller-**attached** dimensions (the failure-isolation `event_name`,
    and the §6-exempt identity and correlation tags) remain governed by the harvest-versus-attach exemption.
  - spec/conformance-adapter/spec.md **§5.5** — add **`metadata_absent: [<key>, ...]`** on a Langfuse
    observation entry, asserting none of the listed keys are present in that observation's `metadata`. The
    existing `metadata:` assertion is a subset match, so it can pin a key's value but never its absence. This
    is the Langfuse-observation analogue of the OTel-span `attributes_absent` directive (§5.11, proposal 0095),
    added for the same reason and with the same semantics.
  - spec/observability/conformance/159-langfuse-llm-failure-error-message.{yaml,md} — new fixture, two cases,
    gating the flag's effect on a failed Generation: flag on means `error_message` is absent (via
    `metadata_absent`) while `error_type` and the category are retained; flag off means the message is present.
    Neither case involves a shared provider, so the flag's effect is isolated from §6's arms.
  - **Reconcile the five shipped fixtures the new gate would otherwise contradict.** 137 and 138's payload-
    suppressed cases keep the flag on but assert `metadata_absent: [error_message]` with `error_type` retained;
    150, 151, and 098's failure case move to `disable_provider_payload: false`, because asserting the message
    **literally** is their purpose (proposal 0107), which also means their request-side `input` now populates as
    it does in 137/138's flag-off cases. Without this, no conforming implementation could pass the corpus.
  - spec/observability/conformance/098-langfuse-tool-observation.{yaml,md} — add
    `failed_tool_default_posture_withholds_message_without_smuggling`: a Tool failure under the default posture
    on a normal provider, asserting `error_type` present, `metadata_absent: [error_message]`, and
    `statusMessage: null`. This carries §6's Tool anti-smuggling clause for **every** adapter, since 158's
    shared-provider tool case is restricted to non-detection-capable adapters (a detection-capable one raises
    before emitting).
  - spec/observability/conformance/123-langfuse-failed-generation-renders-output-usage-finish-reason.{yaml,md} —
    add `metadata_absent: [error_message]` to the payload-disabled case, gating **the leak this proposal exists
    to close**: a `structured_output_invalid` message quoting the model output that failed validation, arriving
    beside a redacted `generation.output`.
  - docs/privacy-controls.md + mkdocs.yml — a non-normative explainer page for the whole control surface (the
    knobs, the two hooks, the acknowledgment, the state-field precedence, and what is not controllable),
    reachable from the docs-site nav.
  - spec/observability/conformance/158-langfuse-payload-leak-fail-closed.{yaml,md} — **repoint** the two
    error-message cases (`error_message_omitted_on_shared`, `tool_failure_omitted_on_shared`) from the
    flag-on configuration to the flag-**off** suppress arm, so they gate real §6 behaviour (suppress-all
    covering the harvested error message, and the Tool anti-smuggling clause under suppression) instead of
    passing on the flag alone.
- **Related:** 0117 (the payload-leak invariant this amends), 0116 (the invariant), 0059 (the
  `disable_provider_payload` flag this extends), 0058 (`LlmFailedEvent` §5.5.7, the source of the Generation's
  error fields), 0095 (the `attributes_absent` precedent for the new absence directive), 0050 (the
  failure-isolation event the over-emission rule resolves), 0043 (the harvested-versus-attached lineage)
- **Supersedes:**

## Summary

This proposal does three things, all in service of one outcome: a caller who turns off provider payload never
gets harvested exception text in Langfuse, while keeping the classifications (`error_type` and the error
category) that let them tell failures apart.

1. **The LLM Generation joins the mapped error-message surfaces.** 0117 excluded it on a rationale that holds
   only for one failure category. For a 4xx, a timeout, or a 5xx, the failed Generation has no output at all,
   so the exception message is its only harvested error content.
2. **The harvested error message moves under `disable_provider_payload`** for all four provider observations.
   This is the substantive change, and it closes a hole: the flag exists to keep the model-interaction
   transcript out of Langfuse, but a `structured_output_invalid` exception message commonly quotes the model
   output that failed validation, and a provider 4xx can quote the request. Before this change a caller could
   set the flag, watch `generation.output` disappear as promised, and still receive that text inside
   `metadata.error_message` on a fully isolated provider, with no lever to stop it.
3. **The exhaustive-mapping rule closes the surface.** 0117 named it as an open question; making it normative
   means a harvested field is either mapped, and therefore governed by the flags and the invariant, or
   forbidden outright. A newly discovered emission site is then an implementation bug the spec already forbids
   rather than a new proposal.

It does **not** supersede 0117. That proposal's client-ownership model, isolation machinery, raise and suppress
arms, state channel, caller-dimension exemption, and Tool anti-smuggling clause all still govern. One rule
inside it, the per-emission error-message rule, is retired as unreachable.

## The organizing principle (unchanged from 0117)

openarmature guards the payload it **harvests** from the runtime, and does not police the dimensions and tags
the caller **deliberately attaches**. A raised exception's message on a failed provider call is harvested:
openarmature extracts it from the provider boundary, and the caller never handed it over as observability
data. What 0118 adds is that harvested content should answer to the caller's payload flag, not only to the
framework's routing decisions.

## Motivation

**The exclusion of the LLM Generation was too narrow.** 0117's §8.4.2 row scoped the error-message mapping to
"Embedding / Tool / Retriever observations **only**," adding that "node `Span` and `Generation` observations
carry only `error.category` here (a Generation's error *output*, where present, is the payload-gated
`generation.output`, §8.4.3)." The parenthetical is the whole justification and it is conditional. §8.4.3 is
explicit that the output is present only for `structured_output_invalid`: "Every other failure category carries
no response, so its failed Generation has `output` / `usage` absent." So for a 4xx, a timeout, or a 5xx there
is no output to carry the error, and the exception message stands alone.

**The flag's promise had a hole, and no lever closed it.** §5.5.4's `disable_provider_payload` enumerates the
input and output payload attributes and does not include `error_message`. A `structured_output_invalid`
failure's exception message commonly embeds the model output that failed validation, which is exactly the
content the flag exists to suppress. A caller running the locked-down posture therefore had no way to keep
that text out of Langfuse. Gating the error message with the same flag gives the caller one rule to hold:
payload off means categories only.

**Nothing is lost by omitting it.** openarmature's OTel observer calls `record_exception` on its own span,
bound to a **private** `TracerProvider` (§6) that is isolated from any shared provider by construction, so the
full exception continues to reach the caller's OTel backend regardless of this flag. Provider failures
propagate, so that path genuinely fires for all four observations. Omission removes a duplicate from Langfuse;
it does not discard the error.

**Why the per-emission rule goes.** 0117 handled the error message with a per-emission rule: do not emit it to
a provider not established as isolated, regardless of the payload knobs. Its purpose was the locked-down case,
where no construction-time channel is live yet a failure still leaked a message. Once the flag covers the
message, that case no longer exists, and no other configuration reaches the rule either:

- flag **on** (the default): the message is never emitted, so the rule has nothing to suppress;
- flag **off** with an isolated provider: the message emits legitimately;
- flag **off** with a shared provider, detectable: the invariant **raises** at construction, so nothing emits;
- flag **off** with a shared provider, not detectable: **suppress-all** omits the message;
- flag **off** with a shared provider, caller opted in: the message emits as an acknowledged leak.

The rule is unreachable as the operative gate in every branch. Leaving it in place would be dead normative
text, and worse, the two shipped fixture cases that claimed to gate it would pass on the flag instead, which is the
vacuity failure mode this cycle already hit twice. So it is retired, its suppress-arm coverage is kept
explicitly, and its Tool anti-smuggling clause is preserved.

**The second finding, and why enumeration is the wrong shape.** A pre-merge review of the 0117 build surfaced a
fifth harvested error-message site: the failure-isolation event's caught-exception message. The
failure-isolation middleware (pipeline-utilities §6.3) dispatches a framework-emitted event when a node's
exception is caught and the node returns degraded. That event is **observer-event-only**, a distinct kind
carrying neither `NodeEvent.error` nor a §4 category, and the §8.4.x tables render it **nowhere**. So it was
never a fifth channel: any Langfuse `error_message` on it is an emission the mapping tables never defined. Two
consecutive findings of the same shape, the enumeration listing observation types and missing an emission
site, say the method will keep missing sites. Hence the exhaustive-mapping rule.

## Detailed design

### §5.5.4 — the flag gates the harvested error message

Add to `disable_provider_payload`'s scope: on the Langfuse side, a failed Generation / Embedding / Tool /
Retriever observation's `error_message` in `observation.metadata` (§8.4.2, §8.4.3, §8.4.5, §8.4.6, §8.4.7).
When the flag is `True` the message is not emitted, and the observation carries its `error_type` and its error
**category** where one exists (the `observation.statusMessage` enum, §8.4.2), both classifications rather than
harvested text. Langfuse-side only, since the OTel surface carries no `error_message` attribute and its
`record_exception` path is unaffected.

### §6 — retire the per-emission rule, keep suppress-all and anti-smuggling

The error message is named as a harvested channel that is live when `disable_provider_payload=False`, the same
condition as the provider payload, so it needs no separate liveness test and adds no new raise driver. Every
harvested channel is then construction-determinable, which simplifies the arms.

The per-emission rule is replaced by a paragraph stating that the message is gated by the flag, that wherever
it is omitted the observation retains its `error_type` and error category, and that the exception message **MUST NOT** be
surfaced through `observation.statusMessage` as a substitute. A failed **Tool** observation has no error
category (§5.5.12), so under omission it carries neither the message nor any message-derived status text.

The suppress-all arm continues to name the error message explicitly, since it is load-bearing whenever the flag
is off. The no-payload clause gains a simplification: with the flag on, a *failed* observation adds nothing
harvested either, so the locked-down posture carries no harvested content on either the success or the failure
path.

### §8.4.2 / §8.4.3 — the four provider observations

The §8.4.2 error row covers failed Generation / Embedding / Tool / Retriever observations, gated by the flag
and, where the flag permits, subject to §6. The node `Span` exclusion stays (its category is the §4.2
graph-engine mapping; it harvests no provider exception), and framework-emitted observer events the tables do
not render have no mapping there at all. §8.4.3 gains a *Failed Generation error message* paragraph noting that
the exception string is a surface distinct from `generation.output`: `structured_output_invalid` carries both,
every other category carries only the message, which is why one flag governs both.

### §8.4 — the exhaustive-mapping rule

Stated as in the Targets above. It forbids an emission the tables never defined, so it adds no gated channel
and needs no directive.

### Fixtures

**New fixture 159**, the load-bearing pair for the flag, on a normal provider so the flag's effect is isolated
from §6's arms:

- `llm_failure_error_message_omitted_under_default_posture` — `mock_llm` 503 to `provider_unavailable`, flag at
  its default `true`. The failed Generation emits at ERROR with `statusMessage: "provider_unavailable"`,
  `input` / `output` null, `error_type` asserted present, and `metadata_absent: [error_message]`. An implementation emitting the
  exception string under the default posture fails here.
- `llm_failure_error_message_emitted_with_payload_flag_off` — the same failure with the flag `false`. The
  fields are present (asserted by format, since the values are implementation-sourced), the request-side
  `input` populates, and `output` stays null because no response arrived. This is what makes the first case's
  null `output` meaningful and its absence assertion non-vacuous.

**Fixture 158**, two repoints and one removal:

- `error_message_omitted_on_shared` and `tool_failure_omitted_on_shared` move from flag-on to **flag-off with a
  non-detection-capable adapter**, which is the suppress arm. They now gate suppress-all covering the harvested
  error message, and the Tool anti-smuggling clause under suppression, asserting `metadata_absent` plus the
  mandated `WARNING`. Under 0118's gating their previous flag-on configuration would have had the flag suppress
  the message, leaving them asserting nothing about §6.
- the draft's `llm_failure_omitted_on_shared` case is dropped as redundant: fixture 159 gates the flag, and the
  two repointed cases gate the suppress arm.

## Conformance test impact

**This change breaks existing fixtures**, and reconciling them is part of the accept rather than follow-up
work. Narrowing what a failed observation may carry under the default posture contradicts five shipped cases
that assert the message present with the flag on or defaulted, so an unreconciled corpus would be
unsatisfiable: no implementation could pass both the old cases and the new rule. `GOVERNANCE.md` scopes MINOR
to changes that do not break existing fixtures, so this lands as a MINOR only under the pre-1.0 allowance for
breaking changes in a MINOR bump, and the CHANGELOG says so plainly.

One new directive. `metadata_absent` is required because what this change gates is an **absence** of metadata
keys, which the subset-matching `metadata:` assertion cannot express; it mirrors the OTel-span
`attributes_absent` directive added by proposal 0095 for the identical reason. Otherwise no new directives: the
`mock_llm` failure, the mock-failure directives, the leak assertions, and `requires_capability` all pre-date
this proposal.

Fixture inventory:

- **New:** 159 (two cases, gating the flag).
- **Reconciled:** 137 and 138's payload-suppressed cases (flag stays on, message now asserted absent); 150,
  151, and 098's failure case (flag moved to `false` so their literal message assertions stay reachable, which
  also populates their request-side `input`).
- **Extended:** 098 gains a default-posture case carrying the Tool anti-smuggling clause for every adapter;
  123's payload-disabled case gains `metadata_absent: [error_message]`, gating the motivating leak.
- **Repointed:** 158 keeps its ten cases, with the two error-message cases moved to the flag-off suppress arm,
  because their prior configuration no longer tests what their names claim.

The exhaustive-mapping rule carries no fixture, because it forbids an emission the mapping tables never
defined, so no conforming emission exists to assert against and no positive baseline could keep an absence
assertion non-vacuous. It is gated by the mapping tables themselves, with an implementation-side sweep of the
bundled observer's handlers as the corresponding check.

## Alternatives considered

1. **Leave the error message ungated by the flag** (ship the LLM channel as 0117 shaped the other three).
   Rejected: it leaves `disable_provider_payload` with a silent hole and no lever, and 0118 would be the change
   that opens that hole for the model-output case. Consistency with three channels that share the same defect
   is not a reason to extend it to a fourth.
2. **Gate only the LLM Generation's error message by the flag**, leaving the other three on 0117's rule.
   Rejected: it makes the four provider observations behave differently for no principled reason, and it does
   not avoid the shadowing problem, since the LLM's own per-emission path becomes unreachable in exactly the
   same way.
3. **Do not emit the LLM error message at all.** Rejected: the LLM would then show less on failure than the
   other three provider observations, with no principled basis, and the caller loses genuinely useful detail in
   the configuration where they explicitly permitted payload.
4. **Gate the message only for `structured_output_invalid`**, the category where it provably embeds model
   output. Rejected: a carve conditional on failure category is fragile, and a provider 4xx can quote the
   request just as readily. Uniform gating is simpler and complete.
5. **Gate `error_type` alongside `error_message`.** Rejected: the type is a classification token, a vendor
   code or an exception class name, not harvested runtime text, so gating it buys no privacy. It also costs
   real diagnostic value, because a failed **Tool** observation carries no error category (§5.5.12), so under
   the default posture gating the type would leave it with `level = "ERROR"` and no indication of what failed.
   For the same reason `error_type` is removed from 0117's payload-bearing conformance predicate: a
   classification does not make an observation payload-bearing.
6. **Also open a node `Span` error-message channel.** Rejected: a node `Span` is not a provider observation and
   §8.4.2 maps it no `error_message` field, so a harvested exception message on it is over-emission rather than
   a channel to gate; a propagating node exception reaches the OTel side via `record_exception`.
7. **Gate the failure-isolation event's message as a fifth channel** (parity with the four provider
   observations). Rejected in favour of the exhaustive-mapping rule: that event is observer-event-only and the
   §8.4.x tables render it nowhere, so there is no mapped observation to gate. Gating it would first require
   defining a Langfuse rendering for the event, a feature addition out of scope here, and would then make an
   *isolated* node failure show more detail in Langfuse than an ordinary one. The caught exception's detail
   remains available to the caller on the event itself (§6.3 `caught_exception`, `on_caught`).

## Open questions

1. **The surface is closed by the mapping tables, not by enumeration.** The four mapped provider observations
   gate their harvested error message through `disable_provider_payload`, alongside the provider-payload and
   state channels; everything else openarmature harvests is governed by the §8.4 exhaustive-mapping rule, so it
   is either mapped and gated or forbidden. A future capability that wants to newly surface a harvested field in
   Langfuse adds a §8.4.x mapping through its own proposal, decided by the harvested-versus-attached test (0117
   Open question #1). That is a feature addition rather than a leak patch.
2. **Debuggability under the locked-down posture.** A caller running `disable_provider_payload=True` now sees
   error categories only in Langfuse and reads exception detail from their OTel backend. That is the intended
   trade and the flag's stated purpose, but it is a visible change for anyone who relied on Langfuse alone for
   failure triage while running the default posture. Whether a future proposal should offer a narrower control,
   for example permitting the exception message while still suppressing request and response payload, is left
   open rather than pre-empted here.
