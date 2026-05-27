# 030 — Caller-Metadata Mid-Invocation Augmentation (Parallel-Branches Per-Branch)

Companion to fixture 029. Verifies §3.4's mid-invocation augmentation + per-async-context
scoping contract for the parallel-branches concurrency exception (pipeline-utilities §11),
which dispatches heterogeneous subgraphs through a different code path than fan-out.

The parallel-branches dispatcher fires two branches concurrently; each branch augments the
in-scope metadata with its own `branchName` before its LLM call. The harness asserts that
sibling branches don't see each other's augmentations and that the baseline caller metadata
reaches every span / observation.

**Spec sections exercised:**

- §3.4 — mid-invocation augmentation via the framework helper.
- §3.4 — per-async-context scoping for parallel-branches (called out explicitly in §3.4's
  per-async-context-scoping paragraph alongside fan-out).
- §5.6 — `openarmature.user.*` cross-cutting attributes reflect in-scope metadata at span
  emission time.
- §8.4.1 — Langfuse `trace.metadata` carries only the baseline (no augmentations bubble up
  to the parent context).
- §8.4.2 — Langfuse `observation.metadata` on each branch's observations carries the
  branch's augmentation alongside the baseline.

**Cases:**

1. `parallel_branches_augment_metadata_independently` — invocation passes
   `{tenantId: "acme-corp"}` as baseline; dispatcher dispatches two branches concurrently
   (`fraud_check`, `policy_audit`); each branch's body augments the metadata with
   `branchName = <its branch's name>` before making its LLM call. Harness asserts
   per-branch isolation and baseline ubiquity.

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — same as fixtures 026 / 027 / 029.
- `parallel_branches.branches.<name>.augment_metadata: {key: value, ...}` — harness
  primitive: at the top of the named branch's subgraph (before any LLM call runs), the
  harness internally calls the framework's augment-metadata helper with the supplied
  entries. Equivalent to placing
  `set_invocation_metadata(branchName="fraud_check")` at the top of the
  `fraud_check` branch's first node.
- `invariants.parallel_branches_per_branch_metadata_isolation: true` — harness verifies
  no branch's observation metadata contains the sibling branch's `branchName`.
- `invariants.baseline_caller_metadata_universal: true` — harness verifies every span and
  observation carries the baseline `tenantId`.

**What passes:**

- Each branch's observations carry both `tenantId` AND its own `branchName`.
- `fraud_check` branch's observations carry `branchName: "fraud_check"`, NOT
  `branchName: "policy_audit"`.
- `policy_audit` branch's observations carry `branchName: "policy_audit"`, NOT
  `branchName: "fraud_check"`.
- The Trace's `metadata` carries only `tenantId` (no `branchName` from either branch).

**What fails:**

- Branches see each other's `branchName` — implementation's parallel-branches dispatcher
  didn't preserve per-async-context isolation. Common miss: using the same `ContextVar` /
  `AsyncLocalStorage` reference across concurrent branch tasks rather than dispatching
  each branch in its own async context with a copy of the metadata.
- The Trace's `metadata` ends up with one of the branches' `branchName` values — the
  implementation's parallel-branches dispatcher applied per-branch augmentations to the
  parent context. Violates §3.4's per-async-context scoping rule.
- Some branches' observations are missing the baseline `tenantId` — the
  parallel-branches dispatcher reset the metadata to only the augmentations within
  branches instead of additively merging. Violates §3.4's additive-merge rule.
- The contract holds for fan-out (fixture 029 passes) but fails for parallel-branches —
  implementation's parallel-branches code path skipped the per-async-context handling
  that fan-out implements correctly. Pipeline-utilities §9 and §11 are separate code
  paths but MUST honor the same §3.4 scoping rules.
