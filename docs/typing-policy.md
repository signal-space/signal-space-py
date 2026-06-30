# Python Typing Policy

`signal-space-py` exposes immutable dataclasses for parsed spec objects and
local projection view models.

## Boundaries

- Parsed spec objects preserve fixture shape where Python identifiers allow it.
  Reserved JSON keys use Python names, such as `SignalEdge.from_node`.
- View-model dataclasses are Python-native and do not attempt to be JSON schema
  mirrors. They are stable helpers for inspectors, CLIs, and tests.
- Public helpers return tuples instead of mutable lists.

## Lazily

The package depends on `lazily-py` because runtime adapters will project Signal
Space state through lazily `Cell` and `Signal` objects. The current public API
does not instantiate lazily primitives yet; inspector and graph helpers remain
pure functions over parsed `SignalGraph` values.

## Compatibility

The supported `signal-space-spec` version is declared in `pyproject.toml` under
`[tool.signal-space].spec-version` and exported as `SPEC_VERSION`. Any future
runtime adapter must preserve fixture validation and these pure projection
helpers as the compatibility floor.
