# 161: A Schema the Provider Did Not Honor

Verifies observability §5.5.7's *A schema the provider did not honor*, §5.5's
`openarmature.llm.structured_output.path` baseline attribute, and graph-engine §6's `structured_output_path`
field (proposal 0126).

For each wire attempt of a `complete()` call, including one call-level retry catches, an implementation MUST
emit exactly one `WARNING` log record carrying `openarmature.structured_output.schema_not_honored` when the
attempt failed `structured_output_invalid` with content that is not well-formed JSON or not a JSON object, on
the `"native"` path, with `finish_reason` `"stop"` and no stop sequence on its request. Each vendor's
constrained decoding promises well-formed JSON, and llm-provider §5 requires an object at the schema's top
level, so such content on a normal finish is evidence the constraint did not reach or did not bind the model.
The implementation MUST NOT emit the record in any other case.

**Spec sections exercised:**

- observability §5.5.7: the diagnostic's condition, its exclusions (the `"native_unenforced"` path among
  them), exactly one record per qualifying attempt, per-attempt evaluation, and the record's four attributes.
- observability §5.5: the path attribute, set when a schema was supplied and a request sent, absent otherwise.
- observability §5.5.2: each attempt's span reports its own request's parameters.
- observability §7: the `openarmature.structured_output.schema_not_honored` event name and the correlation
  fields.
- graph-engine §6: `structured_output_path` on both typed events, null when no schema was supplied or no
  request was sent; under call-level retry, the call's event describes the request its outcome came from and
  keeps the node-level `attempt_index`; `input_messages` is the list as sent.
- llm-provider §8.1.2 and §8.1.6: an OpenAI refusal, atomic or streamed, maps to `"content_filter"`, and a
  streamed refusal's pieces are content token events.
- llm-provider §8.1.5 and §8.1.5.1: `strict: true` for a schema that meets OpenAI's strict-mode rules, which
  makes the path `"native"` rather than `"native_unenforced"`, and the prompt-augmentation fallback. Both are
  SHOULDs, so the cases that depend on them are gated.
- conformance-adapter §5.1, §5.5, §5.10, §5.11 and §5.17: `calls_llm`'s `model`, `config` and `retry`, the
  `mock_llm` mapping form, `log_records` with `count`, `log_records_absent`, `contains_events_in_order`, the
  observer composition rules, the `<call_id_X>` and `<path_X>` binding tokens, `llm_spans`, and the
  `requires_capability` gates with the `llm_strict_native_schema` and `llm_prompt_augmentation_fallback`
  capabilities. This directory's harness note, fixture 001's header, supplies `calls_llm.stream` and
  `mock_llm_stream` for case 17, and `caller_correlation_id`.

**Cases:**

