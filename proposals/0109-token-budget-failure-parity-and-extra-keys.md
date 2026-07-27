# 0109: Token-budget failure-path parity and config extra-key handling

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-26
- **Ships as:** _assigned at acceptance (MINOR)_
- **Targets:** spec/observability/spec.md **§8.4.3** (add a `generation.metadata.token_budget_exceeded`
  boolean that survives the `ERROR`-precedence rule, giving the Langfuse failure path parity with the OTel
  §5.5.15 `openarmature.llm.token_budget.exceeded` attribute; emitted on both the WARNING and failure paths);
  spec/prompt-management/spec.md **§3 / §5** (`token_budget` config parsing: state the call-safety invariant
  explicitly, and converge unrecognized-key handling across backends to *tolerate-and-filter* — recognized
  bounds apply, unrecognized keys ignored). Conformance: a Langfuse failure-path over-budget fixture and a
  prompt-backend unrecognized-key fixture.
- **Related:** 0083 (defined `token_budget` and its observability signals — this refines its Langfuse
  failure-path rendering and its config-parsing contract), 0082 (`structured_output_invalid` failures carry
  usage, so a failure can also be over budget), 0101 (a not-reported counter is *not evaluated* — no flag)
- **Supersedes:**

## Summary

The final whole-proposal review of 0083's reference implementation surfaced two places where two conforming
implementations could diverge. Neither blocks 0083 (both behaviors shipped today are call-safe), but each is an
under-specified seam worth closing:

1. **Failure-path exceedance is discoverable on OTel but not Langfuse.** On a `structured_output_invalid`
   failure that *also* exceeds budget (usage-bearing per 0082), §8.4.3's "a hard `ERROR` takes precedence over
   the advisory WARNING" means the Langfuse Generation renders `ERROR` with the §7-category `statusMessage` —
   so the over-budget signal is not surfaced, while the OTel span carries the
   `openarmature.llm.token_budget.exceeded = true` attribute + the §11 counter. An operator triaging that failure
   in Langfuse sees the declared bounds
   (`metadata.token_budget.*`) but cannot tell the call was also over budget.
2. **Backends diverge on an unrecognized key in a `token_budget` config.** Given a config object with a stray
   key alongside valid bounds (`{"input_max_tokens": 10, "unknown": 5}`), one backend field-filters to a partial
   budget while another rejects the whole budget to fallback — both call-safe, but a different *result*.

## Motivation

0083 made the exceedance signal a first-class, cross-backend observability output (an OTel attribute + a metric
counter + a Langfuse WARNING). The failure path is the one surface where the two backends fall out of parity:
the OTel attribute is level-independent, but the Langfuse signal rode entirely on `observation.level`/
`statusMessage`, which the `ERROR`-precedence rule overrides. A level-independent metadata flag restores parity
without disturbing the `ERROR` status (the §7 category stays the primary signal).

The config-parsing divergence is a gap 0083 simply did not address: it defined the `token_budget` shape and its
advisory semantics, but not how a backend treats a malformed or extended config object. "Advisory / MUST NOT
break the call" was intended but never stated, and the extra-key case was left to each backend's config-model
strictness — so two conforming backends produce different budgets from the same input.

## Proposal

### 1. observability §8.4.3 — failure-path budget-exceedance parity

Add a **single any-bound** boolean **`generation.metadata.token_budget_exceeded`** to the Langfuse Generation:
`true` when the call's actual usage crossed **any** declared bound (the **same** evaluation as the §5.5.15 span
signal and the §11 `token_budget.exceeded` counter — `usage.prompt_tokens > input_max_tokens` or
`usage.total_tokens > total_max_tokens`). The observer **MUST** emit it on the Generation's metadata
**regardless of `observation.level`**, so it **survives** the `ERROR`-precedence rule — parity with the OTel
`openarmature.llm.token_budget.exceeded` attribute, which the observer sets whenever LLM spans are enabled. This
`MUST` governs only the additive metadata field; the `ERROR` `observation.level` / `statusMessage` and the
existing WARNING-path obligations are unchanged.

