# 158 — Langfuse Payload-Leak Invariant (fail-closed / suppress / opt-out)

Gates observability §6's mode-(b) **payload-leak invariant** (proposal 0116): when openarmature constructs
the Langfuse client and the Langfuse observer emits payloads, those payloads MUST NOT reach a provider shared
with the application unless the caller has explicitly accepted a shared provider. Each case primes a
same-credential Langfuse client on the global provider *before* openarmature constructs, so the Langfuse v4
SDK's per-credential singleton hands openarmature the cached client and discards its isolated provider — the
leak condition. openarmature's response depends on whether it can establish the binding (best-effort, since
that introspection rests on non-portable SDK internals) and on the caller opt-out.

The Langfuse client is the provider-faithful fake of conformance-adapter §6.4, extended for 0116 with
per-credential-singleton semantics, a bound-provider accessor, and a payload-bearing vs. payload-free
distinction.

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

**Cases** (all: `mode: credentials`, `preexisting_same_key_client: true`, Langfuse observer emits payload,
`caller_global_otel_active: true`):

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

The *cannot-determine* arm is modeled by a non-detection-capable adapter (`singleton_preexists_suppresses`)
rather than by simulating a real binding-hiding SDK at runtime; the capability declaration is the harness's
portable proxy for that condition, consistent with 0114/0115 treating bound-provider introspection as
non-portable.
