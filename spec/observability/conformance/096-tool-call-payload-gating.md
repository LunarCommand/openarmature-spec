# 096 — Tool-call payload gating

Verifies observability §5.5.4 / §5.5.11 (proposal 0063): `disable_provider_payload`
gates the tool payload attributes on the OTel tool span.

## Spec coverage

- §5.5.4 — `disable_provider_payload` (default `True`) suppresses
  `openarmature.tool.call.arguments` / `.result`; the identity attributes
  (`openarmature.tool.name` / `.call.id`) are not payload and stay.
- §5.5.11 — the payload attributes are subject to the flag.

## Cases

1. `payload_off_default_suppresses_arguments_and_result` — default config →
   identity present, arguments / result absent.
2. `payload_on_populates_arguments_and_result` — `disable_provider_payload: false`
   → arguments / result populated.

## Anti-cases

- Arguments / result emitted under the default (payload-off) posture.
- The identity attributes suppressed by the payload flag (they are not payload).
