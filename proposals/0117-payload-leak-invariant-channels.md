# 0117: Broaden the Langfuse Payload-Leak Invariant to All Harvested-Payload Channels

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-08
- **Targets:**
  - spec/observability/spec.md **§6 Driving span lifecycle** — broaden proposal 0116's mode-(b) payload-leak
    invariant so it covers **every channel through which openarmature emits payload it *harvested* from the
    runtime**, not only the provider-payload channel: the Generation/Embedding/Tool/Retriever provider payload
    (`disable_provider_payload`, §5.5.4), the Trace-level **state payload** (`disable_state_payload`, §8.4.1,
    plus the `trace_input_from_state` / `trace_output_from_state` hooks), and the **error message** written to
    `observation.metadata` on failed Tool / Embedding / Retriever observations (§8.4.5 / §8.4.6 / §8.4.7,
    currently ungated). Add a scoping clause **exempting** the caller-supplied identity/correlation dimensions
    and tags (`correlation_id`, `session_id`, `userId`, trace name, arbitrary caller metadata) as caller-owned
    and cross-backend-by-design. Fix the now-inaccurate "when the observer does not emit payloads … only
    metadata and span structure" clause, **and reconcile the three section-level §6 paragraphs that still
    carry the provider-only framing** — the subsection lead-in, the *No hard failure* block, and the
    *isolation trade-off* paragraph.
  - spec/observability/spec.md **§8.4.1** — cross-reference the Trace input/output state channel to §6's
    invariant.
  - spec/observability/spec.md **§8.4 header + §8.4.5 / §8.4.6 / §8.4.7** — qualify the header's blanket
    "implementations MUST set the corresponding Langfuse fields when the source attribute is set" and each
    section's unconditional "`error_type` / `error_message` in metadata" sentence as **subject to §6's
    error-message rule** (omitted to a not-established-isolated provider, category only), so §8.4 does not
    mandate on failure the emission §6 forbids.
  - spec/observability/spec.md **§8.4.2** — add the `error_type` / `error_message` → `observation.metadata`
    mapping row that §8.4.5 / §8.4.6 / §8.4.7 cite as "the generic §4.2 / §8.4.2 error mapping" but which the
    §8.4.2 table does not actually contain (it maps only `error.category`), scoped to the failed provider
    observations that carry it — resolving a dangling cross-reference and pinning where the error-message
    channel lives.
  - spec/conformance-adapter/spec.md **§5.5 / §6.4** — the `{no_,}payload_bearing_langfuse_observations_on
    _global` assertions and the §6.4 fake's payload-bearing/payload-free distinction cover the state payload
    and a failed observation's `error_message` (payload-bearing), and count the §8.4.1 minimal stub and a
    category-only failed observation as payload-free. State-channel and failure directives already exist
    (proposals 0043 / 0107, fixtures 037 / 150-151).
  - spec/observability/conformance/158-langfuse-payload-leak-fail-closed.{yaml,md} — add cases for the state
    channel, the hook, the error-message omission, and state-channel suppression.
- **Related:** 0116 (the payload-leak invariant this broadens), 0043 (the Trace state channel), 0034
  (caller-supplied invocation metadata — the exemption), 0020 (sessions / `session_id` — the exemption),
  0114 / 0115
- **Supersedes:**

## Summary

Proposal 0116 established a payload-leak invariant for openarmature's Langfuse observations in mode (b) (the
implementation constructs the client): openarmature's payload MUST NOT reach a provider shared with the
application. But 0116 keyed it on **one** channel — the Generation-level provider payload
(`disable_provider_payload`). A systematic sweep of openarmature's whole Langfuse observation surface (Trace,
Span, Generation, Embedding, Tool, Retriever) found **two more channels through which openarmature emits
payload it harvested from the runtime**, both of which 0116's guard misses:

1. the **Trace-level state payload** — Trace `input` / `output` carrying raw application state (proposal
   0043), gated by a separate `disable_state_payload` knob plus `trace_*_from_state` caller hooks that emit
   regardless of the knob; and
