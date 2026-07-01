import json
from pathlib import Path

from signal_space import (
    SPEC_VERSION,
    create_graph_view_model,
    create_inspector_model,
    get_allowed_intents,
    get_decision_nodes,
    get_node,
    get_timeline_by_class,
    load_document,
    summarize_graph,
    validate_document,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC_FIXTURES = ROOT / "signal-space-spec" / "fixtures"


def test_agent_doc_fixture_round_trips() -> None:
    document = load_document(SPEC_FIXTURES / "agent_doc_supervisor.json")

    assert document.schema_version == SPEC_VERSION
    assert json.loads(json.dumps(document.raw))["graph"]["id"] == "agent_doc.supervisor"


def test_patchboard_fixture_validates_decision_capability() -> None:
    document = load_document(SPEC_FIXTURES / "patchboard_attention_router.json")
    decisions = [node for node in document.graph.nodes if node.decision is not None]

    assert len(decisions) == 2
    assert any(
        "trainable_model.lifecycle" in node.allowed_modules for node in decisions
    )


def test_summarizes_decisions_and_recommendations() -> None:
    document = load_document(SPEC_FIXTURES / "patchboard_attention_router.json")
    graph = document.graph

    assert summarize_graph(graph).decisions == 2
    assert len(get_decision_nodes(graph)) == 2
    assert len(get_timeline_by_class(graph, "recommendation")) == 2


def test_builds_inspector_model() -> None:
    document = load_document(SPEC_FIXTURES / "agent_doc_supervisor.json")
    inspector = create_inspector_model(
        document.graph,
        {"kind": "node", "id": "agent.perceptron"},
    )

    assert inspector.title == "Route priority"
    assert [section.id for section in inspector.sections] == ["state", "intents"]
    assert inspector.sections[0].fields[0].id == "perceptron.score"


def test_builds_graph_view_model_from_canonical_fixture() -> None:
    document = load_document(SPEC_FIXTURES / "patchboard_attention_router.json")
    view = create_graph_view_model(document.graph, "model.route_priority")

    assert view.summary.id == "patchboard.attention_router"
    assert view.nodes[2].id == "model.route_priority"
    assert view.nodes[2].selected is True
    assert len(view.edges) == 4
    assert any(event.run_id == "run.patch-review.1" for event in view.timeline)
    assert view.inspector.title == "Route priority"


def test_reads_nodes_and_target_intents() -> None:
    document = load_document(SPEC_FIXTURES / "agent_doc_supervisor.json")
    graph = document.graph

    node = get_node(graph, "agent.perceptron")
    assert node is not None
    assert node.label == "Route priority"
    assert get_node(graph, "missing") is None
    assert get_allowed_intents(
        graph,
        {"kind": "node", "id": "agent.perceptron"},
    ) == (
        "evaluate_perceptron",
        "render_advisory_schedule",
        "request_route",
    )


def test_rejects_silent_direct_authority_escalation() -> None:
    data = json.loads((SPEC_FIXTURES / "agent_doc_supervisor.json").read_text())
    data["graph"]["nodes"][2]["decision"]["proposed_intents"][0]["authority"] = "direct"

    try:
        validate_document(data)
    except ValueError as error:
        assert "direct authority" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_unknown_edge_endpoint() -> None:
    data = json.loads((SPEC_FIXTURES / "agent_doc_supervisor.json").read_text())
    data["graph"]["edges"][0]["from"] = "missing"

    try:
        validate_document(data)
    except ValueError as error:
        assert "unknown endpoint" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_trainable_lifecycle_without_matching_capability() -> None:
    data = json.loads((SPEC_FIXTURES / "patchboard_attention_router.json").read_text())
    node = next(
        node
        for node in data["graph"]["nodes"]
        if "trainable_model.lifecycle" in node.get("allowed_modules", [])
    )
    node["decision"]["capabilities"] = [
        capability
        for capability in node["decision"]["capabilities"]
        if capability != "trainable_model.lifecycle"
    ]

    try:
        validate_document(data)
    except ValueError as error:
        assert "trainable lifecycle" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_trainable_lifecycle_without_decision_envelope() -> None:
    data = json.loads((SPEC_FIXTURES / "patchboard_attention_router.json").read_text())
    node = next(
        node
        for node in data["graph"]["nodes"]
        if "trainable_model.lifecycle" in node.get("allowed_modules", [])
    )
    del node["decision"]

    try:
        validate_document(data)
    except ValueError as error:
        assert "trainable lifecycle" in str(error)
    else:
        raise AssertionError("expected validation failure")
