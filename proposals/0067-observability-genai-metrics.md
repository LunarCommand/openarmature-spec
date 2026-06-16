# 0067: Observability — OTel GenAI Metrics

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-16
- **Targets:** spec/observability/spec.md (add a new **§11 Metrics** — the OTel *metrics* signal complementing the spans of §4–§6 and the logs of §7 — defining two OA-namespaced histogram instruments over provider calls: `openarmature.gen_ai.client.token.usage` and `openarmature.gen_ai.client.operation.duration`, opt-in via an `enable_metrics` observer flag, dimensioned per the existing Stable-only split, sourced from the §5.5.7 / §5.5.9 typed completion events; renumber the current §11 *Out of scope* → §12 and narrow its *Metrics* bullet to graph-level metrics only). spec/conformance-adapter/spec.md (add an in-memory **metric-capture** harness primitive to §6, sibling to §6.3 OTel collector capture, so fixtures can assert recorded measurements).
- **Related:** 0047 (§5.5.3.1 OA-namespaced *stable-only mirror* for cache attributes — the precedent this follows for instrument names), 0059 (embedding observability §5.5.8 / §5.5.9 — the embedding-call surface metrics extend to), 0050 (OA-namespace-when-no-stable-`gen_ai`-equivalent precedent), 0031 (observability §8 + the section-renumber precedent), 0062 (LLM completion streaming — streaming metrics deferred until it lands), 0060 (retrieval-provider rerank — rerank-call metrics fold in when it lands). Policy: *Stable-only upstream adoption* (`GOVERNANCE.md`; tracked in `docs/compatibility.md`).
- **Supersedes:**

## Summary

OpenArmature observability is span-based (§4–§6) and log-correlated (§7); §11 *Out of scope* records that the spec is "trace-only" and that OTel **metrics** are deferred. This proposal adds the metrics signal as a new **§11**, scoped to **provider-call metrics**: two histogram instruments — token usage and operation duration — recorded per LLM completion and per embedding call (per attempt under call-level retry), from the data the framework already surfaces on the §5.5.7 typed LLM completion event and the §5.5.9 typed embedding event. No new data source; metrics are an aggregatable projection of the existing event stream.

The upstream OTel GenAI metric instruments (`gen_ai.client.token.usage`, `gen_ai.client.operation.duration`) and their `gen_ai.*` dimension attributes are at **Development** status (verified 2026-06-16 against `open-telemetry/semantic-conventions-genai`). Per the *Stable-only upstream adoption* policy, OA therefore emits **OA-namespaced** instruments — `openarmature.gen_ai.client.token.usage` and `openarmature.gen_ai.client.operation.duration` — mirroring the upstream instrument type, unit, and explicit bucket advisory so that a future cutover to the `gen_ai.client.*` names is mechanical (strip the `openarmature.` prefix). This is the same move §5.5.3.1 made for the Development-status cache attributes.

Metrics are **opt-in** (default off), independent of span emission, and emitted to the configured OTel `MeterProvider` (a no-op when none is configured). Dimensions follow the same per-attribute Stable-only split the span attributes already use (§5.5.2 / §5.5.3 use stable `gen_ai.*` names directly; Development names mirror to `openarmature.*`).

## Motivation

Spans answer "what happened on this one call"; metrics answer "what is the token throughput and latency distribution across all calls" — the question dashboards, alerts, and capacity planning ask. Today an operator who wants p95 LLM latency or token-spend-per-model has to post-process spans, which is the job a histogram instrument exists to do. Every LLM-aware OTel backend already understands the GenAI metric instruments; OA emitting the aggregatable signal (under the OA namespace until upstream stabilizes) makes that tooling work without per-deployment span post-processing.

The data is already in hand: the §5.5.3 response attributes carry input/output token counts, and the §4.1 LLM provider span already measures call duration. Metrics record those same values into histograms. Embedding calls (§5.5.8 / §5.5.9) carry input-token counts and durations too, so the same two instruments cover them with an operation dimension — matching the upstream single-instrument-plus-`gen_ai.operation.name` model.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance. The change adds the metrics signal (new behavior, opt-in and additive) and renumbers one section.

### §11 — Metrics (new section)

