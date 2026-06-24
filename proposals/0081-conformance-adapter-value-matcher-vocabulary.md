# 0081: Conformance-Adapter Value-Matcher Vocabulary

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-23
- **Accepted:** 2026-06-23
- **Targets:** conformance-adapter/spec.md **§5 Directive vocabulary** — add **§5.10 Value matchers**,
  a normative enumeration of the matcher/placeholder vocabulary fixtures draw on; and update the
  **§3.2** worked-example placeholder list to cite §5.10 as the normative home (the per-directory
  comment stays a navigational example). **No fixture changes** (descriptive of matchers already in
  use).
- **Related:** 0055 (conformance-adapter capability — established §3.2 per-directory harness notes
  and the §5 directive vocabulary this extends), and the observability fixtures that use the tokens
  (`<any-string>` across ~12 fixtures; `non_empty_string` / `harness_parameterized` in 058 / 059 /
  067)
- **Supersedes:**

## Summary

The value-matcher vocabulary every adapter relies on — inline placeholder tokens (`<uuid>`,
`<any-string>`, `<trace_id_X>`), assertion sub-keys (`non_empty_string`, `harness_parameterized`),
and the exact-value-plus-derivation-invariant pattern — is defined only **piecemeal**: the inline
tokens live inside a §3.2 *worked example* framed for the observability suite, and the sub-key
matchers aren't enumerated centrally **anywhere** (they live in fixture prose). This proposal
promotes the vocabulary to a normative **§5.10 Value matchers** enumeration so every adapter
implements **one defined set** rather than re-deriving it per fixture, and it pins
`<any-string>` = **non-empty** normatively.

## Motivation

This is a direct response to a question a reference implementation raised while wiring the
observability conformance fixtures into its harness: *"Is `<any-string>` a blessed matcher token in
the conformance vocabulary, or fixture-local prose? If there is (or should be) a canonical set, I'd
rather implement them uniformly than one-off per fixture. Is there a defined list?"*

The honest answer today is "piecemeal":

- `<uuid>` / `<any-string>` / `<trace_id_X>` are defined only in a §3.2 worked example documenting
  the observability suite's per-directory header comment — framed as an example of per-directory
  specialization, not a normative cross-capability home.
- `non_empty_string` and `harness_parameterized` are used in real fixtures (058 / 059 / 067) but are
  enumerated in **no** central location.

For a vocabulary that is part of the cross-implementation conformance floor — every adapter MUST
interpret these identically or the fixtures don't mean the same thing across implementations — that
is under-specified. Centralizing it gives adapter authors the defined list they asked for and removes
the ambiguity that let one matcher (`<any-string>`) be read as "non-null" rather than the intended
"non-empty."

## Proposed change

Add **§5.10 Value matchers** to the §5 directive vocabulary, enumerating three idioms:

1. **Inline value-tokens** — appear as the expected *scalar value* in an `expected:` mapping:
   - **`<uuid>`** — matches any canonical UUIDv4.
   - **`<any-string>`** — matches any **non-empty** string. The empty string `""` does **not** match.
   - **`<trace_id_X>`** — matches an opaque `trace_id` with **first-occurrence binding**: the token
     binds to the value at first sighting within a case, then every later occurrence of the same
     token MUST equal that bound value (cross-reference within one case).
2. **Assertion sub-keys** — appear as *keys inside a field's assertion mapping* (not as a bare value):
   - **`non_empty_string: true`** — the field is a non-empty string. Semantically identical to
     `<any-string>`; it is the sub-key spelling for contexts where the field's expected value is an
     assertion mapping rather than a bare scalar.
   - **`harness_parameterized: <name>`** — the field equals the harness-injected parameter named
     `<name>` (e.g. the implementation's own `implementation_name`). An **equality check against an
     injected value**, not a wildcard.
3. **Exact-value + named derivation invariant** — an exact expected value derived from inputs by a
   documented rule (e.g. a Langfuse `trace.id` = a UUID's 32-char dashes-stripped hex), paired with a
   named invariant predicate (per §5.9, e.g. `langfuse_trace_id_is_uuid_hex_dashes_stripped`). This
   is **not** a wildcard; it is recorded here as the distinct third idiom so it isn't conflated with
   the matchers above.

**§3.2** — the observability worked-example placeholder list now references §5.10 as the normative
definition; the per-directory header comment remains as a navigational example, consistent with
§3.2's per-directory-specialization model.

## Conformance test impact

**No fixture changes** — §5.10 is descriptive of matchers already in use. The one substantive
clarification with teeth: **`<any-string>` = non-empty is now normative**, so an adapter that treats
it as "non-null" (and accepts the empty string `""`) becomes non-conforming. Adapters already
implement the inline tokens they encounter and the sub-keys in 058 / 059 / 067; §5.10 makes the set
they MUST implement explicit and uniform.

## Versioning

**MINOR bump** (pre-1.0). It extends the conformance-adapter §5 directive vocabulary — consistent
with the capability's §1 framing that "future proposals that introduce new directives extend §5."
Although the content is largely descriptive of existing usage, the normative enumeration plus the
`<any-string>` = non-empty pin are an addition to the public conformance contract, so MINOR (not a
PATCH clarification) is the honest classification.

## Alternatives considered

1. **Leave the tokens in the §3.2 worked example (status quo).** Reject — it is framed as an
   observability-suite example, not a normative cross-capability home, which is exactly why an
   adapter author had to ask whether it is blessed vocabulary.
2. **Ship as a clarification PATCH rather than a proposal.** Viable, since the content is largely
   descriptive — but extending the §5 vocabulary is proposal-shaped per the capability's own framing,
   and the `<any-string>` = non-empty tightening is a (small) change to conformance expectations; a
   proposal gives it a clean, citable record.
3. **Collapse `<any-string>` and `non_empty_string` into one spelling.** Reject — they serve
   different syntactic contexts (an inline scalar value vs. a sub-key within an assertion mapping);
   both are in active use, and removing either churns accepted fixtures for no behavioral gain.
4. **Omit `harness_parameterized`** (it's an equality check, not a wildcard matcher). Reject — it
   co-occurs with the matchers inside the same assertion mappings (058 / 059) and adapters must
   implement it; include it, flagged explicitly as an equality check rather than a wildcard, so the
   distinction is on the record.

## Open questions

None blocking — resolved during drafting:

- **Placement — RESOLVED.** A standalone **§5.10** *Value matchers*, immediately after §5.9
  *Invariant assertions* and before §6 *Harness primitives*. Appending renumbers nothing (§6 and
  later are unaffected).
- **Open vs. closed set — RESOLVED.** **Open** — the enumeration is the current authoritative set,
  not frozen; future proposals extend §5.10 the same way they extend the rest of §5 (per the
  capability's §1 framing).

## Out of scope

- **New matchers not currently in use** — §5.10 documents the existing set, not speculative additions.
- **A fixture-linter that validates matcher syntax** — tooling, per §12 *Out of scope*.
- **Per-directory specialized matchers** — those remain documented in fixture headers per §3.2; §5.10
  is the cross-cutting set every adapter implements.
