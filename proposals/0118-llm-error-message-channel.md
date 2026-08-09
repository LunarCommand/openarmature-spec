# 0118: LLM Generation Error-Message Channel, and Exhaustive Mapping for Harvested Content

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-09
- **Accepted:**
- **Targets:**
  - spec/observability/spec.md **§6 Driving span lifecycle** — add the failed **LLM Generation** to the
    mode-(b) payload-leak invariant's error-message channel. Proposal 0117 enumerated three failed-observation
    error-message surfaces (Tool / Embedding / Retriever, §8.4.5 / §8.4.6 / §8.4.7) and **explicitly excluded**
    the LLM Generation, on the rationale that a Generation's error *output* is the payload-gated
    `generation.output` (§8.4.3). That rationale holds only for `structured_output_invalid`; every other
    failure category carries **no** output, leaving the raised exception's `error_message` — which
    `LlmFailedEvent` (§5.5.7) carries and which an implementation may write to `observation.metadata` — as an
    ungated harvested surface. Broaden the §6 harvested-channel lead-in citation and the error-message channel
    bullet to include the failed Generation (§8.4.3). The per-emission error-message rule and the suppress-all
    clause are already phrased generically ("a failed observation's `error_message` / `error_type`") and need
    no change.
  - spec/observability/spec.md **§8.4.2** — rewrite the `error_type` / `error_message` → `observation.metadata`
    row (added by 0117) to cover the failed **Generation / Embedding / Tool / Retriever** observations; remove
    the "LLM Generation observations carry only `error.category`" exclusion; keep the **node `Span`** exclusion
    (a node Span harvests no provider exception — its category is the graph-engine §4.2 mapping); note that a
    failed Generation's `error_message` (the exception string) is **distinct** from any payload-gated
    `generation.output`.
  - spec/observability/spec.md **§8.4.3** — add a *Failed Generation error message* note: every failed
    Generation (any category, from `LlmFailedEvent` §5.5.7) carries `error_type` / `error_message` in
    `observation.metadata`, **subject to §6's error-message rule** (omitted, category only, to a
    not-established-isolated provider unless the caller accepted a shared provider); distinct from the
    `structured_output_invalid` gated output; error **category** always retained (a Generation has one, unlike
    a Tool failure).
  - spec/observability/spec.md **§8.4 (mapping intro) + §6 + §8.4.2** — state the **exhaustive-mapping /
    over-emission rule** (elevating 0117 Open Question #2 to normative): the §8.4.x tables are the *complete*
    definition of the **harvested content** openarmature renders to Langfuse, so a harvested error message /
    content field is emitted **only** where a table maps it (there, subject to §6's rule), and harvested
    content the tables do **not** map — a graph-mechanism / marker span's exception message (e.g. the
    failure-isolation marker, pipeline-utilities §6.3), a stacktrace — is non-conforming over-emission that
    **MUST NOT** be written to any Langfuse observation (its detail goes to openarmature's OTel span via
    `record_exception`). The rule governs **harvested** content only; caller-**attached** dimensions (e.g. the
    failure-isolation `event_name`, and the §6-exempt `correlation_id` / `session_id` / `userId` / caller
    metadata) stay governed by the harvest-vs-attach exemption (§3.4, 0117), not this rule. Generalize the
    §8.4.2 node-`Span` exclusion to **all** graph-mechanism / marker spans, and note in §6 that the
    harvested-channel set is closed by the mapping tables. This closes the invariant's channel enumeration — a
    second finding (the failure-isolation marker) after the LLM Generation confirmed that
    enumeration-by-observation-type keeps missing emission sites.
  - spec/conformance-adapter/spec.md **§6.4** — broaden the payload-bearing predicate from "a **failed
    observation's** `error_type` / `error_message`" to "**any observation** carrying a harvested `error_type` /
    `error_message`," so it flags a marker span's leaked exception message, not only the four provider failure
    observations. A clarifying broadening of the existing 0117 classification — no new directive.
  - spec/observability/conformance/158-langfuse-payload-leak-fail-closed.{yaml,md} — add
    `llm_failure_omitted_on_shared` (a wire-level LLM failure, provider 503 → `provider_unavailable`, on the
    primed shared provider, locked down, whose failed Generation reaches the global provider at ERROR with its
    category retained as `statusMessage` but `error_type` / `error_message` omitted), and
    `failure_isolation_error_message_omitted_on_shared` (a node wrapped in failure-isolation fails on the
    primed shared provider, locked down; `no_payload_bearing_langfuse_observations_on_global` asserts the
    caught exception's message does not reach the shared provider — gating the over-emission rule for the
    marker span).
  - spec/observability/conformance/159-langfuse-llm-failure-error-message.{yaml,md} — new fixture: the
    **positive-emission** baseline. A failed Generation on a **normal** (non-shared) provider carries
    `error_type` / `error_message` in `observation.metadata` (the LLM sibling of the embedding / rerank
    failure fixtures 137 / 138). This gates §8.4.3's new mapping and makes 158's `llm_failure_omitted_on
    _shared` non-vacuous — 159 proves the Generation emits the fields on a normal provider, 158 proves they
    are omitted to a shared one.
- **Related:** 0117 (the payload-leak invariant this extends to a fourth harvested channel), 0116 (the
  invariant), 0058 (`LlmFailedEvent` §5.5.7 — the source of the Generation's `error_type` / `error_message`),
  0050 (the failure-isolation marker whose over-emission the general rule resolves), 0043 (the
  harvested-vs-attached lineage)
- **Supersedes:**

## Summary

Proposal 0117 broadened the mode-(b) payload-leak invariant (observability §6) from the provider payload to
**every channel through which openarmature emits payload it harvested from the runtime**, and enumerated the
failed-observation **error message** as one such channel — but scoped it to the **Tool / Embedding /
Retriever** observations and **explicitly excluded the LLM Generation**. The exclusion rested on a single
sentence: a Generation's error *output* is the payload-gated `generation.output` (§8.4.3), so no separate
error-message channel was thought necessary.

That rationale is too narrow. §8.4.3 populates `generation.output` **only** on a `structured_output_invalid`
failure — "every other failure category carries no response, so its failed Generation has `output` / `usage`
absent." For a `provider_invalid_request` (4xx), a timeout, or a `provider_unavailable` (5xx), the failed
Generation has **no output at all**, and the only harvested error content is the raised exception's
`error_message` / `error_type`, which `LlmFailedEvent` (§5.5.7) carries and which an implementation may write
to `observation.metadata` — ungated by any privacy knob, exactly as the Tool / Embedding / Retriever error
messages were before 0117. A provider 4xx can quote the request or the flagged prompt; a wrapped exception can
echo application state. By 0117's own **harvested-vs-attached** principle, the LLM error message is harvested
payload.

This proposal does two things. First, it adds the failed LLM Generation to the error-message channel, gated
identically — the fourth **mapped** provider-observation channel. Second — because a delta review then
surfaced a *fifth* harvested error-message site with the **same shape** (the **failure-isolation marker
span**, an ungated `caught_exception.message` on a graph-mechanism span the §8.4.x tables do not map) — it
stops patching channel-by-channel and states the **general rule** that closes the enumeration: openarmature's
rendering of *harvested content* to Langfuse is *exhaustively* the §8.4.x tables (0117 Open Question #2, here
made normative), so harvested content the tables do **not** map is non-conforming over-emission that MUST NOT
be emitted, its detail going to the isolated OTel `record_exception` side. (Caller-*attached* dimensions such
as the failure-isolation `event_name` remain governed by the harvest-vs-attach exemption, not this rule.) It
does **not** supersede 0117; it corrects the one
over-narrow scoping decision (the LLM Generation) and closes the surface so no future emission site can
silently become an ungated leak channel.

## The organizing principle (unchanged from 0117)

openarmature guards the payload it **harvests** from the runtime and emits; it does **not** police the
dimensions and tags the caller **deliberately attaches**. The raised exception's `error_message` on a failed
provider call is harvested payload — openarmature extracts it from the provider boundary; the caller never
handed it over as an observability dimension. The LLM Generation is the fourth such provider observation
(alongside Embedding / Tool / Retriever), and 0117's error-message channel should have covered it.

## Motivation

**The exclusion and why it was too narrow.** 0117 §8.4.2 scoped the error-message row to
"Embedding / Tool / Retriever observations **only**," adding: "node `Span` and `Generation` observations carry
only `error.category` here (a Generation's error *output*, where present, is the payload-gated
`generation.output`, §8.4.3)." The parenthetical is the whole justification, and it is conditional — "where
present." §8.4.3's *Failed Generation for `structured_output_invalid`* note is explicit that the output is
present **only** for that one category: "Every other failure category carries no response, so its failed
Generation has `output` / `usage` absent." So for a 4xx / timeout / 5xx failure there is no
`generation.output` to carry the error, and the exception's `error_message` — which `LlmFailedEvent` §5.5.7
carries as a first-class field — is the sole harvested error content on the Generation.

**It is ungated, exactly like the other three were.** `error_message` is absent from §5.5.4's
`disable_provider_payload` enumerated set (that set covers input messages, `request_extras`, and the
structured-output output — not the error string). So a fully-locked-down configuration
(`disable_provider_payload=True`, `disable_state_payload=True`, no hooks) that hits an LLM failure still
exports the exception message to every processor on a shared provider — the identical leak 0117 closed for
Tool / Embedding / Retriever, on the one provider observation 0117 left open.

**The gated output is a distinct surface, not a substitute.** The `structured_output_invalid`
`generation.output` (the model's raw output, payload-gated per §5.5.4) and the exception `error_message` (the
raised exception's string, §5.5.7) are two different harvested surfaces. They co-occur only on
`structured_output_invalid`; on every other failure category the output is absent and the error message stands
alone. Gating the output (which §5.5.4 already does) does not gate the error message.

**Nothing is lost by omitting it from Langfuse.** As with the other three channels, openarmature's OTel
observer `record_exception`s the full exception (message + stacktrace) onto openarmature's **private**
`TracerProvider` (§6, and 0117 Open question #2), which is isolated from any shared provider by construction
and flows to the caller's OTel backend. Omitting the message from a *shared Langfuse* provider declines only
to duplicate it where it would leak; the caller still has the full error on their OTel backend, and the error
**category** remains on the Langfuse Generation. The argument is for **consistency and completeness**, not for
discarding the message.

**The second finding, and why enumeration is the wrong shape.** A pre-merge delta review of the 0117 build
then surfaced a *fifth* harvested error-message site — the **failure-isolation marker span**.
`FailureIsolationMiddleware` (pipeline-utilities §6.3) emits an `openarmature.failure_isolated` marker when a
node's exception is caught and isolated; the bundled Langfuse observer writes the caught exception's message
(`str(exc)`) onto that marker unconditionally, outside the 0117 gate. Under the full default privacy posture,
a node exception carrying PII or an API error body then reaches a shared provider — the sharpest
default-posture leak yet. It has the **same shape** as the LLM finding — the enumeration listed observation
*types* and missed a *site* the harvest-vs-attach principle covers — but a different structural category: the
marker is a **graph-mechanism span**, not a provider observation. Two consecutive findings of that shape say
the method (enumerate observation types, gate each) will keep missing sites. So this proposal stops
enumerating and states the rule that closes the surface (Detailed design, *exhaustive-mapping rule*).

## Detailed design

### §6 — add the failed Generation to the error-message channel

Two edits, both additive:

- **Harvested-channel lead-in** (the paragraph listing what a shared provider's exports carry) — broaden the
  exception-message citation from `(§8.4.5–§8.4.7)` to `(§8.4.3 / §8.4.5–§8.4.7)`.
- **The error-message channel bullet** — from "on a failed Embedding / Tool / Retriever observation (§8.4.5 /
  §8.4.6 / §8.4.7)" to "on a failed **LLM Generation** / Embedding / Tool / Retriever observation (§8.4.3 /
  §8.4.5 / §8.4.6 / §8.4.7)."

The **per-emission error-message rule** and the **suppress-all** clause already read "a failed observation's
`error_message` / `error_type`" generically, and already say "It retains only the observation's error
**category** where one exists" — a failed Generation has a category (§5.5.7), so it retains its
`statusMessage` exactly as Embedding / Retriever do; only the Tool carve-out (no category) is special. Neither
clause changes.

### §8.4.2 — the error row covers the four provider observations

Rewrite 0117's `error_type` / `error_message` row to name the failed **Generation / Embedding / Tool /
Retriever** observations (§8.4.3 / §8.4.5 / §8.4.6 / §8.4.7; from `LlmFailedEvent` §5.5.7 /
`EmbeddingFailedEvent` §5.5.9 / `ToolCallFailedEvent` §5.5.12 / `RerankFailedEvent` §5.5.14), still subject to
§6's error-message rule. Remove the "Generation observations carry only `error.category`" exclusion. **Keep**
the node `Span` exclusion — a node Span is not a provider observation, harvests no provider exception, and
carries only its §4.2 graph-engine `error.category`. Note that on a failed Generation the `error_message` (the
exception string) is **distinct** from any payload-gated `generation.output` (§8.4.3): `structured_output_
invalid` carries both, every other failure category carries only the error message.

### §8.4.3 — Failed Generation error message

Add a note after the *Failed Generation for `structured_output_invalid`* paragraph: independently of the
response-side output, every failed Generation — any category, from the graph-engine §6 `LlmFailedEvent`
(§5.5.7) — carries `error_type` / `error_message` in `observation.metadata`, **subject to §6's per-emission
error-message rule** (omitted, error category retained, to a provider openarmature has not established is
isolated, unless the caller accepted a shared provider). The `error_message` is a harvested surface distinct
from the payload-gated `generation.output`: `structured_output_invalid` carries both; every other category
(e.g. `provider_invalid_request`, a timeout, `provider_unavailable`) carries no output, so the error message
is the Generation's only harvested error content. Unlike a Tool failure (no category, §8.4.6), a failed
Generation always has an error category (§5.5.7), so it retains its `statusMessage` when the message is
omitted.

### §8.4 + §6 — the exhaustive-mapping rule (closing the surface)

The recurring findings share a root cause 0117 already named but left as an open question: **openarmature's
Langfuse rendering is defined *exhaustively* by the §8.4.x mapping tables** (0117 Open Question #2 — "a
stacktrace on the Langfuse side would be non-conforming over-emission"). This proposal elevates it to a
normative rule.

- **§8.4 (mapping intro)** — state it: the §8.4.x tables are the *complete* definition of the **harvested
  content** openarmature renders to Langfuse. A harvested error message / content field is written to a
  Langfuse observation **only** where a table maps it (there, subject to §6's error-message rule). Harvested
  content **no** table maps — a graph-mechanism / marker span's exception message (e.g. the failure-isolation
  marker, pipeline-utilities §6.3), a stacktrace — is **non-conforming over-emission** and **MUST NOT** be
  written to any Langfuse observation; that exception detail is surfaced only on openarmature's OTel span via
  `record_exception` (§6, the private provider isolated by construction). The rule governs **harvested**
  content only — caller-**attached** dimensions (the failure-isolation `event_name`, and the §6-exempt
  `correlation_id` / `session_id` / `userId` / caller metadata) stay governed by the harvest-vs-attach
  exemption (§3.4, 0117), not by this rule. The §6 invariant's set of harvested channels is therefore closed
  **by the mapping tables**, not by a per-capability enumeration.
- **§8.4.2** — generalize the node-`Span` exclusion: a node `Span` **and any other graph-mechanism / marker
  span** (e.g. the failure-isolation marker) carries only `error.category` here; a harvested exception message
  on such a span is over-emission per the §8.4 rule and MUST NOT be emitted.
- **§6** — note that the three enumerated harvested channels are the fields the §8.4.x tables map; the set is
  closed by those tables, and harvested content they do not map is forbidden outright (over-emission), not a
  further gated channel.

This makes the failure-isolation marker a **resolved case rather than a fifth channel**: its `error_message`
is not a channel to gate but an over-emission to remove (its detail is already on the OTel `record_exception`
side). Any future emission site is likewise either mapped-and-gated or forbidden — it cannot silently become
an ungated leak — so a newly found site is an implementation over-emission bug the spec already forbids, not a
new proposal.

### Fixtures

**New fixture 159 — the positive-emission baseline.** `159-langfuse-llm-failure-error-message` is the LLM
sibling of the embedding / rerank failure fixtures (137 / 138): a failed Generation on a **normal**
(non-shared) provider — `mock_llm` status 503 → `provider_unavailable`, `disable_provider_payload: true` —
renders at `level: ERROR` with `statusMessage: "provider_unavailable"`, `input` / `output` `null`, and
`metadata.error_type` / `metadata.error_message` **present** (asserted by format `<any-string>`, per the 073 /
137 / 138 idiom — the values are impl-sourced). This gates §8.4.3's new failed-Generation error-message
mapping directly, and is what makes 158's omission case below **non-vacuous**: without a fixture proving the
Generation emits the fields on a normal provider, an implementation that never emits them at all would satisfy
the omission assertion trivially.

**Extend 158.** Add `llm_failure_omitted_on_shared` *(all adapters — ungated; the omission outcome is
identical for detected-shared and cannot-establish)*: `mode: credentials`, `preexisting_same_key_client: true`,
`caller_global_otel_active: true`, both payload knobs at their locked-down default
(`disable_provider_payload: true`), no opt-out. A mocked LLM call fails at the wire (`mock_llm` status 503 →
`provider_unavailable`, as in fixture 069). No construction-determinable channel is live, so openarmature does
**not** raise (locked down). The failed Generation observation reaches the global provider
(`langfuse_observations_on_global: true`) at `level: ERROR` with `statusMessage: "provider_unavailable"`
(category retained — not payload) but `error_type` / `error_message` omitted
(`no_payload_bearing_langfuse_observations_on_global: true`); the LLM failure itself propagates as
`expected_error: {category: provider_unavailable}`. The non-vacuity trio (observation present, ERROR-level,
category retained) distinguishes per-message omission from category-drop and from whole-observation drop —
the LLM analogue of `error_message_omitted_on_shared` (rerank), and the parallel that shows the Generation
keeps its category where the Tool case (`tool_failure_omitted_on_shared`) asserts `statusMessage: null`.

Also add `failure_isolation_error_message_omitted_on_shared` *(all adapters)*, gating the exhaustive-mapping
rule for the marker span: a node wrapped in failure-isolation middleware
(`middleware: {per_node: [{type: failure_isolation, degraded_update, event_name}]}`) fails on the primed
shared provider, locked down (`disable_provider_payload: true`), no opt-out. The node's caught exception
carries a message; the run completes degraded (no isolation raise — the app is locked down).
`no_payload_bearing_langfuse_observations_on_global: true` asserts the caught exception's message does **not**
reach the shared provider — a conforming implementation writes no `error_message` on the marker, a
non-conforming one that does fails the payload-bearing assertion. This case depends on the §6.4 payload-bearing
predicate **broadened above** to inspect *any* observation's `error_message` (a marker span is not one of the
four provider failure observations the 0117 predicate names), so the broadening is what gives this case teeth
rather than a vacuous pass. (The `middleware` + failure-isolation directives exist since proposals 0050 /
0084; an adapter may also need to wire failure-isolation into its Langfuse-observer harness path.)

## Conformance test impact

Additive MINOR. No new directives (`mock_llm` failure, the failure-isolation `middleware` directive, and the
leak assertions all exist since proposals 0050 / 0058 / 0116 / 0117); one new fixture (159, the
positive-emission baseline) and two new cases on fixture 158 (the LLM shared-provider omission and the
failure-isolation over-emission); no existing assertions change. The exhaustive-mapping rule elevates 0117's
Open Question #2 to normative — it **forbids** emission rather than adding a gated channel, so it needs no new
directive. The 0117 payload-bearing classification names "a failed observation's `error_type` / `error_message`"
(§6.4), which covers the LLM Generation (a failed provider observation) as-is; the one small adapter edit is
**broadening that predicate to "any observation carrying a harvested `error_type` / `error_message`"** so it
also flags a marker span's leaked message — a clarifying broadening of the existing classification, not a new
directive.

## Alternatives considered

1. **Keep the Generation excluded; drop the implementation's `metadata["error_message"]` emission.** Rejected:
   it leaves the Langfuse Generation showing only a category on failure while the sibling Tool / Embedding /
   Retriever failures show a gated message — an inconsistency with no principled basis. The error message is
   harvested payload by 0117's principle; the right move is to gate it (emit where isolated, omit where it
   would leak), matching the other three, not to discard it. (Nothing is lost either way — the OTel side
   carries the full exception — but that argues for consistency, not for dropping.)
2. **Gate the error message only where there is no gated output** (i.e. skip it for `structured_output_
   invalid`). Rejected: the exception `error_message` and the model `generation.output` are distinct harvested
   surfaces; making the error-message gate conditional on whether the *other* channel is populated is a
   fragile carve with no privacy benefit (both are gated regardless). Uniform gating of the error message
   across all failure categories is simpler and complete.
3. **Also open a node `Span` (or marker-span) error-message channel.** Rejected: these are graph-mechanism
   spans, not provider observations — the §8.4.x tables map them no `error_message` field, so under the
   exhaustive-mapping rule a harvested exception message on them is over-emission (MUST NOT emit), not a
   channel to gate; their exception detail reaches the OTel side via `record_exception` on the private
   provider. The four provider observations (Generation / Embedding / Tool / Retriever) are the
   harvested-provider-payload surfaces; a mechanism span is the graph-engine's own category surface.
4. **Gate the failure-isolation marker's `error_message` as a fifth *gated* channel** (parity with the four
   provider observations — python's initial lean). Rejected in favor of the exhaustive-mapping rule: the
   marker is a graph-mechanism span, the sibling of the node `Span` (category-only), not a provider
   observation. Treating it like one would (a) make an *isolated* node failure show *more* detail in Langfuse
   than an ordinary node failure (which is category-only), and (b) keep the leak-prone per-emission burden
   that produced these findings. The general rule is more robust: a mechanism span carries no harvested
   message at all — nothing to forget to gate — and the same rule forecloses a sixth site without a sixth
   proposal. The caught exception's full detail remains on the OTel `record_exception` side, exactly where an
   ordinary node exception already lands.

## Open questions

1. **The surface is closed by the exhaustive-mapping rule, not by enumeration.** The four *mapped* provider
   observations (Generation / Embedding / Tool / Retriever) gate their harvested error message, alongside the
   provider-payload and state channels; everything else openarmature harvests is governed by the §8.4
   exhaustive-mapping rule — mapped-and-gated, or unmapped-and-forbidden (over-emission). The failure-isolation
   marker was the second finding that drove this generalization; a *sixth* emission site, if one exists, is
   already resolved by the rule (remove the over-emission) without a new proposal, and openarmature's own
   sweep of its observer handlers against the rule is the one-time check. A future capability that wants to
   *newly surface* a harvested field in Langfuse adds a §8.4.x mapping via its own proposal — a feature
   addition, decided by the harvested-vs-attached test (0117 Open question #1), not a leak patch.
