# 002 — Signal payload merge semantics

The signal payload is merged into the loaded state via shallow field
overlay. Reducers declared on the state schema (per graph-engine §2)
are NOT consulted — the merge is a direct field-by-field overwrite.

**Spec sections exercised:**

- §6 — default shallow field overlay; reducers not consulted.
- §6 — rationale: the signal payload represents authoritative external
  data ("the human's decision is X", "the job result is Y"); applying
  reducers would obscure this.

**What passes:**

- The pre-suspend state has `audit_log = ["entry_a"]` (set via the
  field's `append` reducer in the pre-node).
- The signal_payload supplies `audit_log = ["entry_b"]`.
- The resumed state's `audit_log` is `["entry_b"]` — direct overwrite,
  NOT `["entry_a", "entry_b"]` (which would indicate the append
  reducer was incorrectly consulted on merge).
- The scalar `scalar_field` is similarly overwritten by the payload.

**What fails:**

- Resumed `audit_log` is `["entry_a", "entry_b"]` — would mean the
  append reducer was applied to the signal_payload merge (violating
  the direct-overwrite contract).
- Resumed `audit_log` is `["entry_a"]` — would mean the signal_payload
  did not apply.
