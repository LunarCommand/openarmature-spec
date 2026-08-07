# 0114: Langfuse Client Ownership and Provider Isolation

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-05
- **Accepted:**
- **Targets:**
  - spec/observability/spec.md **§8.9 Composition with OTel** — pin the Langfuse-client **ownership
    model** the section currently leaves implementation-defined: implementations **MUST** support both
    supplying a caller-constructed client **and** supplying credentials from which the implementation
    constructs and owns the client. This closes a latent cross-implementation divergence and is the
    contract the isolation rule depends on.
  - spec/observability/spec.md **§6 Driving span lifecycle** — extend the *TracerProvider isolation
    (MUST)* subsection to OA's **Langfuse observations**, with obligations that **track control**: where
    OA constructs the client (it owns the provider) the protection is enforceable; where the caller
    supplies the client (the caller owns the provider) OA does not mislead, documents the remedy, and
    warns only best-effort. Update the rationale list's stale `Langfuse v3` → `Langfuse v4`.
  - Cross-references between §6 and §8.9.
- **Related:** 0083 (§7's token-budget **SHOULD**-emit-`WARNING` precedent); §2 (cross-backend
  correlation via `correlation_id`); §8.9 (observer composition, `disable_provider_payload`)
- **Supersedes:**

## Summary

Two gaps compound. First, §8.9 leaves the **Langfuse-client ownership model** implementation-defined, so
one implementation could take a caller-constructed client while another takes credentials and builds the
client itself — a capability divergence (not mere API-shape) that also determines whether OA can control
the client's tracer provider at all. Second, §6's private-provider MUST protects OA's *own* OTel spans but
says nothing about OA's **Langfuse observations**, which are emitted through the Langfuse client's tracer
provider — and a Langfuse v4 client binds to the **global** `TracerProvider` by default, so those
observations can be exported to every processor on a shared provider, duplicating span structure and metadata into
whatever backend it feeds — and, when the Langfuse observer emits payloads (`disable_provider_payload=False`, off by default), full prompt and completion text. This proposal pins the ownership model (both modes **MUST** be supported), then
states isolation obligations that **track control**: where OA constructs the client it **SHOULD** isolate
by default and **MUST** isolate in the one case where not isolating would silently defeat an OTel-side
payload-suppression setting; where the caller supplies the client, OA **MUST NOT** mutate it or present it
as isolated, **SHOULD** document the remedy, and **MAY** warn if it can determine the binding. Isolation
is never mandated as an unconditional default (it trades against trace-tree coherence) and a
shared-provider client is never refused.

## Motivation

**§6 already treats this hazard as real — in one direction only.** The *TracerProvider isolation (MUST)*
subsection requires a private provider for OA-emitted spans and names the threat directly: other libraries
(it lists `opentelemetry-instrumentation-openai`, OpenInference, LiteLLM-with-OTel, Langfuse) "emit OTel
spans through the global provider when one is set," so OA must not register globally lest those libraries
duplicate its spans. It treats Langfuse purely as an *external* library to defend against — blind to the
fact that OA's own Langfuse observer (§8) **drives exactly such a client**, whose observations can leak the
other way.