> Observability so far has been span-based (§4–§6) and log-correlated (§7). This section adds the
> OpenTelemetry **metrics** signal: aggregatable histograms over provider calls, complementing the
> per-call spans. Metric observations are a projection of the same §6 observer event stream —
> specifically the typed LLM completion event (§5.5.7) and the typed embedding event (§5.5.9) — and
> introduce no new data source.
>
> #### 11.1 Emission and the Meter
>
> Metrics are **opt-in**. Implementations MUST provide an observer-level boolean flag
> `enable_metrics` (default `False`); specific ergonomics (constructor argument, builder method,
> etc.) are implementation-defined, the flag name is normative for cross-implementation
> consistency. When `enable_metrics` is `False`, no metric instrument is created and no measurement
> is recorded.
>
> When `enable_metrics` is `True`, the implementation obtains a `Meter` from the configured OTel
> `MeterProvider` — parallel to how the span-emitting observer obtains a `Tracer` from the
> `TracerProvider`. When no `MeterProvider` is configured, recording MUST be a silent no-op (the
> OTel global/no-op meter); it MUST NOT raise.
>
> Metric emission is **independent of span emission**. The `disable_llm_spans` /
> `disable_provider_payload` / `disable_genai_semconv` flags (§5.5.4) govern spans only; metrics MAY
> be enabled with spans disabled, and vice versa. (Both draw from the §6 event stream, which exists
> regardless of span emission.) The implementation MAY package metric emission in the same observer
> that emits spans or in a dedicated metrics observer; the behavioral contract below is on which
> measurements are recorded, not on observer packaging.
>
> #### 11.2 Instruments
>
> The upstream OTel GenAI metric instruments are at **Development** status (per
> `docs/compatibility.md`); per the *Stable-only upstream adoption* policy, OA emits the
> OA-namespaced instruments below, mirroring the upstream instrument type, unit, and explicit bucket
> advisory so a future cutover to the `gen_ai.client.*` names is mechanical (strip the
> `openarmature.` prefix). Recording cadence under call-level retry is covered in *Call-level
> retry* below.
>
> - **`openarmature.gen_ai.client.token.usage`** — **Histogram**, unit `{token}`. Mirrors upstream
>   `gen_ai.client.token.usage`. SHOULD be configured with explicit bucket boundaries
>   `[1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864]`.
>   For an LLM completion, the implementation records **two** observations: the input-token count
>   with dimension `openarmature.gen_ai.token.type` = `"input"`, and the output-token count with
>   `"output"`, sourced from the response usage record (§5.5.3 `gen_ai.usage.input_tokens` /
>   `gen_ai.usage.output_tokens`). For an embedding call, it records **one** observation — the
>   input-token count with `"input"` (embeddings have no output tokens, per retrieval-provider §2).
>   When a call's usage record is absent (the provider returned no usage), no observation is recorded
>   for that call.
>
> - **`openarmature.gen_ai.client.operation.duration`** — **Histogram**, unit `s`. Mirrors upstream
>   `gen_ai.client.operation.duration`. SHOULD be configured with explicit bucket boundaries
>   `[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]`.
>   Records the wall-clock duration of the provider call — the same interval the §4.1 provider span
>   covers — **including** attempts that ended in error (carrying the error dimension; see §11.3).
>
> **Call-level retry.** Under call-level retry (llm-provider §7.1, surfaced as N attempt spans per
> §5.5), the duration histogram records **once per attempt** — each attempt is a real latency
> sample, and a failed attempt carries `error.type` (§11.3) — matching the per-attempt span model.
> The token-usage histogram records **only for an attempt that returned a usage record**; failed
> attempts have no response and contribute nothing. The attempt index is deliberately NOT a
> dimension (it would create unbounded cardinality); attempts are disambiguated on the spans, not the
> metrics.
>
> The instruments use an `openarmature.gen_ai.*` namespace (not `openarmature.llm.*`) because they
> are operation-generic — one instrument per signal, dimensioned by operation, covering LLM
> completions and embedding calls (and rerank calls when retrieval-provider rerank lands). This
> mirrors the upstream single-instrument model and differs deliberately from the LLM-specific
> `openarmature.llm.*` attribute names of §5.5.3.1, which sit on the LLM span.
>
> #### 11.3 Dimensions
>
> Measurements carry the following dimensions, reusing the keys the provider (§5.5.3) and embedding
> (§5.5.8) spans already emit. `gen_ai.system`, `gen_ai.request.model`, and `error.type` are Stable
> upstream attributes (`docs/compatibility.md`), used directly; the Development-status
> `gen_ai.operation.name` and `gen_ai.token.type` use their `openarmature.*` mirrors until they
> stabilize — the same split §5.5.2 / §5.5.3 apply to the span attributes. Implementations MUST keep
> dimensions low-cardinality (no free-form per-request values).
>
> | Dimension key | On | Source | Notes |
> |---|---|---|---|
> | `openarmature.gen_ai.operation` | both | the operation kind | `"chat"` for LLM completion, `"embeddings"` for embedding. Mirrors the Development `gen_ai.operation.name` (deferred per §5.5.8 / `docs/compatibility.md`). |
> | `gen_ai.request.model` | both | §5.5.3 / §5.5.8 request model | Stable per `docs/compatibility.md`; the model key both the LLM (§5.5.3) and embedding (§5.5.8) spans already emit. Cardinality is bounded by the set of models in use. |
> | `gen_ai.system` | both | §5.5.3 / §5.5.8 system identifier | Stable; the provider identifier both spans already emit. |
> | `openarmature.gen_ai.token.type` | token.usage only | `"input"` / `"output"` | Mirrors the Development `gen_ai.token.type`. |
> | `error.type` | duration only, when the call errored | the llm-provider §7 error category (per retrieval-provider §5 for embedding), carried as `error_category` on the graph-engine §6 typed LLM / embedding failure event | Stable; used directly. Absent on a successful call. |
>
> The two `openarmature.*`-mirrored dimensions track the upstream `gen_ai.operation.name` /
> `gen_ai.token.type` attributes, which are at Development status; a stable-cutover follow-on adds
> the `gen_ai.*` names when they stabilize (the §5.5.8 / 0047 mirror pattern, tracked in
> `docs/compatibility.md`). The Stable upstream `server.address` / `server.port` dimensions (the
> provider endpoint) are out of scope for v1 (endpoint cardinality).
>
> #### 11.4 Determinism
>
> graph-engine §5 determinism covers the *structure* of the §6 event stream — which events fire, in
> what order — but NOT the values a node's external call returns: a real provider's token counts and
> latencies vary run to run (graph-engine §5 explicitly excludes node-implementation / external-I/O
> nondeterminism). Per §10, the conformance suite asserts only the deterministic portion under its
> mocked provider — that the expected observations are recorded with the expected dimensions (and,
> for the suite's fixed-usage mock, token counts) — and does NOT assert duration values, histogram
> bucket assignment, or timestamps.
>
> #### 11.5 Conformance support
>
> Asserting metrics requires capturing recorded measurements in memory. Implementations MUST provide
> an in-memory **metric-capture** harness primitive (an in-memory `MetricReader`, sibling to the
> §6.3 OTel collector capture for spans), exposed to the conformance adapter per conformance-adapter
> §6. Fixtures assert the token-usage observations (value + dimensions) recorded for a completion or
> embedding call, and assert the duration instrument's presence + dimensions (not its value, per
> §11.4).

