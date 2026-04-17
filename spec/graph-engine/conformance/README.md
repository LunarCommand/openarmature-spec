# Graph Engine Conformance Fixtures

Language-agnostic test fixtures for the graph engine specification. Each test is a pair:

- `NNN-name.yaml` — declarative graph definition, initial state, and expected outcome.
- `NNN-name.md` — prose description of what the fixture verifies and which spec sections it exercises.

## Fixture format (informal, v0)

Each YAML fixture uses the following shape. The format is deliberately minimal; a formal schema may land in a
later proposal.

```yaml
state:
  fields:
    <field_name>:
      type: string | int | float | bool | list<string> | list<int> | dict<string,string> | ...
      default: <value>
      reducer: last_write_wins | append | merge | <custom>   # optional; defaults to last_write_wins

entry: <node_name>

nodes:
  <node_name>:
    update: {<field>: <value>, ...}       # partial update the node returns
    # OR
    raises: "<error message>"             # node raises instead of returning

edges:
  - from: <node_name>
    to: <node_name> | END                 # static edge
  - from: <node_name>
    condition:                            # conditional edge (evaluated against post-update state)
      if_field: <field_name>
      equals: <value>
      then: <node_name> | END
      else: <node_name> | END

initial_state: {<field>: <value>, ...}

expected:
  final_state: {<field>: <value>, ...}    # OR expected_error: {type: ..., ...}
  execution_order: [<node_name>, ...]
```

Adapters in each language translate this YAML into native graph constructions, run the graph, and assert
equality on `final_state` and `execution_order`.
