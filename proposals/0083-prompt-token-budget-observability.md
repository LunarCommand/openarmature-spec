# 0083: Per-Prompt Token-Budget Observability

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-25
- **Targets:** spec/prompt-management/spec.md (§3 *Prompt shape* — new optional `Prompt.token_budget` sub-record `{input_max_tokens?, total_max_tokens?}`, sourced from the §5 config sidecar like `sampling`; §4 *PromptResult shape* propagates it; §12 *Cross-spec touchpoints* — new `Prompt.token_budget` → observability wiring); spec/graph-engine/spec.md (§6 — `LlmCompletionEvent` and `LlmFailedEvent` gain a `token_budget` field carrying the active prompt's budget; budget evaluation fires for completions and the usage-bearing failure category `structured_output_invalid` (per 0082), so the typed event drives the observability below); spec/observability/spec.md (§5.5 — `openarmature.prompt.token_budget.*` budget attributes + `openarmature.llm.token_budget.exceeded` on the LLM span; §7 — a WARNING log record on exceed; §8.4 — Langfuse `observation.level = "WARNING"` + metadata mapping on exceed; §11.2 — two new opt-in instruments, `openarmature.gen_ai.client.token_budget.exceeded` counter + `openarmature.gen_ai.client.token_budget.utilization` histogram; §11.4 — the deterministic utilization ratio added as an asserted-value case; §11.5 — metric-capture extended to the two new instruments); spec/conformance-adapter/spec.md (§5.8 *metrics* directive + §6.9 metric-capture primitive — extended to admit the two new instruments, the `openarmature.gen_ai.token_budget.kind` dimension, and an asserted ratio value for the utilization histogram); plus new conformance fixtures.
- **Related:** 0033 (prompt-management surface refinements — added `Prompt.sampling` with `max_tokens`, the *output* budget this complements; `token_budget` is sourced from the same §5 config sidecar), 0067 (OTel GenAI metrics — established §11 and the `openarmature.gen_ai.client.*` instrument family these two instruments join), 0057 (LlmCompletionEvent field-set extension — the `active_prompt` snapshot this sits beside), 0082 (structured-output failure diagnostics — **prerequisite for the failure-path coverage**: 0083's `structured_output_invalid` budget evaluation requires 0082's `LlmFailedEvent.usage` and its §11.2 token-usage-on-failure reconciliation, so 0083 MUST accept after 0082. The completion-path coverage is self-contained and needs no 0082.)
- **Supersedes:**

## Summary

A prompt can already carry an *output* cap (`Prompt.sampling.max_tokens`, proposal 0033), and OA already
emits actual input/output token usage to OTel vendor-neutrally (§11 `openarmature.gen_ai.client.token.usage`,
proposal 0067). What is missing is a per-prompt **input and total token budget** and the **observability
signal** that fires when a call's real usage exceeds it — the vendor-neutral equivalent of eyeballing
input+output token counts in a single vendor's UI.

This proposal adds an optional `Prompt.token_budget` (`{input_max_tokens?, total_max_tokens?}`), carries
it onto the completion event (and the usage-bearing `structured_output_invalid` failure event, per 0082),
and — **reactively, against the provider's actual reported usage** —
surfaces a budget-exceeded signal on the LLM span (`openarmature.llm.token_budget.exceeded`), a Langfuse
`WARNING`-level observation, a §7 log record, and two opt-in §11 instruments (an exceeded **counter** for
alerting and a utilization **histogram** for "which prompts run hot"). It is **advisory observability
only** — it warns and measures; it never rejects, truncates, or counts tokens itself (the provider's
usage record is the source, so no tokenizer is required).

**Sequencing — depends on proposal 0082.** The completion-path coverage is self-contained against the
current spec (`LlmCompletionEvent.usage` and the §11.2 `token.usage` instrument for completions both exist
today). The **failure-path** coverage builds on proposal 0082 (structured-output failure diagnostics): it
requires 0082's addition of `usage` to `LlmFailedEvent` for `structured_output_invalid`, and 0082's
reconciliation of the §11.2 "failed attempts contribute nothing" rule. 0082 is therefore a
**prerequisite** — 0083 MUST be accepted after it, and the references below to 0082's effects (the failure
event carrying `usage`, §11.2 recording it) describe the spec **as 0082 will leave it**, not as it stands
today. 0083 does **not** separately reconcile the §11.2 sentence — that edit belongs to 0082; 0083 builds
on the reconciled §11.2.

## Motivation

