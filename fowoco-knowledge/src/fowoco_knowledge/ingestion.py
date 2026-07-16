from __future__ import annotations

import csv
import hashlib
import re
import shutil
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class SourceValidationError(ValueError):
    """Raised when an official source no longer matches its reviewed snapshot."""


@dataclass(frozen=True)
class ProcessedDataset:
    source_id: str
    output: str
    row_count: int
    sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(part.strip() for part in parts)
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12].upper()}"


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def transform_required_documents(
    rows: list[dict[str, str]], source: dict[str, Any]
) -> tuple[list[dict[str, str]], list[str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        industry_text = _clean(row["해당업종"])
        manufacturing_match = re.search(r"(?:^|\s)제조업(?:\(필수\))?(?:\s|$)", industry_text)
        is_all_industries = industry_text == "전업종"
        if not manufacturing_match and not is_all_industries:
            continue

        application_name = _clean(row["신청서명"])
        document_name = _clean(row["필요서류명"])
        requirement_marker = (
            "REQUIRED" if "제조업(필수)" in industry_text else "OFFICIAL_CONFIRMATION_REQUIRED"
        )
        output.append(
            {
                "requirement_id": stable_id("REQ", application_name, document_name, industry_text),
                "application_name": application_name,
                "document_name": document_name,
                "applicable_scope": "ALL_INDUSTRIES" if is_all_industries else "MANUFACTURING",
                "requirement_marker": requirement_marker,
                "sample_form_available": (
                    "true" if _clean(row["샘플서식제공여부"]) == "제공" else "false"
                ),
                "source_industry_text": industry_text,
                "source_id": source["id"],
                "source_version": source["source_version"],
            }
        )

    fieldnames = [
        "requirement_id",
        "application_name",
        "document_name",
        "applicable_scope",
        "requirement_marker",
        "sample_form_available",
        "source_industry_text",
        "source_id",
        "source_version",
    ]
    output.sort(key=lambda item: (item["application_name"], item["document_name"]))
    return output, fieldnames


def transform_manufacturing_industries(
    rows: list[dict[str, str]], source: dict[str, Any]
) -> tuple[list[dict[str, str]], list[str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if _clean(row["대분류 업종명"]) != "제조업":
            continue
        middle_category = _clean(row["중분류 업종명"])
        business_content_ko = _clean(row["사업내용"])
        business_content_en = _clean(row["사업내용 영어"])
        output.append(
            {
                "industry_id": stable_id("IND", "제조업", middle_category, business_content_ko),
                "major_category": "제조업",
                "middle_category": middle_category,
                "business_content_ko": business_content_ko,
                "business_content_en": business_content_en,
                "source_id": source["id"],
                "source_version": source["source_version"],
            }
        )

    fieldnames = [
        "industry_id",
        "major_category",
        "middle_category",
        "business_content_ko",
        "business_content_en",
        "source_id",
        "source_version",
    ]
    output.sort(key=lambda item: (item["middle_category"], item["business_content_ko"]))
    return output, fieldnames


TRANSFORMS: dict[
    str,
    Callable[
        [list[dict[str, str]], dict[str, Any]],
        tuple[list[dict[str, str]], list[str]],
    ],
] = {
    "required_documents_manufacturing": transform_required_documents,
    "manufacturing_industries": transform_manufacturing_industries,
}


class OfficialDataPipeline:
    """Download, pin, and normalize reviewed public-data snapshots."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        manifest_path = project_root / "data/external/source_manifest.yaml"
        with manifest_path.open("r", encoding="utf-8") as handle:
            self.manifest = yaml.safe_load(handle)

    def sync(
        self,
        cache_dir: Path,
        output_dir: Path,
        *,
        download_missing: bool = True,
    ) -> list[ProcessedDataset]:
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[ProcessedDataset] = []

        for source in self.manifest["sources"]:
            raw_path = cache_dir / source["filename"]
            if not raw_path.exists():
                if not download_missing:
                    raise FileNotFoundError(f"공식 원본이 없습니다: {raw_path}")
                self._download(source["download_url"], raw_path)

            self._validate_raw_source(raw_path, source)
            rows = self._read_rows(raw_path, source["encoding"])
            transform = TRANSFORMS[source["transform"]]
            normalized, fieldnames = transform(rows, source)
            output_path = output_dir / source["output"]
            self._write_rows(output_path, normalized, fieldnames)
            results.append(
                ProcessedDataset(
                    source_id=source["id"],
                    output=source["output"],
                    row_count=len(normalized),
                    sha256=file_sha256(output_path),
                )
            )

        self._write_processed_manifest(output_dir, results)
        return results

    @staticmethod
    def _download(url: str, destination: Path) -> None:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "FOWOCO-Knowledge/0.2 (+official-data-sync)"},
        )
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _validate_raw_source(self, path: Path, source: dict[str, Any]) -> None:
        actual_hash = file_sha256(path)
        if actual_hash != source["sha256"]:
            raise SourceValidationError(
                f"{source['id']} checksum mismatch: {actual_hash} != {source['sha256']}"
            )

        rows = self._read_rows(path, source["encoding"])
        if len(rows) != source["expected_rows"]:
            raise SourceValidationError(
                f"{source['id']} row count mismatch: {len(rows)} != {source['expected_rows']}"
            )
        actual_columns = list(rows[0]) if rows else []
        if actual_columns != source["expected_columns"]:
            raise SourceValidationError(f"{source['id']} columns changed: {actual_columns}")

    @staticmethod
    def _read_rows(path: Path, encoding: str) -> list[dict[str, str]]:
        with path.open("r", encoding=encoding, newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def _write_processed_manifest(self, output_dir: Path, results: list[ProcessedDataset]) -> None:
        payload = {
            "version": self.manifest["version"],
            "source_verified_at": self.manifest["verified_at"],
            "datasets": [
                {
                    "source_id": item.source_id,
                    "path": item.output,
                    "row_count": item.row_count,
                    "sha256": item.sha256,
                }
                for item in results
            ],
        }
        manifest_path = output_dir / "manifest.yaml"
        with manifest_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