- On a `structured_output_invalid` failure that also exceeds budget, the Generation still renders
  `observation.level = "ERROR"` with the §7-category `statusMessage` (unchanged — the failure is the primary
  signal); the flag is **additive metadata**, making the exceedance discoverable, at parity with the OTel
  `openarmature.llm.token_budget.exceeded` attribute.
- On the WARNING (non-failure over-budget) path the flag is emitted alongside the existing `statusMessage`
  (§8.4.3), so **both paths carry it uniformly**.
- **Emitted (`true` or `false`) whenever a budget was declared and at least one bound is evaluable; absent when
  no bound is evaluable.** It is a single boolean, not per-bound: `true` if any evaluated bound was crossed,
  `false` if every evaluated bound held. A bound whose counter is **not reported** (§5.5.15 / llm-provider §7,
  per 0101) is not evaluated and does not contribute; if a budget is declared but **no** bound is evaluable (all
  relevant counters not-reported), the flag is **absent, not `false`** — mirroring the OTel attribute's
  suppression from a null counter.

The declared bounds continue to map to `generation.metadata.token_budget.*` as today; this adds a flat sibling
boolean key `generation.metadata.token_budget_exceeded` (not a nested field under `token_budget`).

### 2. prompt-management §3 / §5 — `token_budget` config: call-safety + unrecognized keys

`token_budget` is advisory / observability-only (§3): it never affects the LLM request. Two rules, previously
implicit or unspecified, become normative:

- **Call-safety (made explicit).** A malformed or unrecognized `token_budget` config **MUST NOT** break the LLM
  call. A backend that cannot parse a `token_budget` config MAY drop the budget (the call proceeds with no
  budget, or a fallback per the backend's own error handling), but MUST NOT propagate the parse failure into the
  call.
- **Unrecognized keys → tolerate-and-filter (converged).** When a `token_budget` config object carries an
  **unrecognized key** alongside valid bounds (e.g. `{"input_max_tokens": 10, "unknown": 5}`), a backend **MUST**
  apply the recognized bounds and **ignore** the unrecognized key — a well-formed budget is not invalidated by a
  stray key. This is forward-compatibility (a future spec or vendor key) and converges the behavior 0083's impl
  left divergent (one backend field-filtered to a partial budget, the other rejected the whole budget to
  fallback); both now field-filter.

A **malformed VALUE** for a *recognized* bound (e.g. a non-integer `input_max_tokens`) is a **distinct** case
this proposal does **not** mandate: it is left to the backend under the call-safety rule above (reject-to-
fallback and tolerate-and-drop are both conformant, provided the call is not broken). Only the unrecognized-*key*
case converges.

## Conformance

- **Langfuse failure-path exceedance** — a `structured_output_invalid` failure whose usage also exceeds a
  declared bound: the failed Generation renders `observation.level = "ERROR"` (§7-category `statusMessage`) **and**
  `generation.metadata.token_budget_exceeded = true`. The failure-path sibling of the existing WARNING-path
  budget rendering; asserts the flag survives `ERROR` precedence.
- **Unrecognized `token_budget` key** — a prompt backend sourcing a `token_budget` config
  `{input_max_tokens: N, <unrecognized>: M}` populates `Prompt.token_budget = {input_max_tokens: N}` (recognized
  bound applied, unrecognized key ignored) and the call proceeds normally.

## Versioning

**MINOR** (whole-spec SemVer). Additive on both counts: §8.4.3 gains one additive observation-metadata field
(`token_budget_exceeded`) whose value is the already-defined exceedance evaluation; prompt-management gains a
normative rule for a previously-undefined case (an unrecognized key in a `token_budget` config) plus an explicit
statement of the already-intended call-safety invariant. No existing signal changes: the OTel exceedance
attribute, the §11 counter, the declared-bounds metadata, and the `ERROR` `statusMessage` are all unchanged, and
malformed-*value* handling is deliberately left to the backend. No completion/WARNING-path behavior regresses. At
acceptance this is a **two-capability** bump — both observability and prompt-management `Latest` advance to the
shipped version (as 0072 did for prompt-management + conformance-adapter).

## Open questions

- None. Both rulings (add the failure-path flag; converge unrecognized-key handling to tolerate-and-filter) were
  settled ahead of drafting.
