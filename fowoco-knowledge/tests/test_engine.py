from __future__ import annotations

import json
from pathlib import Path

from fowoco_knowledge.engine import RequestEvaluator
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def test_complete_document_request_creates_draft() -> None:
    evaluator = RequestEvaluator(KnowledgeRepository(ROOT))
    result = evaluator.evaluate(load_example("complete_document_request.json"))
    assert result.missing_slots == []
    assert result.ambiguities == []
    assert result.action == "CREATE_DRAFT_TASK"
    assert result.hr_approval_required is True


def test_ambiguous_request_returns_targeted_questions() -> None:
    evaluator = RequestEvaluator(KnowledgeRepository(ROOT))
    result = evaluator.evaluate(load_example("ambiguous_document_request.json"))
    assert result.action == "REQUEST_CLARIFICATION"
    assert set(result.missing_slots) == {
        "worker_id",
        "document_type",
        "due_at",
        "submission_channel",
    }
    assert {match.category for match in result.ambiguities} == {
        "TIME",
        "LOCATION",
        "OBJECT",
    }


def test_high_risk_request_always_requires_hr_review() -> None:
    evaluator = RequestEvaluator(KnowledgeRepository(ROOT))
    result = evaluator.evaluate(load_example("high_risk_stay_request.json"))
    assert result.action == "REQUIRE_HR_REVIEW"
    assert result.hr_approval_required is True


def test_low_intent_confidence_requests_confirmation() -> None:
    request = load_example("complete_document_request.json")
    request["intent_candidates"][0]["confidence"] = 0.54
    evaluator = RequestEvaluator(KnowledgeRepository(ROOT))
    result = evaluator.evaluate(request)
    assert result.action == "REQUEST_CLASSIFICATION_CONFIRMATION"
