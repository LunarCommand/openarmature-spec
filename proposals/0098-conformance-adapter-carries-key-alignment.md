# 0098: Align structured-output `carries` assertion keys with the llm-provider §7 error field names

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-12
- **Targets:** spec/conformance-adapter/spec.md **§5.12 Provider structured-output error assertion** —
  rename the three `carries` assertion keys that do not track the llm-provider §7
  `structured_output_invalid` error field names (`raw_response_content` → `output_content`,
  `failure_description_present` → `error_message_present`, `failure_description_mentions` →
  `error_message_mentions`); state the §5.12 key-naming convention **normatively**, so a future `carries`
  key derives its name from the field it asserts; and correct §5.12's fixture-provenance range, which
  today names the 0095 reask fixtures as **(062–067)** when only **063 / 064** carry a `carries` block.
  Conformance (at Accept): fixtures 022 / 023 (0016) and 063 / 064 (0095) move to the new key names.
- **Related:** 0016 (structured output — fixtures 022 / 023 coined the keys), 0082 (structured-output
  failure diagnostics — named the graph-engine §6 failure-**event** fields, and deliberately kept §7's
  error wording distinct from them), 0095 (adaptive call-level retry — **named the llm-provider §7 error
  fields** `output_content` / `error_message`, which its reask builder consumes by name; fixtures
  063 / 064), and the v0.91.1 clarification that documented §5.12's keys as-is and deferred the rename
  (this proposal is that follow-on)
- **Supersedes:**

## Summary

conformance-adapter §5.12's `carries` block asserts the fields a `structured_output_invalid` error exposes
(llm-provider §7). Three of its six keys don't track the field names they assert:

| `carries` key (today)          | asserts §7 error field   | assertion flavor |
|--------------------------------|--------------------------|------------------|
| `raw_response_content`         | `output_content`         | exact-equality   |
| `failure_description_present`  | `error_message`          | presence         |
| `failure_description_mentions` | `error_message`          | contains         |

This renames them to `output_content`, `error_message_present`, and `error_message_mentions`, and states
normatively the convention the vocabulary then follows in full: **a `carries` key is the §7 error field
name it asserts, plus an optional suffix naming the assertion flavor.**

## Motivation

The keys are older than the names they assert, and they mirror wording the spec has since replaced.

0016's fixtures (022 / 023) coined the keys when llm-provider §7 described the error's exposed fields in
prose — *the raw response content*, *a description of the validation or parse failure* — with no field
names to track. 0082 then named the graph-engine §6 failure-**event** fields and deliberately left §7's
error wording alone, recording the split as an accepted cross-surface naming difference (the error was the
caller-facing view; the event, the completion-shaped observability surface). 0095 reversed that: it
**named the §7 error fields** `output_content` and `error_message`, because its reask builder consumes
them by name. The separation 0082 preserved no longer exists at the source — but the `carries` keys still
mirror the wording that applied when it did.

So the keys now cost a reader a lookup for nothing: a fixture asserting the error's `output_content` field
spells the assertion `raw_response_content`, and one asserting `error_message` spells it
`failure_description_*`. The distinction that *does* matter — exact-equality vs presence vs contains — is
carried by the suffix, not by a different stem.

v0.91.1 documented §5.12's keys as-is and deferred the rename: renaming them changes the directive
vocabulary fixtures declare and adapters parse, which is a conformance-expectation change rather than a
clarification. This is that follow-on.

The alignment also turns an ad-hoc key list into a **derivable rule**. Three of the six keys
(`response_schema_present`, `finish_reason`, `usage`) already name their field; after the rename all six
do, and a future `carries` key's name follows from the field it asserts rather than being coined.

## Proposed change

### conformance-adapter §5.12 — rename the three misaligned keys

- `raw_response_content` → **`output_content`**
- `failure_description_present` → **`error_message_present`**
- `failure_description_mentions` → **`error_message_mentions`**

`response_schema_present`, `finish_reason`, and `usage` are unchanged — they already track their fields.
No assertion semantics change: each renamed key asserts exactly what it asserted before, on the same field,
with the same flavor.

### conformance-adapter §5.12 — state the key-naming convention normatively

A `carries` key **MUST** be named for the llm-provider §7 error field it asserts, plus an optional suffix
naming the assertion flavor:

