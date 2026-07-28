# 0110: Remove the reask assistant-prefill continuation branch

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-27
- **Accepted:** 2026-07-27
- **Ships as:** v0.104.1
- **Targets:** spec/llm-provider/spec.md **§7.1** (remove the reask working-transcript's
  *assistant-prefill continuation* clause — the branch that fires "when the working transcript's last
  message is already an `assistant` message (e.g. a caller prefill)"); spec/conformance-adapter/spec.md
  **§5.11** (remove the full-list `wire_requests[*].messages` sub-form, whose sole documented purpose is
  asserting that continuation); conformance: **remove** llm-provider fixture
  `067-call-level-reask-assistant-prefill-continuation` (`.md` + `.yaml`), the branch's only fixture.
- **Related:** 0095 (introduced the reask feature, the continuation clause, fixture 067, and the §5.11
  `messages` sub-form — this retracts that one branch and leaves the rest of 0095 in force), 0082
  (`structured_output_invalid` is the failure reask makes retryable — unchanged)
- **Supersedes:**

## Summary

0095's structured-output reask specifies a working transcript that starts from the caller's `messages`
and, on each `structured_output_invalid` retry, appends the model's raw output as an `assistant` message
plus the caller's correction as a `user` message. One sub-clause handles a special case: *when the
transcript's last message is already an `assistant` message (a caller prefill), the model's output
**continues** that message rather than starting a new one.* Fixture 067 exercises exactly that, and the
conformance-adapter §5.11 full-list `messages` directive exists only to assert it.

That branch is **unreachable**. llm-provider §3 already requires — as a hard MUST, with mandatory
pre-send validation — that the last message handed to `complete()` be `user` or `tool`; a caller cannot
supply a trailing `assistant` prefill without the call raising `provider_invalid_request` first. So the
one input that would put an `assistant` message last in the transcript is rejected before reask runs.
The continuation branch, its fixture, and its bespoke assertion directive are dead code that contradicts
§3, and fixture 067 is **unsatisfiable against a conforming implementation** (one that validates §3 as
required raises `provider_invalid_request` on 067's input and can never reach the asserted success).

This proposal removes the branch, the fixture, and the directive. No reachable behavior changes.

## Motivation

The contradiction is a governance-level defect: two sections of the same spec prescribe incompatible
things for the same input, and a shipped conformance fixture cannot be satisfied by a conforming
implementation. A reference implementation surfaced it directly — an implementation that correctly
enforces the §3 MUST rejects fixture 067's input, so 067 fails not because the implementation is wrong
but because the fixture asks it to violate §3.

The deeper cause is that 0095 introduced first-class **prefill** support (a caller starting the
assistant turn, e.g. `{role: assistant, content: "Sure: "}`) as a side effect of reask, in a spec that
does not support prefill as an input anywhere. §3 forbids a trailing `assistant` message; no §8.x wire
mapping handles prefill continuation; nothing outside the 0095 reask clause mentions it. Prefill is a
real and useful technique, but it is provider-specific (Anthropic continues a trailing `assistant`
message; OpenAI-compatible and Gemini treat it differently), so blessing it belongs in a deliberate,
cross-provider proposal that amends §3 and every mapping — not in a reask footnote that one mapping's
fixture silently assumes. Removing the branch now settles the contradiction; a future proposal MAY add
prefill as a proper first-class input if cross-provider demand warrants.

### Reachability proof (why removal is non-behavioral)

The continuation branch fires only when the reask working transcript's **last message is `assistant`**
at the moment reask appends. Trace every way the transcript can end:

1. It **starts** as a copy of the caller's `messages`. Per §3 those end in `user` or `tool` (MUST,
   validated pre-send) — never `assistant`.
2. A **reask** retry appends `[assistant output, user correction]` — ending in `user`.
3. A **transient** retry appends nothing — the ending is unchanged.

So the transcript ends in `user`/`tool` in every case, and the "last message is already `assistant`"
condition is only ever true if the caller supplied a trailing-`assistant` prefill — which §3 rejects
before the retry loop runs. The branch is therefore unreachable for any implementation that enforces §3,
which every conforming implementation MUST. Removing it changes no reachable behavior; appending the
model's output as a fresh `assistant` message (the general rule that remains) is always valid because the
transcript never ends in `assistant`, so it never produces the consecutive-`assistant` sequence §8.2
forbids.

## Proposal

### 1. llm-provider §7.1 — remove the assistant-prefill continuation clause

In the `reask` extension text, the sentence currently reads (verbatim):

> The `assistant` message carries the attempt's output as the text the error surfaces on
> `output_content` (§7 / 0082); when the working transcript's last message is already an `assistant`
> message (e.g. a caller prefill), the output **continues** that message — concatenated onto its content
> verbatim, with no OA-added separator — rather than starting a new one, so alternation still holds.

The continuation clause (everything from the semicolon onward) is removed, leaving:

> The `assistant` message carries the attempt's output as the text the error surfaces on
> `output_content` (§7 / 0082).

The surviving rule is unchanged and unambiguous: the model's raw output is appended as an `assistant`
message and the builder's correction as a `user` message, keeping the sequence role-alternating. The
reachability proof above guarantees this never yields consecutive `assistant` messages. Every other reask
obligation (transcript accumulation, the single `max_attempts` budget, the builder invoked only when a
further attempt remains, transient retries appending nothing, OA authoring no text of its own) is
untouched.

### 2. conformance-adapter §5.11 — remove the full-list `wire_requests[*].messages` sub-form

§5.11's per-attempt `wire_requests` directive documents two message-assertion sub-forms:
`appended_messages` (the ordered pairs a reask retry appends after the caller's messages) and the
full-list `messages` (the whole outbound list). The full-list form earns its keep **only** when a retry
*modifies* a caller message rather than only appending after it — a case `appended_messages` cannot
express — and the assistant-prefill continuation was the **sole** modifying case the retry loop defined
(fixture 067 is its only user; every other reask fixture asserts via `appended_messages`). With the
continuation branch gone, every reachable retry-loop attempt is **append-only**, so `appended_messages`
covers all of them and the full-list `messages` form is not merely unused but **uncoverable**: no
reachable fixture, present or future, could exercise it that `appended_messages` could not. It is removed.
`appended_messages` (and the `sampling` and `attributes_absent` directives) are unchanged, as is the
single-request `expected_wire_request.messages` whole-list assertion the provider wire-mapping fixtures
use (a separate directive, untouched). This keeps the conformance-adapter directive vocabulary matched to
what fixtures actually use, per the 0107 principle that documented directives track real fixture usage.

### 3. Conformance — remove fixture 067

`spec/llm-provider/conformance/067-call-level-reask-assistant-prefill-continuation.{md,yaml}` is removed.
It is the continuation branch's only fixture and is unsatisfiable against a §3-conforming implementation.
The reachable reask behavior stays fully covered by fixtures 062–066 (success, budget exhausted,
off-by-default, override compose, transient interleave). No fixture is renumbered — conformance fixtures
are addressed by filename, and the corpus tolerates a gap at 067.

## Conformance

- **Removed:** llm-provider fixture `067-call-level-reask-assistant-prefill-continuation`. No fixture is
  added — this proposal removes an unsatisfiable fixture for an unreachable branch and adds no new
  behavior to cover. The reachable reask surface remains covered by 062–066.

## Versioning

**PATCH** (whole-spec SemVer) — **v0.104.1**. Non-behavioral: the removed §7.1 clause, §5.11 sub-form,
and fixture 067 all describe a branch unreachable under the §3 message-ordering MUST, so no conforming
implementation's behavior changes and none can newly fail (the removal deletes an expectation, and one
that no conforming implementation could satisfy). This is the clarification/erratum class
(governance §"Spec versioning": *clarification … or non-behavioral change*). Two capabilities' `Latest`
advance to the shipped version (llm-provider and conformance-adapter both change), as their spec text is
edited; neither gains or loses behavior.

## Open questions

- **First-class prefill support** is deliberately out of scope. If a caller-supplied trailing-`assistant`
  prefill is worth supporting as an input, it earns its own proposal that amends §3's message-ordering
  MUST and specifies the continuation semantics across every §8.x wire mapping (Anthropic, OpenAI-
  compatible, Gemini), whose native trailing-`assistant` behavior differs. That is a MINOR feature
  addition, not this erratum.
