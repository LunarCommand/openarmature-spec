# 145 — Token-usage histogram records no input observation on a not-reported `prompt_tokens`

Verifies observability §11.2's **per-counter** conditionality on the LLM branch of the
`openarmature.gen_ai.client.token.usage` histogram (per proposal 0101). When a completion's
`prompt_tokens` is not reported — mock usage `{prompt_tokens: null, completion_tokens: 5, total_tokens:
15}`, the `{null, 5, 15}` record of 0101 (malformed `prompt_tokens` nulled per llm-provider §7
*Malformed usage counter*, sound completion / total) — the histogram records **no** `"input"`
observation, while still recording the `"output"` observation (completion sound) and the
`operation.duration` observation (a completed call is a real latency sample).

The mock's wire `usage` carries `prompt_tokens: null` directly (the post-nulling state); this fixture
renders a null counter, it does not test the wire-malformed → `null` mapping (sibling llm-provider
fixture).

**Why it bites (the reversal 0101 pins).** §11.2's LLM branch moved from "record two observations, skip
only when the usage record is **absent**" to "record each observation **only when its counter is
reported**" — matching the rerank branch's existing per-counter behavior. A per-record implementation
records an `"input"` observation sourced from the null counter and fails this fixture. There is no
`"total"` token-usage observation to consider: §11.2 records the input and output counts only (`total` is
not a token-usage measurement).

**Spec sections exercised:**

- observability §11.2 — the `openarmature.gen_ai.client.token.usage` histogram LLM branch records the
  input / output observation only when that counter is reported; a null counter records no observation
  for that token type. The `operation.duration` histogram records once per completed call regardless.
- llm-provider §7 *Malformed usage counter* — a malformed counter is not reported (that counter is
  `null`); the others stand.

**Cases:**

1. `token_usage_histogram_records_no_input_observation_when_prompt_tokens_null` — one LLM-calling node;
   `enable_metrics=True`. Mock usage `{null, 5, 15}`. Asserts the exhaustive `metrics:` set is the
   `"output"` token.usage observation (value 5) plus one `operation.duration` observation, with an
   invariant that **no** `"input"` token.usage observation was recorded.

**What passes:**

- No `token.usage` observation carries `openarmature.gen_ai.token.type` = `"input"` — the null counter
  is not summed into the histogram.
- The `"output"` observation records value 5 (completion sound).
- One `operation.duration` observation records (value not asserted, §11.4).

**What fails:**

- An `"input"` token.usage observation recorded (sourced from the null counter) — a per-record impl that
  did not adopt §11.2's per-counter LLM branch.
- The `"output"` observation dropped, or the duration observation missing.
