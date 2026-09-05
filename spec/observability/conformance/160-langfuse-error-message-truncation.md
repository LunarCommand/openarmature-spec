# 160 — Langfuse Error-Message Truncation

Verifies that a failed observation's `metadata.error_message` is subject to observability §5.5.5's
per-observer byte cap, and that the Langfuse observer applies that cap **directly**, under its **own**
configured value, rather than inheriting an already-truncated one (§8.7).

Proposal 0118 classified the harvested exception message as payload so `disable_provider_payload` could gate
it, but did not say whether the size bound followed it. Proposal 0119 closes that: §5.5.5 now governs every
payload-classified value, and where a value has no span-attribute source the mapping that writes it applies
the cap. `error_message` is the case in point. Nothing writes it to a span attribute, so §8.7's inheritance
arm cannot reach it, and before this it was the one payload channel with no size limit.

## Why every case sets a non-default `payload_byte_cap`

§8.7 says an observer **MUST NOT** take the OTel observer's cap for this value. That rule is only testable
when the two observers hold **different** caps.

Leaving the cap unset does not achieve that: it puts **both** observers at §5.5.5's 65,536-byte default,
where an implementation reading the wrong observer's cap produces a byte-identical result and passes. Each
case therefore sets `langfuse_observer.payload_byte_cap` to 1024 and leaves the OTel observer at the
default. An implementation sourcing the cap from the OTel side truncates at 65,536 and fails both
`max_bytes` and `marker_pattern`.

Setting an `otel_observer` block is not the alternative and would not help. The directive carries a
`payload_byte_cap` of its own, so setting both to the same value would restore exactly the ambiguity this
fixture exists to remove.

## Why the filler is a 4-byte character

`utf8_valid` gates §5.5.5 step 4's code-point-boundary backtracking. With all-ASCII filler every byte offset
is already a code-point boundary, so the assertion cannot fail and an implementation that splits a
multi-byte sequence passes anyway. The filler is U+1F600 (four bytes per character) and the numbers are
chosen so the cut lands **inside** a sequence:

```
marker "…[truncated, 102400 bytes total]" = 34 bytes
N = 1024 - 34 = 990;  990 mod 4 = 2, so N falls inside a sequence
step 4 backtracks to 988;  emitted value = 988 + 34 = 1022 bytes
```

`bytes: 102400` is divisible by 4, so `message_repeat` synthesizes exactly 25600 characters and the message
is exactly 102400 bytes, which is the `M` the marker quotes. Where `bytes` does not divide evenly,
conformance-adapter §5.15 rounds **down** to the largest whole number of repetitions that fits.

Changing the filler to ASCII, or rounding the cap to a multiple of the character width, silently disables
the `utf8_valid` assertion while leaving the fixture green. The YAML header says so at the point of change.

## How the cases discriminate

Cases 1 to 4 fail a call whose mock supplies a 100 KiB harvested message, synthesized with `message_repeat`
(conformance-adapter §5.15 for the retrieval mocks, §5.5 for `mock_llm`) rather than carried inline. Case 5
supplies a short literal message instead, as the control.

1. **`embedding_failure_error_message_truncated_to_cap`** — the Embedding mapping (§8.4.5). Asserts all four
   `metadata_truncation` sub-keys: at most 1024 bytes, ends with the §5.5.5 marker, valid UTF-8 across the
   boundary the cut lands inside, and a byte-exact prefix of the untruncated message. Each fails a different
   wrong implementation: one that shortened without the marker, one that split a multi-byte sequence, one
   that re-serialized rather than cut.
2. **`generation_failure_error_message_truncated_to_cap`** — the same on the LLM mapping (§8.4.3). An
   implementation that hooked the cap into one mapping in isolation passes case 1 and fails here.
3. **`default_posture_withholds_message_so_nothing_to_truncate`** — the same failure under
   `disable_provider_payload: true`. §5.5.5 bounds a message the flag **permits**; it does not decide
   whether the message is emitted. §5.5.4 does, and under the default posture it is withheld, so
   `error_message` is **absent** rather than truncated, asserted via `metadata_absent`. The case gates that
   an implementation applies the gate and the cap in that order, rather than treating truncation as a
   substitute for the gate. The cap is still set, so an implementation that emitted a truncated message here
   instead of none fails the absence assertion.
4. **`retriever_failure_error_message_truncated_to_cap`** — the Retriever mapping (§8.4.7). An
   implementation that wired the cap into the Generation and Embedding mappings but not this one passes
   cases 1 and 2 and fails here.
5. **`error_message_below_cap_untouched`** — the control. Cases 1, 2 and 4 all assert an **oversized**
   message comes back truncated; none of them asserts a message **under** the cap comes back whole. An
   implementation that truncated unconditionally, or appended the marker regardless of length, passes all
   three. This case pins the other side of §5.5.5's threshold by asserting `error_message` literally, which
   no truncated form can satisfy: truncation both shortens the value and appends the marker.

`error_type` is asserted by its **literal** value in all four. The mock's `raises` pins it, so a format
matcher would assert less than the fixture knows; fixture 150 sets the same precedent. Asserting it also
keeps the truncation assertions from passing against an observation that emitted nothing at all, which
`metadata_truncation`'s presence requirement (conformance-adapter §5.5) independently enforces.

## Coverage gap: the Tool arm

§8.7's direct-application arm binds a failed Generation and its Embedding, **Tool** and Retriever
counterparts (§8.4.5 to §8.4.7). This fixture gates three of the four.

The Tool arm is not gated, and it is **not blocked**: it is simply unwritten. Inducing an oversized
harvested message from a tool call needs `mock_tool: {raises: ...}`, which fixture 098 case 2 already uses
to drive a failed Tool observation asserting `error_message`. `mock_tool` and the `calls_tool` block are
undefined in conformance-adapter §5, which is tracked separately, but nine fixtures already rest on that
vocabulary, so it cannot be the reason a tenth is not written.

This is a **normative rule with no fixture**, not merely a thin spot, so it is also recorded in
`docs/open-questions.md` where an implementer building against §8.7 will look. The mappings are separate and
an implementation can cap one and not another, which is the defect this fixture exists to detect.

## Not JSON-encoded

§5.5.5's unparseable-JSON truncation signal is a property of truncating a JSON-encoded attribute.
`error_message` is a plain string, so the marker is appended directly and its presence is itself the signal.
`marker_pattern` asserts that rather than any parse failure.

## Spec coverage

- **observability §5.5.5** — the truncation contract's direct-application arm for a payload-classified value
  with no span-attribute source, and step 4's code-point-boundary backtracking.
- **observability §8.7** — the Langfuse observer applying the cap when it writes `metadata.error_message`,
  under its own configured cap and not the OTel observer's.
- **observability §5.5.4** — a message the payload flag permits is subject to the cap; one it withholds is
  absent rather than truncated.
- **conformance-adapter §5.5 / §5.15** — `metadata_truncation` and `payload_byte_cap`, `mock_llm`'s `raises`
  form, and `message_repeat` on the retrieval mocks.
