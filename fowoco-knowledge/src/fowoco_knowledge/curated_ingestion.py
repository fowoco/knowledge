"""
fowoco-knowledge/data/curated/required_documents_manual_raw를 읽어
requirement_id를 ingestion.py 의 stable_id/_clean 과 동일한 규칙으로 채운 뒤
data/processed/required_documents_manual.csv 로 생성(재실행 시 overwrite)하는 코드입니다.

required_documents_manual_raw.csv 파일은 사람이 직접 작성하는 파일이며 required_id만 비워둔 형태입니다.

"""

from __future__ import annotations
 
import argparse
import csv
from datetime import date
from pathlib import Path
from .ingestion import _clean, stable_id

# --- 고정 설정 -------------------------------------------------------------
# 이 파일 위치: <project_root>/src/fowoco_knowledge/curated_ingestion.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = PROJECT_ROOT / "data" / "curated" / "required_documents_manual_raw.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "required_documents_manual.csv"
SOURCE_ID = "SRC-CURATED-REQUIRED-DOCS"
# ----------------------------------------------------------------------------

 
 # 생성될.csv의 최종 스키마.
FIELDNAMES = [
    "requirement_id",
    "application_name",
    "document_name",
    "applicable_scope",
    "requirement_marker",
    "sample_form_available",
    "source_industry_text",
    "source_id",
    "source_version",
    "is_essential", 
    "application_id",
]

 
def _sniff_delimiter(input_path: Path) -> str:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.readline()
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t").delimiter
    except csv.Error:
        return ","
 
 
def _load_rows(input_path: Path) -> list[dict[str, str]]:
    delimiter = _sniff_delimiter(input_path)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        rows = []
        for row in reader:
            # key(컬럼명)와 value(데이터) 양쪽의 줄바꿈/공백을 모두 정제
            cleaned_row = {
                _clean(k): _clean(v)
                for k, v in row.items()
                if k is not None
            }
            if any(cleaned_row.values()):
                rows.append(cleaned_row)
        return rows
 
 
def _norm_scope(applicable_scope: str, industry_text: str) -> str:
    """applicable_scope 컬럼이 비어있는 경우를 대비해 industry_text로 보정."""
    scope = _clean(applicable_scope).upper()
    if scope in {"ALL_INDUSTRIES", "MANUFACTURING"}:
        return scope
    return "ALL_INDUSTRIES" if _clean(industry_text) == "전업종" else "MANUFACTURING"
 
 
def _norm_sample_form_available(value: str | None, *, line_no: int) -> str:
    """sample_form_available은 대문자 TRUE/FALSE 표기를 그대로 유지한다 (값 변환 없음)."""
    v = _clean(value).upper()
    if v not in {"TRUE", "FALSE"}:
        raise ValueError(
            f"{line_no}행: sample_form_available 값은 TRUE/FALSE여야 합니다 (입력값: '{value}')"
        )
    return v
 
 
def _norm_is_essential(value: str | None, *, line_no: int) -> str:
    """is_essential은 Y/N 표기를 그대로 유지한다 (값 변환 없음)."""
    v = _clean(value).upper()
    if v not in {"Y", "N"}:
        raise ValueError(
            f"{line_no}행: is_essential 값은 Y/N이어야 합니다 (입력값: '{value}')"
        )
    return v
 
 
def _load_existing_output(output_path: Path) -> dict[str, dict[str, str]]:
    """이전에 생성된 processed csv를 읽어 requirement_id -> 이전 행 매핑을 만든다.
    파일이 없으면(최초 실행) 빈 딕셔너리를 반환한다."""
    if not output_path.exists():
        return {}
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["requirement_id"]: row for row in reader if row.get("requirement_id")}
 
 
def _unchanged_except_version(new_row: dict[str, str], old_row: dict[str, str]) -> bool:
    """source_version을 제외한 모든 필드가 이전 행과 동일한지 확인."""
    compare_fields = [f for f in FIELDNAMES if f != "source_version"]
    return all(new_row.get(f, "") == old_row.get(f, "") for f in compare_fields)
 
 