**The output cap and raw-usage visibility already exist.** `Prompt.sampling.max_tokens` (0033) gives a
per-prompt output cap that flows into `provider.complete(config=...)`, and §11's
`openarmature.gen_ai.client.token.usage` histogram (0067) already emits actual input and output token
counts to OTel — a Prometheus/Grafana-native signal with no dependence on any single LLM-observability
vendor. So neither a per-prompt output cap nor raw token visibility needs a new proposal.

**What is missing is the budget and the signal.** Two gaps remain:

1. **No input or total budget.** `sampling.max_tokens` caps output; there is no per-prompt declaration of
   an expected *input* size or *total* (input + output) ceiling. A prompt whose input has quietly grown
   (a RAG context that ballooned, an over-long few-shot block) has no declared expectation to measure
   against.
2. **No budget-vs-actual signal.** Even with raw usage in metrics, nothing tells an operator "this call
   ran over what this prompt was budgeted for." Spotting it means manually correlating usage against an
   expectation that lives only in someone's head.

**Reactive is the right first step — and it needs no tokenizer.** The provider returns the exact input
(`prompt_tokens`) and total (`total_tokens`) counts in its usage record, vendor-accurately. So comparing
actual usage to the budget *after* the call requires no token counting of our own — it reuses the usage
OA already has on `LlmCompletionEvent`. (A *proactive*, pre-send guard — counting the rendered prompt
before the call to warn or block — would need a tokenizer abstraction OA does not have, with cross-vendor
approximation issues; that is deliberately deferred, see *Out of scope*.) The reactive signal serves the
core need directly: vendor-neutral alerting and dashboards for token-budget adherence.

**This is squarely observability.** The feature produces a span attribute, a log, a Langfuse level, and
two metrics — it changes no call behavior. It is an incremental, low-risk step in the
visibility/observability space, composing with the §11 metrics (0067) and the §6 typed event stream
already in place.

## Proposed change

### prompt-management §3 / §4 — `Prompt.token_budget`

Add an optional `token_budget` field to the `Prompt` record (§3) and propagate it on `PromptResult` (§4):

> | `token_budget` | Optional. A `TokenBudget` sub-record: `{input_max_tokens?: int, total_max_tokens?: int}`, both optional, non-negative. `input_max_tokens` is the expected ceiling on the call's **input** (prompt) tokens; `total_max_tokens` is the ceiling on **input + output** tokens. The **output** budget is `sampling.max_tokens` (§3) and is not duplicated here. **Advisory and observability-only**: unlike `sampling` — which configures the call — `token_budget` has **no effect on the LLM request**; it drives the observability signals in observability §5.5 / §7 / §8.4 / §11 (compared reactively against the provider's reported usage). Sourced from the same §5 config sidecar as `sampling` (the per-prompt `<name>.config.json` / unified `prompt_configs.json`). Absent (`None` / `null` / `undefined`) when the backend supplies no budget. |

The §5 config-sidecar convention paragraph is extended to note `token_budget` is sourced alongside
`sampling`. §12 *Cross-spec touchpoints* gains a `Prompt.token_budget` → observability touchpoint
(mirroring the existing `Prompt.sampling` → llm-provider §6 touchpoint), noting the budget is **observed,
not applied**.

### graph-engine §6 — the completion and failure events carry the budget

Add one field to the `LlmCompletionEvent` field table (a sibling to `active_prompt`, not a change to the
identity snapshot), and the **same field to `LlmFailedEvent`**:

> | `token_budget` | record \| null | The active prompt's token budget at LLM-call time — `{input_max_tokens, total_max_tokens}`, each null when the prompt declared only the other. Sourced from `Prompt.token_budget` (prompt-management §3) via the same prompt-context binding that populates `active_prompt`. Null when no prompt was active or the active prompt declared no budget. This is the source the observability §11 token-budget instruments and the `openarmature.*.token_budget.*` span attributes render from; carrying it on the event keeps the budget evaluation in the §6 → §11 typed-event flow (and visible to custom observers), consistent with how the other §11 instruments read these events. |

Not payload-bearing (integers, not provider content); not privacy-gated. The field behaves identically on
both event variants — it carries the active prompt's budget whenever one is declared. Budget
**evaluation** (the exceeded signal + the §11 instruments) additionally requires actual `usage` to compare
against, so it fires on every `LlmCompletionEvent` and on the one `LlmFailedEvent` category that carries
`usage` — `structured_output_invalid` (proposal 0082). The other eight §7 failure categories carry no
usage, so `token_budget` may be populated but no evaluation occurs. This keeps the token-budget metrics'
call-coverage aligned with §11.2's `token.usage` — once the prerequisite 0082 lands (see *Sequencing*),
`structured_output_invalid` failures record `token.usage`, so omitting their budget signals would leave a
silent gap between the two instruments.

