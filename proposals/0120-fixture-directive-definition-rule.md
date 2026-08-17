# 0120: Reconcile the Directive-Definition Rule and Enforce It

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-15
- **Accepted:**
- **Targets:**
  - spec/conformance-adapter/spec.md **§5 preamble, §11, §8.2, §3.2, §3.3, §5.9**: reconcile six statements of
    where a directive may be defined, which currently disagree. §5's preamble and §11 both call §5 "the
    authoritative enumeration"; §8.2 anchors lossless parsing to "the §5 directive vocabulary" and requires an
    unknown directive to raise; §3.2 makes a per-directory harness note normative and calls per-directory
    specialization "a permitted extension"; §5.9 sends fixture-specific predicates to "the originating
    fixture's prose" and says "adapters MUST also implement those"; §3.3 demotes per-directory prose to
    "navigational aids at most". Restate them as one rule with one scope, so a directive defined only in a
    per-directory note is not simultaneously required to raise (§8.2) and required to be implemented (§5.9).
  - spec/conformance-adapter/spec.md **§5 (new subsection)**: define **what counts as a definition**. The spec
    currently uses the notion throughout without a test, so a bare mention of a name in prose is
    indistinguishable from a contract. State the minimum a definition must supply (YAML location, value shape,
    and the adapter behavior it obliges) and state that a name appearing in prose without those is not a
    definition.
  - spec/conformance-adapter/spec.md **§8.2**: extend the existing trigger rather than restating it. §8.2
    already requires an unknown directive to raise `fixture_directive_unknown`; the change is to re-anchor its
    vocabulary from "§5" to the reconciled set, and to state that the rule reaches keys at every directive
    position, including under `expected:` and under `nodes.<name>:`, so an unrecognized **assertion** is a
    failure to evaluate the fixture rather than an assertion that trivially holds.
  - spec/conformance-adapter/spec.md **§9**: widen `fixture_schema_invalid` to cover a violated co-occurrence
    constraint between two known directives, which its current scope (missing required directive, malformed
    type, invalid YAML) does not reach. `fixture_directive_unknown` needs no change.
  - spec/conformance-adapter/spec.md **§5.8, §5.9 and siblings**: define the **39 assertion directives** that
    are undefined under every reading of the current rules. This class is prioritized because an adapter that
    does not implement an assertion reports a pass, which is indistinguishable in a passing run from the
    assertion holding.
  - spec/conformance-adapter/spec.md **§5.4**: clarify that an inline subgraph definition at document root is
    referenced by its `name:` value, so a key such as `subgraph_with_idx` is a subgraph definition rather than
    a directive and is outside the directive vocabulary entirely.
- **Related:** 0081 and 0107 (prior directive-vocabulary documentation passes, which this generalizes from
  one-time sweeps into a reconciled rule plus enforcement), 0119 (documents `content_repeat` and
  `attribute_truncation`, two instances found the same way; its open question 1 is what prompted this)

## Summary

Six sections of the conformance-adapter spec state where a fixture directive may be defined, and they
disagree. For 50 directives the disagreement produces two conflicting MUSTs: §8.2 requires an adapter to raise
on them because they are outside §5, while §5.9 requires an adapter to implement them because a per-directory
note defines them. Nothing enforces any reading, which is why a further 61 directives are defined nowhere at
all. This reconciles the six statements into one rule, gives "definition" a test, extends §8.2's existing
trigger to assertion positions, and defines the 39 undefined assertions.

## Motivation

### Two MUSTs, opposite outcomes, same key

The spec says all of the following, in six places:

| Section | What it says |
|---|---|
| §5 preamble | "This section is the authoritative enumeration of directives currently in use." |
| §11 | "The directive vocabulary §5 is the authoritative enumeration." |
| §8.2 | "Parsing MUST be lossless against the §5 directive vocabulary; unknown directives MUST raise `fixture_directive_unknown` (per §9) rather than being silently skipped or treated as defaults." |
| §3.2 | A fixture-header comment block "is normative for the observability fixture suite even though it isn't part of this capability spec"; implementations "MUST honor per-directory harness notes"; per-directory specialization is "a permitted extension". |
| §5.9 | "Fixture-specific predicates not listed here are documented in the originating fixture's prose per §3.2 per-directory harness notes; adapters MUST also implement those." |
| §3.3 | "The capability spec is the authoritative schema reference; per-directory READMEs are navigational aids at most." |

Take a directive defined only in a per-directory note, which §3.2 and §5.9 both explicitly sanction. It is not
in §5. So §8.2 requires an adapter to raise `fixture_directive_unknown` on it, and §5.9 requires the same
adapter to implement it. Both are MUSTs, both are conforming readings, and they cannot both be satisfied.

