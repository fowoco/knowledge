from __future__ import annotations

from pathlib import Path

import yaml

from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def test_lists_mvp_workflows() -> None:
    workflows = KnowledgeRepository(ROOT).list_workflows()
    assert len(workflows) == 9
    assert {workflow["id"] for workflow in workflows} >= {
        "WF-STY-001",
        "WF-STY-EXC-001",
        "WF-DOC-001",
        "WF-PAY-001",
        "WF-CHG-001",
    }


def test_compiled_context_is_cross_linked() -> None:
    context = KnowledgeRepository(ROOT).compile_context("WF-STY-001")
    assert context["intent"]["id"] == "EXPIRY_RENEWAL"
    assert context["slot_policy"]["required"] == ["worker_id", "due_at"]
    worker_contract = context["slot_policy"]["slot_contracts"]["worker_id"]
    assert worker_contract["display_name_ko"] == "대상 근로자"
    assert worker_contract["required"] is True
    assert worker_contract["source_priority"][0] == "HR_CONFIRMED_PROFILE"
    assert "UNIQUE_SUBJECT_MATCH" in worker_contract["validation_rules"]
    assert context["slot_policy"]["optional"] == [
        "stay_expiry_date",
        "passport_status",
        "arc_status",
    ]
    assert (
        context["slot_policy"]["slot_contracts"]["passport_status"]["responsible_actor"] == "SYSTEM"
    )
    assert context["slot_policy"]["slot_contracts"]["arc_status"]["required"] is False
    assert {source["id"] for source in context["official_sources"]} == {
        "SRC-HIKOREA",
        "SRC-LAW-IMMIGRATION-ACT-25",
        "SRC-KEIS-REQUIRED-DOCS",
        "SRC-HOLIDAY-API",
    }
    assert context["checklist"]["id"] == "CHK-STAY-RENEW-001"
    assert context["administrative_procedure"]["id"] == "PROC-STAY-PERIOD-EXTENSION-001"
    assert any(rule["id"] == "GRD-003" for rule in context["guardrails"])


def test_employment_change_context_uses_one_stop_reporting_procedure() -> None:
    context = KnowledgeRepository(ROOT).compile_context("WF-CHG-001")

    procedure = context["administrative_procedure"]
    assert procedure["submission_pattern"] == "one_stop_report"
    assert procedure["deadline_rule"]["value"] == 15
    assert "SRC-LAW-IMMIGRATION-DECREE-24" in context["workflow"]["source_ids"]


def test_expiry_renewal_case_template_keeps_full_business_order() -> None:
    template = KnowledgeRepository(ROOT).get_case_template("CASE-EXPIRY-RENEWAL-001")

    assert template["workflow_ids"] == ["WF-CON-001", "WF-DOC-001", "WF-STY-001"]
    assert [task["key"] for task in template["tasks"]] == [
        "recontract",
        "identity_documents",
        "employment_period_extension",
        "stay_period_extension",
    ]
    assert template["tasks"][1]["activation"] == {
        "mode": "MISSING_ANY",
        "field_keys": ["passport_status", "arc_status"],
    }
    assert template["tasks"][2]["depends_on"] == ["recontract"]
    assert template["tasks"][3]["depends_on"] == ["employment_period_extension"]
    assert len(template["tasks"][0]["checklist_items"]) == 6
    identity_checklists = template["tasks"][1]["checklist_items"]
    assert [item["item_code"] for item in identity_checklists if item["required"]] == [
        "WORKER_DOCUMENT_REQUEST_APPROVED"
    ]
    assert [item["item_code"] for item in identity_checklists if not item["required"]] == [
        "SECURE_LINK_DELIVERY_RECORDED",
        "IDENTITY_DOCUMENTS_SUBMITTED",
        "OCR_RESULT_HR_REVIEWED",
    ]


def test_expiry_renewal_demo_pack_matches_case_template() -> None:
    repository = KnowledgeRepository(ROOT)
    template = repository.get_case_template("CASE-EXPIRY-RENEWAL-001")
    demo = yaml.safe_load(
        (ROOT / "data/demo/expiry_renewal_golden.yaml").read_text(encoding="utf-8")
    )

    assert demo["contains_real_personal_data"] is False
    assert demo["case_template_id"] == template["id"]
    assert demo["workflow_ids"] == template["workflow_ids"]
    assert [task["task_type"] for task in demo["expected_case"]["tasks"]] == [
        task["task_type"] for task in template["tasks"]
    ]
    assert all(
        value is False for value in demo["guardrails"].values()
    )