### observability §5.5 — budget attributes + the exceeded signal on the LLM span

Add to the LLM provider span, beside the `openarmature.prompt.*` identity family (§5.5 / §8.4.4):

> - **`openarmature.prompt.token_budget.input_max_tokens`** / **`openarmature.prompt.token_budget.total_max_tokens`** — int. The active prompt's declared budget (from `LlmCompletionEvent.token_budget`). Each emitted only when the prompt declared that bound. Absent when no active prompt or no budget.
> - **`openarmature.llm.token_budget.exceeded`** — boolean. `true` when the call's actual usage crossed any declared bound — `usage.prompt_tokens > input_max_tokens` (input) or `usage.total_tokens > total_max_tokens` (total; `prompt_tokens + completion_tokens` when the provider omits `total_tokens`). Emitted only when a budget was declared. The per-bound detail (which of input / total was exceeded) is carried on the §11 metric `kind` dimension rather than as additional boolean attributes, to keep the span surface minimal.

**When a budget is declared and exceeded, the implementation MUST** set
`openarmature.llm.token_budget.exceeded = true` (when LLM spans are enabled per §5.5.4) and record the
§11.2 instruments (when `enable_metrics`). The signal is reactive — evaluated from the actual usage on
the terminal typed event after the call returns: every §5.5.7 `LlmCompletionEvent`, and — once the
prerequisite 0082 lands — a `structured_output_invalid` `LlmFailedEvent` (the failure category 0082 makes
carry `usage`, per the §5.5.7 typed-event framing).

### observability §7 + §8.4 — vendor-neutral WARNING surfaces

> **§7 (logs).** On a budget exceedance the implementation SHOULD emit a `WARNING`-level log record
> identifying the prompt (`openarmature.prompt.*`), the exceeded bound, the budget, and the actual usage,
> carrying the standard §7 correlation fields.
>
> **§8.4.3 (Langfuse).** On a budget exceedance the implementation SHOULD set the Generation's
> `observation.level = "WARNING"` with a `statusMessage` naming the exceeded bound (e.g.
> `"token budget exceeded: input 1500 > 1000"`), reusing the soft-error WARNING pattern already defined
> for error-condition `finish_reason`s; the budget values map to `generation.metadata.token_budget.*`. A
> hard `ERROR`-level failure (§4.2 / §8.4.2) still takes precedence when both apply.

The WARNING surfaces are SHOULD (advisory, matching the existing soft-error WARNING posture); the span
attribute + the metrics are MUST (deterministic and assertable).

### observability §11.2 — two new opt-in instruments

Under the existing `enable_metrics` flag (§11.1), add to §11.2 (recorded from a terminal typed event that
carries both `usage` and a non-null `token_budget` — every §5.5.7 `LlmCompletionEvent`, and — once the
prerequisite 0082 lands — a `structured_output_invalid` `LlmFailedEvent` (per §5.5.7 / 0082) — keeping
coverage aligned with the §11.2 `token.usage` instrument):

> - **`openarmature.gen_ai.client.token_budget.exceeded`** — **Counter**, unit `{call}`. Incremented by 1
>   for each declared bound the call's usage exceeded (so a call over both input and total budgets
>   increments twice, once per `kind`). Carries the §11.3 dimensions plus
>   **`openarmature.gen_ai.token_budget.kind`** = `"input"` / `"total"`. The clean signal for alerting and
>   "rate of over-budget calls" without histogram-bucket arithmetic.
> - **`openarmature.gen_ai.client.token_budget.utilization`** — **Histogram**, unit `1` (dimensionless
>   ratio). Records `actual / budget` for each declared bound — `prompt_tokens / input_max_tokens` (`kind`
>   `"input"`), `total_tokens / total_max_tokens` (`kind` `"total"`) — on **every** call with that bound
>   declared, exceeded or not, so the distribution shows how close prompts run to budget (a value `> 1.0`
>   is over budget). SHOULD use explicit bucket boundaries `[0.1, 0.25, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0, 4.0]`.

