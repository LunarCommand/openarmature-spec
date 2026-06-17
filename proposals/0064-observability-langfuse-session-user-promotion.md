# 0064: Observability — Langfuse `trace.sessionId` / `trace.userId` Population

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-10
- **Accepted:** 2026-06-17
- **Targets:** spec/observability/spec.md (§8.4.1 — adds `trace.sessionId` and `trace.userId` mapping rows with a follow-on *Session / user trace-field sourcing* paragraph defining the `session_id` promotion, the recognized-`userId`-key promotion, the OTel data-model asymmetry, and multi-invocation grouping / detached-trace semantics; §8.10 — the *Langfuse Sessions* out-of-scope bullet is realized and removed)
- **Related:** 0031 (Langfuse backend mapping — introduced §8), 0020 (sessions capability — established `openarmature.session_id`, the `trace.sessionId` source, and the §8.10 deferral this realizes), 0034 (caller-supplied invocation metadata — established the `trace.metadata` top-level surface the `userId` promotion reads from, and `openarmature.user.*` on OTel spans), 0043 (sibling Langfuse trace-field population proposal — the observer-side sourcing-paragraph pattern and the OTel-has-no-trace-level-equivalent framing this reuses)
- **Supersedes:**

## Summary

The §8 Langfuse mapping populates `trace.id`, `trace.name`, `trace.metadata`,
and (per 0043) `trace.input` / `trace.output`, but leaves Langfuse's two
cross-trace grouping fields — `trace.sessionId` and `trace.userId` — unset.
§8.2 already enumerates both as Trace fields; §8.10 explicitly defers their
realization, pending the sessions capability (proposal 0020). That capability
is now Accepted, so the realization is unblocked.

These two fields power Langfuse's **Sessions** and **Users** dashboards — the
canonical way to view a multi-turn conversation as one grouped session and to
slice traces by end user. With them unset, an OA + Langfuse user running a
multi-turn agent sees each turn as an isolated trace with no session grouping
and no per-user view, even though OA already carries the identifying data.

This proposal extends §8.4.1 with two mapping rows:

1. **`trace.sessionId`** — sourced directly from `openarmature.session_id`
   (the cross-cutting attribute established by proposal 0020, present when the
   invocation is session-bound). No new OA concept; the source already exists.
2. **`trace.userId`** — sourced by the Langfuse observer recognizing a
   `userId` key in the caller-supplied invocation metadata (§3.4 / 0034) and
   promoting its value to the first-class field. OA has no first-class user
   concept, so the user identity is promoted at the observer from existing
   caller metadata rather than introduced as an engine surface.

## Motivation

The identifying data already exists at the invocation boundary:

- `openarmature.session_id` is set whenever the caller supplied a `session_id`
  at `invoke()` (sessions capability, §5.6). By design it spans **many
  invocations** — the sessions identity trio scopes `session_id` across
  separate `invoke()` calls (sessions capability §3), and in sessioned mode the
  harness threads it into every turn's `invoke()`. Each such invocation has its
  own `invocation_id` and therefore its own Langfuse trace, all carrying the
  same session id. That is exactly the shape Langfuse Sessions consume: N traces
  sharing one `sessionId` render as one conversation.
- Caller-supplied invocation metadata (0034) already lands as top-level
  `trace.metadata.<key>` entries, and §3.4's own examples list `userId` /
  `tenantId` among the keys callers pass. The data Langfuse's Users dashboard
  wants is therefore already flowing — it just isn't promoted to the dedicated
  `trace.userId` field that the dashboard reads.

Today the only way to get session / user grouping is to wrap `invoke()` and
set the session and user ids via direct Langfuse SDK trace-update calls — the
same observer-bypass workaround 0043 called out for `trace.input` /
`trace.output`: it duplicates wiring across every OA + Langfuse user and
reaches past the observer abstraction to hold the Langfuse client and the
`trace_id` correlation directly.

The two fields are asymmetric in where their source lives, and the asymmetry
is principled:

- **`session_id` is a first-class OA concept** (sessions capability) with
  runtime state semantics — it loads and persists cross-invocation state. It
  earns a first-class invoke argument and a cross-cutting attribute.
