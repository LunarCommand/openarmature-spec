# Graph Engine Conformance Fixtures

Language-agnostic test fixtures for the graph engine specification. Each test is a pair:

- `NNN-name.yaml` — declarative graph definition, initial state, and expected outcome.
- `NNN-name.md` — prose description of what the fixture verifies and which spec sections it exercises.

The YAML schema, directive vocabulary, harness primitive requirements, and adapter responsibility
model are specified in the [`conformance-adapter` capability spec](../../conformance-adapter/spec.md).
That spec is the authoritative reference for what each fixture directive means and what the adapter
MUST implement to honor it.
