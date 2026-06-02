# 059 — Implementation attribution rows on Langfuse Trace metadata

Verifies §8.4.1's two new `trace.metadata.*` rows (`implementation_name` and
`implementation_version`) are present on every Langfuse Trace, sourced from the §5.1 OTel
attributes per the mapping table. Companion to fixture 058 (OTel-side).

**Spec sections exercised:**

- §8.4.1 — Two new Trace metadata rows; sourced from §5.1 attributes (parallel to
  `spec_version`'s row).
- §5.1 — Always-emit invariant inherited by the Langfuse mapping (rows emit regardless of
  privacy knobs).

**Cases:**

1. `implementation_attribution_rows_present_on_every_trace` — Any graph invocation against a
   fixture-mock Langfuse client. Asserts:
   - `trace.metadata.implementation_name` is present, non-empty, and matches the
     implementation under test.
   - `trace.metadata.implementation_version` is present and non-empty.
   - Both rows emit regardless of `disable_state_payload` setting (the always-emit invariant
     applies to runtime-identity constants).

**What passes:**

- Both rows present on Langfuse Trace metadata; both non-empty strings.
- `implementation_name` matches the per-language canonical value.
- Rows emit under both `disable_state_payload = True` (the default) and `disable_state_payload
  = False` configurations — privacy knob does not gate runtime-identity constants.

**What fails:**

- Either row missing from `trace.metadata` — §8.4.1 mapping not applied or the source §5.1
  attribute not emitted.
- Either row empty / null — §5.1 says "never null" and the §8.4.1 mapping preserves the values
  verbatim.
- Rows suppressed when `disable_state_payload = True` — the always-emit invariant from §5.1 is
  inherited; the privacy knob gates runtime data (caller state, LLM messages), not runtime
  identity.
