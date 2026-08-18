from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import yaml

from fowoco_knowledge.repository import KnowledgeRepository
from fowoco_knowledge.validation import (
    KnowledgeValidator,
    find_internal_keys,
    read_git_lfs_pointer,
    split_codes,
)

ROOT = Path(__file__).resolve().parents[1]


def test_all_knowledge_files_are_valid() -> None:
    errors = KnowledgeValidator(KnowledgeRepository(ROOT)).validate_all()
    assert errors == []


def test_seed_has_coverage_but_is_not_claimed_as_training_ready() -> None:
    with (ROOT / "data/seed/gold_seed.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 40
    intent_counts = Counter(intent for row in rows for intent in split_codes(row["intents"]))
    for intent in {
        "WORKER_ONBOARDING",
        "EXPIRY_RENEWAL",
        "DOCUMENT_REQUEST",
        "PAYROLL_EXPLANATION",
        "WORK_INSTRUCTION",
        "EMPLOYMENT_CHANGE",
    }:
        assert intent_counts[intent] >= 5
    assert all(row["review_status"] == "DRAFT" for row in rows)


def test_evaluation_set_is_separate_and_has_compound_cases() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "data/evaluation/golden_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(cases) == 18
    assert any(len(case["expected_intents"]) > 1 for case in cases)
    assert any(case["expected_action"] == "OUT_OF_SCOPE" for case in cases)


def test_catalog_e2e_candidates_cover_subject_notice_and_guardrail_boundaries() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "data/evaluation/e2e_catalog_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(cases) == 16
    tags = {tag for case in cases for tag in case["scenario_tags"]}
    assert {
        "SPACING_VARIANT",
        "ROMANIZED_ALIAS",
        "PHONETIC_ALIAS",
        "AMBIGUOUS_NAME",
        "COMPOSITE_REQUEST",
        "BOUNDARY_INTENT",
        "OUT_OF_SCOPE",
        "VIETNAMESE_NOTICE",
        "EXTERNAL_EXECUTION",
    } <= tags
    assert any(notice["locale"] == "vi-VN" for case in cases for notice in case["worker_notices"])
    assert all(not case["expected_guardrails"]["automatic_external_submission"] for case in cases)
    assert all(not case["expected_guardrails"]["automatic_worker_message_send"] for case in cases)
    assert all(not case["expected_guardrails"]["automatic_completion"] for case in cases)
    assert all(case["review"]["adjudication"] == "PENDING" for case in cases)
    renewal_chain = next(case for case in cases if case["case_id"] == "E2E-011")
    assert renewal_chain["expected_intents"] == ["EXPIRY_RENEWAL"]
    assert renewal_chain["expected_workflow_ids"] == ["WF-CON-001", "WF-STY-001"]
    assert renewal_chain["expected_action"] == "SPLIT_AND_CONFIRM"
    expired_cases = [case for case in cases if "WF-STY-EXC-001" in case["expected_workflow_ids"]]
    assert len(expired_cases) == 5
    assert {case["expected_slots"]["stay_verification_status"] for case in expired_cases} == {
        "APPROVED",
        "APPLICATION_PENDING",
        "UNKNOWN",
        "NOT_APPLIED",
        "EMPLOYMENT_ENDED",
    }
    employment_ended = next(
        case
        for case in expired_cases
        if case["expected_slots"]["stay_verification_status"] == "EMPLOYMENT_ENDED"
    )
    assert employment_ended["expected_workflow_ids"] == ["WF-STY-EXC-001", "WF-CHG-001"]


def test_internal_key_leak_detector_matches_machine_identifiers_only() -> None:
    internal_keys = {"worker_id", "WF-DOC-001", "DOCUMENT_REQUEST"}

    assert find_internal_keys("worker_id를 근로자에게 보여주면 안 됩니다.", internal_keys) == [
        "worker_id"
    ]
    assert find_internal_keys("여권 사본을 보안 링크에 제출해 주세요.", internal_keys) == []


def test_final_intent_training_data_matches_documented_contract() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "data/intent/hr_intent_dataset_final.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(cases) == 1340
    assert [case["id"] for case in cases] == list(range(1, 1341))


def test_intent_split_uses_final_data_without_overlap_or_missing_ids() -> None:
    manifest = yaml.safe_load(
        (ROOT / "data/intent/splits/manifest.yaml").read_text(encoding="utf-8")
    )
    final_cases = [
        json.loads(line)
        for line in (ROOT / manifest["source"]["path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    train_ids = {
        int(case_id)
        for case_id in (ROOT / manifest["outputs"]["train"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
        if case_id.strip()
    }
    validation_ids = {
        int(case_id)
        for case_id in (ROOT / manifest["outputs"]["validation"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
        if case_id.strip()
    }

    assert len(train_ids) == 1072
    assert len(validation_ids) == 268
    assert train_ids.isdisjoint(validation_ids)
    assert train_ids | validation_ids == {case["id"] for case in final_cases}


def test_model_artifact_manifest_pins_snapshot_and_runtime_ownership() -> None:
    manifest = yaml.safe_load(
        (ROOT / "hr-intent-service/models/artifact-manifest.yaml").read_text(encoding="utf-8")
    )

    assert manifest["canonical_distribution"] == "HUGGING_FACE_PRIVATE"
    assert manifest["training_dataset"]["version"] == "1.2.0"
    assert manifest["training_dataset"]["matches_current_dataset"] is False
    assert {model["runtime_owner"] for model in manifest["models"]} == {"fowoco/ai"}
    assert {model["revision_policy"] for model in manifest["models"]} == {
        "PIN_COMMIT_SHA_AT_DEPLOYMENT"
    }
    assert all(model["snapshot_files"] for model in manifest["models"])
    assert manifest["secret_policy"]["repository_storage_forbidden"] is True


def test_git_lfs_pointer_exposes_artifact_checksum_and_size(tmp_path: Path) -> None:
    pointer = tmp_path / "model.safetensors"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:abf0d7d3bdb89a5ac34abc8cc41a77396bf024f02de6939591b3c555446bd48b\n"
        "size 442518124\n",
        encoding="ascii",
    )

    assert read_git_lfs_pointer(pointer) == (
        "abf0d7d3bdb89a5ac34abc8cc41a77396bf024f02de6939591b3c555446bd48b",
        442518124,
    )


def test_six_workflow_runtime_profiles_have_three_e2e_paths_each() -> None:
    runtime = yaml.safe_load((ROOT / "knowledge/workflow_runtime.yaml").read_text(encoding="utf-8"))
    cases = [
        json.loads(line)
        for line in (ROOT / "data/evaluation/workflow_runtime_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(runtime["profiles"]) == 6
    assert len(cases) == 18
    for profile in runtime["profiles"]:
        profile_cases = [case for case in cases if case["profile_id"] == profile["id"]]
        assert {case["path"] for case in profile_cases} == {
            "HAPPY_PATH",
            "MISSING_INPUT",
            "MANUAL_REVIEW",
        }
        assert all(stage["completion_evidence"] for stage in profile["stages"])
    assert all(not case["guardrails"]["automatic_external_submission"] for case in cases)
    assert all(not case["guardrails"]["automatic_completion"] for case in cases)
