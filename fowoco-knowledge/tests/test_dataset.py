from __future__ import annotations

import csv
from pathlib import Path

from fowoco_knowledge.dataset import DatasetManager, ReviewComparator
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_report_distinguishes_smoke_and_training_readiness() -> None:
    report = DatasetManager(KnowledgeRepository(ROOT)).build_report()

    assert report["representative_model"] == "INTENT_DOMAIN_MULTI_LABEL"
    assert report["seed"]["rows"] == 40
    assert report["seed"]["gold_rows"] == 0
    assert report["seed"]["multi_intent_rows"] == 6
    assert report["seed"]["workflow_expert_review_required_rows"] == 29
    assert report["evaluation"]["rows"] == 18
    assert report["quality"]["seed_evaluation_overlap"] == []
    assert report["quality"]["pii_pattern_hits"] == []
    assert report["notice_quality"]["rows"] == 12
    assert report["notice_quality"]["locked"] is True
    assert report["notice_quality"]["contract_mismatches"] == []
    assert report["notice_quality"]["contract_accuracy"] == 1.0
    assert report["notice_quality"]["injected_error_cases"] == 9
    assert report["notice_quality"]["interpretation"] == (
        "detector_regression_fixture_not_model_performance"
    )
    assert report["notice_quality"]["gate_distribution"] == {
        "BLOCK_AND_REVIEW": 9,
        "PASS_TO_HR_REVIEW": 3,
    }
    assert report["readiness"]["smoke_evaluation_ready"] is True
    assert report["readiness"]["gold_v1_ready"] is False
    assert report["readiness"]["classification_baseline_ready"] is False


def test_blind_review_queue_does_not_expose_proposed_labels(tmp_path: Path) -> None:
    output = tmp_path / "reviewer-a.csv"
    manager = DatasetManager(KnowledgeRepository(ROOT))

    count = manager.write_blind_review_queue("REV-A", output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert count == 40
    assert len(rows) == 40
    assert {row["reviewer_code"] for row in rows} == {"REV-A"}
    assert all(row["hr_utterance"] for row in rows)
    assert all(row["intents"] == "" for row in rows)
    assert all(row["domains"] == "" for row in rows)
    assert all(row["workflow_ids"] == "" for row in rows)
    assert all(row["slots_json"] == "{}" for row in rows)


def test_review_comparison_reports_pending_rows(tmp_path: Path) -> None:
    manager = DatasetManager(KnowledgeRepository(ROOT))
    reviewer_a = tmp_path / "reviewer-a.csv"
    reviewer_b = tmp_path / "reviewer-b.csv"
    manager.write_blind_review_queue("REV-A", reviewer_a)
    manager.write_blind_review_queue("REV-B", reviewer_b)

    report = ReviewComparator(KnowledgeRepository(ROOT)).compare(reviewer_a, reviewer_b)

    assert report["completed_rows"] == 0
    assert report["pending_rows"] == 40
    assert report["disagreement_rows"] == 0
    assert report["label_guide_ready"] is False


def test_review_comparison_writes_only_disagreements(tmp_path: Path) -> None:
    manager = DatasetManager(KnowledgeRepository(ROOT))
    reviewer_a = tmp_path / "reviewer-a.csv"
    reviewer_b = tmp_path / "reviewer-b.csv"
    output = tmp_path / "disagreements.csv"
    manager.write_blind_review_queue("REV-A", reviewer_a)
    manager.write_blind_review_queue("REV-B", reviewer_b)

    for path, second_intent in (
        (reviewer_a, "EXPIRY_RENEWAL"),
        (reviewer_b, "DOCUMENT_REQUEST"),
    ):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames
        for row in rows[:2]:
            row["intents"] = "WORKER_ONBOARDING"
            row["domains"] = "WORKER_PROFILE"
            row["decision"] = "APPROVE"
        rows[1]["intents"] = second_intent
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    report = ReviewComparator(KnowledgeRepository(ROOT)).compare(
        reviewer_a,
        reviewer_b,
        output,
    )

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        disagreements = list(csv.DictReader(handle))
    assert report["completed_rows"] == 2
    assert report["pending_rows"] == 38
    assert report["agreement"]["intent_exact_match"] == 0.5
    assert report["disagreement_rows"] == 1
    assert len(disagreements) == 1
    assert disagreements[0]["disagreement_fields"] == "intents"