**The leak, its verified mechanism, and when it carries payloads.** A Langfuse v4 client attaches its span
processor to the **global** `TracerProvider` by default; isolation is available only through the client's
own isolated `TracerProvider` (verified against Langfuse's v4 documentation). So when the client is on a
provider shared with the application (the global provider being the common case), OA's Langfuse
observations are also exported to that provider's other exporters. Whether those observations carry the
**sensitive payload** depends on configuration: `disable_provider_payload` defaults to `True` on *both*
observers (§8.9), so the out-of-the-box setup duplicates only metadata and span structure. The
**full-payload** leak — prompt and completion text — occurs when the caller sets
`disable_provider_payload=False` on the *Langfuse* observer, which is the ordinary way to get generation
rendering in Langfuse. A downstream consumer running exactly that (payloads on for Langfuse, on a global
provider) measured it: identical `TraceId` *and* `SpanId` across both backends, LLM spans ~80% of
span-attribute bytes in the application backend. The case that most matters is not a rare opt-in: `disable_provider_payload` defaults to `True` on the
OTel observer (§8.9), so the moment a caller enables Langfuse payloads the OTel side is already suppressing
them — and the Langfuse observations reaching that backend through the shared provider silently undo the
suppression, on the default OTel path, not only under an explicit opt-in. §2's cross-backend join (correlate a Langfuse trace with OTel logs via `correlation_id`) assumes
the two backends hold *different* content; duplicating the LLM payload makes the join redundant and lands
the most sensitive payload these systems carry in a store not scoped for it.

**Why the ownership model must be pinned first.** Whether OA *can* prevent this depends on whether OA
controls the client's construction — and §8.9 currently makes that implementation-defined ("the API shape
is implementation-defined"). That is not a harmless API-shape freedom: "the caller owns the client" versus
"OA owns the client" is a different **capability contract** (who can bind the client to an isolated `TracerProvider`, who owns the
client lifecycle, what the user must do to be safe). Left open, Python and TypeScript could adopt different
models and present users materially different behavior — the exact cross-impl divergence the spec exists to
prevent. Pinning it now is cheap (TypeScript is not yet built); reconciling after it ships on a different
model is a breaking change. And once pinned, the isolation obligations can **track control**: OA can only
guarantee what it owns.

## Detailed design

### §8.9 — Langfuse client ownership (two modes, MUST)

Add to §8.9, alongside the existing "unified Langfuse configuration" guidance:

> **Client ownership.** An implementation exposes the Langfuse client through this observer in two forms,
> and **MUST** support both:
>
> - **(a) Caller-constructed client.** The caller builds and configures the Langfuse client (its
>   credentials, and any client-level configuration the SDK exposes — including the `TracerProvider` it binds to) and
>   supplies it to the implementation. The implementation does not own the client's construction.
> - **(b) Credentials.** The caller supplies Langfuse credentials (host, public/secret key, or
>   equivalent) and the implementation constructs and owns the client.
>
> The API shape of each form is idiomatic per language, but **both capability modes MUST be offered** so
> that implementations do not diverge on which is available. Mode (a) preserves caller control (a custom
> processor pipeline, a client shared across the application, composition with an existing Langfuse
> setup); mode (b) lets the implementation apply a safe provider default where it owns construction (§6).
> The existing contract — a single Langfuse configuration shared across all Langfuse-consuming surfaces —
> applies to both modes; the mechanism by which the shared configuration reaches those surfaces is
> implementation-defined, as today.

### §6 — Provider isolation for OA's Langfuse observations

Add to §6, immediately after the *TracerProvider isolation (MUST)* subsection:

> **OA's Langfuse observations and the client's provider.** The private-provider isolation above governs
> the spans OA emits **directly** through its own OTel observer. OA's **Langfuse observations** are emitted
> instead through the Langfuse client's `TracerProvider` (§8), which a Langfuse v4 client binds to the
> **global** provider by default. When that provider is shared with the application or other
> instrumentation, OA's Langfuse observations are exported to every span processor on it, not only to
> Langfuse — and when the Langfuse observer emits payloads (`disable_provider_payload=False`, §8.9), those
> exports carry full prompt and completion text into whatever backend the shared provider feeds. The
> obligations **track which party controls the provider** (the ownership mode of §8.9):
>
> - **Mode (b) — the implementation constructs the client.** The implementation owns the provider, so the
>   protection is enforceable from its own state, with no introspection of a foreign object. It **SHOULD**
>   construct the client on an **isolated** `TracerProvider` by default — a dedicated provider carrying
>   only the Langfuse span processor, not the global provider and not the provider OA uses for its own OTel
>   observer — so OA's observations reach only Langfuse. It **MAY** offer an opt-out to a shared provider
>   for callers who prefer a single provider (accepting the trade-off below); SHOULD-not-MUST, because
>   isolation is not free. **However**, the opt-out does **not** apply — the implementation **MUST**
>   construct the client on an isolated provider — when a composed OTel observer has
>   `disable_provider_payload` resolving to `True` (its §8.9 default, whether defaulted or set) while the
>   Langfuse observer emits payloads (`disable_provider_payload=False`): placing the client on a shared
>   provider there would silently defeat the OTel-side payload suppression, and the implementation controls
>   the provider, so it MUST NOT. Both conditions are the implementation's own configuration; because
>   `True` is the OTel default, this carve-out fires in the common case where a caller merely enables
>   Langfuse payloads.
> - **Mode (a) — the caller supplies the client.** The implementation does **not** control the provider
>   and **MUST NOT** mutate the supplied client. It **MUST NOT** represent OA's private-provider isolation
>   as covering the supplied client — the §6 guarantee is bounded to OA's own emitted spans. It **SHOULD**
>   state, in its user-facing guidance, that a caller-supplied client bound to a shared/global provider
>   exports OA's observations to every exporter on that provider and that the caller isolates it via the
>   client's own isolated `TracerProvider`. It **MAY** additionally emit a `WARNING`-level diagnostic *if* it can
>   determine that the supplied client is bound to the global (or another shared) provider — MAY, not
>   SHOULD, because reading a supplied client's bound provider may rest on non-portable SDK internals with
>   no cross-language guarantee. A client the caller has already isolated **MUST NOT** be warned about.
>
> **No hard failure.** A shared-provider client is a valid, if leaky, configuration; the implementation
> **MUST NOT** refuse the call or raise on any of the above.
>
> **The isolation trade-off.** Isolation is SHOULD-by-default in mode (b), not an unconditional MUST,
> because a separate `TracerProvider` still shares OTel *context*: a parent span on one provider can leave
> children on another orphaned (Langfuse documents this for a client bound to a separate `TracerProvider`). Whether to
> accept that trade-off is a caller decision (mode a) or a defaulted-but-overridable one (mode b, outside
> the payload-suppression case above); this section requires only that OA never silently present a
> shared-provider client as isolated, and that OA not defeat an OTel-side payload suppression (its §8.9 default or set)
> where it owns the client.

**§6 rationale-list update.** Update the example library `Langfuse v3` to `Langfuse v4` (OA's supported
line per the compatibility matrix; both majors are OTel-based global-provider writers, so the reference is
illustrative and kept current).

**§8.9 cross-reference.** Add a pointer from §8.9 to the §6 subsection above: a Langfuse client's
tracer-provider isolation is governed by §6, per the ownership mode.

## Conformance test impact

Additive MINOR. Honesty about testability up front: most of this contract concerns **observer
construction and provider wiring**, which the current fixture vocabulary (graph-run-oriented) does not
model, so it lands largely as prose-normative contract rather than new fixtures. Crucially, none of the
normative obligations rest on introspecting a *foreign* object: the mode-(b) obligations are checkable
against the implementation's **own** construction and configuration, and the mode-(a) warn is a MAY (so an
implementation that cannot read a supplied client's provider is conforming by not warning).

- **Two-mode ownership (§8.9, MUST).** A capability contract on the construction surface; verified by
  inspection of an implementation's public surface, not by a graph-run fixture.
- **Mode (b) SHOULD-isolate-default and the MUST-isolate carve-out.** Determined by OA's own state (which
  provider it constructed the client on; its own two `disable_provider_payload` settings). Fixturing them
  would still need observer-construction and provider-inspection primitives the harness lacks (Open
  questions); until then they are honest-but-unfixtured, but they rest only on OA's own state, so an
  implementation can meet them deterministically.
