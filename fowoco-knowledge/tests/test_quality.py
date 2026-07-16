from __future__ import annotations

import json
from pathlib import Path

from fowoco_knowledge.quality import NoticeQualityEvaluator
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / "data/evaluation/notice_quality_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def test_locked_notice_quality_cases_match_the_policy() -> None:
    evaluator = NoticeQualityEvaluator(KnowledgeRepository(ROOT))
    cases = load_cases()

    assert len(cases) == 12
    for case in cases:
        result = evaluator.evaluate_case(case)
        assert [issue.code for issue in result.issues] == case["expected_issue_codes"]
        assert result.gate == case["expected_gate"]


def test_awkward_but_value_preserving_notice_is_not_blocked() -> None:
    case = next(case for case in load_cases() if case["case_id"] == "NQ-EVAL-002")

    result = NoticeQualityEvaluator(KnowledgeRepository(ROOT)).evaluate_case(case)

    assert result.core_value_preservation_rate == 1.0
    assert result.issues == []
    assert result.gate == "PASS_TO_HR_REVIEW"


def test_changed_deadline_is_a_critical_error() -> None:
    case = next(case for case in load_cases() if case["case_id"] == "NQ-EVAL-004")

    result = NoticeQualityEvaluator(KnowledgeRepository(ROOT)).evaluate_case(case)

    assert result.core_value_changed == 1
    assert result.issues[0].slot_name == "due_at"
    assert result.issues[0].severity == "critical"
    assert result.gate == "BLOCK_AND_REVIEW"
