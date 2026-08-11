# 158 — Langfuse Payload-Leak Invariant (fail-closed / suppress / opt-out)

Gates observability §6's mode-(b) **payload-leak invariant** (proposals 0116, 0117, 0118): when openarmature
constructs the Langfuse client and would emit payload it harvested from the runtime — provider payload, the
Trace-level state payload, or a failed observation's error message — that payload MUST NOT reach a provider
shared with the application unless the caller has explicitly accepted a shared provider. Each case primes a
same-credential Langfuse client on the global provider *before* openarmature constructs, so the Langfuse v4
SDK's per-credential singleton hands openarmature the cached client and discards its isolated provider — the
leak condition. openarmature's response depends on whether it can establish the binding (best-effort, since
that introspection rests on non-portable SDK internals) and on the caller opt-out.

The Langfuse client is the provider-faithful fake of conformance-adapter §6.4, extended for 0116/0117 with
per-credential-singleton semantics, a bound-provider accessor, and a payload-bearing vs. payload-free
distinction (payload-bearing = provider payload, Trace-level state payload, **or** a failed observation's
`error_message`; payload-free = the §8.4.1 minimal stub, or an observation carrying only its classifications.
Proposal 0118 narrowed this to the message: `error_type` is a classification token, not harvested text, so it
does not make an observation payload-bearing).

**Spec sections exercised:**

- §6 mode-(b) **raise** arm — where openarmature establishes its payload-bearing observations would reach a
  shared provider and the caller has not opted in, it MUST raise `langfuse_provider_isolation_unavailable`
  before any payload-bearing emission.
- §6 mode-(b) **suppress** arm (the portable floor) — where openarmature cannot establish the binding, it
  MUST NOT raise; it suppresses its own Langfuse-side payload and emits a WARNING, so no payload-bearing
  observation reaches the shared provider.
- §6 mode-(b) **opt-out** — where the caller has explicitly accepted a shared provider, openarmature neither
  raises nor suppresses; it warns and proceeds, and the payload-bearing observation reaches the shared
  provider (the acknowledged leak).
- The widened trigger — the raise keys on the Langfuse payload reaching a shared provider, **independent** of
  any composed OTel observer's suppression setting.
- §6 **harvested-payload channels** (proposals 0117, 0118) — the invariant covers the provider payload, the
  Trace-level **state payload** (`disable_state_payload` or a `trace_*_from_state` hook), **and** a failed
  **LLM Generation** / Embedding / Tool / Retriever observation's **error message**. Proposal 0118 put that
  error message under `disable_provider_payload` alongside the provider payload, so it rides the same channel
  liveness rather than a separate per-emission rule; where it is omitted the observation keeps its `error_type`
  and its error category. The caller-attached dimensions (`correlation_id` / `session_id` / `userId` / trace name /
  metadata) are exempt.
