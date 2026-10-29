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

- observability §5.5.7: the diagnostic's condition, its exclusions, exactly one record per qualifying attempt,
  per-attempt evaluation, and the record's four attributes.
- observability §5.5: the path attribute, set when a schema was supplied and a request sent, absent otherwise.
- observability §5.5.2: each attempt's span reports its own request's parameters.
- observability §7: the `openarmature.structured_output.schema_not_honored` event name and the correlation
  fields.
- graph-engine §6: `structured_output_path` on both typed events, null when no schema was supplied or no
  request was sent; under call-level retry, the call's event describes the request its outcome came from and
  keeps the node-level `attempt_index`; `input_messages` is the list as sent, including the
  prompt-augmentation directive.
- llm-provider §8.1.2 and §8.1.6: an OpenAI refusal, atomic or streamed, maps to `"content_filter"`, and a
  streamed refusal's pieces are content token events.
- conformance-adapter §5.1, §5.5, §5.10 and §5.11: `calls_llm`'s `model`, `config` and `retry`, the
  `mock_llm` mapping form, `log_records` with `count`, `log_records_absent`, the observer composition rules,
  the `<call_id_X>` token, and `llm_spans`. Fixture 111's harness note supplies `calls_llm.stream`,
  `mock_llm_stream` and `contains_events_in_order` for case 17, and fixture 001's supplies
  `caller_correlation_id`.

**Cases:**

| Case | Path | Outcome | Diagnostic |
|---|---|---|---|
| 1 `native_not_json_on_stop_emits_once` | native | prose on `stop` | emitted once |
| 2 `native_valid_object_failing_schema_absent` | native | a JSON object failing the schema, `stop` | absent |
| 3 `native_json_array_on_stop_emits_once` | native | a JSON array on `stop` | emitted once |
| 4 `native_not_json_on_length_absent` | native | truncated JSON, `length` | absent |
| 5 `native_not_json_on_content_filter_absent` | native | `content_filter` | absent |
| 6 `native_not_json_with_declared_stop_sequences_absent` | native | prose on `stop`, `stop_sequences` declared | absent |
| 7 `native_not_json_with_extras_stop_absent` | native | prose on `stop`, a stop list only in extras | absent |
| 8 `prompt_augmentation_path_absent` | prompt_augmentation | prose on `stop` | absent |
| 9 `native_valid_content_completion_absent` | native | valid content | absent |
| 10 `no_schema_no_path` | null | completion without a schema | absent; no path attribute |
| 11 `rejected_before_sending_path_null` | null | `provider_invalid_request` before sending | absent |
| 12 `reask_recovers_record_for_attempt_0` | native | attempt 0 prose, attempt 1 valid | emitted once, for attempt 0 |
| 13 `reask_with_override_stop_sequence_records_attempt_0_only` | native | both attempts prose; the override adds a stop sequence for attempt 1 | emitted once, for attempt 0 |
| 14 `no_backend_observer_still_emits_once` | native | prose on `stop`, no backend observer attached | emitted once |
| 15 `native_not_json_with_empty_stop_list_emits_once` | native | prose on `stop`, `stop_sequences: []` | emitted once |
| 16 `native_refusal_reported_as_stop_absent` | native | an OpenAI refusal that OpenAI reports as `stop` | absent |
| 17 `native_streamed_refusal_streams_content_tokens_absent` | native | a streamed OpenAI refusal reported as `stop` | absent |
| 18 `native_not_json_with_empty_extras_stop_emits_once` | native | prose on `stop`, `stop: []` in extras | emitted once |
| 19 `reask_both_attempts_emit_one_record_each` | native | both attempts prose on `stop`, no stop sequence | emitted twice, once per attempt |

**What the absence cases are for.** Without them an implementation that emitted on every
`structured_output_invalid`, or on every native call, would pass. Case 2 pins the narrowing to malformed and
non-object content, case 3 the non-object arm, case 7 the stop sequence carried in extras, cases 12 and 13
the per-attempt evaluation and the rule that the call's event describes the request its outcome came from,
case 14 that the record does not depend on an observer being attached, cases 15 and 18 that an empty stop
list, declared or in extras, does not suppress the record, and cases 16 and 17 that the check reads the
mapped `finish_reason`, not the one OpenAI reports.

**Record content.** Every case that expects the record asserts its four attributes
(`openarmature.llm.provider`, `openarmature.llm.model`, `openarmature.llm.call_id`,
`openarmature.llm.attempt_index`) and its `openarmature.correlation_id`, on a `WARNING` record. Each sets
`caller_correlation_id`, so the correlation id is asserted as that literal value. The record's call id and the
call's typed event bind the same `<call_id_a>` token, so the record must name the call it reports on. A
separate entry counts every record with the event name at any level, so a second record at another level
fails the count. In case 1 the response reports a dated model name, so the record must name the model the
provider is bound to.

**Observers.** Every case except case 14 composes both backend observers (`otel_observer: {}` and
`langfuse_observer: {}`, conformance-adapter §5.5), so an absence case covers a check placed in either
observer, and each record count catches an implementation that emits once per observer. Case 14 composes neither
(`otel_observer: {attached: false}` and no Langfuse key), so an implementation that emits the record from
inside an observer fails it.

**Retry cases.** A caught attempt emits no typed event (graph-engine §6, as in fixture 116). Cases 12, 13
and 19 therefore count the call's typed events, so exactly one terminal event and no other. That event
carries the node-level `attempt_index` 0. In cases 12 and 13 one attempt qualifies, so the record count is 1
and the record carries `openarmature.llm.attempt_index` 0. In case 19 both attempts qualify, so two records
carry indexes 0 and 1 and the same call id. Each attempt's span is asserted through `llm_spans`, with the path
attribute and the attempt's error category. In case 13, attempt 1's span carries the stop sequence the
override added and attempt 0's carries none, so each span reports its own request. Each wire attempt takes
the next `mock_llm` entry. The reask template has no placeholders, so the rendered correction is the literal
template and case 12 can assert `input_messages` exactly.

**What fails:**

- Emitting for a well-formed object that fails the schema (case 2).
- Not emitting for a non-object top level (case 3), for a reask-recovered attempt (case 12), or when the stop
  list is empty, declared or in extras (cases 15, 18).
- Emitting at most one record per call, or writing the node-level or a fixed index into the record (case 19).
- Emitting despite `length`, `content_filter`, a declared or extras stop sequence, or a non-native path
  (cases 4 to 8, 13).
- Emitting for an OpenAI refusal because OpenAI reported `"stop"` (cases 16, 17).
- Emitting once per observer (cases 1, 3, 12, 13, 15, 18, 19), or only when an observer is attached
  (case 14).
- A record missing an attribute, carrying the wrong correlation id, or naming a call id other than its call's
  (cases 1, 3, 12 to 15, 18, 19), or naming the response's model instead of the bound model (case 1).
- An event whose `input_messages` omit the schema directive on the prompt-augmentation path (case 8).
- A missing or wrong `structured_output_path` on the event (cases 9 to 11), or a path attribute on a span
  whose call had no schema (case 10).
- A terminal event describing the caller's original request rather than the last attempt's, a typed event
  for a caught attempt, or a wire-level `attempt_index` on the event (cases 12, 13, 19).
- A span reporting the caller's original request rather than its own attempt's (case 13).
- A streamed refusal whose pieces are not emitted as content token events (case 17).

**Limits.** Case 11 asserts only the event: whether a call rejected before sending gets an LLM span is not
specified. Case 8 asserts the schema directive's position and that it is a non-empty string, not its
wording, which is the implementation's; fixture 027 asserts on the wire that it references the schema.
