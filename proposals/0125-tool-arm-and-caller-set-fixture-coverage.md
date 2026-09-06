# 0125: Fixture Coverage for the Tool Arm and the Caller-Set Scope

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-09-06
- **Accepted:**
- **Targets:**
  - spec/observability/conformance/160-langfuse-error-message-truncation.{yaml,md}: add a **Tool** case,
    closing the fourth arm of §8.7's direct-application rule. The fixture gates the Generation, Embedding
    and Retriever arms and leaves Tool ungated, so an implementation that applies the cap in three of the
    four §8.4 failure mappings passes the suite. The four mappings are separate and an implementation can
    wire one and not another, which is the defect this fixture exists to detect.
  - spec/observability/conformance/098-langfuse-tool-observation.{yaml,md}: supply `caller_metadata` and
    assert those keys on the Tool observation, pinning §8.4.2's scope. The row maps each caller-metadata
    entry to `observation.metadata.<key>` on **EVERY** Observation; no fixture asserts it on a Tool
    observation, and 098 supplies no caller metadata at all.
- **Related:** 0119 (made §8.7's Tool arm normative and left it unpinned), 0118 (classified the harvested
  message as payload), 0043 (introduced §8.4.2's caller-set row)

## Summary

Two normative rules ship with no fixture able to fail them. §8.7's direct-application arm binds four
observation types and fixture 160 gates three. §8.4.2 maps the caller-supplied metadata set onto every
Langfuse Observation and no fixture asserts it on a Tool observation. This proposal adds one case to each
fixture. It changes no spec text and adds no directive.

## Motivation

Both gaps were surfaced by the reference implementation rather than by reading, and both were invisible to
review for the same reason: the artifact asserts the right-looking things at the sites it covers, and
reading cannot distinguish that from full coverage.

**The Tool arm.** 0119 made §8.7's direct application binding on a failed Generation "and on its Embedding,
Tool and Retriever counterparts". Fixture 160 was written with three of those four. The record then
compounded the gap by claiming a Tool case was **blocked** on `calls_tool` and `mock_tool` being undefined
in conformance-adapter §5. That claim was corrected in v0.118.1: the directives are indeed undefined, which
remains an open question in its own right, but eight fixtures already declare `calls_tool`, and fixture 098
case 2 already drives `mock_tool: {raises: ...}` into a Langfuse Tool observation asserting `error_message`.
The arm was never blocked. It was unwritten.

**The caller-set scope.** §8.4.2's row is unscoped where the table's other rows are scoped explicitly, which
makes the unscoped wording deliberate rather than loose. The reference implementation read it that way,
implemented the set on its OTel tool span, and did not implement it on the Langfuse Tool observation. Two
bundled observers therefore disagreed about the same event, which is the clearest available signal that this
is a defect and not a reading. No fixture caught it, because 098 asserts the Tool observation's shape
without supplying any caller metadata for it to carry.

## Detailed design

No spec text changes. Both additions are fixture cases covering normative text that already exists.

### Fixture 160: the Tool arm

A fourth failing-provider case on the tool path, matching the three that exist:

> **`tool_failure_error_message_truncated_to_cap`** — a node whose `calls_tool` block raises with an
> oversized harvested message. The Tool observation emits at ERROR with `error_message` truncated per
> §5.5.5 against the **Langfuse observer's own** cap, asserted with the same four `metadata_truncation`
> sub-keys as the other arms.

**The oversized message is supplied literally, not synthesized.** The other three cases use
`message_repeat`, which 0119 added to `mock_llm`'s `raises` (§5.5) and the retrieval mocks' `raises`
(§5.15). It does **not** reach `mock_tool`, whose `raises` is `{error_type, message}`. Extending it would
mean documenting `mock_tool` itself, which is the undefined-family question this proposal deliberately does
not open.

Instead the case sets a **low cap** and supplies a short literal message. §5.5.5 states no minimum cap, so
`payload_byte_cap: 256` is conforming, and 100 repetitions of a four-byte character is 400 bytes, which is
writable inline and exceeds the cap. Every property the other arms test survives:

```
message = 100 x U+1F600 = 400 bytes, which exceeds the 256-byte cap
marker  = "…[truncated, 400 bytes total]" = 31 bytes
N = 256 - 31 = 225;  225 mod 4 = 1, so the cut lands INSIDE a sequence
step 4 backtracks to 224;  emitted value = 224 + 31 = 255 bytes <= 256
```

The cut landing inside a multi-byte sequence is the point: it is what lets `utf8_valid` fail against an
implementation that splits one, which is the reason fixture 160 uses multi-byte filler at all.

### Fixture 098: the caller-set scope

`caller_metadata` supplied at the case level, with those keys asserted on the Tool observation's `metadata`.
The existing `metadata:` assertion is a subset match, so adding keys to it asserts their presence and value
without disturbing what the case already pins.

Placed on the **success** case rather than a failure case, so the assertion is about §8.4.2's scope alone
and does not entangle with §8.4.6's failure fields or §8.7's cap.

## Conformance test impact

Two cases added, no case changed or removed.

- **160** gains a fourth case. Its sidecar's coverage note, which currently records the Tool arm as an
  uncovered gap, is rewritten to describe the case instead.
- **098** gains `caller_metadata` and metadata assertions on an existing case, plus a sidecar note.

**Both could newly fail an implementation that passes today**, which is why this needs a proposal at all
under `GOVERNANCE.md`'s "changing conformance test expectations in a way that any implementation could
fail". Neither changes what conformance means: both rules are already normative. What changes is that a
non-conforming implementation is now detected. The reference implementation would have failed the 098 case
before it fixed the defect that prompted this.

## Alternatives considered

**Do nothing.** Rejected. §8.7's Tool arm has been normative and unpinned since 0119, and the four mappings
are separate code paths in every implementation seen so far. The caller-set gap is worse, because it is a
silent omission a caller only notices when a Langfuse query returns every observation from an invocation
except the tool calls.

**Extend `message_repeat` to `mock_tool`'s `raises`.** Rejected for scope. It would require documenting
`mock_tool`, and documenting one member of the `calls_tool` family without the other five is worse than
documenting none: it would make the family look defined while five names stayed unrecognized vocabulary
under 0120's definition-homes rule. The low-cap route needs no directive change.

**Carry an oversized message inline without lowering the cap.** Rejected. That means roughly 64 KiB of
literal text in a fixture, which is exactly what the synthesis primitives exist to avoid.

**Bundle the `calls_tool` family documentation.** Rejected. It is a six-name vocabulary addition with its
own design question about definition homes, and bundling it would make a two-case fixture proposal into a
directive proposal. Both cases rest on vocabulary eight fixtures already use.

## Open questions

1. **Whether §8.4.2's caller set should be asserted on more than the Tool observation.** This proposal pins
   the one observation type where an implementation was observed to omit it. The row says EVERY Observation,
   and the Generation, Embedding and Retriever types are equally unpinned by any fixture; they simply have
   not been observed to fail. A later pass could assert it across all four, which is a broader fixture sweep
   than this proposal takes on.
2. **Whether the low-cap route should become the house pattern for oversized-message cases.** It needs no
   synthesis primitive and is easier to read than `message_repeat`, but it makes the cap the variable under
   test rather than the message, which is a different thing to get wrong. Fixture 160 would then carry two
   idioms for one behaviour.
