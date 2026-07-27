from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

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


def test_intent_training_candidates_match_documented_contract() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "data/intent/hr_intent_dataset.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(cases) == 1340
    assert [case["id"] for case in cases] == list(range(1, 1341))


def test_intent_boundary_review_packs_are_independent_and_aligned() -> None:
    reviewer_rows = {}
    for reviewer_code in ("A", "B"):
        with (ROOT / f"data/review/intent_boundary_review_{reviewer_code.lower()}.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            reviewer_rows[reviewer_code] = list(csv.DictReader(handle))

    assert len(reviewer_rows["A"]) == 361
    assert len(reviewer_rows["B"]) == 361
    assert [row["source_record_id"] for row in reviewer_rows["A"]] == [
        row["source_record_id"] for row in reviewer_rows["B"]
    ]
    assert all(row["reviewer_code"] == "A" for row in reviewer_rows["A"])
    assert all(row["reviewer_code"] == "B" for row in reviewer_rows["B"])

    allowed_decisions = {"KEEP", "CHANGE", "EXCLUDE", "NEEDS_DISCUSSION"}
    assert all(row["decision"] in allowed_decisions for row in reviewer_rows["A"])
    assert Counter(row["decision"] for row in reviewer_rows["A"]) == Counter(
        {
            "KEEP": 210,
            "CHANGE": 125,
            "NEEDS_DISCUSSION": 26,
        }
    )
    assert all(
        bool(row["proposed_intents_json"]) == (row["decision"] == "CHANGE")
        for row in reviewer_rows["A"]
    )
    assert all(not row["decision"] for row in reviewer_rows["B"])
