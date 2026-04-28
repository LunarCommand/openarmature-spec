# openarmature-spec

Language-agnostic specification for [OpenArmature](docs/openarmature.md) — a workflow framework for LLM pipelines and tool-calling agents.

**Current spec version:** [v0.3.0](CHANGELOG.md). Pre-1.0; breaking changes may land in MINOR bumps. The only capability specified so far is `graph-engine`; additional capabilities listed in the charter are planned.

This repo holds the spec, conformance fixtures, governance, and proposals. **No implementation code lives here.** Sibling repos:

- [`openarmature-python`](https://github.com/LunarCommand/openarmature-python) — Python reference implementation
- `openarmature-typescript` — planned implementation
- [`openarmature-examples`](https://github.com/LunarCommand/openarmature-examples) — end-to-end examples

## Layout

- [`docs/openarmature.md`](docs/openarmature.md) — project charter (thesis, architecture, roadmap)
- [`spec/`](spec/) — canonical behavioral specs, one directory per capability, with language-agnostic conformance fixtures
- [`proposals/`](proposals/) — numbered RFC-style change proposals
- [`GOVERNANCE.md`](GOVERNANCE.md) — how specs are written, versioned, and changed
- [`CHANGELOG.md`](CHANGELOG.md) — SemVer-tracked spec history with links to driving proposals

## Contributing

Any change to a capability's behavior, public types, or conformance expectations requires a numbered proposal. See [`GOVERNANCE.md#proposal-lifecycle`](GOVERNANCE.md#proposal-lifecycle).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
