import json
from pathlib import Path

from signal_space import SPEC_VERSION, load_document, validate_document


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
    assert any("trainable_model.lifecycle" in node.allowed_modules for node in decisions)


def test_rejects_unknown_edge_endpoint() -> None:
    data = json.loads((SPEC_FIXTURES / "agent_doc_supervisor.json").read_text())
    data["graph"]["edges"][0]["from"] = "missing"

    try:
        validate_document(data)
    except ValueError as error:
        assert "unknown endpoint" in str(error)
    else:
        raise AssertionError("expected validation failure")