This is not hypothetical. **50 directives sit in exactly that position**: named in their capability directory's
fixture prose, absent from §5. `no_spans_emitted` is one. An implementer following §8.2 raises and fails
observability fixture 028; an implementer following §5.9 implements it and passes. Same fixture, opposite
verdicts, both defensible from the shipped text.

The proposal this document replaces diagnosed the problem as a missing rule. That was wrong: the rule is
present in at least three of the six sections above. The defect is that it is stated with three incompatible
scopes and enforced by nothing.

### What non-enforcement has produced

Parsing all 497 fixture files (744 cases) and collecting every key at a directive position (a case-level
sibling of the reserved case keys, a key under `expected:`, or a key under `nodes.<name>:`) yields 211 distinct
keys. Checking each against §5 by whole-word match, then against its own capability directory's fixture
sidecars and YAML header comments:

| Reading | Basis | Undefined |
|---|---|---|
| A: §5 only | §5 preamble, §11, §8.2 | 114 |
| B: §5 plus directory prose | §3.2, §5.9 | 64 |
| The gap between them | the contradiction above | **50** |

The 64 undefined under **both** readings are unambiguous gaps under any interpretation. Excluding two
fixture-local label families (prompt-management's `r_ec` and `r_unknown_resolver_no_default`, which are
resolver-result keys rather than directives) and one document-root subgraph definition (`subgraph_with_idx`,
addressed in §5.4 above) leaves **61 genuine directives** defined nowhere.

### Classified by role, not by position

The earlier draft partitioned these by where the key sat in the YAML and called the case-level group "input
directives". Position is not role, and the spec itself documents a case-level **assertion** (§5.8's
`expected_construction_error`). Classified by what each key actually does:

| Role | Count | Where they sit |
|---|---|---|
| Outcome assertions | **39** | 35 under `expected:`, plus 4 at case level (`expected_wire_bytes_identical`, `expected_backend_state`, `expected_message_equal`, `expected_shared_prefix`) |
| Input / setup | **22** | 13 at case level, 9 under `nodes.<name>:` |

The four case-level assertions matter because the earlier partition deferred them.
`expected_wire_bytes_identical` (llm-provider fixtures 054 and 055) appears nowhere in `spec/`, `docs/` or
`proposals/` outside the two YAML files that use it, and its contract is self-describing: `{calls: [0, 1]}`. An
adapter ignoring it passes the wire-byte-stability fixture having compared no bytes at all.

The nine node-position directives (`noop`, `retry_middleware`, `emits_log`, `explicit_save_session`,
`also_emits_via_global_tracer`, `capture_queryable_observer_read_into`, `per_attempt_behavior`,
`then_assert_bucket_absent_into`, `then_drop_for_current_invocation`) sit at the **canonical** directive
position: §5.1 is titled *Node behavior directives* and §8.3 legislates their document-order execution. A sweep
restricted to case and `expected:` positions never sees them.

### Why the assertion class is prioritized, and what that does not claim

An adapter that does not implement an **assertion** evaluates the keys it recognizes, skips the rest, and
reports a pass. The fixture is green, the conformance report says the behavior is covered, and nothing was
checked. The `no_*` assertions are the sharpest case: their purpose is asserting that something did not happen,
so an adapter that skips them agrees with every implementation including a broken one.

The earlier draft justified deferring the input class on the claim that an unimplemented input directive "fails
loudly" because the harness cannot set the case up. **That claim is false, and it is worth correcting
explicitly because it would otherwise be inherited.** `spec/sessions/conformance/005-session-auto-save-off.yaml`
sets `auto_save: false`, turning a default off. An adapter ignoring that key still compiles the graph, runs the
node, reaches END, and satisfies `expected.final_state`. Nothing errors. The only detectors are
`no_session_save` and `store_after`, both in the undefined-assertion set and therefore skipped. The same shape
holds for `clock_stub` (pipeline-utilities 012 runs against a real clock; only the undefined `timing_records`
would notice) and `langfuse_observer_config` (observability 059 runs both cases with the default config, so the
axis under test is never exercised).

So the input class is **not** self-detecting either. Its loudness, where it exists, is parasitic on the
assertion class. The assertions are prioritized because they are the larger group and because defining them
also restores the detection the input class depends on, not because the input class is safe.

## Detailed design

### One rule, one scope

Replace the six overlapping statements with a single rule, stated in §5's preamble and cross-referenced from
the others:

> **Where a directive may be defined.** Every directive a fixture depends on MUST be defined in one of:
>
> 1. **§5 of this capability spec**, for a directive used by more than one capability's fixtures, or whose
>    contract is general even if only one capability currently exercises it.
> 2. **A per-directory harness note** (§3.2), for a directive whose contract is specific to one capability's
>    fixtures and does not generalize.
>
> Together these are the **recognized vocabulary**. §5 remains authoritative for the general surface and for
> this rule; a per-directory note is authoritative for the directives it defines. Where both define the same
> directive, §5 governs and the note's variant is non-conforming, so that one fixture cannot mean two things.
>
> A directive defined in neither is **undefined**. Being inferable from a fixture that uses it is not a
> definition (see *What counts as a definition*).

§3.3's "navigational aids at most" sentence is narrowed to what it should have said: a per-directory README is
a navigational aid, while a per-directory **harness note** under §3.2 is normative for what it defines. The
current wording is what puts §3.3 in conflict with §3.2 and §5.9.

§5.9's predicate rule is re-anchored to the same set, so "the originating fixture's prose" is understood as a
§3.2 per-directory harness note rather than a separate third home.

### What counts as a definition

> A **definition** of a directive MUST supply all of: its YAML **location** (which position it appears at), its
> **value shape**, and the **adapter behavior** it obliges. A definition MAY additionally name the spec section
> the directive exists to exercise.
>
> A name appearing in prose without those three is **not** a definition. This matters because it is the
> difference between a contract an adapter can implement identically to another adapter, and a mention that
> leaves the contract to be reconstructed from one fixture's usage.

Without this test the rule above is unenforceable, because "defined" would be satisfied by any occurrence of
the name. It is also the test the accompanying check applies.

### §8.2: extend the trigger, do not restate it

§8.2 already carries the operative requirement, so this proposal amends it rather than adding a second
statement elsewhere:

> Parsing MUST be lossless against the **recognized vocabulary** (§5 plus any applicable per-directory harness
> note). A key at a directive position that the adapter does not recognize MUST raise
> `fixture_directive_unknown` (§9) rather than being silently skipped or treated as a default.
>
> **Directive positions** are: a case-level key that is not one of the reserved case keys (`name`,
> `description`, `state`, `entry`, `nodes`, `edges`, `initial_state`, `expected`, `cases`); a key under
> `expected:`; and a key under `nodes.<name>:`. The rule applies at all three. In particular an unrecognized
> key under `expected:` is a failure to **evaluate** the fixture, and an adapter MUST NOT treat it as an
> assertion that holds.

Two things change. The vocabulary is re-anchored so it no longer contradicts §3.2 and §5.9. And the positions
are enumerated, because "unknown directives" left the `expected:` and node positions to inference, which is
where the silent-pass mode lives.

The earlier draft described this as a behavior change. It is not: §8.2 and §9 already require an adapter to
raise rather than skip, so an adapter that silently ignores a directive is already non-conforming. What changes
is that the requirement becomes unambiguous about *which* keys it covers and *which* vocabulary defines
"unknown".

### The 39 assertions

Defined in §5.8 and siblings, grouped by shape, each with its value shape, its semantics, and whether it
matches exhaustively or as a subset (the distinction that made `metadata:` and `metadata_absent` two directives
under proposal 0118):

**Negative assertions** (all boolean, all currently able to pass by being skipped): `no_edge_spans`,
`no_session_load`, `no_session_save`, `no_auto_save_on_end`, `no_failure_isolation_event`,
`no_propagated_error`, `store_untouched`.

Four further negative assertions (`no_spans_emitted`, `no_llm_provider_span`,
`no_langfuse_observations_emitted`, `no_token_events_emitted`) are deliberately **absent** from this list.
They are defined in their capability directory's prose, so they sit in the 50 governed by the contradiction
rather than the 61 defined nowhere. The reconciliation above resolves them without a new definition: once the
recognized vocabulary includes per-directory notes, an adapter implements them instead of being required by
§8.2 to raise. `no_spans_emitted` is the Motivation's worked example for exactly that reason.

**Span-shaped**: `span_tree_global`, `span_tree_private`, `llm_span_attributes`, `llm_span_attributes_absent`,
`parent_trace`, `detached_trace_count`.

**Record and event**: `checkpoint_saves`, `latest_record_assertions`, `expected_attempt_events`,
`expected_observer_event`, `node_completed_event_carries_error`, `migrations_run`, `langfuse_traces`.

**Invocation-shaped**: `invocation_count`, `per_invocation`, `final_state_bounds`, `response_usage`,
`inner_pre_state`, `instance_pre_states`, `store_after`, `determinism_check`, `concurrency_invariant`,
`result_equivalence`, `rendered_hash_equal`, `rendered_hash_different`, `direct_call_result`, `prompt_group`,
`empty_phases_raises_at_registration`.

**Case-level assertions** (position notwithstanding): `expected_wire_bytes_identical`, `expected_backend_state`,
`expected_message_equal`, `expected_shared_prefix`.

