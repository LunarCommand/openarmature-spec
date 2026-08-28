# 0121: Give openarmature's Mandated Diagnostics a Stable Identity

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-19
- **Accepted:** 2026-08-27
- **Targets:**
  - spec/observability/spec.md **§6 Driving span lifecycle**: the two `WARNING`-level log records §6 mandates
    (the accepted-shared-provider arm and the cannot-establish-binding arm) MUST carry a stable event name
    identifying which diagnostic fired. Today §6 mandates the record's **severity** and nothing else, so
    nothing about it is portably assertable and any WARNING from anywhere satisfies it.
  - spec/observability/spec.md **§7 Log correlation**: define the event-name contract for openarmature's own
    diagnostics. Names live in the `openarmature.` namespace and are carried on the OTel `LogRecord`
    **`EventName`** field, which the Logs Data Model defines as identifying "the class / type of the Event".
    Enumerate the names for the four diagnostics openarmature currently specifies.
  - spec/conformance-adapter/spec.md **§5.5**: add an `event_name` key to `expected.log_records` entries, so a
    fixture can assert *which* diagnostic fired rather than only that something logged at a severity.
  - spec/conformance-adapter/spec.md **§5.5**: add an **`otel_observer: {disable_provider_payload: <bool>}`**
    directive. The OTel observer's payload flag has no defined case-level control, and the `langfuse_client`
    paragraph states the OTel side sits at its §5.5.4 default for exactly the fixture family that needs to
    vary it. Reconcile that paragraph to the new directive.
  - spec/observability/conformance/158-langfuse-payload-leak-fail-closed.yaml: assert `event_name` in all six
    `log_records` blocks, and rewrite case 2 (`singleton_preexists_raises_otel_not_suppressing`) onto the
    `otel_observer` directive.
  - spec/observability/conformance/014-otel-llm-payload-truncation.yaml: migrate its bare top-level
    `disable_provider_payload` to the new directive, so one mechanism configures the OTel observer rather
    than two.
  - docs/compatibility.md: add a matrix row for the **OpenTelemetry Logs data model**, which this proposal
    makes openarmature's normative text depend on for the first time. The matrix has rows for the semantic
    conventions and for the trace/span core spec but none for Logs. Status Stable, verified 2026-08-19
    against the published data-model specification.
