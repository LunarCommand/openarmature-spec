# 0116: Fail-Closed When Langfuse Payloads Would Reach a Shared Provider

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-07
- **Targets:**
  - spec/observability/spec.md **§6 Driving span lifecycle** — replace the **entire mode-(b) bullet body** of
    the *Isolation for openarmature's Langfuse observations* subsection (its SHOULD-isolate default, its
    general "MAY opt-out to a shared provider" sentence, and the OTel-suppression *MUST-isolate carve-out*)
    with a single **payload-leak invariant**: whenever the Langfuse observer emits payloads, openarmature
    MUST keep them off a provider shared with the application unless the caller has explicitly accepted a
    shared provider. Met by isolating (SHOULD, default); where openarmature **detects** the observations
    would reach a shared provider it **MUST raise** a categorized error; where it **cannot determine** the
    binding it **MUST suppress** its own Langfuse-side payload (fail-safe); an explicit caller opt-out (one
    switch, unifying 0114's shared-provider preference and this proposal's proceed-on-leak) turns the raise /
    suppress into warn-and-proceed. Detection keys on the **leak condition**, defined portably as *a provider
    other than one openarmature itself established as isolated for this credential*.
  - spec/observability/spec.md **§6** — amend the *No hard failure* block to carve the never-refuse rule for
    the one detected-leak / not-opted-out case; amend the *isolation trade-off* paragraph whose "requires
    only …" summary no longer enumerates the raise/suppress obligation; and **define the isolation-unavailable
    error category** (a home for the token openarmature raises), which observability does not currently have.
  - spec/conformance-adapter/spec.md **§5.5** — add directives to prime a pre-existing same-credential client
    and to set the shared-provider opt-out; add a **construction/setup-time raised-error assertion**
    (`expected_construction_error: {category}`, the setup-scope analogue of `expected_compile_error`); and add
    a **`level`** key to the `expected.log_records` assertion so a mandated `WARNING` severity is gate-able.
    **Reword the surviving §5.5 carve-out-trigger sentences** (the "mode-(b) MUST-isolate carve-out fires when
    the OTel side suppresses payload while the Langfuse observer emits it") to the payload-leak invariant, so
    §5.5 does not contradict the widened §6.
  - spec/conformance-adapter/spec.md **§5.8 / §5.13** — register the isolation-unavailable category token in
    the raised-error category vocabulary so the `carries` / category assertions can reference it.
  - spec/conformance-adapter/spec.md **§6.4** — extend the provider-faithful Langfuse fake to honor the SDK's
    per-credential singleton **and** to expose its bound provider, so detection is deterministic in-harness.
  - spec/observability/conformance/157-langfuse-provider-isolation.{yaml,md} — annotate `mode_b_carveout
    _isolates` with the "openarmature constructs first" precondition its no-leak result now depends on, and
    reword its description off the deleted "MUST-isolate carve-out" term onto the payload-leak invariant's
    isolate-when-first default.
  - spec/observability/conformance/158-langfuse-payload-leak-fail-closed.{yaml,md} — **new** fixture.
  - spec/observability/conformance/001-otel-basic-trace.yaml — extend the harness-contract comment.
- **Related:** 0114 (the client-ownership + provider-isolation contract this amends), 0115 (fixture 157 and
  the provider-faithful fake this extends), 0083 (SHOULD-emit-`WARNING` precedent)
- **Supersedes:**

## Summary

0114 §6 placed two obligations on mode (b) (where openarmature constructs the Langfuse client) that cannot
both hold: in the payload carve-out the implementation **MUST** construct the client on an isolated
`TracerProvider`, and (the *No hard failure* rule) it **MUST NOT** refuse the call or raise on the isolation
decision. The Langfuse v4 SDK maintains a **process-wide client keyed by credential**: the first
construction for a credential caches the client — binding whatever `TracerProvider` it is given — and every
later construction for the same credential returns the cached client and **discards** a newly supplied
provider. So openarmature's isolation takes effect only when openarmature is the *first* party to construct a
client for that credential; in a typical service that initializes Langfuse before wiring openarmature it is
not, and its observations — full prompt/completion text when the Langfuse observer emits payloads — keep
exporting to the shared backend, silently, defeating the very protection the MUST-isolate rule existed to
give.

This proposal replaces the unachievable "always isolate" with an achievable **payload-leak invariant**:
*whenever the Langfuse observer emits payloads (in mode b), openarmature MUST ensure those payloads do not
reach a provider shared with the application or other instrumentation — unless the caller has explicitly
accepted a shared provider.* The invariant is satisfied by **isolating** (SHOULD, the default); where
openarmature **detects** the observations would reach a shared provider, it **raises** a categorized error
(fail-closed); and where it **cannot determine** the binding (a future SDK exposes no way), it **suppresses**
its own Langfuse-side payload so nothing sensitive can leak (fail-safe). A single **explicit caller opt-out**
— "I accept a shared provider for the Langfuse client," unifying 0114's shared-provider preference with this
proposal's proceed-on-leak — turns the raise or suppress into warn-and-proceed, because the caller has
accepted the export. This keys the obligation on the actual leak condition rather than on whether an OTel
observer happens to be composed (closing a second payload-leak path 0114 left at SHOULD), defines the leak
condition portably (a provider other than one openarmature itself established as isolated for the
credential — not a foreign-object inspection), defines the error category and the conformance primitives the
raise and warning need, and reconciles the sibling spec sections the widening touches.

## Motivation

**The impossibility in the shipped contract.** 0114 §6 mode (b) required, in the carve-out (a composed OTel
observer suppressing payload while the Langfuse observer emits it), that the implementation **MUST**
construct the client on an isolated `TracerProvider`; the *No hard failure* block then said it **MUST NOT**
raise on the isolation decision. The spec assumed openarmature can always construct an isolated client. It
cannot.

**The SDK mechanism (verified).** The Langfuse v4 SDK maintains a process-wide client resource keyed by the
credential (public key): the first construction for a credential initializes and caches the client, binding
whatever `TracerProvider` it is given; every later construction for the same credential returns the cached
client and ignores a newly supplied provider. (Verified against the current Langfuse v4 SDK source: the
resource manager is a process-wide singleton keyed by public key; its allocator returns the cached instance
and skips re-initialization, so a `tracer_provider` supplied by a later constructor is discarded.) So
mode-(b) isolation takes effect **only when openarmature is the first constructor for that credential in the
process**. If the application constructed a same-credential client first — directly, via an auto-instrumentor
or decorator, or via an earlier openarmature call — the SDK hands openarmature the cached client on its
original (commonly global) provider, and openarmature's isolated provider never binds.

**The leak condition is the right axis, not the OTel setting.** 0114 scoped its MUST to the case where a
composed OTel observer suppresses payload while Langfuse emits it, reasoning that a shared-provider client
there "silently defeats" an explicit OTel-side setting. But the payload leak does not depend on an OTel
observer being present at all: whenever the Langfuse observer emits payloads and its client sits on a
provider shared with the application, those payloads reach every exporter on that provider. A configuration
with Langfuse payloads on, no OTel observer composed, and a shared provider carrying an application exporter
leaks identically — yet 0114 left it at SHOULD-isolate + MAY-warn. This proposal keys the obligation on the
leak itself (**the Langfuse observer emits payloads and they would reach a shared provider**), which subsumes
the old carve-out and closes that second path. The genuinely-no-payload case (the Langfuse observer
suppresses payload) is unaffected: a shared provider then duplicates only metadata and span structure, and
isolation stays SHOULD with MAY-warn and no raise.

**Why the default must be fail-closed.** When openarmature's observations carry payloads and would reach a
shared backend, a silently-broken guarantee is the worst outcome; a warning is missable; **refusing is the
honest fail-closed** for a protection openarmature otherwise cannot keep.

**Why one explicit opt-out.** Construction order is not always the caller's to control — a third-party
library or framework may construct the same-credential client first — and some callers deliberately prefer a
single shared provider (an isolated provider still shares OTel context and can orphan spans). Both are the
same underlying wish: *let the Langfuse client ride a shared provider.* 0114 expressed one half (a
"MAY opt-out to a shared provider" preference) and this proposal's earlier draft expressed the other
(proceed-on-detected-leak); shipping both would be two overlapping switches a caller could set
inconsistently. This proposal unifies them into **one** explicit opt-out. openarmature owns the *mechanism*;
the caller owns the *policy*: the safe default (isolate; raise or suppress on a would-be leak) is
openarmature's, and the escape hatch is the caller's single, affirmative choice. Because warn-and-proceed
runs only after that opt-in, it does not reintroduce a missable-warning default.

**Why the undetectable case fails safe — but never overrides the opt-out.** Detecting whether observations
would reach a shared provider requires reading the constructed client's bound provider. For the supported
Langfuse v4 line the binding is establishable, so detection is required and the raise is enforceable. A
hypothetical future SDK that exposes no way to establish the binding would make the raise unenforceable — but
openarmature still owns the Langfuse observer in mode (b), so for a caller who has **not** opted in it
**suppresses** its own Langfuse-side payload, guaranteeing no payload reaches a shared provider even without
isolation and without refusing the call. It does **not** suppress for a caller who **has** opted in: that
caller explicitly asked for the export, so suppressing would both discard the data they wanted and silently
override their choice — there, openarmature warns and proceeds. Fail-open (warn and leak for a do-nothing
caller) is rejected: it would collapse the undetectable case back to warn-only. With these arms a
**do-nothing caller is protected in every case** — isolated by default, raised on a detected leak, or
suppressed when the binding is unknowable — while an opted-in caller always gets exactly what they accepted.

## Detailed design

### §6 — the payload-leak invariant (replaces the whole mode-(b) bullet body)

Replace the mode-(b) bullet's entire body — its SHOULD-isolate default, its general "MAY offer an opt-out to
a shared provider … SHOULD-not-MUST" sentence, and the OTel-suppression MUST-isolate carve-out — with:

> **When the Langfuse observer emits payloads.** When openarmature constructs the client (mode b) and the
> Langfuse observer emits payloads (`disable_provider_payload=False`), openarmature's Langfuse observations
> carry full prompt and completion text. openarmature **MUST** ensure those payloads do not reach a provider
> shared with the application or other instrumentation, **unless the caller has explicitly accepted a shared
> provider** (below). The default mechanism is isolation: openarmature **SHOULD** construct the client on an
> **isolated** `TracerProvider` — a dedicated provider carrying only the Langfuse span processor, not the
> global provider and not the provider openarmature uses for its own OTel observer.
>
> Because the Langfuse v4 SDK maintains a process-wide client keyed by credential, constructing on a fresh
> isolated provider takes effect only when openarmature is the **first** party to construct a client for that
> credential; a later same-credential construction returns the cached client on its original provider and
> discards the supplied provider. Where §8.9 has the same Langfuse configuration shared across an
> implementation's Langfuse-consuming surfaces (SHOULD), openarmature **SHOULD** reuse one isolated provider
> per credential, so a second surface resolves to that same isolated provider rather than a fresh one.
>
> **The shared-provider opt-out (one switch).** The caller **MAY** explicitly configure openarmature to
> accept a shared provider for the Langfuse client — a single affirmative acknowledgment that openarmature
> may let its payload-bearing Langfuse observations reach a shared provider (whether because the caller
> prefers a single provider for trace-tree coherence, or because it accepts the leak when isolation cannot
> take). openarmature **MUST** default to the protective behavior and **MUST NOT** treat a shared provider as
> accepted implicitly. The opt-out's API shape is idiomatic per language; the normative behavior is one
> explicit caller choice.
>
> **When the caller has accepted a shared provider (opted in):** openarmature is **not** required to isolate
> the client's provider (it **MAY** honor the caller's preference for a single shared provider — the reason to
> accept one is usually trace-tree coherence); it **MUST NOT** raise and **MUST NOT** suppress its payload on
> account of the provider; if its observations would (or might) reach a shared provider it **MUST** emit a
> `WARNING`-level diagnostic and proceed.
>
> **Otherwise (not opted in):** openarmature **MUST determine** whether the constructed client's observations
> would reach a **shared / non-isolated provider** — defined as *any provider other than one openarmature
> itself established as isolated for this credential* (in particular the global provider). This is a
> leak-condition test decidable from openarmature's own record of the providers it established; it is **not**
> an identity test against the provider supplied on this call (a client the singleton bound to another
> isolated provider openarmature established for the same credential satisfies the invariant and **MUST NOT**
> trigger a failure), and it does **not** require enumerating a foreign provider's exporters.
>
> - **Determined the observations would reach a shared provider** → openarmature **MUST raise** a categorized
>   error of category `langfuse_provider_isolation_unavailable` (below), **before** emitting any
>   payload-bearing observation to that provider, rather than proceed and silently leak.
> - **Cannot determine the binding** (a future SDK exposes no way to establish it) → openarmature **MUST NOT**
>   raise; it **MUST** suppress its own Langfuse-side payload so no payload can reach a shared provider, and
>   **MUST** emit a `WARNING`-level diagnostic.
> - **Determined the observations would *not* reach a shared provider** (the client is on an openarmature-
>   established isolated provider) → proceed normally.
>
> Detection **MUST** be implemented; the *cannot-determine* arm applies only where the SDK version genuinely
> exposes no way to establish the binding — a property of the SDK, uniform across implementations, not an
> implementation's choice to skip detection. For the supported Langfuse v4 line the binding is establishable,
> so that arm is dormant and conforming implementations behave identically.
>
> The point at which the error surfaces (client construction or first use) is implementation-defined, but it
> **MUST** precede any payload-bearing emission to the shared provider.
>
> **When the Langfuse observer does not emit payloads** (`disable_provider_payload=True`), openarmature's
> observations carry only metadata and span structure. A shared provider then duplicates only that (the same
> duplication §6's private-provider rule prevents for openarmature's own OTel spans). openarmature **SHOULD**
> isolate and **MAY** warn, but **MUST NOT** raise.

