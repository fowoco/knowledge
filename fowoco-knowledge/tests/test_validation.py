from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import yaml

from fowoco_knowledge.repository import KnowledgeRepository
from fowoco_knowledge.validation import KnowledgeValidator, split_codes

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
