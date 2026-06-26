# 076 — Nested Fan-Out Resume Lineage

Pins proposal 0085's nested-fan-out checkpoint contract: the
`enclosing_fan_out_lineage` field and the **No mis-skip across enclosing
instances** invariant in §10.11. A fan-out (`inner_process`) nested inside an
outer fan-out instance recurs once per outer instance, so the same
`(namespace, fan_out_node_name)` appears multiple times in `fan_out_progress`,
distinguished only by `enclosing_fan_out_lineage`. On resume, each re-entering
outer instance must consult only the inner entry whose lineage positively
matches it, skipping only its own completed inner instances and never
mis-skipping across outer instances.

**Spec sections exercised:**

- §10.11 `enclosing_fan_out_lineage` — the per-entry outermost→innermost chain
  of `{namespace, fan_out_node_name, fan_out_index}` enclosing-instance
  identifiers that distinguishes the same inner fan-out node per outer
  instance, extending §10.11.1's exactly-once guarantee to nested fan-outs.
- §10.11 **No mis-skip across enclosing instances** — the engine MUST
  positively match a saved entry's lineage to the re-entering execution before
  applying its `completed` skips; an empty/absent saved lineage never matches a
  non-empty re-entering lineage, so a legacy record forces a full re-run.
- §10.7 per-instance resume skip decision — the `completed`/`in_flight`/
  `not_started` classification, now gated on the lineage match.
- §10.2 `fan_out_progress` record shape — entries keyed by `(namespace,
  fan_out_node_name, enclosing_fan_out_lineage)`; multiple entries may share a
  `(namespace, fan_out_node_name)`.

## Topology and arithmetic

Outer fan-out `outer_process` over two outer items; each outer instance runs
the inner fan-out `inner_process` over its three projected inner items; the leaf
computes `out = input`.

- Outer instance 0: `inner_items` `[1, 2, 3]` → `inner_results` `[1, 2, 3]`.
- Outer instance 1: `inner_items` `[4, 5, 6]` → `inner_results` `[4, 5, 6]`.
- `all_results` (append reducer; merged in **outer-index order** at the outer
  fan-in per §10.11.1) = `[[1, 2, 3], [4, 5, 6]]`.

This final state is deterministic even though the outer fan-out runs
`concurrent` — §10.11.1 merges accumulator entries in instance-index order,
independent of completion order.

## Case 1 — `nested_inner_fan_out_resume_skips_per_enclosing_lineage`

The seeded record is a mid-flight snapshot with **both outer instances
`in_flight`**, so the inner fan-out node carries **two distinct
lineage-qualified entries** (asserting requirement 1 — distinct entries, not one
colliding entry). Asymmetric inner progress:

| Outer instance | lineage `fan_out_index` | inner 0 | inner 1 | inner 2 |
| -------------- | ----------------------- | ------- | ------- | ------- |
| 0              | 0                       | `completed` (r=1) | `completed` (r=2) | `not_started` |
| 1              | 1                       | `completed` (r=4) | `not_started`     | `not_started` |

On resume (requirements 2 and 3):

- Outer instance 0 matches lineage `[{outer_process, 0}]`, skips inner 0 and 1,
  re-runs inner 2 (=3) → `inner_results` `[1, 2, 3]`.
- Outer instance 1 matches lineage `[{outer_process, 1}]`, skips inner 0,
  re-runs inner 1 (=5) and inner 2 (=6) → `inner_results` `[4, 5, 6]`.
- `all_results` = `[[1, 2, 3], [4, 5, 6]]`, equal to a from-scratch run.

**What passes:**

- The two same-node inner entries are matched per `enclosing_fan_out_lineage`,
  not collapsed.
- Each outer instance skips only its own completed inner instances.
- Outer instance 1's inner 1 (=5) is **re-run**, never skipped on the strength
  of outer instance 0's `inner-1 = completed` entry.
- Final `all_results` is `[[1, 2, 3], [4, 5, 6]]`.

**What fails (the mis-skip bug 0085 closes):** an engine that keys
`fan_out_progress` by `(namespace, fan_out_node_name)` alone collapses the two
inner entries to one (last-write-wins or merge). Either collision direction is
caught by the exact `final_state`:

- collapse to outer-0's entry `[✓1, ✓2, ✗]` → outer-1 wrongly skips inner 0 and
  1, rolling results 1, 2 forward → `all_results` `[[1,2,3],[1,2,6]]`.
- collapse to outer-1's entry `[✓4, ✗, ✗]` → outer-0 wrongly skips inner 0,
  rolling result 4 forward → `all_results` `[[4,2,3],[4,5,6]]`.

## Case 2 — `legacy_unlineaged_nested_entry_forces_full_re_run`

Pins the **No mis-skip** safety floor directly. The seeded record is
legacy-shaped: a single `inner_process` entry with **no
`enclosing_fan_out_lineage`** (the pre-0085 colliding shape), marking inner 0
and 1 `completed` (results 1, 2).

On resume, each re-entering outer instance carries a non-empty lineage, which
never positively matches the entry's absent lineage, so the engine treats each
inner fan-out as having no saved progress and **re-runs all inner instances**.
Final `all_results` = `[[1, 2, 3], [4, 5, 6]]`.

