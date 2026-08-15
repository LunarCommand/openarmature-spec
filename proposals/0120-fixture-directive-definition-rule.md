# 0120: Require Every Fixture Directive to Have a Definition

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-15
- **Accepted:**
- **Targets:**
  - spec/conformance-adapter/spec.md **§3.2 / §3.3**: resolve the tension between them. §3.2 permits
    per-directory harness notes and calls them normative; §3.3 says the capability spec is "the authoritative
    schema reference" and per-directory material is "navigational aids at most". Read together they leave no
    answer to "where is directive X defined", which is how roughly fifty directives came to be defined
    nowhere. Restate the division: the capability spec defines the **general** surface, a per-directory note
    MAY define a **directory-local** directive, and every directive MUST have exactly one of those two homes.
  - spec/conformance-adapter/spec.md **§3 (new subsection)**: the **definition rule**. A fixture MUST NOT
    depend on a directive that is defined in neither place. A directive discoverable only by reading another
    fixture is undefined for this purpose. State the consequence for an adapter encountering an
    undefined-but-present key, which today is unspecified and therefore silently divergent.
  - spec/conformance-adapter/spec.md **§5.8 / §5.x**: define the **expected-outcome assertion** directives
    currently defined nowhere (roughly thirty-five; the inventory is in *Detailed design*). This class is
    prioritized because an adapter that silently ignores an assertion turns a fixture **green for the wrong
    reason**, which is indistinguishable in a passing run from the assertion holding.
  - spec/conformance-adapter/spec.md **§9**: an adapter encountering a directive with no definition MUST
    fail the fixture with `fixture_directive_unknown` rather than ignore it, and the catalogue entry is
    widened to say so explicitly.
- **Related:** 0081 and 0107 (prior directive-vocabulary documentation passes, which this generalizes from a
  one-time sweep into a standing rule), 0119 (documents `content_repeat` and `attribute_truncation`, two
  instances found the same way; its open question 1 is what prompted this)

## Summary

The conformance-adapter spec is described as the authoritative schema reference for fixture syntax, but
roughly fifty directives that shipped fixtures depend on are defined neither in it nor in any per-directory
note. This adds the missing rule that every directive must have a definition somewhere discoverable, defines
the assertion directives (the class where an unimplemented directive silently passes), and adds a check that
stops the gap reopening.

## Motivation

### The gap, measured

