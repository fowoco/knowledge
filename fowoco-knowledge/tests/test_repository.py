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
        "SRC-LAW-IMMIGRATION-ACT-25",
        "SRC-KEIS-REQUIRED-DOCS",
        "SRC-HOLIDAY-API",
    }
    assert context["checklist"]["id"] == "CHK-STAY-RENEW-001"
    assert context["administrative_procedure"]["id"] == "PROC-STAY-PERIOD-EXTENSION-001"
    assert any(rule["id"] == "GRD-003" for rule in context["guardrails"])
    assert "due_at" in context["quality_policy"]["immutable_slots"]
    assert context["data_protection"]["llm_boundary"]["allowed_slot_source"] == (
        "workflow_required_and_optional_slots_only"
    )


def test_employment_change_context_uses_one_stop_reporting_procedure() -> None:
    context = KnowledgeRepository(ROOT).compile_context("WF-CHG-001")

    procedure = context["administrative_procedure"]
    assert procedure["submission_pattern"] == "one_stop_report"
    assert procedure["deadline_rule"]["value"] == 15
    assert "SRC-LAW-IMMIGRATION-DECREE-24" in context["workflow"]["source_ids"]