| Case | Gate | Path | Outcome | Diagnostic |
|---|---|---|---|---|
| 1 `native_not_json_on_stop_emits_once` | strict | native | prose on `stop` | emitted once |
| 2 `native_valid_object_failing_schema_absent` | none | shared | a JSON object failing the schema, `stop` | absent |
| 3 `native_json_array_on_stop_emits_once` | strict | native | a JSON array on `stop` | emitted once |
| 4 `native_not_json_on_length_absent` | none | shared | truncated JSON, `length` | absent |
| 5 `native_not_json_on_content_filter_absent` | none | shared | `content_filter` | absent |
| 6 `native_not_json_with_declared_stop_sequences_absent` | none | shared | prose on `stop`, `stop_sequences` declared | absent |
| 7 `native_not_json_with_extras_stop_absent` | none | shared | prose on `stop`, a stop list only in extras | absent |
| 8 `prompt_augmentation_path_absent` | fallback | prompt_augmentation | prose on `stop` | absent |
| 9 `native_valid_content_completion_absent` | none | shared | valid content | absent |
| 10 `no_schema_no_path` | none | null | completion without a schema | absent; no path attribute |
| 11 `rejected_before_sending_path_null` | none | null | `provider_invalid_request` before sending | absent |
| 12 `reask_recovers_record_for_attempt_0` | strict | native | attempt 0 prose, attempt 1 valid | emitted once, for attempt 0 |
| 13 `reask_with_override_stop_sequence_records_attempt_0_only` | strict | native | both attempts prose; the override adds a stop sequence for attempt 1 | emitted once, for attempt 0 |
| 14 `no_backend_observer_still_emits_once` | strict | native | prose on `stop`, no backend observer attached | emitted once |
| 15 `native_not_json_with_empty_stop_list_emits_once` | strict | native | prose on `stop`, `stop_sequences: []` | emitted once |
| 16 `native_refusal_reported_as_stop_absent` | none | shared | an OpenAI refusal that OpenAI reports as `stop` | absent |
| 17 `native_streamed_refusal_streams_content_tokens_absent` | none | shared | a streamed OpenAI refusal reported as `stop` | absent |
| 18 `native_not_json_with_empty_extras_stop_emits_once` | strict | native | prose on `stop`, `stop: []` in extras | emitted once |
| 19 `reask_both_attempts_emit_one_record_each` | strict | native | both attempts prose on `stop`, no stop sequence | emitted twice, once per attempt |
| 20 `native_unenforced_not_json_on_stop_absent` | not strict | native_unenforced | as case 1 | absent |
| 21 `native_unenforced_json_array_on_stop_absent` | not strict | native_unenforced | as case 3 | absent |
| 22 `native_unenforced_reask_recovers_absent` | not strict | native_unenforced | as case 12 | absent |
| 23 `native_unenforced_reask_with_override_stop_sequence_absent` | not strict | native_unenforced | as case 13 | absent |
| 24 `native_unenforced_no_backend_observer_absent` | not strict | native_unenforced | as case 14 | absent |
| 25 `native_unenforced_not_json_with_empty_stop_list_absent` | not strict | native_unenforced | as case 15 | absent |
| 26 `native_unenforced_not_json_with_empty_extras_stop_absent` | not strict | native_unenforced | as case 18 | absent |
| 27 `native_unenforced_reask_both_attempts_absent` | not strict | native_unenforced | as case 19 | absent |
| 28 `server_lacks_response_format_path_agrees` | none | shared | as case 8 | not asserted |

In the Gate column, *strict* is `requires_capability: {llm_strict_native_schema: true}`, *not strict* is the
same capability `false`, *fallback* is `{llm_prompt_augmentation_fallback: true}`, and *none* is ungated. In the
Path column, *shared* means the event's `structured_output_path` and the span's path attribute bind one
`<path_a>` token: either value the case allows can be right, but the two must agree.

**Capability gates.** llm-provider §8.1.5 says an implementation SHOULD send `strict: true` for a schema that
meets OpenAI's strict-mode rules, and only then is the path `"native"`. The record cases (1, 3, 12 to 15, 18,
19) depend on it, so they are gated on `llm_strict_native_schema: true` (conformance-adapter §5.17). Each has a
twin gated on `false`, cases 20 to 27 in the same order, with the same inputs and assertions except that the
event and each span report `"native_unenforced"` and `log_records_absent` replaces the record assertions, since
§5.5.7 forbids the record on that path. The native cases that expect no record (2, 4 to 7, 9, 16, 17) hold on
either path, so they are ungated and share one path token. Case 8 depends on llm-provider §8.1.5.1's fallback,
also a SHOULD, so it is gated on `llm_prompt_augmentation_fallback: true`. Case 28 runs case 8's inputs ungated
and asserts what holds with or without the fallback: the `structured_output_invalid` error, its category on
the span and the failed event, the event's `finish_reason`, and the shared path token. Without the fallback,
whether the record is emitted depends on `llm_strict_native_schema`, so case 28 does not assert it.

**What the absence cases are for.** Without them an implementation that emitted on every
`structured_output_invalid`, or on every native call, would pass. Case 2 pins the narrowing to malformed and
non-object content, case 3 the non-object arm, case 7 the stop sequence carried in extras, cases 12 and 13
the per-attempt evaluation and the rule that the call's event describes the request its outcome came from,
case 14 that the record does not depend on an observer being attached, cases 15 and 18 that an empty stop
list, declared or in extras, does not suppress the record, cases 16 and 17 that the check reads the
mapped `finish_reason`, not the one OpenAI reports, and cases 20 to 27 that the record is not emitted on the
`"native_unenforced"` path.

