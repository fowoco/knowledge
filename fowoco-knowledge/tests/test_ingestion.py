from __future__ import annotations

import csv
from pathlib import Path

import yaml

from fowoco_knowledge.ingestion import (
    transform_manufacturing_industries,
    transform_required_documents,
)
from fowoco_knowledge.repository import KnowledgeRepository

ROOT = Path(__file__).resolve().parents[1]


def test_required_document_transform_keeps_manufacturing_and_all_industries() -> None:
    source = {
        "id": "SRC-TEST",
        "source_version": "20260716",
    }
    rows = [
        {
            "신청서명": "고용변동 신고",
            "필요서류명": "사업자등록증",
            "해당업종": "제조업(필수) 서비스업",
            "샘플서식제공여부": "미제공",
        },
        {
            "신청서명": "출국예정 신고",
            "필요서류명": "티켓",
            "해당업종": "전업종",
            "샘플서식제공여부": "제공",
        },
        {
            "신청서명": "어업 전용",
            "필요서류명": "어업면허",
            "해당업종": "어업(필수)",
            "샘플서식제공여부": "미제공",
        },
    ]

    normalized, _ = transform_required_documents(rows, source)

    assert len(normalized) == 2
    assert normalized[0]["requirement_marker"] == "REQUIRED"
    assert normalized[1]["applicable_scope"] == "ALL_INDUSTRIES"


def test_industry_transform_does_not_export_unreviewed_multilingual_columns() -> None:
    source = {
        "id": "SRC-TEST",
        "source_version": "20260716",
    }
    rows = [
        {
            "대분류 업종명": "제조업",
            "중분류 업종명": "금속가공제품 제조업",
            "사업내용": "금속 부품 제조",
            "사업내용 영어": "Manufacture of metal parts",
            "사업내용 베트남": "검증되지 않은 값",
        },
        {
            "대분류 업종명": "건설업",
            "중분류 업종명": "건설",
            "사업내용": "건설 작업",
            "사업내용 영어": "Construction",
            "사업내용 베트남": "값",
        },
    ]

    normalized, fieldnames = transform_manufacturing_industries(rows, source)

    assert len(normalized) == 1
    assert "business_content_ko" in fieldnames
    assert all("vi" not in field for field in fieldnames)


def test_committed_processed_data_has_reviewed_counts() -> None:
    manifest = yaml.safe_load((ROOT / "data/processed/manifest.yaml").read_text(encoding="utf-8"))
    counts = {item["path"]: item["row_count"] for item in manifest["datasets"]}

    assert counts["required_documents_manufacturing.csv"] == 122
    assert counts["manufacturing_industries.csv"] == 569


def test_employment_change_documents_are_queryable() -> None:
    rows = KnowledgeRepository(ROOT).list_required_documents("외국인 고용변동 등 신고")

    assert len(rows) == 2
    assert {row["document_name"] for row in rows} == {
        "기타",
        "사업장 변경 사유 확인서(사업주용)",
    }
    assert all(row["source_version"] == "20250826" for row in rows)


def test_manufacturing_industry_search_is_scoped() -> None:
    repository = KnowledgeRepository(ROOT)
    rows = repository.search_manufacturing_industries("금속가공제품", limit=5)

    assert len(rows) == 5
    assert all(row["major_category"] == "제조업" for row in rows)
    assert all("금속가공제품" in row["middle_category"] for row in rows)


def test_processed_files_use_utf8_csv() -> None:
    path = ROOT / "data/processed/required_documents_manufacturing.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["source_id"] == "SRC-KEIS-REQUIRED-DOCS"