### §6 — the isolation-unavailable error category

openarmature currently defines no native raised-error categories (§8.4.2 maps graph-engine §4 categories
through `openarmature.error.category`); the Langfuse-isolation contract raised nothing (0114 was
MUST-NOT-raise). This proposal introduces the first, so it **defines** it. Add, in the §6 subsection above:

> The categorized error openarmature raises when it determines its payload-bearing Langfuse observations
> would reach a shared provider (and the caller has not opted in) has category
> `langfuse_provider_isolation_unavailable`. It is raised at Langfuse-observer/client construction or first
> use (implementation-defined), before any payload-bearing emission. Implementations **MUST** make it
> distinguishable by this category so callers can catch it specifically.

### §6 — carve the *No hard failure* rule

Replace the *No hard failure* block:

> **No hard failure, except to prevent an unacknowledged payload leak.** A shared-provider client is a valid,
> if leaky, configuration; openarmature **MUST NOT** refuse the call or raise on the isolation decision —
> **except** the one case above: the Langfuse observer emits payloads, the caller has not accepted a shared
> provider, and openarmature determines the observations would reach one. There, and only there, openarmature
> **MUST** raise `langfuse_provider_isolation_unavailable`. In every other case — mode (a), the no-payload
> case, an opted-in caller, or an undetectable binding (which suppresses instead) — it **MUST NOT** raise.