def generate(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    *,
    source_id: str = SOURCE_ID,
    today_version: str | None = None,
) -> list[dict[str, str]]:
    """
    각 행의 source_version은 "그 행이 마지막으로 신규 추가되거나 내용이 바뀐 날짜"를 의미한다.
    - 이전 processed 결과에 동일한 requirement_id + 동일한 나머지 값이 있으면 -> 이전 날짜 유지
    - 신규 행이거나 값이 하나라도 바뀌었으면 -> 오늘 날짜(YYYYMMDD)로 갱신
    today_version을 None으로 두면 실행 시점의 오늘 날짜를 자동으로 쓴다.
    테스트에서 날짜를 고정하고 싶을 때만 명시적으로 넘기면 된다.
    """
    resolved_today = today_version or date.today().strftime("%Y%m%d")
    existing_by_id = _load_existing_output(output_path)
 
    rows = _load_rows(input_path)
 
    output_rows: list[dict[str, str]] = []
    seen_ids: dict[str, tuple[str, str]] = {}  # requirement_id -> (application_name, document_name)
    app_id_by_name: dict[str, str] = {}  # application_name -> application_id (일관성 검사용)
 
    for line_no, row in enumerate(rows, start=2):  # 헤더가 1행이므로 데이터는 2행부터
        application_name = _clean(row.get("application_name"))
        document_name = _clean(row.get("document_name"))
        source_industry_text = _clean(row.get("source_industry_text"))
        application_id = _clean(row.get("application_id"))
 
        if not application_name or not document_name:
            raise ValueError(f"{line_no}행: application_name/document_name이 비어있습니다.")
 
        if application_id:
            prev_app_id = app_id_by_name.get(application_name)
            if prev_app_id is None:
                app_id_by_name[application_name] = application_id
            elif prev_app_id != application_id:
                raise ValueError(
                    f"{line_no}행: '{application_name}'의 application_id가 일관되지 않습니다 "
                    f"(기존: {prev_app_id}, 신규: {application_id})"
                )
 
        # ingestion.py의 transform_required_documents()와 완전히 동일한 규칙.
        # application_id는 해시 입력에서 제외 (공식데이터와 똑같이)
        requirement_id = stable_id(
            "REQ", application_name, document_name, source_industry_text
        )
 
        if requirement_id in seen_ids:
            prev_app, prev_doc = seen_ids[requirement_id]
            if prev_app != application_name or prev_doc != document_name:
                raise ValueError(
                    f"{line_no}행: 해시 충돌 의심 - {requirement_id} 가 서로 다른 항목에서 재사용됨 "
                    f"(기존: {prev_app}/{prev_doc}, 신규: {application_name}/{document_name})"
                )
            continue  # 완전 동일한 행 중복 -> 제거
        seen_ids[requirement_id] = (application_name, document_name)
 
        candidate_row = {
            "requirement_id": requirement_id,
            "application_name": application_name,
            "document_name": document_name,
            "applicable_scope": _norm_scope(
                row.get("applicable_scope", ""), source_industry_text
            ),
            "requirement_marker": _clean(row.get("requirement_marker"))
            or "OFFICIAL_CONFIRMATION_REQUIRED",
            "sample_form_available": _norm_sample_form_available(
                row.get("sample_form_available"), line_no=line_no
            ),
            "source_industry_text": source_industry_text,
            "source_id": source_id,
            "source_version": "",  # 아래에서 신규/변경 여부 판단 후 채운다
            "is_essential": _norm_is_essential(
                row.get("is_essential"), line_no=line_no
            ),
            "application_id": application_id,
        }
 
        old_row = existing_by_id.get(requirement_id)
        if old_row is not None and _unchanged_except_version(candidate_row, old_row):
            candidate_row["source_version"] = old_row["source_version"]
        else:
            candidate_row["source_version"] = resolved_today
 
        output_rows.append(candidate_row)
 
    output_rows.sort(key=lambda item: (item["application_name"], item["document_name"]))
 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
 
    return output_rows
 
 
def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"curated 원본 파일을 찾을 수 없습니다: {INPUT_PATH}")
    rows = generate()
    print(f"완료: {len(rows)}행 -> {OUTPUT_PATH}")
 
 
if __name__ == "__main__":
    main()
