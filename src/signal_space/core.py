from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal, Mapping


SPEC_VERSION = "0.1.0"

AuthorityLevel = Literal["local", "advisory", "gated", "direct"]
StateClass = Literal["observation", "recommendation", "action"]
NodeFamily = Literal["source", "transform", "memory", "decision", "gate", "output"]


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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
        )


@dataclass(frozen=True)
class SignalEdge:
    id: str
    from_node: str
    to_node: str
    label: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalEdge:
        return cls(
            id=data["id"],
            from_node=data["from"],
            to_node=data["to"],
            label=data.get("label"),
        )


@dataclass(frozen=True)
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


@dataclass(frozen=True)
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
        )


@dataclass(frozen=True)
class SignalSpaceDocument:
    schema_version: str
    graph: SignalGraph
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalSpaceDocument:
        if data.get("schema_version") != SPEC_VERSION:
            raise ValidationError(
                f"expected spec version {SPEC_VERSION}, got {data.get('schema_version')}"
            )
        return cls(
            schema_version=data["schema_version"],
            graph=SignalGraph.from_dict(data["graph"]),
            raw=data,
        )


@dataclass(frozen=True)
class GraphSummary:
    id: str
    name: str | None
    source: str | None
    nodes: int
    edges: int
    timeline_events: int
    decisions: int
    authority: AuthorityLevel


@dataclass(frozen=True)
class InspectorSection:
    id: str
    title: str
    fields: tuple[StateField, ...]


@dataclass(frozen=True)
class InspectorModel:
    target: dict[str, str]
    title: str
    sections: tuple[InspectorSection, ...]


@dataclass(frozen=True)
class NodeView:
    id: str
    label: str
    family: NodeFamily
    mode: str | None
    authority: AuthorityLevel
    selected: bool


@dataclass(frozen=True)
class EdgeView:
    id: str
    from_node: str
    to_node: str
    label: str | None


@dataclass(frozen=True)
class TimelineView:
    id: str
    kind: str
    state_class: StateClass
    created_at: str
    node_id: str
    decision_id: str | None
    run_id: str | None


@dataclass(frozen=True)
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
    node_ids = {node.id for node in graph.nodes}
    if len(node_ids) != len(graph.nodes):
        raise ValidationError("duplicate node id")

    edge_ids = {edge.id for edge in graph.edges}
    if len(edge_ids) != len(graph.edges):
        raise ValidationError("duplicate edge id")

    for edge in graph.edges:
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            raise ValidationError(f"edge has unknown endpoint: {edge.id}")

    for node in graph.nodes:
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

    return graph


def _grants_direct_authority(node: SignalNode, intent: SurfaceIntent) -> bool:
    return (
        node.authority.default == "direct"
        or node.authority.by_intent.get(intent.type) == "direct"
        or (node.decision is not None and node.decision.authority == "direct")
    )


def get_node(graph: SignalGraph, node_id: str) -> SignalNode | None:
    return next((node for node in graph.nodes if node.id == node_id), None)


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
    validate_graph(graph)
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
