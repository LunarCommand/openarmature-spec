# 0095: Adaptive Call-Level Retry (Per-Attempt Request Override + Structured-Output Reask)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-02
- **Targets:** spec/llm-provider/spec.md **§7.1 Call-level retry** — extend the in-call retry loop with two
  opt-in, LLM-completion-specific behaviors: (1) a **per-attempt request override** that varies the call's
  sampling (`RuntimeConfig`) across attempts (e.g. an escalating temperature schedule), and (2)
  **structured-output reask** — treating `structured_output_invalid` (§7) as retryable at the call level
  and appending a corrective message, built from the raised error's failure surface, to the next attempt's
  messages so it is *informed* rather than a byte-identical replay. §5 `complete()` gains the opt-in surface
  that carries these. **No change** to the generic pipeline-utilities §6.1 retry middleware (it retries
  arbitrary node chains and has no notion of sampling or messages — these behaviors are inherently
  completion-specific and live at the call level).
- **Related:** 0050 (created §7.1 call-level retry + the §6.1 retry-config record this builds on),
  0082 (structured-output failure diagnostics — the reask half feeds back **0082's** error surface:
  the verbatim `output_content` + the failure description on `error_message`; **prerequisite for reask**)
- **Supersedes:**

## Summary

Call-level retry (§7.1) today replays a **byte-identical** request each attempt. For transient failures
that's correct. For `structured_output_invalid` — bad JSON / schema mismatch — it is close to useless: a
byte-identical replay at `temperature = 0` tends to reproduce the same invalid output (it varies only by
server-side nondeterminism, which is real but not guaranteed), so retry is least reliable exactly where a
self-heal is most wanted. And the model gets **no signal** about what was wrong.

This proposal makes the call-level retry loop **adaptive**, via two opt-in behaviors that compose:

1. **Per-attempt request override** — a declarative, attempt-indexed `RuntimeConfig` override (canonically
   an escalating temperature schedule) applied to the next attempt, so retries are not identical replays.
2. **Structured-output reask** — an opt-in that (a) treats `structured_output_invalid` as retryable at the
   call level without the caller writing a custom classifier, and (b) appends a corrective message —
   constructed from the raised error's failure surface (0082) — to the next attempt's messages, so attempt
   *k+1* is told what to fix.

Together they turn a structured-output call into a single self-healing pass (retry-until-valid with
escalating sampling and informed reask) instead of degrading a node or failing the invocation.

## Motivation

Small or quantized models producing structured output intermittently emit structurally-invalid items
(non-finite floats, empty required fields, wrong shape). The natural remedy is *retry the same call until it
validates, nudging the request each time* — but §7.1 as it stands can't express it:

- **Retries are identical replays.** The wire request is assembled once and replayed unchanged each attempt;
  `on_retry` (§6.1) is observe-only (`(exception, attempt_index) -> None`) and cannot vary the next attempt.
  At `temperature = 0` an identical replay tends to reproduce the same invalid output — retry-on-validation
  is least reliable precisely when it's needed. Varying sampling per attempt (escalating temperature) breaks
  the determinism trap.
- **No reask.** `structured_output_invalid` (post-0082) carries the verbatim failed `output_content` and a
  failure description on `error_message`, but nothing feeds that back into the next attempt — the model
  re-rolls blind.

Both are inherently **completion-level** concerns (sampling, messages), so they belong at §7.1's call-level
retry, not the generic §6.1 middleware (which retries opaque node chains). And they're general: without OA
owning this, every consumer reimplements an app-level retry-until-valid wrapper around `complete()`.

## Proposed change

All behavior below is **opt-in** at the call level; absent it, §7.1 retry is unchanged (byte-identical
replay of transient failures only).

### llm-provider §7.1 — per-attempt request override

The call-level retry loop MAY apply a caller-supplied **per-attempt request override** that adjusts the
call's `RuntimeConfig` (§6) for each attempt. It is **declarative** — an attempt-indexed sequence of config
overrides (the canonical form: a temperature schedule such as `[0.0, 0.3, 0.6]`) — not a mutating callback.
Attempt 0 uses the caller's base `config`; attempt *k* uses the base config with the *k*-th override applied
(sampling fields overridden, unspecified fields inherited). When the sequence is shorter than the attempt
count, the last entry (or the base config — settled at Accept) applies to further attempts.

`complete()` MUST NOT mutate the caller's `config` (§5 immutability) — the override is applied to an
internal per-attempt copy. `on_retry` stays observe-only; the override is the declarative mutation surface.

### llm-provider §7.1 — structured-output reask

An opt-in **reask** behavior:

1. **Retryable-by-opt-in.** When reask is enabled, the call-level loop treats `structured_output_invalid`
   (§7) as retryable **for this call**, without the caller supplying a custom `classifier` (the §6.1 default
   classifier is unchanged; this is a call-level convenience layered on top). A reask budget (`max_reask`,
   or reuse of `max_attempts` — settled at Accept) bounds it.
2. **Informed retry.** On a `structured_output_invalid` attempt, before the next attempt the loop **appends a
   corrective message** to the message list, constructed from the raised error's **0082** failure surface:
   the verbatim failed `output_content` (what the model produced) and the failure description on
   `error_message` (why it failed). The corrective message instructs the model to correct that specific
   problem. `complete()` MUST NOT mutate the caller's `messages`; the corrective message is appended to an
   internal per-attempt copy.