- **Related:** 0114 (introduced the mode-(b) isolation rule), 0116 (fail-closed arms and fixture 158), 0117
  and 0118 (extended fixture 158), 0120 (definition-homes rule, which this proposal's new directives satisfy)

## Summary

openarmature mandates two `WARNING` log records in observability §6 but specifies only their severity, so a
conformance fixture can assert that *a* warning happened and never that the *right* one did. Downstream
mutation testing confirmed the gap: silencing the mandated emitter left fixture 158 green because an
unrelated warning satisfied the assertion. This gives openarmature's diagnostics stable event names and lets
fixtures assert them. It also adds the missing `otel_observer` directive, without which one of fixture 158's
cases cannot express what it claims to test.

## Motivation

### A mandated diagnostic with no identity cannot be asserted

§6 requires a `WARNING`-level log record at two points: when the caller has accepted a shared provider, and
when openarmature cannot establish the client's bound provider and suppresses its payload instead. Both are
MUSTs. Neither says anything about the record beyond its severity.

§7's required log-record fields are all cross-cutting: `openarmature.correlation_id`,
`openarmature.session_id`, `openarmature.user.<key>`, `trace_id`, `span_id`. Every record emitted during an
invocation carries them, so none of them distinguishes one diagnostic from another.

The consequence shows up in fixture 158, whose six `log_records` blocks each declare exactly one key:

```yaml
      log_records:
        - level: WARNING
```

An adapter satisfies that by emitting any WARNING, from anywhere, during the case. Downstream mutation
testing demonstrated this concretely: downgrading only the mandated emitter to a lower severity left the
fixture green, because a second, unrelated warning was in flight during the same window. The assertion was
live and checking the wrong record.

The `log_records` directive is not the limitation. It already accepts `body` and `attributes` alongside
`level`, matched as a subset. The limitation is that openarmature specifies nothing stable for a fixture to
match on. A message substring is the obvious candidate and the wrong one: messages are prose, they get
reworded, and pinning them makes every copy-edit a conformance break.

### Precedent, and the shape openarmature already reaches for

The token-budget diagnostic (§5.5.15, §7) is identified by the `openarmature.prompt.*` attributes it carries.
Identity through structured fields rather than message text is already the house pattern; it has simply never
been applied to the §6 diagnostics, which are the ones a fixture is required to assert.

### Fixture 158 case 2 cannot express what it claims

`singleton_preexists_raises_otel_not_suppressing` differs from case 1 by a single case-level key:

```yaml
    disable_provider_payload: false  # OTel side ALSO emits payload
```

That key has no definition in the conformance-adapter spec. Worse, the `langfuse_client` paragraph that
governs this fixture family states the observers' payload settings use "`langfuse_observer:
{disable_provider_payload: <bool>}` for the Langfuse side, and the OTel observer's §5.5.4 default (`True`)
for the OTel side". So the contract covering this fixture says the OTel side sits at its default here, while
the case sets it through an undefined key.

The case's intent is sound and worth preserving. It is a regression guard against the alternative 0116
considered and rejected, in which the raise fired only when a composed OTel observer was suppressing payload.
An implementation still on that rule passes case 1 and fails case 2, and nothing else in the corpus catches
it. But as written the case is contradicted where it is used and ambiguous where it is not, so an adapter is
entitled to ignore the key, and the case then differs from case 1 in nothing an adapter must honor.

## Detailed design

### §7: the event-name contract

The OTel Logs Data Model, which is **Stable**, defines a top-level `LogRecord` field `EventName`: "Name that
identifies the class / type of the Event. This name SHOULD uniquely identify the event structure (both
attributes and body)." That is precisely the affordance missing here, and openarmature's stable-only adoption
policy permits it because the data model **document** carries Stable status. The field is not separately
stability-marked within it, so adoption rests on the document's status rather than a per-field marker.

> **Diagnostic event names.** A log record openarmature emits to signal a condition it specifies MUST carry
> an event name on the OTel `LogRecord` `EventName` field. Event names are in the `openarmature.` namespace,
> are stable identifiers, and MUST NOT be reworded once shipped; the record's human-readable message is free
> to change independently.
>
> The names openarmature currently defines:
>
> | Event name | Emitted when | Obligation |
> |---|---|---|
> | `openarmature.langfuse.shared_provider_accepted` | §6, the caller has accepted a shared provider and openarmature proceeds | MUST |
> | `openarmature.langfuse.payload_suppressed` | §6, openarmature cannot establish the client's bound provider and suppresses every harvested-payload channel | MUST |
> | `openarmature.token_budget.exceeded` | §5.5.15, an active prompt's `token_budget` is exceeded | SHOULD |
> | `openarmature.langfuse.supplied_client_shared_provider` | §6 mode (a), a caller-supplied client is determined to be bound to a shared provider | MAY |
>
> The obligation column restates the obligation on the **record**, which this rule does not change. Where a
> record is emitted, it carries its event name.

Adopting the field is distinct from adopting an upstream **name**: the Event semantic conventions that
prescribe particular event names remain in Development, and openarmature names its own diagnostics in its own
namespace rather than taking any name from them.

**Naming note.** `event_name` also appears in pipeline-utilities §6.3 as a caller-supplied field on the
failure-isolation middleware. These are unrelated: that one is chosen by the caller to label a catch site and
is a caller-attached dimension (observability §8.4), while these are openarmature-emitted identifiers for
conditions the spec mandates. §7 states the distinction so the two are not conflated.

### §6: the two mandated records carry their names

Both MUST sites gain a clause naming the event they emit, cross-referencing §7's table. No new obligation to
emit is created and no existing one is changed; the records were already mandated, and this says which
diagnostic each one is.

### conformance-adapter §5.5: `event_name` on `log_records`

> An `expected.log_records` entry MAY carry **`event_name: <string>`** alongside `level`, `body` and
> `attributes`, asserting the record's OTel `EventName` field equals the given value. Matching remains a
> subset over the fields an entry specifies, and the list remains non-exhaustive.

This is what lets a fixture pin the mandated diagnostic rather than any record at a severity.

### conformance-adapter §5.5: the `otel_observer` directive

> **`otel_observer: {disable_provider_payload: <bool>}`** configures the composed OTel observer's payload
> flag for the case, the OTel-side counterpart of the existing `langfuse_observer` directive. Omitted, the
> OTel observer keeps its §5.5.4 default.
>
> An adapter MUST honor the directive when present. A case that sets it and an adapter that ignores it
> produce the same observable result as a case that does not set it, so silently dropping it makes the case
> vacuous rather than failing.

The `langfuse_client` paragraph's sentence about the OTel side sitting at its §5.5.4 default is amended to
point at this directive, since that sentence is what currently contradicts fixture 158 case 2.

Adding both directives to §5.5 satisfies proposal 0120's definition-homes rule: they are used by more than
one capability's fixtures in prospect and their contracts are general, so §5 is the correct home.

### Fixtures

**158.** All six `log_records` blocks gain `event_name`. Five assert
`openarmature.langfuse.payload_suppressed`, being the cannot-establish arms
(`singleton_preexists_suppresses`, `state_channel_preexists_suppresses`, `hook_preexists_suppresses`, and the
two error-message cases 0118 repointed onto that arm). One asserts
`openarmature.langfuse.shared_provider_accepted`, the opt-out case
(`singleton_preexists_optout_proceeds`). Case 2 is rewritten to set
`otel_observer: {disable_provider_payload: false}` in place of the bare key, so its differentiator is a
directive an adapter is obliged to honor.

**014.** Its bare top-level `disable_provider_payload` becomes `otel_observer: {disable_provider_payload:
false}`. No semantic change; the fixture is OTel-only, so the bare key was unambiguous there. Migrating it
means one mechanism configures the OTel observer rather than two, and leaves no undocumented form behind for
a future fixture to copy.

## Conformance test impact

**The event-name requirement is a new obligation on implementations.** An implementation emitting the two §6
records without an event name becomes non-conforming. That is the point: the records were mandated but
unidentifiable, so the obligation was unassertable.

**Fixture 158's six blocks tighten.** An implementation that emits the right record already passes; one that
satisfies the old assertion with an unrelated warning starts failing, which is the defect being closed.

**Fixture 158 case 2 becomes non-vacuous.** Under the current text an adapter may ignore its differentiator,
making it a duplicate of case 1. After this it exercises the axis its name claims.

**Fixture 014 is a mechanical migration**, no assertion change.

No new fixture. The six existing blocks and the two rewritten cases carry the change, and adding a seventh
case would assert the same rule the tightened blocks already gate.

## Alternatives considered

1. **Do nothing, and record the fixture as deliberate.** Rejected: the assertion reads as working while
   checking the wrong record, which is worse than an absent assertion because it reports coverage that does
   not exist.
2. **Assert a message substring.** Rejected: messages are prose and get reworded, so every copy-edit becomes
   a conformance break, and a substring is not a stable identifier in any sense the spec can hold an
   implementation to.
3. **Carry the identity on an `openarmature.*` log-record attribute** rather than `EventName`. Rejected: the
   Logs Data Model defines a field whose stated purpose is identifying the class of the event, in a document
   carrying Stable status, so introducing a parallel attribute would duplicate a standard mechanism. This was
   the fallback if the data model had turned out to be Development.
4. **Leave fixture 158 case 2 as a documented duplicate of case 1.** Rejected: it guards against a rejected
   alternative that nothing else in the corpus catches, and the guard costs one directive.
5. **Define the `otel_observer` directive without migrating fixture 014.** Rejected: it would leave two ways
   to set the same flag, one of them undocumented, which is the pattern proposal 0120 exists to stop.

## Open questions

1. **Whether the token-budget and mode-(a) names belong in this proposal.** They are included so §7's table
   is the complete set rather than the two fixture 158 happens to assert, but neither is fixture-gated here
   and both keep their existing obligation levels. Naming them now costs nothing and avoids a second pass;
   the alternative is scoping this to the two MUSTs.
2. **Whether `EventName` should also carry openarmature's non-diagnostic records.** This proposal covers
   records signalling a condition openarmature specifies. Whether ordinary framework logging should be
   event-named is a broader question about openarmature's logging surface, left out of scope.
