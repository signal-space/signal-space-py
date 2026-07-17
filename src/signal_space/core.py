from __future__ import annotations

from dataclasses import dataclass
import dataclasses
import json
from pathlib import Path
from typing import Any, Literal, Mapping


SPEC_VERSION = "0.4.0"
SUPPORTED_VERSIONS = ("0.2.0", "0.3.0", "0.4.0")

AuthorityLevel = Literal["local", "advisory", "gated", "direct"]
StateClass = Literal["observation", "recommendation", "action"]
NodeFamily = Literal["source", "transform", "memory", "decision", "gate", "output"]
PortDirection = Literal["in", "out"]
PortDtype = Literal["scalar", "vector", "event", "window", "decision", "label"]
IoDirection = Literal["ingress", "egress"]
IoTransport = Literal[
    "webhook",
    "websocket",
    "file_tail",
    "timer",
    "stdin_jsonl",
    "exec",
    "notify",
    "mcp",
]


class ValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Authority:
    default: AuthorityLevel
    by_intent: dict[str, AuthorityLevel]
    owner: str | None = None
    boundary: str | None = None
    requires_approval: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Authority:
        return cls(
            default=data["default"],
            by_intent=dict(data.get("by_intent", {})),
            owner=data.get("owner"),
            boundary=data.get("boundary"),
            requires_approval=bool(data.get("requires_approval", False)),
        )


@dataclass(frozen=True, slots=True)
class StateField:
    id: str
    state_class: StateClass
    writable: bool
    derived: bool
    value: Any = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateField:
        return cls(
            id=data["id"],
            state_class=data["state_class"],
            writable=bool(data["writable"]),
            derived=bool(data.get("derived", False)),
            value=data.get("value"),
        )


@dataclass(frozen=True, slots=True)
class SurfaceIntent:
    id: str
    type: str
    target: dict[str, str]
    payload: dict[str, Any]
    actor: str
    authority: AuthorityLevel
    created_at: str
    reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SurfaceIntent:
        return cls(
            id=data["id"],
            type=data["type"],
            target=dict(data["target"]),
            payload=dict(data["payload"]),
            actor=data["actor"],
            authority=data["authority"],
            created_at=data["created_at"],
            reason=data.get("reason"),
        )


