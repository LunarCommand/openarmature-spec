# 055 — Wire-byte stability (Anthropic Messages)

Verifies §8 *Intra-impl wire-byte stability* applied to the §8.2 Anthropic Messages mapping —
two `complete()` calls whose OA inputs are structurally equivalent but were constructed with
different insertion / iteration orders MUST produce byte-identical Anthropic wire request
bodies.

**Spec sections exercised:**

- §8 framing — *Intra-impl wire-byte stability* paragraph.
- §8.2.1 — Anthropic request mapping; *Wire-byte stability* sub-paragraph (system extraction
  concatenation order, `tools[].input_schema` canonicalization, `tool_use` / `tool_result`
  content blocks, `tool_use.input` recursive canonicalization).

**What passes:**

- Tool `input_schema` for both calls emits with sorted JSON object keys at every nesting level.
- `tool_use.input` (a structured-arguments mapping) emits with sorted keys; the second call's
  alternate insertion order produces identical bytes.
- The `system` field concatenates the system message in stable order.

**What fails:**

- The two wire bodies differ in any byte.
- Implementation relies on insertion-order JSON serialization without canonicalization at the
  documented boundaries.
