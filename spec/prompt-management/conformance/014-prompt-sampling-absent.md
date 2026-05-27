# 014 — Prompt.sampling Absent (Opt-In Semantic)

Verifies §3's "opt-in per backend" semantic for the new `sampling` field. A backend that
doesn't supply sampling config returns Prompt with the field as null/None; the manager does
NOT synthesize a default at any layer.

**Spec sections exercised:**

- §3 — `Prompt.sampling` is optional; absent when the backend doesn't supply it.
- §4 — `PromptResult.sampling` propagation: when source is absent, result is absent.
- §3 "opt-in per backend" paragraph: the spec does NOT mandate a default sampling config
  in the absence of a supplied one.

**Cases:**

1. `backend supplies no sampling` — backend's Prompt record has no `sampling` field;
   `PromptResult` after render also has no `sampling` field.

**Harness extensions:**

- `expected.rendered.sampling_absent: true` — harness asserts the field is null / None /
  undefined per language idiom (NOT a populated SamplingConfig with default values).

**What passes:**

- `Prompt.sampling` is absent on fetch.
- `PromptResult.sampling` is absent after render.
- No defaulting at the manager layer.

**What fails:**

- Manager synthesizes a default SamplingConfig (e.g., all-fields-null SamplingConfig)
  when backend supplied none — violates §3's opt-in semantic. Should remain absent.
- `Prompt.sampling` is a populated SamplingConfig with default-ish values (all `None` in
  declared fields, empty extras) — also defaulting; should be absent entirely.
- Backend silently raises or refuses to fetch when no `sampling` is configured — the
  field is OPTIONAL; absence is valid.
