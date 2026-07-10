# 0095: Adaptive Call-Level Retry (Per-Attempt Request Override + Structured-Output Reask)

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-02
- **Accepted:** 2026-07-09
- **Targets:** spec/llm-provider/spec.md **§7.1 Call-level retry** — extend the in-call retry loop with two
  opt-in, LLM-completion-specific behaviors: (1) a **per-attempt request override** that varies the call's
  sampling (`RuntimeConfig`) across attempts (e.g. an escalating temperature schedule), and (2)
  **structured-output reask** — treating `structured_output_invalid` (§7) as retryable at the call level
  and, per failure, appending the model's raw output plus a **caller-authored** correction (from the caller's
  builder, fed the raised error's failure surface) to the next attempt's messages so it is *informed* rather
  than a byte-identical replay. §5 `complete()` gains the opt-in surface
  that carries these. **No change** to the generic pipeline-utilities §6.1 retry middleware (it retries
  arbitrary node chains and has no notion of sampling or messages — these behaviors are inherently
  completion-specific and live at the call level). Also **spec/conformance-adapter/spec.md §5.11**
  (new) — the fixture directives these behaviors need: `per_attempt_override` and a `reask` template
  on `call.retry`, plus the `expected.wire_requests` per-attempt outbound-request assertion.
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

1. **Per-attempt request override** — a declarative override *schedule* (canonically an escalating
   temperature schedule) applied to retries: attempt 0 is the caller's base `config`, and the *i*-th override
   applies to retry *i*, so retries are not identical replays.
2. **Structured-output reask** — an opt-in that (a) treats `structured_output_invalid` as retryable at the
   call level without the caller writing a custom classifier, and (b) on each such failure appends the model's
   raw output (as an `assistant` message) plus a **caller-authored** correction (as a `user` message) to a
   working transcript that accumulates across retries. OA hands the caller's builder the raised error's
   failure surface (0082 — the invalid `output_content` + the `error_message` reason); the caller writes the
   words. **OA ships no prompt of its own** — the appended `assistant` message is the model's verbatim output.

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

When the caller supplies a **per-attempt request override**, the loop applies it — a declarative
*retry* schedule of `RuntimeConfig` partial-overrides (the canonical form: an escalating temperature
schedule such as `[0.3, 0.6]`), not a mutating callback. **Attempt 0 always uses the caller's base `config`
unmodified**; the schedule applies to retries — retry *i* (attempt *i+1*) uses the base config with the
*i*-th override merged on top (the override's fields replace the base, unspecified fields inherited; a
general `RuntimeConfig` partial, the canonical case overriding only sampling). Overrides take effect only
after the base attempt fails. When the schedule is shorter than the retry count, the last entry carries
forward.

`complete()` MUST NOT mutate the caller's `config` (§5 immutability) — the override is applied to an
internal per-attempt copy. `on_retry` stays observe-only; the override is the declarative mutation surface.

### llm-provider §7.1 — structured-output reask

`reask` is an opt-in **caller-supplied corrective-message builder** (not a boolean). When present:

1. **Retryable-by-opt-in.** The call-level loop treats `structured_output_invalid` (§7) as retryable **for
   this call**, without the caller supplying a custom `classifier` (the §6.1 default classifier is unchanged;
   this is a call-level convenience layered on top). Reask attempts consume the **`max_attempts`** budget —
   there is no separate `max_reask`.
2. **Caller-authored corrective message.** On a `structured_output_invalid` attempt, before the next attempt
   the loop invokes the caller's `reask` builder with the raised error's **0082** failure surface — the
   verbatim failed `output_content` (what the model produced) and the failure description on `error_message`
   (why it failed) — and appends **two** messages to a working transcript: the model's raw output as an
   `assistant` message, then the builder's returned content as a `user` message. The transcript starts as a
   copy of the caller's `messages` and **accumulates** these pairs across reask retries, keeping the sequence
   role-alternating (Anthropic forbids consecutive same-role messages — §8.2). **OA authors no
   prompt text of its own** (charter §3.1 principle 7, *No built-in prompts* — the `assistant` message is the
   model's verbatim output and the caller owns every word OA adds beyond it; OA owns only the retry loop and
   the typed error surface). `complete()` MUST NOT mutate the caller's `messages`; the working transcript is
   an internal copy.