Each is defined from its shipped usage. Where a fixture's usage is ambiguous about the general contract, the
definition states the narrower reading and says so, because a wider contract than the fixtures demonstrate
would freeze a guess into a shipped spec.

### The 22 input directives are deferred, and the risk is stated

The 22 input directives are not defined here. The reason is **not** that they are self-detecting: the section
above shows they are not. The reason is that several encode harness setup whose contract cannot be recovered
confidently from usage, and a wrong definition in a shipped spec is obeyed by implementers while a missing one
is caught by the check below.

That is a risk being accepted rather than avoided, and the accept should record it as such: until they are
defined, a fixture whose setup directive an adapter ignores can run in an unintended configuration and pass,
and the assertions defined by this proposal are what will catch it. Defining the assertions first is therefore
the ordering that reduces the exposure fastest, but it does not eliminate it.

The check reports all 22 by name on every run, so the list is a tracked worklist rather than an omission.

## Conformance test impact

**No fixture YAML changes**, and no fixture becomes unrunnable by this proposal. The corpus already uses every
directive being defined; this makes the definitions exist and makes the vocabulary that decides "unknown"
unambiguous. The earlier draft claimed conformance numbers would move because of a new adapter obligation; that
framing was wrong, since §8.2 and §9 already impose it.

What may move is an adapter's conformance result once it stops recognizing a directive it previously accepted
without a definition, or starts recognizing one it previously raised on. Both directions are possible today
under the contradiction, which is the point: the reconciliation makes the outcome determinate rather than a
matter of which section an implementer read.

**New check.** `scripts/validate_fixture_directives.py` parses every fixture, collects keys at the three
directive positions, and fails when a key is not defined in the recognized vocabulary, applying the three-part
definition test above rather than a name match. It runs in the existing markdown-validation workflow.

Its exemption list holds only non-directive keys, each named with a reason: the two fixture-local label families
and the document-root subgraph definitions clarified in §5.4. The earlier draft asserted such a list "cannot
quietly grow", which is not a property a list has; instead the check requires a reason string per entry and the
accept states that an entry without one is a defect, which is a constraint that can actually be inspected.

## Alternatives considered

1. **Do nothing.** Rejected: the two conflicting MUSTs are live in the shipped spec for 50 directives, so two
   conforming implementations can reach opposite verdicts on the same fixture today.
2. **Add a new definition rule without reconciling the six existing statements** (the earlier draft's shape).
   Rejected: it diagnosed a missing rule where the rule already exists three times over, and would have
   produced a seventh statement with a fourth scope. The §8.2-versus-§5.9 contradiction would have survived
   acceptance untouched.
3. **Resolve the contradiction toward §5 only**, retiring per-directory notes as a definition home. Rejected:
   §3.2 exists for a real reason, since a genuinely capability-local harness contract does not belong in a
   cross-capability surface, and §5.9 deliberately scopes its enumeration "to keep this list maintainable".
   Retiring the second home would move roughly 50 definitions into §5 for no benefit.
4. **Resolve toward the notes only**, making §5 non-authoritative. Rejected: it discards the cross-capability
   surface that makes a directive portable, and §5 is what a new implementation reads first.
5. **Define all 61 in this proposal.** Rejected on risk, not effort. The 22 input contracts cannot all be
   recovered confidently from their fixtures, and a wrong definition is obeyed while a missing one is caught.
6. **Define the inputs and defer the assertions.** Rejected: the assertions are the larger group, they are the
   silent-pass class, and defining them restores the detection the input class depends on.
7. **Make an unrecognized directive a warning rather than a failure.** Rejected: a warning in a conformance run
   is a pass, and unearned passes are the defect being closed. This is also already settled by §8.2.

## Open questions

1. **Whether the 22 input directives should be defined in one follow-on or absorbed by whichever proposal next
   touches each.** The piecemeal route is what produced this backlog, so a single follow-on is preferred, but
   several belong to capabilities with in-flight work and may be better defined by the proposal already
   reasoning about them.
2. **Whether the definition test should apply retroactively to §5's own entries.** Some existing §5 entries may
   not supply all three parts. The check applies the test to the recognized vocabulary as a whole, so it would
   flag them; whether that is in scope for the accept or a follow-on sweep is a judgment call.
3. **Whether `fixture_schema_invalid` should distinguish a violated co-occurrence constraint from a malformed
   type.** Both are fixture defects and both must fail, but the diagnostics differ in usefulness and §9
   currently has one token for the pair.
4. **Whether the definition rule should extend to value-level vocabulary.** §5.10's value matchers are
   documented, but a directive's permitted *values* are sometimes only demonstrated by usage. That is the same
   defect one level down, and it is left out of scope here.