- **A user id has no runtime semantics in OA.** It is purely an observability
  dimension. Promoting it from caller metadata at the Langfuse observer keeps
  it out of the engine's invoke surface — observability concerns should not
  dictate engine API. This mirrors 0043's posture: trace-field population is an
  observer-side concern, configured where the Langfuse mapping lives.

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0). The concrete spec version is assigned at acceptance.

### observability §8.4.1 — `trace.sessionId` / `trace.userId` rows + sourcing paragraph

Two new rows are added to the §8.4.1 Trace-level mapping table:

| OA source | Langfuse Trace field |
|---|---|
| `openarmature.session_id` (per §5.6, present when the invocation is session-bound per the sessions capability / proposal 0020) | `trace.sessionId` — groups every trace sharing the session id under one Langfuse Session. Absent when the invocation is not session-bound. |
| The recognized `userId` key in the in-scope caller-supplied invocation metadata (per §3.4), promoted by the Langfuse observer | `trace.userId` — populates Langfuse's first-class user dimension for the Users dashboard and per-user filtering. Absent when no `userId` key is in scope. |

A new paragraph follows the table:

**Session / user trace-field sourcing.** Langfuse exposes two dedicated
cross-trace grouping fields on the Trace object — `sessionId` and `userId` —
distinct from `trace.metadata`. They are sourced as follows.

**`trace.sessionId`.** When the invocation is session-bound (the caller
supplied a `session_id` at `invoke()`, surfaced as `openarmature.session_id`
per §5.6), the Langfuse observer MUST set `trace.sessionId` to that value.
When the invocation is not session-bound, `trace.sessionId` is unset. Because
`session_id` spans many invocations by design (sessions capability §3) and is
unchanged across detached / parent traces (§4.4), every trace produced under
one session id — whether from a separate per-turn `invoke()` or a detached
child — carries the same `trace.sessionId`, and Langfuse groups them into one
Session (see *Multi-invocation session grouping* below).

**`trace.userId`.** OA has no first-class user concept; the user identity is an
observability dimension carried in caller-supplied invocation metadata (0034).
The Langfuse observer recognizes the `userId` key in the in-scope caller
metadata (per §3.4, including any mid-invocation augmentation applied before
trace closure) and MUST promote it: when a `userId` key is in scope the
observer sets `trace.userId` to its value **automatically** — promotion is not
gated behind an opt-in; when absent, `trace.userId` is unset. The recognized
key is `userId`, not `user_id`: it is a caller-supplied *read* key, so it
matches both its target field (Langfuse `trace.userId`) and §3.4's own
caller-metadata examples (`userId`, `tenantId`) with zero translation —
snake_case is OA's convention for keys it *emits* (the §3.4 / §8.4 reserved
set), not for a key it recognizes. Promotion is **additive**: the `userId`
entry also remains a top-level `trace.metadata.userId` key per the existing
§8.4.1 caller-metadata row (0034) — the observer does not remove it. `userId`
is **not** a reserved key (§3.4): unlike the OA-*emitted* keys 0041 / 0042
reserve against collision, `userId` is a caller key OA *reads*, so it is
recognized, not rejected. The cost of automatic zero-config promotion is that a
caller using `userId` to mean something other than an end-user identity sees it
surface in Langfuse's Users dimension; this is rare (the key is unambiguous),
and the escape hatch — an observer-construction option naming a different
promotion key — is a future tightening (Out of scope). The `userId` row's *OA
source* cell deviates from the other rows' `openarmature.*` attribute pattern
because it reads caller metadata, not a §5 span attribute — flagged here as
0042 did for its `detached_from_invocation_id` row, which is likewise not
attribute-sourced.

**OTel data-model asymmetry.** Like 0043's `trace.input` / `trace.output`,
`sessionId` and `userId` are Langfuse Trace-level fields with no OpenTelemetry
trace-level equivalent (an OTel trace is a set of spans sharing a `trace_id`;
it has no trace-level session or user field). The OTel side already carries the
same data as span attributes — `openarmature.session_id` (§5.6) on every span
in sessioned mode, and the `openarmature.user.*` caller-metadata family (§3.4 /
0034) — so this proposal adds no OTel attribute and is Langfuse-specific by
data-model construction.

