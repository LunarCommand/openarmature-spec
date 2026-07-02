# 143 — Embedding metrics: no usage record → no token observation, duration still recorded

Verifies observability §11's **zero-observation** branch of the token-usage instrument (per proposal
0093): when an embedding call's usage record is absent (`EmbeddingResponse.usage = null`, retrieval-provider
§4), NO `openarmature.gen_ai.client.token.usage` observation is recorded, but the
`openarmature.gen_ai.client.operation.duration` observation is **still** recorded (a completed call is a
real latency sample). This is the no-usage counterpart to 089 (which records the token observation from a
present usage record). The mock body drops the `usage` block so `usage` is null — a harness stand-in for
a no-usage embedding provider, NOT a claim that this is any specific vendor's wire shape. TEI `/embed` is
the real-world archetype of a no-usage embedding provider (its actual wire differs from this mock).

## Spec coverage

- §11.2 — `openarmature.gen_ai.client.token.usage` records an observation only when the call's usage
  record is present; when the usage record is absent (`usage = null`), no observation is recorded for
  that call.
- §11.2 / §11.3 — `openarmature.gen_ai.client.operation.duration` records one observation regardless
  (operation `"embeddings"`, dimensions only — value not asserted per §11.4).

## Cases

1. `embedding_no_usage_records_duration_but_no_token_observation` — `enable_metrics=True`; mock body
   drops the `usage` block → `usage = null`. The `metrics:` list carries only the duration observation;
   the invariants assert the token-usage observation was not recorded and the duration observation was.

## Anti-cases

- A `token.usage` observation recorded (e.g. `value: 0` fabricated) when the embedding call reported no
  usage record.
- The duration observation dropped because the call reported no usage.