@dataclass(frozen=True, slots=True)
class DecisionEnvelope:
    id: str
    mode: str
    capabilities: tuple[str, ...]
    inputs: tuple[str, ...]
    output_schema: dict[str, Any]
    authority: AuthorityLevel
    confidence: float | None = None
    proposed_intents: tuple[SurfaceIntent, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionEnvelope:
        return cls(
            id=data["id"],
            mode=data["mode"],
            capabilities=tuple(data.get("capabilities", [])),
            inputs=tuple(data.get("inputs", [])),
            output_schema=dict(data.get("output_schema", {})),
            authority=data["authority"],
            confidence=data.get("confidence"),
            proposed_intents=tuple(
                SurfaceIntent.from_dict(intent)
                for intent in data.get("proposed_intents", [])
            ),
        )


@dataclass(frozen=True, slots=True)
class StateTransition:
    from_state: str
    event: str
    to_state: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateTransition:
        return cls(
            from_state=data["from"],
            event=data["event"],
            to_state=data["to"],
        )


@dataclass(frozen=True, slots=True)
class StateChart:
    states: tuple[str, ...]
    initial: str
    transitions: tuple[StateTransition, ...]
    current: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateChart:
        return cls(
            states=tuple(data.get("states", ())),
            initial=data["initial"],
            transitions=tuple(
                StateTransition.from_dict(t) for t in data.get("transitions", [])
            ),
            current=data.get("current"),
        )

    def contains_state(self, state: str) -> bool:
        return state in self.states

    def transition(self, from_state: str, event: str) -> str | None:
        return next(
            (
                t.to_state
                for t in self.transitions
                if t.from_state == from_state and t.event == event
            ),
            None,
        )

    def effective_current(self) -> str:
        return self.current if self.current is not None else self.initial


@dataclass(frozen=True, slots=True)
class PortSpec:
    id: str
    direction: PortDirection
    dtype: PortDtype
    name: str | None = None
    required: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortSpec:
        return cls(
            id=data["id"],
            direction=data["direction"],
            dtype=data["dtype"],
            name=data.get("name"),
            required=bool(data.get("required", False)),
        )


@dataclass(frozen=True, slots=True)
class StreamTelemetry:
    rate_hz: float | None = None
    latency_ms: float | None = None
    freshness_ms: float | None = None
    last_value_preview: Any = None
    distribution_hint: Any = None
    missing_data: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamTelemetry:
        return cls(
            rate_hz=data.get("rate_hz"),
            latency_ms=data.get("latency_ms"),
            freshness_ms=data.get("freshness_ms"),
            last_value_preview=data.get("last_value_preview"),
            distribution_hint=data.get("distribution_hint"),
            missing_data=bool(data.get("missing_data", False)),
        )


@dataclass(frozen=True, slots=True)
class IoBinding:
    direction: IoDirection
    transport: IoTransport
    endpoint: str | None = None
    format: str | None = None
    schema_ref: str | None = None
    auth_ref: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IoBinding:
        return cls(
            direction=data["direction"],
            transport=data["transport"],
            endpoint=data.get("endpoint"),
            format=data.get("format"),
            schema_ref=data.get("schema_ref"),
            auth_ref=data.get("auth_ref"),
        )


@dataclass(frozen=True, slots=True)
class SignalNode:
    id: str
    family: NodeFamily
    authority: Authority
    state_fields: tuple[StateField, ...]
    allowed_intents: tuple[str, ...]
    mode: str | None = None
    label: str | None = None
    decision: DecisionEnvelope | None = None
    allowed_modules: tuple[str, ...] = ()
    state_chart: StateChart | None = None
    ports: tuple[PortSpec, ...] = ()
    io_binding: IoBinding | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalNode:
        return cls(
            id=data["id"],
            family=data["family"],
            authority=Authority.from_dict(data["authority"]),
            state_fields=tuple(
                StateField.from_dict(field)
                for field in data.get("state", {}).get("fields", [])
            ),
            allowed_intents=tuple(data.get("allowed_intents", [])),
            mode=data.get("mode"),
            label=data.get("label"),
            decision=(
                DecisionEnvelope.from_dict(data["decision"])
                if "decision" in data
                else None
            ),
            allowed_modules=tuple(data.get("allowed_modules", [])),
            state_chart=(
                StateChart.from_dict(data["state_chart"])
                if data.get("state_chart")
                else None
            ),
            ports=tuple(PortSpec.from_dict(p) for p in data.get("ports", [])),
            io_binding=(
                IoBinding.from_dict(data["io_binding"])
                if data.get("io_binding")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class SignalEdge:
    id: str
    from_node: str
    to_node: str
    label: str | None = None
    from_port: str | None = None
    to_port: str | None = None
    stream_telemetry: StreamTelemetry | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalEdge:
        return cls(
            id=data["id"],
            from_node=data["from"],
            to_node=data["to"],
            label=data.get("label"),
            from_port=data.get("from_port"),
            to_port=data.get("to_port"),
            stream_telemetry=(
                StreamTelemetry.from_dict(data["stream_telemetry"])
                if data.get("stream_telemetry")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    id: str
    kind: str
    state_class: StateClass
    created_at: str
    node_id: str
    payload: dict[str, Any]
    decision_id: str | None = None
    run_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        return cls(
            id=data["id"],
            kind=data["kind"],
            state_class=data["state_class"],
            created_at=data["created_at"],
            node_id=data["node_id"],
            payload=dict(data.get("payload", {})),
            decision_id=data.get("decision_id"),
            run_id=data.get("run_id"),
        )


@dataclass(frozen=True, slots=True)
class SignalGraph:
    id: str
    nodes: tuple[SignalNode, ...]
    edges: tuple[SignalEdge, ...]
    timeline: tuple[TimelineEvent, ...]
    authority: Authority
    intent_modules: tuple[dict[str, Any], ...]
    allowed_intents: tuple[str, ...]
    name: str | None = None
    source: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    _node_index: dict[str, SignalNode] = dataclasses.field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "_node_index", {node.id: node for node in self.nodes})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalGraph:
        return cls(
            id=data["id"],
            nodes=tuple(SignalNode.from_dict(node) for node in data.get("nodes", [])),
            edges=tuple(SignalEdge.from_dict(edge) for edge in data.get("edges", [])),
            timeline=tuple(
                TimelineEvent.from_dict(event) for event in data.get("timeline", [])
            ),
            authority=Authority.from_dict(data["authority"]),
            intent_modules=tuple(data.get("intent_modules", [])),
            allowed_intents=tuple(data.get("allowed_intents", [])),
            name=data.get("name"),
            source=data.get("source"),
            category=data.get("category"),
            tags=tuple(data.get("tags", [])),
        )


@dataclass(frozen=True, slots=True)
class SignalSpaceDocument:
    schema_version: str
    graph: SignalGraph
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalSpaceDocument:
        version = data.get("schema_version")
        if version not in SUPPORTED_VERSIONS:
            raise ValidationError(f"unsupported spec version: {version}")
        return cls(
            schema_version=data["schema_version"],
            graph=SignalGraph.from_dict(data["graph"]),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class GraphSummary:
    id: str
    name: str | None
    source: str | None
    nodes: int
    edges: int
    timeline_events: int
    decisions: int
    authority: AuthorityLevel


@dataclass(frozen=True, slots=True)
class InspectorSection:
    id: str
    title: str
    fields: tuple[StateField, ...]


@dataclass(frozen=True, slots=True)
class InspectorModel:
    target: dict[str, str]
    title: str
    sections: tuple[InspectorSection, ...]


@dataclass(frozen=True, slots=True)
class NodeView:
    id: str
    label: str
    family: NodeFamily
    mode: str | None
    authority: AuthorityLevel
    selected: bool


@dataclass(frozen=True, slots=True)
class EdgeView:
    id: str
    from_node: str
    to_node: str
    label: str | None


@dataclass(frozen=True, slots=True)
class TimelineView:
    id: str
    kind: str
    state_class: StateClass
    created_at: str
    node_id: str
    decision_id: str | None
    run_id: str | None


@dataclass(frozen=True, slots=True)
class GraphViewModel:
    summary: GraphSummary
    nodes: tuple[NodeView, ...]
    edges: tuple[EdgeView, ...]
    timeline: tuple[TimelineView, ...]
    inspector: InspectorModel


def load_document(path: str | Path) -> SignalSpaceDocument:
    with Path(path).open(encoding="utf-8") as handle:
        return validate_document(json.load(handle))


def validate_document(data: dict[str, Any]) -> SignalSpaceDocument:
    document = SignalSpaceDocument.from_dict(data)
    validate_graph(document.graph)
    return document


def validate_graph(graph: SignalGraph) -> SignalGraph:
    nodes_by_id: dict[str, SignalNode] = {}
    for node in graph.nodes:
        if node.id in nodes_by_id:
            raise ValidationError(f"duplicate node id: {node.id}")
        nodes_by_id[node.id] = node
        for field in node.state_fields:
            if field.derived and field.writable:
                raise ValidationError(f"derived field cannot be writable: {field.id}")
        if "trainable_model.lifecycle" in node.allowed_modules:
            capabilities = node.decision.capabilities if node.decision else ()
            if "trainable_model.lifecycle" not in capabilities:
                raise ValidationError(
                    f"trainable lifecycle advertised without decision capability: {node.id}"
                )
        if node.decision:
            for intent in node.decision.proposed_intents:
                if intent.authority == "direct" and not _grants_direct_authority(
                    node,
                    intent,
                ):
                    raise ValidationError(
                        f"proposed intent upgrades to direct authority: {intent.id}"
                    )
        if node.state_chart is not None:
            _validate_state_chart(node.id, node.state_chart)
        _validate_ports(node)
        _validate_io_binding(node)

    edge_ids: set[str] = set()
    for edge in graph.edges:
        if edge.id in edge_ids:
            raise ValidationError(f"duplicate edge id: {edge.id}")
        edge_ids.add(edge.id)
        from_node = nodes_by_id.get(edge.from_node)
        to_node = nodes_by_id.get(edge.to_node)
        if from_node is None or to_node is None:
            raise ValidationError(f"edge has unknown endpoint: {edge.id}")
        _validate_edge_ports(edge, from_node, to_node)

    return graph


def _validate_state_chart(node_id: str, chart: StateChart) -> None:
    if not chart.states:
        raise ValidationError(f"state_chart has no states: {node_id}")
    if chart.initial not in chart.states:
        raise ValidationError(f"state_chart initial state not in states: {node_id}")
    if chart.current is not None and chart.current not in chart.states:
        raise ValidationError(f"state_chart current state not in states: {node_id}")
    for transition in chart.transitions:
        if transition.from_state not in chart.states:
            raise ValidationError(
                f"state_chart transition 'from' not in states: {node_id}"
            )
        if transition.to_state not in chart.states:
            raise ValidationError(
                f"state_chart transition 'to' not in states: {node_id}"
            )


def _validate_ports(node: SignalNode) -> None:
    seen: set[str] = set()
    for port in node.ports:
        if port.id in seen:
            raise ValidationError(f"duplicate port id: {port.id} on node {node.id}")
        seen.add(port.id)


def _validate_io_binding(node: SignalNode) -> None:
    binding = node.io_binding
    if binding is None:
        return
    if binding.direction == "ingress":
        if node.family != "source":
            raise ValidationError(
                f"ingress io_binding only allowed on source nodes: {node.id}"
            )
    elif binding.direction == "egress":
        if node.family not in ("gate", "output"):
            raise ValidationError(
                f"egress io_binding only allowed on gate/output nodes: {node.id}"
            )
        if node.authority.default == "direct":
            raise ValidationError(
                f"egress io_binding cannot carry direct authority: {node.id}"
            )


def _validate_edge_ports(
    edge: SignalEdge, from_node: SignalNode, to_node: SignalNode
) -> None:
    if edge.from_port is None:
        return
    from_port = next(
        (port for port in from_node.ports if port.id == edge.from_port), None
    )
    if from_port is None:
        raise ValidationError(f"edge from_port not found on {from_node.id}: {edge.id}")
    if edge.to_port is None:
        raise ValidationError(f"edge names from_port but not to_port: {edge.id}")
    to_port = next((port for port in to_node.ports if port.id == edge.to_port), None)
    if to_port is None:
        raise ValidationError(f"edge to_port not found on {to_node.id}: {edge.id}")
    if from_port.direction != "out":
        raise ValidationError(f"edge from_port is not an output jack: {edge.id}")
    if to_port.direction != "in":
        raise ValidationError(f"edge to_port is not an input jack: {edge.id}")
    if from_port.dtype != to_port.dtype:
        raise ValidationError(
            f"edge port dtype mismatch ({from_port.dtype} -> {to_port.dtype}): {edge.id}"
        )


def _grants_direct_authority(node: SignalNode, intent: SurfaceIntent) -> bool:
    return (
        node.authority.default == "direct"
        or node.authority.by_intent.get(intent.type) == "direct"
        or (node.decision is not None and node.decision.authority == "direct")
    )


def get_node(graph: SignalGraph, node_id: str) -> SignalNode | None:
    return graph._node_index.get(node_id)


def get_decision_nodes(graph: SignalGraph) -> tuple[SignalNode, ...]:
    return tuple(node for node in graph.nodes if node.family == "decision")


def get_timeline_by_class(
    graph: SignalGraph,
    state_class: StateClass,
) -> tuple[TimelineEvent, ...]:
    return tuple(event for event in graph.timeline if event.state_class == state_class)


def get_allowed_intents(
    graph: SignalGraph,
    target: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    if target is None:
        return graph.allowed_intents

    if target.get("kind") == "node":
        node = get_node(graph, target.get("id", ""))
        return node.allowed_intents if node else ()

    if target.get("kind") == "edge":
        return ()

    return graph.allowed_intents


def summarize_graph(graph: SignalGraph) -> GraphSummary:
    return GraphSummary(
        id=graph.id,
        name=graph.name,
        source=graph.source,
        nodes=len(graph.nodes),
        edges=len(graph.edges),
        timeline_events=len(graph.timeline),
        decisions=len(get_decision_nodes(graph)),
        authority=graph.authority.default,
    )


def create_inspector_model(
    graph: SignalGraph,
    target: Mapping[str, str],
) -> InspectorModel:
    target_copy = dict(target)
    node = (
        get_node(graph, target.get("id", "")) if target.get("kind") == "node" else None
    )
    if node is None:
        return InspectorModel(
            target=target_copy,
            title=target.get("id", graph.id),
            sections=(),
        )

    intent_fields = tuple(
        StateField(
            id=intent,
            state_class="recommendation",
            writable=False,
            derived=True,
            value=intent,
        )
        for intent in node.allowed_intents
    )

    return InspectorModel(
        target=target_copy,
        title=node.label or node.id,
        sections=(
            InspectorSection(id="state", title="State", fields=node.state_fields),
            InspectorSection(id="intents", title="Intents", fields=intent_fields),
        ),
    )


def create_graph_view_model(
    graph: SignalGraph,
    selected_node_id: str | None = None,
) -> GraphViewModel:
    selected = get_node(graph, selected_node_id) if selected_node_id else None
    if selected is None:
        selected = graph.nodes[0] if graph.nodes else None

    selected_target = (
        {"kind": "node", "id": selected.id}
        if selected is not None
        else {"kind": "graph", "id": graph.id}
    )

    return GraphViewModel(
        summary=summarize_graph(graph),
        nodes=tuple(
            NodeView(
                id=node.id,
                label=node.label or node.id,
                family=node.family,
                mode=node.mode,
                authority=node.authority.default,
                selected=selected is not None and node.id == selected.id,
            )
            for node in graph.nodes
        ),
        edges=tuple(
            EdgeView(
                id=edge.id,
                from_node=edge.from_node,
                to_node=edge.to_node,
                label=edge.label,
            )
            for edge in graph.edges
        ),
        timeline=tuple(
            TimelineView(
                id=event.id,
                kind=event.kind,
                state_class=event.state_class,
                created_at=event.created_at,
                node_id=event.node_id,
                decision_id=event.decision_id,
                run_id=event.run_id,
            )
            for event in graph.timeline
        ),
        inspector=create_inspector_model(graph, selected_target),
    )