- §8.4 **exhaustive-mapping rule** (proposal 0118) — harvested content the §8.4.x tables do **not** map (a
  stacktrace, or the exception detail on a framework-emitted observer event those tables do not render, e.g.
  the failure-isolation event's `caught_exception`) is over-emission that MUST NOT be written to any Langfuse
  observation, not a further gated channel. Not exercised here: the rule *forbids* an emission the mapping
  tables never defined, so there is no conforming emission to assert against — it is gated by the mapping
  tables themselves (an implementation emitting an unmapped field is non-conforming by §8.4).

**Cases** (all: `mode: credentials`, `preexisting_same_key_client: true`, `caller_global_otel_active: true`;
the 0116 group emits the provider payload, the state cases run with the provider payload off to isolate that
channel, and the two error-message cases run with it on so the suppress arm is what omits the message):

- `singleton_preexists_raises` *(detection-capable adapters)* — OTel observer suppressing (its default), no
  opt-out; asserts `expected_construction_error: {category: langfuse_provider_isolation_unavailable}` **and**
  `no_payload_bearing_langfuse_observations_on_global`.
- `singleton_preexists_raises_otel_not_suppressing` *(detection-capable adapters)* — the OTel observer also
  emits payload (`disable_provider_payload: false`), so there is no OTel-side suppression to "defeat"; still
  raises. Gates the widened trigger. **Note:** proposal 0116 names this case `..._no_otel_observer` ("no OTel
  observer composed"). The observability harness always installs the OTel `SpanExporter` + private provider
  (§6 isolation), so it cannot express "no OTel observer composed"; this case ships the equivalent — and
  strictly stronger — configuration where a composed OTel observer is *not* suppressing, which likewise proves
  the raise is independent of any OTel-side payload setting. Both gate the same OTel-independent mode-(b)
  raise.
- `singleton_preexists_suppresses` *(non-detection-capable adapters)* — no opt-out; does not raise; the
  observation reaches the global provider (`langfuse_observations_on_global`) but **payload-free**
  (`no_payload_bearing_langfuse_observations_on_global`), with a `WARNING` log record. The portable suppress
  floor.
- `singleton_preexists_optout_proceeds` *(all adapters)* — `accept_shared_provider: true`; does not raise or
  suppress; a **payload-bearing** observation reaches the global provider
  (`payload_bearing_langfuse_observations_on_global`) with a `WARNING` log record — the acknowledged leak.

*Proposal 0117 cases, with the two error-message cases repointed by proposal 0118. The state cases keep the
provider payload off; the error-message cases now run with it on, so the suppress arm rather than the flag is
what omits the message. The flag's own effect on the error message is gated by fixture 159:*

- `state_channel_preexists_raises` *(detection-capable)* — provider off, state on
  (`disable_state_payload: false`), no opt-out → raises (`expected_construction_error` +
  `no_payload_bearing_langfuse_observations_on_global`). The trigger fires on the state channel alone.
- `hook_preexists_raises` *(detection-capable)* — both knobs default but a `trace_input_from_state` hook
  supplied, no opt-out → raises. A supplied hook triggers under the full default posture (§8.4.1 lever 1).
- `error_message_omitted_on_shared` *(non-detection-capable; repointed by proposal 0118)* — the provider
  payload is **on**, so the flag permits the harvested error message and the channel is live; the adapter
  cannot establish the binding, so openarmature takes the **suppress** arm rather than raising. A
  `mock_rerank` failure then occurs, and suppress-all must cover the message: the failed Retriever observation
  reaches the global provider (`langfuse_observations_on_global`) but payload-free, with
  `metadata_absent: [error_message]`, its `error_type` and category / `statusMessage` retained, plus the
  mandated `WARNING`. Gates "suppress-all covers the harvested error message." The rerank failure propagates
  as `expected_error: provider_unavailable` (the suppress arm does not raise).
- `tool_failure_omitted_on_shared` *(non-detection-capable; repointed by proposal 0118)* — the same suppress
  configuration with a `mock_tool` failure. A Tool failure has **no** error category (§5.5.12), so this case
  gates §6's Tool anti-smuggling clause under suppression: the Tool observation reaches the global provider at
  ERROR but payload-free with `statusMessage: null`. An impl copying the exception into `statusMessage` fails
  that assertion, and one leaving `error_message` in metadata fails both `metadata_absent` and
  `no_payload_bearing_langfuse_observations_on_global`. The tool failure propagates as `expected_error:
  node_exception`.

- `state_channel_preexists_suppresses` *(non-detection-capable)* — state on, no opt-out → does not raise; the
  Trace reaches the global provider as the §8.4.1 minimal stub
  (`no_payload_bearing_langfuse_observations_on_global`) with a `WARNING`. Portable suppress floor for the
  state channel.
- `hook_preexists_suppresses` *(non-detection-capable)* — a `trace_output_from_state` hook supplied
  (exercising the output-hook spelling; `hook_preexists_raises` uses the input hook, so both §8.4.1 hooks are
  covered), no opt-out → does not raise; the Trace reaches the global provider as the stub — the hook is
  **not** applied — with a `WARNING`. Gates the suppress arm's hook-drop half (the raising hook case never
  reaches rendering).

The *cannot-determine* arm is modeled by a non-detection-capable adapter (`singleton_preexists_suppresses`)
rather than by simulating a real binding-hiding SDK at runtime; the capability declaration is the harness's
portable proxy for that condition, consistent with 0114/0115 treating bound-provider introspection as
non-portable.

**Tool anti-smuggling.** §6's Tool anti-smuggling clause — a failed **Tool** observation (which has no error
category, §5.5.12) MUST NOT surface the exception message through `observation.statusMessage` as a substitute
for the omitted `error_message` — is gated by `tool_failure_omitted_on_shared`, which asserts the Tool
observation's `statusMessage: null` directly (an implementation that smuggles the message there fails),
without needing the §6.4 payload-bearing predicate to inspect `statusMessage`.

**Why the two error-message cases run with the payload flag off (proposal 0118).** They previously ran with it
**on**. Proposal 0118 brought a failed observation's `error_message` under `disable_provider_payload`, so in a
flag-on configuration the **flag** would withhold the message and the cases would assert nothing about §6.
Repointing them to the flag-**off** suppress arm keeps them gating real §6 behaviour, which is why they are also
restricted to non-detection-capable adapters: a detection-capable adapter raises at construction instead of
emitting. Two consequences for coverage elsewhere. The flag's own effect is gated by fixture **159**. And §6's
Tool anti-smuggling clause, which `tool_failure_omitted_on_shared` now covers only for non-detection-capable
adapters, is additionally gated for **every** adapter by fixture **098**'s default-posture case on a normal
provider. Throughout, `error_type` stays present: it is a classification token and is not gated.