Both carry the §11.3 dimensions (`openarmature.gen_ai.operation` = `"chat"`, `gen_ai.request.model`,
`gen_ai.system`) plus `kind`. They are LLM-only for now (prompts budget LLM calls; `operation` is always
`"chat"`); the `openarmature.gen_ai.client.*` namespace and `operation` dimension leave room for
embedding/rerank budgets later without a rename. Recording utilization on **every** budgeted call (not
just over-budget ones) is observation *volume*, not cardinality — the dimensions above are bounded and a
histogram aggregates volume into fixed buckets by design; the sub-`1.0` distribution is the instrument's
whole point.

**On the counter / histogram overlap (deliberate).** The exceeded counter is derivable from the
histogram's `> 1.0` buckets, but the two serve different needs: the histogram answers "how close to budget
is each call" (distribution), the counter answers "how many calls went over" (a monotonic alerting
signal, no bucket math, cleanly split by `kind`). Both are recorded.

## Conformance test impact

New fixtures under `spec/observability/conformance/`:

1. **`NNN-token-budget-input-exceeded`** — prompt with `token_budget.input_max_tokens` below the mock
   usage's `prompt_tokens`. Asserts `LlmCompletionEvent.token_budget` is populated,
   `openarmature.llm.token_budget.exceeded = true`, the `openarmature.prompt.token_budget.input_max_tokens`
   span attribute, the `token_budget.exceeded` counter (`kind = "input"`), and a `utilization` observation
   at the exact `prompt_tokens / input_max_tokens` ratio the mock + budget fix (§5.8 asserts the exact
   value, not a comparison).
2. **`NNN-token-budget-total-exceeded`** — `total_max_tokens` below `total_tokens`. Asserts the `"total"`
   `kind` on the counter + histogram, and the exceeded attribute.
3. **`NNN-token-budget-under-budget-no-warning`** — usage below both bounds. Asserts
   `openarmature.llm.token_budget.exceeded` is `false`/absent, no exceeded-counter increment, and a
   `utilization` observation recorded at the exact under-budget ratio (the distribution is recorded even
   when under budget).
4. **`NNN-token-budget-absent-unchanged`** — prompt with no `token_budget`. Asserts no token-budget
   attributes, no exceeded counter, no utilization observation — the baseline is unperturbed.
5. **`NNN-langfuse-token-budget-warning-level`** — the input-exceeded case through the bundled Langfuse
   observer. Asserts `observation.level = "WARNING"` + `statusMessage` + `generation.metadata.token_budget.*`,
   and that a hard `ERROR` (when also present) takes precedence.
6. **`NNN-token-budget-on-structured-output-failure`** (lands with / after the prerequisite 0082) — a
   `structured_output_invalid` failure (which 0082 makes carry `usage`) from a budgeted prompt whose actual
   usage exceeds the budget. Asserts
   `LlmFailedEvent.token_budget` is populated, `openarmature.llm.token_budget.exceeded = true`, and the
   exceeded counter + utilization histogram fire **on the failure event** — parity with the completion
   path. A companion no-usage failure (`provider_unavailable`) from a budgeted prompt asserts `token_budget`
   MAY be populated but **no** evaluation occurs (no exceeded signal, no metric).

Metric assertions use the §11.5 in-memory metric-capture primitive — **extended by this proposal** (with
conformance-adapter §5.8 / §6.9) to admit the two new instruments, the `kind` dimension, and an asserted
*value* for the utilization histogram (§5.8 today scopes asserted metric values to `token.usage` token
counts). Concrete `kind` / dimensions are asserted; the utilization ratio is a deterministic value (the
mock's fixed usage + the fixture's budget fix it), which §11.4 is extended to name as an asserted-value
case alongside token counts.

## Versioning

**MINOR bump** (pre-1.0), additive, across prompt-management, graph-engine, observability, and
conformance-adapter (one whole-spec SemVer increment). **Sequenced after the prerequisite 0082** — the
failure-path pieces (the `LlmFailedEvent` field, the §11.2 failure-event instruments) land on the spec
0082 leaves; 0082 owns the §11.2 "contribute nothing" reconciliation, so 0083 adds the instruments without
re-editing that sentence:

- prompt-management §3 / §4 — new optional `Prompt.token_budget` field (+ PromptResult propagation,
  §5 sidecar sourcing, §12 touchpoint). Absent-by-default; no change to existing prompts.
- graph-engine §6 — one new optional `token_budget` field on `LlmCompletionEvent` **and** `LlmFailedEvent`
  (null when no budget); budget evaluation fires for completions and `structured_output_invalid` failures
  (the usage-bearing category, per 0082).
- observability §5.5 / §7 / §8.4 / §11.2 — new budget span attributes + exceeded signal, WARNING
  surfaces (SHOULD), two new opt-in instruments; new fixtures.
