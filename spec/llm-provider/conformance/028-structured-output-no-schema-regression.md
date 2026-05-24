# 028 — Structured Output No-Schema Regression

Regression test: `complete()` called WITHOUT `response_schema`. The
v0.4.0 free-form behavior MUST be preserved exactly. `Response.parsed`
is absent, the wire body MUST NOT include `response_format`, and the
call succeeds with text content regardless of whether the model
happens to return content that looks like JSON.

**Spec sections exercised:**

- §5 — when `response_schema` is `None`/absent, the call behaves as
  in v0.4.0; `Response.parsed` is absent regardless of content.
- §8.1.5 — when `complete()` is called without `response_schema`, the
  request body MUST NOT include `response_format`.

**What passes:**

- Wire request does NOT include `response_format`.
- `Response.message.content` is the literal model output (which happens
  to look like JSON, but isn't parsed).
- `Response.parsed` is absent (null / None / undefined per language).
- `finish_reason == "stop"`.

**What fails:**

- `response_format` appears in the wire body — would mean the
  implementation defaulted to structured-output mode (breaks v0.4.0
  callers).
- `Response.parsed` is populated — would mean the implementation
  auto-detected the JSON-looking content and validated it, contrary to
  §5's "parsed is absent when response_schema is None" rule.
