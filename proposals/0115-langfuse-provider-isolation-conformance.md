# 0115: Conformance Test Primitives for Langfuse Provider Isolation

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-06
- **Accepted:** 2026-08-07
- **Targets:**
  - spec/conformance-adapter/spec.md **§5.5 Observer / observability directives** — add a
    `langfuse_client` construction directive and the `no_langfuse_observations_on_global` /
    `no_langfuse_observations_on_private` / `langfuse_observations_on_global` assertions.
  - spec/conformance-adapter/spec.md **§6.4 Langfuse mock** — extend the harness primitive to a
    **provider-faithful** Langfuse client that emits its observations through its bound `TracerProvider`
    (so provider-topology leakage is observable), in addition to the existing content-recording wrapper.
  - spec/observability/conformance — one new fixture (`157-langfuse-provider-isolation`, two cases)
    gating the two observability §6 MUSTs that proposal 0114 shipped without fixtures, and the
    observability per-directory harness-contract comment (fixture 001 header) documenting the new keys.
- **Related:** 0114 (shipped the observability §6 / §8.9 provider-isolation obligations these directives
  test), 0107 (documented the conformance-adapter directive vocabulary in §5), fixture 005 (the OTel
  `caller_global_otel_active` / `no_openarmature_spans_on_global` isolation template this mirrors)
- **Supersedes:**

## Summary

Proposal 0114 (spec v0.108.0) added behavioral MUSTs to observability §6 — where the implementation
constructs the Langfuse client it MUST isolate the provider in the payload-suppression carve-out (mode b),
and where the caller supplies the client the implementation MUST NOT mutate it (mode a) — but shipped **no
fixtures**, because the observability harness's Langfuse mock is content-only and bypasses provider
topology, so leakage to a shared provider was not expressible. This proposal closes that gap the same way
the OTel side already does it (fixture 005's global-provider capture): a **provider-faithful** Langfuse
fake whose observations flow through its bound `TracerProvider`, a `langfuse_client` construction
directive, and the `no_langfuse_observations_on_{global,private}` + `langfuse_observations_on_global` assertions. It gates both 0114 MUSTs
behaviorally — no client-provider introspection required.

## Motivation

**0114's MUSTs are currently un-gated.** The spec's principle is that conformance tests are the source of
truth for behavior; 0114 accepted two behavioral MUSTs (the mode-(b) MUST-isolate carve-out and the
mode-(a) MUST-NOT-mutate) with nothing to catch a violating implementation. 0114's Conformance section and
Open question #1 flagged this and deferred the fixtures to a follow-on — this is that follow-on
(tracked in `docs/open-questions.md` under the conformance-adapter section).

**The pattern already exists for OA's own OTel spans.** Fixture 005's *external auto-instrumentation*
case installs a second in-memory exporter on the OTel global `TracerProvider` (`caller_global_otel_active:
true`) and asserts `no_openarmature_spans_on_global: true` — the exact isolation shape. A Langfuse v4
client emits its observations **as OTel spans** through its tracer provider, so the same global-exporter
capture catches a leaked Langfuse observation; the extension is narrow.

**Mode-(a) non-mutation is testable by effect, not introspection.** A Langfuse v4 client exposes its bound
provider only through a non-portable internal (no public accessor — this is *why* 0114's mode-(a) warn is
MAY), so a fixture cannot read it. It does not need to: a caller-supplied client bound to the global
provider, left un-mutated, emits its observations to the global exporter; an implementation that violates
MUST-NOT-mutate by rebinding the supplied client to an isolated provider produces **no** Langfuse
observations there and fails. The leak that *should* happen is the non-mutation test.

## Detailed design

### §5.5 — `langfuse_client` construction directive

Add a case-level observability harness key (a per-directory §3.2 extension, sibling to `mock_llm` /
`disable_llm_spans` / `caller_global_otel_active`):

> - **`langfuse_client: {mode, provider?}`** — configures how the Langfuse
>   observer's client is constructed for the case, so provider-isolation obligations (observability §6 /
>   §8.9) can be exercised:
>   - **`mode: credentials | supplied`** — `credentials` drives the implementation's own construction
>     path (observability §8.9 mode (b) — the implementation owns the client and its provider);
>     `supplied` hands the implementation a harness-constructed client (mode (a) — the caller owns it).
>   - **`provider: global | isolated`** — applies only to `mode: supplied`: the provider the harness binds
>     the supplied client to (default `global`). Under `mode: credentials` `provider` does not apply — the
>     implementation chooses the provider per §6, and the fixture drives that choice through the flags below.
>
>   The observers' payload settings use the existing per-observer convention, **not** a key on
>   `langfuse_client`: `langfuse_observer: {disable_provider_payload: <bool>}` sets the Langfuse side, and
>   the OTel observer's `disable_provider_payload` takes its §5.5.4 default (`True`). The mode-(b)
>   MUST-isolate carve-out fires when the OTel side suppresses payload (its default) while the Langfuse
>   observer emits it (`disable_provider_payload: false`).
>
>   The Langfuse client the harness constructs (or supplies) is the **provider-faithful** fake of §6.4:
>   its observations emit as OTel spans through its bound `TracerProvider`, so a leak to a shared provider
>   is caught by that provider's exporter. Requires `caller_global_otel_active: true` for the leak
>   assertions below.

Add the assertions (under `expected`, alongside the existing `no_openarmature_spans_on_global`). A *Langfuse
observation span* is one carrying the `langfuse.observation.*` attribute namespace (§6.4):

