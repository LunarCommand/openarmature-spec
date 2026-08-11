# 159 — Failed LLM Generation Error Message Is Payload-Gated (Error Type Is Not)

Gates observability §5.5.4 and §8.4.3 (proposal 0118): a failed provider observation's harvested
`error_message` is gated by **`disable_provider_payload`**, so the default posture never shows the exception
string. `error_type` is deliberately **not** gated: it is a classification token rather than harvested text,
and it remains the caller's failure discriminator on an observation with no error category.

Proposal 0117 put the Tool / Embedding / Retriever error message behind §6's payload-leak invariant alone, as
a per-emission rule keyed on provider isolation, which left it emitted regardless of the payload flag, and it
excluded the LLM Generation entirely. Proposal 0118 adds the failed Generation and moves the whole harvested
error message under the payload flag, collapsing two rules into one: payload off means classifications only.

**Why the LLM case forced it.** A `structured_output_invalid` failure's exception message commonly quotes the
model output that failed validation, and a provider 4xx can quote the request. Under the old arrangement a
caller could set `disable_provider_payload=True`, watch `generation.output` disappear as promised, and still
receive that same text inside `metadata.error_message` on a fully isolated provider, with no lever to stop it.

**The load-bearing pair.** Neither case here involves a shared provider, which isolates the flag's effect from
§6's isolation arms (fixture 158 covers those). Together they make each other non-vacuous: without the
flag-off case, an implementation that never emits the fields at all would satisfy the flag-on case trivially.

**Spec sections exercised:**

- §5.5.4 *Opt-out flags* — `disable_provider_payload` gates a failed call's `error_type` / `error_message` on
  the Langfuse side, alongside the provider payload proper.
- §8.4.3 *Failed Generation error message* — the failed Generation carries the fields only when the flag
  permits them; the error category is retained either way.
- §8.4.2 — `level = "ERROR"` plus `statusMessage` = the §7 `error_category`, which is not payload and is
  always retained. §6 forbids substituting the omitted message into `statusMessage`.

**Cases:**

- `llm_failure_error_message_omitted_under_default_posture` — a `mock_llm` wire failure (status 503 →
  `provider_unavailable`) with `disable_provider_payload` at its default `true`. The failed Generation emits at
  `ERROR` with `statusMessage: "provider_unavailable"`, `input` / `output` null, and
  `error_type` present plus `metadata_absent: [error_message]`. That absence assertion is the gate: an implementation
  emitting the exception string under the default posture fails here. The `metadata_absent` directive is
  required because the ordinary `metadata:` assertion is a subset match and cannot express absence
  (conformance-adapter §5.5, the Langfuse analogue of the OTel `attributes_absent` directive).
- `llm_failure_error_message_emitted_with_payload_flag_off` — the same failure with
  `disable_provider_payload: false`. The fields are now permitted and present (asserted by format, since the
  values are implementation-sourced: a vendor code or an exception class name, per the 073 / 137 / 138 idiom).
  The request-side `input` populates while `output` stays null, because no response was received, which is
  what makes the first case's null `output` meaningful rather than a payload-gating artifact. Level and
  `statusMessage` are unchanged by the flag. Same two-case structure as the embedding sibling, fixture 137.