Reask and the per-attempt override **compose**: the canonical self-heal is escalating temperature *plus* a
caller-authored reask on each `structured_output_invalid`.

### §5 `complete()` — the opt-in surface

`complete()` carries the two behaviors via the §7.1 `retry` parameter, which accepts an **llm-provider
retry-config** that extends the pipeline-utilities §6.1 four-field record with two optional fields:
`per_attempt_override` (the retry override schedule) and `reask` (the caller's corrective-message builder).
A plain §6.1 record — or nothing — preserves current behavior. The §5 "MUST NOT mutate `messages` /
`config`" contract holds — all per-attempt variation is on internal copies.

## Conformance test impact

The behaviors manifest on the **outbound request**, so the fixtures use the new conformance-adapter
§5.11 directives — the `per_attempt_override` / `reask: {template}` fields on `call.retry`, the
per-attempt `expected.wire_requests` assertion (`sampling`; `appended_messages`, the appended
`assistant`-output + `user`-correction pairs), and `attributes_absent` for the attempt-0 span. Six new
llm-provider fixtures, **061–066** (`retry_reason` and its attempt-0 exclusion are asserted across them,
not as a separate fixture):

- **061 — per-attempt override (retry schedule).** A retry loop with a temperature schedule: attempt 0 uses
  the base `config`; retry *i* (attempt *i+1*) applies the *i*-th override to the outbound wire request
  (assert attempt 0 is base and each retry's sampling differs per the schedule); retries carry
  `retry_reason = transient` while attempt 0 asserts `attributes_absent` for `retry_reason`; the caller's
  `config` is unmutated.
- **062 — reask success.** A `structured_output_invalid` on attempt 0 with a `reask` builder → OA appends the
  model's raw output (`assistant`) plus the builder's rendered correction (`user`); attempt 1 validates. With
  a deterministic (`{output_content}`-only) template, assert the appended `user` message equals the builder's
  output **exactly** (OA adds no prompt of its own); attempt 1 carries `retry_reason = reask`; the caller's
  `messages` are unmutated.
- **063 — reask budget exhausted.** `max_attempts` reached with every attempt invalid → the final
  `structured_output_invalid` raises to the caller.
- **064 — reask off by default.** Without a `reask` builder, `structured_output_invalid` raises on the first
  failure (no retry; the second mock response is never consumed) — the current behavior is preserved.
- **065 — compose + accumulate.** Escalating temperature *plus* reask: each reask retry applies both its
  scheduled override and the appended correction, and the working transcript **accumulates** across the two
  reask retries (attempt 2 carries both prior `assistant` / `user` pairs).
- **066 — mixed transient + reask interleave.** A reask retry (attempt 1) followed by a transient retry
  (attempt 2): the transient retry re-sends the accumulated transcript and appends nothing new, and the two
  attempts carry distinct `retry_reason` values (`reask`, then `transient`) in one loop.

## Versioning

**MINOR bump** (pre-1.0), additive: two opt-in call-level retry behaviors; the §7.1 default (transient-only,
byte-identical replay) and the generic §6.1 middleware are unchanged, so existing callers are unaffected.
**Sequencing:** the **reask** half depends on **0082** — the `structured_output_invalid` error must carry
`output_content` + the `error_message` description to feed back. 0082 is Accepted (its error surface
exists), so reask is spec-acceptable now; a downstream implementation MUST NOT ship reask ahead of its own
0082 implementation. The per-attempt override half is independent of 0082. Ships as spec **v0.91.0**.

## Alternatives considered

1. **A mutating `on_retry` callback** (return an overriding `RuntimeConfig` / messages). Reject — a mutating
   callback is hard to spec behaviorally and to conformance-test uniformly across implementations, and it
   overloads `on_retry`'s observe-only contract (§6.1). A declarative override schedule is
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
5. **An OA-authored reask prompt** (the framework builds the corrective message from the error surface; the
   caller opts in with a flag). Reject — OA injecting prompt text it authored into the model conversation is
   a hidden/magical prompt, contrary to charter §3.1 principle 7, *No built-in prompts* (OA is a workflow
   framework, not a prompt library; the caller owns every word reaching the model). The caller supplies the
   corrective-message builder; OA provides only the typed 0082 error surface and the retry loop.

## Resolved at Accept

- **Config placement → llm-provider-scoped superset of the §6.1 retry record.** The two behaviors ride an
  llm-provider retry-config that extends the §6.1 four-field record with two optional fields
  (`per_attempt_override`, `reask`), accepted by the §7.1 `retry` parameter. One unified retry surface; the
  generic pipeline-utilities §6.1 record is unchanged (the superset is llm-provider-specific). A plain §6.1
  record passed to `retry` yields the existing transient-only behavior.
- **Reask corrective-message → caller-authored; OA ships no prompt.** `reask` is a **caller-supplied
  builder**, not a boolean. OA treats `structured_output_invalid` as retryable-for-this-call and invokes the
  builder with the raised error's 0082 surface (the verbatim invalid `output_content` + the `error_message`
  reason). Per attempt, OA appends **two** messages to a working transcript — the model's raw output as an
  `assistant` message, then the builder's returned content as a `user` message — and this **accumulates**
  across reask retries, keeping the sequence role-alternating (Anthropic forbids consecutive same-role
  messages — §8.2). OA authors **no** prompt text — honoring charter §3.1 principle 7, *No built-in prompts* (the
  `assistant` message is the model's verbatim output; OA owns only the retry loop and the typed error
  surface; the caller owns every word OA adds beyond the model's own). Absent a builder, reask is off.
  Fixture 062 asserts the appended `user` message equals the builder's output **exactly** (a deterministic
  `{output_content}`-only template); 063 / 065 assert it via `content_contains` where the template
  interpolates the impl-defined `{error_message}`.
- **Override breadth + indexing → general `RuntimeConfig` partial; a retry schedule (base excluded).** The
  per-attempt override is a general `RuntimeConfig` partial-override, not sampling-only (temperature schedule
  canonical). **Attempt 0 is always the caller's base `config`, unmodified**; the override sequence is the
  *retry* schedule — the *i*-th entry applies to retry *i* (attempt *i+1*), merged onto base (its fields
  replace base, unspecified inherited). Overrides take effect only after base fails. When the sequence is
  shorter than the retry count, the **last entry carries forward**.
- **Budget → reuse `max_attempts`; no `max_reask`.** A reask attempt is a retry and consumes a `max_attempts`
  attempt; one budget, one loop. The §7.1 × §6.1 *multiplicative budget* pitfall (0050) is unchanged — reask
  adds no new multiplication layer — and §7.1's existing caveat covers it.
- **Observability → minimal `retry_reason` discriminator now; full mapping a follow-on.** The §7.1
  per-attempt span carries a new `openarmature.llm.retry_reason` attribute (`transient` | `reask`) on retry
  attempts, sibling to `attempt_index`. The detailed observability §5.5 / Langfuse rendering of it is a
  follow-on; this proposal introduces the attribute and asserts it in a fixture.

## Out of scope

- **The generic pipeline-utilities §6.1 retry middleware** — unchanged; these behaviors are call-level only.
- **0082 itself** — already Accepted; this builds on its error surface (and depends on it for reask).
- **Reask for non-structured-output failures** (e.g. tool-call malformation) — this proposal is scoped to
  `structured_output_invalid`.
- **Provider-side determinism guarantees** — out of scope; the override addresses the determinism trap from
  the client side (varying the request), not by constraining provider behavior.
