from __future__ import annotations

from pathlib import Path

from fowoco_knowledge.repository import KnowledgeRepository


ROOT = Path(__file__).resolve().parents[1]


def test_lists_mvp_workflows() -> None:
    workflows = KnowledgeRepository(ROOT).list_workflows()
    assert len(workflows) == 8
    assert {workflow["id"] for workflow in workflows} >= {
        "WF-STY-001",
        "WF-DOC-001",
        "WF-PAY-001",
        "WF-CHG-001",
    }


def test_compiled_context_is_cross_linked() -> None:
    context = KnowledgeRepository(ROOT).compile_context("WF-STY-001")
    assert context["intent"]["id"] == "EXPIRY_RENEWAL"
    assert context["slot_policy"]["required"] == ["worker_id", "due_at"]
    assert {source["id"] for source in context["official_sources"]} == {
        "SRC-HIKOREA",
        "SRC-KEIS-REQUIRED-DOCS",
        "SRC-HOLIDAY-API",
    }
    assert context["checklist"]["id"] == "CHK-STAY-RENEW-001"
    assert any(rule["id"] == "GRD-003" for rule in context["guardrails"])