### Renumber and narrow the Out-of-scope section

Renumber the current **§11 Out of scope → §12**. (No accepted proposal cross-references observability
§10/§11 by number; the renumber is citation-safe.) Replace the existing *Metrics* bullet — which
declares the spec "trace-only" — with a narrowed bullet, and fold the deferrals this proposal names
into it:

> - **Graph-level metrics** — counters / histograms for node and invocation operations (as opposed
>   to the provider-call metrics of §11). Deferred to a future proposal.
> - **Streaming and server GenAI metrics** — the upstream `gen_ai.client.*` streaming histograms
>   (time-to-first-chunk, time-per-output-chunk) and the `gen_ai.server.*` metrics. The streaming
>   ones are deferred until LLM streaming (proposal 0062) lands a streaming provider contract; the
>   server ones do not apply (OA is always the GenAI client).
> - **Adopting the upstream `gen_ai.client.*` instrument names and the Development `gen_ai.*`
>   dimension names** — deferred to a stable-cutover follow-on per the *Stable-only upstream
>   adoption* policy.

## Conformance test impact

New fixtures under `spec/observability/conformance/` exercising metric emission with `enable_metrics`
on: assert that an LLM completion records two `openarmature.gen_ai.client.token.usage` observations
(input + output counts, with the operation / model / system / token-type dimensions) and one
`openarmature.gen_ai.client.operation.duration` observation (dimensions only); that an embedding call
records one token-usage observation (`input`); that an errored call records a duration observation
carrying `error.type`; and that with `enable_metrics` off, no observations are recorded. Duration
*values* and bucket assignment are not asserted (§11.4).