### observability §8.10 — realize the *Langfuse Sessions* deferral

The §8.10 *Out of scope* bullet currently reads:

> - **Langfuse Sessions.** Langfuse's `userId` / `sessionId` Trace fields
>   support cross-trace grouping. Cross-invocation session identity is proposal
>   0020's concern; once that lands, `trace.sessionId` realization follows.

Proposal 0020 is Accepted, so the precondition is met and this proposal
realizes the deferral. The bullet is removed; the realization is recorded in
§8.4.1 (above). The remaining §8.10 bullets (Langfuse Scoring, Cost / custom
token pricing, prompt-backend caching) are unaffected.

### Multi-invocation session grouping

Session grouping is a property of the sessions model, not of suspend / resume.
The sessions identity trio scopes `session_id` across **many invocations**
(sessions capability §3): in sessioned mode the harness threads the same
`session_id` into every turn's `invoke()`, and each turn is a distinct
invocation with its own `invocation_id` — hence its own Langfuse trace per
§8.4.1's `trace.id` derivation. Every one of those traces carries the same
`trace.sessionId`, so Langfuse renders the turns as one Session. `trace.userId`
populates per-invocation from the `userId` caller metadata in scope for that
turn (0034's per-invocation metadata model).

Two adjacent cases preserve the binding:

- **Detached traces (§4.4).** `session_id` is unchanged across detached /
  parent traces, so a detached child trace carries the parent's
  `trace.sessionId` and groups with it.
- **Suspend / resume.** A session-bound invocation that suspends and resumes
  remains the same session-bound invocation; its trace(s) carry the session id
  unchanged. Session grouping follows the `session_id` the sessions capability
  holds across the session's invocations, not the resume mechanics.

## Conformance test impact

### New fixture

A new fixture under `observability/conformance/` (number assigned at
acceptance) exercises the two promotions:

- **Case 1 — session-bound invocation.** `invoke()` with a `session_id`;
  assert `trace.sessionId` equals the supplied session id.
- **Case 2 — not session-bound.** `invoke()` with no `session_id`; assert
  `trace.sessionId` is unset.
- **Case 3 — `userId` in caller metadata.** An `invoke()` whose caller
  metadata contains a `userId` key; assert `trace.userId` equals the value AND
  the value also appears at top-level `trace.metadata.userId` (additive
  promotion).
- **Case 4 — no `userId` key.** An `invoke()` whose caller metadata lacks
  `userId`; assert `trace.userId` is unset and other metadata is unaffected.
- **Case 5 — multi-invocation grouping.** Two separate session-bound `invoke()`
  calls sharing one `session_id`; assert each produces a distinct Langfuse trace
  (distinct `trace.id`) and both carry the **same** `trace.sessionId`.

### Unaffected

Existing §8 Langfuse fixtures continue to assert their existing payloads; this
proposal adds new Trace-level field expectations rather than changing existing
ones. The existing caller-metadata fixtures (027, 029, 030) remain valid — the
`userId` promotion is additive, so `trace.metadata.userId` still appears where a
caller supplies it.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments
(concrete version assigned at acceptance):

- §8.4.1 gains two mapping-table rows (`trace.sessionId`, `trace.userId`) and
  the *Session / user trace-field sourcing* paragraph.
- §8.10's *Langfuse Sessions* out-of-scope bullet is removed (realized).
- A new conformance fixture exercises both promotions across five cases
  (session-bound / not, `userId` present / absent, multi-invocation grouping).

**Behavior-change note.** A caller already supplying `userId` as invocation
metadata (landing only in `trace.metadata.userId` today) will, after this
lands, also see it populate the first-class `trace.userId` field — almost
always the desired outcome, and the reason `userId` is recognized rather than
reserved. A caller already working around the gap by setting the session / user
ids via direct Langfuse SDK trace-update calls will see OA-observer values
appear on the same fields; both paths write via the Langfuse SDK's OTel
attribute mechanism, so write order determines the final value (the same
clobbering caveat 0043 documented for `trace.input` / `trace.output`).
Migration path: drop the direct calls and rely on the session id + `userId`
metadata.

## Out of scope

- **First-class `userId` invoke argument.** Rejected: a user id has no runtime
  semantics in OA (unlike `session_id`, which loads / persists session state),
  so introducing an engine invoke surface for a purely observability dimension
  is the wrong layer. The observer-side promotion from caller metadata keeps
  the concern where the Langfuse mapping lives. (See Motivation.)
- **OTel-mapping equivalent.** OpenTelemetry has no trace-level session / user
  field. The OTel side already carries `openarmature.session_id` and
  `openarmature.user.*` as span attributes; no OTel change is made. Same
  data-model asymmetry 0043 noted for `trace.input` / `trace.output`.
- **Configurable promotion key name.** `userId` is fixed as the recognized key
  in v1. An observer-construction option naming a different promotion key
  (paralleling 0043's observer-side hooks) — for callers whose convention
  differs, or who use `userId` to mean a non-end-user id — is a natural future
  tightening, deferred until that need surfaces.
- **`trace.tags`.** Langfuse's Trace `tags` field (free-form filtering labels)
  is a separate cross-trace surface with no current OA source; mapping it would
  need a tags concept OA does not have. Out of scope; lands on its own merits
  if a source surfaces.
- **Langfuse Scoring / Cost.** Unchanged from §8.10 — still deferred to their
  own proposals (the `openarmature.score.*` family and a cost-tracking
  capability respectively).

## Alternatives considered

- **First-class `userId` invoke argument** (symmetric with `session_id`).
  Rejected — see Out of scope. The symmetry is superficial: `session_id` is
  first-class because it has state semantics; `userId` is observability-only.
- **`user_id` (snake_case) as the recognized key.** Rejected: snake_case is
  OA's convention for keys it *emits* (the §3.4 / §8.4 reserved set), but the
  recognized key is one the caller *supplies* and OA *reads*. Matching the
  target field (Langfuse `trace.userId`) and §3.4's caller-metadata examples
  (`userId`) with zero translation is the more ergonomic choice for a
  caller-facing key.
- **Opt-in promotion** (a flag that must be enabled before `userId` is
  promoted). Rejected for v1: it defeats the zero-config benefit — the data
  already flows and the dashboard is blank only because the field isn't set.
  Automatic recognition of an unambiguous key is the higher-value default; the
  configurable-key escape hatch (Out of scope) covers the rare mis-promotion
  case without gating the common one.
- **Observer-construction hook `user_id_from_state(state)`** (paralleling
  0043's `trace_input_from_state`). Rejected for v1: a user id is known at
  invoke time, not derived from evolving state, so a state-reading hook is
  heavier than needed. The caller-metadata channel (0034) already carries
  invoke-time context; recognizing a key in it is the lighter mechanism. (A
  configurable key name is the residual flexibility, deferred under Out of
  scope.)
- **Reserve `userId` as an OA key** (per 0041 / 0042). Rejected: those
  proposals reserve OA-*emitted* keys so caller keys cannot silently shadow
  them. `userId` is the inverse — a caller key OA *reads and promotes* — so
  reserving (rejecting) it would defeat the feature. It is recognized, not
  reserved.
- **Map `session_id` only, defer `userId`.** Rejected: both fields are gated on
  the same §8.10 deferral, both sources already exist (one as an attribute, one
  as caller metadata), and the Users dashboard is the natural companion to the
  Sessions dashboard. Splitting them would leave a half-realized §8.10 bullet
  and a second near-identical proposal for no benefit.
- **Do nothing.** Leave `trace.sessionId` / `trace.userId` blank for OA-emitted
  Langfuse traces. Rejected: multi-turn session grouping is the headline
  Langfuse affordance for agent workloads, the data already flows, and the
  application-level trace-update workaround duplicates wiring and bypasses the
  observer abstraction — the same disposition 0043 reached.