Reask and the per-attempt override **compose**: the canonical self-heal is escalating temperature *plus*
informed reask on each `structured_output_invalid`.

### §5 `complete()` — the opt-in surface

`complete()` gains the opt-in carrier for the two behaviors above (exact placement settled at Accept — see
Open questions: an llm-provider-scoped superset of the §6.1 retry record accepted by the `retry` parameter,
vs. dedicated `complete()` parameters). The default (nothing supplied) preserves current behavior. The §5
"MUST NOT mutate `messages` / `config`" contract holds — all per-attempt variation is on internal copies.

## Conformance test impact

New llm-provider fixtures (numbers at Accept):

- **Per-attempt sampling override.** A retry loop with a temperature schedule applies the *k*-th override to
  attempt *k*'s wire request (assert the outbound request's sampling differs per attempt); the caller's
  `config` is unmutated.
- **Reask success.** A `structured_output_invalid` on attempt 0, reask enabled → attempt 1's messages carry
  the appended corrective message (built from the error's `output_content` + `error_message`) and validate;
  the caller's `messages` are unmutated.
- **Reask budget exhausted.** `max_reask` (or `max_attempts`) reached with every attempt invalid → the final
  `structured_output_invalid` raises to the caller.
- **Reask off by default.** Without opting in, a `structured_output_invalid` still raises on the first
  failure (no implicit retry) — the current behavior is preserved.
- **Compose.** Escalating temperature + reask on the same loop.

## Versioning

**MINOR bump** (pre-1.0), additive: two opt-in call-level retry behaviors; the §7.1 default (transient-only,
byte-identical replay) and the generic §6.1 middleware are unchanged, so existing callers are unaffected.
**Sequencing:** the **reask** half depends on **0082** (the `structured_output_invalid` error must carry
`output_content` + the `error_message` description to feed back) — reask MUST NOT be accepted/implemented
ahead of 0082. The per-attempt override half is independent of 0082. Tentative spec version target deferred
to Accept.

## Alternatives considered

1. **A mutating `on_retry` callback** (return an overriding `RuntimeConfig` / messages). Reject — a mutating
   callback is hard to spec behaviorally and to conformance-test uniformly across implementations, and it
   overloads `on_retry`'s observe-only contract (§6.1). A declarative attempt-indexed override is
   cross-impl-clean and testable; keep `on_retry` observe-only.
2. **Put the override / reask on the generic §6.1 retry middleware.** Reject — §6.1 retries arbitrary node
   chains and has no notion of sampling or messages. Per-attempt sampling and message reask are
   completion-specific; they belong at the LLM-specific call-level (§7.1). Widening the framework-agnostic
   §6.1 record with LLM-only fields would pollute it.
3. **Split into two proposals** (per-attempt override; reask). Considered — they're separable (the override
   doesn't depend on 0082; reask does). Kept as one because both are §7.1 call-level retry extensions and
   they compose into the single self-heal use case that motivates them. If Accept prefers, the reask half
   can be carved to a follow-on gated on 0082 while the override lands first.
4. **Leave it to an app-level retry-until-valid wrapper (status quo).** Reject — the identical-replay
   limitation forces every consumer to reimplement the loop around `complete()`; self-healing structured
   output is a general enough need for OA to own natively and specify uniformly.

## Open questions

- **Config placement.** Do the two behaviors ride an **llm-provider-scoped superset** of the §6.1 retry
  record (accepted by the §7.1 `retry` parameter), or **dedicated `complete()` parameters** (e.g. a
  `reask` config + a per-attempt override)? The former keeps one retry surface; the latter keeps the §6.1
  record pristine. Settle at Accept.
- **Reask corrective-message role + wording.** Is the appended message a `user` or `system` message, and is
  its wording spec-pinned (for cross-impl determinism / conformance) or implementation-chosen with only the
  *content sources* (`output_content` + `error_message`) pinned? Leaning: pin the sources, leave exact
  phrasing to the implementation, and have fixtures assert the sources are present.
- **Override breadth.** Sampling-only override, or a full `RuntimeConfig` override? Leaning sampling-focused
  (the motivating case) but expressible as a general config override.
- **Budget.** A dedicated `max_reask` vs. reusing `max_attempts`; and the interaction with the §7.1 /
  §6.1 *multiplicative budget* pitfall (0050) when a per-node retry wraps a call-level reask loop.
- **Observability.** Should a reask attempt be marked distinctly from a transient retry on the per-attempt
  span / event (§7.1 emits one span per attempt)? Possibly a follow-on; out of scope here unless trivial.

## Out of scope

- **The generic pipeline-utilities §6.1 retry middleware** — unchanged; these behaviors are call-level only.
- **0082 itself** — already Accepted; this builds on its error surface (and depends on it for reask).
- **Reask for non-structured-output failures** (e.g. tool-call malformation) — this proposal is scoped to
  `structured_output_invalid`.
- **Provider-side determinism guarantees** — out of scope; the override addresses the determinism trap from
  the client side (varying the request), not by constraining provider behavior.
