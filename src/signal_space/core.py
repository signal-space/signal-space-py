from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        return cls(
            id=data["id"],
            kind=data["kind"],
            state_class=data["state_class"],
            created_at=data["created_at"],
            node_id=data["node_id"],
            payload=dict(data.get("payload", {})),
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


def load_document(path: str | Path) -> SignalSpaceDocument:
    with Path(path).open(encoding="utf-8") as handle:
        return validate_document(json.load(handle))


def validate_document(data: dict[str, Any]) -> SignalSpaceDocument:
    document = SignalSpaceDocument.from_dict(data)
    node_ids = {node.id for node in document.graph.nodes}
    if len(node_ids) != len(document.graph.nodes):
        raise ValidationError("duplicate node id")

    edge_ids = {edge.id for edge in document.graph.edges}
    if len(edge_ids) != len(document.graph.edges):
        raise ValidationError("duplicate edge id")

    for edge in document.graph.edges:
        if edge.from_node not in node_ids or edge.to_node not in node_ids:
            raise ValidationError(f"edge has unknown endpoint: {edge.id}")

    for node in document.graph.nodes:
        for field in node.state_fields:
            if field.derived and field.writable:
                raise ValidationError(f"derived field cannot be writable: {field.id}")
        if (
            "trainable_model.lifecycle" in node.allowed_modules
            and node.decision
            and "trainable_model.lifecycle" not in node.decision.capabilities
        ):
            raise ValidationError(
                f"trainable lifecycle advertised without decision capability: {node.id}"
            )

    return document