### §6 — amend the *isolation trade-off* paragraph

The existing paragraph says the section "requires only that openarmature never silently present a
shared-provider client as isolated, and that openarmature not defeat an OTel-side payload suppression … where
it owns the client." Drop "only" and enumerate the new obligation:

> … this section requires that openarmature never silently present a shared-provider client as isolated; that,
> where it owns the client and the Langfuse observer emits payloads, it not let those payloads reach a shared
> provider unless the caller has explicitly accepted one — raising where it detects they would, suppressing
> its own payload where it cannot verify the binding; and that the shared-provider trade-off (and the
> span-orphaning isolation can cause) is a caller decision (mode a) or a single explicit opt-in (mode b).

### Conformance-adapter §5.5 — directives and assertions

- `langfuse_client.preexisting_same_key_client` — bool, optional, default `false`. When `true`, the harness
  constructs a Langfuse client for the **same credential** *before* the implementation constructs its own,
  priming the SDK's per-credential singleton so the implementation is not first. Meaningful only with `mode:
  credentials`. Per §6.4 the primed client binds the global provider (the faithful default), reproducing the
  discarded-isolation path deterministically.
- `langfuse_client.accept_shared_provider` — bool, optional, default `false`. Sets the caller opt-out (the
  single shared-provider acknowledgment) on the implementation's Langfuse observer construction. Default
  `false` exercises the fail-closed path.
- `expected_construction_error: {category: <token>}` — a new setup-scope raised-error assertion, the analogue
  of `expected_compile_error` for observer/client construction: asserts that standing up and running the case
  raises the categorized error (at construction or first use). Fixture 158 uses `{category:
  langfuse_provider_isolation_unavailable}`. The token is registered in the raised-error category vocabulary
  (§5.8 / §5.13) so `carries`/category assertions can reference it.
- `expected.log_records` gains a **`level`** key (e.g. `level: WARNING`) alongside `body` / `attributes`.
  OTel severity is a first-class `LogRecord` field, not an attribute, so without this key a mandated
  `WARNING` cannot be asserted (an implementation emitting at `INFO` would pass). Fixture 158's opt-out case
  asserts `level: WARNING`.
- **Reword the §5.5 carve-out-trigger prose** (the sentences describing the "mode-(b) MUST-isolate carve-out"
  as firing "when the OTel side suppresses payload while the Langfuse observer emits it") to the payload-leak
  invariant: the isolate/raise obligation is keyed on the Langfuse observer emitting payloads that would
  reach a shared provider, independent of a composed OTel observer, with isolation SHOULD (not MUST) and the
  raise/opt-out/suppress arms. The 0115 §History bullet describing what fixture 157 exercised is a dated
  snapshot and is left as-is.

### Conformance-adapter §6.4 — provider-faithful fake

The provider-faithful Langfuse fake (0115 §6.4) **MUST** (a) honor the SDK's per-credential singleton — the
first construction for a credential binds and records the supplied `TracerProvider`; a later construction for
the same credential returns the first client and ignores a newly supplied provider, and a plain priming
construction (no provider supplied) binds the **global** provider, matching the real v4 default — and (b)
**expose its bound provider**, so detection is deterministic in-harness (the *cannot-determine* arm is
exercised only by a real binding-hiding SDK, which the harness does not simulate).

### Fixtures

- **157 `mode_b_carveout_isolates`** — annotate with `preexisting_same_key_client: false` and a prose note
  that openarmature constructs first, the precondition its no-leak result now depends on; and reword its
  description off the deleted "MUST-isolate carve-out" term onto the payload-leak invariant's
  isolate-when-first default. No change to its assertions.
- **158-langfuse-payload-leak-fail-closed** (new), `langfuse_client.mode: credentials`,
  `preexisting_same_key_client: true`, `langfuse_observer.disable_provider_payload: false`,
  `caller_global_otel_active: true`:
  - `singleton_preexists_raises` — a composed OTel observer suppressing payload (the old carve-out shape),
    `accept_shared_provider: false` → asserts `expected_construction_error: {category:
    langfuse_provider_isolation_unavailable}` **and** that no *payload-bearing* Langfuse observation (the
    Generation) reached the global provider (a metadata-only enclosing span reaching it before a first-use
    raise does not violate the payload invariant).
  - `singleton_preexists_raises_no_otel_observer` — the same, but **no OTel observer composed** → still
    raises. Gates the widened trigger: the raise keys on the payload leak, not on an OTel-side setting.
  - `singleton_preexists_optout_proceeds` — `accept_shared_provider: true` → does not raise; a `WARNING`
    log-record is asserted (`expected.log_records` with `level: WARNING`), and the Generation reaches the
    global provider (`langfuse_observations_on_global: true`) — the acknowledged leak by effect.
- **001** harness-contract comment — document `preexisting_same_key_client`, `accept_shared_provider`,
  `expected_construction_error`, and the `expected.log_records` `level` key.

## Conformance test impact

Additive MINOR. Two new `langfuse_client` sub-directives, a setup-scope `expected_construction_error`
assertion (with a registered category token), and a `level` key on `expected.log_records` in
conformance-adapter §5.5; the §6.4 provider-faithful fake gains singleton semantics and a bound-provider
accessor; one new observability fixture (158, three cases); fixture 157 gains a clarifying precondition
annotation and description reword with no change to its assertions; the §5.5 carve-out-trigger prose is
reworded (a reconciliation, no new assertion). No existing assertions change.

The **cannot-determine → suppress** arm remains unfixtured: exercising it requires simulating an SDK whose
client exposes no binding surface, which the harness does not model (the §6.4 fake exposes its provider by
design). This is honest-but-unfixtured, consistent with 0114's mode-(a) MAY-warn; noted in Open questions.

This resolves **0114 Open question #1** in part: it adds the construction-state primitive (a pre-existing
same-credential client), the category-bearing construction-time raise assertion, and the log-record severity
assertion, letting the mode-(b) payload-leak obligation be conformance-gated.

## Alternatives considered

1. **Pure fail-loud, no opt-out.** Rejected: it traps a caller who cannot control construction order (a
   third-party library or framework constructs the same-credential client first); their only recourse is to
   abandon mode (b). The explicit, fail-closed-by-default opt-out removes the trap without weakening the
   default.
2. **Warn-only (keep never-refuse intact).** Rejected: the warning is missable, and a security-relevant
   guarantee that quietly does not hold is worse than none; a do-nothing caller would silently leak
   payloads — the exact outcome 0114 exists to prevent.
3. **Fail-open on the undetectable binding (warn and proceed for a do-nothing caller).** Rejected: it
   collapses the undetectable case back to warn-only and leaves a do-nothing caller unprotected. Because
   openarmature owns the observer in mode (b) it suppresses its own payload instead — fail-safe, with no
   refusal and no leak. (Suppression does not apply to an opted-in caller, who accepted the export.)
4. **Two opt-outs (a shared-provider preference and a separate proceed-on-leak flag).** Rejected: they encode
   the same caller intent and could be set inconsistently. One explicit opt-out ("accept a shared provider")
   covers both.
5. **Keep the OTel-suppression-specific carve-out (the narrow 0114 scope).** Rejected: the payload leak does
   not depend on a composed OTel observer, so the narrow scope leaves an identical leak (Langfuse payloads
   on, no OTel observer, shared provider) at only SHOULD + MAY-warn. Keying on the leak condition subsumes
   the carve-out and closes that path; the caller retains control via the opt-out.
6. **Identity detection predicate** ("isolation took effect iff the client is bound to exactly the provider
   openarmature supplied this call"). Rejected: in the shared-configuration case a second surface's fresh
   provider is discarded and the singleton returns the cached client on openarmature's *own earlier* isolated
   provider — no leak — yet an identity test would raise, and two conforming implementations (memoize-one-
   provider vs fresh-per-surface) would diverge crash-vs-succeed. The predicate tests the leak condition
   (a provider not among those openarmature established as isolated) instead — decidable from openarmature's
   own state, no foreign-object inspection.
7. **Eager construction to win the singleton race.** Rejected: openarmature cannot control application
   initialization order, and winning the race would bind the application's own same-credential client onto
   openarmature's provider — hijacking the app's Langfuse setup, a worse side effect than the leak.

## Open questions

1. **Fixturing the cannot-determine → suppress arm.** Requires a harness primitive that simulates an SDK
   whose client exposes no binding surface. Not modeled today; the arm is honest-but-unfixtured, as with
   0114's mode-(a) warn.
2. **Generalization beyond Langfuse.** The per-credential-singleton hazard is Langfuse-SDK-specific, but the
   payload-leak invariant (isolate / raise / suppress, with one shared-provider opt-out) would apply to any
   future caller-facing backend client whose isolation can be silently defeated by shared process state.
   Kept scoped to Langfuse until such a client exists, per 0114's general wording.