2. the **error message** — `error_type` / `error_message` written into `observation.metadata` on failed
   **Tool**, **Embedding**, and **Retriever** observations (§8.4.5 / §8.4.6 / §8.4.7), gated by **no** privacy
   knob (`error_message` is absent from `disable_provider_payload`'s enumerated set, §5.5.4). An exception
   message can echo tool arguments, application state, or a secret, so on an un-isolatable client it leaks the
   same class of data — even under the full default privacy posture.

The sweep also drew the boundary: **caller-supplied identity/correlation dimensions and tags** —
`correlation_id`, `session_id`, `userId`, trace name, and arbitrary caller metadata (§3.4, §8.4.1 / §8.4.2) —
are **not** harvested payload. The caller deliberately attaches them as observability dimensions, they are
opaque join keys **cross-backend by design** (§2's cross-backend correlation exists precisely so the same
`correlation_id` / `sessionId` / `userId` appears in Langfuse *and* the caller's OTel backend), and the
§8.4.1 privacy-safe minimal stub is itself built from `entry_node` + `correlation_id`. Guarding them would
break cross-backend correlation and override the caller's own routing.

This proposal broadens the invariant to all three **harvested-payload** channels, adds an explicit exemption
for the caller-owned dimensions, corrects §6's false "only metadata and span structure" claim, and fixes the
§8.4.2 dangling error-mapping reference.

## The organizing principle

openarmature guards the payload it **harvests** from the runtime and emits; it does **not** police the
dimensions and tags the caller **deliberately attaches**.

- **Harvested payload** (in scope) — prompts / completions, embedding inputs / vectors, tool arguments /
  results, rerank query / documents, raw application state, and exception messages. openarmature *extracts*
  these from the runtime and emits them; the caller never handed them over as observability data, and on an
  un-isolatable shared provider the leak is a silent side-effect of openarmature's own mechanism.
- **Caller-attached dimensions** (out of scope) — `correlation_id`, `session_id`, `userId`, trace name,
  arbitrary metadata. The caller chose these keys and values as observability dimensions; they are opaque
  join keys meant to appear across backends. Suppressing them would be openarmature overriding the caller's
  deliberate routing — protecting the developer from themselves — and would break the cross-backend
  correlation those ids exist for.

This is openarmature's standing division applied to data rather than to prompts: the framework owns the
mechanism (what openarmature emits), the developer owns the policy (what they attach).

## Motivation

**Two harvested channels 0116 misses.** 0116 §6 keys the invariant on "the Langfuse observer emits payloads
(`disable_provider_payload=False`)." That is the provider channel. §8.4.1 (proposal 0043) defines a second:
the Trace-level `input` / `output`, serializing `initial_state` / final state when `disable_state_payload` is
OFF, or a caller-hook return value when a `trace_*_from_state` hook is supplied (lever 1 of §8.4.1's decision
tree fires **before** the knob, so a hook emits even under the default posture). §8.4.5 / §8.4.6 / §8.4.7
define a third: a failed Tool / Embedding / Retriever observation writes the raised exception's `error_type`
/ `error_message` into `observation.metadata`. All three ride the **same** Langfuse client's
`TracerProvider`, so on an un-isolatable client all three leak to the shared provider identically. 0116
inspects only the first.

**Why the error message is harvested payload — and the sharpest sub-case.** `error_message` is the raised
exception's message, carried on the failure events of the three provider observations that surface it on the
Langfuse side (§5.5.9 embedding, §5.5.12 tool, §5.5.14 rerank — tool code is arbitrary caller code with no
closed taxonomy; the LLM Generation surfaces no ungated `error_message`, only `error.category`, §8.4.3).
openarmature harvests it; the caller did not tag it. It is gated by **no**
privacy knob (§5.5.4's `disable_provider_payload` set enumerates the input/output payload attributes and does
**not** include `error_message`), so a fully-locked-down configuration (`disable_provider_payload=True`,
`disable_state_payload=True`, no hooks) that hits a tool failure still exports the exception message — which
can echo the tool's arguments or a secret held in state — to every processor on a shared provider.

**Why the caller dimensions are out of scope.** `correlation_id`, `session_id`, and `userId` are
caller-supplied (sessions §: `session_id` is "a caller-supplied string identifier," Origin: Caller; §8.4.1:
openarmature "has no first-class user concept" and merely promotes a caller-supplied `userId` metadata key).
They are the join keys of §2's cross-backend correlation, whose entire purpose is that the same id appears in
Langfuse and the caller's OTel backend so the caller can pivot between them. They are opaque ids in practice,
and the spec already treats this class as safe (the §8.4.1 minimal stub is built from `entry_node` +
`correlation_id`, "privacy-safe by construction"). Suppressing them would break the feature they exist for
and override the caller's deliberate tagging. A caller who puts sensitive content in a metadata tag owns that
choice; it is documented as caller-owned, not an openarmature leak.

**The stale claim.** 0116 §6 says that with `disable_provider_payload=True` the observations carry "only
metadata and span structure." That is false when the state channel is live or a failed provider observation
emits `error_message`. This proposal corrects it.

## Detailed design

### §6 — broaden the trigger to the harvested-payload channels; exempt caller dimensions

In the mode-(b) bullet, replace the opening (that keys on `disable_provider_payload=False` only) with:

> When openarmature constructs the client and would emit a **payload it harvested from the runtime**,
> openarmature **MUST** ensure that payload does not reach a provider shared with the application or other
> instrumentation, **unless the caller has explicitly accepted a shared provider** (below). openarmature's
> harvested-payload channels are:
>
> - the **provider payload** — Generation / Embedding / Tool / Retriever `input` / `output` (prompts,
>   completions, embedding inputs, tool arguments / results, rerank query / documents), live when
>   `disable_provider_payload=False` (§5.5.4);
> - the **state payload** — Trace-level `input` / `output` carrying application state (§8.4.1), live when
>   `disable_state_payload=False`, **or** when a `trace_input_from_state` / `trace_output_from_state` hook is
>   supplied (a supplied hook may emit regardless of the knob, so a supplied hook is treated as potentially
>   payload-bearing); and
> - the **error message** — `error_message` on a failed Tool / Embedding / Retriever observation (§8.4.5 /
>   §8.4.6 / §8.4.7), always potentially present when openarmature emits such observations (see the
>   error-message rule below).
>
> **Out of scope — caller-attached dimensions.** The caller-supplied identity/correlation dimensions and tags
> openarmature carries — `correlation_id`, `session_id`, the promoted `userId`, the trace name, and arbitrary
> caller-supplied invocation metadata (§3.4, §8.4.1 / §8.4.2) — are **not** harvested payload and are **not**
> subject to this invariant. They are dimensions the caller deliberately attaches, opaque join keys that are
> cross-backend by design (§2), and the caller owns their content; openarmature **MUST NOT** suppress or
> refuse on account of them.

The mode-(b) isolate default, the opt-out, and the portable-guarantee paragraph are unchanged in structure;
they now speak of "harvested payload" across all three channels.

### §6 — the construction-time arms cover the provider and state channels

The raise / suppress / opt-out arms are decided at client construction, so they key on the channels
determinable then — the provider and state payloads:

> **Otherwise (not opted in):** openarmature **SHOULD** determine whether the constructed client's
> observations would reach a shared / non-isolated provider (as defined by 0116 — a provider not among those
> openarmature established as isolated for this credential). Where it establishes they would **and** a
> construction-determinable payload channel is live (`disable_provider_payload=False`, or the state channel
> per above), it **MUST raise** `langfuse_provider_isolation_unavailable` before any payload-bearing emission.
> Where it **cannot** establish the binding **and a construction-determinable payload channel is live**, it
> **MUST** suppress **all** harvested-payload channels (below) and emit a `WARNING` log record (§7). (Where no
> such channel is live — the locked-down case — the no-payload clause below governs instead: SHOULD isolate,
> MAY warn, MUST NOT raise; the per-emission error-message rule still applies.) Where it establishes the
> observations reach an isolated provider, it proceeds.

### §6 — the error-message channel: a per-emission omission, not a raise driver

Because a failure is not knowable at client construction, the error-message channel cannot drive the
construction-time raise (refusing a locked-down application because a tool *might* later fail would be
disproportionate). It is handled per-emission:

> **Error-message channel.** openarmature **MUST NOT** emit a failed observation's `error_message` or
> `error_type` to a provider it has not established is isolated (a non-detection-capable implementation cannot
> establish it, so it omits — fail-safe), unless the caller has accepted a shared provider. It retains only
> the observation's error **category** where one exists (the `observation.statusMessage` enum, §8.4.2). A
> failed **Tool** observation has **no** error category (§8.4.6 / §5.5.12); there the observation reaches such
> a provider carrying neither the message nor a message-derived status text — the exception message **MUST
> NOT** be surfaced through `observation.statusMessage` as a substitute for the omitted `error_message`. This
> applies regardless of the payload knobs (the exception message is harvested payload gated by no knob) and
> does **not** itself cause a raise.

### §6 — broaden the suppress arm to all harvested channels

Amend the *cannot establish the binding* arm:

> openarmature **MUST** suppress **all** of its harvested-payload channels so no harvested payload reaches a
> shared provider — the provider payload (as if `disable_provider_payload=True`), the Trace-level state
> payload (forcing the §8.4.1 minimal stub: raw state not serialized and a supplied `trace_*_from_state` hook
> not applied), and a failed observation's `error_message` (omitted, category only) — and **MUST** emit a
> `WARNING` log record (§7).

### §6 — fix the no-payload clause

> When **no** payload channel is live — `disable_provider_payload=True` **and** `disable_state_payload=True`
> **and** no `trace_*_from_state` hook is supplied — a **successful** run's observations carry only metadata
> and span structure; a shared provider then duplicates only that. openarmature **SHOULD** isolate and **MAY**
> warn, but **MUST NOT** raise. (A *failed* provider observation's `error_message` is still governed by the
> error-message rule above — omitted to a non-isolated provider — since it is harvested payload gated by no
> knob.)

### §6 — reconcile the section-level paragraphs

0116's provider-only framing survives in three further §6 paragraphs; they must move with the broadened
trigger or they contradict the new state-channel raise (and 0117's own `state_channel_preexists_raises`
fixture):

- **The subsection lead-in** ("openarmature's Langfuse observations … the obligations track which party
  controls the provider") — reword its payload framing to **harvested payload** (provider payload, state
  payload, or a supplied hook), so the lead-in scopes the whole invariant rather than the provider channel.
- **"No hard failure, except…"** — it currently carves the raise to "the Langfuse observer emits payloads …
  there, and only there" and lists "the no-payload case" among the MUST-NOT-raise cases. Reword the raise
  carve to *a construction-determinable harvested-payload channel (provider or state) is live, openarmature
  establishes it would reach a shared provider, and the caller has not opted in*, and align "the no-payload
  case" with the rewritten no-payload clause (provider off **and** state off **and** no hook) so a
  provider-off / state-on configuration is not mis-read as no-payload (which would forbid the state-channel
  raise). The error-message channel is governed by its per-emission rule, not this carve.
- **"The isolation trade-off"** — reword its "this section requires … where it owns the client" summary to
  enumerate the broadened obligation across the harvested channels (isolate / raise / suppress / omit),
  dropping the provider-payload-only framing.

### §8.4 reconciliation

- **§8.4.1** — add a pointer: when openarmature constructs the client (§8.9 mode b) on a provider shared with
  the application, the Trace-level state payload is subject to §6's payload-leak invariant (raise where
  detectable, suppress — forcing the minimal stub — where not), exactly as the provider payload is.
- **§8.4.2** — add the `error_type` / `error_message` → `observation.metadata` row that §8.4.5 / §8.4.6 /
  §8.4.7 reference, as an **in-cell-scoped** row (per the §8.4.2 table's existing convention for type-scoped
  rows — e.g. the fan-out / parallel-branches rows) naming exactly the failed **Embedding / Tool / Retriever**
  observations whose source failure events carry those fields (§5.5.9 `EmbeddingFailedEvent` / §5.5.12
  `ToolCallFailedEvent` / §5.5.14 `RerankFailedEvent`). Node Span and LLM Generation observations carry only
  `error.category` on the Langfuse side (a Generation's error *output*, where present, is the payload-gated
  `generation.output`, §8.4.3); because the row is in-cell-scoped, §8.4.3's inheritance of the §8.4.2 mapping
  does **not** pull an ungated `error_message` onto Generations. Resolves the dangling "generic error mapping"
  reference and pins the channel to those three observation types.
- **§8.4 header + §8.4.5 / §8.4.6 / §8.4.7** — the §8.4 header's blanket "implementations MUST set the
  corresponding Langfuse fields when the source attribute is set," and each of §8.4.5 / §8.4.6 / §8.4.7's
  unconditional "`error_type` / `error_message` in metadata" sentences, are qualified **subject to §6's
  error-message rule** (omitted to a not-established-isolated provider, category only), mirroring the §8.4.1
  state-channel cross-reference — so §8.4 does not mandate on failure the emission §6 forbids.

### Conformance-adapter §5.5 / §6.4

- **§5.5** — `{no_,}payload_bearing_langfuse_observations_on_global` count as payload-bearing: a Trace
  carrying raw state or a hook value, and a failed observation carrying `error_message`. Payload-free: the
  §8.4.1 minimal stub, and a failed observation carrying only the category enum. State-channel controls use
  the existing `langfuse_observer.disable_state_payload` / `trace_*_from_state` directives (0043 / fixture
  037); a failure is induced with the existing mock-failure directives (0107, `mock_embedding` / `mock_rerank`
  `raises`, fixtures 150-151). No new directive.
- **§6.4** — the provider-faithful fake's payload distinction extends to the Trace state payload and to a
  failed observation's `error_message` (payload-bearing) vs. the stub / category-only observation
  (payload-free).

### Fixtures — extend 158

Add to `158-langfuse-payload-leak-fail-closed` (all `mode: credentials`, `preexisting_same_key_client: true`,
`caller_global_otel_active: true`):

- `state_channel_preexists_raises` *(detection-capable)* — provider off (`disable_provider_payload=True`),
  state on (`disable_state_payload: false`), no opt-out → raises. Trigger fires on the state channel alone.
- `hook_preexists_raises` *(detection-capable)* — both knobs default, a `trace_input_from_state` hook
  supplied, no opt-out → raises. A supplied hook triggers under the full default posture.
- `error_message_omitted_on_shared` *(detection-capable)* — both payload knobs default (no provider/state
  payload), a mock **rerank** failure, no opt-out → does **not** raise (locked down). The failed Retriever
  observation **does** reach the global provider (`langfuse_observations_on_global: true`) but **without**
  `error_message` (`no_payload_bearing_langfuse_observations_on_global: true`), and its error
  **category / `statusMessage` is present** (rerank failures carry a category, unlike Tool). Pairing all
  three assertions proves *message-omitted-but-observation-and-category-present* rather than passing
  vacuously under whole-observation suppression. Gates the error-message omission and the "no raise on a
  locked-down app that merely fails" behavior.
- `state_channel_preexists_suppresses` *(non-detection-capable)* — state on, no opt-out → does not raise; the
  Trace reaches the global provider as the payload-free stub (`no_payload_bearing_langfuse_observations_on
  _global`), with a `WARNING` log record. Suppress forces all channels off.

## Conformance test impact

Additive MINOR. No new directives (the state-channel and failure-mock controls exist since 0043 / 0107); four
new cases on fixture 158; the §6.4 fake's payload distinction is clarified to cover the state and
error-message channels; no existing assertions change; the §8.4.2 edit adds a documentation row for an
already-shipped behavior (the three provider sections already state it). The caller-dimension exemption
requires no fixture (it is an out-of-scope clarification).

## Alternatives considered

1. **Cover the state channel only (the earlier 0117 draft).** Rejected: it patched one of the two missed
   harvested channels and left the error-message leak — which fires even under the full default privacy
   posture — open, and would have needed a third proposal. The systematic sweep is what turned a reactive
   patch into a complete channel enumeration.
2. **Fold caller-supplied metadata / `userId` into the invariant** (guard it too). Rejected: it is not
   harvested payload — the caller deliberately attaches it — and it is a cross-backend join key by design
   (§2); suppressing it would break cross-backend correlation and override the caller's routing (protecting
   the developer from their own tagging). The `accept_shared_provider` opt-out is not even the right lever
   here, since the data is out of scope, not opted-in.
