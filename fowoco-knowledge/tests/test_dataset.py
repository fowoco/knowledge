from __future__ import annotations

import csv
from pathlib import Path

from fowoco_knowledge.dataset import DatasetManager
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