These fixtures require the in-memory **metric-capture** harness primitive added to conformance-adapter
§6 (a counterpart to §6.3 OTel collector capture). The directive surface for registering it and
asserting recorded measurements is descriptive of that new primitive; no other capability's fixtures
change.

## Versioning

**MINOR bump** (pre-1.0): observability gains a new §11 (the metrics signal) and renumbers §11 → §12.
The behavior is opt-in (default off) and additive — no existing span / log / Langfuse behavior
changes. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Graph-level metrics** (node / invocation counters and durations) — a separable concern from
  provider-call metrics; a future proposal MAY add them. This proposal narrows the prior blanket
  "metrics are out of scope" bullet to exactly this.
- **Streaming GenAI metrics** (`gen_ai.client.operation.time_to_first_chunk` /
  `time_per_output_chunk`) — there is no streaming provider contract until proposal 0062 lands;
  defer until then.
- **Server-side GenAI metrics** (`gen_ai.server.*`) — OA is always the GenAI client; no server role.
- **The Stable `server.address` / `server.port` metric dimensions** — upstream includes them (the
  provider endpoint) on the client metrics; deferred for v1 to bound endpoint cardinality. A
  follow-on MAY add them.
- **Rerank-call metrics** — the two instruments extend to rerank calls (via the operation dimension)
  once the retrieval-provider rerank protocol (proposal 0060) is accepted; out of scope until then.
- **Cutover to the upstream `gen_ai.client.*` instrument names** and the Development `gen_ai.*`
  dimension names — a stable-cutover follow-on, per the *Stable-only upstream adoption* policy.
- **SDK-level metric concerns** — views, exemplars, custom aggregations, temporality selection. These
  are configured on the `MeterProvider` outside the framework contract (parallel to §11-on-sampling
  for traces).
- **Langfuse metric mapping** — Langfuse (§8) is a trace/observation/generation model, not a metrics
  backend; metrics target OTel only.

## Alternatives considered

- **Adopt the `gen_ai.client.*` instrument names directly.** Rejected: the instruments are at
  upstream Development status, and the *Stable-only upstream adoption* policy requires the
  OA-namespaced mirror until they stabilize (the §5.5.3.1 precedent). The `openarmature.` prefix
  makes the eventual cutover a mechanical prefix-strip.
- **Per-operation instruments** (`openarmature.llm.*` and `openarmature.embedding.*` token/duration
  instruments). Rejected: it doubles the instrument count, diverges from the upstream
  single-instrument-plus-operation-dimension model, and complicates the stable cutover. One
  operation-dimensioned instrument per signal matches upstream and aggregates cleanly.
- **Default-on metrics** (emit whenever a `MeterProvider` is configured). Rejected for v1: metrics
  add cardinality and cost, and not every deployment scrapes them. Opt-in (default off) matches the
  conservative posture of the rest of observability (payload default-off, etc.). The flag makes
  enabling a one-liner.
- **Record duration only from spans** (derive metrics from emitted spans rather than the event
  stream). Rejected: it would couple metrics to span emission, breaking the §11.1 independence (you
  could not have metrics with spans disabled). Both signals derive from the §6 event stream
  directly.
- **Include graph-level metrics now.** Rejected for scope: "GenAI metrics" is provider-call metrics;
  node/invocation metrics are a distinct surface (different instruments, different dimensions, no
  upstream GenAI convention to mirror) and belong in their own proposal.