**Record content.** Every case that expects the record asserts its four attributes
(`openarmature.llm.provider`, `openarmature.llm.model`, `openarmature.llm.call_id`,
`openarmature.llm.attempt_index`) and its `openarmature.correlation_id`, on a `WARNING` record. Each sets
`caller_correlation_id`, so the correlation id is asserted as that literal value. The record's call id and the
call's typed event bind the same `<call_id_a>` token, so the record must name the call it reports on. A
separate entry counts every record with the event name at any level, so a second record at another level
fails the count. In case 1 the response reports a dated model name, so the record must name the model the
provider is bound to.

**Observers.** Every case except case 14 and its twin, case 24, composes both backend observers
(`otel_observer: {}` and `langfuse_observer: {}`, conformance-adapter §5.5), so an absence case covers a check
placed in either observer, and each record count catches an implementation that emits once per observer.
Cases 14 and 24 compose neither (`otel_observer: {attached: false}` and no Langfuse key), so an implementation
that emits the record from inside an observer fails case 14.

**Retry cases.** A caught attempt emits no typed event (graph-engine §6, as in fixture 116). Cases 12, 13
and 19, and their twins 22, 23 and 27, therefore count the call's typed events, so exactly one terminal event
and no other. That event carries the node-level `attempt_index` 0. In cases 12 and 13 one attempt qualifies,
so the record count is 1 and the record carries `openarmature.llm.attempt_index` 0. In case 19 both attempts
qualify, so two records carry indexes 0 and 1 and the same call id. Each attempt's span is asserted through
`llm_spans`, with the path attribute and the attempt's error category. In cases 13 and 23, attempt 1's span
carries the stop sequence the override added and attempt 0's carries none, so each span reports its own
request. Each wire attempt takes the next `mock_llm` entry. The reask template has no placeholders, so the
rendered correction is the literal template and cases 12 and 22 can assert `input_messages` exactly.

**What fails:**

- Emitting for a well-formed object that fails the schema (case 2).
- Not emitting for a non-object top level (case 3), for a reask-recovered attempt (case 12), or when the stop
  list is empty, declared or in extras (cases 15, 18).
- Emitting at most one record per call, or writing the node-level or a fixed index into the record (case 19).
- Emitting despite `length`, `content_filter`, or a declared or extras stop sequence (cases 4 to 7, 13), or on
  a path other than `"native"`: the prompt-augmentation path (case 8) or `"native_unenforced"` (cases 20 to 27).
- Emitting for an OpenAI refusal because OpenAI reported `"stop"` (cases 16, 17).
- Emitting once per observer (cases 1, 3, 12, 13, 15, 18, 19), or only when an observer is attached
  (case 14).
- A record missing an attribute, carrying the wrong correlation id, or naming a call id other than its call's
  (cases 1, 3, 12 to 15, 18, 19), or naming the response's model instead of the bound model (case 1).
- A missing or wrong `structured_output_path` on the event (cases 1, 3, 8, 10 to 15, 18 to 27), an event path
  that is missing or disagrees with its span's path attribute (cases 2, 4 to 7, 9, 16, 17, 28), or a path
  attribute on a span whose call had no schema (case 10).
- A terminal event describing the caller's original request rather than the last attempt's, a typed event
  for a caught attempt, or a wire-level `attempt_index` on the event (cases 12, 13, 19 and their twins).
- A span reporting the caller's original request rather than its own attempt's (cases 13, 23).
- A streamed refusal whose pieces are not emitted as content token events (case 17).

**Limits.** Case 11 asserts only the event: whether a call rejected before sending gets an LLM span is not
specified. Case 8 does not assert the event's `input_messages`: llm-provider §8.1.5.1 lets the directive be
appended as a system message or merged into an existing one, so its position is the implementation's. Case 28
does not assert the record, which depends on the path the call takes and on strict mode. The shared-token
cases do not fix which path the call took, only that the event and the span agree.