Parsing all 497 shipped fixture files (744 cases) and collecting every key at a **structural** position (a case-level
sibling of `nodes:` / `expected:`, or a key directly under `expected:`), then checking each against the
conformance-adapter spec with whole-word matching, yields 93 undefined there. Checking those in turn against
every per-fixture markdown sidecar and every YAML header comment **in their own capability directory**, so
that §3.2's per-directory allowance is credited wherever it actually applies, leaves **54 defined nowhere at
all**: 17 case-level input directives and 37 expected-outcome assertions. Two of the 37 are fixture-local
labels rather than directives (prompt-management's `r_*` resolver-result keys), so the real figure is
approximately **52**, of which roughly **35** are assertions.

They are not exotic. `no_session_save: true`, `no_spans_emitted: true`, `checkpoint_saves`,
`expected_failure_isolation_event`, `llm_span_attributes_absent`, `span_tree_global`, `determinism_check`,
`concurrency_invariant` and `queryable_observers` are all load-bearing, and all are discoverable only by
reading a fixture that happens to use one.

### Why the assertion class is the dangerous half

The two halves fail differently.

A **case-level input** directive that an adapter does not implement usually fails loudly: the harness cannot
set up the case, so the fixture errors. Divergence is visible.

An **expected-outcome assertion** that an adapter does not implement fails **silently**. The adapter reads
`expected:`, evaluates the keys it recognizes, ignores `no_session_save`, and reports a pass. The fixture is
green, the conformance report says the behavior is covered, and nothing was checked. `no_*` assertions are
the sharpest case, because their whole purpose is asserting that something did not happen, and an adapter
that skips them agrees with every implementation including a broken one.

This is the same failure this repository has now hit twice in recent memory: an assertion that reads as
working while checking nothing. Proposal 0119 found `metadata_truncation` would have shipped with two of the
four sub-keys that gate it, and a mutation test downstream found a fixture asserting the wrong log record.
Neither was caught by the suite being green, because green was exactly the symptom.

### Why the rule is missing rather than the definitions

§3.2 and §3.3 disagree, and that is the root cause rather than any individual omission.

§3.2 ("Per-directory harness notes via fixture-header comments") states that a fixture-header comment block
"is normative for the observability fixture suite even though it isn't part of this capability spec", that
implementations MUST honor per-directory harness notes, and that per-directory specialization is "a permitted
extension". §3.3 states that "the capability spec is the authoritative schema reference; per-directory
READMEs are navigational aids at most".

An author adding a directive can satisfy either sentence and believe they are done: put it in a fixture
header (§3.2 blesses that) or assume the capability spec covers it (§3.3 says it is authoritative). Nothing
says a directive needs a home at all, and nothing detects one without. Fifty-two is what that produces over
the life of the corpus, and the per-directory coverage is uneven in a way that confirms it: the observability
and pipeline-utilities directories open with substantial header blocks, prompt-management has twelve lines,
sessions has four, and graph-engine has none.

Adding fifty-two definitions without fixing the rule would leave the next fifty-two to accumulate the
same way.

## Detailed design

### §3.2 / §3.3: one question, one answer

Restate the division so that "where is directive X defined" has exactly one answer:

> Every directive a fixture depends on MUST be defined in exactly one of two places:
>
> 1. **This capability spec (§5.x)**, for a directive used by more than one capability's fixtures, or whose
>    contract is general even if only one capability currently exercises it.
> 2. **A per-directory harness note** (§3.2), for a directive whose contract is specific to one capability's
>    fixtures and does not generalize.
>
> A directive defined in neither is **undefined**, regardless of how many fixtures use it. Being inferable
> from a fixture that uses it does not constitute a definition: an adapter author cannot distinguish a
> directive's contract from one fixture's incidental usage of it.

§3.3's "authoritative schema reference" sentence is narrowed to what it should have said: the capability spec
is authoritative for the **general** surface and for the rule above, while a per-directory note is
authoritative for the directives it defines. The current wording is what makes §3.2 read as contradicted.

### §3 (new): the definition rule and its consequence

> **Directive definition rule.** A fixture MUST NOT depend on an undefined directive. A proposal that
> introduces a directive MUST define it in one of the two homes above in the same change that introduces the
> fixture using it.
>
> An adapter encountering a key at a directive position that it does not recognize MUST fail the fixture with
> `fixture_directive_unknown` (§9). It MUST NOT ignore the key and report a pass. This applies to keys under
> `expected:` specifically: an unrecognized assertion is a failure to evaluate the fixture, not an assertion
> that trivially holds.

That last paragraph is the load-bearing one, and it is a behavior change rather than documentation. It
converts the silent-pass failure mode into a loud one for every directive, including the ones this proposal
does not get to.

### §5.8 and siblings: define the assertion directives

The following are defined in this proposal, grouped by the capability whose fixtures use them. Each gets its
value shape, its semantics, and whether it is exhaustive or subset-matching, which is the distinction that
made `metadata:` and `metadata_absent` two separate directives in 0118.

**Presence and absence assertions.** `no_spans_emitted`, `no_llm_provider_span`, `no_edge_spans`,
`no_langfuse_observations_emitted`, `no_token_events_emitted`, `no_session_load`, `no_session_save`,
`no_auto_save_on_end`, `no_failure_isolation_event`, `no_propagated_error`, `store_untouched`. All boolean,
all asserting a negative, and all currently able to pass by being ignored.

**Span-shaped assertions.** `span_tree_global`, `span_tree_private`, `llm_span_attributes`,
`llm_span_attributes_absent`, `parent_trace`, `detached_trace_count`, `no_edge_spans`. Note that `span_tree`
itself is defined only in §3.2's worked example, as an observability-local shape; these variants are its
siblings and are defined alongside it.

**Record and event assertions.** `checkpoint_saves`, `latest_record_assertions`, `timing_records`,
`trace_records`, `expected_attempt_events`, `expected_observer_event`,
`expected_failure_isolation_event`, `node_completed_event_carries_error`, `migrations_run`.

**Invocation-shaped assertions.** `invocation_count`, `per_invocation`, `final_state_bounds`,
`response_usage`, `recoverable_state`, `inner_pre_state`, `instance_pre_states`, `store_after`,
`determinism_check`, `concurrency_invariant`, `delivery_order`, `result_equivalence`, `rendered_hash_equal`,
`rendered_hash_different`.

Each is defined from its shipped usage, and where a fixture's usage is ambiguous about the general contract,
the definition states the narrower reading and says so. Writing a wider contract than the fixtures
demonstrate would freeze a guess into a shipped spec, which is the one outcome worse than the status quo.

### The case-level input directives are not defined here

Roughly seventeen case-level directives (`clock_stub`, `queryable_observers`, `seeded_session`,
`session_state`, `session_migrations`, `secondary_manager`, `tertiary_manager`, `subgraph_with_idx`,
`langfuse_observer_config`, `direct_call`, `inner_subgraphs`, and others) remain undefined after this
proposal, and this is deliberate rather than an oversight.

Their semantics have to be recovered from fixture archaeology, and several encode harness setup whose
contract is genuinely unclear from usage alone. Writing thirty more definitions in the same change as the
rule would mean guessing at some of them under deadline, and a wrong definition in a shipped spec is worse
than a missing one: a missing directive is caught by the new check, while a wrong one is obeyed. They fail
loudly today (an adapter that cannot set up a case errors rather than passes), so leaving them undefined for
one more cycle carries the lower risk.

The check below lists them by name on every run, so they are tracked rather than forgotten, and the list is
the worklist for the follow-on.

## Conformance test impact

**This is a behavior change for adapters, not only documentation.** Requiring `fixture_directive_unknown` on
an unrecognized directive means an adapter that today silently ignores a key must now fail. Any adapter
passing a fixture by ignoring one of the roughly thirty-five assertion directives will start failing it, which is
the point: those fixtures were reporting a pass they had not earned. Implementations SHOULD expect their
conformance numbers to move, and a proposal that makes previously-green fixtures red is the correct outcome
where the green was unearned.

No fixture YAML changes. The corpus already uses every directive being defined; this makes the definitions
exist.

**New check.** `scripts/validate_fixture_directives.py` parses every fixture, collects keys at directive
positions, and fails when one is defined in neither the capability spec nor its own directory's notes. It
runs in the existing markdown-validation workflow. Its exemption list holds only the fixture-local label
families identified during this proposal's sweep, each named with the reason, so the list cannot quietly grow
into a way of silencing the check. The seventeen deferred case-level directives are reported by name on every
run as a tracked worklist rather than suppressed.

## Alternatives considered

1. **Do nothing.** Rejected: roughly fifty undefined directives is already a cross-implementation hazard, and
   the assertion half can pass without checking anything. A second implementation reading only the capability
   spec would silently under-implement the suite and report full conformance.
2. **Define all fifty-two in this proposal.** Rejected on risk, not effort. Several case-level directives
   have contracts that cannot be recovered confidently from their fixtures, and a wrong definition is obeyed
   by implementers while a missing one is caught by the check. The rule plus the dangerous half plus a
   tracked worklist gets most of the value with none of the guessing.
3. **Define the case-level directives and defer the assertions.** Rejected: exactly backwards. Case-level
   directives fail loudly when unimplemented; assertions fail silently.
4. **Add the check without the normative rule.** Rejected: the check would encode a rule the spec does not
   state, so a failure would be arguable rather than a conformance defect, and §3.2 could be cited to
   dismiss it.
5. **Require every directive in the capability spec and retire per-directory notes.** Rejected: §3.2 exists
   for a real reason, since a genuinely capability-local harness contract does not belong in a cross-capability
   surface. The problem is the missing rule, not the existence of the second home.
6. **Make an unrecognized directive a warning rather than a failure.** Rejected: a warning in a conformance
   run is a pass, and the entire defect being closed is passes that were not earned.

## Open questions

1. **Whether the seventeen deferred case-level directives should be defined in one follow-on or absorbed by
   whichever proposal next touches each.** The piecemeal route is what produced this backlog, so the
   follow-on is preferred, but several are tied to capabilities with their own in-flight work and may be
   better defined by the proposal that is already reasoning about them.
2. **Whether `fixture_directive_unknown` should distinguish an unknown directive from a known directive used
   at the wrong position.** Both are fixture defects and both should fail, but the diagnostics differ in
   usefulness, and §9's catalogue currently has one token for the pair.
3. **Whether the definition rule should extend to value-level vocabulary**, not just directive keys. The
   §5.10 value matchers are documented, but a directive's permitted *values* (an enum of modes, for example)
   are sometimes only demonstrated by usage. That is the same defect one level down, and it is left out of
   scope here rather than expanded into.