> - **`no_langfuse_observations_on_global: true`** — asserts **no** Langfuse observation span reached the
>   exporter installed on the global `TracerProvider` by `caller_global_otel_active`. The Langfuse analog of
>   `no_openarmature_spans_on_global`.
> - **`no_langfuse_observations_on_private: true`** — asserts none reached openarmature's own private OTel
>   provider's exporter either. Together with the global assertion this gates the mode-(b) MUST-isolate
>   carve-out against **both** provider spellings §6 forbids (not the global provider, and not
>   openarmature's own OTel provider).
> - **`langfuse_observations_on_global: true`** — the inverse: asserts at least one Langfuse observation
>   span **did** reach the global exporter (the mode-(a) non-mutation effect).

### §6.4 — provider-faithful Langfuse fake

Extend §6.4: for provider-isolation fixtures the observability harness provides a **provider-faithful**
Langfuse client fake that does two things in one object — it **records** the Generation / observation
content it is asked to emit (as the existing content wrapper does, so content and non-vacuity stay
assertable) **and** emits those observations as OTel spans **through its bound `TracerProvider`** (as a
Langfuse v4 client does), so an OTel exporter on that provider observes any that reach it. Its emitted
spans carry the `langfuse.observation.*` attribute namespace — the identity the leak assertions filter on.
The leak assertions read the provider side; the content / non-vacuity assertions read the recorded side. The fake
carries no network dependency and stays deterministic. For `mode: credentials`, the adapter injects it into
the implementation's construct-from-credentials path; for `mode: supplied`, the harness constructs it on
the configured provider and passes it in.

### observability fixture 157 — `langfuse-provider-isolation` (two cases)

Both cases run a graph with one LLM-calling node (`calls_llm` + `mock_llm`) so a Langfuse **Generation**
observation is actually produced to leak or not-leak, with the composed OTel + Langfuse observers attached.

> - **`mode_b_carveout_isolates`** — `langfuse_client: {mode: credentials}`, `langfuse_observer:
>   {disable_provider_payload: false}` (Langfuse emits; the OTel side stays at its §5.5.4 default `True`),
>   `caller_global_otel_active: true`. The §6 mode-(b) MUST-isolate
>   carve-out fires. Asserts the Generation observation **was** recorded (non-vacuity — the fake's recorded
>   side) **and** `no_langfuse_observations_on_global: true` **and** `no_langfuse_observations_on_private:
>   true` (the implementation built the client on a dedicated isolated provider, so nothing leaked to the
>   global provider or to openarmature's own OTel provider). An implementation that put the client on
>   either shared provider fails.
> - **`mode_a_supplied_not_mutated`** — `langfuse_client: {mode: supplied, provider: global}`,
>   `langfuse_observer: {disable_provider_payload: false}`, `caller_global_otel_active: true`. The §6
>   mode-(a) MUST-NOT-mutate applies. Asserts `langfuse_observations_on_global: true` — the implementation
>   left the supplied client on the caller's global provider, so its observations reached the global
>   exporter. An implementation that rebound the supplied client to an isolated provider produces none and
>   fails.

Update the observability per-directory harness-contract comment (fixture 001 header) to document
`langfuse_client` and the new assertions.

## Conformance test impact

**One new observability fixture** (`157-langfuse-provider-isolation`, two cases) — the point of the
proposal; it gates 0114's two MUSTs. New conformance-adapter directives (`langfuse_client` + the leak
assertions) documented in §5.5 and the provider-faithful fake in §6.4. observability fixture count 156 → 157.
No existing fixtures change. At acceptance this bumps **two** capabilities' `Latest` in the README
capability table — conformance-adapter (the directives) and observability (the fixture). The
provider-faithful fake is a **new per-language adapter primitive** (today's Langfuse mock records content
only) — language-agnostic to specify, but real adapter work for each implementation.

Two obligations are deliberately **not** fixtured: the mode-(b) **SHOULD**-isolate-by-default (when the
carve-out condition is not met) — SHOULD is MAY-omit, so both isolating and sharing are conforming and no
single expected output exists; and the mode-(a) **SHOULD**-document / **MAY**-warn (documentation and an
optional, non-portable diagnostic). Only the two MUSTs are gated.

## Alternatives considered

1. **Do nothing** (leave 0114 un-fixtured). Rejected: two behavioral MUSTs with no conformance gate is the
   anti-pattern the spec's "conformance is the source of truth" principle guards against.
2. **Assert non-mutation by reading the client's bound provider.** Rejected: Langfuse v4 exposes it only
   through a non-portable internal (no public accessor), with no cross-language guarantee — the same fact
   that makes 0114's mode-(a) warn a MAY. The effect-based assertion (observations on the global exporter)
   needs no introspection.
3. **Use the real Langfuse SDK in the fixtures.** Rejected: non-deterministic (network, credentials). A
   provider-faithful fake that emits through the bound provider is deterministic and sufficient, since the
   contract is about *which provider* the observations flow through, not Langfuse-server behavior.
4. **Also fixture the mode-(b) SHOULD-default / carve-out non-over-firing.** Rejected: SHOULD is MAY-omit,
   so the non-carve-out configuration has two conforming outcomes (isolate or share) and no definite
   expected output — not fixturable. Its scoping is a normative-text matter; the positive fixture gates the
   MUST when the condition holds.

## Open questions

1. **Generalization beyond Langfuse.** If observability later drives observations through another
   caller-supplied backend client (0114 Open question #2), the provider-faithful-fake + global-leak
   assertions generalize to it; the directive is written around "the Langfuse client" for now.
2. **Scope of the mode-(a) effect test.** It covers the isolation-relevant mutation (rebinding the
   supplied client's provider), which is the whole of §6's mode-(a) concern; it does not attempt to detect
   other, non-isolation mutations of the supplied client, which §6 does not govern.