- **Mode (a) MUST-NOT-mutate / MUST-NOT-mislead / SHOULD-document / MAY-warn.** MUST-NOT-mutate is
  inspectable; SHOULD-document is documentation; MAY-warn is optional and explicitly non-portable.

No existing fixtures change.

## Alternatives considered

1. **Do nothing.** Rejected: §6 reads as though TracerProvider isolation is a solved concern for OA users
   when it is solved only for OA's own observer; the failure is silent and can leak sensitive payloads.
2. **Leave ownership implementation-defined; state only a hazard-keyed obligation** (an earlier draft).
   Rejected: leaves the Python-vs-TypeScript construction-model divergence unspecified, and a conforming
   construct-from-credentials implementation could read itself as outside a "caller-supplied client"
   requirement while leaking identically.
3. **A cross-mode MUST floor** (enforce the payload-suppression guarantee in both modes). Rejected:
   mode (a) cannot enforce it — OA does not own the provider and cannot even portably *detect* the
   binding (a Langfuse v4 client exposes its provider only via undocumented internals, with no
   cross-language analogue). A guarantee that cannot be met is worse than one honestly scoped to where OA
   has control, so the enforceable protection lives in mode (b) and mode (a) is best-effort.
4. **Credentials-in only** (implementations MUST construct the client; the caller never supplies one).
   Rejected: removes the caller's ability to hand in a pre-configured client and to compose with an
   existing Langfuse setup, and forces a breaking change on implementations that support the
   caller-constructed form today.
5. **Client-in only** (implementations MUST accept a caller-constructed client; never construct one).
   Rejected: forecloses the safe-by-default path (OA isolating where it owns construction), leaving the
   protection permanently best-effort.
6. **Mandate isolation by default (MUST) unconditionally in mode (b).** Rejected: an isolated provider
   still shares OTel context and can orphan parent/child spans; forcing that on every user is the caller's
   decision to make — hence SHOULD-with-opt-out, with the opt-out withdrawn only in the payload-suppression
   case where staying shared would defeat an explicit setting.

## Open questions

1. **Fixture primitives for construction + runtime diagnostics.** A future proposal could add an
   observer-construction fixture primitive and a runtime/attach-time diagnostic assertion directive, which
   would let the mode-(b) isolation obligations and the mode-(a) warn be conformance-asserted. Not pursued
   here.
2. **Promoting the mode-(a) warn.** If a future Langfuse SDK (or a cross-SDK convention) exposes a
   supplied client's bound provider through a documented, portable accessor, the mode-(a) MAY-warn could be
   raised to a SHOULD via a follow-on proposal.
3. **Generalization beyond Langfuse.** The ownership-plus-isolation model is written for the Langfuse
   client as the only current caller-facing backend client; the wording is kept general so a future such
   client inherits the two-mode ownership and control-tracking isolation contract without a new proposal.
