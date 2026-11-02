# 0127: Matching Rules and Definitions for the Assertion Directives

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-10-29
- **Accepted:** 2026-11-01
- **Targets:**
  - spec/conformance-adapter/spec.md: rewrites §8.4 (the matching rules every assertion follows); adds §4.5 (what a
    fixture may assert), §5.16 (wire-request assertions, moved out of §5.15) and §5.17 (capability gates,
    generalized from §5.5); modifies §2 (the *Assertion shape* and *Invariant* entries), §3.2 (span_tree and the
    binding tokens become general), the §5 preamble (assertion positions and the reserved absence keys), §5.1 (the
    middleware-log sentence, the accumulator snapshot, `flaky_by_index`'s deterministic form and `flaky_per_index`'s
    failures and optional `category`), §5.5 (its preamble, typed-event and log assertions, and the `accumulate`
    behavior's buckets), §5.6 (its preamble, session, resume and checkpointer assertions, and their positions), §5.7
    (`run_count`), §5.8 (its preamble's position rule, the state snapshots, raised errors including `raises` and the
    harness turn outcomes, observer events, spans and traces, metrics and checkpoint records), §5.9 (its opener),
    §5.10 (its opener, `<timestamp>` and the binding-token rules), §5.11 (what `llm_spans` reads for a bare call,
    and the `appended_messages` forms), §5.12 and §5.13 (pointers to the new `raises` and `cause` definitions),
    §5.15 (the order mock responses are dispatched in), §6.1 (per-call accumulator buckets), §6.2, §6.3, §6.7 and
    §6.9 (what the harness primitives record)
  - spec/observability/spec.md: modifies §11.5 (the metric-capture primitive records each measurement)
  - the harness notes of observability, llm-provider, pipeline-utilities, harness, harness-chat, sessions,
    prompt-management and suspension: definitions for the assertion directives only that directory uses, and for
    the capabilities and mock inputs those assertions rely on
  - fixtures in every other capability's conformance directory: about 300 files, listed in *Fixture changes*
- **Related:** 0120 (the definition-homes rule this completes for assertion directives), 0126 (`log_records`
  counts and absence, `llm_spans`), 0081 and 0107 (earlier vocabulary passes), and a following proposal that
  settles the named-claim assertions (`invariants:` blocks and the boolean claims under `expected:`)

## Summary

A fixture says what to compare and almost never says how. Whether a list names every item, whether a mapping must
match exactly, what a written `null` means, and which error an error assertion reads are all left to each
adapter, and adapters can read the same fixture differently. A large part of the assertion vocabulary also has no
definition. This proposal states the matching rules once, in §8.4, and gives every assertion directive in use a
definition, except the named claims a following proposal settles. It also corrects the fixtures that a conforming
implementation would fail under the rules.

## Motivation

### The rules a fixture depends on are not written down

Four examples, each from shipped fixtures:

- **Does a list name every item?** Observability fixtures 143, 145 and 147 call their `metrics` list "the
  exhaustive set of recorded observations". Fixtures 129 and 131 say the same list "cannot express" an absence.
  §5.8 says `metrics: []` means nothing was recorded and is silent about a list with entries. Span `children`
  lists, observer event lists and wire-request lists state no rule either.
- **Must a mapping match exactly?** §5.8 calls `final_state` an "exact-equality assertion", yet 53 retrieval and
  pipeline cases put keys in it that name no state field, such as `vectors_length` and `errors_list_length`.
  Below the top level nothing is stated at all: fixtures 140 and 148 rely on an exact match to show that a usage
  key is missing, while llm-provider fixtures write partial message records and rely on the opposite.
- **What does `null` mean?** §5.5 says a `null` in `contains_event.fields` matches only a field that is present
  and null. Where the capability specs define an unset field, they describe it as "Absent (`null` / `None` /
  `undefined`, per the language's idiom)" or the like. An implementation in a language where an unset field is
  simply missing fails these fixtures with no defect.
- **Which error does an error assertion read?** Of 128 `expected_error.category` uses, 87 expect a provider
  category such as `provider_unavailable` and 22 expect `node_exception`, often for the same situation: a node
  raised a categorized provider error. graph-engine §4 reports a node failure as `node_exception` while the
  node's own exception propagates, so both readings are available and nothing says which an adapter takes. §5.8
  describes the directive as being for failures "at construction or first-node entry", which fits almost none of
  its uses.

### Much of the vocabulary is defined nowhere

Since proposal 0120, a directive's definition lives in §5 or in its directory's harness note, and §8.2 requires
an adapter to raise on a directive in neither. About 65 keys used under `expected:` blocks, several case-level
`expected_*` keys, and many keys inside span and observation entries are in neither home. Examples:
`expected_failure_isolation_event` (15 uses), `delivery_order`, `migrations_run`, `nodes_executed_during_resume`,
`latest_record_assertions`, `traces`, `langfuse_traces`, `status_description` and `exception_recorded`.
`span_tree`, which about fifty observability fixtures use, is defined only by observability's harness note,
although sessions uses it too.

### Why it matters now

Two adapters that read one fixture differently can both pass it while their implementations disagree, which
defeats the point of shared fixtures. It also blocks a decision that depends on these rules: which named claims
an adapter must implement turns on whether another assertion in the same case already pins the claim, and that
has no answer while the assertions themselves have no defined matching.

## Detailed design

### 1. The matching rules (§8.4)

§8.4 *Assertion* currently says only that an adapter verifies each `expected:` block with its host's test
framework. It is replaced by the rules below. A directive's definition says what an assertion reads; these rules
say how the written value is compared with what was read. A definition MAY vary a rule only in the ways the rules
allow: declaring a list unordered, a set, or an existence list; declaring a mapping position exact; or stating a
directive-specific comparison where the capability spec makes two values equivalent or leaves an order partly
open. Examples of the last kind are `tool_calls: null` matching an empty list, a carrier link matching a run of
carriers, and a migration list ordered only within each chain.

#### 1.1 Single values

- A single value (a string, number, boolean or `null`) compares equal to the observed value, after the §5.10
  value matchers are applied.
- Numbers compare by numeric value: `1` matches `1.0`. A boolean never matches a number, and a string never
  matches a number.
- **Span attributes are the exception.** observability fixes each attribute's OpenTelemetry type, so the type is
  part of the value there: a YAML integer matches only an integer attribute and a YAML float only a double. On a
  host whose attribute model has a single numeric type, an integer-valued double cannot be told apart from an
  integer, so a whole-number value compares by value there.
- A value that a wire mapping defines as a JSON-encoded string, such as a tool call's `arguments`, is compared
  after decoding both sides as JSON. Two implementations may serialize the same arguments with different
  separators, and the capability specs require only that the string be JSON.
- Strings compare case-sensitively, and so do the substring matchers: `_mentions`, `content_contains`
  and `content_includes`.
- Floating-point values compare exactly, as binary64 values.

#### 1.2 Lists

- **A list of observed items is complete.** A list written as the expected value of something observed names
  every observed item in the directive's scope: spans, observations, events, requests, saves, metric recordings,
  executed nodes, migrations and the like. `[]` asserts there are none. Leaving the key out asserts nothing.
- **Completeness applies only where the spec fixes the whole set of items.** A directive over an open stream,
  where other items may legitimately appear, is an *existence list*: each entry asserts that some observed item
  matches it. `log_records` is an existence list, as §5.5 already says.
- **Order.** A list is compared in order unless its definition declares it unordered. An unordered list matches
  when there is a one-to-one pairing of entries to observed items in which every pair matches. The adapter MUST
  search for such a pairing and MUST NOT assign greedily, because a general entry can take an item that a more
  specific entry needs. Binding tokens are resolved together with the pairing.
- **Repeats count.** An item observed twice MUST appear twice, unless the definition declares the list a set.
- **A parameter list is not an observed list.** A list that a directive takes as a parameter, such as an
  `_absent_keys` list, `attributes_present` or `event_counts`, means whatever its definition says.
- **A list inside data compares as a value:** complete and in order. A vector, an attribute array and a list held
  in state are examples.

The lists declared unordered are named in their definitions: span and observation `children`, a span's `links`,
the top-level span and trace lists, a Langfuse trace's top-level `observations`, `metrics`, `traces` and
`langfuse_traces`, the instance lists of a resume, and `nodes_skipped_during_resume`.
The spec fixes which span is whose parent, and which traces a span links to, but not the order of siblings or of
links, and §7 forbids an adapter from imposing an order the spec does not fix. Where order matters, a fixture
asserts it through attributes such as the step or attempt index. `expected_compile_warning` is declared a set.

#### 1.3 Mappings

- **A mapping asserts the keys it names, at every depth.** A key it does not name is unconstrained.
- **A position is exact only where an extra key would be a defect rather than an addition**, and only where its
  definition declares it. At an exact position the written mapping is the whole value: an omitted key MUST be
  absent, and nested values compare exactly at every depth. The exact positions are:
  - **Whole-state positions:** `final_state` and the other state snapshots (§4.2 below). The state is declared by
    the case, so a key outside its schema is a defect.
  - **Values copied from the case's own inputs:** an event's `request_params` and `request_extras`, a
    `RuntimeConfig` or sampling `extras` mapping, a tool call's `arguments`, a response's `parsed` value,
    `descriptor.metadata`, an appended message written `{role, content}`, `attribute_parses_as_object`, a
    Langfuse trace's `input` and `output`, `raw`, the provider's response body verbatim, and every wire copy of a
    value the capability specs send verbatim from the case's inputs. Among them are the copies of a
    `response_schema` (`response_format.json_schema.schema`, `output_config.format.schema`, a synthetic tool's
    `input_schema`, `responseJsonSchema`) and of a caller tool's parameter schema. These stay exact wherever they
    appear, inside an `expected_wire_request_includes` body too.
  - **Wire request bodies** asserted with `expected_wire_request`, which §5.15 and llm-provider fixture 005's
    header already compare exactly. For unchanged inputs the spec keeps the wire shape fixed, so a new optional
    wire field never reaches an existing fixture. Where the spec leaves part of a body to the implementation,
    `expected_wire_request_includes` (§4.7) matches by named keys instead.
  - **Metric `dimensions`**, whose complete set observability §11.3 fixes per instrument and outcome.
- **A record inside an exact position still matches by named keys.** That applies to a record in the
  implementation's own language that the engine or a provider wrote and whose type a capability spec defines,
  such as a provider response stored by `calls_embed` or a `ChatMessage`. It is compared by the keys the fixture
  names, because the spec may add optional fields to it. `raw` stays exact, and a message inside a wire body is
  JSON, not such a record, so it stays exact too.
- **A record whose shape the spec leaves to the implementation is asserted by count.** A collect-mode
  errors-field entry is the example. pipeline-utilities §9.7 and §11.1 leave its shape open, and §10.11 types it
  by the field the case declares. A fixture therefore MUST declare that field as a bare `list` (§5.2), which
  constrains no element, and MUST write each entry as `{}`. There `{}` matches any non-null entry, and the
  complete list asserts how many there are.

The reason for the split is that GOVERNANCE.md lists a "new optional field" among the backwards-compatible
additions a MINOR version may make. If nested mappings compared exactly, every new optional field on a record
would break each fixture that writes that record.

#### 1.4 Absence

- **`<key>_absent_keys: [...]`**, beside a mapping-valued key, lists keys that MUST be absent from that mapping.
  The existing `attributes_absent` and `metadata_absent` are instances of this form, spelled as they already are.
- **`absent_keys: [...]`**, inside the mapping of a list entry, lists fields of that entry that MUST be absent.
- **Both spellings are reserved.** A state field, data key or `capture_as` label MUST NOT be named `absent_keys`
  or end in `_absent_keys`.
- On a record in the implementation's own language, a field that is null counts as absent, matching §1.5.

#### 1.5 Null

- **A written `null` asserts that a field is not set.**
- **On a record or event in the implementation's own language,** it matches a field that is null or missing. The
  capability specs describe an unset field that way wherever they define one: llm-provider §6 writes "Absent
  (`null` / `None` / `undefined`, per the language's idiom)", and graph-engine §6 "Absent (null / None /
  equivalent)".
- **On a JSON document,** null and missing are distinct: `null` matches only null, and `_absent_keys` asserts
  that a member is missing. The JSON documents are:
  - wire request bodies and `raw`;
  - a span attribute parsed as JSON (`attribute_parses_as_messages`, `attribute_parses_as_object`);
  - a Langfuse observation's `input` parsed as JSON (`input_parses_as_messages`);
  - every mapping a recorded Langfuse trace or observation holds in a field, such as `metadata`, `usage`,
    `usageDetails` and `modelParameters`.
- **A Langfuse trace's or observation's own top-level fields are the exception.** A field the observer leaves
  unset reads as Langfuse's default, so how a recorder stores it cannot change the result.
  - For `input`, `output`, `statusMessage`, `userId` and `sessionId` the default is null. An unset field and one
    recorded as null are the same state, and `null` and `_absent_keys` both match either.
  - For `level` the default is `DEFAULT`. An unset or null level matches only `level: DEFAULT`.
- **A nested mapping still requires a present record,** as §5.5 already says for `contains_event`. A null or
  missing value cannot satisfy it.

This replaces §5.5's rule that a `null` in `contains_event.fields` matches only a field that is present and null.

#### 1.6 Binding tokens

- **One binding scope covers a whole case,** every assertion block included: `expected:`, `first_run_expected:`,
  `resume.expected:` and `invariants:`.
- **A token matches only a present, non-null value,** at every occurrence. A token that occurs once in a case
  asserts no more than that.
- **A repeated token also asserts equality** with every other occurrence of the same token. It never asserts
  that two different tokens hold different values.
- **The case passes if some assignment of values to its tokens makes every assertion hold.** First occurrence in
  document order is ambiguous inside an existence list or an unordered list, where the first candidate need not
  be the one the rest of the case needs.
- **Tokens are resolved at assertion time only.** An input that needs a value from an earlier call uses the input
  placeholders §5.7 and the directory notes define, which are resolved before the input is sent.

#### 1.7 What an assertion reads

- **What a block reads depends on where it sits.** A block in an invocation's or a resume block's `expected:`
  reads what that `invoke()` call produced: the events it dispatched, the spans and records it emitted, and the
  requests it sent. `first_run_expected` reads the first run's call. A case-level `expected:` reads what every
  call in the case produced. In a single-invocation case that is the one call. In a multi-invocation case it is
  all of them, as observability 084's case-level `langfuse_traces` lists both calls' traces.
- **A directive's own stated scope governs.** Where a definition says a directive reads one call's output, as
  `span_tree`, `observer_events`, the accumulator assertions and `langfuse_trace` do, it belongs in a block
  scoped to one call. A case-level block in a multi-invocation case MUST NOT use it, and an adapter rejects one
  that does with `fixture_schema_invalid`.
- **The unit is the call, not the invocation id.** A suspension resume reuses the suspended call's invocation id
  (suspension §7), so an event is attributed to the call that dispatched it.
- **A case with `run_count`** runs its graph that many times, each run one call, and its `expected:` block
  applies to each run. §5.7 gains a `run_count` entry that says so, since §5 has none.
- **When state is read.** Observer and backend state is read after delivery for the call has completed. Where the
  case's own drain timed out, it is read when that drain returned.

#### 1.8 Every written assertion is checked

- **An adapter MUST check every assertion a fixture writes.** No assertion is optional.
- **A fixture MUST NOT write an assertion an adapter MAY skip.** A capability gate (§5.17) does not make an
  assertion optional: a gated case either applies to an adapter, which then checks every assertion in it, or is a
  recognized skip.
- **A fixture's comments, sidecar and notes MUST NOT claim the fixture checks something that no written key
  asserts.**

### 2. What a fixture may assert (§4.5) and capability gates (§5.17)

New §4.5:

> A fixture asserts only what the spec requires. It MUST NOT pin a value the spec only RECOMMENDS or leaves to the
> implementation, one of several outcomes the spec allows, or an order the spec does not fix (§7). Where such
> behavior matters, the fixture asserts the part the spec fixes, or gates a case on a capability the adapter
> declares (§5.17). Gating MUST NOT take a check away from an adapter. Where the spec fixes what a gated case's
> inputs produce without the capability, every assertion in the case that holds either way MUST also be made, on
> the same inputs, by an ungated case or by a case gated on the capability's other value.

§5.5's `adapter_capabilities` / `requires_capability` mechanism, written for the Langfuse bound-provider
detection, moves to a general §5.17 unchanged in meaning:

- An adapter declares named capabilities.
- A case states the capabilities it requires, as `true` or `false`.
- A case whose requirement an adapter does not meet is a recognized skip, not a silent omission.
- An undeclared capability defaults to `false`.

A capability only one directory uses MUST be defined in that directory's note. One that several directories use,
or that §5 already defines, MUST be defined in §5.17. That puts three in §5.17:
`langfuse_bound_provider_detection`, moved from §5.5, and two new llm-provider capabilities that observability
fixture 161 uses too.

| Capability | The implementation |
|---|---|
| `llm_strict_native_schema` | sends `strict: true` for a schema that meets OpenAI's strict-mode constraints (llm-provider §8.1.5, a SHOULD). |
| `llm_prompt_augmentation_fallback` | falls back to prompt augmentation when the provider's capability metadata says the server lacks `response_format`, the static arm of llm-provider §8.1.5.1's SHOULD. The mocks can signal only through that metadata, so dynamic detection is outside the capability. |

The directory notes add three more, listed under their notes in §5.

### 3. Where assertions sit (§5.8 preamble) and what is open

§5.8's preamble says its directives "appear under per-invocation or per-case `expected:` blocks". That is true of
the bare-named directives and false of the prefixed ones. The preamble is rewritten to say that each directive's
definition states its position, and to name the two families that cover most of them:

- **Bare-named assertions sit inside `expected:`.** Examples: `final_state`, `execution_order`, `outcome`,
  `error`, `observer_events`, `span_tree`, `checkpointer_assertions`.
- **The `expected_*` assertions §5.8 and §5.16 define sit beside `expected:`** at their level: the case, an
  invocation, a resume block, or the document root in the single-case form. These are `expected_error`,
  `expected_compile_error`, `expected_construction_error`, `expected_compile_warning`, and the wire-request
  assertions.

The definitions that place a directive elsewhere:

| Directive | Position |
|---|---|
| `saved_record_assertions`, `every_save_assertions` | Case level, beside `expected:` (§5.8 and pipeline-utilities' note). |
| `first_run_expected_error`, `first_run_expected` | Case level, beside `resume:` (§5.6). |
| `expected_backend_state` | The document root (§6.8). |
| `expected_wire_bytes_identical` | The document root of an llm-provider `calls:` document (llm-provider's note). |
| `expected_chain_ambiguity_error` | Beside `expected:`, or inside `resume:` (pipeline-utilities' note). |
| `expected_failure_isolation_event`, `expected_attempt_events`, `expected_observer_event` | Inside `expected:` (pipeline-utilities' note). |
| `expected_shared_prefix`, `expected_message_equal` | Beside `expected:` (prompt-management's note). |
| `expected_listener_callback` | Inside a signal arrival (harness-chat's note). |

graph-engine fixture 014 and pipeline-utilities fixture 033, the two that nest `expected_error` inside
`expected:`, move it out.

The §5.5 and §5.6 preambles place every directive in those sections at the top level of a case, which their
assertion entries contradict. Each is rewritten to say that the section holds configuration and assertion
directives and that each entry states its position. §5.6's `session_store` and `checkpointer` entries, which
state none, gain theirs: the case level.

The §5 preamble gains a paragraph on assertion positions:

- Every key at an assertion position is a defined assertion directive, with two exceptions.
- **`capture_as` labels.** A label is an author-chosen name that a prompt-management call binds and an
  `expected:` key in the same scope then asserts. It is an open name space by design, as proposal 0120 noted. A
  label MUST NOT reuse a directive name valid at that position, and MUST NOT be named `absent_keys` or end in
  `_absent_keys`.
- **Named claims.** These are keys whose name is the whole claim, wherever they sit: keys inside an `invariants:`
  block, keys under `expected:` such as `no_spans_emitted: true`, and claim sub-keys inside a directive's
  mapping, such as `saved_record_assertions.parent_states_present`. The following proposal settles them. Until it
  does, an adapter MUST implement each named claim it meets, as §5.9 requires of a fixture-specific predicate.

### 4. Definitions in §5

These are the assertion directives used by more than one capability, or whose contract is general. Each is
written to match how every existing use reads it; where uses disagree, *Fixture changes* corrects the outliers.

#### 4.1 Raised errors

**One category rule for every raised-error assertion.** Each of these reads a raised error's category the same
way: `expected_error.category`, `first_run_expected_error.category`, `error.category` under `outcome: errored`,
harness `error_category`, `expected_attempt_events`' `error_category`, and `node_completed_event_carries_error`.
- **The category comes from pipeline-utilities §6.4's classification primitive.** That is the same primitive
  pipeline-utilities §6.3's `caught_exception` and the failure-isolation `catch` decision already use. It gives
  the category of the outermost link in the error's cause chain that is not a carrier and has a category.
- **What counts as a carrier.** A carrier is a graph-engine §4 `node_exception` wrapper, or a subtype of one such
  as `parallel_branches_branch_failed` (pipeline-utilities §6.3).
- **The fallback.** Where §6.4 gives null because no non-carrier link has a category, the assertion reads the
  outermost carrier's own category instead: `node_exception`, or the subtype's category.
- **The exception.** An observer event entry's `error.category` reads something different on purpose: the event's
  own graph-engine §6 `error` field, which carries the engine's §4 category.

**`expected_error`** (§5.8). A sibling of `expected:` at its level. It asserts that the case raised a categorized
error instead of completing or suspending. The error comes from the `invoke()` call at any point in the run, or
from registration or compilation where `raised_at` says so. §5.8's description of it as being for failures "at
construction or first-node entry" is removed. Each sub-key asserts only when present:

- **`category`** follows the rule above.
- **`message`** is the message pipeline-utilities §6.3 derives alongside the category: the message of the link
  the category came from, or of the outermost non-carrier link when no non-carrier link has a category.
- **`cause_message`** is the message of the innermost link in the chain. It differs from `message` where a
  non-carrier error wraps another, as a reducer error wraps the exception its reducer raised (graph-engine §4).
- **`raised_from`** names the node whose execution produced the error.
  - That is the node that raised, except that a node which wraps a failure from inside it names itself: a fan-out
    node, a parallel-branches node, or the node whose reducer merge raised.
  - A subgraph node that lets an inner node's error through is not named; the inner node is.
- **`recoverable_state`** is the state graph-engine §4 requires to be recoverable from the error. It is a state
  snapshot, so it is exact.
- **`cause: {raised_by_mock: <mock>}`** asserts that the raised error's cause, linked per the language's idiom,
  is the exception the named fixture mock raised. It replaces a host-language class name, and §5.13's sentence
  that leaves `cause` out of scope points here instead.
- **`raised_at: registration`** asserts that the error was raised while registering or compiling, before any
  `invoke()` call.
- **`carries`** follows §5.13.

**`raises`** (§5.8, beside `expected_error`; §5.12 and §5.13 mention it but never define it). It sits under a
call's `expected:` in llm-provider and prompt-management, and asserts that the operation raised instead of
returning. `category` compares with the error's category identifier and `carries` follows §5.13; no other sub-key
is defined. It excludes `response` at the same position.

**`outcome` / `error.category`** (§5.8). These read the outcome of the call the block belongs to, with the
category rule above. A clause is added for early detection. Where a capability spec lets an implementation detect
an error at compile or registration time, `outcome: errored` with that category is also satisfied when compiling
or registering raises the same category before the call starts. suspension §9 is such a case: collect-mode
suspension SHOULD be detected at compile or registration time.

**`expected_compile_warning`** (§5.8). Its list form is declared a set, so repeats are not counted, because
graph-engine §2 does not fix how many times a warning is emitted for one round-trip. It counts only warnings that
carry a graph-engine §2 warning category, so a host-language deprecation warning cannot fail `[]`.

**`first_run_expected`** (§5.6). A case-level block beside `first_run_expected_error` and `resume:`. It asserts
on the first run of a resume case, read from that run's call, and takes the same directives as an `expected:`
block.

#### 4.2 State

**`final_state`** (§5.8) is exact, as §5.8 already says, with §1.3's reading of what exact means:

- It names every field the state schema declares, and no other key. A key that names no field, such as
  `vectors_length`, fails.
- Plain data under a field compares exactly at every depth.
- A record the engine or a provider wrote, whose type a capability spec defines, matches by the keys the fixture
  names (§1.3). An `EmbeddingResponse` stored by `calls_embed` is an example. Inside such a record, `raw` is
  exact.
- A record whose shape the spec leaves to the implementation, such as a collect-mode errors-field entry, is
  asserted by count, each entry written `{}` (§1.3).

**The other state snapshots are exact on the same terms.** They are:

- `suspended_state`, `final_state_at_error` and `expected_error.recoverable_state`;
- an observer event's `pre_state` and `post_state`, and each element of its `parent_states`;
- a failure-isolation event's `pre_state`;
- a checkpoint record's `state` and its `parent_states` elements;
- sessions' `entry_state`, `inner_pre_state` and `instance_pre_states`.

**Two snapshot-like values are exact differently:**

- **A failure-isolation event's `post_state`** is the degraded update (pipeline-utilities §6.3), not a full
  state. It is exact as a mapping equal to that update.
- **A session's stored state** (`loaded_session_state`, `saved_session_assertions.state`) is the session's
  projection (sessions §4.2). It is exact over the projection's fields, not over the whole graph state.

**`final_state_bounds: {<field>: {min, max}}`** (§5.8, new). It reads the named fields of the final state and
asserts `min <= value <= max`, inclusive, with either bound optional. It constrains only the fields it names.

#### 4.3 Observer events

**`observer_events: {<observer>: [<entry>, ...]}`** (§5.8):

- **What it reads.** For each observer it names, the node events that observer received from the call the block
  belongs to: events that carry a `phase`. Typed events are asserted through §5.5's collector directives.
- **Matching.** The list is complete and ordered by delivery, and `[]` asserts that none were received.
  graph-engine §6 fixes the delivery order. A fixture MUST NOT use the directive where §7 says the order is not
  determined.
- **Entries.** Each entry matches one event by the graph-engine §6 fields it names:
  - `namespace` and `parent_states` compare as whole lists.
  - The state snapshots inside an entry are exact.
  - `descriptor` matches as the §5.8 `descriptor` directive does.
  - `error` is written `{category: <id>}`, the engine's §4 category of the event's error.
- **Absence of a field** is written with `absent_keys`.

**`delivery_order: [{observer, step, phase, ...}, ...]`** (§5.8, new). It reads every delivery of a node event to
an observer declared in the case's `observers:` list, `raise` observers included, for the call the block belongs
to.
- **Matching.** The list is complete and ordered by when each delivery began, and graph-engine §6 fixes that
  order.
- **Entries.** An entry matches by named keys. It MAY also name `attempt_index`, `fan_out_index` or `branch_name`
  where `step` and `phase` do not single out an event.

**`node_accumulator_snapshots`** and **`final_accumulator_state`** (§5.8). Both read an `accumulate` observer's
bucket for the call the block belongs to. The first reads it as captured when the node's drain returned, the
second after the call returned and delivery completed. Both lists are complete and ordered, and entries match as
`observer_events` entries do. §6.1's `accumulate` observer, and the `accumulate` behavior §5.5 lists, are amended
to keep one bucket per `invoke()` call rather than per invocation id, since a suspension resume reuses the id.
§5.1's `invoke_drain_events_for` snapshots the current call's bucket. §2's *Assertion shape* entry is reworded in
two places. It calls an assertion a key at an assertion position, which the §5 preamble describes, rather than a
field under `expected:`. It points at §8.4 rather than calling `final_state` a literal-equality check. §2's
*Invariant* entry and §5.9's opener, which describe the other assertions as exact-equality checks, also point at
§8.4.

**`drain_summary`** and **`node_drain_summaries`** (§5.8) match by named keys, because graph-engine §6 lets a
summary carry more detail. `node_drain_summaries` gains `undelivered_count_min`, which fixture 030 uses, and an
entry carries `undelivered_count` or `undelivered_count_min`, not both.

**`execution_order`** (§5.8) has one entry per execution of a node of the outermost graph, in the order the
executions began:
- **What counts as executed.** A node is executed when the engine invokes its wrapped function. A subgraph,
  fan-out or parallel-branches node is executed when the engine dispatches it.
- **What is left out.** Nodes inside such a node are not listed. A node whose middleware returned without calling
  `next` was never executed and is not listed.
- **One entry per execution.** Retry attempts within one execution are one entry. A node that raised was
  executed, and a node executed twice, for example around a loop edge, appears twice.
- **Matching.** The list is complete and ordered.

**`middleware_log_captured`** (§5.8, new). It reads the §6.7 middleware-log accumulator: the markers
`wrap_with_middleware` middlewares recorded during the call, in recording order. The list is complete and
ordered. §5.1's sentence that the markers are "recorded as state-log entries" is corrected to point at the §6.7
accumulator, and §6.7 keeps one accumulator per call, as §1.7 requires.

#### 4.4 Typed events (§5.5)

**`observers: {<collector>: <slot>}`** is the container that `contains_event` already sits in. Each slot holds
collector directives evaluated against the events that `typed_observers` collector retained from the call the
block belongs to.

**`contains_event`** stays an existence check, as now: some retained event of `event_type` matches. Changes:
- **`fields` is optional.** Without it, the directive asserts only that an event of the type exists.
- **Matching.** `fields` matches by named keys and the §1.5 null rule.
- **Absence.** `fields_absent_keys`, beside `fields`, lists event fields that must be absent. Inside `fields`,
  `<field>_absent_keys` does the same one level down.
- **Exact fields.** An event's `request_params` and `request_extras` are exact.

**`contains_events_in_order: {event_type, events}`**, now defined only in observability fixture 111's header,
moves to §5.5. It reads every retained event of the type in delivery order. `events` is complete and ordered, and
each entry matches as `contains_event.fields` does.

**`event_count`** and **`event_counts`** are parameter lists: each entry counts the retained events of one
family, and families a list does not name are unconstrained. An event type is matched by name against the
families graph-engine §6 defines. The list of families in §5.5 drops `LlmTokenFailedEvent`, which graph-engine §6
says does not exist.

**Three more §5.5 directives** are defined from their uses in observability 054 to 056:

- **`every_captured_event_has: {<field>: <value>}`** asserts that every retained event matches. It is vacuously
  true for an empty collector, so a fixture pairs it with a count.
- **`captured_event_field_values_cover: {field, values}`** asserts that each listed value appears on at least one
  retained event. `values` is a parameter set.
- **`relative_order_of_events_matching: {filter, expected_order}`** keeps the retained events, in arrival order,
  that match `filter`. It then asserts that the `expected_order` matchers occur among them as a subsequence.

**`node_completed_event_carries_error: {node_name, error_category}`** sits under `expected:`, not in a collector
slot, and reads the node events the call dispatched. It asserts exactly one completed node event from
`node_name`, whose error category, derived as for `expected_error`, must equal `error_category`.

Two duplicates of `event_count` are re-expressed in its terms and retired: `contains_exactly_n_events_of_type`
(observability 054, 055) and `does_not_contain_event_of_type` (observability 053).

#### 4.5 Spans and traces

**`span_tree: [<span entry>, ...]`** (§5.8, moved from observability's note, since sessions 012 uses it too).

- **What it reads.** The spans openarmature exported to its private exporter (§6.3) for the call the block
  belongs to, restricted to the trace rooted in that call's invocation span. Detached traces (observability §4.4)
  are not part of it; `traces` covers them.
- **Building the tree.** The spans are joined into a forest by parent span id. The top-level list names every
  root, and `children` names every child of an entry. Both are complete and unordered, and an entry without
  `children` asserts nothing about its children.
- **§6.3 is extended** so that any case asserting `span_tree`, `traces` or `llm_spans`, in any directory,
  composes the OTel observer and its in-memory exporter. A case does not declare its own OTel observer for this,
  so suspension 011's `behavior: otel` observer entry, which no definition covers, is removed. Such a case MUST
  NOT set `otel_observer: {attached: false}`, and an adapter rejects the combination with
  `fixture_schema_invalid`. §5.5's entry for `attached: false` points at this exception.

A span entry's sub-keys each assert only when present:

| Sub-key | Asserts |
|---|---|
| `name` | The span name. |
| `status` | The OTel status code: `OK`, `ERROR` or `UNSET`. |
| `status_description` | The OTel status description. |
| `exception_recorded` | `true`: at least one OTel exception event is recorded on the span. `false`: none is. |
| `attributes` | A mapping over the span's attributes, with span-attribute typing (§1.1). |
| `attributes_absent` | None of the listed keys is present (§5.11's meaning, now stated for every span entry). |
| `attributes_present` | Each listed key is present, with any value. A parameter list. |
| `attribute_truncation` | As §5.11 defines it. |
| `attribute_parses_as_messages` | The attribute parses as JSON to a message list. The list is complete and ordered, and each message matches by named keys. |
| `attribute_parses_as_object` | The attribute parses as a JSON object equal to the written mapping. Exact, since the object is the caller's extras. |
| `attribute_does_not_contain` | `{<key>: {forbidden_substring_kind: synthetic_base64_prefix}}`: the attribute does not contain the first 64 characters of the base64 data the case synthesized. |
| `links` | Every OTel link on the span (complete, unordered), each entry matched on `target_trace_id`. |
| `link_count` | The number of OTel links on the span. |
| `children` | Every child span (complete, unordered). |
| `absent_keys` | Span fields that must be absent. |

**`traces: [{trace_id, span_tree}, ...]`** (§5.8, new). It reads every trace holding spans from the call: the
invocation's own trace and each detached trace. The list is complete and unordered. `trace_id` compares as a
single value, usually through a `<trace_id_X>` binding token, and `span_tree` is that trace's forest.

**`otel_spans`** (§5.8) is retired. Its only use, suspension 011, is re-expressed as `span_tree`, so the corpus
has one tree directive. Observability's `parent_trace`, which equals `span_tree` under the reading above, is
retired the same way in fixture 008.

#### 4.6 Logs and metrics

**`log_records`** (§5.5) is declared an existence list. This states what §5.5 already says: each entry asserts
that some captured record matches the fields it names, the list is not exhaustive, and entries may match the same
record. `count` and `log_records_absent` carry exact counts and absence. An entry gains `trace_id` and `span_id`,
compared against the record's OTel trace context, which observability §7 keeps apart from the record's
attributes. An all-zero trace or span id, OpenTelemetry's invalid context, counts as absent, so a binding token
there does not match a record emitted outside any span. §6.3 is extended so that any case asserting
`log_records` captures log records.

**`metrics`** (§5.8):

- **Complete and unordered.** The list names every measurement the §6.9 capture recorded in the block's scope,
  and `[]` asserts none. It is a multiset, because observability §11 fixes which measurements are recorded, not
  their order.
- **Entries.** Each entry matches one recording:
  - `instrument` compares as a single value.
  - `value`, when written, compares by numeric value.
  - `dimensions` is exact, since §11.3 fixes the complete set.
- **One entry is one recording:** one histogram record or one counter add.
  - A counter add of 0 is not a recording. observability §11.2 does not fix whether an implementation makes one,
    so a complete list cannot depend on it.
  - §6.9's capture records each measurement individually, as a recording hook sees it, so an aggregating reader's
    merge of two identical recordings cannot hide a repeat.
  - observability §11.5, which describes the primitive as an in-memory `MetricReader`, is amended to match.

#### 4.7 Wire requests (§5.16)

The wire-request assertions move from §5.15's retrieval heading to a general §5.16. llm-provider uses them in 44
files and retrieval-provider in 42. §5.15 keeps the retrieval specifics. Its sentence that mocks are dispatched
per call in arrival order is corrected: one entry per request, in call order, and in chunk order within a chunked
call.

**`expected_wire_request`** sits beside `expected:` on a case or an llm-provider `calls[]` entry. It reads the
JSON body of each outbound request the case or call sent, parsed from the captured bytes.

- **List form.** It names every request and is complete.
  - Entries follow call order, and chunk order within a chunked call. Each entry is compared with the request
    that carries its slice of inputs or documents, not with the request that arrived in its position. Mock
    responses are dispatched the same way, and a chunked call's stitched `raw` follows chunk order, the order
    retrieval-provider §8 calls request order. The capability specs require one request per chunk but do not order
    their issue.
- **Mapping form.** It is a one-element list, so it asserts that exactly one request was sent.
- **Each body is exact** (§1.3):
  - Member order is not significant, and arrays compare in order.
  - A value the mapping defines as a JSON-encoded string compares after decoding.
  - For `mapping: gemini`, the `model` key is compared with the request URL's `{model}` path segment, as
    llm-provider §8.3.1 places it.
- **A repeated member name fails.** A body with a repeated member name fails every wire assertion on that
  request, so the adapter parses with duplicate detection. A parsed JSON body cannot show a repeated member, and
  several llm-provider and retrieval-provider cases exist to prove a member is sent once.

**`expected_wire_request_includes`** (new) is the named-keys form, for a request whose spec fixes some members
and leaves others to the implementation. The synthetic tool of the Anthropic coercion fallback is an example: its
name and description are the implementation's to choose.
- **Position and count.** It sits where `expected_wire_request` does, and asserts that exactly one request was
  sent.
- **Matching.** It matches the body by the keys it names (§1.3), with `<key>_absent_keys` for absence below the
  top level. The §1.3 positions copied from the case's inputs, such as the schema copy, stay exact inside it.
- **Shared rules.** It takes the exact form's Gemini `model` rule, decoding rule and repeated-member rule.
- **Top-level absence** MUST be written with `expected_wire_request_absent_keys`. An `absent_keys` key at the top
  level of an includes body is `fixture_schema_invalid`.
- **Exclusivity.** Writing both forms at one position, on a case or on one `calls[]` entry, is
  `fixture_schema_invalid`.

**`expected_wire_request_absent_keys`** sits where `expected_wire_request` does. It is a parameter list of
top-level member names, none of which may appear in any request the case or call sent. Beside an exact body it
restates absences, which is harmless.

**`expected_wire_headers`** is a mapping over HTTP headers, matched by named keys:
- Every request must carry each named header exactly once, with the written value.
- Header names compare case-insensitively.

**`expected_wire_request_count`** is the number of requests sent, and `0` asserts that none was. When
`expected_wire_request` or `expected_wire_request_includes` is also written, the count MUST agree with it; a
mismatch is `fixture_schema_invalid`.

**`expected_wire_url`**, now defined only in retrieval-provider fixture 025's header, is the full resolved URL of
every request, compared as an exact string.

#### 4.8 Persistence (§5.6, §5.8)

**`saved_record_assertions`** (§5.8). It sits at the case level, beside `expected:`. It reads the record that
`Checkpointer.load` returns for the first run's invocation id once that run has ended. That is the record a resume
with `from_first_run: true` loads; with a batching backend, it is the last flushed record. It matches by named
keys, and absence is written `saved_record_assertions_absent_keys`.

It and three other directives share one vocabulary of record sub-assertions. The others are
`latest_record_assertions`, `checkpoint_saves` entries and `every_save_assertions`, all in pipeline-utilities'
note. Each sub-assertion reads the like-named pipeline-utilities §10.2 field:

- **`invocation_id` and `correlation_id`** compare as single values, against a literal or a §5.10 token.
- **`schema_version`** compares as a single value, and **`last_saved_at`** matches `<timestamp>`.
- **`state`** is a state snapshot, so it is exact.
- **`completed_positions`** is complete and ordered, and each `NodePosition` matches by named keys.
- **`parent_states`** is a complete, ordered list of state snapshots.
- **`fan_out_progress`** is a mapping, matched by named keys, from a fan-out node's name to `{instance_count,
  instances}`. `instances` is complete and positional by fan-out index. Each instance has these sub-keys:
  - `state` and `state_one_of`;
  - `result`, the value the instance contributes, decoded by the adapter from whatever representation the
    implementation stores (pipeline-utilities §10.11 leaves the representation to the implementation);
  - `result_is_error` and `result_present`;
  - `completed_inner_positions`, complete and ordered.

**`instances_executed_during_resume`** and **`instances_skipped_during_resume`** (§5.8):
- `executed` lists every instance of the case's top-level fan-out that the resumed call dispatched, once each.
- `skipped` lists the instances it did not dispatch because their saved entry was completed and rolled forward.
- The two are complete and unordered, and together they partition the instances. They are not defined for a
  nested fan-out.

**`migrations_run`** (§5.6, since sessions and pipeline-utilities both use it). It lists every application of a
migration function during the load the call performed, repeats included. A migration that raised counts as
applied.
- **Order.** Applications are in order within one entry's chain. Across the record state and its `parent_states`
  entries the list is a multiset, because pipeline-utilities §10.12.2 does not fix the interleaving.

**`saved_session_assertions`** (§5.6). It reads the session record the store holds for the call's session after
the call returns, whichever save wrote it. Its `state` is exact, and `schema_version` compares as a single value.
The undefined `excludes_fields` is retired, since an exact `state` already excludes a field.

**`loaded_session_state`** (§5.6) is exact; `null` asserts that no record existed.

**`checkpointer_assertions.record_type`** (§5.6) is the kind of record the backend holds for the call, as the
adapter determines it: `suspended` or `checkpoint`. It is not the value of an implementation field, because
pipeline-utilities §10.15 leaves the discriminator to the implementation. §5.6's `checkpointer_assertions` entry
drops its `paused_invocation_record_exists` example, whose only use is removed (§6.6).

**`session_store_load_calls`** and **`session_store_save_calls`** (§5.6, new). They count the `load()` and
`save()` calls the in-memory SessionStore received during the call. §6.2's in-memory store is amended to count
them.

**Positions in §5.6.** §5.6 places `first_run_expected_error`, `resume`, `crash_injection` and
`populate_checkpointer_via_runs` "at the invocation level". Every fixture writes them on the case, so §5.6 now
says "at the case level", the term the table in §3 above uses.

#### 4.9 Provider retry (§5.11)

**`llm_spans`** gains what it reads for a bare `complete()` call. The harness runs the call inside a one-node
invocation with an OTel observer and the §6.3 exporter attached, and the directive reads the spans that call
produced.

**`wire_requests`**:
- An `appended_messages` entry written `{role, content}` is exact, since §5.11 calls that form exact to prove
  nothing OA-authored was added.
- An entry written `{role, content_contains: [...]}` asserts the role and that `content` contains each string.
  §5.11 keeps this form for a reask template that interpolates the implementation-defined `error_message`.
- `sampling` names declared `RuntimeConfig` fields, read from the attempt's realized wire request.

#### 4.10 Value matchers (§5.10)

- **`<timestamp>`** is added. It matches any non-null value of the implementation's timestamp type, or a string
  in RFC 3339 form, and asserts presence and form only.
- **The binding-token rules of §1.6** are stated beside the token list, and observability's list gains
  `<path_X>`.
- **Where a token is written.** §5.10's opener says a token goes in an `expected:` mapping. It now says any
  assertion where a literal scalar value would go, since §1.6's binding scope covers every assertion block.
- **The `"*"` wildcard is retired.** Seven llm-provider uses write it with the meaning `<any-string>` already
  has. Fixture 041, where two positions must hold the same unknown name, uses a binding token instead.

#### 4.11 Harness turn outcomes (§5.8)

harness and harness-chat both use these, so they move from the harness note to §5.8:

- **`dispatch_path`** is the inbound dispatch path the harness classified the transmission or turn into (harness
  §3.0 to §3.3), compared as a string: `"3.0"` to `"3.3"`.
- **`error_bucket`** is the harness §7 bucket of an errored turn: `session_terminating`, `retryable_transient` or
  `user_correctable`. These are the tokens every use and harness-chat §5.2 write. The harness note's list
  (`terminating|retryable|...`) is corrected to match.
- **`error_category`** is the errored turn's concrete category, derived as for `expected_error.category`.

#### 4.12 §5.1 clarifications

Four §5.1 sentences change. §4.3 covers the accumulator snapshot, and the other three are corrected here:

- **The middleware-log sentence.** §5.1 says `wrap_with_middleware` markers are "recorded as state-log entries".
  It now points at the §6.7 accumulator that `middleware_log_captured` reads.
- **`flaky_by_index`'s deterministic form.** In the `fail_when_idx` form the failing instance raises an
  uncategorized error. Its optional `category`, which §5.1 already calls "meaningful only for the retrying form",
  applies only to `fail_count_per_idx`. pipeline-utilities 018 and 019 read the same mock that way, and
  `node_exception` stays 018's expected category.
- **`flaky_per_index`'s failures** are uncategorized, which §5.1 did not say, unless a new optional `category` gives
  them one. Uncategorized, they read as the carrier's `node_exception` under the category rule, and the retry
  middleware's default classifier, which retries only transient categories (pipeline-utilities §6.1), does not
  retry them. pipeline-utilities 048 to 052 and 054 expect `node_exception` and read the mock that way. 053 sets
  `category: provider_unavailable`, so its instance's retries exhaust as its narrative says (§6.7).

### 5. Definitions in the directory notes

Each directory's harness note is the fixture-header comment or per-directory README that §3.2 and §3.3 describe.
In practice it is the header comment of the directory's first fixture, except observability's Langfuse note,
which is in fixture 022's header. Where a note is spread across several fixture headers today, it is
consolidated, and the pointers that name the wrong header are corrected, including older ones that name a header
the content has left. Each entry below gets a full definition
in its note, written to the §1 rules.

**observability** (fixture 001's header; fixture 022's header for Langfuse, which observability §8 alone uses):

| Directive | Definition |
|---|---|
| `span_tree_private`, `span_tree_global` | `span_tree` over openarmature's private exporter, or over the exporter the harness installs on the global TracerProvider when `caller_global_otel_active` is set. A span whose parent is on the other provider is a root. |
| `detached_trace_count` | The number of OTel traces, other than the invocation's own, that hold spans from the call. |
| `invocation_id` | The `openarmature.invocation_id` attribute of the call's invocation span. |
| `response_usage` | The usage record of the case's single `complete()` response, matched by named keys (§1.3). It asserts the case made exactly one call. |
| `direct_call_result` | `{value, type, exception}` for a `direct_call:` made outside any invocation. `value` is exact; `type: immutable_mapping` classifies the returned mapping as one the caller cannot mutate; `exception: null` asserts nothing was raised. |
| `determinism_check` | `{compare_runs, ignore_attributes, compare, require_equal}`: the listed facets of two runs' private-exporter spans are equal, with sibling spans compared unordered. A trailing `*` in `ignore_attributes` matches any suffix. |
| `per_invocation` | A container that scopes each inner block to the named invocation of the case. Its inner keys are named claims, settled by the following proposal. |
| capability | `langfuse_token_budget_warning_level`: on a token-budget exceedance the implementation sets the Langfuse generation's level to `WARNING` with a `statusMessage` (observability §5.5.15 and §8.4.3, a SHOULD). |
| default bound model | A `calls_llm` that names no `model`, and every `calls_llm_from_wrapper` call, is bound to `test-model`. A case that asserts another request model MUST name it on `calls_llm`. |
| binding tokens | `<path_X>` (fixture 161), for a call's `structured_output_path`, which its typed event and its span's path attribute must share. |
| streaming inputs | `calls_llm.stream: <bool>` and `mock_llm_stream`, moved from fixture 111's header, since fixtures 113 to 118 and 161 stream too. `mock_llm_stream` holds one entry per `complete()` call, in call order, each the ordered list of chunks the mock yields for that call. The mid-stream failure marker and the `wire_attempts:` form a call under call-level retry takes stay defined in fixture 114's and 116's headers, which the note points at. |
| `langfuse_trace` | The one Langfuse Trace the call produced, from the §6.4 recorder; a case producing more than one uses `langfuse_traces`. Trace fields match by named keys. `input` and `output` are exact. `metadata` matches by named keys, with `metadata_absent`. `observations` lists the top-level observations, complete and unordered. Trace-field absence is written `langfuse_trace_absent_keys`. |
| `langfuse_traces` | Every Trace in the block's scope, the invocation's own and each detached one: complete, unordered, each entry as `langfuse_trace`. |
| observation entries | `type` (`span`, `generation`, `event`, `embedding`, `retriever`, `tool`), `name`, `level`, `statusMessage`, `input`, `output`, `model`, `usage` (with `usage_absent_keys`), `usageDetails` (with `usageDetails_absent_keys`), `modelParameters`, `metadata`, `metadata_absent`, `metadata_truncation`, `input_parses_as_messages`, `prompt_entity_link`, `children` and `absent_keys`. Unset fields read per §1.5. `input_parses_as_messages` parses a string `input` as JSON; the message list is complete and ordered and each message matches by named keys. |

**llm-provider** (fixture 001's header, consolidating the parts in the headers of 005, 033, 044, 059 and 060):

| Directive | Definition |
|---|---|
| positions | A call's assertions sit at `calls[i].expected` for the *i*-th call of a document-level list, at `cases[j].expected` for a case's `call`, or at the document root for a single `call:`. The wire assertions sit beside `expected`, never inside it. |
| `response` | In a call's `expected:`, the `Response` the operation returned, matched by named keys (§1.3). `parsed` and each tool call's `arguments` are exact. `message.tool_calls` and a block-list `message.content` are complete and ordered. `tool_calls: null` matches a missing, null or empty list, because llm-provider §3 treats absent and empty tool calls alike. A content block or tool call asserts absence with `absent_keys`, and a value inside one with `<key>_absent_keys`. |
| `response.raw_check.required_keys` | A parameter list. Each listed key is a top-level key of `raw` whose value equals the mock body's value for that key, by exact deep equality. Defined only for an atomic call: a streamed mock has no single body, and llm-provider §6 fixes only that the assembled `raw` keeps the terminal chunk's usage block verbatim, not where it keeps it. |
| `expected_wire_bytes_identical: {calls: [...]}` | At the document root. The captured request bytes of every listed call are byte-identical (llm-provider §8's intra-implementation stability). A body with a repeated member name fails it. |
| capability | `anthropic_fallback_tool_coercion`: when the provider's capability metadata says the model lacks native structured output, the implementation takes tool-call coercion, the fallback llm-provider §8.2.5.1 says it SHOULD prefer. |
| mock echo | `<request_tool_choice_name>`, written in a mock response body, is replaced by the `tool_choice` name the request carried. It is a mock input, not a matcher, and lets a coercion case's mock answer with the synthetic tool the implementation named. |
| pre-send reject | An empty `mock_provider.responses: []` means the case expects the call to be rejected before sending: any request the implementation sends finds no response and fails the case. |
| binding tokens | `<tool_name_X>`, for a name the implementation chooses that two positions must share. |

**pipeline-utilities** (fixture 001's header):

| Directive | Definition |
|---|---|
| `expected_failure_isolation_event` | Inside `expected:`. Exactly one failure-isolation event (pipeline-utilities §6.3) was dispatched in the call, and it matches. Sub-keys: `event_name`; `wrapped_node_lineage` (`namespace`, `attempt_index`, `fan_out_index`, `branch_name`); `pre_state`, an exact snapshot; `post_state`, exact as a mapping equal to the degraded update; `caught_exception` in §5.8's shape. In `caught_exception.chain` a carrier link matches a run of one or more consecutive carrier links, because §6.3 lets a placement add one or more. |
| `expected_attempt_events` | Inside `expected:`. Every node event the call dispatched, complete and ordered. Entries match by named keys, plus `error_category`, read by §4.1's category rule. |
| `expected_observer_event` | Inside `expected:`. Exactly one completed node event from `node_name`, matched by named keys (§1.3). `error_absent: true` is retired for `expected_observer_event_absent_keys: [error]`. |
| `timing_records` | The records every timing middleware with `capture_to: timing_records` passed to its callback, in callback order: complete and ordered. Entries match by named keys over pipeline-utilities §6.2's `TimingRecord`. |
| `trace_records` | `{<recorder>: [<record>, ...]}`, one record per dispatch, complete and ordered. Record sub-keys: `state_in` (exact), `partial_update_returned`, `pre_seen`, `post_seen`. The note's unused `state_seen_in_post_phase` goes. |
| `checkpoint_saves` | The records the call passed to `Checkpointer.save`, in call order: complete and ordered. Entries carry `after_node` and the record sub-assertions of §4.8. |
| `latest_record_assertions` | The record passed to the call's last save. Under a case's `expected:` that is the run; under `resume.expected:` it is the resumed run. Record sub-assertions of §4.8, matched by named keys (§1.3). |
| `every_save_assertions` | Case level, beside `expected:`. Applies the record sub-assertions to every record passed to a save in the case, and fails if none was. |
| `nodes_executed_during_resume` | Under a `resume:` block's `expected:`. Function nodes at any depth whose execution the resumed call began, in order, with retries collapsed: complete and ordered. |
| `nodes_skipped_during_resume` | Under a `resume:` block's `expected:`. Function nodes in the loaded record's `completed_positions` that the resumed call did not execute: complete and unordered. |
| `successful_attempt_index_during_resume` | Under a `resume:` block's `expected:`. The `attempt_index` of the completed event that carries `post_state` for the case's single retried node, in the resumed call. |
| `concurrency_invariant.max_in_flight` | An upper bound: at no point were more than this many of the fan-out's instances in flight. |
| `raises` with `error_category` | In a node's `raises:` mock, a sibling `error_category: <category>` gives the raised error that category. Without it the error is uncategorized, as §5.1 defines `raises:`. |
| `flaky_call_count` | Inside `expected:`, moved out of `expected_error`. The number of times the case's single flaky node body was invoked in the call, counting every fan-out instance and every attempt. |
| `expected_error.fan_out_category`, `expected_error.transient` | The fan-out category the raised error carries (pipeline-utilities §9.1), and whether §6.1's default classifier classifies the error as transient. |
| `on_caught_calls` | New. Every invocation of the failure-isolation `on_caught` callback in the call: complete and ordered, with entries `{message}`. It replaces fixture 062's undefined write of callback results into state. |
| `on_caught: record` | New. On a `failure_isolation` middleware entry, the adapter supplies an `on_caught` callback that records the message of each exception it receives, for `on_caught_calls`, and writes nothing to state. |
| `abort_after_instance` | A mock input that fixtures 052 and 056 use, defined here for the first time. On a `fan_out:` node, a simulated crash: after the instance with that index completes and its save fires, the fan-out node raises an uncategorized error, which surfaces as `node_exception` from the fan-out node. |
| binding tokens | `<corr_id_X>` and `<invocation_id_X>`. |

`expected_chain_ambiguity_error`, defined in fixture 047's header, moves into this note unchanged, with its
position stated: at the case level beside `expected:`, or inside `resume:`.

**harness** (fixture 001's header):

| Directive | Definition |
|---|---|
| `invocation_id` | New. The invocation id of the transmission's `invoke()` outcome, usually a binding token that later transmissions share. |
| `invoke_args` | The arguments the harness passed on its `invoke()` call for the transmission, matched by named keys (§1.3) over argument names, with `invoke_args_absent_keys`. |
| `outbound_shape` | The class of outbound the harness emitted to the synthetic transport: `completion_response`, `error_response` or `suspended_acknowledgment`. |
| `outbound_payload_includes` | The outbound's payload, matched by named keys (§1.3) over the synthetic transport's payload keys: `value`, `category`, `bucket` and `diagnostic_message`. harness §7 leaves an outbound's shape to each transport, and this note fixes the shape for the synthetic transport. |
| `resolved_to_invocation_id` | The invocation id the signal coordinator resolved the arrival to (usually a binding token). |
| input placeholder | `<from <transmission> suspended outcome>`, written in a transmission's input, is replaced before the transmission is sent by the invocation id of the named earlier transmission's suspended outcome. |
| binding tokens | `<invocation_id_X>`, for an id a later transmission refers back to. |

**harness-chat** (fixture 001's header):

| Directive | Definition |
|---|---|
| `final_state` | The post-turn session's saved state: `ChatTurnOutcome.final_state` is optional (harness-chat §5.2), so the adapter reads the session. `messages_count` and `messages_history_contains` are retired; a fixture writes the `messages` list. |
| `tool_calls` absence | On a message or reply, `absent_keys: [tool_calls]` also matches an empty list, since llm-provider §3 treats absent and empty tool calls alike. |
| `reply.content_includes` | A parameter list: each string occurs in the reply's text content, case-sensitively. Block content is read as its text blocks joined in order. |
| `expected_listener_callback` | Exactly one callback fired on the named listener for this arrival (harness-chat §8.2), with `outcome` and `replies` (complete and ordered). |
| `signal_descriptor` | As §5.8's `descriptor`: `metadata` exact, `metadata_includes` by named keys. |

**sessions** (fixture 001's header):

| Directive | Definition |
|---|---|
| `entry_state` | New, replacing `loaded_invoke_state_for_scratch`. The invoke state after the session load and projection merge, before the first node runs. Exact. |
| `store_after` | Reshaped to `{<session_id>: null \| {state, schema_version}}`: what the store's `load()` returns for each session after the call ends. `null` asserts there is no record. `state` is exact over the projection's fields. |
| `inner_pre_state` | A subgraph's state at entry, after input projection. Exact. |
| `instance_pre_states` | Each fan-out instance's state at entry, ordered by fan-out index. Complete; each entry exact. |

**prompt-management** (fixture 001's header):

| Directive | Definition |
|---|---|
| `prompt`, `prompt_result` | In a call's `expected:`. The `Prompt` or `PromptResult` the call returned, matched by named keys (§1.3). `template` compares as its source text. `messages` is complete and ordered. Absence is written `prompt_absent_keys` or `prompt_result_absent_keys`. |
| capture-label assertions | `expected.<label>` asserts on the value the call carrying `capture_as: <label>` returned, matched by named keys (§1.3), with `<label>_absent_keys`. |
| `result_equivalence` | `{of, fields_must_match, fields_may_differ}`: each field in `fields_must_match` is equal, deeply, across the captured results. Fields in `fields_may_differ` are not compared. |
| `prompt_group` | `{of, group_name, member_names}`: `member_names` is complete and ordered. `member_count` is retired as redundant. |
| `rendered_hash_equal`, `rendered_hash_different` | Pairs of capture labels whose `rendered_hash` values are equal, or differ. |
| `backend_call_counts` | `{<backend>: <n>}`, in a call's `expected:`: the `fetch()` calls each mock backend received during the call. `secondary_backend_call_count` folds into it. |
| `expected_shared_prefix`, `expected_message_equal` | Case-level, beside `expected:`. The `between` results' message at an index starts with `prefix`, byte for byte; or the messages at the listed indices are equal across the results. |

**suspension** (fixture 001's header) gains one capability: `session_save_at_suspend`, under which a session
bound to the invocation saves at suspend time (suspension §8.6, a SHOULD).

**retrieval-provider** and **graph-engine** need no new note entries. Their assertions are all general and
defined in §5 by this proposal, and graph-engine fixture 012's sidecar description of the observer format moves
into §5.8.

### 6. Fixture changes

A conforming implementation would fail, or a fixture would assert less than it claims, in the places below once
the rules apply. Each change is listed with the rule that drives it.

#### 6.1 Derived keys removed from state assertions (§4.2)

- **retrieval-provider, 52 cases in 29 fixtures**, carry `vectors_length`, `inner_vector_lengths_all_equal` or
  `results_length` inside a stored response record.
  - The fixtures are 001, 013, 017, 020, 023, 024, 025, 026, 027, 032, 033, 035, 037, 038, 039, 040, 042, 043,
    044, 046, 047, 048, 049, 051, 052, 053, 054, 055 and 056. The keys are removed.
  - In 26 cases the derived key stood in for the data, so the case writes `vectors` instead (`results` in 048),
    taken from its mock: 001, 013 (three cases), 020 (three), 026 (two), 027 (two), 033 (five), 048, 051, 052,
    054 (three), 055 (two) and 056 (two).
  - `dimensions`, a real field that MUST equal each vector's length, already carries the claim
    `inner_vector_lengths_all_equal` stood for.
- **pipeline-utilities 052** replaces `errors_list_length` with the `errors` list, written as one `{}` entry. It
  declares `errors` as a bare `list` in place of the `error_entry` type it names but never defines (§1.3).
- **harness-chat 001 to 004** replace `messages_count` and `messages_history_contains` with the `messages` list,
  since §5 governs a note on conflict and `final_state` names only state fields.

#### 6.2 Absence written explicitly (§1.3, §1.4)

| Fixture | Change |
|---|---|
| observability 140, 142 | `usageDetails_absent_keys`: `[input]` in 140, `[input, searchUnits]` in 142. Each wrote `usageDetails: {}` to mean "no keys". |
| observability 024 | `prompt_entity_link_absent: true` becomes `absent_keys: [prompt_entity_link]`. |
| observability 148 | `usage_absent_keys: [input]`. It relied on an exact `usage` map. |
| observability 062 | `fields_absent_keys` and its comment removed. The exact `request_params` already asserts the absence. |
| prompt-management 004 | `rendered_hash: "<any-string>"` replaces `rendered_hash_present` and `rendered_hash_non_empty_string`. |
| prompt-management 014, 016 | The `<field>_absent: true` flags become `rendered_absent_keys` and `prompt_absent_keys`. |
| prompt-management 037 | `token_budget_absent_keys: [unknown]`, its whole subject. |
| sessions 004 | `excludes_fields` retired; the stored `state` is exact over the projection's fields, which already excludes the scratch field. |
| graph-engine 012, 014, 015, 018 | `parent_states: []` written where entries leave it out. Their sidecars documented an omission as "empty", which no longer asserts anything. |
| graph-engine 014, 020 | `absent_keys: [post_state]` on each failed node's completed entry. In 014, also `absent_keys: [error]` on the successful node's completed entry, which its sidecar claims. |
| pipeline-utilities 015 | `absent_keys` on the event entries its sidecar says lack `post_state` or `error`, as graph-engine 014 and 020 get. |
| llm-provider 052, 059 | `absent_keys: [signature]` on the thinking blocks whose sidecars say they carry none. |
| pipeline-utilities 006 | `error_absent: true` becomes `expected_observer_event_absent_keys: [error]`. |
| harness 001, 002, 011 | The `invoke_args` flags are re-expressed. 001 uses `session_id: "<any-string>"`. 002 drops `session_id_caller_supplied`, since the literal id already proves the threading. 011 uses `invoke_args_absent_keys: [session_id]`. |
| sessions 012 | The undefined `attributes_absent` on a log entry becomes `log_records_absent`. A second entry, with the attribute written `""`, keeps the old check's reach: `<any-string>` matches only a non-empty value. |

#### 6.3 Lists that did not name every item (§1.2)

| Fixture | Change |
|---|---|
| observability 033 | Its detached fan-out case lists all four Langfuse traces, one per instance plus the parent, and drops `detached_trace_count`. |
| observability 058 | Its second case adds the `after` node span its graph runs, which fixture 008, the case it mirrors, lists. It also links the detached trace's token, which otherwise occurs once and asserts only presence. |
| observability 126, 127, 128, 131 | Each `metrics` list gains the token-usage and duration recordings its case makes, matching fixture 088's success recordings, and fixture 125's failure recordings for 131's first case. 131's second case gains a complete `metrics` list: the failed attempt's one duration recording. 128's and 131's notes that a `metrics` list cannot express absence are corrected. |
| observability 119 | The attempt-0 span entry drops `children`. Whether a branch cancelled under `fail_fast` before it ran dispatches `started` is unsettled (*Open questions*), so the child set is not fixed. That also drops the checks on the attempt-0 vector span, which only the child set reached. |
| observability 029, 039 (three cases), 044, 054 | Declare the `products` state field their initial state supplies, and name it wherever the case writes `final_state`. 039's third case also declares `products` in its `wrapped_fan_out` subgraph and maps it in with `inputs: {products: products}`, since graph-engine §2 projects nothing into a subgraph by default. Its `wrap` node is written in §5.4's `subgraph:` form, and its `result` field becomes a `list<dict>`, the type of the `picks` list mapped out to it, since graph-engine §2 says an implementation SHOULD check mapped field types at compile time. Its sidecar's `subgraph_call` description is replaced to match. |
| observability 088 | Gains a case, `retried_call_records_each_attempt`, whose call fails twice with `provider_unavailable` under call-level retry before its third attempt succeeds. observability §11.2 records the duration once per attempt, so the complete `metrics` list holds two identical failed-attempt recordings, which a capture that merges a repeat fails (§6.9). Its header and sidecar say the duration records once per attempt. |
| graph-engine 020 | Declares `target_node_name`, which its first case's `pre_state` asserts but its schema does not declare. |

#### 6.4 Raised errors (§4.1)

These cases raise a categorized error from a node and expected `node_exception`. Under §4.1's category rule they
now expect the error's own category. Where a case also asserts `message`, that message is already the same
error's, so the two now come from the same link.

| Fixture | Expected category |
|---|---|
| observability 007 | `provider_rate_limit` |
| pipeline-utilities 008 | `provider_rate_limit` |
| pipeline-utilities 009 | `provider_authentication` |
| pipeline-utilities 013 | `provider_rate_limit` |
| pipeline-utilities 016 (`state_blocks_retry`) | `provider_invalid_request` |
| pipeline-utilities 021 | `provider_rate_limit` |
| pipeline-utilities 027 | `provider_rate_limit` (`first_run_expected_error`) |
| pipeline-utilities 060 (second case, renamed `predicate_does_not_match_propagates_raised_error`, since its old name claimed a `node_exception` outcome) | `provider_invalid_request` |
| pipeline-utilities 072 | `provider_unavailable` |

The headers, comments and sidecars of all nine that describe the expected category as `node_exception` are corrected
with them.

- **Position.** graph-engine 014 and pipeline-utilities 033 move `expected_error` beside `expected:`. 033's
  `recoverable_state` moves inside it, and its `branch_name` moves under `carries`.
- **Sub-keys.**
  - graph-engine 009 moves `execution_order` from `expected_error` to `expected:`.
  - pipeline-utilities 009 and 016 move `flaky_call_count` the same way.
  - pipeline-utilities 046 and sessions 013 replace `cause.exception_type: KeyError`, a host-language class name,
    with `cause: {raised_by_mock: <mock>}`. Their migration mock, `raises_keyerror`, is renamed
    `raises_during_migration` for the same reason.
- **Undefined error fields.** llm-provider 057 and 058 drop `raises.message`, which llm-provider §7 does not
  define for a provider error. llm-provider 004 drops `raises.retry_after_seconds`, which its own comment made
  optional.

#### 6.5 Assertions on behavior the spec does not require (§2)

A case whose subject is a SHOULD is split, and the assertions that depend on it move to a case gated on a
capability. Where the spec fixes what the case's inputs produce without the capability, every assertion that holds
either way is also made by an ungated case or by a case gated on the capability's other value (§2).

| Fixture | Change |
|---|---|
| llm-provider 021, 026 | Split. A case gated on `llm_strict_native_schema` keeps the exact body with `strict: true`. Each ungated case asserts the native `response_format` with `expected_wire_request_includes`, its schema copy exact and `strict` left out, and keeps the response, `model`, `messages` and a `name` of `"<any-string>"`. |
| llm-provider 027 | Split into two cases on the same inputs. The fallback case is gated on `llm_prompt_augmentation_fallback`, and its header's "MUST fall back" becomes SHOULD. Its call asserts `model` with `expected_wire_request_includes` and the missing `response_format` with `expected_wire_request_absent_keys: [response_format]`. It leaves the messages unasserted, since §8.1.5.1 lets the directive be appended or merged into an existing system message. Without the fallback, §8.1.5's native request is the default and the mock's response is the same, so an ungated case asserts what holds either way: the request's `model`, the response, its parsed value, and that the caller's messages are unmodified. |
| llm-provider 051 | The fallback directive's placement is left open the same way: `expected_wire_request_includes` asserts the native structured-output fields absent. |
| llm-provider 041 | Gated on `anthropic_fallback_tool_coercion`. `expected_wire_request_includes` asserts the synthetic tool's input schema, exact, and the forcing `tool_choice`, with a `<tool_name_X>` token tying the two names. `expected_wire_request_absent_keys: [output_config]` asserts that the native field is missing. The includes body also keeps `model`, `max_tokens` and `messages`, which coercion leaves unchanged. It leaves the description, which §8.2.5.1 does not require, unasserted. Its mock answers through `<request_tool_choice_name>`. Falling back at all is required, so a second case on the same model, gated on the capability's `false` value, asserts what holds without coercion: `model` and `max_tokens` with `expected_wire_request_includes`, `expected_wire_request_absent_keys: [output_config, tools, tool_choice]`, the parsed text answer, and the `caller_messages_unmodified` claim 027's cases carry, since §8.2.5.1 requires the caller's messages to be left unchanged. That path is prompt augmentation, which may put its directive in the system field or the messages, so neither is asserted. |
| llm-provider 059 (three cases), 071 | `raw_check` removed from streamed calls. 071's claim that the terminal usage block survives verbatim stays with its named claim, which the following proposal settles. |
| observability 161 | The eight cases that expect the `schema_not_honored` record (1, 3, 12, 13, 14, 15, 18 and 19) are gated on `llm_strict_native_schema: true`. Each gains a twin gated on `false`, appended as cases 20 to 27. A twin keeps its case's other assertions, and asserts the `native_unenforced` path and no record, which observability §5.5.7 forbids off the native path. The eight native cases that expect no record (2, 4, 5, 6, 7, 9, 16 and 17) hold on either path, so they stay ungated. Each asserts the event's `structured_output_path` and the span's path attribute with one shared `<path_X>` token, since either value can be right but the two must agree. `prompt_augmentation_path_absent` is gated on `llm_prompt_augmentation_fallback` and drops its `input_messages` assertion, whose directive position §8.1.5.1 leaves open. An ungated companion on the same inputs, appended as case 28, asserts what holds without the fallback too: the `structured_output_invalid` error, its category on the span and the failed event, the event's `finish_reason`, and the path through a shared `<path_X>` token. Whether the record is emitted there depends on `llm_strict_native_schema`, so it stays unasserted. |
| observability 022, 031, 032, 033, 134, 136 | The trace name, whose default observability §8.6 only RECOMMENDS, becomes `"<any-string>"`. |
| observability 130 | Split. A case gated on `langfuse_token_budget_warning_level` asserts the `WARNING` level and a `statusMessage` of `"<any-string>"`, since no matcher can check that the message names the exceeded bound and §8.4.3 gives its text only as an example. The MUST token-budget metadata stays ungated. |
| observability 039 | Its third case sets `concurrency: 1`, so the last writer it asserts is fixed. |
| observability 073 | Its third case drops `error_type: null`, which accepts only one of the two sourcing styles graph-engine §6 allows, and its description is reworded. Its `error_category` and `expected_error` assertions stand. |
| observability 050, 111, 112, 113, 114, 116, 117 (both cases), 118 (both cases) | `calls_llm` names `model: gpt-test`, the request model each case asserts. The default bound model, `test-model`, is now written in observability's note. |
| harness 008, 009, 010 | `outbound_payload_includes` drops `intervention_required`, which harness §7.1 makes a SHOULD, and `retry_safe` and `user_action_required`, which no section requires. The invariants that restate those flags go with them: 008's `outbound_marked_intervention_required`, 009's `outbound_marked_retry_safe` and 010's `outbound_marks_user_action_required`. The synthetic transport is the adapter's, so a flag on it would test the adapter rather than the implementation. 010's `diagnostic_message` becomes `"<any-string>"`, since harness §7.3 does not fix what the diagnostic information says. The other named claims, such as 008's `harness_auto_retried: false`, stay until the following proposal settles them. |
| harness-chat 007, 008 | `content_matches_template` removed, and with these its only uses, the note's definition goes too. harness-chat §10.1 and §10.2 let the text be customized. |
| harness-chat 007 to 010 | `error_category` removed. harness-chat §5.2 makes it optional. |
| suspension 012 | Split. A case gated on `session_save_at_suspend` asserts the suspend-time save and carries the `session_saves_at_suspend_time` claim; the resume-side assertions stay ungated. |
| pipeline-utilities 019, 034 | Each collect-mode errors-field entry is written `{}`, and the field is declared a bare `list` in place of 019's `list<dict<string,string>>` and 034's `list<dict>` (§1.3). The list still asserts how many entries there are. |
| pipeline-utilities 026 | The `schema_version` assertion and its sidecar claim removed. With no declared version the record holds an implementation-defined sentinel, typically `""`, which `<any-string>` rejects. Its header, case description and sidecar no longer claim every §10.2 required field. |
| suspension 007, 009 | The `collect_mode_suspend_rejected_at_runtime` and `collect_mode_parallel_branches_suspend_rejected_at_runtime` claims are removed. An implementation that follows suspension §9's SHOULD and rejects at compile time satisfies `outcome: errored` (§4.1) but fails them, and the outcome with its category already asserts the MUST. |
| retrieval-provider 056 | Both cases stop asserting the input. With no prompt map, retrieval-provider §8.1 lets the mapping prepend the client-side prefix (a MAY), so the first case asserts `prompt_name: "passage"` with `expected_wire_request_includes`, the second keeps only its absent keys and count, and the `client_side_prefix_applied_to_input` claim goes. The extras `prompt_name` rides untouched either way. |

#### 6.6 Re-expressed in defined vocabulary (§4, §5)

| Fixture | Change |
|---|---|
| llm-provider 033, 034, 035, 040, 042, 044, 045, 046, 050, 052, 055 (two), 070 | The response `content` is written as a text-block list, as llm-provider §8.2.2 and §8.3.2 map text. §3.1.1's string equivalence covers user messages only. |
| llm-provider 024 | `provider_call_count` becomes `expected_wire_request_count`. |
| llm-provider 029, 032 (two cases), 036 | The absence claims in `expected_wire_request_checks` become `expected_wire_request_absent_keys`. 027's checks are covered by its change in §6.5, and its claim that the directive references the schema, a SHOULD, is removed. |
| llm-provider 021, 026 | `"*"` becomes `"<any-string>"` in the gated exact bodies. |
| observability 009 | `invocation_count: 2`, which restates the case's two invocations, is removed. |
| observability 040, 041, 042 | `llm_span_attributes` and `llm_span_attributes_absent` become an `llm_spans` entry. |
| observability 053, 054, 055 | `does_not_contain_event_of_type` and `contains_exactly_n_events_of_type` become `event_count`. |
| observability 114 | Its count entry for `LlmTokenFailedEvent`, which §5.5 no longer lists, is removed. |
| observability 008 | `parent_trace` becomes `span_tree`. |
| pipeline-utilities 063 | Its node's undefined `raises: {message, exception_kind: ValueError}` becomes conformance-adapter §5.1's string form, `raises: "bad input"`, which raises the same uncategorized error. |
| observability 094 | Its mock tool's `error_type`, which nothing asserts, becomes the neutral `MockToolError` in place of a host-language class name. |
| observability 010 | `trace_id` and `span_id` move from a log entry's `attributes` to the entry. |
| suspension 011 | `otel_spans` becomes `span_tree`, and its `behavior: otel` observer entry is removed (§4.5). |
| suspension 013 | `paused_invocation_record_exists`, which `record_type: suspended` already asserts, is removed. |
| harness 003, 007 | The suspending transmission asserts `invocation_id: "<invocation_id_paused>"`, and the later assertion positions use the same token. In 003 the resume transmission's input names its source as `<from tx_initial_suspends suspended outcome>`. 007's input carries only a `signal_id` and is unchanged, since its subject is that the coordinator resolves the paused invocation from it. |
| sessions 001, 004 | Invocation-level assertions move into an `expected:` block. `expected_final_state` becomes `final_state`, and `loaded_invoke_state_for_scratch` becomes `entry_state`. |
| sessions 005, 006, 008 | `store_after` takes its reshaped form. |
| pipeline-utilities 011 | Declares its observer and keys `observer_events` by it. |
| pipeline-utilities 062 | Asserts the callback with `on_caught_calls`, and writes `final_state` as the state the graph produces. Its `on_caught` input becomes `on_caught: record`, and the side-channel state fields go. |
| graph-engine 014, pipeline-utilities 011 and 015 | An event's `error` is written `{category: <id>}`, as graph-engine 020 already writes it. |
| prompt-management 008, 011 | `secondary_backend_call_count` folds into `backend_call_counts`, and `member_count` and `member_order_preserved`, which `member_names` already asserts, are removed. |

#### 6.7 Claims with no assertion behind them (§1.8)

Where the spec requires the claimed behavior, an assertion is added. Otherwise the claim is removed.

- **observability, additions:**
  - 015: `source_absent_keys: [media_type]` on the redacted image source.
  - 018: `gen_ai.request.repetition_penalty` added to `attributes_absent`.
  - 020: `openarmature.llm.system` added to `attributes_absent`.
  - 027: `langfuse_trace_absent_keys: [userId, sessionId]`; the stale sidecar is refreshed.
  - 029, 030: trace `metadata_absent`.
  - 031, 032, 136: observation `metadata_absent`, per each sidecar's failure list.
  - 137, 138: the response-derived metadata a failure leaves unset is asserted absent: `openarmature_dimensions`
    and `openarmature_response_id` in 137, `openarmature_result_count` and `openarmature_response_id` in 138.
  - 033: `detached_from_invocation_id` asserted against a literal caller id.
  - 039: `metadata_absent: [note]` on the shared parents.
  - 156: `level: DEFAULT` and `statusMessage: null`.
- **observability, removals:** 032's sidecar claim that `compute` carries no `subgraph_name`. No section forbids
  the attribute on a node span.
- **llm-provider:**
  - 002: the wire `tool_call_id` its comment says is checked is now asserted.
  - 056: attempt 1's usage attributes are asserted.
- **graph-engine:**
  - 014: the `recoverable_state` its sidecar describes is asserted.
  - 024: its sidecar's cross-invocation leak claim can no longer fail under the per-call scope, which leaves the
    first call's late events out by construction. The sidecar now says only that the
    `second_invocation_drain_independent_of_first` named claim states the leak check, and the following proposal
    settles that claim.
  - 031: the same, for its claim that one call's events stay out of another call's bucket.
- **pipeline-utilities:**
  - 053's claim that an instance exhausts its retries had nothing behind it, since its mock's failures were
    uncategorized and never retried. The mock now raises `provider_unavailable` through `flaky_per_index`'s new
    `category` (§4.12), so the attempts exhaust, and `first_run_expected_error.category` becomes
    `provider_unavailable`. The failing instance moves from index 1 to the last, index 2, so no sibling can start
    while it fails, and `first_run_expected: {flaky_call_count: 5}` asserts the retries. The saved record, the
    resume's instance lists and the `instance_2_*` named claims follow. The instance retry is written in the note's
    `type: retry` entry form with a zero deterministic backoff, and the sidecar drops its claim about §9.7's retry
    wrapping, which no key asserts.
  - 005's claim that the original exception is kept as the cause is removed. No key asserts it, and graph-engine §4
    does not require it of a node raise.
  - 060's sidecar claims about the predicate's single-argument signature and its default are removed. No case
    checks the signature, and fixture 063 covers the default.
- **harness-chat:** 003 gains `absent_keys: [tool_calls]` on its last reply.
- **prompt-management:**
  - 014 gains a fetch asserting `prompt_absent_keys: [sampling]`, which its sidecar claims and prompt-management §3
    requires.
  - 024's sidecar drops a claim about `detail` that no form can assert.

#### 6.8 Comments and sidecars that contradict the rules

These are corrected with no change to any assertion:

- **llm-provider:**
  - the "presence only" `raw_check` comments in 005, 008, 068, 069 and 070 and in the 068 to 070 sidecars;
  - 009's comment allowing a string in place of an array;
  - the sidecars and headers of the cases §6.5 rewrites: 021's and 026's listing of `strict: true` for the
    ungated case, 027's pass and fail conditions for the system directive, 041's title and intro, which named
    only coercion, its `"*"` description checks and its claim that coercion is required, and 051's
    `systemInstruction` and `"*"` explanation;
  - the older pointers in 072 to 081 that name the headers of 013, 037, 051, 060 and 074 for content now in 001's
    note, in conformance-adapter §5.16, or in 038's header;
  - 006's sidecar, which calls the unset usage fields "explicit null" and rules out a missing one, where §1.5
    reads null as null or missing.
- **observability:**
  - 012's sidecar, which calls `attributes` exact;
  - 066's sidecar, which rejects an additional field;
  - the comments in 129 and 145 that a `metrics` list cannot express absence;
  - the comments in 140, 142 and 148, and in prompt-management 037, that describe exact map matching;
  - 130's header, case description and sidecar, which say `statusMessage` MUST name the exceeded bound;
  - 161's header, which says every request carries `strict: true`, and the `prompt_augmentation_path_absent`
    description;
  - 161's sidecar: its case table and failure list, which the new cases and the shared path token change; the
    line on case 8's `input_messages`; and the claim that fixture 027 asserts the directive references the schema;
  - 161's cases 10 and 11, whose descriptions say the path is "present and null" where §1.5 reads a written null
    as null or missing;
  - 111's header and sidecar, whose streaming-input definitions move to 001's note (§5), the headers of 112 to
    115, 117 and 118, which pointed at 111's, and 161's header and sidecar, which called 111's header a harness
    note.
- **pipeline-utilities:**
  - the comments allowing an assertion to be skipped: the YAML comments in 018 and 020 and the sidecars of 007,
    016 and 021;
  - 019's comment and sidecar, which describe the error entry's index and category;
  - 034's sidecar, which requires the entry's `branch_name` and category "at minimum", where §11.1 says SHOULD;
  - 022's sidecar, now an upper bound;
  - 024's header sentence that cites a retired fixture, removed whole, since it also contradicts §10.3's saves at
    fan-out instance internal nodes;
  - 068's header, on the carrier count;
  - the 011 and 015 sidecars, which count three events where the YAML lists six;
  - 011's header, which put `run_count` in its `expected` block and claimed an equality check between runs,
    where §5.7 checks each run against `expected:`;
  - 060's sidecar, which listed one case under a name the YAML does not use.
- **graph-engine:**
  - the event counts in the 012, 013, 014, 015 and 016 sidecars;
  - 018's sidecar: its registration-time MUST for an unknown phase string, which graph-engine §6 does not state, is
    removed, and its empty-`phases` lines say SHOULD, as §6 does;
  - 012's sidecar paragraph on draining before assertions, which §8.4 now states, and 013's pointer to 012's format
    description, now §5.5 and §5.8;
  - the comments and sidecars of 028 and 031, which describe the accumulator's buckets as keyed by
    `invocation_id`.
- **retrieval-provider:**
  - the "arrival order" comments in 014, 015, 037, 038, 042 and 043, which now read chunk order;
  - the same comments in 001 and 006, which now read "one request, in call order, and chunk order within a
    chunked call";
  - the wire-assertion definitions in the headers of 013, 014, 015 and 018, now pointers to §5.16;
  - the other headers that name another fixture's header for the wire-request assertions, which now point at
    §5.16, including six that say those are "defined in" 013, 014, 015, 018, 020 or 023, and the headers of 022,
    031, 036, 044, 045, 046, 047, 048 and 056, which use those assertions without pointing at a definition;
  - every pointer that names a header an item is not in. The item now points at the header that has it, at the
    cases that assert it, or at the conformance-adapter section that defines it (§5.5, §5.8 or §5.15). Examples:
    `mapping:`, which 032's header and several others do not define; the TEI `/rerank` shapes, which are in
    014's header, not 013's; and the `raw` assertions of 014, 037 and 039, which are in their cases;
  - the list comparison that 037, 038 and 043 restate, which now points at §5.16;
  - 028's and 031's statements that the Cohere mapping is rerank-only, where §8.4 maps `/v2/embed` too. 031
    also gains a case, `embed_429_maps_to_provider_rate_limit`, since §8.4's *Errors* mapping covers both
    endpoints and no fixture asserted it for embed;
  - 043's claim that 042 sums `billed_units`, where 042's malformed chunk nulls the sum; the notes in 001 and 006
    that promise a forthcoming per-vendor mapping proposal, which §8.1 to §8.4 now are; and the TEI fixture
    ranges in 013's and 027's headers.
- **harness:** the 008, 009 and 010 sidecars' descriptions of the dropped payload flags and invariants, and 010's
  line that the outbound carries the upstream error's diagnostic message.
- **harness-chat:** the field names in the 001 and 007 to 010 sidecars.
- **Host-language names:** the comments and sidecars of pipeline-utilities 005, 046, 063, 064 and 072, sessions 013,
  llm-provider 031 and observability 046 name Python classes and attributes (`ValueError`, `KeyError`,
  `RuntimeError`, `__cause__`, `str(exc)`, `None`) where the text means any error, cause, message or null. They now
  say so in plain words.

## Conformance test impact

No capability behavior changes, apart from one sentence: observability §11.5's metric-capture primitive now
records each measurement individually. What changes is what a fixture means, and therefore what an adapter
checks:

- **Adapters** implement the §8.4 rules and the definitions above. An adapter that read lists as subsets, nested
  mappings as exact, `null` as present-and-null, or `node_exception` as the category of every node failure
  changes accordingly.
- **Implementations** that conform still pass. Several fixtures that a conforming implementation could fail stop
  doing so: the SHOULD pins, the unordered lists, the null rule, and the derived keys. The exceptions are named
  claims that assert SHOULD-level behavior, such as harness 008's claim that the harness did not auto-retry; they
  stay until the following proposal settles named claims. An implementation that emitted extra spans, events,
  requests, wire members or metric recordings, or reported an error's category inconsistently, can now be caught.
- **Fixtures** change as listed in §6, about 300 files. No fixture is added or retired, though some cases are
  split so that only their SHOULD part is gated. observability 161 gains nine cases: eight for the non-strict path
  and an ungated companion to its prompt-augmentation case. llm-provider 041 gains a case for the path without
  tool-call coercion, observability 088 a case whose retried call repeats a metric recording, and
  retrieval-provider 031 a Cohere embed rate-limit case.

The change is MINOR: it changes conformance expectations, which GOVERNANCE.md routes through a proposal, and
pre-1.0 MINOR bumps may carry such changes. conformance-adapter's `Latest` advances, and so does observability's,
for its §11.5 sentence. The other capability specs whose fixtures change do not, since their text is unchanged.

## Alternatives considered

1. **Do nothing.** Rejected. Shipped fixtures already pass or fail depending on how an adapter reads them, and
   the named-claim decision that follows cannot be made without these rules.
2. **Compare nested mappings exactly everywhere.** Rejected. It would make every new optional field on a spec
   record break the fixtures that write the record, against GOVERNANCE.md's MINOR.
3. **Compare every mapping as a subset, with no exact positions.** Rejected. A case could then never assert that
   a value it supplied came back with nothing added: an event's `request_params`, a wire body, a stored state. An
   absence list cannot name every key that might be added.
4. **Order sibling spans by when they opened.** Rejected. It passes today's corpus, but fan-out instances and
   parallel branches run concurrently, so open order can vary between runs, and §7 forbids an adapter from
   imposing an order the spec does not fix.
5. **Scope per-invocation assertions by invocation id.** Rejected. A suspension resume reuses the id, so the
   resumed call's assertions would see the suspended call's events.
6. **Keep §5.5's present-and-null rule.** Rejected. The capability specs make null and missing one state on a
   language record, so the rule fails implementations whose language leaves an unset field missing.
7. **Read every error assertion's category as the engine's carrier category.** Rejected. 87 uses expect the
   category of the error a node raised, pipeline-utilities §6.4 already makes that the shared classification for
   the catch decision and the caught-exception report, and a node failure would otherwise always read
   `node_exception`, which says nothing about what failed. The adopted rule changes 9 fixtures instead of 87.
8. **One proposal per capability.** Rejected. The rules are shared, and every capability's fixtures pass through
   the same rules, so separate proposals would each restate them.

## Open questions

These are the questions the audit found. The capability questions are left to the capability specs, so this
proposal does not change the fixtures that depend on them. The last waits on the following proposal:

1. **Does a plain subgraph node dispatch its own started/completed pair?** graph-engine fixtures 013 and 019 list
   no events for it, while graph-engine §6's "Each node attempt produces a started/completed event pair" and
   observability §4.1 imply it does. The completeness rule makes the answer decide both fixtures.
2. **Which terminal event does an attempt emit when an outer middleware recovers its raise?** pipeline-utilities
   006 and 061 assert opposite answers, so no implementation passes both.
3. **What is a checkpoint position's `namespace`?** pipeline-utilities §10.2 defines it "per graph-engine §6",
   which includes the node's own name. Fixtures 024, 025, 026, 029 and 070 write the path that contains the node.
4. **Does a branch cancelled under `fail_fast` before it ran dispatch `started`?** pipeline-utilities §11.5 is
   silent, and observability 119's span tree depends on it.
5. **What is a detached subgraph span named?** observability 008, 033 and 058 use the subgraph's name. §4.5 names
   a subgraph span after the node in the parent graph.
6. **Is migration-chain ambiguity detected at registration?** sessions §13 makes it a SHOULD and
   pipeline-utilities §10.12.1 a MUST. sessions 009's `raised_at: registration` depends on which governs.
7. **Where does a fan-out's `fan_out_empty` category live?** pipeline-utilities §9.1 says the engine raises a
   `node_exception` "with category `fan_out_empty`" without saying where. pipeline-utilities 023's
   `fan_out_category`, and its `category`, depend on the answer.
8. **How is single-text assistant content sent on the OpenAI wire?** After thinking blocks are stripped,
   llm-provider §8.1.1 does not fix whether it is a string or a block array. llm-provider 043 and 053 pin a
   string.
9. **What does a typed implementation raise for a missing required content field?** llm-provider §3 lets it
   reject at construction with an error that is not `provider_invalid_request`. llm-provider 018 and 020 expect
   the provider category.
10. **Should harness-chat §5.2 require `error_category` on an errored turn?** This proposal removes the
    assertions because the field is optional. Requiring it would restore them.
11. **What category does a failed node's span carry?** observability §4.2 and §5.2 set
    `openarmature.error.category` to "the §4 category identifier", and observability 119 asserts `node_exception`
    where a provider error was raised. observability 007 asserts `provider_rate_limit` in the same situation. No
    implementation passes both.
12. **Must every chunk request be sent when one chunk fails?** retrieval-provider §8's batch chunking says to issue
    one request per chunk, but not whether a failing chunk stops the rest. retrieval-provider 043's second case
    asserts that both requests reach the wire.
13. **Which named claims pin a recommendation, or can no longer fail?** Named claims wait for the following
    proposal, so two kinds ship unchanged. harness 008 asserts that the harness did not auto-retry, under
    `expected:` and as an invariant, though harness §7.1 makes that a SHOULD NOT. graph-engine 024 and 031 keep
    their cross-call isolation checks only as named claims, since the per-call scope keeps one call's events out
    of another call's bucket by construction.