- a **bare field name** (`output_content`, `finish_reason`, `usage`) — **exact-equality** on that field.
- the **`_present` suffix** (`response_schema_present`, `error_message_present`) — the field is
  **present** (non-null); its value is not asserted.
- the **`_mentions` suffix** (`error_message_mentions`) — the field's value **contains** the given
  substring (used where the exact wording is implementation-defined).

Every §5.12 key then follows the rule, and a new `carries` key **MUST** derive its name from the field it
asserts rather than coining a fresh stem.

### conformance-adapter §5.12 — correct the fixture-provenance range

§5.12 today cites "the 0016 structured-output fixtures (022 / 023) and the 0095 reask fixtures
**(062–067)**" as the established users of these directives. The 0095 range is wrong: only **063** and
**064** carry a `carries` block (062 and 065–067 are success-path fixtures with no raised error to assert).
The citation is corrected to **022 / 023 and 063 / 064** — the same four fixtures this proposal renames.
The v0.91.1 note recording that the keys are documented "as-is, without renaming" and that the rename is
deferred is removed; this proposal resolves it.

## Conformance test impact

**At Accept** (this is a Draft — the spec edits and fixture updates land with the accept PR, not here), the
four fixtures that use the renamed keys move to the new names:

- **022** / **023** — the 0016 structured-output parse-failure and validation-failure fixtures, which
  coined the keys.
- **063** / **064** — the 0095 reask fixtures (budget-exhausted, off-by-default).

No new fixtures and **no changed expectations**: the same fields are asserted the same way, under names
that match them. The other 0095 fixtures (062, 065–067) carry no `carries` block and are untouched — the
same fact the §5.12 range correction above records.

## Versioning

**MINOR bump** (pre-1.0). A rename of the conformance-adapter §5.12 `carries` directive vocabulary.

No behavioral contract changes: llm-provider §7's error fields keep their names and semantics, every
assertion keeps its meaning, and no expectation moves. But the directive surface an adapter parses does
change, so this is a conformance-expectation change, not a clarification (v0.91.1 was the clarification
half — it renamed nothing; this is the half that moves the keys).

**It is a breaking change for an adapter.** One that reads the old key names stops matching the fixtures,
which move to the new names in the same version; the directive vocabulary and the fixture corpus move
together. Pre-1.0, a breaking change of this kind may land in a MINOR bump. Tentative spec version target
deferred to Accept.

## Alternatives considered

1. **Keep the `carries` keys deliberately distinct from the §7 field names.** Reject — the distinction is
   a leftover, not a live position. 0082 *did* deliberately hold the §7 error's wording (*raw response
   content*) apart from the completion-shaped event field it named `output_content`, and recorded that as
   an accepted cross-surface difference. But 0095 then **named the §7 error fields** `output_content` /
   `error_message`, collapsing the separation at its source. The keys are the last thing still mirroring
   the older wording — they preserve a distinction the spec itself no longer draws. The distinction worth
   keeping (exact-equality vs presence vs contains) is carried by the `_present` / `_mentions` suffixes,
   which survive the rename.
2. **Rename only the un-suffixed key (`raw_response_content` → `output_content`).** Reject — partial
   alignment leaves two of six keys requiring the same lookup and yields no derivable convention, which is
   most of the value.
3. **Add the new names as aliases and keep the old ones.** Reject — two vocabularies for one assertion,
   permanently: every adapter carries both, and §5.12 documents a key list twice as long with no rule
   deriving it — precisely the ad-hoc surface this proposal exists to remove. A rename is a one-time cost
   against a small, versioned fixture corpus; an alias set is a standing one.
4. **Ship it as a clarification PATCH.** Reject — it changes the directive vocabulary fixtures declare and
   adapters parse, so it is a conformance-expectation change by definition. v0.91.1 was the clarification
   that *could* ship as a PATCH (it renamed nothing); this half cannot.

## Out of scope

- **`response_schema_present` / `finish_reason` / `usage`** — already track the fields they assert; no
  change.
- **Other directive families.** Scoped to the §5.12 `carries` block; no other conformance-adapter directive
  vocabulary is touched.
- **llm-provider §7 itself.** The error field names (`output_content` / `error_message`) are unchanged —
  this aligns the assertion vocabulary *to* them, not the reverse.
