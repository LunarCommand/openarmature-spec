# 091 — Metrics disabled: no measurements

Verifies observability §11.1 (proposal 0067): metrics are opt-in (default off), so
with `enable_metrics` off no measurement is recorded.

## Spec coverage

- §11.1 — when `enable_metrics` is `False`, no instrument is created and no
  measurement is recorded.

## Cases

1. `no_measurements_when_metrics_disabled` — the same usage-bearing completion as
   fixture 088, but `enable_metrics=False`: the metric-capture primitive records an
   empty set (`metrics: []`).

## Anti-cases

- Any measurement recorded with metrics disabled — the opt-in gate is broken.
- Metrics emitted whenever a `MeterProvider` is configured (default-on) rather than
  gated on `enable_metrics`.
