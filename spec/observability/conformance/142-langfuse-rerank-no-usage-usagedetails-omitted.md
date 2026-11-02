# 142 — Langfuse rerank observation with empty `usageDetails` (record-null path)

Verifies observability §8.4.7's **record-null** branch (per proposal 0093): when a rerank call reports
no usage record at all (`RerankResponse.usage = null`), the `Retriever` observation's `usageDetails`
MUST carry neither usage figure (no `input` and no `searchUnits` key), per the open-map convention
§8.4.7 documents (`usageDetails` carries only the usage figures the provider reported, none here). The
mock body omits the `meta.billed_units` block entirely (`{id, model, results}`), so `usage` is null. It
is a harness stand-in for a no-usage reranker, NOT a claim that this is any specific vendor's wire
shape. TEI `/rerank` is the real-world archetype of a no-usage reranker (its actual wire differs from
this mock). This is the no-usage counterpart to 108, whose default case populates
`usageDetails.searchUnits` from a present record.

**Spec sections exercised:**

- observability §8.4.7 — Langfuse `Retriever` observation; `usageDetails` open-map convention (empty map
  when the provider reports no usage); `model` + identity metadata always populated; payload-gated
  `input` / `output`.
- retrieval-provider §6 — `RerankResponse.usage` is `record | null`; a provider that reports no usage
  yields `usage = null`.

**Cases:**

1. `rerank_observation_usagedetails_empty_when_no_usage_record` — Default observer config
   (`disable_provider_payload=True`). The mock reports no usage record (the `meta.billed_units` block is
   omitted). Asserts the observation type is `retriever`, `model` + identity metadata are populated,
   `usageDetails` is present and carries no `searchUnits` and no `input` key (`usageDetails: {}` beside
   `usageDetails_absent_keys: [input, searchUnits]`; the empty map matches by named keys, so it asserts
   only that the map is present), and `input` / `output` stay null under the default payload posture.

**What passes:**

- Observation type is `retriever` (not `generation`); `usageDetails` carries neither `input` nor
  `searchUnits`, since there is no usage record to source figures from; `model` + identity metadata
  populated; `input` / `output` null under the default posture.

**What fails:**

- `usageDetails.searchUnits` or `usageDetails.input` populated (e.g. `searchUnits: 0` fabricated) when
  the provider reported no usage record
  — the record-null branch is not honored.
- Observation renders as `generation`, or `model` / metadata dropped.