**What passes:** the legacy entry's skips are discarded; every inner instance
re-runs in every outer instance; the accumulator equals a from-scratch run.

**What fails:** an engine that applies the legacy entry (ignoring the
no-mis-skip invariant) skips inner 0 and 1 for **both** outer instances, rolling
results 1, 2 into outer instance 1 (true inner values 4, 5, 6) →
`all_results` `[[1,2,3],[1,2,6]]` — a silent mis-skip caught by `final_state`.

## Fixture-specific invariant predicates

Per conformance-adapter §5.9 these are documented here; the adapter implements
each against the resumed outcome.

- `inner_fan_out_progress_matched_per_enclosing_lineage` — each re-entering
  outer instance's skip decision used only the inner entry whose
  `enclosing_fan_out_lineage` equals its own, never a sibling's.
- `each_outer_instance_skips_only_its_own_completed_inner_instances` — the set
  of skipped inner indices per outer instance equals exactly its own
  lineage-matched `completed` set (outer-0: {0,1}; outer-1: {0}).
- `no_inner_instance_skipped_across_enclosing_instances` — no inner instance is
  skipped on the strength of a different enclosing instance's entry (outer-1's
  inner 1 and 2 and outer-0's inner 2 all re-run).
- `legacy_unlineaged_entry_not_applied_to_nested_fan_out` — the no-lineage entry
  produced no skips for any re-entering outer instance.
- `all_inner_instances_re_run_in_every_outer_instance` — every inner index runs
  in every outer instance (full re-run): outer-0 {0,1,2}, outer-1 {0,1,2}.

## Notes — why this fixture seeds the record, and directive gaps

**Seeded, not crash-produced.** Proposal 0085's testing sketch describes "a
crash injected while one outer instance is `in_flight` and another has
`completed` its inner fan-out." A saved record holding two distinct
lineage-qualified inner entries *simultaneously* requires two outer instances in
flight at once — only possible under `concurrent` outer execution. The exact
per-instance states captured at a crash save under concurrency are
dispatch-timing-dependent (the same nondeterminism fixture 051 absorbs with
`state_one_of`), and there is no way to deterministically pin "crash while
outer-0 is at inner progress X and outer-1 at inner progress Y." This fixture
therefore **seeds** the precise two-entry record via `seeded_record` /
`resume: {from_seeded_record: true}` (the mechanism the migration suite 039-047
uses to test resume from an exact record shape — e.g. 043 seeds a mid-subgraph
record with `parent_states`). This deterministically exercises 0085's
**consume-side** contract (lineage-matched skip, no mis-skip, exactly-once
accumulator), which is the correctness property the proposal adds. The only new
record/assertion content is `enclosing_fan_out_lineage`; its absence in Case 2
is the legacy shape.

**Directive gaps a deterministic crash-PRODUCED (write-side) variant would
need** — flagged, not invented:

1. **Lineage-qualified crash targeting.** `crash_injection`'s boundaries
   (`after_node`, `after_fan_out_instance: {node, index}`, §5.6) are not
   qualified by enclosing fan-out lineage, so they cannot pin a crash to a
   specific outer instance's inner-fan-out progress. A nested-aware boundary
   would be required to crash-produce the two-entry snapshot deterministically.

2. **Multi-entry `saved_record_assertions.fan_out_progress`.** The assertion
   shape (§5.8) keys per-node by `<node_name>` → a single `{instance_count,
   instances}` value per node, so it cannot assert the two lineage-qualified
   entries a nested fan-out writes for one `(namespace, fan_out_node_name)`.
   Asserting a crash-written record would need the assertion value to accept a
   list of lineage-qualified entries (or to key by the full `(namespace,
   fan_out_node_name, enclosing_fan_out_lineage)` triple). This fixture sidesteps
   the gap by seeding the record directly — `seeded_record.fan_out_progress`
   carries the natural §10.2 record shape (a list of full entries), so no
   assertion-shape change is exercised here.

3. **Lineage-qualified resume instance lists.** `instances_executed_during_resume`
   / `instances_skipped_during_resume` (§5.8) are flat `fan_out_index` lists,
   not qualified by enclosing lineage, so for a nested fan-out they cannot
   express "outer-0 skips inner {0,1}; outer-1 skips inner {0}" distinctly per
   outer instance. This fixture uses the fixture-specific invariant predicates
   above instead.

**Harness note.** `seeded_record` / `resume: {from_seeded_record: true}` are
established by fixtures 039-047 but are **not enumerated in conformance-adapter
§5.6**. Seeding a `fan_out_progress` (let alone a lineage-qualified one) is new
usage — prior `seeded_record` fixtures seed `state`, `parent_states`, and
`completed_positions` only. The adapter must deserialize a seeded
`fan_out_progress` whose entries carry `enclosing_fan_out_lineage`, and map the
abstract `namespace` node-name paths (cf. 043's `namespace: [sub]`) to its
runtime namespace representation so the seeded entries positively match the
re-entering execution.
