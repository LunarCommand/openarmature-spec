# Privacy and Payload Controls

What OpenArmature emits to an observability backend, which parts a developer can switch off, and which data
is not controllable by design.

This page is the readable explainer. The normative source lives in
[`spec/observability/spec.md`](capabilities/observability.md): the flag names, their defaults, the
exact attribute sets each one suppresses, and the isolation obligations. This page is for developers
deciding how to configure an observer, and for implementers who want the mental model before the
section numbers.

## Two independent questions

Most confusion in this area comes from treating one question as if it were the other. They have
different mechanisms and different owners.

**What gets emitted?** Governed by *privacy knobs* the developer sets on an observer. Each knob names
a category of harvested data and suppresses it. The defaults are conservative: payload is off out of
the box. This axis never asks where the data goes, only whether a field is written at all.

**Where does it go?** Governed by the *payload-leak invariant*
([§6](capabilities/observability.md#6-driving-span-lifecycle)). It never judges whether data is
sensitive. It asks only whether OpenArmature's Langfuse observations could reach a `TracerProvider`
shared with the application, and if so prefers, in order: isolate the provider → raise where the
binding is detectable → suppress where it is not → unless the caller explicitly accepted a shared
provider.

Knobs are the *what*. The invariant is the *where*. They are independent questions, but they are not
independent mechanisms, and the overlap is worth knowing. A knob decides whether a field is written at all, so
turning payload off also removes what the invariant would have had to protect: under the default posture there
is nothing harvested for a shared provider to leak. And the invariant can withhold a field the knob permitted,
because where openarmature cannot establish that its Langfuse client is isolated, it suppresses every
harvested channel regardless of your knob settings. So the knobs set the ceiling on what may be emitted, and
the invariant can lower it further.

## The controls

[§5.5.4](capabilities/observability.md#554-opt-out-flags) defines three flags on the OpenTelemetry observer.
Two of them, `disable_llm_spans` and `disable_provider_payload`, exist **twice**: the Langfuse observer carries
its own copy, set independently, because the two backends make their own emission decisions from the same
source event. So `disable_provider_payload` on the OpenTelemetry observer governs span attributes, while the
Langfuse observer's copy governs Langfuse fields, including the failed-call error message.
`disable_genai_semconv` is the exception: §8.9 makes it meaningful only to the OpenTelemetry observer, since
the GenAI semantic conventions have no Langfuse-side equivalent. The state knob
and its two hooks are Langfuse-only
([§8.4.1](capabilities/observability.md#841-trace-level-mapping-sourced-from-invocation-span-attributes)), and
the shared-provider acknowledgment belongs to the invariant
([§6](capabilities/observability.md#6-driving-span-lifecycle)). If you want payload out of both backends, set
the flag on both observers.

| Control | Default | Effect |
|---|---|---|
| `disable_provider_payload` | `True` (payload off) | Suppresses the provider transcript: prompts, completions, tool arguments and results, embedding inputs, rerank query and documents, as span attributes and the equivalent Langfuse fields. On the Langfuse observer's copy, also withholds a failed call's harvested exception text (`error_message`), leaving `error_type` and the error category. |
| `disable_state_payload` | `True` (payload off) | Suppresses the Langfuse Trace's `input` / `output` carrying raw application state. The minimal stub applies instead. |
| `trace_input_from_state` / `trace_output_from_state` | not supplied | Caller hooks turning state into a domain-shaped summary. A supplied hook returning non-null emits **regardless** of `disable_state_payload`. |
| `disable_genai_semconv` | `False` (attributes on) | Suppresses the GenAI semantic-convention attributes, leaving `openarmature.*` attributes only. For when an external library is the canonical GenAI emitter. |
| `disable_llm_spans` | `False` (spans on) | Stops OpenArmature emitting an LLM span at all, for when external auto-instrumentation is canonical. The other two flags then have no LLM span left to act on, though they still govern embedding, tool, and rerank emission, and the Langfuse observer's own copies are unaffected. |
| the shared-provider acknowledgment (`accept_shared_provider` in conformance fixtures) | off | **Not a privacy knob.** An acknowledgment that OpenArmature's Langfuse data may reach a provider shared with the application: it turns the invariant's hard failure into a warning. |

The two payload knobs are deliberately separate rather than one combined flag, because they carry
different threat models. The provider payload is the model-interaction transcript, while the state
payload is the shape of the application's own data. An implementation may offer a convenience flag
setting both, but a caller must be able to enable one without the other.

The shared-provider acknowledgment is the one control that is not about privacy at all. The spec mandates that
such an opt-in exist and defaults to off, but leaves its exact spelling to each implementation; the
conformance fixtures address it as `accept_shared_provider`, so check your implementation for its own name. It
grants permission on the *where* axis, and the framework must default to the protective behaviour and never infer this
setting from context.

## How the Trace state field resolves

Applied independently to `trace.input` and `trace.output`. This is a precedence order, so the first
match wins
([§8.4.1](capabilities/observability.md#841-trace-level-mapping-sourced-from-invocation-span-attributes)).

1. **A hook is supplied and returns a non-null value** → that value is serialized. This beats the
   knob, which is why a supplied hook counts as potentially payload-bearing regardless of the knob's
   setting.
2. **Otherwise, `disable_state_payload` is off** → the raw state object is serialized, subject to the
   payload byte cap.
3. **Otherwise (the default)** → the minimal stub, built only from graph identifiers (the entry node
   and correlation ID for input; the final node and a status enum for output). It carries no
   application payload, so it is privacy-safe by construction.

## What is controllable, and what is not

Not everything OpenArmature writes is developer-controllable, and the reasons differ.

| Data | Developer switch | Notes |
|---|---|---|
| Provider payload | yes | `disable_provider_payload`. Also drives the invariant's construction-time raise or suppress. |
| Trace state payload | yes | `disable_state_payload`, or a supplied hook. Suppression forces the minimal stub. |
| A failed call's `error_message` | yes | The Langfuse observer's `disable_provider_payload` covers the harvested exception text, so the default posture withholds it. Full exception detail still reaches your OpenTelemetry backend through `record_exception`. |
| A failed call's `error_type` | no, by design | A classification token (a vendor code or exception class name), not harvested text, so no flag withholds it. It is an optional field: where the provider supplies no type it may legitimately be absent. Where it is present it is the only failure discriminator on a Tool observation, which has no error category. |
| The error **category** (`level` / `statusMessage`) | not applicable | Not payload. Retained even where the message beside it is omitted. |
| Caller-attached dimensions: `correlation_id`, `session_id`, the promoted `userId`, trace name, caller metadata | not applicable | Exempt by design. The caller attached these deliberately as observability dimensions and owns their content; they are cross-backend join keys, so the framework must not suppress or refuse on account of them. |
| Runtime identity: `spec_version`, implementation name and version, entry node | not applicable | Always emits. Privacy knobs gate runtime *data*, not runtime *identity*. |

The exemption for caller-attached dimensions follows the **harvested-versus-attached** principle:
OpenArmature guards the payload it *harvests* from the runtime, and does not police the dimensions
the caller *deliberately attaches*. Suppressing a caller's own join keys would break the
cross-backend correlation those identifiers exist for.

The same principle bounds what the Langfuse mapping may emit at all: the
[§8.4](capabilities/observability.md#84-attribute-mapping-table) tables are the complete definition
of the harvested content OpenArmature renders to Langfuse. Harvested content no table maps is
non-conforming over-emission rather than a further gated channel. A field is either mapped, and
therefore governed by the knobs and the invariant, or it is not written.

## Where the normative text lives

- [§5.5.4 *Opt-out flags*](capabilities/observability.md#554-opt-out-flags): the OpenTelemetry
  observer flags, their defaults, and the exact attribute set each suppresses.
- [§6 *Driving span lifecycle*](capabilities/observability.md#6-driving-span-lifecycle): the
  payload-leak invariant, covering provider isolation, the raise and suppress arms, and the shared-provider
  acknowledgment.
- [§8.4.1 *Trace-level mapping*](capabilities/observability.md#841-trace-level-mapping-sourced-from-invocation-span-attributes):
  the state knob, both hooks, the precedence order, and the minimal stub.
- [§8.4 *Attribute mapping table*](capabilities/observability.md#84-attribute-mapping-table): the
  per-observation mappings, including where each failed call's error fields land.
- Conformance fixtures `157`, `158`, and `159` under `spec/observability/conformance/`: the
  executable form of the isolation and payload-gating behaviour.
