# signal-space-py

Python types and conformance helpers for Signal Space.

Supported `signal-space-spec`: `0.1.0`

The package is intended to layer on top of `lazily-py` for reactive runtime
integration. The current implementation focuses on fixture parsing,
round-tripping, validation of ids, edges, authority levels, derived state fields,
and immutable inspector/view-model projections for local tools.

Core helpers:

- `load_document(path)` / `validate_document(data)`
- `validate_graph(graph)`
- `get_node(graph, node_id)`
- `get_decision_nodes(graph)`
- `get_timeline_by_class(graph, state_class)`
- `get_allowed_intents(graph, target=None)`
- `summarize_graph(graph)`
- `create_inspector_model(graph, target)`
- `create_graph_view_model(graph, selected_node_id=None)`

Typing and lazily integration policy is documented in
[`docs/typing-policy.md`](docs/typing-policy.md).
