# 082: Structured Output Reports Every Violation, by Location

Verifies llm-provider §7's *What `error_message` describes* (proposal 0126). A `structured_output_invalid`
error's `error_message` MUST describe every violation the content commits against `response_schema`, each
with its location as a JSON Pointer in RFC 6901's URI fragment form and the constraint that failed, and for a
`type` violation the expected type.

Each case returns content that fails its schema in a known set of ways and asserts `error_message_mentions`
as a list naming every expected violation's location. Rows with a wrong-type failure also assert the expected
type's name, which the rule requires a `type` violation to state. The other §7 exposures (`response_schema`, `output_content`, `finish_reason`, `usage`) are
asserted alongside, as in fixtures 022 and 023.

**Spec sections exercised:**

- llm-provider §7, `structured_output_invalid`: every violation, its location in URI fragment form, and the
  rules for where a violation is located, for `anyOf` / `oneOf` / `allOf`, for a composite whose own
  constraint fails, and for content that is not well-formed JSON.
- llm-provider §5: a `response_schema` that declares no `$schema` is read as JSON Schema draft 2020-12.
  Cases 12 and 13 rely on it, since `dependentRequired` and `prefixItems` are not defined by earlier drafts.
- conformance-adapter §5.12 and §5.13: `error_message_mentions` taking a list.

**Cases:**

1. `flat_object_reports_every_violation`: two missing required properties and one wrong type, at `#/alpha`,
   `#/bravo` and `#/charlie`.
2. `nested_object_reports_both_violations`: a wrong type and a missing property under `#/site/`.
3. `nullable_anyof_resolves_to_the_object_member`: the object member's failure (`#/site/foxtrot`), not a
   composite-level report.
4. `union_of_two_objects_reports_both_members`: both members fail, on `#/site/golf` and `#/site/hotel`.
5. `allof_reports_a_type_mismatched_member`: the referenced member's type failure at `#/site`.
6. `oneof_over_match_reported_at_the_composite`: both members satisfied, one violation at `#/pet`.
7. `unexpected_property_located_at_its_own_pointer`: `#/site/zulu`, not the parent object.
8. `property_name_with_a_space_is_percent_encoded`: `#/first%20name`.
9. `array_elements_reported_by_index`: `#/rows/0/november` and `#/rows/2/november`.
10. `content_that_is_not_json_is_one_violation`: a single violation with no location
    (`error_message_present` only).
11. `union_with_no_type_match_reported_at_the_composite`: no member's type admits the content, so one
    violation at `#/site` naming the members' types.
12. `dependent_required_located_at_the_missing_property`: a property `dependentRequired` makes required, at
    `#/sierra`.
13. `disallowed_array_element_located_at_the_element`: an element `items: false` excludes, at `#/tango/1`.
14. `min_items_located_at_the_array`: a count constraint, at `#/uniform`.
15. `unique_items_located_at_the_array`: a uniqueness constraint, at `#/victor`.

**Why fragment pointers rather than property names.** A composite-node message names only the composite's
location, such as `#/site`, so it cannot contain `#/site/foxtrot`. A message that quotes the schema or echoes
the content contains property names but not instance locations. And a schema location, which validators
write as `/properties/site/properties/delta` or `#/properties/site/properties/delta`, does not contain an
instance location such as `#/site/delta`, provided no property is named like a JSON Schema keyword; the
property names here avoid keyword names and are not substrings of one another.

**What separates the rule from wrong readings.** Case 5 is answered by an empty set under a rule that filters
`allOf` members by type, and case 6 by an empty set under a rule that reports only failing members'
assertions. Case 11 is answered by an empty set under a rule that filters union members by type and then
reports only the survivors' failures. Cases 7, 12 and 13 separate the rule from validators that report an
unexpected property, a `dependentRequired` property or a disallowed element at the enclosing object or array,
and case 8 from an implementation that skips the fragment form's percent-encoding.

**What passes:**

- Every case raises `structured_output_invalid` whose `error_message` contains every listed mention.

**What fails:**

- Reporting only the first violation (cases 1, 2, 4, 9).
- Reporting a union at the composite instead of the failing member (cases 3, 4).
- Reporting nothing for a type-mismatched `allOf` member, a `oneOf` over-match, or a union no member's type
  admits (cases 5, 6, 11).
- Reporting an unexpected property, a `dependentRequired` property or a disallowed element at its parent
  (cases 7, 12, 13).
- Reporting nothing for a count or uniqueness constraint (cases 14, 15).
- Writing locations as property names, schema paths, or plain pointers without `#`.

**Limits.** A mention proves a violation was reported, not that nothing extra was, because the closed flavor
set has no negative form. So four rules are not pinned: that a nullable field's `null` member is omitted
(case 3); that a `oneOf` over-match is reported whatever its other members do, since every member's locations
share the composite's prefix; the wording of a missing property's constraint; and that a type-name mention
comes from the stated constraint, since a message that quotes the schema contains type names anyway. A
root-level location, `#`, cannot be asserted by substring, since every location contains it, and a location
asserted by substring also matches a deeper one under it, so cases 11, 14 and 15 do not pin that the violation
is reported at the composite or array rather than inside it. `not` and `contains` are covered by the rule but
not by a case.
