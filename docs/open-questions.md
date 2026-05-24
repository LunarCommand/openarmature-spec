# Open questions backlog

Unresolved open questions surfaced in Accepted proposals. Captured here so
they don't get lost between releases, and so a future proposal drafting in
a related area can find prior discussion of the topic in one place.

This page does not list open questions from Draft proposals — those are
in-flight and get resolved during the acceptance pass. Once a proposal is
Accepted, any remaining Open Questions section migrates here.

**Status tags:**

- **still-relevant** — unresolved, still defers cleanly. Likely addressed by
  a follow-on proposal when signal accumulates.
- **resolved-by-acceptance** — the proposal's acceptance pass effectively
  decided the question (e.g., by picking one of two alternatives in the
  proposal text). Kept on the page for retrieval, marked as closed.
- **inherited** — restates a constraint from an earlier proposal; not a
  novel question. Kept for cross-referencing only.
- **candidate-for-new-proposal** — signal has accumulated; this OQ should
  drive a new proposal. (None currently.)

**Grooming cadence:** trigger-based. The questions get classified here when
(a) a proposal is being drafted in a related area, (b) ~5 acceptance passes
have stacked since the last grooming, or (c) every 6 months as a fallback —
whichever fires first. This page is the load-bearing artifact; the cadence
is just "keep it not-too-stale."

---

## graph-engine

### 0012 — completed event after edges

- **Existing fixture 014 sub-case for routing_error.**
  [resolved-by-acceptance] — proposal text resolved to "020 alone (keeps
  fixtures topical)." The decision is embedded in the conformance suite as
  fixture 020.
- **Edge_exception fixture coverage today.**
  [still-relevant] — the proposal noted a phase 6.1 investigation would
  potentially surface coverage gaps. Hasn't been swept since.

## pipeline-utilities

### 0004 — middleware

- **Per-conditional-branch middleware.**
  [still-relevant] — deferred at acceptance; workaround documented
  (set a state marker at the routing node and branch on it inside per-node
  middleware). Revisit if real workflows surface that the workarounds don't
  cover. No signal accumulated yet.

### 0009 — per-instance fan-out resume

- **Does configurable batching also apply to subgraph-internal saves?**
  [still-relevant] — subgraph internals fire saves per §10.3 (unchanged from
  0008), and a long-running subgraph with many inner nodes could face
  similar volume concerns to fan-outs. Proposal explicitly scopes the §10.11.4
  batching knob to fan-out internals only for clarity; a follow-on can
  extend if signal demonstrates the need.
- **Should `fan_out_progress` be visible in the `list()` summary?**
  [still-relevant] — a user inspecting saved invocations might want to see
  "fan-out X is at instance 800 of 1000" without loading the full record.
  Lean was NOT-in-v2; add as a separate optimization if backends want richer
  summaries.
- **What happens if the graph topology changed between crash and resume
  (e.g., the user edited the fan-out's inner subgraph)?**
  [inherited] — restates 0008's "out of scope" declaration for
  resume-after-code-change. The resumed graph MUST be structurally
  identical to the original. Not a novel question; kept for cross-reference.

### 0011 — parallel branches

- **Branch ordering source.**
  [resolved-by-acceptance] — proposal's "lean" became the spec: insertion-
  order semantics mandated; implementations may use any equivalent shape
  (§11.1).
- **Cancellation precision under `fail_fast`.**
  [still-relevant] — when branch A fails under fail_fast, branches B and C
  are cancelled. If branch B's subgraph was mid-checkpoint-save, does the
  cancellation interact with checkpointing? Proposal noted "need to verify
  when both proposals are accepted." Both (0008 and 0011) are now Accepted;
  the verification hasn't been done. Revisit if a real workload surfaces an
  inconsistency.
- **Concurrency bound for parallel branches.**
  [still-relevant] — deferred at acceptance; M is small in practice. No
  signal accumulated.
- **Top-level timeout for parallel-branches node.**
  [still-relevant] — deferred at acceptance; users wrap with their own
  middleware or wait for a future timeout-middleware proposal.

## llm-provider

### 0019 — multi-provider wire-format extension

- **Numbering convention for §8 subsections.**
  [resolved-by-acceptance] — proposal text picked §8.1, §8.2, … nesting;
  the alternative (§8 → §8 OpenAI-compatible + §8.6+ Anthropic) was rejected
  in the acceptance pass.
- **Per-mapping section structure for §8.X.**
  [still-relevant] — should §8.X subsections follow §8.1's structure
  (Request mapping / Response mapping / Error mapping / Concurrency /
  Structured output) by spec convention, or is each §8.X free to organize
  per-provider? Currently free; the first §8.X follow-on (likely §8.2
  Anthropic) decides whether to mirror §8.1 or diverge.
- **What "Cross-language ambition" means in practice.**
  [still-relevant] — the §8 default placement rule says any mapping with
  multi-language ambition lives in spec. The first concrete test will be
  whether the spec maintainer accepts a new §8.X proposal on the grounds of
  "TypeScript port anticipated" or requires a concrete TypeScript
  implementation in flight. Lean was "former is fine"; worth clarifying in
  the first §8.X follow-on if reviewers push.

---

## How to use this page

**Drafting a proposal in an area touched by an OQ?** Reference the OQ in
the Motivation section. The OQ has prior discussion of constraints,
alternatives considered, and the deferral reason — better starting context
than re-deriving from scratch.

**Resolving an OQ via a new proposal?** When the new proposal is Accepted,
update the OQ here to `resolved-by-NNNN` (or remove the line and leave a
short pointer entry — author's call).

**Spotting an OQ that's actually stale (the spec evolved around it)?**
Update to `inherited` (if subsumed by another proposal's contract) or
`resolved-by-NNNN` (if a specific later proposal made it moot). If neither
applies and the question genuinely no longer matters, remove the entry
with a note in the commit message about why.

**Not seeing your OQ?** This page covers Accepted proposals only. Drafts
have their OQs in the proposal file itself, awaiting acceptance.
