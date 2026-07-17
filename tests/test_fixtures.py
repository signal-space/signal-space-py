import json
from pathlib import Path

from signal_space import (
    SPEC_VERSION,
    SUPPORTED_VERSIONS,
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


def _load_raw(name: str) -> dict:
    return json.loads((SPEC_FIXTURES / name).read_text())


def test_agent_doc_fixture_round_trips() -> None:
    document = load_document(SPEC_FIXTURES / "agent_doc_supervisor.json")

    assert document.schema_version in SUPPORTED_VERSIONS
    assert json.loads(json.dumps(document.raw))["graph"]["id"] == "agent_doc.supervisor"


def test_all_spec_fixtures_round_trip() -> None:
    for name in (
        "agent_doc_supervisor.json",
        "patchboard_attention_router.json",
        "patchboard_io_rack.json",
        "patchboard_supervisor.json",
        "patchboard_webhook_triage.json",
        "patchboard_scheduled_anomaly.json",
        "patchboard_event_fanout.json",
    ):
        document = load_document(SPEC_FIXTURES / name)
        assert document.schema_version in SUPPORTED_VERSIONS
        assert document.graph.id


def test_workflow_template_fixtures_carry_category_and_tags() -> None:
    for name in (
        "patchboard_webhook_triage.json",
        "patchboard_scheduled_anomaly.json",
        "patchboard_event_fanout.json",
    ):
        document = load_document(SPEC_FIXTURES / name)
        assert document.schema_version == SPEC_VERSION
        assert document.graph.category == "workflow_template"
        assert document.graph.tags
        # No node in a template ever holds direct authority.
        for node in document.graph.nodes:
            assert node.authority.default != "direct"


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


def test_rejects_unsupported_spec_version() -> None:
    data = _load_raw("agent_doc_supervisor.json")
    data["schema_version"] = "1.0.0"

    try:
        validate_document(data)
    except ValueError as error:
        assert "unsupported spec version" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_state_chart_transition_out_of_bounds() -> None:
    data = _load_raw("patchboard_attention_router.json")
    node = next(n for n in data["graph"]["nodes"] if n.get("state_chart"))
    node["state_chart"]["transitions"][0]["to"] = "__missing__"

    try:
        validate_document(data)
    except ValueError as error:
        assert "transition 'to' not in states" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_ingress_io_binding_on_non_source_node() -> None:
    data = _load_raw("patchboard_io_rack.json")
    ingress = next(
        n
        for n in data["graph"]["nodes"]
        if n.get("io_binding", {}).get("direction") == "ingress"
    )
    transform = next(n for n in data["graph"]["nodes"] if n["family"] == "transform")
    transform["io_binding"] = ingress["io_binding"]

    try:
        validate_document(data)
    except ValueError as error:
        assert "ingress io_binding only allowed on source" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_egress_io_binding_with_direct_authority() -> None:
    data = _load_raw("patchboard_io_rack.json")
    egress = next(
        n
        for n in data["graph"]["nodes"]
        if n.get("io_binding", {}).get("direction") == "egress"
    )
    egress["authority"]["default"] = "direct"

    try:
        validate_document(data)
    except ValueError as error:
        assert "egress io_binding cannot carry direct authority" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_edge_port_dtype_mismatch() -> None:
    data = _load_raw("patchboard_attention_router.json")
    edge = next(e for e in data["graph"]["edges"] if e.get("from_port"))
    from_node = next(n for n in data["graph"]["nodes"] if n["id"] == edge["from"])
    port = next(p for p in from_node["ports"] if p["id"] == edge["from_port"])
    port["dtype"] = "scalar"

    try:
        validate_document(data)
    except ValueError as error:
        assert "port dtype mismatch" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_rejects_duplicate_port_id() -> None:
    data = _load_raw("patchboard_attention_router.json")
    node = next(n for n in data["graph"]["nodes"] if n.get("ports"))
    node["ports"].append(dict(node["ports"][0]))

    try:
        validate_document(data)
    except ValueError as error:
        assert "duplicate port id" in str(error)
    else:
        raise AssertionError("expected validation failure")
