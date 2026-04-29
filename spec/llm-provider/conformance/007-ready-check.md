# 007 — Ready Check

Verifies the strengthened §5 `ready()` contract: a successful return MUST imply that the next
`complete()` is expected to succeed. Each case below exercises a single `ready()` call against a
stub provider with various health states.

**Spec sections exercised:**

- §5 `ready()` — strong contract, distinguishes model-loaded from model-configured.
- §7 categories — `provider_authentication`, `provider_invalid_model`,
  `provider_model_not_loaded`, `provider_unavailable` are all accessible from `ready()`.

**Cases:**

1. `model_listed_and_loaded` — model listed AND serving → success.
2. `model_listed_not_loaded` — model listed but not serving (local-server warmup pattern) →
   `provider_model_not_loaded` (transient).
3. `authentication_failed` — 401 → `provider_authentication`.
4. `model_unknown_to_provider` — model not in catalog → `provider_invalid_model` (terminal).
5. `network_failure` — connection failure → `provider_unavailable`.

**What passes:**

- Case 1: `ready()` returns successfully without raising.
- Cases 2-5: `ready()` raises an error of the expected category.

**What fails:**

- Case 1: implementation succeeds when the model is in the registry but not loaded (regression of
  the strengthened contract).
- Case 2: implementation raises `provider_invalid_model` instead of `provider_model_not_loaded`
  (loses the operational distinction between "config wrong" and "warming up").
- Cases 3-5: any miscategorization.

## Implementation note

The mock's `health_endpoint` block is a simplification: a real local LLM server may use a separate
non-standard endpoint (e.g., vLLM's `/health` or LM Studio's runtime API) to distinguish loaded
from listed-but-not-loaded. The harness MAY simulate the implementation's actual probe shape;
what the spec requires is that the *outcome* maps correctly to a §7 category. Implementations are
free to use the probe that best fits the provider being targeted.