- observability §11.4 / §11.5 + conformance-adapter §5.8 / §6.9 — metric-capture vocabulary extended for
  the two new instruments, the `openarmature.gen_ai.token_budget.kind` dimension, and the asserted
  utilization ratio.

No behavior change for any prompt without a `token_budget`, any observer with `enable_metrics` off, or any
caller (the budget never touches the LLM request).

## Alternatives considered

1. **Do nothing — rely on a single vendor's UI.** The status quo: reading combined token counts in a
   single LLM-observability vendor's UI. Rejected: it is vendor-locked, and there is no declared per-prompt
   expectation to alert against. The raw-usage half is already vendor-neutral via §11; this adds the
   budget + signal that the vendor UI was standing in for.

2. **Proactive (pre-send) budget guard.** Count the rendered prompt's input tokens before the call and
   warn/block when over budget. Deferred (see *Out of scope*): it requires a token-counter abstraction OA
   lacks, and cross-vendor tokenization is approximate (tiktoken is OpenAI-accurate, ~10–30% off for
   Anthropic/Gemini). The reactive path uses the provider's exact reported usage and needs no tokenizer,
   delivering the alerting/dashboard value first.

3. **Enforcement (reject or truncate on exceed).** Rejected for this proposal — it changes call behavior
   and opens app-specific truncation-strategy questions. The budget is advisory; enforcement, if ever
   wanted, is a separate decision built on this signal.

4. **Put the budget in `Prompt.sampling`.** Rejected: `sampling` mirrors `RuntimeConfig` (call
   parameters that ARE applied to the request) and has no input/total-token concept. `token_budget` is
   observability-only and must not be confused with applied call config; a separate field keeps the
   "applied vs observed" line clean.

5. **Span-only (don't carry the budget on the typed event).** Emit the budget attributes only on the LLM
   span from the prompt-context binding, never on `LlmCompletionEvent`. Rejected: it would exclude the
   §11 metric layer (which reads the typed events) and custom observers from the budget, fragmenting the
   signal. Carrying it on the event keeps the §6 → §11 flow whole.

6. **Counter only, or histogram only.** A single instrument. Rejected: the counter (alerting / over-budget
   rate, split by `kind`) and the histogram (utilization distribution / "which prompts run hot") answer
   different dashboard questions; the slight derivability of the counter from the histogram is accepted for
   alerting ergonomics.

## Open questions

None remaining. The two drafting questions are resolved in the text above:

- **Evaluate budgets on `LlmFailedEvent`?** Yes — for the one failure category that carries `usage`,
  `structured_output_invalid` (proposal 0082). Carrying `token_budget` there and evaluating it keeps the
  budget metrics' call-coverage aligned with §11.2's `token.usage` (which 0082 — the **prerequisite** —
  makes those failures record); skipping them would leave a silent gap between the two instruments. The
  other eight no-usage §7 categories are unaffected (nothing to compare). 0083 accepts after 0082 (see
  *Sequencing*).
- **Utilization histogram — record always or only on exceed?** Record always (per declared bound),
  under-budget calls included — the sub-`1.0` distribution is the instrument's whole value, and recording
  only on exceed would just duplicate the counter. It is observation volume, not cardinality (dimensions
  bounded), so there is no cardinality cost. The exceeded **counter** increments per breached bound (a
  both-bounds breach increments twice, by `kind`); calls-over-budget is the per-call
  `openarmature.llm.token_budget.exceeded` span attribute — a deliberate, confirmed split.

## Out of scope

- **Proactive / pre-send token counting and a `TokenCounter` primitive.** The reactive signal uses the
  provider's reported usage. A pre-send guard (count the rendered prompt, warn/block before the call) needs
  a token-counter abstraction and takes on cross-vendor tokenization approximation; it is a deliberate
  potential phase 2, not part of this proposal.
- **Enforcement.** No rejecting, truncating, or auto-adjusting calls. Advisory only.
- **An output budget field.** Output is `Prompt.sampling.max_tokens` (0033); `token_budget` covers input
  and total only.
- **Embedding / rerank budgets.** The instruments and `operation` dimension leave room, but this proposal
  scopes the budget to LLM calls (the `Prompt` → `complete()` path).
- **Budget evaluation on no-usage failures.** The eight non-`structured_output_invalid` §7 failure
  categories carry no `usage` (per 0082), so no budget evaluation occurs for them — `token_budget` may be
  populated on the event, but there is nothing to compare. The `structured_output_invalid` failure path IS
  in scope (it carries `usage`) — see graph-engine §6 / §11.2.
