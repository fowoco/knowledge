from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

CONSENSUS_COLUMNS = (
    "review_case_id",
    "source_record_id",
    "review_priority",
    "boundary_flags",
    "hr_input",
    "current_intents_json",
    "reviewer_a_decision",
    "reviewer_a_proposed_intents_json",
    "reviewer_b_decision",
    "reviewer_b_proposed_intents_json",
    "agreement_status",
    "consensus_decision",
    "final_intents_json",
    "consensus_note",
)

FINAL_AGREEMENT_STATUS = "AGREED"
REVIEW_DECISIONS = {"KEEP", "CHANGE", "EXCLUDE", "NEEDS_DISCUSSION"}


class ConsensusNotFinalError(ValueError):
    """Raised when provisional or unresolved consensus is applied."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_json(raw: str, field: str, review_case_id: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{review_case_id}: invalid {field}") from error


def selected_intents(row: dict[str, str]) -> list[dict[str, Any]] | None:
    decision = row["decision"].strip()
    if decision == "KEEP":
        return parse_json(
            row["current_intents_json"], "current_intents_json", row["review_case_id"]
        )
    if decision == "CHANGE":
        return parse_json(
            row["proposed_intents_json"], "proposed_intents_json", row["review_case_id"]
        )
    return None


def _aligned_review_rows(
    reviewer_a_path: Path,
    reviewer_b_path: Path,
) -> list[tuple[dict[str, str], dict[str, str]]]:
    reviewer_a_rows = read_csv_rows(reviewer_a_path)
    reviewer_b_by_id = {row["review_case_id"]: row for row in read_csv_rows(reviewer_b_path)}
    if len(reviewer_b_by_id) != len(reviewer_a_rows):
        raise ValueError("Reviewer A/B row counts or review_case_id values differ")

    aligned: list[tuple[dict[str, str], dict[str, str]]] = []
    immutable_fields = (
        "source_record_id",
        "review_priority",
        "boundary_flags",
        "hr_input",
        "current_intents_json",
    )
    for reviewer_a in reviewer_a_rows:
        review_case_id = reviewer_a["review_case_id"]
        reviewer_b = reviewer_b_by_id.get(review_case_id)
        if reviewer_b is None:
            raise ValueError(f"{review_case_id}: missing Reviewer B row")
        if reviewer_a["reviewer_code"] != "A" or reviewer_b["reviewer_code"] != "B":
            raise ValueError(f"{review_case_id}: reviewer_code must be A/B")
        for field in immutable_fields:
            if reviewer_a[field] != reviewer_b[field]:
                raise ValueError(f"{review_case_id}: Reviewer A/B {field} differs")
        aligned.append((reviewer_a, reviewer_b))
    return aligned


def build_consensus_rows(
    reviewer_a_path: Path,
    reviewer_b_path: Path,
    *,
    assume_b_agrees: bool = False,
) -> list[dict[str, str]]:
    consensus_rows: list[dict[str, str]] = []
    for reviewer_a, reviewer_b in _aligned_review_rows(reviewer_a_path, reviewer_b_path):
        review_case_id = reviewer_a["review_case_id"]
        decision_a = reviewer_a["decision"].strip()
        decision_b = reviewer_b["decision"].strip()
        if decision_a not in REVIEW_DECISIONS:
            raise ValueError(f"{review_case_id}: Reviewer A decision is missing or invalid")
        if decision_b and decision_b not in REVIEW_DECISIONS:
            raise ValueError(f"{review_case_id}: Reviewer B decision is invalid")
        intents_a = selected_intents(reviewer_a)
        intents_b = selected_intents(reviewer_b) if decision_b else None
        consensus_decision = ""
        final_intents = ""

        if not decision_b:
            if decision_a == "NEEDS_DISCUSSION":
                agreement_status = "NEEDS_ADJUDICATION"
                consensus_note = "Reviewer A가 논의 필요로 판정함; Reviewer B 및 합의 검수 필요"
            elif assume_b_agrees:
                agreement_status = "ASSUMED_PENDING_B_CONFIRMATION"
                consensus_decision = decision_a
                final_intents = compact_json(intents_a) if intents_a is not None else ""
                consensus_note = (
                    "Reviewer A 판정을 임시 최종안으로 제시; Reviewer B 확인 전 적용 금지"
                )
            else:
                agreement_status = "AWAITING_REVIEWER_B"
                consensus_note = "Reviewer B 독립 검수 대기"
        elif decision_a == "NEEDS_DISCUSSION" or decision_b == "NEEDS_DISCUSSION":
            agreement_status = "NEEDS_ADJUDICATION"
            consensus_note = "한 명 이상의 검수자가 논의 필요로 판정함"
        elif decision_a == decision_b and intents_a == intents_b:
            agreement_status = FINAL_AGREEMENT_STATUS
            consensus_decision = decision_a
            final_intents = compact_json(intents_a) if intents_a is not None else ""
            consensus_note = "Reviewer A/B 독립 판정 일치"
        else:
            agreement_status = "DISAGREED"
            consensus_note = "Reviewer A/B 판정 또는 제안 Intent 불일치; 합의 검수 필요"

        consensus_rows.append(
            {
                "review_case_id": review_case_id,
                "source_record_id": reviewer_a["source_record_id"],
                "review_priority": reviewer_a["review_priority"],
                "boundary_flags": reviewer_a["boundary_flags"],
                "hr_input": reviewer_a["hr_input"],
                "current_intents_json": compact_json(
                    parse_json(
                        reviewer_a["current_intents_json"],
                        "current_intents_json",
                        review_case_id,
                    )
                ),
                "reviewer_a_decision": decision_a,
                "reviewer_a_proposed_intents_json": (
                    compact_json(
                        parse_json(
                            reviewer_a["proposed_intents_json"],
                            "proposed_intents_json",
                            review_case_id,
                        )
                    )
                    if reviewer_a["proposed_intents_json"].strip()
                    else ""
                ),
                "reviewer_b_decision": decision_b,
                "reviewer_b_proposed_intents_json": (
                    compact_json(
                        parse_json(
                            reviewer_b["proposed_intents_json"],
                            "proposed_intents_json",
                            review_case_id,
                        )
                    )
                    if reviewer_b["proposed_intents_json"].strip()
                    else ""
                ),
                "agreement_status": agreement_status,
                "consensus_decision": consensus_decision,
                "final_intents_json": final_intents,
                "consensus_note": consensus_note,
            }
        )
    return consensus_rows


def write_consensus_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CONSENSUS_COLUMNS,
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_consensus_manifest(
    *,
    root: Path,
    reviewer_a_path: Path,
    reviewer_b_path: Path,
    output_path: Path,
    rows: list[dict[str, str]],
    assume_b_agrees: bool,
) -> dict[str, Any]:
    status_counts = Counter(row["agreement_status"] for row in rows)
    reviewer_b_completed = all(row["reviewer_b_decision"] for row in rows)
    source_apply_allowed = (
        bool(rows) and reviewer_b_completed and set(status_counts) == {FINAL_AGREEMENT_STATUS}
    )
    if source_apply_allowed:
        status = "final_agreed"
    elif reviewer_b_completed:
        status = "awaiting_adjudication"
    elif assume_b_agrees:
        status = "provisional_assuming_reviewer_b_agreement"
    else:
        status = "awaiting_reviewer_b"

    review_manifest_path = root / "data/review/intent_boundary_review_manifest.yaml"
    with review_manifest_path.open("r", encoding="utf-8") as handle:
        review_manifest = yaml.safe_load(handle)

    block_reasons = []
    if not reviewer_b_completed:
        block_reasons.append("Reviewer B 판정이 모든 행에 기록되지 않음")
    if any(row["agreement_status"] != FINAL_AGREEMENT_STATUS for row in rows):
        block_reasons.append("AGREED가 아닌 consensus 행이 존재함")

    return {
        "consensus_pack_id": "FOWOCO-INTENT-BOUNDARY-CONSENSUS",
        "version": "0.1.0",
        "status": status,
        "rule_version": review_manifest["rule_version"],
        "depends_on_pr": 31,
        "source": review_manifest["source"],
        "inputs": [
            {
                "reviewer_code": "A",
                "path": str(reviewer_a_path.relative_to(root)),
                "sha256": file_sha256(reviewer_a_path),
                "completed": all(row["reviewer_a_decision"] for row in rows),
            },
            {
                "reviewer_code": "B",
                "path": str(reviewer_b_path.relative_to(root)),
                "sha256": file_sha256(reviewer_b_path),
                "completed": reviewer_b_completed,
            },
        ],
        "generation": {
            "mode": (
                "provisional_assume_b_agrees" if assume_b_agrees else "compare_submitted_reviews"
            ),
            "candidate_count": len(rows),
            "agreement_status_counts": dict(sorted(status_counts.items())),
        },
        "output": {
            "path": str(output_path.relative_to(root)),
            "row_count": len(rows),
            "sha256": file_sha256(output_path),
        },
        "source_application": {
            "allowed": source_apply_allowed,
            "block_reasons": block_reasons,
        },
        "limitations": [
            "ASSUMED_PENDING_B_CONFIRMATION은 Reviewer B의 실제 판정이 아님",
            "NEEDS_ADJUDICATION과 DISAGREED는 합의 검수 전 원본에 반영하지 않음",
            "source_application.allowed가 true인 최종 합의본만 원본 반영에 사용함",
        ],
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, allow_unicode=True, sort_keys=False)


def apply_consensus(
    *,
    consensus_path: Path,
    source_path: Path,
    output_path: Path,
    manifest_path: Path | None = None,
    allow_exclude: bool = False,
) -> tuple[int, int]:
    if source_path.resolve() == output_path.resolve():
        raise ConsensusNotFinalError("원본과 별도인 --output 경로가 필요함")
    if manifest_path is not None:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle)
        if not manifest["source_application"]["allowed"]:
            raise ConsensusNotFinalError("consensus manifest가 원본 반영을 허용하지 않음")
        if file_sha256(consensus_path) != manifest["output"]["sha256"]:
            raise ConsensusNotFinalError("consensus CSV checksum이 manifest와 다름")
        if file_sha256(source_path) != manifest["source"]["sha256"]:
            raise ConsensusNotFinalError("원본 Intent checksum이 manifest와 다름")

    rows = read_csv_rows(consensus_path)
    unresolved = [
        row["review_case_id"]
        for row in rows
        if not row["reviewer_b_decision"] or row["agreement_status"] != FINAL_AGREEMENT_STATUS
    ]
    if unresolved:
        preview = ", ".join(unresolved[:5])
        raise ConsensusNotFinalError(
            f"Reviewer B 미확인 또는 미합의 {len(unresolved)}건: {preview}"
        )

    consensus_by_source_id = {int(row["source_record_id"]): row for row in rows}
    source_cases = [
        json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line
    ]
    source_ids = {case["id"] for case in source_cases}
    missing_ids = sorted(set(consensus_by_source_id) - source_ids)
    if missing_ids:
        raise ValueError(f"Consensus source IDs not found: {missing_ids[:5]}")

    changed_count = 0
    output_cases: list[dict[str, Any]] = []
    for case in source_cases:
        consensus = consensus_by_source_id.get(case["id"])
        if consensus is None or consensus["consensus_decision"] == "KEEP":
            output_cases.append(case)
            continue
        if consensus["consensus_decision"] == "CHANGE":
            updated = dict(case)
            updated["intents"] = parse_json(
                consensus["final_intents_json"],
                "final_intents_json",
                consensus["review_case_id"],
            )
            output_cases.append(updated)
            changed_count += 1
            continue
        if consensus["consensus_decision"] == "EXCLUDE":
            if not allow_exclude:
                raise ConsensusNotFinalError(
                    f"{consensus['review_case_id']}: EXCLUDE requires --allow-exclude"
                )
            changed_count += 1
            continue
        raise ValueError(
            f"{consensus['review_case_id']}: invalid consensus_decision "
            f"{consensus['consensus_decision']}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for case in output_cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    return changed_count, len(output_cases)
