# 089 — Embedding metrics: input token + operation duration

Verifies observability §11.2 / §11.3 (proposal 0067): the two instruments extend to
embedding calls via the operation dimension — one token-usage observation (input
only) and one duration observation, carrying operation `"embeddings"`.

## Spec coverage

- §11.2 — for an embedding call, `openarmature.gen_ai.client.token.usage` records
  **one** observation (input only — embeddings have no output tokens);
  `operation.duration` records one.
- §11.3 — `openarmature.gen_ai.operation` = `"embeddings"`; `gen_ai.request.model`;
  `gen_ai.system`; `openarmature.gen_ai.token.type` = `"input"`.

## Cases

1. `embedding_records_input_token_and_duration` — usage {prompt_tokens 4} → one
   token-usage observation (4 / `"input"`) and one duration observation, both
   `"embeddings"`.

## Anti-cases

- An `"output"` token-usage observation for an embedding (embeddings have none).
- The operation dimension set to `"chat"` instead of `"embeddings"`.
