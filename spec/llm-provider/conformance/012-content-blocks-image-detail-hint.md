# 012 — Content Blocks Image Detail Hint

Two calls. Call 1 sets `detail: "high"` on the spec `ImageBlock`; the
wire payload's `image_url.detail` MUST be `"high"`. Call 2 omits `detail`
on the spec block; the wire payload's `image_url` entry MUST NOT include
the `detail` key (provider applies its own default).

**Spec sections exercised:**

- §3.1.2 Image block — `detail` field; optional with default
  `"auto"`. Providers that don't honor the hint MUST ignore it without
  error.
- §8.1.1.1 Content-block wire mapping — `detail` hint propagation:
  "The `detail` hint, when set on the spec block, becomes
  `image_url.detail`."

**What passes:**

- Call 1's wire payload has `image_url.detail == "high"`.
- Call 2's wire payload's `image_url` entry does NOT include a `detail`
  key at all.

**What fails:**

- Call 1's `detail` field is absent on the wire — would mean the hint
  isn't being propagated.
- Call 2's `detail` is set to `"auto"` (or another default value) by the
  framework — would mean the framework is injecting a default the spec
  says the provider should apply.