3. **Raise on the error-message channel** (treat a possible future failure as a construction-time payload
   channel). Rejected: a failure is not knowable at construction, so raising would refuse a fully-locked-down
   application because a tool *might* fail — disproportionate. Per-emission omission of `error_message` to a
   non-isolated provider is the proportionate fail-safe.
4. **Suppress the state knob but keep applying a supplied hook.** Rejected (as in the state-only draft): a
   hook's return is arbitrary caller data openarmature cannot vet, so proceeding with it re-opens the leak;
   fail-safe forces the stub, and the caller keeps the hook's value by opting in.

## Open questions

1. **Future harvested channels.** The invariant now enumerates three harvested-payload channels (provider,
   state, error message) and one exemption class (caller dimensions). A future capability that adds another
   field openarmature *harvests* onto a Langfuse observation must register it here; the "harvested payload vs.
   caller-attached dimension" principle is the test for which side a new field falls on.
2. **The OTel-native exception path is out of scope by construction.** §6's observer pseudocode calls
   `record_exception` (stacktrace) — but on openarmature's **own** OTel observer, which §6 binds to a
   **private** `TracerProvider` never registered globally, so it is already isolated from any shared provider.
   openarmature's Langfuse rendering is defined exhaustively by the §8.4.x mapping tables, which contain no
   `record_exception` / stacktrace field; a stacktrace on the Langfuse side would be non-conforming
   over-emission, not an unforeclosed channel. So this proposal does not enumerate it as a Langfuse channel.
