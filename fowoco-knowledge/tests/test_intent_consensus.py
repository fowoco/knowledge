from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from fowoco_knowledge.intent_consensus import (
    CONSENSUS_COLUMNS,
    ConsensusNotFinalError,
    apply_consensus,
    build_consensus_rows,
    write_consensus_csv,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW_COLUMNS = (
    "review_case_id",
    "source_record_id",
    "review_priority",
    "boundary_flags",
    "hr_input",
    "current_intents_json",
    "reviewer_code",
    "decision",
    "proposed_intents_json",
    "review_note",
)


def _write_review(path: Path, reviewer_code: str, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "reviewer_code": reviewer_code})


def _review_row(
    *,
    decision: str,
    proposed: str = "",
    source_record_id: int = 1,
) -> dict[str, str]:
    return {
        "review_case_id": f"INT-RVW-{source_record_id:04d}",
        "source_record_id": str(source_record_id),
        "review_priority": "HIGH",
        "boundary_flags": "EXTERNAL_EXECUTION",
        "hr_input": "사업장 변경 신청서 접수 확인",
        "current_intents_json": (
            '[{"intent":"EMPLOYMENT_CHANGE","evidence":"사업장 변경 신청서 접수 확인"}]'
        ),
        "reviewer_code": "",
        "decision": decision,
        "proposed_intents_json": proposed,
        "review_note": "",
    }


def test_committed_consensus_is_provisional_and_cannot_be_applied(tmp_path: Path) -> None:
    consensus_path = ROOT / "data/review/intent_boundary_review_consensus.csv"
    with consensus_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert tuple(rows[0]) == CONSENSUS_COLUMNS
    assert len(rows) == 361
    assert Counter(row["agreement_status"] for row in rows) == Counter(
        {
            "ASSUMED_PENDING_B_CONFIRMATION": 335,
            "NEEDS_ADJUDICATION": 26,
        }
    )
    assert all(not row["reviewer_b_decision"] for row in rows)

    with pytest.raises(ConsensusNotFinalError, match="manifest가 원본 반영을 허용하지 않음"):
        apply_consensus(
            consensus_path=consensus_path,
            source_path=ROOT / "data/intent/hr_intent_dataset.jsonl",
            output_path=tmp_path / "should-not-exist.jsonl",
            manifest_path=ROOT / "data/review/intent_boundary_consensus_manifest.yaml",
        )
    with pytest.raises(ConsensusNotFinalError, match="361건"):
        apply_consensus(
            consensus_path=consensus_path,
            source_path=ROOT / "data/intent/hr_intent_dataset.jsonl",
            output_path=tmp_path / "also-blocked.jsonl",
        )
    assert not (tmp_path / "should-not-exist.jsonl").exists()
    assert not (tmp_path / "also-blocked.jsonl").exists()


def test_matching_reviews_are_agreed_and_can_update_a_separate_output(
    tmp_path: Path,
) -> None:
    reviewer_a_path = tmp_path / "a.csv"
    reviewer_b_path = tmp_path / "b.csv"
    proposed = '[{"intent":"DOCUMENT_REQUEST","evidence":"신청서 접수"}]'
    _write_review(reviewer_a_path, "A", [_review_row(decision="CHANGE", proposed=proposed)])
    _write_review(reviewer_b_path, "B", [_review_row(decision="CHANGE", proposed=proposed)])

    rows = build_consensus_rows(reviewer_a_path, reviewer_b_path)
    assert rows[0]["agreement_status"] == "AGREED"
    assert rows[0]["consensus_decision"] == "CHANGE"

    consensus_path = tmp_path / "consensus.csv"
    write_consensus_csv(consensus_path, rows)
    source_path = tmp_path / "source.jsonl"
    source_path.write_text(
        json.dumps(
            {
                "id": 1,
                "hr_input": "사업장 변경 신청서 접수 확인",
                "intents": [
                    {
                        "intent": "EMPLOYMENT_CHANGE",
                        "evidence": "사업장 변경 신청서 접수 확인",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "output.jsonl"
    changed_count, record_count = apply_consensus(
        consensus_path=consensus_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert changed_count == 1
    assert record_count == 1
    assert json.loads(output_path.read_text(encoding="utf-8"))["intents"] == json.loads(proposed)


def test_different_reviews_require_adjudication(tmp_path: Path) -> None:
    reviewer_a_path = tmp_path / "a.csv"
    reviewer_b_path = tmp_path / "b.csv"
    _write_review(reviewer_a_path, "A", [_review_row(decision="KEEP")])
    _write_review(
        reviewer_b_path,
        "B",
        [
            _review_row(
                decision="CHANGE",
                proposed='[{"intent":"DOCUMENT_REQUEST","evidence":"신청서 접수"}]',
            )
        ],
    )

    rows = build_consensus_rows(reviewer_a_path, reviewer_b_path)
    assert rows[0]["agreement_status"] == "DISAGREED"
    assert rows[0]["consensus_decision"] == ""
